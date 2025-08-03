# **🤖 Offline Czech Voice Assistant**

Welcome\! This is an AI voice assistant designed to operate **completely offline**, utilizing local tools and models, with a specific focus on the **Czech language**.

The assistant leverages the following technologies and models:

* 🧠 **LLM:** [llama.cpp](https://github.com/ggerganov/llama.cpp) for response generation, utilizing models in the GGUF format (e.g., a Mistral-7B model).  
* 🗣️ **TTS:** [Coqui TTS](https://github.com/coqui-ai/TTS) for high-quality Czech text-to-speech.  
* 👂 **Wake-Word:** [Picovoice Porcupine](https://github.com/Picovoice/porcupine) for hands-free activation using a custom keyword.  
* 🎙️ **STT:** [Whisper](https://openai.com/research/whisper) (an offline version like whisper.cpp or faster-whisper) for accurate speech-to-text transcription.

## **✨ Key Features**

* **Fully Offline:** No internet connection or cloud APIs are required.  
* **Czech Language Support:** The assistant understands, processes, and responds in Czech.  
* **Wake-Word Detection:** Activates upon hearing a configurable voice command.  
* **VAD:** Utilizes Voice Activity Detection to trim silent periods from recordings, improving efficiency.  
* **Open-Source:** Built entirely with open-source tools and frameworks.

## **🚀 Getting Started**

Follow these steps to get the assistant up and running.

### **Prerequisites**

* [Python 3.10+](https://www.python.org)  
* [FFmpeg](https://ffmpeg.org)  
* [Git](https://git-scm.com)  
* Picovoice Porcupine SDK (requires an access key).  
* A Czech-compatible LLaMA model in GGUF format.  
* A Czech Coqui TTS model (e.g., tts\_models/cs/cv/vits).

### **Installation**

1. **Clone the repository:**  
   git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git  
   cd ai-assistant-voice-cs

2. **Install dependencies:**  
   The project relies on a number of key Python packages, including:  
   * llama\_cpp\_python: For the LLM.  
   * openai-whisper: For Speech-to-Text.  
   * TTS: For Text-to-Speech.  
   * pvporcupine: For wake-word detection.

To install all dependencies, run:pip install \-r requirements.txt

### **📥 Downloading Models**

The AI models required for this project are not included in the repository due to their large size. Please download them manually and place them in the correct directories.

* **LLaMA Model:**  
  * Download a compatible GGUF model, for example, mistral-7b-instruct-v0.2.Q4\_K\_M.gguf, from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/blob/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf).  
  * Place the downloaded file into the models/ directory.  
* **Picovoice Porcupine Wake-Word:**  
  * You need to obtain a Picovoice Porcupine access key from the [Picovoice Console](https://console.picovoice.ai/).  
  * Download the Porcupine model file (.ppn) for your chosen wake-word and operating system from the Picovoice Porcupine GitHub repository. For a standard model, look in the lib/common/ directory.  
  * Place the downloaded .ppn file into the models/ directory, and update the porcupine section in your config.json file accordingly.  
* **Coqui TTS:**  
  * The Coqui TTS model will be downloaded automatically the first time you run the assistant.

### **🎨 Configuration**

Create a config.json file. The structure should be as follows:

{  
  "porcupine": {  
    "access\_key": "YOUR\_PICOVOICE\_ACCESS\_KEY",  
    "model\_path": "models/porcupine\_params.pv",  
    "keyword": "computer",  
    "sensitivity": 0.7  
  },  
  "whisper": {  
    "model": "medium",  
    "language": "cs"  
  },  
  "llama": {  
    "model": "models/mistral-7b-instruct-v0.2.Q4\_K\_M.gguf",  
    "max\_tokens": 150  
  },  
  "tts": {  
    "model\_name": "tts\_models/cs/cv/vits",  
    "gpu": false  
  },  
  "audio": {  
    "device\_index": \-1,  
    "wake\_word\_device\_index": \-1,  
    "max\_recording\_time": 15  
  },  
  "silero\_vad": {  
    "sample\_rate": 16000,  
    "threshold": 0.3,  
    "silence\_duration\_ms": 2000  
  }  
}

* **porcupine**: Configuration for the wake-word engine. You need to replace "YOUR\_PICOVOICE\_ACCESS\_KEY" with your own key. "keyword" can be set to your desired wake-word.  
* **whisper**: Specifies the Whisper model to use and the language for transcription.  
* **llama**: Defines the path to your GGUF LLM model and the maximum number of tokens for the response.  
* **tts**: Sets the Coqui TTS model and specifies if GPU should be used.  
* **audio**: Initial audio device settings. The script will prompt you to select an audio device on the first run.  
* **silero\_vad**: Parameters for Voice Activity Detection.

### **🏃‍♂️ Run the assistant**

python3 main.py

When you run the script for the first time, it will list available microphones and ask you to select one by its index.

## **📁 Project Structure**

* main.py: The main loop for wake-word detection, audio processing, and core logic.  
* audio.py: Handles audio recording and wake-word detection.  
* stt\_module.py: Wrapper for the Speech-to-Text model.  
* llama\_module.py: Wrapper for the LLaMA model (llama.cpp).  
* tts\_module.py: Wrapper for the Text-to-Speech engine (Coqui TTS).  
* list\_tts\_models.py: A utility script to list available TTS models.  
* config.json: The main configuration file.  
* models/: Directory for storing LLM and TTS models.  
* requirements.txt: Project dependencies.  
* LICENSE: The project's license file.  
* README.md: This file.

## **🗺️ Future Plans & Vision**

This project is a starting point for a powerful, privacy-focused AI assistant that can be deeply integrated into creative and technical workflows. The goal is to move beyond simple voice interactions and make the assistant an indispensable tool for a variety of tasks.

Key areas for future development include:

* **Blender Integration:** Developing and fine-tuning specialized LLM models that can generate and interpret Python scripts (bpy modules) for Blender. This will enable users to create, manipulate, and render 3D scenes using natural voice commands, automating complex modeling and animation tasks.  
* **Advanced Programming Assistance:** Enhancing the assistant's ability to serve as a coding partner. This involves integrating directly with code editors like Neovim to provide real-time code generation, debugging, and refactoring based on voice instructions. The focus will be on natural language-to-code translation for faster development.  
* **General Workflow Automation:** Integrating with other desktop applications and services to automate repetitive tasks and streamline workflows, making the assistant a powerful productivity tool.

Contributions, ideas, and collaborations in these areas are highly welcome\!

## **💖 Credits**

Created by [Vítězslav Koneval](https://github.com/Polygonbeater).

Built with passion for the Czech language ❤️🇨🇿

## **⚖️ License**

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).