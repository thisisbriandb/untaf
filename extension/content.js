/**
 * Sur les pages d'offres et les formulaires de candidature.
 *
 * Une pastille discrète (les deux yeux d'Alice) apparaît seulement sur une
 * page qui ressemble à une offre ou à un formulaire de candidature : ailleurs,
 * l'extension ne fait rien et n'envoie rien. Elle propose d'ajouter l'offre à
 * Alice, ou de remplir le formulaire. Le bouton « Envoyer » reste au candidat.
 */
(() => {
  if (window.__aliceContent) return;
  window.__aliceContent = true;

  const TOP = window === window.top;
  const F = window.AliceFields;

  const call = (type, extra = {}) =>
    new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type, ...extra }, (r) => {
          if (chrome.runtime.lastError) resolve({ ok: false, error: "Extension rechargée : actualise la page." });
          else resolve(r || { ok: false, error: "Pas de réponse." });
        });
      } catch {
        resolve({ ok: false, error: "Extension rechargée : actualise la page." });
      }
    });

  // ── Reconnaître une offre ────────────────────────────────────────────────

  const JOB_HOSTS = [
    /greenhouse\.io/, /lever\.co/, /workable\.com/, /recruitee\.com/, /smartrecruiters\.com/,
    /teamtailor\.com/, /ashbyhq\.com/, /personio\.(de|com|fr)/, /myworkdayjobs\.com/, /taleo\.net/,
    /breezy\.hr/, /join\.com/, /jobteaser\.com/, /bamboohr\.com/, /flatchr\.io/, /digitalrecruiters\.com/,
    /welcometothejungle\.com\/.+\/jobs\//, /francetravail\.fr\/.*offres/, /indeed\.[a-z.]+\/(viewjob|rc\/clk|.*jk=)/,
    /linkedin\.com\/jobs\/(view|collections|search)/, /hellowork\.com\/.+\/emplois\//, /apec\.fr\/.*offre/,
    /labonnealternance/, /^https?:\/\/(jobs|careers|carrieres?|recrutement)\./,
  ];

  function jsonLdJob() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const data = JSON.parse(s.textContent);
        const items = [].concat(data, data["@graph"] || []);
        const job = items.find((d) => d && [].concat(d["@type"]).includes("JobPosting"));
        if (job) return job;
      } catch { /* JSON invalide : on ignore */ }
    }
    return null;
  }

  function hasApplyForm() {
    return [...document.querySelectorAll('input[type="file"]')].some((el) =>
      /cv|resume|résumé|curriculum|candidat|upload/i.test(F.labelOf(el) + " " + el.name + " " + el.id + " " + (el.accept || ""))
    );
  }

  function jobLike() {
    return !!jsonLdJob() || JOB_HOSTS.some((re) => re.test(location.href)) || hasApplyForm();
  }

  function htmlToText(html) {
    const d = document.createElement("div");
    d.innerHTML = html || "";
    return (d.innerText || d.textContent || "").trim();
  }

  /** Le texte de l'annonce, au plus propre possible. */
  function pageText() {
    const job = jsonLdJob();
    if (job) {
      const org = job.hiringOrganization && (job.hiringOrganization.name || job.hiringOrganization);
      const place = [].concat(job.jobLocation || []).map((l) => l.address && (l.address.addressLocality || l.address.addressRegion)).filter(Boolean).join(", ");
      const text = [job.title, typeof org === "string" ? org : "", place, job.employmentType, htmlToText(job.description)]
        .filter(Boolean).join("\n");
      if (text.length > 200) return text;
    }
    const main = document.querySelector("main, article, [role='main']") || document.body;
    return `${document.title}\n${(main.innerText || "").trim()}`.slice(0, 30000);
  }

  const page = () => ({ url: location.href, text: pageText(), jobLike: jobLike() });

  // ── Remplir le formulaire de ce cadre ────────────────────────────────────

  function profileValue(key, ctx) {
    const p = ctx.profile || {};
    if (key === "letter") return ctx.letter ? ctx.letter.body : null;
    // L'adresse de réponse d'Alice : les réponses du recruteur lui arrivent,
    // elle les lit, met à jour le suivi et les transfère.
    if (key === "email") return p.contact_email || p.email || null;
    return p[key] || null;
  }

  async function fillHere(ctx) {
    const fields = F.scan();
    const usable = fields.filter((f) => f.known !== "sensitive");
    if (usable.length < 2 && !fields.some((f) => f.kind === "file")) return null; // pas un formulaire

    let filled = 0;
    let left = 0;
    let cv = false;
    let cvError = null;
    const questions = [];

    for (const f of fields) {
      if (f.known === "sensitive") {
        F.mark(f.el, "left");
        left++;
        continue;
      }
      if (f.known === "cv_file") {
        const r = await call("cv", { jobId: ctx.job.job_id });
        if (r.ok && F.put(f, r.data)) {
          F.mark(f.el, "done");
          filled++;
          cv = true;
        } else {
          cvError = r.ok ? null : r.error;
          F.mark(f.el, "left");
          left++;
        }
        continue;
      }
      if (f.known === "letter_file") {
        F.mark(f.el, "left");
        left++;
        continue;
      }
      if (f.known) {
        if (F.put(f, profileValue(f.known, ctx))) {
          F.mark(f.el, "done");
          filled++;
        } else if (!(f.el.value && f.el.value.trim())) {
          F.mark(f.el, "left");
          left++;
        }
        continue;
      }
      const empty = f.kind === "radio" || f.kind === "checkbox"
        ? !f.group.some((i) => i.checked)
        : !(f.el.value && f.el.value.trim());
      if (empty && f.label) questions.push(f);
    }

    if (questions.length) {
      const r = await call("answers", {
        jobId: ctx.job.job_id,
        questions: questions.map((f) => ({ id: f.id, label: f.label.slice(0, 1000), kind: f.kind, options: f.options.slice(0, 60) })),
      });
      const byId = r.ok ? Object.fromEntries(r.data.answers.map((a) => [a.id, a.value])) : {};
      for (const f of questions) {
        if (F.put(f, byId[f.id])) {
          F.mark(f.el, "done");
          filled++;
        } else {
          F.mark(f.el, "left");
          left++;
        }
      }
    }

    if (filled) watchSubmit(ctx.job);
    return { filled, left, cv, cvError };
  }

  /** Quand le candidat envoie, on le note pour lui proposer de l'ajouter au suivi. */
  function watchSubmit(job) {
    // Le formulaire peut vivre dans un iframe : c'est la page principale qu'on retient.
    const anc = location.ancestorOrigins;
    const top = anc && anc.length ? new URL(anc[anc.length - 1]).hostname : location.hostname;
    const remember = () =>
      chrome.storage.local.set({ pending: { job, host: top, at: Date.now() } });
    document.addEventListener("submit", remember, true);
    document.addEventListener("click", (e) => {
      const b = e.target.closest && e.target.closest("button, input[type=submit], [role=button]");
      if (b && /envoyer|postuler|candidater|submit|apply|send/i.test(b.innerText || b.value || "")) remember();
    }, true);
  }

  chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
    if (msg.type === "page") {
      if (!TOP) return false;
      reply(page());
      return false;
    }
    if (msg.type === "fill") {
      fillHere(msg.ctx).then(reply, () => reply(null));
      return true;
    }
    return false;
  });

  if (!TOP) {
    // Formulaire dans un iframe : la page principale doit afficher la pastille.
    if (hasApplyForm()) call("formInFrame");
    return;
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type !== "formInFrame") return;
    formSeen = true;
    if (!ui) init(true);
    else if (connected !== null && !asking) render(connected);
  });

  // ── La pastille (cadre principal seulement) ──────────────────────────────

  let ui = null;

  function mountUi() {
    if (ui) return ui;
    const host = document.createElement("div");
    host.setAttribute("data-alice-ui", "");
    host.style.cssText = "position:fixed;right:20px;bottom:20px;z-index:2147483647;";
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
        .pill { display:flex; align-items:center; gap:8px; padding:8px 14px 8px 10px; border-radius:999px;
          background:#FAFAF8; color:#161615; border:1px solid rgba(26,25,24,.12); cursor:pointer;
          box-shadow:0 6px 24px rgba(0,0,0,.12); font-size:13px; }
        .pill:hover { border-color: rgba(0,96,69,.4); }
        .eyes { display:inline-flex; gap:4px; align-items:center; justify-content:center; width:26px; height:26px;
          border-radius:999px; background:#ECF4F0; box-shadow: inset 0 0 0 1px rgba(0,96,69,.15); }
        .eye { width:7px; height:7px; border-radius:999px; border:1.5px solid #006045; box-shadow:0 0 6px rgba(0,96,69,.35); }
        .busy .eye { animation: blink 1.2s ease-in-out infinite; }
        @keyframes blink { 50% { transform: scale(1.25); opacity:.6; } }
        .panel { position:absolute; right:0; bottom:52px; width:300px; padding:14px; border-radius:18px;
          background:#FAFAF8; color:#161615; border:1px solid rgba(26,25,24,.12); box-shadow:0 12px 40px rgba(0,0,0,.16);
          font-size:13px; line-height:1.45; display:none; }
        .panel.open { display:block; }
        .title { font-size:12px; color:rgba(26,25,24,.6); margin:0 0 4px; }
        .job { margin:0 0 10px; font-size:14px; }
        .msg { margin:10px 0 0; font-size:12px; color:rgba(26,25,24,.75); white-space:pre-line; }
        .msg.warn { color:#9A4B00; }
        button.action { width:100%; margin-top:8px; padding:9px 12px; border-radius:999px; border:0; cursor:pointer;
          font-size:12.5px; background:#006045; color:#fff; }
        button.action:hover { background:#004d37; }
        button.ghost { background:transparent; color:#161615; border:1px solid rgba(26,25,24,.15); }
        button.ghost:hover { background:rgba(26,25,24,.04); }
        button:disabled { opacity:.55; cursor:default; }
        .close { position:absolute; top:8px; right:10px; background:none; border:0; cursor:pointer; color:rgba(26,25,24,.5); font-size:16px; }
        .legend { display:flex; gap:10px; margin-top:8px; font-size:11px; color:rgba(26,25,24,.6); }
        .legend i { display:inline-block; width:10px; height:10px; margin-right:4px; vertical-align:-1px; border-radius:3px; }
      </style>
      <div class="panel" part="panel">
        <button class="close" aria-label="Fermer">×</button>
        <p class="title">Alice</p>
        <p class="job"></p>
        <div class="actions"></div>
        <p class="msg"></p>
      </div>
      <div class="pill" role="button" tabindex="0"><span class="eyes"><span class="eye"></span><span class="eye"></span></span><span class="label">Alice</span></div>
    `;
    document.documentElement.appendChild(host);
    const $ = (s) => root.querySelector(s);
    ui = {
      root, host,
      panel: $(".panel"), job: $(".job"), actions: $(".actions"), msg: $(".msg"),
      pill: $(".pill"), label: $(".label"), eyes: $(".eyes"),
    };
    ui.pill.addEventListener("click", () => ui.panel.classList.toggle("open"));
    $(".close").addEventListener("click", () => ui.panel.classList.remove("open"));
    return ui;
  }

  function say(text, warn = false) {
    ui.msg.textContent = text || "";
    ui.msg.classList.toggle("warn", !!warn);
  }

  function busy(on, label) {
    ui.eyes.classList.toggle("busy", on);
    ui.label.textContent = on ? (label || "Alice travaille…") : "Alice";
    ui.actions.querySelectorAll("button").forEach((b) => (b.disabled = on));
  }

  function button(text, onClick, ghost = false) {
    const b = document.createElement("button");
    b.className = `action${ghost ? " ghost" : ""}`;
    b.textContent = text;
    b.addEventListener("click", onClick);
    ui.actions.appendChild(b);
    return b;
  }

  let current = null; // offre de la page dans la liste d'Alice
  let formSeen = false; // un cadre de la page contient un formulaire de candidature
  let filledOnce = false;
  let connected = null; // inconnu tant que le service worker n'a pas répondu

  function render(connected) {
    ui.actions.innerHTML = "";
    if (!connected) {
      ui.job.textContent = "Connecte-toi sur le site d'Alice.";
      say("L'extension reprend ta session : rien d'autre à configurer.");
      button("Ouvrir Alice", () => call("status").then((r) => window.open(r.ok ? r.data.app : "https://alice-agent.fr", "_blank")));
      return;
    }
    ui.job.textContent = current
      ? `${current.title}${current.company_name ? ` · ${current.company_name}` : ""}`
      : "Cette offre n'est pas encore dans ta liste.";
    if (!current) button("Ajouter à Alice", addPage);
    if (formSeen || hasApplyForm() || current) {
      button(filledOnce ? "Remplir à nouveau" : "Remplir avec Alice", fill, filledOnce || (!current && !hasApplyForm() && !formSeen));
    }
    if (current && current.status === "applied") say("Candidature déjà notée comme envoyée.");
  }

  async function addPage() {
    busy(true, "J'ajoute l'offre…");
    const r = await call("import", { page: page() });
    busy(false);
    if (!r.ok) return say(r.error, true);
    const c = r.data;
    current = { job_id: c.id, title: c.title, company_name: c.company_name, pack_ready: false, status: c.status };
    render(true);
    const reasons = (c.rejections || []).length ? `\nHors de tes critères : ${c.rejections.join(", ")}.` : "";
    say(`Ajoutée à ta liste (correspondance ${c.match_score} %).${reasons}`);
  }

  async function fill() {
    busy(true, current && current.pack_ready ? "Je remplis…" : "J'adapte ton CV…");
    say(current && current.pack_ready ? "" : "J'adapte ton CV et ta lettre à cette offre, puis je remplis. Ça peut prendre une minute.");
    const r = await call("fill", { page: page() });
    busy(false);
    if (!r.ok) return say(r.error, true);
    const d = r.data;
    filledOnce = d.filled > 0;
    current = { ...(current || {}), ...d.job, pack_ready: true };
    render(true);
    if (!d.filled && !d.left) {
      return say("Je ne trouve pas de formulaire ici. Ouvre la page « Postuler » de l'offre, puis relance-moi.", true);
    }
    const lines = [
      `J'ai rempli ${d.filled} champ${d.filled > 1 ? "s" : ""}${d.cv ? ", CV adapté joint" : ""}.`,
      d.left ? `${d.left} à compléter toi-même (en orange) : questions personnelles ou sans réponse dans ton parcours.` : "",
      d.cvError ? `CV non joint : ${d.cvError}` : "",
      "Relis, puis clique « Envoyer » sur le site.",
    ].filter(Boolean);
    say(lines.join("\n"), !!d.cvError);
    const legend = document.createElement("div");
    legend.className = "legend";
    legend.innerHTML = '<span><i style="background:#006045"></i>rempli</span><span><i style="background:#D9822B"></i>à compléter</span>';
    ui.actions.appendChild(legend);
    button("C'est envoyé — ajoute au suivi", () => confirmApplied(current), true);
  }

  async function confirmApplied(job) {
    if (!job || !job.job_id) return;
    busy(true, "Je note…");
    const r = await call("markApplied", { jobId: job.job_id });
    busy(false);
    await chrome.storage.local.remove("pending");
    if (!r.ok) return say(r.error, true);
    current = { ...job, status: "applied" };
    asking = false;
    connected = true;
    render(true);
    say(`Noté : candidature envoyée${job.company_name ? ` chez ${job.company_name}` : ""}. Je te proposerai une relance.`);
  }

  /** Après un envoi : on demande, une fois, s'il faut l'ajouter au suivi. */
  async function askPending() {
    const { pending } = await chrome.storage.local.get("pending");
    if (!pending || Date.now() - pending.at > 30 * 60 * 1000) return false;
    if (pending.host !== location.hostname) return false;
    mountUi();
    ui.panel.classList.add("open");
    ui.actions.innerHTML = "";
    ui.job.textContent = `${pending.job.title}${pending.job.company_name ? ` · ${pending.job.company_name}` : ""}`;
    say("Tu as envoyé ta candidature ?");
    button("Oui, ajoute-la au suivi", () => confirmApplied(pending.job));
    button("Pas encore", async () => {
      await chrome.storage.local.remove("pending");
      ui.panel.classList.remove("open");
      asking = false;
      starting = null;
      ui.host.remove();
      ui = null;
      init(formSeen);
    }, true);
    return true;
  }

  let starting = null;
  let asking = false; // la question « Tu as envoyé ? » a la priorité

  function init(formInFrame = false) {
    if (!starting) starting = start(formInFrame);
    return starting;
  }

  async function start(formInFrame) {
    if (await askPending()) {
      asking = true;
      return;
    }
    if (!formInFrame && !jobLike()) {
      starting = null; // un formulaire peut encore apparaître dans un cadre
      return; // rien ne sort d'une page qui n'est pas une offre
    }
    mountUi();
    const s = await call("status");
    connected = !!(s.ok && s.data.connected);
    if (connected) {
      const m = await call("match", { url: location.href });
      if (m.ok) current = m.data;
    }
    render(connected);
  }

  init();
})();
