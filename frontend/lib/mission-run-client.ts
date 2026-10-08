/**
 * Missions bornées dans le temps — lancement, suivi, compte rendu.
 *
 * À distinguer du mandat permanent (`mission-client.ts`) : ici il s'agit d'une
 * exécution avec un début, une fin et un rapport.
 */

import { API_BASE_URL } from "./config";
import type { MissionEventKind } from "./mission-client";
import { apiFetch } from "./api";

export type RunStatus = "preparing" | "running" | "completed" | "interrupted";
export type RunStep = "scan" | "qualify" | "match" | "prepare" | "apply";
export type RunObjective = "search" | "prepare" | "apply";

export interface RunEvent {
  id: string;
  kind: MissionEventKind;
  summary: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface MissionRun {
  id: string;
  title: string;
  objective: RunObjective;
  duration_minutes: number;
  status: RunStatus;
  current_step: RunStep | null;
  allowed_actions: { send?: boolean } | null;
  stats: {
    scanned?: number;
    qualified?: number;
    shortlisted?: number;
    letters?: number;
    packs?: number;
    sent?: number;
    simulated?: number;
    blocked?: number;
    failed?: number;
    awaiting_approval?: number;
  } | null;
  report: string | null;
  started_at: string | null;
  ends_at: string | null;
  finished_at: string | null;
  created_at: string;
  seconds_remaining: number;
  /** 0 à 1 — part du temps écoulée. */
  progress: number;
  events: RunEvent[];
}

export const STEP_LABELS: Record<RunStep, string> = {
  scan: "Je reprends tes offres",
  qualify: "Je lis les annonces",
  match: "Je reprends tes offres retenues",
  prepare: "Je prépare les dossiers",
  apply: "J'envoie ce que tu m'as autorisé",
};

export const COUNTS = [3, 5, 10];

const base = (candidateId: string) =>
  `${API_BASE_URL}/api/candidates/${candidateId}/mission/runs`;

export async function startRun(
  candidateId: string,
  payload: {
    title: string;
    objective: RunObjective;
    count: number;
    /** Candidatures spontanées à préparer en plus des offres (0 à 5). */
    spontaneous?: number;
    allowed_actions: { send: boolean };
  },
): Promise<MissionRun | null> {
  try {
    const res = await apiFetch(base(candidateId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchCurrentRun(candidateId: string): Promise<MissionRun | null> {
  try {
    const res = await apiFetch(`${base(candidateId)}/current`);
    if (!res.ok) return null;
    const data = await res.json();
    return data ?? null;
  } catch {
    return null;
  }
}

export async function stopRun(
  candidateId: string,
  runId: string,
): Promise<MissionRun | null> {
  try {
    const res = await apiFetch(`${base(candidateId)}/${runId}/stop`, { method: "POST" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
