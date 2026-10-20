// Mock of the Alice backend (job-discovery API) for screen capture.
// Shapes follow frontend/lib/*.ts clients and backend/job-discovery/app/api/*.py.
// All people and companies are fictional.
import http from "node:http";

export const API = "http://localhost:8765";
export const CAND = "demo-cand";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
  "access-control-expose-headers": "*",
};

const iso = (msAgo = 0) => new Date(Date.now() - msAgo).toISOString();
const DAY = 86400000;

// ── Demo data ──────────────────────────────────────────────────────────────
export const JOBS = [
  { id: "job-atelier-nord", title: "Alternance — Chargée de marketing digital", company_name: "Atelier Nord", location: "Lyon 2e", match_score: 92, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/atelier-nord", status: "matched", apply_mode: "auto", warning: null },
  { id: "job-maison-brume", title: "Alternance — Social media & contenus", company_name: "Maison Brume", location: "Lyon 7e", match_score: 88, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/maison-brume", status: "matched", apply_mode: "auto", warning: null },
  { id: "job-studio-ferro", title: "Alternance — Growth marketing", company_name: "Studio Ferro", location: "Villeurbanne", match_score: 85, contract_type: "alternance", remote_policy: "onsite", source_url: "https://exemple.fr/offres/studio-ferro", status: "matched", apply_mode: "assisted", warning: null },
  { id: "job-collectif-lune", title: "Alternance — Communication & événementiel", company_name: "Collectif Lune", location: "Lyon 1er", match_score: 81, contract_type: "alternance", remote_policy: "onsite", source_url: "https://exemple.fr/offres/collectif-lune", status: "matched", apply_mode: "manual", warning: null },
];
const JOB = Object.fromEntries(JOBS.map((j) => [j.id, j]));

const DESCRIPTION = `**Atelier Nord** est une maison lyonnaise de mobilier et d'objets en bois, vendue en ligne et dans deux boutiques.

### Tes missions
- Animer nos réseaux sociaux (Instagram, Pinterest, LinkedIn) et planifier le calendrier éditorial
- Préparer les newsletters et suivre leurs performances
- Participer aux campagnes d'acquisition (SEA, social ads) avec l'équipe e-commerce
- Construire les tableaux de bord mensuels (trafic, conversions, panier moyen)

### Ton profil
- Bac+3 à Bac+5 en marketing ou communication, en alternance sur 12 à 24 mois
- À l'aise avec Canva, Meta Business Suite et Google Analytics 4
- Curieuse, organisée, avec un vrai goût pour l'image et les mots

### Rythme
3 semaines en entreprise, 1 semaine à l'école. Bureaux à Lyon 2e, télétravail un jour par semaine.`;

export const CANDIDATE = {
  id: CAND, full_name: "Camille Martin", email: "camille.martin@exemple.fr",
  headline: "Alternance Marketing digital · Lyon",
  skills: ["Social media", "Canva", "Google Analytics 4", "Rédaction web", "Meta Ads"],
};

function pipelineItem(job, stage, status, extra = {}) {
  const appliedAt = ["applied", "interview", "rejected"].includes(stage) ? iso(extra.daysAgo * DAY) : null;
  return {
    application_id: `app-${job.id}`, job_id: job.id, title: job.title, company_name: job.company_name,
    location: job.location, contract_type: job.contract_type, remote_policy: job.remote_policy,
    apply_mode: job.apply_mode, match_score: job.match_score, status, stage, pack_ready: stage !== "to_prepare",
    applied_at: appliedAt, source_url: job.source_url,
    dispatch: stage === "awaiting" ? { id: `disp-${job.id}`, status: "awaiting_approval", channel: "email", destination: "recrutement@" + job.company_name.toLowerCase().replace(/\s+/g, "") + ".fr", error: null, sent_at: null, created_at: iso(3600000), mailto: null }
      : appliedAt ? { id: `disp-${job.id}`, status: "sent", channel: "email", destination: null, error: null, sent_at: appliedAt, created_at: appliedAt, mailto: null } : null,
    followup: { due: false, days_since_applied: appliedAt ? extra.daysAgo : null, status: null },
    timeline: [{ status: "to_prepare", at: iso(((extra.daysAgo ?? 0) + 2) * DAY) }, ...(appliedAt ? [{ status: "applied", at: appliedAt }] : []), ...(stage === "interview" ? [{ status: "interview", at: iso(DAY), note: "Entretien mardi 10 h" }] : [])],
    created_at: iso(((extra.daysAgo ?? 0) + 2) * DAY),
  };
}

const EXTRA = [
  { id: "job-maison-orme", title: "Alternance — Assistante chef de produit web", company_name: "Maison Orme", location: "Lyon 6e", match_score: 83, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/maison-orme", apply_mode: "auto" },
  { id: "job-atelier-sable", title: "Alternance — Content marketing", company_name: "Atelier Sable", location: "Lyon 3e", match_score: 80, contract_type: "alternance", remote_policy: "remote", source_url: "https://exemple.fr/offres/atelier-sable", apply_mode: "auto" },
  { id: "job-studio-vela", title: "Alternance — Chargée de communication digitale", company_name: "Studio Vela", location: "Écully", match_score: 77, contract_type: "alternance", remote_policy: "onsite", source_url: "https://exemple.fr/offres/studio-vela", apply_mode: "assisted" },
  { id: "job-maison-alba", title: "Alternance — Assistante marketing e-commerce", company_name: "Maison Alba", location: "Lyon 9e", match_score: 79, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/maison-alba", apply_mode: "auto" },
  { id: "job-studio-cobalt", title: "Alternance — SEO & rédaction web", company_name: "Studio Cobalt", location: "Lyon 3e", match_score: 78, contract_type: "alternance", remote_policy: "remote", source_url: "https://exemple.fr/offres/studio-cobalt", apply_mode: "auto" },
  { id: "job-atelier-pivoine", title: "Alternance — Community manager", company_name: "Atelier Pivoine", location: "Lyon 4e", match_score: 76, contract_type: "alternance", remote_policy: "onsite", source_url: "https://exemple.fr/offres/atelier-pivoine", apply_mode: "assisted" },
  { id: "job-collectif-garance", title: "Alternance — Chargée de partenariats", company_name: "Collectif Garance", location: "Villeurbanne", match_score: 74, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/collectif-garance", apply_mode: "manual" },
  { id: "job-maison-saule", title: "Alternance — Marketing automation", company_name: "Maison Saule", location: "Lyon 7e", match_score: 73, contract_type: "alternance", remote_policy: "hybrid", source_url: "https://exemple.fr/offres/maison-saule", apply_mode: "auto" },
  { id: "job-studio-ambre", title: "Alternance — Brand content", company_name: "Studio Ambre", location: "Lyon 2e", match_score: 71, contract_type: "alternance", remote_policy: "onsite", source_url: "https://exemple.fr/offres/studio-ambre", apply_mode: "auto" },
];
for (const j of EXTRA) JOB[j.id] = j;

export function pipeline(scene) {
  if (scene === "chat") return { items: [], counts: {} };
  if (scene === "canvas") {
    const items = [pipelineItem(JOB["job-atelier-nord"], "awaiting", "matched")];
    return { items, counts: { awaiting: 1 } };
  }
  const items = [
    pipelineItem(JOB["job-studio-ferro"], "interview", "interview", { daysAgo: 6 }),
    pipelineItem(JOB["job-atelier-nord"], "awaiting", "matched"),
    pipelineItem(JOB["job-maison-brume"], "awaiting", "matched"),
    pipelineItem(JOB["job-collectif-lune"], "manual", "matched"),
    pipelineItem(JOB["job-maison-orme"], "applied", "applied", { daysAgo: 2 }),
    pipelineItem(JOB["job-atelier-sable"], "applied", "applied", { daysAgo: 4 }),
    pipelineItem(JOB["job-studio-vela"], "ready", "matched"),
    pipelineItem(JOB["job-maison-alba"], "applied", "applied", { daysAgo: 5 }),
    pipelineItem(JOB["job-studio-cobalt"], "applied", "applied", { daysAgo: 7 }),
    pipelineItem(JOB["job-atelier-pivoine"], "ready", "matched"),
    pipelineItem(JOB["job-collectif-garance"], "manual", "matched"),
    pipelineItem(JOB["job-maison-saule"], "to_prepare", "matched"),
    pipelineItem(JOB["job-studio-ambre"], "rejected", "rejected", { daysAgo: 9 }),
  ];
  const counts = {};
  for (const i of items) counts[i.stage] = (counts[i.stage] ?? 0) + 1;
  return { items, counts };
}

const MISSION = (scene) => ({
  id: "mission-1", candidate_id: CAND, title: "Alternance marketing digital · Lyon", status: "active",
  autonomy: "auto_above", auto_apply_min_score: 85, weekly_quota: 10, last_run_at: scene === "chat" ? null : iso(5 * 3600000),
  criteria: { languages: ["fr"], countries: ["FR"], job_families: ["marketing"], contract_types: ["alternance"], remote_policies: [], locations: ["Lyon"], salary_min: null },
  criteria_is_explicit: true,
  stats: { shortlisted: scene === "chat" ? 0 : 7, applied: scene === "chat" ? 0 : 3, interviews: scene === "chat" ? 0 : 1, scanned_last_run: scene === "chat" ? 0 : 214, applied_this_week: 3, quota_remaining: 7 },
  recent_events: [],
});

const BILLING = {
  enabled: false, plan: "weekly", price_label: "", status: "active", renews_at: null, ends_at: null, cancelled: false,
  usage: Object.fromEntries(["send", "pack", "mission", "spontaneous", "message"].map((k) => [k, { used: 1, limit: 50, label: k, window: "week" }])),
};

// ── Mission run, advanced in time after the chat message ───────────────────
const chez = (c) => ` chez ${c}`;
const RUN_SCRIPT = [
  // [ms after chat, step, event|null, stats patch]
  [300, "scan", null, {}],
  [1200, "qualify", { kind: "scan", summary: "J'ai relevé 214 offres, dont 38 où je peux postuler moi-même." }, { scanned: 214 }],
  [2200, "match", { kind: "shortlist", summary: "Je reprends tes offres retenues : je m'occupe des 4 meilleures." }, { qualified: 38, shortlisted: 4 }],
  [3200, "prepare", { kind: "letter_written", summary: `Dossier prêt pour « ${JOBS[0].title} »${chez("Atelier Nord")} — alice postule.` }, { letters: 1, packs: 1 }],
  [4200, "prepare", { kind: "letter_written", summary: `Dossier prêt pour « ${JOBS[1].title} »${chez("Maison Brume")} — alice postule.` }, { letters: 2, packs: 2 }],
  [5200, "apply", { kind: "applied", summary: `Candidature envoyée pour « ${JOBS[0].title} »${chez("Atelier Nord")}.` }, { sent: 1 }],
  [6200, "apply", { kind: "applied", summary: `Candidature envoyée pour « ${JOBS[1].title} »${chez("Maison Brume")}.` }, { sent: 2 }],
  [7200, "apply", { kind: "awaiting_approval", summary: "1 candidature attend ton feu vert dans Candidatures." }, { awaiting_approval: 1 }],
];

function makeRun(state) {
  const started = state.chatAt;
  const base = {
    id: "run-1", title: "Alternance marketing digital · Lyon", objective: "apply", duration_minutes: 30,
    status: "preparing", current_step: null, allowed_actions: { send: true }, stats: {}, report: null,
    started_at: iso(20000), ends_at: iso(-1800000), finished_at: null, created_at: iso(20000),
    seconds_remaining: 1780, progress: 0.01, events: [],
  };
  if (!started) return base;
  const t = Date.now() - started;
  const events = [];
  let stats = {}, step = null;
  RUN_SCRIPT.forEach(([at, s, ev, patch], i) => {
    if (t < at) return;
    step = s; stats = { ...stats, ...patch };
    if (ev) events.unshift({ id: `ev-${i}`, ...ev, payload: null, created_at: new Date(started + at).toISOString() });
  });
  return { ...base, status: "running", current_step: step, stats, progress: Math.min(0.9, t / 12000), events };
}

// ── Chat reply ─────────────────────────────────────────────────────────────
const CHAT_REPLY = {
  reply:
    "J'ai trouvé **4 alternances en marketing digital à Lyon** qui collent à ton profil. " +
    "Je prépare les dossiers des meilleures et j'envoie celles que ton mandat m'autorise — tu suis tout juste en dessous.",
  ui_blocks: [{ type: "jobs", data: JOBS }],
  conversation_id: "conv-1",
};

// ── SSE for /apply/{job}/stream — real event format (event: x\ndata: {...}\n\n)
const APPLY_EVENTS = (job) => [
  [500, "step", { key: "authorization", label: "Je vérifie ce que ton mandat m'autorise", status: "running" }],
  [1500, "step", { key: "authorization", label: "Autorisée", status: "done" }],
  [1700, "step", { key: "send", label: "J'envoie ta candidature", status: "running" }],
  [3300, "done", { dispatch_id: `disp-${job.id}`, status: "sent", real: true, message: `Candidature envoyée à ${job.company_name}.` }],
];

let sseServer = null;
export async function startSseServer(port = 8799) {
  if (sseServer) return port;
  sseServer = http.createServer((req, res) => {
    const m = req.url.match(/\/apply\/([^/]+)\/stream/);
    const job = JOB[m?.[1]] ?? JOBS[0];
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", ...CORS });
    res.flushHeaders();
    let last = 0;
    (async () => {
      for (const [at, ev, data] of APPLY_EVENTS(job)) {
        await new Promise((r) => setTimeout(r, at - last));
        last = at;
        res.write(`event: ${ev}\ndata: ${JSON.stringify(data)}\n\n`);
      }
      res.end();
    })();
  });
  await new Promise((r) => sseServer.listen(port, r));
  return port;
}
export function stopSseServer() { sseServer?.close(); sseServer = null; }

// ── Router ─────────────────────────────────────────────────────────────────
/**
 * Installs the mock on a Playwright BrowserContext.
 * scene: "chat" | "canvas" | "candidatures"
 */
export async function installMock(ctx, { scene = "chat", ssePort = 8799, log = console.log } = {}) {
  const state = { chatAt: null, sent: false };
  await startSseServer(ssePort);

  const handle = (method, path, url) => {
    const c = `/api/candidates/${CAND}`;
    if (path === "/api/auth/config") return { enabled: true };
    if (path === "/api/me") return { user_id: "u-demo", email: CANDIDATE.email, candidate_id: CAND, auth_disabled: false };
    if (path === "/api/me/seen") return null;
    if (path === c) return CANDIDATE;
    if (path === `${c}/pipeline`) return pipeline(scene);
    if (path === `${c}/mission`) return MISSION(scene);
    if (path === `${c}/mission/journal`) return [];
    if (path === `${c}/mission/journal/read`) return { marked: 0 };
    if (path === `${c}/mission/runs/current`) return scene === "chat" ? makeRun(state) : null;
    if (path === `${c}/billing`) return BILLING;
    if (path === `${c}/cv-design`) return { mode: "template", template_id: "minimalist", color_hex: "#006045", show_photo: false, has_original: false, original_filename: null, is_explicit: true, has_photo: false };
    if (path === `${c}/inbox/unread`) return { unread: 0 };
    if (path === `${c}/inbox`) return { replies: [], unread: 0, total: 0 };
    if (path === `${c}/notifications/history`) return [];
    if (path === `${c}/conversations`) {
      if (scene === "canvas") return [{ id: "conv-1", title: "Alternance marketing à Lyon", updated_at: iso(60000), job_id: null }];
      return state.chatAt ? [{ id: "conv-1", title: "Alternance marketing à Lyon", updated_at: iso(0), job_id: null }] : [];
    }
    if (path === `${c}/conversations/conv-1/messages`) {
      if (scene !== "canvas") return [];
      return [
        { id: "m1", sender: "user", text: "Trouve-moi une alternance en marketing à Lyon", ui_blocks: null, created_at: iso(120000) },
        { id: "m2", sender: "alice", text: CHAT_REPLY.reply, ui_blocks: CHAT_REPLY.ui_blocks, created_at: iso(110000) },
      ];
    }
    if (path === "/api/chat" && method === "POST") { state.chatAt = Date.now() + 200; return CHAT_REPLY; }
    let m;
    if ((m = path.match(/^\/api\/jobs\/([^/]+)$/))) {
      return { description_raw: DESCRIPTION, description_parsed: {}, salary_range: "Grille alternance", experience_range: "Débutant accepté", department: "Marketing", tech_stack: ["Instagram", "Canva", "GA4", "Meta Ads", "Brevo"], apply_url: JOB[m[1]]?.source_url };
    }
    if ((m = path.match(new RegExp(`^${c}/apply/([^/]+)/state$`)))) {
      const sent = state.sent;
      return { application_id: `app-${m[1]}`, stage: sent ? "applied" : "awaiting", apply_mode: "auto", pack_ready: true, pack_ready_at: iso(3600000), headline: "Marketing digital & social media — alternance", letter: { subject: "Candidature — Alternance marketing digital", body: "Madame, Monsieur,", greeting: "Madame, Monsieur,", closing: "Camille Martin" }, applied_at: sent ? iso(0) : null, dispatch_status: sent ? "sent" : "awaiting_approval", dispatch_id: `disp-${m[1]}`, changes: null };
    }
    if ((m = path.match(new RegExp(`^${c}/apply/([^/]+)/plan$`)))) {
      const j = JOB[m[1]] ?? JOBS[0];
      return { job_id: j.id, job_title: j.title, company_name: j.company_name, channel: "ats_api", destination: null, can_apply: true, blocked_reason: null, complexity: "simple", summary: `Je dépose ta candidature sur le site carrière de ${j.company_name} : CV adapté et lettre.`, fallback_url: j.source_url, requirements: [
        { key: "resume", label: "CV adapté à l'offre", status: "satisfied", detail: "Marketing digital & social media" },
        { key: "cover_letter", label: "Lettre de motivation", status: "satisfied", detail: "signée" },
        { key: "identity", label: "Nom, e-mail et téléphone", status: "satisfied", detail: "" },
      ] };
    }
    if ((m = path.match(new RegExp(`^${c}/apply/dispatches/([^/]+)$`)))) {
      state.sent = true;
      return { dispatch_id: m[1], status: "sent", sent: true, headline: "Candidature envoyée à Atelier Nord.", detail: null, job_url: JOBS[0].source_url, has_resume: true, has_letter: true, resume_name: "CV_Camille_Martin.pdf", steps: [], mailto: null };
    }
    return undefined;
  };

  await ctx.route(`${API}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (/\/apply\/[^/]+\/stream$/.test(url.pathname)) {
      if (method === "POST") state.sent = true;
      return route.continue({ url: `http://localhost:${ssePort}${url.pathname}` });
    }
    const body = handle(method, url.pathname.replace(/\/$/, ""), url);
    if (body === undefined) {
      log(`[mock] UNHANDLED ${method} ${url.pathname}${url.search}`);
      return route.fulfill({ status: 404, headers: { ...CORS, "content-type": "application/json" }, body: JSON.stringify({ detail: "Not Found" }) });
    }
    if (body === null) return route.fulfill({ status: 204, headers: CORS });
    const delay = url.pathname === "/api/chat" ? 1800 : 60;
    await new Promise((r) => setTimeout(r, delay));
    return route.fulfill({ status: 200, headers: { ...CORS, "content-type": "application/json" }, body: JSON.stringify(body) });
  });
  return state;
}
