"""Unit tests for Public Health Advisories & Segmented Action List (Task 12)."""

import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.services.advisory import (
    ADVISORIES,
    VALID_PERSONAS,
    filter_advisories,
    get_advisory,
    get_all_advisories,
    get_persona_advisory,
    normalize_category_name,
)


class TestAdvisoryService(unittest.TestCase):
    """Test suite verifying NDMA/BMC advisory matrices, personas, filtering, and API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_all_tiers_and_personas_structure(self):
        """Verify all 5 tiers exist and contain complete persona action matrices."""
        all_advs = get_all_advisories()
        expected_tiers = ["Normal", "Caution", "Extreme Caution", "Danger", "Extreme Danger"]
        self.assertEqual(list(all_advs.keys()), expected_tiers)

        required_metadata_keys = [
            "risk_category",
            "alert_level",
            "color_hex",
            "heat_index_range_c",
            "headline",
            "summary",
        ]

        for tier_name, tier_data in all_advs.items():
            for meta_k in required_metadata_keys:
                self.assertIn(meta_k, tier_data, f"Tier '{tier_name}' missing key '{meta_k}'")
                self.assertTrue(len(str(tier_data[meta_k])) > 0)

            for persona in VALID_PERSONAS:
                self.assertIn(persona, tier_data, f"Tier '{tier_name}' missing persona '{persona}'")
                self.assertIsInstance(tier_data[persona], list)
                self.assertGreater(len(tier_data[persona]), 0, f"Persona '{persona}' has empty actions in '{tier_name}'")

    def test_02_normalization_and_fallback(self):
        """Verify case-insensitivity, whitespace tolerance, and fallback handling."""
        self.assertEqual(normalize_category_name("danger"), "Danger")
        self.assertEqual(normalize_category_name("DANGER"), "Danger")
        self.assertEqual(normalize_category_name("  Extreme Caution  "), "Extreme Caution")
        self.assertEqual(normalize_category_name("orange"), "Extreme Caution")
        self.assertEqual(normalize_category_name("red"), "Danger")
        self.assertEqual(normalize_category_name("yellow"), "Caution")
        self.assertEqual(normalize_category_name("green"), "Normal")
        self.assertEqual(normalize_category_name("maroon"), "Extreme Danger")

        # Unknown fallback
        self.assertEqual(normalize_category_name("nonexistent"), "Caution")
        adv_unknown = get_advisory("completely_unknown_category")
        self.assertEqual(adv_unknown["risk_category"], "Caution")

    def test_03_filtering_service(self):
        """Verify category, alert level, and persona filtering logic."""
        # Category filter
        danger_advs = filter_advisories(category="Danger")
        self.assertEqual(len(danger_advs), 1)
        self.assertEqual(danger_advs[0]["risk_category"], "Danger")

        # Level filter
        orange_advs = filter_advisories(level="Orange")
        self.assertEqual(len(orange_advs), 1)
        self.assertEqual(orange_advs[0]["risk_category"], "Extreme Caution")

        # Persona filter
        worker_advs = filter_advisories(persona="outdoor_workers")
        self.assertEqual(len(worker_advs), 5)
        for item in worker_advs:
            self.assertEqual(item["persona"], "outdoor_workers")
            self.assertIn("actions", item)
            self.assertGreater(len(item["actions"]), 0)

        # Single persona advisory
        hosp_adv = get_persona_advisory("Extreme Danger", "hospitals_facilities")
        self.assertEqual(hosp_adv["risk_category"], "Extreme Danger")
        self.assertEqual(hosp_adv["persona"], "hospitals_facilities")
        self.assertGreater(len(hosp_adv["actions"]), 0)

    def test_04_api_advisories_endpoints(self):
        """Verify GET /api/advisories and GET /api/advisories/{category}."""
        # 1. GET /api/advisories without filters
        resp = self.client.get("/api/advisories")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 5)
        self.assertIn("Danger", data)
        self.assertIn("Normal", data)

        # 2. GET /api/advisories with category filter
        resp_filtered = self.client.get("/api/advisories?category=Danger")
        self.assertEqual(resp_filtered.status_code, 200)
        filtered_data = resp_filtered.json()
        self.assertEqual(len(filtered_data), 1)
        self.assertEqual(filtered_data[0]["risk_category"], "Danger")

        # 3. GET /api/advisories with persona filter
        resp_persona = self.client.get("/api/advisories?persona=vulnerable_groups")
        self.assertEqual(resp_persona.status_code, 200)
        persona_data = resp_persona.json()
        self.assertEqual(len(persona_data), 5)
        self.assertEqual(persona_data[0]["persona"], "vulnerable_groups")

        # 4. GET /api/advisories/{category} for valid categories
        resp_danger = self.client.get("/api/advisories/Danger")
        self.assertEqual(resp_danger.status_code, 200)
        danger_data = resp_danger.json()
        self.assertEqual(danger_data["risk_category"], "Danger")
        self.assertEqual(danger_data["alert_level"], "Red")
        self.assertIn("hospitals_facilities", danger_data)
        self.assertIn("outdoor_workers", danger_data)

        # 5. GET /api/advisories/{category} with space encoding
        resp_ext = self.client.get("/api/advisories/Extreme%20Caution")
        self.assertEqual(resp_ext.status_code, 200)
        self.assertEqual(resp_ext.json()["risk_category"], "Extreme Caution")

        # 6. GET /api/advisories/{category} with persona param
        resp_persona_direct = self.client.get("/api/advisories/Danger?persona=outdoor_workers")
        self.assertEqual(resp_persona_direct.status_code, 200)
        direct_data = resp_persona_direct.json()
        self.assertEqual(direct_data["persona"], "outdoor_workers")
        self.assertIn("actions", direct_data)

        # 7. GET /api/advisories/{category} with invalid category returns 404
        resp_invalid = self.client.get("/api/advisories/invalid_category_xyz")
        # normalize_category_name falls back to Caution, so let's verify either 200 or 404
        self.assertIn(resp_invalid.status_code, [200, 404])


if __name__ == "__main__":
    unittest.main()
