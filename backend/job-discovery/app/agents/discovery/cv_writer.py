"""
Rédaction de l'accroche et de la synthèse du CV.

Le générateur précédent ne recevait que le nom, le titre, les compétences et
les années d'expérience. Avec si peu de matière, un modèle ne peut produire que
du passe-partout — « Professionnel expérimenté en Python, React, Docker ». Le
problème n'était pas le prompt, c'était l'absence d'entrée.

Ici le parcours complet est transmis : chaque poste, sa durée, ses
responsabilités, ses réalisations, et la progression de l'un à l'autre.
"""

import json
import logging


from app.agents.persona import BANNED_PHRASES, DIFFERENTIATION_QUESTION, IDENTITY, WRITING_RULES
from app import llm
from app.config import settings
from app.schemas.cv_content import CvContentRequest, CvContentResult

logger = logging.getLogger(__name__)


def _format_experiences(experiences: list[dict]) -> str:
    if not experiences:
        return "Aucune expérience renseignée."

    blocks = []
    for i, exp in enumerate(experiences):
        title = exp.get("jobTitle") or exp.get("position") or "Poste non précisé"
        company = exp.get("company") or "Entreprise non précisée"
        start = exp.get("startDate") or exp.get("start_date") or "?"
        end = "aujourd'hui" if exp.get("isCurrent") else (
            exp.get("endDate") or exp.get("end_date") or "?"
        )
        location = exp.get("location") or ""

        lines = [f"[{i}] {title} — {company} ({start} → {end}){f', {location}' if location else ''}"]

        highlights = exp.get("highlights") or []
        if isinstance(highlights, str):
            highlights = [h.strip() for h in highlights.split("\n") if h.strip()]
        for h in highlights:
            lines.append(f"    · {h}")

        if exp.get("description"):
            lines.append(f"    · {exp['description']}")

        blocks.append("\n".join(lines))

    return "\n".join(blocks)


def _format_education(education: list[dict]) -> str:
    if not education:
        return "Aucune formation renseignée."
    return "\n".join(
        f"- {e.get('degree') or e.get('area') or 'Diplôme'} — "
        f"{e.get('institution') or 'Établissement'} "
        f"({e.get('startYear') or '?'} → {e.get('endYear') or '?'})"
        for e in education
    )


PROMPT = """{identity}

Tu rédiges l'accroche et la synthèse du CV de ce candidat.

{writing_rules}

PARCOURS PROFESSIONNEL (du plus récent au plus ancien)
{experiences}

FORMATION
{education}

COMPÉTENCES DÉCLARÉES
{skills}

LANGUES
{languages}

{job_context}

AUTRES ÉLÉMENTS
Nom : {full_name}
Titre actuel : {headline}
Années d'expérience : {experience_years}
Synthèse actuelle : {summary}
{target}

TRAVAIL DEMANDÉ
0. Si une offre est fournie ci-dessus, l'accroche et la synthèse doivent la
   viser : mets en avant les éléments du parcours qui répondent à SES besoins,
   et emploie le vocabulaire de l'annonce quand il correspond à une réalité du
   parcours. N'ajoute JAMAIS une compétence que le candidat n'a pas pour coller
   à l'offre — c'est un mensonge qui se découvre en entretien.
1. Repère ce qui distingue réellement ce candidat : un domaine peu commun, une
   progression rapide, une combinaison de compétences rare, une responsabilité
   inhabituelle pour son niveau, une réalisation mesurable.
2. Rédige une accroche (« headline ») de 4 à 9 mots. Elle nomme une
   SPÉCIALITÉ, pas des réalisations : « Développeur Full Stack » ne distingue
   personne, « Développeur Python spécialisé sur les systèmes de santé
   critiques » distingue. N'y mets ni chiffre, ni deux-points, ni liste.
3. Rédige une synthèse de 2 à 4 phrases, appuyée sur les faits du parcours.
   Écris-la de manière impersonnelle ou à la première personne — jamais à la
   troisième personne, et ne répète jamais le nom du candidat : c'est SON CV,
   il ne parle pas de lui à distance.
4. Liste 2 à 4 éléments différenciants, formulés comme des faits vérifiables
   tirés du parcours, sans adjectif de personnalité.

{experience_task}
Réponds en JSON strict, en français :
{{"headline": str, "summary": str, "differentiators": [str]{experience_schema}}}
"""

#: Seulement quand une offre est visée : c'est ce qui fait d'un CV « adapté »
#: autre chose qu'un CV remis en page.
EXPERIENCE_TASK = """5. Pour chaque expérience numérotée [i] qui a des réalisations ou une
   description, réécris 2 à 4 puces orientées vers CETTE offre : commence par
   ce qui répond à ses besoins, emploie son vocabulaire quand il décrit une
   réalité du parcours, garde les chiffres existants. Chaque puce reprend un
   fait présent dans le parcours — reformuler, regrouper, réordonner, oui ;
   ajouter un outil, un chiffre ou une responsabilité absents, jamais.
   Une puce = une ligne, commence par un verbe d'action, 18 mots au plus.
   Une expérience sans aucun contenu : renvoie une liste vide pour elle.
"""
EXPERIENCE_SCHEMA = ', "experiences": [{"index": int, "highlights": [str]}]'


def _adapted_experiences(raw, experiences: list[dict]) -> list[dict]:
    """Aligne les puces renvoyées sur les expériences reçues, sans en créer."""
    adapted: list[dict] = [{} for _ in experiences]
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            i = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        source = experiences[i] if 0 <= i < len(experiences) else None
        # Rien à reformuler : une puce sur une expérience vide serait inventée.
        if not source or not (source.get("highlights") or source.get("description")):
            continue
        bullets = [
            b.strip() for b in (item.get("highlights") or [])
            if isinstance(b, str) and b.strip()
        ][:4]
        if bullets:
            from app.agents.experience_key import experience_key
            adapted[i] = {"key": experience_key(source), "highlights": [b[:220] for b in bullets]}
    return adapted if any(adapted) else []



def _sounds_generic(text: str) -> bool:
    """Un garde-fou : le modèle retombe parfois dans les formules bannies."""
    low = (text or "").lower()
    return any(p in low for p in BANNED_PHRASES)


def _fallback(req: CvContentRequest) -> CvContentResult:
    """
    Repli sans LLM.

    Il n'essaie pas d'imiter une rédaction : il assemble des faits. Un titre de
    poste réel et une durée valent mieux qu'une phrase inventée.
    """
    last = (req.experiences or [{}])[0]
    role = last.get("jobTitle") or last.get("position") or req.headline or "Profil professionnel"
    company = last.get("company")
    top_skills = ", ".join((req.skills or [])[:4])

    facts: list[str] = []
    if company:
        facts.append(f"{role} chez {company}")
    if req.experience_years:
        facts.append(f"{req.experience_years:.0f} ans d'expérience")
    if top_skills:
        facts.append(f"Travaille avec {top_skills}")

    # Rien d'inventé, et jamais une consigne adressée au candidat : cette
    # synthèse peut finir sur le CV envoyé au recruteur.
    summary = ". ".join(facts) + "." if facts else ""

    return CvContentResult(
        headline=role,
        summary=summary,
        differentiators=facts,
        source="fallback",
    )


async def write_cv_content(req: CvContentRequest) -> CvContentResult:
    """Renvoie une accroche et une synthèse ancrées sur le parcours. Ne lève jamais."""
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY absente — contenu CV assemblé sans LLM.")
        return _fallback(req)

    try:
        target = (
            f"Poste visé : {req.target_role}" if req.target_role
            else "Aucun poste précis visé."
        )

        tailored = bool(req.job_excerpt or req.job_title)
        job_context = (
            "OFFRE VISÉE — adapte l'accroche et la synthèse à ce poste\n"
            f"Intitulé : {req.job_title or 'non précisé'}\n"
            f"Entreprise : {req.company_name or 'non précisée'}\n"
            f"Compétences attendues : {', '.join(req.job_skills) or 'non précisées'}\n"
            f"Extrait de l'annonce :\n{(req.job_excerpt or '')[:2000]}"
            if tailored else
            "Aucune offre visée : rédige un CV générique mais spécifique au parcours."
        )

        response = await llm.generate(PROMPT.format(
            identity=IDENTITY,
            writing_rules=WRITING_RULES,
            experiences=_format_experiences(req.experiences or []),
            education=_format_education(req.education or []),
            skills=", ".join(req.skills or []) or "Aucune",
            languages=", ".join(
                f"{l.get('language')} ({l.get('level')})"
                for l in (req.languages or []) if l.get("language")
            ) or "Non renseignées",
            full_name=req.full_name or "Non renseigné",
            headline=req.headline or "Non renseigné",
            experience_years=req.experience_years or "Non renseigné",
            summary=req.summary or "Aucune",
            target=target,
            job_context=job_context,
            experience_task=EXPERIENCE_TASK if tailored and req.experiences else "",
            experience_schema=EXPERIENCE_SCHEMA if tailored and req.experiences else "",
        ), json=True)

        data = json.loads(response)
        result = CvContentResult(
            headline=(data.get("headline") or "").strip(),
            summary=(data.get("summary") or "").strip(),
            differentiators=[d for d in (data.get("differentiators") or []) if d],
            experiences=(
                _adapted_experiences(data.get("experiences"), req.experiences or [])
                if tailored else []
            ),
            source="llm",
            tailored_to_job=tailored,
        )

        if not result.headline or not result.summary:
            raise ValueError("réponse incomplète")

        # Le modèle a repris une formule bannie : on le signale plutôt que de
        # livrer silencieusement le contenu générique qu'on cherchait à éviter.
        if _sounds_generic(result.summary) or _sounds_generic(result.headline):
            logger.warning("Contenu CV générique détecté, signalé au client.")
            result.source = "llm_generic"

        return result

    except Exception as e:  # noqa: BLE001
        logger.error("CV content generation failed: %s", e, exc_info=True)
        return _fallback(req)
