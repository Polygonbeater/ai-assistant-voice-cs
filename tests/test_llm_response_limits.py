import unittest
from unittest.mock import MagicMock, patch

from llama_module import OpenAICompatibleClient, generate_response


class TestLlmResponseLimits(unittest.TestCase):
    def test_auto_limit_uses_long_response_default(self):
        llm = MagicMock()
        llm.create_chat_completion.return_value = iter([
            {"choices": [{"delta": {"content": "A concise answer."}}]}
        ])

        list(
            generate_response(
                llm,
                "Give me an answer.",
                {"llama": {"function_calling": False}},
                enable_tools=False,
            )
        )

        self.assertEqual(llm.create_chat_completion.call_args.kwargs["max_tokens"], 8192)

    def test_tool_enabled_generation_honors_configured_output_limit(self):
        llm = MagicMock()
        llm.create_chat_completion.return_value = iter([
            {"choices": [{"delta": {"content": "A concise answer."}}]}
        ])

        list(
            generate_response(
                llm,
                "Give me an answer.",
                {"llama": {"max_tokens": 65536}},
            )
        )

        self.assertEqual(llm.create_chat_completion.call_args.kwargs["max_tokens"], 65536)

    def test_openai_compatible_client_forwards_large_token_limit(self):
        response = MagicMock(ok=True)
        response.json.return_value = {"choices": []}

        with patch("llama_module.requests.post", return_value=response) as post:
            client = OpenAICompatibleClient("https://api.example/v1", model="test-model")
            client.create_chat_completion(
                [{"role": "user", "content": "Generate a long response."}],
                max_tokens=65536,
                stream=False,
            )

        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 65536)


if __name__ == "__main__":
    unittest.main()
