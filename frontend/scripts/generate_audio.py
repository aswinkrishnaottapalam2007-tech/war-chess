"""Original synthesized wood-friction and impact sound assets; no third-party samples."""
import math
import random
import struct
import wave
from pathlib import Path

folder = Path(__file__).resolve().parent.parent / 'assets' / 'audio'
folder.mkdir(exist_ok=True)
random.seed(42)
for name, duration in [('move', 0.33), ('capture', 0.46), ('notice', 0.35)]:
    samples = []
    brown = 0
    for i in range(int(duration * 22050)):
        t = i / 22050
        brown = brown * 0.8 + random.uniform(-1, 1) * 0.2
        if name == 'notice':
            value = (math.sin(2 * math.pi * 660 * t) + 0.35 * math.sin(2 * math.pi * 990 * t)) * math.exp(-12 * t) * min(1, t * 100) * 0.18
        else:
            impact = max(0, t - 0.21)
            value = brown * 0.36 * math.sin(math.pi * min(t / duration, 1)) + (math.sin(2 * math.pi * (220 if name == 'move' else 155) * impact) * math.exp(-40 * impact) * 0.55 if impact > 0 else 0)
        samples.append(struct.pack('<h', int(max(-1, min(1, value)) * 23000)))
    with wave.open(str(folder / f'{name}.wav'), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(b''.join(samples))