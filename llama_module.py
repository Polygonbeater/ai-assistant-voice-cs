import os
import logging
import re
from pathlib import Path
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ANALYTICAL_PRESETS = {
    "⚡ Auto (Doporučit)": "AUTO",
    "Vypnuto (Standardní chat)": None,
    "Hloubková analýza v3.1": "prompts/Advanced-Analytical-Prompts-main/Enhanced_Analysis_Prompts_v3.1_CZ.md",
    "Audit předpokladů (Standard)": "prompts/assumption-audit-main/CZ/Assumption_Audit.md",
    "Audit předpokladů (Krizový režim)": "prompts/assumption-audit-main/CZ/Assumption_Audit_Crisis.md",
    "Meta-analýza (Plná šablona)": "prompts/assumption-audit-main/templates/meta_full_CZ.txt",
}

DEFAULT_ANALYTICAL_PRESET = "Vypnuto (Standardní chat)"
DEFAULT_SYSTEM_PROMPT = (
    "Jsi užitečná a zdvořilá AI asistentka. "
    "Odpovídej stručně a k věci v češtině."
)


def load_analytical_prompt(
    preset_name: str,
    *,
    project_root: str | Path | None = None,
) -> str | None:
    """Bezpečně načte zvolenou metodiku, nebo vrátí None pro standardní chat."""
    if preset_name in ("⚡ Auto (Doporučit)", "Vypnuto (Standardní chat)"):
        return None
    if preset_name not in ANALYTICAL_PRESETS:
        raise ValueError(f"Neznámá analytická metodika: {preset_name!r}")

    rel_path = ANALYTICAL_PRESETS[preset_name]
    if not rel_path or rel_path == "AUTO":
        return None

    root = Path(project_root) if project_root else Path(__file__).resolve().parent
    prompt_path = (root / rel_path).resolve()

    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Soubor analytické metodiky nebyl nalezen: {prompt_path}") from exc
    except OSError as exc:
        raise OSError(f"Analytickou metodiku nelze načíst: {prompt_path}") from exc


def get_physical_cpu_cores() -> int:
    """
    Zjišťuje přesný počet fyzických jader procesoru (nikoliv logických/SMT vláken).
    Pro inferenci v llama.cpp na CPU je použití počtu vláken rovného počtu fyzických jader
    nejrychlejší konfigurací – zamezuje thread contention a soutěžení o FPU/AVX2 jednotky.
    """
    try:
        import psutil
        physical = psutil.cpu_count(logical=False)
        if physical and physical > 0:
            return physical
    except Exception:
        pass

    try:
        total = os.cpu_count() or 4
        # Standardní fallback pro procesory s hyperthreadingem (2 vlákna na jádro)
        return max(1, total // 2 if total > 2 else total)
    except Exception:
        return 4


def resolve_optimal_context_size(model_path: str, user_n_ctx: int | str | None = None) -> int:
    """
    Určuje optimální velikost kontextového okna (n_ctx) pro modely Qwen2.5 a GLM-4,
    aby KV cache zbytečně neobsazovala operační paměť RAM.
    """
    if user_n_ctx is not None and str(user_n_ctx).strip().lower() not in ("auto", "0", ""):
        try:
            val = int(user_n_ctx)
            if val > 0:
                return val
        except ValueError:
            pass

    model_lower = (model_path or "").lower()
    # GLM-4 (40 vrstev, větší skrytý rozměr) – 3072 tokenů plně pokryje web search i analýzu a šetří RAM
    if "glm-4" in model_lower or "chatglm" in model_lower:
        return 3072
    # Qwen2.5 (28 vrstev, efektivní GQA) – 4096 tokenů poskytne velký prostor pro kontext s nízkou režií
    elif "qwen" in model_lower:
        return 4096
    else:
        return 2048


def initialize_llama(config: dict) -> Llama:
    """Inicializuje Llama model s optimalizací parametrů pro maximální rychlost na CPU."""
    try:
        llama_cfg = config.get('llama', {})
        model_path = llama_cfg.get('model', '')
        if not model_path:
            raise ValueError("V konfiguraci není specifikována cesta k modelu ('llama.model').")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Soubor modelu nebyl nalezen: '{model_path}'")

        # 1. Dynamické zjištění počtu fyzických jader CPU
        physical_cores = get_physical_cpu_cores()
        configured_threads = llama_cfg.get('n_threads')
        if configured_threads and str(configured_threads).isdigit() and int(configured_threads) > 0:
            n_threads = int(configured_threads)
        else:
            n_threads = physical_cores

        n_threads_batch = int(llama_cfg.get('n_threads_batch', n_threads))

        # 2. Optimalizace velikosti kontextu pro model
        n_ctx = resolve_optimal_context_size(model_path, llama_cfg.get('n_ctx'))

        # 3. Dávkování (batching) pro CPU
        n_batch = int(llama_cfg.get('n_batch', 512))
        n_ubatch = int(llama_cfg.get('n_ubatch', 256))

        # 4. Paměťové mapování a uzamčení
        use_mmap = bool(llama_cfg.get('use_mmap', True))
        use_mlock = bool(llama_cfg.get('use_mlock', False))

        # 5. GPU vrstvy (pro CPU je výchozí 0)
        n_gpu_layers = int(llama_cfg.get('n_gpu_layers', 0))

        logging.info(
            f"Načítám Llama model z: {model_path} | "
            f"n_threads={n_threads} (fyzická jádra={physical_cores}), "
            f"n_ctx={n_ctx}, n_batch={n_batch}, n_ubatch={n_ubatch}, "
            f"use_mmap={use_mmap}, use_mlock={use_mlock}, n_gpu_layers={n_gpu_layers}"
        )

        llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch,
            n_ubatch=n_ubatch,
            n_threads=n_threads,
            n_threads_batch=n_threads_batch,
            use_mmap=use_mmap,
            use_mlock=use_mlock,
            verbose=False,
        )
        logging.info(
            f"Llama model úspěšně inicializován na CPU "
            f"({n_threads} fyzických vláken, n_ctx={n_ctx})."
        )
        return llm
    except Exception as e:
        logging.error(f"Chyba při inicializaci Llama modelu: {e}")
        raise


def _try_evaluate_math(prompt: str) -> str | None:
    """Rozpozná a spočítá jednoduchý matematický výraz v textu."""
    clean = prompt.lower().replace('mínus', '-').replace('plus', '+').replace('krát', '*').replace('děleno', '/').replace('x', '*')
    match = re.search(r'(-?\d+)\s*([+\-*/])\s*(-?\d+)', clean)
    if match:
        try:
            num1 = float(match.group(1))
            op = match.group(2)
            num2 = float(match.group(3))
            if op == '+':
                res = num1 + num2
            elif op == '-':
                res = num1 - num2
            elif op == '*':
                res = num1 * num2
            elif op == '/':
                if num2 == 0:
                    return "Dělení nulou není povoleno."
                res = num1 / num2
            if res.is_integer():
                res = int(res)
            return f"Výsledek je {res}."
        except Exception:
            return None
    return None


def classify_methodology(llm, user_text: str) -> str:
    """Rychlá mikro-klasifikace dotazu pro volbu metodiky přes Chat API."""
    messages = [
        {"role": "system", "content": "Jsi klasifikátor dotazů. Odpovídej výhradně jedním ze zadaných názvů."},
        {"role": "user", "content": (
            "Vyber nejvhodnější metodiku pro následující dotaz uživatele:\n"
            "- Hloubková analýza v3.1\n"
            "- Audit předpokladů (Standard)\n"
            "- Audit předpokladů (Krizový režim)\n"
            "- Vypnuto (Standardní chat)\n\n"
            f"Dotaz: {user_text[:250]}\n"
            "Odpověz POUZE přesným názvem možnosti."
        )}
    ]
    try:
        res = llm.create_chat_completion(messages=messages, max_tokens=15, temperature=0.1)
        out = res["choices"][0]["message"].get("content", "").strip()
        for candidate in [
            "Audit předpokladů (Krizový režim)",
            "Audit předpokladů (Standard)",
            "Hloubková analýza v3.1",
            "Vypnuto (Standardní chat)"
        ]:
            if candidate.lower() in out.lower():
                return candidate
    except Exception as exc:
        logging.warning("Klasifikace metodiky selhala: %s", exc)
    return "Vypnuto (Standardní chat)"


def generate_response(llm: Llama, prompt: str, config: dict, callback_on_token=None, stop_event=None, chat_history: list = None, **kwargs) -> str:
    """Generuje odpověď přes Chat API modelu s podporou streamování, paměti a přerušení."""
    math_result = _try_evaluate_math(prompt)
    if math_result:
        if callback_on_token:
            callback_on_token(math_result)
        return math_result

    try:
        llama_config = config.get("llama", {})
        system_prompt = llama_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
        preset_name = llama_config.get("analytical_preset", DEFAULT_ANALYTICAL_PRESET)

        try:
            analytical_prompt = load_analytical_prompt(preset_name)
        except Exception as exc:
            logging.error("Analytickou metodiku se nepodařilo použít: %s", exc)
            analytical_prompt = None

        if analytical_prompt:
            system_prompt = analytical_prompt

        user_content = prompt
        if llama_config.get("online_mode"):
            try:
                from web_search import search_web_context
                search_query = prompt
                if chat_history and len(prompt.split()) <= 6:
                    for prev in reversed(chat_history):
                        if prev.get("role") == "user":
                            search_query = f"{prev.get('content', '')[:60]} {prompt}"
                            break

                web_context = search_web_context(search_query)
                user_content = f"{web_context}\n\nDOTAZ UŽIVATELE:\n{prompt}"
            except Exception:
                logging.exception("Online kontext se nepodařilo načíst.")

        # Dynamické tokeny
        raw_max = llama_config.get('max_tokens', 'auto')
        if str(raw_max).strip().lower() in ('auto', '0', ''):
            if preset_name and preset_name not in ("Vypnuto (Standardní chat)", "⚡ Auto (Doporučit)"):
                max_tokens = 2048
            else:
                max_tokens = 1536
        else:
            try:
                max_tokens = int(raw_max)
            except ValueError:
                max_tokens = 1536

                # Dynamické vložení systémového času a data
        from datetime import datetime
        now = datetime.now()
        dny = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
        den_nazev = dny[now.weekday()]
        cas_info = (
            f"\n\n[AKTUÁLNÍ SYSTÉMOVÝ ČAS A DATUM: {den_nazev} {now.day}. {now.month}. {now.year}, {now.strftime('%H:%M')}]\n"
            "PRAVIDLA PRO ČAS A ZPRAVODAJSTVÍ:\n"
            "- Výše uvedený čas je tvůj přesný reálný čas. Podle něj určuj, co je ráno, odpoledne, dnes či včera.\n"
            "- Z webových článků NIKDY nekopíruj zastaralé relativní údaje jako 'před hodinou' či 'před 7 minutami'. "
            "Uveď pouze přesný čas vydání článku (např. 'v 08:17') a posuzuj stáří zprávy vůči systémovému času.\n"
            "- Vždy navazuj na předchozí kontext konverzace a paměť odpovědí."
        )
        system_prompt = f"{system_prompt}{cas_info}"

        # Sestavení kontextového okna (historie chatu)
        messages = [{"role": "system", "content": system_prompt}]
        if chat_history:
            for turn in chat_history:
                r = "assistant" if turn.get("role") == "assistant" else "user"
                c = turn.get("content") or turn.get("text") or ""
                if c:
                    messages.append({"role": r, "content": c})
        messages.append({"role": "user", "content": user_content})

        logging.info("Generuji odpověď přes Chat API (max_tokens=%d, kontext_zpráv=%d, stream=True)...", max_tokens, len(messages))
        stream = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=float(llama_config.get("temperature", 0.7)),
            stream=True,
        )

        tokens = []
        for chunk in stream:
            if stop_event and stop_event.is_set():
                logging.info("Generování přerušeno uživatelem (Stop).")
                break
            delta = chunk["choices"][0].get("delta", {})
            text_piece = delta.get("content") or ""
            if text_piece:
                tokens.append(text_piece)
                if callback_on_token:
                    callback_on_token(text_piece)

        generated_text = "".join(tokens).strip()
        if not generated_text:
            return "Generování bylo ukončeno nebo model nevrátil text."
        return generated_text

    except Exception as exc:
        logging.error("Chyba při generování: %s", exc)
        return f"Omlouvám se, došlo k chybě: {exc}"
