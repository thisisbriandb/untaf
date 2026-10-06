/**
 * Sur le site d'Alice : transmet la session du candidat à l'extension.
 *
 * L'extension n'a pas d'écran de connexion à elle : être connecté sur le site
 * suffit. On relit régulièrement, pour suivre une connexion ou une déconnexion.
 */
(() => {
  const meta = document.querySelector('meta[name="alice-api"]');
  if (!meta) return; // pas une page d'Alice

  let last = "";
  const sync = () => {
    let session = null;
    try {
      const raw = localStorage.getItem("alice_session");
      const s = raw ? JSON.parse(raw) : null;
      if (s && s.token && new Date(s.expires_at).getTime() > Date.now()) session = s;
    } catch { /* stockage illisible : déconnecté */ }
    const payload = {
      api: meta.content.replace(/\/+$/, ""),
      app: location.origin,
      token: session ? session.token : null,
      expires_at: session ? session.expires_at : null,
      email: session ? session.email : null,
    };
    const key = JSON.stringify(payload);
    if (key === last) return;
    last = key;
    chrome.runtime.sendMessage({ type: "session", payload }).catch(() => {});
  };

  sync();
  setInterval(sync, 4000);
  window.addEventListener("storage", sync);
})();
