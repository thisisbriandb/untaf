// Rend la page d'annonces en PNG et relève la position des annonces retenues (pixels de la texture).
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const here = fileURLToPath(new URL(".", import.meta.url));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 2048, height: 2730 } });
await p.goto("file://" + here + "page.html");
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: here + "page.png" });
const rects = await p.$$eval(".ad[data-target]", (els) => els.map((e) => { const r = e.getBoundingClientRect(); return { i: +e.dataset.target, x: r.x, y: r.y, w: r.width, h: r.height }; }));
writeFileSync(here + "targets.js", "window.TARGETS = " + JSON.stringify(rects.sort((a, b) => a.i - b.i)) + ";\n");
console.log(rects);
await b.close();
