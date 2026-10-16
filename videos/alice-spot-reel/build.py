"""Spot « Alice, en vrai » : vraies captures de l'app et de l'extension, DA du manifeste.

Noir pur, un seul élément à la fois, Geist. Chaque capture est montrée seule, dans
un écran flottant, et la caméra cadre ce qui compte (zoom et panoramique).
Usage : python3 build.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
COMP = ROOT / "compositions"
COMP.mkdir(exist_ok=True)

FONTS = "".join(
    f'@font-face {{ font-family: "Geist"; src: url("assets/fonts/Geist-{n}.woff2") format("woff2"); font-weight: {w}; }}\n    '
    for n, w in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)])
EYES = ('<svg viewBox="0 0 60 30"><circle cx="15" cy="15" r="10" fill="none" stroke="#006045" stroke-width="5"/>'
        '<circle cx="45" cy="15" r="10" fill="none" stroke="#006045" stroke-width="5"/></svg>')

# Écran flottant : taille du cadre, et largeur d'affichage de la vidéo.
SW, SH = 960, 1360


def base_css():
    return f"""
    {FONTS}
    #root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000;
            font-family: "Geist", sans-serif; color: #F5F5F2; }}
    .t {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 0 96px;
         text-align: center; opacity: 0; font-weight: 600; letter-spacing: -0.035em; line-height: 1.1; }}
    .halo {{ position: absolute; left: 40px; top: 360px; width: 1000px; height: 1200px; border-radius: 50%;
      background: radial-gradient(ellipse, rgba(255,255,255,0.20) 0%, rgba(255,255,255,0.06) 40%, rgba(255,255,255,0) 68%); }}
    .screen {{ position: absolute; left: {(1080 - SW) // 2}px; top: {(1920 - SH) // 2}px; width: {SW}px; height: {SH}px;
      border-radius: 44px; overflow: hidden; background: #FAFAF8;
      box-shadow: 0 0 0 1.5px rgba(255,255,255,0.35), 0 0 120px rgba(255,255,255,0.18), 0 60px 140px rgba(0,0,0,0.8); }}
    .cam {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; }}
    .cam video {{ display: block; width: {SW}px; height: {SH}px; object-fit: cover; }}
"""


def page(cid, body, script, extra=""):
    return f"""<template>
  <style>{base_css()}{extra}
  </style>
  <div id="root" data-composition-id="{cid}" data-width="1080" data-height="1920">
    {body}
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      // Cadrage : centre le point (fx, fy) de la vidéo (fractions) dans l'écran, au zoom s.
      const frame = (vh) => (fx, fy, s) => ({{ x: {SW} / 2 - fx * {SW} * s, y: {SH} / 2 - fy * vh * s, scale: s }});{script}
      window.__timelines["{cid}"] = tl;
    }})();
  </script>
</template>
"""


def text_beats(beats):
    """beats : (id, texte, taille, début, fin) — un seul texte à la fois, fondu doux."""
    body = "\n    ".join(f'<div class="t" id="{i}" style="font-size:{sz}px"><span>{tx}</span></div>' for i, tx, sz, a, b in beats)
    js = "".join(
        f'\n      tl.fromTo("#{i}", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.45, ease: "power3.out" }}, {a});'
        f'\n      tl.to("#{i}", {{ opacity: 0, y: -16, duration: 0.3, ease: "power2.in" }}, {b - 0.3});'
        for i, tx, sz, a, b in beats)
    return body, js


def video_scene(cid, src, dur, vh, keys, light=True):
    """keys : (t, fx, fy, zoom, durée de transition) ; le premier fixe le cadrage de départ."""
    body = "\n    ".join([
        '<div class="halo" id="halo"></div>',
        f'<div class="screen" id="scr" style="background:{"#FAFAF8" if light else "#000"}"><div class="cam" id="cam">'
        f'<video id="v-{cid}" class="clip" src="assets/video/framed/{src}" muted playsinline data-start="0" data-duration="{dur}" data-track-index="0"></video></div></div>',
    ])
    t0, fx, fy, s, _ = keys[0]
    js = f"""
      const F = frame({vh});
      tl.fromTo("#scr", {{ opacity: 0, scale: 0.94, y: 40 }}, {{ opacity: 1, scale: 1, y: 0, duration: 0.5, ease: "expo.out" }}, 0);
      tl.fromTo("#halo", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.6 }}, 0);
      tl.fromTo("#scr", {{ rotationX: 3, transformPerspective: 1800 }}, {{ rotationX: -2, transformPerspective: 1800, duration: {dur}, ease: "none" }}, 0);"""
    js += f'\n      tl.to("#scr", {{ opacity: 0, scale: 0.97, duration: 0.25, ease: "power2.in" }}, {dur - 0.25});'
    (COMP / f"{cid}.html").write_text(page(cid, body, js))


# ---------- 00 · l'accroche ----------
body, js = text_beats([("a", "Dimanche, 23&nbsp;h&nbsp;47.", 104, 0.25, 1.35),
                       ("b", "Ta 47<sup style='font-size:.5em'>e</sup> lettre de motivation.", 92, 1.45, 2.8)])
(COMP / "00-accroche.html").write_text(page("00-accroche", body, js))

# ---------- 01 · le vrai CV ----------
body = "\n    ".join([
    '<div class="halo" id="halo"></div>',
    '<div class="paper-wrap" id="pw"><img class="paper" src="assets/cv/cv-camille.png" alt="CV de Camille Martin" /></div>',
    '<div class="t" id="c" style="font-size:92px">Et si Alice s\'en chargeait&nbsp;?</div>',
])
extra = """
    .paper-wrap { position: absolute; left: 190px; top: 400px; width: 700px; height: 906px; perspective: 1600px; }
    .paper { width: 700px; height: 906px; border-radius: 6px; display: block;
      box-shadow: 0 0 0 1px rgba(255,255,255,0.15), 0 50px 120px rgba(0,0,0,0.9), 0 0 140px rgba(255,255,255,0.15); }"""
js = """
      tl.fromTo("#halo", { opacity: 0 }, { opacity: 1, duration: 0.8 }, 0);
      tl.fromTo("#pw", { opacity: 0, y: 80, rotationX: 14, rotationY: -10, scale: 0.92, transformPerspective: 1600 },
        { opacity: 1, y: 0, rotationX: 6, rotationY: -4, scale: 1, transformPerspective: 1600, duration: 0.9, ease: "expo.out" }, 0);
      tl.to("#pw", { rotationX: 2, rotationY: 3, scale: 1.04, duration: 0.7, ease: "sine.inOut" }, 0.9);
      tl.to("#pw", { opacity: 0, y: -60, scale: 0.9, duration: 0.3, ease: "power2.in" }, 1.6);
      tl.to("#halo", { opacity: 0.5, duration: 0.3 }, 1.6);"""
b2, j2 = text_beats([("c", "", 92, 1.95, 2.95)])
(COMP / "01-cv.html").write_text(page("01-cv", body, js + j2, extra))

# ---------- 02/03 · le chat : on tape, Alice trouve et postule ----------
VH = SW * 2700 / 2160  # hauteur affichée des captures de l'app (1080x1350)
video_scene("02-chat", "chat-a.mp4", 3.47, VH, [(0, 0.5, 0.955, 2.3, 0)])
video_scene("03-mission", "chat-b.mp4", 3.5, VH, [(0, 0.5, 0.74, 1.75, 0), (1.2, 0.5, 0.86, 1.75, 2.0)])
# ---------- 04 · le canevas : valider et envoyer ----------
video_scene("04-envoi", "canvas.mp4", 4.07, VH,
            [(0, 0.79, 0.40, 2.2, 0), (1.35, 0.64, 0.50, 2.6, 0.35), (2.0, 0.79, 0.16, 2.2, 0.4)])
# ---------- 05 · « Aussi sur Chrome. » ----------
body, js = text_beats([("d", "Aussi sur Chrome.", 112, 0.15, 1.0)])
(COMP / "05-chrome.html").write_text(page("05-chrome", body, js))
# ---------- 06 · l'extension remplit le formulaire ----------
video_scene("06-extension", "extension.mp4", 4.77, SW * 1100 / 1200,
            [(0, 0.5, 0.45, 1.5, 0), (2.9, 0.82, 0.80, 2.0, 0.6)])
# ---------- 07 · le suivi des candidatures ----------
video_scene("07-suivi", "candidatures.mp4", 2.0, VH, [(0, 0.5, 0.34, 1.7, 0)])

# ---------- 08 · signature ----------
body = "\n    ".join([
    '<div class="halo" id="halo"></div>',
    '<div class="end" id="logo"><div class="eyes">' + EYES + '</div><div class="name">Alice</div></div>',
    '<div class="t" id="u" style="font-size:84px">alice-agent.fr</div>',
])
extra = """
    .end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0; }
    .eyes { width: 240px; height: 240px; border-radius: 50%; background: #ECF4F0; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 0 100px rgba(255,255,255,0.25); }
    .eyes svg { width: 160px; height: 80px; }
    .name { margin-top: 40px; font-size: 140px; font-weight: 700; letter-spacing: -0.05em; line-height: 1; }"""
js = """
      tl.fromTo("#halo", { opacity: 0 }, { opacity: 1, duration: 0.8 }, 0);
      tl.fromTo("#logo", { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.6, ease: "expo.out" }, 0.1);
      tl.to("#logo", { opacity: 0, duration: 0.3 }, 1.4);
      tl.fromTo("#u", { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }, 1.7);"""
(COMP / "08-signature.html").write_text(page("08-signature", body, js, extra))

# ---------- index ----------
SCENES = [("00-accroche", 2.8), ("01-cv", 2.5), ("02-chat", 3.47), ("03-mission", 3.5), ("04-envoi", 4.07),
          ("05-chrome", 1.0), ("06-extension", 4.77), ("07-suivi", 2.0), ("08-signature", 3.0)]
starts, t = [], 0.0
for cid, d in SCENES:
    starts.append((cid, round(t, 3), d))
    t += d
TOTAL = round(t, 3)
master = json.dumps({"version": 1, "nodes": [
    {"type": "compressor", "id": "m1", "label": "Glue", "params": {"threshold": -18, "ratio": 2, "attack": 15, "release": 180, "knee": 6}},
    {"type": "gain", "id": "m3", "label": "Loudness", "params": {"gain": 4}},
    {"type": "truepeak", "id": "m2", "label": "Ceiling", "params": {"ceiling": -1.5, "lookahead": 3, "release": 80}}]})
hosts = "\n".join(
    f'      <div id="el-{cid}" class="scene" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
    f'data-start="{a}" data-duration="{d}" data-track-index="{i % 2}"></div>' for i, (cid, a, d) in enumerate(starts))
(ROOT / "timeline.json").write_text(json.dumps({"total": TOTAL, "scenes": starts}, indent=1))
(ROOT / "index.html").write_text(f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="assets/vendor/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; }}
      .scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="1080" data-height="1920" data-fx-chain='{master}'>
{hosts}
      <audio id="sound" src="assets/audio/sound.mp3" data-start="0" data-duration="{TOTAL}" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
""")
print("ok", TOTAL)
