import whisper
import numpy as np
import logging

# Konfigurace logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_whisper(config: dict):
    """
    Inicializuje a vrátí instanci Whisper modelu.
    """
    model_name = config['whisper']['model']
    try:
        model = whisper.load_model(model_name)
        logging.info(f"Whisper model inicializován: {model_name}")
        return model
    except Exception as e:
        logging.error(f"Chyba při načítání Whisper modelu '{model_name}': {e}")
        raise

def transcribe_audio_np(model: whisper.Whisper, audio_data: np.ndarray, config: dict) -> str:
    """
    Přepíše zvuková data z numpy pole na text pomocí Whisper.
    """
    try:
        # Převedení PCM dat na float32, což Whisper očekává
        audio_float32 = audio_data.astype(np.float32) / 32768.0
        
        # VYLEPŠENÍ: Načtení jazyka z konfigurace pro spolehlivější přepis
        language = config['whisper'].get('language', 'cs') # 'cs' jako výchozí
        
        # Přepis audia s explicitně nastaveným jazykem
        logging.info(f"Spouštím přepis pro jazyk: {language}")
        result = model.transcribe(audio_float32, fp16=False, language=language)
        
        transcribed_text = result['text'].strip()
        logging.info(f"Přepsaný text: '{transcribed_text}'")
        return transcribed_text
        
    except Exception as e:
        logging.error(f"Chyba při přepisu audia: {e}")
        return ""
