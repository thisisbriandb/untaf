"""Transforme le texte de la lettre en tracés de stylo horodatés (strokes.json).

Police : EMS Felix (tracé d'un seul trait, SIL Open Font License), légèrement
irrégularisée lettre par lettre pour ressembler à une vraie main.
Coordonnées en pixels de la texture du papier (1024 × 1448, A4).
"""
import html
import json
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = (HERE / "EMSFelix.svg").read_text()
UPM = 1000.0

LINES = [  # (texte, x, y de la ligne de base, taille de l'em en px)
    ("Madame, Monsieur,", 112, 430, 60),
    ("Actuellement à la recherche d'une alternance,", 112, 540, 50),
    ("je me permets de vous adresser ma candidature", 112, 612, 50),
    ("pour le poste de chargée de marketing digital.", 112, 684, 50),
]
T_START = 2.75                  # premier contact du stylo (s)
LINE_DUR = [2.3, 2.0, 1.5, 1.15]  # durée de chaque ligne : la main accélère, on écrit encore et encore
LINE_GAP = [0.35, 0.2, 0.15]      # retour à la ligne
LIFT_FRAC = 0.22                # part de la ligne passée stylo levé


def glyphs():
    g = {}
    for m in re.finditer(r"<glyph\s([^>]*)/?>", SRC):
        a = m.group(1)
        u = re.search(r'unicode="([^"]*)"', a)
        d = re.search(r'\sd="([^"]*)"', a)
        w = re.search(r'horiz-adv-x="([^"]*)"', a)
        if u:
            g[html.unescape(u.group(1))] = (d.group(1) if d else "", float(w.group(1)) if w else 500.0)
    return g


def parse(d):
    """Chemin SVG (M, L, C absolus) → liste de polylignes."""
    toks = re.findall(r"[MLCZz]|-?\d*\.?\d+(?:e-?\d+)?", d)
    strokes, cur, i, cmd = [], None, 0, None
    while i < len(toks):
        t = toks[i]
        if t in "MLCZz":
            cmd = t; i += 1
            if t in "Zz" and cur:
                cur.append(cur[0])
            continue
        if cmd == "M":
            cur = [(float(toks[i]), float(toks[i + 1]))]; strokes.append(cur); i += 2; cmd = "L"
        elif cmd == "L":
            cur.append((float(toks[i]), float(toks[i + 1]))); i += 2
        elif cmd == "C":
            p0 = cur[-1]
            p1, p2, p3 = [(float(toks[i + k]), float(toks[i + k + 1])) for k in (0, 2, 4)]
            for s in range(1, 9):
                u = s / 8
                x = (1 - u) ** 3 * p0[0] + 3 * (1 - u) ** 2 * u * p1[0] + 3 * (1 - u) * u * u * p2[0] + u ** 3 * p3[0]
                y = (1 - u) ** 3 * p0[1] + 3 * (1 - u) ** 2 * u * p1[1] + 3 * (1 - u) * u * u * p2[1] + u ** 3 * p3[1]
                cur.append((x, y))
            i += 6
        else:
            i += 1
    return [s for s in strokes if len(s) > 1]


def main():
    G = glyphs()
    rnd = random.Random(20261020)
    strokes = []
    for li, (text, x0, y0, em) in enumerate(LINES):
        sc = em / UPM
        x = x0
        drift = 0.0
        for ch in text:
            d, w = G.get(ch, ("", 400.0))
            drift += rnd.uniform(-0.6, 0.6)
            rot = rnd.uniform(-0.035, 0.035)
            k = sc * rnd.uniform(0.96, 1.04)
            dy = drift * 0.6 + rnd.uniform(-1.2, 1.2)
            for poly in parse(d):
                pts = []
                for gx, gy in poly:
                    px, py = gx * k, -gy * k
                    rx = px * math.cos(rot) - py * math.sin(rot)
                    ry = px * math.sin(rot) + py * math.cos(rot)
                    pts.append([round(x + rx, 2), round(y0 + dy + ry, 2)])
                strokes.append((li, pts))
            x += w * sc * rnd.uniform(0.97, 1.05)

    # Horodatage : chaque ligne tient dans sa durée ; vitesse constante dans la ligne, levers proportionnels.
    out, t = [], T_START
    for li in range(len(LINES)):
        line = [p for l, p in strokes if l == li]
        lens = []
        for pts in line:
            seg = [0.0]
            for a, b in zip(pts, pts[1:]):
                seg.append(seg[-1] + math.dist(a, b))
            lens.append(seg)
        gaps = [math.dist(line[i - 1][-1], line[i][0]) for i in range(1, len(line))]
        down = LINE_DUR[li] * (1 - LIFT_FRAC)
        up = LINE_DUR[li] * LIFT_FRAC
        v_down = sum(sg[-1] for sg in lens) / down
        g_total = sum(gaps) or 1.0
        for i, (pts, seg) in enumerate(zip(line, lens)):
            if i:
                t += up * (0.25 / len(line) + 0.75 * gaps[i - 1] / g_total)
            dur = seg[-1] / v_down
            out.append({"t0": round(t, 4), "t1": round(t + dur, 4), "line": li, "pts": pts, "len": [round(x, 2) for x in seg]})
            t += dur
        if li < len(LINE_GAP):
            t += LINE_GAP[li]
    data = json.dumps({"strokes": out, "end": round(t, 3)})
    (HERE / "strokes.json").write_text(data)
    (HERE / "strokes.js").write_text("window.STROKES = " + data + ";\n")
    print("tracés", len(out), "fin des lignes", [max(o["t1"] for o in out if o["line"] == li) for li in range(len(LINES))])

main()
