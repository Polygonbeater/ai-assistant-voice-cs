import asyncio
import logging
import wave
import pyaudio
import tempfile
import os
from TTS.api import TTS
from num2words import num2words
import re

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
    Připraví text pro TTS: převede čísla na slova, včetně záporných.
    """
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
    text = re.sub(r'-?\d[\d\s]*', replace_number, text)
    logging.info(f"Text po úpravě pro TTS: '{text}'")
    return text

def _play_wav_pyaudio(file_path: str):
    """
    Přehrává .wav soubor pomocí PyAudio pro zajištění multiplatformní kompatibility.
    """
    try:
        if not os.path.exists(file_path):
            logging.error(f"Soubor {file_path} neexistuje.")
            return
        with wave.open(file_path, 'rb') as wf:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
    except Exception as e:
        logging.error(f"Chyba při přehrávání audia přes PyAudio: {e}")

async def speak_async(tts: TTS, text: str):
    """
    Asynchronně generuje a přehrává řeč pomocí TTS.
    Používá dočasný soubor a PyAudio.
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
        logging.info("Přehrávám TTS výstup...")
        await asyncio.get_event_loop().run_in_executor(
            None,
            _play_wav_pyaudio,
            temp_filename
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