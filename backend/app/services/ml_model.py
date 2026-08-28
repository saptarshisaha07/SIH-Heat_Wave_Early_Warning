"""ML Model inference and multi-horizon forecast service for SIH Heat Wave Early Warning System.

Loads the multi-output RandomForestRegressor model from ml/model.pkl, extracts daily-aggregated
lag features from WeatherReading records, predicts t+1, t+2, t+3 Heat Index, maps to 5-band
risk categories, and stores Forecast rows in the database.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend directory to sys.path to support direct execution
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import joblib
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.forecast import Forecast
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.services.risk_engine import categorize_risk, compute_base_heat_score

logger = logging.getLogger(__name__)

# Default relative paths to model artifacts
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_MODEL_PATH = BASE_DIR / "ml" / "model.pkl"

# Module-level cache for model artifact bundle
_CACHED_MODEL_BUNDLE: Optional[Dict[str, Any]] = None


def load_ml_model(model_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load and cache the trained ML model artifact bundle using joblib.

    Loads the artifact bundle once and caches it in memory for subsequent inference calls.

    Args:
        model_path: Optional path to ml/model.pkl artifact.

    Returns:
        Dictionary containing 'model', 'feature_columns', 'ward_ids', 'target_columns', etc.

    Raises:
        FileNotFoundError: If the model.pkl file does not exist.
        RuntimeError: If the bundle format is invalid.
    """
    global _CACHED_MODEL_BUNDLE
    if _CACHED_MODEL_BUNDLE is not None and model_path is None:
        return _CACHED_MODEL_BUNDLE

    target_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    if not target_path.exists():
        raise FileNotFoundError(
            f"Trained ML model artifact not found at: {target_path.resolve()}. "
            "Please train the model using ml/train_model.py first."
        )

    try:
        bundle = joblib.load(target_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load ML model artifact from {target_path}: {exc}") from exc

    if not isinstance(bundle, dict) or "model" not in bundle or "feature_columns" not in bundle:
        raise RuntimeError(
            f"Invalid model artifact structure in {target_path}. Expected dictionary bundle with 'model' and 'feature_columns'."
        )

    if model_path is None:
        _CACHED_MODEL_BUNDLE = bundle

    logger.info("Loaded ML model artifact successfully from %s", target_path)
    return bundle


def get_recent_features(db: Session, ward_id: int) -> pd.DataFrame:
    """Query and construct the 18-element feature row using daily-aggregated weather stats.

    1. Validates that ward_id exists in the database.
    2. Groups weather_readings by calendar date (func.date(WeatherReading.timestamp)).
    3. Computes daily mean temperature, daily mean relative humidity, and daily max wind speed.
    4. Takes the 3 most recent distinct calendar days (ordered by date desc):
         - Day 0 (t):   temp_mean_lag0, humidity_lag0, wind_speed_lag0, month, day_of_year
         - Day 1 (t-1): temp_mean_lag1, humidity_lag1
         - Day 2 (t-2): temp_mean_lag2
    5. Dynamically builds the one-hot ward indicators from bundle['feature_columns'].
    6. Returns a 1-row DataFrame strictly ordered matching bundle['feature_columns'].

    Args:
        db: Active SQLAlchemy database session.
        ward_id: Integer primary key ID of the ward (e.g. 1 for BBSR-01).

    Returns:
        pd.DataFrame of shape (1, 18) with columns matching the model bundle's feature_columns.

    Raises:
        ValueError: If the ward does not exist, fewer than 3 distinct daily aggregates exist,
                    or required daily aggregate metrics are missing/null.
    """
    # 1. Validate ward existence
    ward = db.query(Ward).filter(Ward.id == ward_id).first()
    if not ward:
        raise ValueError(f"Ward with id {ward_id} not found in database.")

    # 2. Query daily-aggregated stats for the last 3 distinct calendar days
    daily_stats = (
        db.query(
            func.date(WeatherReading.timestamp).label("reading_date"),
            func.avg(WeatherReading.temperature).label("temp_mean"),
            func.avg(WeatherReading.relative_humidity).label("humidity_mean"),
            func.max(WeatherReading.wind_speed).label("wind_speed_max"),
        )
        .filter(WeatherReading.ward_id == ward_id)
        .group_by(func.date(WeatherReading.timestamp))
        .order_by(func.date(WeatherReading.timestamp).desc())
        .limit(3)
        .all()
    )

    if len(daily_stats) < 3:
        raise ValueError(
            f"Insufficient historical data for ward {ward_id} ({ward.ward_number}). "
            f"Found {len(daily_stats)} distinct days of readings, but at least 3 daily aggregates are required."
        )

    # daily_stats is sorted descending: [day_t (lag0), day_t_minus_1 (lag1), day_t_minus_2 (lag2)]
    d0_date_str, d0_temp, d0_hum, d0_wind = daily_stats[0]
    d1_date_str, d1_temp, d1_hum, _ = daily_stats[1]
    d2_date_str, d2_temp, _, _ = daily_stats[2]

    # Explicit None-guards for required lag features
    if d0_temp is None:
        raise ValueError(
            f"Missing temperature reading for ward {ward_id} ({ward.ward_number}) on {d0_date_str} (day t / lag0)."
        )
    if d0_hum is None:
        raise ValueError(
            f"Missing relative humidity reading for ward {ward_id} ({ward.ward_number}) on {d0_date_str} (day t / lag0)."
        )
    if d1_temp is None:
        raise ValueError(
            f"Missing temperature reading for ward {ward_id} ({ward.ward_number}) on {d1_date_str} (day t-1 / lag1)."
        )
    if d1_hum is None:
        raise ValueError(
            f"Missing relative humidity reading for ward {ward_id} ({ward.ward_number}) on {d1_date_str} (day t-1 / lag1)."
        )
    if d2_temp is None:
        raise ValueError(
            f"Missing temperature reading for ward {ward_id} ({ward.ward_number}) on {d2_date_str} (day t-2 / lag2)."
        )

    # Parse reference date (day t)
    d0_date = datetime.strptime(d0_date_str, "%Y-%m-%d").date()

    # Base features
    features: Dict[str, Any] = {
        "temp_mean_lag0": float(d0_temp),
        "temp_mean_lag1": float(d1_temp),
        "temp_mean_lag2": float(d2_temp),
        "humidity_lag0": float(d0_hum),
        "humidity_lag1": float(d1_hum),
        "wind_speed_lag0": float(d0_wind) if d0_wind is not None else 0.0,
        "month": int(d0_date.month),
        "day_of_year": int(d0_date.timetuple().tm_yday),
    }

    # 3. Dynamically populate one-hot ward indicators from model bundle's feature columns
    bundle = load_ml_model()
    model_feature_cols: List[str] = bundle["feature_columns"]

    for col in model_feature_cols:
        if col.startswith("ward_id_"):
            target_ward_code = col.replace("ward_id_", "", 1)
            features[col] = 1 if ward.ward_number == target_ward_code else 0

    # Ensure all required model columns are present and correctly ordered
    missing_cols = [c for c in model_feature_cols if c not in features]
    if missing_cols:
        raise ValueError(f"Failed to build all required feature columns. Missing: {missing_cols}")

    return pd.DataFrame([features])[model_feature_cols]


def predict_forecast(db: Session, ward_id: int) -> List[Dict[str, Any]]:
    """Predict Heat Index for t+1, t+2, t+3, record Forecast rows in DB, and return structured results.

    Workflow:
    1. Extracts recent daily-aggregated lag features via get_recent_features(db, ward_id).
    2. Runs multi-output prediction with the cached RandomForestRegressor model.
    3. Categorizes each predicted Heat Index using risk_engine.py thresholds.
    4. Inserts Forecast rows into the DB for today + 1, + 2, and + 3 days.
    5. Commits the transaction and returns a list of dictionaries matching teammate endpoint contract.

    Args:
        db: Active SQLAlchemy database session.
        ward_id: Integer primary key ID of the ward.

    Returns:
        List of dicts:
        [
            {"date": "YYYY-MM-DD", "predicted_heat_index": float, "predicted_risk_category": str},
            ...
        ]

    Raises:
        ValueError: If ward doesn't exist, insufficient data exists, or model fails.
    """
    ward = db.query(Ward).filter(Ward.id == ward_id).first()
    if not ward:
        raise ValueError(f"Ward with id {ward_id} not found in database.")

    # 1. Build features
    features_df = get_recent_features(db, ward_id)

    # 2. Load model and predict
    bundle = load_ml_model()
    model = bundle["model"]
    preds = model.predict(features_df)

    if preds.ndim != 2 or preds.shape[1] != 3:
        raise RuntimeError(f"Unexpected prediction output shape: {preds.shape}. Expected (1, 3).")

    hi_t1 = float(preds[0, 0])
    hi_t2 = float(preds[0, 1])
    hi_t3 = float(preds[0, 2])
    predicted_his = [hi_t1, hi_t2, hi_t3]

    # Reference base date is today (UTC date)
    today = datetime.utcnow().date()
    forecast_now = datetime.utcnow()

    forecast_results: List[Dict[str, Any]] = []

    for idx, pred_hi_raw in enumerate(predicted_his, start=1):
        target_date = today + timedelta(days=idx)
        target_dt = datetime.combine(target_date, datetime.min.time())
        pred_hi = round(pred_hi_raw, 2)

        # 3. Categorize using authoritative risk_engine functions
        heat_score = compute_base_heat_score(pred_hi)
        cat_meta = categorize_risk(heat_score)
        risk_category = cat_meta["category"]

        # 4. Insert Forecast DB row
        # NOTE: predicted_temp has a NOT NULL constraint on the Forecast table schema.
        # The ML model predicts Heat Index directly, not atmospheric dry-bulb temperature.
        # We populate predicted_temp with predicted_heat_index as a proxy placeholder
        # solely to satisfy the database schema's NOT NULL constraint. Downstream API
        # and frontend consumers must use predicted_heat_index.
        forecast_record = Forecast(
            ward_id=ward.id,
            forecast_time=forecast_now,
            target_time=target_dt,
            predicted_temp=pred_hi,
            predicted_heat_index=pred_hi,
            predicted_risk_level=risk_category,
        )
        db.add(forecast_record)

        forecast_results.append(
            {
                "date": target_date.strftime("%Y-%m-%d"),
                "predicted_heat_index": pred_hi,
                "predicted_risk_category": risk_category,
            }
        )

    # 5. Commit database transaction
    db.commit()

    return forecast_results


if __name__ == "__main__":
    # Configure root logger for standalone test execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("\n" + "=" * 70)
    print("TESTING ML MODEL SERVICE (backend/app/services/ml_model.py)")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Check ward 1
        test_ward_id = 1
        ward = db.query(Ward).filter(Ward.id == test_ward_id).first()
        if not ward:
            print(f"Error: Ward {test_ward_id} not found in database. Run app/seed.py first.")
            sys.exit(1)

        print(f"Target Ward: ID={ward.id}, Ward Number={ward.ward_number}, Name={ward.name}")

        # Check existing weather readings count
        reading_count = db.query(WeatherReading).filter(WeatherReading.ward_id == test_ward_id).count()
        print(f"Existing WeatherReading rows for ward {test_ward_id}: {reading_count}")

        # If fewer than 3 days of readings exist, seed realistic test readings for 3 consecutive days
        distinct_days = (
            db.query(func.date(WeatherReading.timestamp))
            .filter(WeatherReading.ward_id == test_ward_id)
            .distinct()
            .count()
        )

        if distinct_days < 3:
            print(f"Seeding 3 days of test WeatherReading records for ward {test_ward_id}...")
            today = datetime.utcnow()
            sample_weather = [
                {"days_ago": 2, "temp": 32.5, "hum": 65.0, "wind": 4.2, "solar": 650.0},
                {"days_ago": 1, "temp": 34.0, "hum": 70.0, "wind": 5.1, "solar": 720.0},
                {"days_ago": 0, "temp": 35.8, "hum": 68.0, "wind": 4.8, "solar": 780.0},
            ]
            for sw in sample_weather:
                reading_time = today - timedelta(days=sw["days_ago"])
                reading = WeatherReading(
                    ward_id=test_ward_id,
                    timestamp=reading_time,
                    temperature=sw["temp"],
                    relative_humidity=sw["hum"],
                    wind_speed=sw["wind"],
                    solar_radiation=sw["solar"],
                )
                db.add(reading)
            db.commit()
            print("Successfully inserted sample weather readings.")

        # Test feature extraction
        print("\n1. Testing get_recent_features(db, ward_id)...")
        features_df = get_recent_features(db, test_ward_id)
        print(f"   Features Shape: {features_df.shape}")
        print("   Features DataFrame:")
        print(features_df.to_string(index=False))

        # Test forecast prediction and persistence
        print("\n2. Testing predict_forecast(db, ward_id)...")
        results = predict_forecast(db, test_ward_id)
        print(f"   Forecast Output ({len(results)} horizons):")
        for item in results:
            print(f"     - Date: {item['date']} | Heat Index: {item['predicted_heat_index']} °C | Risk: {item['predicted_risk_category']}")

        # Verify database Forecast records
        recent_forecasts = (
            db.query(Forecast)
            .filter(Forecast.ward_id == test_ward_id)
            .order_by(Forecast.id.desc())
            .limit(3)
            .all()
        )
        print(f"\n3. Verified {len(recent_forecasts)} Forecast records saved in SQLite DB:")
        for fc in reversed(recent_forecasts):
            print(f"     Forecast ID: {fc.id} | Target: {fc.target_time} | HI: {fc.predicted_heat_index} °C | Risk: {fc.predicted_risk_level}")

        print("\n" + "=" * 70)
        print("ALL ML MODEL SERVICE TESTS PASSED SUCCESSFULLY!")
        print("=" * 70 + "\n")
    finally:
        db.close()
