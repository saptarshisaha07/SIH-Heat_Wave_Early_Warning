# Task 16 — Heat index model training

- Owner: P4 / ML Team
- Status: PASS
- What was built: Extended `ml/train_model.py` to train a multi-output `RandomForestRegressor` that predicts Heat Index 1, 2, and 3 days ahead ($t+1, t+2, t+3$) per municipal ward in Bhubaneswar using historical daily weather from `ml/historical_weather.csv`. Reused `backend/app/services/thermal_index.py`'s Rothfusz `heat_index()` implementation without duplication. Engineered lag features (`temp_mean` $t, t-1, t-2$; `humidity` $t, t-1$; `wind` $t$), calendar features (`month`, `day_of_year`), and one-hot encoded ward indicators (`ward_id_BBSR-01` to `ward_id_BBSR-10`). Implemented chronological train/test split with dynamic 90-day cutoff, uncherry-picked test MAE evaluation, joblib serialization to `ml/model.pkl`, metadata export to `ml/model_metadata.json`, and automated validation routines with real sample inference.
- Date-range and cutoff diagnostics:
  - Raw Historical Weather CSV: `2024-01-01` to `2025-12-31` (731 daily records per ward across all 10 authoritative wards, 7,310 total rows)
  - Usable Range (after lag/target trimming): `2024-01-03` to `2025-12-28` (726 rows per ward, 7,260 total rows; dropped 5 boundary rows per ward)
  - Computed Test Cutoff Date (`max_date - 90 days`): `2025-10-02`
  - Training set (`< 2025-10-02`): 6,380 rows (638 rows per ward)
  - Held-out chronological test set (`>= 2025-10-02`): 880 rows (88 rows per ward)
- Evaluation Metrics (MAE on held-out chronological test set):
  - Horizon $t+1$ (Day +1 Forecast) MAE: **1.3796 °C**
  - Horizon $t+2$ (Day +2 Forecast) MAE: **1.8251 °C**
  - Horizon $t+3$ (Day +3 Forecast) MAE: **1.9091 °C**
  - Overall Multi-Horizon Average MAE: **1.7046 °C**
- Files changed:
  - `ml/train_model.py` (extended with model training, feature engineering, evaluation, and validation)
  - `ml/requirements.txt` (added `scikit-learn>=1.3.0` and `joblib>=1.3.0`)
  - `ml/model.pkl` (serialized multi-output model bundle and inference metadata)
  - `ml/model_metadata.json` (human-readable metadata sidecar)
  - `BUILD_TASKS/TASK-16-model-training.md` (task build report)
- How to verify:
  1. Run end-to-end model training, evaluation, and validation:
     ```bash
     python ml/train_model.py
     ```
     Expect: exit code 0, printed chronological diagnostics, printed MAE for $t+1, t+2, t+3$, and `FINAL MODEL VALIDATION RESULT: PASS`.
  2. Run validation-only mode:
     ```bash
     python ml/train_model.py --validate-only
     ```
     Expect: exit code 0, dataset validation PASS (10/10 wards, 7,310 rows), saved model validation PASS (loads artifact, executes sample prediction on real row, outputs 3 valid numeric values in physical range).
- Blockers or known limitations: None. Single Multi-Output RandomForestRegressor captures joint multi-day correlation cleanly with low computational overhead.
