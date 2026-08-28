"""Unit tests for Multi-Ward Weather Ingestion & Scheduler Service (Task 11)."""

import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.risk import RiskScore
from app.models.ward import Ward
from app.models.weather import WeatherReading
from app.scheduler import (
    get_scheduler,
    ingest_all_wards_weather,
    shutdown_scheduler,
    start_scheduler,
)
from app.seed import seed_database


class TestSchedulerService(unittest.TestCase):
    """Test suite verifying scheduled batch ingestion and POST /api/refresh endpoint."""

    @classmethod
    def setUpClass(cls):
        """Initialize database tables and ensure wards are seeded."""
        init_db()
        seed_database()
        cls.client = TestClient(app)

    def setUp(self):
        """Create a fresh database session for test isolation."""
        self.db: Session = SessionLocal()

    def tearDown(self):
        """Close session and ensure background scheduler is stopped."""
        self.db.close()
        shutdown_scheduler()

    def test_01_ingest_all_wards_weather(self):
        """Verify batch weather ingestion inserts records for all wards."""
        wards_count = self.db.query(Ward).count()
        self.assertGreater(wards_count, 0, "Database must have seeded wards.")

        initial_readings_count = self.db.query(WeatherReading).count()
        initial_risk_count = self.db.query(RiskScore).count()

        summary = ingest_all_wards_weather(self.db)

        self.assertIn(summary["status"], ["ok", "partial"])
        self.assertGreaterEqual(summary["wards_processed"], 1)
        self.assertGreaterEqual(summary["readings_inserted"], 1)
        self.assertGreaterEqual(summary["risk_scores_inserted"], 1)

        new_readings_count = self.db.query(WeatherReading).count()
        new_risk_count = self.db.query(RiskScore).count()

        self.assertGreater(new_readings_count, initial_readings_count)
        self.assertGreater(new_risk_count, initial_risk_count)

        # Inspect latest inserted reading
        latest_reading = (
            self.db.query(WeatherReading)
            .order_by(WeatherReading.id.desc())
            .first()
        )
        self.assertIsNotNone(latest_reading)
        self.assertIsInstance(latest_reading.temperature, float)
        self.assertIsInstance(latest_reading.relative_humidity, float)
        self.assertIsInstance(latest_reading.heat_index, float)
        self.assertIsInstance(latest_reading.wet_bulb_temp, float)

        # Inspect latest inserted risk score
        latest_risk = (
            self.db.query(RiskScore)
            .order_by(RiskScore.id.desc())
            .first()
        )
        self.assertIsNotNone(latest_risk)
        self.assertIsInstance(latest_risk.hazard_score, float)
        self.assertIsInstance(latest_risk.risk_score, float)
        self.assertIn(
            latest_risk.risk_level,
            ["Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"],
        )

    def test_02_post_api_refresh_endpoint(self):
        """Verify POST /api/refresh triggers on-demand ingestion successfully."""
        response = self.client.post("/api/refresh")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn(data["status"], ["ok", "partial"])
        self.assertIn("wards_processed", data)
        self.assertIn("readings_inserted", data)
        self.assertIn("risk_scores_inserted", data)
        self.assertIn("timestamp", data)
        self.assertGreaterEqual(data["wards_processed"], 1)

    def test_03_scheduler_lifecycle(self):
        """Verify scheduler initialization, job registration, and graceful shutdown."""
        scheduler = start_scheduler(interval_minutes=45)
        self.assertTrue(scheduler.running)

        job = scheduler.get_job("weather_ingestion_job")
        self.assertIsNotNone(job)
        self.assertEqual(job.name, "Multi-Ward Weather Ingestion")

        shutdown_scheduler()


if __name__ == "__main__":
    unittest.main()
