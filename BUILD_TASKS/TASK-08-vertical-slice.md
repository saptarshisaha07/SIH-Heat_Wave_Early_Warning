# Task 08 — Critical one-ward vertical slice

- Owner: Project team
- Status: PASS
- What was built: Implemented the end-to-end one-ward vertical slice endpoint `GET /api/wards/{id}` in `backend/app/main.py`. The endpoint loads ward `BBSR-01` (id: 1) from the SQLite database, queries real-time atmospheric data and 5-day forecasts from Open-Meteo for the ward's coordinates, computes NWS Heat Index and simplified BOM WBGT thermal indices, evaluates base heat scores and demographic vulnerability-adjusted composite risk scores, and returns structured risk categories, forecasts, and public health advisories.
- Files changed:
  - `backend/app/services/risk_engine.py`
  - `backend/app/main.py`
  - `backend/tests/test_p8_vertical_slice.py`
  - `BUILD_TASKS/TASK-08-vertical-slice.md`
- How to verify:
  1. Start the FastAPI backend server:
     ```bash
     cd backend
     .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
     ```
  2. Query the application health check:
     ```bash
     curl http://127.0.0.1:8000/health
     ```
     Expected response: `{"status":"ok"}`
  3. Query the vertical slice endpoint for ward 1 (`BBSR-01`):
     ```bash
     curl http://127.0.0.1:8000/api/wards/1
     ```
     Expected response: JSON payload containing `ward` metadata (BBSR-01, Bhubaneswar Zone 01, population, vulnerability index), live `current` atmospheric readings and thermal/risk scores (temp, humidity, wind, solar radiation, heat_index, wbgt, base_score, composite_score, risk_category), 5-day `forecast` array with predicted heat indices and risk categories, and `advisory` recommendations.
  4. Run the focused automated test suite:
     ```bash
     .venv\Scripts\python.exe -m unittest tests/test_p8_vertical_slice.py
     ```
     Expected result: 3 tests pass with exit code 0.
- Blockers or known limitations: none
