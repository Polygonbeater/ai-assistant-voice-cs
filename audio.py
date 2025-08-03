import pyaudio
import pvporcupine
import numpy as np
import logging
import torch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_porcupine(config: dict):
    """Inicializuje Porcupine pro detekci klíčového slova."""
    try:
        access_key = config['porcupine']['access_key']
        model_path = config['porcupine']['model_path']
        keyword = config['porcupine']['keyword']
        sensitivity = config['porcupine'].get('sensitivity', 0.5)
        logging.info(f"Inicializuji Porcupine s vestavěným klíčovým slovem: '{keyword}'")
        return pvporcupine.create(
            access_key=access_key,
            model_path=model_path,
            keywords=[keyword],
            sensitivities=[sensitivity]
        )
    except Exception as e:
        logging.error(f"Chyba při inicializaci Porcupine: {e}")
        raise

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

def capture_wake_word(porcupine: pvporcupine.Porcupine, pa: pyaudio.PyAudio, config: dict):
    """Zachytí zvukový vstup a čeká na detekci klíčového slova."""
    device_index = config['audio']['wake_word_device_index']
    stream = None
    try:
        stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length,
            input_device_index=device_index
        )
        while True:
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm_np = np.frombuffer(pcm, dtype=np.int16)
            keyword_index = porcupine.process(pcm_np)
            if keyword_index >= 0:
                return keyword_index
    except KeyboardInterrupt:
        logging.info("Přerušení detekce klíčového slova uživatelem.")
        raise
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
            logging.info("Audio stream pro Porcupine uzavřen.")

def record_with_vad(config: dict, pa: pyaudio.PyAudio, vad_model) -> np.ndarray:
    """Nahrává audio po detekci klíčového slova pomocí Silero VAD."""
    device_index = config['audio']['device_index']
    vad_config = config['silero_vad']
    sample_rate = vad_config['sample_rate']
    threshold = vad_config['threshold']
    silence_duration_ms = vad_config['silence_duration_ms']
    
    chunk_size = 512
    
    stream = None
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk_size,
            input_device_index=device_index
        )
        logging.info("Spouštím VAD nahrávání...")
        
        voiced_frames = []
        is_speaking = False
        silent_chunks = 0
        chunk_duration_ms = (chunk_size / sample_rate) * 1000
        max_silent_chunks = int(silence_duration_ms / chunk_duration_ms)

        while True:
            pcm_data = stream.read(chunk_size, exception_on_overflow=False)
            audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            
            speech_prob = vad_model(torch.from_numpy(audio_float32), sample_rate).item()
            logging.info(f"speech_prob: {speech_prob}")  # Přidáno pro ladění

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
            
            if len(voiced_frames) * chunk_size / sample_rate > config['audio']['max_recording_time']:
                logging.warning("Překročen maximální čas nahrávání.")
                break
    except KeyboardInterrupt:
        logging.info("Přerušení nahrávání uživatelem.")
        raise
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
            logging.info("Audio stream pro VAD uzavřen.")

    if not voiced_frames:
        return np.array([], dtype=np.int16)

    combined_data = b''.join(voiced_frames)
    return np.frombuffer(combined_data, dtype=np.int16)