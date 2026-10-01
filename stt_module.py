import logging
import os
import numpy as np
import torch
from faster_whisper import WhisperModel

# Konfigurace logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_whisper(config: dict) -> WhisperModel:
    """
    Inicializuje a vrátí instanci faster-whisper modelu optimalizovaného pro CPU/GPU.
    """
    whisper_cfg = config.get('whisper', {})
    model_name = whisper_cfg.get('model', 'small')

    # Automatická detekce hardware nebo převzetí z konfigurace
    device = whisper_cfg.get('device')
    if not device:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    compute_type = whisper_cfg.get('compute_type')
    if not compute_type:
        compute_type = "float16" if device == "cuda" else "int8"

    cpu_threads = whisper_cfg.get('cpu_threads', min(4, os.cpu_count() or 4))

    try:
        logging.info(
            f"Načítám faster-whisper model '{model_name}' na zařízení '{device}' "
            f"(compute_type={compute_type}, cpu_threads={cpu_threads})..."
        )
        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads,
            download_root=whisper_cfg.get('download_root', None)
        )
        logging.info(f"faster-whisper model inicializován: {model_name}")
        return model
    except Exception as e:
        logging.error(f"Chyba při načítání faster-whisper modelu '{model_name}': {e}")
        raise

def transcribe_audio_np(model: WhisperModel, audio_data: np.ndarray, config: dict) -> str:
    """
    Přepíše zvuková data z numpy pole na text pomocí faster-whisper.
    """
    if audio_data is None or audio_data.size == 0:
        logging.warning("Předána prázdná audio data pro přepis.")
        return ""

    try:
        # Převedení PCM dat na float32 v rozsahu [-1.0, 1.0], pokud ještě nejsou
        if audio_data.dtype != np.float32:
            audio_float32 = audio_data.astype(np.float32) / 32768.0
        else:
            audio_float32 = audio_data

        # Kontrola minimální délky záznamu (alespoň 0.1 s při 16 kHz)
        if len(audio_float32) < 1600:
            logging.warning("Audio záznam je příliš krátký pro přepis (< 0.1 s).")
            return ""

        whisper_cfg = config.get('whisper', {})
        language = whisper_cfg.get('language', 'cs')
        beam_size = int(whisper_cfg.get('beam_size', 1))
        temperature = float(whisper_cfg.get('temperature', 0.0))

        logging.info(f"Spouštím faster-whisper přepis pro jazyk: {language} (beam_size={beam_size})")
        segments, info = model.transcribe(
            audio_float32,
            language=language,
            beam_size=beam_size,
            temperature=temperature,
            condition_on_previous_text=False,
            no_speech_threshold=float(whisper_cfg.get('no_speech_threshold', 0.6)),
            compression_ratio_threshold=float(whisper_cfg.get('compression_ratio_threshold', 2.4)),
            vad_filter=False  # VAD filtraci již provádí Silero VAD v modulu audio.py
        )

        valid_segments = []
        for segment in segments:
            # Odfiltrování segmentů, které jsou vyhodnoceny jako ticho nebo nekonečná smyčka
            if segment.no_speech_prob is not None and segment.no_speech_prob > 0.6:
                continue
            if segment.compression_ratio is not None and segment.compression_ratio > 2.4:
                continue
            text = segment.text.strip()
            if text:
                valid_segments.append(text)

        transcribed_text = " ".join(valid_segments).strip()
        logging.info(f"Přepsaný text: '{transcribed_text}'")
        return transcribed_text

    except Exception as e:
        logging.error(f"Chyba při přepisu audia: {e}")
        return ""

