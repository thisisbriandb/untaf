"""
Classification d'un champ de formulaire — sans appel à un modèle.

Le principe : un modèle ne doit être sollicité que là où le programme ne sait
pas. Un champ `type="email"` n'a jamais besoin d'être interprété, et « Prénom »,
« First name », « Vorname » désignent la même chose dans un dictionnaire de
trente lignes.

L'ordre des tests n'est pas arbitraire, il va du plus fiable au plus faillible :

1. le type natif (`email`, `tel`, `file`) — non ambigu ;
2. `autocomplete`, que la norme HTML définit précisément ;
3. le nom ou l'identifiant, quand l'ATS publie un contrat stable ;
4. le libellé visible, multilingue, en dernier.

Ce qui ressort en `UNKNOWN` est la seule matière à confier à un modèle. Sur les
formulaires mesurés, c'est une poignée de champs par page, pas quinze.
"""

from __future__ import annotations

import re
from enum import Enum

from app.agents.application.form_parser import FormField


class Semantic(str, Enum):
    """Ce que le champ demande, indépendamment de sa forme."""

    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    FULL_NAME = "full_name"
    COMPANY = "current_company"
    EMAIL = "email"
    PHONE = "phone"
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    LOCATION = "location"
    COUNTRY = "country"
    SALARY = "salary_expectation"
    AVAILABILITY = "availability"
    NOTICE_PERIOD = "notice_period"
    WORK_AUTHORIZATION = "work_authorization"
    EDUCATION = "education"
    SCHOOL = "school"
    CONSENT = "consent"
    #: Question ouverte propre à l'employeur — à rédiger.
    OPEN_QUESTION = "open_question"
    #: Question démographique facultative : on n'y répond pas à la place du
    #: candidat, ce sont des données sensibles.
    DEMOGRAPHIC = "demographic"
    UNKNOWN = "unknown"


#: Motifs par type sémantique, en français, anglais, allemand et espagnol.
#: Testés dans l'ordre : le premier qui accroche gagne, donc les intitulés les
#: plus spécifiques doivent précéder les plus généraux.
_PATTERNS: list[tuple[Semantic, re.Pattern[str]]] = [
    (Semantic.DEMOGRAPHIC, re.compile(
        r"\b(identit[àa] di genere|identidad de g[ée]nero|orientamento sessuale|"
        r"orientaci[óo]n sexual|etnia|discapacidad|disabilit[àa]|"
        r"pronomi|pronombre|veterano)\b", re.I)),
    (Semantic.DEMOGRAPHIC, re.compile(
        r"\b(gender|genre|geschlecht|ethnic|ethnie|race|veteran|disabilit|"
        r"handicap|behinderung|orientation|pronoun)\w*", re.I)),
    (Semantic.LINKEDIN, re.compile(r"linked ?in", re.I)),
    (Semantic.GITHUB, re.compile(r"\b(github|gitlab)\b", re.I)),
    (Semantic.PORTFOLIO, re.compile(
        r"\b(portfolio|website|site web|webseite|twitter|x\.com|bluesky|"
        r"personal site)\b", re.I)),
    # Avant FULL_NAME : sans cela, « Company name » serait pris pour un nom
    # de personne, le motif du nom complet acceptant « name » seul.
    (Semantic.COMPANY, re.compile(
        r"\b(current )?(company|employer|entreprise|employeur|arbeitgeber|"
        r"unternehmen)\b", re.I)),
    (Semantic.COVER_LETTER, re.compile(
        r"\b(cover ?letter|lettre de motivation|motivationsschreiben|"
        r"anschreiben|carta de presentaci)", re.I)),
    (Semantic.RESUME, re.compile(
        r"\b(resume|résumé|cv\b|curriculum|lebenslauf)", re.I)),
    (Semantic.FIRST_NAME, re.compile(
        r"\b(first ?name|given ?name|pr[ée]nom|vorname|nombre)\b", re.I)),
    (Semantic.LAST_NAME, re.compile(
        r"\b(last ?name|sur ?name|family ?name|nom de famille|nachname|"
        r"apellido|cognome)\b", re.I)),
    # « Nom » seul, sans qualificatif : c'est le patronyme sur un formulaire
    # français, et il précède presque toujours un « Prénom » séparé. Le
    # placer ici, après « nom de famille » et avant FULL_NAME, lui évite
    # d'être pris pour un nom complet.
    (Semantic.LAST_NAME, re.compile(r"^\s*nom\s*\*?\s*$", re.I)),
    # « Name » seul est fréquent (Ashby). Placé après FIRST/LAST_NAME et
    # COMPANY, il ne capture plus que le cas réellement générique.
    (Semantic.FULL_NAME, re.compile(
        r"\b(full ?name|nom complet|vollst[äa]ndiger name|name)\b", re.I)),
    (Semantic.EMAIL, re.compile(r"\b(e[- ]?mail|courriel|correo)\b", re.I)),
    (Semantic.PHONE, re.compile(
        r"\b(phone|t[ée]l[ée]phone|telefon|mobile|portable|m[oó]vil)\b", re.I)),
    (Semantic.SALARY, re.compile(
        r"\b(salary|salaire|r[ée]mun[ée]ration|pr[ée]tention|compensation|"
        r"gehalt|expectation)\w*", re.I)),
    (Semantic.NOTICE_PERIOD, re.compile(
        r"\b(notice ?period|pr[ée]avis|k[üu]ndigungsfrist)\w*", re.I)),
    # « When can you start? » est une question ouverte par la forme mais une
    # donnée de profil par le fond : la reconnaître ici évite de la faire
    # rédiger par un modèle.
    (Semantic.AVAILABILITY, re.compile(
        r"\b(availab|disponibilit|date de d[ée]but|start ?date|eintrittstermin|"
        r"verf[üu]gbar)|when can you start", re.I)),
    (Semantic.WORK_AUTHORIZATION, re.compile(
        r"\b(work ?authorization|right to work|visa|sponsorship|permis de "
        r"travail|arbeitserlaubnis|autorisation de travail)\b", re.I)),
    (Semantic.SCHOOL, re.compile(
        r"\b(school|university|universit[ée]|[ée]cole|ausbildungsst[äa]tte|"
        r"hochschule)\w*", re.I)),
    (Semantic.EDUCATION, re.compile(
        r"\b(degree|dipl[oô]m\w*|diploma|qualification|graduation|"
        r"niveau d.?[ée]tudes|education|abschluss|studiengang)\b", re.I)),
    (Semantic.COUNTRY, re.compile(r"\b(country|pays|land|pa[íi]s)\b", re.I)),
    (Semantic.LOCATION, re.compile(
        r"\b(location|city|ville|adresse|address|standort|stadt|ciudad)\b", re.I)),
    (Semantic.CONSENT, re.compile(
        r"\b(consent|consentement|j.?accepte|i agree|einverstanden|"
        r"privacy|confidentialit|datenschutz)\b", re.I)),
]

#: `autocomplete` est normalisé par le HTML : quand il est présent, il tranche.
_AUTOCOMPLETE = {
    "given-name": Semantic.FIRST_NAME,
    "family-name": Semantic.LAST_NAME,
    "name": Semantic.FULL_NAME,
    "email": Semantic.EMAIL,
    "tel": Semantic.PHONE,
    "tel-national": Semantic.PHONE,
    "country": Semantic.COUNTRY,
    "country-name": Semantic.COUNTRY,
    "address-level2": Semantic.LOCATION,
    "url": Semantic.PORTFOLIO,
}

#: Noms de champs publiés par les ATS. Stables, mesurés identiques sur tous les
#: boards Greenhouse testés.
_ATS_NAMES = {
    "first_name": Semantic.FIRST_NAME,
    "last_name": Semantic.LAST_NAME,
    "email": Semantic.EMAIL,
    "phone": Semantic.PHONE,
    "resume": Semantic.RESUME,
    "cv": Semantic.RESUME,
    "cover_letter": Semantic.COVER_LETTER,
    "cover_letter_text": Semantic.COVER_LETTER,
    "candidate-location": Semantic.LOCATION,
    "country": Semantic.COUNTRY,
}

#: Une question ouverte se reconnaît à sa longueur et à sa ponctuation, pas à
#: un mot-clé : « Pourquoi souhaitez-vous nous rejoindre ? » n'a pas de terme
#: distinctif, mais c'est une phrase interrogative dans une zone de texte.
_QUESTION = re.compile(r"[?？]\s*$|^(pourquoi|why|comment|how|tell us|"
                       r"d[ée]crivez|describe|parlez[- ]nous)", re.I)

#: Longueur à partir de laquelle un intitulé cesse de nommer un champ pour
#: énoncer une question. Mesuré sur le corpus : en dessous, on trouve des
#: intitulés de champs ; au-dessus, des phrases.
_LONGUEUR_QUESTION = 40


def classify(field: FormField) -> Semantic:
    """Le type sémantique d'un champ, ou `UNKNOWN` si le programme ne sait pas."""
    # 1. Type natif — sans ambiguïté possible.
    if field.input_type == "email":
        return Semantic.EMAIL
    if field.input_type == "tel":
        return Semantic.PHONE
    if field.input_type == "file":
        blob = field.signals + " " + field.accept.lower()
        if re.search(r"cover|motivation|anschreiben", blob, re.I):
            return Semantic.COVER_LETTER
        return Semantic.RESUME
    if field.input_type == "checkbox" and not field.signals.strip():
        return Semantic.CONSENT

    # 2. `autocomplete`, défini par la norme.
    auto = field.autocomplete.strip().lower()
    if auto in _AUTOCOMPLETE:
        return _AUTOCOMPLETE[auto]

    # 3. Nom ou identifiant publié par l'ATS.
    for key in (field.name.strip().lower(), field.element_id.strip().lower()):
        if key in _ATS_NAMES:
            return _ATS_NAMES[key]

    # 4. Libellé visible, multilingue.
    blob = field.signals
    for semantic, pattern in _PATTERNS:
        if pattern.search(blob):
            return semantic

    # 5. Question ouverte : reconnue à sa forme, pas à son vocabulaire.
    if field.tag == "textarea" or _QUESTION.search(field.label):
        if field.label:
            return Semantic.OPEN_QUESTION

    # 6. La longueur, faute de mieux. « Qual è la tua data di inizio ideale e
    #    hai un preavviso da rispettare ? » ne contient aucun terme du
    #    dictionnaire et ne finit pas toujours par un point d'interrogation,
    #    mais quarante caractères d'énoncé ne nomment pas un champ de saisie :
    #    ils posent une question. Le critère porte sur la forme, donc il vaut
    #    pour les langues qu'on n'a pas prévues — c'est tout son intérêt.
    if len(field.label) >= _LONGUEUR_QUESTION:
        return Semantic.OPEN_QUESTION

    return Semantic.UNKNOWN


def classify_all(fields: list[FormField]) -> list[tuple[FormField, Semantic]]:
    """Classe tous les champs d'une page en un passage, sans appel réseau."""
    return [(f, classify(f)) for f in fields]


def coverage(pairs: list[tuple[FormField, Semantic]]) -> dict[str, int]:
    """
    Ce que le niveau déterministe a résolu, et ce qu'il laisse.

    Sert à décider s'il faut solliciter un modèle : sans champ inconnu ni
    question ouverte, il n'y a rien à lui demander.
    """
    unknown = [f for f, s in pairs if s is Semantic.UNKNOWN]
    open_q = [f for f, s in pairs if s is Semantic.OPEN_QUESTION]
    return {
        "total": len(pairs),
        "classes": len(pairs) - len(unknown),
        "inconnus": len(unknown),
        "questions_ouvertes": len(open_q),
        "inconnus_obligatoires": sum(1 for f in unknown if f.required),
    }


#: Ce que le programme sait renseigner seul, à partir du profil du candidat.
#: Le reste — questions ouvertes, champs inconnus — relève du niveau supérieur.
PROFILE_BACKED = {
    Semantic.FIRST_NAME, Semantic.LAST_NAME, Semantic.FULL_NAME,
    Semantic.EMAIL, Semantic.PHONE, Semantic.RESUME, Semantic.COVER_LETTER,
    Semantic.LINKEDIN, Semantic.GITHUB, Semantic.PORTFOLIO,
    Semantic.LOCATION, Semantic.COUNTRY,
}

#: Champs auxquels on ne répond jamais à la place du candidat. Les données
#: démographiques sont sensibles et leur déclaration est facultative par la
#: loi : les remplir automatiquement serait décider pour lui.
NEVER_AUTOFILL = {Semantic.DEMOGRAPHIC, Semantic.CONSENT}


def needs_model(pairs: list[tuple[FormField, Semantic]]) -> list[FormField]:
    """
    Les champs qui justifient un appel au modèle — et eux seuls.

    Un formulaire dont tout est classé et adossé au profil n'en déclenche
    aucun. C'est le point de toute l'architecture : le modèle intervient là
    où le programme ne sait pas, pas à chaque champ.
    """
    return [
        f for f, s in pairs
        if s in (Semantic.UNKNOWN, Semantic.OPEN_QUESTION)
        and s not in NEVER_AUTOFILL
        and f.required
    ]
