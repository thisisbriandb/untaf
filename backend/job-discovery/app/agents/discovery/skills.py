"""
Skill canonicalisation.

The previous matcher intersected raw strings, so "React" / "ReactJS" /
"React.js" counted as three unrelated skills and a well-matched candidate
scored as a stranger. Everything is normalised to a canonical token before
comparison, with partial credit for skills of the same family.
"""

import re

# ── Canonical aliases ──────────────────────────────────────────────────────

_ALIASES: dict[str, str] = {
    # JS ecosystem
    "js": "javascript", "ecmascript": "javascript",
    "ts": "typescript",
    "reactjs": "react", "react.js": "react", "react js": "react",
    "react native": "react-native", "reactnative": "react-native",
    "vuejs": "vue", "vue.js": "vue", "vue 3": "vue", "vue3": "vue",
    "angularjs": "angular", "angular.js": "angular",
    "nodejs": "node", "node.js": "node",
    "nextjs": "next.js", "next js": "next.js", "next": "next.js",
    "nuxtjs": "nuxt", "nuxt.js": "nuxt",
    "svelte kit": "sveltekit", "svelte.js": "svelte",
    "express.js": "express", "expressjs": "express",
    # Python
    "py": "python", "python3": "python",
    "fast api": "fastapi",
    "django rest framework": "django", "drf": "django",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn",
    "tensor flow": "tensorflow",
    "py torch": "pytorch", "torch": "pytorch",
    # Backend / langages
    "golang": "go",
    "c sharp": "c#", "csharp": "c#",
    "dotnet": ".net", ".net core": ".net", "dot net": ".net",
    "asp.net": ".net", "aspnet": ".net",
    "spring boot": "spring", "springboot": "spring",
    "ruby on rails": "rails", "ror": "rails",
    "objective c": "objective-c",
    # Data stores
    "postgres": "postgresql", "psql": "postgresql", "postgre": "postgresql",
    "mongo": "mongodb",
    "sql server": "mssql", "microsoft sql server": "mssql", "t-sql": "mssql",
    "elastic": "elasticsearch", "elk": "elasticsearch", "opensearch": "elasticsearch",
    "rabbit mq": "rabbitmq",
    "apache kafka": "kafka",
    # Cloud / infra
    "amazon web services": "aws",
    "gcp": "google cloud", "google cloud platform": "google cloud",
    "ms azure": "azure", "microsoft azure": "azure",
    "k8s": "kubernetes", "kube": "kubernetes",
    "ci/cd": "ci-cd", "cicd": "ci-cd", "ci cd": "ci-cd",
    "continuous integration": "ci-cd", "intégration continue": "ci-cd",
    "infrastructure as code": "terraform", "iac": "terraform",
    "github actions": "ci-cd", "gitlab ci": "ci-cd", "jenkins": "ci-cd",
    # Web
    "tailwindcss": "tailwind", "tailwind css": "tailwind",
    "rest api": "rest", "restful": "rest", "api rest": "rest",
    "graphql api": "graphql",
    "html5": "html", "css3": "css",
    "sass": "scss",
    # Divers
    "machine learning": "ml", "apprentissage automatique": "ml",
    "deep learning": "ml",
    "intelligence artificielle": "ai", "artificial intelligence": "ai",
    "gestion de projet": "project management",
    "méthode agile": "agile", "agile/scrum": "agile", "scrum": "agile",
}

# Skills that are close enough to earn partial credit for one another.
_FAMILIES: dict[str, set[str]] = {
    "sql": {"postgresql", "mysql", "mssql", "oracle", "sqlite", "mariadb", "sql"},
    "nosql": {"mongodb", "redis", "cassandra", "dynamodb", "couchbase"},
    "frontend-framework": {"react", "vue", "angular", "svelte", "ember"},
    "meta-framework": {"next.js", "nuxt", "sveltekit", "remix"},
    "python-web": {"django", "flask", "fastapi", "tornado"},
    "jvm": {"java", "kotlin", "scala", "spring"},
    "cloud": {"aws", "google cloud", "azure", "scaleway", "ovh", "digitalocean"},
    "container": {"docker", "kubernetes", "podman", "helm"},
    "systems": {"go", "rust", "c", "c++"},
    "mobile": {"swift", "kotlin", "react-native", "flutter", "objective-c"},
    "ml": {"ml", "ai", "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy"},
    "queue": {"kafka", "rabbitmq", "sqs", "pubsub", "celery"},
}

_FAMILY_OF: dict[str, str] = {
    skill: family for family, skills in _FAMILIES.items() for skill in skills
}

# Knowing the framework means knowing the language. A CV listing "FastAPI"
# without "Python" is the normal case, not an edge case.
_IMPLIES: dict[str, tuple[str, ...]] = {
    "django": ("python",), "flask": ("python",), "fastapi": ("python",),
    "pandas": ("python",), "numpy": ("python",), "scikit-learn": ("python",),
    "pytorch": ("python",), "tensorflow": ("python",),
    "react": ("javascript",), "vue": ("javascript",), "angular": ("javascript",),
    "svelte": ("javascript",), "node": ("javascript",), "express": ("javascript",),
    "typescript": ("javascript",),
    "next.js": ("react", "javascript"), "nuxt": ("vue", "javascript"),
    "sveltekit": ("svelte", "javascript"), "remix": ("react", "javascript"),
    "react-native": ("react", "javascript"),
    "spring": ("java",), "rails": ("ruby",), "laravel": ("php",),
    "symfony": ("php",), ".net": ("c#",),
    "kubernetes": ("docker",), "helm": ("kubernetes",),
    "scss": ("css",), "tailwind": ("css",),
}

_PARTIAL_CREDIT = 0.4

_PUNCT = re.compile(r"[\s_/\\|,;()\[\]]+")


def canonical(skill: str) -> str:
    """Reduce a free-text skill to its canonical token."""
    s = (skill or "").strip().lower()
    if not s:
        return ""

    s = _PUNCT.sub(" ", s).strip()
    if s in _ALIASES:
        return _ALIASES[s]

    # Retry without separators: "react .js" → "react.js"
    compact = s.replace(" ", "")
    if compact in _ALIASES:
        return _ALIASES[compact]

    # Trailing framework suffixes: "vuejs" handled above, "somethingjs" generic
    if compact.endswith("js") and len(compact) > 4:
        base = compact[:-2]
        if base in _ALIASES:
            return _ALIASES[base]

    return s


def canonical_set(skills) -> set[str]:
    return {c for c in (canonical(s) for s in (skills or [])) if c}


def expand(skills: set[str]) -> set[str]:
    """Add transitively implied skills (fastapi → python → …)."""
    out = set(skills)
    frontier = set(skills)
    while frontier:
        implied = {i for s in frontier for i in _IMPLIES.get(s, ())} - out
        out |= implied
        frontier = implied
    return out


def skill_coverage(
    required: set[str],
    owned: set[str],
) -> tuple[float, list[str], list[str]]:
    """
    Share of the job's required skills the candidate covers.

    Returns (ratio 0..1, matched skills, missing skills). An exact canonical
    match is worth 1, a same-family skill 0.4 — knowing Vue when the job asks
    for React is not nothing, but it is not React either.
    """
    if not required:
        return 0.0, [], []

    owned = expand(owned)
    owned_families = {_FAMILY_OF[s] for s in owned if s in _FAMILY_OF}

    earned = 0.0
    matched: list[str] = []
    missing: list[str] = []

    for skill in required:
        if skill in owned:
            earned += 1.0
            matched.append(skill)
        elif skill in _FAMILY_OF and _FAMILY_OF[skill] in owned_families:
            earned += _PARTIAL_CREDIT
            matched.append(skill)
        else:
            missing.append(skill)

    return earned / len(required), sorted(matched), sorted(missing)
