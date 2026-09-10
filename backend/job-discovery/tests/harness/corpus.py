"""
Corpus d'évaluation du moteur de candidature.

Le stock d'offres en base sert de matière première, pas de vérité : les
annonces vieillissent, disparaissent, et surtout ne se rendent pas deux fois
pareil. Mesuré sur une page Ashby, quatre chargements identiques donnent
26, 26, 0 et 0 champs — `networkidle` rend la main avant que React ait monté
le formulaire. Un corpus d'URL vivantes mélangerait donc deux choses qu'il
faut séparer absolument : « le moteur a régressé » et « la page a répondu
autrement ».

D'où le gel. Chaque page est capturée une fois, après stabilisation, en
instantané MHTML — le DOM rendu et ses feuilles de style dans un seul fichier.
Le rejeu est hors ligne, identique à chaque fois, et vingt fois plus rapide.

Ce que le gel conserve : la structure du DOM, les libellés, les attributs, les
styles calculés — tout ce que lit l'extracteur.
Ce qu'il perd : React. Un instantané ne réagit pas au clavier. Il mesure donc
la lecture et la classification, pas le remplissage : ces deux derniers étages
exigent une page vivante.
"""

from __future__ import annotations

import gzip
import json
import pathlib
import tempfile
from dataclasses import dataclass

RACINE = pathlib.Path(__file__).resolve().parent.parent / "corpus"
MANIFESTE = RACINE / "manifest.json"
PAGES = RACINE / "pages"
ORACLE = RACINE / "oracle"


@dataclass(frozen=True)
class Page:
    """Une page du corpus : d'où elle vient, où elle est gelée."""

    id: str
    strate: str
    url: str

    @property
    def instantane(self) -> pathlib.Path:
        return PAGES / f"{self.id}.mhtml.gz"

    @property
    def corrige(self) -> pathlib.Path:
        """Le corrigé publié par l'ATS, quand il en publie un."""
        return ORACLE / f"{self.id}.json"

    @property
    def gelee(self) -> bool:
        return self.instantane.exists()


def charger(strates: list[str] | None = None) -> list[Page]:
    """Les pages du manifeste, éventuellement filtrées par strate."""
    brut = json.loads(MANIFESTE.read_text(encoding="utf-8"))
    pages = [Page(**p) for p in brut]
    if strates:
        pages = [p for p in pages if p.strate in strates]
    return pages


def gelees(strates: list[str] | None = None) -> list[Page]:
    """Les seules pages exploitables : celles dont l'instantané existe."""
    return [p for p in charger(strates) if p.gelee]


def ecrire_instantane(page: Page, mhtml: str) -> int:
    """Range un instantané, compressé. Rend sa taille en octets."""
    PAGES.mkdir(parents=True, exist_ok=True)
    donnees = gzip.compress(mhtml.encode("utf-8"), compresslevel=9)
    page.instantane.write_bytes(donnees)
    return len(donnees)


def ouvrir(page: Page) -> pathlib.Path:
    """
    Décompresse un instantané et rend un chemin ouvrable par le navigateur.

    Chromium sait charger un `.mhtml` par `file://` mais pas un `.gz` ; le
    détour par un fichier temporaire coûte quelques millisecondes et évite de
    versionner trois fois le poids nécessaire.
    """
    cible = pathlib.Path(tempfile.gettempdir()) / f"corpus-{page.id}.mhtml"
    if not cible.exists():
        cible.write_bytes(gzip.decompress(page.instantane.read_bytes()))
    return cible
