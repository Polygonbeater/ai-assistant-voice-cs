import asyncio
import logging
import pyaudio
import re
from TTS.api import TTS
from num2words import num2words
import numpy as np

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

def _play_raw_audio_pyaudio(audio_data: np.ndarray, sample_rate: int):
    """Přehrává surová audio data (numpy array) přímo z paměti."""
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=sample_rate,
                        output=True)

        audio_bytes = audio_data.astype(np.float32).tobytes()
        stream.write(audio_bytes)

        stream.stop_stream()
        stream.close()
        p.terminate()
    except Exception as e:
        logging.error(f"Chyba při přehrávání audia přes PyAudio: {e}")

async def speak_async(tts: TTS, text: str):
    """
    Asynchronně generuje a přehrává řeč přímo z paměti, bez ukládání na disk.
    """
    try:
        processed_text = _preprocess_text_for_tts(text)
        logging.info("Generuji TTS výstup přímo do paměti...")

        # Získáme sample rate přímo z modelu
        sample_rate = tts.synthesizer.output_sample_rate
        
        # Získáme výchozího mluvčího a jazyk, pokud model podporuje více
        speaker = tts.speakers[0] if tts.is_multi_speaker else None
        language = tts.languages[0] if tts.is_multi_lingual else None

        # Generování audia do numpy pole v samostatném vlákně
        wav_output = await asyncio.get_event_loop().run_in_executor(
            None,
            tts.tts,
            processed_text,
            speaker,
            language
        )
        audio_output_np = np.array(wav_output, dtype=np.float32)

        logging.info("Přehrávám TTS výstup z paměti...")
        # Přehrání v samostatném vlákně
        await asyncio.get_event_loop().run_in_executor(
            None,
            _play_raw_audio_pyaudio,
            audio_output_np,
            sample_rate
        )

    except Exception as e:
        logging.error(f"Chyba v procesu generování nebo přehrávání TTS: {e}")
