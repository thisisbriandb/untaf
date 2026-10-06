"""
Candidature par formulaire — raccordement entre le dispatcher et l'agent
navigateur.

Ce module fait trois choses, et rien d'autre : il récupère le contrat de
formulaire publié par l'ATS quand il existe, il reconstitue le dossier tel
qu'il a été approuvé, et il traduit le résultat de l'agent dans le vocabulaire
du dispatcher.

Il ne décide jamais d'envoyer. Deux conditions indépendantes doivent être
réunies : le mandat autorise la candidature (c'est `decide()` qui le vérifie,
en amont), et le déploiement autorise le clic final (`browser_submit_enabled`).
Si l'une manque, le formulaire est rempli puis abandonné, et l'appelant
enregistre une simulation.
"""

import logging
import re
from typing import Any

import httpx

from app.agents.application.candidate_agent import (
    CandidateAgent, CandidatePayload,
)
from app.config import settings
from app.models.dispatch import ApplicationDispatch
from app.agents.inbox import contact_of

logger = logging.getLogger(__name__)

#: Board et identifiant d'offre dans une URL Greenhouse, quelle que soit la
#: forme de l'hôte (`boards.` et `job-boards.` coexistent).
_GREENHOUSE_URL = re.compile(
    r"(?:job-)?boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", re.I
)

_QUESTIONS_URL = (
    "https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true"
)


async def fetch_form_schema(apply_url: str) -> list[dict[str, Any]] | None:
    """
    Le contrat de formulaire publié par l'ATS, quand il en publie un.

    Greenhouse expose la liste exacte des champs sans authentification. C'est
    préférable à toute lecture du DOM : les noms y sont stables — mesurés
    identiques sur quatre boards — et on connaît d'avance ce qui est
    obligatoire, donc ce qui manquera.

    `None` quand l'ATS ne publie rien : l'agent se rabattra sur le socle commun.
    """
    match = _GREENHOUSE_URL.search(apply_url or "")
    if not match:
        return None

    board, job = match.group(1), match.group(2)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(_QUESTIONS_URL.format(board=board, job=job))
        if resp.status_code != 200:
            return None
        questions = resp.json().get("questions") or []
    except Exception as exc:  # noqa: BLE001 — l'absence de schéma n'est pas fatale
        logger.info("Schéma de formulaire indisponible pour %s : %s", apply_url, exc)
        return None

    schema: list[dict[str, Any]] = []
    for question in questions:
        fields = question.get("fields") or []
        if not fields:
            continue
        field = fields[0]
        if not field.get("name"):
            continue
        schema.append({
            "name": field["name"],
            "type": field.get("type", "input_text"),
            "required": bool(question.get("required")),
            "label": question.get("label", ""),
        })

    return schema or None


def _payload(dispatch: ApplicationDispatch, candidate) -> CandidatePayload:
    """
    Reconstitue le dossier à partir de l'instantané de l'envoi.

    Le CV et la lettre viennent du dispatch, pas du candidat : c'est cette
    version-là qui a été montrée puis approuvée. Prendre le profil courant
    enverrait un document que personne n'a validé.
    """
    full_name = (candidate.full_name or "").strip()
    first, _, last = full_name.partition(" ")

    return CandidatePayload(
        candidate_id=str(dispatch.candidate_id),
        first_name=first or full_name or "",
        last_name=last.strip() or "",
        email=contact_of(candidate),
        phone=candidate.phone or None,
        linkedin_url=candidate.linkedin_url or None,
        cover_letter_text=dispatch.letter_body or None,
        cv_pdf_bytes=dispatch.resume_blob,
        cv_filename=dispatch.resume_name or "CV.pdf",
    )


async def submit_via_browser(
    dispatch: ApplicationDispatch, candidate, apply_url: str
) -> dict[str, Any]:
    """
    Remplit le formulaire de l'offre et, si tout l'autorise, le soumet.

    Renvoie la même forme que l'envoi par email — `{ok, real, proof?, error?}` —
    pour que le dispatcher traite les deux canaux sans cas particulier.
    `real=False` signifie qu'aucune candidature n'est partie.
    """
    if not apply_url:
        return {"ok": False, "real": False, "error": "aucune URL de candidature"}
    if not dispatch.resume_blob:
        return {"ok": False, "real": False, "error": "aucun CV joint au dossier"}

    schema = await fetch_form_schema(apply_url)
    will_submit = settings.browser_submit_enabled

    agent = CandidateAgent(
        dry_run=not will_submit, headless=settings.browser_headless
    )
    result = await agent.apply_to_job(
        job_url=apply_url,
        company_name=dispatch.company_name,
        payload=_payload(dispatch, candidate),
        schema=schema,
    )

    proof = {
        "channel": "browser_form",
        "url": apply_url,
        "schema_source": "ats_api" if schema else "socle_commun",
        "filled_fields": result.filled_fields,
        "uploaded_files": result.uploaded_files,
        "unhandled_fields": result.unhandled_fields,
    }

    if result.status == "submitted":
        return {"ok": True, "real": True, "proof": proof}

    if result.status == "dry_run_success":
        # Distinguer les deux raisons de ne pas avoir envoyé : elles n'appellent
        # pas la même action de la part de l'utilisateur.
        reason = (
            "envoi par navigateur désactivé sur ce serveur "
            "(BROWSER_SUBMIT_ENABLED) — le formulaire a été rempli, rien n'a "
            "été soumis"
        )
        return {"ok": True, "real": False, "proof": proof, "error": reason}

    return {
        "ok": False,
        "real": False,
        "proof": proof,
        "error": result.error or "le formulaire n'a pas pu être rempli",
    }
