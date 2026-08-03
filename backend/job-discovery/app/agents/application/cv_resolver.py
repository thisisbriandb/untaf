"""
Quel CV part réellement avec la candidature.

Le candidat peut avoir déposé un PDF puis choisi un modèle dans le Canvas. Le
document envoyé doit refléter ce choix : joindre l'original alors qu'il a
configuré un modèle revient à ignorer son travail sans le lui dire.
"""

import logging
import re
import sys
import unicodedata
from pathlib import Path

from app.models.candidate import Candidate

logger = logging.getLogger(__name__)

CV_ENGINE_PATH = Path(__file__).resolve().parents[3] / "cv-engine"
if str(CV_ENGINE_PATH) not in sys.path:
    sys.path.append(str(CV_ENGINE_PATH))

try:
    from backend.renderer import render_cv
    from backend.compiler import compile_typst_to_pdf
    HAS_ENGINE = True
except Exception as e:  # noqa: BLE001
    HAS_ENGINE = False
    logger.warning("cv-engine indisponible pour la génération de CV : %s", e)


def _safe_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s-]", "", ascii_name).strip().replace(" ", "_") or "candidat"


def resolve_cv(candidate: Candidate) -> tuple[bytes | None, str, str]:
    """
    Renvoie (pdf, nom_de_fichier, origine).

    `origine` vaut « original » ou « template » — c'est ce qui est affiché au
    candidat, pour qu'il sache lequel des deux part.
    """
    design = candidate.cv_design or {}
    mode = design.get("mode") or ("original" if candidate.resume_file else "template")
    template_id = design.get("template_id")

    # Mode original, ou modèle non choisi : on envoie le document déposé.
    if mode != "template" or not template_id:
        return (
            candidate.resume_file,
            candidate.resume_filename or "CV.pdf",
            "original",
        )

    if not HAS_ENGINE:
        logger.warning("Modèle demandé mais cv-engine absent — repli sur l'original.")
        return candidate.resume_file, candidate.resume_filename or "CV.pdf", "original"

    cv = candidate.cv_content or {}
    sections: dict = {}
    if cv.get("summary"):
        sections["profil"] = [cv["summary"]]

    experiences = []
    for exp in cv.get("experiences") or []:
        highlights = exp.get("highlights") or []
        if isinstance(highlights, str):
            highlights = [h.strip() for h in highlights.split("\n") if h.strip()]
        experiences.append({
            "company": exp.get("company") or "Entreprise",
            "position": exp.get("jobTitle") or exp.get("position") or "Poste",
            "location": exp.get("location") or "",
            "start_date": exp.get("startDate") or "",
            "end_date": "present" if exp.get("isCurrent") else (exp.get("endDate") or ""),
            "summary": exp.get("description") or "",
            "highlights": highlights,
        })
    if experiences:
        sections["experience"] = experiences

    education = [
        {
            "institution": e.get("institution") or "",
            "area": e.get("degree") or "",
            "degree": e.get("degree") or "",
            "location": e.get("location") or "",
            "start_date": e.get("startYear") or "",
            "end_date": e.get("endYear") or "",
        }
        for e in (cv.get("education") or [])
    ]
    if education:
        sections["education"] = education

    if candidate.skills:
        sections["competences"] = [", ".join(candidate.skills)]

    languages = [
        f"**{l.get('language')}** — {l.get('level')}" if l.get("level") else f"**{l.get('language')}**"
        for l in (cv.get("languages") or []) if l.get("language")
    ]
    if languages:
        sections["langues"] = languages

    color = design.get("color_hex") or "#234C6A"
    data = {
        "name": candidate.full_name or "Candidat",
        "headline": candidate.headline or "",
        "email": candidate.email or "",
        "phone": candidate.phone or "",
        "location": "France",
        "social_networks": (
            [{"network": "LinkedIn", "username": "LinkedIn", "url": candidate.linkedin_url}]
            if candidate.linkedin_url else []
        ),
        "photo": None,
        "sections": sections,
    }

    try:
        typst = render_cv(
            data,
            design={
                "theme": template_id,
                "header_style": "banner",
                "colors": {
                    "body": "rgb(30, 41, 59)", "name": "rgb(255, 255, 255)",
                    "headline": "rgb(255, 255, 255)", "connections": "rgb(255, 255, 255)",
                    "banner_bg": color, "section_titles": color, "links": color,
                },
                "typography": {"font_family": {
                    k: "Liberation Sans"
                    for k in ("body", "name", "headline", "connections", "section_titles")
                }},
            },
            locale="fr",
            bold_keywords=list(candidate.skills or []),
        )
        pdf = compile_typst_to_pdf(typst)
        return pdf, f"CV_{_safe_name(candidate.full_name)}_{template_id}.pdf", "template"

    except Exception as e:  # noqa: BLE001
        # Un échec de compilation ne doit pas envoyer un document inattendu :
        # on retombe sur l'original en le signalant.
        logger.error("Génération du CV au modèle échouée : %s", e, exc_info=True)
        return candidate.resume_file, candidate.resume_filename or "CV.pdf", "original"
