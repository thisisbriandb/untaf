"""Sound design du spot « Alice, en vrai », synthétisé de façon déterministe.

Principe : l'image est minimale, c'est le son qui crée l'espace. Chaque élément
est sec et précis au premier plan, puis envoyé dans une grande réverbération
stéréo décorrélée (la « 3D invisible »). Deux pistes :
  - bed.wav : drone, nappes, air (sera creusé sous les voix) ;
  - sfx.wav : tics, verre, souffles, impacts (calés sur l'image).

Usage : python3 sound_design.py <dossier_de_sortie>
"""
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
DUR = 28.0
END = 27.11  # fin du film
N = int(SR * DUR)
rng = np.random.default_rng(20261015)


# ---------- outils ----------
def tt(d):
    return np.arange(int(SR * d)) / SR


def sos(kind, f, order=2):
    return butter(order, f, btype=kind, fs=SR, output="sos")


def filt(x, kind, f, order=2):
    return sosfilt(sos(kind, f, order), x)


def noise(d):
    return rng.standard_normal(int(SR * d))


def pan(x, p):
    """Panoramique à puissance constante, p dans [-1, 1]."""
    a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)])


class Track:
    off = 0.0  # décalage de la section en cours (le film a été rallongé par l'accroche)

    def __init__(self):
        self.dry = np.zeros((2, N))
        self.send = np.zeros((2, N))

    def add(self, st, t0, gain=1.0, send=0.0):
        i = int((t0 + Track.off) * SR)
        if i >= N:
            return
        n = min(st.shape[1], N - i)
        self.dry[:, i:i + n] += st[:, :n] * gain
        self.send[:, i:i + n] += st[:, :n] * gain * send


def impulse(rt60, predelay=0.03, bright=7000, seed=1):
    r = np.random.default_rng(seed)
    t = tt(rt60 * 1.2)
    env = np.exp(-6.9 * t / rt60)
    ir = []
    for _ in range(2):  # gauche / droite décorrélées : la largeur
        n = r.standard_normal(t.size) * env
        early = filt(n, "lowpass", bright) * np.exp(-t * 3)
        late = filt(n, "lowpass", bright * 0.35)
        ir.append(np.concatenate([np.zeros(int(predelay * SR)), 0.6 * early + late]))
    ir = np.array(ir)
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))


def reverb(send, ir):
    out = np.stack([fftconvolve(send[c], ir[c])[:N] for c in range(2)])
    return filt(out, "highpass", 180)


# ---------- timbres ----------
def glass(f0, d=3.5, soft=0.004, detune=0.0025):
    """Verre frappé : partiels inharmoniques, battement gauche/droite."""
    t = tt(d)
    ratios = [1.0, 2.32, 4.25, 6.63, 9.38]
    amps = [1.0, 0.55, 0.32, 0.18, 0.1]
    decays = [d * 0.55, d * 0.32, d * 0.18, d * 0.1, d * 0.06]
    att = np.minimum(t / soft, 1)
    out = []
    for side in (-1, 1):
        s = np.zeros_like(t)
        for r, a, dc in zip(ratios, amps, decays):
            f = f0 * r * (1 + side * detune * r ** 0.5)
            s += a * np.sin(2 * np.pi * f * t) * np.exp(-t / dc)
        out.append(s * att)
    st = np.array(out)
    return st / np.abs(st).max()


def tick(freq=3200, d=0.05, body=1100):
    t = tt(d)
    n = filt(noise(d), "bandpass", [freq * 0.6, min(freq * 1.6, 20000)]) * np.exp(-t / 0.004)
    b = np.sin(2 * np.pi * body * t) * np.exp(-t / 0.01) * 0.5
    x = n / (np.abs(n).max() + 1e-9) + b
    return x / np.abs(x).max()


def thud(f=70, d=0.35):
    t = tt(d)
    ph = 2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-t / 0.03))) / SR
    return np.sin(ph) * np.exp(-t / 0.09)


def whoosh(d, f_from, f_to, width=0.6, shape=2.0, seed_pan=(-0.3, 0.3)):
    """Souffle filtré qui balaie, avec une enveloppe en cloche asymétrique."""
    t = tt(d)
    x = np.zeros((2, t.size))
    for c in range(2):
        n = rng.standard_normal(t.size)
        # balayage : banque de passe-bande sur blocs
        blk = 1024
        y = np.zeros_like(n)
        for i in range(0, n.size, blk):
            k = i / max(n.size - 1, 1)
            fc = f_from * (f_to / f_from) ** k
            lo, hi = max(fc * (1 - width / 2), 30), min(fc * (1 + width / 2), 21000)
            seg = n[max(i - 2048, 0):i + blk]
            y[i:i + blk] = sosfilt(sos("bandpass", [lo, hi]), seg)[-min(blk, n.size - i):]
        x[c] = y
    env = (t / d) ** shape * np.exp(-shape * (t / d - 1))
    env /= env.max()
    x *= env
    p0, p1 = seed_pan
    pans = np.linspace(p0, p1, t.size)
    a = (pans + 1) * np.pi / 4
    st = np.stack([x[0] * np.cos(a), x[1] * np.sin(a)])
    return st / np.abs(st).max()


def pad(freqs, d, attack=2.5, release=2.5, bright=1800, detune=0.0018):
    """Nappe : paires de sinus/triangles désaccordées gauche/droite, filtrée."""
    t = tt(d)
    out = []
    for side in (-1, 1):
        s = np.zeros_like(t)
        for i, f in enumerate(freqs):
            ff = f * (1 + side * detune * (1 + 0.3 * i))
            lfo = 1 + 0.25 * np.sin(2 * np.pi * (0.07 + 0.013 * i) * t + i + side)
            s += (np.sin(2 * np.pi * ff * t) + 0.18 * np.sin(2 * np.pi * 2 * ff * t)) * lfo / (1 + 0.25 * i)
        out.append(filt(s, "lowpass", bright))
    st = np.array(out)
    env = np.minimum(t / attack, 1) * np.minimum((d - t) / release, 1).clip(0, 1)
    st *= env
    return st / np.abs(st).max()


def air(d, lo=5500, level_lfo=0.09):
    t = tt(d)
    st = np.stack([filt(noise(d), "highpass", lo, 4) for _ in range(2)])
    st *= 0.6 + 0.4 * np.sin(2 * np.pi * level_lfo * t)
    return st / np.abs(st).max()


def sub(f_from, f_to, d, decay):
    t = tt(d)
    f = f_from * (f_to / f_from) ** (t / d)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / decay) * np.minimum(t / 0.005, 1)
    return np.stack([x, x])


def fade_window(st, t0, t1, fin=0.005, fout=0.005):
    """Garde st seulement dans [t0, t1] (coupe nette, rampes courtes)."""
    t = np.arange(st.shape[1]) / SR
    g = np.clip((t - t0) / fin, 0, 1) * np.clip((t1 - t) / fout, 0, 1)
    return st * g


D = {"D2": 73.42, "A2": 110.0, "B2": 123.47, "D3": 146.83, "F#3": 185.0, "G2": 98.0, "A3": 220.0,
     "B3": 246.94, "D4": 293.66, "E4": 329.63, "F#4": 369.99, "A4": 440.0, "C#5": 554.37,
     "D5": 587.33, "F#5": 739.99, "A5": 880.0, "D6": 1174.66, "E6": 1318.51, "F#6": 1479.98,
     "A6": 1760.0, "D7": 2349.32}


mus, sfx = Track(), Track()

# ===== accroche : la nuit, une pièce silencieuse, deux notes graves =====
room = filt(noise(5.3), "lowpass", 240)
sfx.add(np.stack([room, np.roll(room, 400)]) / np.abs(room).max(), 0, 0.035, send=0.2)
sfx.add(glass(D["D5"], d=3.5, soft=0.02), 0.25, 0.05, send=1.0)
sfx.add(glass(D["A5"] * 0.5, d=3.5, soft=0.02), 1.45, 0.05, send=1.0)
# ===== le vrai CV : la feuille glisse (froissement doux) =====
pp = filt(noise(0.9), "bandpass", [1500, 7000]) * np.sin(np.pi * tt(0.9) / 0.9) ** 2
sfx.add(np.stack([pp, np.roll(pp, 120)]), 2.8, 0.05, send=0.4)
# ===== la nappe s'ouvre sur « Et si Alice s'en chargeait ? » et porte la suite =====
mus.add(pad([D["D3"], D["A3"], D["E4"], D["F#4"], D["C#5"]], 7.8, attack=1.0, release=1.4, bright=1700), 4.6, 0.22, send=0.8)
mus.add(pad([D["B2"], D["F#3"], D["D4"], D["A4"], D["C#5"]], 5.6, attack=1.0, release=1.2, bright=2000), 11.6, 0.22, send=0.8)
mus.add(pad([D["G2"], D["D3"], D["B3"], D["F#4"], D["A4"], D["D5"]], 7.6, attack=1.0, release=1.2, bright=2600), 16.3, 0.24, send=0.8)
mus.add(pad([D["D2"], D["A2"], D["D3"], D["F#3"], D["A3"], D["E4"]], 4.2, attack=0.6, release=1.4, bright=2200), 23.6, 0.24, send=0.8)
mus.add(filt(air(22.5), "lowpass", 13000), 4.6, 0.025, send=0.5)
tg = 5.4
while tg < 26.5:
    f = [587.33, 739.99, 880.0, 1174.66, 1479.98][int(rng.integers(5))]
    g = tt(rng.uniform(0.04, 0.12))
    mus.add(pan(np.sin(2 * np.pi * f * g) * np.sin(np.pi * g / g[-1]) ** 2, rng.uniform(-0.95, 0.95)), tg, rng.uniform(0.015, 0.04), send=0.9)
    tg += rng.exponential(1 / 5)
# ===== le chat : la frappe, l'envoi, Alice répond, la mission avance =====
for j in range(30):
    sfx.add(pan(tick(2700 + 300 * (j % 4), d=0.025, body=900), 0.08 * np.sin(j)), 5.75 + j * 0.034, 0.06, send=0.15)
sfx.add(glass(D["D6"], d=1.5, soft=0.003), 8.35, 0.06, send=0.8)
sfx.add(glass(D["A6"], d=1.8, soft=0.003), 8.43, 0.05, send=0.8)
for f, dt in [("D5", 0), ("F#5", 0.05), ("A5", 0.1)]:
    sfx.add(glass(D[f], d=3, soft=0.03), 8.9 + dt, 0.05, send=1.0)
for k in range(7):
    sfx.add(pan(glass([D["D6"], D["E6"], D["F#6"], D["A6"]][k % 4], d=0.8, soft=0.002)[k % 2], -0.3 + 0.1 * k), 9.4 + k * 0.4, 0.035, send=0.6)
# ===== valider et envoyer =====
sfx.add(whoosh(0.4, 1200, 6000, width=0.6, shape=1.8, seed_pan=(0, 0)), 13.45, 0.06, send=0.5)
sfx.add(pan(tick(2200, d=0.04, body=800), 0), 14.25, 0.18, send=0.3)
sfx.add(pan(thud(80, 0.3), 0), 14.25, 0.15, send=0.2)
for f, dt, g in [("D6", 0, 0.07), ("F#6", 0.09, 0.06), ("A6", 0.18, 0.06)]:
    sfx.add(glass(D[f], d=2.5, soft=0.002), 15.3 + dt, g, send=1.0)
# ===== Chrome : l'extension remplit, champ par champ =====
sfx.add(glass(D["D5"], d=2.5, soft=0.004), 16.4, 0.05, send=0.9)
for i, f in enumerate([D["D6"], D["E6"], D["F#6"], 1567.98, D["A6"], 1975.53, D["D7"]]):
    sfx.add(pan(glass(f, d=0.6, soft=0.002)[i % 2], -0.3 + 0.1 * i), 18.6 + i * 0.11, 0.04, send=0.6)
sfx.add(pan(glass(1046.5, d=0.9, soft=0.004, detune=0.01)[0], 0.4), 19.45, 0.045, send=0.6)
sfx.add(glass(D["A5"], d=2, soft=0.01), 20.2, 0.05, send=0.9)
sfx.add(whoosh(0.5, 1500, 6500, width=0.6, shape=1.8, seed_pan=(0, 0)), 22.0, 0.06, send=0.5)
# ===== signature =====
for f, dt in [("D5", 0), ("F#5", 0.05), ("A5", 0.1), ("D6", 0.15)]:
    sfx.add(glass(D[f], d=4, soft=0.01), 24.2 + dt, 0.07, send=1.0)
sfx.add(sub(73.4, 73.4, 2.5, 1.0), 24.2, 0.2)
sfx.add(glass(D["A6"], d=2.5, soft=0.004), 25.8, 0.05, send=1.0)

def finish(track, rt60, bright, seed):
    return track.dry + reverb(track.send, impulse(rt60, bright=bright, seed=seed)) * 0.5
mix = finish(mus, 4.0, 6000, 3) * 0.6 + finish(sfx, 2.8, 8000, 5)
t = np.arange(N) / SR
mix *= np.clip((END - t) / 0.9, 0, 1)
mix = mix / np.abs(mix).max() * 10 ** (-3 / 20)
pcm = (mix.T * 32767).astype("<i2")
with wave.open(str(Path(sys.argv[1]) / "sound.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok")
