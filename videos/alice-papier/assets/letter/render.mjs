// Rend la lettre propre (typed.html) en PNG transparent, à la taille de la texture du papier.
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import { fileURLToPath } from "node:url";
const here = fileURLToPath(new URL(".", import.meta.url));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1024, height: 1448 } });
await p.goto("file://" + here + "typed.html");
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: here + "typed.png", omitBackground: true });
await b.close();
