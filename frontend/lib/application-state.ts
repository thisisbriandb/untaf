"use client";

/**
 * L'état d'une candidature, partagé par toute l'interface.
 *
 * Une offre n'a qu'un dossier : s'il est prêt, la fiche de l'offre, le panneau
 * de candidature et la liste le savent tous en même temps. Après toute action
 * qui le change (préparation, envoi, « j'ai postulé »), `invalidateApplication`
 * prévient chaque composant abonné, qui relit l'état sur le serveur.
 */

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "./config";
import { apiFetch } from "./api";
import type { CoverLetter } from "./letter-client";
import type { ApplyMode } from "./alice-client";

export type ApplicationStage =
  | "to_prepare" | "ready" | "awaiting" | "simulated" | "manual"
  | "applied" | "interview" | "offer" | "rejected" | "closed";

export interface ApplicationState {
  application_id: string | null;
  stage: ApplicationStage;
  apply_mode: ApplyMode;
  pack_ready: boolean;
  pack_ready_at: string | null;
  headline: string | null;
  letter: CoverLetter | null;
  applied_at: string | null;
  dispatch_status: string | null;
  dispatch_id: string | null;
  changes: CvChanges | null;
}

/** Avant / après de l'adaptation, pour relire avant d'envoyer. */
export interface CvChanges {
  headline_before: string | null;
  headline_after: string | null;
  summary_before: string | null;
  summary_after: string | null;
  strengths: string[];
  skills_first: string[];
  experiences: { title: string; company: string; before: string[]; after: string[] }[];
}

/** Enregistre la lettre relue : c'est elle qui partira. */
export async function saveLetter(
  candidateId: string,
  jobId: string,
  letter: CoverLetter,
): Promise<ApplicationState | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/apply/${jobId}/letter`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(letter),
    });
    if (!res.ok) return null;
    const state = (await res.json()) as ApplicationState;
    invalidateApplication(jobId);
    return state;
  } catch {
    return null;
  }
}

const EVENT = "untaf:application-changed";
const cache = new Map<string, ApplicationState>();

/** Déjà envoyée (ou au-delà) : plus rien à préparer ni à envoyer. */
export const isSent = (s: ApplicationState | null) =>
  !!s && ["applied", "interview", "offer", "rejected", "closed"].includes(s.stage);

export async function fetchApplicationState(
  candidateId: string,
  jobId: string,
): Promise<ApplicationState | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/apply/${jobId}/state`);
    if (!res.ok) return null;
    const state = (await res.json()) as ApplicationState;
    cache.set(jobId, state);
    return state;
  } catch {
    return null;
  }
}

/** À appeler après tout ce qui change un dossier. Sans argument : toutes les offres. */
export function invalidateApplication(jobId?: string) {
  if (jobId) cache.delete(jobId);
  else cache.clear();
  window.dispatchEvent(new CustomEvent(EVENT, { detail: jobId ?? null }));
}

export function useApplicationState(candidateId: string | null, jobId: string) {
  const [state, setState] = useState<ApplicationState | null>(() => cache.get(jobId) ?? null);

  const refresh = useCallback(async () => {
    if (!candidateId) return;
    const fresh = await fetchApplicationState(candidateId, jobId);
    if (fresh) setState(fresh);
  }, [candidateId, jobId]);

  useEffect(() => {
    let alive = true;
    if (candidateId) {
      void fetchApplicationState(candidateId, jobId).then((fresh) => {
        if (alive) setState(fresh ?? cache.get(jobId) ?? null);
      });
    }
    const onChange = (e: Event) => {
      const target = (e as CustomEvent<string | null>).detail;
      if (!target || target === jobId) void refresh();
    };
    window.addEventListener(EVENT, onChange);
    return () => {
      alive = false;
      window.removeEventListener(EVENT, onChange);
    };
  }, [candidateId, jobId, refresh]);

  return { state, refresh };
}
