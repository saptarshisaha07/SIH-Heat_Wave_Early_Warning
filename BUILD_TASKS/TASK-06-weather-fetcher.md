# Task 06 — Weather fetcher

- Owner: P2
- Status: PASS
- What was built: Implemented `fetch_weather(lat, lon)` service in `backend/app/services/weather_fetcher.py` to fetch real-time weather readings and 5-day forward forecasts from the Open-Meteo Forecast API with strict coordinate bounds validation, error handling, unit normalization, and excluding current/past dates from the forecast array.
- Files changed:
  - `backend/app/services/weather_fetcher.py`
  - `BUILD_TASKS/TASK-06-weather-fetcher.md`
- How to verify:
  1. From `backend/` directory, run the live verification command using the canonical Bhubaneswar ward coordinate (`BBSR-01`: `20.2961, 85.8245` from `backend/data/wards.geojson`):
     ```bash
     .venv\Scripts\python.exe -c "from app.services.weather_fetcher import fetch_weather; from datetime import date; lat,lon=20.2961,85.8245; d=fetch_weather(lat,lon); required={'temp_c','humidity_pct','wind_kmh','solar_radiation','forecast'}; assert required.issubset(d), d.keys(); assert isinstance(d['temp_c'],(int,float)); assert isinstance(d['humidity_pct'],(int,float)); assert isinstance(d['wind_kmh'],(int,float)); assert d['solar_radiation'] is None or isinstance(d['solar_radiation'],(int,float)); assert isinstance(d['forecast'],list) and len(d['forecast'])==5; keys={'date','temp_max_c','temp_min_c','humidity_max_pct','wind_max_kmh','solar_radiation_sum'}; assert all(keys.issubset(x) for x in d['forecast']); dates=[x['date'] for x in d['forecast']]; assert len(set(dates))==5; assert all(str(x) != str(date.today()) for x in dates); print('ward: BBSR-01'); print('coordinates:',lat,lon); print('forecast dates:',dates); print('Task 6 final Bhubaneswar verification: PASS')"
     ```
  2. Success criteria: Performs a real Open-Meteo request, prints `ward: BBSR-01`, `coordinates: 20.2961 85.8245`, 5 unique forward forecast dates, and `Task 6 final Bhubaneswar verification: PASS`.
- Blockers or known limitations: none
