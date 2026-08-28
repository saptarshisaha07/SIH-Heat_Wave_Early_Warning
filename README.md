# SIH — Bhubaneswar Heat Wave Early Warning System

An integrated heatwave risk monitoring and early warning system for Bhubaneswar municipal zones. Combines real-time atmospheric data, multi-factor demographic vulnerability modeling, thermal comfort indices (Heat Index, WBGT), 5-day risk projections, and actionable public health advisories into an interactive dashboard.

---

## Quickstart (Single Server, Single Port)

The entire application (FastAPI backend, REST APIs, and Leaflet frontend dashboard) runs unified on port `8000`.

### 1. Install & Launch

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 2. Access the Application

- **Interactive Dashboard & Map**: Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.
- **Interactive API Documentation (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative API Documentation (ReDoc)**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Key Features

- **Unified Single-Port Architecture**: FastAPI directly serves the frontend UI and static assets alongside REST API endpoints, eliminating CORS configuration and cross-port latency.
- **Automated Idempotent Seeding**: Automatically initializes the SQLite database schema and seeds all 10 Bhubaneswar municipal zones on server startup.
- **Interactive Risk Map**: Leaflet.js-based geospatial map rendering municipal zones and risk markers populated dynamically via `/api/risk-map`.
- **Vertical Risk Slice**: Real-time atmospheric conditions (temperature, humidity, wind, solar radiation), computed thermal indices (Heat Index, simplified WBGT), composite risk scoring (+30% vulnerability amplification cap), and 5-tier public health advisories for outdoor workers and vulnerable demographics.
- **Automated Weather Ingestion**: Background scheduler (APScheduler) continuously refreshes atmospheric observations and risk metrics for all zones.

---

## API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the interactive web map dashboard (`index.html`) |
| `GET` | `/api/risk-map` | Returns GeoJSON `FeatureCollection` of all 10 municipal zones with coordinates and vulnerability indices |
| `GET` | `/api/wards/{id}` | Fetches real-time weather, thermal indices, 5-day forecasts, and health advisories for a specific ward |
| `POST` | `/api/refresh` | Triggers on-demand weather ingestion and risk computation across all wards |
| `GET` | `/health` | Service health status check |
| `GET` | `/docs` | OpenAPI / Swagger interactive documentation |

---

## Project Structure

```text
SIH-Heat_Wave_Early_Warning/
├── README.md                # Project documentation and quickstart
├── BUILD.md                 # Technical architecture and task history
├── backend/
│   ├── requirements.txt     # Python dependencies
│   ├── data/
│   │   ├── wards.geojson    # 10 Bhubaneswar municipal zone definitions
│   │   └── vulnerability.csv# Demographic vulnerability indicators
│   ├── app/
│   │   ├── main.py          # FastAPI application, route definitions & static mount
│   │   ├── seed.py          # Idempotent database seeder
│   │   ├── scheduler.py     # Background APScheduler ingestion service
│   │   ├── db/              # SQLAlchemy database session & engine
│   │   ├── models/          # ORM models (Ward, WeatherReading, RiskScore, etc.)
│   │   └── services/        # Risk calculation, thermal indices, advisories & alerts
│   └── tests/               # Automated unit and integration test suite
└── frontend/
    ├── index.html           # Map interface and sidebar layout
    └── js/
        ├── api.js           # Same-origin API client
        ├── app.js           # Sidebar UI controller & race-condition handling
        └── map.js           # Leaflet map initialization & risk-map integration
```

---

## Running Automated Tests

Run the test suite from the `backend/` directory:

```bash
cd backend
python -m unittest discover -s tests -p "test_*.py"
```
