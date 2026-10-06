/**
 * CV profile store — the single source of truth for the CV the user edits
 * inside the Canvas.
 *
 * Persistence:
 *   - identity + matching fields   → backend (`PUT /api/candidates/{id}`)
 *   - parcours (expériences, formation, langues) → backend (`cv_content`),
 *     qui fait foi sur tous les appareils
 *   - photo et mise en page        → localStorage, keyed by candidate id
 * A save always writes both.
 */

import { API_BASE_URL } from "./config";
import type {
  EducationEntry,
  ExperienceEntry,
  LanguageEntry,
} from "@/app/onboarding/types";
import { apiFetch } from "./api";

export interface CvProfile {
  fullName: string;
  email: string;
  phone: string;
  linkedinUrl: string;
  headline: string;
  summary: string;
  photoUrl: string | null;
  showPhotoOnCv: boolean;
  experiences: ExperienceEntry[];
  education: EducationEntry[];
  skills: string[];
  languages: LanguageEntry[];
  experienceYears: number;
  templateId: string;
  colorHex: string;
}

export const EMPTY_CV_PROFILE: CvProfile = {
  fullName: "",
  email: "",
  phone: "",
  linkedinUrl: "",
  headline: "",
  summary: "",
  photoUrl: null,
  showPhotoOnCv: false,
  experiences: [],
  education: [],
  skills: [],
  languages: [],
  experienceYears: 0,
  templateId: "classic",
  colorHex: "#006045",
};

const storageKey = (candidateId: string) => `cv_profile:${candidateId}`;

// ── Local half ─────────────────────────────────────────────────────────────

export function readLocalCvProfile(candidateId: string): Partial<CvProfile> | null {
  try {
    const raw = localStorage.getItem(storageKey(candidateId));
    return raw ? (JSON.parse(raw) as Partial<CvProfile>) : null;
  } catch {
    return null;
  }
}

export function writeLocalCvProfile(candidateId: string, profile: CvProfile): void {
  try {
    localStorage.setItem(storageKey(candidateId), JSON.stringify(profile));
  } catch {
    // Quota or private mode — the backend half still went through.
  }
}

// ── Backend half ───────────────────────────────────────────────────────────

/**
 * Load the CV the user last worked on: backend record as the base, local draft
 * layered on top (it is always newer, since every save writes both).
 */
/** Les entrées venues du serveur (relecture du CV) n'ont pas toujours d'id. */
function withIds<T extends { id?: string }>(entries: unknown): T[] {
  if (!Array.isArray(entries)) return [];
  return entries.map((e, i) => ({ ...(e as T), id: (e as T)?.id || `srv-${i}-${Date.now()}` }));
}

export async function loadCvProfile(candidateId: string): Promise<CvProfile> {
  let remote: Partial<CvProfile> = {};

  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}`);
    if (res.ok) {
      const c = await res.json();
      remote = {
        fullName: c.full_name ?? "",
        email: c.email ?? "",
        phone: c.phone ?? "",
        linkedinUrl: c.linkedin_url ?? "",
        headline: c.headline ?? "",
        skills: Array.isArray(c.skills) ? c.skills : [],
        experienceYears: c.experience_years ?? 0,
      };
      // Le parcours détaillé vit côté serveur : c'est lui qui fait foi, sur
      // tous les appareils. Le brouillon local ne comble que ce qui manque.
      const cv = c.cv_content ?? {};
      if (cv.summary) remote.summary = cv.summary;
      if (cv.experiences?.length) remote.experiences = withIds<ExperienceEntry>(cv.experiences);
      if (cv.education?.length) remote.education = withIds<EducationEntry>(cv.education);
      if (cv.languages?.length) remote.languages = withIds<LanguageEntry>(cv.languages);
    }
  } catch {
    // Offline / backend down — fall back to whatever is cached locally.
  }

  const local = readLocalCvProfile(candidateId) ?? {};
  const merged = { ...EMPTY_CV_PROFILE, ...local, ...remote };
  // Mise en page et photo ne vivent que localement : on les garde.
  for (const key of ["photoUrl", "showPhotoOnCv", "templateId", "colorHex"] as const) {
    if (local[key] !== undefined) (merged as Record<string, unknown>)[key] = local[key];
  }
  // Un brouillon local plus riche que le serveur (saisie hors ligne) n'est pas perdu.
  for (const key of ["experiences", "education", "languages"] as const) {
    if (!(remote[key]?.length) && local[key]?.length) merged[key] = local[key] as never;
  }
  return merged;
}

/**
 * Persist a CV. Returns true when the backend half succeeded; the local half
 * is always written so an offline edit is never lost.
 */
export async function saveCvProfile(
  candidateId: string,
  profile: CvProfile,
): Promise<boolean> {
  writeLocalCvProfile(candidateId, profile);

  // Le parcours détaillé part aussi au serveur : Alice rédige côté backend et
  // ne peut argumenter à partir d'expériences restées dans le navigateur.
  try {
    await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/cv-content`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary: profile.summary,
        experiences: profile.experiences,
        education: profile.education,
        languages: profile.languages,
      }),
    });
  } catch {
    // Non bloquant : la copie locale reste la source de l'éditeur.
  }

  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: profile.fullName,
        email: profile.email,
        phone: profile.phone || null,
        linkedin_url: profile.linkedinUrl || null,
        headline: profile.headline || null,
        skills: profile.skills,
        experience_years: profile.experienceYears || null,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Présentation : original ou modèle ──────────────────────────────────────

export type CvMode = "original" | "template";

export interface CvDesign {
  mode: CvMode;
  template_id: string | null;
  color_hex: string | null;
  show_photo: boolean;
  has_original: boolean;
  original_filename: string | null;
  /** False tant que le candidat n'a rien choisi : on est sur le défaut. */
  is_explicit: boolean;
  /** Une photo est enregistrée côté serveur. */
  has_photo: boolean;
  /** Le modèle réellement utilisé pour les CV adaptés (le classique à défaut). */
  effective_template_id: string;
}

export function resumeUrl(candidateId: string): string {
  return `${API_BASE_URL}/api/candidates/${candidateId}/resume`;
}

export async function fetchCvDesign(candidateId: string): Promise<CvDesign | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/cv-design`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function saveCvDesign(
  candidateId: string,
  patch: Partial<Pick<CvDesign, "mode" | "template_id" | "color_hex" | "show_photo">>,
): Promise<CvDesign | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/${candidateId}/cv-design`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// ── Photo ──────────────────────────────────────────────────────────────────

export function photoUrl(candidateId: string): string {
  return `${API_BASE_URL}/api/candidates/${candidateId}/photo`;
}

/**
 * Réduit la photo dans le navigateur (600 px max, JPEG) : légère à stocker et
 * à joindre, et assez nette pour un CV. Renvoie un data URL.
 */
export function shrinkPhoto(file: File, max = 600): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const src = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("canvas"));
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(src);
      resolve(canvas.toDataURL("image/jpeg", 0.86));
    };
    img.onerror = () => {
      URL.revokeObjectURL(src);
      reject(new Error("image illisible"));
    };
    img.src = src;
  });
}

/** Enregistre la photo côté serveur ; elle figure ensuite sur les CV. */
export async function uploadPhoto(candidateId: string, dataUrl: string): Promise<boolean> {
  try {
    const blob = await (await fetch(dataUrl)).blob();
    const form = new FormData();
    form.append("file", blob, "photo.jpg");
    const res = await apiFetch(photoUrl(candidateId), { method: "PUT", body: form });
    return res.ok;
  } catch {
    return false;
  }
}

export async function deletePhoto(candidateId: string): Promise<boolean> {
  try {
    return (await apiFetch(photoUrl(candidateId), { method: "DELETE" })).ok;
  } catch {
    return false;
  }
}

/** La photo enregistrée, en data URL (pour l'aperçu local), ou null. */
export async function fetchPhotoDataUrl(candidateId: string): Promise<string | null> {
  try {
    const res = await apiFetch(photoUrl(candidateId));
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve((reader.result as string) ?? null);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

// ── Rédaction par Alice ────────────────────────────────────────────────────

export interface CvContent {
  headline: string;
  summary: string;
  differentiators: string[];
  /** "fallback" = rédigé sans LLM ; "llm_generic" = retombé dans le passe-partout. */
  source: "llm" | "llm_generic" | "fallback";
  /** Vrai quand la rédaction a visé une offre précise. */
  tailored_to_job: boolean;
}

/**
 * Fait rédiger l'accroche et la synthèse à partir du parcours COMPLET.
 * Les expériences ne vivent pas en base : c'est le client qui les fournit.
 */
export interface JobContext {
  job_title?: string;
  company_name?: string;
  job_excerpt?: string;
  job_skills?: string[];
}

export async function writeCvContent(
  profile: CvProfile,
  targetRole?: string,
  job?: JobContext,
): Promise<CvContent | null> {
  try {
    const res = await apiFetch(`${API_BASE_URL}/api/candidates/cv-content`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: profile.fullName,
        headline: profile.headline,
        summary: profile.summary,
        skills: profile.skills,
        experience_years: profile.experienceYears,
        experiences: profile.experiences,
        education: profile.education,
        languages: profile.languages,
        target_role: targetRole || null,
        ...(job ?? {}),
      }),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// ── PDF export ─────────────────────────────────────────────────────────────

export function toCvRenderPayload(profile: CvProfile) {
  return {
    template_id: profile.templateId,
    color_hex: profile.colorHex,
    show_photo: profile.showPhotoOnCv,
    photo_url: profile.photoUrl,
    full_name: profile.fullName || "Candidat",
    email: profile.email || "contact@email.com",
    phone: profile.phone,
    headline: profile.headline,
    summary: profile.summary,
    skills: profile.skills,
    experience_years: profile.experienceYears,
    linkedin_url: profile.linkedinUrl,
    location: "France",
    experiences: profile.experiences,
    education: profile.education,
    languages: profile.languages,
  };
}

export async function downloadCvPdf(profile: CvProfile): Promise<void> {
  const res = await apiFetch(`${API_BASE_URL}/api/candidates/download-cv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toCvRenderPayload(profile)),
  });

  if (!res.ok) throw new Error("Compilation PDF impossible");

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `CV_${(profile.fullName || "candidat").replace(/\s+/g, "_")}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
