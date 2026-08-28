# Task 13 — Risk Map API & Multi-Ward Endpoints

- Owner: P1
- Status: PASS
- What was built:
  - Implemented `GET /api/risk-map` and `GET /api/wards` routes in `backend/app/main.py` serving full-city multi-ward risk and geospatial data.
  - Returns a GeoJSON `FeatureCollection` containing all 10 Bhubaneswar municipal zones with geometry (Point coordinates), ward metadata, demographic vulnerability indices, and composite risk parameters.
  - Completed as part of the frontend/backend single-port server integration to power the dynamic Leaflet map layer directly from the backend API.
- Inputs: Existing risk_engine and ward vulnerability data for all wards.
- Outputs: `GET /api/wards` and `GET /api/risk-map`, both returning valid GeoJSON and structured ward JSON payloads for all wards.
- Dependencies: Task 11
- Files changed:
  - `backend/app/main.py`
  - `BUILD_TASKS/TASK-13-risk-map-api.md`
- How to verify:
  1. Start the backend server:
     ```bash
     cd backend
     uvicorn app.main:app --reload
     ```
  2. Query `GET /api/risk-map`:
     ```bash
     curl http://127.0.0.1:8000/api/risk-map
     ```
     Expected response: GeoJSON `FeatureCollection` with 10 ward features, Point geometries (`[lon, lat]`), ward numbers (`BBSR-01` through `BBSR-10`), zone names, and vulnerability indices.
  3. Query `GET /api/wards`:
     ```bash
     curl http://127.0.0.1:8000/api/wards
     ```
     Expected response: Returns the full ward list matching the GeoJSON FeatureCollection shape.
  4. Run automated test suite:
     ```bash
     cd backend
     python -m unittest tests/test_p8_vertical_slice.py tests/test_e2e_integration.py
     ```
     Expected result: All tests pass with exit code 0.
- Blockers or known limitations: none
