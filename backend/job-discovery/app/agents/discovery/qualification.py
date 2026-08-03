"""
Qualification Agent — uses Gemini API to extract structured parameters
(tech stack, experience, contract type, remote policy, salary, and summary)
from raw job descriptions.
"""

import json
import logging
import re
from typing import Optional

import google.generativeai as genai
from pydantic import BaseModel, Field

from app.config import settings
from app.models.job_posting import ContractType, RemotePolicy

logger = logging.getLogger(__name__)


class QualifiedJobResponse(BaseModel):
    tech_stack: list[str] = Field(
        description="Technologies, frameworks, and programming languages mentioned (e.g. ['python', 'fastapi', 'react'])"
    )
    experience_years_required: Optional[float] = Field(
        description="Minimum years of experience required. Null if not specified."
    )
    contract_type: str = Field(
        description="Must be one of: 'cdi', 'cdd', 'freelance', 'internship', 'alternance', 'other'"
    )
    remote_policy: str = Field(
        description="Must be one of: 'remote', 'hybrid', 'onsite', 'unknown'"
    )
    salary_min: Optional[int] = Field(description="Minimum salary in EUR per year. Null if not specified.")
    salary_max: Optional[int] = Field(description="Maximum salary in EUR per year. Null if not specified.")
    summary_french: str = Field(description="A concise 2-sentence summary of the job description in French.")


# Fallback/heuristic parser if Gemini is not configured
def heuristic_qualify(title: str, text: str) -> dict:
    """Fallback parser using word boundary regex matching if no Gemini API key is configured."""
    text_lower = text.lower()
    title_lower = title.lower()

    # Tech stack extraction (using regex word boundary to prevent matching substrings)
    known_techs = [
        "python", "javascript", "typescript", "react", "vue", "angular", "node",
        "fastapi", "django", "flask", "go", "rust", "java", "spring", "c++",
        "c#", ".net", "ruby", "rails", "php", "laravel", "aws", "gcp", "azure",
        "docker", "kubernetes", "postgresql", "mysql", "redis", "mongodb",
        "next.js", "tailwind", "html", "css"
    ]
    tech_stack = []
    for t in known_techs:
        escaped = re.escape(t)
        if t in ["c++", "c#", ".net", "next.js"]:
            pattern = r'(?:^|[^a-zA-Z0-9])' + escaped + r'(?:$|[^a-zA-Z0-9])'
        else:
            pattern = r'\b' + escaped + r'\b'
        
        if re.search(pattern, text_lower) or re.search(pattern, title_lower):
            tech_stack.append(t)

    # Contract Type guess
    contract_type = "cdi"  # default to cdi if not found, since most tech jobs are CDI
    if any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) or re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in ["cdi", "permanent", "full-time"]):
        contract_type = "cdi"
    elif any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) or re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in ["cdd", "temp"]):
        contract_type = "cdd"
    elif any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) or re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in ["freelance", "contractor", "indépendant"]):
        contract_type = "freelance"
    elif any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) or re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in ["intern", "stage", "stagiaire", "internship"]):
        contract_type = "internship"
    elif any(re.search(r'\b' + re.escape(k) + r'\b', title_lower) or re.search(r'\b' + re.escape(k) + r'\b', text_lower) for k in ["alternance", "apprentissage", "apprenti"]):
        contract_type = "alternance"

    # Remote Policy guess
    remote_policy = "hybrid"  # default to hybrid
    if any(k in text_lower for k in ["télétravail complet", "remote", "télétravail total", "100% remote", "fully remote"]):
        remote_policy = "remote"
    elif any(k in text_lower for k in ["hybrid", "hybride", "télétravail partiel", "jours de télétravail"]):
        remote_policy = "hybrid"
    elif any(k in text_lower for k in ["onsite", "sur site", "présentiel"]):
        remote_policy = "onsite"

    # Experience guess
    experience = None
    exp_match = re.search(r'(\d+)\s*(?:years?|ans?)\s*(?:d\'?\s*expérience)?', text_lower)
    if exp_match:
        experience = float(exp_match.group(1))
    else:
        # Fallback based on title keywords
        if "senior" in title_lower or "lead" in title_lower:
            experience = 5.0
        elif "junior" in title_lower:
            experience = 1.0

    return {
        "tech_stack": tech_stack,
        "experience_years_required": experience,
        "contract_type": contract_type,
        "remote_policy": remote_policy,
        "salary_min": None,
        "salary_max": None,
        "summary_french": f"Poste de {title}. Analyse automatisée via heuristiques.",
    }


async def qualify_job_description(title: str, description: str) -> dict:
    """
    Qualify a job posting description using Gemini 1.5/2.5 Flash API.
    Falls back to simple regex/heuristic parsing if api_key is missing.
    """
    api_key = settings.gemini_api_key
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured. Falling back to heuristic parsing.")
        return heuristic_qualify(title, description)

    try:
        # Initialize Gemini client
        genai.configure(api_key=api_key)
        
        # Use settings.gemini_model for structured data extraction
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": QualifiedJobResponse,
            }
        )

        prompt = f"""
        Analyze the following job description and extract structured information.
        
        Job Title: {title}
        
        Job Description:
        {description}
        """

        response = model.generate_content(prompt)
        parsed_data = json.loads(response.text)
        return parsed_data

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}. Falling back to heuristics.", exc_info=True)
        return heuristic_qualify(title, description)
