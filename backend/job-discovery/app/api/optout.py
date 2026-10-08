"""
Désinscription des candidatures spontanées, en un clic.

Le lien figure au bas de chaque candidature spontanée. Il est signé (HMAC) :
personne ne peut désinscrire l'adresse d'un autre. Le refus vaut pour tout le
domaine de l'adresse — l'entreprise entière ne reçoit plus de spontanées.
"""

import base64
import hashlib
import hmac
from html import escape
from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.email_optout import EmailOptout

router = APIRouter(tags=["optout"])


def _sign(email: str) -> str:
    key = (settings.auth_secret or "alice-optout").encode()
    digest = hmac.new(key, email.lower().encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode().rstrip("=")


def optout_link(email: str) -> str | None:
    """Le lien de désinscription, ou None si l'adresse publique de l'API n'est pas connue."""
    if not settings.public_api_url:
        return None
    base = settings.public_api_url.rstrip("/")
    return f"{base}/api/optout?e={quote(email.lower())}&t={_sign(email)}"


def _page(title: str, text: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title></head>
<body style="font-family:system-ui,sans-serif;background:#FAFAF8;color:#1A1918;max-width:520px;margin:15vh auto;padding:0 20px">
<h1 style="font-weight:400;font-size:22px">{escape(title)}</h1><p style="line-height:1.6">{escape(text)}</p></body></html>"""
    )


@router.get("/optout", response_class=HTMLResponse)
async def optout(e: str, t: str):
    email = (e or "").strip().lower()
    if "@" not in email or not hmac.compare_digest(_sign(email), t or ""):
        return _page("Lien invalide", "Ce lien de désinscription n'est pas valide.")
    domain = "@" + email.rsplit("@", 1)[1]
    async with async_session() as session:
        await session.execute(
            pg_insert(EmailOptout).values(value=domain, reason="lien de désinscription")
            .on_conflict_do_nothing(index_elements=["value"])
        )
        await session.commit()
    return _page(
        "C'est noté",
        f"Plus aucune candidature spontanée ne sera envoyée par Alice aux adresses {domain}. "
        "Les candidatures en réponse à vos offres publiées ne sont pas concernées.",
    )
