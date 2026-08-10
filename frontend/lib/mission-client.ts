/**
 * Client Mission — le mandat confié à Alice et son journal.
 */

import { apiFetch } from "./api";

export type AutonomyLevel = "propose" | "auto_above" | "full";
export type MissionStatus = "active" | "paused" | "archived";

export type MissionEventKind =
  | "mission_created" | "mandate_changed" | "autonomy_changed" | "status_changed"
  | "scan" | "shortlist" | "discard" | "cv_adapted" | "letter_written"
  | "applied" | "awaiting_approval" | "reply" | "error";

export interface MissionEvent {
  id: string;
  kind: MissionEventKind;
  summary: string;
  payload?: {
    scanned?: number;
    kept?: number;
    discarded?: number;
    top_reasons?: Record<string, number>;
    job_id?: string;
    score?: number;
    company?: string;
  } | null;
  is_read: boolean;
  created_at: string;
}

export interface MissionCriteria {
  languages: string[];
  countries: string[];
  job_families: string[];
  contract_types: string[];
  remote_policies: string[];
  locations: string[];
  salary_min: number | null;
}

export interface MissionStats {
  shortlisted: number;
  applied: number;
  interviews: number;
  scanned_last_run: number;
  applied_this_week: number;
  quota_remaining: number;
}

export interface Mission {
  id: string;
  candidate_id: string;
  title: string;
  status: MissionStatus;
  autonomy: AutonomyLevel;
  auto_apply_min_score: number;
  weekly_quota: number;
  last_run_at: string | null;
  criteria: MissionCriteria;
  criteria_is_explicit: boolean;
  stats: MissionStats;
  recent_events: MissionEvent[];
}

const base = (candidateId: string) => `/api/candidates/${candidateId}/mission`;

export async function fetchMission(candidateId: string): Promise<Mission | null> {
  try {
    const res = await apiFetch(base(candidateId));
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function updateMission(
  candidateId: string,
  patch: Partial<Pick<Mission, "title" | "status" | "autonomy" | "auto_apply_min_score" | "weekly_quota">>,
): Promise<boolean> {
  try {
    const res = await apiFetch(base(candidateId), {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function fetchJournal(
  candidateId: string,
  limit = 50,
): Promise<MissionEvent[]> {
  try {
    const res = await apiFetch(`${base(candidateId)}/journal?limit=${limit}`);
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}
