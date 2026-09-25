# 🤖 Polygon Beater AI Assistant

A modern, fully local AI assistant focused on the **Czech language**, privacy, and high productivity. It combines offline inference of Large Language Models (GGUF), a complete voice stack (Wake-Word, VAD, Whisper STT, Coqui TTS), in-depth document analysis, and optional live web data verification.

---

## 🌟 Key Features

* **100% Privacy & Local Operation:** Data never leaves your device. Inference runs locally via the optimized `llama.cpp` engine.
* **Modern Dark Interface (GUI):**
  * Clean sidebar for managing, searching, and viewing conversation history.
  * Smooth, real-time token streaming.
  * Markdown formatting support (headings, bullets, bold text with consistent line spacing).
  * Interactive, clickable web links that open directly in your browser.
* **🌐 Intelligent Online Mode:**
  * One-click activation for online research.
  * Direct integration of live feeds from ČT24 and Google News RSS.
  * Automatic article cleaning (`trafilatura`) and context delivery with timestamps and sources.
* **📄 Document Analysis (RAG):**
  * Instant summarization and querying over your own text files.
* **🧠 Analytical Methodologies & Presets:**
  * Integrated frameworks for Assumption Audits and structured expertise.
* **🎙️ Complete Voice Ecosystem:**
  * **Wake-Word Detection:** Hands-free activation via a keyword.
  * **Voice Activity Detection (VAD):** Silero VAD for silence trimming.
  * **Speech-to-Text (STT):** OpenAI Whisper optimized for Czech.
  * **Text-to-Speech (TTS):** Natural voice output via Coqui TTS.

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone [https://github.com/Polygonbeater/ai-assistant-voice-cs.git](https://github.com/Polygonbeater/ai-assistant-voice-cs.git)
cd ai-assistant-voice-cs
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
