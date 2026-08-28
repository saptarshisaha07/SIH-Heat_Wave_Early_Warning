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
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

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


def main() -> None:
    """CLI entrypoint for data collection and validation."""
    parser = argparse.ArgumentParser(
        description="Historical Weather Data Collector for Bhubaneswar Early Warning System"
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
        "--validate-only",
        action="store_true",
        help="Only run validation on existing output CSV without re-fetching",
    )
    args = parser.parse_args()

    if not args.validate_only:
        fetch_historical_data(
            wards_geojson_path=args.wards_geojson,
            output_csv_path=args.output_csv,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    val_result = validate_historical_data(
        csv_path=args.output_csv,
        wards_geojson_path=args.wards_geojson,
    )

    if not val_result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
