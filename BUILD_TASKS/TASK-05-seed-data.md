# Task 05 — Seed ward and vulnerability data

- Owner: Project team
- Status: PASS
- What was built: Corrected the `Ward` model schema in `backend/app/models/ward.py` by deliberately renaming `vulnerability_score` to `vulnerability_index` while preserving integer `id` PKs and authoritative `ward_number` string IDs (`BBSR-01` to `BBSR-10`). Implemented an idempotent database seed operation in `backend/app/seed.py` that cross-validates `backend/data/wards.geojson` and `backend/data/vulnerability.csv`, computes normalized vulnerability indices ($V \in [0.0, 1.0]$), and populates the SQLite `wards` table.
- Files changed:
  - `backend/app/models/ward.py`
  - `backend/app/seed.py`
  - `BUILD_TASKS/TASK-05-seed-data.md`
- How to verify:
  1. Recreate the SQLite database and seed the dataset:
     ```bash
     cd backend
     .venv\Scripts\python.exe -m app.seed
     ```
  2. Query SQLite `wards` table to confirm `vulnerability_index` column presence and non-null values:
     ```bash
     .venv\Scripts\python.exe -c "import sqlite3, json; conn = sqlite3.connect('db.sqlite3'); conn.row_factory = sqlite3.Row; cur = conn.cursor(); cur.execute('SELECT * FROM wards ORDER BY ward_number'); rows = cur.fetchall(); print(f'Total rows: {len(rows)}'); geo_data = json.load(open('data/wards.geojson', encoding='utf-8'))['features']; geo_map = {f['properties']['id']: f['properties']['name'] for f in geo_data}; assert len(rows) == 10; [print(f'Ward: {r[\"ward_number\"]} | Name: {r[\"name\"]} | Pop: {r[\"population\"]} | Vuln Index: {r[\"vulnerability_index\"]} | Lat: {r[\"latitude\"]} | Lon: {r[\"longitude\"]}') for r in rows]; assert all(r['vulnerability_index'] is not None and 0.0 <= float(r['vulnerability_index']) <= 1.0 for r in rows); print('All SQLite wards table validations PASSED successfully.')"
     ```
  3. Verify idempotency by running seed a second time:
     ```bash
     .venv\Scripts\python.exe -m app.seed
     ```
     Success criteria: Returns exit code 0, outputs `0 inserted, 10 updated`, and row count remains 10.
- Blockers or known limitations: none
