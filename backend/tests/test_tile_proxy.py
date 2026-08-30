import os
import unittest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

from app.db.session import init_db
from app.main import app
from app.seed import seed_database


class TestTileProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        seed_database()
        cls.client = TestClient(app)

    @patch("app.main.httpx.AsyncClient")
    def test_01_proxy_tile_with_carto_key(self, mock_client_cls):
        """Verify /tiles/{z}/{x}/{y}.png proxies to Carto when CARTO_API_KEY is present."""
        fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        mock_resp = httpx.Response(
            status_code=200,
            content=fake_png,
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", "https://a.basemaps.cartocdn.com/dark_all/12/3252/1780.png"),
        )
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        with patch.dict(os.environ, {"CARTO_API_KEY": "test_carto_key_12345"}):
            response = self.client.get("/tiles/12/3252/1780.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("content-type"), "image/png")
            self.assertEqual(response.content, fake_png)
            self.assertIn("max-age=86400", response.headers.get("cache-control", ""))

            # Verify upstream URL contains the Carto key and correct coordinates
            mock_instance.get.assert_called_once()
            called_url = mock_instance.get.call_args[0][0]
            self.assertIn("basemaps.cartocdn.com/dark_all/12/3252/1780.png", called_url)
            self.assertIn("key=test_carto_key_12345", called_url)

    @patch("app.main.httpx.AsyncClient")
    def test_02_proxy_tile_fallback_without_carto_key(self, mock_client_cls):
        """Verify /tiles/{z}/{x}/{y}.png falls back to OpenStreetMap when CARTO_API_KEY is unset."""
        fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        mock_resp = httpx.Response(
            status_code=200,
            content=fake_png,
            headers={"content-type": "image/png"},
            request=httpx.Request("GET", "https://tile.openstreetmap.org/12/3252/1780.png"),
        )
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/tiles/12/3252/1780.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("content-type"), "image/png")
            self.assertEqual(response.content, fake_png)

            mock_instance.get.assert_called_once()
            called_url = mock_instance.get.call_args[0][0]
            self.assertIn("tile.openstreetmap.org/12/3252/1780.png", called_url)
            self.assertNotIn("key=", called_url)

    @patch("app.main.httpx.AsyncClient")
    def test_03_proxy_tile_upstream_error_propagation(self, mock_client_cls):
        """Verify upstream non-200 responses raise appropriate HTTP errors."""
        mock_resp = httpx.Response(
            status_code=404,
            content=b"Not found",
            request=httpx.Request("GET", "https://tile.openstreetmap.org/99/99/99.png"),
        )
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_resp
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/tiles/99/99/99.png")
            self.assertEqual(response.status_code, 404)

    @patch("app.main.httpx.AsyncClient")
    def test_04_proxy_tile_network_error_handled(self, mock_client_cls):
        """Verify network/connection failure returns 502 Bad Gateway."""
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.ConnectError("Network unreachable")
        mock_client_cls.return_value.__aenter__.return_value = mock_instance

        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/tiles/12/3252/1780.png")
            self.assertEqual(response.status_code, 502)

    def test_05_frontend_map_js_contains_no_hardcoded_keys(self):
        """Verify frontend map.js uses /tiles/ and contains zero hardcoded CARTO keys."""
        map_js_response = self.client.get("/js/map.js")
        self.assertEqual(map_js_response.status_code, 200)
        content = map_js_response.text

        self.assertNotIn("CARTO_API_KEY", content)
        self.assertNotIn("cb1_2hv1_1_c5c94b5aadeaa289343a7178", content)
        self.assertIn("'/tiles/{z}/{x}/{y}.png'", content)


if __name__ == "__main__":
    unittest.main()
