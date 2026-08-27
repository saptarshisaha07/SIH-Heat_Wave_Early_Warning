"""Focused automated test suite for Task 08 (Critical One-Ward End-to-End Vertical Slice)."""

import unittest
from app.db.session import SessionLocal, init_db
from app.models.ward import Ward
from app.main import get_ward_risk_slice
from app.seed import seed_database
from app.services.risk_engine import (
    compute_base_heat_score,
    compute_composite_risk,
    categorize_risk,
)
from app.services.thermal_index import heat_index, wbgt
from fastapi import HTTPException


class TestP8VerticalSlice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_ward_1_vertical_slice_payload_structure(self):
        """Verify GET /api/wards/1 vertical slice response conforms to required JSON contract."""
        payload = get_ward_risk_slice(1, self.db)

        # 1. Ward block assertions
        self.assertIn("ward", payload)
        ward = payload["ward"]
        self.assertEqual(ward["id"], 1)
        self.assertEqual(ward["ward_number"], "BBSR-01")
        self.assertEqual(ward["name"], "Bhubaneswar Zone 01")
        self.assertIsInstance(ward["elderly_pct"], (int, float))
        self.assertIsInstance(ward["outdoor_worker_pct"], (int, float))
        self.assertIsInstance(ward["vulnerability_index"], float)
        self.assertTrue(0.0 <= ward["vulnerability_index"] <= 1.0)

        # 2. Current conditions assertions
        self.assertIn("current", payload)
        curr = payload["current"]
        required_current_keys = {
            "temp_c",
            "humidity_pct",
            "wind_kmh",
            "solar_radiation",
            "heat_index",
            "wbgt",
            "base_score",
            "vulnerability_adjustment",
            "composite_score",
            "risk_category",
        }
        self.assertTrue(required_current_keys.issubset(curr.keys()))
        self.assertIsInstance(curr["temp_c"], (int, float))
        self.assertIsInstance(curr["humidity_pct"], (int, float))
        self.assertIsInstance(curr["heat_index"], (int, float))
        self.assertIsInstance(curr["wbgt"], (int, float))
        self.assertIsInstance(curr["composite_score"], (int, float))
        self.assertIn(
            curr["risk_category"],
            {"Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"},
        )

        # 3. Forecast block assertions
        self.assertIn("forecast", payload)
        forecast = payload["forecast"]
        self.assertIsInstance(forecast, list)
        self.assertEqual(len(forecast), 5)
        for day in forecast:
            self.assertIn("date", day)
            self.assertIn("predicted_heat_index", day)
            self.assertIn("predicted_risk_category", day)
            self.assertIsInstance(day["predicted_heat_index"], (int, float))
            self.assertIn(
                day["predicted_risk_category"],
                {"Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"},
            )

        # 4. Advisory block assertions
        self.assertIn("advisory", payload)
        adv = payload["advisory"]
        self.assertEqual(adv["risk_category"], curr["risk_category"])
        self.assertIn("headline", adv)
        self.assertIn("general_public", adv)
        self.assertIn("outdoor_workers", adv)

    def test_nonexistent_ward_returns_404(self):
        """Verify requesting non-existent ward ID raises HTTP 404."""
        with self.assertRaises(HTTPException) as ctx:
            get_ward_risk_slice(99999, self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_risk_engine_integration_math(self):
        """Verify mathematical integrity of base score, amplification cap, and risk bands."""
        # 1. Normal (HI < 27 C)
        score_normal = compute_base_heat_score(20.0)
        self.assertEqual(score_normal, 14.81)

        # 2. Caution (27 - 32 C)
        score_caution = compute_base_heat_score(30.0)
        self.assertEqual(score_caution, 32.0)

        # 3. Extreme Caution (32 - 39 C)
        score_ext_caution = compute_base_heat_score(35.5)
        self.assertEqual(score_ext_caution, 50.0)

        # 4. Danger (39 - 51 C)
        score_danger = compute_base_heat_score(45.0)
        self.assertEqual(score_danger, 72.5)

        # 5. Extreme Danger (>= 51 C)
        score_ext_danger = compute_base_heat_score(58.5)
        self.assertEqual(score_ext_danger, 92.5)

        # Composite score amplification with vulnerability index 0.3328 (BBSR-01)
        res = compute_composite_risk(heat_index_c=35.5, vulnerability_index=0.3328)
        self.assertEqual(res["base_heat_score"], 50.0)
        expected_composite = round(50.0 * (1.0 + 0.3 * 0.3328), 2)  # 54.99
        self.assertEqual(res["composite_score"], expected_composite)
        self.assertEqual(res["vulnerability_adjustment"], round(expected_composite - 50.0, 2))


if __name__ == "__main__":
    unittest.main()
