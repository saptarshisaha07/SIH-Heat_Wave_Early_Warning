# Task 02 — Create and verify ward GeoJSON

- Owner: P5
- Status: PASS
- What was built: Created GeoJSON FeatureCollection (`backend/data/wards.geojson`) defining 10 ward/zone centroid point features distributed across the urban area of Bhubaneswar, Odisha, India (centered at ~20.2961° N, 85.8245° E). An illustrative/synthetic centroid point fallback was used with stable IDs (`BBSR-01` to `BBSR-10`) to provide precise coordinate anchors for weather lookups and risk calculations; this is illustrative/synthetic zone data and not official municipal ward-boundary polygons.
- Files changed:
  - `backend/data/wards.geojson`
  - `BUILD_TASKS/TASK-02-wards-geojson.md`
- How to verify:
  1. Automated structural validation:
     Run the following automated validation command from the repository root:
     ```bash
     python3 -c "import json; data = json.load(open('backend/data/wards.geojson')); assert data.get('type') == 'FeatureCollection'; feats = data.get('features', []); assert 8 <= len(feats) <= 15; ids = set(); names = set(); [ids.add(f['properties']['id']) or names.add(f['properties']['name']) or (f['geometry']['type'] == 'Point' and len(f['geometry']['coordinates']) == 2 and 20.15 <= f['geometry']['coordinates'][1] <= 20.45 and 85.65 <= f['geometry']['coordinates'][0] <= 86.00) for f in feats]; assert len(ids) == len(feats) and len(names) == len(feats); print(f'Successfully validated {len(feats)} Bhubaneswar ward features.')"
     ```
     Expected result: Prints `Successfully validated 10 Bhubaneswar ward features.` and exits with code 0.
  2. Visual map validation:
     Upload or paste `backend/data/wards.geojson` into [geojson.io](https://geojson.io) or load the file in a Leaflet map viewer.
     Expected result: Exactly 10 markers render accurately across Bhubaneswar, Odisha, spanning key urban zones (Nayapalli, Patia, Chandrasekharpur, Saheed Nagar, Rasulgarh, Master Canteen/Unit 1, Old Town, Khandagiri, Laxmisagar, Bharatpur) clustered within 20.22°–20.38° N latitude and 85.75°–85.89° E longitude around the city center.
- Blockers or known limitations: none
