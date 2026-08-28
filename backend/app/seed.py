"""Database seed module for SIH Heat Wave Early Warning System.

Loads Bhubaneswar ward geospatial definitions and demographic vulnerability indicators,
validates datasets, computes normalized multi-factor vulnerability indices, and
idempotently populates the SQLite wards table using the SQLAlchemy Ward model.
"""

import csv
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure backend directory is on sys.path for direct execution
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal, init_db
from app.models.advisory import Advisory
from app.models.ward import Ward
from app.services.advisory import ADVISORIES, VALID_PERSONAS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GEOJSON_FILE = DATA_DIR / "wards.geojson"
CSV_FILE = DATA_DIR / "vulnerability.csv"


def load_and_validate_datasets(
    geojson_path: Path, csv_path: Path
) -> List[Dict[str, Any]]:
    """Load, cross-validate, and normalize GeoJSON and CSV ward datasets.

    Args:
        geojson_path: Path to wards.geojson file.
        csv_path: Path to vulnerability.csv file.

    Returns:
        List of merged and validated ward dictionaries ready for insertion.

    Raises:
        FileNotFoundError: If input files do not exist.
        ValueError: If validation fails (structural, missing/extra IDs, range errors, etc.).
    """
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found at: {geojson_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Vulnerability CSV not found at: {csv_path}")

    # 1. Load GeoJSON
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    if geojson_data.get("type") != "FeatureCollection":
        raise ValueError("Invalid GeoJSON: Root must be a FeatureCollection.")

    features = geojson_data.get("features", [])
    if not features:
        raise ValueError("Invalid GeoJSON: features array is empty.")

    geojson_wards: Dict[str, Dict[str, Any]] = {}
    for idx, feat in enumerate(features):
        props = feat.get("properties", {})
        feat_id = feat.get("id") or props.get("id")
        if not feat_id or not isinstance(feat_id, str):
            raise ValueError(f"Feature at index {idx} missing valid string id.")

        feat_id = feat_id.strip()
        if feat_id in geojson_wards:
            raise ValueError(f"Duplicate ward ID '{feat_id}' found in GeoJSON.")

        name = props.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            raise ValueError(f"Feature '{feat_id}' missing valid name in properties.")
        name = name.strip()

        geometry = feat.get("geometry", {})
        if not geometry:
            raise ValueError(f"Feature '{feat_id}' missing geometry.")

        coords = geometry.get("coordinates")
        if not coords or not isinstance(coords, (list, tuple)):
            raise ValueError(f"Feature '{feat_id}' missing valid coordinates.")

        geom_type = geometry.get("type")
        if geom_type == "Point":
            if len(coords) < 2:
                raise ValueError(f"Feature '{feat_id}' Point geometry must have [lon, lat].")
            lon, lat = coords[0], coords[1]
        else:
            raise ValueError(f"Unsupported geometry type '{geom_type}' for feature '{feat_id}'.")

        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError(f"Feature '{feat_id}' coordinates must be numeric.")

        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Feature '{feat_id}' coordinates out of global bounds: lat={lat}, lon={lon}.")

        geojson_wards[feat_id] = {
            "id": feat_id,
            "name": name,
            "latitude": float(lat),
            "longitude": float(lon),
            "geometry": geometry,
        }

    # 2. Load CSV
    csv_rows: Dict[str, Dict[str, Any]] = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_headers = {"ward_id", "ward_name", "population", "elderly_pct", "outdoor_worker_pct"}
        if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV header missing required columns: {required_headers - set(reader.fieldnames or [])}")

        for row_idx, row in enumerate(reader, start=2):
            w_id = row.get("ward_id", "").strip()
            if not w_id:
                raise ValueError(f"CSV row {row_idx} missing ward_id.")

            if w_id in csv_rows:
                raise ValueError(f"Duplicate ward_id '{w_id}' in CSV at row {row_idx}.")

            w_name = row.get("ward_name", "").strip()
            if not w_name:
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') missing ward_name.")

            try:
                pop = int(row.get("population", "").strip())
            except ValueError:
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') population is not an integer.")

            if pop <= 0:
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') population must be a positive integer, got {pop}.")

            try:
                elderly_pct = float(row.get("elderly_pct", "").strip())
            except ValueError:
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') elderly_pct is not numeric.")

            if not (0.0 <= elderly_pct <= 100.0):
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') elderly_pct out of range [0, 100]: {elderly_pct}.")

            try:
                worker_pct = float(row.get("outdoor_worker_pct", "").strip())
            except ValueError:
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') outdoor_worker_pct is not numeric.")

            if not (0.0 <= worker_pct <= 100.0):
                raise ValueError(f"CSV row {row_idx} (ward_id '{w_id}') outdoor_worker_pct out of range [0, 100]: {worker_pct}.")

            csv_rows[w_id] = {
                "ward_id": w_id,
                "ward_name": w_name,
                "population": pop,
                "elderly_pct": elderly_pct,
                "outdoor_worker_pct": worker_pct,
            }

    # 3. Cross-validate IDs and Names
    geojson_ids = set(geojson_wards.keys())
    csv_ids = set(csv_rows.keys())

    if geojson_ids != csv_ids:
        missing_in_csv = geojson_ids - csv_ids
        extra_in_csv = csv_ids - geojson_ids
        raise ValueError(
            f"Ward ID mismatch between GeoJSON and CSV. "
            f"Missing in CSV: {sorted(missing_in_csv)}, Extra in CSV: {sorted(extra_in_csv)}"
        )

    for w_id, g_ward in geojson_wards.items():
        c_ward = csv_rows[w_id]
        if g_ward["name"] != c_ward["ward_name"]:
            raise ValueError(
                f"Ward name mismatch for ID '{w_id}': "
                f"GeoJSON has '{g_ward['name']}', CSV has '{c_ward['ward_name']}'."
            )

    # 4. Compute Normalized Vulnerability Index across entire ward set
    elderly_vals = [c["elderly_pct"] for c in csv_rows.values()]
    worker_vals = [c["outdoor_worker_pct"] for c in csv_rows.values()]

    min_e, max_e = min(elderly_vals), max(elderly_vals)
    min_w, max_w = min(worker_vals), max(worker_vals)

    range_e = max_e - min_e if max_e > min_e else 1.0
    range_w = max_w - min_w if max_w > min_w else 1.0

    merged_wards: List[Dict[str, Any]] = []
    for w_id in sorted(geojson_ids):
        g = geojson_wards[w_id]
        c = csv_rows[w_id]

        norm_e = (c["elderly_pct"] - min_e) / range_e
        norm_w = (c["outdoor_worker_pct"] - min_w) / range_w

        vuln_index = round(0.5 * norm_e + 0.5 * norm_w, 4)

        if not (0.0 <= vuln_index <= 1.0):
            raise ValueError(f"Computed vulnerability_index {vuln_index} out of range [0, 1] for ward '{w_id}'.")

        merged_wards.append(
            {
                "ward_id": w_id,
                "ward_name": g["name"],
                "latitude": g["latitude"],
                "longitude": g["longitude"],
                "geometry": g["geometry"],
                "population": c["population"],
                "elderly_pct": c["elderly_pct"],
                "outdoor_worker_pct": c["outdoor_worker_pct"],
                "vulnerability_index": vuln_index,
            }
        )

    return merged_wards


def seed_database(
    geojson_path: Optional[Path] = None, csv_path: Optional[Path] = None
) -> None:
    """Safely re-runnable and idempotent database seed for wards, vulnerability data, and advisories.

    Args:
        geojson_path: Optional custom path to wards.geojson.
        csv_path: Optional custom path to vulnerability.csv.
    """
    g_path = geojson_path or GEOJSON_FILE
    c_path = csv_path or CSV_FILE

    # Ensure database schema is initialized
    init_db()

    # Load and validate datasets prior to modifying database
    wards_data = load_and_validate_datasets(g_path, c_path)

    session = SessionLocal()
    try:
        # 1. Upsert Wards Table
        ward_inserted_count = 0
        ward_updated_count = 0

        for item in wards_data:
            ward_id = item["ward_id"]

            # Match vulnerability.csv ward_id to Ward.ward_number directly
            existing_ward = session.query(Ward).filter(Ward.ward_number == ward_id).first()

            if existing_ward:
                ward = existing_ward
                ward_updated_count += 1
            else:
                ward = Ward(ward_number=ward_id)
                session.add(ward)
                ward_inserted_count += 1

            # Populate model attributes directly
            ward.name = item["ward_name"]
            ward.population = item["population"]
            ward.latitude = item["latitude"]
            ward.longitude = item["longitude"]
            ward.vulnerability_index = item["vulnerability_index"]

        # 2. Upsert Advisories Table
        adv_inserted_count = 0
        adv_updated_count = 0

        for cat_name, adv_data in ADVISORIES.items():
            for persona in VALID_PERSONAS:
                actions_list = adv_data.get(persona, [])
                precautions_text = "\n".join(actions_list)
                alert_level_val = adv_data.get("alert_level", "Yellow")

                existing_adv = (
                    session.query(Advisory)
                    .filter(
                        Advisory.risk_level == alert_level_val,
                        Advisory.target_audience == persona,
                    )
                    .first()
                )

                if existing_adv:
                    existing_adv.title = adv_data.get("headline", "")
                    existing_adv.description = adv_data.get("summary", "")
                    existing_adv.precautions = precautions_text
                    adv_updated_count += 1
                else:
                    new_adv = Advisory(
                        risk_level=alert_level_val,
                        target_audience=persona,
                        title=adv_data.get("headline", ""),
                        description=adv_data.get("summary", ""),
                        precautions=precautions_text,
                    )
                    session.add(new_adv)
                    adv_inserted_count += 1

        session.commit()
        logger.info(
            "Database seeding completed successfully: "
            "Wards (%d inserted, %d updated), Advisories (%d inserted, %d updated).",
            ward_inserted_count,
            ward_updated_count,
            adv_inserted_count,
            adv_updated_count,
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Error during database seeding: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
