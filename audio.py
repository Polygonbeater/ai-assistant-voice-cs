import pyaudio
import numpy as np
import logging
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_vad():
    """Inicializuje Silero VAD model."""
    try:
        logging.info("Načítám Silero VAD model...")
        model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                     model='silero_vad',
                                     force_reload=False,
                                     onnx=True)
        logging.info("Silero VAD model načten.")
        return model, utils
    except Exception as e:
        logging.error(f"Chyba při inicializaci Silero VAD: {e}")
        raise

def record_with_vad(config: dict, pa: pyaudio.PyAudio, vad_model) -> np.ndarray:
    """Nahrává audio po detekci hlasu pomocí Silero VAD s ošetřením chybových stavů streamu."""
    audio_cfg = config.get('audio', {})
    device_index = audio_cfg.get('device_index', -1)
    # Pro PyAudio hodnota None znamená výchozí systémové vstupní zařízení
    input_device_index = None if (device_index is None or device_index < 0) else int(device_index)

    vad_config = config.get('silero_vad', {})
    sample_rate = vad_config.get('sample_rate', 16000)
    threshold = vad_config.get('threshold', 0.3)
    silence_duration_ms = vad_config.get('silence_duration_ms', 2000)
    max_recording_time = audio_cfg.get('max_recording_time', 15)

    chunk_size = 512
    stream = None

    try:
        device_count = pa.get_device_count()
        if device_count == 0:
            logging.error("Nebyla nalezena žádná audio vstupní zařízení.")
            return np.array([], dtype=np.int16)
    except Exception as e:
        logging.error(f"Chyba při zjišťování dostupných audio zařízení: {e}")
        return np.array([], dtype=np.int16)

    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
            input_device_index=input_device_index
        )
        logging.info(f"Audio stream otevřen (zařízení={input_device_index}). Spouštím VAD nahrávání...")

        voiced_frames = []
        is_speaking = False
        silent_chunks = 0
        chunk_duration_ms = (chunk_size / sample_rate) * 1000
        max_silent_chunks = int(silence_duration_ms / chunk_duration_ms)

        while True:
            try:
                pcm_data = stream.read(chunk_size, exception_on_overflow=False)
                if not pcm_data or len(pcm_data) < chunk_size * 2:
                    logging.warning("Audio stream vrátil neúplná data.")
                    break
            except (IOError, OSError) as e:
                logging.error(f"Chyba při čtení z audio streamu (odpojení mikrofonu / pád audio subsystému): {e}")
                break

            try:
                audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0

                speech_prob = vad_model(torch.from_numpy(audio_float32), sample_rate).item()
                logging.debug(f"speech_prob: {speech_prob:.4f}")
            except Exception as e:
                logging.error(f"Chyba při vyhodnocení VAD: {e}")
                break

            if speech_prob > threshold:
                if not is_speaking:
                    logging.info("Detekována řeč, začínám nahrávat.")
                    is_speaking = True
                silent_chunks = 0
                voiced_frames.append(pcm_data)
            else:
                if is_speaking:
                    silent_chunks += 1
                    if silent_chunks > max_silent_chunks:
                        logging.info("Detekováno ticho, nahrávání ukončeno.")
                        break

            if len(voiced_frames) * chunk_size / sample_rate > max_recording_time:
                logging.warning("Překročen maximální čas nahrávání.")
                break

    except KeyboardInterrupt:
        logging.info("Přerušení nahrávání uživatelem.")
        raise
    except Exception as e:
        logging.error(f"Neočekávaná chyba při nahrávání audia: {e}")
    finally:
        if stream is not None:
            try:
                if stream.is_active():
                    stream.stop_stream()
            except Exception as e:
                logging.debug(f"Chyba při zastavování audio streamu: {e}")
            try:
                stream.close()
            except Exception as e:
                logging.debug(f"Chyba při zavírání audio streamu: {e}")
            logging.info("Audio stream pro VAD uzavřen.")

    if not voiced_frames:
        return np.array([], dtype=np.int16)

    combined_data = b''.join(voiced_frames)
    return np.frombuffer(combined_data, dtype=np.int16)

