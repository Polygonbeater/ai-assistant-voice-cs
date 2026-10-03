# 🎙️ Polygon Beater — AI Assistant Voice CS
### *Lokální hlasový AI asistent a 3D technický ředitel pro Blender 4.x*

🌍 **[🇬🇧 Read the English Version (Anglická verze)](README.md)**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg?logo=python)](https://www.python.org/)
[![Blender 4.x+](https://img.shields.io/badge/Blender-4.x%20LTS-orange.svg?logo=blender)](https://www.blender.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vulkan Accelerated](https://img.shields.io/badge/Vulkan-Hardware%20Offload-red.svg?logo=vulkan)](https://www.khronos.org/vulkan/)
[![AST Protected](https://img.shields.io/badge/Security-AST%20Gatekeeper-success.svg)]()
[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-58%2F58%20Passed%20(100%25)-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Polygon Beater** je pokročilý, 100% suverénní lokální hlasový asistent s integrovaným 3D kognitivním jádrem pro přímou procedurální tvorbu, parametrické CAD modelování, inspekci topologie a automatizaci renderovací pipeline v **Blenderu 4.x LTS**.  
> *Vytváříme explicitní geometrii — čisté Quad sítě, rozbalené UV a přepečené PBR materiály připravené pro herní enginy, 3D tisk a VFX.*

---

**Hlavní architekt & autor:** Vítězslav Koneval (*Polygon Beater*)  
**Projektový repozitář:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)

---

## 🔒 Hlavní myšlenka: Suverenita dat & Hybridní AI mozek

**Polygon Beater** je postaven na nekompromisním principu **ochrany soukromí a nulové závislosti na cloudu**:
* **100% offline jako výchozí stav:** Vaše hlasové nahrávky, historie konverzací, soukromé CAD náčrty ani 3D scény nikdy neopustí vaši pracovní stanici.
* **Hybridní kognitivní flexibilita:** Běží zcela offline na lokálních GGUF modelech (s akcelerací přes fyzická jádra CPU a Vulkan GPU offload), nebo umožňuje bleskově připojit cloudové LPU (Groq Llama 3.3 / Qwen 2.5), multimodální Google Gemini (2.0 Flash / Vision) i libovolné vlastní OpenAI-kompatibilní API (DeepSeek, OpenRouter, Mistral, Ollama, vLLM).
* **Přirozený dialog v češtině i angličtině:** Bezchybná česká fonetika, okamžitá hlasová syntéza se streamingem, inteligentní přerušení při vstupu řeči (barge-in) a schopnost řídit profesionální 3D software.

---

## 🧠 Sekce 1: Jádro asistenta (Kognitivní a Hlasový modul)

Jádro systému tvoří tři synchronizované pilíře, které určují, jak asistent vnímá svět, jak uvažuje a jak komunikuje:

```
                          [ UŽIVATEL MLUVÍ / PÍŠE ]
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. JAK ASISTENT SLYŠÍ (Whisper + Silero VAD + openWakeWord)            │
│ • openWakeWord: Kontinuální hands-free aktivace "Hey Jarvis"           │
│ • Silero VAD: Neuronová detekce hlasové aktivity a ořez ticha          │
│ • Faster-Whisper (int8 CTranslate2): Bleskový lokální přepis řeči      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ textový prompt
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. JAK ASISTENT MYSLÍ (Hybridní LLM + Sémantická paměť RAG)           │
│ • llama-cpp-python: Lokální GGUF inference (Qwen 2.5, GLM-4) na Vulkan │
│ • Cloud LPU & Multimodalita: Groq, Gemini Flash Latest, DeepSeek     │
│ • Dlouhodobá sémantická paměť: FAISS vektorová databáze + MiniLM       │
│ • Lokální dokumentový RAG: PDF / DOCX parsing a vyhledávání faktů      │
│ • Dynamické kontextové načítání nástrojů (26 nástrojů -> 8 v chatu)   │
│ • Online rešerše: DuckDuckGo vyhledávání + optimalizovaný kontext      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ tokenový stream / větné události
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. JAK ASISTENT MLUVÍ (Gruut & Coqui Streaming TTS)                   │
│ • Gruut: Přesná česká fonetika, spodoba znělosti a normalizace čísel   │
│ • Coqui TTS: Přirozené české a anglické hlasové modely                 │
│ • Pipelined Streaming: Přehrávání první věty začíná ihned během        │
│   probíhající inference zbytku odpovědi model em                       │
│ • Instant Barge-in: Okamžité přerušení přehrávání při novém vstupu     │
└────────────────────────────────────────────────────────────────────────┘
```

### 👂 Jak asistent slyší (Whisper & Neuronový VAD)
* **Faster-Whisper (CTranslate2 int8):** Využívá 8bitovou kvantizaci a optimalizovaný C++ engine. Přepis probíhá až 4× rychleji než u standardního Whisperu při zachování maximální gramatické přesnosti a interpunkce.
* **Soukromý hlasový vstup ve Web UI:** Záznam z mikrofonu se odesílá výhradně na lokální FastAPI endpoint `/api/stt/transcribe`. Cloudové rozhraní SpeechRecognition v prohlížeči se nepoužívá.
* **Hands-Free aktivace (`openWakeWord`):** Běží na pozadí s minimální zátěží CPU. Po vyslovení hesla (*"Hey Jarvis"*) zazní jemný tón a asistent okamžitě naslouchá.
* **Detekce hlasu (`Silero VAD`):** Pokročilá neuronová detekce hlasu odfiltruje klikání klávesnice a ruchy okolí a ukončí záznam přesně ve chvíli, kdy domluvíte.

### 🗣️ Jak asistent mluví (Gruut & Coqui TTS)
* **Gruut fonetická pipeline:** Český jazyk má specifickou výslovnost, spodobu znělosti a skloňování číslovek. Modul `gruut` zajišťuje bezchybnou fonetickou transkripci a převod čísel na česká slova přes `num2words`.
* **Pipelined Sentence Streaming:** Uživatel nečeká sekundy na vygenerování celého odstavce. Jakmile LLM dokončí první větu, dedikované audio vlákno (`pyaudio`) ji okamžitě syntetizuje a přehrává, zatímco model generuje další věty.
* **Instant Barge-in:** Pokud začnete mluvit v průběhu odpovědi asistenta, přehrávání se okamžitě zastaví a mikrofon zpracuje nový dotaz.

### 🧠 Jak asistent myslí (Hybridní LLM, RAG & Dynamické načítání nástrojů)
* **Lokální inference (Llama GGUF):** Běží na kvantizovaných modelech formátu GGUF (např. *Qwen 2.5 7B/14B Instruct* nebo *GLM-4 9B*). Automaticky detekuje fyzická jádra CPU přes `psutil` a rozděluje vrstvy do VRAM grafické karty přes Vulkan.
* **Univerzální API klient (`OpenAICompatibleClient`):** Integrovaný streaming klient pro Groq, Google Gemini (přes OpenAI endpoint), DeepSeek, OpenRouter, Mistral, Ollama a vLLM včetně měření latence v reálném čase.
* **Dlouhodobá sémantická paměť relací (Memory RAG):** Konverzace jsou na pozadí ukládány jako sémantické vektory přes `all-MiniLM-L6-v2` do lokální vektorové databáze **FAISS**. Asistent si spolehlivě vybaví technická rozhodnutí (*"Jaké rozměry jsme minule zvolili pro krabičku na elektroniku?"*).
* **Dynamické kontextové načítání nástrojů:** Pokud je aktivní profil Standardní chat nebo je Blender offline, asistent nepředává do systémového promptu 18 náročných 3D nástrojů, což **ušetří přes 3 000 tokenů na dotaz** a zásadně zrychlí generování na CPU i GPU.
* **Nástroje pro soubory projektu:** Asistent může soubory projektu vypisovat, prohledávat, číst a zapisovat. Čtení je omezené na 500 KB, zápis je uzamčený uvnitř aktivního kořene projektu a citlivé cesty i privátní klíče jsou blokovány. Před úpravou kódu má asistent nejprve přečíst relevantní soubor. Workspace lze změnit nebo obnovit v **Nastavení → Obecná konfigurace → Pracovní adresář projektu**.

---

## 🎨 Sekce 2: The Blender Pro Toolkit (18 Produkčních Nástrojů & AST Bezpečnost)

Asistent se napojuje přes lokální neblokující TCP socket (`127.0.0.1:9876`) přímo do běžící instance **Blenderu 4.x LTS**. Skript [`blender_receiver.py`](file:///home/polygon/ai-assistant-voice-cs/blender_receiver.py) využívá časovač `bpy.app.timers`, takže veškeré operace probíhají bezpečně v hlavním grafickém vlákně bez pádů GPU či kolizí paměti.

### 🛡️ AST Bezpečnostní validátor (`code_validator.py`)
Veškerý Python/bpy kód vygenerovaný asistentem nebo zadaný v editoru prochází před odesláním do socketu statickou **AST (Abstract Syntax Tree) analýzou**:
* **Whitelist povolených knihoven:** Pouze `{"bpy", "bmesh", "mathutils", "math", "random", "colorsys", "json"}`.
* **Zákaz nebezpečných modulů a příkazů:** Okamžitě blokuje `os`, `sys`, `subprocess`, `shutil`, `socket`, `requests`, `pathlib`, `eval()`, `exec()`, `open()`, `compile()`, `globals()`, `locals()`.
* **Ochrana před reflexí a sandbox escape:** Blokuje přístup k dunder atributům (`__subclasses__`, `__builtins__`, `__globals__`, `__code__`) i dynamické triky přes `getattr()`.

```
                  ┌──────────────────────────────────────────────┐
                  │    Kód vygenerovaný LLM / zadaný ve Web UI   │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │   AST BEZPEČNOSTNÍ VALIDÁTOR                 │
                  │   • Kontrola whitelistu (bpy, bmesh, math)   │
                  │   • Zákaz nebezpečných importů (os, subproc) │
                  │   • Zákaz dunder reflexe (__subclasses__)    │
                  └──────────────┬────────────────┬──────────────┘
                                 │                │
                        [Čistý a validní]   [Bezpečnostní porušení / Chyba syntaxe]
                                 │                │
                                 ▼                ▼
┌─────────────────────────────────────────────┐ ┌────────────────────────────────┐
│ Odeslání do Blenderu přes TCP socket (9876) │ │ Okamžité odmítnutí a hlášení   │
│ • Bezpečný běh v hlavním vlákně Blenderu    │ │ předané uživateli / asistentovi│
│ • Autonomní Self-Healing smyčka při chybách │ │ (Socket se vůbec neotevře)     │
└─────────────────────────────────────────────┘ └────────────────────────────────┘
```

### Kompletní přehled 18 integrovaných 3D nástrojů:

| Kategorie | Nástroje | Co asistent reálně vykoná v Blenderu 4.x |
|---|---|---|
| **1. Geometrie a parametrické CAD modelování** | `generate_parametric_model`<br>`apply_modifier_stack`<br>`create_geometry_nodes_bridge`<br>`vectorize_image_to_3d`<br>`generate_local_ai_mesh` | Procedurálně vymodeluje krabičku na elektroniku (enclosure), ozubené kolo s přesným modulem a zuby, nebo montážní L-profil. Aplikuje hard-surface řetěz (Solidify, Bevel, Weighted Normal). Převede 2D křivky na 3D geometrii a rekonstruuje 3D koncept z obrázku. |
| **2. Audit topologie & 3D tisk (Mesh Doctor)** | `mesh_doctor_audit`<br>`mesh_doctor_repair`<br>`inspect_blender_scene` | Pomocí modulu `bmesh` odhalí non-manifold hrany, díry, n-gony a převrácené normály. Provede automatickou opravu: merge by distance, zacelení děr a sjednocení normál pro slicer. Pořídí telemetrii a snímek scény z viewportu. |
| **3. Materiály, UV mapování a textury** | `create_procedural_shader`<br>`uv_texel_audit`<br>`smart_uv_pack` | Založí v Shader Editoru nodový strom propojený do Principled BSDF (kartáčovaný kov, matný plast, rez, optické sklo s IOR). Změří texel density (px/m) a provede UV rozbalení s definovaným odstupem ostrovů. |
| **4. Scéna, produktové studio a kompozitor** | `create_product_studio`<br>`setup_blueprint_reference`<br>`setup_compositor` | Sestaví zakřivené studio pozadí (cyclorama), rozmístí 3bodové AREA osvětlení (Key, Fill, Rim) a ustaví 85mm portrétní kameru. Umístí referenční výkresy do ortografických pohledů a zapne kompozitor (glare bloom, denoiser). |
| **5. Rigging a animace** | `auto_rig_and_skin`<br>`apply_fcurve_animation`<br>`create_motion_node_setup` | Vygeneruje kostru (`ARMATURE_AUTO`) a provede automatický skinning s vahami. Nastaví klíčové snímky s vyhlazením F-křivek (BEZIER, BOUNCE) nebo vytvoří procedurální kinetický pohyb přes Python drivery (`#frame * speed`). |
| **6. Spuštění kódu & Telemetrie** | `execute_blender_code`<br>`analyze_viewport_image` | Spouští ověřený Python kód se **samoopravnou Self-Healing smyčkou** (při chybě zachytí traceback a nechá LLM kód opravit). Pořídí snímek viewportu pro multimodální analýzu. |

---

## ⚡ Sekce 3: Generativní AI (Image-to-3D Bridge s Auto-Retopologií)

### Naše filosofie: Explicitní 3D geometrie vs. Implicitní pixelová halucinace
Generativní video modely pouze hádají barvy pixelů na 2D obrazovce. Výsledkem je video, které nelze vložit do herního enginu, nelze u něj změnit úhel kamery v reálném čase, ani upravit jeho rozměry.

**Náš nástroj `generate_local_ai_mesh` převádí 2D obrázek na skutečná výrobní 3D data:**

```
  2D OBRÁZEK / FOTKA
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ 1. LOKÁLNÍ AI INFERENCE (TripoSR / Rembg)              │
│ • Odstranění pozadí (rembg)                            │
│ • Rekonstrukce objemu neuronovou sítí (TripoSR)        │
│ • Export surového meshe s vertexovými barvami (.obj)   │
└──────────────────────────┬─────────────────────────────┘
                           │ import do Blenderu 4.x
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. PRODUKČNÍ AUTO-RETOPOLOGY PIPELINE                  │
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
│   game-ready / 3D print asset!                         │
└────────────────────────────────────────────────────────┘
```

### Porovnání fází pipeline:

| Fáze pipeline | Surový AI Scan (TripoSR) | Produkční model (Retopo) | Změna / Standard |
|---|---|---|---|
| **Počet polygonů (Faces)** | 56,890 tris | **10,000 polygonů** | 📉 **-82.4%** redukce |
| **Počet vrcholů (Vertices)** | 28,450 | **10,042** | ⚡ Optimalizovaná paměť |
| **Topologie & Geometrie** | Triangulated Soup (100% tris) | **98.4% Quady** (1.6% tris) | ✅ Čisté QuadriFlow smyčky |
| **UV Unwrapping** | ❌ Chybí | ✅ **Smart UV Project** | 🗺️ UV s definovaným odstupem |
| **PBR Textura & Baking** | Jen hrubé Vertex Colors | **2048×2048 px** (`AI_Baked_Diffuse`) | 🎨 Upečeno do Albedo mapy |
| **Materiál** | Žádný | **Principled BSDF** (`AI_PBR_Material`) | 💎 Plný PBR standard |

---

## 🧭 Sekce 4: Intelektuální moduly & Strategické frameworky (Expert Prompts V3.1)

Asistent neslouží pouze jako technický operátor pro 3D grafiku a hlasový dialog – disponuje integrovanou kognitivní výbavou čítající **11 expertních metodik** (`prompts/`) pro hloubkovou strategickou analýzu, řízení rizik a rozhodování v podmínkách nejistoty:

* **Talebova metodika (Incerto):** Analýza systémů z pohledu Antifragility, zranitelnosti vůči černým labutím (Black Swan), *Via Negativa* (odstraňování slabin), konvexity/konkavity dopadů, principu Skin in the Game a Pre-mortem analýzy selhání.
* **Cynefin rámec & OODA Loop:** Kategorizace problémů do domén (prostá, komplikovaná, komplexní, chaotická) a rychlé cykly rozhodování (*Observe-Orient-Decide-Act*) pro hyperdynamická prostředí.
* **Systémové myšlení (Peter Senge) & Porterových pět sil:** Mapování kauzálních smyček a zpětných vazeb (včetně generování Mermaid diagramů), hledání pákových bodů a analýza konkurenčních tlaků v odvětví.
* **Design Thinking & Plánování scénářů:** Uživatelsky orientovaná inovace s behaviorálními ukazateli (KBIs), práce s kritickými nejistotami a sledování varovných indikátorů (trigger points).
* **Meta-prompt pro komplexní strategickou analýzu:** Ucelený exekutivní protokol propojující makroanalýzu PESTLE, oborového Portera, matici SWOT, multikriteriální rozhodovací matice a metodu ACH (Analysis of Competing Hypotheses).
* **Metodické protokoly pro hloubkovou oponenturu (`prompts/frameworks/`):**
  * [`advanced_assumption_audit.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/advanced_assumption_audit.md): Red Team zátěžové testy a forenzní audit skrytých premis (striktní třídění výroků na Fakta, Hypotézy a Dogmata), Popperovská falsifikační kritéria a steelmanning protinávrhů.
  * [`auteur_visual_analysis.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/auteur_visual_analysis.md): Sémiotická a ikonografická dekonstrukce audiovizuálních děl (geometrie mizanscény, světelná dramaturgie šerosvitu, montážní syntax a odkazy na mistry od Caravaggia po Fritze Langa).
  * [`first_principles_technical.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/first_principles_technical.md): Myšlení v prvních principech pro kód a 3D geometrii ($4\times 4$ transformační matice, kvaterniony bez rizika Gimbal Locku, neměnné stavy a přímá práce s BMesh strukturami v Blenderu).

---

## 🖥️ Sekce 5: Moderní vývojářské IDE & Zabezpečení

Webové uživatelské rozhraní bylo přepracováno do podoby moderního vývojářského prostředí (ve stylu Cursoru a VS Code), navrženého pro maximální přehlednost, technickou přesnost a 100% offline spolehlivost:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   HLAVIČKA / STAVOVÝ ŘÁDEK                             │
│ [Status: Qwen 2.5]  [Blender: Připojen]  [RAG: Offline]  [Báze Znalostí] [Nastavení]   │
├─────────────────┬──────────────────────────────────────┬───────────────────────────────┤
│   LEVÝ PANEL    │            CHAT WORKSPACE            │       KONTEXTOVÝ PANEL        │
│ • Strom relací  │ • Markdown s tématem Atom One Dark   │ ┌───────────────────────────┐ │
│ • Hard Delete   │ • Zvýraznění kódu a kopírování       │ │ [3D]    [Rešerše]   [Log] │ │
│ • Hledání chatu │ • Výběr expertní analytické metodiky │ ├───────────────────────────┤ │
│ • Změna šířky   │ • Prompt bar (Whisper STT + RAG doc) │ │ Karta aktivní záložky     │ │
│                 │ • AI Korektura + SSE Live Stream     │ │ (Interní scroll & resize) │ │
└─────────────────┴──────────────────────────────────────┴───────────────────────────────┘
```

### 1. Ergonomie a vizuální styl moderního IDE
* **Barevné zvýraznění kódu Atom One Dark:** Kódové bloky v chatu využívají knihovnu Highlight.js s tématem Atom One Dark a tlačítkem pro kopírování na jedno kliknutí.
* **100% offline Lucide ikony:** Veškeré ovládací prvky, indikátory stavu a tlačítka používají čisté inline SVG ikony v designu Lucide (`viewBox="0 0 24 24"`). Aplikace nestahuje žádná externí webová písma a funguje zcela bez připojení k internetu.
* **Vícesměrné resizery pro změnu velikosti:** Horizontální posuvníky pro plynulou změnu šířky panelů a vertikální resizery jednotlivých boxů s trvalým ukládáním rozměrů do `localStorage`.
* **Bilingvní lokalizace (CZ / EN):** Kompletní lokalizační slovník s dynamickým přepínáním v nastavení a trvalým ukládáním předvoleb.
* **AI Korektura jedním kliknutím:** Tlačítko se symbolem korektury analyzuje vstupní text, provede gramatickou, stylistickou a interpunkční úpravu a nabídne tlačítko pro okamžité vložení opravené verze zpět do vstupního pole.

### 2. Kontextově závislý pravý panel (Context Workspace)
* 🧊 **3D Workspace:** Živý náhled viewportu z Blenderu s lightboxem, panel metrik scény (objekty, MESH, polygony, vrcholy, test vodotěsnosti, kosti) a matice 18 rychlých 3D příkazů.
* 🌐 **Rešerše:** Výsledky webového vyhledávání přes DuckDuckGo s citacemi a úryvky textu a nalezené bloky z FAISS s procentuální shodou relevance.
* ⚡ **Agent Log:** Časová osa kroků agenta s barevnými odznaky jednotlivých akcí (nástroje, RAG, rešerše) a telemetrická konzole v reálném čase.

### 3. Network Loopback Shield
* Webový server FastAPI i Blender socket server naslouchají striktně na loopback rozhraní (`127.0.0.1`, `localhost`, `::1`).
* Citlivé endpointy (`/api/config`, `/api/llm/test-connection`, `/api/app/shutdown`) okamžitě odmítají požadavky z vnějších IP adres kódem `403 Forbidden`, čímž chrání API klíče a konfiguraci před útoky ze sítě (SSRF).

---

## 💻 Hardwarové nároky a doporučení

| Komponenta | Minimální konfigurace | Doporučená konfigurace (Lokální GGUF) | Cloud / Hybridní režim |
|---|---|---|---|
| **Procesor (CPU)** | 4jádrový CPU (x86_64) | 8jádrový CPU s podporou AVX2 | 4jádrový CPU |
| **Operační paměť (RAM)** | 8 GB RAM | 16 GB - 32 GB RAM | 8 GB RAM |
| **Grafická karta (GPU)** | Integrovaná grafika | Dedikovaná GPU s Vulkanem (např. AMD RX 560 4GB / NVIDIA GTX 1060+) | Není vyžadována (0 MB VRAM při použití Groq / Gemini) |
| **Místo na disku** | 5 GB SSD volného místa | 15 GB NVMe SSD (včetně .gguf modelů) | 3 GB SSD volného místa |
| **Software** | Python 3.11+, Blender 4.x LTS | Python 3.11, Blender 4.2.1 LTS | Python 3.11, Blender 4.2.1 LTS |

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

> **Bezpečnostní autentizační token pro Blender Bridge (Fail-Secure):**
> V souladu s bezpečnostním modelem systém nepoužívá žádný výchozí/hardcoded tajný klíč.
> Vygenerujte náhodný token (např. `openssl rand -hex 16`) a vložte jej do `config.json` pod klíč `blender.auth_token`, nebo nastavte proměnnou prostředí `POLYGON_BLENDER_AUTH_TOKEN`:
> ```bash
> export POLYGON_BLENDER_AUTH_TOKEN="$(openssl rand -hex 16)"
> ```

### Krok 4: Spuštění webového serveru a aplikace
Spusťte backend server:
```bash
venv/bin/python web_server.py
```
nebo kompletní desktopovou aplikaci:
```bash
./start_app.sh
```
Aplikace bude dostupná v prohlížeči na adrese **`http://127.0.0.1:8000`**.

### Krok 5: Propojení s Blenderem
1. Spusťte **Blender 4.x**.
2. Otevřete záložku **Scripting** (nebo okno *Text Editor*).
3. Otevřete soubor [`blender_receiver.py`](file:///home/polygon/ai-assistant-voice-cs/blender_receiver.py) a klikněte na tlačítko **Run Script** (`Alt + P`).
4. V konzoli Blenderu se zobrazí hlášení: `[Blender Receiver] Server naslouchá na 127.0.0.1:9876`.
5. Webové rozhraní Polygon Beater okamžitě zobrazí stav: **`Blender: Připojen`**.

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
├── web_search.py           # Odlehčené vyhledávání přes DuckDuckGo / ddgs s optimalizací kontextu
├── config.example.json     # Referenční šablona konfigurace
├── requirements.txt        # Konsolidovaný seznam přesně pinovaných závislostí
├── tests/                  # Sada 58 automatických unit testů (AST, API, Blender, RAG, Security)
│   ├── test_code_validator.py
│   ├── test_llm_connection_endpoint.py
│   ├── test_blender_connector.py
│   ├── test_security_patches.py
│   └── test_web_server.py
└── web_ui/                 # Dark-Tech frontend (Vanilla JS, CSS Grid, 0 CDN závislostí)
    ├── index.html          # Hlavní HTML struktura s 3D workspace a modálními dialogy
    ├── style.css           # Responzivní design, CSS proměnné, animace a split-panely
    └── script.js           # Klientská logika, SSE zpracování, i18n lokalizace, AST integrace
```

---

## 🧪 Testování a verifikace

```bash
# Spuštění celé sady unit testů
venv/bin/python -m unittest discover -s tests

# Kontrola kompilace Pythonu a JavaScriptu
venv/bin/python -m py_compile web_server.py llama_module.py blender_connector.py code_validator.py
node --check web_ui/script.js
```

---

## 📄 Licence

Tento projekt je licencován pod licencí **MIT** — podrobnosti naleznete v souboru [LICENSE](LICENSE).

**Autor a hlavní architekt:** Vítězslav Koneval (*Polygon Beater*)  
**GitHub:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)
