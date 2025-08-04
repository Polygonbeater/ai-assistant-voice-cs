# 🤖 Offline Czech Voice Assistant

Welcome! This is an AI voice assistant designed to operate **completely offline**, utilizing local tools and models, with a specific focus on the **Czech language**.

## Technologies & Key Features

### Technologies Used
* 🧠 **LLM:** [llama.cpp](https://github.com/ggerganov/llama.cpp) for response generation, utilizing models in the GGUF format (e.g., [Mistral-7B](https://huggingface.co/mistralai/Mixtral-8x7B-v0.1)).
* 🗣️ **TTS:** [Coqui TTS](https://github.com/coqui-ai/TTS) for high-quality Czech text-to-speech.
* 👂 **Wake-Word:** [Picovoice Porcupine](https://github.com/Picovoice/porcupine) for hands-free activation using a custom keyword.
* 🎙️ **STT:** [Whisper](https://github.com/openai/whisper) (offline versions like [whisper.cpp](https://github.com/ggerganov/whisper.cpp) or [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) for accurate speech-to-text transcription.

### Key Features
* **Fully Offline:** No internet connection or cloud APIs required.
* **Czech Language Support:** Understands, processes, and responds in Czech.
* **Wake-Word Detection:** Activates on a configurable voice command.
* **VAD:** Utilizes Voice Activity Detection to trim silent periods from recordings.
* **Open-Source:** Built with open-source tools and frameworks.

## 🚀 Getting Started

### Prerequisites
* [Python 3.10+](https://www.python.org)
* [FFmpeg](https://ffmpeg.org)
* [Git](https://git-scm.com)
* [Picovoice Porcupine SDK](https://console.picovoice.ai/) (requires an access key)
* A Czech-compatible LLaMA model in GGUF format
* A Czech Coqui TTS model (e.g., `tts_models/cs/cv/vits`)

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
   cd ai-assistant-voice-cs
   ```

2. **Install dependencies:**
   Required Python packages:
   * `llama_cpp_python`: For LLM.
   * `openai-whisper`: For Speech-to-Text.
   * `TTS`: For Text-to-Speech.
   * `pvporcupine`: For wake-word detection.
   ```bash
   pip install -r requirements.txt
   ```

### 📥 Downloading Models
Models are not included due to size. Download manually:

* **LLaMA Model:**
  * Download a GGUF model (e.g., `mistral-7b-instruct-v0.2.Q4_K_M.gguf`) from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/blob/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf).
  * Place in `models/`.

* **Picovoice Porcupine Wake-Word:**
  * Obtain an access key from [Picovoice Console](https://console.picovoice.ai/).
  * Download the `.ppn` file for your wake-word and OS from [Picovoice Porcupine GitHub](https://github.com/Picovoice/porcupine/tree/master/lib/common).
  * Place in `models/` and update `config.json`.

* **Coqui TTS:**
  * Automatically downloaded on first run.

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

* **porcupine**: Wake-word engine settings (access key, model path, keyword, sensitivity).
* **whisper**: Speech-to-text model and language.
* **llama**: LLaMA model path and token limit.
* **tts**: Text-to-speech model and GPU usage.
* **audio**: Audio device settings.
* **silero_vad**: Voice activity detection parameters.

### 🏃‍♂️ Running the Assistant
Run the script (prompts for microphone selection on first run):
```bash
python3 main.py
```

## 📁 Project Structure
* `main.py`: Main loop and core logic.
* `audio.py`: Audio recording and wake-word detection.
* `stt_module.py`: Speech-to-text wrapper.
* `llama_module.py`: LLaMA model wrapper.
* `tts_module.py`: Text-to-speech wrapper.
* `list_tts_models.py`: Utility script for listing TTS models.
* `config.json`: Configuration file.
* `models/`: Directory for AI models.
* `requirements.txt`: Dependencies.
* `LICENSE`: License file.
* `README.md`: This file.

## 🗺️ Future Plans & Vision
* **Blender Integration:** Generate `bpy` scripts for voice-controlled 3D scenes in Blender.
* **Advanced Programming Assistance:** Integrate with editors like Neovim for code generation, debugging, and refactoring.
* **General Workflow Automation:** Automate tasks like file management and app control via voice.

Contributions and ideas are welcome!

## 💖 Credits
Created by [Vítězslav Koneval](https://github.com/Polygonbeater).  
Built with passion for the Czech language ❤️🇨🇿

## ⚖️ License
Licensed under the [MIT License](https://github.com/Polygonbeater/ai-assistant-voice-cs/blob/main/LICENSE).