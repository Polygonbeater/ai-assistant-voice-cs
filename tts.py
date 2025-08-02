import asyncio
import subprocess
import logging
from TTS.api import TTS

def initialize_tts(config):
    try:
        logging.info("Inicializace TTS modelu...")
        return TTS(model_name=config["tts"]["model_name"])
    except Exception as e:
        logging.error(f"Chyba při inicializaci TTS: {e}")
        raise

async def speak_async(tts, text, config):
    try:
        logging.info("Generuji TTS výstup...")
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: tts.tts_to_file(text=text, file_path="tts_output.wav")
        )
        logging.info("Přehrávám TTS výstup...")
        subprocess.run(["aplay", "tts_output.wav"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logging.error(f"Chyba při přehrávání TTS: {e}")
