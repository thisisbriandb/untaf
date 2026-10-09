"""
Deterministic signals derived from a job posting: language, country, job
family, seniority.

These are what the hard filters run on. They are computed here rather than
asked of the LLM so they behave identically on the Gemini path and on the
heuristic fallback, and so existing rows already qualified keep working
without a re-parse.
"""

import re
from datetime import datetime, timezone

# ── Language ───────────────────────────────────────────────────────────────

# Deliberately built from tokens that are *distinctive*: "de" is dropped
# because it belongs to French, Spanish, Italian, Portuguese and Dutch alike.
_STOPWORDS: dict[str, set[str]] = {
    "fr": {"les", "une", "pour", "dans", "avec", "vous", "nous", "sur", "est",
           "aux", "qui", "que", "nos", "votre", "chez", "être", "plus", "sera",
           "notre", "vos", "ainsi", "afin", "cette", "leurs"},
    "en": {"the", "and", "for", "with", "you", "our", "are", "this", "that",
           "will", "your", "have", "from", "their", "about", "who", "what",
           "they", "been", "were", "which", "these"},
    "de": {"der", "die", "das", "und", "für", "mit", "sie", "wir", "ist",
           "den", "dem", "ein", "eine", "von", "bei", "auf", "als", "auch",
           "nicht", "sich", "werden", "haben", "unser", "unsere"},
    "es": {"los", "las", "para", "con", "que", "una", "por", "del", "está",
           "nuestro", "nuestra", "tus", "eres", "serás", "sobre"},
    "it": {"gli", "per", "con", "che", "una", "del", "nel", "sono", "nostra",
           "nostro", "sarà", "anche", "questo"},
    "nl": {"het", "een", "van", "voor", "met", "wij", "aan", "bij", "zijn",
           "onze", "wordt", "worden", "jouw", "jij"},
    "pt": {"para", "com", "que", "uma", "não", "você", "nossa", "nosso",
           "será", "sobre", "seus"},
}

_WORD_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüÿœæß]+", re.I)

_MIN_LANG_HITS = 4


def detect_language(text: str | None) -> str:
    """Best-effort ISO-639-1 code, or 'unknown' when there is too little signal."""
    if not text:
        return "unknown"

    tokens = [t.lower() for t in _WORD_RE.findall(text[:4000])]
    if len(tokens) < 20:
        return "unknown"

    counts = {lang: sum(1 for t in tokens if t in words)
              for lang, words in _STOPWORDS.items()}

    best = max(counts, key=lambda k: counts[k])
    if counts[best] < _MIN_LANG_HITS:
        return "unknown"

    # Ambiguous when the runner-up is within 20% — better to say nothing than
    # to reject a job on a coin flip.
    runner_up = max((v for k, v in counts.items() if k != best), default=0)
    if runner_up and runner_up / counts[best] > 0.8:
        return "unknown"

    return best


# ── Country ────────────────────────────────────────────────────────────────

_CITY_COUNTRY: dict[str, str] = {
    # France
    "paris": "FR", "lyon": "FR", "marseille": "FR", "toulouse": "FR",
    "bordeaux": "FR", "lille": "FR", "nantes": "FR", "nice": "FR",
    "strasbourg": "FR", "rennes": "FR", "montpellier": "FR", "grenoble": "FR",
    "sophia antipolis": "FR", "aix-en-provence": "FR", "annecy": "FR",
    "toulon": "FR", "reims": "FR", "dijon": "FR", "angers": "FR",
    "clermont-ferrand": "FR", "saint-étienne": "FR", "le mans": "FR",
    "ile-de-france": "FR", "île-de-france": "FR", "la défense": "FR",
    # Germany
    "berlin": "DE", "munich": "DE", "münchen": "DE", "hamburg": "DE",
    "düsseldorf": "DE", "dusseldorf": "DE", "frankfurt": "DE", "cologne": "DE",
    "köln": "DE", "stuttgart": "DE", "leipzig": "DE", "dresden": "DE",
    # Rest of Europe
    "london": "GB", "manchester": "GB", "edinburgh": "GB", "bristol": "GB",
    "madrid": "ES", "barcelona": "ES", "barcelone": "ES", "valencia": "ES",
    "sevilla": "ES", "malaga": "ES",
    "lisbon": "PT", "lisbonne": "PT", "lisboa": "PT", "porto": "PT",
    "amsterdam": "NL", "rotterdam": "NL", "utrecht": "NL", "eindhoven": "NL",
    "brussels": "BE", "bruxelles": "BE", "antwerp": "BE", "anvers": "BE",
    "gand": "BE", "ghent": "BE",
    "geneva": "CH", "genève": "CH", "zurich": "CH", "zürich": "CH",
    "lausanne": "CH", "basel": "CH", "bâle": "CH",
    "luxembourg": "LU",
    "milan": "IT", "milano": "IT", "rome": "IT", "roma": "IT", "turin": "IT",
    "torino": "IT", "naples": "IT",
    "dublin": "IE", "cork": "IE",
    "vienna": "AT", "vienne": "AT", "wien": "AT",
    "copenhagen": "DK", "copenhague": "DK",
    "stockholm": "SE", "gothenburg": "SE",
    "oslo": "NO", "helsinki": "FI",
    "warsaw": "PL", "varsovie": "PL", "krakow": "PL", "cracovie": "PL",
    "prague": "CZ", "budapest": "HU", "bucharest": "RO", "bucarest": "RO",
    "belgrade": "RS", "beograd": "RS", "sofia": "BG", "zagreb": "HR",
    "athens": "GR", "athènes": "GR", "istanbul": "TR",
    # Americas
    "new york": "US", "san francisco": "US", "austin": "US", "boston": "US",
    "seattle": "US", "chicago": "US", "los angeles": "US", "denver": "US",
    "montreal": "CA", "montréal": "CA", "toronto": "CA", "vancouver": "CA",
    "quebec": "CA", "québec": "CA",
    "são paulo": "BR", "sao paulo": "BR", "buenos aires": "AR",
    # Africa / Middle East / Asia
    "casablanca": "MA", "rabat": "MA", "marrakech": "MA",
    "tunis": "TN", "alger": "DZ", "algiers": "DZ",
    "dakar": "SN", "abidjan": "CI", "cairo": "EG", "le caire": "EG",
    "dubai": "AE", "dubaï": "AE", "tel aviv": "IL",
    "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN", "delhi": "IN",
    "singapore": "SG", "singapour": "SG", "tokyo": "JP", "sydney": "AU",
}

_COUNTRY_NAMES: dict[str, str] = {
    "france": "FR", "germany": "DE", "deutschland": "DE", "allemagne": "DE",
    "united kingdom": "GB", "royaume-uni": "GB", "england": "GB", "uk": "GB",
    "spain": "ES", "espagne": "ES", "españa": "ES",
    "portugal": "PT", "netherlands": "NL", "pays-bas": "NL", "nederland": "NL",
    "belgium": "BE", "belgique": "BE", "belgië": "BE",
    "switzerland": "CH", "suisse": "CH", "schweiz": "CH",
    "luxembourg": "LU", "italy": "IT", "italie": "IT", "italia": "IT",
    "ireland": "IE", "irlande": "IE", "austria": "AT", "autriche": "AT",
    "denmark": "DK", "danemark": "DK", "sweden": "SE", "suède": "SE",
    "norway": "NO", "norvège": "NO", "finland": "FI", "finlande": "FI",
    "poland": "PL", "pologne": "PL", "czech republic": "CZ", "tchéquie": "CZ",
    "hungary": "HU", "hongrie": "HU", "romania": "RO", "roumanie": "RO",
    "serbia": "RS", "serbie": "RS", "bulgaria": "BG", "bulgarie": "BG",
    "croatia": "HR", "croatie": "HR", "greece": "GR", "grèce": "GR",
    "turkey": "TR", "turquie": "TR",
    "united states": "US", "usa": "US", "états-unis": "US", "etats-unis": "US",
    "canada": "CA", "brazil": "BR", "brésil": "BR", "argentina": "AR",
    "morocco": "MA", "maroc": "MA", "tunisia": "TN", "tunisie": "TN",
    "algeria": "DZ", "algérie": "DZ", "senegal": "SN", "sénégal": "SN",
    "ivory coast": "CI", "côte d'ivoire": "CI", "egypt": "EG", "égypte": "EG",
    "israel": "IL", "israël": "IL", "india": "IN", "inde": "IN",
    "singapore": "SG", "japan": "JP", "japon": "JP",
    "australia": "AU", "australie": "AU",
    "united arab emirates": "AE", "émirats arabes unis": "AE",
}


def detect_country(location: str | None) -> str | None:
    """ISO-3166-1 alpha-2 from a free-text location, or None."""
    if not location:
        return None

    text = location.strip().lower()

    # Country name wins over city — "Customer Service - Germany" beats a city
    # match hidden elsewhere in the string.
    for name, code in _COUNTRY_NAMES.items():
        if re.search(rf"(?:^|[^a-zà-ÿ]){re.escape(name)}(?:$|[^a-zà-ÿ])", text):
            return code

    for city, code in _CITY_COUNTRY.items():
        if re.search(rf"(?:^|[^a-zà-ÿ]){re.escape(city)}(?:$|[^a-zà-ÿ])", text):
            return code

    return None


# ── Job family ─────────────────────────────────────────────────────────────

# Ordered: the first family whose keyword hits wins, so the most specific
# titles are listed before the catch-alls.
_FAMILY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("data", ("data scientist", "data engineer", "data analyst", "analytics engineer",
              "machine learning", "ml engineer", "ai engineer", "deep learning",
              "business intelligence", "statisticien", "datamining", "big data")),
    ("education", ("enseignant", "professeur", " formateur", " formatrice", "teacher",
                   "instituteur", "institutrice", "soutien scolaire",
                   "conseiller pédagogique", "conseillère pédagogique")),
    ("sales", ("account executive", "account manager", "business developer",
               "business development", "sales development", "sales manager",
               "sales representative", " sdr", " bdr", "commercial", "vente",
               "revenue", "partnership manager", "chargé d'affaires")),
    ("support", ("customer care", "customer support", "customer success",
                 "support agent", "service client", "hotline", "helpdesk",
                 "conseiller client", "technicien support")),
    ("marketing", ("marketing", "growth", "seo", "sea", "content manager",
                   "communication", "brand", "social media", "acquisition")),
    ("hr", ("recruiter", "recruteur", "talent acquisition", "talent partner",
            "human resources", "ressources humaines", "people ops", "hrbp",
            "chargé de recrutement")),
    ("finance", ("comptab", "accountant", "controller", "contrôleur de gestion",
                 "auditeur", "audit financier", "trésorerie", "analyste financier",
                 "cfo", "daf")),
    ("design", ("ux designer", "ui designer", "product designer", "designer",
                "graphiste", "directeur artistique", "motion design", "ux/ui")),
    ("product", ("product manager", "product owner", "chef de produit",
                 "product marketing", "responsable produit")),
    ("legal", ("juriste", "legal counsel", "avocat", "compliance officer",
               "dpo", "rgpd")),
    ("ops", ("supply chain", "logistique", "logistics", "office manager",
             "operations manager", "onboarding consultant", "responsable d'exploitation",
             "planificateur", "achats", "procurement")),
    ("construction", ("conducteur de travaux", "conductrice de travaux", "chef de chantier",
                      "cheffe de chantier", "btp", "maçon", "macon", "électricien",
                      "electricien", "plombier", "chauffagiste", "plaquiste", "couvreur",
                      "charpentier", "carreleur", "menuisier", "peintre en bâtiment",
                      "économiste de la construction", "ingénieur travaux", "géomètre")),
    ("software", ("developer", "développeur", "developpeur", "software engineer",
                  "ingénieur logiciel", "backend", "back-end", "frontend",
                  "front-end", "full stack", "fullstack", "devops", "sre",
                  "site reliability", "architect", "architecte", "tech lead",
                  "programmeur", "ios ", "android ", "mobile engineer",
                  "qa engineer", "test engineer", "cloud engineer", "platform engineer",
                  "security engineer", "cybersécurité", "cybersecurity",
                  "administrateur système", "system administrator", "sysadmin")),
    ("engineering", ("ingénieur mécanique", "ingénieur civil", "ingénieur process",
                     "bureau d'études", "automaticien", "électronicien")),
    ("health", ("infirmier", "médecin", "aide-soignant", "pharmacien",
                "kinésithérapeute", "sage-femme", "radioprotection", "physique médicale",
                "physicien médical", "dosimétri", "manipulateur", "radiolog", "biologiste",
                "laborantin", "préparateur en pharmacie")),
]

_FAMILY_MIN_TECH = 3

#: Ce qui compte comme technologie logicielle pour le repli ci-dessous. Les
#: « compétences » d'une annonce ne sont pas toutes des technos : une offre
#: de radioprotection en liste trois (dosimétrie, réglementation…), et le
#: repli la classait « software ».
_SOFTWARE_TECH = {
    "python", "java", "javascript", "typescript", "react", "vue", "angular", "node",
    "next.js", "php", "symfony", "laravel", "ruby", "rails", "go", "rust", "c#", ".net",
    "c++", "c", "kotlin", "swift", "scala", "sql", "postgresql", "mysql", "mongodb",
    "redis", "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "linux", "git",
    "django", "flask", "fastapi", "spring", "graphql", "html", "css", "tailwind",
    "react-native", "flutter", "dart", "elasticsearch", "kafka", "spark", "airflow",
    "ci/cd", "jenkins", "gitlab", "github", "devops", "api", "rest", "microservices",
}


#: Annonces génériques des sites carrière : pas un poste, un vivier.
_GENERIC_POSTING = re.compile(
    r"\b(spontaneous|unsolicited|open|general)\s+application\b|candidature\s+spontan|"
    r"talent\s+(pool|community)|vivier|future\s+opportunit|join\s+our\s+talent",
    re.I,
)


def is_generic_posting(title: str | None) -> bool:
    """« Spontaneous Application », « Talent Pool – Paris » : aucun poste derrière."""
    return bool(_GENERIC_POSTING.search(title or ""))


# ── Écoles qui recrutent des élèves sous couvert d'alternance ──────────────
#
# Des écoles, CFA et organismes de formation publient des « offres »
# d'alternance pour remplir leurs promotions : le candidat croit postuler à un
# poste, il s'inscrit à une formation. Une école peut aussi embaucher un vrai
# alternant (assistant RH, chargé de com…) : un seul indice ne suffit pas à
# écarter, il en faut deux qui concordent.

#: NAF « 85 » : enseignement (85.59A formation continue, 85.42Z supérieur…).
_EDUCATION_NAF = re.compile(r"^\s*85")
_SCHOOL_NAME = re.compile(
    r"\b(e|é)coles?\b|\bschool\b|\bcfa\b|\bcampus\b|\binstitut\b|\bacad(e|é)m(y|ie)\b|"
    r"\bcentre de formation\b|\borganisme de formation\b|\bformations?\b|\bbusiness school\b|"
    r"\bapprentissage\b",
    re.I,
)
#: Instituts, académies… qui sont de vrais employeurs.
_REAL_EMPLOYERS = re.compile(
    r"institut (pasteur|curie|gustave roussy|national|de recherche|fran(c|ç)ais du p(e|é)trole)|"
    r"\binserm\b|\bcnrs\b|\binrae?\b|\bifremer\b|acad(e|é)mie (de|d')|\bminist(e|è)re\b",
    re.I,
)
_STUDENT_PITCH = re.compile(
    r"formation (100 ?% )?(gratuite|financ(e|é)e|prise en charge)|frais de (scolarit(e|é)|formation) "
    r"(pris en charge|financ|offert)|entreprises? partenaires?|r(e|é)seau d'entreprises|"
    r"rejoin(s|dre|t|ez) (notre|nos) (e|é)cole|int(e|è)gre[rz]? (notre|nos) (formation|programme|(e|é)cole)|"
    r"\badmissions?\b|inscri(s|ption|vez|re)[- ](toi|vous)?|places? limit(e|é)es?|"
    r"rentr(e|é)e (de |en )?(septembre|octobre|janvier|f(e|é)vrier|mars)|nos (e|é)tudiants|"
    r"pr(e|é)pare[rz]? (un|le|ton|votre) (titre|dipl(o|ô)me|bachelor|mast(e|è)re|bts)|"
    r"titre rncp|nous (te|vous) (trouvons|accompagnons dans la recherche d')(une|ton|votre) entreprise|"
    r"recrutons pour (le compte de )?(nos|des) (entreprises|partenaires|clients)",
    re.I,
)


def training_org_evidence(
    company_name: str | None,
    description: str | None,
    employer: dict | None = None,
) -> tuple[str | None, str]:
    """
    (« strong » | « weak » | None, motif) : l'annonce vient-elle d'une école
    qui recrute des élèves ? « strong » demande deux indices concordants.
    """
    employer = employer or {}
    name = company_name or ""
    clues: list[str] = []

    naf = str(employer.get("naf") or employer.get("sector_code") or "")
    sector = str(employer.get("sector") or employer.get("naf_label") or "")
    if _EDUCATION_NAF.match(naf.replace(".", "")) or re.search(r"enseignement|formation", sector, re.I):
        clues.append(f"employeur du secteur de l'enseignement ({naf or sector})")

    for label in dict.fromkeys(x for x in (name, employer.get("legal_name")) if x):
        if _SCHOOL_NAME.search(label) and not _REAL_EMPLOYERS.search(label):
            clues.append(f"nom d'école ou d'organisme de formation (« {label} »)")
            break

    pitches = {m.group(0).lower() for m in _STUDENT_PITCH.finditer(description or "")}
    if pitches:
        clues.append("annonce qui recrute des élèves (" + ", ".join(f"« {x} »" for x in sorted(pitches)[:2]) + ")")
    strong = len(clues) >= 2 or len(pitches) >= 2
    if not clues:
        return None, ""
    return ("strong" if strong else "weak"), " ; ".join(clues)


def detect_job_family(title: str | None, tech_stack: list[str] | None = None) -> str:
    """Coarse job family, or 'unknown'."""
    text = f" {(title or '').lower()} "

    for family, keywords in _FAMILY_KEYWORDS:
        if any(kw in text for kw in keywords):
            return family

    # A dense *software* stack on an unrecognised title is still a tech job.
    if tech_stack:
        from app.agents.discovery.skills import canonical
        techs = {canonical(t) for t in tech_stack if t}
        if len(techs & _SOFTWARE_TECH) >= _FAMILY_MIN_TECH:
            return "software"

    return "unknown"


# ── Seniority ──────────────────────────────────────────────────────────────

SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "lead"]

_SENIORITY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("intern", ("intern", "stage", "stagiaire", "alternance", "apprenti",
                "apprentice", "graduate program", "internship")),
    ("lead", ("lead", "principal", "staff engineer", "head of", "director",
              "directeur", "vp ", "chief", "manager", "responsable",
              "architect", "architecte")),
    ("senior", ("senior", "sr.", "sr ", "confirmé", "expérimenté", "expert")),
    ("junior", ("junior", "jr.", "jr ", "débutant", "entry level", "entry-level")),
]


#: Un stage s'annonce dans le titre. France Travail publie beaucoup d'offres
#: de stage avec typeContrat=CDI ou CDD — le champ contrat y est peu fiable,
#: l'intitulé l'est. Sans cette lecture, un mandat « stage » ne voit rien.
_TITLE_CONTRACT_RE = [
    ("alternance", re.compile(r"\b(alternan\w*|apprenti\w*|contrat\s+pro)\b", re.I)),
    ("stage", re.compile(r"\b(stage|stagiaire|internship|intern)\b", re.I)),
    ("freelance", re.compile(r"\b(freelance|ind[ée]pendant|consultant\s+ind)\b", re.I)),
]


def contract_from_title(title: str | None) -> str | None:
    """Type de contrat annoncé par l'intitulé, ou None."""
    text = title or ""
    for kind, pattern in _TITLE_CONTRACT_RE:
        if pattern.search(text):
            return kind
    return None


def detect_seniority(title: str | None, years_required: float | None = None) -> str:
    text = f" {(title or '').lower()} "

    for level, keywords in _SENIORITY_PATTERNS:
        if any(kw in text for kw in keywords):
            return level

    if years_required is not None:
        if years_required <= 1:
            return "junior"
        if years_required <= 4:
            return "mid"
        if years_required <= 8:
            return "senior"
        return "lead"

    return "mid"


def seniority_from_experience(years: float | None) -> str:
    if years is None:
        return "mid"
    if years < 1:
        return "junior"
    if years < 4:
        return "mid"
    if years < 8:
        return "senior"
    return "lead"


def seniority_gap(job: str, candidate: str) -> int:
    """Écart signé : positif quand le poste est plus senior que le profil."""
    try:
        return SENIORITY_ORDER.index(job) - SENIORITY_ORDER.index(candidate)
    except ValueError:
        return 0


def seniority_distance(a: str, b: str) -> int:
    try:
        return abs(SENIORITY_ORDER.index(a) - SENIORITY_ORDER.index(b))
    except ValueError:
        return 0


# ── Freshness ──────────────────────────────────────────────────────────────

def days_since(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
