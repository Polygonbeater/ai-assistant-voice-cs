import pyaudio, numpy as np
from openwakeword.model import Model

oww = Model(wakeword_model_paths=["models/hey_jarvis_v0.1.onnx"])
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, input_device_index=8, frames_per_buffer=1280)

print("\n>>> Naslouchám... Řekni do webkamery 'Hey Jarvis' (Ukonči přes Ctrl+C) <<<")
try:
    while True:
        data = stream.read(1280, exception_on_overflow=False)
        audio = np.frombuffer(data, dtype=np.int16)
        preds = oww.predict(audio)
        score = list(preds.values())[0]
        if hasattr(score, '__iter__'):
            val = float(list(score)[-1])
        else:
            val = float(score)
        
        bars = "#" * int(val * 40)
        status = ">>> ZACHYCENO! <<<" if val >= 0.25 else ""
        print(f"\rShoda: [{bars:<40}] {val*100:5.1f} %  {status}", end="", flush=True)
except KeyboardInterrupt:
    print("\nKonec testu.")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
