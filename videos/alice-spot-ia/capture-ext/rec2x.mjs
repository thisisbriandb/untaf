import { chromium } from '/home/user/untaf/tools/agent-bench/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const EXT = '/home/user/untaf/extension';
fs.rmSync('frames', { recursive: true, force: true }); fs.mkdirSync('frames');
const ctx = await chromium.launchPersistentContext('/tmp/claude-0/-home-user-untaf/5225086e-6df9-5de7-8737-cb57e0697953/scratchpad/extprof2', {
  executablePath: '/opt/pw-browsers/chromium', headless: true, locale: 'fr-FR',
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`, '--headless=new', '--lang=fr-FR'],
  viewport: { width: 1200, height: 1100 }, deviceScaleFactor: 2 });
let [sw] = ctx.serviceWorkers(); if (!sw) sw = await ctx.waitForEvent('serviceworker');
await sw.evaluate(() => chrome.storage.local.set({ session: { token: 'demo', expires_at: '2099-01-01T00:00:00Z', email: 'camille.martin@exemple.fr', api: 'http://127.0.0.1:8766', app: 'https://alice-agent.fr' } }));
const p = ctx.pages()[0] || await ctx.newPage();
await p.goto('http://127.0.0.1:3200/', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200);
const frames = []; let rec = true; const t0 = Date.now();
const loop = (async () => { while (rec) { const d = await p.screenshot({ type: 'png' }); frames.push({ t: (Date.now() - t0) / 1000, d: d.toString('base64') }); } })();
await p.waitForTimeout(800);
await p.getByText('Alice', { exact: true }).last().click(); await p.waitForTimeout(900);
await p.getByText(/Remplir avec Alice|Remplir à nouveau/).click(); await p.waitForTimeout(6500);
rec = false; await loop;
let list = ''; frames.forEach((f, i) => { const n = `frames/${String(i).padStart(5, '0')}.png`; fs.writeFileSync(n, Buffer.from(f.d, 'base64'));
  const dur = i + 1 < frames.length ? frames[i + 1].t - f.t : 0.05; list += `file '${n}'\nduration ${dur.toFixed(4)}\n`; });
fs.writeFileSync('frames.txt', list); console.log(frames.length, 'frames');
await ctx.close();
