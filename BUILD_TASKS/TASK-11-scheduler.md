# Task 11 — Multi-Ward Weather Ingestion & In-Process Scheduler Service

- Owner: P2 (Data Engineer)
- Status: PASS
- What was built:
  - Created `backend/app/scheduler.py` implementing `ingest_all_wards_weather()` which loops across all 10 Bhubaneswar municipal wards in SQLite, retrieves live Open-Meteo atmospheric readings, computes NWS Rothfusz Heat Index and BOM simplified WBGT (`thermal_index.py`), computes multi-factor composite risk scores (`risk_engine.py`), and persists records into both `weather_readings` and `risk_scores` database tables.
  - Configured in-process `BackgroundScheduler` (APScheduler) running automatic background ingestion every 30 minutes.
  - Registered scheduler startup and shutdown in FastAPI application lifespan in `backend/app/main.py`.
  - Added on-demand demo trigger endpoint `POST /api/refresh` to trigger full city recalculation on demand.
  - Added `apscheduler>=3.10.0` to `backend/requirements.txt`.
  - Added test suite `backend/tests/test_scheduler.py` verifying multi-ward ingestion, database persistence, relationships, and lifecycle management.
- Files changed:
  - `backend/requirements.txt`
  - `backend/app/scheduler.py`
  - `backend/app/main.py`
  - `backend/tests/test_scheduler.py`
  - `BUILD_TASKS/TASK-11-scheduler.md`
- How to verify:
  1. Run unit test suite:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest backend/tests/test_scheduler.py"
     ```
  2. Test on-demand manual batch ingestion:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -c ""from app.scheduler import ingest_all_wards_weather; res = ingest_all_wards_weather(); print('Ingestion summary:', res); assert res['status'] in ['ok', 'partial']; assert res['wards_processed'] >= 1; print('Task 11 live verification: PASS')"""
     ```
- Blockers or known limitations: none
