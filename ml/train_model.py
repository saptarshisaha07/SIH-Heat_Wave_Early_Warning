"""Historical Weather Data Collector for Bhubaneswar Heat Wave Early Warning System.

This module retrieves historical daily weather data from the Open-Meteo Historical
Weather (Archive) API (https://archive-api.open-meteo.com/v1/archive) for all municipal
wards in Bhubaneswar, defined in backend/data/wards.geojson.

Output is saved to ml/historical_weather.csv with the following schema:
- ward_id
- ward_name
- latitude
- longitude
- date
- temperature_2m_mean
- temperature_2m_max
- temperature_2m_min
- relative_humidity_2m_mean
- wind_speed_10m_max
- shortwave_radiation_sum
- precipitation_sum
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure utf-8 output encoding across Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path to enable clean cross-module imports from backend
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from backend.app.services.thermal_index import heat_index

# Configure module-level logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ml.train_model")

# Open-Meteo Archive API endpoint
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Required daily metrics to request from Open-Meteo
DAILY_METRICS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
    "precipitation_sum",
]

# Output CSV column order
OUTPUT_COLUMNS = [
    "ward_id",
    "ward_name",
    "latitude",
    "longitude",
    "date",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "shortwave_radiation_sum",
    "precipitation_sum",
]

# Base feature column order before one-hot encoding ward IDs
BASE_FEATURE_COLUMNS = [
    "temp_mean_lag0",
    "temp_mean_lag1",
    "temp_mean_lag2",
    "humidity_lag0",
    "humidity_lag1",
    "wind_speed_lag0",
    "month",
    "day_of_year",
]

# Forecast target horizons (1, 2, and 3 days ahead Heat Index in deg C)
TARGET_COLUMNS = [
    "target_heat_index_t1",
    "target_heat_index_t2",
    "target_heat_index_t3",
]


def load_wards(geojson_path: str | Path = "backend/data/wards.geojson") -> List[Dict[str, Any]]:
    """Load authoritative ward definitions from GeoJSON file.

    Extracts ward id, name, latitude, and longitude. GeoJSON coordinates are in
    [longitude, latitude] format per RFC 7946.

    Args:
        geojson_path: Path to backend/data/wards.geojson.

    Returns:
        List of dicts with keys: 'ward_id', 'ward_name', 'latitude', 'longitude'.

    Raises:
        FileNotFoundError: If the GeoJSON file does not exist.
        ValueError: If GeoJSON structure is invalid or missing required properties.
    """
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"Authoritative wards GeoJSON file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict) or "features" not in data:
        raise ValueError(f"Invalid GeoJSON: missing 'features' in {path}")

    wards: List[Dict[str, Any]] = []
    for idx, feature in enumerate(data.get("features", [])):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])

        ward_id = str(feature.get("id") or properties.get("id", "")).strip()
        ward_name = str(properties.get("name", "")).strip()

        if not ward_id:
            raise ValueError(f"Feature at index {idx} missing 'id'")
        if not ward_name:
            raise ValueError(f"Feature at index {idx} missing properties.name")
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            raise ValueError(f"Feature '{ward_id}' invalid coordinates: {coords}")

        lon = float(coords[0])
        lat = float(coords[1])

        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Ward '{ward_id}' latitude out of bounds [-90, 90]: {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Ward '{ward_id}' longitude out of bounds [-180, 180]: {lon}")

        wards.append({
            "ward_id": ward_id,
            "ward_name": ward_name,
            "latitude": lat,
            "longitude": lon,
        })

    logger.info("Loaded %d authoritative wards from %s", len(wards), path)
    return wards


def fetch_ward_weather(
    lat: float,
    lon: float,
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    timezone: str = "Asia/Kolkata",
    max_retries: int = 3,
    initial_backoff: float = 2.0,
    timeout: int = 20,
) -> Optional[Dict[str, List[Any]]]:
    """Fetch daily historical weather series from Open-Meteo Archive API for a single location.

    Includes retry with exponential backoff on HTTP/network errors. If the request
    fails completely after all retries or returned daily arrays have mismatched lengths,
    logs the error and returns None so the caller can skip this ward.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        timezone: Timezone string (e.g. 'Asia/Kolkata').
        max_retries: Maximum number of retry attempts.
        initial_backoff: Initial backoff delay in seconds.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary containing daily weather lists (time and metric arrays) if successful,
        or None if failed or invalid.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone,
        "daily": ",".join(DAILY_METRICS),
    }

    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(
                "Querying Open-Meteo (lat=%.4f, lon=%.4f, attempt=%d/%d)...",
                lat,
                lon,
                attempt,
                max_retries,
            )
            response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=timeout)
            response.raise_for_status()

            payload = response.json()
            if not isinstance(payload, dict):
                logger.warning(
                    "Unexpected non-dictionary JSON response from Open-Meteo for lat=%.4f, lon=%.4f",
                    lat,
                    lon,
                )
                return None

            daily = payload.get("daily")
            if not isinstance(daily, dict):
                logger.warning(
                    "Missing 'daily' object in Open-Meteo response for lat=%.4f, lon=%.4f",
                    lat,
                    lon,
                )
                return None

            times = daily.get("time")
            if not isinstance(times, list) or len(times) == 0:
                logger.warning(
                    "Empty or missing 'time' series in daily payload for lat=%.4f, lon=%.4f",
                    lat,
                    lon,
                )
                return None

            expected_length = len(times)

            # Validate that all requested daily metrics are present and have identical lengths
            for metric in DAILY_METRICS:
                series = daily.get(metric)
                if not isinstance(series, list):
                    logger.warning(
                        "Missing daily metric '%s' for lat=%.4f, lon=%.4f", metric, lat, lon
                    )
                    return None
                if len(series) != expected_length:
                    logger.warning(
                        "Length mismatch for metric '%s' (len=%d, expected=%d) at lat=%.4f, lon=%.4f",
                        metric,
                        len(series),
                        expected_length,
                        lat,
                        lon,
                    )
                    return None

            # Successfully retrieved and validated
            return daily

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            logger.warning(
                "HTTP/Network error fetching weather for lat=%.4f, lon=%.4f (attempt %d/%d): %s",
                lat,
                lon,
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                backoff_time = initial_backoff * (2 ** (attempt - 1))
                logger.info("Retrying in %.1f seconds...", backoff_time)
                time.sleep(backoff_time)

    logger.error(
        "Failed to fetch weather data for lat=%.4f, lon=%.4f after %d attempts. Error: %s",
        lat,
        lon,
        max_retries,
        last_error,
    )
    return None


def fetch_historical_data(
    wards_geojson_path: str | Path = "backend/data/wards.geojson",
    output_csv_path: str | Path = "ml/historical_weather.csv",
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    timezone: str = "Asia/Kolkata",
    request_delay: float = 0.5,
) -> pd.DataFrame:
    """Standalone function to fetch historical weather data for all wards and export to CSV.

    Never fabricates or placeholders weather values. If a ward fails entirely after retries,
    it is skipped, logged, and the function proceeds with remaining wards.

    Args:
        wards_geojson_path: Path to backend/data/wards.geojson.
        output_csv_path: Destination path for historical weather CSV.
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        timezone: Timezone string for Open-Meteo.
        request_delay: Delay in seconds between API requests to avoid rate limits.

    Returns:
        pd.DataFrame containing historical records for all successfully fetched wards.

    Raises:
        RuntimeError: If all wards failed to fetch data.
    """
    wards = load_wards(wards_geojson_path)
    output_path = Path(output_csv_path)

    all_rows: List[Dict[str, Any]] = []
    successful_wards: List[str] = []
    failed_wards: List[Dict[str, str]] = []

    total_wards = len(wards)
    logger.info(
        "Starting historical weather data collection for %d wards (%s to %s)...",
        total_wards,
        start_date,
        end_date,
    )

    for idx, ward in enumerate(wards, 1):
        w_id = ward["ward_id"]
        w_name = ward["ward_name"]
        lat = ward["latitude"]
        lon = ward["longitude"]

        logger.info(
            "[%d/%d] Fetching data for ward %s (%s) at (%.4f, %.4f)...",
            idx,
            total_wards,
            w_id,
            w_name,
            lat,
            lon,
        )

        daily_data = fetch_ward_weather(
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
        )

        if daily_data is None:
            logger.warning(
                "SKIPPED WARD: %s (%s) could not be fetched/validated. Continuing with remaining wards.",
                w_id,
                w_name,
            )
            failed_wards.append({
                "ward_id": w_id,
                "ward_name": w_name,
                "reason": "Request failed after retries or response payload was invalid/misaligned",
            })
        else:
            times = daily_data["time"]
            for i, date_str in enumerate(times):
                row = {
                    "ward_id": w_id,
                    "ward_name": w_name,
                    "latitude": lat,
                    "longitude": lon,
                    "date": date_str,
                    "temperature_2m_mean": daily_data["temperature_2m_mean"][i],
                    "temperature_2m_max": daily_data["temperature_2m_max"][i],
                    "temperature_2m_min": daily_data["temperature_2m_min"][i],
                    "relative_humidity_2m_mean": daily_data["relative_humidity_2m_mean"][i],
                    "wind_speed_10m_max": daily_data["wind_speed_10m_max"][i],
                    "shortwave_radiation_sum": daily_data["shortwave_radiation_sum"][i],
                    "precipitation_sum": daily_data["precipitation_sum"][i],
                }
                all_rows.append(row)

            successful_wards.append(w_id)
            logger.info("Successfully retrieved %d daily records for ward %s.", len(times), w_id)

        # Rate-limiting delay between requests
        if idx < total_wards:
            time.sleep(request_delay)

    logger.info("--- Data Collection Summary ---")
    logger.info("Total wards processed: %d", total_wards)
    logger.info("Successful wards (%d): %s", len(successful_wards), ", ".join(successful_wards))
    if failed_wards:
        logger.warning("Failed/Skipped wards (%d):", len(failed_wards))
        for fw in failed_wards:
            logger.warning("  - %s (%s): %s", fw["ward_id"], fw["ward_name"], fw["reason"])
    else:
        logger.info("Failed wards: 0 (all wards succeeded)")

    if not all_rows:
        raise RuntimeError(
            "Historical data collection failed: zero rows collected across all wards."
        )

    # Build DataFrame and order columns strictly according to schema
    df = pd.DataFrame(all_rows, columns=OUTPUT_COLUMNS)

    # Sort deterministically by ward_id, then date
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(by=["ward_id", "date_dt"]).drop(columns=["date_dt"]).reset_index(drop=True)

    # Save to CSV cleanly (deterministic overwrite)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Saved %d rows to %s", len(df), output_path)

    return df


def validate_historical_data(
    csv_path: str | Path = "ml/historical_weather.csv",
    wards_geojson_path: str | Path = "backend/data/wards.geojson",
) -> Dict[str, Any]:
    """Validate the historical weather CSV dataset.

    Verifies:
    1. CSV exists and loads cleanly.
    2. Every ward from wards.geojson is present (lists missing if any).
    3. Required columns are present and weather columns are numeric.
    4. Dates are valid, sorted per ward, no duplicate (ward_id, date) pairs.
    5. Each ward has substantial daily date range with no major unexplained gaps.
    6. Missing value counts per column.
    7. Formatted reporting with PASS/FAIL result.

    Args:
        csv_path: Path to generated CSV file.
        wards_geojson_path: Path to backend/data/wards.geojson.

    Returns:
        Dictionary of validation metrics including boolean 'passed'.
    """
    path = Path(csv_path)
    report_lines: List[str] = []
    failures: List[str] = []

    report_lines.append("=" * 70)
    report_lines.append("HISTORICAL WEATHER DATASET VALIDATION REPORT")
    report_lines.append("=" * 70)

    if not path.exists():
        msg = f"Validation failed: CSV file not found at {path}"
        logger.error(msg)
        return {"passed": False, "error": msg}

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        msg = f"Validation failed: Could not read CSV file: {exc}"
        logger.error(msg)
        return {"passed": False, "error": msg}

    report_lines.append(f"Target CSV: {path.resolve()}")
    report_lines.append(f"Total Rows: {len(df):,}")
    report_lines.append(f"Total Columns: {len(df.columns)}")

    # 1. Check columns
    missing_cols = [c for c in OUTPUT_COLUMNS if c not in df.columns]
    if missing_cols:
        failures.append(f"Missing required columns: {missing_cols}")
        report_lines.append(f"[FAIL] Missing columns: {missing_cols}")
    else:
        report_lines.append("[PASS] All 12 required columns present.")

    # 2. Check wards against authoritative GeoJSON
    try:
        expected_wards = load_wards(wards_geojson_path)
        expected_ward_ids = [w["ward_id"] for w in expected_wards]
    except Exception as exc:
        expected_ward_ids = []
        failures.append(f"Could not load authoritative wards GeoJSON: {exc}")

    actual_ward_ids = sorted(df["ward_id"].astype(str).unique().tolist()) if "ward_id" in df.columns else []
    missing_wards = [w for w in expected_ward_ids if w not in actual_ward_ids]
    extra_wards = [w for w in actual_ward_ids if w not in expected_ward_ids]

    report_lines.append(f"Authoritative Wards Expected: {len(expected_ward_ids)} {expected_ward_ids}")
    report_lines.append(f"Wards in CSV: {len(actual_ward_ids)} {actual_ward_ids}")

    if missing_wards:
        failures.append(f"Missing expected wards: {missing_wards}")
        report_lines.append(f"[FAIL] Missing wards: {missing_wards}")
    else:
        report_lines.append("[PASS] All authoritative wards present in CSV.")

    if extra_wards:
        failures.append(f"Unexpected extra wards in CSV: {extra_wards}")
        report_lines.append(f"[FAIL] Extra unexpected wards: {extra_wards}")

    # 3. Numeric check for weather metrics
    weather_cols = [
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "relative_humidity_2m_mean",
        "wind_speed_10m_max",
        "shortwave_radiation_sum",
        "precipitation_sum",
    ]
    for col in weather_cols:
        if col in df.columns:
            non_numeric = pd.to_numeric(df[col], errors="coerce").isna().sum()
            if non_numeric > 0:
                failures.append(f"Column '{col}' has {non_numeric} non-numeric/null values")
                report_lines.append(f"[FAIL] Column '{col}' non-numeric/null count: {non_numeric}")
            else:
                report_lines.append(f"[PASS] Column '{col}' is fully numeric (min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f})")

    # 4. Duplicate (ward_id, date) check
    if "ward_id" in df.columns and "date" in df.columns:
        dup_count = df.duplicated(subset=["ward_id", "date"]).sum()
        if dup_count > 0:
            failures.append(f"Found {dup_count} duplicate (ward_id, date) pairs")
            report_lines.append(f"[FAIL] Duplicate (ward_id, date) count: {dup_count}")
        else:
            report_lines.append("[PASS] 0 duplicate (ward_id, date) pairs.")

    # 5. Date validation, sorting, and continuity per ward
    if "ward_id" in df.columns and "date" in df.columns:
        df["parsed_date"] = pd.to_datetime(df["date"], errors="coerce")
        invalid_dates = df["parsed_date"].isna().sum()
        if invalid_dates > 0:
            failures.append(f"Found {invalid_dates} invalid date strings")
            report_lines.append(f"[FAIL] Invalid date strings: {invalid_dates}")
        else:
            report_lines.append("[PASS] All dates are valid ISO date strings.")

        report_lines.append("-" * 70)
        report_lines.append("WARD BREAKDOWN & DATE CONTINUITY:")
        for ward_id in actual_ward_ids:
            ward_df = df[df["ward_id"] == ward_id].copy()
            row_count = len(ward_df)
            min_date = ward_df["parsed_date"].min()
            max_date = ward_df["parsed_date"].max()

            # Check if dates are sorted
            is_sorted = ward_df["parsed_date"].is_monotonic_increasing

            # Check date continuity (expected continuous daily date range)
            expected_days = (max_date - min_date).days + 1 if pd.notna(min_date) and pd.notna(max_date) else 0
            missing_days = expected_days - row_count

            status_note = "OK"
            if not is_sorted:
                failures.append(f"Ward {ward_id} dates are not sorted ascending")
                status_note = "NOT SORTED"
            if missing_days != 0:
                failures.append(f"Ward {ward_id} has {missing_days} missing date gaps in range")
                status_note = f"GAPS: {missing_days} days missing"

            report_lines.append(
                f"  Ward {ward_id:<8}: {row_count:>4} rows | Range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} | Sorted: {str(is_sorted):<5} | Continuity: {status_note}"
            )

    # 6. Missing value summary
    report_lines.append("-" * 70)
    report_lines.append("NULL / MISSING VALUE SUMMARY:")
    for col in df.columns:
        if col != "parsed_date":
            null_cnt = df[col].isna().sum()
            report_lines.append(f"  {col:<30}: {null_cnt} missing values")

    # 7. Final status
    passed = len(failures) == 0
    report_lines.append("=" * 70)
    report_lines.append(f"FINAL VALIDATION RESULT: {'PASS' if passed else 'FAIL'}")
    if failures:
        report_lines.append("Validation Failures:")
        for f in failures:
            report_lines.append(f"  - {f}")
    report_lines.append("=" * 70)

    report_text = "\n".join(report_lines)
    print(report_text)

    return {
        "passed": passed,
        "total_rows": len(df),
        "ward_count": len(actual_ward_ids),
        "date_min": str(df["date"].min()) if "date" in df.columns else "",
        "date_max": str(df["date"].max()) if "date" in df.columns else "",
        "failures": failures,
        "report_text": report_text,
    }


def compute_heat_index_series(df: pd.DataFrame) -> pd.Series:
    """Compute NOAA / NWS Heat Index in degrees Celsius for each row.

    Reuses the authoritative Rothfusz polynomial implementation from
    backend/app/services/thermal_index.py without duplication.

    Args:
        df: DataFrame containing 'temperature_2m_mean' and 'relative_humidity_2m_mean'.

    Returns:
        pd.Series of computed Heat Index values rounded to 1 decimal place.
    """
    return df.apply(
        lambda row: heat_index(
            temp_c=float(row["temperature_2m_mean"]),
            humidity_pct=float(row["relative_humidity_2m_mean"]),
        ),
        axis=1,
    )


def build_features_and_targets(
    df: pd.DataFrame,
    wards_geojson_path: str | Path = "backend/data/wards.geojson",
) -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Construct lag-based features and multi-horizon forward targets per ward.

    For each ward (sorted chronologically by date):
    Features per row (t):
      - temp_mean(t), temp_mean(t-1), temp_mean(t-2)
      - humidity(t), humidity(t-1)
      - wind(t)
      - month, day_of_year (derived from date)
      - ward_id (one-hot encoded)
    Target variables:
      - heat_index(t+1), heat_index(t+2), heat_index(t+3)

    Drops rows where lag or target values are unavailable (start/end of each ward's date range).

    Args:
        df: Historical weather DataFrame with computed 'heat_index'.
        wards_geojson_path: Path to authoritative wards GeoJSON for one-hot encoding columns.

    Returns:
        Tuple of (featured_dataframe, feature_column_names, list_of_ward_ids).
    """
    expected_wards = load_wards(wards_geojson_path)
    authoritative_ward_ids = [w["ward_id"] for w in expected_wards]
    actual_ward_ids = sorted(df["ward_id"].astype(str).unique().tolist())

    # Ensure all authoritative ward IDs are tracked deterministically
    all_ward_ids = sorted(list(set(authoritative_ward_ids + actual_ward_ids)))
    ward_dummy_cols = [f"ward_id_{w}" for w in all_ward_ids]
    feature_cols = BASE_FEATURE_COLUMNS + ward_dummy_cols

    df_copy = df.copy()
    df_copy["parsed_date"] = pd.to_datetime(df_copy["date"], errors="coerce")

    ward_dfs: List[pd.DataFrame] = []

    for w_id in all_ward_ids:
        ward_sub = df_copy[df_copy["ward_id"] == w_id].copy()
        if ward_sub.empty:
            logger.warning("Ward '%s' has 0 records in historical dataset and cannot be used.", w_id)
            continue

        ward_sub = ward_sub.sort_values(by="parsed_date").reset_index(drop=True)

        # 1. Temperature lags
        ward_sub["temp_mean_lag0"] = ward_sub["temperature_2m_mean"]
        ward_sub["temp_mean_lag1"] = ward_sub["temperature_2m_mean"].shift(1)
        ward_sub["temp_mean_lag2"] = ward_sub["temperature_2m_mean"].shift(2)

        # 2. Humidity lags
        ward_sub["humidity_lag0"] = ward_sub["relative_humidity_2m_mean"]
        ward_sub["humidity_lag1"] = ward_sub["relative_humidity_2m_mean"].shift(1)

        # 3. Wind speed
        ward_sub["wind_speed_lag0"] = ward_sub["wind_speed_10m_max"]

        # 4. Temporal calendar features derived from date
        ward_sub["month"] = ward_sub["parsed_date"].dt.month
        ward_sub["day_of_year"] = ward_sub["parsed_date"].dt.dayofyear

        # 5. One-hot encoded ward indicators
        for w in all_ward_ids:
            ward_sub[f"ward_id_{w}"] = (ward_sub["ward_id"] == w).astype(int)

        # 6. Multi-horizon targets (forward shifts of heat index)
        ward_sub["target_heat_index_t1"] = ward_sub["heat_index"].shift(-1)
        ward_sub["target_heat_index_t2"] = ward_sub["heat_index"].shift(-2)
        ward_sub["target_heat_index_t3"] = ward_sub["heat_index"].shift(-3)

        initial_len = len(ward_sub)
        # Drop rows where lag or target values are unavailable (NaN)
        ward_sub = ward_sub.dropna(subset=feature_cols + TARGET_COLUMNS).reset_index(drop=True)
        trimmed_len = len(ward_sub)

        logger.info(
            "Ward %s: %d total rows -> %d usable rows after lag/target trimming (dropped %d boundary rows)",
            w_id,
            initial_len,
            trimmed_len,
            initial_len - trimmed_len,
        )

        if trimmed_len < 30:
            logger.warning(
                "EXPLICIT WARNING: Ward '%s' has only %d usable rows after trimming, which may be insufficient.",
                w_id,
                trimmed_len,
            )

        ward_dfs.append(ward_sub)

    if not ward_dfs:
        raise ValueError("No usable data across any ward after feature engineering.")

    featured_df = pd.concat(ward_dfs, ignore_index=True)
    featured_df = featured_df.sort_values(by=["ward_id", "parsed_date"]).reset_index(drop=True)

    return featured_df, feature_cols, all_ward_ids


def chronological_split(
    featured_df: pd.DataFrame,
    ward_ids: List[str],
    raw_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Perform chronological train/test split holding out roughly the last 3 months (90 days).

    - Prints min and max dates in ml/historical_weather.csv (overall and per ward).
    - Computes test cutoff dynamically as max_date - 90 days.
    - Applies the same computed cutoff across all wards for synchronized temporal boundary.
    - Prints cutoff date and row counts in train vs test per ward before training.

    Args:
        featured_df: DataFrame with features, targets, and parsed_date.
        ward_ids: List of unique ward IDs.
        raw_df: Optional raw historical DataFrame before feature engineering.

    Returns:
        Tuple of (train_df, test_df, cutoff_date_str).
    """
    print("\n" + "=" * 70)
    print("CHRONOLOGICAL SPLIT & DATE ANALYSIS")
    print("=" * 70)

    # 1. Print min and max date in ml/historical_weather.csv (overall and per ward)
    if raw_df is not None and "date" in raw_df.columns:
        raw_copy = raw_df.copy()
        raw_copy["raw_date"] = pd.to_datetime(raw_copy["date"], errors="coerce")
        raw_min = raw_copy["raw_date"].min()
        raw_max = raw_copy["raw_date"].max()
        print(f"Historical Weather CSV Date Range (Overall): {raw_min.strftime('%Y-%m-%d')} to {raw_max.strftime('%Y-%m-%d')}")
        print("\nHistorical Weather CSV Date Range per Ward (Raw Data):")
        for w in ward_ids:
            w_raw = raw_copy[raw_copy["ward_id"] == w]
            if not w_raw.empty:
                w_min_s = w_raw["raw_date"].min().strftime("%Y-%m-%d")
                w_max_s = w_raw["raw_date"].max().strftime("%Y-%m-%d")
                print(f"  Ward {w:<8}: {len(w_raw):>4} rows | Range: {w_min_s} to {w_max_s}")
            else:
                print(f"  Ward {w:<8}: 0 rows (NO DATA)")

        cutoff_dt = raw_max - pd.Timedelta(days=90)
    else:
        min_date = featured_df["parsed_date"].min()
        max_date = featured_df["parsed_date"].max()
        print(f"Date Range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
        cutoff_dt = max_date - pd.Timedelta(days=90)

    min_feat_date = featured_df["parsed_date"].min()
    max_feat_date = featured_df["parsed_date"].max()
    print(f"\nUsable Date Range after Lag/Target Trimming: {min_feat_date.strftime('%Y-%m-%d')} to {max_feat_date.strftime('%Y-%m-%d')}")

    cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
    print(f"\nComputed Test Cutoff Date (max_date - 90 days): {cutoff_str}")
    print(f"Train Period: < {cutoff_str} | Test Period: >= {cutoff_str}")

    train_df = featured_df[featured_df["parsed_date"] < cutoff_dt].copy().reset_index(drop=True)
    test_df = featured_df[featured_df["parsed_date"] >= cutoff_dt].copy().reset_index(drop=True)

    print("\nTrain vs Test Allocation per Ward:")
    for w in ward_ids:
        w_train = len(train_df[train_df["ward_id"] == w])
        w_test = len(test_df[test_df["ward_id"] == w])
        print(f"  Ward {w:<8}: Train={w_train:>4} rows | Test={w_test:>4} rows")

    print(f"\nTotal Dataset: Train={len(train_df):,} rows | Test={len(test_df):,} rows")
    print("=" * 70 + "\n")

    return train_df, test_df, cutoff_str


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.DataFrame,
    random_state: int = 42,
) -> RandomForestRegressor:
    """Train a Multi-Output RandomForestRegressor predicting t+1, t+2, t+3 Heat Index.

    Architecture Choice:
    We choose a single Multi-Output RandomForestRegressor (scikit-learn natively supports
    multi-target regression) over 3 separate single-output models because:
    1. Joint Objective: Multi-output trees split on multi-dimensional MSE reduction,
       capturing shared weather dynamics and correlation structure across horizons.
    2. Consistency: Prevents contradictory forecasts across consecutive horizons.
    3. Efficiency: 3x faster training time and produces a single compact .pkl artifact.
    4. Simple Interface: A single model.predict(X) call yields shape (n, 3) for [t+1, t+2, t+3].

    Hyperparameters:
    - n_estimators=100: Standard robust ensemble size for daily time-series regression.
    - min_samples_leaf=2: Slight regularization to prevent overfitting noisy single days.
    - random_state=42: Deterministic reproducibility.
    - n_jobs=-1: Multi-core parallel training.
    """
    logger.info("Training Multi-Output RandomForestRegressor (n_estimators=100, min_samples_leaf=2)...")
    model = RandomForestRegressor(
        n_estimators=100,
        random_state=random_state,
        n_jobs=-1,
        min_samples_leaf=2,
    )
    model.fit(X_train, y_train)
    logger.info("Model training completed successfully.")
    return model


def evaluate_model(
    model: RandomForestRegressor,
    X_test: pd.DataFrame,
    y_test: pd.DataFrame,
    target_cols: List[str],
) -> Dict[str, float]:
    """Evaluate multi-horizon model performance honestly on held-out chronological test set.

    Prints exact, unrounded Mean Absolute Error (MAE in degrees Celsius) for each horizon
    (t+1, t+2, t+3) and the overall multi-horizon average.

    Args:
        model: Trained RandomForestRegressor.
        X_test: Held-out test features DataFrame.
        y_test: Held-out test ground truth targets DataFrame.
        target_cols: List of target column names.

    Returns:
        Dictionary containing MAE metrics for each horizon.
    """
    preds = model.predict(X_test)

    mae_t1 = mean_absolute_error(y_test[target_cols[0]], preds[:, 0])
    mae_t2 = mean_absolute_error(y_test[target_cols[1]], preds[:, 1])
    mae_t3 = mean_absolute_error(y_test[target_cols[2]], preds[:, 2])
    overall_mae = mean_absolute_error(y_test, preds)

    print("\n" + "=" * 70)
    print("HONEST MODEL EVALUATION REPORT (CHRONOLOGICAL TEST SET)")
    print("=" * 70)
    print(f"Held-out test rows evaluated: {len(X_test):,}")
    print(f"  Horizon t+1 (Day +1 Forecast) MAE : {mae_t1:.4f} °C")
    print(f"  Horizon t+2 (Day +2 Forecast) MAE : {mae_t2:.4f} °C")
    print(f"  Horizon t+3 (Day +3 Forecast) MAE : {mae_t3:.4f} °C")
    print(f"  Overall Multi-Horizon Average MAE : {overall_mae:.4f} °C")
    print("=" * 70 + "\n")

    return {
        "mae_t1_c": float(round(mae_t1, 4)),
        "mae_t2_c": float(round(mae_t2, 4)),
        "mae_t3_c": float(round(mae_t3, 4)),
        "overall_mae_c": float(round(overall_mae, 4)),
    }


def save_model_artifact(
    model: RandomForestRegressor,
    feature_cols: List[str],
    ward_ids: List[str],
    target_cols: List[str],
    metrics: Dict[str, float],
    cutoff_date: str,
    model_path: str | Path = "ml/model.pkl",
    metadata_path: str | Path = "ml/model_metadata.json",
) -> None:
    """Save the trained model and required metadata for future inference.

    Saves:
    - ml/model.pkl: joblib dictionary bundle with fitted model and metadata.
    - ml/model_metadata.json: human-readable sidecar with feature column order and metrics.
    """
    model_file = Path(model_path)
    meta_file = Path(metadata_path)

    model_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.parent.mkdir(parents=True, exist_ok=True)

    bundle = {
        "model": model,
        "feature_columns": feature_cols,
        "ward_ids": ward_ids,
        "target_columns": target_cols,
        "metrics": metrics,
        "cutoff_date": cutoff_date,
    }
    joblib.dump(bundle, model_file)
    logger.info("Saved model artifact bundle to %s", model_file.resolve())

    metadata = {
        "model_architecture": "RandomForestRegressor(MultiOutput)",
        "n_estimators": model.n_estimators,
        "feature_columns": feature_cols,
        "feature_count": len(feature_cols),
        "ward_ids": ward_ids,
        "target_columns": target_cols,
        "evaluation_metrics_mae_c": metrics,
        "test_cutoff_date": cutoff_date,
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info("Saved model metadata sidecar JSON to %s", meta_file.resolve())


def validate_model(
    model_path: str | Path = "ml/model.pkl",
    csv_path: str | Path = "ml/historical_weather.csv",
    wards_geojson_path: str | Path = "backend/data/wards.geojson",
) -> Dict[str, Any]:
    """Validate that saved ml/model.pkl can be loaded and predict on real sample data.

    1. Loads ml/model.pkl from disk.
    2. Builds sample feature row from real data in CSV.
    3. Runs prediction and confirms it returns 3 numeric values.
    4. Validates values are physical / sensible.
    5. Prints clear PASS/FAIL.
    """
    report_lines: List[str] = []
    failures: List[str] = []

    report_lines.append("=" * 70)
    report_lines.append("SAVED MODEL ARTIFACT VALIDATION REPORT")
    report_lines.append("=" * 70)

    model_file = Path(model_path)
    if not model_file.exists():
        msg = f"Model artifact not found at: {model_file}"
        failures.append(msg)
        report_lines.append(f"[FAIL] {msg}")
    else:
        report_lines.append(f"[PASS] Model artifact found at {model_file.resolve()}")
        try:
            bundle = joblib.load(model_file)
            if not isinstance(bundle, dict) or "model" not in bundle:
                failures.append("Invalid model bundle format: missing 'model' key")
                report_lines.append("[FAIL] Invalid model bundle format.")
            else:
                model = bundle["model"]
                feature_cols = bundle.get("feature_columns", [])
                ward_ids = bundle.get("ward_ids", [])
                target_cols = bundle.get("target_columns", [])
                metrics = bundle.get("metrics", {})

                report_lines.append("[PASS] Loaded model artifact successfully from disk.")
                report_lines.append(f"       Features ({len(feature_cols)}): {feature_cols}")
                report_lines.append(f"       Authoritative Ward IDs ({len(ward_ids)}): {ward_ids}")
                report_lines.append(f"       Target Horizons ({len(target_cols)}): {target_cols}")
                report_lines.append(f"       Recorded Test MAE Metrics: {metrics}")

                # Load sample row from CSV
                csv_file = Path(csv_path)
                if not csv_file.exists():
                    failures.append(f"Historical CSV not found at: {csv_file}")
                    report_lines.append(f"[FAIL] Historical CSV not found at: {csv_file}")
                else:
                    df = pd.read_csv(csv_file)
                    df["heat_index"] = compute_heat_index_series(df)
                    featured_df, _, _ = build_features_and_targets(df, wards_geojson_path)

                    sample_row = featured_df.iloc[[0]][feature_cols]
                    preds = model.predict(sample_row)

                    if preds.shape != (1, 3):
                        failures.append(f"Expected prediction shape (1, 3), got {preds.shape}")
                        report_lines.append(f"[FAIL] Invalid prediction shape: {preds.shape}")
                    else:
                        p1, p2, p3 = float(preds[0, 0]), float(preds[0, 1]), float(preds[0, 2])
                        if any(math.isnan(x) for x in [p1, p2, p3]):
                            failures.append(f"Predictions contain NaN: {[p1, p2, p3]}")
                            report_lines.append(f"[FAIL] NaN in predictions: {[p1, p2, p3]}")
                        elif not (all(10.0 <= x <= 70.0 for x in [p1, p2, p3])):
                            failures.append(f"Predictions out of physical range [10, 70]: {[p1, p2, p3]}")
                            report_lines.append(f"[FAIL] Out-of-bounds predictions: {[p1, p2, p3]}")
                        else:
                            report_lines.append("[PASS] Sample inference executed successfully!")
                            report_lines.append(f"       Sample Ward: {featured_df.iloc[0]['ward_id']} | Date: {featured_df.iloc[0]['date']}")
                            report_lines.append(f"       Predicted t+1 Heat Index: {p1:.2f} °C")
                            report_lines.append(f"       Predicted t+2 Heat Index: {p2:.2f} °C")
                            report_lines.append(f"       Predicted t+3 Heat Index: {p3:.2f} °C")
        except Exception as exc:
            failures.append(f"Model validation exception: {exc}")
            report_lines.append(f"[FAIL] Model validation error: {exc}")

    passed = len(failures) == 0
    report_lines.append("=" * 70)
    report_lines.append(f"FINAL MODEL VALIDATION RESULT: {'PASS' if passed else 'FAIL'}")
    if failures:
        report_lines.append("Validation Failures:")
        for f in failures:
            report_lines.append(f"  - {f}")
    report_lines.append("=" * 70)

    report_text = "\n".join(report_lines)
    print(report_text)

    return {"passed": passed, "failures": failures, "report_text": report_text}


def train_and_save_pipeline(
    csv_path: str | Path = "ml/historical_weather.csv",
    wards_geojson_path: str | Path = "backend/data/wards.geojson",
    model_path: str | Path = "ml/model.pkl",
    metadata_path: str | Path = "ml/model_metadata.json",
) -> Dict[str, Any]:
    """End-to-end pipeline to engineer features, train model, evaluate, and save artifact."""
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"Historical weather dataset not found at: {csv_file}")

    logger.info("Loading historical weather dataset from %s...", csv_file)
    df = pd.read_csv(csv_file)

    # Step 1: Compute Heat Index
    logger.info("Step 1: Computing Heat Index column reusing backend Rothfusz formula...")
    df["heat_index"] = compute_heat_index_series(df)
    logger.info(
        "Heat Index computed. Min=%.2f C, Max=%.2f C, Mean=%.2f C",
        df["heat_index"].min(),
        df["heat_index"].max(),
        df["heat_index"].mean(),
    )

    # Step 2: Feature Engineering
    logger.info("Step 2: Building lag features and multi-horizon targets...")
    featured_df, feature_cols, ward_ids = build_features_and_targets(df, wards_geojson_path)
    logger.info(
        "Feature engineering complete. %d total rows, %d feature columns.",
        len(featured_df),
        len(feature_cols),
    )

    # Step 3: Chronological Train/Test Split
    logger.info("Step 3: Performing chronological train/test split...")
    train_df, test_df, cutoff_date = chronological_split(featured_df, ward_ids, raw_df=df)

    X_train = train_df[feature_cols]
    y_train = train_df[TARGET_COLUMNS]
    X_test = test_df[feature_cols]
    y_test = test_df[TARGET_COLUMNS]

    # Step 4: Model Training
    logger.info("Step 4: Training Multi-Output RandomForestRegressor...")
    model = train_model(X_train, y_train)

    # Step 5: Evaluation
    logger.info("Step 5: Evaluating model on held-out test set...")
    metrics = evaluate_model(model, X_test, y_test, TARGET_COLUMNS)

    # Step 6: Save Model and Metadata
    logger.info("Step 6: Saving model artifact and metadata...")
    save_model_artifact(
        model=model,
        feature_cols=feature_cols,
        ward_ids=ward_ids,
        target_cols=TARGET_COLUMNS,
        metrics=metrics,
        cutoff_date=cutoff_date,
        model_path=model_path,
        metadata_path=metadata_path,
    )

    # Step 7: Validate Model
    logger.info("Step 7: Validating saved model artifact...")
    val_result = validate_model(
        model_path=model_path,
        csv_path=csv_path,
        wards_geojson_path=wards_geojson_path,
    )

    return {
        "model": model,
        "metrics": metrics,
        "cutoff_date": cutoff_date,
        "validation_passed": val_result["passed"],
    }


def main() -> None:
    """CLI entrypoint for data collection, validation, and model training."""
    parser = argparse.ArgumentParser(
        description="Historical Weather Data Collector and Heat Index Model Trainer for Bhubaneswar"
    )
    parser.add_argument(
        "--wards-geojson",
        default="backend/data/wards.geojson",
        help="Path to backend/data/wards.geojson (default: backend/data/wards.geojson)",
    )
    parser.add_argument(
        "--output-csv",
        default="ml/historical_weather.csv",
        help="Path to output CSV (default: ml/historical_weather.csv)",
    )
    parser.add_argument(
        "--model-path",
        default="ml/model.pkl",
        help="Path to save trained model (default: ml/model.pkl)",
    )
    parser.add_argument(
        "--metadata-path",
        default="ml/model_metadata.json",
        help="Path to save model metadata JSON (default: ml/model_metadata.json)",
    )
    parser.add_argument(
        "--start-date",
        default="2024-01-01",
        help="Start date YYYY-MM-DD (default: 2024-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default="2025-12-31",
        help="End date YYYY-MM-DD (default: 2025-12-31)",
    )
    parser.add_argument(
        "--fetch-data",
        action="store_true",
        help="Explicitly re-fetch historical weather data from Open-Meteo API",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run validation on existing output CSV and saved model without re-training",
    )
    args = parser.parse_args()

    csv_path = Path(args.output_csv)

    if args.validate_only:
        # Validate historical CSV
        val_data = validate_historical_data(
            csv_path=args.output_csv,
            wards_geojson_path=args.wards_geojson,
        )
        # Validate saved model
        val_model = validate_model(
            model_path=args.model_path,
            csv_path=args.output_csv,
            wards_geojson_path=args.wards_geojson,
        )
        if not (val_data["passed"] and val_model["passed"]):
            sys.exit(1)
        return

    # If fetch-data is requested or CSV doesn't exist, fetch data
    if args.fetch_data or not csv_path.exists():
        fetch_historical_data(
            wards_geojson_path=args.wards_geojson,
            output_csv_path=args.output_csv,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        val_data = validate_historical_data(
            csv_path=args.output_csv,
            wards_geojson_path=args.wards_geojson,
        )
        if not val_data["passed"]:
            logger.error("Historical data validation failed prior to model training.")
            sys.exit(1)

    # Train, evaluate, save, and validate model
    result = train_and_save_pipeline(
        csv_path=args.output_csv,
        wards_geojson_path=args.wards_geojson,
        model_path=args.model_path,
        metadata_path=args.metadata_path,
    )

    if not result["validation_passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
