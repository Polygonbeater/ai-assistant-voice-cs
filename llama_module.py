import logging
import json
import re
from llama_cpp import Llama

# Konfigurace logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def initialize_llama(config: dict) -> Llama:
    """Inicializuje a vrátí instanci Llama modelu."""
    try:
        model_path = config['llama']['model']
        logging.info(f"Načítám Llama model z: {model_path}")
        llm = Llama(model_path=model_path, n_ctx=4096, verbose=False)
        logging.info("Llama model inicializován.")
        return llm
    except Exception as e:
        logging.error(f"Chyba při inicializaci Llama modelu: {e}")
        raise

def _try_evaluate_math(prompt: str) -> str | None:
    """
    Pokusí se rozpoznat a vypočítat jednoduchý matematický výraz v textu.
    """
    # Nahradíme slovní operátory a 'x' za symboly
    prompt = prompt.lower().replace('mínus', '-').replace('plus', '+').replace('krát', '*').replace('děleno', '/').replace('x', '*')
    
    # Hledá vzor jako "10 + 5" nebo "kolik je 268-400"
    match = re.search(r'(-?\d+)\s*([+\-*/])\s*(-?\d+)', prompt)
    if match:
        try:
            num1 = int(match.group(1))
            operator = match.group(2)
            num2 = int(match.group(3))
            
            result = 0
            if operator == '+':
                result = num1 + num2
            elif operator == '-':
                result = num1 - num2
            elif operator == '*':
                result = num1 * num2
            elif operator == '/':
                if num2 == 0:
                    return "Nemohu dělit nulou."
                result = num1 / num2
            
            logging.info(f"Rozpoznán matematický výraz: {num1} {operator} {num2}. Výsledek: {result}")
            return f"Výsledek je {result}."
        except (ValueError, IndexError):
            return None # Pokud se parsování nepovede
    return None

def _create_full_prompt(user_text: str) -> str:
    """Sestaví prompt ve formátu, který očekává Mistral Instruct."""
    system_prompt = "Jsi užitečná a zdvořilá AI asistentka. Odpovídej stručně a k věci v češtině."
    return f"[INST] {system_prompt} [/INST]\n[INST] {user_text} [/INST]"

def generate_response(llm: Llama, prompt: str, config: dict) -> str:
    """
    Generuje textovou odpověď. Nejprve zkusí matematiku, pak LLM.
    """
    math_result = _try_evaluate_math(prompt)
    if math_result:
        return math_result

    try:
        full_prompt = _create_full_prompt(prompt)
        max_tokens = config['llama'].get('max_tokens', 150)

        logging.info("Generuji odpověď pomocí LLM...")
        response = llm(
            prompt=full_prompt,
            max_tokens=max_tokens,
            temperature=0.7,
            stop=["</s>", "[INST]"],
            echo=False,
        )
        generated_text = response['choices'][0]['text'].strip()
        
        if not generated_text:
            logging.warning("LLM vrátil prázdnou odpověď. Používám záložní text.")
            return "Bohužel, na to teď nedokážu odpovědět."

        logging.info(f"LLM odpověď: '{generated_text}'")
        return generated_text
        
    except Exception as e:
        logging.error(f"Chyba při generování odpovědi Llama: {e}")
        return "Omlouvám se, došlo k chybě při generování odpovědi."
