# Task 20 — Public Health Advisory Panel + Score Breakdown Chart

- **Owner**: Frontend Team
- **Status**: PASS
- **What was built**: Implemented the Public Health Advisory text panel and the 3-bar visual Score Breakdown chart in the Bhubaneswar Heatwave Early Warning dashboard sidebar. The advisory panel displays prominent alert headlines and actionable cohort guidelines (with fallback handling for missing/empty advisories), while the breakdown chart visualizes the Base Heat Score, Vulnerability Adjustment, and Final Composite Risk Score using Chart.js with strict instance destruction to prevent memory leaks and canvas collisions. All DOM generation uses `document.createElement` and `textContent` without `innerHTML`, adhering to established project conventions.
- **Files changed**:
  - `frontend/css/style.css` (new file: added styling for `.advisory-headline`, `.advisory-actions-list`, and `.advisory-action-item`)
  - `frontend/index.html` (edited: added `<link rel="stylesheet" href="css/style.css">` after Leaflet CSS and `<script src="js/advisory.js"></script>` before `js/app.js`; preserved inline `<style>` and single Chart.js CDN tag)
  - `frontend/js/advisory.js` (new file: implemented `renderAdvisoryText` and `renderScoreBreakdownChart` with dedicated Chart.js lifecycle management, risk color mapping, and null safety)
  - `frontend/js/app.js` (edited: extended `renderSidebarData` to append "Public Health Advisory" and "Score Breakdown" container sections and invoke `window.renderAdvisoryText` and `window.renderScoreBreakdownChart`)
  - `BUILD_TASKS/TASK-20-advisory-breakdown.md` (new file: task build report)
- **CSS Resolution**:
  - Verified that `frontend/css/style.css` did not exist prior to this task (all baseline styles were inline in `index.html`).
  - Created `frontend/css/style.css` containing only the new rules needed for the advisory panel and breakdown chart.
  - Linked `frontend/css/style.css` in `index.html` `<head>` after the Leaflet stylesheet without altering any existing inline styles.
- **Implementation Approach**:
  1. **Dedicated Chart.js Instance Lifecycle**: Maintained an independent module-level variable `let currentBreakdownChartInstance = null;` in `advisory.js`. Whenever `renderScoreBreakdownChart` is invoked, it calls `.destroy()` on the existing instance and nulls it before creating a new `<canvas>` element, eliminating orphaned canvases and memory leaks without interfering with the forecast chart in `charts.js`.
  2. **Public Health Advisory Panel (`renderAdvisoryText`)**:
     - Inspects `advisoryObj` and `headline`. If missing or empty, renders `<p class="placeholder-text">No advisory available for this ward.</p>`.
     - Appends a prominent `<strong>` headline element with class `.advisory-headline`.
     - Supports `advisoryObj.actions` (with fallback to `advisoryObj.general_public`). If non-empty, renders a `<ul>` with `<li class="advisory-action-item">` items using `textContent`.
  3. **Visual Score Breakdown Bar Chart (`renderScoreBreakdownChart`)**:
     - Extracts `base_score`, `vulnerability_adjustment`, and `composite_score`, treating missing values as 0.
     - If all three metrics are null/undefined or `current` is missing, renders `<p class="placeholder-text">No score breakdown available.</p>`.
     - Plots 3 distinct bars:
       - Base Heat Score (Theme Blue: `#3182ce`)
       - Vulnerability Adjustment (Purple: `#805ad5`)
       - Final Composite Score (Dynamic risk color via `window.getRiskCategoryColor(current.risk_category)` or `#e53e3e`)
     - Auto-scaling numeric Y-axis (`beginAtZero: true`, labeled 'Score') with tooltips and clean gridlines.
  4. **Sidebar Integration in `app.js`**:
     - Appended two new `.sidebar-section` containers sequentially after the "3–5 Day Forecast" section:
       1. `<h3>Public Health Advisory</h3>` -> `window.renderAdvisoryText(data.advisory, advisorySection)`
       2. `<h3>Score Breakdown</h3>` -> `window.renderScoreBreakdownChart(data.current, breakdownSection)`
- **How to verify**:
  1. **Run full backend unit test suite**:
     ```bash
     $env:PYTHONPATH="backend"; python -m unittest discover -s backend/tests
     ```
     *Expect*: All 45 tests pass (`OK`).
  2. **Run frontend headless tests**:
     ```bash
     node scratch/test_frontend_advisory.js
     ```
     *Expect*: All tests pass for advisory text, actions list, fallback handling, chart destruction lifecycle, and full sidebar sequence.
  3. **Interactive Browser Verification**:
     - Start FastAPI backend: `cd backend && python -m uvicorn app.main:app --port 8000`
     - Start static frontend server: `python -m http.server 5500 --bind 127.0.0.1`
     - Open `http://127.0.0.1:5500/frontend/index.html` in a web browser.
     - Click on ward marker `BBSR-01`:
       - Verify "Public Health Advisory" section displays bold headline and action items list below the forecast chart.
       - Verify "Score Breakdown" section renders a 3-bar chart matching Base Heat Score, Vulnerability Adjustment, and Final Composite Score.
     - Click rapidly across multiple wards (e.g. `BBSR-01`, `BBSR-02`, `BBSR-03`, `BBSR-10`):
       - Verify both charts and advisories update smoothly with zero console errors or stacked canvases.
- **Blockers or known limitations**: None.
