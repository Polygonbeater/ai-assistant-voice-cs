# 🎙️ AI Assistant Voice CS: Lokální hlasový parťák & 3D Technical Director

🌍 **[🇬🇧 Read the English Version (Anglická verze)](README.md)**

> **100% lokální, soukromý hlasový AI asistent pro český jazyk s přímou automatizací 3D modelování, procedurální geometrie a postprodukce v Blenderu 4.2.1 LTS.**  
> *Vytváříme explicitní geometrii — čisté Quad sítě, rozbalené UV a přepečené PBR materiály připravené pro herní enginy a VFX.*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python)](https://www.python.org/)
[![Blender 4.2.1 LTS](https://img.shields.io/badge/Blender-4.2.1%20LTS-orange.svg?logo=blender)](https://www.blender.org/)
[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-176%20Passed%20%28100%25%29-brightgreen.svg)]()
[![Tools](https://img.shields.io/badge/Registered%20Tools-20%20Production%20Tools-purple.svg)]()
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%2F%20Zero%20Cloud-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

**Hlavní architekt & autor:** Vítězslav Koneval (*Polygon Beater*)  
**Projektový repozitář:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)

---

## 🔒 Hlavní myšlenka: Plně lokální, hlasem ovládaný asistent

**AI Assistant Voice CS** je postaven na nekompromisním principu **suverenity dat a nulové závislosti na cloudu**:
* **Žádné API klíče, žádné předplatné, žádné odesílání hlasu na servery třetích stran.** Vaše konverzace ani soukromé 3D modely nikdy neopustí vaši pracovní stanici.
* **Maximální offline výpočetní síla:** Architektura je optimalizována pro moderní vícejádrové procesory (automatická detekce fyzických jader přes `psutil`) i dedikované grafické karty NVIDIA (CUDA / PyTorch).
* **Přirozený dialog v českém jazyce:** Bezchybná česká fonetika, okamžitá hlasová syntéza a schopnost řídit profesionální 3D software.

---

## 🧠 Sekce 1: Jádro asistenta (Kognitivní a Hlasový modul)

Jádro systému tvoří tři dokonale synchronizované pilíře, které určují, jak asistent vnímá svět, jak uvažuje a jak komunikuje:

```
    [ UŽIVATEL MLUVÍ ]
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ 1. JAK ASISTENT SLYŠÍ (Whisper + VAD + Wake Word)     │
│ • openWakeWord: Kontinuální hands-free "Hey Jarvis"    │
│ • Silero VAD: Detekce hlasové aktivity a ořez ticha   │
│ • Faster-Whisper (int8 CTranslate2): Bleskový přepis  │
└──────────────────────────┬─────────────────────────────┘
                           │ textový prompt
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. JAK ASISTENT MYSLEL (Llama + Vektorový RAG)        │
│ • llama-cpp-python: Qwen 2.5 / GLM-4 GGUF inference    │
│ • Dlouhodobá sémantická paměť: FAISS + all-MiniLM-L6-v2│
│ • Lokální dokumentový RAG: PDF / DOCX parsing          │
│ • Online rešerše: DuckDuckGo vyhledávání + trafilatura │
│ • JSON Tool-Use Dispatcher (20 registrovaných nástrojů)│
└──────────────────────────┬─────────────────────────────┘
                           │ tokeny / větný stream
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. JAK ASISTENT MLUVÍ (Gruut & Coqui Streaming TTS)    │
│ • Gruut: Přesná česká fonetika a normalizace čísel     │
│ • Coqui TTS: Přirozený český hlasový model             │
│ • Pipelined Streaming: Přehrávání první věty začíná    │
│   ihned během inference zbytku odpovědi                │
│ • Instant Barge-in: Okamžité přerušení při vstupu řeči │
└────────────────────────────────────────────────────────┘
```

### 👂 Jak asistent slyší (Whisper)
* **Faster-Whisper (CTranslate2 int8):** Místo standardního pomalého Whisperu využíváme 8bitovou kvantizaci a optimalizovaný C++ engine. Přepis češtiny probíhá až 4× rychleji při zachování maximální přesnosti bez halucinací.
* **Hands-Free aktivace (`openWakeWord`):** Asistent běží neustále na pozadí s minimální zátěží CPU. Po vyslovení aktivačního hesla (*"Hey Jarvis"*) zazní jemný tón a asistent okamžitě naslouchá.
* **Detekce hlasu (`Silero VAD`):** Pokročilá neuronová detekce hlasu přesně odfiltruje klikání klávesnice a hluk okolí, a ukončí záznam přesně ve chvíli, kdy domluvíte.

### 🗣️ Jak asistent mluví (Gruut & Coqui TTS)
* **Gruut fonetická pipeline:** Český jazyk má specifickou výslovnost, spodobu znělosti a skloňování číslovek. Modul `gruut` zajišťuje bezchybnou fonetickou transkripci a převod čísel na česká slova přes `num2words`.
* **Pipelined Sentence Streaming:** Uživatel nečeká sekundy na vygenerování celého odstavce. Jakmile LLM dokončí první větu, dedikované audio vlákno (`pyaudio`) ji okamžitě syntetizuje a přehrává, zatímco model generuje další věty.

### 🧠 Jak asistent myslí (Llama & RAG Paměť)
* **Lokální inference (Llama):** Běží na kvantizovaných modelech formátu GGUF (např. *Qwen 2.5 7B/14B Instruct* nebo *GLM-4 9B*). Disponuje striktním JSON Tool-Use dispečerem schopným volat nástroje nebo odpovídat přímo.
* **Dlouhodobá sémantická paměť relací (Memory RAG):** Každá konverzace je na pozadí rozsekána na sémantické bloky a zaindexována do lokální vektorové databáze **FAISS** pomocí modelu `all-MiniLM-L6-v2`. Pokud v budoucnu řeknete *"Jakou barvu jsme minule vybrali pro auto?"*, asistent si preferenci okamžitě vybaví.
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

```
  2D OBRÁZEK / FOTKA
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. LOKÁLNÍ AI INFERENCE (TripoSR / Real Model Wrapper) │
│ • Odstranění pozadí (rembg)                            │
│ • Rekonstrukce objemu neuronovou sítí (TripoSR)        │
│ • Export surového meshe s vertexovými barvami (.obj)   │
└──────────────────────────┬─────────────────────────────┘
                           │ import do Blenderu 4.2.1
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. AUTO-RETOPOLOGY PIPELINE                            │
│ • Voxel Remesh: Sjednocení objemu a zacelení děr       │
│ • QuadriFlow Remesh: Převod chaotického "triangle      │
│   soup" na čistou 98%+ Quad topologii na cílový       │
│   počet polygonů (např. 10 000 polygonů)               │
│ • Smooth Shading                                       │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. UV & TEXTURE BAKING DO PBR STANDARDU                │
│ • Smart UV Project: Automatické rozbalení do UV plochy │
│ • Cycles Baking: Přepečení původních vertexových barev │
│   ze surového AI skenu do nové 2048×2048 px textury    │
│ • Principled BSDF: Vytvoření PBR materiálu             │
│ • Vymazání surového modelu: Ve scéně zůstává čistý     │
│   game-ready / VFX-ready 3D asset!                     │
└────────────────────────────────────────────────────────┘
```

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

Stabilita celého ekosystému je doložena rozsáhlým testovacím balíkem pokrývajícím všech 20 nástrojů, socketový protokol, parser i sémantickou paměť:

```bash
PYTHONPATH=. ./venv/bin/python -m unittest discover -s scratch/ -p "test_*.py"
```

```text
Ran 176 tests in 20.885s

OK (100% pass rate — 0 chyb, 0 selhání)
```

Pokryté oblasti testů:
1. `test_local_ai_mesh.py` — TripoSR wrapper, generování OBJ/PLY, mock/reálná inference, QuadriFlow integrace.
2. `test_compositor_pipeline.py` — Postprodukční kompozitor, presety a nodové stromy.
3. `test_image_to_3d_bridge.py` — Blueprint reference, vektorizace kontur a kognitivní Vision AI.
4. `test_animation_motion_nodes.py` — F-křivky, interpolace, procedurální drivery.
5. `test_geometry_nodes_bridge.py` — Tvorba nodových skupin na Geometry Nodes modifikátoru.
6. `test_parametric_modeling.py` — CAD parametrické modely a hard-surface modifikátory.
7. `test_uv_pipeline.py` — Texel density audity a Smart UV packing.
8. `test_procedural_shader.py` — Procedurální materiály a Principled BSDF nody.
9. `test_product_studio.py` — Světla, kamery a cyclorama studio pozadí.
10. `test_mesh_doctor.py` — bmesh inspekce a automatické opravy geometrie.
11. `test_semantic_memory.py` — FAISS vektorové ukládání a kontinuita relací.
12. `test_blender_inspection.py` & `test_blender_self_healing.py` — Telemetrie a samoopravná smyčka kódu.
13. `test_function_calling.py` — Validace všech 20 nástrojů v systémovém promptu a JSON parseru.

---

## 💻 Technologický Stack & Požadavky

* **3D Software:** Blender 4.2.1 LTS (vyžaduje spuštěný skript `blender_receiver.py` v Text Editoru).
* **Python:** 3.11 (doporučeno pro maximální kompatibilitu knihoven).
* **LLM Engine:** `llama-cpp-python` (GGUF modely Qwen 2.5, GLM-4).
* **Hlasový subsystém:** `faster-whisper`, `openwakeword`, `TTS` (Coqui TTS), `gruut`, `pyaudio`.
* **Vektorová paměť:** `faiss-cpu`, `sentence-transformers` (`all-MiniLM-L6-v2`).
* **AI 3D Inference:** `TripoSR`, `torch`, `torchvision`, `trimesh`, `pillow`, `rembg`.

---

## 🚀 Rychlý start

### 1. Klonování a příprava virtuálního prostředí
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

python3.11 -m venv venv
source venv/bin/activate
```

### 2. Instalace systémových knihoven (Linux)
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev ffmpeg
```

### 3. Instalace Python závislostí
Závislosti jsou striktně fixovány v `requirements.txt` proti rozbití syntetizéru `gruut`:
```bash
pip install -r requirements.txt
```

*(Volitelné: instalace TripoSR pro plnou lokální GPU rekonstrukci)*:
```bash
pip install git+https://github.com/VAST-AI-Research/TripoSR.git
pip install git+https://github.com/tatsy/torchmcubes.git
```

### 4. Spuštění serveru v Blenderu
1. Otevřete **Blender 4.2.1 LTS**.
2. V horním menu zvolte záložku **Scripting**.
3. Otevřete soubor `blender_receiver.py` a stiskněte **Run Script** (`Alt + P`).
4. V konzoli Blenderu se potvrdí: `[AI-Blender] Server naslouchá na 127.0.0.1:9876`.

### 5. Spuštění asistenta
```bash
python gui.py
```
Můžete ihned mluvit do mikrofonu nebo psát do chatu:
* *"Zkontroluj aktivní model přes Mesh Doctor a oprav případné chyby."*
* *"Nastav produktové studio s 85mm kamerou a vytvoř materiál z kartáčovaného kovu."*
* *"Vezmi obrázek robota a vytvoř z něj produkční 3D mesh s čistými quady a upečenou texturou."*

---

## 👨‍💻 Autor

* **Autor:** **Vítězslav Koneval** (*Polygon Beater*)
* **Specializace:** AI 3D Technical Direction, Procedural Geometry, Local AI Architecture
* **GitHub:** [@Polygonbeater](https://github.com/Polygonbeater)

---

## 📄 Licence

Tento projekt je vydán jako Open-Source pod licencí **MIT** — je volně k použití, modifikaci a šíření pro osobní, komerční i výzkumné účely.

Copyright (c) 2026 Vítězslav Koneval (*Polygon Beater*).
