import { API_BASE_URL } from "./config";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Wrapper fetch qui envoie toujours le cookie de session (indispensable :
 * frontend et backend sont sur des origines différentes, `fetch` ne joint
 * pas les cookies cross-origin sans `credentials: "include"`) et redirige
 * vers /login sur un 401 — sauf pour les appels d'auth eux-mêmes.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });

  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/")) {
    window.location.href = "/login";
  }

  return res;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  return res.json();
}
