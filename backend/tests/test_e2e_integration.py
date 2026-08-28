"""End-to-end integration tests for single-server FastAPI frontend/backend integration."""

import unittest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.ward import Ward
from app.seed import seed_database


class TestEndToEndIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.client = TestClient(app)

    def setUp(self):
        self.db: Session = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_root_serves_frontend_html(self):
        """Verify GET / serves frontend index.html with 200 OK."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("Bhubaneswar Heatwave Early Warning", response.text)
        self.assertIn("id=\"map\"", response.text)
        self.assertIn("id=\"ward-details\"", response.text)

    def test_02_static_javascript_assets_served(self):
        """Verify static JS files are accessible directly via same port."""
        for js_file in ["/js/map.js", "/js/api.js", "/js/app.js"]:
            res = self.client.get(js_file)
            self.assertEqual(res.status_code, 200, f"Failed to fetch static asset: {js_file}")
            self.assertIn("javascript", res.headers.get("content-type", ""))

    def test_03_risk_map_endpoint_returns_geojson(self):
        """Verify GET /api/risk-map returns GeoJSON FeatureCollection."""
        response = self.client.get("/api/risk-map")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("type"), "FeatureCollection")
        features = data.get("features", [])
        self.assertEqual(len(features), 10)

        # Confirm feature format aligns with map.js expectations
        for feat in features:
            self.assertEqual(feat.get("type"), "Feature")
            self.assertTrue(feat.get("id", "").startswith("BBSR-"))
            props = feat.get("properties", {})
            self.assertIn("id", props)
            self.assertIn("name", props)
            self.assertIn("vulnerability_index", props)
            geom = feat.get("geometry", {})
            self.assertEqual(geom.get("type"), "Point")
            coords = geom.get("coordinates", [])
            self.assertEqual(len(coords), 2)

    def test_04_ward_details_endpoint(self):
        """Verify GET /api/wards/1 returns live risk slice with advisory and forecast."""
        response = self.client.get("/api/wards/1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ward", data)
        self.assertIn("current", data)
        self.assertIn("forecast", data)
        self.assertIn("advisory", data)
        self.assertEqual(data["ward"]["ward_number"], "BBSR-01")

    def test_05_database_seeding_idempotency(self):
        """Verify seed_database is idempotent and does not create duplicate ward records."""
        initial_count = self.db.query(Ward).count()
        self.assertEqual(initial_count, 10)

        # Run seeding again
        seed_database()

        count_after = self.db.query(Ward).count()
        self.assertEqual(count_after, 10, "Seeding must not duplicate ward records.")


if __name__ == "__main__":
    unittest.main()
