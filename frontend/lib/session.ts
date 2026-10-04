/**
 * Où aller une fois connecté : le serveur dit quel profil appartient au
 * compte. Avec un profil, le tableau de bord ; sans, l'onboarding.
 */

import { fetchMe } from "./api";

export const CANDIDATE_KEYS = ["candidate_id", "candidate_email", "candidate_name"] as const;

export function clearLocalCandidate(): void {
  for (const key of CANDIDATE_KEYS) localStorage.removeItem(key);
}

/** Destination après connexion, et mémorisation du profil pour l'interface. */
export async function destinationAfterSignIn(next?: string | null): Promise<string> {
  const me = await fetchMe();
  if (!me?.candidate_id) {
    clearLocalCandidate();
    return "/";
  }
  localStorage.setItem("candidate_id", me.candidate_id);
  if (me.email) localStorage.setItem("candidate_email", me.email);
  // Seules les destinations internes sont suivies : un `next` externe
  // ferait de la page de connexion un tremplin vers n'importe quel site.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}
