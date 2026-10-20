// Records real Alice dashboard screens against the mocked API.
// Usage: node capture.mjs [chat|canvas|candidatures ...]
import { chromium } from "/home/user/untaf/tools/agent-bench/node_modules/playwright/index.mjs";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { installMock, stopSseServer } from "./mock-api.mjs";

const OUT = path.dirname(fileURLToPath(import.meta.url));
const APP = "http://localhost:3100";
const W = Number(process.env.VW || 430), H = Number(process.env.VH || 860), DSF = 3;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const INIT = () => {
  localStorage.setItem("alice_session", JSON.stringify({ token: "demo", expires_at: "2099-01-01T00:00:00Z", email: "camille.martin@exemple.fr" }));
  localStorage.setItem("candidate_id", "demo-cand");
  localStorage.setItem("candidate_email", "camille.martin@exemple.fr");
  localStorage.setItem("candidate_name", "Camille");
  // MissionStream polls every 2.5 s; poll faster so the journal reads as live in a short clip.
  const si = window.setInterval;
  window.setInterval = (fn, ms, ...a) => si(fn, ms === 2500 ? 700 : ms, ...a);
  // Hide the Next.js dev indicator.
  const css = "nextjs-portal{display:none!important}";
  document.addEventListener("DOMContentLoaded", () => { const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s); });
};

async function scene(name, run) {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
  const tmp = path.join(OUT, ".rec-" + name);
  fs.rmSync(tmp, { recursive: true, force: true });
  const ctx = await browser.newContext({
    viewport: { width: W, height: H }, deviceScaleFactor: DSF, locale: "fr-FR", timezoneId: "Europe/Paris",
  });
  const errors = [];
  await installMock(ctx, { scene: name === "envoi" ? "canvas" : name, log: (m) => { console.log(m); errors.push(m); } });
  await ctx.addInitScript(INIT);
  const page = await ctx.newPage();
  fs.mkdirSync(tmp, { recursive: true });
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  let n = 0;
  cdp.on("Page.screencastFrame", async (f) => {
    const file = path.join(tmp, `f${String(n++).padStart(6, "0")}.jpg`);
    fs.writeFileSync(file, Buffer.from(f.data, "base64"));
    frames.push({ file, t: f.metadata.timestamp * 1000 });
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 95, maxWidth: W * DSF, maxHeight: H * DSF, everyNthFrame: 1 });
  page.on("pageerror", (e) => errors.push("pageerror " + e.message));
  page.on("console", (m) => m.type() === "error" && errors.push("console " + m.text()));
  const startAt = await run(page);            // ms timestamp where the clip should start
  const endAt = Date.now();
  await cdp.send("Page.stopScreencast").catch(() => {});
  await sleep(300);
  await ctx.close();
  await browser.close();
  // Build a concat list from frame timestamps, starting at startAt (last frame before it is the first shown).
  let i = frames.findLastIndex((f) => f.t <= startAt); if (i < 0) i = 0;
  const sel = frames.slice(i);
  let list = "";
  sel.forEach((f, k) => {
    const from = Math.max(f.t, startAt), to = k + 1 < sel.length ? sel[k + 1].t : endAt;
    list += `file '${f.file}'\nduration ${Math.max(0.001, (to - from) / 1000).toFixed(4)}\n`;
  });
  list += `file '${sel.at(-1).file}'\n`;
  fs.writeFileSync(path.join(tmp, "list.txt"), list);
  const webm = path.join(OUT, `${name}.webm`), mp4 = path.join(OUT, `${name}.mp4`);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(tmp, "list.txt"), "-vf", `fps=30,scale=${W * DSF}:${H * DSF}`, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", "-movflags", "+faststart", "-an", mp4]);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", mp4, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "24", "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", "-an", webm]);
  const ss = (startAt - frames[0]?.t) / 1000;
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`${name}: ${webm} (trim ${ss.toFixed(2)}s)`, errors.length ? "\n  issues: " + errors.join("\n  ") : "");
}

const SCENES = {
  // Format téléphone : l'offre s'ouvre, « Valider et envoyer », « Vas-y », envoyée.
  async envoi(page) {
    await page.goto(`${APP}/dashboard`);
    const card = page.getByRole("button", { name: /Chargée de marketing digital/ }).first();
    await card.waitFor();
    await sleep(1500);
    const start = Date.now();
    await sleep(1200);
    await card.click();
    const valider = page.getByRole("button", { name: "Valider et envoyer" });
    await valider.waitFor();
    await sleep(1800);
    await valider.click();
    const go = page.getByRole("button", { name: "Vas-y" });
    await go.waitFor();
    await sleep(1500);
    await page.screenshot({ path: path.join(OUT, "envoi-confirm.png") });
    await go.click();
    await page.getByText("Candidature envoyée à Atelier Nord.").first().waitFor({ timeout: 15000 });
    await sleep(2400);
    await page.screenshot({ path: path.join(OUT, "envoi.png") });
    return start;
  },
  async chat(page) {
    await page.goto(`${APP}/dashboard`);
    const input = page.getByPlaceholder(/Dis-moi ce que tu cherches/);
    await input.waitFor();
    await page.getByText("Je m'y mets…").waitFor();
    await sleep(1200);
    const start = Date.now();
    await sleep(900);
    await input.click();
    await input.pressSequentially("Trouve-moi une alternance en marketing à Lyon", { delay: 45 });
    await sleep(400);
    await input.press("Enter");
    await page.getByText("Je passe les offres en revue…").waitFor();
    await page.getByText(/attend ton feu vert/).waitFor({ timeout: 20000 });
    await sleep(1600);
    await page.screenshot({ path: path.join(OUT, "chat.png") });
    return start;
  },
  async canvas(page) {
    await page.goto(`${APP}/dashboard`);
    const card = page.getByRole("button", { name: /Chargée de marketing digital/ }).first();
    await card.waitFor();
    await card.click();
    await page.getByText("Tes missions").waitFor();
    const valider = page.getByRole("button", { name: "Valider et envoyer" });
    await valider.waitFor();
    await sleep(500);
    const start = Date.now();
    await sleep(1800);
    await page.locator(".scroll-discreet").filter({ hasText: "Tes missions" }).last().evaluate((el) => el.scrollBy({ top: 260, behavior: "smooth" }));
    await sleep(1200);
    await valider.click();
    const go = page.getByRole("button", { name: "Vas-y" });
    await go.waitFor();
    await sleep(1400);
    await go.click();
    await page.getByText("Candidature envoyée à Atelier Nord.").first().waitFor({ timeout: 15000 });
    await sleep(2200);
    await page.screenshot({ path: path.join(OUT, "canvas.png") });
    return start;
  },
  async candidatures(page) {
    await page.goto(`${APP}/dashboard?tab=candidatures`);
    await page.getByText("Studio Ferro").first().waitFor();
    await sleep(1200);
    await page.screenshot({ path: path.join(OUT, "candidatures.png") });
    const start = Date.now();
    await sleep(700);
    await page.locator(".scroll-discreet").filter({ hasText: "Candidatures" }).first().evaluate(async (el) => {
      const max = el.scrollHeight - el.clientHeight;
      const t0 = performance.now(), dur = 2600;
      await new Promise((res) => {
        const f = (t) => { const p = Math.min(1, (t - t0) / dur); el.scrollTop = max * (0.5 - Math.cos(Math.PI * p) / 2); p < 1 ? requestAnimationFrame(f) : res(); };
        requestAnimationFrame(f);
      });
    });
    await sleep(700);
    return start;
  },
};

const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(SCENES);
for (const n of wanted) await scene(n, SCENES[n]);
stopSseServer();
