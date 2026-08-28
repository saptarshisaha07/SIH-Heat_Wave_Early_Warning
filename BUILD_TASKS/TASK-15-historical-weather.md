# Task 15 — Historical weather data

- Owner: P4
- Status: PASS
- What was built: A data-collection module (`ml/train_model.py`) that fetches ~2 years (2024-01-01 to 2025-12-31) of daily historical weather from the Open-Meteo Archive API for all 10 Bhubaneswar wards defined in `backend/data/wards.geojson`, plus an automated validation suite that confirms completeness and consistency of the resulting `ml/historical_weather.csv`.
- Files changed: `ml/train_model.py` (new), `ml/requirements.txt` (new), `ml/historical_weather.csv` (new, 7,310 rows)
- How to verify: `python ml/train_model.py --validate-only` — expect `FINAL VALIDATION RESULT: PASS`, 10/10 wards present, 7,310 total rows, 0 duplicate (ward_id, date) pairs, 0 missing values, contiguous daily coverage per ward from 2024-01-01 to 2025-12-31.
- Blockers or known limitations: None. All 10 wards fetched successfully with 0 failures and 0 fabricated values. Ward centroids in `wards.geojson` are illustrative approximations rather than official ward boundaries (per Task 2's scope), so historical weather reflects each ward's approximate area rather than a precise boundary polygon.
