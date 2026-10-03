import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from web_server import app


class SpeechToTextEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, headers={"X-Polygon-Client": "true"})

    def test_transcribes_uploaded_audio_with_local_whisper(self):
        model = MagicMock()
        recorded_path = []

        def fake_transcribe(path, **kwargs):
            recorded_path.append(path)
            return iter([SimpleNamespace(
                text=" Dobrý den. ",
                no_speech_prob=0.0,
                compression_ratio=1.0,
            )]), SimpleNamespace(language="cs")

        model.transcribe.side_effect = fake_transcribe
        with patch("web_server.get_whisper", return_value=model):
            response = self.client.post(
                "/api/stt/transcribe",
                files={"file": ("voice.webm", b"fake audio data", "audio/webm;codecs=opus")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"text": "Dobrý den."})
        self.assertEqual(len(recorded_path), 1)
        self.assertFalse(os.path.exists(recorded_path[0]))

    def test_rejects_unsupported_audio_format(self):
        with patch("web_server.get_whisper") as get_whisper:
            response = self.client.post(
                "/api/stt/transcribe",
                files={"file": ("voice.txt", b"not audio", "text/plain")},
            )

        self.assertEqual(response.status_code, 415)
        get_whisper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
