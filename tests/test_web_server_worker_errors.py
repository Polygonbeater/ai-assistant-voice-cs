import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from web_server import app


class ChatWorkerErrorTests(unittest.TestCase):
    def test_methodology_classifier_failure_is_sent_as_sse_error(self):
        client = TestClient(app, headers={"X-Polygon-Client": "true"})

        with (
            patch("web_server.get_llm", return_value=MagicMock()),
            patch("web_server.classify_methodology", side_effect=RuntimeError("classifier failed")),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "session_id": "worker-error-test",
                    "prompt": "Test classifier failure",
                    "analytical_preset": "⚡ Auto (Doporučit)",
                    "rag_enabled": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        events = [line for line in response.iter_lines() if line.startswith("data: ")]
        self.assertTrue(any('"type": "error"' in event for event in events))
        self.assertTrue(any("classifier failed" in event for event in events))


if __name__ == "__main__":
    unittest.main()
