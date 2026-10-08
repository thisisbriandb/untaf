/**
 * Banc d'essai « computer use » pour Alice.
 *
 * Un modèle regarde des captures d'écran et renvoie des actions (cliquer,
 * taper, faire défiler) ; ce script les exécute dans un vrai navigateur, sur
 * de vrais formulaires de candidature, et mesure ce qui marche.
 *
 * RIEN N'EST JAMAIS SOUMIS : toute requête autre que GET est bloquée au niveau
 * du réseau, et un clic sur un bouton d'envoi est refusé avant d'être fait.
 *
 * Usage (sur ta machine, la clé ne quitte pas ton ordinateur) :
 *   npm install && npx playwright install chromium
 *   MODEL_API_KEY=... node bench.mjs --probe            # vérifie la clé et le format
 *   MODEL_API_KEY=... node bench.mjs                    # formulaire de test local
 *   MODEL_API_KEY=... node bench.mjs https://boards.greenhouse.io/...  https://jobs.lever.co/...
 *
 * Options d'environnement :
 *   MODEL_API_BASE (défaut https://api.meta.ai/v1), MODEL (défaut muse-spark-1.3),
 *   MAX_STEPS (défaut 40), HEADLESS=0 pour voir le navigateur.
 */

import { chromium } from "playwright";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const API = (process.env.MODEL_API_BASE || "https://api.meta.ai/v1").replace(/\/+$/, "");
const MODEL = process.env.MODEL || "muse-spark-1.3";
const KEY = process.env.MODEL_API_KEY;
const MAX_STEPS = Number(process.env.MAX_STEPS || 40);
//: Réflexion du modèle : low | medium | high. « high » (défaut chez Meta) est lent et coûteux.
const EFFORT = process.env.EFFORT || "low";
const CALL_TIMEOUT_MS = Number(process.env.CALL_TIMEOUT || 180) * 1000;
const t0 = Date.now();
const elapsed = () => `${Math.round((Date.now() - t0) / 1000)}s`;
let firstCallShown = false;
const VIEWPORT = { width: 1280, height: 900 };

// Candidat fictif : jamais de vraies données personnelles dans un banc d'essai.
const CANDIDATE = {
  first_name: "Camille", last_name: "Test", email: "camille.test@example.com",
  phone: "06 12 34 56 78", city: "Lyon", linkedin: "https://www.linkedin.com/in/camille-test",
  cover_letter: "Madame, Monsieur,\n\nDéveloppeuse Python depuis trois ans, je souhaite rejoindre votre équipe…\n\nCamille Test",
  cv_path: path.join(HERE, "cv-test.pdf"),
};

const TASK = `Tu remplis un formulaire de candidature pour la candidate ci-dessous.
Remplis chaque champ que tu peux à partir de ces informations, joins le CV si un champ fichier le demande
(le fichier est déjà sélectionnable : clique sur le champ et je m'occupe du fichier), réponds aux questions
simples. Ne coche JAMAIS une case de consentement ou d'acceptation de conditions. N'ENVOIE PAS le formulaire :
quand tout ce que tu peux remplir est rempli, arrête-toi et dis "TERMINÉ" en listant ce qui reste à faire.

Prénom : ${CANDIDATE.first_name}
Nom : ${CANDIDATE.last_name}
E-mail : ${CANDIDATE.email}
Téléphone : ${CANDIDATE.phone}
Ville : ${CANDIDATE.city}
LinkedIn : ${CANDIDATE.linkedin}
Lettre de motivation :
${CANDIDATE.cover_letter}`;

// ── API ─────────────────────────────────────────────────────────────────────

async function call(body) {
  if (EFFORT && !body.reasoning) body = { ...body, reasoning: { effort: EFFORT } };
  const started = Date.now();
  process.stdout.write(`  … appel au modèle (${elapsed()})`);
  let res;
  try {
    res = await fetch(`${API}/responses`, {
      method: "POST",
      headers: { Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(CALL_TIMEOUT_MS),
    });
  } catch (e) {
    process.stdout.write("\n");
    throw new Error(`pas de réponse du modèle en ${CALL_TIMEOUT_MS / 1000}s (${e.name})`);
  }
  process.stdout.write(` → ${res.status} en ${Math.round((Date.now() - started) / 1000)}s\n`);
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* corps non JSON */ }
  if (!res.ok) throw new Error(`API ${res.status} : ${text.slice(0, 600)}`);
  return json;
}

const shot = async (page) =>
  `data:image/png;base64,${(await page.screenshot({ type: "png" })).toString("base64")}`;

/** Les actions d'un appel, quelle que soit la forme (une action ou une liste). */
function actionsOf(item) {
  if (Array.isArray(item.actions)) return item.actions;
  if (item.action) return [item.action];
  return [];
}

// ── Garde-fous : rien ne part ────────────────────────────────────────────────

const SUBMIT_TEXT = /envoyer|soumettre|submit|send application|postuler maintenant|apply now|valider ma candidature/i;

async function isSubmitAt(page, x, y) {
  return page.evaluate(([x, y, re]) => {
    const el = document.elementFromPoint(x, y);
    const b = el && el.closest("button, input[type=submit], [role=button], a");
    if (!b) return false;
    const label = (b.innerText || b.value || b.getAttribute("aria-label") || "").trim();
    return b.type === "submit" || new RegExp(re, "i").test(label);
  }, [x, y, SUBMIT_TEXT.source]);
}

/** Noms de touches façon X11 / xdotool (BackSpace, Return, ctrl…) → Playwright. */
const KEY_MAP = {
  backspace: "Backspace", return: "Enter", enter: "Enter", tab: "Tab", escape: "Escape", esc: "Escape",
  delete: "Delete", del: "Delete", space: " ", home: "Home", end: "End", insert: "Insert",
  page_up: "PageUp", pageup: "PageUp", prior: "PageUp", page_down: "PageDown", pagedown: "PageDown", next: "PageDown",
  up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight",
  arrowup: "ArrowUp", arrowdown: "ArrowDown", arrowleft: "ArrowLeft", arrowright: "ArrowRight",
  ctrl: "Control", control: "Control", control_l: "Control", control_r: "Control",
  alt: "Alt", alt_l: "Alt", shift: "Shift", shift_l: "Shift", super: "Meta", cmd: "Meta", meta: "Meta", win: "Meta",
};
function pwKey(k) {
  const name = String(k).trim();
  const mapped = KEY_MAP[name.toLowerCase()];
  if (mapped) return mapped;
  if (/^f\d{1,2}$/i.test(name)) return name.toUpperCase();
  return name.length === 1 ? name : name[0].toUpperCase() + name.slice(1);
}

async function execute(page, a, log) {
  try {
    return await executeRaw(page, a, log);
  } catch (e) {
    // Une action ratée ne fait pas tomber le test : on la note, le modèle
    // verra l'écran inchangé et pourra s'adapter.
    log.push({ failed_action: a, error: String(e.message || e).slice(0, 200) });
    console.log(`    ✗ action ${a.type} impossible : ${String(e.message || e).split("\n")[0].slice(0, 120)}`);
    return "FAILED";
  }
}

async function executeRaw(page, a, log) {
  const t = a.type;
  if (t === "click" || t === "double_click") {
    if (await isSubmitAt(page, a.x, a.y)) {
      log.push({ blocked: "clic sur un bouton d'envoi refusé", x: a.x, y: a.y });
      return "BLOCKED_SUBMIT";
    }
    // Champ fichier : on fournit le CV au lieu d'ouvrir la boîte de dialogue.
    const chooser = page.waitForEvent("filechooser", { timeout: 1500 }).catch(() => null);
    await page.mouse.click(a.x, a.y, { button: a.button === "right" ? "right" : "left", clickCount: t === "double_click" ? 2 : 1 });
    const fc = await chooser;
    if (fc) { await fc.setFiles(CANDIDATE.cv_path); log.push({ file: "CV joint" }); }
  } else if (t === "type") {
    await page.keyboard.type(a.text ?? "", { delay: 5 });
  } else if (t === "keypress" || t === "key") {
    const keys = [].concat(a.keys ?? a.key ?? []).flatMap((k) => String(k).split("+")).map(pwKey);
    if (keys.includes("Enter")) {
      log.push({ blocked: "Entrée refusée (pourrait envoyer)" });
      return "OK";
    }
    // Plusieurs touches = un raccourci (ctrl+a…), pas une suite de frappes.
    if (keys.length) await page.keyboard.press(keys.join("+"));
  } else if (t === "scroll") {
    await page.mouse.move(a.x ?? 640, a.y ?? 450);
    await page.mouse.wheel(a.scroll_x ?? 0, a.scroll_y ?? 400);
  } else if (t === "move") {
    await page.mouse.move(a.x, a.y);
  } else if (t === "wait") {
    await page.waitForTimeout(1500);
  } else if (t !== "screenshot") {
    log.push({ unknown_action: a });
  }
  await page.waitForTimeout(400);
  return "OK";
}

// ── Un formulaire ────────────────────────────────────────────────────────────

async function runOne(browser, url) {
  const context = await browser.newContext({ viewport: VIEWPORT, locale: "fr-FR" });
  const page = await context.newPage();
  const blockedRequests = [];
  // Garde-fou réseau : aucune requête d'écriture ne quitte le navigateur.
  await page.route("**/*", (route) => {
    const m = route.request().method();
    if (m !== "GET" && m !== "HEAD" && m !== "OPTIONS") {
      blockedRequests.push(`${m} ${route.request().url().slice(0, 120)}`);
      return route.abort();
    }
    return route.continue();
  });

  const started = Date.now();
  const log = [];
  const usage = { input_tokens: 0, output_tokens: 0 };
  let steps = 0, finalText = "", error = null;

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);
    const tools = [{ type: "computer" }];
    let resp = await call({
      model: MODEL, tools, truncation: "auto",
      input: [{ role: "user", content: [
        { type: "input_text", text: TASK },
        { type: "input_image", image_url: await shot(page) },
      ] }],
    });

    for (; steps < MAX_STEPS; steps++) {
      if (resp.usage) {
        usage.input_tokens += resp.usage.input_tokens || 0;
        usage.output_tokens += resp.usage.output_tokens || 0;
      }
      const output = resp.output || [];
      const calls = output.filter((o) => o.type === "computer_call");
      // La première fois, on montre la forme exacte d'un appel : utile si
      // le format diffère de ce que le script attend.
      if (calls.length && !firstCallShown) {
        firstCallShown = true;
        console.log("  forme d'un appel :", JSON.stringify(calls[0]).slice(0, 400));
      }
      if (!calls.length) {
        console.log(`  fin : sorties ${JSON.stringify(output.map((o) => o.type))}, statut ${resp.status}`);
      }
      finalText = output.filter((o) => o.type === "message")
        .flatMap((m) => (m.content || []).map((c) => c.text || "")).join("\n") || finalText;
      if (!calls.length) break;

      const outputs = [];
      for (const c of calls) {
        const acts = actionsOf(c);
        if (!acts.length) console.log("  ⚠ appel sans action reconnue :", JSON.stringify(c).slice(0, 300));
        for (const a of acts) {
          log.push({ step: steps, action: a.type, ...(a.text ? { text: String(a.text).slice(0, 40) } : {}) });
          const keysTxt = a.keys || a.key ? ` [${[].concat(a.keys ?? a.key).join("+")}]` : "";
          console.log(`  étape ${steps + 1} : ${a.type}${keysTxt}${a.text ? ` « ${String(a.text).slice(0, 30)} »` : ""}` +
            `${a.x != null ? ` (${a.x},${a.y})` : ""}`);
          const r = await execute(page, a, log);
          if (r === "BLOCKED_SUBMIT") console.log("    ⛔ clic d'envoi refusé : rien n'est parti");
        }
        // Points de vigilance signalés par le modèle (site sensible, action à
        // confirmer…) : l'API exige qu'on les confirme un par un. On les garde
        // dans le rapport — c'est ce qu'il faudrait montrer au candidat.
        const checks = c.pending_safety_checks || [];
        for (const chk of checks) {
          log.push({ safety_check: chk.code || chk.id, message: chk.message });
          console.log(`    ⚠ point de vigilance : ${chk.code || ""} ${chk.message || ""}`.trimEnd());
        }
        outputs.push({
          type: "computer_call_output", call_id: c.call_id || c.id,
          ...(checks.length ? { acknowledged_safety_checks: checks.map((k) => ({ id: k.id, code: k.code, message: k.message })) } : {}),
          output: { type: "computer_screenshot", image_url: await shot(page) },
        });
      }
      resp = await call({ model: MODEL, tools, truncation: "auto", previous_response_id: resp.id, input: outputs });
    }
  } catch (e) {
    error = String(e.message || e);
  }

  // Ce qui est réellement rempli sur la page (cadre principal et iframes).
  const filled = [];
  for (const frame of page.frames()) {
    try {
      filled.push(...await frame.evaluate(() =>
        [...document.querySelectorAll("input, textarea, select")]
          .filter((el) => !["hidden", "submit", "button"].includes(el.type))
          .map((el) => ({
            field: el.name || el.id || el.type,
            value: el.type === "file" ? [...el.files].map((f) => f.name).join(",")
              : el.type === "checkbox" || el.type === "radio" ? (el.checked ? "coché" : "")
              : String(el.value || "").slice(0, 40),
          }))
          .filter((f) => f.value)));
    } catch { /* cadre inaccessible */ }
  }
  await page.screenshot({ path: path.join(HERE, `result-${new URL(url).hostname}.png`), fullPage: true }).catch(() => {});
  await context.close();
  return {
    url, steps, seconds: Math.round((Date.now() - started) / 1000), usage, error,
    filled, final_message: finalText.slice(0, 500), blocked_requests: blockedRequests, log,
  };
}

// ── Lancement ────────────────────────────────────────────────────────────────

function serveLocalForm() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.end(fs.readFileSync(path.join(HERE, "form.html")));
    }).listen(0, "127.0.0.1", () => resolve(server));
  });
}

function ensureTestCv() {
  if (fs.existsSync(CANDIDATE.cv_path)) return;
  // PDF minimal valide : un CV fictif d'une ligne.
  const pdf = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 72 760 Td (Camille Test - CV) Tj ET\nendstream endobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n";
  fs.writeFileSync(CANDIDATE.cv_path, pdf);
}

async function main() {
  if (!KEY) {
    console.error("MODEL_API_KEY manquante. Exemple : MODEL_API_KEY=... node bench.mjs --probe");
    process.exit(1);
  }
  const args = process.argv.slice(2);

  if (args.includes("--probe")) {
    // Vérifie la clé, le modèle et la forme d'une réponse avec l'outil « computer ».
    const r = await call({
      model: MODEL, tools: [{ type: "computer" }],
      input: [{ role: "user", content: [{ type: "input_text", text: "Dis simplement bonjour." }] }],
    });
    console.log(JSON.stringify(r, null, 2).slice(0, 3000));
    return;
  }

  ensureTestCv();
  let server = null;
  let urls = args.filter((a) => /^https?:\/\//.test(a));
  if (!urls.length) {
    server = await serveLocalForm();
    urls = [`http://127.0.0.1:${server.address().port}/`];
  }

  const browser = await chromium.launch({ headless: process.env.HEADLESS !== "0" });
  const results = [];
  for (const url of urls) {
    console.log(`\n▶ ${url}`);
    const r = await runOne(browser, url);
    results.push(r);
    console.log(`  ${r.steps} étapes, ${r.seconds}s, ${r.filled.length} champs remplis` +
      `${r.error ? `, ERREUR : ${r.error}` : ""}`);
    console.log(`  jetons : ${r.usage.input_tokens} en entrée, ${r.usage.output_tokens} en sortie`);
    if (r.blocked_requests.length) console.log(`  requêtes bloquées (rien n'est parti) : ${r.blocked_requests.length}`);
  }
  await browser.close();
  server?.close();
  const out = path.join(HERE, `report-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
  fs.writeFileSync(out, JSON.stringify({ model: MODEL, api: API, results }, null, 2));
  console.log(`\nRapport : ${out}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
