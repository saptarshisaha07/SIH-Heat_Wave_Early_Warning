import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db, init_db
from app.models.alert import AlertLog
from app.models.risk import RiskScore
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.scheduler import ingest_all_wards_weather, shutdown_scheduler, start_scheduler
from app.seed import seed_database
from app.services.advisory import (
    filter_advisories,
    get_advisory,
    get_all_advisories,
    get_persona_advisory,
    normalize_category_name,
)
from app.services.alerts import build_simulated_alert
from app.services.ml_model import predict_forecast
from app.services.risk_engine import categorize_risk, compute_composite_risk
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
    summary = ingest_all_wards_weather(db)
    wards_total = db.query(Ward).count()
    if summary.get("wards_processed", 0) == 0 and wards_total > 0:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"All {wards_total} wards failed weather ingestion with no cached readings available: {summary.get('errors', [])}",
        )
    return summary


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

    # 1. Fetch live weather and 5-day forecast from Open-Meteo (with fallback to cache)
    try:
        weather_data = fetch_weather(ward.latitude, ward.longitude, db=db, ward_id=ward.id)
    except (WeatherFetcherError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve weather data for ward {ward.ward_number}: {exc}",
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

    # 5. Compute ML forecast risk projections
    forecast_items: List[Dict[str, Any]] = []
    try:
        raw_forecast = predict_forecast(db, ward.id)
        if raw_forecast:
            forecast_items = [
                {
                    "date": str(item["date"]),
                    "predicted_heat_index": float(item["predicted_heat_index"]),
                    "predicted_risk_category": str(item["predicted_risk_category"]),
                }
                for item in raw_forecast
            ]
        else:
            forecast_items = []
    except Exception as exc:
        logger.warning(
            f"Failed to generate ML forecast for ward {id} ({ward.ward_number}): {exc}"
        )
        forecast_items = []

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
            "heat_only_score": risk_profile["heat_only_score"],
            "heat_only_risk_category": risk_profile["heat_only_risk_category"],
            "heat_only_color": risk_profile["heat_only_color"],
        },
        "forecast": forecast_items,
        "advisory": advisory_data,
    }


@app.get("/api/risk-map")
@app.get("/api/wards")
def get_risk_map(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve GeoJSON FeatureCollection of all wards with spatial, vulnerability, and risk data."""
    wards = db.query(Ward).order_by(Ward.id).all()
    features = []
    for ward in wards:
        latest_risk = (
            db.query(RiskScore)
            .filter(RiskScore.ward_id == ward.id)
            .order_by(RiskScore.id.desc())
            .first()
        )
        risk_score_val = latest_risk.risk_score if latest_risk else 0.0
        risk_cat_val = latest_risk.risk_level if latest_risk else "Normal"
        color_val = categorize_risk(risk_score_val)["color_hex"]

        heat_only_score_val = latest_risk.hazard_score if (latest_risk and latest_risk.hazard_score is not None) else 0.0
        heat_only_info = categorize_risk(heat_only_score_val)
        heat_only_risk_cat_val = heat_only_info["category"]
        heat_only_color_val = heat_only_info["color_hex"]

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
                    "risk_score": risk_score_val,
                    "risk_category": risk_cat_val,
                    "color": color_val,
                    "heat_only_score": heat_only_score_val,
                    "heat_only_risk_category": heat_only_risk_cat_val,
                    "heat_only_color": heat_only_color_val,
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


class AlertSimulateRequest(BaseModel):
    ward_id: int
    channel: Optional[str] = "sms"


@app.post("/api/alerts/simulate")
def simulate_alert(
    request: AlertSimulateRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Simulate SMS or WhatsApp early warning alert broadcast for a ward based on current weather and risk."""
    ward = db.query(Ward).filter(Ward.id == request.ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward with id {request.ward_id} not found.",
        )

    # 1. Resolve current heat index and risk category from latest DB records or fallback to live compute
    latest_risk = (
        db.query(RiskScore)
        .filter(RiskScore.ward_id == ward.id)
        .order_by(RiskScore.id.desc())
        .first()
    )
    latest_weather = (
        db.query(WeatherReading)
        .filter(WeatherReading.ward_id == ward.id)
        .order_by(WeatherReading.id.desc())
        .first()
    )

    if latest_risk and latest_weather:
        heat_index_val = latest_weather.heat_index
        risk_cat_val = latest_risk.risk_level
    else:
        try:
            weather_data = fetch_weather(ward.latitude, ward.longitude, db=db, ward_id=ward.id)
            heat_index_val = heat_index(weather_data["temp_c"], weather_data["humidity_pct"])
            risk_profile = compute_composite_risk(
                heat_index_c=heat_index_val,
                vulnerability_index=ward.vulnerability_index,
            )
            risk_cat_val = risk_profile["risk_category"]
        except Exception:
            heat_index_val = 30.0
            risk_cat_val = "Caution"

    # 2. Build simulated alert payload
    alert_payload = build_simulated_alert(
        ward_id=ward.id,
        ward_name=ward.name,
        risk_category=risk_cat_val,
        heat_index_c=heat_index_val,
        channel=request.channel or "sms",
    )

    # 3. Log simulated broadcast event in alerts_log table
    log_entry = AlertLog(
        ward_id=ward.id,
        channel=alert_payload["channel"],
        message=alert_payload["message"],
        status="simulated",
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return alert_payload


@app.get("/tiles/{z}/{x}/{y}.png")
async def proxy_tile(z: int, x: int, y: int):
    """Proxy map tile requests to CARTO basemaps (or OSM fallback) hiding CARTO_API_KEY from the browser."""
    carto_key = os.getenv("CARTO_API_KEY", "").strip()
    if carto_key:
        subdomain = ("a", "b", "c", "d")[(x + y) % 4]
        target_url = f"https://{subdomain}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key={carto_key}"
    else:
        # Fallback to OpenStreetMap tile server when no CARTO API key is set in environment
        target_url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                target_url,
                headers={"User-Agent": "HeatWaveEarlyWarning/1.0"},
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Upstream tile server returned status {resp.status_code}",
                )
            return Response(
                content=resp.content,
                media_type=resp.headers.get("content-type", "image/png"),
                headers={
                    "Cache-Control": "public, max-age=86400",
                },
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch map tile from upstream provider: {exc}",
        )


# Static frontend mounting (MUST be mounted after all /api/ and other backend routes)
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")

