import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import web_server


class TestLlmConnectionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_server.app)

    def test_saved_key_uses_configured_provider_url_not_request_url(self):
        config = {
            "llm_provider": {
                "groq": {
                    "api_key": "saved-secret",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model": "test-model",
                }
            }
        }
        with (
            patch.dict(web_server.config, config, clear=True),
            patch("web_server.test_provider_connection", return_value={"status": "ok"}) as test_connection,
        ):
            response = self.client.post(
                "/api/llm/test-connection",
                json={
                    "provider_type": "groq",
                    "base_url": "https://attacker.example/collect",
                },
            )

        self.assertEqual(response.status_code, 200)
        test_connection.assert_called_once_with(
            provider_type="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key="saved-secret",
            model="test-model",
        )

    def test_custom_provider_type_uses_custom_saved_credentials(self):
        config = {
            "llm_provider": {
                "groq": {"api_key": "groq-secret"},
                "custom": {
                    "api_key": "custom-secret",
                    "base_url": "https://configured.example/v1",
                    "model": "custom-model",
                },
            }
        }
        with (
            patch.dict(web_server.config, config, clear=True),
            patch("web_server.test_provider_connection", return_value={"status": "ok"}) as test_connection,
        ):
            response = self.client.post(
                "/api/llm/test-connection",
                json={
                    "provider_type": "custom",
                    "base_url": "https://attacker.example/collect",
                },
            )

        self.assertEqual(response.status_code, 200)
        test_connection.assert_called_once_with(
            provider_type="custom",
            base_url="https://configured.example/v1",
            api_key="custom-secret",
            model="custom-model",
        )

    def test_explicit_key_can_test_requested_endpoint(self):
        with (
            patch.dict(web_server.config, {"llm_provider": {}}, clear=True),
            patch("web_server.test_provider_connection", return_value={"status": "ok"}) as test_connection,
        ):
            response = self.client.post(
                "/api/llm/test-connection",
                json={
                    "provider_type": "custom",
                    "base_url": "https://custom.example/v1",
                    "api_key": "provided-key",
                    "model": "custom-model",
                },
            )

        self.assertEqual(response.status_code, 200)
        test_connection.assert_called_once_with(
            provider_type="custom",
            base_url="https://custom.example/v1",
            api_key="provided-key",
            model="custom-model",
        )

    def test_rejects_conflicting_provider_fields(self):
        response = self.client.post(
            "/api/llm/test-connection",
            json={"provider": "groq", "provider_type": "custom"},
        )

        self.assertEqual(response.status_code, 400)

    def test_remote_client_cannot_test_saved_credentials(self):
        remote_client = TestClient(web_server.app, client=("192.0.2.1", 50000))
        with patch("web_server.test_provider_connection") as test_connection:
            response = remote_client.post(
                "/api/llm/test-connection",
                json={"provider_type": "groq"},
            )

        self.assertEqual(response.status_code, 403)
        test_connection.assert_not_called()

    def test_remote_client_cannot_change_saved_provider_url(self):
        remote_client = TestClient(web_server.app, client=("192.0.2.1", 50000))
        original_config = {"llm_provider": {"groq": {"base_url": "https://api.groq.com/openai/v1"}}}
        with patch.dict(web_server.config, original_config, clear=True):
            response = remote_client.post(
                "/api/config",
                json={
                    "llm_provider": {
                        "groq": {"base_url": "https://attacker.example/collect"},
                    }
                },
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(web_server.config, original_config)


if __name__ == "__main__":
    unittest.main()
