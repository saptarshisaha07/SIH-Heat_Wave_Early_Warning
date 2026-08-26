# Task 06 — Weather fetcher

- Owner: P2
- Status: PARTIAL
- What was built: Implemented `fetch_weather(lat, lon)` service in `backend/app/services/weather_fetcher.py` to fetch real-time weather readings and 5-day forward forecasts from the Open-Meteo Forecast API with strict coordinate bounds validation, error handling, unit normalization, and excluding current/past dates from the forecast array.
- Files changed:
  - `backend/app/services/weather_fetcher.py`
  - `BUILD_TASKS/TASK-06-weather-fetcher.md`
- How to verify:
  1. Ensure `requests` is installed in the Python environment.
  2. Run the live verification smoke test from the repository root:
     ```bash
     cmd /c "set PYTHONPATH=backend&& py -c ""from app.services.weather_fetcher import fetch_weather; data = fetch_weather(28.6139, 77.2090); required = {'temp_c', 'humidity_pct', 'wind_kmh', 'solar_radiation', 'forecast'}; assert required.issubset(data.keys()), data.keys(); assert isinstance(data['forecast'], list); assert len(data['forecast']) == 5, len(data['forecast']); assert isinstance(data['temp_c'], (int, float)); assert isinstance(data['humidity_pct'], (int, float)); assert isinstance(data['wind_kmh'], (int, float)); assert data['solar_radiation'] is None or isinstance(data['solar_radiation'], (int, float)); forecast_keys = {'date', 'temp_max_c', 'temp_min_c', 'humidity_max_pct', 'wind_max_kmh', 'solar_radiation_sum'}; dates = []; [dates.append(day['date']) for day in data['forecast'] if forecast_keys.issubset(day.keys()) and isinstance(day['temp_max_c'], (int, float)) and isinstance(day['temp_min_c'], (int, float)) and isinstance(day['humidity_max_pct'], (int, float)) and isinstance(day['wind_max_kmh'], (int, float)) and (day['solar_radiation_sum'] is None or isinstance(day['solar_radiation_sum'], (int, float)))]; assert len(dates) == 5; assert len(set(dates)) == 5, dates; print('Task 6 live smoke test passed'); print(data)"""
     ```
  3. Success criteria: Returns exit code 0, prints `'Task 6 live smoke test passed'`, returns normalized current weather dictionary and exactly 5 distinct forward forecast day objects.
- Blockers or known limitations:
  - Tested using temporary development coordinates (Lat: 28.6139, Lon: 77.2090 / New Delhi). Final status remains PARTIAL until P1 supplies and validates the target city coordinates.
  - `requests` is required by `weather_fetcher.py`; P1 should record `requests>=2.28.0` in `backend/requirements.txt`.
