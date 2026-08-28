# Task 19 — Forecast Line Chart (Chart.js)

- **Owner**: Frontend Team
- **Status**: PASS
- **What was built**: Implemented a multi-horizon Heat Index forecast line chart in the Bhubaneswar Heatwave Early Warning dashboard sidebar using Chart.js. The chart visualizes multi-day predicted Heat Index values (°C) with individual point background colors reflecting their respective risk categories. Integrated strict instance lifecycle management to prevent memory leaks and orphaned canvases across frequent ward marker clicks. Built strictly without `innerHTML` or template HTML strings, preserving pure DOM construction and full JSDoc documentation.
- **Files changed**:
  - `frontend/js/charts.js` (new file: created `renderForecastChart` with Chart.js instance destruction, dynamic `<canvas>` insertion, 5-band risk color mapping, fallback handling for empty/missing forecasts, and global window export)
  - `frontend/index.html` (added Chart.js CDN script tag and `js/charts.js` script tag in the specified load order before `js/app.js`)
  - `frontend/js/app.js` (extended `renderSidebarData` to create the "3–5 Day Forecast" section container via DOM methods and invoke `window.renderForecastChart`)
  - `BUILD_TASKS/TASK_19.md` (task build report)
- **Implementation Approach**:
  1. **Instance Lifecycle Management**: Maintained a module-level variable `let currentForecastChartInstance = null;` at the top of `charts.js`. Whenever `renderForecastChart` is called on a new ward click, it calls `.destroy()` on any existing instance and nulls it before dynamically creating a new `<canvas>` element. This prevents internal Chart.js state leaks and canvas stacking during repeated sidebar teardowns.
  2. **Authoritative Color Mapping**: Implemented `getRiskCategoryColor(category)` matching the 5-band heat stress scale in `map.js` and `risk_engine.py`:
     - Normal / Green: `#28a745`
     - Caution / Yellow: `#ffc107`
     - Extreme Caution / Orange: `#fd7e14`
     - Danger / Red: `#dc3545`
     - Extreme Danger / Maroon: `#800000`
  3. **Point & Axis Customization**: Configured `pointBackgroundColor` as an array of hex colors matching each forecast day's risk category, with a connecting primary theme line (`#3182ce`), °C axis labels and tooltips, responsive sizing, and clean axis gridlines.
  4. **Graceful Fallback**: If a ward has missing, null, or empty forecast data (e.g. fewer than 3 historical days available for ML inference), renders a `<p class="placeholder-text">No forecast available.</p>` element cleanly without throwing errors or attempting invalid chart instantiations.
- **How to verify**:
  1. **Run backend unit test suites**:
     ```bash
     $env:PYTHONPATH="backend"; python -m unittest backend/tests/test_p8_vertical_slice.py
     python -m unittest backend/tests/test_ml_model.py
     ```
     *Expect*: All tests pass with HTTP 200 responses containing 3-day forecast payloads.
  2. **Run frontend headless unit tests**:
     ```bash
     node scratch/test_frontend_charts.js
     ```
     *Expect*: All color mappings, placeholder handling, canvas generation, and Chart `.destroy()` lifecycle validations pass.
  3. **Manual Interactive Verification**:
     - Start FastAPI backend: `cd backend && python -m uvicorn app.main:app --port 8000`
     - Start static frontend server: `python -m http.server 5500 --bind 127.0.0.1`
     - Open `http://127.0.0.1:5500/frontend/index.html` in a web browser.
     - Click on ward marker `BBSR-01` on the Leaflet map:
       - Verify the sidebar displays "3–5 Day Forecast" below "Risk & Vulnerability Assessment".
       - Verify a smooth line chart appears showing dates on the X-axis and predicted Heat Index on the Y-axis labeled in °C.
       - Verify the point markers are colored according to each day's risk level (e.g., Orange for Extreme Caution).
     - Click across multiple different wards (e.g. `BBSR-02`, `BBSR-03`, `BBSR-01`):
       - Verify charts update immediately without console errors, duplicate/stacked canvases, or leftover instances.
       - If a ward has an empty forecast, verify "No forecast available." appears gracefully.
- **Blockers or known limitations**: None.
