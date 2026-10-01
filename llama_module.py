import json
import logging
import os
import re
from pathlib import Path
from typing import Any
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


def is_blender_inspection_query(prompt: str, config: dict | None = None) -> bool:
    """
    Detekuje, zda uživatel žádá o vizuální kontrolu, analýzu či telemetrii 3D scény / viewportu v Blenderu.
    Např.: „podívej se na scénu“, „zkontroluj co je ve viewportu“, „co vidíš ve scéně“, „jak vypadá scéna v blenderu“.
    """
    if config and not config.get("blender", {}).get("enabled", True):
        return False

    p = prompt.strip().lower()

    # Přímé technické výrazy
    direct_terms = (
        "inspect scene", "viewport snapshot", "inspekce scény", "inspekce viewportu",
        "snímek viewportu", "screenshot viewportu", "render viewportu", "viewport render"
    )
    if any(t in p for t in direct_terms):
        return True

    # Cílová doména (musí se týkat scény / viewportu / blenderu)
    domain_terms = ("scén", "viewport", "3d pohled", "3d scén", "blender")
    has_domain = any(d in p for d in domain_terms)
    if not has_domain:
        return False

    # Vizuální / inspekční dotazy
    inspection_actions = (
        "podívej se", "koukni se", "mrkni se", "zkontroluj", "prohlédni",
        "co vidíš", "co je na", "co je ve", "co máme ve", "co máme na",
        "jak vypadá", "jaký je stav", "stav scény", "zhodnoť", "analyzuj",
        "ukaž", "popiš"
    )
    has_action = any(act in p for act in inspection_actions)

    if has_action:
        # Odfiltrování obecných otázek nesouvisejících se stavem aktuální 3D scény
        generic_non_scene = (
            "kdo vytvořil", "kdy vyšel", "novinky ve verzi", "historie", "počasí", "jak stáhnout"
        )
        if any(ign in p for ign in generic_non_scene):
            return False
        return True

    return False


def format_scene_metrics_for_prompt(metrics: dict, screenshot_path: str = "") -> str:
    """
    Zformátuje telemetrii a metriky 3D scény z Blenderu do přehledného strukturovaného textu pro LLM prompt.
    """
    total_objects = metrics.get("total_objects", 0)
    mode = metrics.get("mode", "OBJECT")
    scene_name = metrics.get("scene_name", "Scene")
    engine = metrics.get("render_engine", "EEVEE")

    lines = [
        "=== TELEMETRIE A METRIKY 3D SCÉNY BLENDERU ===",
        f"Název scény: {scene_name}",
        f"Režim editoru: {mode}",
        f"Renderovací engine: {engine}",
        f"Celkový počet objektů ve scéně: {total_objects}",
    ]

    if screenshot_path:
        lines.append(f"Cesta ke snímku 3D viewportu: {screenshot_path}")

    # Aktivní objekt
    active = metrics.get("active_object")
    if active:
        act_line = (
            f"Aktivní objekt: '{active.get('name')}' (typ: {active.get('type')}, "
            f"pozice: {active.get('location')}, rotace: {active.get('rotation_euler')}, "
            f"měřítko: {active.get('scale')}"
        )
        if "vertices" in active:
            act_line += f", vrcholy: {active.get('vertices')}, polygony: {active.get('polygons')}"
        act_line += ")"
        lines.append(act_line)
    else:
        lines.append("Aktivní objekt: Žádný vybraný aktivní objekt.")

    # Vybrané objekty
    selected = metrics.get("selected_objects", [])
    lines.append(f"Počet vybraných objektů ({len(selected)}):")
    if selected:
        for obj in selected:
            info = (
                f"  - '{obj.get('name')}' [{obj.get('type')}]: "
                f"pozice={obj.get('location')}, rotace={obj.get('rotation_euler')}, měřítko={obj.get('scale')}"
            )
            if "vertices" in obj:
                info += f", {obj.get('vertices')} vrcholů, {obj.get('polygons')} polygonů"
            if obj.get("materials"):
                info += f", materiály: {', '.join(obj.get('materials'))}"
            lines.append(info)
    else:
        lines.append("  - (Žádný objekt není označen/vybrán)")

    # Světla
    lights = metrics.get("lights", [])
    lines.append(f"Světla ve scéně ({len(lights)}):")
    if lights:
        for light in lights:
            lines.append(
                f"  - Světlo '{light.get('name')}' [{light.get('light_type')}]: "
                f"výkon={light.get('energy')} W, pozice={light.get('location')}"
            )
    else:
        lines.append("  - ⚠️ Žádná světla nebyla nalezena (scéna může být tmavá).")

    # Kamery
    cameras = metrics.get("cameras", [])
    lines.append(f"Kamery ve scéně ({len(cameras)}):")
    if cameras:
        for cam in cameras:
            active_marker = " [HLAVNÍ KAMERA SCÉNY]" if cam.get("is_active_scene_camera") else ""
            lines.append(
                f"  - Kamera '{cam.get('name')}'{active_marker}: "
                f"ohnisko={cam.get('lens_mm')} mm, pozice={cam.get('location')}"
            )
    else:
        lines.append("  - ⚠️ Ve scéně chybí jakákoliv kamera.")

    # Přehled ostatních objektů
    all_objs = metrics.get("all_objects_summary", [])
    other_objs = [o for o in all_objs if o.get("type") not in ("LIGHT", "CAMERA")]
    if other_objs:
        lines.append(f"Ostatní objekty/geometrie (celkem {len(other_objs)}):")
        for o in other_objs[:15]:
            vis = "viditelný" if o.get("visible", True) else "skrytý"
            lines.append(f"  - '{o.get('name')}' ({o.get('type')}, {vis})")
        if len(other_objs) > 15:
            lines.append(f"  - ... a dalších {len(other_objs) - 15} objektů")

    return "\n".join(lines)


def handle_blender_inspection(
    llm: Llama,
    prompt: str,
    config: dict,
    chat_history: list | None = None,
    callback_on_token=None,
    stop_event=None,
    status_callback=None,
):
    """
    Provede multimodální inspekci 3D scény v Blenderu:
    1. Přes blender_connector odešle požadavek na inspekci scény a pořízení snímku viewportu.
    2. Předá získané telemetrické metriky do expertního promptu pro LLM.
    3. Zobrazí snímek a telemetrii v GUI a streamuje slovní komentář k aktuálnímu stavu scény.
    """
    from blender_connector import request_scene_inspection, is_blender_available

    blender_cfg = config.get("blender", {})
    host = blender_cfg.get("host", "127.0.0.1")
    port = int(blender_cfg.get("port", 9876))
    output_path = blender_cfg.get("viewport_snapshot_path", "/tmp/blender_viewport.png")

    if status_callback:
        status_callback("● Připojuji se k Blenderu pro inspekci scény…")

    if not is_blender_available(host, port):
        warn_msg = (
            f"\n\n⚠️ **Blender není připojen na portu {port}.**\n\n"
            f"Spusťte prosím v Blenderu v Text Editoru skript `blender_receiver.py` (Run Script / Alt+P).\n\n"
        )
        tts_alert = f"Blender není připojen na portu {port}. Spusťte prosím v Blenderu přijímací skript."
        if callback_on_token:
            callback_on_token(warn_msg)
        yield tts_alert
        return

    if status_callback:
        status_callback("● Pořizuji snímek viewportu a načítám data scény…")

    try:
        res = request_scene_inspection(host=host, port=port, output_path=output_path, timeout=12.0)
    except Exception as e:
        res = {"status": "error", "error": str(e)}

    if res.get("status") != "success":
        err_msg = res.get("error") or res.get("message", "Neznámá chyba při komunikaci s Blenderem.")
        fail_ui = f"\n\n❌ **Inspekce 3D scény v Blenderu selhala:** `{err_msg}`\n"
        if callback_on_token:
            callback_on_token(fail_ui)
        yield "Při inspekci scény v Blenderu došlo k chybě."
        return

    metrics = res.get("scene_metrics", {})
    screenshot_path = res.get("screenshot_path", output_path)

    total_objs = metrics.get("total_objects", 0)
    sel_count = metrics.get("selected_count", 0)
    lights_count = len(metrics.get("lights", []))
    cams_count = len(metrics.get("cameras", []))
    mode = metrics.get("mode", "OBJECT")
    engine = metrics.get("render_engine", "EEVEE")

    # Informační blok a náhled v GUI chatu
    ui_header = (
        f"\n\n📸 **3D Viewport Snapshot:**\n"
        f"![Viewport Snapshot]({screenshot_path})\n\n"
        f"📊 **Telemetrie scény:** Celkem objektů: **{total_objs}** | "
        f"Vybráno: **{sel_count}** | Světla: **{lights_count}** | Kamery: **{cams_count}** | "
        f"Režim: **{mode}** | Engine: **{engine}**\n\n"
        f"---\n\n"
    )
    if callback_on_token:
        callback_on_token(ui_header)

    telemetry_text = format_scene_metrics_for_prompt(metrics, screenshot_path)

    system_prompt = (
        "Jsi špičkový 3D grafik, technický režisér a expert na Blender 3D.\n"
        "Uživatel tě požádal o vizuální kontrolu, telemetrii a zhodnocení aktuálního stavu 3D scény ve viewportu.\n"
        "Zde jsou přesná naměřená data přímo z běžící instance Blenderu:\n\n"
        f"{telemetry_text}\n\n"
        "PRAVIDLA PRO TVOJI ODPOVĚĎ:\n"
        "1. Odpověz přirozenou, věcnou a plynulou češtinou přímo vhodnou pro hlasový výstup (TTS) i čtení v chatu.\n"
        "2. Stručně a jasně popiš, co se na scéně nachází: jaké objekty zde jsou, který je vybraný/aktivní, jejich pozici a měřítko.\n"
        "3. Zhodnoť osvětlení (přítomnost a typ světel) a zda scéna disponuje aktivní kamerou pro render.\n"
        "4. Pokud vidíš technický problém (např. neaplikované měřítko/scale jiné než 1.0, chybějící světlo, neaktivní kamera, vysoký počet polygonů), konstruktivně na něj upozorni.\n"
        "5. Přímo zodpověz konkrétní otázku uživatele."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    if status_callback:
        status_callback("● Analyzuji stav 3D scény…")

    try:
        stream = llm.create_chat_completion(
            messages=messages,
            max_tokens=650,
            temperature=0.3,
            stream=True
        )

        sentence_buffer = ""
        for chunk in stream:
            if stop_event and stop_event.is_set():
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

        final_chunks, _ = extract_sentence_chunks(sentence_buffer, is_final=True)
        for ready_chunk in final_chunks:
            yield ready_chunk

        if status_callback:
            status_callback("● ✅ Inspekce 3D scény dokončena")

    except Exception as exc:
        logging.exception("Chyba při generování komentáře k inspekci scény: %s", exc)
        err = f"Chyba při analýze scény: {exc}"
        if callback_on_token:
            callback_on_token(f"\n{err}\n")
        yield err


def is_blender_command(prompt: str, config: dict | None = None) -> bool:
    """
    Detekuje, zda uživatelský pokyn představuje automatizační příkaz pro Blender 3D.
    Rozlišuje obecné otázky (např. "co je nového v Blenderu") od akčních skriptovacích příkazů.
    """
    if config and not config.get("blender", {}).get("enabled", True):
        return False

    if is_blender_inspection_query(prompt, config):
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
    memory_context: str | None = None,
):
    """
    Vygeneruje Python kód pro Blender (bpy) na základě uživatelského pokynu
    a odešle ho přes lokální TCP socket do běžící instance Blenderu.
    Obsahuje Self-Healing Blender Loop – při chybě (Exception) zachytí traceback
    a nechá LLM kód automaticky opravit (až 2 pokusy o opravu).
    Využívá případnou dlouhodobou sémantickou paměť pro návaznost na minulý kód.
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

        blender_sys = BLENDER_SYSTEM_PROMPT
        if memory_context:
            blender_sys = f"{blender_sys}\n\n{memory_context}"

        messages = [
            {"role": "system", "content": blender_sys},
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


# ==============================================================================
# NATIVNÍ FUNCTION CALLING & JSON TOOL-USE ARCHITECTURE
# ==============================================================================

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Živé online vyhledávání na internetu pro aktuální zprávy, čerstvé události, release notes nebo ověření faktů v reálném čase přes DuckDuckGo a Multi-Source RAG.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optimalizovaný vyhledávací dotaz pro internetový vyhledávač.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_local_rag",
            "description": "Sémantické vyhledávání v lokálně nahraných a zaindexovaných dokumentech (PDF, DOCX, zdrojové kódy, texty) pomocí FAISS vektorové databáze.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Sémantický vyhledávací dotaz pro vyhledání relevantních úseků v dokumentech.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_memory_rag",
            "description": "Prohledávání dlouhodobé sémantické paměti minulých rozhovorů s uživatelem (dřívější dohody, parametry, preference, minulé skripty).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Sémantický dotaz na historické informace nebo preference z minulých konverzací.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_blender_code",
            "description": "Spuštění Python skriptu (bpy) v 3D modelovacím programu Blender přes lokální TCP socket. Použij při požadavcích na vytváření, manipulaci, úpravy materiálů, mazání či renderování 3D objektů.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Kompletní, syntakticky správný spustitelný Python kód využívající modul bpy.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_blender_scene",
            "description": "Získání telemetrie o aktuální 3D scéně v Blenderu (počet objektů, vybrané objekty, kamery, světla, transformační data) a pořízení screenshotu 3D viewportu.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mesh_doctor_audit",
            "description": (
                "Audit topologie aktivního síťového objektu (MESH) v Blenderu pomocí bmesh. "
                "Spočítá počet vrcholů, hran a polygonů, detekuje non-manifold hrany, volné prvky "
                "(loose vertices/edges), díry (boundary edges), n-gony a potenciálně převrácené normály. "
                "Použij při dotazech jako 'zkontroluj síť', 'je model printovatelný', 'analýza topologie', "
                "'je model watertight' nebo 'zkontroluj geometrii'."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mesh_doctor_repair",
            "description": (
                "Automatická oprava topologie aktivního síťového objektu (MESH) v Blenderu. "
                "Provede: (1) Merge by distance — sloučí duplicitní vrcholy, "
                "(2) Delete loose geometry — odstraní volné vrcholy a hrany, "
                "(3) Recalculate Normals Outside — přepočítá normály směrem ven. "
                "Použij při požadavcích jako 'oprav síť', 'vyčisti mesh', 'přepočítej normály', "
                "'připrav model na 3D tisk' nebo 'oprav non-manifold chyby'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "merge_distance": {
                        "type": "number",
                        "description": (
                            "Práh pro sloučení duplicitních vrcholů v metrech. "
                            "Výchozí: 0.0001 (= 0.1 mm). Zvyšte na 0.001 pro hrubší modely, "
                            "snižte na 0.00001 pro přesné inženýrské modely."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product_studio",
            "description": (
                "Automaticky vytvoří kompletní produktové prezentační studio v Blenderu pro aktivní objekt. "
                "Vygeneruje: (1) zakřivené hladké pozadí (backdrop) s Bevel a Solidify modifikátory, "
                "(2) profesionální tříbodové AREA osvětlení (Key light, Fill light, Rim light), "
                "(3) kameru s ohniskovou vzdáleností 85mm namířenou na objekt, "
                "(4) render nastavení 2048×2048px. "
                "Použij při požadavcích jako 'vytvoř produktové studio', 'nastavit prezentační osvětlení', "
                "'připrav scénu pro produktové foto', 'tříbodové svícení', 'key fill rim světla', "
                "'nastavit studio pro render', 'udělej profesionální fotografické pozadí'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "style": {
                        "type": "string",
                        "enum": ["standard", "dramatic", "soft"],
                        "description": (
                            "Osvětlovací styl studia: "
                            "'standard' = neutrální vyvážené bílé studio (výchozí), "
                            "'dramatic' = vysoký kontrast s teplým key lightem a slabým fill lightem, "
                            "'soft' = jemné přesvětlení s velkými difuzními plochami pro beauty produkty."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_procedural_shader",
            "description": (
                "Programově vygeneruje kompletní procedurální materiál (node tree) v Blenderu "
                "a přiřadí jej k aktivnímu MESH objektu. Využívá Principled BSDF propojený "
                "s procedurálními texturami (Noise, Bump, ColorRamp, Mapping, TexCoord). "
                "Podporované typy: 'brushed_metal' (kartáčovaný kov s anizotropií), "
                "'matte_plastic' (matný polymer s mikrotexturou drsnosti), "
                "'rusted_iron' (kov s procedurální mapou koroze a rzi), "
                "'glossy_glass' (čiré optické sklo s lomem IOR 1.52). "
                "Použij při požadavcích jako 'vytvoř materiál', 'udělej shader', 'procedurální kov', "
                "'nastav texturu rzi', 'vytvoř matný plast', 'přidej skleněný materiál', 'vygeneruj shader'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shader_type": {
                        "type": "string",
                        "enum": ["brushed_metal", "matte_plastic", "rusted_iron", "glossy_glass"],
                        "description": (
                            "Typ procedurálního shaderu: "
                            "'brushed_metal' = kartáčovaný hliník/ocel (výchozí), "
                            "'matte_plastic' = matný prémiový polymer, "
                            "'rusted_iron' = zkorodované surové železo s nerovnostmi, "
                            "'glossy_glass' = optické čiré sklo s lomem světla."
                        ),
                    },
                    "material_name": {
                        "type": "string",
                        "description": "Volitelný název nového materiálu v Blenderu (např. 'Titanium_Mat', 'Car_Paint').",
                    },
                },
                "required": [],
            },
        },
    },
]

ALLOWED_TOOL_NAMES = {
    "search_web",
    "query_local_rag",
    "query_memory_rag",
    "execute_blender_code",
    "inspect_blender_scene",
    "mesh_doctor_audit",
    "mesh_doctor_repair",
    "create_product_studio",
    "create_procedural_shader",
}


def build_tool_use_prompt(tools: list[dict[str, Any]] | None = None) -> str:
    """Sestaví systémové instrukce a JSON schémata pro nativní Function Calling."""
    tools = tools or TOOL_SCHEMAS
    schemas_json = json.dumps(tools, ensure_ascii=False, indent=2)
    return (
        "## DOSTUPNÉ NÁSTROJE (TOOLS):\n"
        "Máš k dispozici následující registrované nástroje definované formátem JSON Schema:\n"
        f"```json\n{schemas_json}\n```\n\n"
        "## PRAVIDLA PRO VOLÁNÍ NÁSTROJŮ (TOOL-USE RULES):\n"
        "1. Pokud dotaz uživatele vyžaduje externí informace nebo akci (aktuální zprávy na internetu, "
        "lokální dokumenty, minulou paměť rozhovorů, operace či tvorbu objektů v Blenderu, nebo inspekci 3D scény), "
        "vygeneruj požadavek na volání nástroje ve formátu JSON.\n"
        "2. Formát požadavku na volání nástroje MUSÍ být validní JSON:\n"
        "```json\n"
        "{\n"
        '  "tool": "název_nástroje",\n'
        '  "arguments": {\n'
        '    "parametr": "hodnota"\n'
        "  }\n"
        "}\n"
        "```\n"
        "Nebo standardní OpenAI formát:\n"
        "```json\n"
        "{\n"
        '  "type": "function",\n'
        '  "function": {\n'
        '    "name": "název_nástroje",\n'
        '    "arguments": { ... }\n'
        "  }\n"
        "}\n"
        "```\n"
        "3. Pokud dotaz uživatele NEVYŽADUJE žádný nástroj (běžný rozhovor, obecné vysvětlení teorie, "
        "pozdrav, matematika, psaní textu bez externích dat), odpověz PŘÍMO přirozeným jazykem bez jakéhokoliv JSONu.\n"
        "4. Pokud voláš nástroj, odpověz VÝHRADNĚ JSON objektem pro volání nástroje a nepřidávej žádný zbytečný úvodní ani závěrečný text.\n"
    )


def parse_tool_call(text: str) -> dict[str, Any] | None:
    """
    Bezpečný parser strukturovaných požadavků na volání nástrojů z výstupu LLM.
    Podporuje:
    1. Standardní JSON Schema formát: {"type": "function", "function": {"name": "...", "arguments": {...}}}
    2. Stručný JSON formát: {"tool": "...", "arguments": {...}} nebo {"name": "...", "arguments": {...}}
    3. Markdown bloky: ```json ... ```
    4. XML tagy: <tool_call> ... </tool_call> nebo <function_call> ... </function_call>
    """
    if not text or not text.strip():
        return None

    clean = text.strip()

    # 1. Kontrola XML obalu (<tool_call>...</tool_call> nebo <function_call>...</function_call>)
    xml_match = re.search(r"<(?:tool_call|function_call)>(.*?)</(?:tool_call|function_call)>", clean, re.DOTALL | re.IGNORECASE)
    if xml_match:
        clean = xml_match.group(1).strip()

    # 2. Kontrola Markdown bloku ```json ... ``` nebo ``` ... ```
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL | re.IGNORECASE)
    if md_match:
        clean = md_match.group(1).strip()

    # 3. Vyhledání JSON objektu v textu
    candidates = []
    if clean.startswith("{") and clean.endswith("}"):
        candidates.append(clean)
    else:
        start_idx = clean.find("{")
        while start_idx != -1:
            depth = 0
            in_string = False
            escape = False
            for i in range(start_idx, len(clean)):
                char = clean[i]
                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                else:
                    if char == '"':
                        in_string = True
                    elif char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            candidates.append(clean[start_idx : i + 1])
                            break
            start_idx = clean.find("{", start_idx + 1)

    for cand in candidates:
        try:
            data = json.loads(cand)
            if not isinstance(data, dict):
                continue

            tool_name = None
            tool_args = {}

            # Formát OpenAI: {"type": "function", "function": {"name": ..., "arguments": ...}}
            if data.get("type") == "function" and isinstance(data.get("function"), dict):
                fn = data["function"]
                tool_name = fn.get("name")
                tool_args = fn.get("arguments", {})
            # Formát {"tool": "...", "arguments": ...}
            elif "tool" in data:
                tool_name = data["tool"]
                tool_args = data.get("arguments", {})
            # Formát {"name": "...", "arguments": ...}
            elif "name" in data:
                tool_name = data["name"]
                if "arguments" in data:
                    tool_args = data["arguments"]
                elif "parameters" in data:
                    tool_args = data["parameters"]
                else:
                    tool_args = {k: v for k, v in data.items() if k not in ("name", "type")}
            # Formát {"function": "...", "arguments": ...}
            elif "function" in data and isinstance(data["function"], str):
                tool_name = data["function"]
                tool_args = data.get("arguments", {})

            if not tool_name or not isinstance(tool_name, str):
                continue

            tool_name = tool_name.strip()
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    pass

            if not isinstance(tool_args, dict):
                tool_args = {}

            if tool_name in ALLOWED_TOOL_NAMES:
                return {
                    "name": tool_name,
                    "arguments": tool_args,
                    "raw": cand,
                }
        except Exception:
            continue

    return None


class UnifiedToolDispatcher:
    """
    Centrální dispatcher pro spouštění registrovaných nástrojů:
    - search_web(query)
    - query_local_rag(query)
    - query_memory_rag(query)
    - execute_blender_code(code) (včetně Self-Healing smyčky)
    - inspect_blender_scene()
    - mesh_doctor_audit()
    - mesh_doctor_repair(merge_distance)
    - create_product_studio(style)
    - create_procedural_shader(material_name, shader_type)
    """

    def __init__(
        self,
        llm: Llama | None = None,
        config: dict | None = None,
        document_service=None,
        memory_service=None,
        active_session_id: str | None = None,
        status_callback=None,
        callback_on_token=None,
        stop_event=None,
    ):
        self.llm = llm
        self.config = config or {}
        self.document_service = document_service
        self.memory_service = memory_service
        self.active_session_id = active_session_id
        self.status_callback = status_callback
        self.callback_on_token = callback_on_token
        self.stop_event = stop_event

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Centrální dispatcher pro spuštění vybraného nástroje."""
        tool_name = (tool_name or "").strip()
        arguments = arguments or {}
        logging.info("UnifiedToolDispatcher: Volání nástroje '%s' s argumenty: %s", tool_name, arguments)

        if tool_name == "search_web":
            query = str(arguments.get("query", "")).strip()
            return self._execute_search_web(query)
        elif tool_name == "query_local_rag":
            query = str(arguments.get("query", "")).strip()
            return self._execute_query_local_rag(query)
        elif tool_name == "query_memory_rag":
            query = str(arguments.get("query", "")).strip()
            return self._execute_query_memory_rag(query)
        elif tool_name == "execute_blender_code":
            code = str(arguments.get("code", "")).strip()
            return self._execute_blender_code(code)
        elif tool_name == "inspect_blender_scene":
            return self._execute_inspect_blender_scene()
        elif tool_name == "mesh_doctor_audit":
            return self._execute_mesh_doctor_audit()
        elif tool_name == "mesh_doctor_repair":
            merge_distance = float(arguments.get("merge_distance", 0.0001))
            return self._execute_mesh_doctor_repair(merge_distance=merge_distance)
        elif tool_name == "create_product_studio":
            style = str(arguments.get("style", "standard")).strip()
            if style not in ("standard", "dramatic", "soft"):
                style = "standard"
            return self._execute_create_product_studio(style=style)
        elif tool_name == "create_procedural_shader":
            mat_name = arguments.get("material_name")
            sh_type = str(arguments.get("shader_type", "brushed_metal")).strip()
            return self._execute_create_procedural_shader(material_name=mat_name, shader_type=sh_type)
        else:
            err = f"Neznámý nástroj: '{tool_name}'"
            logging.error(err)
            return {"status": "error", "tool": tool_name, "error": err, "result": err}

    def _execute_search_web(self, query: str) -> dict[str, Any]:
        if self.status_callback:
            self.status_callback(f"● 🌐 Vyhledávám na webu: {query[:35]}…")
        if self.callback_on_token:
            self.callback_on_token(f"\n🌐 *Volám nástroj:* `search_web(query='{query}')`\n")

        from web_search import search_web_multi_source
        try:
            context = search_web_multi_source(query, max_sources=3)
            return {
                "status": "success",
                "tool": "search_web",
                "query": query,
                "result": context,
            }
        except Exception as exc:
            logging.exception("Chyba při volání nástroje search_web: %s", exc)
            return {
                "status": "error",
                "tool": "search_web",
                "query": query,
                "error": str(exc),
                "result": f"Chyba při online vyhledávání: {exc}",
            }

    def _execute_query_local_rag(self, query: str) -> dict[str, Any]:
        if self.status_callback:
            self.status_callback(f"● 📄 Prohledávám lokální dokumenty: {query[:30]}…")
        if self.callback_on_token:
            self.callback_on_token(f"\n📄 *Volám nástroj:* `query_local_rag(query='{query}')`\n")

        if not self.document_service or self.document_service.total_chunks() == 0:
            msg = "V lokálním RAG úložišti nejsou žádné indexované dokumenty."
            return {"status": "error", "tool": "query_local_rag", "query": query, "result": msg}

        try:
            top_k = getattr(self.document_service, "top_k", 3)
            chunks = self.document_service.search(query, top_k=top_k)
            if not chunks:
                res_text = f"Pro dotaz '{query}' nebyly v lokálních dokumentech nalezeny žádné relevantní úseky."
            else:
                res_text = self.document_service.format_chunks_for_prompt(chunks)
            return {
                "status": "success",
                "tool": "query_local_rag",
                "query": query,
                "chunks_count": len(chunks),
                "result": res_text,
            }
        except Exception as exc:
            logging.exception("Chyba při volání query_local_rag: %s", exc)
            return {
                "status": "error",
                "tool": "query_local_rag",
                "query": query,
                "error": str(exc),
                "result": f"Chyba při prohledávání dokumentů: {exc}",
            }

    def _execute_query_memory_rag(self, query: str) -> dict[str, Any]:
        if self.status_callback:
            self.status_callback(f"● 🧠 Prohledávám sémantickou paměť: {query[:30]}…")
        if self.callback_on_token:
            self.callback_on_token(f"\n🧠 *Volám nástroj:* `query_memory_rag(query='{query}')`\n")

        if not self.memory_service or self.memory_service.get_memory_stats()["total_chunks"] == 0:
            msg = "Dlouhodobá sémantická paměť konverzací je prázdná."
            return {"status": "error", "tool": "query_memory_rag", "query": query, "result": msg}

        try:
            rag_cfg = self.config.get("rag", {})
            top_k = int(rag_cfg.get("memory_top_k", 2))
            score_thresh = float(rag_cfg.get("memory_score_threshold", 0.25))
            memories = self.memory_service.search_memory(
                query,
                top_k=top_k,
                score_threshold=score_thresh,
                exclude_session_id=self.active_session_id,
            )
            if not memories:
                res_text = f"Pro dotaz '{query}' nebyly v dlouhodobé paměti nalezeny žádné záznamy."
            else:
                res_text = self.memory_service.format_memory_for_prompt(memories)
            return {
                "status": "success",
                "tool": "query_memory_rag",
                "query": query,
                "memories_count": len(memories),
                "result": res_text,
            }
        except Exception as exc:
            logging.exception("Chyba při volání query_memory_rag: %s", exc)
            return {
                "status": "error",
                "tool": "query_memory_rag",
                "query": query,
                "error": str(exc),
                "result": f"Chyba při prohledávání paměti: {exc}",
            }

    def _execute_blender_code(self, code: str) -> dict[str, Any]:
        from blender_connector import send_code_to_blender, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))
        max_retries = int(blender_cfg.get("max_retries", 2))

        if self.status_callback:
            self.status_callback("● 🎨 Spouštím kód v Blenderu…")
        if self.callback_on_token:
            self.callback_on_token("\n🎨 *Volám nástroj:* `execute_blender_code`\n")

        if not is_blender_available(host, port):
            warn_msg = (
                f"Blender není připojen na portu {port}. "
                "Ujistěte se, že Blender běží a má spuštěný skript blender_receiver.py (Alt+P)."
            )
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn_msg}**\n")
            return {
                "status": "error",
                "tool": "execute_blender_code",
                "error": "BlenderNotConnected",
                "result": warn_msg,
            }

        clean_code = clean_python_code(code)
        current_code = clean_code
        attempt = 0
        last_res = {}

        while attempt <= max_retries:
            if self.stop_event and self.stop_event.is_set():
                return {"status": "error", "tool": "execute_blender_code", "error": "StoppedByUser", "result": "Operace přerušena uživatelem."}

            if attempt > 0:
                if self.status_callback:
                    self.status_callback(f"● 🔄 Blender Self-Healing: Oprava ({attempt}/{max_retries})…")
                if self.callback_on_token:
                    self.callback_on_token(f"\n🔄 *Self-Healing smyčka (pokus {attempt}/{max_retries}): Odesílám opravený kód...*\n")

            res = send_code_to_blender(current_code, host=host, port=port, timeout=10.0)
            last_res = res

            if res.get("status") == "success":
                output_info = res.get("output", "Kód byl úspěšně vykonán.")
                ui_msg = (
                    f"\n\n✅ **Kód v Blenderu byl úspěšně vykonán{' po automatické opravě' if attempt > 0 else ''}:**\n"
                    f"```python\n{current_code}\n```\n"
                )
                if self.callback_on_token:
                    self.callback_on_token(ui_msg)
                if self.status_callback:
                    self.status_callback("● ✅ Kód byl v Blenderu úspěšně vykonán")

                return {
                    "status": "success",
                    "tool": "execute_blender_code",
                    "code": current_code,
                    "output": output_info,
                    "repaired": (attempt > 0),
                    "attempts": attempt + 1,
                    "result": f"Kód byl v Blenderu úspěšně vykonán{' po automatické opravě' if attempt > 0 else ''}. Výstup: {output_info}\nVykonaný kód:\n```python\n{current_code}\n```",
                }

            # Došlo k chybě -> Self-Healing loop
            err_msg = res.get("error") or res.get("message", "Neznámá chyba")
            tb = res.get("traceback", "")
            err_short = err_msg.splitlines()[-1] if "\n" in err_msg else err_msg

            attempt += 1
            if attempt <= max_retries and self.llm is not None:
                if self.status_callback:
                    self.status_callback(f"● ⚠️ Chyba v Blenderu: {err_short[:30]}… Opravuji ({attempt}/{max_retries})")
                if self.callback_on_token:
                    self.callback_on_token(
                        f"\n⚠️ *Chyba při vykonávání v Blenderu:* `{err_short}`\n"
                        f"🛠️ *Aktivuji Self-Healing smyčku (pokus {attempt}/{max_retries})...*\n"
                    )

                repair_prompt = (
                    f"Předchozí Python kód pro Blender selhal s chybou:\n"
                    f"CHYBA: {err_msg}\n"
                    f"TRACEBACK:\n{tb}\n"
                    f"KÓD:\n```python\n{current_code}\n```\n"
                    "Analyzuj chybu (např. neplatný kontext, chybějící objekt nebo atribut) a vygeneruj "
                    "OPRAVENÝ a funkční Python kód pro Blender (bpy). "
                    "Odpověz VÝHRADNĚ čistým Python kódem bez jakýchkoliv komentářů či markdownu."
                )
                repair_messages = [
                    {"role": "system", "content": BLENDER_SYSTEM_PROMPT},
                    {"role": "user", "content": repair_prompt}
                ]
                try:
                    rep_resp = self.llm.create_chat_completion(
                        messages=repair_messages,
                        max_tokens=450,
                        temperature=0.1,
                        stream=False,
                    )
                    rep_raw = rep_resp["choices"][0]["message"].get("content", "")
                    current_code = clean_python_code(rep_raw)
                except Exception as repair_exc:
                    logging.error("Chyba při generování opravného kódu: %s", repair_exc)
                    break
            else:
                break

        final_err = last_res.get("error", "Chyba při spuštění kódu v Blenderu")
        fail_ui = (
            f"\n\n❌ **Při vykonávání v Blenderu došlo k chybě (i po {max_retries} pokusech o opravu):**\n"
            f"**Chyba:** `{final_err}`\n"
        )
        if self.callback_on_token:
            self.callback_on_token(fail_ui)
        if self.status_callback:
            self.status_callback("● ❌ Kód se v Blenderu nepodařilo vykonat")

        return {
            "status": "error",
            "tool": "execute_blender_code",
            "error": final_err,
            "traceback": last_res.get("traceback", ""),
            "attempts": attempt,
            "result": f"Při vykonávání kódu v Blenderu došlo k chybě: {final_err}\nKód:\n```python\n{current_code}\n```",
        }

    def _execute_inspect_blender_scene(self) -> dict[str, Any]:
        from blender_connector import request_scene_inspection, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))
        output_path = blender_cfg.get("viewport_snapshot_path", "/tmp/blender_viewport.png")

        if self.status_callback:
            self.status_callback("● 📸 Pořizuji snímek viewportu a telemetrii scény…")
        if self.callback_on_token:
            self.callback_on_token("\n📸 *Volám nástroj:* `inspect_blender_scene()`\n")

        if not is_blender_available(host, port):
            warn_msg = f"Blender není připojen na portu {port}. Spusťte prosím v Blenderu blender_receiver.py (Alt+P)."
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn_msg}**\n")
            return {"status": "error", "tool": "inspect_blender_scene", "error": "BlenderNotConnected", "result": warn_msg}

        try:
            res = request_scene_inspection(host=host, port=port, output_path=output_path, timeout=12.0)
        except Exception as e:
            res = {"status": "error", "error": str(e)}

        if res.get("status") != "success":
            err_msg = res.get("error") or res.get("message", "Neznámá chyba při komunikaci s Blenderem.")
            if self.callback_on_token:
                self.callback_on_token(f"\n❌ **Inspekce selhala:** `{err_msg}`\n")
            return {"status": "error", "tool": "inspect_blender_scene", "error": err_msg, "result": f"Inspekce scény selhala: {err_msg}"}

        metrics = res.get("scene_metrics", {})
        screenshot_path = res.get("screenshot_path", output_path)

        total_objs = metrics.get("total_objects", 0)
        sel_count = metrics.get("selected_count", 0)
        lights_count = len(metrics.get("lights", []))
        cams_count = len(metrics.get("cameras", []))
        mode = metrics.get("mode", "OBJECT")
        engine = metrics.get("render_engine", "EEVEE")

        ui_header = (
            f"\n\n📸 **3D Viewport Snapshot:**\n"
            f"![Viewport Snapshot]({screenshot_path})\n\n"
            f"📊 **Telemetrie scény:** Celkem objektů: **{total_objs}** | "
            f"Vybráno: **{sel_count}** | Světla: **{lights_count}** | Kamery: **{cams_count}** | "
            f"Režim: **{mode}** | Engine: **{engine}**\n\n"
            f"---\n\n"
        )
        if self.callback_on_token:
            self.callback_on_token(ui_header)

        telemetry_text = format_scene_metrics_for_prompt(metrics, screenshot_path)
        return {
            "status": "success",
            "tool": "inspect_blender_scene",
            "scene_metrics": metrics,
            "screenshot_path": screenshot_path,
            "result": telemetry_text,
        }

    # ------------------------------------------------------------------
    # Mesh Doctor – audit a oprava topologie síťového objektu
    # ------------------------------------------------------------------

    _MESH_DOCTOR_SYSTEM_PROMPT = (
        "Jsi expert na 3D topologii, přípravu modelů pro 3D tisk a analýzu síťové geometrie. "
        "Analyzuješ výsledky bmesh auditu z Blenderu jako zkušený specialista na:\n"
        "  • Manifold topologie (uzavřené povrchy bez non-manifold hran)\n"
        "  • Watertight mesh (hermeticky uzavřená síť vhodná pro 3D tisk, Booleans, remesh)\n"
        "  • N-gony a triangulace (dopad na subdivision, shading a 3D tisk)\n"
        "  • Orientace normál (převrácené normály způsobují tmavé skvrny nebo selhání tisku)\n"
        "  • Volná geometrie (loose verts/edges způsobující artefakty)\n"
        "  • Díry v sítí (boundary edges = nespojené okraje polygonů)\n\n"
        "Při interpretaci výsledků:\n"
        "  1. Vysvětli každou nalezenou chybu jednoduše a srozumitelně\n"
        "  2. Zhodnoť závažnost pro různé use-case (3D tisk, render, herní engine)\n"
        "  3. Navrhni konkrétní opravné kroky v Blenderu (nástroje, klávesové zkratky)\n"
        "  4. Závěrem jasně řekni, zda je model připraven pro 3D tisk nebo ne\n"
    )

    def _execute_mesh_doctor_audit(self) -> dict[str, Any]:
        """Spustí Mesh Doctor AUDIT — bmesh analýzu topologie aktivního mesh objektu."""
        from blender_connector import request_mesh_audit, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))

        if self.status_callback:
            self.status_callback("● 🩺 Spouštím Mesh Doctor AUDIT…")
        if self.callback_on_token:
            self.callback_on_token("\n🩺 *Volám nástroj:* `mesh_doctor_audit()`\n")

        if not is_blender_available(host, port):
            warn = (
                f"Blender není připojen na portu {port}. "
                "Spusťte prosím v Blenderu blender_receiver.py (Alt+P)."
            )
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn}**\n")
            return {"status": "error", "tool": "mesh_doctor_audit", "error": "BlenderNotConnected", "result": warn}

        try:
            res = request_mesh_audit(host=host, port=port, timeout=20.0)
        except Exception as exc:
            res = {"status": "error", "error": str(exc)}

        if res.get("status") != "success":
            err_msg = res.get("error") or res.get("message", "Neznámá chyba Mesh Doctor AUDIT.")
            if self.callback_on_token:
                self.callback_on_token(f"\n❌ **Mesh Doctor AUDIT selhal:** `{err_msg}`\n")
            return {"status": "error", "tool": "mesh_doctor_audit", "error": err_msg, "result": f"Audit selhal: {err_msg}"}

        audit = res.get("audit", {})
        obj_name = audit.get("object_name", "?")
        mesh_name = audit.get("mesh_name", "?")
        verts = audit.get("total_vertices", 0)
        edges = audit.get("total_edges", 0)
        faces = audit.get("total_faces", 0)
        tris = audit.get("triangles", 0)
        ngons = audit.get("ngons", 0)
        non_manifold = audit.get("non_manifold_edges", 0)
        loose_v = audit.get("loose_vertices", 0)
        loose_e = audit.get("loose_edges", 0)
        boundary = audit.get("boundary_edges_holes", 0)
        flipped = audit.get("potentially_flipped_faces", 0)
        watertight = audit.get("is_watertight", False)
        print_ready = audit.get("print_ready", False)

        def _icon(val, ok_val=0, warn_thresh=None):
            """Vrátí emoji ikonu podle hodnoty: 0=✅, >0=⚠️ nebo ❌."""
            if val == ok_val:
                return "✅"
            if warn_thresh is not None and val <= warn_thresh:
                return "⚠️"
            return "❌"

        watertight_icon = "✅" if watertight else "❌"
        print_icon = "✅" if print_ready else "❌"

        # Formátovaný Markdown výstup pro UI
        ui_report = (
            f"\n\n🩺 **Mesh Doctor — Audit: `{obj_name}`** (mesh: `{mesh_name}`)\n\n"
            f"| Metrika | Hodnota |\n"
            f"|---|---|\n"
            f"| Vrcholy | **{verts}** |\n"
            f"| Hrany | **{edges}** |\n"
            f"| Polygony | **{faces}** (trojúhelníky: {tris}, n-gony: {ngons}) |\n"
            f"\n**Topologické problémy:**\n\n"
            f"| Problém | Počet | Stav |\n"
            f"|---|---|---|\n"
            f"| Non-manifold hrany | {non_manifold} | {_icon(non_manifold)} |\n"
            f"| Volné vrcholy | {loose_v} | {_icon(loose_v)} |\n"
            f"| Volné hrany | {loose_e} | {_icon(loose_e)} |\n"
            f"| Díry (boundary edges) | {boundary} | {_icon(boundary)} |\n"
            f"| Potenciálně převrácené normály | {flipped} | {_icon(flipped, warn_thresh=5)} |\n"
            f"| N-gony (>4 strany) | {ngons} | {_icon(ngons, warn_thresh=10)} |\n"
            f"\n**Celkový verdikt:**\n\n"
            f"| | |\n|---|---|\n"
            f"| Watertight (uzavřená síť) | {watertight_icon} {'ANO' if watertight else 'NE'} |\n"
            f"| Připraven pro 3D tisk | {print_icon} {'ANO' if print_ready else 'NE'} |\n\n"
            f"---\n\n"
        )
        if self.callback_on_token:
            self.callback_on_token(ui_report)

        # Textový souhrn pro LLM
        result_text = (
            f"MESH DOCTOR AUDIT — objekt: '{obj_name}' (mesh: '{mesh_name}')\n"
            f"Geometrie: {verts} vrcholů, {edges} hran, {faces} polygonů "
            f"(z toho {tris} trojúhelníků, {ngons} n-gonů).\n"
            f"Topologické problémy:\n"
            f"  - Non-manifold hrany: {non_manifold}\n"
            f"  - Volné vrcholy: {loose_v}\n"
            f"  - Volné hrany: {loose_e}\n"
            f"  - Díry (boundary edges): {boundary}\n"
            f"  - Potenciálně převrácené normály: {flipped}\n"
            f"  - N-gony: {ngons}\n"
            f"Watertight: {'ANO' if watertight else 'NE'} | "
            f"Připraven pro 3D tisk: {'ANO' if print_ready else 'NE'}\n"
        )

        if self.status_callback:
            verdict = "✅ model je watertight" if watertight else f"❌ nalezeny problémy ({non_manifold} non-manifold hran)"
            self.status_callback(f"● 🩺 Mesh Doctor AUDIT dokončen — {verdict}")

        return {
            "status": "success",
            "tool": "mesh_doctor_audit",
            "audit": audit,
            "result": result_text,
            "_expert_system_prompt": self._MESH_DOCTOR_SYSTEM_PROMPT,
        }

    def _execute_mesh_doctor_repair(self, merge_distance: float = 0.0001) -> dict[str, Any]:
        """Spustí Mesh Doctor REPAIR — automatickou opravu topologie aktivního mesh objektu."""
        from blender_connector import request_mesh_repair, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))

        if self.status_callback:
            self.status_callback(f"● 🔧 Spouštím Mesh Doctor REPAIR (merge_distance={merge_distance} m)…")
        if self.callback_on_token:
            self.callback_on_token(
                f"\n🔧 *Volám nástroj:* `mesh_doctor_repair(merge_distance={merge_distance})`\n"
            )

        if not is_blender_available(host, port):
            warn = (
                f"Blender není připojen na portu {port}. "
                "Spusťte prosím v Blenderu blender_receiver.py (Alt+P)."
            )
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn}**\n")
            return {"status": "error", "tool": "mesh_doctor_repair", "error": "BlenderNotConnected", "result": warn}

        try:
            res = request_mesh_repair(host=host, port=port, merge_distance=merge_distance, timeout=25.0)
        except Exception as exc:
            res = {"status": "error", "error": str(exc)}

        if res.get("status") != "success":
            err_msg = res.get("error") or res.get("message", "Neznámá chyba Mesh Doctor REPAIR.")
            if self.callback_on_token:
                self.callback_on_token(f"\n❌ **Mesh Doctor REPAIR selhal:** `{err_msg}`\n")
            return {"status": "error", "tool": "mesh_doctor_repair", "error": err_msg, "result": f"Oprava selhala: {err_msg}"}

        repairs = res.get("repairs_applied", [])
        stats = res.get("post_repair_stats", {})
        obj_name = stats.get("object_name", "?")
        verts = stats.get("total_vertices", 0)
        edges = stats.get("total_edges", 0)
        faces = stats.get("total_faces", 0)
        non_manifold = stats.get("non_manifold_edges", 0)
        loose_v = stats.get("loose_vertices", 0)
        loose_e = stats.get("loose_edges", 0)
        boundary = stats.get("boundary_edges_holes", 0)
        watertight = stats.get("is_watertight", False)
        print_ready = stats.get("print_ready", False)

        repairs_readable = {
            "merge_by_distance": f"Merge by distance (práh: {merge_distance} m)",
            "delete_loose_geometry": "Smazat volnou geometrii",
            "recalculate_normals_outside": "Přepočítat normály směrem ven",
        }
        repairs_list = "\n".join(
            f"  ✅ {repairs_readable.get(r, r)}" for r in repairs
        )

        watertight_icon = "✅" if watertight else "⚠️"
        print_icon = "✅" if print_ready else "⚠️"

        ui_report = (
            f"\n\n🔧 **Mesh Doctor — Oprava dokončena: `{obj_name}`**\n\n"
            f"**Provedené opravy:**\n{repairs_list}\n\n"
            f"**Stav sítě po opravě:**\n\n"
            f"| Metrika | Hodnota |\n|---|---|\n"
            f"| Vrcholy | **{verts}** |\n"
            f"| Hrany | **{edges}** |\n"
            f"| Polygony | **{faces}** |\n"
            f"| Non-manifold hrany | **{non_manifold}** |\n"
            f"| Volné vrcholy | **{loose_v}** |\n"
            f"| Volné hrany | **{loose_e}** |\n"
            f"| Díry (boundary edges) | **{boundary}** |\n"
            f"| Watertight | {watertight_icon} {'ANO' if watertight else 'STÁLE NE'} |\n"
            f"| Připraven pro 3D tisk | {print_icon} {'ANO' if print_ready else 'STÁLE NE'} |\n\n"
            f"---\n\n"
        )
        if self.callback_on_token:
            self.callback_on_token(ui_report)

        result_text = (
            f"MESH DOCTOR REPAIR dokončen — objekt: '{obj_name}'\n"
            f"Provedené opravy: {', '.join(repairs)}\n"
            f"Stav po opravě: {verts} vrcholů, {edges} hran, {faces} polygonů.\n"
            f"Non-manifold: {non_manifold} | Volné vrcholy: {loose_v} | Volné hrany: {loose_e} | "
            f"Díry: {boundary}\n"
            f"Watertight: {'ANO' if watertight else 'NE'} | "
            f"Připraven pro 3D tisk: {'ANO' if print_ready else 'NE'}\n"
        )

        if self.status_callback:
            verdict = "✅ model je nyní watertight" if watertight else "⚠️ zbývají neopravitelné problémy"
            self.status_callback(f"● 🔧 Mesh Doctor REPAIR dokončen — {verdict}")

        return {
            "status": "success",
            "tool": "mesh_doctor_repair",
            "repairs_applied": repairs,
            "post_repair_stats": stats,
            "result": result_text,
            "_expert_system_prompt": self._MESH_DOCTOR_SYSTEM_PROMPT,
        }

    # ------------------------------------------------------------------
    # Product Viz Studio Automator – produktové prezentační studio
    # ------------------------------------------------------------------

    _PRODUCT_STUDIO_SYSTEM_PROMPT = (
        "Jsi profesionální produktový fotorežisér a lighting designer specializovaný na 3D vizualizaci "
        "a CGI reklamu. Analyzuješ a komentuj vytvořené studio nastavení z pohledu odborníka na:\n"
        "  • Tříbodové osvětlení (Key light – hlavní zdroj světla a tvar stínu,\n"
        "    Fill light – vyplnění stínů a kontrola kontrastu,\n"
        "    Rim/Back light – oddělení produktu od pozadí a zvýraznění kontury)\n"
        "  • Fotometrie a exponometrické poměry světel (Key:Fill ratio, Rim intensity)\n"
        "  • Barevná teplota světel a její vliv na materiálové odlesky a kolorit produktu\n"
        "  • Kompozice záběru: pravidlo třetin, goldilocks zone ohniskové vzdálenosti (85mm = mírný telephoto)\n"
        "  • Odlesky a spekulární světla na lesklých materiálech (kov, sklo, lakovaný plast)\n"
        "  • Backdrop design: zakřivené studio pozadí eliminuje rohy a vytváří nekonečný horizont\n\n"
        "Při komentáři studia:\n"
        "  1. Popiš roli každého světla a jeho příspěvek k výsledné fotografii\n"
        "  2. Zhodnoť volbu stylu (standard/dramatic/soft) pro daný typ produktu\n"
        "  3. Navrhni případné doladění (výkon, barevná teplota, velikost světla) pro konkrétní materiály\n"
        "  4. Okomentuj kameru a ohniskovou vzdálenost z pohledu produktové fotografie\n"
        "  5. Případně doporuč render engine (Cycles vs EEVEE) a klíčové nastavení\n"
    )

    _STYLE_DESCRIPTIONS = {
        "standard": "Neutrální vyvážené bílé studio — universální pro většinu produktů",
        "dramatic": "Vysoký kontrast s teplým key lightem — ideální pro prémiové produkty (parfémy, šperky, elektronika)",
        "soft": "Jemné přesvětlení s velkými difuzními plochami — ideální pro kosmetiku, food a beauty produkty",
    }

    def _execute_create_product_studio(self, style: str = "standard") -> dict[str, Any]:
        """Spustí Product Viz Studio Automator — vytvoří produktové studio v Blenderu."""
        from blender_connector import request_product_studio, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))
        style_desc = self._STYLE_DESCRIPTIONS.get(style, style)

        if self.status_callback:
            self.status_callback(f"● 🎬 Vytvářím produktové studio (styl: {style})…")
        if self.callback_on_token:
            self.callback_on_token(
                f"\n🎬 *Volám nástroj:* `create_product_studio(style='{style}')`\n"
            )

        if not is_blender_available(host, port):
            warn = (
                f"Blender není připojen na portu {port}. "
                "Spusťte prosím v Blenderu blender_receiver.py (Alt+P)."
            )
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn}**\n")
            return {
                "status": "error",
                "tool": "create_product_studio",
                "error": "BlenderNotConnected",
                "result": warn,
            }

        try:
            res = request_product_studio(host=host, port=port, style=style, timeout=30.0)
        except Exception as exc:
            res = {"status": "error", "error": str(exc)}

        if res.get("status") != "success":
            err_msg = res.get("error") or res.get("message", "Neznámá chyba při vytváření studia.")
            if self.callback_on_token:
                self.callback_on_token(f"\n❌ **Studio Automator selhal:** `{err_msg}`\n")
            return {
                "status": "error",
                "tool": "create_product_studio",
                "error": err_msg,
                "result": f"Vytvoření studia selhalo: {err_msg}",
            }

        studio = res.get("studio", {})
        backdrop = studio.get("backdrop", {})
        lights = studio.get("lights", [])
        camera = studio.get("camera", {})
        scale = studio.get("scale_factor", 1.0)
        target = studio.get("target_object", "?")

        # Najít světla podle role
        key_l   = next((l for l in lights if l.get("role") == "key"), {})
        fill_l  = next((l for l in lights if l.get("role") == "fill"), {})
        rim_l   = next((l for l in lights if l.get("role") == "rim"), {})

        def light_row(light: dict, label: str, icon: str) -> str:
            if not light:
                return f"| {icon} {label} | — | — | — |\n"
            return (
                f"| {icon} **{label}** (`{light.get('name', '?')}`) "
                f"| {light.get('energy', '?')} W "
                f"| {light.get('color_temp', '?')} "
                f"| {light.get('size', '?')} m |\n"
            )

        dims = backdrop.get("dimensions_m", [0, 0, 0])
        mods = " + ".join(backdrop.get("modifiers", []))

        ui_report = (
            f"\n\n🎬 **Product Viz Studio — `{style.upper()}` styl**\n"
            f"*{style_desc}*\n\n"
            f"---\n\n"
            f"**🎨 Pozadí (Backdrop)**\n\n"
            f"| Parametr | Hodnota |\n|---|---|\n"
            f"| Objekt | `{backdrop.get('name', '?')}` |\n"
            f"| Rozměry | {dims[0]:.1f} × {dims[1]:.1f} m |\n"
            f"| Materiál | `{backdrop.get('material', '?')}` (matný bílý 95%) |\n"
            f"| Modifikátory | {mods} |\n\n"
            f"**💡 Tříbodové osvětlení**\n\n"
            f"| Světlo | Výkon | Barevná teplota | Velikost |\n|---|---|---|---|\n"
            + light_row(key_l, "Key Light", "☀️")
            + light_row(fill_l, "Fill Light", "🔵")
            + light_row(rim_l, "Rim Light", "⭐")
            + f"\n**📷 Kamera**\n\n"
            f"| Parametr | Hodnota |\n|---|---|\n"
            f"| Objekt | `{camera.get('name', '?')}` |\n"
            f"| Ohnisková vzdálenost | **{camera.get('focal_length_mm', 85)} mm** |\n"
            f"| Rozlišení renderu | {camera.get('resolution', '?')} px |\n"
            f"| Aktivní kamera | {'✅ Ano' if camera.get('is_active_camera') else '❌ Ne'} |\n\n"
            f"**🎯 Cílový objekt:** `{target}` | **Měřítko studia:** {scale:.2f} m\n\n"
            f"---\n\n"
        )
        if self.callback_on_token:
            self.callback_on_token(ui_report)

        # Textový souhrn pro LLM
        result_text = (
            f"PRODUCT VIZ STUDIO vytvořeno — styl: '{style}' ({style_desc})\n"
            f"Cílový objekt: '{target}', měřítko studia: {scale:.2f} m\n\n"
            f"Backdrop:\n"
            f"  - Objekt: '{backdrop.get('name', '?')}', rozměry: {dims[0]:.1f}×{dims[1]:.1f} m\n"
            f"  - Modifikátory: {mods}\n"
            f"  - Materiál: matný bílý (roughness=0.9)\n\n"
            f"Osvětlení:\n"
        )
        for light in lights:
            result_text += (
                f"  - {light.get('role', '?').upper()} ({light.get('name', '?')}): "
                f"{light.get('energy', '?')} W, {light.get('color_temp', '?')}, "
                f"velikost {light.get('size', '?')} m\n"
            )
        result_text += (
            f"\nKamera:\n"
            f"  - '{camera.get('name', '?')}', ohnisková vzdálenost: {camera.get('focal_length_mm', 85)} mm\n"
            f"  - Rozlišení: {camera.get('resolution', '?')} px, aktivní kamera: "
            f"{'ANO' if camera.get('is_active_camera') else 'NE'}\n"
        )

        if self.status_callback:
            self.status_callback(
                f"● ✅ Studio '{style}' vytvořeno — {len(lights)} světla, 85mm kamera"
            )

        return {
            "status": "success",
            "tool": "create_product_studio",
            "studio": studio,
            "result": result_text,
            "_expert_system_prompt": self._PRODUCT_STUDIO_SYSTEM_PROMPT,
        }

    # ------------------------------------------------------------------
    # Procedural Shader & Node Tree Generator – tvorba materiálů
    # ------------------------------------------------------------------

    _PROCEDURAL_SHADER_SYSTEM_PROMPT = (
        "Jsi elitní 3D shading artist, material TD (Technical Director) a expert na PBR materiály a procedurální node tree v Blenderu. "
        "Odborně a detailně komentuješ vygenerovaný procedurální shader z hlediska fyzikálních a optických vlastností:\n"
        "  • PBR workflow a chování světla (Metallic vs Dielectric, Fresnelův jev, IOR, zachování energie)\n"
        "  • Mikrofasetová teorie drsnosti (Roughness, mikrostruktura povrchu, anizotropní směrové kartáčování)\n"
        "  • Procedurální architektura node tree (princip skládání Noise, ColorRamp, Bump a Mapping bez nutnosti UV rozbalení)\n"
        "  • Vrstvení detailů (Bump/Normal výšky, barevné přechody v ColorRamp, vliv škálování v Mapping uzlu)\n"
        "  • Praktické tipy pro osvětlení a doladění (jak vyniknou odlesky v závislosti na světelných zdrojích a jak shader upravit v Shader Editoru)\n\n"
        "Při formulaci odpovědi pro uživatele:\n"
        "  1. Zhodnoť vizuální a materiálové vlastnosti (barva, odlesky, textura) a jeho reálnou analogii\n"
        "  2. Stručně a srozumitelně popiš, jak jednotlivé uzly spolupracují (TexCoord -> Mapping -> Noise -> ColorRamp/Bump -> Principled BSDF)\n"
        "  3. Zmiň klíčové hodnoty (Roughness, Metallic, IOR/Transmission, Bump sílu) a na jaký objekt byl aplikován\n"
        "  4. Nabídni 1-2 praktické tipy pro okamžité doladění v Blenderu (např. posuvník v ColorRamp nebo Scale v Mapping)\n"
    )

    _SHADER_DESCRIPTIONS = {
        "brushed_metal": "Kartáčovaný kov / hliník s anizotropním lineárním vzorem a nízkou drsností",
        "matte_plastic": "Matný prémiový polymer s jemným mikroskopickým šumem v Bump a Roughness",
        "rusted_iron": "Zkorodované železo s procedurální mapou koroze, separovanou drsností a výškovým reliéfem",
        "glossy_glass": "Opticky čisté sklo s lomem světla IOR 1.52, plnou transmisí a mikroskopickým zvlněním",
    }

    def _execute_create_procedural_shader(
        self, material_name: str | None = None, shader_type: str = "brushed_metal"
    ) -> dict[str, Any]:
        """Spustí Procedural Shader Generator — vytvoří procedurální materiál v Blenderu."""
        from blender_connector import request_procedural_shader, is_blender_available

        blender_cfg = self.config.get("blender", {})
        host = blender_cfg.get("host", "127.0.0.1")
        port = int(blender_cfg.get("port", 9876))
        clean_type = (shader_type or "brushed_metal").lower().strip()
        type_desc = self._SHADER_DESCRIPTIONS.get(clean_type, "Procedurální shader")

        if self.status_callback:
            self.status_callback(f"● 🎨 Generuji procedurální materiál '{clean_type}'…")
        if self.callback_on_token:
            name_display = f", name='{material_name}'" if material_name else ""
            self.callback_on_token(
                f"\n🎨 *Volám nástroj:* `create_procedural_shader(shader_type='{clean_type}'{name_display})`\n"
            )

        if not is_blender_available(host, port):
            warn = (
                f"Blender není připojen na portu {port}. "
                "Spusťte prosím v Blenderu blender_receiver.py (Alt+P)."
            )
            if self.callback_on_token:
                self.callback_on_token(f"\n⚠️ **{warn}**\n")
            return {
                "status": "error",
                "tool": "create_procedural_shader",
                "error": "BlenderNotConnected",
                "result": warn,
            }

        try:
            res = request_procedural_shader(
                material_name=material_name,
                shader_type=clean_type,
                host=host,
                port=port,
                timeout=25.0,
            )
        except Exception as exc:
            res = {"status": "error", "error": str(exc)}

        if res.get("status") != "success":
            err_msg = res.get("error") or res.get("message", "Neznámá chyba při vytváření materiálu.")
            if self.callback_on_token:
                self.callback_on_token(f"\n❌ **Procedural Shader Generator selhal:** `{err_msg}`\n")
            return {
                "status": "error",
                "tool": "create_procedural_shader",
                "error": err_msg,
                "result": f"Generování materiálu selhalo: {err_msg}",
            }

        shader_data = res.get("shader", {})
        mat_name = shader_data.get("material_name", material_name or "Procedural_Material")
        assigned_obj = shader_data.get("assigned_to_object")
        nodes_list = shader_data.get("nodes", [])
        node_count = shader_data.get("node_count", len(nodes_list))
        link_count = shader_data.get("link_count", 0)
        key_params = shader_data.get("key_parameters", {})

        # Formátování tabulky uzlů a parametrů pro UI
        node_names_formatted = ", ".join(f"`{n.get('name', '?')}`" for n in nodes_list[:8])
        if len(nodes_list) > 8:
            node_names_formatted += f" a dalších {len(nodes_list) - 8}"

        params_rows = ""
        for k, v in key_params.items():
            if k != "shader_type":
                params_rows += f"| {k.replace('_', ' ').title()} | **{v}** |\n"

        target_display = f"`{assigned_obj}`" if assigned_obj else "*Žádný (materiál vytvořen v knihovně)*"

        ui_report = (
            f"\n\n🎨 **Procedural Shader — `{mat_name}`** (`{clean_type}`)\n"
            f"*{type_desc}*\n\n"
            f"---\n\n"
            f"| Vlastnost | Hodnota |\n|---|---|\n"
            f"| Typ shaderu | `{clean_type}` |\n"
            f"| Přiřazeno k objektu | {target_display} |\n"
            f"| Počet uzlů (Nodes) | **{node_count}** |\n"
            f"| Počet propojení (Links) | **{link_count}** |\n"
            + params_rows +
            f"\n**🧩 Zapojené uzly:** {node_names_formatted}\n\n"
            f"---\n\n"
        )
        if self.callback_on_token:
            self.callback_on_token(ui_report)

        result_text = (
            f"PROCEDURAL SHADER vytvořen — název: '{mat_name}', typ: '{clean_type}' ({type_desc})\n"
            f"Přiřazeno k objektu: {assigned_obj or 'žádný (pouze v datech)'}\n"
            f"Architektura node tree: {node_count} uzlů, {link_count} propojení.\n"
            f"Seznam uzlů: {', '.join(n.get('name', '?') for n in nodes_list)}\n"
            f"Klíčové parametry: {json.dumps(key_params, ensure_ascii=False)}\n"
        )

        if self.status_callback:
            self.status_callback(
                f"● ✅ Shader '{mat_name}' ({clean_type}) vytvořen ({node_count} uzlů)"
            )

        return {
            "status": "success",
            "tool": "create_procedural_shader",
            "shader": shader_data,
            "result": result_text,
            "_expert_system_prompt": self._PROCEDURAL_SHADER_SYSTEM_PROMPT,
        }


def generate_response(
    llm: Llama,
    prompt: str,
    config: dict,
    callback_on_token=None,
    stop_event=None,
    chat_history: list = None,
    status_callback=None,
    document_service=None,
    memory_service=None,
    memory_context: str | None = None,
    active_session_id: str | None = None,
    enable_tools: bool = True,
    **kwargs
):
    """
    Generuje odpověď přes Chat API modelu a vrací (yield) text po ucelených větách / logických úsecích.
    Podporuje Nativní Function Calling (JSON Tool-Use Architecture) s automatickým dispatcherem:
    - search_web(query)
    - query_local_rag(query)
    - query_memory_rag(query)
    - execute_blender_code(code)
    - inspect_blender_scene()
    """
    math_result = _try_evaluate_math(prompt)
    if math_result:
        if callback_on_token:
            callback_on_token(math_result)
        yield math_result
        return

    dispatcher = UnifiedToolDispatcher(
        llm=llm,
        config=config,
        document_service=document_service,
        memory_service=memory_service,
        active_session_id=active_session_id,
        status_callback=status_callback,
        callback_on_token=callback_on_token,
        stop_event=stop_event,
    )

    tools_enabled = enable_tools and config.get("llama", {}).get("function_calling", True)

    # 1. Zpracování analytické metodiky
    llama_config = config.get("llama", {})
    system_prompt = llama_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()
    preset_name = llama_config.get("analytical_preset", DEFAULT_ANALYTICAL_PRESET)

    analytical_prompt = None
    if preset_name and preset_name not in ("⚡ Auto (Doporučit)", "Vypnuto (Standardní chat)"):
        try:
            analytical_prompt = load_analytical_prompt(preset_name)
        except Exception as exc:
            logging.error("Analytickou metodiku se nepodařilo použít: %s", exc)
            analytical_prompt = None

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

    # Dynamické vložení systémového času a data
    from datetime import datetime
    now = datetime.now()
    dny = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
    den_nazev = dny[now.weekday()]
    cas_info = (
        f"\n\n[AKTUÁLNÍ SYSTÉMOVÝ ČAS A DATUM: {den_nazev} {now.day}. {now.month}. {now.year}, {now.strftime('%H:%M')}]\n"
        "PRAVIDLA PRO ČAS A ZPRAVODAJSTVÍ:\n"
        "- Výše uvedený čas je tvůj přesný reálný čas. Podle něj určuj, co je ráno, odpoledne, dnes či včera.\n"
        "- Z webových článků NIKDY nekopíruj zastaralé relativní údaje jako 'před hodinou'. Uváděj přesný čas.\n"
    )
    system_prompt = f"{system_prompt}{cas_info}"

    # Injektování definic nástrojů, pokud jsou nástroje povoleny
    if tools_enabled:
        system_prompt = f"{system_prompt}\n\n{build_tool_use_prompt()}"

    # Předběžná sémantická paměť (pokud je předána zvenčí nebo nástroje nejsou aktivní)
    if memory_context:
        mem_instructions = (
            f"\n\n{memory_context}\n\n"
            "POKYNY PRO HISTORICKOU PAMĚŤ:\n"
            "- Výše uvedené záznamy pocházejí z předchozích rozhovorů s uživatelem v minulosti.\n"
            "- Využij je jako kontext pro zachování kontinuity, domluvených parametrů a preferencí.\n"
        )
        system_prompt = f"{system_prompt}{mem_instructions}"

    # Sestavení zpráv konverzace
    messages = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for turn in chat_history:
            r = "assistant" if turn.get("role") == "assistant" else "user"
            c = turn.get("content") or turn.get("text") or ""
            if c:
                messages.append({"role": r, "content": c})
    messages.append({"role": "user", "content": prompt})

    # Určení maximálního počtu tokenů
    raw_max = llama_config.get('max_tokens', 'auto')
    if str(raw_max).strip().lower() in ('auto', '0', ''):
        max_tokens = 2048 if analytical_prompt else 1536
    else:
        try:
            max_tokens = int(raw_max)
        except ValueError:
            max_tokens = 1536

    temperature = float(llama_config.get("temperature", 0.7))

    try:
        # --- 1. TAH: Detekce volání nástroje vs. přímá odpověď ---
        first_stream = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens if not tools_enabled else min(max_tokens, 750),
            temperature=0.1 if tools_enabled else temperature,
            stream=True,
        )

        first_turn_buffer = ""
        is_tool_candidate = None  # None = nerozhodnuto, True = bufferuji JSON, False = streamuji text
        tool_call_detected = None
        sentence_buffer = ""

        for chunk in first_stream:
            if stop_event and stop_event.is_set():
                return
            delta = chunk["choices"][0].get("delta", {})
            text_piece = delta.get("content") or ""
            if not text_piece:
                continue

            if not tools_enabled:
                if callback_on_token:
                    callback_on_token(text_piece)
                sentence_buffer += text_piece
                ready_chunks, sentence_buffer = extract_sentence_chunks(sentence_buffer, is_final=False)
                for rc in ready_chunks:
                    yield rc
                continue

            # Nástroje jsou zapnuty: analyzujeme úvodní tokeny
            if is_tool_candidate is None:
                first_turn_buffer += text_piece
                stripped = first_turn_buffer.strip()
                if not stripped:
                    continue
                if stripped.startswith(("{", "<", "```", "tool_call", "function_call")):
                    is_tool_candidate = True
                else:
                    is_tool_candidate = False
                    if callback_on_token:
                        callback_on_token(first_turn_buffer)
                    sentence_buffer += first_turn_buffer
                    ready_chunks, sentence_buffer = extract_sentence_chunks(sentence_buffer, is_final=False)
                    for rc in ready_chunks:
                        yield rc
                continue

            if not is_tool_candidate:
                if callback_on_token:
                    callback_on_token(text_piece)
                sentence_buffer += text_piece
                ready_chunks, sentence_buffer = extract_sentence_chunks(sentence_buffer, is_final=False)
                for rc in ready_chunks:
                    yield rc
                continue

            if is_tool_candidate:
                first_turn_buffer += text_piece
                parsed = parse_tool_call(first_turn_buffer)
                if parsed:
                    tool_call_detected = parsed
                    break

        if not is_tool_candidate:
            final_chunks, _ = extract_sentence_chunks(sentence_buffer, is_final=True)
            for rc in final_chunks:
                yield rc
            return

        if not tool_call_detected and first_turn_buffer.strip():
            tool_call_detected = parse_tool_call(first_turn_buffer)

        # Fallback: pokud model nevygeneroval JSON, ale dotaz je zjevný příkaz pro Blender
        if not tool_call_detected and is_blender_command(prompt, config):
            logging.info("Tool-Use fallback: Aktivuji execute_blender_code pro zjevný příkaz Blenderu.")
            tool_call_detected = {"name": "execute_blender_code", "arguments": {"code": first_turn_buffer or prompt}}
        elif not tool_call_detected and is_blender_inspection_query(prompt, config):
            logging.info("Tool-Use fallback: Aktivuji inspect_blender_scene pro zjevný dotaz na viewport.")
            tool_call_detected = {"name": "inspect_blender_scene", "arguments": {}}

        if not tool_call_detected:
            # Buffer neobsahoval validní volání nástroje -> uvolníme ho jako běžný text
            if callback_on_token:
                callback_on_token(first_turn_buffer)
            sentence_buffer += first_turn_buffer
            final_chunks, _ = extract_sentence_chunks(sentence_buffer, is_final=True)
            for rc in final_chunks:
                yield rc
            return

        # --- 2. TAH: Spuštění nástroje přes UnifiedToolDispatcher a syntéza finální odpovědi ---
        tool_name = tool_call_detected["name"]
        tool_args = tool_call_detected["arguments"]
        logging.info("Spouštím detekovaný nástroj: %s (%s)", tool_name, tool_args)

        dispatch_res = dispatcher.dispatch(tool_name, tool_args)
        tool_obs_text = dispatch_res.get("result", "")

        if status_callback:
            status_callback("● Formuluji finální odpověď na základě výsledků…")

        # Pokud nástroj vrátil expertní systémový prompt (např. Mesh Doctor),
        # vložíme ho jako dočasnou instrukci pro Turn 2 syntézu
        expert_sys = dispatch_res.get("_expert_system_prompt")
        if expert_sys:
            messages.append({"role": "system", "content": expert_sys})

        messages.append({
            "role": "assistant",
            "content": json.dumps({"tool": tool_name, "arguments": tool_args}, ensure_ascii=False)
        })
        messages.append({
            "role": "user",
            "content": (
                f"VÝSLEDEK VOLÁNÍ NÁSTROJE '{tool_name}':\n"
                f"{tool_obs_text}\n\n"
                "POKYN: Na základě výše uvedeného výsledku nástroje nyní zformuluj konečnou, "
                "přirozenou, věcnou a plynulou odpověď pro uživatele v češtině (vhodnou pro zobrazení i pro hlasový výstup TTS). "
                "Pokud výsledek obsahuje odkazy na zdroje, uveď je na konci. "
                "Odpověz PŘÍMO bez generování dalšího JSONu."
            )
        })

        second_stream = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        sentence_buffer = ""
        for chunk in second_stream:
            if stop_event and stop_event.is_set():
                break
            delta = chunk["choices"][0].get("delta", {})
            text_piece = delta.get("content") or ""
            if text_piece:
                if callback_on_token:
                    callback_on_token(text_piece)
                sentence_buffer += text_piece
                ready_chunks, sentence_buffer = extract_sentence_chunks(sentence_buffer, is_final=False)
                for rc in ready_chunks:
                    yield rc

        final_chunks, _ = extract_sentence_chunks(sentence_buffer, is_final=True)
        for rc in final_chunks:
            yield rc

    except Exception as exc:
        logging.error("Chyba při generování: %s", exc)
        err_msg = f"Omlouvám se, došlo k chybě: {exc}"
        if callback_on_token:
            callback_on_token(err_msg)
        yield err_msg


def generate_response_text(llm: Llama, prompt: str, config: dict, **kwargs) -> str:
    """Pomocná funkce, která vyčerpá stream a vrátí celou odpověď jako jeden řetězec."""
    return " ".join(generate_response(llm, prompt, config, **kwargs)).strip()

