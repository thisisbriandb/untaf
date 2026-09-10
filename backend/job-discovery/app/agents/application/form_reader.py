"""
Lecture d'un formulaire sur page vivante — l'étage qui manquait.

`form_parser` lit le DOM tel qu'il est. Ce module le rend d'abord lisible, ce
qui n'est pas la même chose : sur le web réel, une partie du formulaire n'existe
pas encore au chargement.

Trois manques ont été mesurés sur un corpus de 109 pages, et ce module répond à
chacun.

**Le formulaire est parfois à un clic.** 45 pages sur 109 n'exposent aucun
formulaire : ce sont des pages de description, dont 11 portent un bouton
« Postuler ». Sans ce clic, le moteur lit les filtres du board — « Department »,
« Office » — et croit avoir lu une candidature.

**Le formulaire arrive après le signal réseau.** `networkidle` rend la main
avant que React ait monté les champs : quatre chargements d'une même page Ashby
ont donné 26, 26, 0 et 0 champs. On attend donc que le compte de champs cesse
de bouger, ce qui est un fait de la page et non du réseau.

**Les options d'une liste fermée ne sont pas dans le DOM.** Sur 247 listes
mesurées, 26 seulement déclarent leur panneau par `aria-controls` ; les 221
autres ne contiennent rien avant ouverture. Il n'y a pas de lecture statique
possible : il faut ouvrir la liste, lire, refermer. Lecture et interaction sont
le même acte, et prétendre le contraire produisait des options fausses — 88 %
des listes se voyaient attribuer celles d'un voisin, « Diplôme » proposant
« Afghanistan+93 ».

Ce module ne remplit rien et ne soumet rien. Il rend ce que la page contient
vraiment, une fois qu'on a pris la peine de le lui demander.
"""

from __future__ import annotations

import logging

from app.agents.application.field_classifier import Semantic, classify
from app.agents.application.form_parser import FormField, extract_fields

logger = logging.getLogger(__name__)

#: Intitulés qui mènent d'une description d'offre à son formulaire. Cherchés
#: sur le texte visible, pas sur une classe CSS : « Apply » survit aux refontes.
_APPEL_CANDIDATURE = (
    r"^(apply( now| for this job)?|postuler|je postule|candidater|"
    r"bewerben|solicitar|candidatura)"
)

#: Au-delà, ce n'est plus un formulaire qui se charge : c'est une page qui ne
#: viendra pas.
_TOURS_ATTENTE = 15
_PAS_ATTENTE_MS = 700


async def _compter_champs(page) -> int:
    return await page.evaluate(
        "() => document.querySelectorAll('input, textarea, select').length"
    )


async def attendre_formulaire(page, tours: int = _TOURS_ATTENTE,
                              pas_ms: int = _PAS_ATTENTE_MS) -> int:
    """
    Rend la main quand le formulaire a fini d'apparaître.

    Le critère est la stabilité : deux relevés consécutifs identiques et non
    nuls. Un compte qui bouge encore signale un rendu en cours ; un compte nul
    ne prouve rien — ni que la page est vide, ni qu'elle est prête.
    """
    precedent, stable = -1, 0
    for _ in range(tours):
        combien = await _compter_champs(page)
        if combien and combien == precedent:
            stable += 1
            if stable >= 2:
                return combien
        else:
            stable = 0
        precedent = combien
        await page.wait_for_timeout(pas_ms)
    return max(precedent, 0)


def _est_un_formulaire(champs: list[FormField]) -> bool:
    """
    Cette page demande-t-elle une candidature, ou décrit-elle seulement une
    offre ?

    Le signe le plus sûr est le dépôt de CV. À défaut, un e-mail accompagné
    d'un nom : aucune page de description ne réclame les deux. Les filtres d'un
    board — « Department », « Office » — n'en réclament aucun, et c'est
    précisément ce qui les distingue.
    """
    sens = {classify(champ) for champ in champs}
    if Semantic.RESUME in sens:
        return True
    return Semantic.EMAIL in sens and bool(
        sens & {Semantic.FIRST_NAME, Semantic.FULL_NAME}
    )


async def atteindre_formulaire(page) -> bool:
    """
    Amène la page sur son formulaire, en cliquant s'il le faut.

    Rend vrai quand un formulaire est là. Rend faux quand la page n'en propose
    pas — offre expirée, mur de connexion, page d'atterrissage —, et c'est une
    information utilisable : il n'y a rien à remplir, autant le dire tout de
    suite plutôt que de rapporter des champs qui n'appartiennent pas à une
    candidature.
    """
    await attendre_formulaire(page)
    if _est_un_formulaire(await extract_fields(page)):
        return True

    appel = page.get_by_role(
        "link", name=_APPEL_CANDIDATURE
    ).or_(page.get_by_role("button", name=_APPEL_CANDIDATURE)).first

    try:
        if not await appel.count():
            return False
        await appel.click(timeout=5_000)
    except Exception as exc:  # noqa: BLE001
        logger.info("Le bouton de candidature n'a pas répondu : %s", exc)
        return False

    await attendre_formulaire(page)
    return _est_un_formulaire(await extract_fields(page))


#: Les options visibles, et le panneau auquel elles appartiennent. On ne prend
#: que ce qui est réellement affiché : ces composants gardent leurs options
#: dans le DOM en permanence, et lire les invisibles ramènerait la liste
#: entière d'un autre champ.
_OPTIONS_VISIBLES = """
() => {
  const affichees = Array.from(document.querySelectorAll('[role="option"]'))
    .filter(o => o.checkVisibility ? o.checkVisibility() : o.getClientRects().length);
  return affichees.map(o => (o.innerText || '').trim())
                  .filter(Boolean).slice(0, 400);
}
"""


async def _sonder_options(page, tours: int = 8, pas_ms: int = 250) -> list[str]:
    """
    Attend que des options deviennent visibles, puis les rend.

    Le sondage remplace une attente sur locator, qui ne pouvait pas marcher :
    `[role="option"]` désigne le premier de la page, et les listes de ces
    composants gardent leurs options dans le DOM en permanence. On attendait
    donc la visibilité d'une option du champ « pays » pendant qu'une autre
    liste était ouverte — elle ne venait jamais.
    """
    for _ in range(tours):
        options = await page.evaluate(_OPTIONS_VISIBLES)
        if options:
            return options
        await page.wait_for_timeout(pas_ms)
    return []


async def _refermer(page, cible) -> None:
    """
    Referme le panneau, quoi qu'il en coûte.

    Un panneau resté ouvert recouvre les champs suivants : leur clic atterrit
    sur une option de la liste précédente, et la lecture de tout le reste du
    formulaire est perdue. Échap d'abord, un clic dans le vide ensuite pour les
    composants qui ignorent la touche.
    """
    try:
        await cible.press("Escape", timeout=1_500)
        if await page.evaluate(_OPTIONS_VISIBLES):
            await page.mouse.click(2, 2)
            await page.wait_for_timeout(150)
    except Exception:  # noqa: BLE001
        pass


async def lire_options(page, champ: FormField) -> tuple[list[str], str]:
    """
    Ouvre une liste, lit ce qu'elle propose, la referme.

    Rend les options **et** la nature du composant, parce que « aucune option »
    recouvre deux situations qu'il ne faut pas confondre au moment de remplir :

    - `enumerable` — la liste montre ses options au clic. On peut choisir.
    - `recherche` — elle ne montre rien avant qu'on tape : le champ interroge
      un service à la frappe, et sa liste d'options n'existe pas. C'est le cas
      des champs de ville. Il n'y a rien à énumérer, mais tout à saisir.
    - `inerte` — rien ne s'ouvre. Là seulement, le composant résiste.

    Un remplisseur qui ignore cette distinction traite un champ de recherche
    comme une liste cassée, et abandonne un champ qui marchait.
    """
    cible = page.locator(champ.selector).first
    try:
        if not await cible.count():
            return [], "inerte"
        await cible.scroll_into_view_if_needed(timeout=3_000)
        await cible.click(timeout=3_000)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Liste « %s » non ouvrable : %s", champ.label or champ.selector, exc)
        return [], "inerte"

    options = await _sonder_options(page)
    if options:
        await _refermer(page, cible)
        return options, "enumerable"

    # Rien au clic : reste à savoir si le composant attend une frappe. Une
    # seule lettre suffit à trancher, et elle est effacée aussitôt.
    nature = "inerte"
    try:
        await cible.press_sequentially("a", delay=40, timeout=3_000)
        if await _sonder_options(page, tours=6):
            nature = "recherche"
        await cible.press("Control+a", timeout=1_000)
        await cible.press("Backspace", timeout=1_000)
    except Exception:  # noqa: BLE001
        pass

    await _refermer(page, cible)
    return [], nature


async def lire(page, *, ouvrir_les_listes: bool = True) -> list[FormField]:
    """
    Le formulaire de cette page, aussi complètement que la page veut bien le
    dire.

    `ouvrir_les_listes` a un coût : un aller-retour navigateur par liste, soit
    quelques secondes sur un formulaire qui en compte vingt. Le désactiver rend
    la lecture immédiate mais laisse les listes sans options — utile pour un
    diagnostic, jamais pour une candidature.
    """
    if not await atteindre_formulaire(page):
        logger.info("Aucun formulaire de candidature sur cette page.")
        return []

    champs = await extract_fields(page)
    if not ouvrir_les_listes:
        return champs

    for champ in champs:
        if not champ.is_choice or champ.options or champ.tag == "radiogroup":
            continue
        champ.options, champ.choice_mode = await lire_options(page, champ)

    return champs
