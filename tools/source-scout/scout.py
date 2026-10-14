"""
Repérage de sources d'offres : pour chaque site carrière, comment y postule-t-on ?

Pour chaque site de la liste :
  1. trouve des liens d'offres (sitemap.xml, sinon les liens de la page) ;
  2. lit quelques offres (3 par défaut, une par seconde) et y cherche :
     e-mail de candidature (mailto), formulaire avec dépôt de CV, compte
     obligatoire, captcha, ATS utilisé, lien « Postuler » vers une autre page ;
  3. regarde le robots.txt et cherche la Licence Ouverte (Etalab) dans les
     conditions d'utilisation ou mentions légales.

Verdict par site :
  e-mail direct          → Alice postule seule (comme INRAE) ;
  formulaire sans compte → à passer à la sonde (tools/agent-bench/probe.mjs) ;
  compte obligatoire     → extension seulement ;
  rendu JS               → pages vides sans navigateur : à revoir avec la sonde ;
  inconnu / erreur.

Rien n'est jamais envoyé : uniquement des lectures (GET), lentes.

Usage (depuis backend/job-discovery, pour son environnement Python) :
  .venv/bin/python ../../tools/source-scout/scout.py                 # liste par défaut
  .venv/bin/python ../../tools/source-scout/scout.py --file sites.txt
  .venv/bin/python ../../tools/source-scout/scout.py https://jobs.inria.fr ...

Sortie : rapport Markdown et JSON dans tools/source-scout/reports/.
"""

import argparse
import asyncio
import html as html_lib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

HERE = Path(__file__).resolve().parent
UA = "AliceBot/1.0 (+https://www.alice-agent.fr ; reperage de sites carriere, lecture seule)"
PAUSE_S = 1.0

#: Point de départ : établissements publics et de recherche (candidature
#: souvent par e-mail au recruteur). Une adresse erronée sort en « erreur ».
DEFAULT_SITES = [
    ("INRAE", "https://jobs.inrae.fr"),
    ("Inria", "https://jobs.inria.fr"),
    ("CNRS", "https://emploi.cnrs.fr"),
    ("CEA", "https://www.emploi.cea.fr"),
    ("Ifremer", "https://recrutement.ifremer.fr"),
    ("IRD", "https://www.ird.fr/offres-demploi"),
    ("Cirad", "https://www.cirad.fr/nous-rejoindre"),
    ("Inserm", "https://www.inserm.fr/nous-rejoindre"),
    ("Anses", "https://www.anses.fr/fr/content/offres-demploi"),
    ("BRGM", "https://www.brgm.fr/fr/offres-emploi"),
    ("IFP Énergies nouvelles", "https://www.ifpenergiesnouvelles.fr/carrieres"),
    ("Institut Pasteur", "https://www.pasteur.fr/fr/institut-pasteur/emplois"),
    ("Muséum national d'histoire naturelle", "https://www.mnhn.fr/fr/offres-d-emploi"),
    ("Choisir le service public", "https://choisirleservicepublic.gouv.fr/nos-offres/"),
    ("Université Paris-Saclay", "https://www.universite-paris-saclay.fr/universite/travailler-luniversite"),
    ("Sorbonne Université", "https://www.sorbonne-universite.fr/universite/recrutement"),
]

OFFER_HINT = re.compile(
    r"(offre|offres|emploi|job|jobs|poste|stage|internship|vacanc|recrut|career|carriere|position|annonce|ot-\d+)",
    re.I,
)
#: Pages de liste ou de navigation, pas des offres.
LISTING = re.compile(
    r"(liste|listing|recherche|search|selection|filtre|filter|\.css|\.js|page=|alerte|"
    r"offres-ponctuelles|toutes-offres|/offres/?$|/jobs/?$|/emplois?/?$|/carrieres?/?$)",
    re.I,
)
#: Une offre précise a presque toujours un identifiant dans son adresse.
OFFER_ID = re.compile(r"(\d{3,}|ot-\d+|[?&](id|ref|offre|job)=)", re.I)

NOT_OFFER = re.compile(
    r"(actualit|news|blog|agenda|evenement|event|contact|mentions|cgu|cookies|login|connexion|"
    r"\.pdf$|\.jpg$|\.png$|linkedin|facebook|twitter|instagram|youtube|mailto:|tel:|#)",
    re.I,
)
CAPTCHA = re.compile(
    r"recaptcha|hcaptcha\.com|challenges\.cloudflare\.com|turnstile|arkoselabs|funcaptcha|captcha-delivery|geetest",
    re.I,
)
LOGIN = re.compile(
    r"type=\"password\"|se connecter|créer (un|mon|votre) compte|creer (un|mon|votre) compte|"
    r"mon espace candidat|espace candidat|sign in|log in|create an account",
    re.I,
)
APPLY_LINK = re.compile(
    r"<a[^>]+href=\"([^\"]+)\"[^>]*>\s*(?:<[^>]+>\s*)*(postuler|je postule|candidater|apply|"
    r"postuler à cette offre|postuler en ligne|déposer ma candidature)",
    re.I,
)
MAILTO = re.compile(r"href=\"mailto:([^\"?]+)", re.I)
EMAIL_IN_TEXT = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
NOREPLY = re.compile(
    r"^(no-?reply|ne-?pas-?repondre|webmaster|dpo|rgpd|communication|presse|contact|admin[\w.-]*|support|info)@", re.I,
)
OPEN_LICENCE = re.compile(r"licence ouverte|etalab|open licence", re.I)
LEGAL_LINK = re.compile(
    r"href=\"([^\"]*(/cgu|conditions-generales|conditions-d-utilisation|mentions-legales|mentions_legales|/legal(?!ite))[^\"]*)\"",
    re.I,
)
LEGAL_PATHS = ["/conditions-generales-dutilisation", "/conditions-generales-d-utilisation", "/cgu", "/mentions-legales"]

ATS = {
    "Workday": r"myworkdayjobs\.com|workday",
    "Taleo": r"taleo\.net",
    "SuccessFactors": r"successfactors|jobs\.sap\.com",
    "SmartRecruiters": r"smartrecruiters\.com",
    "Teamtailor": r"teamtailor",
    "Welcome to the Jungle": r"welcometothejungle\.com|welcomekit",
    "Flatchr": r"flatchr",
    "Taleez": r"taleez",
    "Beetween": r"beetween",
    "Jobaffinity": r"jobaffinity",
    "DigitalRecruiters": r"digitalrecruiters",
    "Softy": r"softy\.pro",
    "Talentsoft / Cegid": r"talent-soft|talentsoft|cegid",
    "Recruitee": r"recruitee\.com",
    "Greenhouse": r"greenhouse\.io",
    "Lever": r"lever\.co",
    "Ashby": r"ashbyhq\.com",
    "JobTeaser": r"jobteaser",
    "Gestmax": r"gestmax",
    "Altays": r"altays",
}


@dataclass
class OfferCheck:
    url: str
    status: int = 0
    emails: list[str] = field(default_factory=list)
    file_input: bool = False
    login: bool = False
    captcha: bool = False
    apply_link: str | None = None
    text_chars: int = 0


@dataclass
class SiteReport:
    name: str
    url: str
    verdict: str = "inconnu"
    detail: str = ""
    offers_found: int = 0
    via: str = ""
    ats: list[str] = field(default_factory=list)
    robots_ok: bool | None = None
    open_licence: bool = False
    checks: list[OfferCheck] = field(default_factory=list)
    error: str | None = None


def _text_len(page: str) -> int:
    body = re.sub(r"<(script|style|svg|noscript)[\s\S]*?</\1>", " ", page, flags=re.I)
    return len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip())


def _same_site(base: str, url: str) -> bool:
    a, b = urlparse(base).netloc.removeprefix("www."), urlparse(url).netloc.removeprefix("www.")
    return a == b or b.endswith("." + a) or a.endswith("." + b)


def offer_links(base: str, page: str, limit: int = 60) -> tuple[list[str], list[str]]:
    """(offres probables, pages de liste) trouvées dans une page."""
    offers: list[str] = []
    listings: list[str] = []
    for href in re.findall(r"href=\"([^\"]+)\"", page):
        url = urljoin(base, html_lib.unescape(href)).split("#")[0]
        if not url.startswith("http") or NOT_OFFER.search(url) or url.rstrip("/") == base.rstrip("/"):
            continue
        path_q = urlparse(url).path + "?" + urlparse(url).query
        if not OFFER_HINT.search(path_q) and not detect_ats(url):
            continue
        if LISTING.search(path_q) or not OFFER_ID.search(path_q):
            if url not in listings:
                listings.append(url)
        elif url not in offers:
            offers.append(url)
        if len(offers) >= limit:
            break
    return offers, listings


def sitemap_offers(xml: str) -> list[str]:
    locs = [l.strip() for l in re.findall(r"<loc>([^<]+)</loc>", xml)]
    return [
        l for l in locs
        if not NOT_OFFER.search(l) and not LISTING.search(urlparse(l).path)
        and OFFER_ID.search(urlparse(l).path + "?" + urlparse(l).query)
    ]


def dominant(urls: list[str]) -> list[str]:
    """Les adresses du motif le plus fréquent (« /ot-N », « /offres/N/… ») : les offres."""
    groups: dict[str, list[str]] = {}
    for u in urls:
        key = re.sub(r"\d+", "N", urlparse(u).path.rsplit("/", 1)[0] + "/" + re.sub(r"[^/]*\d[^/]*$", "*", urlparse(u).path.rsplit("/", 1)[-1]))
        groups.setdefault(key, []).append(u)
    return max(groups.values(), key=len) if groups else []


def check_offer(url: str, status: int, page: str) -> OfferCheck:
    c = OfferCheck(url=url, status=status, text_chars=_text_len(page))
    emails: list[str] = []
    for raw in MAILTO.findall(page):
        for part in re.split(r"[;,]", html_lib.unescape(raw)):
            e = part.strip().lower()
            if EMAIL_IN_TEXT.fullmatch(e) and not NOREPLY.match(e) and e not in emails:
                emails.append(e)
    c.emails = emails
    c.file_input = bool(re.search(r"<input[^>]+type=\"file\"", page, re.I))
    c.login = bool(LOGIN.search(page))
    c.captcha = bool(CAPTCHA.search(page))
    m = APPLY_LINK.search(page)
    if m:
        c.apply_link = urljoin(url, html_lib.unescape(m.group(1)))
    return c


def detect_ats(*texts: str) -> list[str]:
    blob = " ".join(texts)
    return [name for name, pat in ATS.items() if re.search(pat, blob, re.I)]


def verdict(r: SiteReport) -> tuple[str, str]:
    if r.error:
        return "erreur", r.error
    if not r.checks:
        if r.offers_found == 0:
            return "inconnu", "aucun lien d'offre trouvé sans navigateur (rendu JS ou page d'accueil sans offres)"
        return "inconnu", "offres trouvées mais illisibles"
    n = len(r.checks)
    with_email = sum(1 for c in r.checks if c.emails)
    forms = sum(1 for c in r.checks if c.file_input)
    login = sum(1 for c in r.checks if c.login)
    captcha = sum(1 for c in r.checks if c.captcha)
    thin = sum(1 for c in r.checks if c.text_chars < 600)
    if with_email >= max(1, n // 2) and not login:
        return "e-mail direct", f"{with_email}/{n} offres avec un e-mail de candidature"
    if forms and not login and not captcha:
        return "formulaire sans compte", f"{forms}/{n} offres avec dépôt de CV, sans compte ni captcha visibles"
    if login or captcha:
        what = " et ".join(x for x, k in (("compte", login), ("captcha", captcha)) if k)
        extra = " ; un e-mail de contact est affiché (questions, pas candidature)" if with_email else ""
        return "compte obligatoire", f"{what} sur {max(login, captcha)}/{n} offres{extra}"
    if thin == n:
        return "rendu JS", "pages presque vides sans navigateur : à passer à la sonde"
    if any(c.apply_link for c in r.checks):
        return "lien externe", "le bouton « Postuler » mène ailleurs : voir l'ATS"
    return "inconnu", "ni e-mail, ni formulaire, ni compte repérés"


async def scout(client: httpx.AsyncClient, name: str, base: str, sample: int) -> SiteReport:
    r = SiteReport(name=name, url=base)
    try:
        home = await client.get(base)
        if home.status_code >= 400:
            r.error = f"page {home.status_code}"
            r.verdict, r.detail = verdict(r)
            return r
        base = str(home.url)

        # robots.txt
        root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
        rp = RobotFileParser()
        try:
            rob = await client.get(root + "/robots.txt")
            rp.parse(rob.text.splitlines() if rob.status_code == 200 else [])
        except httpx.HTTPError:
            rp.parse([])

        # Offres : sitemap d'abord, sinon les liens de la page.
        links: list[str] = []
        try:
            sm = await client.get(root + "/sitemap.xml")
            if sm.status_code == 200 and "<loc>" in sm.text:
                links = dominant(sitemap_offers(sm.text))
                r.via = "sitemap"
        except httpx.HTTPError:
            pass
        if not links:
            offers, listings = offer_links(base, home.text)
            links = [l for l in offers if _same_site(base, l) or detect_ats(l)]
            r.via = "liens de la page"
            # La page d'accueil ne mène qu'à des listes : on descend d'un niveau.
            for listing in listings[:2]:
                if links:
                    break
                await asyncio.sleep(PAUSE_S)
                try:
                    lp = await client.get(listing)
                except httpx.HTTPError:
                    continue
                more, _ = offer_links(str(lp.url), lp.text)
                links = [l for l in more if _same_site(base, l) or detect_ats(l)]
                r.via = "page de liste"
        r.offers_found = len(links)
        r.robots_ok = all(rp.can_fetch(UA, l) for l in links[:sample]) if links else rp.can_fetch(UA, base)

        # Licence ouverte : page d'accueil, puis CGU / mentions légales.
        if OPEN_LICENCE.search(home.text):
            r.open_licence = True
        else:
            seen_legal: list[str] = []
            candidates = [urljoin(base, html_lib.unescape(m.group(1))) for m in LEGAL_LINK.finditer(home.text)]
            candidates += [root + p for p in LEGAL_PATHS]
            for u in candidates:
                if u in seen_legal or not u.startswith("http"):
                    continue
                seen_legal.append(u)
                await asyncio.sleep(PAUSE_S)
                try:
                    lp = await client.get(u)
                except httpx.HTTPError:
                    continue
                if OPEN_LICENCE.search(lp.text):
                    r.open_licence = True
                    break
                if len(seen_legal) >= 4:
                    break

        texts = [str(home.url), home.text[:200000]]
        for url in links[:sample]:
            await asyncio.sleep(PAUSE_S)
            try:
                page = await client.get(url)
            except httpx.HTTPError as e:
                r.checks.append(OfferCheck(url=url, status=0))
                continue
            c = check_offer(str(page.url), page.status_code, page.text)
            # Bouton « Postuler » vers une autre page sans e-mail ni formulaire : on la lit aussi.
            if c.apply_link and not c.emails and not c.file_input and c.apply_link.startswith("http"):
                await asyncio.sleep(PAUSE_S)
                try:
                    ap = await client.get(c.apply_link)
                    ac = check_offer(str(ap.url), ap.status_code, ap.text)
                    c.emails = c.emails or ac.emails
                    c.file_input = ac.file_input
                    c.login = c.login or ac.login
                    c.captcha = c.captcha or ac.captcha
                    texts.append(str(ap.url))
                except httpx.HTTPError:
                    pass
            r.checks.append(c)
            texts += [str(page.url), page.text[:200000]]
        # Une adresse présente sur toutes les pages lues appartient au gabarit
        # du site (administration, contact général) : ce n'est pas un recruteur.
        if len(r.checks) >= 2:
            common = set.intersection(*(set(c.emails) for c in r.checks))
            for c in r.checks:
                c.emails = [e for e in c.emails if e not in common]
        r.ats = detect_ats(*texts)
    except httpx.HTTPError as e:
        r.error = f"{type(e).__name__}"
    r.verdict, r.detail = verdict(r)
    return r


ORDER = ["e-mail direct", "formulaire sans compte", "lien externe", "rendu JS", "compte obligatoire", "inconnu", "erreur"]


def to_markdown(reports: list[SiteReport]) -> str:
    rows = sorted(reports, key=lambda r: (ORDER.index(r.verdict) if r.verdict in ORDER else 99, r.name))
    lines = [
        f"# Repérage de sources · {datetime.now():%d/%m/%Y %H:%M}",
        "",
        "| Site | Verdict | Détail | Offres trouvées | ATS | robots.txt | Licence ouverte |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        robots = "—" if r.robots_ok is None else ("ok" if r.robots_ok else "interdit")
        lines.append(
            f"| [{r.name}]({r.url}) | **{r.verdict}** | {r.detail} | {r.offers_found} ({r.via or '—'}) "
            f"| {', '.join(r.ats) or '—'} | {robots} | {'oui' if r.open_licence else '—'} |"
        )
    lines += [
        "",
        "Lecture : « e-mail direct » = Alice peut postuler seule (vérifier la réutilisation "
        "des offres avant de brancher) ; « formulaire sans compte » et « rendu JS » = à "
        "passer à la sonde `tools/agent-bench/probe.mjs` ; « compte obligatoire » = extension.",
        "",
    ]
    return "\n".join(lines)


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file", help="un site par ligne : « Nom | https://… » ou juste l'adresse")
    ap.add_argument("--sample", type=int, default=3)
    args = ap.parse_args()

    sites: list[tuple[str, str]] = []
    if args.file:
        for line in Path(args.file).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, url = line.rpartition("|") if "|" in line else ("", "", line)
            sites.append(((name or urlparse(url.strip()).netloc).strip(), url.strip()))
    sites += [(urlparse(u).netloc, u) for u in args.urls]
    sites = sites or DEFAULT_SITES

    async with httpx.AsyncClient(timeout=25, follow_redirects=True, headers={"User-Agent": UA}) as client:
        reports = []
        for name, url in sites:
            print(f"… {name}", file=sys.stderr)
            reports.append(await scout(client, name, url, args.sample))

    out = HERE / "reports"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    (out / f"scout-{stamp}.json").write_text(json.dumps([asdict(r) for r in reports], ensure_ascii=False, indent=2))
    md = to_markdown(reports)
    (out / f"scout-{stamp}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    asyncio.run(main())
