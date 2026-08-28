"""One-off weather history backfill script for SIH Heat Wave Early Warning System.

Fetches the last N complete calendar days (default: 5) of historical atmospheric data
from Open-Meteo Archive API (https://archive-api.open-meteo.com/v1/archive) for each
municipal ward, normalizes the weather observations, computes thermal stress and
composite risk scores, and inserts backdated rows into `weather_readings` and `risk_scores`.

Avoids duplicate entries by inspecting existing dates for each ward prior to insertion.
"""

from __future__ import annotations

import argparse
import datetime
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.models.risk import RiskScore
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.services.risk_engine import compute_composite_risk
from app.services.thermal_index import heat_index, wbgt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_weather_history")

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_ward_historical_weather(
    lat: float,
    lon: float,
    start_date: datetime.date,
    end_date: datetime.date,
    max_retries: int = 3,
    timeout: int = 15,
) -> Optional[Dict[str, Any]]:
    """Fetch daily weather metrics from Open-Meteo Historical Archive API.

    Args:
        lat: Ward centroid latitude.
        lon: Ward centroid longitude.
        start_date: Earliest calendar date.
        end_date: Latest calendar date.
        max_retries: Maximum HTTP retry attempts with exponential backoff.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary containing 'time', 'temperature_2m_mean', 'relative_humidity_2m_mean',
        'wind_speed_10m_max', 'shortwave_radiation_sum', or None on failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily": [
            "temperature_2m_mean",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
            "shortwave_radiation_sum",
        ],
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(
                "Querying Open-Meteo Archive (lat=%.4f, lon=%.4f, attempt=%d/%d)...",
                lat,
                lon,
                attempt,
                max_retries,
            )
            resp = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict):
                logger.warning("Invalid non-dict response from Open-Meteo for lat=%.4f, lon=%.4f", lat, lon)
                return None

            daily = data.get("daily")
            if not isinstance(daily, dict) or "time" not in daily:
                logger.warning("Missing 'daily' object or 'time' series for lat=%.4f, lon=%.4f", lat, lon)
                return None

            return daily
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            logger.warning(
                "HTTP/Network error fetching archive for lat=%.4f, lon=%.4f (attempt %d/%d): %s",
                lat,
                lon,
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

    logger.error("Failed to fetch historical weather after %d attempts for lat=%.4f, lon=%.4f: %s", max_retries, lat, lon, last_exc)
    return None


def backfill_weather_history(
    days: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Backfill weather_readings and risk_scores for all wards over the last N days.

    Args:
        days: Number of complete past calendar days to backfill (default: 5).
        dry_run: If True, executes queries and calculations without writing to the DB.

    Returns:
        Summary statistics dictionary.
    """
    init_db()
    db: Session = SessionLocal()

    today = datetime.date.today()
    # Target last N complete calendar days ending yesterday
    end_date = today - datetime.timedelta(days=1)
    start_date = today - datetime.timedelta(days=days)

    logger.info("=" * 70)
    logger.info("WEATHER HISTORY BACKFILL MAINTENANCE JOB")
    logger.info("Target Date Range: %s to %s (%d complete calendar days)", start_date, end_date, days)
    logger.info("Dry Run Mode: %s", dry_run)
    logger.info("=" * 70)

    try:
        wards: List[Ward] = db.query(Ward).order_by(Ward.id).all()
        if not wards:
            logger.error("No wards found in database. Run app/seed.py first.")
            return {"status": "error", "message": "No wards found in database."}

        ward_results: List[Dict[str, Any]] = []
        total_readings_inserted = 0
        total_risk_scores_inserted = 0
        total_days_skipped = 0

        for ward in wards:
            logger.info("Processing Ward %d (%s: %s)...", ward.id, ward.ward_number, ward.name)

            if ward.latitude is None or ward.longitude is None:
                logger.error("Ward %d (%s) missing latitude/longitude coordinates. Skipping.", ward.id, ward.ward_number)
                continue

            # Query existing distinct calendar dates for this ward to prevent duplicate insertions
            existing_dates: Set[str] = set(
                row[0]
                for row in db.query(func.date(WeatherReading.timestamp))
                .filter(WeatherReading.ward_id == ward.id)
                .distinct()
                .all()
                if row[0] is not None
            )

            # Fetch daily historical observations from Open-Meteo Archive API
            daily_data = fetch_ward_historical_weather(
                lat=ward.latitude,
                lon=ward.longitude,
                start_date=start_date,
                end_date=end_date,
            )

            if not daily_data:
                logger.error("Could not obtain historical data for ward %d (%s).", ward.id, ward.ward_number)
                continue

            times = daily_data.get("time", [])
            temp_means = daily_data.get("temperature_2m_mean", [])
            hum_means = daily_data.get("relative_humidity_2m_mean", [])
            wind_maxs = daily_data.get("wind_speed_10m_max", [])
            solar_sums = daily_data.get("shortwave_radiation_sum", [])

            ward_inserted = 0
            ward_skipped = 0

            for i, date_str in enumerate(times):
                if date_str in existing_dates:
                    logger.debug("  Date %s already exists for Ward %s. Skipping duplicate.", date_str, ward.ward_number)
                    ward_skipped += 1
                    continue

                temp_val = temp_means[i] if i < len(temp_means) else None
                hum_val = hum_means[i] if i < len(hum_means) else None
                wind_val = wind_maxs[i] if i < len(wind_maxs) else None
                solar_sum_val = solar_sums[i] if i < len(solar_sums) else None

                if temp_val is None or hum_val is None:
                    logger.warning("  Missing temperature or humidity for %s on %s. Skipping.", ward.ward_number, date_str)
                    continue

                temp_c = float(temp_val)
                humidity_pct = float(hum_val)
                wind_kmh = float(wind_val) if wind_val is not None else 0.0

                # Approximate daytime solar radiation in W/m^2 from daily MJ/m^2 sum over 12 daytime hours
                solar_w_m2: Optional[float] = (
                    round((float(solar_sum_val) * 1e6) / (12 * 3600), 1)
                    if solar_sum_val is not None
                    else None
                )

                # Compute thermal indices
                hi_c = heat_index(temp_c, humidity_pct)
                wbgt_c = wbgt(temp_c, humidity_pct, solar_w_m2)

                # Compute composite risk scores
                risk_profile = compute_composite_risk(
                    heat_index_c=hi_c,
                    vulnerability_index=ward.vulnerability_index,
                )

                # Assign realistic midday backdated timestamp (12:00:00)
                reading_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                reading_timestamp = datetime.datetime.combine(reading_date, datetime.time(12, 0, 0))

                if not dry_run:
                    # Insert WeatherReading row
                    reading_record = WeatherReading(
                        ward_id=ward.id,
                        timestamp=reading_timestamp,
                        temperature=temp_c,
                        relative_humidity=humidity_pct,
                        wind_speed=wind_kmh,
                        solar_radiation=solar_w_m2,
                        heat_index=hi_c,
                        wet_bulb_temp=wbgt_c,
                        apparent_temp=hi_c,
                    )
                    db.add(reading_record)

                    # Insert RiskScore row
                    risk_record = RiskScore(
                        ward_id=ward.id,
                        timestamp=reading_timestamp,
                        hazard_score=risk_profile["base_heat_score"],
                        exposure_score=risk_profile.get("vulnerability_adjustment", 0.0),
                        vulnerability_score=ward.vulnerability_index,
                        risk_score=risk_profile["composite_score"],
                        risk_level=risk_profile["risk_category"],
                    )
                    db.add(risk_record)

                ward_inserted += 1
                existing_dates.add(date_str)

            if not dry_run:
                db.commit()

            # Query updated distinct dates count for verification
            final_distinct_dates = (
                db.query(func.date(WeatherReading.timestamp))
                .filter(WeatherReading.ward_id == ward.id)
                .distinct()
                .count()
            )

            total_readings_inserted += ward_inserted
            total_risk_scores_inserted += ward_inserted
            total_days_skipped += ward_skipped

            ward_results.append(
                {
                    "ward_id": ward.id,
                    "ward_number": ward.ward_number,
                    "ward_name": ward.name,
                    "rows_inserted": ward_inserted,
                    "rows_skipped": ward_skipped,
                    "distinct_days_count": final_distinct_dates,
                    "ml_ready": final_distinct_dates >= 3,
                }
            )

        # Print final formatted summary table
        print("\n" + "=" * 80)
        print("WEATHER HISTORY BACKFILL SUMMARY REPORT")
        print("=" * 80)
        print(f"{'ID':<4} {'Ward Code':<10} {'Ward Name':<28} {'Inserted':<10} {'Skipped':<9} {'Total Days':<12} {'ML Ready (>=3)':<14}")
        print("-" * 80)

        all_ml_ready = True
        for res in ward_results:
            ml_status = "PASS (Ready)" if res["ml_ready"] else "FAIL (<3 days)"
            if not res["ml_ready"]:
                all_ml_ready = False
            print(
                f"{res['ward_id']:<4} {res['ward_number']:<10} {res['ward_name']:<28} "
                f"{res['rows_inserted']:<10} {res['rows_skipped']:<9} "
                f"{res['distinct_days_count']:<12} {ml_status:<14}"
            )

        print("-" * 80)
        print(f"Total Wards Processed:         {len(ward_results)}")
        print(f"Total WeatherReadings Added:   {total_readings_inserted}")
        print(f"Total RiskScores Added:        {total_risk_scores_inserted}")
        print(f"Total Existing Dates Skipped:  {total_days_skipped}")
        print(f"All Wards ML-Forecasting Ready: {'YES (All >= 3 days)' if all_ml_ready else 'NO'}")
        print("=" * 80 + "\n")

        return {
            "status": "ok",
            "total_inserted": total_readings_inserted,
            "total_skipped": total_days_skipped,
            "all_ml_ready": all_ml_ready,
            "ward_details": ward_results,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Backfill transaction failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill historical weather data for ML forecast service.")
    parser.add_argument("--days", type=int, default=5, help="Number of complete past days to backfill (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Execute without committing to database")
    args = parser.parse_args()

    backfill_weather_history(days=args.days, dry_run=args.dry_run)
