"""Unit and integration tests for Task 24 — Cached Fallback Resilience and Re-runnable Seed."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch
import requests
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.advisory import Advisory
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.scheduler import ingest_all_wards_weather, shutdown_scheduler
from app.seed import seed_database
from app.services.weather_fetcher import WeatherFetcherError, fetch_weather


class TestTask24Resilience(unittest.TestCase):
    """Test suite for Open-Meteo network failure resilience and seed idempotency."""

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.db: Session = SessionLocal()

    def tearDown(self):
        self.db.close()
        shutdown_scheduler()

    def test_01_fetch_weather_live_success(self):
        """Verify normal live fetch returns source='live' and expected structure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current": {
                "time": "2026-08-29T12:00",
                "temperature_2m": 34.5,
                "relative_humidity_2m": 68.0,
                "wind_speed_10m": 14.2,
                "shortwave_radiation": 720.0,
            },
            "daily": {
                "time": ["2026-08-29", "2026-08-30", "2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03"],
                "temperature_2m_max": [35.0, 36.0, 36.5, 37.0, 36.0, 35.5],
                "temperature_2m_min": [26.0, 26.5, 27.0, 27.0, 26.5, 26.0],
                "relative_humidity_2m_max": [80.0, 82.0, 85.0, 80.0, 78.0, 80.0],
                "wind_speed_10m_max": [15.0, 16.0, 14.0, 12.0, 15.0, 14.0],
                "shortwave_radiation_sum": [22.0, 23.0, 24.0, 22.5, 23.5, 22.0],
            },
        }

        with patch("requests.get", return_value=mock_response):
            result = fetch_weather(20.2961, 85.8245, db=self.db, ward_id=1)
            self.assertEqual(result["source"], "live")
            self.assertEqual(result["temp_c"], 34.5)
            self.assertEqual(result["humidity_pct"], 68.0)
            self.assertEqual(result["wind_kmh"], 14.2)
            self.assertEqual(result["solar_radiation"], 720.0)
            self.assertEqual(len(result["forecast"]), 5)

    def test_02_fetch_weather_fallback_on_timeout(self):
        """Verify fetch_weather falls back to last cached reading on requests.Timeout."""
        # Ensure ward 1 has at least one reading
        now_utc = datetime.now(timezone.utc)
        reading = WeatherReading(
            ward_id=1,
            timestamp=now_utc,
            temperature=33.3,
            relative_humidity=65.5,
            wind_speed=11.1,
            solar_radiation=600.0,
            heat_index=38.0,
            wet_bulb_temp=28.0,
            apparent_temp=38.0,
        )
        self.db.add(reading)
        self.db.commit()

        with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
            result = fetch_weather(20.2961, 85.8245, db=self.db, ward_id=1)
            self.assertEqual(result["source"], "cached")
            self.assertEqual(result["temp_c"], 33.3)
            self.assertEqual(result["humidity_pct"], 65.5)
            self.assertEqual(result["wind_kmh"], 11.1)
            self.assertEqual(result["solar_radiation"], 600.0)
            self.assertIsInstance(result["forecast"], list)

    def test_03_fetch_weather_fallback_on_http_500(self):
        """Verify fetch_weather falls back to cached reading on HTTP 500 or ConnectionError."""
        with patch("requests.get", side_effect=requests.ConnectionError("Failed to establish a new connection")):
            result = fetch_weather(20.2961, 85.8245, db=self.db, ward_id=1)
            self.assertEqual(result["source"], "cached")
            self.assertIsInstance(result["temp_c"], float)
            self.assertIsInstance(result["humidity_pct"], float)

    def test_04_fetch_weather_no_cached_data_raises_weather_fetcher_error(self):
        """Verify unrecoverable failure raises WeatherFetcherError when ward has 0 cached readings."""
        # Create a temporary ward with no readings
        temp_ward = Ward(
            ward_number="BBSR-TEMP-99",
            name="Temporary Test Ward",
            latitude=20.999,
            longitude=85.999,
            vulnerability_index=0.5,
        )
        self.db.add(temp_ward)
        self.db.commit()
        self.db.refresh(temp_ward)

        try:
            with patch("requests.get", side_effect=requests.ConnectionError("Network down")):
                with self.assertRaises(WeatherFetcherError) as ctx:
                    fetch_weather(temp_ward.latitude, temp_ward.longitude, db=self.db, ward_id=temp_ward.id)
                self.assertIn("no cached weather readings exist", str(ctx.exception))
        finally:
            self.db.delete(temp_ward)
            self.db.commit()

    def test_05_invalid_coordinates_raise_value_error(self):
        """Verify invalid coordinates raise ValueError directly and do not trigger fallback."""
        with self.assertRaises(ValueError):
            fetch_weather(999.0, 85.0)

        with self.assertRaises(ValueError):
            fetch_weather(True, 85.0)

    def test_06_get_ward_endpoint_with_network_failure_returns_200_using_cache(self):
        """Verify GET /api/wards/1 returns HTTP 200 with cached weather when Open-Meteo is unreachable."""
        with patch("requests.get", side_effect=requests.ConnectionError("Open-Meteo unreachable")):
            response = self.client.get("/api/wards/1")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("ward", data)
            self.assertIn("current", data)
            self.assertIn("temp_c", data["current"])
            self.assertIn("heat_index", data["current"])
            self.assertIn("composite_score", data["current"])
            self.assertEqual(data["ward"]["id"], 1)

    def test_07_get_ward_endpoint_uncached_ward_with_network_failure_returns_502(self):
        """Verify GET /api/wards/{id} returns 502 for a ward with zero cached readings when offline."""
        temp_ward = Ward(
            ward_number="BBSR-TEMP-88",
            name="Temporary Uncached Ward",
            latitude=20.888,
            longitude=85.888,
            vulnerability_index=0.4,
        )
        self.db.add(temp_ward)
        self.db.commit()
        self.db.refresh(temp_ward)

        try:
            with patch("requests.get", side_effect=requests.ConnectionError("Network down")):
                response = self.client.get(f"/api/wards/{temp_ward.id}")
                self.assertEqual(response.status_code, 502)
                self.assertIn("detail", response.json())
        finally:
            self.db.delete(temp_ward)
            self.db.commit()

    def test_08_scheduler_ingestion_with_network_failure_uses_cache(self):
        """Verify batch ingestion continues with cached readings during network outage."""
        with patch("requests.get", side_effect=requests.ConnectionError("Open-Meteo unreachable")):
            summary = ingest_all_wards_weather(self.db)
            self.assertIn(summary["status"], ["ok", "partial"])
            self.assertGreaterEqual(summary["wards_processed"], 1)
            self.assertGreater(summary["cached_count"], 0)
            self.assertEqual(summary["live_count"], 0)

    def test_09_refresh_api_endpoint_with_network_failure(self):
        """Verify POST /api/refresh returns 200 with cached breakdown when network fails."""
        with patch("requests.get", side_effect=requests.ConnectionError("Network outage")):
            response = self.client.post("/api/refresh")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn(data["status"], ["ok", "partial"])
            self.assertIn("cached_count", data)
            self.assertGreater(data["cached_count"], 0)

    def test_10_seed_database_idempotency_double_run(self):
        """Verify running seed_database() twice in a row results in exact same row counts."""
        # Initial seed
        seed_database()
        ward_count_1 = self.db.query(Ward).count()
        adv_count_1 = self.db.query(Advisory).count()

        self.assertEqual(ward_count_1, 10)
        self.assertEqual(adv_count_1, 25)

        # Second seed run
        seed_database()
        ward_count_2 = self.db.query(Ward).count()
        adv_count_2 = self.db.query(Advisory).count()

        self.assertEqual(ward_count_1, ward_count_2, "Ward count must not change on re-seeding")
        self.assertEqual(adv_count_1, adv_count_2, "Advisory count must not change on re-seeding")
        self.assertEqual(ward_count_2, 10)
        self.assertEqual(adv_count_2, 25)


if __name__ == "__main__":
    unittest.main()
