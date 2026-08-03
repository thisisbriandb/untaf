"""
CV Audit & Enhancement Agent —
Evaluates candidate profiles for ATS (Applicant Tracking Systems) compatibility,
provides scores, diagnostic feedback, and generates optimized professional titles & summaries.
"""

import json
import logging
import google.generativeai as genai

from app.config import settings
from app.schemas.candidate import ParsedCandidateProfile, CVAuditResult

logger = logging.getLogger(__name__)


def heuristic_audit_profile(profile: ParsedCandidateProfile) -> CVAuditResult:
    """Fallback ATS auditor using rules when Gemini is unavailable."""
    score = 70
    strengths = []
    improvements = []

    if profile.email:
        score += 5
        strengths.append("Adresse email professionnelle détectée")
    else:
        improvements.append("Ajouter une adresse email valide")

    if profile.linkedin_url:
        score += 5
        strengths.append("Lien de profil LinkedIn présent")
    else:
        improvements.append("Inclure votre lien de profil LinkedIn pour rassurer les recruteurs")

    if profile.skills and len(profile.skills) >= 4:
        score += 10
        strengths.append(f"{len(profile.skills)} compétences clés identifiées")
    else:
        improvements.append("Ajouter davantage de compétences techniques ciblées (min. 5)")

    if profile.experience_years and profile.experience_years > 0:
        score += 5
        strengths.append(f"Expérience quantifiée ({int(profile.experience_years)} ans)")
    else:
        improvements.append("Préciser le nombre d'années d'expérience globale")

    score = min(98, max(55, score))

    score_label = "Excellent" if score >= 88 else "Très Bon" if score >= 78 else "À Optimiser"

    skills_str = ", ".join(profile.skills[:3]) if profile.skills else "Tech & Produit"
    name_str = profile.full_name or "Candidat"
    
    optimized_headline = profile.headline or f"Développeur & Spécialiste {skills_str}"
    optimized_summary = (
        f"Professionnel expérimenté ({profile.experience_years or 2}+ ans) en {skills_str}. "
        f"Expertise éprouvée dans la conception de solutions performantes et scalables, alignées sur les exigences métier."
    )

    suggested_skills = ["Docker", "CI/CD", "TypeScript", "Agile/Scrum"]
    # Filter out skills already in profile
    suggested_skills = [s for s in suggested_skills if s not in profile.skills]

    return CVAuditResult(
        ats_score=score,
        score_label=score_label,
        strengths=strengths or ["Structure lisible"],
        improvements=improvements or ["Ajouter plus de métriques chiffrées sur les projets"],
        optimized_headline=optimized_headline,
        optimized_summary=optimized_summary,
        suggested_skills=suggested_skills,
    )


async def audit_candidate_profile(profile: ParsedCandidateProfile) -> CVAuditResult:
    """
    Audit a candidate profile for ATS optimization using Gemini 2.5 Flash.
    Falls back to heuristic rules if Gemini API is missing or fails.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        logger.info("GEMINI_API_KEY not configured. Using heuristic ATS audit.")
        return heuristic_audit_profile(profile)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": CVAuditResult,
            }
        )

        prompt = f"""
        Tu es un expert RH et ATS francophone. Realise un audit ATS et propose un profil optimise EN FRANCAIS pour ce candidat.

        Candidat :
        Nom : {profile.full_name or 'Non renseigné'}
        Titre actuel : {profile.headline or 'Non renseigné'}
        Compétences : {', '.join(profile.skills) if profile.skills else 'Aucune'}
        Années d'expérience : {profile.experience_years or 'Non renseigné'}
        Aperçu du texte : {profile.extracted_text_preview or ''}

        EXIGENCES DE SORTIE (JSON STRICT) :
        - ats_score : note entre 68 et 96
        - score_label : "Excellent", "Très Bon" ou "À Optimiser"
        - strengths : 2 à 3 points forts en français
        - improvements : 2 à 3 pistes d'amélioration concrètes en français
        - optimized_headline : un titre professionnel percutant EN FRANÇAIS (ex: "Développeur Full Stack React & Node.js")
        - optimized_summary : une synthèse professionnelle de 2 à 3 phrases RÉDIGÉE EN FRANÇAIS IMPECCABLE. Ne laisse aucun mot en anglais sauf les termes techniques.
        - suggested_skills : 3 à 4 compétences techniques complémentaires à ajouter.
        """

        response = model.generate_content(prompt)
        parsed = json.loads(response.text)
        return CVAuditResult(**parsed)

    except Exception as e:
        logger.error(f"Gemini error during CV audit: {e}. Falling back to heuristics.", exc_info=True)
        return heuristic_audit_profile(profile)
