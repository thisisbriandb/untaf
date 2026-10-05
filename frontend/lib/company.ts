/**
 * Le nom d'un employeur, tel qu'on l'affiche.
 *
 * France Travail publie beaucoup d'offres anonymes (« Employeur non
 * précisé ») et des raisons sociales en capitales. Les afficher telles
 * quelles donne une liste de doublons illisibles : l'anonyme s'efface au
 * profit du poste, les capitales redeviennent un nom.
 */

const ANONYMOUS = /^(employeur|entreprise)\s+non\s+pr[ée]cis[ée]e?$/i;
const SMALL = new Set(["de", "du", "des", "la", "le", "les", "et", "en", "à", "au", "aux", "d", "l"]);

export function isAnonymous(name?: string | null): boolean {
  return !name || !name.trim() || ANONYMOUS.test(name.trim());
}

/** Le nom lisible, ou null quand l'employeur n'est pas communiqué. */
export function companyOf(name?: string | null): string | null {
  if (isAnonymous(name)) return null;
  const n = name!.trim();
  const letters = n.replace(/[^\p{L}]/gu, "");
  if (letters !== letters.toUpperCase()) return n;
  // Un sigle seul (SNCF, EDF) reste un sigle.
  if (!/\s/.test(n) && letters.length <= 5) return n;
  return n
    .toLowerCase()
    .split(/(\s+|-|')/)
    .map((w, i) => {
      if (!/\p{L}/u.test(w)) return w;
      if (i > 0 && SMALL.has(w)) return w;
      // Formes juridiques : en capitales.
      if (["sas", "sarl", "sa", "eurl", "sasu", "sci"].includes(w)) return w.toUpperCase();
      return w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join("");
}

/** « chez Acme », ou rien quand l'employeur est anonyme. */
export function chez(name?: string | null): string {
  const c = companyOf(name);
  return c ? ` chez ${c}` : "";
}
