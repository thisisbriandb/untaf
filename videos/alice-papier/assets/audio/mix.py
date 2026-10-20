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
DUR = 25.5
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


# Le stylo : un grattement de bille pendant chaque tracé, rien quand il est levé.
import json
ST = json.loads((HERE.parent / "handwriting" / "strokes.json").read_text())["strokes"]
S1 = 6.5 - 2.75
S2 = json.loads((HERE.parent / "handwriting" / "strokes.json").read_text())["end"] - 10.3873
pen_src = [load(n) for n in ("2367", "3194", "2369")]
bed = np.concatenate([x[:, int(0.05 * SR):-int(0.1 * SR)] for x in pen_src * 12], axis=1)
bed = bed / (np.sqrt((bed ** 2).mean()) + 1e-9) * 0.05
gate = np.zeros(N)
for s in ST:
    a, b = int(s["t0"] * SR), int(s["t1"] * SR)
    gate[a:b] = 1
k = int(0.012 * SR)
gate = np.convolve(gate, np.ones(k) / k, "same")
mix += bed[:, :N] * gate * 1.0
put("2376", 0.0, 0.25, ST[0]["t0"] - 0.02, 0.18, 0.1)   # la pointe touche le papier
put("2380", 0.0, 0.6, 1.95 + S1, 0.18, 0.4)                  # le stylo glisse dans le champ

# ---------- deuxième moitié ----------
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


put("2380", 0.0, 0.7, 10.55 + S2, 0.2, 0.5)                    # le stylo s'en va
# La déchirure : une fibre qui cède, des craquements qui s'accélèrent, puis s'arrêtent net.
put("2384", 0.0, 0.3, 11.5 + S2, 0.35, 0.0)
tr = clip(load("2389"), 0.0, 0.55, fade=0.01)
tr = np.stack([hp(c, 1200) for c in tr])
env = np.linspace(0.5, 1.0, tr.shape[1]) ** 1.5
env[-int(0.04 * SR):] *= np.linspace(1, 0, int(0.04 * SR))
tr = tr * env / np.abs(tr).max()
i0 = int((11.55 + S2) * SR); mix[:, i0:i0 + tr.shape[1]] += tr * 0.75
put("2996", 0.0, 0.35, 11.62 + S2, 0.3, -0.15)
put("2384", 0.0, 0.39, 12.38 + S2, 0.16, 0.2)                 # les morceaux retombent
# Alice : un silence, puis une note douce ; le clignement à peine audible.
felt([587.33], d=2.2, gain=0.06, t=12.78 + S2, pan=0.0)
put("2376", 0.0, 0.12, 13.27 + S2, 0.05, 0.0)
# Les morceaux se rejoignent, la lettre se réécrit.
put("1530", 0.1, 0.9, 13.58 + S2, 0.4, -0.2)
put("2386", 0.0, 1.0, 13.95 + S2, 0.35, 0.2)
# Pliage en trois, puis l'enveloppe.
put("2380", 0.0, 0.8, 15.2 + S2, 0.45, 0.15)
put("2386", 0.0, 0.9, 15.62 + S2, 0.45, -0.15)
put("2384", 0.0, 0.39, 16.06 + S2, 0.25, 0.0)
put("1530", 0.15, 0.9, 16.0 + S2, 0.4, 0.0)
put("2379", 1.2, 0.55, 16.75 + S2, 0.35, 0.0, fade=0.08)      # la lettre glisse dans la poche
put("1105", 0.0, 0.7, 17.32 + S2, 0.5, 0.0)                   # le rabat se ferme
put("2384", 0.0, 0.3, 17.72 + S2, 0.22, 0.0)

# ---------- acte 1 : la recherche ----------
put("2379", 0.0, 1.4, 0.0, 0.22, -0.2, fade=0.3)             # le journal, la pièce
felt([587.33], d=2.0, gain=0.05, t=0.38, pan=-0.1)            # les yeux s'ouvrent
put("2376", 0.0, 0.12, 1.0, 0.05, 0.0)                         # clignement
for t0, f in [(1.75, 880.0), (2.55, 987.77), (3.35, 1174.66)]:  # chaque annonce retenue : une note
    felt([f], d=1.6, gain=0.045, t=t0, pan=0.15)
put("2386", 0.0, 1.0, 3.95, 0.4, 0.1)                          # les coupures se détachent
put("1530", 0.1, 0.95, 4.72, 0.55, -0.3)                       # le journal glisse hors de la table

# ---------- acte 3 : le vol d'enveloppes ----------
put("2386", 0.0, 1.0, 18.0 + S2, 0.5, 0.2)                     # l'enveloppe décolle
r3 = np.random.default_rng(5)
for k in range(15):                                            # les autres arrivent, chacune son froissement
    put(["2380", "2386", "1530"][k % 3], 0.0, 0.7, 18.25 + S2 + k * 0.075, 0.12, float(r3.uniform(-0.8, 0.8)))
felt([587.33, 739.99, 880.0], d=2.6, gain=0.07, t=20.5 + S2, pan=0.0)   # les anneaux se forment
felt([293.66, 440.0, 587.33], d=3.2, gain=0.08, t=21.95 + S2, pan=0.0)  # Alice

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
