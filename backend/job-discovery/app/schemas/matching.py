"""
Matching criteria — the mandate the candidate gives the matcher.

Split in two on purpose:
  - hard filters : a posting that fails one is *discarded*, not penalised.
    Language, country and job family belong here — a French developer has no
    use for a German-language sales role, however many other boxes it ticks.
    Une famille de métier seulement déduite de l'ancien poste n'en fait pas
    partie : elle est notée, pas imposée (reconversion).
  - soft weights : award points on positive evidence only.

`MatchingCriteria.derive` builds a sane mandate from an existing profile so
candidates created before this model still get sensible filtering.
"""

from pydantic import BaseModel, Field

DEFAULT_WEIGHTS: dict[str, int] = {
    "skills": 40,
    "seniority": 15,
    "remote": 12,
    "location": 12,
    "contract": 10,
    "salary": 6,
    "freshness": 5,
    # La famille de métier n'était qu'un filtre dur : une offre non classable
    # y échappait entièrement. Elle est aussi notée, désormais.
    "family": 12,
}

TOTAL_WEIGHT = sum(DEFAULT_WEIGHTS.values())  # 100


class MatchingCriteria(BaseModel):
    """Versioned so stored mandates can be migrated later."""

    version: int = 1

    # ── Filtres durs ───────────────────────────────────────
    languages: list[str] = Field(
        default_factory=lambda: ["fr", "en"],
        description="Langues que le candidat peut lire (ISO-639-1). Une annonce "
                    "détectée dans une autre langue est écartée.",
    )
    countries: list[str] = Field(
        default_factory=list,
        description="Pays acceptés (ISO-3166-1 alpha-2). Vide = aucune contrainte.",
    )
    job_families: list[str] = Field(
        default_factory=list,
        description="Familles de métier acceptées (software, data, sales…). "
                    "Vide = aucune contrainte.",
    )
    job_families_inferred: bool = Field(
        default=False,
        description="Vrai quand la famille est déduite de l'ancien poste et non "
                    "choisie : elle compte dans le score, sans écarter d'offre.",
    )
    contract_types: list[str] = Field(
        default_factory=list,
        description="Types de contrat acceptés. Vide = aucune contrainte.",
    )
    remote_policies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Mots dans le titre qui disqualifient l'offre.",
    )
    exclude_companies: list[str] = Field(default_factory=list)
    salary_min: int | None = Field(
        default=None, description="Salaire annuel brut minimum en EUR."
    )
    max_experience_gap: float = Field(
        default=3.0,
        description="Écart maximum toléré entre l'expérience requise et celle "
                    "du candidat, en années.",
    )
    max_seniority_gap: int = Field(
        default=2,
        description="Écart maximum de séniorité vers le haut (poste plus senior "
                    "que le profil). Un poste plus junior est pénalisé, jamais écarté.",
    )

    # ── Réglages ──────────────────────────────────────────
    remote_ignores_country: bool = Field(
        default=True,
        description="Une offre 100% remote échappe-t-elle au filtre pays ?",
    )
    strict_location: bool = Field(
        default=False,
        description="Si vrai, la localisation devient un filtre dur au lieu "
                    "d'une dimension pondérée.",
    )
    weights: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    def weight(self, key: str) -> int:
        return self.weights.get(key, DEFAULT_WEIGHTS.get(key, 0))

    def total_weight(self) -> int:
        return sum(self.weight(k) for k in DEFAULT_WEIGHTS)

    @classmethod
    def derive(cls, candidate) -> "MatchingCriteria":
        """
        Build a mandate from a bare profile.

        Used when the candidate has never set criteria explicitly: without it,
        an empty mandate means "no hard filter at all" and the noise the
        rewrite is meant to remove comes straight back.
        """
        from app.agents.discovery.signals import detect_country, detect_job_family

        countries = sorted(
            {c for c in (detect_country(loc) for loc in (candidate.preferred_locations or [])) if c}
        )

        family = detect_job_family(candidate.headline, list(candidate.skills or []))

        return cls(
            countries=countries,
            job_families=[family] if family != "unknown" else [],
            job_families_inferred=family != "unknown",
            contract_types=list(candidate.preferred_contract_types or []),
            remote_policies=list(candidate.preferred_remote_policies or []),
            locations=list(candidate.preferred_locations or []),
        )

    @classmethod
    def resolve(cls, candidate) -> "MatchingCriteria":
        """
        The mandate actually applied: what the candidate stated, layered over
        what we can infer from the profile.

        The merge matters. Onboarding only asks a handful of questions — if a
        partial mandate replaced the derived one wholesale, an unanswered
        `countries` would read as "no country filter" and the noise would come
        straight back. Stating a field overrides it; staying silent keeps the
        inferred value.
        """
        derived = cls.derive(candidate)

        stored = getattr(candidate, "matching_criteria", None)
        if not stored:
            return derived

        try:
            merged = derived.model_dump()
            merged.update({k: v for k, v in stored.items() if v is not None})
            # Une famille choisie filtre ; une famille déduite ne fait que noter.
            if stored.get("job_families") is None:
                merged["job_families_inferred"] = derived.job_families_inferred
            else:
                merged["job_families_inferred"] = bool(stored.get("job_families_inferred"))
            return cls.model_validate(merged)
        except Exception:  # noqa: BLE001 — a corrupt mandate must not stop matching
            return derived
