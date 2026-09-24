import json
import os
import tempfile

import pytest

import main


def test_config_normalization_accepts_example_config():
    config = json.loads(open('config.example.json', 'r', encoding='utf-8').read())
    normalized = main._normalize_config(config)

    assert normalized['porcupine']['model_path']
    assert normalized['porcupine']['keyword'] == 'computer'
    assert normalized['whisper']['language'] == 'cs'
    assert normalized['tts']['gpu'] is False


def test_runtime_config_rejects_placeholder_key():
    config = json.loads(open('config.example.json', 'r', encoding='utf-8').read())
    config['porcupine']['access_key'] = 'YOUR_PICOVOICE_ACCESS_KEY'
    with pytest.raises(ValueError):
        main.validate_runtime_config(config)


def test_config_legacy_aliases_are_supported():
    legacy_config = {
        'porcupine': {
            'access_key': 'demo_key',
            'keyword_path': 'models/porcupine_params.pv',
            'keyword': 'computer',
            'sensitivity': 0.7,
        },
        'whisper': {'model': 'tiny', 'language': 'cs'},
        'llama': {'model': 'models/demo.gguf', 'max_tokens': 64},
        'tts': {'model_name': 'tts_models/cs/cv/vits', 'use_gpu': True},
        'audio': {'device_index': 0, 'wake_word_device_index': 0, 'max_recording_time': 5},
        'silero_vad': {'sample_rate': 16000, 'threshold': 0.3, 'silence_duration_ms': 1000},
    }

    normalized = main._normalize_config(legacy_config)

    assert normalized['porcupine']['model_path'] == 'models/porcupine_params.pv'
    assert normalized['tts']['gpu'] is True
    assert normalized['tts']['use_gpu'] is True


def test_load_config_accepts_example_file_without_crashing():
    config = main.load_config('config.example.json')
    assert 'porcupine' in config
    assert 'llama' in config
    assert 'tts' in config


def test_missing_access_key_is_rejected():
    bad = {
        'porcupine': {'access_key': '', 'model_path': 'models/test.pv', 'keyword': 'computer'},
        'whisper': {'model': 'tiny', 'language': 'cs'},
        'llama': {'model': 'models/test.gguf'},
        'tts': {'model_name': 'tts_models/cs/cv/vits', 'gpu': False},
        'audio': {'device_index': -1, 'wake_word_device_index': -1, 'max_recording_time': 5},
        'silero_vad': {'sample_rate': 16000, 'threshold': 0.3, 'silence_duration_ms': 1000},
    }

    with pytest.raises(ValueError):
        main.validate_runtime_config(main._normalize_config(bad))
