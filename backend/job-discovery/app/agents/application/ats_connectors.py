"""
Connecteurs de candidature ATS — Greenhouse, Lever, Ashby.

Trois plateformes, trois niveaux de certitude différents, vérifiés en
interrogeant leurs API publiques réelles (lecture seule, sans conséquence) :

- **Greenhouse** publie le schéma exact du formulaire
  (`GET .../jobs/{id}?questions=true`) : on sait avec certitude quels champs
  sont requis et lesquels ne peuvent pas être pré-remplis automatiquement
  (`first_name`, `last_name`, `email`, `phone`, `resume`, `cover_letter` sont
  le socle stable documenté dans le README ; le reste, ce sont des questions
  propres à l'offre).
- **Lever** et **Ashby** ne publient aucun schéma de formulaire via leur API
  publique — seulement les métadonnées de l'offre (vérifié : leurs endpoints
  de listing n'exposent ni `questions` ni équivalent). Le socle est un
  contrat stable documenté par ces plateformes, mais l'existence de
  questions personnalisées sur une offre donnée ne peut pas être vérifiée
  sans charger la page de candidature elle-même — hors périmètre ici. Ces
  deux connecteurs restent donc honnêtement non-automatisables tant que ce
  angle mort n'est pas comblé.

Rien n'est jamais soumis pour de vrai depuis ce module : `submit_ats_application`
retourne toujours un résultat simulé (`real: False`), sur le même modèle que
`email_sender.py`. La construction de la requête réelle (`submit_url`,
mapping des champs) doit être vérifiée manuellement contre un board vivant
avant qu'un futur changement n'active un envoi effectif.
"""

import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job_posting import ApplyChannel, JobPosting

logger = logging.getLogger(__name__)

GREENHOUSE_JOB_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"

#: Champs du socle, stables sur les boards testés (voir README).
BASE_FIELD_NAMES = {"first_name", "last_name", "email", "phone", "resume", "cover_letter"}

#: Motif partagé par Lever et Ashby : ni l'un ni l'autre ne publie le schéma
#: du formulaire via son API publique.
_NO_SCHEMA_BLOCKER = (
    "{platform} ne publie pas le schéma du formulaire via son API publique — "
    "impossible de garantir l'absence de question personnalisée non "
    "pré-remplie sur cette offre précise."
)


@dataclass
class ApplicationPlan:
    """Ce qu'on soumettrait, et ce qui manque pour le faire honnêtement."""

    platform: str
    automatable: bool
    mapped_fields: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    submit_url: str | None = None


def _candidate_field_values(candidate: Candidate, letter_body: str | None) -> dict[str, str]:
    parts = (candidate.full_name or "").strip().split(" ", 1)
    return {
        "first_name": parts[0] if parts else "",
        "last_name": parts[1] if len(parts) > 1 else "",
        "email": candidate.email or "",
        "phone": candidate.phone or "",
        "resume": "(pièce jointe)",
        "cover_letter": (letter_body or "")[:200],
    }


async def _fetch_greenhouse_schema(board: str, job_external_id: str) -> dict | None:
    url = GREENHOUSE_JOB_API.format(board=board, job_id=job_external_id)
    async with httpx.AsyncClient(
        timeout=settings.scrape_request_timeout,
        headers={"User-Agent": settings.scrape_user_agent},
    ) as client:
        try:
            resp = await client.get(url, params={"questions": "true"})
            if resp.status_code != 200:
                logger.warning(
                    "Greenhouse schema %s/%s: HTTP %d", board, job_external_id, resp.status_code
                )
                return None
            return resp.json()
        except httpx.HTTPError as e:
            logger.warning(
                "Greenhouse schema fetch failed for %s/%s: %s", board, job_external_id, e
            )
            return None


async def build_greenhouse_plan(
    job: JobPosting, company: Company, candidate: Candidate, letter_body: str | None
) -> ApplicationPlan:
    """
    Lit le formulaire réel de l'offre et détermine ce qui peut être
    pré-rempli automatiquement à partir du socle candidat, et ce qui bloque.
    """
    if not company.ats_slug:
        return ApplicationPlan(
            "greenhouse", False,
            blockers=["Board Greenhouse non identifié pour cette entreprise."],
        )

    schema = await _fetch_greenhouse_schema(company.ats_slug, job.external_id)
    if schema is None:
        return ApplicationPlan(
            "greenhouse", False,
            blockers=["Formulaire Greenhouse introuvable — offre peut-être retirée."],
        )

    values = _candidate_field_values(candidate, letter_body)
    mapped: dict[str, str] = {}
    blockers: list[str] = []

    for q in schema.get("questions") or []:
        label = q.get("label") or "Question sans intitulé"
        required = bool(q.get("required"))
        field_names = [f.get("name") for f in (q.get("fields") or []) if f.get("name")]
        mappable = next((n for n in field_names if n in values), None)

        if mappable:
            mapped[mappable] = values[mappable]
        elif required:
            blockers.append(f"Question requise sans réponse automatisable : « {label} »")

    return ApplicationPlan(
        "greenhouse",
        automatable=not blockers,
        mapped_fields=mapped,
        blockers=blockers,
        submit_url=(
            f"https://boards.greenhouse.io/embed/job_app"
            f"?for={company.ats_slug}&token={job.external_id}"
        ),
    )


def build_lever_plan(
    job: JobPosting, candidate: Candidate, letter_body: str | None
) -> ApplicationPlan:
    values = _candidate_field_values(candidate, letter_body)
    return ApplicationPlan(
        "lever",
        automatable=False,
        mapped_fields={
            "name": f"{values['first_name']} {values['last_name']}".strip(),
            "email": values["email"],
            "phone": values["phone"],
        },
        blockers=[_NO_SCHEMA_BLOCKER.format(platform="Lever")],
        submit_url=job.apply_url,
    )


def build_ashby_plan(
    job: JobPosting, candidate: Candidate, letter_body: str | None
) -> ApplicationPlan:
    values = _candidate_field_values(candidate, letter_body)
    return ApplicationPlan(
        "ashby",
        automatable=False,
        mapped_fields={
            "name": f"{values['first_name']} {values['last_name']}".strip(),
            "email": values["email"],
        },
        blockers=[_NO_SCHEMA_BLOCKER.format(platform="Ashby")],
        submit_url=job.apply_url,
    )


async def build_application_plan(
    job: JobPosting, company: Company, candidate: Candidate, letter_body: str | None
) -> ApplicationPlan:
    """Point d'entrée unique — route vers le bon connecteur selon l'offre."""
    if job.apply_channel == ApplyChannel.GREENHOUSE_API:
        return await build_greenhouse_plan(job, company, candidate, letter_body)
    if job.apply_channel == ApplyChannel.LEVER_API:
        return build_lever_plan(job, candidate, letter_body)
    if job.apply_channel == ApplyChannel.ASHBY_API:
        return build_ashby_plan(job, candidate, letter_body)

    channel_name = job.apply_channel.value if job.apply_channel else "unknown"
    return ApplicationPlan(channel_name, False, blockers=[f"Canal « {channel_name} » non pris en charge."])


async def submit_ats_application(plan: ApplicationPlan) -> dict:
    """
    Toujours simulé — aucune requête n'est jamais postée vers un vrai board
    depuis cette fonction. Miroir du contrat de `email_sender.send_application_email` :
    `ok` dit si le dossier est complet, `real` dit si quelque chose est
    effectivement parti (jamais vrai ici).
    """
    if not plan.automatable:
        return {
            "ok": False,
            "real": False,
            "error": "; ".join(plan.blockers) or "Formulaire non automatisable.",
        }

    return {
        "ok": True,
        "real": False,
        "simulated_reason": (
            f"Connecteur {plan.platform} en simulation — aucune candidature "
            f"n'est encore soumise pour de vrai à un board réel."
        ),
        "proof": {
            "simulated": True,
            "platform": plan.platform,
            "submit_url": plan.submit_url,
            "fields_mapped": sorted(plan.mapped_fields.keys()),
        },
    }
