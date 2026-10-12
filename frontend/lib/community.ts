/**
 * Alice Community : la liste publique des alternances et des stages.
 *
 * Une offre choisie sur la liste est retenue ici le temps de l'inscription
 * ou de la connexion, puis ouverte dans le tableau de bord.
 */

import { API_BASE_URL } from "./config";

export type CommunityKind = "alternance" | "stage" | "emploi";

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
  /** Mention exigée par l'agrégateur qui relaie l'offre, avec son lien. */
  attribution_label?: string | null;
  attribution_url?: string | null;
  /** La même offre publiée dans d'autres villes. */
  other_cities?: number;
  /** Recrutement par une école ou un CFA pour une entreprise partenaire. */
  via_school?: boolean;
}

export interface CommunityList {
  updated_at: string;
  total: number;
  new_count: number;
  offers: CommunityOffer[];
}

/** Une page de résultats, avec de quoi afficher les filtres. */
export interface CommunityPage {
  updated_at: string;
  kind: CommunityKind;
  /** Offres de ce type, avant filtres. */
  total: number;
  new_count: number;
  alice_count: number;
  families: { name: string; count: number }[];
  /** Offres qui répondent aux filtres. */
  matched: number;
  page: number;
  per_page: number;
  offers: CommunityOffer[];
}

export interface CommunityFilters {
  kind: CommunityKind;
  q: string;
  city: string;
  family: string | null;
  alice: boolean;
  fresh: boolean;
  direct: boolean;
}

export const DEFAULT_FILTERS: CommunityFilters = {
  kind: "alternance",
  q: "",
  city: "",
  family: null,
  alice: false,
  fresh: false,
  direct: false,
};

export function searchUrl(f: CommunityFilters, page = 1): string {
  const p = new URLSearchParams({ kind: f.kind, page: String(page), per_page: "50" });
  if (f.q.trim()) p.set("q", f.q.trim());
  if (f.city.trim()) p.set("city", f.city.trim());
  if (f.family) p.set("family", f.family);
  if (f.alice) p.set("alice", "true");
  if (f.fresh) p.set("new", "true");
  if (f.direct) p.set("direct", "true");
  return `${API_BASE_URL}/api/community/recherche?${p}`;
}

export async function fetchCommunityPage(f: CommunityFilters, page = 1): Promise<CommunityPage | null> {
  try {
    const res = await fetch(searchUrl(f, page));
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export async function fetchCommunityOffer(id: string): Promise<CommunityOffer | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/api/community/offres/${encodeURIComponent(id)}`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
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
