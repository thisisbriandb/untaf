// Rend chaque bloc du CV en PNG transparent ; le film les réordonne pour « adapter » le CV à l'offre.
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const here = fileURLToPath(new URL(".", import.meta.url));
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1024, height: 1600 } });
await p.goto("file://" + here + "cv.html");
await p.evaluate(() => document.fonts.ready);
const sizes = {};
for (const id of ["header", "skills", "skillsG", "exp", "edu"]) {
  const el = await p.$("#" + id);
  const box = await el.boundingBox();
  sizes[id] = Math.ceil(box.height);
  await p.screenshot({ path: here + id + ".png", omitBackground: true, clip: { x: 0, y: box.y, width: 1024, height: Math.ceil(box.height) } });
}
writeFileSync(here + "blocks.js", "window.CV_BLOCKS = " + JSON.stringify(sizes) + ";\n");
console.log(sizes);
await b.close();
