"""Scheduled weather ingestion service for SIH Heat Wave Early Warning System.

Periodically loops across all municipal wards in the SQLite database, fetches live
weather readings from Open-Meteo, computes thermal stress metrics (Heat Index, WBGT),
evaluates composite risk scores, and persists records to weather_readings and risk_scores tables.
Also provides manual on-demand execution for demonstration control via POST /api/refresh.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.risk import RiskScore
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.services.risk_engine import compute_composite_risk
from app.services.thermal_index import heat_index, wbgt
from app.services.weather_fetcher import WeatherFetcherError, fetch_weather

logger = logging.getLogger(__name__)

# Global in-process scheduler instance
_scheduler: Optional[BackgroundScheduler] = None


def ingest_all_wards_weather(db: Optional[Session] = None) -> Dict[str, Any]:
    """Ingest real-time weather and calculate risk scores for all wards in the database.

    Args:
        db: Optional existing SQLAlchemy session. If None, creates and manages a new SessionLocal.

    Returns:
        Summary dictionary with execution metadata, counts, and any errors encountered:
        {
            "status": "ok" | "partial" | "error",
            "timestamp": ISO-8601 string,
            "wards_processed": int,
            "readings_inserted": int,
            "risk_scores_inserted": int,
            "errors": List[str]
        }
    """
    close_db_on_exit = False
    if db is None:
        db = SessionLocal()
        close_db_on_exit = True

    wards_processed = 0
    readings_inserted = 0
    risk_scores_inserted = 0
    errors: List[str] = []

    try:
        wards = db.query(Ward).order_by(Ward.id).all()
        if not wards:
            logger.warning("No wards found in database for scheduled weather ingestion.")
            return {
                "status": "ok",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "wards_processed": 0,
                "readings_inserted": 0,
                "risk_scores_inserted": 0,
                "errors": ["No wards found in database."],
            }

        now_utc = datetime.now(timezone.utc)

        for ward in wards:
            if ward.latitude is None or ward.longitude is None:
                err_msg = f"Ward {ward.ward_number} (ID: {ward.id}) is missing geographic coordinates."
                logger.error(err_msg)
                errors.append(err_msg)
                continue

            try:
                weather_data = fetch_weather(ward.latitude, ward.longitude)
            except (WeatherFetcherError, ValueError, Exception) as exc:
                err_msg = f"Failed to fetch weather for ward {ward.ward_number}: {exc}"
                logger.error(err_msg)
                errors.append(err_msg)
                continue

            temp_c = weather_data["temp_c"]
            humidity_pct = weather_data["humidity_pct"]
            wind_kmh = weather_data["wind_kmh"]
            solar_radiation = weather_data.get("solar_radiation")

            # 1. Compute thermal stress indices
            hi_c = heat_index(temp_c, humidity_pct)
            wbgt_c = wbgt(temp_c, humidity_pct, solar_radiation)

            # 2. Compute multi-factor composite risk
            risk_profile = compute_composite_risk(
                heat_index_c=hi_c,
                vulnerability_index=ward.vulnerability_index,
            )

            # 3. Create WeatherReading record
            weather_reading = WeatherReading(
                ward_id=ward.id,
                timestamp=now_utc,
                temperature=temp_c,
                relative_humidity=humidity_pct,
                wind_speed=wind_kmh,
                solar_radiation=solar_radiation,
                heat_index=hi_c,
                wet_bulb_temp=wbgt_c,
                apparent_temp=hi_c,
            )
            db.add(weather_reading)

            # 4. Create RiskScore record
            risk_score_entry = RiskScore(
                ward_id=ward.id,
                timestamp=now_utc,
                hazard_score=risk_profile["base_heat_score"],
                exposure_score=risk_profile.get("vulnerability_adjustment", 0.0),
                vulnerability_score=ward.vulnerability_index,
                risk_score=risk_profile["composite_score"],
                risk_level=risk_profile["risk_category"],
            )
            db.add(risk_score_entry)

            wards_processed += 1
            readings_inserted += 1
            risk_scores_inserted += 1

        db.commit()
        logger.info(
            "Weather ingestion complete: %d wards processed, %d readings, %d risk scores inserted.",
            wards_processed,
            readings_inserted,
            risk_scores_inserted,
        )

    except Exception as exc:
        db.rollback()
        logger.exception("Database transaction failed during weather ingestion: %s", exc)
        errors.append(f"Database error: {exc}")
    finally:
        if close_db_on_exit:
            db.close()

    status_str = "ok" if not errors else ("partial" if wards_processed > 0 else "error")

    return {
        "status": status_str,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wards_processed": wards_processed,
        "readings_inserted": readings_inserted,
        "risk_scores_inserted": risk_scores_inserted,
        "errors": errors,
    }


def get_scheduler() -> BackgroundScheduler:
    """Retrieve or instantiate the global BackgroundScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler(interval_minutes: int = 30) -> BackgroundScheduler:
    """Initialize and start the in-process background weather ingestion job.

    Args:
        interval_minutes: Interval in minutes between scheduled runs (default: 30m).

    Returns:
        The running BackgroundScheduler instance.
    """
    scheduler = get_scheduler()

    # Schedule weather ingestion interval job
    scheduler.add_job(
        ingest_all_wards_weather,
        trigger="interval",
        minutes=interval_minutes,
        id="weather_ingestion_job",
        name="Multi-Ward Weather Ingestion",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started: weather ingestion scheduled every %d minutes.", interval_minutes)

    return scheduler


def shutdown_scheduler() -> None:
    """Gracefully shutdown the in-process background scheduler."""
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("APScheduler shutdown complete.")
        _scheduler = None
