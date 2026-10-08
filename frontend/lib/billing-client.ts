/**
 * Abonnement : formule, usage de la semaine, paiement et espace client.
 *
 * Le paiement et la gestion (carte, factures, résiliation) se font chez Lemon
 * Squeezy : on ne fait qu'y envoyer, par des liens créés côté serveur.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

export type UsageKind = "pack" | "mission" | "spontaneous" | "message";

export interface Usage {
  used: number;
  limit: number;
  label: string;
  window: "day" | "week";
}

export interface Billing {
  /** La facturation est-elle ouverte sur ce déploiement ? */
  enabled: boolean;
  plan: "free" | "weekly";
  price_label: string;
  status: string | null;
  renews_at: string | null;
  ends_at: string | null;
  cancelled: boolean;
  usage: Record<UsageKind, Usage>;
}

/** Ce que le serveur renvoie (402) quand une limite est atteinte. */
export interface PlanLimit {
  code: "plan_limit";
  kind: UsageKind;
  used: number;
  limit: number;
  paid: boolean;
  message: string;
}

const base = (candidateId: string) => `${API_BASE_URL}/api/candidates/${candidateId}/billing`;

export async function fetchBilling(candidateId: string): Promise<Billing | null> {
  try {
    const res = await apiFetch(base(candidateId));
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

async function urlFrom(res: Response): Promise<string> {
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.url) {
    throw new Error(typeof body?.detail === "string" ? body.detail : "Réessaie dans un instant.");
  }
  return body.url as string;
}

/** Page de paiement Lemon Squeezy (abonnement hebdomadaire). */
export async function checkoutUrl(candidateId: string): Promise<string> {
  return urlFrom(await apiFetch(`${base(candidateId)}/checkout`, { method: "POST" }));
}

/** Espace client : carte bancaire, factures, résiliation. */
export async function portalUrl(candidateId: string): Promise<string> {
  return urlFrom(await apiFetch(`${base(candidateId)}/portal`, { method: "POST" }));
}
