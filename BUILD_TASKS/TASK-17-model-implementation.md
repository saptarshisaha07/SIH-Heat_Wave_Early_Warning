# Task 17 — ML Model Implementation and Forecast Service

- **Owner**: P4 / ML & Backend Team
- **Status**: PASS
- **What was built**: Implemented the ML Model Inference and Multi-Horizon Forecast Service in `backend/app/services/ml_model.py`. The service loads the pre-trained multi-output `RandomForestRegressor` from `ml/model.pkl` with module-level caching via `joblib`, queries `weather_readings` grouped by calendar date (`func.date(WeatherReading.timestamp)`), extracts daily-aggregated means and maxima across the 3 most recent distinct days to form an 18-element feature vector matching `ml/train_model.py`, executes multi-horizon prediction for $t+1, t+2, t+3$ Heat Index in °C, categorizes predictions into 5-band thermal risk categories via `backend/app/services/risk_engine.py`, persists `Forecast` rows to SQLite, and returns a JSON payload matching the contract for Task 18 (`GET /api/wards/{id}`).
- **Files changed**:
  - `backend/app/services/ml_model.py` (implemented ML inference, feature extraction, caching, and database persistence)
  - `backend/tests/test_ml_model.py` (automated test suite covering 7 unit test cases)
  - `BUILD_TASKS/TASK-17-model-implementation.md` (task build report)
- **How to verify**:
  1. **Run the automated unit test suite**:
     ```bash
     python -m unittest backend/tests/test_ml_model.py
     ```
     *Expect*: 7/7 tests pass (`OK`).
  2. **Run manual verification / standalone test**:
     ```bash
     python backend/app/services/ml_model.py
     ```
     *Expect*: Prints extracted feature vector of shape `(1, 18)`, generated 3-day forecast predictions (`37.65 °C`, `37.76 °C`, `38.93 °C`), and verifies 3 `Forecast` records committed to SQLite.
- **Blockers or known limitations**:
  - **Cold-Start Requirement**: Requires at least 3 distinct calendar days of `weather_readings` per ward before forecasts can be produced.
  - **`predicted_temp` Database Placeholder**: `predicted_temp` in the `forecasts` table holds `predicted_heat_index` to satisfy a legacy schema NOT NULL constraint.
  - **Atmospheric Generalization**: The Random Forest model was trained on 2024–2025 Open-Meteo historical reanalysis data for Bhubaneswar municipal coordinates.

---

## 1. Feature Schema
The inference service constructs an input feature matrix of shape `(1, 18)`. The columns strictly match the training pipeline's feature order and nomenclature:

| Index | Feature Name | Description | Source / Aggregation |
| :--- | :--- | :--- | :--- |
| 1 | `temp_mean_lag0` | Mean temperature on day $t$ (most recent) | Daily average of `weather_readings.temperature` on day $t$ |
| 2 | `temp_mean_lag1` | Mean temperature on day $t-1$ | Daily average of `weather_readings.temperature` on day $t-1$ |
| 3 | `temp_mean_lag2` | Mean temperature on day $t-2$ | Daily average of `weather_readings.temperature` on day $t-2$ |
| 4 | `humidity_lag0` | Mean relative humidity on day $t$ | Daily average of `weather_readings.relative_humidity` on day $t$ |
| 5 | `humidity_lag1` | Mean relative humidity on day $t-1$ | Daily average of `weather_readings.relative_humidity` on day $t-1$ |
| 6 | `wind_speed_lag0` | Maximum wind speed on day $t$ | Daily maximum of `weather_readings.wind_speed` on day $t$ |
| 7 | `month` | Calendar month (1–12) | Extracted from timestamp date of day $t$ |
| 8 | `day_of_year` | Day of year (1–366) | Extracted from timestamp date of day $t$ |
| 9 | `ward_id_BBSR-01` | One-hot indicator for Ward 1 | 1 if `ward.ward_number == "BBSR-01"`, else 0 |
| 10 | `ward_id_BBSR-02` | One-hot indicator for Ward 2 | 1 if `ward.ward_number == "BBSR-02"`, else 0 |
| 11 | `ward_id_BBSR-03` | One-hot indicator for Ward 3 | 1 if `ward.ward_number == "BBSR-03"`, else 0 |
| 12 | `ward_id_BBSR-04` | One-hot indicator for Ward 4 | 1 if `ward.ward_number == "BBSR-04"`, else 0 |
| 13 | `ward_id_BBSR-05` | One-hot indicator for Ward 5 | 1 if `ward.ward_number == "BBSR-05"`, else 0 |
| 14 | `ward_id_BBSR-06` | One-hot indicator for Ward 6 | 1 if `ward.ward_number == "BBSR-06"`, else 0 |
| 15 | `ward_id_BBSR-07` | One-hot indicator for Ward 7 | 1 if `ward.ward_number == "BBSR-07"`, else 0 |
| 16 | `ward_id_BBSR-08` | One-hot indicator for Ward 8 | 1 if `ward.ward_number == "BBSR-08"`, else 0 |
| 17 | `ward_id_BBSR-09` | One-hot indicator for Ward 9 | 1 if `ward.ward_number == "BBSR-09"`, else 0 |
| 18 | `ward_id_BBSR-10` | One-hot indicator for Ward 10 | 1 if `ward.ward_number == "BBSR-10"`, else 0 |

> **Pipeline Warning**: This feature order and aggregation method (`func.avg` for temperature/humidity, `func.max` for wind speed) must match `ml/train_model.py` exactly. Any changes in feature definitions in either file will cause feature misalignment during inference.

---

## 2. Key Design Decisions

- **Daily Aggregation vs. Raw Sensor Rows**: `get_recent_features` groups `WeatherReading` records by calendar date (`func.date(WeatherReading.timestamp)`) and takes the last 3 distinct days. This mirrors the daily granularity of Open-Meteo's archive on which `ml/train_model.py` was trained, avoiding lag distortions from uneven hourly timestamps.
- **`predicted_temp` NOT NULL Constraint Handling**: The `Forecast` ORM table specifies `predicted_temp = Column(Float, nullable=False)`. Because the model predicts Heat Index directly rather than dry-bulb temperature, `predicted_temp` stores `predicted_heat_index` as a proxy value. Codebase checks confirmed that neither `backend/app/main.py` nor `frontend/js/*.js` reads `predicted_temp` expecting real temperature; all consumers use `predicted_heat_index`.
- **Dynamic One-Hot Vector Generation**: One-hot ward indicators are dynamically resolved from `bundle["feature_columns"]` loaded from `ml/model.pkl`, preventing brittle hardcoding.
- **Specific Error Handling**: Raises clear `ValueError` exceptions naming the exact `ward_id`, date, and missing field if a ward is missing, $< 3$ distinct daily aggregates exist, or null values are encountered.

---

## 3. API Contract (Return Shape)

### Signature
```python
def predict_forecast(db: Session, ward_id: int) -> List[Dict[str, Any]]:
    """Predict Heat Index for t+1, t+2, t+3, record Forecast rows in DB, and return structured results."""
```

### Response Payload
```json
[
  {
    "date": "2026-08-29",
    "predicted_heat_index": 37.65,
    "predicted_risk_category": "Extreme Caution"
  },
  {
    "date": "2026-08-30",
    "predicted_heat_index": 37.76,
    "predicted_risk_category": "Extreme Caution"
  },
  {
    "date": "2026-08-31",
    "predicted_heat_index": 38.93,
    "predicted_risk_category": "Extreme Caution"
  }
]
```

---

## 4. Test Coverage & Verification Details

### Automated Test Suite (`backend/tests/test_ml_model.py`)
All 7 unit tests pass cleanly (`Ran 7 tests in 1.316s, OK`):
- `test_01_load_ml_model_cached`: Confirms `load_ml_model()` loads the dictionary bundle and caches the memory reference across repeated invocations.
- `test_02_load_ml_model_missing_file`: Confirms `FileNotFoundError` is raised when passing an invalid model path.
- `test_03_get_recent_features_nonexistent_ward`: Confirms `ValueError` is raised when requesting features for an unseeded ward ID.
- `test_04_get_recent_features_insufficient_data`: Confirms `ValueError` is raised when $< 3$ distinct calendar days of data exist.
- `test_05_get_recent_features_exact_schema_and_order`: Validates that the returned DataFrame has shape `(1, 18)`, exact matching columns, correct one-hot encoding for the active ward, and accurate lag values.
- `test_06_predict_forecast_success_and_db_persistence`: Validates end-to-end inference, correct return schema, and insertion of 3 `Forecast` records into SQLite with valid timestamps and risk categories.
- `test_07_predict_forecast_nonexistent_ward`: Confirms `ValueError` handling in `predict_forecast`.
