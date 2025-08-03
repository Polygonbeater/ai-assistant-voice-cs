# 🤖 Offline Czech Voice Assistant

Welcome! This is an AI voice assistant designed to operate **completely offline**, utilizing local tools and models, with a specific focus on the **Czech language**.

The assistant leverages the following technologies and models:

-   🧠 **LLM:** [llama.cpp](https://github.com/ggeranov/llama.cpp) for response generation, utilizing models in the GGUF format (e.g., a Mistral-7B model).
-   🗣️ **TTS:** [Coqui TTS](https://github.com/coqui-ai/TTS) for high-quality Czech text-to-speech.
-   👂 **Wake-Word:** [Picovoice Porcupine](https://github.com/Picovoice/porcupine) for hands-free activation using a custom keyword.
-   🎙️ **STT:** [Whisper](https://openai.com/research/whisper) (an offline version like `whisper.cpp` or `faster-whisper`) for accurate speech-to-text transcription.

---

## ✨ Key Features

-   **Fully Offline:** No internet connection or cloud APIs are required.
-   **Czech Language Support:** The assistant understands, processes, and responds in Czech.
-   **Wake-Word Detection:** Activates upon hearing a configurable voice command.
-   **VAD:** Utilizes Voice Activity Detection to trim silent periods from recordings, improving efficiency.
-   **Open-Source:** Built entirely with open-source tools and frameworks.

---

## 🚀 Getting Started

Follow these steps to get the assistant up and running.

### Prerequisites

-   [Python 3.10+](https://www.python.org)
-   [FFmpeg](https://ffmpeg.org)
-   [Git](https://git-scm.com)
-   Picovoice Porcupine SDK (requires an access key).
-   A Czech-compatible LLaMA model in [GGUF format](https://huggingface.co/TheBloke/csMPT-7B-v2-GGUF).
-   A Czech Coqui TTS model (e.g., `tts_models/cs/cv/vits`).

### Installation

1.  **Clone the repository:**

    ```bash
    git clone [https://github.com/Polygonbeater/ai-assistant-voice-cs.git](https://github.com/Polygonbeater/ai-assistant-voice-cs.git)
    cd ai-assistant-voice-cs
    ```

2.  **Install dependencies:**

    The project relies on a number of key Python packages, including:
    * `llama_cpp_python`: For the LLM.
    * `openai-whisper`: For Speech-to-Text.
    * `TTS`: For Text-to-Speech.
    * `pvporcupine`: For wake-word detection.
    
    To install all dependencies, run:
    
    ```bash
    pip install -r requirements.txt
    ```

### 📥 Downloading Models

The AI models required for this project are not included in the repository due to their large size. Please download them manually and place them in the correct directories.

* **LLaMA Model:**
    * Download a compatible GGUF model, for example, `mistral-7b-instruct-v0.2.Q4_K_M.gguf`, from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/blob/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf).
    * Place the downloaded file into the `models/` directory.

* **Picovoice Porcupine Wake-Word:**
    * You need to obtain a Picovoice Porcupine access key from the [Picovoice Console](https://console.picovoice.ai/).
    * Download the Porcupine model file (`.ppn`) for your chosen wake-word and operating system from the Picovoice Porcupine GitHub repository. For a standard model, look in the `lib/common/` directory.
    * Place the downloaded `.ppn` file into the `models/` directory, and update the `porcupine` section in your `config.json` file accordingly.

* **Coqui TTS:**
    * The Coqui TTS model will be downloaded automatically the first time you run the assistant.

### 🎨 Configuration

Create a `config.json` file. The structure should be as follows:

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