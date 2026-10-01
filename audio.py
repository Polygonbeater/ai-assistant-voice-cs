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


def play_activation_chime(sample_rate: int = 16000):
    """
    Plynule přehraje příjemný dvoutónový zvuk (600 Hz -> 900 Hz, cca 180 ms)
    pro potvrzení detekce klíčového slova (Hands-free).
    """
    try:
        t1 = np.linspace(0, 0.08, int(sample_rate * 0.08), False)
        t2 = np.linspace(0, 0.10, int(sample_rate * 0.10), False)

        wave1 = np.sin(2 * np.pi * 600 * t1) * 0.25
        wave2 = np.sin(2 * np.pi * 900 * t2) * 0.3

        # Fade envelope proti lupání v reproduktorech
        fade = int(sample_rate * 0.01)
        env1 = np.ones_like(wave1)
        env1[:fade] = np.linspace(0, 1, fade)
        env1[-fade:] = np.linspace(1, 0, fade)

        env2 = np.ones_like(wave2)
        env2[:fade] = np.linspace(0, 1, fade)
        env2[-fade:] = np.linspace(1, 0, fade)

        combined = np.concatenate([wave1 * env1, wave2 * env2])
        audio_int16 = (combined * 32767).astype(np.int16)

        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)
            stream.write(audio_int16.tobytes())
            stream.stop_stream()
            stream.close()
        finally:
            p.terminate()
    except Exception as e:
        logging.debug(f"Přehrání potvrzovacího zvuku selhalo: {e}")


def initialize_wakeword(config: dict | None = None):
    """
    Inicializuje openWakeWord model. Pokud model není stažen, automaticky ho stáhne.
    """
    import openwakeword
    from openwakeword.model import Model
    import openwakeword.utils

    ww_cfg = (config or {}).get("wakeword", {})
    model_name = ww_cfg.get("model", "hey_jarvis")

    try:
        try:
            oww = Model(wakeword_models=[model_name], inference_framework="onnx")
        except Exception:
            logging.info(f"Model pro Wake Word '{model_name}' nebyl nalezen, stahuji...")
            openwakeword.utils.download_models([model_name])
            oww = Model(wakeword_models=[model_name], inference_framework="onnx")

        logging.info(f"openWakeWord model '{model_name}' úspěšně načten.")
        return oww
    except Exception as e:
        logging.error(f"Chyba při inicializaci openWakeWord: {e}")
        raise


class WakeWordListener:
    """
    Běží na pozadí v samostatném vlákně a neblokuje hlavní GUI vlákno.
    Průběžně vyhodnocuje mikrofon a při detekci klíčového slova (např. 'Hey Jarvis')
    přehraje pípnutí, uvolní mikrofon a spustí callback (STT nahrávání).
    """
    def __init__(self, config: dict, on_detected_callback: callable):
        self.config = config
        self.on_detected_callback = on_detected_callback
        import threading
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread = None
        self.model = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        import threading
        self.stop_event.clear()
        self.pause_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def pause(self):
        """Dočasně pozastaví poslech (např. když asistent odpovídá přes TTS nebo nahrává projev)."""
        self.pause_event.set()

    def resume(self):
        """Obnoví poslech na pozadí po dokončení odpovědi asistenta."""
        self.pause_event.clear()

    def stop(self):
        """Úplně ukončí vlákno listeneru a uvolní zvukové zařízení."""
        self.stop_event.set()
        self.pause_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive() and not self.stop_event.is_set()

    def _run_loop(self):
        import time
        logging.info("Startuji WakeWordListener na pozadí...")
        if self.model is None:
            try:
                self.model = initialize_wakeword(self.config)
            except Exception as e:
                logging.error(f"Nelze spustit WakeWordListener (chyba modelu): {e}")
                return

        ww_cfg = self.config.get("wakeword", {})
        threshold = float(ww_cfg.get("threshold", 0.5))
        model_name = ww_cfg.get("model", "hey_jarvis")

        audio_cfg = self.config.get("audio", {})
        device_index = audio_cfg.get("device_index", -1)
        input_device_index = None if (device_index is None or device_index < 0) else int(device_index)

        sample_rate = 16000
        chunk_size = 1280  # 80 ms audio chunk pro openWakeWord

        pa = None
        stream = None

        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                time.sleep(0.1)
                continue

            if stream is None:
                try:
                    if pa is None:
                        pa = pyaudio.PyAudio()
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=sample_rate,
                        input=True,
                        frames_per_buffer=chunk_size,
                        input_device_index=input_device_index
                    )
                    logging.info("WakeWordListener aktivně naslouchá na mikrofonu...")
                except Exception as e:
                    logging.error(f"WakeWordListener nemohl otevřít audio stream: {e}")
                    time.sleep(1.0)
                    continue

            try:
                pcm_data = stream.read(chunk_size, exception_on_overflow=False)
                if not pcm_data or len(pcm_data) < chunk_size * 2:
                    continue

                audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
                prediction = self.model.predict(audio_int16)

                score = prediction.get(model_name, 0.0)
                if not score and prediction:
                    score = max(prediction.values())

                if score > threshold:
                    logging.info(f"Klíčové slovo detekováno! (skóre={score:.3f} > {threshold})")

                    # Uvolníme stream před spuštěním nahrávání
                    self.pause_event.set()
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None

                    # Potvrzovací pípnutí
                    play_activation_chime(sample_rate)

                    # Reset vnitřního stavu modelu
                    self.model.reset()

                    # Spustit callback pro hlavní nahrávání
                    if self.on_detected_callback:
                        import threading
                        threading.Thread(target=self.on_detected_callback, daemon=True).start()

            except (IOError, OSError) as e:
                logging.debug(f"Chyba při čtení audio streamu v WakeWordListener: {e}")
                time.sleep(0.05)
            except Exception as e:
                logging.error(f"Chyba v běhu WakeWordListener: {e}")
                time.sleep(0.1)

        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
        logging.info("WakeWordListener byl korektně ukončen.")


