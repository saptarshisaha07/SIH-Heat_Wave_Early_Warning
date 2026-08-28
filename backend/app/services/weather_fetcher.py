"""Weather fetcher service for SIH Heat Wave Early Warning System.

This module retrieves live atmospheric readings and 5-day future forecasts
from the Open-Meteo Forecast API (https://api.open-meteo.com/v1/forecast),
normalizing units and payload shapes for downstream thermal index and risk engines.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger(__name__)


class WeatherFetcherError(Exception):
    """Custom exception raised when weather data cannot be fetched or parsed."""


OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(
    lat: float,
    lon: float,
    db: Optional[Any] = None,
    ward_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Fetch live weather and a 5-day forward forecast from Open-Meteo for given coordinates,
    with automatic fallback to the most recent cached reading in the database if the API is unreachable.

    Args:
        lat: Latitude between -90.0 and 90.0.
        lon: Longitude between -180.0 and 180.0.
        db: Optional SQLAlchemy Session for querying cached weather readings on network failure.
        ward_id: Optional integer ward ID to directly look up cached readings for that ward.

    Returns:
        A dictionary containing normalized weather and forecast items, plus a source indicator:
        {
            "temp_c": <float>,
            "humidity_pct": <float>,
            "wind_kmh": <float>,
            "solar_radiation": <float or None>,
            "forecast": [
                {
                    "date": "YYYY-MM-DD",
                    "temp_max_c": <float>,
                    "temp_min_c": <float>,
                    "humidity_max_pct": <float>,
                    "wind_max_kmh": <float>,
                    "solar_radiation_sum": <float or None>
                },
                ...
            ],
            "source": "live" | "cached"
        }

    Raises:
        ValueError: If coordinates are non-numeric or out of valid geographic bounds.
        WeatherFetcherError: If live fetch fails AND no cached weather readings exist in the database.
    """
    # Reject non-numeric types or booleans
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("Latitude and longitude must be numeric values, not booleans.")

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid non-numeric coordinates: lat={lat!r}, lon={lon!r}") from exc

    if not (-90.0 <= lat_f <= 90.0):
        raise ValueError(f"Latitude must be between -90.0 and 90.0. Got: {lat_f}")
    if not (-180.0 <= lon_f <= 180.0):
        raise ValueError(f"Longitude must be between -180.0 and 180.0. Got: {lon_f}")

    params = {
        "latitude": lat_f,
        "longitude": lon_f,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "shortwave_radiation",
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_max",
            "wind_speed_10m_max",
            "shortwave_radiation_sum",
        ],
        "wind_speed_unit": "kmh",
        "timezone": "auto",
        "forecast_days": 8,  # Request extra days to ensure today + 5 future days
    }

    try:
        response = requests.get(OPEN_METEO_BASE_URL, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if not isinstance(data, dict):
            raise WeatherFetcherError("Open-Meteo response must be a JSON object.")

        current = data.get("current")
        if not isinstance(current, dict):
            raise WeatherFetcherError("Missing or malformed 'current' block in Open-Meteo response.")

        temp_raw = current.get("temperature_2m")
        humidity_raw = current.get("relative_humidity_2m")
        wind_raw = current.get("wind_speed_10m")
        solar_raw = current.get("shortwave_radiation")

        if temp_raw is None or not isinstance(temp_raw, (int, float)):
            raise WeatherFetcherError(f"Invalid current temperature received: {temp_raw}")
        if humidity_raw is None or not isinstance(humidity_raw, (int, float)):
            raise WeatherFetcherError(f"Invalid current relative humidity received: {humidity_raw}")
        if wind_raw is None or not isinstance(wind_raw, (int, float)):
            raise WeatherFetcherError(f"Invalid current wind speed received: {wind_raw}")

        temp_c = float(temp_raw)
        humidity_pct = float(humidity_raw)
        wind_kmh = float(wind_raw)
        solar_radiation: Optional[float] = (
            float(solar_raw) if (solar_raw is not None and isinstance(solar_raw, (int, float))) else None
        )

        daily = data.get("daily")
        if not isinstance(daily, dict):
            raise WeatherFetcherError("Missing or malformed 'daily' block in Open-Meteo response.")

        # Determine local date of current reading to exclude today from future forecast
        current_time_str = str(current.get("time", ""))
        current_local_date = current_time_str.split("T")[0] if "T" in current_time_str else current_time_str

        dates = daily.get("time")
        temp_max_list = daily.get("temperature_2m_max")
        temp_min_list = daily.get("temperature_2m_min")
        humidity_max_list = daily.get("relative_humidity_2m_max")
        wind_max_list = daily.get("wind_speed_10m_max")
        solar_sum_list = daily.get("shortwave_radiation_sum") or []

        if not isinstance(dates, list) or not isinstance(temp_max_list, list) or not isinstance(temp_min_list, list):
            raise WeatherFetcherError("Malformed daily forecast series in Open-Meteo response.")
        if not isinstance(humidity_max_list, list) or not isinstance(wind_max_list, list):
            raise WeatherFetcherError("Malformed daily humidity/wind series in Open-Meteo response.")

        forecast_days: List[Dict[str, Any]] = []
        total_entries = min(
            len(dates),
            len(temp_max_list),
            len(temp_min_list),
            len(humidity_max_list),
            len(wind_max_list),
        )

        for i in range(total_entries):
            date_str = str(dates[i])
            # Skip current local date (today) or past dates to ensure forward forecast
            if current_local_date and date_str <= current_local_date:
                continue

            t_max = temp_max_list[i]
            t_min = temp_min_list[i]
            h_max = humidity_max_list[i]
            w_max = wind_max_list[i]
            s_sum = solar_sum_list[i] if i < len(solar_sum_list) else None

            if (
                t_max is None
                or t_min is None
                or h_max is None
                or w_max is None
                or not isinstance(t_max, (int, float))
                or not isinstance(t_min, (int, float))
                or not isinstance(h_max, (int, float))
                or not isinstance(w_max, (int, float))
            ):
                raise WeatherFetcherError(f"Malformed daily forecast values for date {date_str}")

            solar_rad_sum: Optional[float] = (
                float(s_sum) if (s_sum is not None and isinstance(s_sum, (int, float))) else None
            )

            forecast_days.append(
                {
                    "date": date_str,
                    "temp_max_c": float(t_max),
                    "temp_min_c": float(t_min),
                    "humidity_max_pct": float(h_max),
                    "wind_max_kmh": float(w_max),
                    "solar_radiation_sum": solar_rad_sum,
                }
            )

            if len(forecast_days) == 5:
                break

        if len(forecast_days) != 5:
            raise WeatherFetcherError(
                f"Expected exactly 5 forward forecast days from Open-Meteo, but extracted {len(forecast_days)}."
            )

        return {
            "temp_c": temp_c,
            "humidity_pct": humidity_pct,
            "wind_kmh": wind_kmh,
            "solar_radiation": solar_radiation,
            "forecast": forecast_days,
            "source": "live",
        }

    except (requests.RequestException, requests.Timeout, WeatherFetcherError, ValueError, KeyError, Exception) as live_exc:
        logger.warning(
            "Live weather fetch from Open-Meteo failed for lat=%s, lon=%s (%s). Attempting cached fallback from database...",
            lat_f,
            lon_f,
            live_exc,
        )

        close_session = False
        session = db
        if session is None:
            from app.db.session import SessionLocal
            session = SessionLocal()
            close_session = True

        try:
            target_ward_id = ward_id
            if target_ward_id is None:
                from app.models.ward import Ward
                matched_ward = (
                    session.query(Ward)
                    .filter(
                        Ward.latitude.isnot(None),
                        Ward.longitude.isnot(None),
                    )
                    .order_by(
                        ((Ward.latitude - lat_f) * (Ward.latitude - lat_f) + (Ward.longitude - lon_f) * (Ward.longitude - lon_f)).asc()
                    )
                    .first()
                )
                if matched_ward:
                    target_ward_id = matched_ward.id

            from app.models.weather import WeatherReading
            cached_reading = None
            if target_ward_id is not None:
                cached_reading = (
                    session.query(WeatherReading)
                    .filter(WeatherReading.ward_id == target_ward_id)
                    .order_by(WeatherReading.timestamp.desc(), WeatherReading.id.desc())
                    .first()
                )
            else:
                cached_reading = (
                    session.query(WeatherReading)
                    .order_by(WeatherReading.timestamp.desc(), WeatherReading.id.desc())
                    .first()
                )

            if cached_reading is None:
                logger.error(
                    "No cached weather readings found in database for ward ID %s (lat=%s, lon=%s). Unrecoverable weather fetch failure.",
                    target_ward_id,
                    lat_f,
                    lon_f,
                )
                raise WeatherFetcherError(
                    f"Open-Meteo API unreachable ({live_exc}) and no cached weather readings exist for ward ID {target_ward_id} (lat={lat_f}, lon={lon_f})."
                ) from live_exc

            from app.models.forecast import Forecast
            cached_forecasts: List[Dict[str, Any]] = []
            if target_ward_id is not None:
                fc_rows = (
                    session.query(Forecast)
                    .filter(Forecast.ward_id == target_ward_id)
                    .order_by(Forecast.target_time.asc())
                    .limit(5)
                    .all()
                )
                for fc in fc_rows:
                    d_str = (
                        fc.target_time.strftime("%Y-%m-%d")
                        if hasattr(fc.target_time, "strftime")
                        else str(fc.target_time).split()[0]
                    )
                    cached_forecasts.append(
                        {
                            "date": d_str,
                            "temp_max_c": float(fc.predicted_temp),
                            "temp_min_c": float(fc.predicted_temp),
                            "humidity_max_pct": float(fc.predicted_humidity) if fc.predicted_humidity is not None else 50.0,
                            "wind_max_kmh": 0.0,
                            "solar_radiation_sum": None,
                        }
                    )

            logger.info(
                "Fallback to cached weather reading successful for ward ID %s (temp=%.1f C, humidity=%.1f%%, timestamp=%s).",
                target_ward_id,
                cached_reading.temperature,
                cached_reading.relative_humidity,
                cached_reading.timestamp,
            )

            return {
                "temp_c": float(cached_reading.temperature),
                "humidity_pct": float(cached_reading.relative_humidity),
                "wind_kmh": float(cached_reading.wind_speed) if cached_reading.wind_speed is not None else 0.0,
                "solar_radiation": float(cached_reading.solar_radiation) if cached_reading.solar_radiation is not None else None,
                "forecast": cached_forecasts,
                "source": "cached",
            }
        finally:
            if close_session and session is not None:
                session.close()

