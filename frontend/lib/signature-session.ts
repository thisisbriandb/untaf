/**
 * Signer sur son téléphone depuis un ordinateur : une session courte (10 min)
 * dont le jeton voyage dans un QR code. Routes publiques : on signe aussi
 * pendant l'inscription, avant d'avoir un compte.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

const base = `${API_BASE_URL}/api/signature-sessions`;

export async function openSignatureSession(): Promise<{ token: string; expires_at: string } | null> {
  try {
    const res = await apiFetch(base, { method: "POST" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export type SessionState = { status: "pending" | "signed" | "expired" | "gone"; image?: string | null };

export async function readSignatureSession(token: string): Promise<SessionState | null> {
  try {
    const res = await apiFetch(`${base}/${encodeURIComponent(token)}`);
    if (res.status === 404) return { status: "gone" };
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/** Depuis le téléphone. Renvoie null si c'est fait, sinon le motif. */
export async function dropSignature(token: string, image: string): Promise<string | null> {
  try {
    const res = await apiFetch(`${base}/${encodeURIComponent(token)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image }),
    });
    if (res.ok) return null;
    const body = await res.json().catch(() => null);
    return typeof body?.detail === "string" ? body.detail : "La signature n'a pas pu être envoyée.";
  } catch {
    return "Pas de connexion : réessaie dans un instant.";
  }
}
