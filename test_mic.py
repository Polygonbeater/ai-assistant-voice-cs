import pyaudio
import numpy as np
import time

p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    input_device_index=8,
    frames_per_buffer=1024
)

print("\n>>> Mluv do webkamery Creative Live! Cam (test trvá 6 sekund)...")
start = time.time()
bar_char = "#"

while time.time() - start < 6:
    data = stream.read(1024, exception_on_overflow=False)
    vol = int(np.abs(np.frombuffer(data, dtype=np.int16)).mean())
    count = min(40, vol // 80)
    bars = bar_char * count
    print(f"\rHlasitost: [{bars:<40}] {vol:5d}", end="", flush=True)
    time.sleep(0.05)

print("\nTest dokončen.")
stream.stop_stream()
stream.close()
p.terminate()
