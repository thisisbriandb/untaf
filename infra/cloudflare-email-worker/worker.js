/**
 * Worker Cloudflare : réception des réponses des recruteurs pour Alice.
 *
 * Chaque e-mail arrivé sur le sous-domaine de réception (ex.
 * reponses.alice-agent.fr) est transmis tel quel à l'API d'Alice, qui le lit,
 * le range dans la bonne candidature et le transfère au candidat.
 *
 * Variables (Settings → Variables du Worker) :
 *   ALICE_INBOUND_URL  https://<api>/api/inbound/email
 *   INBOUND_SECRET     même valeur que INBOUND_SECRET sur Railway (secret chiffré)
 *   FALLBACK_TO        optionnel : adresse vérifiée qui reçoit l'e-mail si
 *                      l'API ne répond pas (rien ne se perd)
 *
 * Aucune dépendance : copiable tel quel dans l'éditeur du tableau de bord.
 */

const MAX_BYTES = 20 * 1024 * 1024;

async function readRaw(stream) {
  const reader = stream.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > MAX_BYTES) throw new Error("message trop volumineux");
    chunks.push(value);
  }
  const out = new Uint8Array(size);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

function toBase64(bytes) {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}

export default {
  async email(message, env) {
    try {
      const raw = await readRaw(message.raw);
      const res = await fetch(env.ALICE_INBOUND_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Inbound-Secret": env.INBOUND_SECRET },
        // L'enveloppe (from/to) en plus du message : l'adresse de réponse peut
        // n'être qu'en copie cachée.
        body: JSON.stringify({ from: message.from, to: message.to, raw: toBase64(raw) }),
      });
      if (!res.ok) throw new Error(`API Alice : ${res.status}`);
    } catch (e) {
      console.error("Réception Alice :", e.message);
      if (env.FALLBACK_TO) {
        await message.forward(env.FALLBACK_TO, new Headers({ "X-Alice-Inbound-Error": String(e.message).slice(0, 200) }));
        return;
      }
      throw e;
    }
  },
};
