import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from document_service import DocumentService
from llama_module import generate_response
from web_server import ChatRequest


class TestVisionBridge(unittest.TestCase):
    """Test suite for Multimodal Vision Bridge."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.doc_service = DocumentService(storage_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_document_service_skips_binary_image_reading(self):
        """DocumentService.read should return placeholder text and skip parsing for image files."""
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            test_file = Path(self.temp_dir.name) / f"sample{ext}"
            test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")
            
            content = self.doc_service.read(test_file)
            self.assertIn(f"Zde je vložen obrázek sample{ext}", content)
            self.assertIn("Obsah nelze textově prohledávat.", content)

    def test_chat_request_schema_accepts_images(self):
        """ChatRequest schema should accept optional list of base64 image strings."""
        req = ChatRequest(
            prompt="Describe this render",
            images=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY44YAAAAASUVORK5CYII="]
        )
        self.assertEqual(len(req.images), 1)
        self.assertTrue(req.images[0].startswith("data:image/png;base64,"))

    def test_generate_response_constructs_multimodal_payload(self):
        """generate_response should structure OpenAI Vision API user message when images are present."""
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = iter([
            {"choices": [{"delta": {"content": "This is a 3D rendered cube."}}]}
        ])

        config = {
            "llama": {
                "system_prompt": "You are a 3D assistant.",
                "max_tokens": 512,
                "temperature": 0.7,
            },
            "language": "en",
        }

        raw_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY44YAAAAASUVORK5CYII="
        tokens = list(
            generate_response(
                llm=mock_llm,
                prompt="Analyze this image",
                config=config,
                images=[raw_b64],
                tools_enabled=False,
            )
        )

        self.assertTrue(mock_llm.create_chat_completion.called)
        call_kwargs = mock_llm.create_chat_completion.call_args[1]
        messages = call_kwargs.get("messages", [])

        # Check that the last message is multimodal user message
        user_msg = messages[-1]
        self.assertEqual(user_msg["role"], "user")
        self.assertIsInstance(user_msg["content"], list)
        self.assertEqual(user_msg["content"][0], {"type": "text", "text": "Analyze this image"})
        self.assertEqual(
            user_msg["content"][1],
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"}}
        )

    def test_generate_response_preserves_explicit_data_uri(self):
        """generate_response should preserve provided data:image/ prefix instead of defaulting to jpeg."""
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = iter([
            {"choices": [{"delta": {"content": "PNG image received."}}]}
        ])

        config = {
            "llama": {
                "system_prompt": "You are a 3D assistant.",
                "max_tokens": 512,
                "temperature": 0.7,
            },
            "language": "en",
        }

        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY44YAAAAASUVORK5CYII="
        list(
            generate_response(
                llm=mock_llm,
                prompt="Analyze this PNG",
                config=config,
                images=[data_uri],
                tools_enabled=False,
            )
        )

        self.assertTrue(mock_llm.create_chat_completion.called)
        call_kwargs = mock_llm.create_chat_completion.call_args[1]
        messages = call_kwargs.get("messages", [])
        user_msg = messages[-1]
        self.assertEqual(
            user_msg["content"][1],
            {"type": "image_url", "image_url": {"url": data_uri}}
        )

    def test_generate_response_vision_graceful_fallback_cs(self):
        """generate_response should yield localized fallback when model does not support Vision in CS."""
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.side_effect = Exception("Invalid parameter: image/vision multimodal input is not supported by this model (400 Bad Request)")

        config = {
            "llama": {
                "system_prompt": "Jsi asistent.",
                "max_tokens": 512,
                "temperature": 0.7,
            },
            "language": "cs",
        }

        tokens = list(
            generate_response(
                llm=mock_llm,
                prompt="Popiš tento render",
                config=config,
                images=["some_base64_data"],
                tools_enabled=False,
            )
        )

        full_res = " ".join(tokens)
        self.assertIn("můj aktuálně aktivní model nepodporuje zpracování obrazu (Vision)", full_res)

    def test_generate_response_vision_graceful_fallback_en(self):
        """generate_response should yield localized fallback when model does not support Vision in EN."""
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.side_effect = Exception("400 Bad Request: multimodal content types not allowed")

        config = {
            "llama": {
                "system_prompt": "You are an assistant.",
                "max_tokens": 512,
                "temperature": 0.7,
            },
            "language": "en",
        }

        tokens = list(
            generate_response(
                llm=mock_llm,
                prompt="Describe this render",
                config=config,
                images=["some_base64_data"],
                tools_enabled=False,
            )
        )

        full_res = " ".join(tokens)
        self.assertIn("my currently active model does not support image processing (Vision)", full_res)


if __name__ == "__main__":
    unittest.main()
