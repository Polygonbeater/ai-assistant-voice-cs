# 🎙️ Polygon Beater — AI Assistant Voice CS
### *Lokální hlasový AI asistent a 3D technický ředitel pro Blender*

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python)](https://www.python.org/)
[![Blender 4.x+](https://img.shields.io/badge/Blender-4.x%20LTS-orange.svg?logo=blender)](https://www.blender.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vulkan Accelerated](https://img.shields.io/badge/Vulkan-Hardware%20Offload-red.svg?logo=vulkan)](https://www.khronos.org/vulkan/)
[![AST Protected](https://img.shields.io/badge/Security-AST%20Gatekeeper-success.svg)]()
[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-27%2F27%20Passed%20(100%25)-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Polygon Beater** je pokročilý, 100% suverénní lokální hlasový asistent s integrovaným 3D kognitivním jádrem pro přímou procedurální tvorbu, parametrické CAD modelování, inspekci topologie a automatizaci renderovací pipeline v **Blenderu 4.x LTS**.

---

## 🌟 Klíčové přednosti a architektura

```
                          ┌────────────────────────────────────────────────────────┐
                          │            MODERNÍ WEBOVÉ ROZHRANÍ (DARK TECH)         │
                          │  • Streaming SSE Chat   • 3D Viewport & Telemetrie     │
                          │  • 18-Tool Quick Matrix • AI Proofreading (Korektura)  │
                          │  • RAG Knowledge Base   • Inspekce aktivních nástrojů │
                          └───────────────────────────┬────────────────────────────┘
                                                      │ HTTP / SSE / REST API
                                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FASTAPI WEB SERVER BACKEND                                         │
│ • Bezpečnostní Network Shield (Loopback-only ochrana citlivých endpointů, SSRF guard)                    │
│ • Dynamické kontextové načítání nástrojů (redukce tokenů z 22 na 4 nástroje ve standardním chatu)        │
│ • Správa sémantické paměti a lokální RAG báze (FAISS + all-MiniLM-L6-v2)                                 │
└─────────────────────────────┬──────────────────────────────────────────────┬─────────────────────────────┘
                              │                                              │
                              ▼                                              ▼
┌──────────────────────────────────────────────┐ ┌─────────────────────────────────────────────────────────┐
│        HYBRIDNÍ KOGNITIVNÍ MOZEK             │ │             3D WORKSPACE & BLENDER BRIDGE               │
│ • Lokální GGUF inference (Qwen 2.5, GLM-4)   │ │ • Obousměrný TCP Socket (127.0.0.1:9876)                │
│   s Vulkan GPU offloadingem (CPU+GPU)        │ │ • AST Bezpečnostní validátor (Code Sandbox Gatekeeper)  │
│ • Cloud LPU: Groq Cloud (Llama 3.3, Qwen)    │ │ • Self-Healing smyčka při syntaktických chybách         │
│ • Multimodální AI: Google Gemini             │ │ • 18 specializovaných 3D výrobních nástrojů             │
│ • Vlastní OpenAI-kompatibilní API            │ │ • Telemetrie scény, živý snapshot a Mesh Doctor         │
│   (DeepSeek, OpenRouter, Mistral, Ollama)    │ │ • Generování procedurálních shaderů a fotostudia        │
└──────────────────────────────────────────────┘ └─────────────────────────────────────────────────────────┘
```

### 1. 🧠 Hybridní LLM mozek & Univerzální API konektivita
* **Lokální modely (.gguf)**: Plně privátní běh na lokálním hardware přes `llama-cpp-python`. Automatické dynamické skenování složky `./models/`, detekce parametrů a kvantizace s možností přepínání modelu za běhu (hot-reload RAM/VRAM bez restartu serveru).
* **Vulkan GPU akcelerace**: Hybridní rozdělení vrstev (např. 12 vrstev do GPU VRAM a zbytek na CPU), což umožňuje bleskový běh i na dostupných grafických kartách (např. AMD Radeon RX 560 4GB).
* **Rychlé Cloud LPU (Groq Cloud)**: Okamžitá odezva (stovky tokenů za sekundu) s modely *Llama 3.3 70B Versatile* nebo *Qwen 2.5 32B*.
* **Google Gemini & Multimodalita**: Nativní podpora *Gemini 2.0 Flash* a *Gemini 1.5 Pro* pro pokročilé kognitivní a vizuální úlohy.
* **Univerzální vlastní API**: Možnost připojit libovolného OpenAI-kompatibilního poskytovatele (*DeepSeek Chat/Coder*, *OpenRouter*, *Mistral AI*, lokální *Ollama* či *vLLM*).

### 2. 🛡️ Bezpečnostní architektura (AST Gatekeeper & Network Shield)
* **AST (Abstract Syntax Tree) Validátor (`code_validator.py`)**: Veškerý Python/bpy kód vygenerovaný asistentem nebo zadaný v editoru prochází statickou syntaktickou a bezpečnostní analýzou před odesláním do Blenderu.
  * **Whitelist povolených knihoven**: `{"bpy", "bmesh", "mathutils", "math", "random", "colorsys", "json"}`.
  * **Zákaz nebezpečných importů a systémových volání**: Okamžitě blokuje `os`, `sys`, `subprocess`, `shutil`, `socket`, `requests`, `pathlib`, `eval()`, `exec()`, `open()`, `globals()` i pokusy o sandbox escape přes dunder atributy (`__subclasses__`, `__builtins__`).
* **Network Loopback Shield**: Správa konfigurace a testování API klíčů je striktně omezena na lokální loopback rozhraní (`127.0.0.1`, `localhost`, `::1`), čímž je zamezeno jakémukoliv zneužití ze sítě (ochrana proti SSRF a neautorizovanému přenastavení).

### 3. ⚡ Dynamické kontextové načítání nástrojů
* Systém inteligentně analyzuje stav prostředí a aktivní metodiku:
  * Pokud je aktivní profil **Standardní chat** nebo je Blender offline, asistent nepředává do systémového promptu 18 náročných 3D nástrojů, ale pouze obecné nástroje (rešerše, paměť).
  * **Úspora přes 3 000 tokenů na dotaz** dramaticky zrychluje prompt evaluation a generování odpovědi na CPU i GPU.
  * **Inspektor nástrojů**: Uživatel má možnost v záhlaví rozhraní kliknout na odznak nástrojů a libovolný z 22 nástrojů manuálně zapnout či vypnout.

### 4. 🎨 3D Workspace & 18 Blender nástrojů
Kompletní matice nástrojů rozdělená do 6 logických výrobních kategorií:
1. **Geometrie a parametrické CAD modelování**:
   * `generate_parametric_model` – parametrické krabičky, ozubená kola, montážní konzole.
   * `apply_modifier_stack` – optimalizace a sloučení zásobníku modifikátorů.
   * `create_geometry_nodes_bridge` – procedurální uzly pro scatter a panely.
   * `vectorize_image_to_3d` – převod 2D SVG / obrázku na 3D geometrii.
   * `generate_local_ai_mesh` – konceptuální 3D AI rekonstrukce z obrázku.
2. **Audit topologie a příprava pro 3D tisk (Mesh Doctor)**:
   * `mesh_doctor_audit` – detekce non-manifold hran, děr a tloušťky stěn.
   * `mesh_doctor_repair` – automatické zacelení děr a přepočet normál pro slicer.
   * `inspect_blender_scene` – telemetrie scény a pořízení snímku viewportu.
3. **Materiály, UV mapování a textury**:
   * `create_procedural_shader` – procedurální materiály (kov, plast, rez, sklo).
   * `uv_texel_audit` – měření hustoty texelů (px/m).
   * `smart_uv_pack` – chytré UV rozbalení s optimálním uspořádáním ostrovů.
4. **Scéna, produktové studio a kompozitor**:
   * `create_product_studio` – fotostudio s nekonečným pozadím a 3bodovým světlem.
   * `setup_blueprint_reference` – umístění technických výkresů do ortografických pohledů.
   * `setup_compositor` – postprodukční nody (glare bloom, denoiser, vinětace).
5. **Rigging a animace**:
   * `auto_rig_and_skin` – vygenerování kostry (Armature) a automatický skinning.
   * `apply_fcurve_animation` – interpolace a vyhlazení animačních křivek.
   * `create_motion_node_setup` – kinetické drivery a procedurální rotace.
6. **Přímé spuštění Python kódu**:
   * `execute_blender_code` – spouštění ověřeného kódu s autonomní **Self-Healing smyčkou**.

### 5. 🌐 Dvojjazyčné rozhraní & AI Korektura (CZ / EN)
* Plná dvojjazyčnost celého UI (přepínání za běhu bez nutnosti reloadu stránky).
* Nativní systémová kontrola pravopisu (`spellcheck="true"` s dynamickým přepínáním atributu `lang="cs"` / `lang="en"`).
* **AI Korektura jedním kliknutím**: Tlačítko se symbolem korektury analyzuje vstupní text, provede gramatickou, stylistickou a interpunkční úpravu a nabídne tlačítko pro okamžité vložení opravené verze zpět do vstupního pole.

---

## 💻 Hardwarové nároky a doporučení

Projekt byl navržen tak, aby poskytoval maximální flexibilitu a špičkový výkon na běžně dostupném hardwaru:

| Komponenta | Minimální konfigurace | Doporučená konfigurace | Cloud / Hybridní režim |
|---|---|---|---|
| **Procesor (CPU)** | 4jádrový CPU (x86_64) | 8jádrový CPU s podporou AVX2 | 4jádrový CPU |
| **Operační paměť (RAM)** | 8 GB RAM | 16 GB RAM | 8 GB RAM |
| **Grafická karta (GPU)** | Integrovaná grafika | Dedikovaná GPU s Vulkanem (např. AMD RX 560 4GB / NVIDIA GTX 1060) | Není vyžadována (0 MB VRAM při použití Groq / Gemini) |
| **Místo na disku** | 5 GB (kód + závislosti) | 15 GB (včetně lokálních .gguf modelů) | 3 GB |
| **Software** | Python 3.11+, Blender 4.2+ LTS | Python 3.11, Blender 4.2.1 LTS | Python 3.11, Blender 4.2.1 LTS |

---

## 🚀 Instalace a rychlý start

### Krok 1: Klonování repozitáře a vytvoření virtuálního prostředí
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

# Vytvoření virtuálního prostředí s Pythonem 3.11
python3.11 -m venv venv
source venv/bin/activate
```

### Krok 2: Instalace závislostí
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

> **Poznámka pro GPU akceleraci (Vulkan):**
> Pro zprovoznění Vulkan akcelerace v `llama-cpp-python` zadejte při instalaci:
> ```bash
> CMAKE_ARGS="-DGGML_VULKAN=on" pip install --force-reinstall --no-cache-dir llama-cpp-python
> ```

### Krok 3: Konfigurace
Zkopírujte vzorovou konfiguraci do [`config.json`](file:///home/polygon/ai-assistant-voice-cs/config.json):
```bash
cp config.example.json config.json
```
V [`config.json`](file:///home/polygon/ai-assistant-voice-cs/config.json) (nebo přímo v UI v dialogu Nastavení) můžete zvolit aktivního poskytovatele (`local`, `groq`, `gemini`, `custom`), cesty k modelům či API klíče.

### Krok 4: Spuštění webového serveru a aplikace
Můžete spustit buď samostatný backend server:
```bash
venv/bin/python web_server.py
```
nebo kompletní aplikaci se spouštěcím skriptem:
```bash
./start_app.sh
```
Aplikace bude dostupná ve vašem prohlížeči na adrese **`http://127.0.0.1:8000`**.

### Krok 5: Propojení s Blenderem
1. Spusťte **Blender 4.x**.
2. Otevřete záložku **Scripting** (nebo okno *Text Editor*).
3. Otevřete soubor [`blender_receiver.py`](file:///home/polygon/ai-assistant-voice-cs/blender_receiver.py) z tohoto repozitáře.
4. Klikněte na tlačítko **Run Script** (nebo stiskněte `Alt + P`).
5. V konzoli Blenderu se zobrazí hlášení: `[Blender Receiver] Server naslouchá na 127.0.0.1:9876`.
6. Webové rozhraní Polygon Beater okamžitě detekuje stav: **`Blender: Připojen`**.

---

## 📂 Přehled struktury projektu

```
ai-assistant-voice-cs/
├── web_server.py           # FastAPI backend — REST & SSE streaming API, security loopback shield
├── llama_module.py         # Kognitivní jádro — lokální Llama GGUF, OpenAI client, RAG & dispatching
├── blender_connector.py    # TCP Socket klient pro komunikaci s Blenderem (127.0.0.1:9876)
├── blender_receiver.py     # Přijímací daemon skript spouštěný v Blender Text Editoru
├── code_validator.py       # AST bezpečnostní validátor pro statickou analýzu Python kódu
├── document_service.py     # Lokální vektorová dokumentová báze (RAG) a sémantická paměť (FAISS)
├── history_repository.py   # Správa a ukládání relací a zpráv v JSON formátu
├── web_search.py           # Odlehčené vyhledávání přes DuckDuckGo s optimalizací kontextu
├── config.example.json     # Referenční šablona konfigurace
├── requirements.txt        # Konsolidovaný seznam přesně pinovaných závislostí
├── tests/                  # Sada unit testů pokrývající AST, API endpointy, Blender a RAG
│   ├── test_code_validator.py
│   ├── test_llm_connection_endpoint.py
│   ├── test_blender_connector.py
│   └── test_web_server.py
└── web_ui/                 # Moderní Dark-Tech frontend (Vanilla JS, CSS Grid, bez externích CDN)
    ├── index.html          # Hlavní HTML struktura s 3D workspace a modálními dialogy
    ├── style.css           # Responzivní design, CSS proměnné, animace a split-panely
    └── script.js           # Klientská logika, SSE zpracování, i18n lokalizace, AST integrace
```

---

## 🧪 Testování a verifikace

Projekt obsahuje kompletní sadu automatických unit testů ověřujících bezpečnost, REST rozhraní, RAG paměť i AST validaci:

```bash
# Spuštění celé testovací sady
venv/bin/python -m unittest discover -s tests

# Kontrola syntaxe Pythonu a JavaScriptu
venv/bin/python -m py_compile web_server.py llama_module.py blender_connector.py code_validator.py
node --check web_ui/script.js
```

---

## 📄 Licence

Tento projekt je licencován pod licencí **MIT** — podrobnosti naleznete v souboru [LICENSE](LICENSE).

**Autor a architekt:** Vítězslav Koneval (*Polygon Beater*)  
**GitHub:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)
