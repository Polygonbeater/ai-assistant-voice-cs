# 🧠 Czech Voice Assistant using Local LLM & TTS

This is a Czech-speaking voice assistant using only **offline local tools**, powered by:

- 🦙 [llama.cpp](https://github.com/ggerganov/llama.cpp) (e.g. csMPT7B)
- 🐸 [Coqui TTS](https://github.com/coqui-ai/TTS) for Czech text-to-speech
- 📢 [Picovoice Porcupine](https://github.com/Picovoice/porcupine) for wake-word detection
- 🎞️ Whisper (OpenAI) for speech-to-text (offline via whisper.cpp or faster-whisper)

## 🔧 Features

- Czech-language voice commands
- Fully offline (no cloud APIs)
- Wake-word detection ("Polygon")
- Uses VAD (voice activity detection) to trim silence
- Whisper for speech transcription
- llama.cpp for LLM response
- Coqui TTS for voice output

---

## 📖 Usage

Clone the repo:

```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `config.yaml` file (see `config_example.yaml` for structure).

Run the assistant:

```bash
python3 ai_assistant.py
```

---

## ⚡ Dependencies

You will need:

- [Python 3.10+](https://www.python.org)
- [FFmpeg](https://ffmpeg.org)
- [Git](https://git-scm.com)
- Picovoice Porcupine SDK
- A Czech-compatible [LLaMA model in GGUF format](https://huggingface.co/TheBloke/csMPT-7B-v2-GGUF)
- A Czech Coqui TTS model (e.g. `tts_models/cs/cv-corpus-11-0/cs-mlt`)

---

## 🎨 Configuration

Edit `config.yaml`:

```yaml
audio:
  rate: 16000
  device: null
  silence_duration: 1.0
  max_recording_duration: 10

porcupine:
  keyword_path: /home/user/porcupine-env/Polygon_en_linux_v3_0_0/Polygon_en_linux_v3_0_0.ppn
  access_key: "YOUR_ACCESS_KEY"

tts:
  model_name: "tts_models/cs/cv-corpus-11-0/cs-mlt"
```

---

## 📁 Project Structure

```
ai-assistant-voice-cs/
├── ai_assistant.py      # Main loop (wake word + VAD + logic)
├── config.yaml          # Configuration file (wake word path, rate, etc.)
├── audio.py             # Wake word and audio recording
├── whisper.py           # Speech-to-text wrapper
├── llama.py             # LLaMA model wrapper
├── tts.py               # TTS (Coqui) wrapper
├── .gitignore
└── README.md
```

---

## 🧳 Credits

Created by [Vítězslav Koneval](https://github.com/Polygonbeater)

Built with love for the Czech language ❤️🇨🇿

---

## ✉ Feedback

Feel free to open issues or contribute with PRs!

---

## ⚖️ License

This project is open-source under the MIT license.

