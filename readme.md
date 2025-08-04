# 🤖 Offline Czech Voice Assistant

Welcome! This is an AI voice assistant designed to operate **completely offline**, utilizing local tools and models, with a specific focus on the **Czech language**.

## Key Features

* **100% Offline:** No data ever leaves your computer. All operations are processed locally.
* **Czech Language:** The assistant is built from the ground up for the Czech language—from speech transcription to response generation.
* **Wake-Word Detection:** It listens for a custom keyword (e.g., "computer") and activates without needing a button press.
* **Voice Activity Detection (VAD):** Intelligently trims silence from recordings, which speeds up and improves the accuracy of transcription.
* **Open-Source:** The entire project is built on publicly available tools.

## Technologies Used

| Component                  | Tool                                                              | Description                                                                    |
| :------------------------- | :---------------------------------------------------------------- | :----------------------------------------------------------------------------- |
| **Response Generation (LLM)** | [Llama.cpp](https://github.com/ggerganov/llama.cpp)               | For efficiently running large language models (GGUF format) on standard hardware. |
| **Text-to-Speech (TTS)** | [Coqui TTS](https://github.com/coqui-ai/TTS)                      | For high-quality and natural-sounding Czech voice synthesis.                   |
| **Wake-Word Detection** | [Picovoice Porcupine](https://github.com/Picovoice/porcupine)     | For reliable and low-resource hands-free activation.                           |
| **Speech-to-Text (STT)** | [OpenAI Whisper](https://github.com/openai/whisper)               | For accurate offline transcription of the Czech language.                      |
| **Voice Activity Detection** | [Silero VAD](https://github.com/snakers4/silero-vad)              | For real-time separation of speech from silence.                               |

## How It Works

The entire process, from addressing the assistant to its response, occurs in several steps:

1.  **Wake-Word Detection:** `audio.py` continuously listens using `Picovoice Porcupine`. Once it hears the keyword, it triggers the next step.
2.  **Command Recording:** After activation, `audio.py` uses `Silero VAD` to detect speech, and the recording automatically stops when the user finishes speaking.
3.  **Speech-to-Text (STT):** The recording is passed to `stt_module.py`, which uses `OpenAI Whisper` to transcribe the spoken words into text.
4.  **Response Generation (LLM):** The transcribed text is sent to `llama_module.py`. It first checks for simple math expressions. If none are found, it generates a response using `Llama.cpp`.
5.  **Text-to-Speech (TTS):** The generated text response is passed to `tts_module.py`, which uses `Coqui TTS` to convert the text into audio and play it back.

## 🚀 Getting Started

### Prerequisites
* [Python 3.10+](https://www.python.org)
* [FFmpeg](https://ffmpeg.org)
* [Git](https://git-scm.com)
* A [Picovoice Account](https://console.picovoice.ai/) for a free access key.
* A Czech-compatible LLaMA model in GGUF format.

### Installation
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Polygonbeater/ai-assistant-voice-cs.git](https://github.com/Polygonbeater/ai-assistant-voice-cs.git)
    cd ai-assistant-voice-cs
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### 📥 Downloading Models
Models are not included due to their size. Download them manually and place them in the `models/` directory.

* **LLaMA Model:**
    * Download a GGUF model (e.g., `mistral-7b-instruct-v0.2.Q4_K_M.gguf`) from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF).
    * Place the downloaded file in the `models/` folder.

* **Picovoice Porcupine Wake-Word:**
    * Obtain your free access key from [Picovoice Console](https://console.picovoice.ai/).
    * Download the `.ppn` file for your desired wake-word and OS from the [Porcupine GitHub repository](https://github.com/Picovoice/porcupine/tree/master/resources/keyword_files).
    * Place the `.ppn` file in the `models/` folder.

* **Coqui TTS & Silero VAD:**
    * These models will be downloaded automatically on the first run.

### 🎨 Configuration
Create a `config.json` file and populate it with your settings.

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
* **audio**: Audio device settings (`-1` for default).
* **silero_vad**: Voice activity detection parameters.

### 🏃‍♂️ Running the Assistant
Run the script. It will prompt for microphone selection on the first run.
```bash
python3 main.py
```

### 📁 Project Structure
```
.
├── 🐍 Core Logic
│   ├── main.py              # Main application entry point and orchestration
│   ├── audio.py             # Handles audio input, wake-word, and VAD
│   ├── stt_module.py        # Speech-to-Text (Whisper) wrapper
│   ├── llama_module.py      # Large Language Model (Llama.cpp) wrapper
│   └── tts_module.py        # Text-to-Speech (Coqui TTS) wrapper
│
├── ⚙️ Configuration & Data
│   ├── config.json          # Main configuration for all modules
│   ├── requirements.txt     # Python package dependencies
│   └── models/              # Directory for storing AI models (not in git)
│
├── 🛠️ Utilities
│   └── list_tts_models.py   # Utility script to list available TTS models
│
└── 📖 Documentation
    ├── LICENSE              # Project's MIT License
    └── README.md            # This documentation file
```

### 🗺️ Future Plans & Vision
* **Blender Integration:** Generate `bpy` scripts for voice-controlled 3D scenes.
* **Advanced Programming Assistance:** Integrate with editors like Neovim for code generation.
* **Workflow Automation:** Automate tasks like file management and app control.

### 👋 Contributing
Contributions are welcome! If you have an idea for an improvement or a new feature, feel free to fork the repository and submit a pull request.

1.  Fork the Project.
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the Branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

### 💖 Credits
Created by [Vítězslav Koneval](https://github.com/Polygonbeater).  
Built with passion for the Czech language ❤️🇨🇿

### ⚖️ License
Licensed under the [MIT License](https://github.com/Polygonbeater/ai-assistant-voice-cs/blob/main/LICENSE). Copyright (c) 2025 Polygonbeater.

