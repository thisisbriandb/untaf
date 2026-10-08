/**
 * Sonde de formulaires de candidature — sans IA, sans rien envoyer.
 *
 * Pour chaque lien « Postuler », elle répond à une question : Alice peut-elle
 * envoyer cette candidature sans navigateur (en rejouant la requête), faut-il
 * un navigateur, ou seule l'extension (dans le navigateur du candidat) peut-elle
 * le faire ?
 *
 *   1. Elle rend la page et lit le formulaire final : champs, noms, types,
 *      obligatoires, contraintes, champs cachés — et vérifie s'ils sont déjà
 *      dans le HTML brut (lisibles sans JavaScript).
 *   2. Elle remplit avec un candidat fictif, clique sur « Envoyer »… et coupe la
 *      requête au réseau : rien ne part, mais on enregistre ce qui serait parti
 *      (adresse, format, noms des champs, en-têtes utiles).
 *   3. Elle repère ce qui empêche de rejouer : captcha, connexion, dépôt du CV
 *      en deux temps.
 *
 * Usage :
 *   node probe.mjs <url> [<url> …]        # ou : node probe.mjs --file liens.txt
 *   HEADLESS=0 node probe.mjs <url>       # pour regarder
 */

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CV_PATH = path.join(HERE, "cv-test.pdf");
const FAKE = {
  first: "Camille", last: "Test", full: "Camille Test", email: "camille.test@example.com",
  phone: "0612345678", city: "Lyon", url: "https://www.linkedin.com/in/camille-test",
  text: "Réponse de test", number: "1", date: "2026-11-01",
};

const CAPTCHA_SCRIPT = /recaptcha|hcaptcha\.com|challenges\.cloudflare\.com|turnstile|arkoselabs|funcaptcha|captcha-delivery|geetest/i;
const CAPTCHA_FIELD = /g-recaptcha-response|h-captcha-response|cf-turnstile-response|captcha/i;
const LOGIN_TEXT = /se connecter|connexion|sign in|log in|create (an )?account|créer (un|mon) compte|mot de passe oublié/i;
const APPLY_TEXT = /^(postuler|apply|candidater|je postule|apply now|apply for this job|postuler maintenant)\b/i;
const SUBMIT_TEXT = /envoyer|soumettre|submit|send|postuler|apply|valider|candidater/i;

function ensureTestCv() {
  if (fs.existsSync(CV_PATH)) return;
  const pdf = "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 72 760 Td (Camille Test - CV) Tj ET\nendstream endobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n";
  fs.writeFileSync(CV_PATH, pdf);
}

/** Noms des champs d'un corps de requête, quel que soit son format. */
function bodyShape(contentType, body) {
  if (!body) return { format: "vide", fields: [] };
  const ct = (contentType || "").toLowerCase();
  try {
    if (ct.includes("json")) {
      const keys = [];
      const walk = (o, prefix) => {
        if (o && typeof o === "object" && !Array.isArray(o)) {
          for (const [k, v] of Object.entries(o)) {
            const key = prefix ? `${prefix}.${k}` : k;
            if (v && typeof v === "object" && !Array.isArray(v) && keys.length < 80) walk(v, key);
            else keys.push(key);
          }
        }
      };
      walk(JSON.parse(body), "");
      return { format: "json", fields: keys };
    }
    if (ct.includes("multipart")) {
      const names = [...body.matchAll(/name="([^"]+)"(?:; filename="([^"]*)")?/g)]
        .map((m) => (m[2] !== undefined ? `${m[1]} (fichier)` : m[1]));
      return { format: "multipart", fields: [...new Set(names)] };
    }
    if (ct.includes("x-www-form-urlencoded")) {
      return { format: "urlencoded", fields: [...new URLSearchParams(body).keys()] };
    }
  } catch { /* corps illisible */ }
  return { format: ct.split(";")[0] || "inconnu", fields: [], preview: body.slice(0, 200) };
}

/** Lit les champs de toutes les frames (le formulaire peut vivre dans un iframe). */
async function readFields(page) {
  const all = [];
  for (const frame of page.frames()) {
    try {
      const fields = await frame.evaluate(() => {
        const clean = (s) => (s || "").replace(/\s+/g, " ").trim().slice(0, 120);
        const labelOf = (el) => {
          if (el.id) {
            const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (l) return clean(l.innerText);
          }
          const w = el.closest("label");
          if (w) return clean(w.innerText);
          if (el.getAttribute("aria-label")) return clean(el.getAttribute("aria-label"));
          const by = el.getAttribute("aria-labelledby");
          if (by) return clean(by.split(/\s+/).map((i) => document.getElementById(i)?.innerText || "").join(" "));
          return clean(el.placeholder || "");
        };
        return [...document.querySelectorAll("input, textarea, select")].map((el) => ({
          tag: el.tagName.toLowerCase(),
          type: (el.type || "").toLowerCase(),
          name: el.name || null,
          id: el.id || null,
          label: labelOf(el),
          required: el.required || el.getAttribute("aria-required") === "true",
          pattern: el.pattern || null,
          min: el.min || null, max: el.max || null, maxlength: el.maxLength > 0 ? el.maxLength : null,
          accept: el.accept || null,
          options: el.tagName === "SELECT" ? el.options.length : null,
          combobox: el.getAttribute("role") === "combobox",
          in_form: !!el.closest("form"),
          hidden_value: el.type === "hidden" ? String(el.value || "").slice(0, 24) : undefined,
        }));
      });
      for (const f of fields) all.push({ frame: frame === page.mainFrame() ? "principal" : new URL(frame.url()).hostname, ...f });
    } catch { /* frame inaccessible */ }
  }
  return all;
}

async function forms(page) {
  const out = [];
  for (const frame of page.frames()) {
    try {
      out.push(...await frame.evaluate(() => [...document.forms].map((f) => ({
        action: f.getAttribute("action"), method: (f.method || "get").toUpperCase(),
        enctype: f.enctype, fields: f.elements.length,
      }))));
    } catch { /* frame inaccessible */ }
  }
  return out;
}

/** Remplit avec le candidat fictif ; rien ne part (le réseau est coupé pour les envois). */
async function fillFake(page) {
  let filled = 0;
  for (const frame of page.frames()) {
    try {
      filled += await frame.evaluate((F) => {
        let n = 0;
        const set = (el, v) => {
          const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          n++;
        };
        for (const el of document.querySelectorAll("input, textarea, select")) {
          if (el.disabled || el.readOnly || el.value) continue;
          const hint = `${el.name} ${el.id} ${el.placeholder} ${el.getAttribute("aria-label") || ""} ${el.getAttribute("autocomplete") || ""}`.toLowerCase();
          const t = (el.type || "").toLowerCase();
          if (["hidden", "submit", "button", "file", "password", "search"].includes(t)) continue;
          if (el.tagName === "SELECT") {
            if (el.required && el.options.length > 1) { el.selectedIndex = 1; el.dispatchEvent(new Event("change", { bubbles: true })); n++; }
            continue;
          }
          if (t === "checkbox" || t === "radio") {
            if (el.required && !el.checked) { el.click(); n++; }
            continue;
          }
          if (t === "email" || /mail/.test(hint)) set(el, F.email);
          else if (t === "tel" || /phone|t[ée]l/.test(hint)) set(el, F.phone);
          else if (/first|pr[ée]nom|given/.test(hint)) set(el, F.first);
          else if (/last|family|surname|\bnom\b/.test(hint)) set(el, F.last);
          else if (/name|nom/.test(hint)) set(el, F.full);
          else if (/linkedin|url|site|website|portfolio/.test(hint) || t === "url") set(el, F.url);
          else if (/city|ville|location/.test(hint)) set(el, F.city);
          else if (t === "number") set(el, F.number);
          else if (t === "date") set(el, F.date);
          else if (el.required) set(el, F.text);
        }
        return n;
      }, FAKE);
      for (const input of await frame.$$('input[type="file"]')) {
        await input.setInputFiles(CV_PATH).catch(() => {});
      }
    } catch { /* frame inaccessible */ }
  }
  return filled;
}

async function clickByText(page, re, { submit = false } = {}) {
  for (const frame of page.frames()) {
    const handles = await frame.$$(submit
      ? 'button[type="submit"], input[type="submit"], button, [role="button"]'
      : 'a, button, [role="button"]');
    for (const h of handles) {
      const label = (await h.evaluate((e) => (e.innerText || e.value || e.getAttribute("aria-label") || "").trim())).slice(0, 60);
      const isSubmit = await h.evaluate((e) => e.type === "submit");
      if ((submit && (isSubmit || re.test(label))) || (!submit && re.test(label))) {
        if (!(await h.isVisible().catch(() => false))) continue;
        await h.scrollIntoViewIfNeeded().catch(() => {});
        await h.click({ timeout: 5000 }).catch(() => {});
        return label || "(bouton d'envoi)";
      }
    }
  }
  return null;
}

async function probe(browser, url) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "fr-FR" });
  const page = await context.newPage();
  const writes = [];
  const scriptHosts = new Set();
  await page.route("**/*", async (route) => {
    const req = route.request();
    if (req.resourceType() === "script") {
      try { scriptHosts.add(new URL(req.url()).hostname + new URL(req.url()).pathname.slice(0, 40)); } catch { /* url */ }
    }
    const m = req.method();
    if (!["GET", "HEAD", "OPTIONS"].includes(m)) {
      const headers = req.headers();
      const body = req.postData() || "";
      writes.push({
        method: m,
        url: req.url().slice(0, 200),
        content_type: headers["content-type"] || null,
        notable_headers: Object.fromEntries(Object.entries(headers).filter(([k]) =>
          /next-action|csrf|xsrf|x-requested-with|authorization|x-.*token/i.test(k)).map(([k, v]) => [k, v.slice(0, 40)])),
        body: bodyShape(headers["content-type"], body),
        // Dans le corps ou dans le NOM d'un en-tête — jamais dans l'adresse
        // de la page (Referer), qui peut contenir n'importe quoi.
        captcha_token: CAPTCHA_FIELD.test(body) || Object.keys(headers).some((k) => CAPTCHA_FIELD.test(k)),
      });
      return route.abort();
    }
    return route.continue();
  });

  const result = { url, verdict: null, reasons: [] };
  try {
    // HTML brut (sans JavaScript) : les champs y sont-ils déjà ?
    const raw = await context.request.get(url, { timeout: 30000 }).then((r) => r.text()).catch(() => "");
    result.next_js = /__NEXT_DATA__|self\.__next_f/.test(raw);
    // Le HTML hors scripts : un champ écrit dans du code JavaScript n'est pas
    // « lisible sans JavaScript ».
    const rawMarkup = raw.replace(/<script\b[\s\S]*?<\/script>/gi, "");

    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});

    let fields = (await readFields(page)).filter((f) => !["submit", "button", "image", "reset"].includes(f.type));
    const visibleInputs = fields.filter((f) => f.type !== "hidden");
    if (visibleInputs.length < 2) {
      const clicked = await clickByText(page, APPLY_TEXT);
      if (clicked) {
        result.opened_with = clicked;
        await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
        await page.waitForTimeout(1500);
        fields = (await readFields(page)).filter((f) => !["submit", "button", "image", "reset"].includes(f.type));
      }
    }
    result.final_url = page.url();
    result.forms = await forms(page);
    result.fields = fields;
    const named = fields.filter((f) => f.name && f.type !== "hidden").map((f) => f.name);
    result.fields_in_raw_html = named.length ? named.filter((n) => rawMarkup.includes(`name="${n}"`)).length / named.length : 0;

    const bodyText = await page.evaluate(() => document.body?.innerText?.slice(0, 20000) || "").catch(() => "");
    const captchaDom = await page.evaluate(() =>
      !!document.querySelector(".g-recaptcha, .h-captcha, .cf-turnstile, iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='turnstile']")).catch(() => false);
    result.captcha = captchaDom || [...scriptHosts].some((h) => CAPTCHA_SCRIPT.test(h)) ||
      page.frames().some((f) => CAPTCHA_SCRIPT.test(f.url()));
    result.login = fields.some((f) => f.type === "password") || (visibleInputs.length < 2 && LOGIN_TEXT.test(bodyText));

    // Envoi à blanc : on remplit, on clique, la requête est coupée et notée.
    ensureTestCv();
    result.filled_fake = await fillFake(page);
    await page.waitForTimeout(1500);
    const before = writes.length;
    result.submit_clicked = await clickByText(page, SUBMIT_TEXT, { submit: true });
    await page.waitForTimeout(4000);
    result.upload_requests = writes.slice(0, before);  // ex. dépôt du CV avant l'envoi
    result.submit_requests = writes.slice(before);
    result.validation_messages = await page.evaluate(() =>
      [...document.querySelectorAll("[aria-invalid='true'], .error, .field-error, [role='alert']")]
        .map((e) => (e.innerText || "").trim()).filter(Boolean).slice(0, 8)).catch(() => []);
  } catch (e) {
    result.error = String(e.message || e).split("\n")[0];
  }

  // ── Verdict ──
  const sub = result.submit_requests || [];
  const tokenInRequest = sub.some((r) => r.captcha_token);
  if (result.error) {
    result.verdict = "erreur";
  } else if (result.login) {
    result.verdict = "extension";
    result.reasons.push("connexion ou création de compte demandée");
  } else if (result.captcha || tokenInRequest) {
    result.verdict = "extension";
    result.reasons.push(tokenInRequest ? "jeton de captcha dans la requête d'envoi" : "captcha présent sur la page");
  } else if (sub.length) {
    result.verdict = "rejouable";
    const r = sub[sub.length - 1];
    result.reasons.push(`${r.method} ${r.body.format} vers ${new URL(r.url).hostname}`);
    if (Object.keys(r.notable_headers).length) result.reasons.push(`en-têtes à reproduire : ${Object.keys(r.notable_headers).join(", ")}`);
    if ((result.upload_requests || []).length) result.reasons.push("CV déposé à part avant l'envoi (deux temps)");
    if ((result.fields || []).some((f) => f.type === "hidden" && /csrf|token|authenticity/i.test(`${f.name}`))) {
      result.reasons.push("jeton anti-falsification à relire sur la page");
    }
  } else if ((result.fields || []).filter((f) => f.type !== "hidden").length >= 2) {
    result.verdict = "navigateur";
    result.reasons.push(result.validation_messages?.length
      ? "envoi non déclenché : champs à compléter"
      : "aucune requête d'envoi observée");
  } else {
    result.verdict = "introuvable";
    result.reasons.push("pas de formulaire de candidature sur cette page");
  }

  await page.screenshot({ path: path.join(HERE, `probe-${new URL(url).hostname}.png`), fullPage: true }).catch(() => {});
  await context.close();
  return result;
}

async function main() {
  let urls = process.argv.slice(2).filter((a) => /^https?:\/\//.test(a));
  const fileArg = process.argv.indexOf("--file");
  if (fileArg > -1) {
    urls = urls.concat(fs.readFileSync(process.argv[fileArg + 1], "utf8").split(/\s+/).filter((l) => /^https?:\/\//.test(l)));
  }
  if (!urls.length) {
    console.error("Usage : node probe.mjs <url> [<url> …]   ou   node probe.mjs --file liens.txt");
    process.exit(1);
  }
  const browser = await chromium.launch({ headless: process.env.HEADLESS !== "0" });
  const results = [];
  for (const url of urls) {
    process.stdout.write(`▶ ${url}\n`);
    const r = await probe(browser, url);
    results.push(r);
    const visible = (r.fields || []).filter((f) => f.type !== "hidden").length;
    console.log(`  → ${r.verdict.toUpperCase()} — ${r.reasons.join(" ; ") || r.error || ""}`);
    console.log(`    ${visible} champs (${Math.round((r.fields_in_raw_html || 0) * 100)} % dans le HTML brut)` +
      `${r.next_js ? ", Next.js" : ""}${r.captcha ? ", captcha" : ""}${r.login ? ", connexion" : ""}` +
      `, requêtes d'envoi interceptées : ${(r.submit_requests || []).length}`);
  }
  await browser.close();

  const counts = results.reduce((acc, r) => ({ ...acc, [r.verdict]: (acc[r.verdict] || 0) + 1 }), {});
  console.log("\nBilan :", Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(" · "));
  const out = path.join(HERE, `probe-${new Date().toISOString().replace(/[:.]/g, "-")}.json`);
  fs.writeFileSync(out, JSON.stringify({ results }, null, 2));
  console.log(`Rapport : ${out}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
