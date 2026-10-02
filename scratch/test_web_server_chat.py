"""
Unit test pro ověření web_server.py /api/chat a ChatRequest schématu.
Testuje odolnost proti 422 chybám (null session_id, chybějící session_id, camelCase/snake_case, extra pole).
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import web_server
from web_server import ChatRequest, app


class TestWebServerChatEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_chat_request_pydantic_schema_validation(self):
        """Ověří, že ChatRequest přijímá různé formáty payloadu bez validační chyby."""
        # Standardní payload
        req1 = ChatRequest(**{"session_id": "test-1", "prompt": "Ahoj"})
        self.assertEqual(req1.session_id, "test-1")
        self.assertEqual(req1.prompt, "Ahoj")

        # Null session_id (což UI posílalo, když byla relace undefined)
        req2 = ChatRequest(**{"session_id": None, "prompt": "Ahoj"})
        self.assertIsNone(req2.session_id)

        # Chybějící session_id, alternativní názvy (camelCase, message, methodology)
        req3 = ChatRequest(**{
            "sessionId": "test-cam",
            "message": "Otázka",
            "toolsEnabled": True,
            "methodology": "Analýza",
            "ragEnabled": False,
        })
        self.assertEqual(req3.sessionId, "test-cam")
        self.assertEqual(req3.message, "Otázka")
        self.assertTrue(req3.toolsEnabled)

        # Extra neznámá pole (nesmí vyvolat 422 díky ConfigDict(extra="allow"))
        req4 = ChatRequest(**{
            "prompt": "Test",
            "extra_unknown_param": 12345,
            "another_field": {"nested": True}
        })
        self.assertEqual(req4.prompt, "Test")

    @patch("web_server.memory_service")
    @patch("web_server.generate_response")
    @patch("web_server.get_llm")
    def test_api_chat_endpoint_null_session_id(self, mock_get_llm, mock_gen, mock_mem):
        """Ověří, že POST /api/chat nevrací 422 při session_id=null."""
        mock_get_llm.return_value = MagicMock()
        mock_gen.return_value = iter(["Ahoj", " světe!"])

        payload = {
            "session_id": None,
            "prompt": "Testovací dotaz",
            "online_mode": True,
            "rag_enabled": False,
        }

        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        lines = list(response.iter_lines())
        self.assertTrue(len(lines) > 0)

    @patch("web_server.memory_service")
    @patch("web_server.generate_response")
    @patch("web_server.get_llm")
    def test_api_chat_endpoint_camel_case_payload(self, mock_get_llm, mock_gen, mock_mem):
        """Ověří, že POST /api/chat správně zpracuje camelCase payload."""
        mock_get_llm.return_value = MagicMock()
        mock_gen.return_value = iter(["Odpověď"])

        payload = {
            "sessionId": "session-camel-case",
            "message": "Jak se máš?",
            "tools_enabled": True,
            "methodology": "⚡ Auto (Doporučit)",
            "rag_enabled": True,
        }

        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        lines = list(response.iter_lines())
        self.assertTrue(len(lines) > 0)

    def test_api_chat_empty_prompt_returns_400(self):
        """Ověří, že prázdný dotaz vrátí HTTP 400 (nikoli 422)."""
        response = self.client.post("/api/chat", json={"prompt": ""})
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_api_sessions_normalization(self):
        """Ověří, že /api/sessions vrací objekty obsahující jak 'id' tak 'session_id'."""
        response = self.client.get("/api/sessions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sessions", data)
        self.assertTrue(len(data["sessions"]) > 0)
        first = data["sessions"][0]
        self.assertIn("id", first)
        self.assertIn("session_id", first)
        self.assertEqual(first["id"], first["session_id"])


if __name__ == "__main__":
    unittest.main()
