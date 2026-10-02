"""
Rédaction de lettre de motivation.

La lettre s'écrit à partir de trois matières, et elle n'a de valeur que si les
trois sont présentes :
  1. l'annonce réelle (intitulé, entreprise, stack, texte de l'offre) ;
  2. le parcours détaillé du candidat — postes tenus, réalisations, durées ;
  3. les conventions du document (objet, lieu et date, politesse, signature).

Sans (2), une lettre ne peut que reformuler des compétences : c'est ce qui
produit des textes interchangeables. Le parcours est donc lu depuis
`Candidate.cv_content`, alimenté par l'éditeur du Canvas.
"""

import json
import logging
import re
from datetime import date


from app.agents.persona import IDENTITY, WRITING_RULES
from app import llm
from app.config import settings
from app.schemas.cover_letter import CoverLetterResult

logger = logging.getLogger(__name__)

_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def french_date(today: date | None = None) -> str:
    d = today or date.today()
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _format_experiences(experiences: list[dict]) -> str:
    if not experiences:
        return "Aucune expérience renseignée."

    blocks = []
    for exp in experiences:
        title = exp.get("jobTitle") or exp.get("position") or "Poste"
        company = exp.get("company") or "Entreprise"
        start = exp.get("startDate") or exp.get("start_date") or "?"
        end = "aujourd'hui" if exp.get("isCurrent") else (
            exp.get("endDate") or exp.get("end_date") or "?"
        )
        lines = [f"- {title} — {company} ({start} → {end})"]

        highlights = exp.get("highlights") or []
        if isinstance(highlights, str):
            highlights = [h.strip() for h in highlights.split("\n") if h.strip()]
        lines += [f"    · {h}" for h in highlights]
        if exp.get("description"):
            lines.append(f"    · {exp['description']}")

        blocks.append("\n".join(lines))

    return "\n".join(blocks)


PROMPT = """{identity}

Tu rédiges une lettre de motivation pour ce candidat.

{writing_rules}

PARCOURS DU CANDIDAT (du plus récent au plus ancien)
{experiences}

FORMATION
{education}

COMPÉTENCES
{skills}

SYNTHÈSE DU PROFIL
{summary}

POSTE VISÉ
Intitulé : {job_title}
Entreprise : {company_name}
Localisation : {location}
Technologies attendues : {tech_stack}
Texte de l'annonce :
{job_excerpt}

TRAVAIL DEMANDÉ
Établis les correspondances entre CE parcours et CE poste. Chaque argument doit
s'appuyer sur une expérience réellement listée ci-dessus — nomme l'entreprise,
la réalisation, le chiffre quand il existe. Une lettre qui pourrait être envoyée
à une autre entreprise est une lettre ratée.

Structure du corps :
- Une accroche qui dit pourquoi CETTE entreprise, à partir du texte de l'annonce.
- Un paragraphe reliant une réalisation précise du parcours à un besoin exprimé
  dans l'offre.
- Une liste de 3 puces maximum : besoin de l'offre → preuve tirée du parcours.
- Une phrase de clôture proposant un échange.

Contraintes :
- 220 à 300 mots pour le corps.
- Markdown pour le corps uniquement (gras et puces). Pas de titre.
- Vouvoiement de l'entreprise, première personne pour le candidat.
- N'écris NI l'en-tête, NI l'objet, NI la formule d'appel, NI la formule de
  politesse, NI la signature dans le corps : ils sont fournis séparément.

Réponds en JSON strict, en français :
{{"subject": str, "body": str, "closing": str}}

- "subject" : objet de la lettre, sur une ligne, sans le mot « Objet ».
- "closing" : formule de politesse complète et classique.
"""


def _clean(text: str) -> str:
    text = re.sub(r"^\s*```(?:markdown|md|json)?\s*\n", "", text or "")
    text = re.sub(r"\n\s*```\s*$", "", text)
    return text.strip()


def _fallback_body(
    headline: str, skills: list[str], job_title: str, company_name: str,
    experiences: list[dict],
) -> tuple[str, str, str]:
    """Repli sans LLM : sobre, mais bâti sur des faits réels."""
    poste = job_title or "le poste proposé"
    boite = company_name or "votre entreprise"
    last = experiences[0] if experiences else {}
    role = last.get("jobTitle") or last.get("position")
    company = last.get("company")

    intro = (
        f"Actuellement {role} chez {company}, je souhaite mettre cette expérience "
        f"au service de **{poste}**."
        if role and company
        else f"Je vous adresse ma candidature pour **{poste}**."
    )

    bullets = []
    for exp in experiences[:3]:
        hl = (exp.get("highlights") or [None])[0]
        if hl:
            bullets.append(f"- {hl}")
    bullets_block = "\n".join(bullets) if bullets else (
        f"- Pratique de {', '.join(skills[:3]) if skills else 'mes outils'}"
    )

    body = f"""{intro}

Ce que je peux apporter à {boite} :

{bullets_block}

Je reste à votre disposition pour en échanger."""

    return (
        f"Candidature au poste de {poste}",
        body,
        "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
    )


async def write_cover_letter(
    *,
    full_name: str = "",
    email: str = "",
    phone: str = "",
    linkedin_url: str = "",
    headline: str = "",
    skills: list[str] | None = None,
    summary: str = "",
    experiences: list[dict] | None = None,
    education: list[dict] | None = None,
    job_title: str = "",
    company_name: str = "",
    location: str = "",
    tech_stack: list[str] | None = None,
    job_excerpt: str = "",
    signature_image: str | None = None,
) -> CoverLetterResult:
    """Renvoie une lettre complète et prête à l'envoi. Ne lève jamais."""
    skills = skills or []
    experiences = experiences or []
    education = education or []
    tech_stack = tech_stack or []

    contact = [c for c in (email, phone, linkedin_url) if c]

    def assemble(subject: str, body: str, closing: str, source: str) -> CoverLetterResult:
        return CoverLetterResult(
            sender_name=full_name,
            sender_contact=contact,
            recipient_name="Service Recrutement",
            recipient_company=company_name,
            place=location.split(",")[0].strip() if location else None,
            date=french_date(),
            subject=subject,
            body=body,
            closing=closing,
            signature_name=full_name,
            signature_image=signature_image,
            grounded_on_posting=bool(job_excerpt),
            grounded_on_experiences=bool(experiences),
            source=source,
        )

    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY absente — lettre assemblée sans LLM.")
        return assemble(
            *_fallback_body(headline, skills, job_title, company_name, experiences),
            "fallback",
        )

    try:
        response = await llm.generate(PROMPT.format(
            identity=IDENTITY,
            writing_rules=WRITING_RULES,
            experiences=_format_experiences(experiences),
            education="\n".join(
                f"- {e.get('degree') or 'Diplôme'} — {e.get('institution') or ''} "
                f"({e.get('endYear') or '?'})"
                for e in education
            ) or "Non renseignée",
            skills=", ".join(skills) or "Non renseignées",
            summary=summary or "Non renseignée",
            job_title=job_title or "non précisé",
            company_name=company_name or "non précisée",
            location=location or "non précisée",
            tech_stack=", ".join(tech_stack) or "non précisées",
            job_excerpt=(job_excerpt or "non disponible")[:3000],
        ), json=True)

        data = json.loads(_clean(response))
        body = _clean(data.get("body") or "")
        if len(body) < 150:
            raise ValueError("corps trop court")

        return assemble(
            (data.get("subject") or f"Candidature — {job_title}").strip(),
            body,
            (data.get("closing") or
             "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.").strip(),
            "llm",
        )

    except Exception as e:  # noqa: BLE001 — l'échec de rédaction ne doit pas
        # empêcher le Canvas de s'ouvrir.
        logger.error("Cover letter generation failed: %s", e, exc_info=True)
        return assemble(
            *_fallback_body(headline, skills, job_title, company_name, experiences),
            "fallback",
        )
