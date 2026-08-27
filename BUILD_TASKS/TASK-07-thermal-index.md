# Task 07 — Heat Index and simplified WBGT

- Owner: Project team
- Status: PASS
- What was built: Implemented pure calculation functions for NOAA/NWS Rothfusz Heat Index (with Steadman mild temperature threshold and low/high humidity corrections) and Australian BOM simplified outdoor WBGT (with solar radiation adjustments) in `backend/app/services/thermal_index.py`. Added comprehensive unit test suite in `backend/tests/test_thermal_index.py`.
- Files changed:
  - `backend/app/services/thermal_index.py`
  - `backend/tests/test_thermal_index.py`
  - `BUILD_TASKS/TASK-07-thermal-index.md`
- How to verify:
  1. From repository root, run the unit test suite:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p ""test_thermal_index.py"""
     ```
  2. Or from inside `backend/` directory:
     ```bash
     cmd /c "cd backend && .venv\Scripts\python.exe -m unittest tests/test_thermal_index.py"
     ```
  3. Verify live calculation values:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -c ""from app.services.thermal_index import heat_index, wbgt; hi_humid = heat_index(35.0, 70.0); hi_dry = heat_index(35.0, 20.0); print(f'35C/70% RH -> HI: {hi_humid} C, 35C/20% RH -> HI: {hi_dry} C'); assert hi_humid > hi_dry; assert hi_humid >= 48.0; w = wbgt(35.0, 70.0, 800.0); print(f'35C/70% RH (800 W/m2) -> WBGT: {w} C'); assert w > 30.0; print('Task 7 verification passed successfully!')"""
     ```
  4. Success criteria: All 8 unit tests pass with exit code 0; 35°C at 70% RH yields Heat Index >= 48.0°C and WBGT > 30.0°C.
- Blockers or known limitations: none
