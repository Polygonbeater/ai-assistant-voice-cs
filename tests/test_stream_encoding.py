import json
import unittest
from unittest.mock import MagicMock, patch

from llama_module import OpenAICompatibleClient


class StreamEncodingTests(unittest.TestCase):
    def test_gemini_v1main_base_url_uses_supported_v1beta_endpoint(self):
        for model in ("gemini-flash-latest",):
            with self.subTest(model=model):
                client = OpenAICompatibleClient(
                    base_url="https://generativelanguage.googleapis.com/v1main/openai/",
                    model=model,
                )

                self.assertEqual(
                    client.endpoint,
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                )
                self.assertEqual(client.model, model)

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

    def test_openai_compatible_stream_decodes_utf8_split_across_network_chunks(self):
        response_text = (
            "data: "
            + json.dumps(
                {"choices": [{"delta": {"content": "Příliš žluťoučký kůň"}}]},
                ensure_ascii=False,
            )
            + "\n\n"
            + "data: [DONE]\n\n"
        )
        response_bytes = response_text.encode("utf-8")
        split_at = response_bytes.index("ř".encode("utf-8")) + 1
        response = MagicMock()
        response.ok = True
        response.iter_content.return_value = [
            response_bytes[:split_at],
            response_bytes[split_at:],
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
            ["Příliš žluťoučký kůň"],
        )
        response.iter_content.assert_called_once_with(chunk_size=1024)
        self.assertEqual(
            post.call_args.kwargs["headers"]["Content-Type"],
            "application/json; charset=utf-8",
        )

    def test_openai_compatible_stream_surfaces_invalid_sse_json(self):
        response = MagicMock(ok=True)
        response.iter_content.return_value = [b"data: not-json\n\n"]
        request = MagicMock()
        request.__enter__.return_value = response
        client = OpenAICompatibleClient("https://api.example/v1", model="test-model")

        with patch("llama_module.requests.post", return_value=request):
            with self.assertRaisesRegex(RuntimeError, "invalid SSE JSON"):
                list(
                    client.create_chat_completion(
                        messages=[{"role": "user", "content": "Ahoj"}],
                        stream=True,
                    )
                )


if __name__ == "__main__":
    unittest.main()
