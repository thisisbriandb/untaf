/**
 * Le service worker : seul à parler à l'API d'Alice.
 *
 * Les pages (et leurs cadres) lui envoient des messages ; il porte le jeton,
 * évite les blocages CORS et garde en mémoire le CV adapté d'une offre le
 * temps de remplir tous les cadres d'un formulaire.
 */

const cvCache = new Map(); // jobId → { data, name, type }

async function session() {
  const { session } = await chrome.storage.local.get("session");
  if (!session || !session.token) return null;
  if (session.expires_at && new Date(session.expires_at).getTime() <= Date.now()) return null;
  return session;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, { method = "GET", body, raw = false } = {}) {
  const s = await session();
  if (!s) throw new ApiError(401, "Connecte-toi sur le site d'Alice : l'extension reprendra ta session.");
  const res = await fetch(`${s.api}/api${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${s.token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : "";
    } catch { /* corps vide */ }
    if (res.status === 401) {
      await chrome.storage.local.remove("candidateId");
      detail = detail || "Session expirée : reconnecte-toi sur le site d'Alice.";
    }
    throw new ApiError(res.status, detail || `Alice ne répond pas (erreur ${res.status}).`);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

async function candidateId() {
  const { candidateId } = await chrome.storage.local.get("candidateId");
  if (candidateId) return candidateId;
  const me = await api("/me");
  if (!me.candidate_id) throw new ApiError(404, "Termine ton profil sur le site d'Alice d'abord.");
  await chrome.storage.local.set({ candidateId: me.candidate_id });
  return me.candidate_id;
}

function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}

function filenameOf(res, fallback) {
  const cd = res.headers.get("Content-Disposition") || "";
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  return m ? decodeURIComponent(m[1]) : fallback;
}

// ── Les actions ──────────────────────────────────────────────────────────

/** L'offre de cette page dans la liste du candidat, ou null. */
async function match(url) {
  const cid = await candidateId();
  return api(`/candidates/${cid}/extension/match?url=${encodeURIComponent(url)}`);
}

/** Ajoute la page à la liste ; renvoie la fiche d'offre. */
async function importPage({ url, text }) {
  const cid = await candidateId();
  if (!text || text.length < 80) {
    throw new ApiError(422, "Je ne trouve pas assez de texte d'annonce sur cette page.");
  }
  return api(`/candidates/${cid}/apply/import`, {
    method: "POST",
    body: { url, text: text.slice(0, 30000) },
  });
}

/**
 * Tout ce qu'il faut pour remplir : l'offre (retrouvée ou ajoutée), l'identité,
 * la lettre du dossier.
 */
async function prepareFill({ url, text }) {
  const cid = await candidateId();
  let job = await match(url);
  let imported = false;
  if (!job) {
    const card = await importPage({ url, text });
    job = { job_id: card.id, title: card.title, company_name: card.company_name, pack_ready: false };
    imported = true;
  }
  const [profile, state] = await Promise.all([
    api(`/candidates/${cid}/extension/profile`),
    api(`/candidates/${cid}/apply/${job.job_id}/state`).catch(() => null),
  ]);
  return { job, imported, profile, letter: state && state.letter ? state.letter : null };
}

/** Le CV adapté à l'offre, en base64 (rédigé à la demande s'il ne l'est pas). */
async function tailoredCv(jobId) {
  if (cvCache.has(jobId)) return cvCache.get(jobId);
  const cid = await candidateId();
  const res = await api(`/candidates/${cid}/apply/${jobId}/cv`, { raw: true });
  const file = {
    data: toBase64(await res.arrayBuffer()),
    name: filenameOf(res, "CV.pdf"),
    type: res.headers.get("Content-Type") || "application/pdf",
  };
  cvCache.set(jobId, file);
  return file;
}

async function answers({ jobId, questions, pageText }) {
  const cid = await candidateId();
  return api(`/candidates/${cid}/extension/answers`, {
    method: "POST",
    body: { job_id: jobId, questions, page_text: pageText ? pageText.slice(0, 12000) : null },
  });
}

async function markApplied(jobId) {
  const cid = await candidateId();
  return api(`/candidates/${cid}/apply/${jobId}/mark-applied`, { method: "POST" });
}

async function status() {
  const s = await session();
  const { session: stored } = await chrome.storage.local.get("session");
  return {
    connected: !!s,
    email: s ? s.email : null,
    app: (stored && stored.app) || "https://alice-agent.fr",
  };
}

// ── Remplir tous les cadres d'un onglet ──────────────────────────────────

/**
 * Les formulaires vivent souvent dans un iframe (Greenhouse, Lever…) : on
 * prépare une fois, puis chaque cadre remplit ce qu'il contient.
 */
async function fillTab(tabId, page) {
  const ctx = await prepareFill(page);
  const frames = await chrome.webNavigation?.getAllFrames?.({ tabId }).catch(() => null);
  const results = [];
  const targets = frames && frames.length ? frames.map((f) => f.frameId) : [0];
  await Promise.all(targets.map(async (frameId) => {
    try {
      const r = await chrome.tabs.sendMessage(tabId, { type: "fill", ctx }, { frameId });
      if (r) results.push(r);
    } catch { /* cadre sans script (about:blank, autre extension) */ }
  }));
  const total = results.reduce(
    (acc, r) => ({
      filled: acc.filled + (r.filled || 0),
      left: acc.left + (r.left || 0),
      cv: acc.cv || !!r.cv,
      cvError: acc.cvError || r.cvError || null,
    }),
    { filled: 0, left: 0, cv: false, cvError: null },
  );
  return { ...total, job: ctx.job, imported: ctx.imported };
}

const handlers = {
  async session({ payload }) {
    const { session: prev } = await chrome.storage.local.get("session");
    if (!prev || prev.token !== payload.token || prev.api !== payload.api) {
      await chrome.storage.local.remove("candidateId");
      cvCache.clear();
    }
    await chrome.storage.local.set({ session: payload });
    return true;
  },
  status: () => status(),
  match: ({ url }) => match(url),
  import: ({ page }) => importPage(page),
  answers: (msg) => answers(msg),
  cv: ({ jobId }) => tailoredCv(jobId),
  markApplied: ({ jobId }) => markApplied(jobId),
  fill: ({ page }, sender) => fillTab(sender.tab.id, page),
  async formInFrame(_msg, sender) {
    await chrome.tabs.sendMessage(sender.tab.id, { type: "formInFrame" }, { frameId: 0 }).catch(() => {});
    return true;
  },
  async fillActive({ tabId }) {
    // Depuis la fenêtre de l'extension : on demande la page au cadre principal.
    const page = await chrome.tabs.sendMessage(tabId, { type: "page" }, { frameId: 0 });
    return fillTab(tabId, page);
  },
  async importActive({ tabId }) {
    const page = await chrome.tabs.sendMessage(tabId, { type: "page" }, { frameId: 0 });
    return importPage(page);
  },
  async matchActive({ tabId }) {
    const page = await chrome.tabs.sendMessage(tabId, { type: "page" }, { frameId: 0 });
    return { page: { url: page.url, jobLike: page.jobLike }, job: await match(page.url) };
  },
};

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  const handler = handlers[msg && msg.type];
  if (!handler) return false;
  Promise.resolve()
    .then(() => handler(msg, sender))
    .then((data) => reply({ ok: true, data }))
    .catch((e) => reply({ ok: false, error: e.message || String(e), status: e.status || 0 }));
  return true; // réponse asynchrone
});
