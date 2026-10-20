"""Sound design du plan-séquence « Postuler, c'est facile », synthétisé de façon déterministe.

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
DUR = 22.5
END = 22.0
N = int(SR * DUR)
rng = np.random.default_rng(20261020)


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


mus, sfx = Track(), Track()   # mus : nappe + pulsation ; sfx : bruitages calés sur l'image
BEAT = 60 / 112


def kick():
    return pan(thud(58, 0.45), 0) * 0.9


def hat(seed):
    t = tt(0.06)
    x = filt(noise(0.06), "highpass", 8000) * np.exp(-t / 0.012)
    return pan(x / np.abs(x).max(), 0.35 * np.sin(seed))


# ===== Nappe : ré → si mineur → sol → la → ré (une seule prise, une seule phrase) =====
mus.add(pad([D["D3"], D["A3"], D["E4"], D["F#4"], D["C#5"]], 5.2, attack=0.6, release=1.0, bright=1500), 0.0, 0.24, send=0.8)
mus.add(pad([D["B2"], D["F#3"], D["D4"], D["A4"], D["C#5"]], 5.8, attack=1.0, release=1.0, bright=1900), 4.4, 0.24, send=0.8)
mus.add(pad([D["G2"], D["D3"], D["B3"], D["F#4"], D["A4"], D["D5"]], 4.3, attack=0.9, release=0.05, bright=2600), 9.6, 0.26, send=0.8)
mus.add(pad([D["A2"], D["E4"], D["A3"], D["C#5"], D["E6"] / 2], 4.0, attack=0.05, release=1.0, bright=3200), 14.95, 0.28, send=0.8)
mus.add(pad([D["D2"], D["D3"], D["A3"], D["F#4"], D["E4"], D["A4"]], 3.6, attack=0.4, release=1.6, bright=2200), 18.85, 0.30, send=0.9)
mus.add(filt(air(21.5), "lowpass", 12000), 0.3, 0.025, send=0.5)

# Pulsation : elle entre quand la caméra se met à suivre, s'arrête au clic, repart après l'envoi.
t = 2.3
while t < 18.4:
    if not (13.85 <= t < 15.05):
        sfx.add(kick(), t, 0.32 if t < 9.9 else 0.38, send=0.1)
        if t >= 9.9:
            sfx.add(hat(t), t + BEAT / 2, 0.05, send=0.2)
    t += BEAT

# ===== 0 – 2.3 : le point de lumière devient une offre =====
sfx.add(sub(40, 60, 1.4, 0.7), 0.0, 0.35)
sfx.add(whoosh(1.2, 400, 6000, width=0.9, shape=2.5, seed_pan=(-0.2, 0.2)), 0.0, 0.18, send=0.6)
sfx.add(glass(D["D5"], d=3, soft=0.03), 0.4, 0.08, send=1.0)
for i in range(4):                                                    # les compétences s'allument
    sfx.add(pan(glass([D["A5"], D["D6"], D["F#6"], D["A6"]][i], d=0.9, soft=0.001)[i % 2], -0.4 + 0.27 * i), 1.25 + i * 0.16, 0.06, send=0.6)
    sfx.add(pan(tick(7000, d=0.015, body=3500), -0.4 + 0.27 * i), 1.25 + i * 0.16, 0.05, send=0.3)

# ===== 2.3 – 4.6 : elles descendent dans le CV =====
sfx.add(whoosh(1.2, 5000, 900, width=0.8, shape=1.6, seed_pan=(0.3, -0.2)), 2.35, 0.16, send=0.5)
for i in range(4):
    tl = 2.45 + i * 0.07 + 1.05
    sfx.add(pan(glass([D["D6"], D["F#6"], D["A6"], D["D7"]][i], d=0.8, soft=0.001)[i % 2], -0.3 + 0.2 * i), tl, 0.06, send=0.6)
sfx.add(whoosh(0.4, 3000, 1200, width=0.6, shape=1.2, seed_pan=(-0.2, 0.2)), 3.1, 0.05, send=0.3)  # les anciennes s'effacent
sc = tt(0.7); scan = np.sin(2 * np.pi * (900 + 1400 * sc / 0.7) * sc) * 0.4 + filt(noise(0.7), "bandpass", [3000, 9000])
scan *= np.sin(np.pi * sc / 0.7)
sfx.add(np.stack([scan, np.roll(scan, 200)]) / np.abs(scan).max(), 3.55, 0.05, send=0.5)
sfx.add(pan(tick(5200, d=0.03, body=2200), 0.2), 4.2, 0.3, send=0.3)                              # badge
sfx.add(glass(D["A5"], d=1.4, soft=0.002), 4.22, 0.06, send=0.8)

# ===== 4.6 – 7.4 : la lettre glisse et s'écrit =====
sfx.add(whoosh(1.0, 1500, 6000, width=0.7, shape=1.4, seed_pan=(-0.6, 0.5)), 4.55, 0.14, send=0.5)
for i in range(8):
    for j in range(3):
        sfx.add(pan(tick(2600 + 400 * ((i + j) % 3), d=0.02, body=900), 0.3), 5.45 + i * 0.16 + j * 0.05, 0.05, send=0.12)
pen = filt(noise(0.65), "bandpass", [1800, 5000]) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 9 * tt(0.65))))
sfx.add(pan(pen / np.abs(pen).max(), 0.4), 6.75, 0.07, send=0.2)
sfx.add(glass(D["D6"], d=1.8, soft=0.003), 7.38, 0.06, send=0.9)

# ===== 7.4 – 9.9 : le dossier, puis on le suit =====
sfx.add(whoosh(0.7, 6000, 1500, width=0.8, shape=1.0, seed_pan=(0.6, -0.6)), 7.35, 0.14, send=0.4)
sfx.add(pan(thud(90, 0.25), 0), 7.98, 0.32, send=0.2)
sfx.add(glass(D["F#5"], d=2.0, soft=0.004), 7.98, 0.06, send=0.9)
sfx.add(whoosh(1.4, 300, 4000, width=1.0, shape=2.2, seed_pan=(-0.1, 0.1)), 8.55, 0.22, send=0.7)
sfx.add(sub(70, 45, 1.2, 0.5), 9.7, 0.4)
sfx.add(glass(D["D5"], d=2.5, soft=0.02), 9.25, 0.05, send=1.0)

# ===== 9.9 – 12.6 : l'extension remplit =====
for k, (t0, d) in enumerate([(10.0, 0.3), (10.35, 0.3), (10.75, 0.4), (11.2, 0.75), (12.05, 0.25)]):
    n = max(3, int(d / 0.045))
    for j in range(n):
        sfx.add(pan(tick(3000 + 350 * (j % 4), d=0.018, body=1000), -0.2 + 0.1 * k), t0 + j * d / n, 0.05, send=0.1)
    sfx.add(pan(glass([D["D6"], D["F#6"], D["A6"], D["D7"], D["F#6"]][k], d=0.8, soft=0.001)[k % 2], -0.2 + 0.1 * k), t0 + d * 0.8, 0.07, send=0.6)
sfx.add(glass(D["A5"], d=2.0, soft=0.004), 12.4, 0.07, send=0.9)                                # « Alice a tout rempli »

# ===== 12.8 – 14 : tu cliques ; tout se suspend =====
sfx.add(whoosh(0.9, 2500, 1200, width=0.5, shape=1.2, seed_pan=(0.6, 0.0)), 12.85, 0.04, send=0.2)
rs = tt(1.0); riser = whoosh(1.0, 400, 8000, width=1.0, shape=4.0, seed_pan=(-0.3, 0.3))
sfx.add(riser, 12.85, 0.12, send=0.6)
sfx.add(pan(tick(4200, d=0.03, body=1900), 0.05), 13.85, 0.5, send=0.25)                         # clic
sfx.add(pan(tick(3600, d=0.03, body=1500), 0.05), 13.95, 0.3, send=0.25)

# ===== 14 – 15.1 : implosion, la traînée, l'arrivée =====
imp = whoosh(0.35, 6000, 200, width=1.0, shape=0.6, seed_pan=(0.0, 0.0))
sfx.add(imp, 14.05, 0.3, send=0.5)
sfx.add(whoosh(0.85, 800, 12000, width=1.0, shape=3.0, seed_pan=(-0.8, 0.8)), 14.3, 0.45, send=0.8)
sfx.add(sub(60, 35, 2.2, 0.8), 15.05, 0.7)
sfx.add(pan(filt(noise(0.4), "lowpass", 4000) * np.exp(-tt(0.4) / 0.07), 0), 15.05, 0.25, send=1.0)
for f, dt in [("D6", 0), ("F#6", 0.06), ("A6", 0.12)]:                                            # « Envoyée »
    sfx.add(glass(D[f], d=2.4, soft=0.002), 15.1 + dt, 0.08, send=0.9)

# ===== 16.6 – 18.4 : les suivantes =====
sfx.add(whoosh(1.6, 4000, 900, width=0.8, shape=1.4, seed_pan=(-0.2, 0.2)), 16.6, 0.12, send=0.6)
for i in range(4):
    t0 = 16.85 + i * 0.3
    sfx.add(pan(glass([D["A5"], D["D6"], D["F#6"], D["A6"]][i], d=1.2, soft=0.002)[i % 2], [-0.5, 0.5, -0.3, 0.3][i]), t0, 0.06, send=0.8)
    sfx.add(pan(tick(6000, d=0.02, body=2600), [-0.5, 0.5, -0.3, 0.3][i]), t0, 0.06, send=0.3)

# ===== 18.4 – 22 : elles se rassemblent ; Alice =====
sfx.add(whoosh(0.7, 1200, 9000, width=1.0, shape=3.5, seed_pan=(-0.5, 0.5)), 18.35, 0.3, send=0.7)
sfx.add(sub(73.4, 73.4, 2.8, 1.1), 18.95, 0.35)
for f, dt in [("D5", 0), ("F#5", 0.05), ("A5", 0.1), ("D6", 0.15)]:
    sfx.add(glass(D[f], d=4, soft=0.01), 18.95 + dt, 0.08, send=1.0)

# ---------- rendu ----------
def finish(track, rt60, bright, seed):
    wet = reverb(track.send, impulse(rt60, bright=bright, seed=seed))
    return track.dry + wet * 0.5

mix = finish(mus, 4.0, 6000, 3) * 0.6 + finish(sfx, 2.6, 8000, 5)
t = np.arange(N) / SR
mix *= np.clip((END - t) / 1.0, 0, 1)
mix = mix / np.abs(mix).max() * 10 ** (-2 / 20)
out = Path(sys.argv[1])
pcm = (mix.T * 32767).astype("<i2")
with wave.open(str(out / "sound.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("ok")
