"""
Détection des prérequis d'une candidature.

Toutes les offres ne demandent pas la même chose : certaines se contentent d'un
CV, d'autres réclament une lettre, un portfolio, des prétentions salariales ou
une date de disponibilité. Deviner mal, c'est envoyer un dossier incomplet —
donc griller la candidature.

La détection est déterministe : elle lit le canal de candidature et le texte de
l'annonce. Pas d'appel LLM, pour que le résultat soit stable et explicable.
"""

import logging
import re
from dataclasses import dataclass, field

from app.models.candidate import Candidate
from app.agents.application.feasibility import assess
from app.models.job_posting import ApplyChannel, JobPosting

logger = logging.getLogger(__name__)


@dataclass
class Requirement:
    """Un élément attendu par l'offre."""

    key: str
    label: str
    #: satisfied — déjà disponible · generate — Alice peut le produire
    #: missing — il manque une action de l'utilisateur
    status: str
    detail: str = ""

    @property
    def blocking(self) -> bool:
        return self.status == "missing"


@dataclass
class ApplicationPlan:
    """Ce qu'il faut faire, et si on peut le faire."""

    channel: str
    destination: str | None
    requirements: list[Requirement] = field(default_factory=list)
    can_apply: bool = False
    blocked_reason: str | None = None
    complexity: str = "unknown"
    fallback_url: str | None = None
    summary: str = ""

    @property
    def to_generate(self) -> list[str]:
        return [r.key for r in self.requirements if r.status == "generate"]

    @property
    def missing(self) -> list[Requirement]:
        return [r for r in self.requirements if r.blocking]


#: Ce que l'annonce réclame explicitement. Volontairement conservateur : on
#: préfère rater une exigence exotique que d'en inventer une.
_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("cover_letter", "Lettre de motivation",
     re.compile(r"lettre\s+de\s+motivation|cover\s+letter|motivation\s+letter", re.I)),
    ("portfolio", "Portfolio ou lien vers tes travaux",
     re.compile(r"\bportfolio\b|book\s+en\s+ligne|github|dribbble|behance", re.I)),
    ("salary_expectation", "Prétentions salariales",
     re.compile(r"pr[ée]tentions?\s+salariales?|salary\s+expectation", re.I)),
    ("availability", "Date de disponibilité",
     re.compile(r"date\s+de\s+disponibilit|disponibilit[ée]\s*:|available\s+from", re.I)),
    ("references", "Références professionnelles",
     re.compile(r"r[ée]f[ée]rences?\s+professionnelles?|\breferences\b", re.I)),
    ("driving_licence", "Permis de conduire",
     re.compile(r"permis\s+(?:de\s+conduire|b)\b", re.I)),
]


def detect_requirements(job: JobPosting, candidate: Candidate,
                        cover_letter: dict | None = None,
                        tailoring: dict | None = None) -> ApplicationPlan:
    """Ce que cette offre demande, et ce dont on dispose déjà."""
    contact = job.contact_json or {}
    channel = (job.apply_channel.value if job.apply_channel else "unknown")

    destination = contact.get("email") or contact.get("apply_url") or job.apply_url
    text = job.description_raw or ""

    reqs: list[Requirement] = []

    # Le CV est attendu partout, sans exception.
    from app.agents.application.cv_resolver import resolve_cv
    cv_bytes, cv_name, cv_origin = resolve_cv(candidate, tailoring)
    if cv_bytes:
        origin = {
            "original": "ton document d’origine",
            "tailored": "adapté à cette offre",
            "render_failed": "ton document d’origine — la mise en page a échoué",
        }.get(cv_origin, "généré depuis ton modèle")
        reqs.append(Requirement("resume", "CV", "satisfied", f"{cv_name} — {origin}"))
    elif cv_origin == "render_failed":
        reqs.append(Requirement(
            "resume", "CV", "missing",
            "Ton CV adapté n'a pas pu être mis en page — l'équipe est prévenue, réessaie bientôt.",
        ))
    else:
        reqs.append(Requirement(
            "resume", "CV", "missing",
            "Aucun CV enregistré — dépose-le dans l'éditeur.",
        ))

    # La lettre : exigée si l'annonce le dit, sinon proposée par défaut sur
    # les canaux où elle fait la différence.
    letter_required = _PATTERNS[0][2].search(text) is not None
    if cover_letter:
        reqs.append(Requirement(
            "cover_letter", "Lettre de motivation", "satisfied",
            cover_letter.get("subject", ""),
        ))
    elif letter_required or channel == "email":
        reqs.append(Requirement(
            "cover_letter", "Lettre de motivation", "generate",
            "Je la rédige à partir de l'annonce et de ton parcours.",
        ))

    for key, label, pattern in _PATTERNS[1:]:
        if not pattern.search(text):
            continue
        if key == "portfolio" and (candidate.github_url or candidate.website_url):
            reqs.append(Requirement(key, label, "satisfied",
                                    candidate.github_url or candidate.website_url))
        else:
            reqs.append(Requirement(
                key, label, "missing",
                "Demandé par l'annonce — je ne peux pas l'inventer.",
            ))

    plan = ApplicationPlan(channel=channel, destination=destination, requirements=reqs)

    # Le verdict d'automatisation vient d'un seul endroit, pour que le message
    # affiché soit le même partout.
    # Le CV qui partira, pas seulement un PDF déposé : un parcours saisi
    # suffit à composer le CV adapté.
    verdict = assess(job, has_resume=bool(cv_bytes))
    plan.complexity = verdict.complexity
    plan.fallback_url = verdict.fallback_url
    plan.summary = verdict.summary

    if verdict.automatable:
        plan.can_apply = not any(r.blocking for r in reqs)
        plan.blocked_reason = None if plan.can_apply else "il manque des éléments obligatoires"
    else:
        plan.can_apply = False
        plan.blocked_reason = verdict.blockers[0] if verdict.blockers else verdict.summary

    return plan
