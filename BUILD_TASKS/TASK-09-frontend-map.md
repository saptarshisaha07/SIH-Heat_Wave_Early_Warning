# Task 09 — Leaflet map foundation

- Owner: Project team
- Status: PASS
- What was built: Implemented the Leaflet map foundation in `frontend/index.html` and `frontend/js/map.js` centered on Bhubaneswar, Odisha. The frontend loads OpenStreetMap tiles, fetches the canonical ward dataset from `/backend/data/wards.geojson`, renders all 10 ward markers, binds popups with ward IDs and zone names, fits map bounds to the markers, and logs clicked ward IDs to the browser console.
- Files changed:
  - `frontend/index.html`
  - `frontend/js/map.js`
  - `BUILD_TASKS/TASK-09-frontend-map.md`
- How to verify:
  1. From the repository root, start a local HTTP server:
     ```bash
     python -m http.server 5500
     ```
  2. Open the page in a browser:
     ```
     http://127.0.0.1:5500/frontend/index.html
     ```
  3. Verify that the map loads centered on Bhubaneswar with OpenStreetMap tiles and all 10 ward markers from `backend/data/wards.geojson`.
  4. Open developer tools (F12 -> Console) and click markers (e.g., `BBSR-01`, `BBSR-02`, `BBSR-10`). Confirm the console logs `Clicked ward: <WARD_ID>` and popups display the ward ID and name.
- Blockers or known limitations: none
