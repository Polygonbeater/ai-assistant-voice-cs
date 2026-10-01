import asyncio
import logging
import os
import queue
import re
import tempfile
import threading
import wave
from num2words import num2words
import pyaudio
from TTS.api import TTS

# Konfigurace logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def initialize_tts(config: dict) -> TTS:
    """Inicializuje TTS model."""
    try:
        model_name = config["tts"]["model_name"]
        gpu = config.get("tts", {}).get("gpu", False)

        logging.info(f"Inicializace TTS modelu: {model_name} (GPU: {gpu})")
        return TTS(model_name=model_name, gpu=gpu)

    except Exception as e:
        logging.error(f"Chyba při inicializaci TTS: {e}")
        raise


def _preprocess_text_for_tts(text: str) -> str:
    """
    Připraví text pro TTS:
    - Odstraní Markdown formátování (odkazy, hvězdičky, mřížky, kód), aby je TTS nečetlo doslova.
    - Převede čísla na česká slova včetně záporných hodnot.
    """
    if not text:
        return ""

    # 1. Odstranění Markdownu
    # Odkazy [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Kódové bloky a inline kód `kód`
    text = re.sub(r'`+([^`]+)`+', r'\1', text)
    # Tučné písmo a kurzíva (*, _, **)
    text = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', text)
    # Nadpisy (#, ##, ...)
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    # Odrážky (-, *, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Zbylé osamocené symboly
    text = text.replace('*', '').replace('#', '').replace('`', '')

    # 2. Převod čísel na slova v češtině
    def replace_number(match):
        number_str = match.group(0).replace(" ", "")
        try:
            number = int(number_str)
            if number < 0:
                return "mínus " + num2words(abs(number), lang='cs')
            else:
                return num2words(number, lang='cs')
        except ValueError:
            return match.group(0)

    # Shoda na čísla včetně možných mezer mezi tisíci (např. '10 000')
    text = re.sub(r'-?\b\d+(?:[\s]\d{3})*\b', replace_number, text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _play_wav_pyaudio(file_path: str, stop_event: threading.Event | None = None):
    """
    Přehrává .wav soubor pomocí PyAudio s možností okamžitého přerušení přes stop_event.
    """
    if not os.path.exists(file_path):
        logging.error(f"Soubor {file_path} neexistuje.")
        return

    p = None
    stream = None
    try:
        with wave.open(file_path, 'rb') as wf:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            data = wf.readframes(1024)
            while data:
                if stop_event and stop_event.is_set():
                    logging.info("Přehrávání audia bylo přerušeno (Stop).")
                    break
                stream.write(data)
                data = wf.readframes(1024)
    except Exception as e:
        logging.error(f"Chyba při přehrávání audia přes PyAudio: {e}")
    finally:
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass


class TTSStreamPlayer:
    """
    Asynchronní streamovaný přehrávač řeči.
    Využívá dvoustupňový pipeline (Syntéza na pozadí -> Plynulé přehrávání přes PyAudio):
    První věta začne hrát ihned, jakmile ji LLM dokončí, zatímco další věty se paralelně
    syntetizují na pozadí, čímž vzniká plynulý poslech bez mezer.
    """
    def __init__(self, tts: TTS, stop_event: threading.Event | None = None):
        self.tts = tts
        self.stop_event = stop_event
        self.text_queue: queue.Queue[str | None] = queue.Queue()
        self.audio_queue: queue.Queue[str | None] = queue.Queue(maxsize=3)
        self.is_stopped = threading.Event()

        self.synth_thread = threading.Thread(target=self._synthesis_worker, daemon=True)
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.synth_thread.start()
        self.playback_thread.start()

    def _synthesis_worker(self):
        """Spotřebovává textové věty z fronty a vytváří dočasné WAV soubory."""
        while not self.is_stopped.is_set():
            if self.stop_event and self.stop_event.is_set():
                break
            try:
                text = self.text_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if text is None:
                # Konec streamu textu
                self.audio_queue.put(None)
                self.text_queue.task_done()
                break

            try:
                clean_text = _preprocess_text_for_tts(text)
                if not clean_text:
                    self.text_queue.task_done()
                    continue

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    temp_wav_path = tmp.name

                self.tts.tts_to_file(text=clean_text, file_path=temp_wav_path)

                if self.is_stopped.is_set() or (self.stop_event and self.stop_event.is_set()):
                    if os.path.exists(temp_wav_path):
                        os.remove(temp_wav_path)
                    self.text_queue.task_done()
                    break

                self.audio_queue.put(temp_wav_path)
            except Exception as e:
                logging.error(f"Chyba při syntéze TTS fragmentu: {e}")
            finally:
                self.text_queue.task_done()

    def _playback_worker(self):
        """Spotřebovává připravené WAV soubory z fronty a přehrává je přes reproduktory."""
        while not self.is_stopped.is_set():
            if self.stop_event and self.stop_event.is_set():
                break
            try:
                wav_path = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if wav_path is None:
                self.audio_queue.task_done()
                break

            try:
                if not (self.is_stopped.is_set() or (self.stop_event and self.stop_event.is_set())):
                    _play_wav_pyaudio(wav_path, stop_event=self.stop_event)
            except Exception as e:
                logging.error(f"Chyba při přehrávání audia: {e}")
            finally:
                if os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
                self.audio_queue.task_done()

    def enqueue(self, text: str):
        """Zařadí textový fragment (větu) do fronty k okamžité syntéze a přehrání."""
        if not text or self.is_stopped.is_set():
            return
        if self.stop_event and self.stop_event.is_set():
            return
        self.text_queue.put(text)

    def finish(self):
        """Oznámí konec textu a vyčká na dohrání všech zařazených vět."""
        if not self.is_stopped.is_set():
            self.text_queue.put(None)
            self.synth_thread.join(timeout=30)
            self.playback_thread.join(timeout=60)

    def stop(self):
        """Okamžitě zastaví syntézu i přehrávání a smaže dočasné audio soubory."""
        self.is_stopped.set()
        # Vyprázdnění textové fronty
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except Exception:
                break
        # Vyprázdnění a smazání audio fronty
        while not self.audio_queue.empty():
            try:
                item = self.audio_queue.get_nowait()
                if item and os.path.exists(item):
                    try:
                        os.remove(item)
                    except Exception:
                        pass
                self.audio_queue.task_done()
            except Exception:
                break


async def speak_async(tts: TTS, text: str, stop_event: threading.Event | None = None):
    """
    Asynchronně generuje a přehrává řeč pomocí TTS (pro jednorázové použití).
    """
    if not text:
        logging.warning("Prázdný text pro TTS, přeskakuji.")
        return
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        temp_filename = tmpfile.name
    try:
        processed_text = _preprocess_text_for_tts(text)
        logging.info(f"Generuji TTS výstup do souboru: {temp_filename}")
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: tts.tts_to_file(text=processed_text, file_path=temp_filename)
        )
        if not (stop_event and stop_event.is_set()):
            logging.info("Přehrávám TTS výstup...")
            await asyncio.get_event_loop().run_in_executor(
                None,
                _play_wav_pyaudio,
                temp_filename,
                stop_event
            )
    except Exception as e:
        logging.error(f"Chyba v procesu generování nebo přehrávání TTS: {e}")
    finally:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
                logging.info(f"Dočasný soubor smazán: {temp_filename}")
            except Exception as e:
                logging.error(f"Chyba při mazání dočasného souboru: {e}")