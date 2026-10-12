/**
 * Alice Community : la liste publique des alternances et des stages.
 *
 * Une offre choisie sur la liste est retenue ici le temps de l'inscription
 * ou de la connexion, puis ouverte dans le tableau de bord.
 */

export type CommunityKind = "alternance" | "stage";

export interface CommunityOffer {
  id: string;
  title: string;
  company: string;
  city: string;
  kind: CommunityKind;
  family: string;
  remote: string;
  published: string;
  is_new: boolean;
  /** Alice envoie la candidature elle-même (e-mail, API publique). */
  alice_sends: boolean;
  source: string;
  url: string;
}

export interface CommunityList {
  updated_at: string;
  total: number;
  new_count: number;
  offers: CommunityOffer[];
}

const TARGET_KEY = "alice_offre_cible";

export interface TargetOffer {
  id: string;
  title: string;
  company: string;
}

export function rememberTargetOffer(offer: TargetOffer): void {
  try {
    localStorage.setItem(TARGET_KEY, JSON.stringify({ ...offer, at: Date.now() }));
  } catch {
    /* navigation privée : l'offre ne suivra pas, l'inscription reste possible */
  }
}

/** L'offre retenue, une seule fois : la lire la retire. Oubliée après 7 jours. */
export function takeTargetOffer(): TargetOffer | null {
  try {
    const raw = localStorage.getItem(TARGET_KEY);
    if (!raw) return null;
    localStorage.removeItem(TARGET_KEY);
    const data = JSON.parse(raw);
    if (!data?.id || Date.now() - (data.at ?? 0) > 7 * 86_400_000) return null;
    return { id: String(data.id), title: String(data.title ?? ""), company: String(data.company ?? "") };
  } catch {
    return null;
  }
}

/** Où aller pour postuler : le tableau de bord si un profil existe, sinon l'inscription. */
export function applyDestination(): string {
  try {
    return localStorage.getItem("candidate_id") ? "/dashboard" : "/";
  } catch {
    return "/";
  }
}
