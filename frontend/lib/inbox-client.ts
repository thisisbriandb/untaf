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
  application_id: string | null;
  /** Rattachement incertain : c'est au candidat de dire quelle candidature. */
  to_link: boolean;
  suggested_application_id: string | null;
  attachments_count: number;
}

export interface ReplyAttachment {
  id: string;
  filename: string;
  mime: string;
  size: number;
}

export interface ReplyDetail extends Reply {
  text: string;
  attachments: ReplyAttachment[];
  /** Trop lourdes pour être gardées : le nom seulement. */
  skipped_attachments: { filename: string; size: number }[];
}

/** Une candidature à laquelle rattacher un message. */
export interface LinkChoice {
  application_id: string;
  job_title: string;
  company_name: string | null;
  status: string;
}

export interface Inbox {
  address: string | null;
  configured: boolean;
  unread: number;
  replies: Reply[];
  choices: LinkChoice[];
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

/** Dit à quelle candidature répond un message (null : aucune). Le suivi suit. */
export async function linkReply(candidateId: string, replyId: string, applicationId: string | null) {
  const r = await json<{ reply: Reply; status: string | null }>(
    apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/inbox/${replyId}/link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ application_id: applicationId }),
    }),
  );
  if (r && typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
  return r;
}

export const attachmentUrl = (candidateId: string, replyId: string, attachmentId: string) =>
  `${API_BASE_URL}/api/candidates/${candidateId}/inbox/${replyId}/attachments/${attachmentId}`;

export function fileSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
  return `${Math.max(1, Math.round(bytes / 1024))} Ko`;
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
