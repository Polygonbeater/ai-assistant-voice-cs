import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import web_server
from history_repository import HistoryRepository
from web_server import app

# ID relací, které tyto testy vytvářejí – nesmí se nikdy zapsat do reálného sessions/.
ISOLATED_SESSION_IDS = (
    "worker-answer-callback-test",
    "worker-yield-fallback-test",
    "worker-error-test",
)


class ChatWorkerErrorTests(unittest.TestCase):
    """Streamovací testy /api/chat běží proti dočasnému repozitáři relací.

    Bez izolace by testy psaly do reálných ``sessions/`` a přes ``memory_service``
    přestavovaly ``rag_storage/memory``. Proto se v ``setUp`` nahradí modulová
    globální ``web_server.history_repository`` instancí nad temp složkou
    (bez napojené sémantické paměti) a v ``tearDown`` se ověří, že reálné
    úložiště zůstalo beze změny.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="worker-errors-")
        self.addCleanup(self.temp_dir.cleanup)

        self.real_history_repository = web_server.history_repository
        self.repo_patcher = patch(
            "web_server.history_repository",
            HistoryRepository(Path(self.temp_dir.name) / "chat_history.txt"),
        )
        self.repo_patcher.start()
        # addCleanup běží v obráceném pořadí → patch se zruší dřív než temp složka.
        self.addCleanup(self.repo_patcher.stop)

        self.history = web_server.history_repository
        self.assertNotEqual(
            self.history.sessions_dir,
            self.real_history_repository.sessions_dir,
            "Izolovaný repozitář musí mířit do temp složky.",
        )

    def tearDown(self):
        self._assert_real_storage_untouched()

    def _assert_real_storage_untouched(self):
        """Reálné sessions/ a rag_storage/memory nesmí obsahovat testovací data."""
        real_sessions_dir = self.real_history_repository.sessions_dir
        for session_id in ISOLATED_SESSION_IDS:
            self.assertFalse(
                (real_sessions_dir / f"{session_id}.json").exists(),
                f"Test znečistil reálný soubor sessions/{session_id}.json.",
            )
            self.assertFalse(
                (real_sessions_dir / session_id).exists(),
                f"Test znečistil reálnou složku sessions/{session_id}.",
            )

        memory_service = getattr(self.real_history_repository, "memory_service", None)
        memory_dir = getattr(memory_service, "storage_dir", None)
        if memory_dir is None:
            return
        for filename in ("registry.json", "chunks.json"):
            path = Path(memory_dir) / filename
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8")
            for session_id in ISOLATED_SESSION_IDS:
                self.assertNotIn(
                    session_id,
                    content,
                    f"Test znečistil reálnou paměť rag_storage/memory/{filename}.",
                )

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
        # Relace musela vzniknout výhradně v dočasném repozitáři, ne v reálném sessions/.
        self.assertTrue(
            (self.history.sessions_dir / "worker-answer-callback-test.json").is_file(),
            "Relace nebyla zapsána do izolovaného temp repozitáře.",
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
