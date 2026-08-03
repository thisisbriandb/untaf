/**
 * Lettre de motivation — structure du document et signature réutilisable.
 */

import { API_BASE_URL } from "./config";

/**
 * Les blocs conventionnels sont des champs distincts, pas du Markdown : c'est
 * ce qui permet de les mettre en page correctement et de les réutiliser d'une
 * lettre à l'autre. Seul `body` est rédigé, et donc éditable, en Markdown.
 */
export interface CoverLetter {
  sender_name: string;
  sender_contact: string[];
  recipient_name: string;
  recipient_company: string;
  place: string | null;
  date: string;
  subject: string;
  salutation: string;
  body: string;
  closing: string;
  signature_name: string;
  signature_image: string | null;
  grounded_on_posting: boolean;
  grounded_on_experiences: boolean;
  source: string;
}

export function emptyLetter(companyName = "", jobTitle = ""): CoverLetter {
  return {
    sender_name: "",
    sender_contact: [],
    recipient_name: "Service Recrutement",
    recipient_company: companyName,
    place: null,
    date: new Date().toLocaleDateString("fr-FR", {
      day: "numeric", month: "long", year: "numeric",
    }),
    subject: jobTitle ? `Candidature au poste de ${jobTitle}` : "Candidature",
    salutation: "Madame, Monsieur,",
    body: "_Demande à Alice de rédiger cette lettre, ou écris-la ici._",
    closing:
      "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
    signature_name: "",
    signature_image: null,
    grounded_on_posting: false,
    grounded_on_experiences: false,
    source: "empty",
  };
}

// ── Téléchargement ─────────────────────────────────────────────────────────

/**
 * Le PDF est compilé par le serveur (Typst) et téléchargé directement.
 *
 * L'ancienne version ouvrait la boîte d'impression du navigateur : rendu
 * différent d'un navigateur à l'autre, et une étape de plus pour l'utilisateur.
 */
export async function downloadLetterPdf(letter: CoverLetter): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/candidates/download-cover-letter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(letter),
    });
    if (!res.ok) return false;

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Lettre_${(letter.recipient_company || "candidature").replace(/\s+/g, "_")}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}

// ── Signature ──────────────────────────────────────────────────────────────

export async function fetchSignature(candidateId: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/candidates/${candidateId}/signature`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.image ?? null;
  } catch {
    return null;
  }
}

export async function saveSignature(
  candidateId: string,
  dataUrl: string,
): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/candidates/${candidateId}/signature`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function deleteSignature(candidateId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/candidates/${candidateId}/signature`, {
      method: "DELETE",
    });
    return res.ok;
  } catch {
    return false;
  }
}
