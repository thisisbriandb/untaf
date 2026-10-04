"""
Extraction des coordonnées de candidature dans un texte libre.

Les sources donnent rarement une adresse propre dans le champ prévu pour : le
`courriel` de France Travail contient souvent une consigne (« Pour postuler,
utiliser le lien suivant : … »), et beaucoup d'annonces écrivent l'adresse en
toutes lettres dans la description (« CV et lettre à recrutement@acme.fr »).
Ignorer ces adresses revenait à vider le seul canal d'envoi irréprochable.

Deux règles :
  - une adresse n'est retenue que si elle ressemble à une boîte de
    candidature, jamais celle d'une plateforme ou d'un expéditeur automatique ;
  - quand le texte en contient plusieurs, on préfère celle qui est entourée de
    mots de candidature, plutôt que la première venue.
"""

from __future__ import annotations

import re

#: Adresse complète, isolée. Volontairement plus stricte qu'un `\S+@\S+` :
#: une ponctuation collée (« rh@acme.fr. ») ne doit pas finir dans l'adresse.
_EMAIL_RE = re.compile(
    r"(?<![\w.+-])([A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24})(?![\w-])"
)
_EMAIL_FULL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}")
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

#: Domaines qui n'appartiennent jamais au recruteur.
_PLATFORM_DOMAINS = (
    "francetravail.fr", "francetravail.org", "pole-emploi.fr", "pole-emploi.net",
    "example.com", "example.org", "domaine.fr", "domain.com", "email.com",
    "sentry.io", "indeed.com", "linkedin.com", "welcometothejungle.com",
)

#: Préfixes d'expéditeurs automatiques : y écrire, c'est écrire dans le vide.
_NOREPLY = re.compile(r"^(no[-_.]?reply|ne[-_.]?pas[-_.]?repondre|donotreply|mailer-daemon|bounce)", re.I)

#: Extensions de fichiers qu'un motif d'adresse attrape par erreur (logo@2x.png).
_FILE_SUFFIX = re.compile(r"\.(png|jpe?g|gif|svg|webp|pdf|docx?)$", re.I)

#: Mots qui, près d'une adresse, signalent une boîte de candidature.
_APPLY_HINTS = re.compile(
    r"candidat|postul|cv\b|curriculum|lettre|motivation|recrut|rh\b|ressources humaines|"
    r"apply|resume|career|carri[eè]re|jobs?\b|emploi|envoy|adress",
    re.I,
)
_LOCAL_HINTS = re.compile(r"^(rh|hr|recrut|recruit|jobs?|career|carriere|emploi|talent|candidat|apply)", re.I)

#: Liens qui mènent au portail candidat authentifié, pas à l'employeur.
_PORTAL_URL = re.compile(r"(francetravail|pole-emploi)\.(fr|org)", re.I)


def is_valid_email(value: str | None) -> bool:
    """Une adresse exploitable, et non une consigne rédigée ni une boîte de plateforme."""
    if not value:
        return False
    value = value.strip()
    if not _EMAIL_FULL.fullmatch(value):
        return False
    local, _, domain = value.lower().rpartition("@")
    if _FILE_SUFFIX.search(value) or _NOREPLY.match(local):
        return False
    return not any(domain == d or domain.endswith("." + d) for d in _PLATFORM_DOMAINS)


def _score(text: str, start: int, end: int, address: str) -> int:
    window = text[max(0, start - 120):min(len(text), end + 40)]
    score = 2 * len(_APPLY_HINTS.findall(window))
    if _LOCAL_HINTS.match(address.split("@", 1)[0]):
        score += 3
    return score


def find_apply_email(*texts: str | None, min_score: int = 0) -> str | None:
    """
    La meilleure adresse de candidature trouvée dans ces textes, ou None.

    Les textes sont donnés par ordre de confiance : à score égal, une adresse
    du champ contact l'emporte sur une adresse croisée dans la description.
    `min_score` exige des mots de candidature autour de l'adresse — utile sur
    une description, où une adresse peut servir à tout autre chose.
    """
    best: tuple[int, int, str] | None = None
    for rank, text in enumerate(texts):
        if not text:
            continue
        for match in _EMAIL_RE.finditer(text):
            address = match.group(1).strip(".")
            if not is_valid_email(address):
                continue
            key = (_score(text, match.start(), match.end(), address), -rank, address)
            if key[0] < min_score:
                continue
            if best is None or key[:2] > best[:2]:
                best = key
    return best[2].lower() if best else None


def find_apply_url(*texts: str | None) -> str | None:
    """Premier lien qui ne renvoie pas au portail candidat authentifié."""
    for text in texts:
        if not text:
            continue
        for match in _URL_RE.finditer(text):
            url = match.group(0).rstrip(".,;:!?")
            if not _PORTAL_URL.search(url):
                return url
    return None
