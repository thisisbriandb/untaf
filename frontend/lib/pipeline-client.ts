/**
 * Suivi de bout en bout : candidatures, file de validation, relances,
 * notifications par e-mail.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

export type Stage =
  | "to_prepare"
  | "ready"
  | "awaiting"
  | "simulated"
  | "manual"
  | "applied"
  | "interview"
  | "offer"
  | "rejected"
  | "closed";

export type ApplicationStatus =
  | "pending" | "matched" | "applied" | "rejected" | "interview" | "offer" | "closed";

export interface DispatchBrief {
  id: string;
  status: "prepared" | "awaiting_approval" | "approved" | "sent" | "failed" | "rejected" | "simulated";
  channel: string;
  destination: string | null;
  error: string | null;
  sent_at: string | null;
  created_at: string;
  /** Brouillon prêt à ouvrir pour finir à la main, quand rien n'est parti. */
  mailto: string | null;
}

export interface Followup {
  due: boolean;
  days_since_applied: number | null;
  status: "drafted" | "sent" | "dismissed" | null;
  subject?: string | null;
  body?: string | null;
  to?: string | null;
  sent_at?: string | null;
}

export interface PipelineItem {
  application_id: string;
  job_id: string;
  title: string;
  company_name: string;
  location: string | null;
  contract_type: string;
  remote_policy: string;
  match_score: number;
  status: ApplicationStatus;
  stage: Stage;
  pack_ready: boolean;
  applied_at: string | null;
  source_url: string | null;
  dispatch: DispatchBrief | null;
  followup: Followup;
  timeline: { status: string; at: string; note?: string }[];
  created_at: string;
}

export interface Pipeline {
  items: PipelineItem[];
  counts: Partial<Record<Stage | "followup_due", number>>;
}

export const STAGE_LABELS: Record<Stage, string> = {
  to_prepare: "Retenue",
  ready: "Pack prêt",
  awaiting: "À valider",
  simulated: "Répétition",
  manual: "À finir",
  applied: "Envoyée",
  interview: "Entretien",
  offer: "Offre",
  rejected: "Refusée",
  closed: "Close",
};

const root = (candidateId: string) => `${API_BASE_URL}/api/candidates/${candidateId}`;

async function json<T>(promise: Promise<Response>): Promise<T | null> {
  try {
    const res = await promise;
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

const post = (url: string, body?: unknown) =>
  apiFetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

// ── Pipeline ──────────────────────────────────────────────────────────────

export const fetchPipeline = (candidateId: string) =>
  json<Pipeline>(apiFetch(`${root(candidateId)}/pipeline`));

export const approveDispatch = (candidateId: string, dispatchId: string) =>
  json<DispatchBrief>(post(`${root(candidateId)}/dispatches/${dispatchId}/approve`));

export const rejectDispatch = (candidateId: string, dispatchId: string) =>
  json<DispatchBrief>(post(`${root(candidateId)}/dispatches/${dispatchId}/reject`));

export const approveAll = (candidateId: string) =>
  json<{ sent: number; simulated: number; failed: number }>(
    post(`${root(candidateId)}/dispatches/approve-all`),
  );

export async function updateApplicationStatus(
  applicationId: string,
  status: ApplicationStatus,
  note?: string,
): Promise<boolean> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/applications/${applicationId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note: note || null }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

/** Pièces figées d'un envoi : exactement ce qui est parti (ou serait parti). */
export const dispatchResumeUrl = (candidateId: string, dispatchId: string) =>
  `${root(candidateId)}/apply/dispatches/${dispatchId}/resume`;

// ── Relances ──────────────────────────────────────────────────────────────

export const prepareFollowup = (candidateId: string, applicationId: string, regenerate = false) =>
  json<Followup>(
    post(`${root(candidateId)}/applications/${applicationId}/followup?regenerate=${regenerate}`),
  );

export const markFollowup = (
  candidateId: string,
  applicationId: string,
  status: "sent" | "dismissed",
) =>
  json<Followup>(post(`${root(candidateId)}/applications/${applicationId}/followup/mark`, { status }));

export function followupMailto(f: Followup): string {
  const to = f.to ? encodeURIComponent(f.to) : "";
  return `mailto:${to}?subject=${encodeURIComponent(f.subject ?? "")}&body=${encodeURIComponent(
    f.body ?? "",
  )}`;
}

// ── Notifications ─────────────────────────────────────────────────────────

export type DigestPeriod = "off" | "daily" | "weekly";

export interface NotificationPrefs {
  enabled: boolean;
  mission_report: boolean;
  application_sent: boolean;
  awaiting_approval: boolean;
  followups: boolean;
  digest: DigestPeriod;
}

export interface NotificationSettings {
  prefs: NotificationPrefs;
  recipient: string;
  delivery_configured: boolean;
}

export interface NotificationRecord {
  id: string;
  kind: string;
  status: "sent" | "simulated" | "failed";
  subject: string;
  error: string | null;
  created_at: string;
}

export const fetchNotificationSettings = (candidateId: string) =>
  json<NotificationSettings>(apiFetch(`${root(candidateId)}/notifications`));

export const saveNotificationPrefs = (candidateId: string, prefs: NotificationPrefs) =>
  json<NotificationSettings>(
    apiFetch(`${root(candidateId)}/notifications`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(prefs),
    }),
  );

export const sendTestNotification = (candidateId: string) =>
  json<NotificationRecord>(post(`${root(candidateId)}/notifications/test`));

export const fetchNotificationHistory = (candidateId: string) =>
  json<NotificationRecord[]>(apiFetch(`${root(candidateId)}/notifications/history?limit=8`));

// ── Journal (cloche) ──────────────────────────────────────────────────────

export const markJournalRead = (candidateId: string) =>
  json<{ marked: number }>(post(`${root(candidateId)}/mission/journal/read`));
