"""Sound design du manifeste Alice, synthétisé de façon déterministe.

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
DUR = 45.6
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
    def __init__(self):
        self.dry = np.zeros((2, N))
        self.send = np.zeros((2, N))

    def add(self, st, t0, gain=1.0, send=0.0):
        i = int(t0 * SR)
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

bed, sfx = Track(), Track()

# ===== Acte 1 · la boucle (0 – 10.5) : sec, mécanique, de plus en plus serré =====
# Tics d'horloge qui accélèrent, alternés gauche/droite.
times, t, k = [], 0.25, 0
while t < 10.45:
    times.append(t)
    iv = 0.72 - 0.52 * (t / 10.5) ** 1.4
    t += iv
for i, t0 in enumerate(times):
    p = -0.55 if i % 2 else 0.55
    sfx.add(pan(tick(2800 + 400 * (i % 3), body=900 + 150 * (i % 2)), p), t0, 0.16 + 0.1 * t0 / 10.5, send=0.25)
    if i % 2 == 0:
        sfx.add(pan(thud(62), 0), t0, 0.22 + 0.12 * t0 / 10.5, send=0.1)
# Chaque coupe de mot claque, au centre.
for t0 in [1.05, 2.35, 3.02, 3.82, 4.7, 5.5, 6.42, 8.68]:
    sfx.add(pan(tick(5200, d=0.06, body=1600), 0), t0, 0.32, send=0.35)
    sfx.add(pan(thud(48, 0.4), 0), t0, 0.3, send=0.05)
# Drone étroit, presque mono, qui s'ouvre et oppresse.
d1 = tt(10.5)
drone = sum(np.sin(2 * np.pi * f * d1 + ph) for f, ph in [(55, 0), (55.4, 1), (110.3, 2), (164.8, 0.5)])
drone *= 0.55 + 0.45 * np.sin(2 * np.pi * (1.2 + 2.4 * d1 / 10.5) * d1) ** 2  # trémolo qui accélère
drone = sosfilt(sos("lowpass", 420), np.tanh(drone * 1.6))
drone *= np.minimum(d1 / 1.5, 1) * (0.35 + 0.65 * d1 / 10.5)
bed.add(fade_window(np.stack([drone, np.roll(drone, 24)]) / np.abs(drone).max(), 0, 10.5), 0, 0.22, send=0.15)
# Poussière : micro-craquements très larges, à peine audibles.
for i in range(140):
    t0 = 0.5 + rng.random() * 9.9
    sfx.add(pan(tick(9000, d=0.012, body=4000), rng.uniform(-1, 1)), t0, 0.025, send=0.6)
# La plaque de verre monte (9.35) et se pose (10.2).
sfx.add(whoosh(0.95, 300, 5200, width=0.8, shape=2.2, seed_pan=(0, 0)), 9.3, 0.2, send=0.45)
sfx.add(glass(D["D6"], d=2.5, soft=0.02) , 10.18, 0.11, send=0.9)

# ===== Coupure 10.5 : tout s'arrête, une sub-basse tombe, la réverbération reste =====
sfx.add(sub(58, 30, 3.2, 1.1), 10.5, 0.55, send=0.0)
sfx.add(whoosh(2.6, 9000, 2500, width=1.2, shape=0.9, seed_pan=(-0.2, 0.2)), 10.5, 0.05, send=0.8)

# ===== Acte 2 · la rupture (10.5 – 20) : l'espace s'ouvre =====
sfx.add(glass(D["D6"], d=5, soft=0.06), 10.7, 0.12, send=1.0)          # le disque se forme
sfx.add(glass(D["A5"], d=5, soft=0.08, detune=0.004), 10.95, 0.08, send=1.0)
bed.add(pad([D["D3"], D["A3"], D["E4"], D["F#4"], D["C#5"]], 9.6, attack=3.5, release=1.2, bright=1500), 11.0, 0.2, send=0.7)
bed.add(filt(air(34.5), "lowpass", 13000), 10.6, 0.025, send=0.5)
sfx.add(whoosh(1.2, 700, 7500, width=0.7, shape=1.6, seed_pan=(0, 0)), 12.15, 0.16, send=0.6)  # le verre se lève
sfx.add(glass(D["F#6"], d=3, soft=0.01), 13.05, 0.06, send=0.9)
sfx.add(glass(D["D5"], d=6, soft=0.12), 16.25, 0.13, send=1.0)          # le disque revient
# La lumière s'allume : un scintillement qui monte.
t2 = tt(4.2)
shim = np.zeros((2, t2.size))
for j, f in enumerate([D["D6"], D["E6"], D["F#6"], D["A6"], D["D7"]]):
    for c in range(2):
        shim[c] += np.sin(2 * np.pi * f * (1 + (c - 0.5) * 0.003) * t2 + j) * (0.5 + 0.5 * np.sin(2 * np.pi * (3 + j * 0.7) * t2 + c)) / (1 + j * 0.4)
shim *= (t2 / 4.2) ** 1.8 * np.minimum((4.2 - t2) / 0.6, 1)
bed.add(shim / np.abs(shim).max(), 16.0, 0.05, send=0.9)

# ===== Acte 3 · le déploiement (20 – 25.5) =====
bed.add(pad([D["B2"], D["F#3"], D["D4"], D["A4"], D["C#5"]], 6.2, attack=1.8, release=1.5, bright=1700), 19.6, 0.2, send=0.7)
for t0, f in [(20.4, D["D6"]), (21.55, D["A5"]), (22.45, D["F#5"])]:     # vis, crées, respires
    sfx.add(glass(f, d=2.5, soft=0.03), t0, 0.04, send=1.0)
sfx.add(whoosh(1.7, 600, 2600, width=0.9, shape=1.3, seed_pan=(-1, 1)), 23.85, 0.22, send=0.5)  # le verre traverse
sfx.add(glass(D["D5"], d=3, soft=0.3, detune=0.006), 24.1, 0.07, send=1.0)

# ===== Acte 4 · la preuve (25.5 – 36.3) =====
bed.add(pad([D["G2"], D["D3"], D["B3"], D["F#4"], D["A4"]], 4.7, attack=1.2, release=0.5, bright=1500), 25.2, 0.2, send=0.7)
bed.add(pad([D["G2"], D["D3"], D["B3"], D["F#4"], D["A4"], D["D5"]], 6.3, attack=0.8, release=1.6, bright=2600), 29.97, 0.22, send=0.75)
# Compteur : des micro-données dont la densité suit la vitesse du chiffre (power2.out).
t0, c0 = 25.9, 0
while t0 < 28.3:
    x = (t0 - 25.9) / 2.4
    rate = 6 + 48 * 2 * (1 - x)
    sfx.add(pan(tick(7000 + 1500 * (c0 % 3), d=0.015, body=3000), rng.uniform(-0.8, 0.8)), t0, 0.05, send=0.4)
    t0 += 1 / rate
    c0 += 1
sfx.add(pan(tick(4200, d=0.05, body=2100), 0), 28.3, 0.12, send=0.5)
# « frappe aux bonnes portes » : deux coups de verre, feutrés.
for t0, p in [(28.72, -0.25), (28.98, 0.25)]:
    sfx.add(pan(thud(90, 0.3), p), t0, 0.22, send=0.3)
    sfx.add(pan(tick(1800, d=0.05, body=700), p), t0, 0.12, send=0.3)
# « Directement. » : un temps de vide, puis un impact net et profond.
sfx.add(sub(70, 38, 2.0, 0.45), 29.97, 0.6)
sfx.add(pan(filt(noise(0.25), "lowpass", 2500) * np.exp(-tt(0.25) / 0.03), 0), 29.97, 0.35, send=0.9)
sfx.add(glass(D["D6"], d=4, soft=0.002), 29.97, 0.1, send=1.0)
# Trois écrans de verre : un glissement et un carillon chacun.
for t0, notes, p in [(31.15, ("D6", "A6"), -0.2), (33.0, ("F#6", "D7"), 0.2), (34.75, ("A5", "E6"), 0.0)]:
    sfx.add(whoosh(0.55, 1200, 6000, width=0.6, shape=1.8, seed_pan=(p, p)), t0 - 0.12, 0.08, send=0.5)
    sfx.add(pan(glass(D[notes[0]], d=1.8, soft=0.003)[0], p), t0 + 0.05, 0.1, send=0.8)
    sfx.add(pan(glass(D[notes[1]], d=2.2, soft=0.003)[1], p), t0 + 0.17, 0.08, send=0.8)

# ===== Acte 5 · la résolution (36.3 – 45) =====
bed.add(pad([D["D2"], D["A2"], D["D3"], D["F#3"], D["A3"], D["E4"]], 9.3, attack=1.5, release=2.2, bright=2200), 36.0, 0.24, send=0.8)
sfx.add(whoosh(0.7, 8000, 1500, width=1.0, shape=1.5, seed_pan=(0, 0)), 39.2, 0.05, send=0.7)
for f, dt, g in [("D5", 0, 0.1), ("F#5", 0.04, 0.08), ("A5", 0.08, 0.07), ("D6", 0.12, 0.07)]:  # le logo
    sfx.add(glass(D[f], d=6, soft=0.01), 39.85 + dt, g, send=1.0)
sfx.add(sub(73.4, 73.4, 4.0, 1.6), 39.85, 0.2)
# « Alice » : souffle inversé qui aspire, puis un tintement.
rev = whoosh(0.8, 2000, 9000, width=0.8, shape=4.0, seed_pan=(0, 0))
sfx.add(rev, 40.5, 0.07, send=0.6)
sfx.add(glass(D["A6"], d=3, soft=0.005), 41.3, 0.06, send=1.0)
sfx.add(glass(D["D6"], d=5, soft=0.004), 43.75, 0.1, send=1.0)            # alice-agent.fr
sfx.add(glass(D["D7"], d=4, soft=0.004), 43.79, 0.04, send=1.0)


# ===== Texture : des grains de verre dispersés dans l'espace (actes 2 à 5) =====
CHORDS = [(10.5, ["D", "A", "E", "F#", "C#"]), (20.0, ["B", "F#", "D", "A", "C#"]),
          (25.5, ["G", "D", "B", "F#", "A"]), (36.3, ["D", "A", "F#", "E"])]
PC = {"C#": 277.18, "D": 293.66, "E": 329.63, "F#": 369.99, "G": 392.0, "A": 440.0, "B": 493.88}
t0 = 11.2
while t0 < 44.2:
    names = [c for start, c in CHORDS if start <= t0][-1]
    f = PC[names[int(rng.integers(len(names)))]] * (4 if rng.random() < 0.7 else 8)
    g = tt(rng.uniform(0.04, 0.14))
    grain = np.sin(2 * np.pi * f * g) * np.sin(np.pi * g / g[-1]) ** 2
    dens = 5 + (5 if 25.5 <= t0 < 36.3 else 0)
    bed.add(pan(grain, rng.uniform(-0.95, 0.95)), t0, rng.uniform(0.02, 0.06), send=0.9)
    t0 += rng.exponential(1 / dens)


# ---------- rendu ----------
def finish(track, rt60, bright, seed, fade_end=True):
    wet = reverb(track.send, impulse(rt60, bright=bright, seed=seed))
    mix = track.dry + wet * 0.55
    t = np.arange(N) / SR
    if fade_end:
        mix *= np.clip((45.0 - t) / 1.4, 0, 1)  # extinction douce, silence à 45 s
    return mix


def write(path, st, peak_db):
    st = st / np.abs(st).max() * 10 ** (peak_db / 20)
    pcm = (st.T * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


out = Path(sys.argv[1])
write(out / "bed.wav", finish(bed, 4.5, 6000, 7), -9.0)
write(out / "sfx.wav", finish(sfx, 3.2, 8000, 11), -4.0)
print("ok")
