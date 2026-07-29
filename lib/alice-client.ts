/**
 * Alice API Client — talks to POST /api/chat on the backend.
 */

import { API_BASE_URL } from "./config";

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
}

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

export type UiBlock =
  | { type: "jobs"; data: JobCardData[] }
  | { type: "applications"; data: { applications: ApplicationData[]; counts: Record<string, number> } }
  | { type: "cv_audit"; data: CvAuditData }
  | { type: "action"; action: string; data?: any };

export interface AliceResponse {
  reply: string;
  ui_blocks: UiBlock[];
}

// ── Client ─────────────────────────────────────────────────────────────────

export async function sendMessageToAlice(
  candidateId: string,
  message: string,
): Promise<AliceResponse> {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: candidateId,
      message,
    }),
  });

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
