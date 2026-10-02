/**
 * Offres collées par le candidat, et documents adaptés à une offre.
 *
 * Le CV et la lettre adaptés sont rangés sur la candidature côté serveur :
 * ce sont eux qui partent à l'envoi, et le CV du profil reste intact.
 */

import { API_BASE_URL } from "./config";
import type { JobCardData } from "./alice-client";
import type { CoverLetter } from "./letter-client";

export interface ImportedJob extends JobCardData {
  /** Motifs pour lesquels l'offre sort du mandat, s'il y en a. */
  rejections: string[];
}

export interface TailoredCv {
  headline: string;
  summary: string;
  tailored_to_job: boolean;
  source: string;
}

export interface TailoredDocuments {
  cv: TailoredCv;
  letter: CoverLetter;
}

const base = (candidateId: string) => `${API_BASE_URL}/api/candidates/${candidateId}/apply`;

/** Longueur minimale acceptée par le serveur pour un texte d'annonce. */
export const MIN_OFFER_LENGTH = 80;

export async function importJob(
  candidateId: string,
  text: string,
  url?: string,
): Promise<ImportedJob | null> {
  try {
    const res = await fetch(`${base(candidateId)}/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, url: url || null }),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function tailorDocuments(
  candidateId: string,
  jobId: string,
): Promise<TailoredDocuments | null> {
  try {
    const res = await fetch(`${base(candidateId)}/${jobId}/tailor`, { method: "POST" });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

/**
 * Le dossier complet en ZIP : CV, lettre, annonce. Les pièces envoyées si la
 * candidature est partie, sinon celles qui partiraient maintenant.
 */
export function packUrl(candidateId: string, jobId: string): string {
  return `${base(candidateId)}/${jobId}/pack`;
}

/** Le CV qui partira pour cette offre : adapté s'il l'a été, général sinon. */
export function tailoredCvUrl(candidateId: string, jobId: string): string {
  return `${base(candidateId)}/${jobId}/cv`;
}
