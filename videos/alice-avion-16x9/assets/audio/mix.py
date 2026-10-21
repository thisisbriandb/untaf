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
DUR = 21.0
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


import json
ST = json.loads((HERE.parent / "handwriting" / "strokes.json").read_text())["strokes"]

# ---------- la nuit : la pièce, une horloge, la bille ----------
r0 = np.random.default_rng(11)
for k in range(7):                                             # une horloge au loin, une fois par seconde
    tt = np.arange(int(0.05 * SR)) / SR
    tk = sosfilt(butter(2, [1800, 4200], "bandpass", fs=SR, output="sos"), r0.standard_normal(tt.size)) * np.exp(-tt / 0.006)
    tk += 0.4 * np.sin(2 * np.pi * 900 * tt) * np.exp(-tt / 0.01)
    tk /= np.abs(tk).max()
    i = int((0.3 + k * 1.0) * SR); mix[:, i:i + tk.size] += np.stack([tk, tk]) * 0.05 * (1 - k / 9)
pen_src = [load(n) for n in ("2367", "3194", "2369")]
bed = np.concatenate([x[:, int(0.05 * SR):-int(0.1 * SR)] for x in pen_src * 12], axis=1)
bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * 0.05
gate = np.zeros(N)
for s_ in ST:
    a, b = int(s_["t0"] * SR), int(s_["t1"] * SR)
    gate[a:b] = 1
k = int(0.012 * SR)
gate = np.convolve(gate, np.ones(k) / k, "same")
mix += bed[:, :N] * gate * 1.0
for sh in range(4):                                            # la pointe touche chaque nouvelle feuille
    t0 = min(s_["t0"] for s_ in ST if s_["sheet"] == sh)
    put("2376", 0.0, 0.25, t0 - 0.02, 0.16, 0.1)
for t0 in (1.75, 3.4, 5.3):                                    # la feuille rejoint la pile
    put("1530", 0.15, 0.6, t0, 0.32, -0.5)
for t0 in (1.95, 3.55, 5.4):                                   # la suivante arrive
    put("2380", 0.0, 0.5, t0, 0.22, 0.5)

def hp(x, f):
    return sosfilt(butter(2, f, "highpass", fs=SR, output="sos"), x)


def felt(freqs, d=2.6, gain=0.1, t=0.0, pan=0.0):
    """Piano feutré, très doux : harmoniques qui s'éteignent vite, attaque amortie."""
    tt = np.arange(int(d * SR)) / SR
    x = np.zeros_like(tt)
    for f in freqs:
        for h, a in [(1, 1.0), (2, 0.35), (3, 0.12), (4, 0.05)]:
            x += a * np.sin(2 * np.pi * f * h * tt) * np.exp(-tt * (1.6 + 1.2 * h))
    x *= np.minimum(tt / 0.012, 1)
    x = sosfilt(butter(2, 2600, "lowpass", fs=SR, output="sos"), x)
    x /= np.abs(x).max()
    a = (pan + 1) * np.pi / 4
    i = int(t * SR); n = min(len(x), N - i)
    mix[0, i:i + n] += x[:n] * np.cos(a) * gain * 1.41
    mix[1, i:i + n] += x[:n] * np.sin(a) * gain * 1.41


# ---------- la déchirure, puis le temps s'arrête ----------
put("2384", 0.0, 0.3, 6.7, 0.35, 0.0)
tr = clip(load("2389"), 0.0, 0.5, fade=0.01)
tr = np.stack([hp(c, 1200) for c in tr])
env = np.linspace(0.5, 1.0, tr.shape[1]) ** 1.5
env[-int(0.04 * SR):] *= np.linspace(1, 0, int(0.04 * SR))
tr = tr * env / np.abs(tr).max()
i0 = int(6.75 * SR); mix[:, i0:i0 + tr.shape[1]] += tr * 0.75
put("2996", 0.0, 0.3, 6.82, 0.28, -0.15)
felt([587.33], d=2.4, gain=0.06, t=7.3, pan=0.0)               # les yeux
put("2376", 0.0, 0.12, 7.8, 0.05, 0.0)                          # clignement
felt([146.83, 220.0, 369.99, 440.0], d=3.4, gain=0.06, t=7.55)  # la lumière revient
put("1530", 0.1, 0.9, 8.25, 0.35, -0.2)                         # les morceaux se rejoignent
put("2386", 0.0, 1.0, 8.6, 0.3, 0.2)                            # la lettre se réécrit
put("2384", 0.0, 0.3, 9.42, 0.2, 0.0)                           # elle se pose
# ---------- le CV s'adapte ----------
put("2380", 0.0, 0.6, 9.4, 0.35, 0.3)
for j, f in enumerate([587.33, 739.99, 880.0, 1174.66]):
    felt([f], d=1.4, gain=0.04, t=10.3 + j * 0.15, pan=0.2)
put("1530", 0.15, 0.7, 11.05, 0.32, 0.0)
# ---------- le pliage ----------
for j, t0 in enumerate((11.5, 11.78, 12.06, 12.34)):
    put("2384", 0.0, 0.25, t0 + 0.12, 0.22, (-0.3, 0.3, -0.2, 0.2)[j])
    put("2380", 0.0, 0.3, t0, 0.2, (-0.3, 0.3, -0.2, 0.2)[j])
put("2386", 0.0, 0.7, 12.62, 0.35, 0.0)
# ---------- l'envol, la flotte, les offres ----------
put("2386", 0.0, 1.0, 13.05, 0.45, 0.0)
put("1530", 0.1, 0.9, 13.3, 0.3, 0.3)
for i in range(1, 12):
    put(["2380", "2386"][i % 2], 0.0, 0.5, 13.7 + i * 0.09, 0.07, (-0.7, 0.7)[i % 2])
notes = [587.33, 659.25, 739.99, 880.0, 987.77, 1174.66]
lits = [16.75] + [15.0 + i * 0.1 + 0.85 for i in range(1, 12)] + [16.85 + q * 0.08 for q in range(4)]
for j, t0 in enumerate(sorted(lits)):
    felt([notes[j % len(notes)]], d=1.2, gain=0.035, t=t0, pan=float(np.sin(j * 1.7) * 0.6))
felt([293.66, 369.99, 440.0, 587.33], d=2.8, gain=0.07, t=17.55)   # les yeux d'Alice
felt([146.83, 293.66, 440.0], d=3.0, gain=0.08, t=18.55)           # Alice

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
