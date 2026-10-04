"""
Garde-fous du moteur de candidature.

Ces tests ne décrivent pas un comportement idéal : ils figent ce qui est
mesuré, pour qu'une régression se voie. Les seuils viennent du corpus, pas
d'une intention — et ils descendent, ils ne montent pas.

Tout tourne hors ligne, sur des pages gelées : aucune assertion ne peut échouer
parce qu'une offre a expiré. La mesure complète, elle, est ailleurs :
`python -m tests.harness.report`.
"""

from __future__ import annotations

import pytest

# Extra « browser » : sans lui, ces tests sont sautés au lieu de faire échouer
# la collecte de toute la suite.
pytest.importorskip("playwright")
from playwright.async_api import async_playwright

from app.agents.application.field_classifier import Semantic, classify_all, needs_model
from app.agents.application.form_parser import extract_fields
from tests.harness import corpus, oracle, scoring

#: Relevé de référence (run « corrige2 ») : sur les pages dont l'ATS publie le
#: contrat, aucun champ obligatoire déclaré n'échappe à l'extracteur. Une
#: hausse doit s'expliquer par un run, pas par un ajustement du seuil.
SEUIL_MANQUES_OBLIGATOIRES = 0

#: Assez de pages pour que l'invariant soit éprouvé, assez peu pour que la
#: suite reste lançable à chaque modification.
ECHANTILLON = 25


def _pages(strates=None, avec_corrige=False):
    pages = corpus.gelees(strates)
    if avec_corrige:
        pages = [p for p in pages if p.corrige.exists()]
    if not pages:
        pytest.skip("Corpus vide — lancer python -m tests.harness.freeze")
    return pages[:ECHANTILLON]


async def _champs(contexte, page_corpus):
    onglet = await contexte.new_page()
    try:
        await onglet.goto(corpus.ouvrir(page_corpus).as_uri(),
                          wait_until="load", timeout=30_000)
        await onglet.wait_for_timeout(250)
        return await extract_fields(onglet)
    finally:
        await onglet.close()


async def test_le_gel_rend_la_lecture_deterministe():
    """
    Trois lectures d'une même page figée donnent le même résultat.

    C'est la propriété qui rend toute mesure possible. Sur page vivante elle
    est fausse : quatre chargements d'une même offre Ashby ont donné 26, 26,
    0 et 0 champs, selon que React avait fini de monter le formulaire.
    """
    page = _pages()[0]
    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context()
        comptes = {len(await _champs(contexte, page)) for _ in range(3)}
        await navigateur.close()
    assert len(comptes) == 1, f"lecture instable : {comptes}"


async def test_aucun_champ_obligatoire_du_corrige_n_est_invisible():
    """
    Le manquement le plus grave, parce qu'il est muet : un champ obligatoire
    que l'extracteur ne voit pas ne peut figurer dans aucun rapport d'échec.
    La candidature part incomplète en se croyant complète.
    """
    pages = _pages(avec_corrige=True)
    manques: list[str] = []
    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context()
        for page in pages:
            paires = classify_all(await _champs(contexte, page))
            note = scoring.noter(page.id, page.strate, paires, oracle.lire(page.corrige))
            manques += [f"{page.id}:{nom}" for nom in note.manques_obligatoires]
        await navigateur.close()

    assert len(manques) <= SEUIL_MANQUES_OBLIGATOIRES, (
        f"{len(manques)} champs obligatoires invisibles : {manques[:5]}"
    )


async def test_les_questions_demographiques_ne_partent_jamais_au_modele():
    """
    Genre, origine, handicap, pronoms : leur déclaration est facultative par
    construction, et y répondre à la place du candidat serait décider pour lui.

    Le risque est concret depuis qu'un intitulé long vaut « question ouverte » :
    sans reconnaissance explicite, « Come descriveresti la tua identità di
    genere » serait passé au générateur de réponses.
    """
    pages = _pages()
    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context()
        for page in pages:
            paires = classify_all(await _champs(contexte, page))
            sens_par_selecteur = {c.selector: s for c, s in paires}
            for champ in needs_model(paires):
                sens = sens_par_selecteur[champ.selector]
                assert sens is not Semantic.DEMOGRAPHIC, f"{page.id} : {champ.label!r}"
        await navigateur.close()


async def test_un_groupe_de_boutons_est_une_seule_question():
    """
    Douze cases « pronouns » chez Lever, treize boutons radio chez Ashby : la
    page les rend un par un, mais ils posent une question et une seule. Les
    compter séparément gonflait le nombre de champs obligatoires et donnait à
    chacun l'intitulé de son option — « Yes » pour question.
    """
    pages = _pages(["lever", "ashby"])
    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context()
        groupes_vus = 0
        for page in pages:
            for champ in await _champs(contexte, page):
                if champ.tag != "radiogroup":
                    continue
                groupes_vus += 1
                assert len(champ.group_selectors) >= 2, (
                    f"{page.id} : groupe d'un seul élément"
                )
                assert champ.label not in champ.options, (
                    f"{page.id} : le groupe porte l'intitulé d'une de ses "
                    f"options ({champ.label!r})"
                )
        await navigateur.close()
    assert groupes_vus, "aucun groupe rencontré : le corpus ne teste plus rien"
