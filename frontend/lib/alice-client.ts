/**
 * Alice API Client — talks to POST /api/chat on the backend.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

// ── Types ──────────────────────────────────────────────────────────────────

export interface JobCardData {
  id: string;
  title: string;
  company_name: string;
  location: string;
  match_score: number;
  contract_type: string;
  remote_policy: string;
  source_url: string;
  status: string;
  /** Qui envoie : auto (Alice) · assisted (un clic) · manual (sur le site). */
  apply_mode?: ApplyMode;
  /** Un indice qui mérite l'attention (ex. école qui recrute des élèves). */
  warning?: string | null;
}

export type ApplyMode = "auto" | "assisted" | "manual";

export const APPLY_MODE_LABELS: Record<ApplyMode, string> = {
  auto: "Alice postule",
  assisted: "Prêt en un clic",
  manual: "À finir sur le site",
};

export interface ApplicationData {
  id: string;
  job_title: string;
  company_name: string;
  status: string;
  match_score: number;
}

export interface CvAuditData {
  ats_score: number;
  score_label: string;
  strengths: string[];
  improvements: string[];
  optimized_headline: string;
  optimized_summary: string;
  suggested_skills: string[];
}

export interface MissionReportData {
  mission: {
    titre: string;
    statut: string;
    autonomie: string;
    quota_hebdomadaire: number;
    derniere_veille: string | null;
  };
  mandat: Record<string, string[]>;
  compteurs: { retenues: number; envoyees: number; entretiens: number };
  derniere_veille: {
    scanned?: number;
    kept?: number;
    discarded?: number;
    top_reasons?: Record<string, number>;
  };
  journal: { quand: string; quoi: string }[];
}

export type UiBlock =
  | { type: "jobs"; data: JobCardData[] }
  | { type: "applications"; data: { applications: ApplicationData[]; counts: Record<string, number> } }
  | { type: "cv_audit"; data: CvAuditData }
  | { type: "mission"; data: MissionReportData }
  | { type: "action"; action: string; data?: any };

export interface AliceResponse {
  reply: string;
  ui_blocks: UiBlock[];
  /** Conversation où l'échange a été enregistré, côté serveur. */
  conversation_id?: string | null;
}

// ── Client ─────────────────────────────────────────────────────────────────

export interface ChatTurn {
  sender: "user" | "alice";
  text: string;
}

export async function sendMessageToAlice(
  candidateId: string,
  message: string,
  history: ChatTurn[] = [],
  conversationId: string | null = null,
  jobId: string | null = null,
): Promise<AliceResponse> {
  const res = await apiFetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: candidateId,
      conversation_id: conversationId,
      job_id: jobId,
      message,
      // Le fil de la discussion seulement : les chiffres sont relus côté
      // serveur depuis la base à chaque tour.
      history: history.slice(-12),
    }),
  });

  if (res.status === 402) {
    // Limite de la formule : la fenêtre d'abonnement s'ouvre (apiFetch), Alice le dit.
    const body = await res.json().catch(() => null);
    return {
      reply: body?.detail?.message ?? "Tu as atteint la limite de ta formule pour aujourd'hui.",
      ui_blocks: [],
    };
  }

  if (!res.ok) {
    const errorText = await res.text().catch(() => "Unknown error");
    console.error("Alice API error:", res.status, errorText);
    return {
      reply: "Désolée, je n'ai pas pu traiter ta demande. Réessaie dans un instant.",
      ui_blocks: [],
    };
  }

  return res.json();
}

// ── Conversations sauvegardées ────────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
  /** Offre dont parle la conversation, s'il y en a une. */
  job_id?: string | null;
  company_name?: string | null;
  job_title?: string | null;
}

export interface StoredMessage {
  id: string;
  sender: "user" | "alice";
  text: string;
  ui_blocks: UiBlock[] | null;
  created_at: string;
}

const convBase = (candidateId: string) =>
  `${API_BASE_URL}/api/candidates/${candidateId}/conversations`;

export async function fetchConversations(candidateId: string): Promise<ConversationSummary[]> {
  try {
    const res = await apiFetch(convBase(candidateId));
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

export async function fetchConversationMessages(
  candidateId: string,
  conversationId: string,
): Promise<StoredMessage[]> {
  try {
    const res = await apiFetch(`${convBase(candidateId)}/${conversationId}/messages`);
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

export async function deleteConversation(candidateId: string, conversationId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`${convBase(candidateId)}/${conversationId}`, { method: "DELETE" });
    return res.ok;
  } catch {
    return false;
  }
}
