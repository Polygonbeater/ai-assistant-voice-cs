import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

import web_server


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class TestOpenExternalUrl(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_server.app, headers={"X-Polygon-Client": "true"})

    def test_rejects_invalid_url_syntax_before_network_access(self):
        invalid_urls = [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/html,hello",
            "https://example.com:invalid",
            "https://",
            " https://example.com",
            "https://user:password@example.com",
        ]

        with (
            patch("web_server.is_safe_web_url") as is_safe_web_url,
            patch("web_server._safe_get") as safe_get,
            patch("web_server.webbrowser.open_new_tab") as open_new_tab,
        ):
            for url in invalid_urls:
                with self.subTest(url=url):
                    response = self.client.post("/api/open-external-url", json={"url": url})
                    self.assertEqual(response.status_code, 400)

        is_safe_web_url.assert_not_called()
        safe_get.assert_not_called()
        open_new_tab.assert_not_called()

    def test_rejects_unsafe_host_before_network_access(self):
        with (
            patch("web_server.is_safe_web_url", return_value=False),
            patch("web_server._safe_get") as safe_get,
            patch("web_server.webbrowser.open_new_tab") as open_new_tab,
        ):
            response = self.client.post(
                "/api/open-external-url",
                json={"url": "http://127.0.0.1/private"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")
        safe_get.assert_not_called()
        open_new_tab.assert_not_called()

    def test_opens_valid_url_in_default_browser_after_successful_check(self):
        checked_response = Mock(status=200)
        session = FakeSession()
        with (
            patch("web_server.is_safe_web_url", return_value=True),
            patch("web_server.aiohttp.ClientSession", return_value=session),
            patch("web_server._safe_get", new=AsyncMock(return_value=checked_response)) as safe_get,
            patch("web_server.webbrowser.open_new_tab", return_value=True) as open_new_tab,
        ):
            response = self.client.post(
                "/api/open-external-url",
                json={"url": "https://example.com/article"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        checked_response.release.assert_called_once()
        safe_get.assert_awaited_once()
        open_new_tab.assert_called_once_with("https://example.com/article")

    def test_accepts_long_google_news_style_token_urls(self):
        token = "Abcdefghijklmnopqrstuvwxyz0123456789-_" * 300
        url = f"https://news.google.com/rss/articles/{token}?hl=en-US&gl=US&ceid=US:en"
        checked_response = Mock(status=200)
        with (
            patch("web_server.is_safe_web_url", return_value=True),
            patch("web_server.aiohttp.ClientSession", return_value=FakeSession()),
            patch("web_server._safe_get", new=AsyncMock(return_value=checked_response)) as safe_get,
            patch("web_server.webbrowser.open_new_tab", return_value=True),
        ):
            response = self.client.post("/api/open-external-url", json={"url": url})

        self.assertEqual(response.status_code, 200)
        safe_get.assert_awaited_once()

    def test_unavailable_or_missing_url_is_not_opened(self):
        for checked_response in (None, Mock(status=404)):
            with self.subTest(response=checked_response):
                with (
                    patch("web_server.is_safe_web_url", return_value=True),
                    patch("web_server.aiohttp.ClientSession", return_value=FakeSession()),
                    patch("web_server._safe_get", new=AsyncMock(return_value=checked_response)),
                    patch("web_server.webbrowser.open_new_tab") as open_new_tab,
                ):
                    response = self.client.post(
                        "/api/open-external-url",
                        json={"url": "https://example.com/missing"},
                    )

                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json()["status"], "error")
                open_new_tab.assert_not_called()


if __name__ == "__main__":
    unittest.main()
