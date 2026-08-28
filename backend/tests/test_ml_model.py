"""Automated test suite for ML Model Inference & Multi-Horizon Forecast Service (backend/app/services/ml_model.py)."""

from datetime import datetime, timedelta
import os
from pathlib import Path
import sys
import unittest

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal, init_db
from app.models.forecast import Forecast
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.seed import seed_database
from app.services.ml_model import (
    get_recent_features,
    load_ml_model,
    predict_forecast,
)


class TestMLModelService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.db = SessionLocal()

        # Seed 3 distinct calendar days of WeatherReading records for ward 1
        cls.ward_id = 1
        cls.db.query(WeatherReading).filter(WeatherReading.ward_id == cls.ward_id).delete()
        cls.db.query(Forecast).filter(Forecast.ward_id == cls.ward_id).delete()
        cls.db.commit()

        today = datetime.utcnow()
        sample_weather = [
            {"days_ago": 2, "temp": 32.5, "hum": 65.0, "wind": 4.2, "solar": 650.0},
            {"days_ago": 1, "temp": 34.0, "hum": 70.0, "wind": 5.1, "solar": 720.0},
            {"days_ago": 0, "temp": 35.8, "hum": 68.0, "wind": 4.8, "solar": 780.0},
        ]
        for sw in sample_weather:
            reading_time = today - timedelta(days=sw["days_ago"])
            reading = WeatherReading(
                ward_id=cls.ward_id,
                timestamp=reading_time,
                temperature=sw["temp"],
                relative_humidity=sw["hum"],
                wind_speed=sw["wind"],
                solar_radiation=sw["solar"],
            )
            cls.db.add(reading)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_load_ml_model_cached(self):
        """Verify model bundle loads cleanly and caches across multiple calls."""
        bundle1 = load_ml_model()
        bundle2 = load_ml_model()

        self.assertIs(bundle1, bundle2, "load_ml_model must cache the bundle at module level")
        self.assertIn("model", bundle1)
        self.assertIn("feature_columns", bundle1)
        self.assertEqual(len(bundle1["feature_columns"]), 18)

    def test_02_load_ml_model_missing_file(self):
        """Verify loading from non-existent path raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_ml_model(model_path="nonexistent/path/to/model.pkl")

    def test_03_get_recent_features_nonexistent_ward(self):
        """Verify requesting features for a non-existent ward raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            get_recent_features(self.db, ward_id=99999)
        self.assertIn("Ward with id 99999 not found", str(ctx.exception))

    def test_04_get_recent_features_insufficient_data(self):
        """Verify requesting features for a ward with < 3 days of readings raises ValueError."""
        # Ward 2 has 0 readings initially
        self.db.query(WeatherReading).filter(WeatherReading.ward_id == 2).delete()
        self.db.commit()

        with self.assertRaises(ValueError) as ctx:
            get_recent_features(self.db, ward_id=2)
        self.assertIn("Insufficient historical data", str(ctx.exception))

    def test_05_get_recent_features_exact_schema_and_order(self):
        """Verify DataFrame shape, columns, and dynamic one-hot encoding."""
        bundle = load_ml_model()
        expected_cols = bundle["feature_columns"]

        features_df = get_recent_features(self.db, ward_id=1)

        self.assertEqual(features_df.shape, (1, 18))
        self.assertListEqual(list(features_df.columns), expected_cols)

        # Ward 1 is BBSR-01 -> ward_id_BBSR-01 should be 1, others 0
        self.assertEqual(features_df.iloc[0]["ward_id_BBSR-01"], 1)
        for col in expected_cols:
            if col.startswith("ward_id_") and col != "ward_id_BBSR-01":
                self.assertEqual(features_df.iloc[0][col], 0)

        # Lag features must match daily means
        self.assertEqual(features_df.iloc[0]["temp_mean_lag0"], 35.8)
        self.assertEqual(features_df.iloc[0]["temp_mean_lag1"], 34.0)
        self.assertEqual(features_df.iloc[0]["temp_mean_lag2"], 32.5)

    def test_06_predict_forecast_success_and_db_persistence(self):
        """Verify 3-day forecast generation, return payload shape, and database persistence."""
        # Clear forecasts for ward 1 before running
        self.db.query(Forecast).filter(Forecast.ward_id == 1).delete()
        self.db.commit()

        results = predict_forecast(self.db, ward_id=1)

        # 1. Verify return structure
        self.assertEqual(len(results), 3)
        valid_risk_categories = {"Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"}

        for item in results:
            self.assertIn("date", item)
            self.assertIn("predicted_heat_index", item)
            self.assertIn("predicted_risk_category", item)
            self.assertIsInstance(item["predicted_heat_index"], float)
            self.assertIn(item["predicted_risk_category"], valid_risk_categories)

        # 2. Verify Forecast rows in database
        saved_forecasts = (
            self.db.query(Forecast)
            .filter(Forecast.ward_id == 1)
            .order_by(Forecast.id.desc())
            .limit(3)
            .all()
        )
        self.assertEqual(len(saved_forecasts), 3)

        for fc in saved_forecasts:
            self.assertEqual(fc.ward_id, 1)
            self.assertIsNotNone(fc.forecast_time)
            self.assertIsNotNone(fc.target_time)
            self.assertIsNotNone(fc.predicted_temp)
            self.assertIsNotNone(fc.predicted_heat_index)
            self.assertEqual(fc.predicted_temp, fc.predicted_heat_index)
            self.assertIn(fc.predicted_risk_level, valid_risk_categories)

    def test_07_predict_forecast_nonexistent_ward(self):
        """Verify predict_forecast with non-existent ward ID raises ValueError."""
        with self.assertRaises(ValueError):
            predict_forecast(self.db, ward_id=99999)


if __name__ == "__main__":
    unittest.main()
