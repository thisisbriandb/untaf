"""
Resume and LinkedIn Profile Extractor Agent —
Extracts candidate attributes (Name, Email, Phone, LinkedIn, GitHub, Skills, Experience, Headline)
from raw PDF resume files and LinkedIn profile URLs using pypdf, Regex, and Gemini API.
"""

import io
import json
import logging
import re
from typing import Optional

import httpx
from pypdf import PdfReader

from app import llm
from app.config import settings
from app.schemas.candidate import ParsedCandidateProfile

logger = logging.getLogger(__name__)

# Known skill keywords for fallback regex extraction
KNOWN_SKILLS = [
    "python", "typescript", "javascript", "react", "next.js", "vue", "angular", "node.js",
    "fastapi", "django", "flask", "express", "go", "rust", "java", "spring", "c++", "c#",
    ".net", "ruby", "rails", "php", "laravel", "sql", "postgresql", "mysql", "mongodb",
    "redis", "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ci/cd", "git",
    "graphql", "rest api", "tailwind", "css", "html", "product management", "scrum", "agile"
]


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text content from PDF bytes using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_pages = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_pages.append(extracted)
        return "\n".join(text_pages)
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return ""


FORBIDDEN_NAME_KEYWORDS = [
    "centre d'intérêt", "centres d'intérêt", "centres d'interet", "centres d'interets",
    "centre d'interet", "interests", "hobbies", "curriculum vitae", "curriculum", "vitae",
    "resume", "cv", "profil", "profile", "contact", "informations", "information",
    "compétences", "competences", "skills", "expériences", "experiences", "experience",
    "formation", "formations", "education", "langues", "languages", "projets", "projects",
    "certifications", "references", "références", "a propos", "à propos", "summary"
]


def sanitize_full_name(name: str | None, email: str | None, raw_text: str) -> str | None:
    """Ensure extracted full name is not a section title like 'Centres d'intérêt'."""
    if name:
        name_clean = name.strip()
        name_lower = name_clean.lower()
        is_invalid = any(kw in name_lower for kw in FORBIDDEN_NAME_KEYWORDS)
        if not is_invalid and 1 <= len(name_clean.split()) <= 4 and not re.search(r'[\d@:/\\=]', name_clean):
            return name_clean.title()

    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    for line in lines[:10]:
        l_lower = line.lower()
        if any(kw in l_lower for kw in FORBIDDEN_NAME_KEYWORDS):
            continue
        if "@" in line or "http" in line or ":" in line or "/" in line or re.search(r'\d', line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.isalpha() or '-' in w for w in words):
            return line.title()

    if email:
        username = email.split('@')[0]
        clean_user = re.sub(r'[\._-]', ' ', username)
        clean_user = re.sub(r'\d+', '', clean_user).strip()
        if len(clean_user) >= 2:
            return clean_user.title()

    return None


def heuristic_extract_profile(raw_text: str) -> ParsedCandidateProfile:
    """Extract candidate profile using Regex and Heuristics when LLM is unavailable."""
    text_lower = raw_text.lower()

    # 1. Email extraction
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_text)
    email = email_match.group(0) if email_match else None

    # 2. LinkedIn URL
    linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', raw_text, re.IGNORECASE)
    linkedin_url = linkedin_match.group(0) if linkedin_match else None

    # 3. GitHub URL
    github_match = re.search(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+/?', raw_text, re.IGNORECASE)
    github_url = github_match.group(0) if github_match else None

    # 4. Phone extraction
    phone_match = re.search(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}(?:[\s.-]?\d{2,4})?', raw_text)
    phone = phone_match.group(0).strip() if phone_match and len(re.sub(r'\D', '', phone_match.group(0))) >= 8 else None

    # 5. Full name estimation with section title filtering
    full_name = sanitize_full_name(None, email, raw_text)

    # 6. Skills extraction
    skills = []
    for skill in KNOWN_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            formatted_skill = skill.title() if not skill in ["aws", "gcp", "sql", "css", "html", "ci/cd"] else skill.upper()
            if formatted_skill not in skills:
                skills.append(formatted_skill)

    # 7. Experience years estimation
    exp_years = None
    exp_match = re.search(r'(\d+)\s*(?:years?|ans?)\s*(?:d\'?\s*expérience)?', text_lower)
    if exp_match:
        exp_years = float(exp_match.group(1))

    preview = raw_text[:300] + "..." if len(raw_text) > 300 else raw_text

    return ParsedCandidateProfile(
        full_name=full_name,
        email=email,
        phone=phone,
        github_url=github_url,
        linkedin_url=linkedin_url,
        # Pas de titre inventé : sans IA, on ne sait pas le lire.
        headline=None,
        summary=preview,
        skills=skills,
        experience_years=exp_years,
        preferred_locations=["Paris"],
        preferred_contract_types=["cdi"],
        extracted_text_preview=preview,
    )


FORBIDDEN_GENERIC_SKILLS = {
    "programming", "problem solving", "ai tools", "software development",
    "computer science", "teamwork", "communication", "soft skills", "hard skills",
    "developer", "development", "coding", "technologies", "problem-solving"
}


def sanitize_skills(skills: list[str]) -> list[str]:
    """Clean up and deduplicate skills array, removing generic noise."""
    cleaned = []
    seen_lower = set()
    for s in skills:
        if not s or not isinstance(s, str):
            continue
        s_clean = s.strip()
        s_lower = s_clean.lower()
        if s_lower in FORBIDDEN_GENERIC_SKILLS or len(s_clean) < 2:
            continue
        if s_lower in seen_lower:
            continue
        seen_lower.add(s_lower)
        cleaned.append(s_clean)
    return cleaned[:10]


async def parse_resume(pdf_bytes: bytes, filename: str = "cv.pdf") -> ParsedCandidateProfile:
    """
    Parses a PDF resume file using Gemini LLM if API key configured,
    or falls back to regex-based heuristic extraction.
    """
    raw_text = extract_text_from_pdf(pdf_bytes)
    if not raw_text.strip():
        logger.warning(f"Empty text extracted from PDF {filename}.")
        # CV scanné : rien à lire, on le dit au lieu d'inventer un titre.
        return ParsedCandidateProfile(text_detected=False)

    api_key = settings.gemini_api_key
    if not api_key:
        logger.info("GEMINI_API_KEY not set. Using heuristic resume parsing.")
        return heuristic_extract_profile(raw_text)

    try:
        prompt = f"""
        Tu es un expert recruteur francophone et un parser de CV de haute précision.
        Analyse le texte de CV ci-dessous et extrait les informations au format JSON strict.

        CONSIGNES IMPÉRATIVES DE LANGUE ET QUALITÉ :
        1. Rédige IMPÉRATIVEMENT la synthèse ('summary') et le titre professionnel ('headline') EN FRANÇAIS SOIGNÉ, PERCUTANT ET PROFESSIONNEL. Si le CV original est en anglais, TRADUIS et synthétise en français élégant.
        2. Extrais le nom complet ('full_name') de la personne réelle (NE PAS utiliser d'intitulés de section comme 'Centres d'intérêt' ou 'Curriculum Vitae').
        3. Pour la liste des compétences ('skills') :
           - Extrais uniquement 6 à 10 compétences techniques et fonctionnelles précises (ex: React, TypeScript, Python, Docker, PostgreSQL, Flutter, C#).
           - EXCLUS STRICTEMENT les compétences vagues ou génériques comme "Programming", "Problem Solving", "AI Tools", "Teamwork", "Software Development".
           - Évite les doublons évidents.
        4. Identifie email, phone, linkedin_url, github_url, experience_years.
        5. EXTRAIS LE PARCOURS COMPLET — c'est la partie la plus importante :
           - 'experiences' : TOUS les postes tenus, du plus récent au plus ancien.
             Un STAGE, une ALTERNANCE, un JOB ÉTUDIANT, une MISSION FREELANCE ou
             un SERVICE CIVIQUE sont des expériences professionnelles à part
             entière : ne les omets JAMAIS. Un CV de junior n'a souvent que ça.
             Format de chaque entrée :
             {{"jobTitle": str, "company": str, "location": str,
               "startDate": "AAAA-MM", "endDate": "AAAA-MM" ou "present",
               "isCurrent": bool, "highlights": [str]}}
             'highlights' reprend les puces du CV telles qu'elles sont écrites.
           - 'education' : {{"degree": str, "institution": str, "location": str,
             "startYear": "AAAA", "endYear": "AAAA"}}
           - 'languages' : {{"language": str, "level": str}}
           Si une date est absente du CV, mets une chaîne vide plutôt que
           d'inventer. Ne fusionne jamais deux postes distincts.

        Texte du CV :
        {raw_text[:12000]}
        """

        parsed_json = json.loads(await llm.generate(prompt, json=True))
        profile = ParsedCandidateProfile(**parsed_json)
        
        # Sanitize full name against section titles
        profile.full_name = sanitize_full_name(profile.full_name, profile.email, raw_text)

        # Sanitize and deduplicate skills
        if profile.skills:
            profile.skills = sanitize_skills(profile.skills)

        # Ensure extracted_text_preview is populated
        if not profile.extracted_text_preview:
            profile.extracted_text_preview = raw_text[:300] + "..." if len(raw_text) > 300 else raw_text
            
        # Fallback regex check for LinkedIn URL if LLM missed it
        if not profile.linkedin_url:
            linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+/?', raw_text, re.IGNORECASE)
            if linkedin_match:
                profile.linkedin_url = linkedin_match.group(0)

        return profile

    except Exception as e:
        logger.error(f"Gemini API error during resume parsing: {e}. Falling back to heuristics.", exc_info=True)
        return heuristic_extract_profile(raw_text)


async def parse_linkedin_url(linkedin_url: str) -> ParsedCandidateProfile:
    """
    Tente de lire les métadonnées publiques d'un profil LinkedIn.

    En pratique, LinkedIn répond HTTP 999 à toute requête anonyme : la lecture
    échoue quasi systématiquement. Cette fonction ne renvoie donc, le plus
    souvent, que l'URL et un nom *deviné* depuis le slug.

    Elle ne doit rien inventer d'autre. Un profil rempli de valeurs par défaut
    est pire qu'un profil vide : il se propage silencieusement dans le CV et
    dans le mandat de recherche, sans que l'utilisateur ait rien demandé.
    """
    cleaned_url = linkedin_url.strip()
    if not cleaned_url.startswith("http"):
        cleaned_url = f"https://{cleaned_url}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    full_name = None
    headline = None

    # Try extracting name from LinkedIn URL slug (e.g. linkedin.com/in/jean-dupont-1234 -> Jean Dupont)
    match = re.search(r'linkedin\.com/in/([^/]+)', cleaned_url)
    if match:
        raw_slug = match.group(1)
        # remove trailing numbers or hashes
        clean_slug = re.sub(r'-\d+$', '', raw_slug)
        name_parts = clean_slug.split('-')
        full_name = " ".join([p.capitalize() for p in name_parts if p])

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.get(cleaned_url, headers=headers)
            if resp.status_code == 200:
                html = resp.text
                # Extract og:title or title tag
                title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\'"]+)["\']', html, re.IGNORECASE)
                if title_match:
                    og_title = title_match.group(1)
                    # Often "Name - Title | LinkedIn"
                    headline = og_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "")
                    if " - " in headline and not full_name:
                        parts = headline.split(" - ", 1)
                        full_name = parts[0].strip()
                        headline = parts[1].strip()

            else:
                # 999 = blocage anti-bot de LinkedIn. C'est le cas nominal.
                logger.info(
                    "LinkedIn a refusé la lecture de %s (HTTP %s)",
                    cleaned_url, resp.status_code,
                )

    except Exception as e:
        logger.warning(f"Could not fetch LinkedIn metadata from URL {cleaned_url}: {e}")

    # Uniquement ce qui est réellement connu. Pas de nom de repli, pas de titre
    # bricolé à partir de l'URL, pas de préférences par défaut.
    return ParsedCandidateProfile(
        full_name=full_name,
        linkedin_url=cleaned_url,
        headline=headline,
        skills=[],
        extracted_text_preview=(
            None if headline
            else "Profil LinkedIn non lisible : LinkedIn bloque les lectures anonymes."
        ),
    )
