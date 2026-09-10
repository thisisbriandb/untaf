"""
Gel du corpus : capture chaque page une fois, pour qu'elle se relise à
l'identique ensuite.

    python -m tests.harness.freeze [strate ...]

Deux précautions donnent au corpus sa valeur.

La première est l'attente. `networkidle` ne convient pas : ces pages gardent
des connexions ouvertes en permanence, et le signal arrive tantôt avant tantôt
après le montage du formulaire — d'où les 26, 26, 0, 0 champs mesurés sur
quatre chargements d'une même page Ashby. On attend donc que le nombre de
champs cesse de bouger, ce qui est un fait de la page et non du réseau. Cette
barrière manque au moteur lui-même : c'est l'une des corrections à venir.

La seconde est le format. Un HTML seul perd les feuilles de style, donc les
styles calculés, donc le test de visibilité de l'extracteur : les champs
masqués deviendraient visibles et le corpus mentirait. L'instantané MHTML
embarque le rendu et son habillage dans un fichier unique, relisible hors
ligne.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from tests.harness import corpus, oracle

logging.basicConfig(level=logging.WARNING, format="%(message)s")

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


async def attendre_formulaire(page, tours: int = 15, pas_ms: int = 700) -> int:
    """
    Rend la main quand le formulaire a fini d'apparaître.

    Le critère est la stabilité : deux relevés consécutifs identiques et non
    nuls. Un compte qui bouge encore signale un rendu en cours ; un compte nul
    ne prouve rien — ni que la page est vide, ni qu'elle est prête.
    """
    precedent, stable = -1, 0
    for _ in range(tours):
        combien = await page.evaluate(
            "() => document.querySelectorAll('input, textarea, select').length"
        )
        if combien and combien == precedent:
            stable += 1
            if stable >= 2:
                return combien
        else:
            stable = 0
        precedent = combien
        await page.wait_for_timeout(pas_ms)
    return max(precedent, 0)


async def geler(strates: list[str] | None = None) -> None:
    from playwright.async_api import async_playwright

    pages = [p for p in corpus.charger(strates) if not p.gelee]
    if not pages:
        print("Rien à geler : le corpus est complet.")
        return

    print(f"{len(pages)} pages à geler.\n")
    reussites, poids = 0, 0

    async with async_playwright() as pw:
        navigateur = await pw.chromium.launch(headless=True)
        contexte = await navigateur.new_context(user_agent=_UA)

        for rang, page_corpus in enumerate(pages, 1):
            onglet = await contexte.new_page()
            try:
                reponse = await onglet.goto(
                    page_corpus.url, wait_until="domcontentloaded", timeout=45_000
                )
                if reponse and reponse.status >= 400:
                    raise RuntimeError(f"HTTP {reponse.status}")

                champs = await attendre_formulaire(onglet)
                if not champs:
                    # Une page sans le moindre champ n'est pas un formulaire :
                    # offre expirée, mur de connexion, redirection. L'inclure
                    # au corpus fausserait toutes les moyennes.
                    raise RuntimeError("aucun champ")

                session = await contexte.new_cdp_session(onglet)
                instantane = await session.send("Page.captureSnapshot", {"format": "mhtml"})
                octets = corpus.ecrire_instantane(page_corpus, instantane["data"])
                poids += octets

                corrige = await oracle.recuperer(page_corpus.url)
                if corrige:
                    oracle.ecrire(page_corpus.corrige, corrige)

                reussites += 1
                marque = f"corrigé {len(corrige)}" if corrige else "sans corrigé"
                print(f"[{rang:3}/{len(pages)}] {page_corpus.id:16} "
                      f"{champs:3} champs · {octets // 1024:4} Ko · {marque}", flush=True)

            except Exception as exc:  # noqa: BLE001
                print(f"[{rang:3}/{len(pages)}] {page_corpus.id:16} écarté — "
                      f"{str(exc).splitlines()[0][:60]}", flush=True)
            finally:
                await onglet.close()

        await navigateur.close()

    print(f"\n{reussites}/{len(pages)} pages gelées · {poids / 1e6:.1f} Mo")


if __name__ == "__main__":
    asyncio.run(geler(sys.argv[1:] or None))
