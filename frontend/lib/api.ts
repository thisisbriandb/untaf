/**
 * Appels à l'API, authentifiés.
 *
 * Tout passe par `apiFetch`, qui joint le jeton de session : l'API refuse
 * désormais toute requête sur un profil sans preuve que c'est le sien. Les
 * téléchargements ne peuvent plus être de simples liens (`<a href>` n'envoie
 * pas d'en-tête) : ils passent par `downloadFile` / `openFile`.
 */

import { API_BASE_URL } from "./config";
import { accessToken } from "./supabase";

/**
 * Le serveur d'Alice ne répond pas du tout (éteint, mauvaise adresse, CORS).
 * Distinct d'une réponse en erreur : l'interface doit dire « injoignable »,
 * pas « vérifie ta connexion », qui envoie l'utilisateur sur une fausse piste.
 */
export class ApiUnreachableError extends Error {
  constructor() {
    super(`Le serveur d'Alice ne répond pas (${API_BASE_URL}).`);
    this.name = "ApiUnreachableError";
  }
}

let warned = false;

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(input, { ...init, headers });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    if (!warned) {
      warned = true;
      console.error(
        `API injoignable sur ${API_BASE_URL}. En local : lancer \`uvicorn app.main:app --port 8000\` ` +
          "dans backend/job-discovery. Déployé : renseigner NEXT_PUBLIC_API_URL au build du frontend.",
      );
    }
    throw new ApiUnreachableError();
  }
  if (res.status === 401 && typeof window !== "undefined" && token) {
    // Session révoquée ou expirée sans rafraîchissement possible.
    window.dispatchEvent(new CustomEvent("untaf:unauthorized"));
  }
  return res;
}

function filenameFrom(res: Response, fallback: string): string {
  const header = res.headers.get("Content-Disposition") ?? "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1]) : fallback;
}

/** Télécharge un fichier protégé. Renvoie false si le serveur refuse. */
export async function downloadFile(url: string, fallbackName = "document"): Promise<boolean> {
  const res = await apiFetch(url);
  if (!res.ok) return false;
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filenameFrom(res, fallbackName);
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 10_000);
  return true;
}

/** Ouvre un fichier protégé (PDF) dans un nouvel onglet. */
export async function openFile(url: string): Promise<boolean> {
  // L'onglet est ouvert tout de suite, dans le geste de l'utilisateur, sans
  // quoi le navigateur le bloque comme une fenêtre surgissante.
  const tab = window.open("", "_blank");
  const res = await apiFetch(url);
  if (!res.ok) {
    tab?.close();
    return false;
  }
  const href = URL.createObjectURL(await res.blob());
  if (tab) tab.location.href = href;
  else window.open(href, "_blank", "noopener");
  return true;
}

export interface Me {
  user_id: string;
  email: string | null;
  candidate_id: string | null;
  auth_disabled: boolean;
}

/** Le compte connecté et son profil, ou null sans session valide. */
export async function fetchMe(): Promise<Me | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/me`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** Message à montrer à l'utilisateur pour une erreur d'appel. */
export function describeApiError(err: unknown, fallback: string): string {
  if (err instanceof ApiUnreachableError) {
    return "Je n'arrive pas à joindre mon serveur pour l'instant. Réessaie dans un moment.";
  }
  return fallback;
}
