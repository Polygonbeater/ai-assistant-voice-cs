# 🇨🇿 Czech Voice Assistant (Offline)

This is a fully local Czech-speaking voice assistant that responds to custom wake words and processes voice commands using the following stack:

- 🗣️ Wake word detection: **Porcupine** (custom-trained "Polygon")
- 🔊 Voice recording: VAD (Voice Activity Detection)
- 🧠 Speech-to-text: **Whisper** (OpenAI) – local transcription
- 💬 Text generation: **LLaMA.cpp** (e.g. csMPT-7B GGUF model)
- 🔈 Text-to-speech: **Coqui TTS** (Czech voice synthesis)

---

## ✅ Features

- Offline operation – no cloud services needed
- Czech language supported end-to-end
- Customizable wake word and commands
- Easily extendable (e.g. to control smart home or Blender)

---

## 📦 Requirements

Install Python dependencies:

```bash
pip install -r requirements.txt

