import os
import yaml
import logging
import time
import wave

from audio import initialize_porcupine, capture_wake_word, record_with_vad
from whisper import transcribe_audio
from llama_cpp import Llama

# --- Nastavení logování ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_config():
    """Načte konfigurační soubor config.yaml."""
    try:
        config_path = os.path.expanduser("~/ai-assistant/config.yaml")
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"Chyba při načítání konfigurace: {e}")
        exit(1)

def initialize_llama(config):
    model_path = config['llama']['model']
    max_tokens = config['llama'].get('max_tokens', 128)
    llm = Llama(model_path=model_path)
    return llm, max_tokens

def generate_response(llm, prompt: str, max_tokens: int) -> str:
    """Generuje odpověď pomocí Llama modelu."""
    response = llm(
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0.7,
        stop=None,
        echo=False,
    )
    return response['choices'][0]['text']

def save_audio(audio_data, config, filename="command.wav"):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 bit = 2 bytes
        wf.setframerate(config["audio"]["rate"])
        wf.writeframes(audio_data.tobytes())
    logging.info(f"Audio uloženo do {filename}")

def ai_assistant_loop():
    config = load_config()

    porcupine = initialize_porcupine(config)
    llm, max_tokens = initialize_llama(config)

    logging.info("Asistent spuštěn, čekám na klíčové slovo...")

    while True:
        result = capture_wake_word(porcupine, config)
        if result >= 0:
            logging.info("🟢 Klíčové slovo detekováno!")

            logging.info("Nahrávám tvůj příkaz...")
            audio_data = record_with_vad(config)

            save_audio(audio_data, config)

            text = transcribe_audio("command.wav", config)
            logging.info(f"Přepsaný text: {text}")

            if text.strip():
                logging.info("Generuji odpověď modelem Llama...")
                odpoved = generate_response(llm, text, max_tokens)
                logging.info(f"Odpověď asistenta: {odpoved}")

                # TTS, nebo další akce můžeš přidat zde
                print("Asistent říká:", odpoved)

        time.sleep(0.1)

if __name__ == "__main__":
    ai_assistant_loop()
