# Task 07 — Thermal index & WBGT calculation

- Owner: P2
- Status: PASS
- What was built: Implemented pure mathematical calculation functions in `backend/app/services/thermal_index.py` for NOAA/NWS Rothfusz Heat Index (with Steadman mild temperature threshold and low/high humidity corrections) and Australian Bureau of Meteorology (BOM) simplified outdoor WBGT (with optional solar radiation thermal load adjustment). Added comprehensive unit test suite in `backend/tests/test_thermal_index.py`.
- Files changed:
  - `backend/app/services/thermal_index.py`
  - `backend/tests/test_thermal_index.py`
  - `BUILD_TASKS/TASK-07-thermal-index.md`
  - `BUILD.md`
- How to verify:
  1. Run the automated unittest test suite from repository root:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p ""test_*.py"""
     ```
  2. Verify live calculation against reference values:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -c ""from app.services.thermal_index import heat_index, wbgt; hi_humid = heat_index(35.0, 70.0); hi_dry = heat_index(35.0, 20.0); print(f'35C/70% RH -> HI: {hi_humid} C, 35C/20% RH -> HI: {hi_dry} C'); assert hi_humid > hi_dry; assert hi_humid >= 48.0; w = wbgt(35.0, 70.0, 800.0); print(f'35C/70% RH (800 W/m2) -> WBGT: {w} C'); assert w > 30.0; print('Task 7 verification passed successfully!')"""
     ```
  3. Success criteria: All 13 unit tests pass with exit code 0, 35°C/70% RH produces HI >= 48.0°C and WBGT > 30.0°C.
- Blockers or known limitations: none
