/**
 * Adresse de l'API. Tolère une valeur saisie sans protocole ou avec un « / »
 * final : « api.exemple.com/ » serait sinon lu comme un chemin relatif au site.
 *
 * En production, NEXT_PUBLIC_API_URL doit être fourni AU BUILD (Next l'inscrit
 * dans le bundle) : sans lui, le site déployé appelle le localhost du visiteur
 * et chaque requête échoue en ERR_CONNECTION_REFUSED.
 */
function normalizeApiUrl(raw: string | undefined): string {
  const value = (raw || "").trim().replace(/\/+$/, "");
  if (!value) return "http://localhost:8000";
  return /^https?:\/\//.test(value) ? value : `https://${value}`;
}

export const API_BASE_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);

if (
  typeof window !== "undefined" &&
  !process.env.NEXT_PUBLIC_API_URL &&
  !["localhost", "127.0.0.1"].includes(window.location.hostname)
) {
  console.error(
    "NEXT_PUBLIC_API_URL absent du build : le frontend appelle http://localhost:8000. " +
      "Renseigne la variable dans l'hébergeur (Vercel) puis redéploie.",
  );
}
