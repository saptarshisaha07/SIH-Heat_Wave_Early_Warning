# Heat Wave Early Warning System — Project & Agent Build Guide

> **Notice for Collaborators and AI Agents**: 
> This document (`BUILD.md`) serves as the single source of truth for project architecture, environment setup, active configuration, coding conventions, and task completion state. 
> Whenever an AI agent or team member works on a task, read this document first to avoid code, schema, or environment mismatches. **Always update this file upon completing each task.**

---

## 1. Project Overview
- **Project Name**: SIH Heat Wave Early Warning System
- **Repository Root**: `SIH-Heat_Wave_Early_Warning`
- **Current Stack**:
  - **Backend**: FastAPI, Uvicorn, Python 3.11+
  - **Environment**: Virtual Environment (`.venv`)

---

## 2. Directory Structure & Architecture

```text
SIH-Heat_Wave_Early_Warning/
├── .gitignore               # Standard Python & environment gitignore
├── BUILD.md                 # Agent & Developer build guide (this file)
├── README.md                # General project overview
├── BUILD_TASKS/             # Individual task completion reports
│   ├── TASK-01-fastapi.md
│   ├── TASK-02-wards-geojson.md
│   ├── TASK-03-vulnerability-risk-engine.md
│   ├── TASK-04-database.md
│   ├── TASK-06-weather-fetcher.md
│   └── TASK-07-thermal-index.md
└── backend/
    ├── requirements.txt     # Python dependencies
    ├── data/
    │   ├── wards.geojson    # 10 Bhubaneswar municipal zone coordinates
    │   └── vulnerability.csv# Demographic vulnerability indicators per zone
    ├── app/
    │   ├── __init__.py      # Package marker
    │   ├── main.py          # FastAPI app entry point & route definitions
    │   ├── db/
    │   │   └── session.py   # SQLAlchemy 2.0 SQLite database engine & session
    │   ├── models/          # ORM models (Ward, WeatherReading, RiskScore, Forecast, Advisory, AlertLog)
    │   └── services/
    │       ├── weather_fetcher.py  # Open-Meteo current + 5-day forecast fetcher
    │       ├── thermal_index.py    # NWS Rothfusz Heat Index & BOM WBGT thermal math
    │       ├── vulnerability.py    # Demographic vulnerability loader & normalizer
    │       ├── risk_engine.py      # Base Heat Score, composite risk, and explainability breakdown
    │       ├── advisory.py         # 5-band public health advisories
    │       └── alerts.py           # SMS / WhatsApp simulated emergency alert builder
    └── tests/
        ├── test_p3_risk_engine.py  # Automated test suite for risk & vulnerability calculations
        └── test_thermal_index.py   # Automated test suite for thermal stress calculations
```

### Module Layout Conventions (For Future Tasks)
When extending the backend in upcoming tasks, adhere strictly to the following directory layout inside `backend/app/`:
- `backend/app/api/` or `backend/app/routers/` &rarr; API route controllers (e.g. `alerts.py`, `predictions.py`, `auth.py`).
- `backend/app/core/` &rarr; Application configuration, settings (`config.py`), security.
- `backend/app/models/` &rarr; Database / ORM models (e.g. SQLAlchemy, SQLModel).
- `backend/app/schemas/` &rarr; Pydantic request/response validation schemas.
- `backend/app/services/` &rarr; Business logic, ML model inference, external weather API integrations.
- `backend/app/utils/` &rarr; Helper functions and utilities.

---

## 3. Environment & Setup Instructions

### Python Version
- **Recommended**: Python `3.10` or `3.11`

### Local Setup (Backend)

1. **Navigate to the `backend` folder**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD)**:
     ```cmd
     python -m venv .venv
     .\.venv\Scripts\activate.bat
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run Automated Tests**:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```

5. **Run the Development Server**:
   ```bash
   uvicorn app.main:app --reload
   ```
   *Server will run at `http://127.0.0.1:8000` with hot reloading enabled.*

---

## 4. Environment Variables Specification

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | No | `sqlite:///backend/db.sqlite3` | SQLite database URI connection string. |

> **Rule for AI Agents**: If adding environment variables in future tasks:
> 1. Use `pydantic-settings` or `python-dotenv`.
> 2. Document every new variable in this table.
> 3. Provide a `backend/.env.example` template with dummy values. Never commit actual `.env` files.

---

## 5. Active Endpoints & Health Check

| Method | Endpoint | Description | Expected Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Application health check | `{"status": "ok"}` |
| `GET` | `/docs` | Interactive Swagger API Docs | OpenAPI UI |
| `GET` | `/redoc` | Alternative ReDoc documentation | ReDoc UI |

---

## 6. AI Agent Collaboration Rules & Guidelines

To ensure seamless multi-agent and multi-developer collaboration without merge conflicts or code regressions:

1. **Strict Scoping**: Stick strictly to the assigned task without removing or rewriting existing valid modules unless explicitly instructed.
2. **Dependency Management**: If a new library is required, pin the minimum version in `backend/requirements.txt` (e.g. `package>=x.y.z`).
3. **Pydantic Validation**: All request payloads and response bodies for new endpoints must use Pydantic `BaseModel` schemas.
4. **Error Handling**: Use standard FastAPI `HTTPException` with clear status codes and error detail messages.
5. **Update BUILD.md**: Every AI agent **MUST** update this `BUILD.md` file at the end of each task to record new endpoints, architecture updates, new dependencies, or newly introduced environment variables.

---

## 7. Task Changelog & Status

- **Task 1: Scaffolding & Health Check** *(PASS)*
  - Initialized `backend/app/` package structure and `GET /health` endpoint.
- **Task 2: Ward GeoJSON Dataset** *(PASS)*
  - Created GeoJSON FeatureCollection (`backend/data/wards.geojson`) for 10 Bhubaneswar zones.
- **Task 3: Vulnerability Dataset & Multi-Factor Risk Engine (P3)** *(PASS)*
  - Created `backend/data/vulnerability.csv` with demographic indicators for all 10 Bhubaneswar zones.
  - Implemented `vulnerability.py` with min-max normalization into a `0.0–1.0` vulnerability index.
  - Built `risk_engine.py` with continuous piecewise linear Base Heat Score, $+30\%$ vulnerability amplification cap, and heat-only toggle breakdown.
  - Built `advisory.py` with 5-band public health advisories.
  - Built `alerts.py` with SMS/WhatsApp simulation payloads.
  - Added automated test suite `tests/test_p3_risk_engine.py` (all tests passing).
- **Task 4: Database & ORM Setup** *(PASS)*
  - Configured SQLite connection with SQLAlchemy 2.0 and defined 6 core ORM models.
- **Task 6: Weather Fetcher Service** *(PARTIAL)*
  - Built Open-Meteo live weather and 5-day forecast fetcher service.
- **Task 7: Thermal Index Math Service** *(PASS)*
  - Implemented `backend/app/services/thermal_index.py` providing `heat_index()` (NOAA/NWS Rothfusz regression with Steadman mild-temperature threshold and low/high humidity adjustments) and `wbgt()` (Australian BOM outdoor simplified approximation with solar radiation adjustment).
  - Added comprehensive automated test suite `backend/tests/test_thermal_index.py` (all tests passing).
