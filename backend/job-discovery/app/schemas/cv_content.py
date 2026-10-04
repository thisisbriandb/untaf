"""Schémas de rédaction du contenu de CV."""

from typing import Literal

from pydantic import BaseModel, Field


class CvContentRequest(BaseModel):
    """
    Le parcours complet.

    Les expériences et la formation ne sont pas stockées côté serveur : elles
    vivent dans l'éditeur du Canvas. C'est donc au client de les transmettre —
    et c'est précisément cette matière qui manquait au générateur précédent.
    """

    full_name: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    experiences: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    languages: list[dict] = Field(default_factory=list)
    target_role: str | None = Field(
        default=None,
        description="Poste visé, pour orienter l'accroche sans la fausser.",
    )

    # ── Adaptation à une offre précise ────────────────────
    # Sans le texte de l'annonce, « adapter le CV au poste » ne veut rien dire :
    # on ne peut que réécrire à l'identique.
    job_title: str | None = None
    company_name: str | None = None
    job_excerpt: str | None = Field(
        default=None, description="Texte de l'annonce, pour cibler l'accroche."
    )
    job_skills: list[str] = Field(default_factory=list)


class CvContentResult(BaseModel):
    headline: str
    summary: str
    differentiators: list[str] = Field(
        default_factory=list,
        description="Faits du parcours qui distinguent le candidat.",
    )
    #: Réalisations reformulées pour l'offre, alignées sur l'ordre des
    #: expériences reçues : [{"highlights": [...]}, ...]. Vide sans offre.
    experiences: list[dict] = Field(default_factory=list)
    source: Literal["llm", "llm_generic", "fallback"] = "llm"
    #: Vrai quand la rédaction a été ciblée sur une offre précise.
    tailored_to_job: bool = False
