# Task 18 — Forecast Endpoint Integration

- **Owner**: Backend Team
- **Status**: PASS
- **What was built**: Extended the existing `GET /api/wards/{id}` route handler in `backend/app/main.py` to integrate the trained ML multi-horizon forecast service from `backend/app/services/ml_model.py`. The endpoint calls `predict_forecast(db, ward.id)` to retrieve 3-day Heat Index predictions ($t+1, t+2, t+3$) and categorizes them into risk bands, populating the `forecast` array in the JSON response payload. Implemented resilient exception handling and fallback logic so that if forecasting fails (e.g. fewer than 3 days of historical readings, model file missing, or inference errors), the endpoint logs a warning and returns HTTP 200 with an empty `"forecast": []` list rather than crashing with an HTTP 500 error.
- **Files changed**:
  - `backend/app/main.py` (imported `predict_forecast`, integrated prediction execution with fallback error handling)
  - `backend/tests/test_p8_vertical_slice.py` (added tests for ML forecast population, 3-day payload contract, graceful fallback on missing data, exception handling, empty forecast response, and HTTP endpoint verification)
  - `BUILD_TASKS/TASK-18-forecast-api.md` (task build report)
- **How to verify**:
  1. **Run full automated test suite**:
     ```bash
     $env:PYTHONPATH="backend"; python -m unittest discover -s backend/tests
     ```
     *Expect*: All 45 tests pass (`Ran 45 tests in ...s, OK`).
  2. **Run focused vertical slice test suite**:
     ```bash
     $env:PYTHONPATH="backend"; python -m unittest backend/tests/test_p8_vertical_slice.py
     ```
     *Expect*: All 8 tests pass (`Ran 8 tests in ...s, OK`).
  3. **Manual verification via FastAPI / TestClient / curl**:
     ```bash
     curl http://127.0.0.1:8000/api/wards/1
     ```
     *Expect*: Returns HTTP 200 with JSON payload containing:
     ```json
     {
       "ward": {"id": 1, "ward_number": "BBSR-01", "name": "Bhubaneswar Zone 01", ...},
       "current": {"temp_c": ..., "humidity_pct": ..., "heat_index": ..., "composite_score": ..., "risk_category": ...},
       "forecast": [
         {"date": "2026-08-29", "predicted_heat_index": 37.65, "predicted_risk_category": "Extreme Caution"},
         {"date": "2026-08-30", "predicted_heat_index": 37.76, "predicted_risk_category": "Extreme Caution"},
         {"date": "2026-08-31", "predicted_heat_index": 38.93, "predicted_risk_category": "Extreme Caution"}
       ],
       "advisory": {"risk_category": ..., "headline": ..., "general_public": [...], ...}
     }
     ```
- **Blockers or known limitations**: None. Requires at least 3 distinct calendar days of `WeatherReading` records per ward for the ML model to generate forecasts; gracefully falls back to `"forecast": []` if readings are insufficient.
