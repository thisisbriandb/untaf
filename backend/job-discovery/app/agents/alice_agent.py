"""
Alice Agent — Orchestrator using Gemini Function Calling.

Alice is the central conversational agent. She receives a user message,
decides which tool to call (search_jobs, get_applications_status, etc.),
executes it server-side, and returns a structured response.
"""

import json
import re
import logging
from uuid import UUID

from google.genai import types
from google.genai.types import FunctionDeclaration, Tool
from sqlalchemy import select, func as sql_func

from app import llm
from app.config import settings
from app.database import async_session
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job_posting import JobPosting, PostingStatus
from app.models.application import Application, ApplicationStatus
from app.models.mission import MissionEvent, MissionEventKind
from app.agents.discovery.cv_audit import audit_candidate_profile
from app.agents.discovery.cover_letter import write_cover_letter
from app.agents.discovery.cv_editor import merge_entries, structure_cv_entries
from app.agents.mission_log import get_or_create_mission
from app.agents.persona import IDENTITY
from app.agents.alice_state import OPEN_STATUSES, load_state
from app.agents.application.feasibility import apply_mode
from app.schemas.candidate import ParsedCandidateProfile
from app.schemas.matching import MatchingCriteria

logger = logging.getLogger(__name__)


# ── Function Declarations (tools Alice can use) ──────────────────────────────

_search_jobs_fn = FunctionDeclaration(
    name="search_jobs",
    description=(
        "Recherche les offres d'emploi correspondant au profil du candidat. "
        "Utilise cette fonction quand l'utilisateur demande à voir des offres, "
        "des opportunités, ou des postes disponibles."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Mots-clés de recherche optionnels (technologie, ville, entreprise).",
            },
            "limit": {
                "type": "integer",
                "description": "Nombre maximum de résultats à retourner (défaut: 5).",
            },
        },
    },
)

_get_applications_fn = FunctionDeclaration(
    name="get_applications_status",
    description=(
        "Récupère le statut des candidatures du candidat. "
        "Utilise cette fonction quand l'utilisateur demande le statut de ses candidatures, "
        "postulations ou applications."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_get_cv_audit_fn = FunctionDeclaration(
    name="get_cv_audit",
    description=(
        "Lance un audit ATS du CV du candidat et retourne un score avec des recommandations. "
        "Utilise cette fonction quand l'utilisateur demande un audit, une analyse ou un diagnostic de son CV."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_open_cv_editor_fn = FunctionDeclaration(
    name="open_cv_editor",
    description=(
        "Ouvre l'éditeur de CV dans l'interface. "
        "Utilise cette fonction quand l'utilisateur veut modifier, éditer ou mettre à jour son CV."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_open_cover_letter_fn = FunctionDeclaration(
    name="open_cover_letter",
    description=(
        "Rédige ou ouvre l'éditeur de lettre de motivation dans le Canvas. "
        "Utilise cette fonction quand l'utilisateur demande de rédiger, préparer, créer, écrire ou ouvrir une lettre de motivation."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Nom de l'entreprise cible optionnel.",
            },
            "job_title": {
                "type": "string",
                "description": "Intitulé du poste cible optionnel.",
            },
        },
    },
)

_get_mission_fn = FunctionDeclaration(
    name="get_mission_report",
    description=(
        "Récupère l'état de la mission confiée à Alice : mandat de recherche en "
        "vigueur, niveau d'autonomie, quota, compteurs, et le journal de ce qui "
        "a été fait récemment. Utilise cette fonction quand l'utilisateur demande "
        "ce que tu as fait, où en est la recherche, un bilan, un point, un "
        "récapitulatif, ou pourquoi il n'a pas ou peu d'offres."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_trigger_agent_scan_fn = FunctionDeclaration(
    name="trigger_agent_scan",
    description=(
        "Lance l'agent d'exploration (ScraperAgent avec Playwright) pour inspecter le site carrière d'une entreprise spécifique. "
        "Utilise cette fonction si l'utilisateur demande de chercher, scrapper ou explorer les offres d'une entreprise en particulier."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Nom de l'entreprise (ex: Alan, Doctolib, Qonto).",
            },
        },
        "required": ["company_name"],
    },
)

_edit_cv_fn = FunctionDeclaration(
    name="add_to_cv",
    description=(
        "Ajoute du contenu au CV du candidat à partir d'un texte qu'il fournit. "
        "Utilise cette fonction DÈS QUE l'utilisateur colle ou décrit une "
        "expérience, un stage, une alternance, une formation, une langue ou des "
        "compétences en demandant de les ajouter à son CV. Ne réponds jamais "
        "que tu ne peux pas ajouter : structure ce qu'il t'a donné et écris-le."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "section": {
                "type": "string",
                "enum": ["experiences", "education", "languages", "skills"],
                "description": "Section du CV à compléter. Un stage ou une "
                               "alternance va dans 'experiences'.",
            },
            "content": {
                "type": "string",
                "description": "Le texte fourni par l'utilisateur, recopié "
                               "intégralement et sans reformulation.",
            },
        },
        "required": ["section", "content"],
    },
)


_JOB_QUERY = {
    "type": "string",
    "description": "Entreprise et/ou intitulé de l'offre, tels que l'utilisateur les "
                   "nomme (ex. « Doctolib », « data engineer chez Alan »).",
}

_prepare_application_fn = FunctionDeclaration(
    name="prepare_application",
    description=(
        "Prépare le dossier de candidature d'UNE offre de la liste du candidat : "
        "CV adapté à l'offre (accroche, présentation, compétences demandées en "
        "tête — tout le parcours est conservé) et lettre de motivation. Utilise-la "
        "quand l'utilisateur demande d'adapter son CV à une offre, de préparer une "
        "candidature ou un dossier, ou de « tout préparer » pour une offre."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {"job_query": _JOB_QUERY},
        "required": ["job_query"],
    },
)

_apply_to_job_fn = FunctionDeclaration(
    name="apply_to_job",
    description=(
        "Lance la candidature à UNE offre de la liste : ouvre l'offre et démarre "
        "l'envoi (Alice envoie elle-même si le canal le permet, sinon elle prépare "
        "le dossier et indique où finir). Utilise-la quand l'utilisateur dit "
        "« postule », « envoie ma candidature », « vas-y pour cette offre »."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {"job_query": _JOB_QUERY},
        "required": ["job_query"],
    },
)

_choose_cv_template_fn = FunctionDeclaration(
    name="choose_cv_template",
    description=(
        "Ouvre le choix du modèle de mise en page du CV. Utilise-la quand "
        "l'utilisateur veut changer l'apparence, le design ou le modèle de son "
        "CV, ou quand son CV est un PDF d'origine qu'il faut mettre en page pour "
        "pouvoir l'adapter."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_start_mission_fn = FunctionDeclaration(
    name="start_mission",
    description=(
        "Ouvre l'assistant de mission : Alice prépare les dossiers complets (CV "
        "adapté + lettre) des 3, 5 ou 10 meilleures offres retenues PUIS envoie ce "
        "qui peut l'être (directement, ou après validation selon le choix de "
        "l'utilisateur) ; le reste est prêt à envoyer sur le site de l'employeur. "
        "Une seule mission, une seule passe, sans durée ; l'utilisateur peut fermer "
        "l'onglet, il reçoit un e-mail à la fin. Utilise-la quand il veut que tu "
        "postules ou prépares plusieurs candidatures d'un coup, ou qu'il parle de "
        "déléguer. Le repérage des offres, lui, tourne déjà chaque matin."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_open_candidatures_fn = FunctionDeclaration(
    name="open_candidatures",
    description=(
        "Ouvre l'onglet Candidatures : file de validation des envois, dossiers "
        "prêts, relances à faire, suivi des réponses. Utilise-la quand "
        "l'utilisateur veut valider des envois, voir ses relances ou noter une "
        "réponse (entretien, refus)."
    ),
    parameters_json_schema={"type": "object", "properties": {}},
)

_alice_tools = Tool(function_declarations=[
    _prepare_application_fn,
    _apply_to_job_fn,
    _choose_cv_template_fn,
    _start_mission_fn,
    _open_candidatures_fn,
    _search_jobs_fn,
    _edit_cv_fn,
    _get_applications_fn,
    _get_cv_audit_fn,
    _get_mission_fn,
    _open_cv_editor_fn,
    _open_cover_letter_fn,
    _trigger_agent_scan_fn,
])


async def _find_application(candidate_id: UUID, query: str):
    """
    L'offre que l'utilisateur désigne, parmi les siennes. La meilleure
    correspondance l'emporte : entreprise et intitulé, puis score.
    """
    words = [w for w in re.split(r"\W+", (query or "").lower()) if len(w) > 2]
    async with async_session() as session:
        rows = (await session.execute(
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.updated_at.desc())
            .limit(300)
        )).all()

    def score(row) -> tuple[int, int]:
        app, job, company = row
        hay = f"{job.title} {company or ''}".lower()
        return (sum(1 for w in words if w in hay), app.match_score)

    ranked = sorted(rows, key=score, reverse=True)
    if not ranked or (words and score(ranked[0])[0] == 0):
        return None
    return ranked[0]


def _job_card(app, job, company) -> dict:
    return {
        "id": str(job.id),
        "title": job.title,
        "company_name": company or "Entreprise",
        "location": job.location or "Non précisé",
        "match_score": app.match_score,
        "contract_type": job.contract_type.value if job.contract_type else "unknown",
        "remote_policy": job.remote_policy.value if job.remote_policy else "unknown",
        "source_url": job.source_url,
        "status": app.status.value,
        "apply_mode": apply_mode(job),
    }


async def _execute_prepare_application(candidate_id: UUID, args: dict) -> tuple[dict, dict | None]:
    from app.agents.application.cv_completeness import SECTION_LABELS
    from app.agents.application.feasibility import APPLY_MODE_LABELS
    from app.agents.application.pack import build_pack

    found = await _find_application(candidate_id, args.get("job_query", ""))
    if not found:
        return {"found": False, "hint": "aucune offre de sa liste ne correspond ; "
                                        "propose de chercher ou de coller l'annonce"}, None
    app, job, company = found
    pack = await build_pack(candidate_id, app.id)
    if not pack:
        return {"found": False}, None
    card = _job_card(app, job, company)
    return {
        "found": True,
        "offre": f"{job.title} chez {company}",
        "nouvelle_accroche": pack.cv.headline,
        "adaptation": "accroche et présentation réécrites pour l'offre, compétences "
                      "demandées en tête, parcours complet conservé",
        "cv_sections_encore_vides": [SECTION_LABELS.get(x, x) for x in pack.missing_sections],
        "qui_envoie": APPLY_MODE_LABELS[card["apply_mode"]],
        "dossier_telechargeable": True,
    }, card


async def _execute_apply_to_job(candidate_id: UUID, args: dict) -> tuple[dict, dict | None]:
    from app.agents.application.feasibility import APPLY_MODE_LABELS

    found = await _find_application(candidate_id, args.get("job_query", ""))
    if not found:
        return {"found": False}, None
    card = _job_card(*found)
    return {
        "found": True,
        "offre": f"{card['title']} chez {card['company_name']}",
        "qui_envoie": APPLY_MODE_LABELS[card["apply_mode"]],
        "statut": "candidature lancée dans le panneau de droite ; le résultat s'y affiche",
    }, card


def _parts(response: types.GenerateContentResponse) -> list[types.Part]:
    """Les morceaux de la réponse ; vide si le modèle n'a rien renvoyé."""
    if not response.candidates or not response.candidates[0].content:
        return []
    return response.candidates[0].content.parts or []


# ── Tool execution (server-side) ─────────────────────────────────────────────

async def _execute_search_jobs(candidate_id: UUID, args: dict) -> dict:
    """
    Les offres réellement proposables au candidat.

    Deux principes tenus ici :
      - on interroge France Travail EN DIRECT avec le profil, parce qu'une
        offre stockée hier peut être pourvue aujourd'hui ;
      - les candidatures déjà envoyées sortent de la liste. « Montre-moi les
        offres » veut dire « ce qui reste à traiter », pas l'historique.
    """
    limit = args.get("limit", 5)
    query = (args.get("query") or "").strip()

    refreshed = 0
    try:
        # Rafraîchissement à la demande : la donnée métier vit chez la source,
        # pas dans notre copie locale.
        from app.agents.discovery.france_travail_task import ingest_for_candidate
        from app.agents.discovery.tasks import _match_candidate_to_existing_jobs

        report = await ingest_for_candidate(candidate_id)
        if report.get("ok"):
            refreshed = report["processed"]
            await _match_candidate_to_existing_jobs(candidate_id)
    except Exception as e:  # noqa: BLE001 — on sert le stock plutôt que rien
        logger.warning("Rafraîchissement des offres impossible : %s", e)

    async with async_session() as session:
        stmt = (
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(Application.status.in_(OPEN_STATUSES))
            .order_by(Application.match_score.desc())
            .limit(limit)
        )

        if query:
            q = f"%{query.lower()}%"
            stmt = stmt.where(
                JobPosting.title.ilike(q) | JobPosting.location.ilike(q)
            )

        rows = (await session.execute(stmt)).all()

        # Le total sert à dire la vérité quand on n'affiche qu'un extrait.
        total_stmt = (
            select(sql_func.count(Application.id))
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .where(Application.candidate_id == candidate_id)
            .where(JobPosting.status == PostingStatus.ACTIVE)
            .where(Application.status.in_(OPEN_STATUSES))
        )
        total = (await session.execute(total_stmt)).scalar() or 0

    jobs = []
    for app, job, company_name in rows:
        jobs.append({
            "id": str(job.id),
            "title": job.title,
            "company_name": company_name or "Entreprise",
            "location": job.location or "Non précisé",
            "match_score": app.match_score,
            "contract_type": job.contract_type.value if job.contract_type else "unknown",
            "remote_policy": job.remote_policy.value if job.remote_policy else "unknown",
            "source_url": job.source_url,
            "status": app.status.value,
            # Dire d'emblée qui envoie : Alice, un clic, ou le candidat sur le site.
            "apply_mode": apply_mode(job),
        })

    return {
        "jobs": jobs,
        "postulables_par_alice": sum(1 for j in jobs if j["apply_mode"] == "auto"),
        "affichees": len(jobs),
        "total_proposables": total,
        "offres_rafraichies": refreshed,
    }


async def _execute_get_applications(candidate_id: UUID) -> dict:
    """Get application statuses for this candidate."""
    async with async_session() as session:
        stmt = (
            select(Application, JobPosting, Company.name)
            .join(JobPosting, Application.job_posting_id == JobPosting.id)
            .join(Company, JobPosting.company_id == Company.id)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.updated_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        rows = result.all()

    applications = []
    for app, job, company_name in rows:
        applications.append({
            "id": str(app.id),
            "job_title": job.title,
            "company_name": company_name or "Entreprise",
            "status": app.status.value,
            "match_score": app.match_score,
        })

    # Summary counts
    async with async_session() as session:
        count_result = await session.execute(
            select(
                Application.status,
                sql_func.count(Application.id),
            )
            .where(Application.candidate_id == candidate_id)
            .group_by(Application.status)
        )
        counts = {row[0].value: row[1] for row in count_result.all()}

    return {"applications": applications, "counts": counts}


async def _execute_add_to_cv(candidate_id: UUID, args: dict) -> dict:
    """
    Écrit dans le CV à partir d'un texte fourni par le candidat.

    C'est le geste qui manquait : jusqu'ici Alice pouvait ouvrir l'éditeur mais
    pas y écrire, donc elle renvoyait l'utilisateur à une saisie manuelle des
    informations qu'il venait justement de lui donner.
    """
    section = args.get("section") or "experiences"
    raw = (args.get("content") or "").strip()

    if not raw:
        return {"error": "Aucun contenu fourni", "added": 0}

    entries = await structure_cv_entries(raw, section)
    if not entries:
        return {"error": "Contenu non exploitable", "added": 0}

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"error": "Candidat introuvable", "added": 0}

        candidate.cv_content = merge_entries(
            candidate.cv_content or {}, section, entries
        )

        # Les compétences vivent aussi sur le profil : c'est elles qui servent
        # au matching, elles doivent rester synchronisées.
        if section == "skills":
            known = {s.lower() for s in (candidate.skills or [])}
            candidate.skills = list(candidate.skills or []) + [
                s for s in entries if isinstance(s, str) and s.lower() not in known
            ]

        await session.commit()
        total = len(candidate.cv_content.get(section) or [])

    labels = {
        "experiences": "expérience", "education": "formation",
        "languages": "langue", "skills": "compétence",
    }

    return {
        "section": section,
        "added": len(entries),
        "total": total,
        "label": labels.get(section, section),
        "entries": entries[:3],
    }


async def _execute_open_cover_letter(candidate_id: UUID, args: dict) -> dict:
    """
    Rédige la lettre demandée, puis renvoie de quoi ouvrir le Canvas.

    On tente d'abord de retrouver l'annonce réelle parmi les offres du candidat :
    une lettre écrite à partir du texte de l'annonce vaut infiniment mieux qu'une
    lettre écrite à partir d'un intitulé.
    """
    job_title = (args.get("job_title") or "").strip()
    company_name = (args.get("company_name") or "").strip()

    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"error": "Candidat introuvable"}

        posting = None
        if job_title or company_name:
            stmt = (
                select(JobPosting, Company.name)
                .join(Company, JobPosting.company_id == Company.id)
                .join(Application, Application.job_posting_id == JobPosting.id)
                .where(Application.candidate_id == candidate_id)
            )
            if job_title:
                stmt = stmt.where(JobPosting.title.ilike(f"%{job_title}%"))
            elif company_name:
                stmt = stmt.where(Company.name.ilike(f"%{company_name}%"))

            row = (await session.execute(stmt.limit(1))).first()
            if row:
                posting, resolved_company = row
                company_name = company_name or resolved_company

    parsed = (posting.description_parsed or {}) if posting else {}
    cv = candidate.cv_content or {}

    letter = await write_cover_letter(
        full_name=candidate.full_name or "",
        email=candidate.email or "",
        phone=candidate.phone or "",
        linkedin_url=candidate.linkedin_url or "",
        headline=candidate.headline or "",
        skills=list(candidate.skills or []),
        summary=cv.get("summary") or candidate.resume_raw or "",
        experiences=cv.get("experiences") or [],
        education=cv.get("education") or [],
        job_title=posting.title if posting else job_title,
        company_name=company_name,
        location=(posting.location if posting else "") or "",
        tech_stack=list(parsed.get("tech_stack") or []),
        job_excerpt=(posting.description_raw or "") if posting else "",
        signature_image=candidate.signature_image,
    )

    return {
        "companyName": company_name or "Entreprise",
        "jobTitle": posting.title if posting else job_title,
        "letter": letter.model_dump(),
        "grounded_on_posting": posting is not None,
        "grounded_on_experiences": letter.grounded_on_experiences,
    }


async def _execute_get_mission(candidate_id: UUID) -> dict:
    """
    État de la mission + journal récent.

    Le mandat effectif est renvoyé tel quel : c'est ce qui permet à Alice de
    répondre « tu n'as que 2 offres parce que tu m'as demandé de l'alternance
    en France » au lieu d'un vague « je cherche ».
    """
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"error": "Candidat introuvable"}

        mission = await get_or_create_mission(session, candidate_id)
        await session.commit()

        events = (await session.execute(
            select(MissionEvent)
            .where(MissionEvent.mission_id == mission.id)
            .order_by(MissionEvent.created_at.desc())
            .limit(10)
        )).scalars().all()

        counts = dict((await session.execute(
            select(Application.status, sql_func.count(Application.id))
            .where(Application.candidate_id == candidate_id)
            .group_by(Application.status)
        )).all())

    criteria = MatchingCriteria.resolve(candidate)
    last_scan = next((e for e in events if e.kind == MissionEventKind.SCAN), None)

    autonomy_labels = {
        "propose": "je propose, tu valides chaque envoi",
        "auto_above": f"j'envoie seule au-dessus de {mission.auto_apply_min_score}%",
        "full": "je gère les envois dans les limites du mandat",
    }

    return {
        "mission": {
            "titre": mission.title,
            "statut": mission.status.value,
            "autonomie": autonomy_labels.get(mission.autonomy.value, mission.autonomy.value),
            "quota_hebdomadaire": mission.weekly_quota,
            "derniere_veille": mission.last_run_at.isoformat() if mission.last_run_at else None,
        },
        "mandat": {
            "langues": criteria.languages,
            "pays": criteria.countries,
            "metiers": criteria.job_families,
            "contrats": criteria.contract_types,
            "villes": criteria.locations,
            "rythme": criteria.remote_policies,
        },
        "compteurs": {
            "retenues": counts.get(ApplicationStatus.MATCHED, 0) + counts.get(ApplicationStatus.PENDING, 0),
            "envoyees": counts.get(ApplicationStatus.APPLIED, 0),
            "entretiens": counts.get(ApplicationStatus.INTERVIEW, 0),
        },
        "derniere_veille": (last_scan.payload or {}) if last_scan else {},
        "journal": [
            {"quand": e.created_at.isoformat(), "quoi": e.summary}
            for e in events
        ],
    }


async def _execute_cv_audit(candidate_id: UUID) -> dict:
    """Run ATS audit on the candidate's CV."""
    async with async_session() as session:
        candidate = await session.get(Candidate, candidate_id)
        if not candidate:
            return {"error": "Candidat introuvable"}

    profile = ParsedCandidateProfile(
        full_name=candidate.full_name,
        email=candidate.email,
        headline=candidate.headline,
        skills=candidate.skills or [],
        experience_years=candidate.experience_years,
        linkedin_url=candidate.linkedin_url,
        extracted_text_preview=candidate.resume_raw[:500] if candidate.resume_raw else None,
    )

    audit_result = await audit_candidate_profile(profile)
    return audit_result.model_dump()


# ── Main orchestration ────────────────────────────────────────────────────────

SYSTEM_PROMPT = IDENTITY + """

Tu travailles pour {user_name}.

MANIÈRE DE FAIRE
Tu prends en charge, tu ne conseilles pas. Tu parles au passé ou au présent
d'actions réelles : « j'ai retenu 4 offres », jamais « je pourrais chercher ».
Tu es responsable du résultat : si une recherche ne donne rien, tu dis ce que
tu changes ou ce qu'il te faut.

OUTILS — appelle-les, ne les annonce pas
Une demande qui correspond à un outil déclenche cet outil, puis tu rends compte
du résultat avec ses chiffres. Ne réponds jamais par un simple accusé de
réception.
- voir des offres → search_jobs
- adapter le CV / préparer le dossier pour UNE offre → prepare_application
- postuler, envoyer la candidature pour UNE offre → apply_to_job
- statut des candidatures → get_applications_status ; valider des envois,
  relancer, noter une réponse → open_candidatures
- bilan, point sur la recherche, ce que tu as fait, peu d'offres → get_mission_report
- préparer ou envoyer plusieurs candidatures d'un coup, déléguer → start_mission
- audit du CV → get_cv_audit
- modifier le contenu du CV → open_cv_editor ; changer sa mise en page → choose_cv_template
- l'utilisateur te DONNE du contenu pour son CV (stage, expérience, formation,
  compétences) → add_to_cv avec son texte tel quel, sans le lui faire ressaisir
- lettre de motivation seule → open_cover_letter
- explorer une entreprise précise → trigger_agent_scan

CE QUE LE LOGICIEL FAIT — et ce qu'il ne fait pas. Ne promets rien en dehors.
- Adapter un CV à une offre = réécrire l'accroche et la présentation pour ce
  poste, mettre les compétences demandées en tête. Tout le parcours est
  conservé : expériences, formation, langues. Le CV général ne change pas.
- Un CV déposé en PDF est remis en page AUTOMATIQUEMENT (modèle classique)
  dans chaque dossier : ce n'est jamais un blocage, ne demande pas de choisir
  un modèle et ne dis pas que le CV est « non modifiable ». Si l'utilisateur
  parle d'apparence, de design ou de modèle, appelle choose_cv_template (qui
  affiche les modèles à l'écran) — ne te contente jamais de lui dire d'en
  choisir un sans les lui montrer.
- Si `cv_sections_vides` n'est pas vide (expériences, formation ou
  compétences), dis-le une fois, brièvement, et propose open_cv_editor. Ne
  réclame jamais les langues ni la synthèse : elles sont facultatives, et la
  synthèse est rédigée pour chaque offre.
- Postuler : trois cas, à annoncer clairement pour chaque offre.
  · « Alice postule » — tu envoies toi-même (adresse e-mail publiée, offre
    d'alternance La bonne alternance transmise par l'API de l'État, ou ATS
    avec envoi navigateur actif) ;
  · « Prêt en un clic » — tout est rempli, le candidat confirme l'envoi ;
  · « À finir sur le site » — portail France Travail ou formulaire propre :
    aucun envoi automatique possible (compte candidat requis, tu ne manipules
    jamais ses identifiants). Tu prépares le dossier complet et il l'envoie.
  Dans tous les cas, le dossier (CV adapté + lettre + annonce) est
  téléchargeable. Privilégie les offres où tu peux postuler toi-même.
- Une mission fait tout d'un coup : elle cherche de nouvelles offres, rédige
  les dossiers, puis envoie ce qui peut partir (ou le présente d'abord, selon
  le choix fait au lancement). Il n'y a plus de mission « préparer » séparée.
- Si `envoi_email_actif` est faux, aucun e-mail ne part réellement (répétition) :
  ne dis jamais qu'une candidature est partie dans ce cas.
- Les candidatures en attente de feu vert sont dans l'onglet Candidatures
  (`candidatures_a_valider`), comme les relances (`relances_a_faire`).
- Le candidat peut coller une offre trouvée ailleurs (bouton presse-papiers
  à côté du champ de saisie) : elle rejoint sa liste et se prépare pareil.
- Tu lui écris par e-mail (fin de mission, envois, relances) selon ses réglages
  dans Paramètres.
- La conversation est sauvegardée : il la retrouve sur tous ses appareils.

RÈGLES
- Français, tutoiement, 1 à 3 phrases. Jusqu'à 5 pour un bilan chiffré.
- N'annonce que ce que les outils viennent réellement de faire. Ne promets ni
  envoi de candidature ni document que tu n'as pas produit.
- Si aucun outil ne convient, réponds naturellement en 1 ou 2 phrases.
- Ne mentionne jamais que tu es une IA.
"""


async def chat_with_alice(
    candidate_id: UUID,
    user_message: str,
    user_name: str = "l'utilisateur",
    history: list[dict] | None = None,
    extra_context: str | None = None,
) -> dict:
    """
    Point d'entrée de la conversation.

    Deux apports par rapport à un appel isolé :
      - `history` rend la conversation continue. Sans elle, Alice repartait de
        zéro à chaque message et ne pouvait pas comprendre « et les autres ? ».
      - l'état réel du système est injecté avant chaque tour, pour qu'aucun
        chiffre ne soit reconstitué de mémoire.

    L'historique porte le fil de la discussion ; les chiffres viennent
    toujours de la base. L'un ne remplace jamais l'autre.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Returning fallback.")
        return {
            "reply": "Je ne suis pas encore connectée. Configure la clé API Gemini.",
            "ui_blocks": [],
        }

    state = await load_state(candidate_id)

    config = types.GenerateContentConfig(
        tools=[_alice_tools],
        # Les outils sont exécutés ici, à la main : le SDK ne doit pas tenter
        # de les appeler lui-même.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=(
            SYSTEM_PROMPT.format(user_name=user_name)
            + "\n\nÉTAT RÉEL DU SYSTÈME À CET INSTANT — ce sont les seuls "
              "chiffres que tu as le droit de citer. S'il t'en manque un, "
              "appelle l'outil qui le donne plutôt que de l'estimer :\n"
            + json.dumps(state.as_facts(), ensure_ascii=False, indent=2)
            + (f"\n\n{extra_context}" if extra_context else "")
        ),
    )

    # L'historique n'inclut que les tours déjà joués, jamais le message courant.
    gemini_history = []
    for turn in (history or [])[-12:]:
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        role = "user" if turn.get("sender") == "user" else "model"
        gemini_history.append(
            types.Content(role=role, parts=[types.Part.from_text(text=text)])
        )

    # Gemini exige que l'historique commence par un tour utilisateur.
    while gemini_history and gemini_history[0].role != "user":
        gemini_history.pop(0)

    chat = llm.client().aio.chats.create(
        model=settings.gemini_model, config=config, history=gemini_history,
    )

    try:
        # Step 1: Send user message to Gemini
        response = await chat.send_message(user_message)

        ui_blocks = []
        final_text = ""
        # Gemini peut demander plusieurs outils dans une même réponse ; il
        # attend alors tous leurs résultats ensemble, en un seul tour.
        function_responses = []

        # Step 2: Check if Gemini wants to call a function
        for part in _parts(response):
            if part.function_call:
                fc = part.function_call
                fn_name = fc.name
                fn_args = dict(fc.args or {})

                logger.info("Alice calling tool: %s(%s)", fn_name, fn_args)

                # Execute the tool server-side
                tool_result = {}
                if fn_name == "search_jobs":
                    tool_result = await _execute_search_jobs(candidate_id, fn_args)
                    ui_blocks.append({"type": "jobs", "data": tool_result["jobs"]})

                elif fn_name == "get_applications_status":
                    tool_result = await _execute_get_applications(candidate_id)
                    ui_blocks.append({"type": "applications", "data": tool_result})

                elif fn_name == "get_cv_audit":
                    tool_result = await _execute_cv_audit(candidate_id)
                    ui_blocks.append({"type": "cv_audit", "data": tool_result})

                elif fn_name == "add_to_cv":
                    tool_result = await _execute_add_to_cv(candidate_id, fn_args)
                    if tool_result.get("added"):
                        # Le Canvas se rouvre sur la section modifiée pour que
                        # l'utilisateur voie le résultat, pas juste une phrase.
                        ui_blocks.append({
                            "type": "action",
                            "action": "open_cv_editor",
                            "data": {"section": tool_result.get("section")},
                        })

                elif fn_name == "get_mission_report":
                    tool_result = await _execute_get_mission(candidate_id)
                    ui_blocks.append({"type": "mission", "data": tool_result})

                elif fn_name == "prepare_application":
                    tool_result, card = await _execute_prepare_application(candidate_id, fn_args)
                    if card:
                        ui_blocks.append({"type": "action", "action": "open_job", "data": {"job": card}})

                elif fn_name == "apply_to_job":
                    tool_result, card = await _execute_apply_to_job(candidate_id, fn_args)
                    if card:
                        ui_blocks.append({
                            "type": "action", "action": "open_job",
                            "data": {"job": card, "autoApply": True},
                        })

                elif fn_name == "choose_cv_template":
                    tool_result = {"status": "opened"}
                    ui_blocks.append({
                        "type": "action", "action": "open_cv_editor", "data": {"pane": "design"},
                    })

                elif fn_name == "start_mission":
                    tool_result = {"status": "assistant de mission ouvert"}
                    ui_blocks.append({"type": "action", "action": "open_mission_launcher"})

                elif fn_name == "open_candidatures":
                    tool_result = {"status": "onglet Candidatures ouvert"}
                    ui_blocks.append({
                        "type": "action", "action": "select_tab", "data": {"tab": "candidatures"},
                    })

                elif fn_name == "open_cv_editor":
                    tool_result = {"status": "opened"}
                    ui_blocks.append({"type": "action", "action": "open_cv_editor"})

                elif fn_name == "trigger_agent_scan":
                    company_name = fn_args.get("company_name", "Entreprise")
                    from app.agents.discovery.scraper_agent import ScraperAgent
                    agent = ScraperAgent()
                    scan_res = await agent.run(company_name, f"https://www.{company_name.lower().replace(' ', '')}.com/careers")
                    tool_result = {"status": scan_res.status, "scraped_jobs_count": len(scan_res.jobs)}
                    ui_blocks.append({
                        "type": "action",
                        "action": "agent_scan_completed",
                        "data": {"companyName": company_name, "count": len(scan_res.jobs)}
                    })

                elif fn_name == "open_cover_letter":
                    tool_result = await _execute_open_cover_letter(candidate_id, fn_args)
                    ui_blocks.append({
                        "type": "action",
                        "action": "open_cover_letter",
                        "data": {
                            "companyName": tool_result.get("companyName"),
                            "jobTitle": tool_result.get("jobTitle"),
                            "letter": tool_result.get("letter"),
                        },
                    })
                    # La lettre elle-même n'a rien à faire dans le contexte du
                    # modèle : il la reformulerait. On ne lui rend que le fait.
                    tool_result = {
                        "status": "opened",
                        "company": tool_result.get("companyName"),
                        "job_title": tool_result.get("jobTitle"),
                        "grounded_on_posting": tool_result.get("grounded_on_posting"),
                        "grounded_on_experiences": tool_result.get("grounded_on_experiences"),
                    }

                function_responses.append(
                    types.Part.from_function_response(name=fn_name, response=tool_result)
                )

            elif part.text and not part.thought:
                final_text += part.text

        # Step 3: Feed tool results back to Gemini for final response
        if function_responses:
            follow_up = await chat.send_message(function_responses)
            final_text = follow_up.text or ""

        # Le modèle n'a ni appelé d'outil ni produit de texte. Masquer ça
        # derrière « C'est noté. » donnait une réponse qui ressemble à un
        # accusé de réception alors que rien n'a été fait — le pire des cas
        # pour un agent censé agir. On relance une fois, explicitement.
        if not final_text.strip() and not ui_blocks:
            logger.warning("Alice: réponse vide sans outil, relance forcée.")
            retry = await chat.send_message(
                "Tu n'as rien produit. Reprends la demande de l'utilisateur et "
                "APPELLE l'outil approprié maintenant, puis donne le résultat "
                "avec ses chiffres. N'accuse pas réception."
            )

            for part in _parts(retry):
                if part.function_call and part.function_call.name:
                    fc_name = part.function_call.name
                    fc_args = dict(part.function_call.args or {})
                    logger.info("Alice retry calling tool: %s", fc_name)

                    if fc_name == "search_jobs":
                        result = await _execute_search_jobs(candidate_id, fc_args)
                        ui_blocks.append({"type": "jobs", "data": result["jobs"]})
                        final_text = (
                            f"J'en ai retenu {len(result['jobs'])}. Les voici."
                            if result["jobs"]
                            else "Aucune offre de ton mandat ne ressort pour l'instant."
                        )
                    elif fc_name == "get_applications_status":
                        result = await _execute_get_applications(candidate_id)
                        ui_blocks.append({"type": "applications", "data": result})
                        final_text = f"Tu as {len(result['applications'])} candidature(s) suivie(s)."
                    elif fc_name == "get_mission_report":
                        result = await _execute_get_mission(candidate_id)
                        ui_blocks.append({"type": "mission", "data": result})
                        final_text = "Voici où en est ta mission."
                elif part.text and not part.thought:
                    final_text += part.text

        if not final_text.strip():
            final_text = (
                "Je n'ai pas réussi à traiter cette demande. Reformule-la et je m'y remets."
            )

        return {"reply": final_text.strip(), "ui_blocks": ui_blocks}

    except Exception as e:
        logger.error("Alice agent error: %s", e, exc_info=True)
        return {
            "reply": "Désolée, j'ai rencontré un problème. Réessaie dans un instant.",
            "ui_blocks": [],
        }
