/**
 * Lire et remplir un formulaire de candidature.
 *
 * Sans dépendance au reste de l'extension : `AliceFields.scan()` décrit les
 * champs (libellé, type, options, ce qu'on y reconnaît), `AliceFields.fill()`
 * les remplit comme le ferait une saisie au clavier — les sites en React ou
 * Vue ne voient sinon pas la valeur. Rien n'est jamais soumis.
 */
(() => {
  if (window.AliceFields) return;

  const clean = (s) => (s || "").replace(/\s+/g, " ").replace(/[*:]+\s*$/, "").trim();

  function visible(el) {
    if (el.type === "file") return true; // souvent masqué derrière un bouton stylé
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && st.display !== "none";
  }

  function textOf(id) {
    const el = id && document.getElementById(id);
    return el ? clean(el.innerText || el.textContent) : "";
  }

  /** Le libellé que voit le candidat, par ordre de fiabilité. */
  function labelOf(el) {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && clean(l.innerText)) return clean(l.innerText);
    }
    const wrap = el.closest("label");
    if (wrap && clean(wrap.innerText)) return clean(wrap.innerText);
    const by = el.getAttribute("aria-labelledby");
    if (by) {
      const t = by.split(/\s+/).map(textOf).join(" ").trim();
      if (t) return t;
    }
    if (el.getAttribute("aria-label")) return clean(el.getAttribute("aria-label"));
    // Texte qui précède le champ dans son bloc (mises en page sans <label>).
    let node = el;
    for (let depth = 0; depth < 4 && node && node.parentElement; depth++) {
      node = node.parentElement;
      const lab = node.querySelector("label, legend, .label, [class*='label'], [class*='Label']");
      if (lab && !lab.contains(el) && clean(lab.innerText)) return clean(lab.innerText);
    }
    return clean(el.getAttribute("placeholder") || el.getAttribute("title") || el.name || "");
  }

  /** Pour un groupe radio / case à cocher : la question, pas l'option. */
  function groupLabelOf(el) {
    const fs = el.closest("fieldset");
    if (fs) {
      const lg = fs.querySelector("legend");
      if (lg && clean(lg.innerText)) return clean(lg.innerText);
    }
    const group = el.closest("[role='radiogroup'], [role='group']");
    if (group) {
      const by = group.getAttribute("aria-labelledby");
      if (by) return by.split(/\s+/).map(textOf).join(" ").trim();
      if (group.getAttribute("aria-label")) return clean(group.getAttribute("aria-label"));
    }
    let node = el.parentElement;
    for (let depth = 0; depth < 5 && node; depth++, node = node.parentElement) {
      const inputs = node.querySelectorAll(`input[name="${CSS.escape(el.name)}"]`);
      if (inputs.length > 1) {
        const lab = [...node.querySelectorAll("label, legend, p, span, div")]
          .find((n) => ![...inputs].some((i) => n.contains(i) || i.closest("label") === n) && clean(n.innerText));
        if (lab) return clean(lab.innerText);
      }
    }
    return clean(el.name);
  }

  function optionLabel(input) {
    if (input.id) {
      const l = document.querySelector(`label[for="${CSS.escape(input.id)}"]`);
      if (l) return clean(l.innerText);
    }
    const wrap = input.closest("label");
    return wrap ? clean(wrap.innerText) : clean(input.value);
  }

  // Ce qu'on sait remplir sans réfléchir. L'ordre compte : « prénom » avant « nom ».
  const RULES = [
    ["email", (h, el) => el.type === "email" || /e-?mail|courriel/.test(h)],
    ["phone", (h, el) => el.type === "tel" || /t[ée]l[ée]phone|phone|mobile|portable|\btel\b/.test(h)],
    ["first_name", (h) => /pr[ée]nom|first.?name|given.?name|fname/.test(h)],
    ["last_name", (h) => /last.?name|family.?name|surname|lname|nom de famille|^nom\b|\bnom$/.test(h)],
    ["full_name", (h) => /full.?name|nom complet|^name$|^your name|^nom et pr[ée]nom|pr[ée]nom et nom|^name\b/.test(h)],
    ["linkedin_url", (h) => /linkedin/.test(h)],
    ["github_url", (h) => /github/.test(h)],
    ["website_url", (h) => /portfolio|site (web|perso|internet)|website|personal (site|url)/.test(h)],
    ["city", (h) => /\bville\b|\bcity\b|localisation|location|o[uù] habitez/.test(h)],
    ["headline", (h) => /titre (du poste|actuel)|current (title|position)|poste actuel|headline/.test(h)],
  ];

  // Jamais à notre place : le candidat coche ces cases lui-même.
  const SENSITIVE = /rgpd|gdpr|consent|j'accepte|i agree|accept|conditions|privacy|confidentialit|handicap|disabilit|gender|genre|sexe|ethni|origine|race|religion|veteran|casier|criminal|newsletter/;

  function classify(el, label) {
    const hint = [label, el.name, el.id, el.getAttribute("autocomplete"), el.getAttribute("placeholder")]
      .filter(Boolean).join(" ").toLowerCase();
    if (el.type === "file") {
      if (/lettre|cover|motivation/.test(hint) && !/cv|resume|résumé/.test(hint)) return "letter_file";
      return "cv_file";
    }
    if (SENSITIVE.test(hint)) return "sensitive";
    if (el.tagName === "TEXTAREA" && /lettre|cover|motivation|message|pr[ée]sentez|introduce|additional information|informations compl/.test(hint)) {
      return "letter";
    }
    const ac = (el.getAttribute("autocomplete") || "").toLowerCase();
    if (ac === "given-name") return "first_name";
    if (ac === "family-name") return "last_name";
    if (ac === "name") return "full_name";
    if (ac === "email") return "email";
    if (ac === "tel") return "phone";
    for (const [key, test] of RULES) if (test(hint, el)) return key;
    return null;
  }

  /**
   * Les champs du document, un par question : un groupe de radios compte pour
   * un seul champ. `known` dit ce qu'on y reconnaît ; null = question à poser.
   */
  function scan(root = document) {
    const out = [];
    const seenGroups = new Set();
    const els = root.querySelectorAll("input, textarea, select");
    let n = 0;
    for (const el of els) {
      const type = (el.type || "").toLowerCase();
      if (["hidden", "submit", "button", "reset", "image", "password", "search"].includes(type)) continue;
      if (el.disabled || el.readOnly || !visible(el)) continue;
      if (el.closest("[data-alice-ui]")) continue;

      if (type === "radio" || type === "checkbox") {
        const key = `${type}:${el.name || el.id}`;
        if (el.name && seenGroups.has(key)) continue;
        seenGroups.add(key);
        const group = el.name
          ? [...root.querySelectorAll(`input[type="${type}"][name="${CSS.escape(el.name)}"]`)]
          : [el];
        const label = group.length > 1 ? groupLabelOf(el) : labelOf(el);
        const known = classify(el, label) === "sensitive" || SENSITIVE.test(label.toLowerCase())
          ? "sensitive" : null;
        out.push({
          id: `f${n++}`, el, group, kind: type, label,
          options: group.map(optionLabel), known,
        });
        continue;
      }

      const label = labelOf(el);
      const kind = el.tagName === "SELECT" ? "select" : el.tagName === "TEXTAREA" ? "textarea"
        : type === "file" ? "file" : ["number", "date", "email", "tel", "url"].includes(type) ? type : "text";
      const options = el.tagName === "SELECT"
        ? [...el.options].filter((o) => o.value !== "" && !/^(-+|choisi|select|s[ée]lection)/i.test(o.text.trim())).map((o) => clean(o.text))
        : [];
      out.push({ id: `f${n++}`, el, group: [el], kind, label, options, known: classify(el, label) });
    }
    return out;
  }

  // ── Saisie ──────────────────────────────────────────────────────────────

  function setNative(el, value) {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype
      : el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, value);
  }

  function fire(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function mark(el, state) {
    const target = el.type === "file" ? (el.closest("label, div") || el) : el;
    target.style.outline = state === "done" ? "2px solid #006045" : "2px dashed #D9822B";
    target.style.outlineOffset = "2px";
    target.dataset.aliceFilled = state;
  }

  function fillText(f, value) {
    const el = f.el;
    if (el.value && el.value.trim()) return false; // ne jamais écraser une saisie
    el.focus({ preventScroll: true });
    setNative(el, value);
    fire(el);
    return true;
  }

  function fillSelect(f, value) {
    const el = f.el;
    const v = value.trim().toLowerCase();
    const opt = [...el.options].find((o) => clean(o.text).toLowerCase() === v)
      || [...el.options].find((o) => clean(o.text).toLowerCase().includes(v) && v.length > 2);
    if (!opt) return false;
    setNative(el, opt.value);
    fire(el);
    return true;
  }

  function fillChoice(f, value) {
    const v = value.trim().toLowerCase();
    const idx = f.options.findIndex((o) => o.toLowerCase() === v);
    if (idx < 0) return false;
    const input = f.group[idx];
    if (!input.checked) input.click();
    return true;
  }

  function fillFile(f, file) {
    const el = f.el;
    if (el.files && el.files.length) return false;
    const bytes = Uint8Array.from(atob(file.data), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bytes], file.name, { type: file.type }));
    el.files = dt.files;
    fire(el);
    return true;
  }

  /** Une valeur dans un champ, quelle que soit sa nature. Vrai si posée. */
  function put(f, value) {
    if (value == null || value === "") return false;
    if (f.kind === "file") return fillFile(f, value);
    if (f.kind === "select") return fillSelect(f, String(value));
    if (f.kind === "radio" || f.kind === "checkbox") return fillChoice(f, String(value));
    return fillText(f, String(value));
  }

  window.AliceFields = { scan, put, mark, classify, labelOf };
})();
