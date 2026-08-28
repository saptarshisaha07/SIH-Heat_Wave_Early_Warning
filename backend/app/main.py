import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.session import get_db, init_db
from app.models.ward import Ward
from app.scheduler import ingest_all_wards_weather, shutdown_scheduler, start_scheduler
from app.seed import seed_database
from app.services.advisory import (
    filter_advisories,
    get_advisory,
    get_all_advisories,
    get_persona_advisory,
    normalize_category_name,
)
from app.services.risk_engine import compute_composite_risk
from app.services.thermal_index import heat_index, wbgt
from app.services.vulnerability import get_ward_vulnerability
from app.services.weather_fetcher import WeatherFetcherError, fetch_weather

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        seed_database()
    except Exception as exc:
        logger.error(f"Database seeding failed on startup: {exc}")
        raise
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Heat Wave Early Warning Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/refresh")
def refresh_weather(db: Session = Depends(get_db)):
    return ingest_all_wards_weather(db)


@app.get("/api/wards/{id}")
def get_ward_risk_slice(
    id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve live atmospheric readings, thermal indices, composite risk, and forecast for a ward.

    Args:
        id: Internal integer primary key ID of the ward (e.g. 1 for BBSR-01).
        db: SQLAlchemy database session.

    Returns:
        Structured vertical slice JSON payload with ward demographics, live conditions,
        5-day risk forecasts, and public health advisories.
    """
    ward = db.query(Ward).filter(Ward.id == id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward with id {id} not found.",
        )

    if ward.latitude is None or ward.longitude is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ward with id {id} ({ward.ward_number}) is missing geographic coordinates.",
        )

    # 1. Fetch live weather and 5-day forecast from Open-Meteo
    try:
        weather_data = fetch_weather(ward.latitude, ward.longitude)
    except (WeatherFetcherError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve live weather data for ward {ward.ward_number}: {exc}",
        ) from exc

    temp_c = weather_data["temp_c"]
    humidity_pct = weather_data["humidity_pct"]
    wind_kmh = weather_data["wind_kmh"]
    solar_radiation = weather_data["solar_radiation"]

    # 2. Compute thermal indices
    hi_c = heat_index(temp_c, humidity_pct)
    wbgt_c = wbgt(temp_c, humidity_pct, solar_radiation)

    # 3. Compute base score, vulnerability adjustment, and composite risk
    risk_profile = compute_composite_risk(
        heat_index_c=hi_c,
        vulnerability_index=ward.vulnerability_index,
    )

    # 4. Resolve demographic indicator percentages from ward record or vulnerability dataset
    vuln_info = get_ward_vulnerability(ward.ward_number)
    elderly_pct: Optional[float] = getattr(ward, "elderly_pct", None)
    if elderly_pct is None and vuln_info:
        elderly_pct = vuln_info.get("elderly_pct")

    outdoor_worker_pct: Optional[float] = getattr(ward, "outdoor_worker_pct", None)
    if outdoor_worker_pct is None and vuln_info:
        outdoor_worker_pct = vuln_info.get("outdoor_worker_pct")

    # 5. Compute forecast risk projections
    forecast_items: List[Dict[str, Any]] = []
    for day in weather_data.get("forecast", []):
        f_temp = day["temp_max_c"]
        f_humidity = day["humidity_max_pct"]
        predicted_hi = heat_index(f_temp, f_humidity)
        predicted_risk = compute_composite_risk(predicted_hi, ward.vulnerability_index)
        forecast_items.append(
            {
                "date": day["date"],
                "predicted_heat_index": predicted_hi,
                "predicted_risk_category": predicted_risk["risk_category"],
            }
        )

    # 6. Retrieve public health advisory for active composite risk category
    advisory_data = get_advisory(risk_profile["risk_category"])

    return {
        "ward": {
            "id": ward.id,
            "ward_number": ward.ward_number,
            "name": ward.name,
            "elderly_pct": elderly_pct,
            "outdoor_worker_pct": outdoor_worker_pct,
            "vulnerability_index": ward.vulnerability_index,
        },
        "current": {
            "temp_c": temp_c,
            "humidity_pct": humidity_pct,
            "wind_kmh": wind_kmh,
            "solar_radiation": solar_radiation,
            "heat_index": hi_c,
            "wbgt": wbgt_c,
            "base_score": risk_profile["base_heat_score"],
            "vulnerability_adjustment": risk_profile["vulnerability_adjustment"],
            "composite_score": risk_profile["composite_score"],
            "risk_category": risk_profile["risk_category"],
        },
        "forecast": forecast_items,
        "advisory": advisory_data,
    }


@app.get("/api/risk-map")
@app.get("/api/wards")
def get_risk_map(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve GeoJSON FeatureCollection of all wards with spatial and vulnerability data."""
    wards = db.query(Ward).order_by(Ward.id).all()
    features = []
    for ward in wards:
        features.append(
            {
                "type": "Feature",
                "id": ward.ward_number,
                "properties": {
                    "id": ward.ward_number,
                    "name": ward.name,
                    "vulnerability_index": ward.vulnerability_index,
                    "population": ward.population,
                    "db_id": ward.id,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [ward.longitude, ward.latitude],
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
    }


@app.get("/api/advisories")
def list_advisories(
    category: Optional[str] = None,
    level: Optional[str] = None,
    persona: Optional[str] = None,
) -> Any:
    """Retrieve public health advisories with optional filtering by category, alert level, or persona."""
    if not category and not level and not persona:
        return get_all_advisories()
    return filter_advisories(category=category, level=level, persona=persona)


@app.get("/api/advisories/{category}")
def get_single_advisory(
    category: str,
    persona: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve public health advisory and action items for a specific thermal risk category."""
    canonical = normalize_category_name(category)
    all_advs = get_all_advisories()
    if canonical not in all_advs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advisory category '{category}' not found. Valid categories: {list(all_advs.keys())}",
        )
    if persona:
        return get_persona_advisory(canonical, persona)
    return all_advs[canonical]


# Static frontend mounting (MUST be mounted after all /api/ and other backend routes)
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

