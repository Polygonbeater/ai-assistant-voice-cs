import whisper
import logging
import numpy as np
import tempfile
import os
import soundfile as sf  # pip install soundfile

_model = None

def load_model(model_name="base"):
    global _model
    if _model is None:
        logging.info(f"Načítám Whisper model: {model_name}")
        _model = whisper.load_model(model_name)
    return _model

def transcribe_audio_np(audio_np: np.ndarray, sample_rate: int = 16000, config=None) -> str:
    """
    Přepisuje audio data v numpy poli (int16) na text pomocí Whisper.

    Args:
        audio_np (np.ndarray): Audio data jako 1D numpy pole int16.
        sample_rate (int): Vzorkovací frekvence audia (Whisper preferuje 16000).
        config (dict, optional): Konfigurace, kde můžeš specifikovat model.

    Returns:
        str: Přepsaný text.
    """
    try:
        model_name = "base"
        if config and "whisper" in config and "model" in config["whisper"]:
            model_name = config["whisper"]["model"]

        model = load_model(model_name)

        # Ulož audio numpy data do temp WAV souboru
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            sf.write(tmpfile.name, audio_np, sample_rate)
            tmp_path = tmpfile.name

        logging.info(f"Přepisuji audio z temp souboru {tmp_path} modelem {model_name}")
        result = model.transcribe(tmp_path, language="cs")
        os.remove(tmp_path)  # smažeme temp soubor
        return result.get("text", "")

    except Exception as e:
        logging.error(f"Chyba při přepisu audio numpy dat: {e}")
        return ""
