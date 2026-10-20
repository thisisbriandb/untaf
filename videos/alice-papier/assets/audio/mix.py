"""Bruitages du film papier, montés à partir de vrais enregistrements (Mixkit, licence gratuite).

Usage : python3 mix.py  (écrit sound.wav à côté)
Chaque événement : (fichier, début dans la source, durée, instant dans le film, gain, panoramique).
"""
import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
DUR = 11.5
HERE = Path(__file__).parent
N = int(SR * DUR)


def load(name):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(HERE / "src" / f"{name}.mp3"), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)


def clip(x, s0, d, fade=0.03):
    a, b = int(s0 * SR), int((s0 + d) * SR)
    y = x[:, a:b].copy()
    n = y.shape[1]
    f = min(int(fade * SR), n // 2)
    env = np.ones(n)
    env[:f] = np.linspace(0, 1, f)
    env[n - f:] = np.linspace(1, 0, f)
    return y * env


mix = np.zeros((2, N))


def put(name, s0, d, t, gain=1.0, pan=0.0, fade=0.03):
    y = clip(load(name), s0, d, fade)
    y = y / (np.abs(y).max() + 1e-9)
    a = (pan + 1) * np.pi / 4
    y = np.stack([y.mean(0) * np.cos(a) * 1.41, y.mean(0) * np.sin(a) * 1.41]) * 0.5 + y * 0.5
    i = int(t * SR)
    n = min(y.shape[1], N - i)
    mix[:, i:i + n] += y[:, :n] * gain


# Le haut se lève (frottement court), le bas suit, la feuille se pose.
put("2380", 0.0, 0.9, 0.5, 0.5, 0.15)
put("2386", 0.0, 1.0, 0.98, 0.55, -0.1)
put("2384", 0.0, 0.39, 1.6, 0.25, 0.0)

# Le stylo : un grattement de bille pendant chaque tracé, rien quand il est levé.
import json
ST = json.loads((HERE.parent / "handwriting" / "strokes.json").read_text())["strokes"]
pen_src = [load(n) for n in ("2367", "3194", "2369")]
bed = np.concatenate([x[:, int(0.05 * SR):-int(0.1 * SR)] for x in pen_src * 6], axis=1)
bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * 0.05
gate = np.zeros(N)
for s in ST:
    a, b = int(s["t0"] * SR), int(s["t1"] * SR)
    gate[a:b] = 1
k = int(0.012 * SR)
gate = np.convolve(gate, np.ones(k) / k, "same")
mix += bed[:, :N] * gate * 1.0
put("2376", 0.0, 0.25, ST[0]["t0"] - 0.02, 0.18, 0.1)   # la pointe touche le papier
put("2380", 0.0, 0.6, 1.95, 0.18, 0.4)                  # le stylo glisse dans le champ

# Petite pièce : une réverbération courte, sèche, qui donne l'espace de la table.
r = np.random.default_rng(3)
t = np.arange(int(0.35 * SR)) / SR
ir = np.stack([r.standard_normal(t.size) * np.exp(-t / 0.06) for _ in range(2)])
ir = sosfilt(butter(2, 5000, "lowpass", fs=SR, output="sos"), ir)
ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
wet = np.stack([fftconvolve(mix[c], ir[c])[:N] for c in range(2)])
out = mix + wet * 0.18
room = sosfilt(butter(2, 300, "lowpass", fs=SR, output="sos"), r.standard_normal((2, N))) * 0.004
out = out + room
out *= np.clip((DUR - np.arange(N) / SR) / 0.5, 0, 1)
out = out / np.abs(out).max() * 10 ** (-1.5 / 20)
pcm = (out.T * 32767).astype("<i2")
with wave.open(str(HERE / "sound.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok")
