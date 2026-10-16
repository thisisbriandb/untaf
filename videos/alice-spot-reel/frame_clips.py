"""Cadre chaque capture (zoom + panoramique) et l'écrit à la taille de l'écran flottant.

Le rendu HyperFrames ne dessine pas une vidéo dont un parent est agrandi : le cadrage
est donc précalculé ici, image par image. Usage : python3 frame_clips.py
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
SRC, OUT = ROOT / "assets/video", ROOT / "assets/video/framed"
OUT.mkdir(parents=True, exist_ok=True)
SW, SH, FPS = 960, 1360, 30
SCALE = 2  # écrit en 1920x2720 pour rester net
BG = (250, 250, 248)


def ease(u):  # power3.inOut
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def cam_at(keys, t):
    _, fx, fy, s, _ = keys[0]
    cur = (fx, fy, s)
    for kt, kx, ky, ks, kd in keys[1:]:
        if t <= kt:
            break
        u = 1.0 if kd == 0 else min(1.0, (t - kt) / kd)
        e = ease(u)
        cur = tuple(a + (b - a) * e for a, b in zip(cur, (kx, ky, ks)))
    return cur


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height", "-of", "json", str(path)])
    st = json.loads(out)["streams"][0]
    return st["width"], st["height"]


def frame(name, keys, drift=0.03):
    src = SRC / f"{name}.mp4"
    w, h = probe(src)
    k = SW / w  # vidéo affichée à la largeur de l'écran
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    ow, oh = SW * SCALE, SH * SCALE
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")],
                           stdin=subprocess.PIPE)
    n, size = 0, w * h * 3
    total = None
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        t = n / FPS
        fx, fy, s = cam_at(keys, t)
        s *= 1 + drift * t / 4  # lente poussée continue
        vw, vh = SW / s / k, SH / s / k  # zone visible, en pixels source
        cx, cy = fx * w, fy * h
        x0, y0 = cx - vw / 2, cy - vh / 2
        im = Image.frombytes("RGB", (w, h), buf)
        canvas = Image.new("RGB", (int(round(vw)), int(round(vh))), BG)
        canvas.paste(im, (int(round(-x0)), int(round(-y0))))
        enc.stdin.write(canvas.resize((ow, oh), Image.LANCZOS).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print(name, n, "images")


SHOTS = {
    "chat-a": [(0, 0.5, 0.955, 2.3, 0)],
    "chat-b": [(0, 0.5, 0.74, 1.75, 0), (1.2, 0.5, 0.86, 1.75, 2.0)],
    "canvas": [(0, 0.79, 0.40, 2.2, 0), (1.35, 0.64, 0.50, 2.6, 0.35), (2.0, 0.79, 0.16, 2.2, 0.4)],
    "extension": [(0, 0.5, 0.45, 1.5, 0), (2.9, 0.82, 0.80, 2.0, 0.6)],
    "candidatures": [(0, 0.5, 0.34, 1.7, 0)],
}
for name in (sys.argv[1:] or SHOTS):
    frame(name, SHOTS[name])
