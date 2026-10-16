import { chromium } from '/home/user/untaf/tools/agent-bench/node_modules/playwright/index.mjs';
const EXT = '/home/user/untaf/extension';
const ctx = await chromium.launchPersistentContext('/tmp/claude-0/-home-user-untaf/5225086e-6df9-5de7-8737-cb57e0697953/scratchpad/extprof', {
  executablePath: '/opt/pw-browsers/chromium', headless: true,
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`, '--headless=new', '--lang=fr-FR'],
  viewport: { width: 1200, height: 1100 }, deviceScaleFactor: 2, locale: 'fr-FR',
  recordVideo: { dir: 'vid', size: { width: 1200, height: 1100 } },
});
let [sw] = ctx.serviceWorkers(); if (!sw) sw = await ctx.waitForEvent('serviceworker');
await sw.evaluate(() => chrome.storage.local.set({ session: { token: 'demo', expires_at: '2099-01-01T00:00:00Z', email: 'camille.martin@exemple.fr', api: 'http://127.0.0.1:8766', app: 'https://alice-agent.fr' } }));
const p = ctx.pages()[0] || await ctx.newPage();
await p.goto('http://127.0.0.1:3200/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
const pill = p.getByText('Alice', { exact: true }).last();
await pill.click(); await p.waitForTimeout(900);
await p.getByText(/Remplir avec Alice|Remplir à nouveau/).click();
await p.waitForTimeout(6000);
await p.screenshot({ path: 'filled.png' });
await ctx.close();
