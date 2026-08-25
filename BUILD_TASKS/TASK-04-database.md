# Task 04 — SQLAlchemy models + SQLite database setup

- Owner: Contributor (Task 4 Owner)
- Status: PASS
- What was built: Configured SQLite database connection using SQLAlchemy 2.0 with automatic table creation during FastAPI startup lifespan. Defined ORM models for all six core tables: `wards`, `weather_readings`, `risk_scores`, `forecasts`, `advisories`, and `alerts_log`.
- Files changed:
  - `backend/requirements.txt`
  - `backend/app/main.py`
  - `backend/app/db/session.py`
  - `backend/app/models/__init__.py`
  - `backend/app/models/ward.py`
  - `backend/app/models/weather.py`
  - `backend/app/models/risk.py`
  - `backend/app/models/forecast.py`
  - `backend/app/models/advisory.py`
  - `backend/app/models/alert.py`
  - `.gitignore`
- How to verify:
  1. From `backend/` directory, start the server or test client:
     ```bash
     uvicorn app.main:app --reload
     ```
  2. Inspect that `backend/db.sqlite3` is generated and contains all six tables:
     ```bash
     python -c "import sqlite3; conn = sqlite3.connect('backend/db.sqlite3'); cur = conn.cursor(); cur.execute(\"SELECT name FROM sqlite_master WHERE type='table';\"); print(cur.fetchall())"
     ```
  3. Success looks like: `db.sqlite3` is generated on startup and `sqlite_master` contains `['wards', 'weather_readings', 'risk_scores', 'forecasts', 'advisories', 'alerts_log']`.
- Blockers or known limitations: none
