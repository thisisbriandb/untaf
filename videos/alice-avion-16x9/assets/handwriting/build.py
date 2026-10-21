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

# Quatre feuilles, de plus en plus vite : on écrit la même lettre encore et encore.
# Chaque unité : (texte, x, y de la ligne de base, taille de l'em, début, durée).
SHEETS = [
    [("n° 35", 770, 175, 50, 0.15, 0.42), ("Madame, Monsieur,", 112, 430, 60, 0.66, 0.95)],
    [("n° 36", 770, 175, 50, 2.22, 0.32), ("Madame, Monsieur,", 112, 430, 60, 2.6, 0.72)],
    [("n° 37", 770, 175, 50, 3.78, 0.28), ("Madame, Monsieur,", 112, 430, 60, 4.1, 0.58),
     ("Actuellement à la recherche", 112, 540, 50, 4.75, 0.5)],
    [("n° 38", 770, 175, 50, 5.6, 0.25), ("Madame, Mons", 112, 430, 60, 5.9, 0.38)],
]
LIFT_FRAC = 0.2


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
    out = []
    for si, units in enumerate(SHEETS):
        for text, x0, y0, em, t0, dur in units:
            sc = em / UPM
            x, drift, strokes = x0, 0.0, []
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
                        pts.append([round(x + px * math.cos(rot) - py * math.sin(rot), 2), round(y0 + dy + px * math.sin(rot) + py * math.cos(rot), 2)])
                    strokes.append(pts)
                x += w * sc * rnd.uniform(0.97, 1.05)
            # vitesse constante dans l'unité, levers de stylo proportionnels aux sauts
            lens = []
            for pts in strokes:
                seg = [0.0]
                for a, b in zip(pts, pts[1:]):
                    seg.append(seg[-1] + math.dist(a, b))
                lens.append(seg)
            gaps = [math.dist(strokes[i - 1][-1], strokes[i][0]) for i in range(1, len(strokes))]
            v = sum(sg[-1] for sg in lens) / (dur * (1 - LIFT_FRAC))
            up, g_total, t = dur * LIFT_FRAC, (sum(gaps) or 1.0), t0
            for i, (pts, seg) in enumerate(zip(strokes, lens)):
                if i:
                    t += up * (0.25 / len(strokes) + 0.75 * gaps[i - 1] / g_total)
                d = seg[-1] / v
                out.append({"sheet": si, "t0": round(t, 4), "t1": round(t + d, 4), "pts": pts, "len": [round(q, 2) for q in seg]})
                t += d
    data = json.dumps({"strokes": out, "end": max(o["t1"] for o in out)})
    (HERE / "strokes.json").write_text(data)
    (HERE / "strokes.js").write_text("window.STROKES = " + data + ";\n")
    for si in range(len(SHEETS)):
        print("feuille", si, "fin", max(o["t1"] for o in out if o["sheet"] == si))

main()
