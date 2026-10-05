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
    _ENGINE_ERROR = f"{type(e).__name__}: {e}"
    logger.warning("cv-engine indisponible pour la génération de CV : %s", e)


#: Dernière erreur de mise en page, jointe aux alertes : sans elle, un
#: « CV impossible à composer » ne dit pas quoi réparer.
last_render_error: str | None = None


def _safe_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s-]", "", ascii_name).strip().replace(" ", "_") or "candidat"



_MONTHS = {
    "jan": 1, "janv": 1, "janvier": 1, "january": 1, "fev": 2, "fév": 2, "févr": 2,
    "fevr": 2, "février": 2, "fevrier": 2, "feb": 2, "february": 2, "mar": 3, "mars": 3,
    "march": 3, "avr": 4, "avril": 4, "apr": 4, "april": 4, "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6, "juil": 7, "juillet": 7, "jul": 7, "july": 7,
    "aou": 8, "aoû": 8, "aout": 8, "août": 8, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "septembre": 9, "september": 9, "oct": 10, "octobre": 10, "october": 10, "nov": 11,
    "novembre": 11, "november": 11, "dec": 12, "déc": 12, "décembre": 12, "decembre": 12,
    "december": 12,
}
_PRESENT = re.compile(r"aujourd|pr[ée]sent|en cours|actuel|now|current|ce jour|à ce jour", re.I)


def _date(value) -> str:
    """
    Une date de parcours au format que le moteur accepte (AAAA-MM, AAAA ou
    « present »), ou "" si on ne sait pas la lire. Les CV lus depuis un PDF
    portent « 09/2022 », « Septembre 2022 », « Sept 2020 »… : passés tels
    quels, ils faisaient échouer toute la mise en page.
    """
    if value is None or value == "":
        return ""
    v = str(value).strip()
    if _PRESENT.search(v):
        return "present"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", v)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.fullmatch(r"(\d{1,2})[/.\-](\d{4})", v)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"\d{1,2}[/.]\d{1,2}[/.](\d{4})", v)
    if m:
        return m.group(1)
    m = re.search(r"([a-zA-Zéûô]+)\.?\s*(\d{4})", v)
    if m and m.group(1).lower() in _MONTHS:
        return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"(19|20)\d{2}", v)
    return m.group(0) if m else ""


def _period(start, end) -> dict:
    """
    Début et fin, ou une date unique : le moteur refuse une seule borne
    (« No date provided for this entry »), fréquente dans un CV lu depuis un PDF.
    """
    start, end = _date(start), _date(end)
    if start and end:
        return {"start_date": start, "end_date": end}
    single = start or (end if end != "present" else "")
    return {"date": single} if single else {}


def _text(value) -> str:
    """Un champ texte, quel que soit ce que l'extraction a rangé dedans."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "description", "value", "content", "name", "title"):
            if isinstance(value.get(key), str):
                return value[key]
        return " ".join(str(v) for v in value.values() if isinstance(v, (str, int, float)))
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(v) for v in value if v)
    return str(value)


def _lines(value) -> list[str]:
    if isinstance(value, str):
        return [h.strip() for h in value.split("\n") if h.strip()]
    return [t for t in (_text(v).strip() for v in (value or [])) if t]


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
    global last_render_error
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
        last_render_error = f"cv-engine indisponible : {globals().get('_ENGINE_ERROR', '?')}"
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
        if not isinstance(exp, dict):
            continue
        highlights = _lines(exp.get("highlights"))
        description = _text(exp.get("description"))
        adapted = rewritten[i] if i < len(rewritten) and isinstance(rewritten[i], dict) else {}
        if adapted.get("highlights"):
            highlights = _lines(adapted["highlights"])
            # La description d'origine est déjà fondue dans les puces adaptées.
            description = ""
        experiences.append({
            "company": _text(exp.get("company")) or "Entreprise",
            "position": _text(exp.get("jobTitle") or exp.get("position")) or "Poste",
            "location": _text(exp.get("location")),
            **_period(
                exp.get("startDate") or exp.get("start_date"),
                "present" if exp.get("isCurrent") else (exp.get("endDate") or exp.get("end_date")),
            ),
            "summary": description,
            "highlights": highlights,
        })
    if experiences:
        sections["Expérience"] = experiences

    education = [
        {
            "institution": _text(e.get("institution")),
            # Le diplôme en intitulé, pas dans la colonne étroite des
            # abréviations (« BUT Infor-ma-tique » sur quatre lignes).
            "area": _text(e.get("degree") or e.get("field")),
            "degree": "",
            "location": _text(e.get("location")),
            **_period(e.get("startYear") or e.get("startDate"), e.get("endYear") or e.get("endDate")),
        }
        for e in (cv.get("education") or []) if isinstance(e, dict)
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
        last_render_error = f"{type(e).__name__}: {e}"[:500]
        logger.error("Génération du CV au modèle échouée : %s", e, exc_info=True)
        # « render_failed » : l'appelant sait que la promesse (un CV mis en
        # page) n'est pas tenue, et peut le dire au lieu de servir en silence
        # l'original — ou rien du tout.
        if tailored:
            # Jamais l'original à la place du CV adapté : l'appelant le dit.
            return None, f"CV_{_safe_name(candidate.full_name)}.pdf", "render_failed"
        return candidate.resume_file, candidate.resume_filename or "CV.pdf", "render_failed"
