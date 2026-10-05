"""
Mise en forme des e-mails d'Alice.

Un seul gabarit, sobre, qui tient dans tous les clients : tableaux et styles en
ligne, aucune image distante (bloquée par défaut presque partout), largeur
fixe. Le texte brut est toujours fourni à côté — c'est lui que lisent les
filtres anti-spam et les montres connectées.

Tout ce qui vient de l'extérieur (intitulés d'offres, noms d'entreprises,
comptes rendus rédigés par le modèle) est échappé.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

INK = "#1A1918"
PAPER = "#FAFAF8"
#: Une seule encre, comme dans l'application : l'action principale en noir.
GREEN = "#161615"
MUTED = "#8A8884"


@dataclass
class Item:
    title: str
    subtitle: str = ""
    badge: str = ""


@dataclass
class Email:
    subject: str
    preheader: str
    heading: str
    paragraphs: list[str] = field(default_factory=list)
    stats: list[tuple[int | str, str]] = field(default_factory=list)
    items_title: str = ""
    items: list[Item] = field(default_factory=list)
    cta_label: str = ""
    cta_url: str = ""
    footer: str = ""


def render_html(email: Email) -> str:
    stats = ""
    if email.stats:
        cells = "".join(
            f'<td style="padding:0 18px 0 0;vertical-align:top">'
            f'<div style="font-size:24px;font-weight:300;color:{INK}">{escape(str(v))}</div>'
            f'<div style="font-size:11px;color:{MUTED}">{escape(label)}</div></td>'
            for v, label in email.stats
        )
        stats = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin:20px 0;border-top:1px solid #E7E6E2;border-bottom:1px solid #E7E6E2;'
            f'width:100%"><tr><td style="padding:14px 0"><table role="presentation" '
            f'cellpadding="0" cellspacing="0"><tr>{cells}</tr></table></td></tr></table>'
        )

    items = ""
    if email.items:
        rows = "".join(
            f'<tr><td style="padding:10px 0;border-bottom:1px solid #EFEEEA">'
            f'<div style="font-size:14px;color:{INK}">{escape(i.title)}</div>'
            + (f'<div style="font-size:12px;color:{MUTED};margin-top:2px">{escape(i.subtitle)}</div>'
               if i.subtitle else "")
            + "</td>"
            + (f'<td style="padding:10px 0;border-bottom:1px solid #EFEEEA;text-align:right;'
               f'font-size:12px;color:{GREEN};white-space:nowrap">{escape(i.badge)}</td>'
               if i.badge else "<td></td>")
            + "</tr>"
            for i in email.items
        )
        title = (
            f'<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
            f'color:{MUTED};margin:22px 0 4px">{escape(email.items_title)}</div>'
            if email.items_title else ""
        )
        items = (
            f'{title}<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="width:100%">{rows}</table>'
        )

    paragraphs = "".join(
        f'<p style="font-size:15px;line-height:1.6;color:{INK};margin:0 0 12px">{escape(p)}</p>'
        for p in email.paragraphs
    )

    cta = ""
    if email.cta_label and email.cta_url:
        cta = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:26px 0 8px">'
            f'<tr><td style="background:{GREEN};border-radius:999px">'
            f'<a href="{escape(email.cta_url, quote=True)}" style="display:inline-block;'
            f'padding:11px 22px;font-size:14px;color:#fff;text-decoration:none">'
            f'{escape(email.cta_label)}</a></td></tr></table>'
        )

    footer = escape(email.footer) if email.footer else ""

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(email.subject)}</title></head>
<body style="margin:0;padding:0;background:{PAPER};font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(email.preheader)}</div>
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;background:{PAPER}">
<tr><td align="center" style="padding:32px 16px">
<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;background:#fff;border:1px solid #ECEBE7;border-radius:18px">
<tr><td style="padding:28px 28px 8px">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:10px"><img src="{escape(_avatar_url(), quote=True)}" width="32" height="32" alt="Alice" style="display:block;border-radius:50%"></td>
<td style="font-size:13px;color:#2E6B5E;letter-spacing:.01em">Alice</td></tr></table>
<h1 style="font-size:21px;font-weight:400;color:{INK};margin:10px 0 16px;line-height:1.35">{escape(email.heading)}</h1>
{paragraphs}{stats}{items}{cta}
</td></tr>
<tr><td style="padding:16px 28px 26px;font-size:11px;line-height:1.5;color:{MUTED}">{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _avatar_url() -> str:
    """La tête d'Alice, servie par le front (les clients mail bloquent le SVG)."""
    from app.config import settings
    return settings.frontend_url.rstrip("/") + "/alice-mail.png"


def render_text(email: Email) -> str:
    lines = [email.heading, ""]
    lines += [p + "\n" for p in email.paragraphs]
    if email.stats:
        lines.append(" · ".join(f"{v} {label}" for v, label in email.stats))
        lines.append("")
    if email.items:
        if email.items_title:
            lines.append(email.items_title.upper())
        for i in email.items:
            extra = " — ".join(x for x in (i.subtitle, i.badge) if x)
            lines.append(f"- {i.title}" + (f" ({extra})" if extra else ""))
        lines.append("")
    if email.cta_url:
        lines.append(f"{email.cta_label} : {email.cta_url}")
        lines.append("")
    if email.footer:
        lines.append(email.footer)
    return "\n".join(lines).strip() + "\n"
