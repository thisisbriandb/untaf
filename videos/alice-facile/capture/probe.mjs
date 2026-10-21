import { chromium } from "/home/user/untaf/tools/agent-bench/node_modules/playwright/index.mjs";
import { installMock, stopSseServer } from "../../alice-spot-ia/capture/mock-api.mjs";
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await b.newContext({ viewport: { width: 430, height: 860 }, deviceScaleFactor: 2, locale: "fr-FR" });
await installMock(ctx, { scene: "canvas", log: console.log });
await ctx.addInitScript(() => { localStorage.setItem("alice_session", JSON.stringify({ token: "demo", expires_at: "2099-01-01T00:00:00Z", email: "camille.martin@exemple.fr" })); localStorage.setItem("candidate_id", "demo-cand"); localStorage.setItem("candidate_name", "Camille"); });
const p = await ctx.newPage();
await p.goto("http://localhost:3100/dashboard"); await p.waitForTimeout(6000);
await p.screenshot({ path: "probe1.png" });
const card = p.getByRole("button", { name: /Chargée de marketing digital/ }).first();
console.log("card count", await card.count());
if (await card.count()) { await card.click(); await p.waitForTimeout(3000); await p.screenshot({ path: "probe2.png" }); }
await b.close(); stopSseServer();
