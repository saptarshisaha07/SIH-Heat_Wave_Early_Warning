"""Automated test suite for P3 deliverables (Vulnerability Data, Risk Engine, Advisory, Alerts).

Validates mathematical formulas, CSV consistency with GeoJSON, 5-band category transitions,
vulnerability amplification, explainability breakdowns, and alert payload generation.
"""

import json
import unittest
from pathlib import Path

from app.services.vulnerability import (
    load_vulnerability_data,
    get_ward_vulnerability,
    get_all_ward_vulnerabilities,
)
from app.services.risk_engine import (
    compute_base_heat_score,
    categorize_risk,
    compute_composite_risk,
    evaluate_ward_risk,
    RISK_CATEGORIES,
)
from app.services.advisory import get_advisory, get_all_advisories
from app.services.alerts import build_simulated_alert, format_sms_message, format_whatsapp_message


class TestP3RiskEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend_dir = Path(__file__).resolve().parent.parent
        cls.geojson_path = cls.backend_dir / "data" / "wards.geojson"
        cls.csv_path = cls.backend_dir / "data" / "vulnerability.csv"

    def test_01_vulnerability_csv_matches_geojson(self):
        """Verify vulnerability.csv has exact 1:1 ward_id alignment with wards.geojson."""
        self.assertTrue(self.geojson_path.exists(), "wards.geojson must exist")
        self.assertTrue(self.csv_path.exists(), "vulnerability.csv must exist")

        with open(self.geojson_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        geojson_ids = [feat["properties"]["id"] for feat in geojson_data.get("features", [])]
        self.assertEqual(len(geojson_ids), 10, "Expected 10 GeoJSON ward features")

        vuln_data = load_vulnerability_data(reload=True)
        self.assertEqual(len(vuln_data), 10, "Expected 10 vulnerability CSV records")

        for w_id in geojson_ids:
            self.assertIn(w_id, vuln_data, f"Ward ID {w_id} missing from vulnerability dataset")
            record = vuln_data[w_id]
            self.assertGreater(record["population"], 0, "Population must be positive")
            self.assertGreater(record["elderly_pct"], 0.0, "Elderly pct must be positive")
            self.assertGreater(record["outdoor_worker_pct"], 0.0, "Outdoor worker pct must be positive")
            self.assertTrue(0.0 <= record["vulnerability_index"] <= 1.0, "Vulnerability index out of [0, 1]")

    def test_02_vulnerability_normalization_bounds(self):
        """Verify min-max normalization produces valid 0.0-1.0 range and proper min/max values."""
        all_wards = get_all_ward_vulnerabilities()
        self.assertEqual(len(all_wards), 10)

        min_vuln = min(w["vulnerability_index"] for w in all_wards)
        max_vuln = max(w["vulnerability_index"] for w in all_wards)

        self.assertGreaterEqual(min_vuln, 0.0)
        self.assertLessEqual(max_vuln, 1.0)
        self.assertGreater(max_vuln, min_vuln, "Should have demographic spread across wards")

    def test_03_base_heat_score_piecewise_interpolation(self):
        """Verify piecewise linear interpolation across all NWS Heat Index boundary thresholds."""
        # 1. Normal (< 27°C): 0 to 20
        self.assertEqual(compute_base_heat_score(0.0), 0.0)
        self.assertEqual(compute_base_heat_score(13.5), 10.0)
        self.assertEqual(compute_base_heat_score(27.0), 20.0)

        # 2. Caution (27°C - 32°C): 20 to 40
        self.assertEqual(compute_base_heat_score(29.5), 30.0)
        self.assertEqual(compute_base_heat_score(32.0), 40.0)

        # 3. Extreme Caution (32°C - 39°C): 40 to 60
        self.assertEqual(compute_base_heat_score(35.5), 50.0)
        self.assertEqual(compute_base_heat_score(39.0), 60.0)

        # 4. Danger (39°C - 51°C): 60 to 85
        self.assertEqual(compute_base_heat_score(45.0), 72.5)
        self.assertEqual(compute_base_heat_score(51.0), 85.0)

        # 5. Extreme Danger (>= 51°C): 85 to 100 (capped)
        self.assertEqual(compute_base_heat_score(58.5), 92.5)
        self.assertEqual(compute_base_heat_score(66.0), 100.0)
        self.assertEqual(compute_base_heat_score(80.0), 100.0)

    def test_04_composite_risk_math_and_amplification(self):
        """Verify composite score amplification formula and 30% vulnerability cap."""
        # Case A: Zero vulnerability index -> Composite == Base
        res_zero = compute_composite_risk(heat_index_c=35.5, vulnerability_index=0.0)
        self.assertEqual(res_zero["base_heat_score"], 50.0)
        self.assertEqual(res_zero["composite_score"], 50.0)
        self.assertEqual(res_zero["vulnerability_adjustment"], 0.0)
        self.assertFalse(res_zero["is_amplified"])

        # Case B: Maximum vulnerability index (1.0) -> +30% amplification
        res_max = compute_composite_risk(heat_index_c=35.5, vulnerability_index=1.0)
        self.assertEqual(res_max["base_heat_score"], 50.0)
        self.assertEqual(res_max["composite_score"], 65.0)  # 50 * 1.30 = 65.0
        self.assertEqual(res_max["vulnerability_adjustment"], 15.0)
        # 50.0 was Extreme Caution (Orange), 65.0 becomes Danger (Red)
        self.assertEqual(res_max["heat_only_category"], "Extreme Caution")
        self.assertEqual(res_max["risk_category"], "Danger")
        self.assertTrue(res_max["is_amplified"])

        # Case C: Extreme heat score capped at 100.0
        res_extreme = compute_composite_risk(heat_index_c=60.0, vulnerability_index=0.8)
        self.assertEqual(res_extreme["composite_score"], 100.0)

    def test_05_5_band_risk_categories_and_colors(self):
        """Verify 5-band category boundaries and color mappings."""
        bands = [
            (15.0, "Normal", "Green", "#28a745"),
            (25.0, "Caution", "Yellow", "#ffc107"),
            (45.0, "Extreme Caution", "Orange", "#fd7e14"),
            (70.0, "Danger", "Red", "#dc3545"),
            (90.0, "Extreme Danger", "Maroon", "#800000"),
        ]
        for score, expected_cat, expected_level, expected_hex in bands:
            cat_data = categorize_risk(score)
            self.assertEqual(cat_data["category"], expected_cat)
            self.assertEqual(cat_data["alert_level"], expected_level)
            self.assertEqual(cat_data["color_hex"], expected_hex)

    def test_06_advisories_completeness(self):
        """Verify all 5 risk tiers have detailed public health advisory templates."""
        all_advisories = get_all_advisories()
        self.assertEqual(len(all_advisories), 5)

        for cat_name in RISK_CATEGORIES.keys():
            advisory = get_advisory(cat_name)
            self.assertEqual(advisory["risk_category"], cat_name)
            self.assertIn("headline", advisory)
            self.assertIn("general_public", advisory)
            self.assertIn("outdoor_workers", advisory)
            self.assertIn("vulnerable_groups", advisory)
            self.assertIn("municipal_actions", advisory)
            self.assertGreater(len(advisory["general_public"]), 0)
            self.assertGreater(len(advisory["outdoor_workers"]), 0)

    def test_07_alert_simulation_payloads(self):
        """Verify simulated SMS and WhatsApp alert payloads."""
        # Test SMS Alert
        sms_alert = build_simulated_alert("BBSR-05", heat_index_c=44.0, channel="sms")
        self.assertEqual(sms_alert["ward_id"], "BBSR-05")
        self.assertEqual(sms_alert["channel"], "sms")
        self.assertEqual(sms_alert["status"], "simulated")
        self.assertIn("HEAT ALERT", sms_alert["message"])
        self.assertIn("BBSR-05", sms_alert["ward_id"])
        self.assertIn("Rasulgarh", sms_alert["zone_name"])

        # Test WhatsApp Alert
        wa_alert = build_simulated_alert("BBSR-07", heat_index_c=46.5, channel="whatsapp")
        self.assertEqual(wa_alert["ward_id"], "BBSR-07")
        self.assertEqual(wa_alert["channel"], "whatsapp")
        self.assertIn("HEATWAVE EARLY WARNING NOTICE", wa_alert["message"])
        self.assertIn("Old Town", wa_alert["message"])
        self.assertIn("Emergency Helpline", wa_alert["message"])


if __name__ == "__main__":
    unittest.main()
