# Task 24 — Resilience: Cached Fallback + Re-runnable Seed

- **Owner**: Backend Team
- **Status**: PASS
- **What was built**:
  - Implemented automatic cached weather reading fallback in `backend/app/services/weather_fetcher.py` when the Open-Meteo API is unreachable, times out, or fails, returning the normalized dictionary with a `"source": "cached"` flag.
  - Implemented strict error handling raising `WeatherFetcherError` without fabricating fake weather data when a ward has zero prior cached readings and network access is unavailable.
  - Updated `backend/app/scheduler.py` and `POST /api/refresh` in `backend/app/main.py` to maintain per-ward loop continuity during network failures, reporting `live_count`, `cached_count`, and `failed_count` in the execution summary.
  - Updated `backend/app/main.py` endpoints (`/api/wards/{id}` and `/api/alerts/simulate`) to pass database session and ward identifiers to `fetch_weather`, providing offline resilience for cached wards and isolated 502 responses for uncached wards.
  - Updated `backend/app/seed.py` with an idempotent upsert pattern across all seeded tables (`Ward` and `Advisory`), guaranteeing identical row counts across consecutive seed runs without creating duplicates.
  - Preserved `backend/app/services/risk_engine.py` completely untouched (`git diff` shows 0 changes) to guarantee clean, collision-free merging with the concurrent Task 23 branch.
  - Created comprehensive unit and integration test suite `backend/tests/test_task24_resilience.py` (10 tests) and verified full suite passing (61 tests).
- **Files changed**:
  - `backend/app/services/weather_fetcher.py` (edited: added cached database fallback, source tagging, and logging on network failure)
  - `backend/app/scheduler.py` (edited: passed session/ward_id to fetch_weather, added live/cached/failed metrics tracking)
  - `backend/app/main.py` (edited: updated `/api/refresh` summary response and passed session/ward_id in `/api/wards/{id}` and `/api/alerts/simulate`)
  - `backend/app/seed.py` (edited: implemented upsert pattern for `Ward` and `Advisory` models)
  - `backend/tests/test_task24_resilience.py` (new file: unit and integration tests for resilience and seed idempotency)
  - `BUILD_TASKS/TASK-24-resilience-fallback.md` (new file: task build report)
- **Step 0 Scope Analysis & Network Call Layer Determination**:
  - **`backend/app/services/weather_fetcher.py`**: **Required Network Failure Handling**. This is the **only** module that performs external HTTP network requests (to `https://api.open-meteo.com/v1/forecast`).
  - **`backend/app/services/thermal_index.py`**: **No Network Handling Needed**. Pure mathematical computation (Rothfusz Heat Index regression & Australian BOM WBGT formulas).
  - **`backend/app/services/risk_engine.py`**: **No Network Handling Needed / Left 100% Untouched**. Pure computation operating on already fetched data. Left completely unmodified to avoid collisions with concurrent Task 23 branch.
  - **`backend/app/services/vulnerability.py`**: **No Network Handling Needed**. In-memory lookup reading local CSV `vulnerability.csv`.
  - **`backend/app/services/advisory.py`**: **No Network Handling Needed**. In-memory dictionary lookup.
  - **`backend/app/services/ml_model.py`**: **No Network Handling Needed**. Local `RandomForestRegressor` inference via `joblib` on local SQLite records.
  - **`backend/app/services/alerts.py`**: **No Network Handling Needed**. Local string formatting for SMS / WhatsApp messages.
- **Confirmation of `risk_engine.py` Unmodified**:
  - Command: `git diff backend/app/services/risk_engine.py`
  - Output:
    ```
    (empty - 0 lines modified)
    ```
- **Fallback Mechanism in `weather_fetcher.py`**:
  1. `fetch_weather(lat, lon, db=None, ward_id=None)` validates numeric coordinate ranges $[-90, 90]$ and $[-180, 180]$. Out-of-bounds coordinates immediately raise `ValueError`.
  2. Executes live `requests.get` to Open-Meteo Forecast API with a 10-second timeout.
  3. On successful live response, parses and normalizes current conditions and 5-day forecast, tagging `"source": "live"`.
  4. On connection error, timeout, HTTP 5xx/4xx error, or JSON decode failure:
     - Emits a structured warning log: `Live weather fetch from Open-Meteo failed for lat=..., lon=... (...). Attempting cached fallback from database...`
     - Opens a managed `SessionLocal` if `db` is not provided.
     - Resolves the ward by `ward_id` or nearest coordinate match in the `wards` table.
     - Queries `weather_readings` for the most recent record for that ward (`ORDER BY timestamp DESC, id DESC`).
     - If a cached record exists, retrieves any cached forecasts from `forecasts` table and returns the identical normalized dictionary structure tagged `"source": "cached"`.
     - If zero cached records exist for that ward, logs an error and raises `WeatherFetcherError` (`Open-Meteo API unreachable (...) and no cached weather readings exist...`), strictly preventing fake null or zero data fabrication.
- **Database Seeding Upsert Approach (`seed.py`)**:
  1. **`Ward` Table**: Natural key `ward_number` (e.g. `BBSR-01`). Queries `existing_ward = session.query(Ward).filter(Ward.ward_number == ward_id).first()`. Updates existing record attributes (`name`, `population`, `latitude`, `longitude`, `vulnerability_index`) if present; inserts new `Ward` instance if absent.
  2. **`Advisory` Table**: Natural key `(risk_level, target_audience)`. Queries `existing_adv = session.query(Advisory).filter(Advisory.risk_level == alert_level, Advisory.target_audience == persona).first()`. Updates `title`, `description`, and `precautions` if present; inserts new `Advisory` instance if absent.
  3. **Verification of Double-Run Idempotency**:
     - *Fresh database run*: Wards = 0, Advisories = 0 -> After 1st seed: Wards = 10 (10 inserted), Advisories = 25 (25 inserted).
     - *Second seed run*: Wards = 10 (0 inserted, 10 updated), Advisories = 25 (0 inserted, 25 updated).
     - *Result*: Exact same row counts ($10$ wards, $25$ advisories), $0$ duplicates.
- **How to verify**:
  1. **Run Task 24 Resilience Test Suite**:
     ```bash
     cd backend && python -m unittest tests/test_task24_resilience.py
     ```
     *Expect*: All 10 tests pass (`OK`), verifying live fetch, timeout fallback, 500 fallback, unseeded ward exception, 200 cached endpoint response, 502 uncached endpoint response, scheduler resilience, `/api/refresh` summary, and seed idempotency.
  2. **Run Full Backend Test Suite**:
     ```bash
     cd backend && python -m unittest discover -s tests -p "test_*.py"
     ```
     *Expect*: All 61 tests pass (`OK`) across all test modules.
  3. **Verify Re-runnable Seed Idempotency Directly**:
     ```bash
     cd backend && python -c "from app.db.session import SessionLocal; from app.models.ward import Ward; from app.models.advisory import Advisory; from app.seed import seed_database; db = SessionLocal(); print('Initial - Wards:', db.query(Ward).count(), 'Advisories:', db.query(Advisory).count()); seed_database(); print('Run 1 - Wards:', db.query(Ward).count(), 'Advisories:', db.query(Advisory).count()); seed_database(); print('Run 2 - Wards:', db.query(Ward).count(), 'Advisories:', db.query(Advisory).count()); db.close()"
     ```
     *Expect*: Row counts remain exactly 10 Wards and 25 Advisories across both runs.
  4. **Verify `risk_engine.py` Was Untouched**:
     ```bash
     git diff backend/app/services/risk_engine.py
     ```
     *Expect*: Zero lines changed (empty diff).
- **Blockers or known limitations**: None.
