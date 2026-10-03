import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from web_server import app


class ChatWorkerErrorTests(unittest.TestCase):
    def test_answer_tokens_are_not_duplicated_or_mixed_with_tool_notifications(self):
        client = TestClient(app, headers={"X-Polygon-Client": "true"})

        def generate_with_answer_callback(*args, **kwargs):
            callback_on_token = kwargs["callback_on_token"]
            callback_on_answer_token = kwargs["callback_on_answer_token"]
            callback_on_token("Tool call notification")
            for token in ("Final ", "answer."):
                callback_on_token(token)
                callback_on_answer_token(token)
            yield "Final answer."

        with (
            patch("web_server.get_llm", return_value=MagicMock()),
            patch(
                "web_server.generate_response",
                side_effect=generate_with_answer_callback,
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "session_id": "worker-answer-callback-test",
                    "prompt": "Test streamed answer",
                    "language": "en",
                    "rag_enabled": False,
                },
            )

        events = [
            json.loads(line[6:])
            for line in response.iter_lines()
            if line.startswith("data: {")
        ]
        token_events = [
            event["content"] for event in events if event.get("type") == "token"
        ]
        self.assertEqual(token_events, ["Tool call notification", "Final ", "answer."])
        self.assertEqual(
            next(event["content"] for event in events if event.get("type") == "done"),
            "Final answer.",
        )

    def test_yielded_chunks_reach_sse_when_callback_omits_final_response(self):
        client = TestClient(app, headers={"X-Polygon-Client": "true"})

        def generate_without_final_token_callback(*args, **kwargs):
            callback_on_token = kwargs.get("callback_on_token")
            if callback_on_token:
                callback_on_token("Tool call notification")
            yield "Final answer from yielded chunks."

        with (
            patch("web_server.get_llm", return_value=MagicMock()),
            patch(
                "web_server.generate_response",
                side_effect=generate_without_final_token_callback,
            ),
        ):
            response = client.post(
                "/api/chat",
                json={
                    "session_id": "worker-yield-fallback-test",
                    "prompt": "Test yielded response",
                    "language": "en",
                    "rag_enabled": False,
                },
            )

        events = [
            json.loads(line[6:])
            for line in response.iter_lines()
            if line.startswith("data: {")
        ]
        self.assertTrue(
            any(
                event.get("type") == "token"
                and event.get("content") == "Final answer from yielded chunks."
                for event in events
            )
        )
        self.assertTrue(
            any(
                event.get("type") == "done"
                and event.get("content") == "Final answer from yielded chunks."
                for event in events
            )
        )
        self.assertEqual(
            sum(
                event.get("type") == "token"
                and event.get("content") == "Final answer from yielded chunks."
                for event in events
            ),
            1,
        )

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
                    "language": "cs",
                    "analytical_preset": "⚡ Auto (Doporučit)",
                    "rag_enabled": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream; charset=utf-8", response.headers["content-type"])
        self.assertIn("Určuji optimální analytickou metodiku…".encode("utf-8"), response.content)
        events = [line for line in response.iter_lines() if line.startswith("data: ")]
        self.assertTrue(any('"type": "error"' in event for event in events))
        self.assertTrue(any("classifier failed" in event for event in events))


if __name__ == "__main__":
    unittest.main()
