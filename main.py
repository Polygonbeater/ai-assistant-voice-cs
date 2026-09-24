import sys
import pyaudio
import logging
import json
import os
import asyncio
import soundfile as sf
import numpy as np
import torch
import gc

# Importujeme funkce z našich modulů
from audio import initialize_porcupine, initialize_vad, capture_wake_word, record_with_vad
from stt_module import initialize_whisper, transcribe_audio_np
from llama_module import initialize_llama, generate_response
from tts_module import initialize_tts, speak_async

# Nastavení logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def _resolve_model_path(base_dir: str, configured_path: str) -> str:
    """Převede cestu v konfiguraci na absolutní cestu k projektu."""
    if not configured_path:
        raise ValueError("Konfigurační hodnota cesty nesmí být prázdná.")

    if os.path.isabs(configured_path):
        return configured_path

    return os.path.normpath(os.path.join(base_dir, configured_path))


def validate_config(config: dict) -> dict:
    """Kontroluje, že konfigurace obsahuje všechny potřebné klíče."""
    if not isinstance(config, dict):
        raise ValueError("Konfigurace musí být objekt JSON.")

    required_sections = {
        'porcupine': ['access_key', 'model_path', 'keyword'],
        'whisper': ['model'],
        'llama': ['model'],
        'tts': ['model_name'],
        'audio': ['device_index', 'wake_word_device_index', 'max_recording_time'],
        'silero_vad': ['sample_rate', 'threshold', 'silence_duration_ms'],
    }

    missing = []
    for section_name, required_keys in required_sections.items():
        section = config.get(section_name)
        if not isinstance(section, dict):
            missing.append(f"{section_name} (sekce chybí)")
            continue
        for key in required_keys:
            value = section.get(key)
            if value is None or (isinstance(value, str) and value.strip() == ''):
                missing.append(f"{section_name}.{key}")

    if missing:
        raise ValueError("Chybějící nebo neplatné klíče v konfiguraci: " + ", ".join(sorted(missing)))

    return config


def load_config(path="config.json"):
    """Načte konfiguraci ze souboru a přidá přátelské chybové hlášení."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.error(
            f"Konfigurační soubor '{path}' nebyl nalezen. "
            "Zkopírujte config.example.json do config.json a nastavte své údaje."
        )
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Chyba při parsování souboru '{path}'.")
        sys.exit(1)

    try:
        return validate_config(config)
    except ValueError as exc:
        logging.error(f"Neplatná konfigurace: {exc}")
        sys.exit(1)

def get_audio_device_index(p: pyaudio.PyAudio):
    """Vypíše dostupné audio vstupy a požádá uživatele o výběr."""
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')
    
    input_devices = []
    print("\n--- Dostupné audio vstupy ---")
    for i in range(num_devices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        if device_info.get('maxInputChannels') > 0:
            input_devices.append((i, device_info.get('name')))
            print(f"  Index: {i}, Název: {device_info.get('name')}")
    print("------------------------------\n")

    while True:
        try:
            choice = int(input("Zadejte index mikrofonu, který chcete použít: "))
            if any(choice == dev[0] for dev in input_devices):
                return choice
            else:
                print("Neplatný index. Zkuste to prosím znovu.")
        except ValueError:
            print("Neplatný vstup. Zadejte prosím číslo.")

def normalize_audio(audio_data_np: np.ndarray) -> np.ndarray:
    """
    Zesílí nahrávku na optimální úroveň pro Whisper.
    """
    if audio_data_np is None or audio_data_np.size == 0:
        logging.warning("Nahrávka je prázdná, vracím nepozměněné audio.")
        return np.asarray(audio_data_np if audio_data_np is not None else [], dtype=np.int16)

    logging.info("Normalizuji hlasitost nahrávky...")
    peak = np.abs(audio_data_np).max()
    if peak == 0:
        return audio_data_np  # Nahrávka je tichá

    # Cílová hlasitost (80% maximální možné)
    target_peak = 32767 * 0.8
    gain = target_peak / peak

    normalized_audio = (audio_data_np * gain).astype(np.int16)
    return normalized_audio

async def main():
    """Hlavní asynchronní smyčka asistenta."""
    porcupine = None
    pa = None
    loop = asyncio.get_event_loop()

    try:
        config = load_config()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config['porcupine']['model_path'] = _resolve_model_path(script_dir, config['porcupine']['model_path'])
        config['llama']['model'] = _resolve_model_path(script_dir, config['llama']['model'])

        if not os.path.exists(config['porcupine']['model_path']):
            raise FileNotFoundError(f"Soubor Porcupine modelu nebyl nalezen: {config['porcupine']['model_path']}")
        if not os.path.exists(config['llama']['model']):
            raise FileNotFoundError(f"Soubor LLaMA modelu nebyl nalezen: {config['llama']['model']}")

        pa = pyaudio.PyAudio()
        
        device_index = get_audio_device_index(pa)
        config['audio']['device_index'] = device_index
        config['audio']['wake_word_device_index'] = device_index
        
        logging.info("Inicializuji všechny modely, prosím čekejte...")
        porcupine = await loop.run_in_executor(None, initialize_porcupine, config)
        vad_model, _ = await loop.run_in_executor(None, initialize_vad)
        whisper_model = await loop.run_in_executor(None, initialize_whisper, config)
        llm = await loop.run_in_executor(None, initialize_llama, config)
        tts = await loop.run_in_executor(None, initialize_tts, config)
        logging.info(f"\n✅ Všechny modely úspěšně načteny. Asistent je připraven.")
        
        while True:
            logging.info(f"Čekám na klíčové slovo '{config['porcupine']['keyword']}'...")
            
            keyword_index = await loop.run_in_executor(None, capture_wake_word, porcupine, pa, config)

            if keyword_index >= 0:
                logging.info("🟢 Klíčové slovo detekováno!")
                await speak_async(tts, "Ano?")
                
                await asyncio.sleep(0.5)

                logging.info("Nahrávám tvůj příkaz...")
                audio_data_np = await loop.run_in_executor(None, record_with_vad, config, pa, vad_model)

                if audio_data_np.size > 0:
                    normalized_audio = normalize_audio(audio_data_np)

                    sample_rate = config['silero_vad']['sample_rate']
                    sf.write('debug_recording.wav', normalized_audio, sample_rate)
                    logging.info("Normalizovaná nahrávka uložena do 'debug_recording.wav'.")

                    transcribed_text = await loop.run_in_executor(None, transcribe_audio_np, whisper_model, normalized_audio, config)
                    
                    if transcribed_text:
                        response_text = await loop.run_in_executor(None, generate_response, llm, transcribed_text, config)
                        await speak_async(tts, response_text)
                    else:
                        logging.warning("Přepis byl prázdný, zkuste to znovu.")
                        await speak_async(tts, "Nerozuměl jsem, zkuste to prosím znovu.")
                else:
                    logging.info("Nahrávka byla prázdná.")

    except Exception as e:
        logging.error(f"Kritická chyba v hlavní smyčce: {e}", exc_info=True)
    finally:
        logging.info("Ukončuji aplikaci a provádím úklid...")
        if 'pa' in locals():
            try:
                pa.terminate()
                logging.info("PyAudio ukončeno.")
            except Exception as e:
                logging.error(f"Chyba při ukončení PyAudio: {e}")
        if 'porcupine' in locals():
            try:
                porcupine.delete()
                logging.info("Porcupine ukončeno.")
            except Exception as e:
                logging.error(f"Chyba při ukončení Porcupine: {e}")
        if 'llm' in locals():
            try:
                del llm
                logging.info("LLaMA ukončeno.")
            except Exception as e:
                logging.error(f"Chyba při ukončení LLaMA: {e}")
        if 'tts' in locals():
            try:
                tts = None
                logging.info("TTS ukončeno.")
            except Exception as e:
                logging.error(f"Chyba při ukončení TTS: {e}")
        if 'vad_model' in locals():
            try:
                vad_model = None
                logging.info("VAD model ukončen.")
            except Exception as e:
                logging.error(f"Chyba při ukončení VAD: {e}")
        if 'whisper_model' in locals():
            try:
                del whisper_model
                logging.info("Whisper model ukončen.")
            except Exception as e:
                logging.error(f"Chyba při ukončení Whisper: {e}")
        try:
            torch.cuda.empty_cache()
            logging.info("GPU paměť uvolněna.")
        except Exception as e:
            logging.error(f"Chyba při uvolnění GPU paměti: {e}")
        try:
            gc.collect()
            logging.info("Garbage collection provedena.")
        except Exception as e:
            logging.error(f"Chyba při garbage collection: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAplikace ukončena uživatelem.")