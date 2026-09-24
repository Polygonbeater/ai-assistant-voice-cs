
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main


def test_config_example_matches_runtime_keys():
    with open('config.example.json', 'r', encoding='utf-8') as fh:
        config = json.load(fh)

    assert set(config.keys()) == {'porcupine', 'whisper', 'llama', 'tts', 'audio', 'silero_vad'}
    assert config['porcupine']['keyword'] == 'computer'
    assert config['silero_vad']['sample_rate'] == 16000
    assert config['tts']['model_name'] == 'tts_models/cs/cv/vits'


def test_validate_config_accepts_valid_config():
    with open('config.example.json', 'r', encoding='utf-8') as fh:
        config = json.load(fh)

    validated = main.validate_config(config)
    assert validated == config


def test_validate_config_rejects_missing_key():
    bad_config = {
        'porcupine': {'access_key': 'x', 'keyword': 'computer'},
        'whisper': {'model': 'tiny'},
        'llama': {'model': 'demo.gguf'},
        'tts': {'model_name': 'tts_models/cs/cv/vits'},
        'audio': {'device_index': -1, 'wake_word_device_index': -1, 'max_recording_time': 15},
        'silero_vad': {'sample_rate': 16000, 'threshold': 0.3, 'silence_duration_ms': 2000},
    }

    try:
        main.validate_config(bad_config)
        raise AssertionError('validate_config should reject incomplete config')
    except ValueError:
        pass


def test_resolve_model_path_relative_to_project_root():
    project_dir = '/tmp/demo-project'
    resolved = main._resolve_model_path(project_dir, 'models/example.gguf')
    assert resolved == os.path.join(project_dir, 'models/example.gguf')

def test_resolve_model_path_accepts_absolute_path():
    absolute = '/opt/models/example.gguf'
    assert main._resolve_model_path('/tmp/demo-project', absolute) == absolute

def test_normalize_audio_handles_empty_input():
    empty = np.array([], dtype=np.int16)
    result = main.normalize_audio(empty)
    assert result.size == 0
    assert result.dtype == np.int16

def test_normalize_audio_handles_regular_signal():
    signal = np.array([0, 1000, -1000, 4000], dtype=np.int16)
    normalized = main.normalize_audio(signal)
    assert normalized.dtype == np.int16
    assert normalized.size == signal.size
    assert np.max(np.abs(normalized)) > 0
