"""
Ecosystem Seeder — curated lists of high-value French tech companies.

Sources:
- French Tech 120 / Next 40 (government-backed labels)
- Notable VC-backed startups (Kima, Elaia, Partech portfolio)
- Key French tech employers

These lists are embedded directly (no API needed) and updated periodically.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EcosystemCompany:
    """A company from a curated ecosystem list."""
    name: str
    domain: str
    source: str  # "ft120" | "next40" | "vc_backed"
    sector: str | None = None


# ── French Tech Next40 (2024-2025 cohort, top tier) ──────
NEXT40: list[dict] = [
    {"name": "Alan", "domain": "alan.com", "sector": "healthtech"},
    {"name": "Back Market", "domain": "backmarket.com", "sector": "marketplace"},
    {"name": "BlaBlaCar", "domain": "blablacar.com", "sector": "mobility"},
    {"name": "Contentsquare", "domain": "contentsquare.com", "sector": "analytics"},
    {"name": "Dataiku", "domain": "dataiku.com", "sector": "data/ai"},
    {"name": "Deezer", "domain": "deezer.com", "sector": "entertainment"},
    {"name": "Doctolib", "domain": "doctolib.fr", "sector": "healthtech"},
    {"name": "Exotec", "domain": "exotec.com", "sector": "robotics"},
    {"name": "Hugging Face", "domain": "huggingface.co", "sector": "ai/ml"},
    {"name": "Ivalua", "domain": "ivalua.com", "sector": "procurement"},
    {"name": "Ledger", "domain": "ledger.com", "sector": "crypto"},
    {"name": "Lydia", "domain": "lydia-app.com", "sector": "fintech"},
    {"name": "ManoMano", "domain": "manomano.fr", "sector": "marketplace"},
    {"name": "Mirakl", "domain": "mirakl.com", "sector": "marketplace tech"},
    {"name": "Mistral AI", "domain": "mistral.ai", "sector": "ai/ml"},
    {"name": "OVHcloud", "domain": "ovhcloud.com", "sector": "cloud"},
    {"name": "Payfit", "domain": "payfit.com", "sector": "hr tech"},
    {"name": "Pennylane", "domain": "pennylane.com", "sector": "fintech"},
    {"name": "Pigment", "domain": "pigment.com", "sector": "fintech"},
    {"name": "Platform.sh", "domain": "platform.sh", "sector": "devtools"},
    {"name": "Qonto", "domain": "qonto.com", "sector": "fintech"},
    {"name": "Shift Technology", "domain": "shift-technology.com", "sector": "insurtech"},
    {"name": "Spendesk", "domain": "spendesk.com", "sector": "fintech"},
    {"name": "Swile", "domain": "swile.co", "sector": "hr tech"},
    {"name": "Vestiaire Collective", "domain": "vestiairecollective.com", "sector": "marketplace"},
]

# ── French Tech 120 (extended tier, selected) ────────────
FT120_EXTENDED: list[dict] = [
    {"name": "360Learning", "domain": "360learning.com", "sector": "edtech"},
    {"name": "AB Tasty", "domain": "abtasty.com", "sector": "marketing"},
    {"name": "Algolia", "domain": "algolia.com", "sector": "search"},
    {"name": "Alma", "domain": "getalma.eu", "sector": "fintech"},
    {"name": "Batch", "domain": "batch.com", "sector": "mobile"},
    {"name": "Believe", "domain": "believe.com", "sector": "entertainment"},
    {"name": "Brevo", "domain": "brevo.com", "sector": "marketing"},
    {"name": "Bump", "domain": "bump.sh", "sector": "devtools"},
    {"name": "Comet", "domain": "comet.co", "sector": "freelance"},
    {"name": "Dailymotion", "domain": "dailymotion.com", "sector": "media"},
    {"name": "Dashlane", "domain": "dashlane.com", "sector": "cybersecurity"},
    {"name": "Doctrine", "domain": "doctrine.fr", "sector": "legaltech"},
    {"name": "Evaneos", "domain": "evaneos.com", "sector": "travel"},
    {"name": "Frichti", "domain": "frichti.co", "sector": "foodtech"},
    {"name": "GitGuardian", "domain": "gitguardian.com", "sector": "cybersecurity"},
    {"name": "iAdvize", "domain": "iadvize.com", "sector": "conversational ai"},
    {"name": "JobTeaser", "domain": "jobteaser.com", "sector": "hr tech"},
    {"name": "Joko", "domain": "joko.com", "sector": "fintech"},
    {"name": "Legalstart", "domain": "legalstart.fr", "sector": "legaltech"},
    {"name": "Lucky Cart", "domain": "luckycart.com", "sector": "adtech"},
    {"name": "Luko", "domain": "luko.eu", "sector": "insurtech"},
    {"name": "Malt", "domain": "malt.fr", "sector": "freelance"},
    {"name": "Meero", "domain": "meero.com", "sector": "photography"},
    {"name": "Meilisearch", "domain": "meilisearch.com", "sector": "search"},
    {"name": "MWM", "domain": "mwm.io", "sector": "entertainment"},
    {"name": "Neoen", "domain": "neoen.com", "sector": "energy"},
    {"name": "Ornikar", "domain": "ornikar.com", "sector": "edtech"},
    {"name": "Owkin", "domain": "owkin.com", "sector": "biotech"},
    {"name": "Photoroom", "domain": "photoroom.com", "sector": "ai/ml"},
    {"name": "PlayPlay", "domain": "playplay.com", "sector": "video"},
    {"name": "Scaleway", "domain": "scaleway.com", "sector": "cloud"},
    {"name": "Sendinblue", "domain": "sendinblue.com", "sector": "marketing"},
    {"name": "Side", "domain": "side.co", "sector": "hr tech"},
    {"name": "Skeepers", "domain": "skeepers.io", "sector": "marketing"},
    {"name": "Sorare", "domain": "sorare.com", "sector": "gaming/nft"},
    {"name": "Stockly", "domain": "stockly.ai", "sector": "ecommerce"},
    {"name": "Strapi", "domain": "strapi.io", "sector": "devtools"},
    {"name": "Teads", "domain": "teads.com", "sector": "adtech"},
    {"name": "Theodo", "domain": "theodo.fr", "sector": "consulting tech"},
    {"name": "Tinycoaching", "domain": "tinycoaching.com", "sector": "hr tech"},
    {"name": "Trustpair", "domain": "trustpair.com", "sector": "fintech"},
    {"name": "Welcome to the Jungle", "domain": "welcometothejungle.com", "sector": "hr tech"},
    {"name": "Yousign", "domain": "yousign.com", "sector": "legaltech"},
]

# ── Notable VC-backed French companies ───────────────────
VC_BACKED: list[dict] = [
    {"name": "Ankorstore", "domain": "ankorstore.com", "sector": "marketplace"},
    {"name": "Aqemia", "domain": "aqemia.com", "sector": "biotech"},
    {"name": "Brigad", "domain": "brigad.co", "sector": "hr tech"},
    {"name": "Clay", "domain": "clay.earth", "sector": "fintech"},
    {"name": "Dust", "domain": "dust.tt", "sector": "ai"},
    {"name": "Elevo", "domain": "elevo.fr", "sector": "hr tech"},
    {"name": "Figures", "domain": "figures.hr", "sector": "hr tech"},
    {"name": "Flatchr", "domain": "flatchr.io", "sector": "hr tech"},
    {"name": "Folk", "domain": "folk.app", "sector": "crm"},
    {"name": "Holberton School", "domain": "holbertonschool.com", "sector": "edtech"},
    {"name": "Hyperline", "domain": "hyperline.co", "sector": "fintech"},
    {"name": "Inato", "domain": "inato.com", "sector": "biotech"},
    {"name": "Kombo", "domain": "kombo.co", "sector": "mobility"},
    {"name": "Lemon Learning", "domain": "lemonlearning.com", "sector": "edtech"},
    {"name": "Libeo", "domain": "libeo.io", "sector": "fintech"},
    {"name": "Livestorm", "domain": "livestorm.co", "sector": "video"},
    {"name": "Lucca", "domain": "lucca.fr", "sector": "hr tech"},
    {"name": "Memo Bank", "domain": "memo.bank", "sector": "fintech"},
    {"name": "Napta", "domain": "napta.io", "sector": "hr tech"},
    {"name": "Numberly", "domain": "numberly.com", "sector": "data"},
    {"name": "October", "domain": "october.eu", "sector": "fintech"},
    {"name": "Pretto", "domain": "pretto.fr", "sector": "fintech"},
    {"name": "Silvr", "domain": "silvr.co", "sector": "fintech"},
    {"name": "Swan", "domain": "swan.io", "sector": "fintech"},
    {"name": "Sweep", "domain": "sweep.net", "sector": "climate tech"},
    {"name": "Taster", "domain": "tfrk.co", "sector": "foodtech"},
    {"name": "TextCortex", "domain": "textcortex.com", "sector": "ai"},
    {"name": "Treezor", "domain": "treezor.com", "sector": "fintech"},
    {"name": "Upflow", "domain": "upflow.io", "sector": "fintech"},
    {"name": "Yolaw", "domain": "yolaw.fr", "sector": "legaltech"},
]


def get_ecosystem_companies() -> list[EcosystemCompany]:
    """
    Return all curated ecosystem companies as a flat list.
    Deduplicates by domain.
    """
    seen_domains: set[str] = set()
    result: list[EcosystemCompany] = []

    for source_name, source_list in [
        ("next40", NEXT40),
        ("ft120", FT120_EXTENDED),
        ("vc_backed", VC_BACKED),
    ]:
        for entry in source_list:
            domain = entry["domain"].lower()
            if domain not in seen_domains:
                seen_domains.add(domain)
                result.append(EcosystemCompany(
                    name=entry["name"],
                    domain=domain,
                    source=source_name,
                    sector=entry.get("sector"),
                ))

    logger.info("Ecosystem seeding: %d unique companies from curated lists", len(result))
    return result
