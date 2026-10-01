# 🤖 Polygon Beater AI Assistant

🇬🇧 **English** | [🇨🇿 Česky](README.cs.md)

---

A modern, high-performance, and **100% local voice AI assistant** optimized for the **Czech language**, strict privacy, ultra-low latency on multi-core CPUs, and direct **3D modeling automation in Blender**.

The project integrates offline Large Language Model (GGUF) inference, state-of-the-art speech-to-text (**Faster-Whisper** with `int8` quantization), zero-latency real-time voice synthesis (**Pipelined Streaming TTS**), non-blocking **hands-free wake word detection** (openWakeWord), and a bidirectional TCP automation bridge for the Blender API (`bpy`).

---

## 🌟 Key Features

### ⚡ 1. Maximum CPU-First Performance & Complete Privacy
* **Zero Cloud Dependencies & No API Keys:** All data, voice recordings, and text chat sessions remain strictly on your local machine.
* **Dynamic Physical CPU Core Detection:** Using `psutil`, the engine automatically detects the exact number of **physical CPU cores** (excluding SMT / hyperthreading threads) and dynamically assigns optimal worker threads (`n_threads`). This prevents CPU thrashing, thread starvation, and context-switching overhead.
* **Optimized llama.cpp Engine:** Tuned specifically for CPU inference with `use_mmap=True`, `mlock` safely disabled to adhere to OS resource limits, `n_batch=512`, and dynamic context sizing (`n_ctx`) customized for **Qwen 2.5** and **GLM-4** models to avoid unnecessary RAM consumption.

### 🎙️ 2. Next-Generation Voice Stack
* **Faster-Whisper (int8 CTranslate2):** Fully migrated from standard Whisper to CTranslate2. With 8-bit quantization (`int8`), Czech transcription executes up to 4× faster on CPU while retaining full transcription accuracy, deterministic greedy decoding (`beam_size=1`, `temperature=0.0`), and aggressive silence/hallucination filtering.
* **Pipelined Streaming TTS (Sentence-Level Chunking):** The LLM inference loop yields text in cohesive sentence and punctuation-based chunks (`extract_sentence_chunks`). A dedicated asynchronous audio worker (**Coqui TTS** + **PyAudio**) immediately synthesizes and begins streaming playback of the first sentence while the LLM continues generating subsequent tokens in the background.
* **Instant Barge-in Interruption:** User speech detection or manual abort actions immediately clear audio queues and terminate synthesis without lag.
* **Hands-Free Wake Word Mode (openWakeWord):** Runs continuously in an efficient background daemon thread. Upon detecting the wake phrase (*"Hey Jarvis"*), an auditory activation chime sounds and voice recording with Silero VAD begins automatically.
* **Silero VAD:** Advanced Voice Activity Detection precisely trims leading/trailing silence and terminates recording instantly once the user finishes speaking.

### 🎨 3. Voice-Driven Blender 3D Automation (TCP Bridge)
* **Natural Language to Blender Python (bpy):** With a specialized system prompt, the assistant detects 3D viewport requests (e.g., *"vycentruj pivoty a aplikuj scale všem vybraným meshům"*) and generates pure, executable Python code with no markdown filler.
* **Reliable TCP Socket Architecture:** Communicates with Blender over a local TCP socket (`127.0.0.1:9876`).
* **Thread-Safe Main Thread Execution:** The receiver script inside Blender (`blender_receiver.py`) utilizes Blender's native `bpy.app.timers` API. Code received over the network is executed safely in Blender's main UI/graphics thread, eliminating crashes, race conditions, and GPU context corruption.
* **Instant 3D Viewport Redraw:** Following code execution, all active 3D viewports are automatically tagged for redraw (`tag_redraw`), and the assistant confirms the result via both voice and chat.

### 🖥️ 4. Modern Desktop GUI & Analytical Tooling
* **Dark-Themed Interface (CustomTkinter / Tkinter):** Sleek, distraction-free GUI with a persistent sidebar for conversation history (`sessions/`), full-text search, and session management.
* **Rich Markdown & Clickable Hyperlinks:** Full Markdown rendering (headings, bullet points, code blocks) with interactive browser-ready links.
* **Online Research Mode (Web Search & RSS):** Optional real-time internet verification pulling live RSS feeds (ČT24, Google News) with article cleanup via `trafilatura`.
* **Document Analysis (RAG):** Fast upload, text extraction, and contextual querying of local text and PDF documents (`document_service.py`).
* **Analytical Prompt Frameworks:** Built-in expert presets (including *Assumption Audit* for structured hypothesis stress-testing).

---

## 📋 System Requirements

* **Operating System:** Linux (tested on Ubuntu, Debian, Manjaro, Arch), macOS, or Windows (WSL2 recommended).
* **Python:** 3.10, 3.11, or 3.12.
* **Processor:** Modern multi-core CPU (minimum 4 physical cores recommended, e.g., AMD Ryzen or Intel Core i5/i7/i9).
* **RAM:** Minimum 16 GB of system RAM (for running 7B/9B GGUF models smoothly).
* **3D Software:** Blender 3.0+ (optional, required for 3D automation features).

---

## ⚙️ Step-by-Step Installation

### 1. Clone the Repository & Setup Virtual Environment
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs

python3 -m venv venv
source venv/bin/activate
```

### 2. Install System Dependencies (Linux)
PortAudio and FFmpeg development headers are required for low-latency microphone capture and audio synthesis:
```bash
sudo apt update
sudo apt install -y python3-dev portaudio19-dev ffmpeg
```

### 3. Install Python Dependencies
Install all project requirements into your virtual environment:
```bash
pip install -r requirements.txt
```

> **Key highlighted packages in `requirements.txt`:**
> * `faster-whisper` – Accelerated speech recognition via CTranslate2 (with int8 quantization).
> * `openwakeword` & `onnxruntime` – Ultra-lightweight offline wake word detection engine.
> * `psutil` – Dynamic physical CPU core topology inspection.
> * `llama-cpp-python` – High-performance local GGUF inference runtime.
> * `TTS` (Coqui TTS) & `PyAudio` – Local neural speech synthesis with Czech voice models.

### 4. Download LLM Model & Configure
Place any instruction-tuned GGUF model with strong Czech language capabilities (e.g., *Qwen 2.5 7B Instruct* or *GLM-4 9B Chat*) into the `models/` directory:
```bash
mkdir -p models
# Example: copy or move your model into models/glm-4-9b-chat.Q4_K_M.gguf
```

Initialize your local configuration:
```bash
cp config.example.json config.json
```

Verify or customize parameters in `config.json`:
```json
{
  "whisper": {
    "model": "medium",
    "language": "cs"
  },
  "llama": {
    "model": "models/glm-4-9b-chat.Q4_K_M.gguf",
    "max_tokens": 150
  },
  "tts": {
    "model_name": "tts_models/cs/cv/vits",
    "gpu": false
  },
  "audio": {
    "device_index": -1,
    "max_recording_time": 15
  },
  "silero_vad": {
    "sample_rate": 16000,
    "threshold": 0.3,
    "silence_duration_ms": 2000
  },
  "wakeword": {
    "enabled": false,
    "model": "hey_jarvis",
    "threshold": 0.5
  },
  "blender": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 9876
  }
}
```

---

## 🚀 User Guide

### 1. Launching the Assistant
Activate your virtual environment and start the graphical interface:
```bash
source venv/bin/activate
python gui.py
```

---

### 2. Hands-Free Wake Word Mode
Hands-free mode enables complete voice-activated control without having to manually press the recording button.

1. **Enable in GUI:** Check the **`🎙️ Hands-free (Hey Jarvis)`** toggle button in the bottom control bar.
2. **Background Listening:** The `openWakeWord` daemon starts processing live audio frames in a background thread. The status indicator notifies you that the assistant is waiting for the wake word.
3. **Trigger:** Clearly speak the wake phrase:
   > *"Hey Jarvis"*
4. **Chime Confirmation:** The assistant plays a brief melodic audio chime confirming detection and immediately opens the recording stream.
5. **Speak Your Command:** State your question or instruction (e.g., *"Jaký je rozdíl mezi procedurálním a parametrickým modelováním?"*).
6. **Automatic Voice Activity Detection:** As soon as you stop speaking, Silero VAD detects the end of speech, finishes capture, transcribes audio via Faster-Whisper, and begins streaming the synthesized spoken reply.
7. **Disable:** Uncheck the Hands-free checkbox at any time to return to manual push-to-talk mode.

---

### 3. Blender 3D Automation (Step-by-Step)
Control Blender using spoken or typed natural language commands. The assistant converts instructions into valid Blender Python (`bpy`) scripts and executes them remotely.

#### Step A: Launch the Receiver in Blender
1. Open **Blender** (version 3.0 or newer) and load your project or a new scene.
2. Switch to the **Scripting** workspace tab (or open a **Text Editor** window).
3. Click **Open** and select `blender_receiver.py` from the project's root directory.
4. Click ▶ **Run Script** (or press `Alt + P`).
5. Check Blender's system console (*Window -> Toggle System Console*). You should see:
   ```text
   ✅ [AI-Blender] TCP Server naslouchá na 127.0.0.1:9876...
   ```
   > 💡 *The receiver runs as a non-blocking TCP socket server and delegates code execution to Blender's main thread via `bpy.app.timers`. Blender's UI remains completely responsive with zero freezing.*

#### Step B: Issue a Voice or Text Command
In the assistant's interface (via voice or chat input), issue any 3D operation command in Czech:
* *"Vytvoř kruh z osmi kostek a dej každé náhodnou výšku."* *(Create a circle of 8 cubes with randomized heights.)*
* *"Vycentruj pivoty všem vybraným objektům a nastav jim jednotný scale."* *(Center pivots for all selected objects and apply scale.)*
* *"Přidej do scény bodové světlo nad vybraný objekt a zbarvi ho do tepla."* *(Add a warm point light above the selected object.)*
* *"Nastav všem označeným meshům hladké stínování (shade smooth)."* *(Set shade smooth for all selected meshes.)*

#### Step C: Execution & Viewport Redraw
1. The assistant automatically recognizes the request as a Blender operation.
2. The LLM generates clean, targeted `bpy` code.
3. The script is dispatched over the local TCP socket (`port 9876`).
4. Blender executes the code safely, forces a redraw of all active 3D viewports (`tag_redraw`), and returns execution status to the assistant.
5. The assistant announces completion via both audio and text.

#### Step D: Stopping the Server in Blender
To shut down the background listener in Blender, execute the following in the Blender Text Editor:
```python
import blender_receiver
blender_receiver.stop_server()
```
The server will also close automatically when Blender exits.

---

## 📁 Project Architecture

| File / Directory | Purpose & Functionality |
| :--- | :--- |
| `gui.py` | Desktop GUI (Tkinter) with streaming text rendering, conversation history, and Hands-free toggle. |
| `llama_module.py` | LLM inference wrapper (`llama.cpp`), physical CPU core detection, sentence chunking, and Blender prompt routing. |
| `stt_module.py` | Accelerated speech-to-text using **Faster-Whisper** with `int8` quantization and silence filtering. |
| `tts_module.py` | Asynchronous speech synthesis using **Coqui TTS**, pipelined streaming player (`TTSStreamPlayer`) with barge-in support. |
| `audio.py` | Low-level microphone capture, Silero VAD filtering, auditory chime generator, and `openWakeWord` listener daemon. |
| `blender_connector.py` | Client TCP socket communicator for dispatching generated Python code to Blender. |
| `blender_receiver.py` | Standalone receiver script executed inside Blender using `bpy.app.timers`. |
| `web_search.py` | Live online research, RSS parsing (ČT24, Google News), and article extraction with `trafilatura`. |
| `document_service.py` | Local document parsing and RAG question answering over text and PDF files. |
| `history_repository.py` | Persistent JSON conversation session storage in the `sessions/` directory. |
| `prompts/` | Analytical framework system prompts (e.g., *Assumption Audit*). |

---

## 🛠️ Troubleshooting

* **Microphone error or no audio detected:**
  * Check your input device ID. In the GUI, specify the audio device index in the `Vstup:` field (leave `-1` for system default).
* **Hands-free does not respond to wake phrase:**
  * Ensure the wake phrase (*"Hey Jarvis"*) is spoken clearly. You can adjust detection sensitivity in `config.json` under `"wakeword": { "threshold": 0.45 }`.
* **Blender connection error (`Blender TCP spojení selhalo`):**
  * Verify that you executed `blender_receiver.py` inside Blender using `Run Script` (`Alt + P`).
  * Ensure the port (`9876`) matches in both `config.json` and `blender_receiver.py`.
* **High RAM usage during model loading:**
  * Context size (`n_ctx`) is computed dynamically based on the model. For systems with 16 GB RAM, 7B/9B models with `Q4_K_M` quantization are strongly recommended.

---

## 💖 Author & License

* **Author:** Vítězslav Koneval ([Polygon Beater](https://github.com/Polygonbeater))
* **License:** Released under the open-source [MIT License](LICENSE).
