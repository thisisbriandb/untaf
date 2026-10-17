"""Sound design du spot « Alice postule pendant ta pause », synthétisé de façon déterministe.

Principe : l'image est minimale, c'est le son qui crée l'espace. Chaque élément
est sec et précis au premier plan, puis envoyé dans une grande réverbération
stéréo décorrélée (la « 3D invisible »). Deux pistes :
  - bed.wav : drone, nappes, air (sera creusé sous les voix) ;
  - sfx.wav : tics, verre, souffles, impacts (calés sur l'image).

Usage : python3 sound_design.py <dossier_de_sortie>  (écrit sound.wav)
"""
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
DUR = 24.0
END = 23.0  # fin du film
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


mus, sfx = Track(), Track()   # mus : nappe ; sfx : bruitages calés sur l'image

def buzz(d=0.36):
    """Vibration de téléphone : bourdon grave modulé, sourd."""
    t = tt(d)
    x = np.sign(np.sin(2 * np.pi * 165 * t)) * 0.5 + np.sin(2 * np.pi * 82.5 * t)
    x = filt(x, "lowpass", 600) * (0.6 + 0.4 * np.sin(2 * np.pi * 28 * t)) * np.minimum(t / 0.01, 1) * np.minimum((d - t) / 0.03, 1)
    return x / np.abs(x).max()

# ===== 0 – 1 s : la pièce, le CV glisse, le clic =====
room = filt(noise(1.85), "lowpass", 260) * 0.5 + filt(noise(1.85), "bandpass", [900, 2500]) * 0.05
sfx.add(np.stack([room, np.roll(room, 300)]) / np.abs(room).max(), 0, 0.05, send=0.2)
sfx.add(whoosh(0.7, 2500, 900, width=0.6, shape=1.2, seed_pan=(0.5, 0.1)), 0.1, 0.03, send=0.2)  # glisser
sfx.add(pan(thud(110, 0.15), 0.1), 0.85, 0.08, send=0.2)                                          # déposé
sfx.add(pan(tick(4200, d=0.03, body=1900), 0.05), 0.99, 0.4, send=0.25)                           # clic
sfx.add(pan(tick(3600, d=0.03, body=1500), 0.05), 1.07, 0.25, send=0.25)                          # relâché

# ===== 1.15 – 2.4 s : catapultée, puis la plongée dans la fenêtre noire =====
sfx.add(whoosh(1.2, 300, 9000, width=1.0, shape=3.5, seed_pan=(-0.2, 0.2)), 1.15, 0.4, send=0.5)
rise = tt(1.2); r = np.sin(2 * np.pi * np.cumsum(180 * (1 + 6 * (rise / 1.2) ** 2)) / SR) * (rise / 1.2) ** 2.5
sfx.add(np.stack([r, r]), 1.15, 0.06, send=0.5)
sfx.add(sub(58, 30, 2.4, 0.8), 2.38, 0.7)                                                          # on entre dans le noir
sfx.add(whoosh(2.2, 9000, 2000, width=1.2, shape=0.8, seed_pan=(-0.3, 0.3)), 2.38, 0.06, send=1.0)

# ===== La nappe (comme le manifeste) : ré → si mineur → sol, qui monte vers 12 s =====
mus.add(pad([D["D3"], D["A3"], D["E4"], D["F#4"], D["C#5"]], 3.6, attack=0.8, release=1.0, bright=1600), 2.3, 0.22, send=0.8)
mus.add(pad([D["B2"], D["F#3"], D["D4"], D["A4"], D["C#5"]], 6.2, attack=1.2, release=1.2, bright=1900), 5.0, 0.22, send=0.8)
mus.add(pad([D["G2"], D["D3"], D["B3"], D["F#4"], D["A4"], D["D5"]], 6.2, attack=1.0, release=0.05, bright=2800), 10.85, 0.26, send=0.8)
mus.add(filt(air(14.6), "lowpass", 13000), 2.4, 0.03, send=0.5)
tg = 2.8
while tg < 16.8:                                                                                    # grains de verre dans l'espace
    f = [587.33, 739.99, 880.0, 1174.66, 1479.98][int(rng.integers(5))] * (2 if rng.random() < 0.3 else 1)
    g = tt(rng.uniform(0.04, 0.12))
    grain = np.sin(2 * np.pi * f * g) * np.sin(np.pi * g / g[-1]) ** 2
    mus.add(pan(grain, rng.uniform(-0.95, 0.95)), tg, rng.uniform(0.02, 0.05), send=0.9)
    tg += rng.exponential(1 / (5 if tg < 11 else 11))

# ===== 2.4 – 5.4 : la signature =====
sfx.add(glass(D["D5"], d=3, soft=0.05), 2.45, 0.07, send=1.0)                                       # le CV de verre apparaît
sc = tt(0.7); scan = np.sin(2 * np.pi * (900 + 1400 * sc / 0.7) * sc) * 0.4 + filt(noise(0.7), "bandpass", [3000, 9000])
scan *= np.sin(np.pi * sc / 0.7)
sfx.add(np.stack([scan, np.roll(scan, 200)]) / np.abs(scan).max(), 2.85, 0.06, send=0.5)            # scan
sfx.add(glass(D["D6"], d=2.0, soft=0.003), 3.5, 0.08, send=0.9)                                      # la signature s'embrase
sfx.add(whoosh(0.5, 1500, 7000, width=0.8, shape=1.5, seed_pan=(-0.7, 0.7)), 3.75, 0.13, send=0.5)   # l'éventail
for i in range(4):                                                                                     # les tampons
    t = 2.4 + 1.85 + i * 0.14
    sfx.add(pan(thud(70, 0.25), -0.45 + 0.3 * i), t, 0.26, send=0.2)
    sfx.add(pan(glass([D["A5"], D["D6"], D["F#6"], D["A6"]][i], d=1.2, soft=0.002)[i % 2], -0.45 + 0.3 * i), t, 0.05, send=0.7)
sfx.add(whoosh(0.5, 4000, 800, width=0.8, shape=1.2, seed_pan=(0.4, -0.6)), 4.88, 0.12, send=0.5)    # pivot

# ===== 5.4 – 11 : CV et lettre sur mesure =====
LIT = [[0, 1, 2], [1, 3], [0, 2, 3]]
for k, T in enumerate([0.4, 2.1, 3.8]):
    t = 5.4 + T
    sfx.add(whoosh(0.35, 2000, 8000, width=0.6, shape=1.5, seed_pan=(0.5, -0.3)), t - 0.05, 0.08, send=0.4)
    if k:
        sfx.add(whoosh(0.6, 3000, 600, width=0.8, shape=1.4, seed_pan=(-0.2, 0.2)), t + 0.1, 0.06, send=0.5)  # les blocs glissent
    for n, i in enumerate(LIT[k]):                                                                    # clics cristallins des mots-clés
        f = [D["D6"], D["F#6"], D["A6"], D["D7"]][min(n + k % 2, 3)]
        sfx.add(pan(glass(f, d=0.9, soft=0.001)[n % 2], -0.3 + 0.3 * n), t + 0.2 + i * 0.03, 0.06, send=0.6)
        sfx.add(pan(tick(7000, d=0.015, body=3500), -0.3 + 0.3 * n), t + 0.2 + i * 0.03, 0.05, send=0.3)

# ===== 11 – 17 : la rafale de formulaires, montée en puissance =====
for j in range(12):                                                                                    # gros plan : frappe
    sfx.add(pan(tick(2800 + 300 * (j % 4), d=0.025, body=900), 0), 11.15 + j * 0.07, 0.08, send=0.15)
rs = tt(1.9); riser = whoosh(1.9, 300, 7000, width=1.0, shape=4.0, seed_pan=(-0.4, 0.4))
tone = np.sin(2 * np.pi * np.cumsum(110 * (1 + 3 * (rs / 1.9) ** 2)) / SR) * (rs / 1.9) ** 3
sfx.add(riser, 11.0, 0.22, send=0.6)
sfx.add(np.stack([tone, tone]), 11.0, 0.08, send=0.6)
sfx.add(sub(55, 34, 2.0, 0.7), 12.9, 0.55)                                                            # la vague part
sfx.add(pan(filt(noise(0.4), "lowpass", 4000) * np.exp(-tt(0.4) / 0.07), 0), 12.9, 0.3, send=1.0)
for k in range(69):                                                                                    # chaque formulaire propulsé
    t = 11 + 1.9 + k * 0.052
    pp = np.sin(k * 2.1) * 0.8
    sfx.add(pan(tick(3200 + 500 * (k % 3), d=0.02, body=1200), pp), t, 0.035, send=0.2)
    sfx.add(whoosh(0.45, 500, 6500, width=0.8, shape=3.2, seed_pan=(pp, pp * 0.2)), t + 0.25, 0.035, send=0.4)

# ===== 17 – 23 : coupure, la pièce, les vibrations =====
room2 = filt(noise(6.0), "lowpass", 220)
sfx.add(np.stack([room2, np.roll(room2, 500)]) / np.abs(room2).max(), 17.0, 0.04, send=0.2)
for k, t in enumerate([17.45, 17.95, 18.4, 18.85]):
    sfx.add(pan(buzz(), 0), t, 0.35, send=0.1)
    sfx.add(glass(D["D6"] if k % 2 == 0 else D["F#6"], d=1.5, soft=0.002), t + 0.02, 0.05, send=0.7)
mus.add(pad([D["D3"], D["A3"], D["F#4"], D["E4"]], 5.2, attack=1.5, release=1.5, bright=1500), 17.8, 0.12, send=0.8)
for f, dt in [("D5", 0), ("F#5", 0.05), ("A5", 0.1), ("D6", 0.15)]:                                  # Alice signe
    sfx.add(glass(D[f], d=4, soft=0.01), 21.6 + dt, 0.07, send=1.0)
sfx.add(sub(73.4, 73.4, 2.5, 1.0), 21.6, 0.2)

# ---------- rendu ----------
def finish(track, rt60, bright, seed):
    wet = reverb(track.send, impulse(rt60, bright=bright, seed=seed))
    return track.dry + wet * 0.5

mix = finish(mus, 4.0, 6000, 3) * 0.6 + finish(sfx, 2.8, 8000, 5)
t = np.arange(N) / SR
mix *= np.clip((END - t) / 0.8, 0, 1)
mix = mix / np.abs(mix).max() * 10 ** (-3 / 20)
out = Path(sys.argv[1])
pcm = (mix.T * 32767).astype("<i2")
with wave.open(str(out / "sound.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok")
