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

CV_ENGINE_PATH = Path(__file__).resolve().parents[4] / "cv-engine"
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


def resolve_cv(
    candidate: Candidate, tailoring: dict | None = None,
) -> tuple[bytes | None, str, str]:
    """
    Renvoie (pdf, nom_de_fichier, origine).

    `origine` vaut « original », « template » ou « tailored » — c'est ce qui
    est affiché au candidat, pour qu'il sache lequel part.

    `tailoring` ({headline, summary}) est l'adaptation à UNE offre, rangée sur
    la candidature. Elle remplace l'accroche et la synthèse de ce CV-là sans
    toucher au profil : les autres candidatures gardent le CV général. Un PDF
    déposé ne se réécrit pas ; l'adaptation passe donc toujours par un modèle,
    celui choisi par le candidat ou le classique à défaut.
    """
    design = candidate.cv_design or {}
    mode = design.get("mode") or ("original" if candidate.resume_file else "template")
    template_id = design.get("template_id")

    tailoring = tailoring or {}
    tailored = bool(tailoring.get("headline") or tailoring.get("summary"))
    if tailored and HAS_ENGINE:
        mode, template_id = "template", template_id or "classic"
    # Aucun PDF déposé et aucun modèle choisi : le parcours saisi suffit à
    # composer un CV au modèle classique. Répondre « aucun CV » alors que tout
    # le contenu est là bloquait la candidature pour rien.
    if not candidate.resume_file and HAS_ENGINE and not template_id:
        mode, template_id = "template", "classic"

    # Mode original, ou modèle non choisi : on envoie le document déposé.
    if mode != "template" or not template_id:
        return (
            candidate.resume_file,
            candidate.resume_filename or "CV.pdf",
            "original",
        )

    if not HAS_ENGINE:
        logger.error("Modèle demandé mais cv-engine absent.")
        # Un CV adapté ne se remplace pas par l'original : ce serait livrer
        # le document que le candidat avait déjà, sous le nom de « pack ».
        if tailored:
            return None, f"CV_{_safe_name(candidate.full_name)}.pdf", "render_failed"
        return candidate.resume_file, candidate.resume_filename or "CV.pdf", "original"

    cv = candidate.cv_content or {}
    summary = (tailoring.get("summary") if tailored else None) or cv.get("summary")
    headline = (tailoring.get("headline") if tailored else None) or candidate.headline
    # Titres affichés tels quels (le moteur ne retouche pas une clé accentuée
    # ou capitalisée) : un CV français ne titre pas « Experience ».
    sections: dict = {}
    if summary:
        sections["Profil"] = [summary]

    # Ce que l'offre demande et que le parcours prouve — la partie la plus
    # visiblement adaptée du document.
    strengths = [s for s in (tailoring.get("strengths") or []) if s] if tailored else []
    if strengths:
        sections["Points forts pour ce poste"] = [{"bullet": s} for s in strengths[:4]]

    # Réalisations reformulées pour l'offre, expérience par expérience.
    rewritten = (tailoring.get("experiences") or []) if tailored else []

    experiences = []
    for i, exp in enumerate(cv.get("experiences") or []):
        highlights = exp.get("highlights") or []
        if isinstance(highlights, str):
            highlights = [h.strip() for h in highlights.split("\n") if h.strip()]
        description = exp.get("description") or ""
        adapted = rewritten[i] if i < len(rewritten) and isinstance(rewritten[i], dict) else {}
        if adapted.get("highlights"):
            highlights = [h for h in adapted["highlights"] if isinstance(h, str) and h.strip()]
            # La description d'origine est déjà fondue dans les puces adaptées.
            description = ""
        experiences.append({
            "company": exp.get("company") or "Entreprise",
            "position": exp.get("jobTitle") or exp.get("position") or "Poste",
            "location": exp.get("location") or "",
            "start_date": exp.get("startDate") or "",
            "end_date": "present" if exp.get("isCurrent") else (exp.get("endDate") or ""),
            "summary": description,
            "highlights": highlights,
        })
    if experiences:
        sections["Expérience"] = experiences

    education = [
        {
            "institution": e.get("institution") or "",
            # Le diplôme en intitulé, pas dans la colonne étroite des
            # abréviations (« BUT Infor-ma-tique » sur quatre lignes).
            "area": e.get("degree") or e.get("field") or "",
            "degree": "",
            "location": e.get("location") or "",
            "start_date": e.get("startYear") or "",
            "end_date": e.get("endYear") or "",
        }
        for e in (cv.get("education") or [])
    ]
    if education:
        sections["Formation"] = education

    # Toutes les compétences, dans l'ordre choisi pour l'offre s'il y en a un.
    skills = list(candidate.skills or [])
    order = (tailoring.get("skills_order") if tailored else None) or []
    if order:
        skills = [s for s in order if s in skills] + [s for s in skills if s not in order]
    if skills:
        sections["Compétences"] = [", ".join(skills)]

    languages = [
        f"**{l.get('language')}** — {l.get('level')}" if l.get("level") else f"**{l.get('language')}**"
        for l in (cv.get("languages") or []) if l.get("language")
    ]
    if languages:
        sections["Langues"] = languages

    color = design.get("color_hex") or "#234C6A"
    data = {
        "name": candidate.full_name or "Candidat",
        "headline": headline or "",
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
        if tailored:
            return pdf, f"CV_{_safe_name(candidate.full_name)}.pdf", "tailored"
        return pdf, f"CV_{_safe_name(candidate.full_name)}_{template_id}.pdf", "template"

    except Exception as e:  # noqa: BLE001
        # Un échec de compilation ne doit pas envoyer un document inattendu :
        # on retombe sur l'original en le signalant.
        logger.error("Génération du CV au modèle échouée : %s", e, exc_info=True)
        # « render_failed » : l'appelant sait que la promesse (un CV mis en
        # page) n'est pas tenue, et peut le dire au lieu de servir en silence
        # l'original — ou rien du tout.
        if tailored:
            # Jamais l'original à la place du CV adapté : l'appelant le dit.
            return None, f"CV_{_safe_name(candidate.full_name)}.pdf", "render_failed"
        return candidate.resume_file, candidate.resume_filename or "CV.pdf", "render_failed"
