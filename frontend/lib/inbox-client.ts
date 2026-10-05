/**
 * Les réponses des recruteurs, arrivées sur l'adresse de réponse du candidat.
 *
 * Un événement fenêtre (`untaf:inbox-changed`) prévient les autres vues
 * (compteur de la barre latérale) quand un message est lu.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

export type ReplyKind = "interview" | "rejection" | "offer" | "request" | "acknowledgement" | "other";

export interface Reply {
  id: string;
  kind: ReplyKind;
  summary: string;
  next_step: string | null;
  subject: string;
  from_email: string;
  from_name: string | null;
  received_at: string;
  read: boolean;
  job_id: string | null;
  job_title: string | null;
  company_name: string | null;
}

export interface ReplyDetail extends Reply {
  text: string;
}

export interface Inbox {
  address: string | null;
  configured: boolean;
  unread: number;
  replies: Reply[];
}

export const KIND_LABEL: Record<ReplyKind, string> = {
  interview: "Entretien proposé",
  offer: "Proposition d'embauche",
  request: "Demande du recruteur",
  rejection: "Réponse négative",
  acknowledgement: "Accusé de réception",
  other: "Message",
};

const EVENT = "untaf:inbox-changed";

async function json<T>(res: Promise<Response>): Promise<T | null> {
  try {
    const r = await res;
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

export function fetchInbox(candidateId: string, jobId?: string) {
  const q = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return json<Inbox>(apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/inbox${q}`));
}

export async function fetchReply(candidateId: string, replyId: string) {
  const r = await json<ReplyDetail>(apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/inbox/${replyId}`));
  if (r && typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
  return r;
}

export function onInboxChanged(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}

/** Lien pour répondre au recruteur depuis sa messagerie. */
export function replyMailto(r: Reply) {
  const subject = /^re\s*:/i.test(r.subject) ? r.subject : `Re: ${r.subject}`;
  return `mailto:${r.from_email}?subject=${encodeURIComponent(subject)}`;
}
