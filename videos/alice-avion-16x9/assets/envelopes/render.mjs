// Rend les huit adresses en une planche (1024 × 520 chacune, empilées).
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import { fileURLToPath } from "node:url";
const here = fileURLToPath(new URL(".", import.meta.url));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1024, height: 4160 } });
await p.goto("file://" + here + "addresses.html");
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: here + "addresses.png" });
await b.close();
