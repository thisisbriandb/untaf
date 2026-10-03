"""
API routes for Candidates — register and manage job seeker profiles.
"""

import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, require_user
from app.config import settings
from app.database import get_db
from app.models.candidate import Candidate
from app.schemas.candidate import (
    CandidateCreate, CandidateOut, CandidateUpdate, CvDesignOut, CvDesignUpdate,
    EffectiveCriteriaOut, ParsedCandidateProfile, CVAuditResult, CVRenderRequest,
)
from app.schemas.matching import MatchingCriteria
from app.agents.discovery.tasks import _match_candidate_to_existing_jobs
from app.agents.discovery.resume_parser import parse_resume, parse_linkedin_url
from app.agents.discovery.cv_audit import audit_candidate_profile
from app.agents.discovery.cv_writer import write_cv_content
from app.schemas.cv_content import CvContentRequest, CvContentResult
from app.schemas.cover_letter import CoverLetterResult, SignatureUpdate
from app.agents.discovery.letter_render import render_letter_pdf


import sys
from pathlib import Path
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# Import cv-engine render & compile functions
CV_ENGINE_PATH = Path(__file__).resolve().parents[3] / "cv-engine"
if str(CV_ENGINE_PATH) not in sys.path:
    sys.path.append(str(CV_ENGINE_PATH))

try:
    from backend.renderer import render_cv
    from backend.compiler import compile_typst_to_pdf, compile_typst_to_svg
    HAS_CV_ENGINE = True
except Exception as e:
    HAS_CV_ENGINE = False
    logger.warning(f"cv-engine non chargé: {e}")


router = APIRouter(prefix="/candidates", tags=["candidates"])

MAX_RESUME_BYTES = 10 * 1024 * 1024
#: ~1 Mo de data URL — largement au-delà d'une signature manuscrite.
MAX_SIGNATURE_CHARS = 1_400_000




@router.get("/", response_model=list[CandidateOut])
async def list_candidates(
    email: str | None = Query(
        default=None,
        description="Filtre exact sur l'email — permet de retrouver un profil "
                    "existant plutôt que de buter sur un 409 à la création.",
    ),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """
    Les profils visibles par l'appelant : le sien, et lui seul. En
    développement sans authentification, tous (filtrables par email).
    """
    query = select(Candidate)
    if not settings.auth_disabled:
        query = query.where(Candidate.auth_user_id == user.id)
    if email:
        # Case-insensitive: emails are stored as typed, not normalised.
        query = query.where(func.lower(Candidate.email) == email.strip().lower())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    candidates = result.scalars().all()
    return candidates


def _apply_create(candidate: Candidate, data: CandidateCreate) -> None:
    for key in (
        "full_name", "phone", "github_url", "linkedin_url", "website_url",
        "headline", "skills", "experience_years", "preferred_locations",
        "preferred_remote_policies", "preferred_contract_types", "resume_raw",
    ):
        setattr(candidate, key, getattr(data, key))
    candidate.matching_criteria = (
        data.matching_criteria.model_dump(mode="json", exclude_unset=True)
        if data.matching_criteria else None
    )


@router.post("/", response_model=CandidateOut, status_code=201)
async def create_candidate(
    data: CandidateCreate,
    background_tasks: BackgroundTasks,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_user),
):
    """
    Crée le profil de l'utilisateur connecté — ou le met à jour s'il existe.

    Avec authentification, l'adresse du profil est celle du compte, quelle que
    soit celle envoyée : sinon on pourrait créer un profil au nom d'un autre.
    Refaire l'onboarding reprend le profil existant au lieu d'un 409.
    """
    from app.agents.account import claim_candidate

    email = data.email if settings.auth_disabled else (user.email or data.email)

    if settings.auth_disabled:
        existing = await db.scalar(select(Candidate).where(Candidate.email == email))
        if existing:
            raise HTTPException(409, f"Candidate with email '{email}' already exists")
    else:
        existing = await claim_candidate(db, user)
        if existing is None and await db.scalar(
            select(Candidate.id).where(func.lower(Candidate.email) == email.lower())
        ):
            # Adresse prise par un profil rattaché à un autre compte.
            raise HTTPException(409, "Cette adresse est déjà liée à un autre compte.")
        if existing is not None:
            _apply_create(existing, data)
            await db.commit()
            await db.refresh(existing)
            background_tasks.add_task(_match_candidate_to_existing_jobs, existing.id)
            response.status_code = 200
            return existing

    candidate = Candidate(
        email=email,
        auth_user_id=None if settings.auth_disabled else user.id,
    )
    _apply_create(candidate, data)
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    # Schedule the matching flow in the background
    background_tasks.add_task(_match_candidate_to_existing_jobs, candidate.id)

    return candidate


@router.get("/{candidate_id}", response_model=CandidateOut)
async def get_candidate(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a candidate profile by ID."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")
    return candidate


@router.put("/{candidate_id}", response_model=CandidateOut)
async def update_candidate(
    candidate_id: UUID,
    data: CandidateUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing candidate profile."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    # mode="json" so a nested MatchingCriteria lands in JSONB as a plain dict.
    update_data = data.model_dump(exclude_unset=True, mode="json")
    for key, value in update_data.items():
        setattr(candidate, key, value)

    await db.commit()
    await db.refresh(candidate)

    # Anything that feeds the matcher invalidates the existing scores.
    if update_data.keys() & {
        "skills", "experience_years", "headline", "matching_criteria",
        "preferred_locations", "preferred_remote_policies", "preferred_contract_types",
    }:
        background_tasks.add_task(_match_candidate_to_existing_jobs, candidate.id)

    return candidate


@router.get("/{candidate_id}/criteria", response_model=EffectiveCriteriaOut)
async def get_matching_criteria(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Le mandat de matching réellement appliqué.

    `is_explicit` à false signifie qu'il est dérivé du profil (pays déduits des
    localisations souhaitées, famille de métier déduite du titre) et non choisi
    par le candidat.
    """
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    return EffectiveCriteriaOut(
        criteria=MatchingCriteria.resolve(candidate),
        is_explicit=candidate.matching_criteria is not None,
    )


@router.put("/{candidate_id}/criteria", response_model=EffectiveCriteriaOut)
async def set_matching_criteria(
    candidate_id: UUID,
    criteria: MatchingCriteria,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Fixer le mandat et relancer le matching sur le stock d'offres existant."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    # Only what the caller actually stated is stored, so unanswered fields keep
    # falling back to what we infer from the profile.
    candidate.matching_criteria = criteria.model_dump(mode="json", exclude_unset=True)
    await db.commit()
    await db.refresh(candidate)

    background_tasks.add_task(_match_candidate_to_existing_jobs, candidate.id)

    return EffectiveCriteriaOut(criteria=criteria, is_explicit=True)


@router.post("/{candidate_id}/resume", response_model=dict)
async def upload_resume(
    candidate_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Conserve le CV tel que déposé.

    Tant que ce fichier existe, la présentation par défaut reste « originale » :
    on ne bascule sur un modèle que si le candidat le demande.
    """
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Le fichier transmis est vide.")
    if len(contents) > MAX_RESUME_BYTES:
        raise HTTPException(413, "Le CV dépasse la taille maximale (10 Mo).")

    candidate.resume_file = contents
    candidate.resume_filename = file.filename or "cv.pdf"
    candidate.resume_mime = file.content_type or "application/pdf"

    # Premier dépôt : la présentation d'origine devient la référence.
    if not candidate.cv_design:
        candidate.cv_design = {"mode": "original"}

    await db.commit()

    return {
        "filename": candidate.resume_filename,
        "size": len(contents),
        "mode": (candidate.cv_design or {}).get("mode"),
    }


@router.get("/{candidate_id}/resume")
async def get_resume(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Restitue le CV d'origine, pour l'afficher tel quel dans le Canvas."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")
    if not candidate.resume_file:
        raise HTTPException(404, "Aucun CV d'origine enregistré.")

    return Response(
        content=candidate.resume_file,
        media_type=candidate.resume_mime or "application/pdf",
        headers={
            "Content-Disposition":
                f'inline; filename="{candidate.resume_filename or "cv.pdf"}"',
            "Cache-Control": "private, max-age=60",
        },
    )


@router.get("/{candidate_id}/cv-design", response_model=CvDesignOut)
async def get_cv_design(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Présentation choisie, et si un CV d'origine est disponible."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    stored = candidate.cv_design or {}
    has_original = candidate.resume_file is not None

    return CvDesignOut(
        # Sans choix explicite, on reste sur l'original quand il existe.
        mode=stored.get("mode") or ("original" if has_original else "template"),
        template_id=stored.get("template_id"),
        color_hex=stored.get("color_hex"),
        show_photo=stored.get("show_photo", False),
        has_original=has_original,
        original_filename=candidate.resume_filename,
        is_explicit=bool(stored),
    )


@router.put("/{candidate_id}/cv-design", response_model=CvDesignOut)
async def set_cv_design(
    candidate_id: UUID,
    design: CvDesignUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre un choix de présentation.

    Modèle et couleur sont indépendants : choisir un modèle n'impose pas sa
    palette, et changer de couleur ne change pas de modèle.
    """
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    current = dict(candidate.cv_design or {})
    current.update(design.model_dump(exclude_unset=True))
    candidate.cv_design = current

    await db.commit()
    await db.refresh(candidate)

    return await get_cv_design(candidate_id, db)


@router.post("/parse-resume", response_model=ParsedCandidateProfile)
async def extract_resume_data(file: UploadFile = File(...)):
    """Extract candidate profile fields from an uploaded PDF resume."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Seuls les fichiers PDF sont pris en charge pour l'extraction.")
    
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Le fichier transmis est vide.")
        
    profile = await parse_resume(contents, filename=file.filename)
    return profile


@router.post("/parse-linkedin", response_model=ParsedCandidateProfile)
async def extract_linkedin_data(linkedin_url: str = Query(..., description="LinkedIn profile URL")):
    """Extract public candidate details from a LinkedIn profile URL."""
    if not linkedin_url or "linkedin.com" not in linkedin_url.lower():
        raise HTTPException(400, "L'URL fournie ne semble pas être une URL LinkedIn valide.")
        
    profile = await parse_linkedin_url(linkedin_url)
    return profile


@router.put("/{candidate_id}/cv-content", response_model=dict)
async def store_cv_content(
    candidate_id: UUID,
    content: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Enregistre le parcours détaillé (expériences, formation, langues).

    Sans ça, Alice ne peut pas argumenter : elle rédige côté serveur et n'a
    aucun accès au navigateur où ces données vivaient jusqu'ici.
    """
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    candidate.cv_content = content
    await db.commit()

    return {
        "experiences": len(content.get("experiences") or []),
        "education": len(content.get("education") or []),
    }


@router.get("/{candidate_id}/signature", response_model=dict)
async def get_signature(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    """La signature enregistrée, réutilisée sur chaque lettre générée."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")
    return {"image": candidate.signature_image, "has_signature": bool(candidate.signature_image)}


@router.put("/{candidate_id}/signature", response_model=dict)
async def set_signature(
    candidate_id: UUID,
    data: SignatureUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Enregistre la signature manuscrite une fois pour toutes."""
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")

    if not data.image.startswith("data:image/"):
        raise HTTPException(400, "La signature doit être une data URL image.")
    if len(data.image) > MAX_SIGNATURE_CHARS:
        raise HTTPException(413, "Signature trop volumineuse.")

    candidate.signature_image = data.image
    await db.commit()
    return {"has_signature": True}


@router.delete("/{candidate_id}/signature", response_model=dict)
async def delete_signature(candidate_id: UUID, db: AsyncSession = Depends(get_db)):
    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate profile not found")
    candidate.signature_image = None
    await db.commit()
    return {"has_signature": False}


@router.post("/download-cover-letter")
async def download_cover_letter(letter: CoverLetterResult):
    """
    Compile la lettre en PDF côté serveur et renvoie le fichier.

    Le rendu passe par Typst, comme le CV : identique sur toutes les
    plateformes, et sans boîte de dialogue d'impression.
    """
    import unicodedata

    try:
        pdf = render_letter_pdf(letter)
    except Exception as e:
        logger.error("Rendu PDF de la lettre impossible : %s", e, exc_info=True)
        raise HTTPException(500, f"Génération du PDF impossible : {e}")

    label = letter.recipient_company or letter.subject or "lettre"
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    safe = re.sub(r"[^\w\s-]", "", ascii_label).strip().replace(" ", "_") or "lettre"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Lettre_{safe}.pdf"'},
    )


@router.post("/cv-content", response_model=CvContentResult)
async def generate_cv_content(req: CvContentRequest):
    """
    Rédige l'accroche et la synthèse à partir du parcours complet.

    Sans état : les expériences vivent dans l'éditeur du Canvas, pas en base.
    `source` indique si le contenu vient du modèle, d'un repli sans LLM, ou
    d'une réponse retombée dans le générique malgré les consignes.
    """
    return await write_cv_content(req)


@router.post("/audit-cv", response_model=CVAuditResult)
async def audit_cv_profile(profile: ParsedCandidateProfile):
    """Audit a candidate profile for ATS compatibility and generate improvement suggestions."""
    audit = await audit_candidate_profile(profile)
    return audit


_PHOTO_CACHE: dict[str, str] = {}


def _prepare_photo_path(photo_url: str | None) -> str | None:
    if not photo_url:
        return None

    if photo_url in _PHOTO_CACHE:
        cached_path = _PHOTO_CACHE[photo_url]
        if Path(cached_path).exists():
            return cached_path

    try:
        if photo_url.startswith("http://") or photo_url.startswith("https://"):
            import urllib.request
            import tempfile
            req = urllib.request.Request(photo_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                img_data = resp.read()
                ext = ".png" if img_data.startswith(b"\x89PNG") else ".jpg"
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                temp_img.write(img_data)
                temp_img.close()
                _PHOTO_CACHE[photo_url] = temp_img.name
                return temp_img.name
        elif photo_url.startswith("data:image"):
            import base64
            import tempfile
            header, encoded = photo_url.split(",", 1)
            img_data = base64.b64decode(encoded)
            ext = ".png" if ("png" in header.lower() or img_data.startswith(b"\x89PNG")) else ".jpg"
            temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_img.write(img_data)
            temp_img.close()
            _PHOTO_CACHE[photo_url] = temp_img.name
            return temp_img.name
        elif Path(photo_url).exists():
            return photo_url
    except Exception as e:
        logger.warning(f"Impossible de charger la photo du CV ({photo_url}): {e}")
    return None


def _normalize_date(date_val: str | None, default: str = "2021-01") -> str:
    if not date_val:
        return default
    d = str(date_val).strip()
    if not d:
        return default
    if d.lower() in ["present", "présent", "actuel", "current"]:
        return "present"
    if re.match(r"^\d{4}$", d):
        return d
    if re.match(r"^\d{4}-\d{2}$", d):
        return d
    if re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return d[:7]
    return default


def _build_cv_data_from_request(data: CVRenderRequest) -> dict:
    normalized_name = (data.full_name or "Candidat").replace("\u2019", "'").replace("\u2018", "'")
    normalized_headline = (data.headline or "Professionnel").replace("\u2019", "'").replace("\u2018", "'")
    
    exp_list = []
    if data.experiences:
        for exp in data.experiences:
            company = exp.get("company") or "Entreprise"
            position = exp.get("jobTitle") or exp.get("position") or normalized_headline
            start_date = _normalize_date(exp.get("startDate") or exp.get("start_date"), default="2021-01")
            end_date = "present" if exp.get("isCurrent") or str(exp.get("endDate")).lower() in ["present", "présent"] else _normalize_date(exp.get("endDate") or exp.get("end_date"), default="present")
            summary = exp.get("description") or exp.get("summary") or ""
            highlights = exp.get("highlights") or []
            if isinstance(highlights, str):
                highlights = [h.strip() for h in highlights.split("\n") if h.strip()]
            loc = exp.get("location") or ""

            exp_list.append({
                "company": company,
                "position": position,
                "location": loc,
                "start_date": start_date,
                "end_date": end_date,
                "summary": summary,
                "highlights": highlights,
            })
    else:
        exp_list.append({
            "company": "Expérience Professionnelle",
            "position": normalized_headline,
            "location": "France",
            "start_date": "2021-01",
            "end_date": "present",
            "summary": f"Spécialiste en {', '.join(data.skills[:3]) if data.skills else 'développement logiciel'}.",
            "highlights": []
        })

    edu_list = []
    if data.education:
        for edu in data.education:
            degree = edu.get("degree") or edu.get("area") or "Diplôme"
            institution = edu.get("institution") or "Établissement"
            start_year = _normalize_date(edu.get("startYear") or edu.get("startDate") or edu.get("start_date"), default="2018")
            end_year = _normalize_date(edu.get("endYear") or edu.get("endDate") or edu.get("end_date"), default="2021")
            loc = edu.get("location") or ""

            edu_list.append({
                "institution": institution,
                "area": degree,
                "degree": degree,
                "location": loc,
                "start_date": start_year,
                "end_date": end_year,
            })


    sections = {}
    if data.summary:
        sections["profil"] = [data.summary]

    sections["experience"] = exp_list

    if edu_list:
        sections["education"] = edu_list

    if data.skills:
        sections["competences"] = [", ".join(data.skills)]

    if data.languages:
        lang_items = []
        for l in data.languages:
            if isinstance(l, dict):
                lang_name = l.get("language") or ""
                level = l.get("level") or ""
                if lang_name:
                    lang_items.append(f"**{lang_name}** — {level}" if level else f"**{lang_name}**")
            elif isinstance(l, str):
                lang_items.append(l)

        if lang_items:
            sections["langues"] = lang_items

    social_networks = []
    if data.linkedin_url:
        social_networks.append({
            "network": "LinkedIn",
            "username": "LinkedIn",
            "url": data.linkedin_url
        })

    photo_path = None
    if data.show_photo:
        photo_url = data.photo_url or "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&auto=format&fit=crop&q=80"
        photo_path = _prepare_photo_path(photo_url)

    return {
        "name": normalized_name,
        "headline": normalized_headline,
        "email": data.email or "contact@email.com",
        "phone": data.phone or "",
        "location": data.location or "France",
        "social_networks": social_networks,
        "photo": photo_path,
        "sections": sections
    }


@router.post("/render-cv")
async def render_redesigned_cv(data: CVRenderRequest):
    """
    Render a redesigned CV using the cv-engine (Typst).
    Returns template confirmation, generated Typst source, and PDF download endpoint.
    """
    cv_data = _build_cv_data_from_request(data)
    color_hex = data.color_hex or "#234C6A"

    design_config = {
        "theme": data.template_id or "classic",
        "header_style": "banner",
        "colors": {
            "body": "rgb(30, 41, 59)",
            "name": "rgb(255, 255, 255)",
            "headline": "rgb(255, 255, 255)",
            "connections": "rgb(255, 255, 255)",
            "banner_bg": color_hex,
            "section_titles": color_hex,
            "links": color_hex,
        },
        "typography": {
            "font_family": {
                "body": "Liberation Sans",
                "name": "Liberation Sans",
                "headline": "Liberation Sans",
                "connections": "Liberation Sans",
                "section_titles": "Liberation Sans",
            }
        }
    }
    
    typst_code = ""
    if HAS_CV_ENGINE:
        try:
            typst_code = render_cv(cv_data, design=design_config, locale="fr", bold_keywords=data.skills)
        except Exception as e:
            typst_code = f"// Erreur lors du rendu Typst: {e}"

    return {
        "status": "success",
        "template_id": data.template_id,
        "message": f"CV généré avec succès en utilisant le moteur cv-engine (modèle '{data.template_id}').",
        "typst_source_preview": typst_code[:500] if typst_code else None,
        "download_url": f"/api/candidates/download-cv/{data.template_id}",
    }


@router.post("/download-cv")
async def download_candidate_cv_pdf(data: CVRenderRequest):
    """
    Compile and return the actual PDF generated by cv-engine (Typst) for a complete candidate profile payload.
    """
    import unicodedata
    import re

    cv_data = _build_cv_data_from_request(data)

    if not HAS_CV_ENGINE:
        raise HTTPException(500, "Le moteur cv-engine n'est pas disponible.")

    color_hex = data.color_hex or "#234C6A"

    design_config = {
        "theme": data.template_id or "classic",
        "header_style": "banner",
        "colors": {
            "body": "rgb(30, 41, 59)",
            "name": "rgb(255, 255, 255)",
            "headline": "rgb(255, 255, 255)",
            "connections": "rgb(255, 255, 255)",
            "banner_bg": color_hex,
            "section_titles": color_hex,
            "links": color_hex,
        },
        "typography": {
            "font_family": {
                "body": "Liberation Sans",
                "name": "Liberation Sans",
                "headline": "Liberation Sans",
                "connections": "Liberation Sans",
                "section_titles": "Liberation Sans",
            }
        }
    }

    try:
        typst_code = render_cv(cv_data, design=design_config, locale="fr", bold_keywords=data.skills or [])
        pdf_bytes = compile_typst_to_pdf(typst_code)
        
        ascii_name = unicodedata.normalize('NFKD', cv_data["name"]).encode('ascii', 'ignore').decode('ascii')
        safe_filename_name = re.sub(r'[^\w\s-]', '', ascii_name).strip().replace(' ', '_') or "candidat"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="CV_{safe_filename_name}_{data.template_id}.pdf"'}
        )
    except Exception as e:
        logger.error(f"Erreur de compilation PDF par cv-engine: {e}")
        raise HTTPException(500, f"Erreur de compilation PDF par cv-engine: {e}")


@router.get("/download-cv/{template_id}")
async def download_cv_pdf(template_id: str, name: str = "candidat", headline: str = "Ingénieur Développeur"):
    """
    Fallback GET endpoint for PDF download.
    """
    req = CVRenderRequest(
        template_id=template_id,
        full_name=name,
        email="contact@email.com",
        headline=headline,
    )
    return await download_candidate_cv_pdf(req)


@router.post("/render-preview-svg")
async def render_cv_preview_svg(data: CVRenderRequest):
    """
    Compile and return the SVG image directly rendered by Typst for real-time visual parity.
    """
    cv_data = _build_cv_data_from_request(data)

    if not HAS_CV_ENGINE:
        raise HTTPException(500, "Le moteur cv-engine n'est pas disponible.")

    color_hex = data.color_hex or "#234C6A"

    design_config = {
        "theme": data.template_id or "classic",
        "header_style": "banner",
        "colors": {
            "body": "rgb(30, 41, 59)",
            "name": "rgb(255, 255, 255)",
            "headline": "rgb(255, 255, 255)",
            "connections": "rgb(255, 255, 255)",
            "banner_bg": color_hex,
            "section_titles": color_hex,
            "links": color_hex,
        },
        "typography": {
            "font_family": {
                "body": "Liberation Sans",
                "name": "Liberation Sans",
                "headline": "Liberation Sans",
                "connections": "Liberation Sans",
                "section_titles": "Liberation Sans",
            }
        }
    }

    try:
        typst_code = render_cv(cv_data, design=design_config, locale="fr", bold_keywords=data.skills or [])
        svg_content = compile_typst_to_svg(typst_code)
        
        return Response(
            content=svg_content,
            media_type="image/svg+xml"
        )
    except Exception as e:
        logger.error(f"Erreur de génération du preview SVG par Typst: {e}")
        raise HTTPException(500, f"Erreur de génération du preview SVG: {e}")




