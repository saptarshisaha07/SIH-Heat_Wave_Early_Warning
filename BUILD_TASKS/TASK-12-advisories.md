# Task 12 — Public Health Advisories & Segmented Action List

- Owner: P3 (Risk Engineer) / Pair Execution
- Status: PASS
- What was built:
  - Enhanced `backend/app/services/advisory.py` with a 5-tier public health advisory and action matrix aligned with NDMA and BMC Heat Action Plan standards.
  - Segmented recommendations across 5 target cohorts: `general_public`, `outdoor_workers`, `vulnerable_groups`, `hospitals_facilities`, and `municipal_actions`.
  - Added metadata: `risk_category`, `alert_level`, `color_hex`, `heat_index_range_c`, `headline`, and `summary`.
  - Implemented flexible helper functions: `get_advisory()` (case-insensitive with fallback), `get_all_advisories()`, `filter_advisories(category, level, persona)`, and `get_persona_advisory(category, persona)`.
  - Exposed REST endpoints in `backend/app/main.py`:
    - `GET /api/advisories`: Returns full matrix or filtered subset based on `category`, `level`, and `persona` query parameters.
    - `GET /api/advisories/{category}`: Returns detailed actions for a specific risk tier with optional `persona` filtering.
  - Added unit test suite `backend/tests/test_advisory.py` verifying all 5 tiers, personas, filtering, and API endpoints.
- Files changed:
  - `backend/app/services/advisory.py`
  - `backend/app/main.py`
  - `backend/tests/test_advisory.py`
  - `BUILD_TASKS/TASK-12-advisories.md`
- How to verify:
  1. Run the advisory unit test suite:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest backend/tests/test_advisory.py"
     ```
  2. Verify API endpoints using TestClient / Python:
     ```bash
     cmd /c "cd backend && .venv\Scripts\python.exe -c ""from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); print('All tiers count:', len(c.get('/api/advisories').json())); print('Danger headline:', c.get('/api/advisories/Danger').json()['headline']); print('Persona actions count:', len(c.get('/api/advisories?persona=outdoor_workers').json())); print('Task 12 verification: PASS')"""
     ```
- Blockers or known limitations: none
