/**
 * La fenêtre de l'extension : l'état de la connexion, et les deux gestes sur
 * l'onglet ouvert, même quand la pastille ne s'y affiche pas.
 */
const $ = (id) => document.getElementById(id);
const send = (msg) => new Promise((resolve) => chrome.runtime.sendMessage(msg, (r) => resolve(r || { ok: false, error: "Pas de réponse." })));

function say(text, warn = false) {
  $("msg").textContent = text || "";
  $("msg").classList.toggle("warn", warn);
}

function button(text, onClick, ghost = false) {
  const b = document.createElement("button");
  b.textContent = text;
  if (ghost) b.className = "ghost";
  b.addEventListener("click", async () => {
    document.querySelectorAll("button").forEach((x) => (x.disabled = true));
    await onClick();
    document.querySelectorAll("button").forEach((x) => (x.disabled = false));
  });
  $("actions").appendChild(b);
}

async function main() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const status = await send({ type: "status" });
  const s = status.ok ? status.data : { connected: false, app: "https://alice-agent.fr" };

  if (!s.connected) {
    $("who").textContent = "Non connecté";
    $("job").textContent = "Connecte-toi sur le site d'Alice : l'extension reprend ta session.";
    button("Ouvrir Alice", () => chrome.tabs.create({ url: s.app }));
    return;
  }
  $("who").textContent = s.email || "Connecté";

  if (!tab || !/^https?:/.test(tab.url || "")) {
    $("job").textContent = "Ouvre une offre d'emploi pour qu'Alice t'aide.";
    return;
  }
  const m = await send({ type: "matchActive", tabId: tab.id });
  if (!m.ok) {
    $("job").textContent = "Actualise la page pour qu'Alice puisse la lire.";
    return;
  }
  const job = m.data.job;
  $("job").textContent = job
    ? `${job.title}${job.company_name ? ` · ${job.company_name}` : ""}${job.pack_ready ? " — dossier prêt" : ""}`
    : "Cette page n'est pas dans ta liste.";

  $("actions").innerHTML = "";
  if (!job) {
    button("Ajouter à Alice", async () => {
      say("J'ajoute l'offre…");
      const r = await send({ type: "importActive", tabId: tab.id });
      if (!r.ok) return say(r.error, true);
      $("job").textContent = `${r.data.title} · ${r.data.company_name}`;
      say(`Ajoutée à ta liste (correspondance ${r.data.match_score} %).`);
    });
  }
  button("Remplir avec Alice", async () => {
    say(job && job.pack_ready ? "Je remplis…" : "J'adapte ton CV à l'offre puis je remplis…");
    const r = await send({ type: "fillActive", tabId: tab.id });
    if (!r.ok) return say(r.error, true);
    const d = r.data;
    if (!d.filled && !d.left) return say("Pas de formulaire ici : ouvre la page « Postuler ».", true);
    say(`${d.filled} champ(s) rempli(s)${d.cv ? ", CV adapté joint" : ""}.${d.left ? `\n${d.left} à compléter (en orange).` : ""}\nRelis, puis envoie sur le site.`);
  }, !job);
  button("Ouvrir mes candidatures", () => chrome.tabs.create({ url: `${s.app}/dashboard` }), true);
}

main();
