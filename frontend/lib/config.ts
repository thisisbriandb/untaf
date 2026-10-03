/**
 * Adresse de l'API. Tolère une valeur saisie sans protocole ou avec un « / »
 * final : « api.exemple.com/ » serait sinon lu comme un chemin relatif au site.
 */
function normalizeApiUrl(raw: string | undefined): string {
  const value = (raw || "").trim().replace(/\/+$/, "");
  if (!value) return "http://localhost:8000";
  return /^https?:\/\//.test(value) ? value : `https://${value}`;
}

export const API_BASE_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);
