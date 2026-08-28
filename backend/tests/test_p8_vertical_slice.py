from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import SessionLocal, init_db
from app.main import app, get_ward_risk_slice
from app.models.forecast import Forecast
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.seed import seed_database
from app.services.risk_engine import (
    compute_base_heat_score,
    compute_composite_risk,
    categorize_risk,
)
from app.services.thermal_index import heat_index, wbgt


class TestP8VerticalSlice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.db = SessionLocal()
        cls.client = TestClient(app)

        # Seed 3 distinct calendar days of WeatherReading records for ward 1
        cls.ward_id = 1
        cls.db.query(WeatherReading).filter(WeatherReading.ward_id == cls.ward_id).delete()
        cls.db.query(Forecast).filter(Forecast.ward_id == cls.ward_id).delete()
        # Also clean ward 2 weather readings so it acts as an unseeded ward
        cls.db.query(WeatherReading).filter(WeatherReading.ward_id == 2).delete()
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

    def test_ward_1_vertical_slice_payload_structure(self):
        """Verify GET /api/wards/1 vertical slice response conforms to required JSON contract."""
        payload = get_ward_risk_slice(1, self.db)

        # 1. Ward block assertions
        self.assertIn("ward", payload)
        ward = payload["ward"]
        self.assertEqual(ward["id"], 1)
        self.assertEqual(ward["ward_number"], "BBSR-01")
        self.assertEqual(ward["name"], "Bhubaneswar Zone 01")
        self.assertIsInstance(ward["elderly_pct"], (int, float))
        self.assertIsInstance(ward["outdoor_worker_pct"], (int, float))
        self.assertIsInstance(ward["vulnerability_index"], float)
        self.assertTrue(0.0 <= ward["vulnerability_index"] <= 1.0)

        # 2. Current conditions assertions
        self.assertIn("current", payload)
        curr = payload["current"]
        required_current_keys = {
            "temp_c",
            "humidity_pct",
            "wind_kmh",
            "solar_radiation",
            "heat_index",
            "wbgt",
            "base_score",
            "vulnerability_adjustment",
            "composite_score",
            "risk_category",
        }
        self.assertTrue(required_current_keys.issubset(curr.keys()))
        self.assertIsInstance(curr["temp_c"], (int, float))
        self.assertIsInstance(curr["humidity_pct"], (int, float))
        self.assertIsInstance(curr["heat_index"], (int, float))
        self.assertIsInstance(curr["wbgt"], (int, float))
        self.assertIsInstance(curr["composite_score"], (int, float))
        self.assertIn(
            curr["risk_category"],
            {"Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"},
        )

        # 3. Forecast block assertions (populated ML multi-horizon predictions)
        self.assertIn("forecast", payload)
        forecast = payload["forecast"]
        self.assertIsInstance(forecast, list)
        self.assertEqual(len(forecast), 3)
        for day in forecast:
            self.assertIn("date", day)
            self.assertIn("predicted_heat_index", day)
            self.assertIn("predicted_risk_category", day)
            self.assertIsInstance(day["date"], str)
            self.assertIsInstance(day["predicted_heat_index"], (int, float))
            self.assertIsInstance(day["predicted_risk_category"], str)
            self.assertIn(
                day["predicted_risk_category"],
                {"Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"},
            )

        # 4. Advisory block assertions
        self.assertIn("advisory", payload)
        adv = payload["advisory"]
        self.assertEqual(adv["risk_category"], curr["risk_category"])
        self.assertIn("headline", adv)
        self.assertIn("general_public", adv)
        self.assertIn("outdoor_workers", adv)

    def test_ward_forecast_graceful_fallback_on_insufficient_data(self):
        """Verify endpoint returns 200 with empty forecast [] when historical data is missing."""
        with self.assertLogs("app.main", level="WARNING") as cm:
            payload = get_ward_risk_slice(2, self.db)

        self.assertIn("forecast", payload)
        self.assertEqual(payload["forecast"], [])
        self.assertTrue(
            any("Failed to generate ML forecast for ward 2" in msg for msg in cm.output),
            f"Expected warning log for ward 2 forecast failure, got: {cm.output}",
        )

    def test_ward_forecast_graceful_fallback_on_exception(self):
        """Verify endpoint returns 200 with empty forecast [] when predict_forecast raises an exception."""
        with patch("app.main.predict_forecast", side_effect=RuntimeError("Model file corrupted")):
            with self.assertLogs("app.main", level="WARNING") as cm:
                payload = get_ward_risk_slice(1, self.db)

            self.assertIn("forecast", payload)
            self.assertEqual(payload["forecast"], [])
            self.assertTrue(
                any("Model file corrupted" in msg for msg in cm.output),
                f"Expected warning log containing error message, got: {cm.output}",
            )

    def test_ward_forecast_graceful_fallback_on_empty_prediction(self):
        """Verify endpoint returns 200 with empty forecast [] when predict_forecast returns empty list."""
        with patch("app.main.predict_forecast", return_value=[]):
            payload = get_ward_risk_slice(1, self.db)
            self.assertIn("forecast", payload)
            self.assertEqual(payload["forecast"], [])

    def test_get_ward_endpoint_via_http_client(self):
        """Verify HTTP GET /api/wards/{id} returns 200 and matches expected payload shape."""
        # Test seeded ward 1 (populated forecast)
        resp1 = self.client.get("/api/wards/1")
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertIn("ward", data1)
        self.assertIn("current", data1)
        self.assertIn("forecast", data1)
        self.assertIn("advisory", data1)
        self.assertIsInstance(data1["forecast"], list)
        self.assertEqual(len(data1["forecast"]), 3)
        self.assertIn("date", data1["forecast"][0])
        self.assertIn("predicted_heat_index", data1["forecast"][0])
        self.assertIn("predicted_risk_category", data1["forecast"][0])

        # Test unseeded ward 2 (fallback empty forecast array)
        resp2 = self.client.get("/api/wards/2")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertIn("ward", data2)
        self.assertIn("forecast", data2)
        self.assertEqual(data2["forecast"], [])

    def test_nonexistent_ward_returns_404(self):
        """Verify requesting non-existent ward ID raises HTTP 404."""
        with self.assertRaises(HTTPException) as ctx:
            get_ward_risk_slice(99999, self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_risk_engine_integration_math(self):
        """Verify mathematical integrity of base score, amplification cap, and risk bands."""
        # 1. Normal (HI < 27 C)
        score_normal = compute_base_heat_score(20.0)
        self.assertEqual(score_normal, 14.81)

        # 2. Caution (27 - 32 C)
        score_caution = compute_base_heat_score(30.0)
        self.assertEqual(score_caution, 32.0)

        # 3. Extreme Caution (32 - 39 C)
        score_ext_caution = compute_base_heat_score(35.5)
        self.assertEqual(score_ext_caution, 50.0)

        # 4. Danger (39 - 51 C)
        score_danger = compute_base_heat_score(45.0)
        self.assertEqual(score_danger, 72.5)

        # 5. Extreme Danger (>= 51 C)
        score_ext_danger = compute_base_heat_score(58.5)
        self.assertEqual(score_ext_danger, 92.5)

        # Composite score amplification with vulnerability index 0.3328 (BBSR-01)
        res = compute_composite_risk(heat_index_c=35.5, vulnerability_index=0.3328)
        self.assertEqual(res["base_heat_score"], 50.0)
        expected_composite = round(50.0 * (1.0 + 0.3 * 0.3328), 2)  # 54.99
        self.assertEqual(res["composite_score"], expected_composite)
        self.assertEqual(res["vulnerability_adjustment"], round(expected_composite - 50.0, 2))

    def test_risk_map_geojson_feature_collection(self):
        """Verify GET /api/risk-map returns GeoJSON FeatureCollection with 10 wards."""
        from app.main import get_risk_map
        result = get_risk_map(self.db)
        self.assertEqual(result.get("type"), "FeatureCollection")
        features = result.get("features", [])
        self.assertEqual(len(features), 10)

        for feat in features:
            self.assertEqual(feat.get("type"), "Feature")
            self.assertTrue(feat.get("id").startswith("BBSR-"))
            props = feat.get("properties", {})
            self.assertIn("id", props)
            self.assertIn("name", props)
            self.assertIn("vulnerability_index", props)
            self.assertTrue(0.0 <= props["vulnerability_index"] <= 1.0)
            geom = feat.get("geometry", {})
            self.assertEqual(geom.get("type"), "Point")
            coords = geom.get("coordinates", [])
            self.assertEqual(len(coords), 2)
            lon, lat = coords
            self.assertTrue(85.0 <= lon <= 86.5)
            self.assertTrue(20.0 <= lat <= 21.0)


if __name__ == "__main__":
    unittest.main()

