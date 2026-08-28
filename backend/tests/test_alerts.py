"""Unit tests for Simulated SMS/WhatsApp Alert Trigger Service (Task 21)."""

import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.alert import AlertLog
from app.models.ward import Ward
from app.seed import seed_database
from app.services.alerts import (
    build_simulated_alert,
    format_sms_message,
    format_whatsapp_message,
)


class TestAlertsService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.db: Session = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_format_sms_message(self):
        """Verify SMS alert formatting produces concise telecom-compliant string."""
        msg = format_sms_message(
            ward_name="Bhubaneswar Zone 01",
            risk_category="Extreme Caution",
            heat_index_c=36.5,
            headline="High Heat Stress Warning",
        )
        self.assertIn("HEAT ALERT: Bhubaneswar Zone 01 is under EXTREME CAUTION risk", msg)
        self.assertIn("Heat Index: 36.5°C", msg)
        self.assertIn("High Heat Stress Warning", msg)
        self.assertIn("Dial 108/112", msg)
        self.assertIn("BMC Heat Cell", msg)

    def test_02_format_whatsapp_message(self):
        """Verify WhatsApp alert formatting includes rich card elements and action bullets."""
        msg = format_whatsapp_message(
            ward_name="Bhubaneswar Zone 02",
            risk_category="Danger",
            heat_index_c=44.2,
            headline="Severe Heat Wave Alert",
            precautions=["Drink plenty of water", "Stay indoors between 12-3pm"],
        )
        self.assertIn("HEATWAVE EARLY WARNING NOTICE", msg)
        self.assertIn("Bhubaneswar Zone 02", msg)
        self.assertIn("Danger", msg)
        self.assertIn("44.2°C", msg)
        self.assertIn("Severe Heat Wave Alert", msg)
        self.assertIn("• Drink plenty of water", msg)
        self.assertIn("Dial 108 / 112", msg)

    def test_03_build_simulated_alert_payload_structure(self):
        """Verify build_simulated_alert produces correct response schema."""
        res_sms = build_simulated_alert(
            ward_id=1,
            heat_index_c=38.0,
            channel="sms",
            ward_name="Bhubaneswar Zone 01",
            risk_category="Extreme Caution",
        )
        self.assertEqual(res_sms["ward_id"], 1)
        self.assertEqual(res_sms["ward_name"], "Bhubaneswar Zone 01")
        self.assertEqual(res_sms["channel"], "sms")
        self.assertEqual(res_sms["status"], "simulated")
        self.assertIn("message", res_sms)
        self.assertIn("timestamp", res_sms)

    def test_04_simulate_alert_api_endpoint_sms(self):
        """Verify POST /api/alerts/simulate with channel=sms logs to db and returns 200."""
        resp = self.client.post("/api/alerts/simulate", json={"ward_id": 1, "channel": "sms"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ward_id"], 1)
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["status"], "simulated")
        self.assertIn("HEAT ALERT:", data["message"])

        # Confirm database persistence in alerts_log
        log = (
            self.db.query(AlertLog)
            .filter(AlertLog.ward_id == 1, AlertLog.channel == "sms")
            .order_by(AlertLog.id.desc())
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "simulated")

    def test_05_simulate_alert_api_endpoint_whatsapp(self):
        """Verify POST /api/alerts/simulate with channel=whatsapp logs to db and returns 200."""
        resp = self.client.post("/api/alerts/simulate", json={"ward_id": 1, "channel": "whatsapp"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["ward_id"], 1)
        self.assertEqual(data["channel"], "whatsapp")
        self.assertEqual(data["status"], "simulated")
        self.assertIn("HEATWAVE EARLY WARNING NOTICE", data["message"])

        log = (
            self.db.query(AlertLog)
            .filter(AlertLog.ward_id == 1, AlertLog.channel == "whatsapp")
            .order_by(AlertLog.id.desc())
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "simulated")

    def test_06_simulate_alert_api_endpoint_invalid_ward_404(self):
        """Verify POST /api/alerts/simulate with invalid ward_id returns 404."""
        resp = self.client.post("/api/alerts/simulate", json={"ward_id": 99999, "channel": "sms"})
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
