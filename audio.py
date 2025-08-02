import pvporcupine
import pyaudio
import numpy as np
import logging

def initialize_porcupine(config):
    try:
        keyword_path = config["porcupine"]["keyword_path"]
        access_key = config["porcupine"]["access_key"]
        porcupine = pvporcupine.create(
            keyword_paths=[keyword_path],
            access_key=access_key
        )
        logging.info("Porcupine inicializován.")
        return porcupine
    except Exception as e:
        logging.error(f"Chyba při inicializaci Porcupine: {e}")
        raise

def capture_wake_word(porcupine, config):
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )
    try:
        pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
        pcm = np.frombuffer(pcm, dtype=np.int16)
        keyword_index = porcupine.process(pcm)
        return keyword_index  # -1 pokud nic, >=0 pokud detekováno
    except Exception as e:
        logging.error(f"Chyba při zachytávání wake word: {e}")
        return -1
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

def record_with_vad(config):
    import webrtcvad
    import collections
    import sys
    import time
    import pyaudio

    vad = webrtcvad.Vad(config["audio"]["vad_aggressiveness"])
    sample_rate = config["audio"]["rate"]
    frame_duration = config["audio"]["vad_frame_duration"]  # ms
    frame_size = int(sample_rate * frame_duration / 1000) * 2  # bytes (16-bit)

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=frame_size,
    )

    logging.info("Spouštím VAD nahrávání...")

    frames = []
    ring_buffer = collections.deque(maxlen=int(config["audio"]["silence_duration"] / frame_duration))
    triggered = False
    start_time = time.time()

    while True:
        frame = stream.read(frame_size, exception_on_overflow=False)
        is_speech = vad.is_speech(frame, sample_rate)
        ring_buffer.append((frame, is_speech))

        num_voiced = len([f for f, speech in ring_buffer if speech])
        if not triggered:
            if num_voiced > 0.9 * ring_buffer.maxlen:
                triggered = True
                logging.info("Detekován začátek řeči.")
                frames.extend([f for f, s in ring_buffer])
                ring_buffer.clear()
        else:
            frames.append(frame)
            if num_voiced < 0.1 * ring_buffer.maxlen:
                logging.info("Detekován konec řeči.")
                break

        if time.time() - start_time > config["audio"]["max_record_duration"]:
            logging.info("Maximální délka nahrávání dosažena.")
            break

    stream.stop_stream()
    stream.close()
    pa.terminate()

    audio_data = b"".join(frames)
    return np.frombuffer(audio_data, dtype=np.int16)

