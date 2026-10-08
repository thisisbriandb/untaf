"""
L'adresse de recrutement qu'une entreprise publie elle-même.

Règles, non négociables :
  - jamais d'adresse devinée (rh@, recrutement@…) : seulement ce qui est écrit
    sur le site de l'entreprise ;
  - l'adresse doit être sur le domaine du site (ou un sous-domaine) ;
  - on respecte robots.txt et on lit peu de pages (accueil, contact,
    recrutement, mentions légales) ;
  - le site lui-même n'est retenu que si la page d'accueil porte bien le nom
    de l'entreprise.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

# ASCII obligatoire : un en-tête HTTP avec un accent fait échouer chaque requête.
USER_AGENT = "AliceBot/1.0 (+https://alice-agent.fr/bot; candidatures spontanees)"
MAX_PAGES = 6

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
#: Formes masquées courantes : « jobs [at] acme [dot] fr », « jobs(at)acme.fr ».
_OBFUSCATED = [
    (re.compile(r"\s*[\[\(\{]\s*(?:at|arobase|@)\s*[\]\)\}]\s*", re.I), "@"),
    (re.compile(r"\s*[\[\(\{]\s*(?:dot|point)\s*[\]\)\}]\s*", re.I), "."),
]

#: Ce qui mérite une candidature, du plus pertinent au moins pertinent.
_RECRUIT = re.compile(r"recrut|\brh\b|^rh|jobs?|careers?|carri|emploi|candidat|talent|hiring|join|rejoindre|stage|alternance", re.I)
_GENERIC = re.compile(r"^(contact|info|infos|hello|bonjour|accueil|direction|secretariat|office|agence)\b", re.I)
#: Jamais : personne ne lit une candidature là, ou ce n'est pas fait pour.
_EXCLUDED = re.compile(r"no-?reply|ne-?pas-?repondre|dpo|rgpd|gdpr|privacy|donnees|compta|factur|invoice|billing|"
                       r"presse|press|media|support|sav|abuse|webmaster|postmaster|admin|unsubscribe|commande|order|"
                       r"\.(png|jpg|jpeg|gif|svg|webp)$", re.I)

#: Liens à suivre depuis l'accueil, et chemins à essayer.
_LINK_HINT = re.compile(r"recrut|carri|emploi|job|rejoindre|join|contact|mentions|legal|about|qui-sommes", re.I)
_PATHS = ["/contact", "/recrutement", "/carrieres", "/nous-rejoindre", "/mentions-legales"]

#: Annuaires et réseaux : jamais « le site de l'entreprise ».
_NOT_A_COMPANY_SITE = re.compile(
    r"societe\.com|pappers|infogreffe|verif\.com|annuaire|pagesjaunes|linkedin|facebook|instagram|"
    r"twitter|x\.com|wikipedia|indeed|welcometothejungle|glassdoor|francetravail|pole-emploi|"
    r"manageo|corporama|kompass|google\.|bing\.|yelp|data\.gouv", re.I,
)


@dataclass
class Contact:
    email: str
    source_url: str
    kind: str  # recrutement | general


def registrable(host: str) -> str:
    """« jobs.acme.co.uk » → « acme.co.uk » (approximation suffisante pour un contrôle de domaine)."""
    parts = (host or "").lower().removeprefix("www.").split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "gouv", "asso", "org", "ac"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_LEGAL = {"sas", "sa", "sarl", "eurl", "sasu", "groupe", "group", "france", "societe", "ste", "et", "de", "la", "le", "les", "des"}


def name_matches(company_name: str, page_text: str) -> bool:
    """La page porte-t-elle le nom de l'entreprise ? (au moins un mot distinctif)"""
    words = [w for w in _norm(company_name).split() if len(w) > 2 and w not in _LEGAL]
    hay = f" {_norm(page_text)} "
    return bool(words) and any(f" {w} " in hay for w in words)


def extract_emails(page: str, site_host: str) -> list[str]:
    """Adresses écrites dans la page (liens mailto et texte), sur le domaine du site."""
    text = html_lib.unescape(page or "")
    for pattern, repl in _OBFUSCATED:
        text = pattern.sub(repl, text)
    found = set(re.findall(r"mailto:([^\"'?>\s]+)", text, re.I)) | set(_EMAIL_RE.findall(text))
    domain = registrable(site_host)
    out = []
    for raw in found:
        email = raw.strip().strip(".").lower()
        if "@" not in email or _EXCLUDED.search(email):
            continue
        host = email.rsplit("@", 1)[1]
        if registrable(host) != domain:
            continue  # adresse d'un prestataire, d'un autre site : pas celle de l'entreprise
        out.append(email)
    return sorted(set(out))


def best_contact(candidates: list[tuple[str, str]]) -> Contact | None:
    """(adresse, page) → la meilleure : recrutement d'abord, générale ensuite, sinon rien."""
    recruit = [(e, u) for e, u in candidates if _RECRUIT.search(e.split("@")[0])]
    if recruit:
        e, u = recruit[0]
        return Contact(e, u, "recrutement")
    generic = [(e, u) for e, u in candidates if _GENERIC.search(e.split("@")[0])]
    if generic:
        e, u = generic[0]
        return Contact(e, u, "general")
    # Une adresse nominative (prenom.nom@) n'est pas faite pour des candidatures
    # non sollicitées : on s'abstient.
    return None


def _links(page: str, base: str) -> list[str]:
    host = urlsplit(base).hostname or ""
    out = []
    for href, label in re.findall(r"<a[^>]+href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page, re.I | re.S):
        url = urljoin(base, href)
        if urlsplit(url).hostname != host:
            continue
        if _LINK_HINT.search(href) or _LINK_HINT.search(re.sub(r"<[^>]+>", " ", label)):
            out.append(url.split("#")[0])
    return list(dict.fromkeys(out))


def page_summary(page: str) -> str:
    """Ce que l'entreprise dit d'elle-même : titre, description, premiers paragraphes."""
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    desc = re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)", page, re.I)
    paras = re.findall(r"<p[^>]*>(.*?)</p>", page, re.I | re.S)
    text = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras[:8])
    parts = [title.group(1) if title else "", desc.group(1) if desc else "", text]
    return html_lib.unescape(re.sub(r"\s+", " ", " ".join(parts))).strip()[:2500]


async def _allowed(client: httpx.AsyncClient, base: str) -> RobotFileParser:
    rp = RobotFileParser()
    try:
        res = await client.get(urljoin(base, "/robots.txt"))
        rp.parse(res.text.splitlines() if res.status_code == 200 else [])
    except Exception:  # noqa: BLE001 — sans robots.txt lisible, on reste prudent mais on lit l'accueil
        rp.parse([])
    return rp


@dataclass
class SiteFindings:
    website: str
    contact: Contact | None
    summary: str
    pages_read: int


async def scan_site(website: str, company_name: str,
                    client: httpx.AsyncClient | None = None) -> SiteFindings | None:
    """Lit quelques pages du site ; None si ce n'est pas le site de cette entreprise."""
    own = client is None
    client = client or httpx.AsyncClient(timeout=12, follow_redirects=True,
                                         headers={"User-Agent": USER_AGENT})
    try:
        base = website if website.startswith("http") else f"https://{website}"
        try:
            home = await client.get(base)
        except Exception as e:  # noqa: BLE001
            logger.info("Site injoignable %s : %s", base, e)
            return None
        if home.status_code >= 400 or "html" not in home.headers.get("content-type", "html"):
            return None
        base = str(home.url)
        host = urlsplit(base).hostname or ""
        if _NOT_A_COMPANY_SITE.search(host) or not name_matches(company_name, home.text[:200_000]):
            return None

        robots = await _allowed(client, base)
        candidates: list[tuple[str, str]] = [(e, base) for e in extract_emails(home.text, host)]
        queue = _links(home.text, base) + [urljoin(base, p) for p in _PATHS]
        seen, read = {base}, 1
        for url in queue:
            if read >= MAX_PAGES or url in seen:
                continue
            seen.add(url)
            if not robots.can_fetch(USER_AGENT, url):
                continue
            try:
                res = await client.get(url)
            except Exception:  # noqa: BLE001
                continue
            read += 1
            if res.status_code < 400:
                candidates += [(e, url) for e in extract_emails(res.text, host)]
        return SiteFindings(base, best_contact(candidates), page_summary(home.text), read)
    finally:
        if own:
            await client.aclose()


# ── Le site d'une entreprise ───────────────────────────────────────────────

SITE_PROMPT = """Quel est le site internet officiel de cette entreprise française ?
Entreprise : {name}
SIREN : {siren}
Ville : {city}

Réponds en JSON : {{"website": "https://…"}} avec la page d'accueil du site
de l'entreprise elle-même — pas un annuaire, pas un réseau social, pas un site
d'offres d'emploi. Si tu n'es pas sûr, {{"website": null}}."""


async def find_website(name: str, siren: str, city: str | None) -> str | None:
    """
    Le site de l'entreprise, via le modèle avec recherche Google. Le résultat
    n'est qu'un candidat : `scan_site` vérifie ensuite que la page porte bien
    le nom de l'entreprise.
    """
    from app.llm import generate_grounded

    try:
        text = await generate_grounded(SITE_PROMPT.format(name=name, siren=siren, city=city or "?"))
    except Exception as e:  # noqa: BLE001
        logger.info("Recherche du site de %s impossible : %s", name, e)
        return None
    match = re.search(r"\{.*\}", text or "", re.S)
    try:
        url = (json.loads(match.group(0)) if match else {}).get("website")
    except ValueError:
        url = None
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    if _NOT_A_COMPANY_SITE.search(urlsplit(url).hostname or ""):
        return None
    return url
