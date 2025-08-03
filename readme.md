🤖 Offline Czech Voice AssistantWelcome! This is an AI voice assistant designed to operate completely offline, utilizing local tools and models, with a specific focus on the Czech language.The assistant leverages the following technologies and models:🧠 LLM: llama.cpp for response generation, utilizing models in the GGUF format (e.g., a Mistral-7B model).🗣️ TTS: Coqui TTS for high-quality Czech text-to-speech.👂 Wake-Word: Picovoice Porcupine for hands-free activation using a custom keyword.🎙️ STT: Whisper (an offline version like whisper.cpp or faster-whisper) for accurate speech-to-text transcription.✨ Key FeaturesFully Offline: No internet connection or cloud APIs are required.Czech Language Support: The assistant understands, processes, and responds in Czech.Wake-Word Detection: Activates upon hearing a configurable voice command.VAD: Utilizes Voice Activity Detection to trim silent periods from recordings, improving efficiency.Open-Source: Built entirely with open-source tools and frameworks.🚀 Getting StartedFollow these steps to get the assistant up and running.PrerequisitesPython 3.10+FFmpegGitPicovoice Porcupine SDK (requires an access key).A Czech-compatible LLaMA model in GGUF format.A Czech Coqui TTS model (e.g., tts_models/cs/cv/vits).InstallationClone the repository:git clone https://github.com/Polygonbeater/ai-assistant-voice-cs.git
cd ai-assistant-voice-cs
Install dependencies:The project relies on a number of key Python packages, including:llama_cpp_python: For the LLM.openai-whisper: For Speech-to-Text.TTS: For Text-to-Speech.pvporcupine: For wake-word detection.To install all dependencies, run:pip install -r requirements.txt
📥 Downloading ModelsThe AI models required for this project are not included in the repository due to their large size. Please download them manually and place them in the correct directories.LLaMA Model:Download a compatible GGUF model, for example, mistral-7b-instruct-v0.2.Q4_K_M.gguf, from Hugging Face.Place the downloaded file into the models/ directory.Picovoice Porcupine Wake-Word:You need to obtain a Picovoice Porcupine access key from the Picovoice Console.Download the Porcupine model file (.ppn) for your chosen wake-word and operating system from the Picovoice Porcupine GitHub repository. For a standard model, look in the lib/common/ directory.Place the downloaded .ppn file into the models/ directory, and update the porcupine section in your config.json file accordingly.Coqui TTS:The Coqui TTS model will be downloaded automatically the first time you run the assistant.🎨 ConfigurationCreate a config.json file. The structure should be as follows:{
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
porcupine: Wake-word engine settings (access key, model path, keyword, sensitivity).whisper: Speech-to-text model and language settings.llama: Path to LLaMA model and max token limit.tts: Text-to-speech model and GPU usage.audio: Audio device settings.silero_vad: Voice activity detection parameters.🏃‍♂️ Running the AssistantRun the main script. On first run, you'll be prompted to select a microphone:python3 main.py
📁 Project Structuremain.py: The main loop and assistant logic.audio.py: Audio processing and wake-word detection.stt_module.py: Speech-to-text wrapper.llama_module.py: LLaMA model wrapper.tts_module.py: Text-to-speech wrapper.list_tts_models.py: Helper script for listing TTS models.config.json: Configuration file.models/: Directory for AI models.requirements.txt: Dependency list.LICENSE: License file.🗺️ Future Plans & VisionThis project is a starting point for a powerful, privacy-focused AI assistant that can be deeply integrated into creative and technical workflows. The goal is to move beyond simple voice interactions and make the assistant an indispensable tool for a variety of tasks.Key areas for future development include:Blender Integration: Developing and fine-tuning specialized LLM models that can generate and interpret Python scripts (bpy modules) for Blender. This will enable users to create, manipulate, and render 3D scenes using natural voice commands, automating complex modeling and animation tasks.Advanced Programming Assistance: Enhancing the assistant's ability to serve as a coding partner. This involves integrating directly with code editors like Neovim to provide real-time code generation, debugging, and refactoring based on voice instructions. The focus will be on natural language-to-code translation for faster development.General Workflow Automation: Expand capabilities for file management and app control via voice.AboutCreated by Vítězslav Koneval.Licensed under the MIT License.Built with passion for the Czech language ❤️🇨🇿
