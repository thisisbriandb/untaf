"""
Matching engine.

The previous version started at 100 and subtracted penalties, which meant an
offer we knew nothing about kept nearly all its points: a German sales role
with no parsed tech stack outscored a well-understood Python job. Absence of
information was rewarded.

This version:
  1. runs hard filters first — a posting that fails one is discarded with a
     reason, never scored;
  2. awards points only on positive evidence, and only for dimensions where
     both sides actually have data;
  3. tracks coverage, so a posting we could barely evaluate cannot reach the
     top of the list.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import inspect

from app.agents.discovery.signals import (
    contract_from_title,
    days_since,
    detect_country,
    detect_job_family,
    is_generic_posting,
    training_org_evidence,
    detect_language,
    detect_seniority,
    seniority_distance,
    seniority_from_experience,
    seniority_gap,
)
from app.agents.discovery.skills import canonical_set, skill_coverage
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.schemas.matching import MatchingCriteria

logger = logging.getLogger(__name__)

# Below this share of evaluable weight we simply do not know enough to rank
# the posting. Anchored just under the skills weight (40/100) so a job whose
# tech stack could not be parsed and that matches nothing else is dropped
# instead of surfacing at 90.
MIN_COVERAGE = 0.30

#: Vocabulaires réconciliés. Le qualifieur LLM dit « internship », l'onboarding
#: dit « stage », France Travail dit « SAI » — sans cette table, un mandat
#: « stage » ne rencontre jamais une offre de stage.
CONTRACT_ALIASES = {
    "internship": "stage", "stage": "stage", "stagiaire": "stage",
    "apprenticeship": "alternance", "alternance": "alternance",
    "permanent": "cdi", "cdi": "cdi", "full-time": "cdi",
    "temporary": "cdd", "cdd": "cdd", "fixed-term": "cdd",
    "freelance": "freelance", "contractor": "freelance", "independent": "freelance",
    "interim": "interim", "intérim": "interim",
}

#: Un contrat non déterminé ne vaut pas un contrat conforme. Sans cette
#: nuance, une offre vague passait le filtre là où une offre correctement
#: qualifiée mais non conforme était rejetée — l'imprécision était récompensée.
UNKNOWN_CONTRACT_CREDIT = 0.35

#: Même logique pour la famille de métier.
UNKNOWN_FAMILY_CREDIT = 0.3


def normalize_contract(value: str | None) -> str:
    return CONTRACT_ALIASES.get((value or "").strip().lower(), (value or "unknown").lower())

# How much an incomplete evaluation is allowed to be worth: a posting scored
# on a third of the criteria tops out around 76, never 100.
COVERAGE_FLOOR = 0.60

FRESHNESS_FULL_DAYS = 7.0
FRESHNESS_ZERO_DAYS = 45.0

# Number of required skills below which the skills dimension carries reduced
# weight. Matching the single skill of a posting that only mentions "SQL" is
# not evidence of a fit; matching 4 of 6 is. Without this, a thin tech stack
# yields a 100% ratio and pockets the full 40 points.
SKILLS_FULL_EVIDENCE = 4


@dataclass
class Dimension:
    weight: int
    ratio: float
    detail: str


@dataclass
class MatchResult:
    score: int
    accepted: bool
    rejections: list[str] = field(default_factory=list)
    breakdown: dict[str, dict] = field(default_factory=dict)
    signals: dict[str, Any] = field(default_factory=dict)
    coverage: float = 0.0

    def to_metadata(self) -> dict:
        """Compact form stored on the Application so the score is explainable."""
        return {
            "score": self.score,
            "accepted": self.accepted,
            "coverage": round(self.coverage, 3),
            "rejections": self.rejections,
            "breakdown": self.breakdown,
            "signals": self.signals,
        }


def _contains_any(text: str, needles: list[str]) -> str | None:
    low = text.lower()
    for n in needles:
        n = (n or "").strip().lower()
        if n and n in low:
            return n
    return None


def _safe_company_name(job: JobPosting) -> str:
    """
    Company name without ever triggering a lazy load.

    `JobPosting.company` is a plain (lazy="select") relationship: touching it
    from async code outside a greenlet raises MissingGreenlet and kills the
    whole matching run. Callers should pass the name explicitly; this is the
    fallback for the case where the relationship happens to be loaded already.
    """
    try:
        state = inspect(job)
        if "company" in state.unloaded:
            return ""
        return getattr(job.company, "name", "") or ""
    except Exception:  # noqa: BLE001 — a missing name must never stop matching
        return ""


def evaluate_match(
    candidate: Candidate,
    job: JobPosting,
    parsed: dict | None = None,
    criteria: MatchingCriteria | None = None,
    company_name: str | None = None,
) -> MatchResult:
    parsed = parsed or job.description_parsed or {}
    criteria = criteria or MatchingCriteria.resolve(candidate)

    title = job.title or ""
    tech_stack = parsed.get("tech_stack") or list(job.tech_stack or [])

    # ── Signaux dérivés ────────────────────────────────────
    job_language = detect_language(job.description_raw)
    job_country = detect_country(job.location)
    job_family = detect_job_family(title, tech_stack)
    job_remote = str(parsed.get("remote_policy") or getattr(job.remote_policy, "value", "unknown")).lower()
    job_contract = normalize_contract(
        parsed.get("contract_type") or getattr(job.contract_type, "value", "unknown")
    )
    # L'intitulé prime sur le champ contrat : « STAGE - Développeur » publié
    # en CDI est un stage, quoi qu'en dise la métadonnée de la source.
    titled = contract_from_title(title)
    if titled:
        job_contract = titled
    years_required = parsed.get("experience_years_required")
    job_seniority = detect_seniority(title, years_required)
    wanted_contracts = [normalize_contract(c) for c in (criteria.contract_types or [])]

    # Qui vise une alternance ou un stage, ou change de métier, repart du
    # début : ses années passées ne font pas de lui un « lead » dans le
    # nouveau métier.
    past_family = detect_job_family(candidate.headline, list(candidate.skills or []))
    in_training = any(c in ("alternance", "stage") for c in wanted_contracts)
    reconversion = bool(
        criteria.job_families and not criteria.job_families_inferred
        and past_family != "unknown" and past_family not in criteria.job_families
    )
    if in_training:
        candidate_seniority = "intern"
    elif reconversion:
        candidate_seniority = "junior"
    else:
        candidate_seniority = seniority_from_experience(candidate.experience_years)
    fresh_start = in_training or reconversion
    is_remote = job_remote == "remote"

    signals: dict[str, Any] = {
        "language": job_language,
        "country": job_country,
        "family": job_family,
        "remote_policy": job_remote,
        "contract_type": job_contract,
        "job_seniority": job_seniority,
        "candidate_seniority": candidate_seniority,
        "experience_years_required": years_required,
        "reconversion": reconversion,
        "in_training": in_training,
    }

    # ── 1. Filtres durs ────────────────────────────────────
    rejections: list[str] = []

    if job_language != "unknown" and criteria.languages:
        if job_language not in criteria.languages:
            rejections.append(f"annonce en '{job_language}', hors des langues du mandat")

    if criteria.countries and job_country and job_country not in criteria.countries:
        if not (is_remote and criteria.remote_ignores_country):
            rejections.append(f"pays '{job_country}' hors du mandat")

    if is_generic_posting(title):
        rejections.append("annonce générique (candidature spontanée, vivier) : pas un poste")

    # Une école qui « recrute » des alternants remplit sa promotion : ce n'est
    # pas un poste. Deux indices concordants → écartée ; un seul → signalée.
    if job_contract in ("alternance", "stage") or re.search(r"alternan|apprenti", title, re.I):
        level, motif = training_org_evidence(
            company_name if company_name is not None else _safe_company_name(job),
            job.description_raw, parsed.get("employer"),
        )
        if level == "strong":
            rejections.append(f"organisme de formation : {motif}")
        elif level == "weak":
            signals["training_org"] = motif

    family_known = job_family != "unknown"
    # Seule une famille choisie écarte une offre ; déduite de l'ancien poste,
    # elle ne fait que noter (dimension « family » plus bas).
    if criteria.job_families and family_known and not criteria.job_families_inferred:
        if job_family not in criteria.job_families:
            rejections.append(f"métier '{job_family}' hors du mandat")

    contract_known = job_contract not in ("unknown", "other", "")
    if wanted_contracts and contract_known and job_contract not in wanted_contracts:
        rejections.append(f"contrat '{job_contract}' hors du mandat")

    if criteria.remote_policies and job_remote != "unknown":
        if job_remote not in [r.lower() for r in criteria.remote_policies]:
            rejections.append(f"modalité '{job_remote}' hors du mandat")

    hit = _contains_any(title, criteria.exclude_keywords)
    if hit:
        rejections.append(f"mot exclu dans le titre : '{hit}'")

    if criteria.exclude_companies:
        name = company_name if company_name is not None else _safe_company_name(job)
        hit = _contains_any(name, criteria.exclude_companies)
        if hit:
            rejections.append(f"entreprise exclue : '{hit}'")

    if criteria.salary_min is not None:
        salary_max = parsed.get("salary_max") or parsed.get("salary_min")
        if salary_max and salary_max < criteria.salary_min:
            rejections.append(
                f"salaire max {salary_max}€ sous le plancher {criteria.salary_min}€"
            )

    if years_required is not None and candidate.experience_years is not None:
        gap = years_required - candidate.experience_years
        if gap > criteria.max_experience_gap:
            rejections.append(
                f"{years_required:.0f} ans requis contre {candidate.experience_years:.0f} "
                f"(écart {gap:.0f} > {criteria.max_experience_gap:.0f})"
            )

    # Seul un poste trop senior est écarté. Un poste plus junior que le profil
    # est pénalisé dans le score (dimension « seniority »), jamais rejeté :
    # c'est souvent exactement ce que vise une reconversion.
    if not fresh_start and seniority_gap(job_seniority, candidate_seniority) > criteria.max_seniority_gap:
        rejections.append(
            f"poste '{job_seniority}' trop senior pour un profil '{candidate_seniority}'"
        )

    if criteria.strict_location and criteria.locations and not is_remote:
        loc = (job.location or "").lower()
        if not any((p or "").lower() in loc for p in criteria.locations if p):
            rejections.append(f"localisation '{job.location}' hors du mandat")

    if rejections:
        return MatchResult(
            score=0, accepted=False, rejections=rejections, signals=signals
        )

    # ── 2. Dimensions pondérées ────────────────────────────
    dims: dict[str, Dimension] = {}

    # Compétences — la seule dimension qui exige des données des deux côtés.
    required = canonical_set(tech_stack)
    owned = canonical_set(candidate.skills)
    if required and owned:
        ratio, matched, missing = skill_coverage(required, owned)
        # Weight by how much the posting actually tells us, so a thin stack
        # also drags coverage — and therefore the confidence factor — down.
        evidence = min(1.0, len(required) / SKILLS_FULL_EVIDENCE)
        dims["skills"] = Dimension(
            round(criteria.weight("skills") * evidence),
            ratio,
            f"{len(matched)}/{len(required)} compétences couvertes"
            + (f" — manque : {', '.join(missing[:5])}" if missing else "")
            + (f" (preuve faible : {len(required)} techno)" if evidence < 1 else ""),
        )

    # Séniorité — proche = plein pot, un cran d'écart = la moitié.
    distance = seniority_distance(job_seniority, candidate_seniority)
    dims["seniority"] = Dimension(
        criteria.weight("seniority"),
        max(0.0, 1.0 - 0.5 * distance),
        f"poste '{job_seniority}' vs profil '{candidate_seniority}'",
    )

    if criteria.remote_policies and job_remote != "unknown":
        ok = job_remote in [r.lower() for r in criteria.remote_policies]
        dims["remote"] = Dimension(
            criteria.weight("remote"), 1.0 if ok else 0.0, f"modalité '{job_remote}'"
        )

    if criteria.locations and not criteria.strict_location:
        if is_remote:
            dims["location"] = Dimension(
                criteria.weight("location"), 1.0, "poste 100% remote"
            )
        elif job.location:
            loc = job.location.lower()
            ok = any((p or "").lower() in loc or loc in (p or "").lower()
                     for p in criteria.locations if p)
            dims["location"] = Dimension(
                criteria.weight("location"), 1.0 if ok else 0.0, job.location
            )

    if wanted_contracts:
        # Un contrat inconnu n'est plus un laissez-passer : il rapporte un
        # crédit partiel, jamais le plein score d'une correspondance établie.
        if contract_known:
            ratio = 1.0 if job_contract in wanted_contracts else 0.0
            detail = f"contrat '{job_contract}'"
        else:
            ratio = UNKNOWN_CONTRACT_CREDIT
            detail = "contrat non précisé dans l'annonce"
        dims["contract"] = Dimension(criteria.weight("contract"), ratio, detail)

    if criteria.salary_min is not None:
        salary_min = parsed.get("salary_min")
        if salary_min:
            ratio = min(1.0, salary_min / criteria.salary_min) if criteria.salary_min else 1.0
            dims["salary"] = Dimension(
                criteria.weight("salary"), ratio, f"à partir de {salary_min}€"
            )

    # Un métier indéterminé n'est pas un métier conforme. Sans cette
    # dimension, « Stage - Community Engagement » passait aussi librement
    # qu'une offre de développeur, faute d'être classable.
    if criteria.job_families:
        dims["family"] = Dimension(
            criteria.weight("family"),
            1.0 if (family_known and job_family in criteria.job_families) else (
                UNKNOWN_FAMILY_CREDIT if not family_known else 0.0
            ),
            f"métier '{job_family}'" if family_known else "métier non identifiable",
        )

    age = days_since(job.first_seen_at)
    if age is not None:
        if age <= FRESHNESS_FULL_DAYS:
            ratio = 1.0
        elif age >= FRESHNESS_ZERO_DAYS:
            ratio = 0.0
        else:
            ratio = 1.0 - (age - FRESHNESS_FULL_DAYS) / (FRESHNESS_ZERO_DAYS - FRESHNESS_FULL_DAYS)
        dims["freshness"] = Dimension(
            criteria.weight("freshness"), ratio, f"publiée il y a {age:.0f} j"
        )

    # ── 3. Score ───────────────────────────────────────────
    possible = sum(d.weight for d in dims.values())
    total = criteria.total_weight() or 1
    coverage = possible / total

    if possible == 0 or coverage < MIN_COVERAGE:
        return MatchResult(
            score=0,
            accepted=False,
            rejections=[
                f"information insuffisante pour évaluer (couverture {coverage:.0%} "
                f"< {MIN_COVERAGE:.0%})"
            ],
            breakdown={k: {"weight": d.weight, "ratio": round(d.ratio, 3), "detail": d.detail}
                       for k, d in dims.items()},
            signals=signals,
            coverage=coverage,
        )

    earned = sum(d.weight * d.ratio for d in dims.values())
    raw = earned / possible
    confidence = COVERAGE_FLOOR + (1 - COVERAGE_FLOOR) * coverage
    score = int(round(100 * raw * confidence))

    return MatchResult(
        score=max(0, min(100, score)),
        accepted=True,
        breakdown={k: {"weight": d.weight, "ratio": round(d.ratio, 3), "detail": d.detail}
                   for k, d in dims.items()},
        signals=signals,
        coverage=coverage,
    )


def compute_match_score(candidate: Candidate, job: JobPosting, parsed_details: dict) -> int:
    """Backwards-compatible shim — returns 0 for a rejected posting."""
    return evaluate_match(candidate, job, parsed_details).score
