/**
 * Missions bornées dans le temps — lancement, suivi, compte rendu.
 *
 * À distinguer du mandat permanent (`mission-client.ts`) : ici il s'agit d'une
 * exécution avec un début, une fin et un rapport.
 */

import { API_BASE_URL } from "./config";
import type { MissionEventKind } from "./mission-client";

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
  scan: "Je relève les offres",
  qualify: "Je lis les annonces",
  match: "Je compare à ton mandat",
  prepare: "Je prépare les packs : CV adapté et lettre",
  apply: "J'envoie ce que tu m'as autorisé",
};

export const OBJECTIVES: { id: RunObjective; label: string; detail: string }[] = [
  { id: "search", label: "Repérer des offres", detail: "Je cherche et je te présente ce qui tient la route." },
  { id: "prepare", label: "Préparer les candidatures", detail: "J'adapte ton CV et je rédige la lettre pour chaque offre retenue." },
  { id: "apply", label: "Aller jusqu'à l'envoi", detail: "Je prépare tout et j'envoie si tu m'y autorises." },
];

export const DURATIONS = [
  { minutes: 30, label: "30 minutes" },
  { minutes: 120, label: "2 heures" },
  { minutes: 240, label: "Une demi-journée" },
];

const base = (candidateId: string) =>
  `${API_BASE_URL}/api/candidates/${candidateId}/mission/runs`;

export async function startRun(
  candidateId: string,
  payload: {
    title: string;
    objective: RunObjective;
    duration_minutes: number;
    allowed_actions: { send: boolean };
  },
): Promise<MissionRun | null> {
  try {
    const res = await fetch(base(candidateId), {
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
    const res = await fetch(`${base(candidateId)}/current`);
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
    const res = await fetch(`${base(candidateId)}/${runId}/stop`, { method: "POST" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export function formatRemaining(seconds: number): string {
  if (seconds <= 0) return "terminé";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")}`;
  if (m > 0) return `${m} min ${String(s).padStart(2, "0")}`;
  return `${s} s`;
}
