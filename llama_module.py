import os
import logging
import re
from pathlib import Path
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ANALYTICAL_PRESETS = {
    "⚡ Auto (Doporučit)": "AUTO",
    "🎬 Auteur & Vizuální analýza (Mise-en-scène)": "prompts/frameworks/auteur_visual_analysis.md",
    "📐 First Principles (Kód & 3D dekonstrukce)": "prompts/frameworks/first_principles_technical.md",
    "🛡️ Red Team & Oponentura hypotéz": "prompts/frameworks/advanced_assumption_audit.md",
    "Hloubková analýza v3.1": "prompts/Advanced-Analytical-Prompts-main/Enhanced_Analysis_Prompts_v3.1_CZ.md",
    "Audit předpokladů (Standard)": "prompts/assumption-audit-main/CZ/Assumption_Audit.md",
    "Audit předpokladů (Krizový režim)": "prompts/assumption-audit-main/CZ/Assumption_Audit_Crisis.md",
    "Meta-analýza (Plná šablona)": "prompts/assumption-audit-main/templates/meta_full_CZ.txt",
    "Vypnuto (Standardní chat)": None,
}

DEFAULT_ANALYTICAL_PRESET = "Vypnuto (Standardní chat)"
DEFAULT_SYSTEM_PROMPT = (
    "Jsi užitečná a zdvořilá AI asistentka. "
    "Odpovídej stručně a k věci v češtině."
)


ANALYSIS_MODE_PATTERNS = {
    "🎬 Auteur & Vizuální analýza (Mise-en-scène)": [
        r"\b(filmov[a-ž]+\s+(vědec|teoretik|analytik|věda|teorie|analýz[a-ž]*|dekonstrukc[a-ž]*|jazyk))\b",
        r"\b(mise[- ]en[- ]sc[èe]ne|mizanscén[a-ž]*)\b",
        r"\b(auteur|autorsk[a-ž]+\s+rukopis|režijn[a-ž]+\s+styl)\b",
        r"\b(chiaroscuro|šerosvit|tenebrism[a-ž]*)\b",
        r"\b(německ[a-ž]+\s+expresionism[a-ž]*|fritz\s+lang|metropolis)\b",
        r"\b(kompozic[a-ž]+\s+záběr[a-ž]*|vizuáln[a-ž]+\s+rytm[a-ž]*|střihov[a-ž]+\s+skladb[a-ž]*|montážn[a-ž]+\s+skladb[a-ž]*)\b",
        r"\b(malířsk[a-ž]+\s+ikonografi[a-ž]*|ikonografick[a-ž]*|vizuáln[a-ž]+\s+dekonstrukc[a-ž]*)\b",
        r"\b(analyzuj\s+.*filmov[a-ž]+(\s+věd[a-ž]+)?)\b",
    ],
    "📐 First Principles (Kód & 3D dekonstrukce)": [
        r"\b(prvn[ií][a-ž]*\s+princip[a-ž]*|first\s+principles)\b",
        r"\b(rozeber\s+.*(od|ze)\s+základ[a-ž]*|od\s+(úpln[a-ž]+|fyzikáln[a-ž]+|matematick[a-ž]+)\s+základ[a-ž]*)\b",
        r"\b(technick[a-ž]+\s+dekonstrukc[a-ž]*|dekonstrukc[a-ž]+\s+kód[a-ž]*|dekonstruuj\s+(kód|problém|systém|architektur[a-ž]*))\b",
        r"\b(bez\s+zkratek|žádn[a-ž]+\s+zkratk[a-ž]*|rigorózn[a-ž]+\s+řešen[a-ž]*)\b",
        r"\b(blender\s+.*od\s+základ[a-ž]*|3d\s+matematik[a-ž]*|geometrick[a-ž]+\s+dekonstrukc[a-ž]*)\b",
        r"\b(invariant[a-ž]*|stavov[a-ž]+\s+prostor\s+bez\s+zkratek)\b",
    ],
    "🛡️ Red Team & Oponentura hypotéz": [
        r"\b(kritick[a-ž]*\s+oponentur[a-ž]*|udělej\s+oponentur[a-ž]*|oponentur[a-ž]*\s+(hypotéz[a-ž]*|návrh[a-ž]*|kód[a-ž]*))\b",
        r"\b(red\s+team|red\s+teaming|red\s+team\s+critique|zátěžov[a-ž]+\s+test\s+hypotéz[a-ž]*)\b",
        r"\b(audit\s+předpoklad[a-ž]*|audit\s+samozřejmost[a-ž]*|assumption\s+audit)\b",
        r"\b(prověř\s+předpoklad[a-ž]*|zpochybni\s+předpoklad[a-ž]*|slep[aá][a-ž]*\s+míst[a-ž]*)\b",
        r"\b(kde\s+to\s+selže|jak\s+to\s+může\s+selhat|najdi\s+slab[a-ž]+\s+míst[a-ž]*|najdi\s+logick[a-ž]+\s+chyb[a-ž]*)\b",
        r"\b(vyvrať\s+mi\s+to|falsifikuj|popperovsk[a-ž]+\s+falsifikac[a-ž]*|falsifikačn[a-ž]+\s+kritéri[a-ž]*)\b",
    ],
}

ANALYTICAL_ROUTER_SYSTEM_PROMPT = (
    "Jsi bleskový router analytických metodik. Rozhodni, zda dotaz vyžaduje jeden ze 3 expertních frameworků:\n"
    "1. AUTEUR - filmová dekonstrukce, mise-en-scène, režie, kompozice záběru, malířská ikonografie, Fritz Lang apod.\n"
    "2. FIRST_PRINCIPLES - myšlení v prvních principech, složitý kód/architektura, 3D matematika, Blender API od základů.\n"
    "3. RED_TEAM - kritická oponentura hypotéz, hledání slepých míst, audit předpokladů a analýza selhání.\n"
    "4. STANDARD - běžný dotaz, konverzace, obecná otázka.\n"
    "Odpověz POUZE jedním slovem: AUTEUR, FIRST_PRINCIPLES, RED_TEAM nebo STANDARD."
)


def detect_analytical_mode(
    prompt: str,
    llm: Llama | None = None,
    allow_llm_classifier: bool = False,
) -> str | None:
    """
    Automaticky rozpozná, zda uživatel v dotazu požaduje hluboký analytický režim:
    - 🎬 Auteur & Vizuální analýza (Mise-en-scène)
    - 📐 First Principles (Kód & 3D dekonstrukce)
    - 🛡️ Red Team & Oponentura hypotéz

    1. Fáze: Rychlá pravidlová detekce klíčových frází (0 ms latence).
    2. Fáze: Pokud je povoleno a pravidla nenašla shodu (např. v režimu Auto), blesková LLM klasifikace.
    """
    clean_p = prompt.strip().lower()
    if not clean_p:
        return None

    # 1. Pravidlová detekce podle regexů
    for mode, regexes in ANALYSIS_MODE_PATTERNS.items():
        for pattern in regexes:
            if re.search(pattern, clean_p, re.IGNORECASE):
                logging.info("Analytický router: Pravidlová detekce -> %s", mode)
                return mode

    # 2. Blesková klasifikace modelem (pokud je explicitně vyžádána v režimu Auto)
    if allow_llm_classifier and llm is not None:
        try:
            resp = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": ANALYTICAL_ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Dotaz: {prompt[:300]}\nFramework:"}
                ],
                max_tokens=6,
                temperature=0.0,
                stream=False
            )
            decision = resp["choices"][0]["message"].get("content", "").strip().upper()
            logging.info("Analytický router LLM vyhodnocení: '%s'", decision)
            if "AUTEUR" in decision:
                return "🎬 Auteur & Vizuální analýza (Mise-en-scène)"
            if "FIRST_PRINCIPLES" in decision:
                return "📐 First Principles (Kód & 3D dekonstrukce)"
            if "RED_TEAM" in decision:
                return "🛡️ Red Team & Oponentura hypotéz"
        except Exception as exc:
            logging.warning("Analytický router LLM selhal: %s", exc)

    return None


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


CZECH_ABBREVIATIONS = {
    'např.', 'tzv.', 'atd.', 'apod.', 'tj.', 'tzn.', 'č.', 'str.',
    'ing.', 'mgr.', 'dr.', 'bc.', 'odd.', 'kol.', 'prof.', 'mudr.', 'judr.'
}


def extract_sentence_chunks(buffer: str, is_final: bool = False) -> tuple[list[str], str]:
    """
    Rozdělí textový buffer na ucelené věty nebo logické úseky podle interpunkce.
    Vrací seznam dokončených úseků (vhodných pro okamžitou TTS syntézu) a zbývající buffer.
    """
    chunks = []
    while True:
        # Hledáme větnou interpunkci (. ! ?) nebo nový řádek
        match = re.search(r'([.!?]+|\n+)(?:\s+|$)', buffer)
        if not match:
            # Pokud je věta dlouhá (> 75 znaků) a obsahuje čárku, středník, dvojtečku nebo pomlčku
            if len(buffer) > 75:
                clause_match = re.search(r'([,;:—–]|\s-\s)\s*', buffer)
                if clause_match:
                    split_pos = clause_match.end()
                    chunk = buffer[:split_pos].strip()
                    if chunk:
                        chunks.append(chunk)
                    buffer = buffer[split_pos:]
                    continue
            break

        punct_end = match.end(1)
        full_match_end = match.end()
        candidate = buffer[:punct_end].strip()

        # Ochrana proti roztržení zkratek a řadových číslovek (např. '1. října')
        last_word = candidate.split()[-1].lower() if candidate.split() else ''
        is_ordinal_or_abbrev = (
            last_word in CZECH_ABBREVIATIONS or
            bool(re.search(r'\b\d+\.$', candidate))
        )

        if is_ordinal_or_abbrev and not is_final:
            remaining = buffer[full_match_end:]
            next_match = re.search(r'([.!?]+|\n+)(?:\s+|$)', remaining)
            if not next_match:
                break
            punct_end = full_match_end + next_match.end(1)
            full_match_end = full_match_end + next_match.end()
            candidate = buffer[:punct_end].strip()

        if candidate:
            chunks.append(candidate)
        buffer = buffer[full_match_end:]

    if is_final and buffer.strip():
        chunks.append(buffer.strip())
        buffer = ""

    return chunks, buffer


BLENDER_SYSTEM_PROMPT = """Jsi specializovaný asistent pro generování Python skriptů pro 3D software Blender (knihovna bpy).
Tvým úkolem je převést uživatelský pokyn na bezpečný, přesný a plně funkční Python kód pro Blender API.

PRAVIDLA:
1. Vracíš VÝHRADNĚ a POUZE čistý spustitelný Python kód. Žádné markdown bloky (žádné ```python ani ```), žádné komentáře okolo, žádný úvodní ani závěrečný text.
2. Vždy na začátku importuj `import bpy`.
3. Používej správné operátory a metody Blender API:
   - Vycentrování pivotů na geometrii:
     for obj in bpy.context.selected_objects:
         bpy.context.view_layer.objects.active = obj
         bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
   - Aplikace transformací (scale):
     bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
   - Tvorba primitiv:
     bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
   - Smazání objektů:
     bpy.ops.object.delete(use_global=False)
4. Kód musí být připraven k okamžitému spuštění přes exec()."""


def clean_python_code(raw_text: str) -> str:
    """
    Odstraní z textu Markdown syntaxi kódových bloků (```python ... ```)
    a případné doprovodné věty, aby zbyl pouze čistý spustitelný Python kód.
    """
    text = raw_text.strip()
    match = re.search(r'```(?:python)?\s*\n?(.*?)\n?```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) > 1:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    return text


def is_blender_command(prompt: str, config: dict | None = None) -> bool:
    """
    Detekuje, zda uživatelský pokyn představuje automatizační příkaz pro Blender 3D.
    Rozlišuje obecné otázky (např. "co je nového v Blenderu") od akčních skriptovacích příkazů.
    """
    if config and not config.get("blender", {}).get("enabled", True):
        return False

    p = prompt.strip().lower()

    # Informační dotazy a otázky nesmí spustit bpy automatizaci
    info_question_starters = (
        "co je", "co jsou", "jaké jsou", "jaký je", "jaká je", "kdy", "proč",
        "kdo", "vysvětli", "popiš", "jak funguje", "jak se liší", "porovnej",
        "napiš", "řekni", "pověz", "shrň", "jak vytvořit", "jak udělat"
    )
    if any(p.startswith(q) for q in info_question_starters):
        return False

    # Příkaz pro Blender vyžaduje akční operaci nebo skriptování
    action_keywords = [
        "vytvoř", "přidej", "smaž", "odstraň", "vycentruj", "aplikuj", "nastav",
        "otoč", "posuň", "změň", "vyber", "označ", "vyrenderuj", "extruduj", "subdivide",
        "vyčisti", "spusť skript", "vygeneruj skript"
    ]
    has_action = any(re.search(rf"\b{act}", p) for act in action_keywords)

    if any(k in p for k in ["v blenderu", "do blenderu", "pomocí bpy", "přes bpy"]):
        if has_action or "kód" in p or "skript" in p:
            return True

    blender_patterns = [
        r'\bpivot', r'\bvycentruj',
        r'\baplikuj scale\b', r'\baplikuj rotac', r'\baplikuj transformac',
        r'\borigin\b', r'\bset origin\b', r'\bvybran[éý]ch objekt', r'\boznačen[éý]ch objekt',
        r'\b(vytvoř|přidej)\s+(krychl|koul|vál|kužel|mesh|světl|kamer|materiál)',
        r'\bsmaž\s+(vybran|všechn|objekt)',
        r'\bvyrenderuj\b', r'\bextruduj\b', r'\bsubdivide\b',
        r'\bshade (smooth|flat)\b'
    ]

    for pat in blender_patterns:
        if re.search(pat, p):
            return True

    return False


def handle_blender_command(
    llm: Llama,
    prompt: str,
    config: dict,
    callback_on_token=None,
    stop_event=None,
    status_callback=None,
):
    """
    Vygeneruje Python kód pro Blender (bpy) na základě uživatelského pokynu
    a odešle ho přes lokální TCP socket do běžící instance Blenderu.
    Obsahuje Self-Healing Blender Loop – při chybě (Exception) zachytí traceback
    a nechá LLM kód automaticky opravit (až 2 pokusy o opravu).
    """
    from blender_connector import send_code_to_blender, is_blender_available

    blender_cfg = config.get("blender", {})
    host = blender_cfg.get("host", "127.0.0.1")
    port = int(blender_cfg.get("port", 9876))
    max_retries = int(blender_cfg.get("max_retries", 2))

    if status_callback:
        status_callback("● Generuji Python kód pro Blender…")

    status_msg = "Generuji Python kód pro Blender…"
    if callback_on_token:
        callback_on_token(status_msg + "\n")
    yield status_msg

    try:
        # Ověření dostupnosti Blenderu na socketu
        if not is_blender_available(host, port):
            warn_msg = (
                f"\n\n⚠️ **Blender není připojen na portu {port}.**\n\n"
                f"Spusťte prosím v Blenderu v Text Editoru skript `blender_receiver.py` (Run Script / Alt+P).\n\n"
            )
            tts_alert = "Blender není připojen na portu 9876. Spusťte prosím v Blenderu přijímací skript."
            if callback_on_token:
                callback_on_token(warn_msg)
            yield tts_alert
            return

        messages = [
            {"role": "system", "content": BLENDER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Příkaz: {prompt}"}
        ]

        attempt = 0
        last_code = ""
        last_res = {}

        while attempt <= max_retries:
            if stop_event and stop_event.is_set():
                return

            if attempt > 0:
                if status_callback:
                    status_callback(f"● 🔄 Blender Self-Healing: Generuji opravu ({attempt}/{max_retries})…")
                if callback_on_token:
                    callback_on_token(f"\n🔄 *Self-Healing (pokus {attempt}/{max_retries}): Generuji opravenou verzi kódu...*\n")

            response = llm.create_chat_completion(
                messages=messages,
                max_tokens=450,
                temperature=0.1,
                stream=False
            )

            raw_code = response["choices"][0]["message"].get("content", "")
            clean_code = clean_python_code(raw_code)
            last_code = clean_code

            if not clean_code:
                err_msg = "Nepodařilo se vygenerovat kód pro Blender."
                if callback_on_token:
                    callback_on_token(f"\n{err_msg}\n")
                yield err_msg
                return

            # Odeslání do Blenderu přes TCP socket
            if status_callback:
                if attempt == 0:
                    status_callback("● Odesílám kód do Blenderu…")
                else:
                    status_callback(f"● Odesílám opravený kód do Blenderu ({attempt}/{max_retries})…")

            res = send_code_to_blender(clean_code, host=host, port=port, timeout=10.0)
            last_res = res

            # Vyhodnocení výsledku
            if res.get("status") == "success":
                output_info = res.get("output", "").strip()
                out_detail = f"\n*Výstup z Blenderu:* `{output_info}`" if output_info and output_info != "Kód byl úspěšně vykonán." else ""

                if attempt > 0:
                    success_ui = (
                        f"\n\n✅ **Příkaz v Blenderu byl úspěšně vykonán po automatické opravě (pokus {attempt}/{max_retries}).**{out_detail}\n\n"
                        f"```python\n{clean_code}\n```"
                    )
                    success_tts = "Příkaz byl po automatické opravě úspěšně vykonán v Blenderu."
                    if status_callback:
                        status_callback("● ✅ Kód byl v Blenderu úspěšně opraven a vykonán")
                else:
                    success_ui = (
                        f"\n\n✅ **Příkaz v Blenderu byl úspěšně vykonán.**{out_detail}\n\n"
                        f"```python\n{clean_code}\n```"
                    )
                    success_tts = "Příkaz byl úspěšně vykonán v Blenderu."
                    if status_callback:
                        status_callback("● ✅ Kód byl v Blenderu úspěšně vykonán")

                if callback_on_token:
                    callback_on_token(success_ui)
                yield success_tts
                return

            # Došlo k chybě při spuštění kódu v Blenderu
            err_msg = res.get("error") or res.get("message", "Neznámá chyba")
            tb = res.get("traceback", "")
            err_short = err_msg.splitlines()[-1] if "\n" in err_msg else err_msg

            # Síťová chyba (odmítnuto / timeout socketu)
            if res.get("error_type") in ("ConnectionRefused", "Timeout") and not is_blender_available(host, port):
                fail_ui = (
                    f"\n\n❌ **Spojení s Blenderem selhalo:** {err_msg}\n"
                    f"**Poslední kód:**\n```python\n{clean_code}\n```"
                )
                if callback_on_token:
                    callback_on_token(fail_ui)
                yield "Spojení s Blenderem bylo přerušeno."
                return

            attempt += 1
            if attempt <= max_retries:
                logging.warning(
                    "Blender kód vyvolal chybu (pokus %d/%d): %s. Spouštím Self-Healing smyčku.",
                    attempt, max_retries, err_short
                )
                if status_callback:
                    status_callback(f"● ⚠️ Chyba v Blenderu: {err_short[:35]}… Zahajuji opravu ({attempt}/{max_retries})")

                if callback_on_token:
                    callback_on_token(
                        f"\n⚠️ *Chyba při vykonávání v Blenderu:* `{err_short}`\n"
                        f"🛠️ *Aktivuji Self-Healing smyčku (pokus {attempt}/{max_retries})...*\n"
                    )

                # Přidáme asistentův kód a uživatelský pokyn k opravě
                messages.append({"role": "assistant", "content": clean_code})
                repair_prompt = (
                    f"Tvůj předchozí kód pro Blender selhal s následující chybou (Exception):\n"
                    f"CHYBA: {err_msg}\n"
                )
                if tb:
                    repair_prompt += f"TRACEBACK:\n{tb}\n"
                repair_prompt += (
                    f"\nAnalyzuj přesnou příčinu selhání (např. neplatný kontext, chybějící objekt, "
                    f"nesprávný atribut nebo zastaralá syntaxe API) a vygeneruj kompletní OPRAVENÝ a funkční "
                    f"Python kód pro Blender (bpy). Odpověz VÝHRADNĚ čistým Python kódem bez jakéhokoliv markdownu či komentářů."
                )
                messages.append({"role": "user", "content": repair_prompt})

        # Všechny pokusy vyčerpány
        final_err = last_res.get("error") or last_res.get("message", "Neznámá chyba")
        final_tb = last_res.get("traceback", "")
        tb_detail = f"\n```\n{final_tb}\n```" if final_tb else ""
        fail_ui = (
            f"\n\n❌ **Při vykonávání v Blenderu došlo k chybě (i po {max_retries} pokusech o automatickou opravu):**\n"
            f"**Chyba:** `{final_err}`{tb_detail}\n\n"
            f"**Poslední verze kódu:**\n```python\n{last_code}\n```"
        )
        fail_tts = "Při vykonávání kódu v Blenderu došlo k chybě i po automatických pokusech o opravu."
        if status_callback:
            status_callback("● ❌ Kód se v Blenderu nepodařilo automaticky opravit")
        if callback_on_token:
            callback_on_token(fail_ui)
        yield fail_tts

    except Exception as exc:
        logging.exception("Chyba při zpracování příkazu pro Blender: %s", exc)
        err = f"Chyba při zpracování příkazu pro Blender: {exc}"
        if callback_on_token:
            callback_on_token(f"\n{err}\n")
        yield err


SEARCH_INTENT_SYSTEM_PROMPT = (
    "Jsi bleskový klasifikátor záměru vyhledávání. Rozhodni, zda dotaz vyžaduje aktuální informace z internetu "
    "(např. čerstvé zprávy, dnešní události, konkrétní ceny, kurzy, počasí, nové verze a release notes po roce 2024), "
    "nebo zda si vystačí s obecnými vnitřními znalostmi (programování, teorie, matematika, definice, kód, skripty pro Blender, běžný rozhovor).\n"
    "Odpověz VÝHRADNĚ jedním slovem: ONLINE nebo OFFLINE."
)


def classify_search_intent(
    llm: Llama,
    prompt: str,
    chat_history: list | None = None
) -> bool:
    """
    Bleskový Search Intent Router (5-10 tokenů).
    Vyhodnotí, zda uživatelský dotaz reálně vyžaduje čerstvá internetová data (ONLINE),
    nebo si vystačí s interními váhami modelu (OFFLINE).
    """
    p = prompt.strip().lower()

    # 1. Rychlé pravidlové zkratky (rychlost 0 ms)
    explicit_online = (
        "vyhledej", "najdi na webu", "vygoogli", "hledej online",
        "dnešní zprávy", "čt24", "aktuální zprávy", "co je dnes nového",
        "dnešní kurz", "předpověď počasí", "jaké je dnes počasí"
    )
    if any(k in p for k in explicit_online):
        logging.info("Search Intent Router: Explicitní online klíčové slovo detekováno -> ONLINE.")
        return True

    # Běžné konverzační fráze a jednoduchá matematika nepotřebují internet
    if p in ("ahoj", "dobrý den", "čau", "zdravím", "nazdar", "díky", "děkuji", "děkuju", "jak se máš"):
        logging.info("Search Intent Router: Běžná konverzační fráze -> OFFLINE.")
        return False

    # 2. Blesková klasifikace pomocí LLM (max 6 tokenů, greedy decoding)
    messages = [
        {"role": "system", "content": SEARCH_INTENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Dotaz: {prompt}\nRozhodnutí:"}
    ]

    try:
        resp = llm.create_chat_completion(
            messages=messages,
            max_tokens=6,
            temperature=0.0,
            stream=False
        )
        decision = resp["choices"][0]["message"].get("content", "").strip().upper()
        is_online = "ONLINE" in decision
        logging.info(
            "Search Intent Router: dotaz='%s' -> vyhodnocení=%s (raw='%s')",
            prompt[:60], "ONLINE" if is_online else "OFFLINE", decision
        )
        return is_online
    except Exception as exc:
        logging.warning("Search Intent Router selhal při klasifikaci: %s. Výchozí: ONLINE", exc)
        return True


def generate_search_queries(
    llm: Llama,
    user_prompt: str,
    chat_history: list | None = None,
    max_queries: int = 3
) -> list[str]:
    """
    Využije LLM model k vygenerování 2-3 optimalizovaných vyhledávacích frází
    pro internetový vyhledávač na základě uživatelského dotazu a historie.
    """
    clean_p = user_prompt.strip()
    if not clean_p:
        return []

    context_prefix = ""
    prev_user_text = ""
    if chat_history and len(clean_p.split()) <= 6:
        for prev in reversed(chat_history):
            if prev.get("role") == "user":
                prev_user_text = str(prev.get("content", "")).strip()[:80]
                if prev_user_text:
                    context_prefix = f"Předchozí kontext konverzace: {prev_user_text}\n"
                break

    expansion_prompt = (
        "Jsi expert na internetové rešerše. Tvým úkolem je na základě uživatelského dotazu "
        "vytvořit 2 až 3 různé, vysoce přesné a stručné vyhledávací fráze pro webový vyhledávač.\n"
        "Pravidla:\n"
        "- Fráze musí jít přímo k jádru věci a používat konkrétní klíčová slova bez zbytečných spojek a otázek.\n"
        "- Vrať VÝHRADNĚ 2 až 3 fráze, každou na samostatném novém řádku.\n"
        "- Nepoužívej uvozovky, číslování (1., 2.), ani odrážky."
    )

    messages = [
        {"role": "system", "content": expansion_prompt},
        {"role": "user", "content": f"{context_prefix}Uživatelský dotaz: {clean_p}"}
    ]

    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=70,
            temperature=0.2,
            stream=False
        )
        raw_text = response["choices"][0]["message"].get("content", "")
        queries = []
        for line in raw_text.strip().splitlines():
            line_clean = line.strip().lstrip("0123456789.-*• \t").strip("\"'` ")
            if len(line_clean) > 3 and line_clean.lower() not in [q.lower() for q in queries]:
                queries.append(line_clean)

        if len(queries) >= 2:
            return queries[:max_queries]
    except Exception as exc:
        logging.warning("Generování vyhledávacích frází selhalo: %s", exc)

    # Fallback, pokud model vrátil méně než 2 fráze
    fallback = [clean_p.rstrip(".?!")]
    if prev_user_text:
        combined = f"{prev_user_text} {clean_p}".rstrip(".?!")
        fallback.append(combined[:80])
    return fallback


def generate_response(
    llm: Llama,
    prompt: str,
    config: dict,
    callback_on_token=None,
    stop_event=None,
    chat_history: list = None,
    status_callback=None,
    **kwargs
):
    """
    Generuje odpověď přes Chat API modelu a vrací (yield) text po ucelených větách / logických úsecích.
    Zároveň průběžně volá callback_on_token pro okamžité vykreslování jednotlivých tokenů v GUI.
    """
    math_result = _try_evaluate_math(prompt)
    if math_result:
        if callback_on_token:
            callback_on_token(math_result)
        yield math_result
        return

    # Detekce a zpracování příkazu pro Blender
    if is_blender_command(prompt, config):
        for chunk in handle_blender_command(
            llm,
            prompt,
            config,
            callback_on_token=callback_on_token,
            stop_event=stop_event,
            status_callback=status_callback,
        ):
            yield chunk
        return

    try:
        llama_config = config.get("llama", {})
        system_prompt = llama_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
        preset_name = llama_config.get("analytical_preset", DEFAULT_ANALYTICAL_PRESET)

        # 1. Zkusíme načíst staticky zvolenou metodiku (pokud není Auto či Vypnuto)
        analytical_prompt = None
        if preset_name and preset_name not in ("⚡ Auto (Doporučit)", "Vypnuto (Standardní chat)"):
            try:
                analytical_prompt = load_analytical_prompt(preset_name)
            except Exception as exc:
                logging.error("Analytickou metodiku se nepodařilo použít: %s", exc)
                analytical_prompt = None

        # 2. Automatické rozpoznání hlubokého analytického režimu z dotazu uživatele
        auto_requested = (preset_name == "⚡ Auto (Doporučit)")
        detected_mode = detect_analytical_mode(
            prompt,
            llm=llm,
            allow_llm_classifier=auto_requested,
        )

        if detected_mode and (auto_requested or not analytical_prompt or preset_name == "Vypnuto (Standardní chat)"):
            try:
                detected_prompt = load_analytical_prompt(detected_mode)
                if detected_prompt:
                    analytical_prompt = detected_prompt
                    preset_name = detected_mode
                    mode_clean = detected_mode.split("(")[0].strip()
                    logging.info("Dynamicky aktivována analytická metodika: %s", detected_mode)
                    if status_callback:
                        status_callback(f"● Aktivována metodika: {mode_clean}…")
            except Exception as exc:
                logging.error("Chyba při načítání detekované analytické metodiky: %s", exc)

        if analytical_prompt:
            system_prompt = analytical_prompt

        user_content = prompt
        web_search_executed = False

        if llama_config.get("online_mode"):
            try:
                # Bleskový Search Intent Router vyhodnotí, zda je internet skutečně potřeba
                needs_online = classify_search_intent(llm, prompt, chat_history=chat_history)

                if needs_online:
                    from web_search import search_web_multi_source

                    if status_callback:
                        status_callback("● Analyzuji dotaz a navrhuji vyhledávací fráze…")

                    # 1. Vygenerovat 2-3 optimalizované fráze pro vyhledávač
                    search_queries = generate_search_queries(
                        llm,
                        prompt,
                        chat_history=chat_history,
                        max_queries=3
                    )
                    logging.info("Multi-Source RAG fráze: %s", search_queries)

                    if status_callback:
                        queries_preview = ", ".join(f"„{q}“" for q in search_queries[:2])
                        status_callback(f"● Prohledávám web a stahuji zdroje ({queries_preview})…")

                    # 2. Asynchronně vyhledat a stáhnout top 3 relevantní zdroje přes aiohttp + trafilatura
                    web_context = search_web_multi_source(
                        search_queries,
                        max_sources=3,
                        max_total_chars=3600
                    )

                    if status_callback:
                        status_callback("● Syntetizuji odpověď z více webových zdrojů…")

                    user_content = f"{web_context}\n\nDOTAZ UŽIVATELE K ZPRACOVÁNÍ:\n{prompt}"
                    web_search_executed = True
                else:
                    logging.info("Search Intent Router: dotaz nevyžaduje internet, odpovídám přímo z lokálních vah.")
            except Exception:
                logging.exception("Multi-Source online kontext se nepodařilo načíst.")

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

        if web_search_executed:
            multi_rag_rules = (
                "\n\nPRAVIDLA PRO MULTI-SOURCE SYNTÉZU:\n"
                "- Odpověď musí komplexně syntetizovat fakta ze všech poskytnutých webových zdrojů do uceleného a srozumitelného textu.\n"
                "- Pokud se informace ve zdrojích doplňují nebo liší, popiš souvislosti věcně a přesně.\n"
                "- Na ÚPLNÝ KONEC své odpovědi VŽDY přidej sekci '### Použité zdroje:' s číslovaným seznamem klikatelných odkazů ve formátu [Titulek](URL)."
            )
            system_prompt = f"{system_prompt}{multi_rag_rules}"

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

        sentence_buffer = ""
        for chunk in stream:
            if stop_event and stop_event.is_set():
                logging.info("Generování přerušeno uživatelem (Stop).")
                break
            delta = chunk["choices"][0].get("delta", {})
            text_piece = delta.get("content") or ""
            if text_piece:
                if callback_on_token:
                    callback_on_token(text_piece)
                sentence_buffer += text_piece
                ready_chunks, sentence_buffer = extract_sentence_chunks(sentence_buffer, is_final=False)
                for ready_chunk in ready_chunks:
                    yield ready_chunk

        # Vyprázdnění zbývajícího bufferu po skončení inference
        final_chunks, _ = extract_sentence_chunks(sentence_buffer, is_final=True)
        for ready_chunk in final_chunks:
            yield ready_chunk

    except Exception as exc:
        logging.error("Chyba při generování: %s", exc)
        err_msg = f"Omlouvám se, došlo k chybě: {exc}"
        if callback_on_token:
            callback_on_token(err_msg)
        yield err_msg


def generate_response_text(llm: Llama, prompt: str, config: dict, **kwargs) -> str:
    """Pomocná funkce, která vyčerpá stream a vrátí celou odpověď jako jeden řetězec."""
    return " ".join(generate_response(llm, prompt, config, **kwargs)).strip()

