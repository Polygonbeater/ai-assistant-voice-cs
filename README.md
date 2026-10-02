# 🎙️ AI Assistant Voice CS: Local Voice Companion & 3D Technical Director

🌍 **[🇨🇿 Přejít na Českou verzi (Czech Version)](README.cs.md)**

> **100% Local, Private, Voice-Controlled AI Assistant for Czech & English with Direct 3D Automation, Procedural Modeling, and Post-Processing in Blender 4.2.1 LTS.**  
> *Producing explicit 3D geometry — clean Quad topology, unwrap UVs, and baked PBR materials ready for game engines and VFX.*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python)](https://www.python.org/)
[![Blender 4.2.1 LTS](https://img.shields.io/badge/Blender-4.2.1%20LTS-orange.svg?logo=blender)](https://www.blender.org/)
[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-176%20Passed%20%28100%25%29-brightgreen.svg)]()
[![Tools](https://img.shields.io/badge/Registered%20Tools-20%20Production%20Tools-purple.svg)]()
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%2F%20Zero%20Cloud-success.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

**Lead Architect & Author:** Vítězslav Koneval (*Polygon Beater*)  
**Repository:** [github.com/Polygonbeater/ai-assistant-voice-cs](https://github.com/Polygonbeater/ai-assistant-voice-cs)

---

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
│ • Instant Barge-in: Immediate interruption on user speech │
└────────────────────────────────────────────────────────┘
```

### 👂 How the Assistant Hears (Whisper)
* **Faster-Whisper (CTranslate2 int8):** Rather than relying on slow, unoptimized standard models, our transcription uses 8-bit quantization with an optimized C++ execution engine. Transcription runs up to 4× faster while retaining flawless grammatical accuracy.
* **Private Web UI voice input:** Microphone recordings are sent only to the local FastAPI `/api/stt/transcribe` endpoint and processed by Whisper; the browser's cloud-backed SpeechRecognition API is not used. The Whisper model loads on first use.
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
| **UV Unwrapping** | ❌ None | ✅ **Smart UV Project** | Clean texture space utilization |
| **Texture & Baking** | Raw unbaked vertex colors | **2048×2048 px** (`AI_Baked_Diffuse`) | 🎨 Crisp, standard Albedo map |
| **Material Setup** | Missing | **Principled BSDF** (`AI_PBR_Material`) | 💎 Full PBR rendering pipeline |

---

## 🧭 Section 4: Intellectual Modules & Strategic Frameworks (Expert Prompts V3.1 & Methodologies)

Beyond being a precision voice and 3D technical operator, the assistant integrates a sophisticated cognitive engine driven by **11 expert methodologies** for strategic analysis, risk management, and decision-making under uncertainty.

### 📚 Embedded Methodology Suite (`prompts/Advanced-Analytical-Prompts-main/`)

The repository includes a curated collection of executive-level analytical frameworks:
* **Taleb’s Methodology (Incerto):** Audits systems for Antifragility, Black Swan exposures, Via Negativa (eliminating systemic vulnerabilities), Convexity vs. Concavity payoffs, Skin in the Game accountability, and Pre-mortem failure analysis.
* **Cynefin Framework & OODA Loop:** Domain categorization (Simple, Complicated, Complex, Chaotic, Disordered) coupled with high-tempo Observe-Orient-Decide-Act cycles for hyper-dynamic operational environments.
* **Systems Thinking (Peter Senge) & Porter’s Five Forces:** Structural feedback loops (reinforcing vs. balancing loops mapped with Mermaid diagrams), system archetypes, leverage interventions, and competitive industry forces (rivalry, supplier/buyer power, substitute threats, entry barriers).
* **Design Thinking & Scenario Planning:** Human-centered innovation with Key Behavioral Indicators (KBIs), identification of critical uncertainties, trigger point signposts, and multi-timeline contingency planning.
* **Meta-Prompt for Comprehensive Strategic Analysis:** A unified executive protocol combining macro-environmental PESTLE, industry Porter, internal SWOT matrices, multi-criteria decision matrices, and ACH (Analysis of Competing Hypotheses).

### 🔍 Methodological Protocols for Deep Peer-Review (`prompts/frameworks/`)

For rigorous cross-examination of technical and creative tasks, the assistant draws upon dedicated analytical protocols:
* **[`advanced_assumption_audit.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/advanced_assumption_audit.md):** Red Team stress testing, forensic audits of hidden premises (categorizing statements into Facts, Hypotheses, and Dogmas), Popperian falsification criteria, and steelmanning counter-proposals before deconstruction.
* **[`auteur_visual_analysis.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/auteur_visual_analysis.md):** Deep semiotic and art-historical film deconstruction (mise-en-scène geometry, chiaroscuro/tenebrism lighting, camera movement, and historical iconographies from Caravaggio to Fritz Lang).
* **[`first_principles_technical.md`](file:///home/polygon/ai-assistant-voice-cs/prompts/frameworks/first_principles_technical.md):** First-principles technical deconstruction for Python systems and 3D graphics (matrix transformations, quaternion rotation mathematics, illegal state prevention, deterministic invariant proofs, and direct Blender BMesh vector memory operations).

### 🧠 Cognitive Integration with the AI Model

These frameworks function as an internal cognitive toolkit for the local LLM. Rather than relying on unstructured generative text, the assistant applies structured reasoning that:
1. **Eliminates cognitive biases** (confirmation bias, narrative fallacy, planning optimism, sunk cost fallacy).
2. **Enforces empirical falsifiability** through Analysis of Competing Hypotheses (ACH).
3. **Elevates responses** from generic chat dialogue to rigorous, boardroom-grade technical direction.

---

## 🖥️ Section 5: Modern Developer IDE & Context-Aware Workspace

The web interface has been engineered to match the ergonomics of high-end developer IDEs (such as VS Code and Cursor), optimized for maximum visual clarity, technical density, and 100% offline reliability.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 HEADER / STATUS BAR                                    │
│ [Status: Qwen 2.5]  [Blender: Connected]  [RAG: Offline]  [Knowledge Base] [Settings] │
├─────────────────┬──────────────────────────────────────┬───────────────────────────────┤
│  LEFT SIDEBAR   │            CHAT WORKSPACE            │      CONTEXT WORKSPACE        │
│ • Session Tree  │ • Markdown with Atom One Dark        │ ┌───────────────────────────┐ │
│ • Hard Delete   │ • Inline Code Execution & Copy       │ │ [3D]    [Research]  [Log] │ │
│ • Search Filter │ • Methodology Framework Selector     │ ├───────────────────────────┤ │
│ • Drag Resizer  │ • Prompt Bar (Whisper Mic + RAG Doc) │ │ Active Tab Pane & Cards   │ │
│                 │ • Streaming State & Instant Stop     │ │ (Inner Scroll & Resizers) │ │
└─────────────────┴──────────────────────────────────────┴───────────────────────────────┘
```

### 1. Developer IDE Aesthetics & Typography
* **Atom One Dark Syntax Highlighting:** Integrated via Highlight.js to render code blocks with precise token coloring that perfectly blends into the dark developer palette. Features single-click copy buttons with instant visual feedback.
* **100% Offline Lucide Vector Icons:** All UI controls (RAG, Web Tools, Presets, Actions, Viewport, Audio) utilize clean, inline SVG Lucide icons (`viewBox="0 0 24 24"`). Zero external font downloads, zero CDN tracking, and 100% functional in isolated air-gapped environments.
* **Multi-Directional Drag Resizers:**
  * **Horizontal sidebar resizing:** Smooth pointer-drag resizing for both left and right sidebars with clamped min/max boundaries and auto-persistence to `localStorage`.
  * **Vertical card height resizers:** Independent vertical dragging handles on every inspector card, respecting element-aware minimum heights (`min-height`) with internal card scrolling (`overflow-y: auto`).
* **Bilingual Localization (EN / CS):** Comprehensive language switcher (English by default, Czech fully supported) with complete translation coverage for all analytical methodologies, Blender tool actions, and settings.
* **Hard Delete Session Management:** Complete removal of chat sessions with full recursive directory cleanup from the local disk via `history_repository.delete_session()`.

### 2. Context-Aware Workspace (Tabbed Right Inspector)
The right inspector features a dynamic 3-mode tab switcher that adapts to the user's current workflow:
* 🧊 **3D Workspace (`tab-btn-3d`, Box icon):**
  * **Live Viewport Snapshot:** Direct capture of Blender's active viewport (`/api/blender/viewport-image`) with click-to-enlarge lightbox mode.
  * **Scene Metrics Dashboard:** Live telemetry showing object counts, active mesh name, polygon and vertex counts, watertight manifold verification, and armature bones.
  * **Quick 3D Command Deck:** One-click shortcuts for Viewport Inspection, Auto-Rig & Skinning, Mesh Doctor topology audit, Product Studio backdrop generation, and Procedural Brushed Metal shader creation.
* 🌐 **Research (`tab-btn-research`, Globe icon):**
  * **Live Web Research & Sources:** Real-time search query feed displaying clickable citation links and excerpt summaries extracted via DuckDuckGo and `trafilatura`.
  * **Semantic Memory (RAG) Chunks:** Live display of retrieved FAISS vector chunks with similarity match percentages (`% match`) and source document metadata.
  * **Knowledge Base Launcher:** Instant button to open the modal document manager for adding and reindexing technical PDFs and DOCX files.
* ⚡ **Agent Log (`tab-btn-agent`, Terminal icon):**
  * **Agent Workflow & Tool Traces:** Realtime timeline showing each step of the agent's reasoning loop (tool dispatch, RAG query, web search, analytical framework classification).
  * **Telemetric Console:** Low-level event log recording TCP socket packets, Blender timer execution, and background worker state.
* **Tab State Persistence:** The active inspector tab is remembered across restarts via `localStorage` (`polygon_active_right_tab`).

### 3. Security Hardening & Architectural Integrity
* **Strict Loopback Binding:** Both the FastAPI web backend (`127.0.0.1:8000`) and the Blender bridge socket (`127.0.0.1:9876`) bind exclusively to loopback addresses, completely blocking unauthorized network access from the local area network (LAN).
* **Robust SSE Stream Lifecycle:** Server-Sent Events (SSE) stream reader implements deterministic cancellation and lock release (`reader.cancel()`, `reader.releaseLock()`), ensuring that streaming flags (`state.isStreaming`), prompt inputs, and the "Thinking..." status indicator immediately reset to idle mode as soon as generation completes or stops.
* **Audio Watchdog & VAD Safety:** Whisper speech-to-text and Silero Voice Activity Detection incorporate strict recording timeouts and fallback abort controllers to eliminate lingering microphone capturing.
* **Thread-Safe Resource Allocation:** Coqui TTS audio synthesis and Llama.cpp inference execute within dedicated, thread-safe asynchronous workers.

### 4. Standalone Desktop Application (Click-and-Run Launcher)
* **Single-Window Desktop Mode:** Running `python main.py` or `python start_app.py` launches the FastAPI service and immediately spawns a native, clean desktop window (via Chromium `--app` mode or `pywebview`) without URL bars or browser tabs.
* **Unified Process Lifecycle:** Closing the application window automatically intercepts the window event and cleanly shuts down the background FastAPI/Uvicorn processes, leaving zero orphaned zombie tasks.

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

## 🖥️ Hardware Requirements

| Specification | Minimum | Recommended (Production) |
|---|---|---|
| **System RAM** | 16 GB | **32 GB+** |
| **GPU VRAM** | 8 GB (NVIDIA CUDA) | **12+ GB VRAM (NVIDIA RTX)** |
| **Target Workload** | Basic local LLM inference + lightweight Blender scenes | Smooth simultaneous execution of GGUF model, Faster-Whisper, TripoSR neural generation, and Blender viewport without Out-of-Memory (OOM) crashes |
| **Storage** | 10 GB free SSD space | High-speed NVMe SSD (fast weights & cache loading) |

---

## 💻 Technology Stack & Requirements

* **3D Software:** Blender 4.2.1 LTS (requires running `blender_receiver.py` in the Scripting tab).
* **Python:** 3.11 (recommended for maximum library ABI stability).
* **LLM Engine:** `llama-cpp-python` (quantized GGUF models: Qwen 2.5, GLM-4).
* **Voice Subsystem:** `faster-whisper`, `openwakeword`, `TTS` (Coqui TTS), `gruut`, `pyaudio`.
* **Vector Memory:** `faiss-cpu`, `sentence-transformers` (`all-MiniLM-L6-v2`).
* **AI 3D Inference:** `TripoSR`, `torch`, `torchvision`, `trimesh`, `pillow`, `rembg`.

---

## 🚀 Quick Start & Setup

### Option A: Automated One-Line Setup (Recommended for Linux)
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

chmod +x install.sh
./install.sh
```
*(Add `--with-tripo` to automatically compile TripoSR and torchmcubes for local GPU 3D reconstruction)*.

### Option B: Manual Step-by-Step Setup

#### 1. Clone & Prepare Virtual Environment
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

python3.11 -m venv venv
source venv/bin/activate
```

### 2. Install System Dependencies (Linux)
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev ffmpeg build-essential
```

> [!IMPORTANT]
> The `build-essential` package (providing gcc and g++ compilers) is strictly required to compile the C++ extension `torchmcubes` during TripoSR setup.

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

### 5. Launch the Assistant (Polygon Beater Desktop Experience)
```bash
# Launch Click-and-Run Desktop App / Web Interface (recommended)
python main.py

# Or launch standalone launcher
python start_app.py
```

## 👨‍💻 Author

* **Author:** **Vítězslav Koneval** (*Polygon Beater*)
* **Specialization:** AI 3D Technical Direction, Procedural Geometry, Local AI Architecture
* **GitHub:** [@Polygonbeater](https://github.com/Polygonbeater)

---

## 🤝 Contributing

Contributions from the 3D and AI community are warmly welcome! If you have ideas for new procedural geometry nodes, CAD generators, shader templates, or workflow automation for Blender:

1. **Fork the repository** and create your feature branch: `git checkout -b feature/amazing-blender-tool`
2. **Implement your tool** in `blender_receiver.py`, `blender_connector.py`, and register its schema in `llama_module.py`.
3. **Add unit tests** to maintain our 100% pass rate.
4. **Submit a Pull Request** — every contribution that expands the assistant's creative reach is valued!

---

## 📄 License

This project is open-source and released under the **MIT License** — you are free to use, modify, study, and distribute this software for personal, academic, or commercial projects.

Copyright (c) 2026 Vítězslav Koneval (*Polygon Beater*). All rights reserved.
