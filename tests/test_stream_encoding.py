import json
import unittest
from unittest.mock import MagicMock, patch

from llama_module import OpenAICompatibleClient


class StreamEncodingTests(unittest.TestCase):
    def test_non_stream_response_decodes_utf8_json(self):
        response = MagicMock()
        response.ok = True
        response.content = '{"reply":"Příliš žluťoučký kůň"}'.encode("utf-8")

        client = OpenAICompatibleClient(
            base_url="https://api.groq.com/openai/v1",
            model="test-model",
        )
        with patch("llama_module.requests.post", return_value=response):
            result = client.create_chat_completion(
                messages=[{"role": "user", "content": "Ahoj"}],
                stream=False,
            )

        self.assertEqual(result, {"reply": "Příliš žluťoučký kůň"})

    def test_openai_compatible_stream_decodes_utf8_and_replaces_invalid_bytes(self):
        response = MagicMock()
        response.ok = True
        response.iter_lines.return_value = [
            (
                "data: "
                + json.dumps(
                    {"choices": [{"delta": {"content": "Příliš žluťoučký"}}]},
                    ensure_ascii=False,
                )
            ).encode("utf-8"),
            b'data: {"choices":[{"delta":{"content":"caf\xe9"}}]}',
            b"data: [DONE]",
        ]
        request = MagicMock()
        request.__enter__.return_value = response

        client = OpenAICompatibleClient(
            base_url="https://api.groq.com/openai/v1",
            model="test-model",
        )
        with patch("llama_module.requests.post", return_value=request) as post:
            chunks = list(
                client.create_chat_completion(
                    messages=[{"role": "user", "content": "Ahoj"}],
                    stream=True,
                )
            )

        self.assertEqual(
            [chunk["choices"][0]["delta"]["content"] for chunk in chunks],
            ["Příliš žluťoučký", "caf�"],
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["Content-Type"],
            "application/json; charset=utf-8",
        )


if __name__ == "__main__":
    unittest.main()
