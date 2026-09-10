"""
Notation du moteur, étage par étage.

Un taux global ne dit pas quoi corriger. « 70 % de réussite » peut vouloir dire
que l'extracteur est aveugle, que le classifieur se trompe, ou que le profil
candidat est vide — trois chantiers sans rapport. La note se décompose donc
selon le chemin réel d'un champ :

    déclaré → vu → classé → résolu → rempli → vérifié

Les deux derniers étages exigent une page vivante : un instantané ne réagit pas
au clavier. Ils ne sont pas mesurés ici, et leur absence est dite plutôt que
comblée par une estimation.

Le premier étage — `déclaré` — n'existe que là où l'ATS publie un corrigé. Il
porte pourtant la mesure la plus importante, parce qu'un champ jamais vu ne
peut apparaître dans aucun rapport d'échec : c'est le seul endroit d'où la
cécité silencieuse est visible.

Deux profils de référence servent à séparer ce que le moteur ne sait pas lire
de ce que la base ne sait pas fournir. La différence entre les deux chiffre
exactement ce que coûte l'absence du socle candidat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.application.field_classifier import Semantic

#: Ce que le modèle `Candidate` sait fournir aujourd'hui, colonne par colonne.
PROFIL_ACTUEL: set[Semantic] = {
    Semantic.FIRST_NAME, Semantic.LAST_NAME, Semantic.FULL_NAME,
    Semantic.EMAIL, Semantic.PHONE, Semantic.RESUME, Semantic.COVER_LETTER,
    Semantic.LINKEDIN, Semantic.GITHUB, Semantic.PORTFOLIO, Semantic.LOCATION,
}

#: Ce qu'il fournirait une fois le socle candidat collecté. L'écart avec le
#: profil actuel est la mesure du chantier « socle ».
SOCLE_MANQUANT: set[Semantic] = {
    Semantic.COUNTRY, Semantic.SALARY, Semantic.AVAILABILITY,
    Semantic.NOTICE_PERIOD, Semantic.WORK_AUTHORIZATION,
    Semantic.EDUCATION, Semantic.SCHOOL, Semantic.COMPANY,
}
PROFIL_COMPLET: set[Semantic] = PROFIL_ACTUEL | SOCLE_MANQUANT

#: Champs auxquels on ne répond jamais à la place du candidat. Les compter
#: comme des échecs fausserait la note : ne pas les remplir est le comportement
#: voulu.
JAMAIS: set[Semantic] = {Semantic.DEMOGRAPHIC, Semantic.CONSENT}


@dataclass
class Note:
    """Le compte rendu d'une page."""

    id: str
    strate: str

    # ── ce que l'extracteur a vu ──
    vus: int = 0
    obligatoires: int = 0
    classes: int = 0
    inconnus: int = 0
    inconnus_obligatoires: int = 0

    # ── ce qu'on saurait renseigner ──
    resolus_actuel: int = 0
    resolus_complet: int = 0
    a_generer: int = 0
    jamais: int = 0

    # ── ce que le corrigé révèle, quand il existe ──
    declares: int | None = None
    declares_obligatoires: int | None = None
    manques: list[str] = field(default_factory=list)
    manques_obligatoires: list[str] = field(default_factory=list)

    erreur: str | None = None

    @property
    def rappel(self) -> float | None:
        """Part des champs déclarés que l'extracteur a effectivement vus."""
        if not self.declares:
            return None
        return (self.declares - len(self.manques)) / self.declares


#: Une même question, deux champs possibles. Greenhouse déclare `resume` et
#: `resume_text` pour un seul dépôt de CV — fichier ou texte collé — et la page
#: n'en rend qu'un à la fois, selon l'onglet actif. Les compter comme deux
#: attentes distinctes faisait apparaître 19 « champs obligatoires invisibles »
#: qui n'ont jamais existé. La cécité mesurée doit être celle du moteur, pas
#: celle du corrigé.
_VARIANTES: dict[str, set[str]] = {
    "resume": {"resume", "resume_text"},
    "resume_text": {"resume", "resume_text"},
    "cover_letter": {"cover_letter", "cover_letter_text"},
    "cover_letter_text": {"cover_letter", "cover_letter_text"},
}


def noter(page_id: str, strate: str, paires, corrige: list[dict] | None) -> Note:
    """
    Note une page à partir des champs extraits et classés, et du corrigé.

    `paires` est la sortie de `classify_all` : le champ tel que la page le
    décrit, et le sens qu'on lui a prêté.
    """
    note = Note(id=page_id, strate=strate, vus=len(paires))

    for champ, sens in paires:
        if champ.required:
            note.obligatoires += 1
        if sens is Semantic.UNKNOWN:
            note.inconnus += 1
            if champ.required:
                note.inconnus_obligatoires += 1
            continue
        note.classes += 1

        if sens in JAMAIS:
            note.jamais += 1
        elif sens is Semantic.OPEN_QUESTION:
            note.a_generer += 1
        else:
            if sens in PROFIL_ACTUEL:
                note.resolus_actuel += 1
            if sens in PROFIL_COMPLET:
                note.resolus_complet += 1

    if corrige:
        note.declares = len(corrige)
        note.declares_obligatoires = sum(1 for c in corrige if c["required"])
        # Le corrigé nomme les champs ; la page les porte tantôt en `name`,
        # tantôt en `id` — les boards React n'émettent aucun `name`. On
        # cherche donc dans les deux avant de conclure à un manque.
        vus = {c.name.strip().lower() for c, _ in paires if c.name}
        vus |= {c.element_id.strip().lower() for c, _ in paires if c.element_id}
        for attendu in corrige:
            noms = _VARIANTES.get(attendu["name"], {attendu["name"]})
            if not any(n.strip().lower() in vus for n in noms):
                note.manques.append(attendu["name"])
                if attendu["required"]:
                    note.manques_obligatoires.append(attendu["name"])

    return note


def agreger(notes: list[Note]) -> dict:
    """Les totaux d'une strate, en une ligne lisible."""
    valides = [n for n in notes if n.erreur is None]
    if not valides:
        return {"pages": 0, "echecs": len(notes)}

    somme = lambda cle: sum(getattr(n, cle) for n in valides)  # noqa: E731
    vus, oblig = somme("vus"), somme("obligatoires")
    avec_corrige = [n for n in valides if n.declares]

    resultat = {
        "pages": len(valides),
        "echecs": len(notes) - len(valides),
        "champs": vus,
        "obligatoires": oblig,
        "classes_pct": round(100 * somme("classes") / vus) if vus else 0,
        "inconnus_obligatoires": somme("inconnus_obligatoires"),
        "resolus_actuel_pct": round(100 * somme("resolus_actuel") / vus) if vus else 0,
        "resolus_complet_pct": round(100 * somme("resolus_complet") / vus) if vus else 0,
        "a_generer": somme("a_generer"),
    }
    if avec_corrige:
        declares = sum(n.declares for n in avec_corrige)
        manques = sum(len(n.manques) for n in avec_corrige)
        resultat |= {
            "declares": declares,
            "rappel_pct": round(100 * (declares - manques) / declares),
            "manques_obligatoires": sum(len(n.manques_obligatoires) for n in avec_corrige),
        }
    return resultat
