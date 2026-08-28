# Task 21 — Simulated SMS/WhatsApp Alert Trigger Service

- **Owner**: P3 (Risk Engineer) / P2 Pair
- **Status**: PASS
- **What was built**:
  - Implemented `POST /api/alerts/simulate` endpoint in `backend/app/main.py` enabling on-demand simulation of automated SMS and WhatsApp heat warning alerts.
  - Implemented multi-channel formatting in `backend/app/services/alerts.py`:
    - `format_sms_message()`: Generates concise, telecom-compliant warning text with ward name, risk category, thermal heat index, advisory headline, and 108/112 emergency helpline numbers.
    - `format_whatsapp_message()`: Generates rich formatted cards with emoji status badges, localized advisory headlines, top 3 protective action items from `get_advisory()`, and emergency helpline numbers.
    - Built strictly from real public health advisories without invented facts or locations.
  - Resolved `ward_id` as an `int` only (matching `wards.id` foreign key) and dynamically reads the ward's current heat index and risk category from the database.
  - Persisted all broadcast simulation events into SQLite `alerts_log` table via `AlertLog` ORM model.
- **Files changed**:
  - `backend/app/models/alert.py` (updated `AlertLog` table schema: `id`, `ward_id`, `channel`, `message`, `status`, `timestamp`)
  - `backend/app/services/alerts.py` (implemented `format_sms_message`, `format_whatsapp_message`, and `build_simulated_alert`)
  - `backend/app/main.py` (added `AlertSimulateRequest` model and `POST /api/alerts/simulate` route)
  - `BUILD_TASKS/TASK-21-alerts.md` (new file: task build report)
- **API Contract**:
  - **Route**: `POST /api/alerts/simulate`
  - **Request Body**:
    ```json
    {
      "ward_id": 1,
      "channel": "sms"
    }
    ```
    *(where `channel` defaults to `"sms"`, supports `"sms"` or `"whatsapp"`)*
  - **Response Payload**:
    ```json
    {
      "ward_id": 1,
      "channel": "sms",
      "status": "simulated",
      "message": "HEAT ALERT: Bhubaneswar Zone 01 is under EXTREME CAUTION risk (Heat Index: 32.4°C). High Heat Stress Warning for Outdoor Workers & Vulnerable Groups. Dial 108/112 for emergencies. - BMC Heat Cell",
      "timestamp": "2026-08-28T19:37:44.776411+00:00"
    }
    ```
- **How to verify**:
  1. **Run full backend unit test suite**:
     ```bash
     cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p \"test_*.py\""
     ```
     *Expect*: All 45 tests pass (`OK`).
  2. **Test live API simulation**:
     ```bash
     cmd /c "cd backend && .venv\Scripts\python.exe -c \"from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); print(c.post('/api/alerts/simulate', json={'ward_id': 1, 'channel': 'sms'}).json())\""
     ```
     *Expect*: Returns HTTP 200 with valid simulated SMS text and records row in `alerts_log`.
- **Blockers or known limitations**: None.
