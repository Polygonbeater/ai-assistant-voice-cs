# Offline Czech Voice Assistant

Welcome! This is an AI voice assistant designed to operate completely offline, utilizing local tools and models, with a specific focus on the Czech language.

## Technologies & Key Features

### Technologies Used
- **LLM (llama.cpp):** Response generation with GGUF models (e.g., Mistral-7B).
- **TTS (Coqui TTS):** High-quality Czech text-to-speech.
- **Wake-Word (Picovoice Porcupine):** Hands-free activation with custom keyword.
- **STT (Whisper):** Accurate offline speech-to-text transcription.

### Key Features
- **Fully Offline:** No internet or cloud APIs required.
- **Czech Language Support:** Understands, processes, and responds in Czech.
- **Wake-Word Detection:** Activates on voice command.
- **VAD:** Trims silence from recordings for efficiency.
- **Open-Source:** Built with open-source tools.

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- FFmpeg
- Git
- Picovoice Porcupine SDK (with access key)
- Czech LLaMA model (GGUF format)
- Czech Coqui TTS model

### Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs
pip install -r requirements.txt
```

Key packages:
- `llama_cpp_python`: For LLM.
- `openai-whisper`: For Speech-to-Text.
- `TTS`: For Text-to-Speech.
- `pvporcupine`: For wake-word detection.

### 📥 Downloading Models
Models are not included due to size. Download manually:
- **LLaMA Model:** Get a GGUF model (e.g., `mistral-7b-instruct-v0.2.Q4_K_M.gguf`) from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/blob/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf) and place in `models/`.
- **Picovoice Porcupine:** Obtain access key from [Picovoice Console](https://console.picovoice.ai/). Download `.ppn` file for your keyword/OS from [Porcupine GitHub](https://github.com/Picovoice/porcupine) and place in `models/`.
- **Coqui TTS:** Auto-downloads on first run.

### 🎨 Configuration
Create `config.json`:
```json
{
  "porcupine": {
    "access_key": "YOUR_PICOVOICE_ACCESS_KEY",
    "model_path": "models/porcupine_params.pv",
    "keyword": "computer",
    "sensitivity": 0.7
  },
  "whisper": {
    "model": "medium",
    "language": "cs"
  },
  "llama": {
    "model": "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
    "max_tokens": 150
  },
  "tts": {
    "model_name": "tts_models/cs/cv/vits",
    "gpu": false
  },
  "audio": {
    "device_index": -1,
    "wake_word_device_index": -1,
    "max_recording_time": 15
  },
  "silero_vad": {
    "sample_rate": 16000,
    "threshold": 0.3,
    "silence_duration_ms": 2000
  }
}
```

**Key Descriptions:**
- **porcupine:** Wake-word engine settings.
- **whisper:** Speech-to-text model and language.
- **llama:** LLaMA model path and token limit.
- **tts:** Text-to-speech model and GPU usage.
- **audio:** Audio device settings.
- **silero_vad:** Voice activity detection parameters.

### 🏃‍♂️ Running the Assistant
Run the script. Select microphone on first run:
```bash
python3 main.py
```

## 📁 Project Structure
- `main.py`: Main loop and logic.
- `audio.py`: Audio processing and wake-word detection.
- `stt_module.py`: Speech-to-text wrapper.
- `llama_module.py`: LLaMA model wrapper.
- `tts_module.py`: Text-to-speech wrapper.
- `list_tts_models.py`: Lists TTS models.
- `config.json`: Configuration file.
- `models/`: Directory for AI models.
- `requirements.txt`: Dependencies.
- `LICENSE`: License file.

## 🗺️ Future Plans & Vision
- **Blender Integration:** Generate `bpy` scripts for voice-controlled 3D scenes.
- **Advanced Programming Assistance:** Integrate with editors like Neovim for code generation and debugging.
- **Workflow Automation:** Voice-controlled file management and app control.

## About
Created by [Vítězslav Koneval](https://github.com/Polygonbeater).  
Licensed under the [MIT License](https://github.com/Polygonbeater/ai-assistant-voice-cs/blob/main/LICENSE).  
Built with passion for the Czech language ❤️🇨🇿