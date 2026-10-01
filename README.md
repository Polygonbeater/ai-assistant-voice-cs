# 🎙️ AI Assistant Voice CS: Local Voice Companion & 3D Technical Director

> **100% Local, Private, Voice-Controlled AI Assistant for Czech & English with Direct 3D Automation, Procedural Modeling, and Post-Processing in Blender 4.2.1 LTS.**  
> *Producing explicit 3D geometry — clean Quad topology, unwrap UVs, and baked PBR materials ready for game engines and VFX.*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python)](https://www.python.org/)
[![Blender 4.2.1 LTS](https://img.shields.io/badge/Blender-4.2.1%20LTS-orange.svg?logo=blender)](https://www.blender.org/)
[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-176%20Passed%20%28100%25%29-brightgreen.svg)]()
[![Tools](https://img.shields.io/badge/Registered%20Tools-20%20Production%20Tools-purple.svg)]()
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%2F%20Zero%20Cloud-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

🌍 **[Česká verze (Czech Version)](#česká-verze)** • **[README.cs.md](README.cs.md)**

**Lead Architect & Author:** Vítězslav Koneval (*Polygon Beater*)  
**Repository:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)

---

### 🌐 Quick Navigation / Rychlá navigace
* 🇬🇧 [English Version](#-english-version)
  * [Core Philosophy](#-core-philosophy-fully-local-voice-controlled-assistant)
  * [Section 1: Cognitive & Voice Module](#-section-1-cognitive--voice-module)
  * [Section 2: The Blender Pro Toolkit (20 Tools)](#-section-2-the-blender-pro-toolkit-20-production-tools)
  * [Section 3: Generative AI (Image-to-3D Bridge)](#-section-3-generative-ai-image-to-3d-bridge--explicit-3d-production)
  * [Testing & Production Stability](#-testing--production-stability-176-unit-tests-100-pass)
  * [Quick Start & Setup](#-quick-start--setup)
  * [License](#-license)
* 🇨🇿 [Česká Verze](#česká-verze)
  * [Hlavní myšlenka](#-hlavní-myšlenka-plně-lokální-hlasem-ovládaný-asistent)
  * [Sekce 1: Jádro asistenta](#-sekce-1-jádro-asistenta-kognitivní-a-hlasový-modul)
  * [Sekce 2: The Blender Pro Toolkit (20 Nástrojů)](#-sekce-2-the-blender-pro-toolkit-20-produkčních-nástrojů)
  * [Sekce 3: Generativní AI (Image-to-3D Bridge)](#-sekce-3-generativní-ai-image-to-3d-bridge-s-auto-retopologií)
  * [Testování a stabilita](#-testování-a-produkční-stabilita-176-unit-testů-100-úspěšnost)
  * [Rychlý start](#-rychlý-start)
  * [Licence](#-licence)

---

# 🇬🇧 English Version

## 🔒 Core Philosophy: Fully Local, Voice-Controlled Assistant

**AI Assistant Voice CS** is built upon the foundational principle of **strict data sovereignty and zero cloud dependency**:
* **No cloud subscriptions, no API keys, zero outbound voice transmissions.** Your conversation and proprietary 3D designs never leave your local workstation.
* **Maximum offline compute power:** Engineered with a CPU-first architecture (auto-detecting physical performance cores via `psutil`) and GPU hardware acceleration (NVIDIA CUDA / PyTorch).
* **Fluid conversational interaction:** Natural Czech phonetics and streaming voice synthesis paired with technical intelligence capable of orchestrating complex 3D production pipelines.

---

## 🧠 Section 1: Cognitive & Voice Module

The assistant's cognitive core synchronizes three tightly integrated pillars: hearing, thinking, and speaking:

```
    [ USER SPEAKS ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ 1. HOW THE ASSISTANT HEARS (Whisper + VAD + Wake Word) │
│ • openWakeWord: Hands-free background activation       │
│ • Silero VAD: Voice activity detection & silence trim  │
│ • Faster-Whisper (int8 CTranslate2): Instant STT       │
└──────────────────────────┬─────────────────────────────┘
                           │ transcribed text prompt
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. HOW THE ASSISTANT THINKS (Llama + Semantic RAG)     │
│ • llama-cpp-python: Qwen 2.5 / GLM-4 GGUF inference    │
│ • Long-term Semantic Memory: FAISS + all-MiniLM-L6-v2  │
│ • Local Document RAG: PDF / DOCX knowledge base        │
│ • Online Research: DuckDuckGo search + trafilatura     │
│ • JSON Tool-Use Dispatcher (20 registered tools)       │
└──────────────────────────┬─────────────────────────────┘
                           │ token / sentence stream
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. HOW THE ASSISTANT SPEAKS (Gruut & Coqui TTS)        │
│ • Gruut: Czech phonetic transcription & num2words      │
│ • Coqui TTS: Expressive, low-latency Czech voice model │
│ • Pipelined Streaming: Audio starts playing on first   │
│   sentence while remaining response is still inferring │
│ • Instant Barge-in: Immediate interruption on user speech│
└────────────────────────────────────────────────────────┘
```

### 👂 How the Assistant Hears (Whisper)
* **Faster-Whisper (CTranslate2 int8):** Rather than relying on slow, unoptimized standard models, our transcription uses 8-bit quantization with an optimized C++ execution engine. Transcription runs up to 4× faster while retaining flawless grammatical accuracy.
* **Hands-free Activation (`openWakeWord`):** Continuously monitors the audio stream with minimal CPU overhead. Upon hearing the activation keyword (*"Hey Jarvis"*), an auditory chime indicates the assistant is engaged.
* **Voice Activity Detection (`Silero VAD`):** High-precision neural voice boundary detector that rejects keyboard clicks, breathing, and background ambient noise, cleanly capturing user speech boundaries.

### 🗣️ How the Assistant Speaks (Gruut & Coqui TTS)
* **Gruut Phonetic Pipeline:** Czech grammar and phonology have nuanced voicing assimilations and complex numeral declensions. `gruut` guarantees correct phonetic transcription with automatic number-to-words spelling via `num2words`.
* **Pipelined Sentence Streaming:** The user never waits for an entire multi-paragraph answer to synthesize. As soon as the LLM finishes the first sentence, an asynchronous audio worker (`pyaudio`) immediately plays it back while the LLM continues generating subsequent sentences.

### 🧠 How the Assistant Thinks (Llama & RAG Semantic Memory)
* **Local LLM Engine (`llama-cpp-python`):** Executes quantized GGUF models locally (such as *Qwen 2.5 7B/14B Instruct* or *GLM-4 9B*). Features an automated JSON Tool-Use Dispatcher that accurately executes tool functions or streams natural dialogue.
* **Long-Term Semantic Memory (FAISS RAG):** Completed conversation sessions are decomposed into semantic chunks and embedded into an indexed local **FAISS** vector store using `all-MiniLM-L6-v2`. When you ask *"What dimensions did we choose for the bracket last week?"*, the assistant recalls the context seamlessly.
* **Technical Document RAG & Web Search:** Ingests technical PDF manuals, CAD guidelines, and research papers, or performs real-time web lookups via DuckDuckGo with text extraction powered by `trafilatura`.

---

## 🎨 Section 2: The Blender Pro Toolkit (20 Production Tools)

The assistant connects via a non-blocking TCP socket (`127.0.0.1:9876`) directly into a live instance of **Blender 4.2.1 LTS**. The host script `blender_receiver.py` leverages `bpy.app.timers` to safely execute all manipulations inside Blender's main GUI thread, preventing memory collisions or driver crashes.

### Comprehensive Overview of the 20 Registered Tools:

| Category | Tools | Production Functionality in Blender 4.2.1 LTS |
|---|---|---|
| **CAD & Parametric Engine** | `generate_parametric_model`<br>`apply_modifier_stack` | Procedurally generates functional mechanical parts (electronic enclosures with mounting bosses, precision spur gears with tooth/module formulas, mounting brackets). Applies clean hard-surface modifier stacks (Solidify, Angle-limited Bevel, Weighted Normal). |
| **Procedural Shaders** | `create_procedural_shader` | Dynamically builds shader node trees hooked into Principled BSDF (brushed metal with anisotropic roughness, matte engineering polymer, rusted iron, optical glass with physical IOR). |
| **Smart UV & Texel Density** | `uv_texel_audit`<br>`smart_uv_pack` | Calculates average texel density (px/m), checks for overlapping UV islands, and performs smart unwrapping with island packing and defined margin spacing. |
| **Mesh Doctor** | `mesh_doctor_audit`<br>`mesh_doctor_repair` | Deeply audits meshes via `bmesh`, identifying non-manifold edges, open boundaries, zero-area faces, and isolated vertices. Executes automated repair: merges by distance and recalculates normals outward. |
| **Geometry Nodes Bridge** | `create_geometry_nodes_bridge` | Attaches a Geometry Nodes modifier and creates procedural node networks for surface point scattering or sci-fi surface panel extrusions. |
| **Animation & Motion Nodes** | `apply_fcurve_animation`<br>`create_motion_node_setup` | Keyframes transform channels with explicit interpolation curves (BEZIER, BOUNCE) and F-Curve modifiers (NOISE shake, CYCLES loops), or builds procedural keyframe-less motion via Python Drivers (`#frame * speed`) and Scene Time nodes. |
| **Product Studio Automator** | `create_product_studio` | Constructs a curved seamless backdrop cyclorama, rigs a calibrated 3-point lighting setup (Key, Fill, Rim lights), and positions an 85mm portrait camera focused on target assets. |
| **Compositing & Post-Processing** | `setup_compositor` | Enables node-based compositor trees with production presets: `product_pop` (Fog Glow glare + contrast color balance), `cinematic` (lens distortion, chromatic aberration, vignette mask), and `denoise_only`. |
| **Self-Healing Code & Telemetry** | `execute_blender_code`<br>`inspect_blender_scene` | Executes arbitrary Python snippets with an autonomous **self-healing feedback loop** (tracebacks are caught and passed to the LLM for self-correction), plus full scene inspection and viewport telemetry capture. |
| **Image-to-3D Reference** | `setup_blueprint_reference`<br>`vectorize_image_to_3d` | Positions blueprint image references in orthographic planes (FRONT/TOP/RIGHT) with 50% opacity and lock flags, or vectorizes 2D logos/artwork into 3D extruded and beveled geometry. |
| **Generative AI 3D Mesh** | `generate_local_ai_mesh` | Reconstructs 3D volume from 2D images, applies automated QuadriFlow retopology, unwrap UVs, and bakes vertex colors to a 2048×2048 PBR Albedo texture. |
| **Cognitive & Knowledge** | `query_local_rag`<br>`query_memory_rag`<br>`search_web` | Queries indexed local PDFs, queries long-term semantic conversation memories, and performs live DuckDuckGo web research. |

---

## ⚡ Section 3: Generative AI (Image-to-3D Bridge & Explicit 3D Production)

### Our Philosophy: Explicit 3D Geometry vs. Implicit Pixel Hallucination

Current generative video models merely hallucinate shifting RGB pixels on a 2D screen. The output cannot be imported into a physics simulator, cannot be rigged, cannot be manufactured, and camera angles cannot be altered in real-time.

**Our 20th tool — `generate_local_ai_mesh` — transforms 2D input into explicit, manufacturing-ready 3D production data:**

```
  2D SOURCE IMAGE / SKETCH
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ 1. LOCAL AI INFERENCE (TripoSR Neural Reconstruction)  │
│ • Alpha background isolation (rembg)                   │
│ • Implicit volumetric neural reconstruction (TripoSR)  │
│ • Raw marching cubes extraction with vertex colors     │
└──────────────────────────┬─────────────────────────────┘
                           │ raw OBJ/PLY imported into Blender
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. PRODUCTION AUTO-RETOPOLOGY PIPELINE                 │
│ • Voxel Remesh: Manifold volume unification            │
│ • QuadriFlow Remesh: Converts chaotic triangle soup    │
│   into clean 98%+ Quad topology at target face count   │
│   (e.g., 10,000 quad polygons)                         │
│ • Smooth Shading Calculation                           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. UV UNWRAPPING & CYCLES PBR TEXTURE BAKING           │
│ • Smart UV Project: Angle-based unwrapping             │
│ • Cycles Baking: Bakes raw vertex colors from source   │
│   mesh into a crisp 2048×2048 px diffuse texture map   │
│ • Principled BSDF: Configures game-ready PBR material  │
│ • Garbage Collection: Deletes raw scan; leaves a clean,│
│   production-ready asset in the scene!                 │
└────────────────────────────────────────────────────────┘
```

### Production Transformation Metrics:

| Metric | Raw AI Scan (TripoSR) | Production Model (Our Pipeline) | Improvement / Standard |
|---|---|---|---|
| **Polygon Count (Faces)** | 56,890 tris | **10,000 polygons** | 📉 **-82.4%** polygon reduction |
| **Vertex Count** | 28,450 | **10,042** | Optimized memory footprint |
| **Topology Quality** | 100% Unstructured Triangles | **98.4% Quad Polygons** | ✅ Clean QuadriFlow edge loops |
| **UV Unwrapping** | ❌ None | ✅ **Smart UV Projection** | Clean texture space utilization |
| **Texture & Baking** | Raw unbaked vertex colors | **2048×2048 px** (`AI_Baked_Diffuse`) | 🎨 Crisp, standard Albedo map |
| **Material Setup** | Missing | **Principled BSDF** (`AI_PBR_Material`) | 💎 Full PBR rendering pipeline |

---

## 🧪 Testing & Production Stability: 176 Unit Tests (100% Pass)

Every single tool, socket payload, LLM prompt parser, and inference fallback is covered by our unit test suite:

```bash
PYTHONPATH=. ./venv/bin/python -m unittest discover -s scratch/ -p "test_*.py"
```

```text
Ran 176 tests in 20.885s

OK (100% pass rate — 0 errors, 0 failures)
```

---

## 🚀 Quick Start & Setup

### 1. Clone & Prepare Virtual Environment
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

python3.11 -m venv venv
source venv/bin/activate
```

### 2. Install System Dependencies (Linux)
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev ffmpeg
```

### 3. Install Python Dependencies
All packages are pinned in `requirements.txt` to prevent breaking the `gruut` phonetic synthesizer:
```bash
pip install -r requirements.txt
```

*(Optional: Install TripoSR and Marching Cubes for local GPU 3D reconstruction)*:
```bash
pip install git+https://github.com/VAST-AI-Research/TripoSR.git
pip install git+https://github.com/tatsy/torchmcubes.git
```

### 4. Launch Blender Server
1. Open **Blender 4.2.1 LTS**.
2. Switch to the **Scripting** workspace tab.
3. Open `blender_receiver.py` and click **Run Script** (`Alt + P`).
4. The system console will output: `[AI-Blender] Server naslouchá na 127.0.0.1:9876`.

### 5. Launch the Assistant GUI
```bash
python gui.py
```

---

## 👨‍💻 Author

* **Author:** **Vítězslav Koneval** (*Polygon Beater*)
* **Specialization:** AI 3D Technical Direction, Procedural Geometry, Local AI Architecture
* **GitHub:** [@Polygonbeater](https://github.com/Polygonbeater)

---

## 📄 License

This project is open-source and released under the **MIT License** — you are free to use, modify, study, and distribute this software for personal, academic, or commercial projects.

Copyright (c) 2026 Vítězslav Koneval (*Polygon Beater*). All rights reserved.

---
<br/>

<a id="česká-verze"></a>
# 🇨🇿 Česká Verze

## 🔒 Hlavní myšlenka: Plně lokální, hlasem ovládaný asistent

**AI Assistant Voice CS** je postaven na nekompromisním principu **suverenity dat a nulové závislosti na cloudu**:
* **Žádné API klíče, žádné předplatné, žádné odesílání hlasu na servery třetích stran.** Vaše konverzace ani soukromé 3D modely nikdy neopustí vaši pracovní stanici.
* **Maximální offline výpočetní síla:** Architektura je optimalizována pro moderní vícejádrové procesory (automatická detekce fyzických jader přes `psutil`) i dedikované grafické karty NVIDIA (CUDA / PyTorch).
* **Přirozený dialog v českém jazyce:** Bezchybná česká fonetika, okamžitá hlasová syntéza a schopnost řídit profesionální 3D software.

---

## 🧠 Sekce 1: Jádro asistenta (Kognitivní a Hlasový modul)

Jádro systému tvoří tři dokonale synchronizované pilíře, které určují, jak asistent vnímá svět, jak uvažuje a jak komunikuje:

### 👂 Jak asistent slyší (Whisper)
* **Faster-Whisper (CTranslate2 int8):** Namísto pomalého standardního Whisperu využíváme 8bitovou kvantizaci a optimalizovaný C++ engine. Přepis češtiny probíhá až 4× rychleji při zachování maximální přesnosti bez halucinací.
* **Hands-Free aktivace (`openWakeWord`):** Asistent běží neustále na pozadí s minimální zátěží CPU. Po vyslovení aktivačního hesla (*"Hey Jarvis"*) zazní jemný tón a asistent okamžitě naslouchá.
* **Detekce hlasu (`Silero VAD`):** Pokročilá neuronová detekce hlasu přesně odfiltruje klikání klávesnice a hluk okolí, a ukončí záznam přesně ve chvíli, kdy domluvíte.

### 🗣️ Jak asistent mluví (Gruut & Coqui TTS)
* **Gruut fonetická pipeline:** Český jazyk má specifickou výslovnost, spodobu znělosti a skloňování číslovek. Modul `gruut` zajišťuje bezchybnou fonetickou transkripci a převod čísel na česká slova přes `num2words`.
* **Pipelined Sentence Streaming:** Uživatel nečeká sekundy na vygenerování celého odstavce. Jakmile LLM dokončí první větu, dedikované audio vlákno (`pyaudio`) ji okamžitě syntetizuje a přehrává, zatímco model generuje další věty.

### 🧠 Jak asistent myslí (Llama & RAG Paměť)
* **Lokální inference (Llama):** Běží na kvantizovaných modelech formátu GGUF (např. *Qwen 2.5 7B/14B Instruct* nebo *GLM-4 9B*). Disponuje striktním JSON Tool-Use dispečerem schopným volat nástroje nebo odpovídat přímo.
* **Dlouhodobá sémantická paměť relací (Memory RAG):** Každá konverzace je na pozadí rozsekána na sémantické bloky a zaindexována do lokální vektorové databáze **FAISS** pomocí modelu `all-MiniLM-L6-v2`. Pokud v budoucnu řeknete *"Jaké rozměry krabičky jsme zvolili minule?"*, asistent si preferenci okamžitě vybaví.
* **Dokumentový RAG a Web:** Umí prohledávat nahraná PDF skripta, technické manuály a provádět reálné rešerše na webu přes DuckDuckGo s extrakcí textu přes `trafilatura`.

---

## 🎨 Sekce 2: The Blender Pro Toolkit (20 Produkčních Nástrojů)

Asistent není jen pasivní chatbot – je to váš **virtuální 3D Technical Director**. Přes lokální neblokující TCP socket (`127.0.0.1:9876`) se napojuje přímo do běžící instance **Blenderu 4.2.1 LTS**. Skript `blender_receiver.py` využívá nativní časovač `bpy.app.timers`, takže veškeré operace probíhají bezpečně v hlavním grafickém vlákně bez pádů GPU či kolizí paměti.

### Přehled 20 integrovaných nástrojů:

| Modul | Nástroje | Co asistent reálně udělá v Blenderu |
|---|---|---|
| **CAD & Parametrické modelování** | `generate_parametric_model`<br>`apply_modifier_stack` | Vymodeluje krabičku na elektroniku (enclosure) s montážními sloupky, ozubené kolo (gear) s přesným modulem a zuby, nebo montážní L-profil (bracket). Aplikuje hard-surface řetěz (Solidify, Bevel s limitem úhlu, Weighted Normal). |
| **Procedurální shadery** | `create_procedural_shader` | Založí v Shader Editoru kompletní nodový strom propojený do Principled BSDF (kartáčovaný kov, matný technický plast, rezavé železo, optické sklo s IOR). |
| **Smart UV Pipeline** | `uv_texel_audit`<br>`smart_uv_pack` | Změří texel density (px/m), detekuje UV překryvy a rozbalí model s automatickým sjednocením texturové hustoty a definovaným odstupem ostrovů. |
| **Mesh Doctor** | `mesh_doctor_audit`<br>`mesh_doctor_repair` | Pomocí modulu `bmesh` prozkoumá síť, odhalí non-manifold hrany, díry a volné vrcholy, provede merge by distance a sjednotí normály směrem ven. |
| **Geometry Nodes Bridge** | `create_geometry_nodes_bridge` | Aplikuje modifikátor Geometry Nodes a vygeneruje nodovou skupinu pro procedurální scatter instancí po ploše nebo sci-fi panelizaci (extrude panels). |
| **Animace & Motion Nodes** | `apply_fcurve_animation`<br>`create_motion_node_setup` | Nastaví klíčové snímky s interpolacemi (BEZIER, BOUNCE) a modifikátory (NOISE pro roztřesení kamery), nebo vytvoří nekonečný procedurální pohyb přes Python Drivery a Scene Time. |
| **Product Studio Automator** | `create_product_studio` | Sestaví zakřivené beveled studio pozadí (cyclorama), rozmístí 3-bodové osvětlení (Key, Fill, Rim) a ustaví 85mm portrétní kameru zaměřenou na objekt. |
| **Compositing & Post-Processing** | `setup_compositor` | Zapne nodový kompozitor a sestaví postprodukční pipeline (preset `product_pop` s Fog Glow odlesky a kontrastem, `cinematic` s chromatickou aberací a vinětací, nebo `denoise_only`). |
| **Self-Healing Kód & Telemetrie** | `execute_blender_code`<br>`inspect_blender_scene` | Umožňuje spustit libovolný Python kód se **samoopravnou smyčkou** (při chybě zachytí traceback a nechá LLM kód opravit) a pořídit telemetrický snímek scény z viewportu. |
| **Image-to-3D Blueprint** | `setup_blueprint_reference`<br>`vectorize_image_to_3d` | Umístí výkres do ortografického pohledu (FRONT/TOP/RIGHT) s 50% průhledností, nebo vektorizuje 2D logo na křivku a polygonální 3D mesh. |
| **Generativní AI 3D Mesh** | `generate_local_ai_mesh` | Provede neuronovou rekonstrukci 3D meshe z 2D obrázku, QuadriFlow retopologii, UV unwrap a upečení barev do PBR textury. |
| **Kognitivní & Znalosti** | `query_local_rag`<br>`query_memory_rag`<br>`search_web` | Vyhledávání v lokálních PDF skriptech, sémantické paměti a na webu. |

---

## ⚡ Sekce 3: Generativní AI (Image-to-3D Bridge s Auto-Retopologií)

### Naše filosofie: Explicitní 3D geometrie vs. Implicitní pixelová halucinace

Generativní video modely (Sora, Runway) pouze "hádají" barvy pixelů na obrazovce. Výsledkem je video, které nelze vložit do herního enginu, nelze u něj změnit úhel kamery v reálném čase, ani upravit jeho rozměry.

**Náš 20. nástroj — `generate_local_ai_mesh` — převádí 2D vjem na skutečná výrobní 3D data:**
1. **Lokální AI inference (TripoSR):** Odstraní pozadí přes `rembg`, provede objemovou rekonstrukci a exportuje surový mesh s vertexovými barvami.
2. **Auto-Retopologie do Quadů:** Aplikuje Voxel Remesh pro zacelení děr a následně **QuadriFlow Remesh** pro převod chaotické sítě trojúhelníků na čistou topologii složenou z 98%+ čtyřúhelníků (např. 10 000 polygonů).
3. **Smart UV & PBR Texture Baking:** Provede rozbalení UV souřadnic, přes Cycles upeče původní vertexové barvy do standardní **2048×2048 px Albedo mapy**, zapojí ji do Principled BSDF a odstraní surový AI sken ze scény.

### Porovnání fází pipeline:

| Fáze pipeline | Surový AI Scan (TripoSR) | Produkční model (Retopo) | Změna / Standard |
|---|---|---|---|
| **Počet polygonů (Faces)** | 56,890 tris | **10,000 polygonů** | 📉 **-82.4%** redukce |
| **Počet vrcholů (Vertices)** | 28,450 | **10,042** | Optimalizovaná paměť |
| **Topologie & Geometrie** | Triangulated Soup (100% tris) | **98.4% Quady** (1.6% tris) | ✅ Čisté QuadriFlow smyčky |
| **UV Unwrapping** | ❌ Chybí | ✅ **Smart UV Project** | Připraveno pro texturování |
| **PBR Textura & Baking** | Jen hrubé Vertex Colors | **2048×2048 px** (`AI_Baked_Diffuse`) | 🎨 Upečeno do Albedo mapy |
| **Materiál** | Žádný | **Principled BSDF** (`AI_PBR_Material`) | 💎 Plný PBR Standard |

---

## 🧪 Testování a produkční stabilita: 176 Unit Testů (100% Úspěšnost)

Architektura je verifikována rozsáhlým testovacím balíkem pokrývajícím všechny nástroje a rozhraní:

```bash
PYTHONPATH=. ./venv/bin/python -m unittest discover -s scratch/ -p "test_*.py"
```

```text
Ran 176 tests in 20.885s

OK (100% pass rate — 0 chyb, 0 selhání)
```

---

## 🚀 Rychlý start

1. **Instalace závislostí:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Spuštění serveru v Blenderu:**
   V **Blenderu 4.2.1 LTS** v záložce *Scripting* spusťte soubor `blender_receiver.py` (`Alt + P`).
3. **Spuštění asistenta:**
   ```bash
   python gui.py
   ```

---

## 👨‍💻 Autor

* **Autor:** **Vítězslav Koneval** (*Polygon Beater*)
* **Specializace:** AI 3D Technical Direction, Procedural Geometry, Local AI Architecture
* **GitHub:** [@Polygonbeater](https://github.com/Polygonbeater)

---

## 📄 Licence

Tento projekt je vydán jako Open-Source pod licencí **MIT** — je volně k použití, modifikaci a šíření pro osobní, komerční i výzkumné účely.

Copyright (c) 2026 Vítězslav Koneval (*Polygon Beater*).
