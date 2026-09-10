"""
Mesure du moteur sur le corpus gelé.

    python -m tests.harness.report [étiquette]

Rejoue chaque page figée, lui applique l'extracteur puis le classifieur, et
rend la note par strate. Le résultat est écrit à côté du corpus : deux runs se
comparent, ce qui est le seul moyen de dire qu'une correction a corrigé
quelque chose.

Les strates ne sont pas décoratives. `gh_canonique` est le cas facile, celui
dont l'ATS publie le corrigé : il doit sortir à 100 % et sa chute signale une
régression. `web_form` est le cas réel — aucune structure connue, aucun
corrigé — et c'est lui qui dit si le moteur tient sa promesse.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time

from app.agents.application.field_classifier import classify_all
from app.agents.application.form_parser import extract_fields
from tests.harness import corpus, oracle, scoring

logging.basicConfig(level=logging.ERROR, format="%(message)s")

_ORDRE = ["gh_canonique", "gh_eu", "gh_employeur", "ashby", "lever", "web_form"]


async def mesurer(pages) -> list[scoring.Note]:
    from playwright.async_api import async_playwright

    notes: list[scoring.Note] = []
    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context()

        for page_corpus in pages:
            onglet = await contexte.new_page()
            try:
                await onglet.goto(corpus.ouvrir(page_corpus).as_uri(),
                                  wait_until="load", timeout=30_000)
                # L'instantané est déjà rendu : rien n'arrive après le
                # chargement, une courte pause suffit à laisser poser la mise
                # en page dont dépendent les styles calculés.
                await onglet.wait_for_timeout(300)

                paires = classify_all(await extract_fields(onglet))
                notes.append(scoring.noter(
                    page_corpus.id, page_corpus.strate, paires,
                    oracle.lire(page_corpus.corrige),
                ))
            except Exception as exc:  # noqa: BLE001
                note = scoring.Note(id=page_corpus.id, strate=page_corpus.strate)
                note.erreur = str(exc).splitlines()[0][:80]
                notes.append(note)
            finally:
                await onglet.close()

        await navigateur.close()
    return notes


def afficher(notes: list[scoring.Note]) -> dict:
    par_strate: dict[str, list[scoring.Note]] = {}
    for note in notes:
        par_strate.setdefault(note.strate, []).append(note)

    entete = (f"{'strate':14} {'pages':>5} {'champs':>7} {'classés':>8} "
              f"{'inconnus':>9} {'profil':>7} {'+socle':>7} {'générer':>8} {'rappel':>7} {'manqués':>8}")
    print(entete)
    print("─" * len(entete))

    resultats = {}
    for strate in _ORDRE:
        if strate not in par_strate:
            continue
        a = scoring.agreger(par_strate[strate])
        resultats[strate] = a
        if not a["pages"]:
            print(f"{strate:14} {'—':>5}")
            continue
        rappel = f"{a['rappel_pct']}%" if "rappel_pct" in a else "—"
        manques = str(a["manques_obligatoires"]) if "manques_obligatoires" in a else "—"
        print(f"{strate:14} {a['pages']:5} {a['champs']:7} "
              f"{a['classes_pct']:7}% {a['inconnus_obligatoires']:9} "
              f"{a['resolus_actuel_pct']:6}% {a['resolus_complet_pct']:6}% "
              f"{a['a_generer']:8} {rappel:>7} {manques:>8}")

    total = scoring.agreger(notes)
    print("─" * len(entete))
    print(f"{'TOTAL':14} {total['pages']:5} {total['champs']:7} "
          f"{total['classes_pct']:7}% {total['inconnus_obligatoires']:9} "
          f"{total['resolus_actuel_pct']:6}% {total['resolus_complet_pct']:6}% "
          f"{total['a_generer']:8}")

    print("\nclassés  — le classifieur a donné un sens au champ")
    print("inconnus — champs OBLIGATOIRES sans aucun sens attribué")
    print("profil   — renseignables avec les colonnes de `Candidate` aujourd'hui")
    print("+socle   — renseignables si le socle candidat était collecté")
    print("générer  — questions ouvertes, à rédiger (un appel par page)")
    print("rappel   — part des champs du corrigé que l'extracteur a vus")
    print("manqués  — champs OBLIGATOIRES du corrigé jamais vus (cécité silencieuse)")
    resultats["TOTAL"] = total
    return resultats


async def principal(etiquette: str) -> None:
    pages = corpus.gelees()
    if not pages:
        print("Corpus vide. Lancer d'abord : python -m tests.harness.freeze")
        return

    depart = time.time()
    notes = await mesurer(pages)
    resultats = afficher(notes)
    duree = time.time() - depart

    dossier = corpus.RACINE / "runs"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"{etiquette}.json").write_text(
        json.dumps({"etiquette": etiquette, "pages": len(pages),
                    "secondes": round(duree, 1), "strates": resultats,
                    "detail": [vars(n) for n in notes]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(pages)} pages en {duree:.0f} s · écrit dans "
          f"tests/corpus/runs/{etiquette}.json")


if __name__ == "__main__":
    asyncio.run(principal(sys.argv[1] if len(sys.argv) > 1 else "run"))
