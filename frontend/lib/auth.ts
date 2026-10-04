/**
 * Session de connexion — sans mot de passe, par e-mail.
 *
 * L'API envoie un lien et un code (depuis alice@alice-agent.fr) et signe
 * elle-même la session. Le jeton vit dans le navigateur ; un autre onglet le
 * voit apparaître (événement `storage`) — c'est ce qui permet à l'onglet resté
 * ouvert pendant l'onboarding de reprendre seul quand on clique sur le lien.
 */

import { API_BASE_URL } from "./config";

const KEY = "alice_session";

interface StoredSession {
  token: string;
  expires_at: string;
  email: string;
}

function read(): StoredSession | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as StoredSession;
    if (new Date(s.expires_at).getTime() <= Date.now()) {
      localStorage.removeItem(KEY);
      return null;
    }
    return s;
  } catch {
    return null;
  }
}

/** Jeton de session courant, ou null. */
export async function accessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return read()?.token ?? null;
}

export function sessionEmail(): string | null {
  return typeof window === "undefined" ? null : read()?.email ?? null;
}

function save(s: StoredSession) {
  localStorage.setItem(KEY, JSON.stringify(s));
  // L'événement `storage` ne se déclenche que dans les AUTRES onglets.
  window.dispatchEvent(new CustomEvent("alice:session"));
}

export async function signOut(): Promise<void> {
  localStorage.removeItem(KEY);
  window.dispatchEvent(new CustomEvent("alice:session"));
}

/** Prévient quand une session apparaît ou disparaît, dans cet onglet ou un autre. */
export function onSessionChange(cb: (signedIn: boolean) => void): () => void {
  const fire = () => cb(Boolean(read()));
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) fire();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("alice:session", fire);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("alice:session", fire);
  };
}

let configPromise: Promise<boolean> | null = null;

/**
 * La connexion est-elle requise ? Le serveur le dit : en développement sans
 * configuration, il lève les gardes et l'interface saute la connexion.
 */
export function authEnabled(): Promise<boolean> {
  if (!configPromise) {
    configPromise = fetch(`${API_BASE_URL}/api/auth/config`)
      .then((r) => (r.ok ? r.json() : { enabled: true }))
      .then((c: { enabled: boolean }) => c.enabled !== false)
      .catch(() => true);
  }
  return configPromise;
}

export type AuthError = "rate_limited" | "invalid" | "unavailable";

export async function requestLoginLink(email: string): Promise<AuthError | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (res.status === 429) return "rate_limited";
    if (res.status === 422) return "invalid";
    return res.ok ? null : "unavailable";
  } catch {
    return "unavailable";
  }
}

/** Échange un lien (`token`) ou un code (`email` + `code`) contre une session. */
export async function verifyLogin(
  input: { token: string } | { email: string; code: string },
): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) return false;
    const s = await res.json();
    save({ token: s.access_token, expires_at: s.expires_at, email: s.email });
    return true;
  } catch {
    return false;
  }
}
