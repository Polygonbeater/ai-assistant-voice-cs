import unittest
from unittest.mock import patch

from web_search import _safe_get


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or {}
        self.released = False

    def release(self):
        self.released = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requested_urls = []

    async def get(self, url, **kwargs):
        self.requested_urls.append(url)
        return next(self.responses)


class SafeRedirectTests(unittest.IsolatedAsyncioTestCase):
    @patch("web_search.is_safe_web_url", return_value=True)
    async def test_resolves_path_relative_redirect_and_releases_response(self, _is_safe_url):
        redirect = FakeResponse(302, {"Location": "page2"})
        final_response = FakeResponse(200)
        session = FakeSession([redirect, final_response])

        result = await _safe_get(
            session,
            "https://example.com/news/page1",
            timeout=None,
        )

        self.assertIs(result, final_response)
        self.assertTrue(redirect.released)
        self.assertEqual(
            session.requested_urls,
            ["https://example.com/news/page1", "https://example.com/news/page2"],
        )

    @patch("web_search.is_safe_web_url", side_effect=lambda url: url.startswith("https://"))
    async def test_rejects_redirect_to_private_http_host(self, _is_safe_url):
        redirect = FakeResponse(302, {"Location": "http://127.0.0.1/admin"})
        session = FakeSession([redirect])

        result = await _safe_get(session, "https://example.com/start", timeout=None)

        self.assertIsNone(result)
        self.assertTrue(redirect.released)
        self.assertEqual(session.requested_urls, ["https://example.com/start"])


if __name__ == "__main__":
    unittest.main()
