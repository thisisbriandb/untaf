/**
 * Candidature depuis le Canvas.
 *
 * L'envoi arrive en flux : chaque étape est annoncée avant d'être exécutée,
 * puis confirmée avec son résultat réel.
 */

import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";

export type RequirementStatus = "satisfied" | "generate" | "missing";

export interface Requirement {
  key: string;
  label: string;
  status: RequirementStatus;
  detail: string;
}

export type Complexity = "simple" | "medium" | "complex" | "impossible" | "unknown";

export interface ApplyPlan {
  job_id: string;
  job_title: string;
  company_name: string;
  channel: string;
  destination: string | null;
  can_apply: boolean;
  blocked_reason: string | null;
  /** Évalué par le service de faisabilité, côté serveur. */
  complexity: Complexity;
  summary: string;
  fallback_url: string | null;
  requirements: Requirement[];
}

export const COMPLEXITY_LABEL: Record<Complexity, string> = {
  simple: "Automatisable",
  medium: "Presque automatisable",
  complex: "Formulaire à remplir",
  impossible: "À faire toi-même",
  unknown: "À vérifier",
};

export type ApplyEvent =
  | { type: "step"; key: string; label: string; status: "running" | "done"; detail?: string }
  | { type: "blocked"; message: string; missing: { label: string; detail: string }[]; pack_ready?: boolean; has_resume?: boolean }
  | { type: "awaiting"; dispatch_id: string; message: string; destination?: string }
  | {
      type: "unsupported";
      complexity: Complexity;
      message: string;
      reason: string | null;
      fallback_url: string | null;
      /** Le CV adapté et la lettre sont prêts, même sans envoi automatique. */
      pack_ready?: boolean;
      /** Le CV a pu être produit et fait partie du dossier. */
      has_resume?: boolean;
    }
  | { type: "done"; dispatch_id: string | null; status: string; real: boolean; message: string }
  | { type: "error"; message: string };

/**
 * Ce qu'il reste après une tentative — réussie ou non.
 *
 * Les pièces sont celles qui ont réellement été assemblées, pas une
 * régénération : un échec ne doit pas obliger à tout refaire.
 */
export interface ApplyOutcome {
  dispatch_id: string;
  status: string;
  /** Vrai uniquement si quelque chose est parti pour de bon. */
  sent: boolean;
  headline: string;
  detail: string | null;
  job_url: string | null;
  has_resume: boolean;
  has_letter: boolean;
  resume_name: string | null;
  steps: string[];
  /** Brouillon d'e-mail pré-rempli, absent quand l'envoi a abouti. */
  mailto: string | null;
}

const dispatchBase = (candidateId: string, dispatchId: string) =>
  `${API_BASE_URL}/api/candidates/${candidateId}/apply/dispatches/${dispatchId}`;

export async function fetchApplyOutcome(
  candidateId: string,
  dispatchId: string,
): Promise<ApplyOutcome | null> {
  try {
    const res = await apiFetch(dispatchBase(candidateId, dispatchId));
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export function dispatchResumeUrl(candidateId: string, dispatchId: string): string {
  return `${dispatchBase(candidateId, dispatchId)}/resume`;
}

export function dispatchLetterUrl(candidateId: string, dispatchId: string): string {
  return `${dispatchBase(candidateId, dispatchId)}/letter`;
}

export async function fetchApplyPlan(
  candidateId: string,
  jobId: string,
): Promise<ApplyPlan | null> {
  try {
    const res = await apiFetch(
      `${API_BASE_URL}/api/candidates/${candidateId}/apply/${jobId}/plan`,
    );
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/**
 * Lance la candidature et rappelle `onEvent` à chaque étape.
 *
 * On lit le flux à la main plutôt qu'avec EventSource : celui-ci ne sait pas
 * faire de POST, et l'envoi ne doit pas être déclenchable par un simple GET.
 */
export async function streamApply(
  candidateId: string,
  jobId: string,
  onEvent: (event: ApplyEvent) => void,
): Promise<void> {
  const res = await apiFetch(
    `${API_BASE_URL}/api/candidates/${candidateId}/apply/${jobId}/stream`,
    { method: "POST" },
  );

  if (!res.ok || !res.body) {
    onEvent({ type: "error", message: "La candidature n'a pas pu démarrer." });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Les messages SSE sont séparés par une ligne vide.
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      let eventName = "message";
      const dataLines: string[] = [];

      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }

      if (!dataLines.length) continue;
      try {
        onEvent({ type: eventName, ...JSON.parse(dataLines.join("")) } as ApplyEvent);
      } catch {
        // Un fragment illisible ne doit pas interrompre le flux.
      }
    }
  }
}

// ── Préférence « ne plus afficher » ────────────────────────────────────────

const SKIP_KEY = "apply_confirm_skipped";

export function shouldConfirmApply(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) !== "1";
  } catch {
    return true;
  }
}

export function rememberSkipConfirm(): void {
  try {
    localStorage.setItem(SKIP_KEY, "1");
  } catch {
    // Mode privé : on redemandera, ce n'est pas grave.
  }
}

/** Le candidat a fini la candidature lui-même : elle entre dans le suivi. */
export async function markApplied(candidateId: string, jobId: string): Promise<boolean> {
  try {
    const res = await apiFetch(
      `${API_BASE_URL}/api/candidates/${candidateId}/apply/${jobId}/mark-applied`,
      { method: "POST" },
    );
    return res.ok;
  } catch {
    return false;
  }
}
