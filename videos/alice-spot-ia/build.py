"""Génère les compositions du spot « Alice postule pendant ta pause » (23 s, 1080x1920).

Usage : python3 build.py
Les textes modifiables sont regroupés en tête de fichier.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent
COMP = ROOT / "compositions"

# ---------- textes ----------
OFFERS = ["Offre #1 · Data", "Offre #2 · FinTech", "Offre #3 · Retail"]
CV_TITLES = ["Data Analyst — Alternance", "Analyste FinTech — Alternance", "Chargée Retail — Alternance"]
NOTIFS = [
    "Candidature transmise chez Doctolib (CV adapté + Lettre signée)",
    "Formulaire complété chez L'Oréal",
    "18 candidatures envoyées pendant ta pause.",
    "Atelier Nord vient de répondre : Proposition d'entretien.",
]

FONTS = "".join(
    f'@font-face {{ font-family: "Geist"; src: url("assets/fonts/Geist-{n}.woff2") format("woff2"); font-weight: {w}; }}\n    '
    for n, w in [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)])

EYES = ('<svg viewBox="0 0 60 30"><circle cx="15" cy="15" r="10" fill="none" stroke="#006045" stroke-width="5"/>'
        '<circle cx="45" cy="15" r="10" fill="none" stroke="#006045" stroke-width="5"/></svg>')

# Signature manuscrite stylisée (tracé SVG unique, dessiné à la main).
SIGN = ("M 10 62 C 22 20, 40 8, 46 30 C 52 52, 30 70, 26 54 C 22 38, 60 30, 70 44 C 78 56, 74 66, 82 52 "
        "C 90 38, 96 40, 98 52 C 100 62, 108 60, 114 46 C 120 32, 126 36, 128 50 C 130 64, 142 58, 150 40 "
        "C 156 28, 162 34, 160 48 C 158 62, 176 60, 196 30 M 60 74 C 100 70, 150 66, 206 58")


def css_base(p, bg="#000"):
    return f"""
    {FONTS}
    #root {{ position: absolute; inset: 0; width: 1080px; height: 1920px; overflow: hidden;
            background: {bg}; font-family: "Geist", sans-serif; color: #F5F5F2; }}
    .{p}-glass {{
      backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
      background: linear-gradient(150deg, rgba(255,255,255,0.17) 0%, rgba(255,255,255,0.04) 48%, rgba(255,255,255,0.10) 100%);
      border: 1.5px solid rgba(255,255,255,0.26);
      box-shadow: inset 0 2px 0 rgba(255,255,255,0.45), inset 0 -1px 0 rgba(255,255,255,0.10), 0 40px 90px rgba(0,0,0,0.7); }}
    .{p}-bar {{ height: 14px; border-radius: 7px; background: rgba(255,255,255,0.22); }}
    .{p}-lit {{ background: #FFFFFF; box-shadow: 0 0 18px rgba(255,255,255,0.8); }}
"""


def page(cid, p, extra, body, script, bg="#000"):
    return f"""<template>
  <style>{css_base(p, bg)}{extra}
  </style>

  <div id="root" data-composition-id="{cid}" data-width="1080" data-height="1920">
    {body}
  </div>

  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});{script}
      window.__timelines["{cid}"] = tl;
    }})();
  </script>
</template>
"""


# ===================== 01 · intro (0 – 2.4) =====================
# Écran du moniteur dans l'image source mise à 1080x1920 : x 120–960, y 540–1060.
# La tête du personnage commence vers y 800 : tout ce qui se passe à l'écran reste au-dessus (y < 780).
p = "i1"
BOX_X, BOX_Y = 540, 668          # centre de la fenêtre sombre, en coordonnées image
body = "\n    ".join([
    '<div class="i1-cam" id="i1-cam">',
    '  <video id="i1-video" class="clip" src="assets/video/intro-ramp.mp4" muted playsinline data-start="0" data-duration="2.4" data-track-index="0"></video>',
    '  <div class="i1-screen">',
    '    <div class="i1-win" id="i1-win"><div class="i1-wbar"><span></span><span></span><span></span><em>Alice</em></div>'
    '<div class="i1-drop" id="i1-drop"><span id="i1-droptx">Dépose ton CV</span></div></div>',
    '    <div class="i1-file" id="i1-file"><div class="i1-doc"><div class="i1-fold"></div><b>PDF</b></div><div class="i1-fname">CV.pdf</div></div>',
    '    <svg class="i1-cursor" id="i1-cursor" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.6L20 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    '  </div>',
    '</div>',
])
extra = f"""
    .i1-cam {{ position: absolute; inset: 0; transform-origin: {BOX_X}px {BOX_Y}px; }}
    #i1-video {{ position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }}
    .i1-screen {{ position: absolute; left: 120px; top: 540px; width: 840px; height: 520px; overflow: hidden; }}
    /* Fenêtre sombre d'Alice, en haut de l'écran, au-dessus de la tête. */
    .i1-win {{ position: absolute; left: 250px; top: 38px; width: 340px; height: 180px; border-radius: 14px;
      background: #0B0B0C; box-shadow: 0 10px 30px rgba(0,0,0,0.35); padding: 12px 16px; }}
    .i1-wbar {{ display: flex; align-items: center; gap: 7px; }}
    .i1-wbar span {{ width: 9px; height: 9px; border-radius: 50%; background: #3A3A40; }}
    .i1-wbar em {{ margin-left: 8px; font-style: normal; font-size: 13px; font-weight: 600; color: #8A8A86; }}
    .i1-drop {{ margin-top: 12px; height: 118px; border-radius: 10px; border: 1.5px dashed rgba(255,255,255,0.28);
      display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 500; color: #9A9A96; }}
    .i1-file {{ position: absolute; left: 0; top: 0; width: 80px; text-align: center; transform-origin: 50% 50%; }}
    .i1-doc {{ position: relative; width: 52px; height: 66px; margin: 0 auto; border-radius: 6px; background: #FFFFFF;
      box-shadow: 0 6px 16px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,0,0,0.15); display: flex; align-items: flex-end; justify-content: center; padding-bottom: 8px; }}
    .i1-doc b {{ font-size: 13px; font-weight: 700; color: #1A1918; }}
    .i1-fold {{ position: absolute; right: 0; top: 0; width: 15px; height: 15px; background: #DCDCD8; border-bottom-left-radius: 5px; }}
    .i1-fname {{ margin-top: 4px; font-size: 12px; font-weight: 600; color: #1A1918; }}
    .i1-cursor {{ position: absolute; left: 0; top: 0; width: 26px; height: 26px; }}"""
script = """
      const cam = document.getElementById("i1-cam");
      // 0 – 1 s : vitesse normale, léger travelling ; le CV glisse depuis le bord de l'écran jusqu'à la fenêtre d'Alice.
      tl.fromTo(cam, { scale: 1 }, { scale: 1.04, duration: 1.0, ease: "sine.inOut" }, 0);
      tl.fromTo("#i1-file", { x: 700, y: 40, rotation: 6 }, { x: 380, y: 92, rotation: 0, duration: 0.75, ease: "power3.out" }, 0.05);
      tl.fromTo("#i1-cursor", { x: 740, y: 70 }, { x: 420, y: 122, duration: 0.75, ease: "power3.out" }, 0.05);
      tl.to("#i1-drop", { borderColor: "rgba(255,255,255,0.75)", duration: 0.2 }, 0.3);
      tl.to("#i1-droptx", { opacity: 0, duration: 0.2 }, 0.3);
      // Le clic (1.0) : le curseur presse, la caméra frémit, la fenêtre avale le CV.
      tl.to("#i1-cursor", { scale: 0.8, duration: 0.06, ease: "power2.in" }, 0.98);
      tl.to("#i1-cursor", { scale: 1, opacity: 0, duration: 0.12, ease: "power2.out" }, 1.04);
      tl.fromTo(cam, { x: 0 }, { x: -5, duration: 0.04, ease: "none" }, 1.0);
      tl.to(cam, { x: 4, duration: 0.05, ease: "none" }, 1.04);
      tl.to(cam, { x: 0, duration: 0.05, ease: "none" }, 1.09);
      tl.to("#i1-file", { scale: 0, rotation: 25, opacity: 0, duration: 0.25, ease: "power4.in" }, 1.0);
      tl.to("#i1-drop", { opacity: 0, duration: 0.2 }, 1.15);
      // 1.15 – 2.4 : vidéo à 6x, recadrage et angle hollandais, puis la caméra plonge dans la fenêtre noire (x12).
      tl.to(cam, { scale: 1.25, x: 30, rotation: 3, duration: 0.55, ease: "power2.in" }, 1.15);
      tl.to(cam, { scale: 17, x: 0, rotation: 0, duration: 0.62, ease: "expo.in" }, 1.7);"""
(COMP / "01-intro.html").write_text(page("01-intro", p, extra, body, script))


# ===================== 02 · la signature (2.4 – 5.4) =====================
p = "s2"
FAN_X = [-300, -100, 100, 300]
FAN_RY = [34, 12, -12, -34]
FAN_R = [-7, -2.5, 2.5, 7]
FAN_Z = [-220, -60, -60, -220]
SIG_SRC = (700, 1290)  # signature du CV, en coordonnées écran
letters = ""
for i in range(4):
    dx = SIG_SRC[0] - (540 + FAN_X[i] + 100)
    dy = SIG_SRC[1] - 1240
    letters += (
        f'<div class="s2-letter s2-glass" id="s2-l{i}" data-dx="{dx}" data-dy="{dy}"><div class="s2-lh"></div>'
        + "".join(f'<div class="s2-bar" style="width:{w}%"></div>' for w in (88, 94, 70, 90, 82, 60))
        + f'<svg class="s2-lsig" id="s2-ls{i}" viewBox="0 0 220 80"><path d="{SIGN}" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/></svg></div>')
body = "\n    ".join([
    '<div class="s2-halo" id="s2-halo"></div>',
    '<div class="s2-stage" id="s2-stage">',
    '  <div class="s2-pdf s2-glass" id="s2-pdf"><div class="s2-name">Camille Martin</div><div class="s2-role">Alternance · Marketing</div>'
    + "".join(f'<div class="s2-pbar" style="width:{w}%"></div>' for w in (92, 80, 86, 64, 90, 74, 58, 84))
    + f'<svg class="s2-sig" id="s2-sig" viewBox="0 0 220 80"><path d="{SIGN}" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/></svg>'
    '<div class="s2-scan" id="s2-scan"></div></div>',
    '  <div class="s2-fan" id="s2-fan">' + letters + '</div>',
    '</div>',
])
extra = """
    .s2-halo { position: absolute; left: 90px; top: 520px; width: 900px; height: 900px; border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.26) 0%, rgba(255,255,255,0.08) 38%, rgba(255,255,255,0) 68%); }
    .s2-stage { position: absolute; inset: 0; perspective: 1500px; transform-style: preserve-3d; }
    .s2-pdf { position: absolute; left: 240px; top: 540px; width: 600px; height: 840px; border-radius: 34px; padding: 60px 56px; overflow: hidden; }
    .s2-name { font-size: 40px; font-weight: 700; letter-spacing: -0.02em; }
    .s2-role { margin-top: 6px; font-size: 22px; font-weight: 500; color: #A9A9A4; margin-bottom: 26px; }
    .s2-pbar { height: 14px; border-radius: 7px; background: rgba(255,255,255,0.20); margin-top: 26px; }
    .s2-sig { position: absolute; right: 50px; bottom: 50px; width: 260px; height: 95px; filter: drop-shadow(0 0 6px rgba(255,255,255,0.6)); }
    .s2-scan { position: absolute; left: -10%; width: 120%; top: 0; height: 6px; background: #fff; opacity: 0;
      box-shadow: 0 0 30px 12px rgba(255,255,255,0.75), 0 0 110px 36px rgba(255,255,255,0.3); }
    .s2-fan { position: absolute; inset: 0; transform-style: preserve-3d; }
    .s2-letter { position: absolute; left: 340px; top: 720px; width: 400px; height: 560px; border-radius: 30px; padding: 44px 38px; opacity: 0; }
    .s2-lh { width: 46%; height: 16px; border-radius: 8px; background: rgba(255,255,255,0.45); margin-bottom: 16px; }
    .s2-bar { height: 11px; border-radius: 6px; background: rgba(255,255,255,0.22); margin-top: 22px; }
    .s2-lsig { position: absolute; right: 26px; bottom: 30px; width: 180px; height: 66px; opacity: 0; filter: drop-shadow(0 0 10px rgba(255,255,255,0.95)); }"""
script = f"""
      const FX = {json.dumps(FAN_X)}, FRY = {json.dumps(FAN_RY)}, FR = {json.dumps(FAN_R)}, FZ = {json.dumps(FAN_Z)};
      // Caméra continue : la scène flotte et se rapproche lentement.
      tl.fromTo("#s2-stage", {{ scale: 0.95, rotationX: 5, transformPerspective: 1800 }}, {{ scale: 1.05, rotationX: -3, transformPerspective: 1800, duration: 3.0, ease: "sine.inOut" }}, 0);
      tl.fromTo("#s2-halo", {{ opacity: 0, scale: 0.6 }}, {{ opacity: 1, scale: 1, duration: 0.8, ease: "sine.out" }}, 0);
      // Le CV de verre sort de la fenêtre noire et flotte en 3D.
      tl.fromTo("#s2-pdf", {{ z: -900, rotationY: -30, rotationX: 12, opacity: 0 }}, {{ z: 0, rotationY: -16, rotationX: 7, opacity: 1, duration: 0.7, ease: "expo.out" }}, 0);
      tl.to("#s2-pdf", {{ rotationY: -6, duration: 0.8, ease: "sine.inOut" }}, 0.7);
      // Le rayon le scanne de haut en bas.
      tl.set("#s2-scan", {{ opacity: 1 }}, 0.45);
      tl.fromTo("#s2-scan", {{ y: 0 }}, {{ y: 834, duration: 0.7, ease: "power1.inOut" }}, 0.45);
      tl.set("#s2-scan", {{ opacity: 0 }}, 1.15);
      // La signature s'embrase et se détache de la feuille.
      tl.to("#s2-sig", {{ filter: "drop-shadow(0 0 18px rgba(255,255,255,1))", scale: 1.15, y: -20, duration: 0.25, ease: "power2.out" }}, 1.1);
      tl.to(".s2-name, .s2-role, .s2-pbar", {{ opacity: 0.15, duration: 0.25 }}, 1.15);
      tl.to("#s2-pdf", {{ z: -700, opacity: 0, rotationY: 10, duration: 0.45, ease: "power2.in" }}, 1.5);
      // Les lettres de verre s'ouvrent en éventail dans l'espace ; chaque signature vient s'y tamponner.
      [0, 1, 2, 3].forEach((i) => {{
        const l = "#s2-l" + i, s = "#s2-ls" + i, el = document.querySelector(l);
        const dx = +el.dataset.dx, dy = +el.dataset.dy;
        tl.fromTo(l, {{ x: 0, z: -400, rotationY: 0, rotation: 0, opacity: 0 }},
          {{ x: FX[i], z: FZ[i], rotationY: FRY[i], rotation: FR[i], opacity: 1, duration: 0.55, ease: "expo.out" }}, 1.4 + i * 0.05);
        const t = 1.85 + i * 0.14;
        tl.fromTo(s, {{ x: dx, y: dy, scale: 1.4, opacity: 0 }}, {{ x: dx * 0.5, y: dy * 0.5 - 60, scale: 1.3, opacity: 1, duration: 0.2, ease: "power2.out" }}, t - 0.36);
        tl.to(s, {{ x: 0, y: 0, scale: 1, duration: 0.16, ease: "power4.in" }}, t - 0.16);
        tl.fromTo(l, {{ scale: 1.05 }}, {{ scale: 1, duration: 0.3, ease: "power3.out", immediateRender: false }}, t);
      }});
      tl.to("#s2-sig", {{ opacity: 0, duration: 0.2 }}, 1.6);
      // La caméra pivote vers la suite.
      [0, 1, 2, 3].forEach((i) => tl.to("#s2-l" + i, {{ rotationY: FRY[i] - 40, x: FX[i] - 160, opacity: 0, duration: 0.45, ease: "power3.in" }}, 2.5 + i * 0.03));
      tl.to("#s2-halo", {{ opacity: 0.4, duration: 0.45 }}, 2.5);"""
(COMP / "02-signature.html").write_text(page("02-signature", p, extra, body, script))


# ===================== 03 · CV et lettre sur mesure (5.4 – 11) =====================
p = "m3"
# Trois mises en page : blocs (id, y, h, largeur %) qui glissent et changent de taille.
LAYOUTS = [
    {"b0": (150, 120, 100), "b1": (290, 230, 100), "b2": (540, 200, 100), "b3": (760, 90, 100)},
    {"b0": (150, 120, 100), "b1": (510, 230, 100), "b2": (290, 200, 100), "b3": (760, 90, 100)},
    {"b0": (150, 160, 100), "b1": (330, 150, 100), "b2": (690, 200, 100), "b3": (500, 170, 100)},
]
KEYS = [["SQL", "Python", "Power BI", "Excel", "Agile"], ["Python", "Risque", "Excel", "Paiements", "SQL"], ["Merch", "Excel", "Ventes", "CRM", "Terrain"]]
LIT = [[0, 1, 2], [1, 3], [0, 2, 3]]
LETTER = [[92, 70, 86, 60, 80, 74], [70, 92, 60, 88, 66, 82], [84, 66, 92, 72, 58, 90]]
cv_blocks = (
    '<div class="m3-blk" id="m3-b0"><div class="m3-h">Profil</div><div class="m3-bar" style="width:90%"></div><div class="m3-bar" style="width:72%"></div></div>'
    '<div class="m3-blk" id="m3-b1"><div class="m3-h">Expériences</div><div class="m3-bar" id="m3-x0" style="width:86%"></div><div class="m3-bar" id="m3-x1" style="width:64%"></div><div class="m3-bar" id="m3-x2" style="width:78%"></div></div>'
    '<div class="m3-blk" id="m3-b2"><div class="m3-h">Compétences</div><div class="m3-keys">'
    + "".join(f'<span class="m3-key" id="m3-k{i}">{k}</span>' for i, k in enumerate(KEYS[0])) + '</div></div>'
    '<div class="m3-blk" id="m3-b3"><div class="m3-h">Formation</div><div class="m3-bar" style="width:58%"></div></div>'
)
body = "\n    ".join([
    '<div class="m3-halo"></div>',
    '<div class="m3-pills">' + "".join(f'<div class="m3-pill m3-glass" id="m3-p{i}">{o}</div>' for i, o in enumerate(OFFERS)) + '</div>',
    '<div class="m3-stage" id="m3-stage">',
    '  <div class="m3-letter m3-glass" id="m3-letter"><div class="m3-lt">Lettre</div>'
    + "".join(f'<div class="m3-bar m3-lb" id="m3-lb{i}" style="width:{w}%"></div>' for i, w in enumerate(LETTER[0])) + '</div>',
    '  <div class="m3-cv m3-glass" id="m3-cv"><div class="m3-title" id="m3-title">' + CV_TITLES[0] + '</div>' + cv_blocks + '</div>',
    '</div>',
])
extra = """
    .m3-halo { position: absolute; left: -50px; top: 670px; width: 900px; height: 900px; border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.26) 0%, rgba(255,255,255,0.08) 38%, rgba(255,255,255,0) 68%); }
    .m3-pills { position: absolute; left: 0; top: 450px; width: 1080px; height: 110px; }
    .m3-pill { position: absolute; left: 50%; top: 0; transform: translateX(-50%); white-space: nowrap; padding: 26px 46px; border-radius: 60px;
      font-size: 42px; font-weight: 600; letter-spacing: -0.02em; opacity: 0; }
    .m3-stage { position: absolute; inset: 0; perspective: 1800px; }
    .m3-cv { position: absolute; left: 80px; top: 640px; width: 640px; height: 960px; border-radius: 40px; padding: 48px 46px; overflow: hidden; }
    .m3-title { font-size: 40px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.15; height: 100px; }
    .m3-blk { position: absolute; left: 46px; right: 46px; top: 0; overflow: hidden; border-radius: 18px; padding: 18px 20px;
      background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); }
    .m3-h { font-size: 22px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #BDBDB8; }
    .m3-bar { height: 12px; border-radius: 6px; background: rgba(255,255,255,0.22); margin-top: 18px; }
    .m3-keys { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }
    .m3-key { padding: 10px 20px; border-radius: 30px; border: 1.5px solid rgba(255,255,255,0.25); font-size: 24px; font-weight: 500; color: #CFCFCA; }
    .m3-key.on { color: #000; }
    .m3-letter { position: absolute; left: 600px; top: 760px; width: 420px; height: 780px; border-radius: 36px; padding: 44px 38px; }
    .m3-lt { font-size: 26px; font-weight: 600; color: #DADAD5; margin-bottom: 10px; }
    .m3-lb { margin-top: 30px; }"""
script = f"""
      const L = {json.dumps(LAYOUTS)}, KEYS = {json.dumps(KEYS)}, LIT = {json.dumps(LIT)}, LET = {json.dumps(LETTER)}, TITLES = {json.dumps(CV_TITLES)};
      const apply = (k, t, d) => {{
        Object.entries(L[k]).forEach(([id, [y, h]]) => tl.to("#m3-" + id, {{ y, height: h, duration: d, ease: "expo.inOut" }}, t));
        LET[k].forEach((w, i) => tl.to("#m3-lb" + i, {{ width: w + "%", duration: d, ease: "expo.inOut" }}, t + i * 0.02));
        KEYS[k].forEach((word, i) => {{
          const el = document.getElementById("m3-k" + i), on = LIT[k].includes(i);
          tl.call(() => {{ el.textContent = word; el.classList.toggle("on", false); }}, null, t + 0.05);
          tl.to(el, {{ backgroundColor: on ? "#FFFFFF" : "rgba(255,255,255,0)", color: on ? "#000000" : "#CFCFCA",
            boxShadow: on ? "0 0 22px rgba(255,255,255,0.85)" : "0 0 0 rgba(255,255,255,0)", duration: 0.25 }}, t + 0.1 + i * 0.03);
        }});
        tl.call(() => {{ document.getElementById("m3-title").textContent = TITLES[k]; }}, null, t + 0.12);
        tl.fromTo("#m3-title", {{ opacity: 0.2 }}, {{ opacity: 1, duration: 0.25, immediateRender: false }}, t + 0.12);
      }};
      // État de départ, sans animation.
      Object.entries(L[0]).forEach(([id, [y, h]]) => tl.set("#m3-" + id, {{ y, height: h }}, 0));
      // La caméra pivote vers le CV central.
      tl.fromTo("#m3-stage", {{ rotationY: 38, x: 260, opacity: 0, scale: 0.95, transformPerspective: 1800 }},
        {{ rotationY: 0, x: 0, opacity: 1, scale: 0.96, transformPerspective: 1800, duration: 0.6, ease: "expo.out" }}, 0);
      // Caméra continue : lent zoom et légère rotation, les cartes flottent dans le vide.
      tl.to("#m3-stage", {{ scale: 1.05, rotationY: -7, rotationX: 4, duration: 4.6, ease: "sine.inOut" }}, 0.6);
      tl.fromTo(".m3-halo", {{ opacity: 0.6, scale: 0.9 }}, {{ opacity: 1, scale: 1.08, duration: 5.2, ease: "sine.inOut" }}, 0);
      tl.fromTo("#m3-letter", {{ rotation: 0 }}, {{ rotation: 3, duration: 5, ease: "sine.inOut" }}, 0);
      // Les offres défilent ; à chaque offre, CV et lettre se réorganisent.
      const T = [0.4, 2.1, 3.8];
      T.forEach((t, k) => {{
        const pill = "#m3-p" + k;
        tl.fromTo(pill, {{ opacity: 0, xPercent: 10 }}, {{ opacity: 1, xPercent: -50, duration: 0.35, ease: "power3.out" }}, t);
        if (k < 2) tl.to(pill, {{ opacity: 0, xPercent: -110, duration: 0.25, ease: "power2.in" }}, T[k + 1] - 0.05);
        apply(k, t + 0.1, k === 0 ? 0.01 : 0.55);
        if (k > 0) tl.fromTo("#m3-cv", {{ rotationY: -12, z: -60, transformPerspective: 1600 }}, {{ rotationY: 0, z: 0, transformPerspective: 1600, duration: 0.7, ease: "expo.out", immediateRender: false }}, t + 0.05);
      }});
      tl.to("#m3-stage", {{ scale: 0.92, opacity: 0, duration: 0.35, ease: "power2.in" }}, 5.25);
      tl.to(".m3-pills", {{ opacity: 0, duration: 0.25 }}, 5.25);"""
(COMP / "03-sur-mesure.html").write_text(page("03-sur-mesure", p, extra, body, script))

# ===================== 04 · la rafale de formulaires (11 – 17) =====================
# Un champ de formulaires qui remplit tout l'écran ; la caméra le traverse,
# chaque formulaire rempli part vers l'avant et dépasse la caméra.
p = "f4"
COLS, ROWS = 7, 10
FW, FH, GAP = 300, 400, 40
CC, CR = 3, 5
CENTER = CR * COLS + CC
cx, cy = CC * (FW + GAP) + FW / 2, CR * (FH + GAP) + FH / 2
forms = []
for i in range(COLS * ROWS):
    c, r = i % COLS, i // COLS
    fields = "".join(f'<div class="f4-lab">{lab}</div><div class="f4-fld"><div class="f4-val" style="width:{w}%"></div></div>'
                     for lab, w in [("Nom", 52), ("Prénom", 44), ("E-mail", 78)])
    forms.append(f'<div class="f4-form" id="f4-{i}" style="left:{c * (FW + GAP)}px; top:{r * (FH + GAP)}px">'
                 f'<div class="f4-ft">Postuler</div>{fields}<div class="f4-lab">Pièce jointe</div><div class="f4-att"><div class="f4-cv">CV adapté.pdf</div></div></div>')
order = sorted((i for i in range(COLS * ROWS) if i != CENTER),
               key=lambda i: ((i % COLS - CC) ** 2 + ((i // COLS - CR) * 1.2) ** 2) ** 0.5)  # onde depuis le centre
body = "\n    ".join([
    '<div class="f4-halo" id="f4-halo"></div>',
    '<div class="f4-space"><div class="f4-grid" id="f4-grid">',
    *forms,
    '</div></div>',
])
extra = f"""
    .f4-halo {{ position: absolute; left: 40px; top: 460px; width: 1000px; height: 1000px; border-radius: 50%;
      background: radial-gradient(circle, rgba(255,255,255,0.20) 0%, rgba(255,255,255,0.05) 40%, rgba(255,255,255,0) 68%); }}
    .f4-space {{ position: absolute; inset: 0; perspective: 1400px; perspective-origin: 540px 960px; }}
    .f4-grid {{ position: absolute; left: {540 - cx}px; top: {960 - cy}px; width: {COLS * (FW + GAP)}px; height: {ROWS * (FH + GAP)}px;
      transform-origin: {cx}px {cy}px; transform-style: preserve-3d; }}
    /* Pas de backdrop-filter ici : 70 cartes sur du noir, le flou n'apporterait rien et coûterait cher au rendu. */
    .f4-form {{ position: absolute; width: {FW}px; height: {FH}px; border-radius: 26px; padding: 24px 22px;
      background: linear-gradient(150deg, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.04) 50%, rgba(255,255,255,0.09) 100%);
      border: 1.5px solid rgba(255,255,255,0.24); box-shadow: inset 0 2px 0 rgba(255,255,255,0.4); }}
    .f4-ft {{ font-size: 26px; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 4px; }}
    .f4-lab {{ margin-top: 12px; font-size: 15px; font-weight: 500; color: #A9A9A4; }}
    .f4-fld {{ margin-top: 6px; height: 40px; border-radius: 10px; border: 1.5px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.04);
      display: flex; align-items: center; padding: 0 12px; }}
    .f4-val {{ height: 10px; border-radius: 5px; background: #FFFFFF; transform-origin: 0 50%; transform: scaleX(0); }}
    .f4-att {{ margin-top: 6px; height: 50px; border-radius: 10px; border: 1.5px dashed rgba(255,255,255,0.28); display: flex; align-items: center; padding: 0 8px; }}
    .f4-cv {{ padding: 8px 14px; border-radius: 8px; background: #FFFFFF; color: #000; font-size: 15px; font-weight: 600; opacity: 0; }}"""
script = f"""
      const CENTER = {CENTER}, ORDER = {json.dumps(order)};
      const fill = (i, t, sp) => {{
        const f = "#f4-" + i;
        tl.to(f + " .f4-val", {{ scaleX: 1, duration: 0.07 * sp, stagger: 0.06 * sp, ease: "power2.out" }}, t);
        tl.to(f + " .f4-fld", {{ borderColor: "rgba(255,255,255,0.75)", duration: 0.08 * sp, stagger: 0.06 * sp }}, t);
        tl.to(f, {{ borderColor: "rgba(255,255,255,0.7)", boxShadow: "inset 0 2px 0 rgba(255,255,255,0.6), 0 0 40px rgba(255,255,255,0.35)", duration: 0.1 }}, t);
        tl.fromTo(f + " .f4-cv", {{ opacity: 0, x: 120, scale: 1.3 }}, {{ opacity: 1, x: 0, scale: 1, duration: 0.12 * sp, ease: "back.out(2.5)" }}, t + 0.2 * sp);
      }};
      // Propulsé vers l'avant et vers le haut : il grossit, dépasse la caméra et disparaît.
      const launch = (i, t) => tl.to("#f4-" + i, {{ z: 1500, y: -420, opacity: 0, duration: 0.5, ease: "power3.in" }}, t);
      // Gros plan sur un formulaire qui se remplit tout seul.
      tl.fromTo("#f4-grid", {{ z: 760 }}, {{ z: 700, duration: 1.0, ease: "sine.out" }}, 0);
      tl.fromTo("#f4-halo", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.6 }}, 0);
      fill(CENTER, 0.15, 2.2);
      // La caméra recule : le champ de formulaires remplit tout l'écran.
      tl.to("#f4-grid", {{ z: -1500, rotationX: 6, duration: 0.9, ease: "expo.inOut" }}, 1.0);
      launch(CENTER, 1.75);
      // Puis elle avance à travers, pendant que l'onde remplit et propulse chaque formulaire.
      tl.to("#f4-grid", {{ z: -700, rotationX: 0, duration: 4.1, ease: "power1.in" }}, 1.9);
      ORDER.forEach((i, k) => {{
        const t = 1.9 + k * 0.052;
        fill(i, t, 0.4);
        launch(i, t + 0.2);
      }});
      tl.to("#f4-halo", {{ scale: 1.6, opacity: 0, duration: 0.6 }}, 5.4);"""
(COMP / "04-formulaires.html").write_text(page("04-formulaires", p, extra, body, script))


# ===================== 05 · retour au réel, pluie de notifications (17 – 23) =====================
p = "n5"
notes = "".join(
    f'<div class="n5-note n5-glass" id="n5-n{i}"><div class="n5-ic">{EYES}</div><div class="n5-tx"><div class="n5-top"><b>Alice</b><span>maintenant</span></div>'
    f'<div class="n5-msg">{m}</div></div></div>' for i, m in enumerate(NOTIFS))
body = "\n    ".join([
    '<video id="n5-video" class="clip" src="assets/video/outro-recul.mp4" muted playsinline data-start="0" data-duration="6" data-track-index="0"></video>',
    '<div class="n5-dim"></div>',
    '<div class="n5-stack" id="n5-stack">' + notes + '</div>',
    '<div class="n5-end" id="n5-end"><div class="n5-logo">' + EYES + '</div><div class="n5-name">Alice</div><div class="n5-url">alice-agent.fr</div></div>',
])
extra = """
    #n5-video { position: absolute; inset: 0; width: 1080px; height: 1920px; object-fit: cover; }
    .n5-dim { position: absolute; inset: 0; background: rgba(0,0,0,0.7); }
    .n5-stack { position: absolute; left: 60px; top: 0; width: 960px; height: 1920px; }
    .n5-note { position: absolute; left: 0; width: 960px; border-radius: 44px; padding: 32px 36px; display: flex; gap: 28px; align-items: flex-start; opacity: 0;
      background: linear-gradient(150deg, rgba(40,40,44,0.55), rgba(20,20,24,0.45)); }
    .n5-ic { flex: none; width: 84px; height: 84px; border-radius: 22px; background: #ECF4F0; display: flex; align-items: center; justify-content: center; }
    .n5-ic svg { width: 64px; height: 32px; }
    .n5-tx { flex: 1; }
    .n5-top { display: flex; justify-content: space-between; font-size: 28px; color: #BDBDB8; }
    .n5-top b { color: #F5F5F2; font-weight: 600; }
    .n5-msg { margin-top: 8px; font-size: 38px; font-weight: 500; line-height: 1.25; letter-spacing: -0.015em; }
    .n5-end { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; opacity: 0; }
    .n5-logo { width: 220px; height: 220px; border-radius: 50%; background: #ECF4F0; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 0 80px rgba(255,255,255,0.25); }
    .n5-logo svg { width: 150px; height: 75px; }
    .n5-name { margin-top: 36px; font-size: 120px; font-weight: 700; letter-spacing: -0.05em; line-height: 1; }
    .n5-url { margin-top: 28px; padding: 22px 48px; border-radius: 60px; border: 1.5px solid rgba(255,255,255,0.35); font-size: 44px; font-weight: 600; }"""
script = """
      // Les notifications surgissent au centre et s'empilent en rafale (la plus récente en haut).
      const T = [0.45, 0.95, 1.4, 1.85], H = 200, BASE = 760;
      T.forEach((t, k) => {
        const id = "#n5-n" + k;
        tl.fromTo(id, { opacity: 0, y: BASE - 140, scale: 0.9 }, { opacity: 1, y: BASE, scale: 1, duration: 0.35, ease: "back.out(1.6)" }, t);
        for (let j = 0; j < k; j++) tl.to("#n5-n" + j, { y: BASE + (k - j) * H, duration: 0.3, ease: "power3.out" }, t);
        // Vibration du téléphone.
        tl.fromTo(id, { x: -7 }, { x: 7, duration: 0.04, repeat: 5, yoyo: true, ease: "none", immediateRender: false }, t + 0.1);
        tl.to(id, { x: 0, duration: 0.04 }, t + 0.34);
      });
      tl.to("#n5-stack", { y: -230, duration: 2.2, ease: "sine.inOut" }, 1.9);
      // Fin : la pile s'efface, Alice signe.
      tl.to("#n5-stack", { opacity: 0, scale: 0.94, duration: 0.35, ease: "power2.in" }, 4.3);
      tl.fromTo("#n5-end", { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.5, ease: "expo.out" }, 4.6);"""
(COMP / "05-notifications.html").write_text(page("05-notifications", p, extra, body, script))

# ===================== index =====================
SCENES = [("01-intro", 0, 2.4), ("02-signature", 2.4, 3.0), ("03-sur-mesure", 5.4, 5.6), ("04-formulaires", 11.0, 6.0), ("05-notifications", 17.0, 6.0)]
master = json.dumps({"version": 1, "nodes": [
    {"type": "compressor", "id": "m1", "label": "Glue", "params": {"threshold": -18, "ratio": 2, "attack": 15, "release": 180, "knee": 6}},
    {"type": "gain", "id": "m3", "label": "Loudness", "params": {"gain": 4}},
    {"type": "truepeak", "id": "m2", "label": "Ceiling", "params": {"ceiling": -1.5, "lookahead": 3, "release": 80}}]})
hosts = "\n".join(
    f'      <div id="el-{cid}" class="scene" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
    f'data-start="{a}" data-duration="{d}" data-track-index="{i % 2}"></div>' for i, (cid, a, d) in enumerate(SCENES))
index = f"""<!doctype html>
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
    <div id="root" data-composition-id="main" data-start="0" data-duration="23" data-width="1080" data-height="1920" data-fx-chain='{master}'>
{hosts}
      <audio id="sound" src="assets/audio/sound.mp3" data-start="0" data-duration="23" data-track-index="10" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""
(ROOT / "index.html").write_text(index)
print("ok")
