# Task 23 — Heat-Only vs. Vulnerability-Adjusted Score Toggle

- **Owner**: P3 (Risk Engineer) / P2 Pair
- **Status**: PASS
- **What was built**:
  - Implemented a persistent UI toggle allowing seamless switching between **Vulnerability-Adjusted** (composite score amplified by demographic vulnerability index) and **Heat-Only** (pure atmospheric thermal stress with zero vulnerability amplification).
  - Extended `backend/app/services/risk_engine.py` to calculate and expose `heat_only_score`, `heat_only_risk_category`, and `heat_only_color` directly using the existing shared `categorize_risk()` function (zero threshold duplication).
  - Propagated heat-only metrics through `GET /api/wards/{id}` (`current` payload) and `GET /api/risk-map` (GeoJSON `properties`) in `backend/app/main.py`.
  - Added in-place Leaflet marker recoloring in `frontend/js/map.js` via `layer.setStyle({ fillColor })` and `layer.setTooltipContent()`, eliminating layer removal and preventing duplicate marker bugs.
  - Added mode-aware sidebar rendering in `frontend/js/app.js` with client-side caching of `lastSelectedWardData` to instantly refresh the sidebar metrics upon toggling without redundant network calls.
  - Preserved complete independence of `services/advisory.py` and `services/alerts.py` (untouched; continue to evaluate composite risk for public safety).
- **Files changed**:
  - `backend/app/services/risk_engine.py` (exposed `heat_only_score`, `heat_only_risk_category`, `heat_only_color`)
  - `backend/app/main.py` (propagated heat-only metrics to `/api/wards/{id}` and `/api/risk-map`)
  - `frontend/index.html` (placed persistent mode toggle in `<header>` outside `#ward-details`)
  - `frontend/css/style.css` (styled toggle container and active state button)
  - `frontend/js/map.js` (implemented `window.updateMapMarkerMode` updating existing Leaflet layers in place)
  - `frontend/js/app.js` (implemented `window.setScoreMode`, cached data re-rendering, and mode-aware risk rows)
  - `BUILD_TASKS/TASK-23-heat-only-toggle.md` (task documentation report)
- **Rationale for Touching Files Beyond the Original Two-File List**:
  - The original task specification listed only `backend/app/services/risk_engine.py` and `frontend/js/app.js`.
  - `backend/app/main.py`: Necessary because FastAPI route handlers assemble the response dictionaries for `/api/wards/{id}` and `/api/risk-map`; without propagating the fields here, frontend map and sidebar would not receive the heat-only properties.
  - `frontend/index.html`: Necessary to place the toggle control in the permanent page header outside `#ward-details` (which is destroyed and recreated on every ward click).
  - `frontend/css/style.css`: Necessary to provide styling for the segmented toggle control.
  - `frontend/js/map.js`: Necessary to update the Leaflet circle marker colors and tooltips in place when the toggle changes.
- **Backend Field Names & Categorization Logic**:
  - `heat_only_score`: Exact value of pre-vulnerability `base_heat_score` (0–100 continuous score).
  - `heat_only_risk_category`: Direct output of `categorize_risk(heat_only_score)["category"]`.
  - `heat_only_color`: Direct output of `categorize_risk(heat_only_score)["color_hex"]`.
  - 100% threshold and category reuse; no duplicated tables.
- **Untouched Services Confirmation**:
  - Confirmed `backend/app/services/advisory.py` and `backend/app/services/alerts.py` are untouched and continue to use `composite_score` and `risk_category` exclusively.
- **Toggle Control Location & Sidebar Cache Architecture**:
  - **Location**: In `<header class="header-container">` in `frontend/index.html`.
  - **Sidebar Re-render**: `app.js` caches `lastSelectedWardData` on ward click. When toggle is clicked, `setScoreMode()` re-invokes `renderSidebarData(lastSelectedWardData)` immediately in memory without triggering additional HTTP requests.
- **How to verify**:
  1. **Run full backend unit test suite**:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p \"test_*.py\""
     ```
     *Expect*: All 51 tests pass (`OK`).
  2. **Verify live backend endpoints**:
     ```bash
     cmd /c "cd backend && .venv\Scripts\python.exe -c \"from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); print(c.get('/api/risk-map').json()['features'][0]['properties']); print(c.get('/api/wards/1').json()['current'])\""
     ```
     *Expect*: Both endpoints include `heat_only_score`, `heat_only_risk_category`, and `heat_only_color`.
  3. **Interactive Visual & Toggle Verification**:
     - Start server: `cd backend && python -m uvicorn app.main:app --port 8000`
     - Open `http://127.0.0.1:8000/` in a browser.
     - Observe header toggle defaulting to "Vulnerability-Adjusted".
     - Click high-vulnerability ward `BBSR-07`:
       - Composite score is ~52.27 (Extreme Caution / Orange).
       - Click "Heat-Only":
         - Marker recolors in place and sidebar updates to show "Heat-Only Risk Score: 42.86".
         - Click back to "Vulnerability-Adjusted": restores 52.27.
- **Blockers or known limitations**: None.
