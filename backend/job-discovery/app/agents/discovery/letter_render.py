"""
Rendu PDF de la lettre de motivation.

Le PDF est produit par le serveur, via le même moteur Typst que le CV. Passer
par la boîte d'impression du navigateur donnait un rendu différent selon le
navigateur et la plateforme, et imposait une étape à l'utilisateur.
"""

import base64
import logging
import re
import sys
import tempfile
from pathlib import Path

from app.schemas.cover_letter import CoverLetterResult

logger = logging.getLogger(__name__)

CV_ENGINE_PATH = Path(__file__).resolve().parents[4] / "cv-engine"
if str(CV_ENGINE_PATH) not in sys.path:
    sys.path.append(str(CV_ENGINE_PATH))

try:
    from backend.compiler import compile_typst_to_pdf
    from backend.transformers.markdown_to_typst import markdown_to_typst
    HAS_ENGINE = True
except Exception as e:  # noqa: BLE001
    HAS_ENGINE = False
    logger.warning("cv-engine indisponible pour le rendu de lettre : %s", e)


def _esc(text: str) -> str:
    """Neutralise les caractères qui ont un sens en Typst."""
    if not text:
        return ""
    for ch in ("\\", "#", "$", "*", "_", "`", "<", ">", "@", "~"):
        text = text.replace(ch, "\\" + ch)
    return text


def _signature_file(data_url: str | None) -> Path | None:
    """Écrit la signature sur disque : Typst référence des fichiers, pas des data URL."""
    if not data_url or not data_url.startswith("data:image/"):
        return None
    try:
        header, encoded = data_url.split(",", 1)
        suffix = ".png" if "png" in header.lower() else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(base64.b64decode(encoded))
        tmp.close()
        return Path(tmp.name)
    except Exception as e:  # noqa: BLE001
        logger.warning("Signature illisible, ignorée : %s", e)
        return None


def _body_to_typst(markdown_body: str) -> str:
    """Corps Markdown → Typst, en conservant paragraphes et puces."""
    blocks: list[str] = []
    for raw_block in re.split(r"\n\s*\n", (markdown_body or "").strip()):
        block = raw_block.strip()
        if not block:
            continue

        lines = [l.strip() for l in block.splitlines() if l.strip()]
        is_list = all(re.match(r"^[-*+]\s+", l) for l in lines)

        if is_list:
            items = [
                markdown_to_typst(re.sub(r"^[-*+]\s+", "", l)) if HAS_ENGINE
                else _esc(re.sub(r"^[-*+]\s+", "", l))
                for l in lines
            ]
            blocks.append("\n".join(f"- {item}" for item in items))
        else:
            joined = " ".join(lines)
            blocks.append(markdown_to_typst(joined) if HAS_ENGINE else _esc(joined))

    return "\n\n".join(blocks)


TEMPLATE = """#set page(paper: "a4", margin: (x: 2.4cm, y: 2.2cm))
#set text(font: ("Liberation Serif", "DejaVu Serif"), size: 11pt, lang: "fr")
#set par(justify: true, leading: 0.72em, spacing: 1.15em)

#grid(
  columns: (1fr, 1fr),
  align(left)[
    #text(weight: "semibold", size: 11.5pt)[{sender_name}] \\
    #text(size: 9.5pt, fill: rgb("#55524f"))[{sender_contact}]
  ],
  align(right)[
    #text(weight: "semibold", size: 11.5pt)[{recipient_name}] \\
    #text(size: 9.5pt, fill: rgb("#55524f"))[{recipient_company}]
  ],
)

#v(1.6em)
#align(right)[{place_date}]
#v(1.2em)

{subject_line}
#v(0.6em)

{salutation}

#v(0.4em)
{body}

#v(1em)
{closing}

// Bloc signature : le tracé, puis le nom dessous, aligné à droite.
#v(1.6em)
#align(right)[
  #block[
    {signature_image}
    #text(size: 10.5pt)[{signature_name}]
  ]
]
"""


def render_letter_pdf(letter: CoverLetterResult) -> bytes:
    """Compile la lettre en PDF. Lève si le moteur est indisponible."""
    if not HAS_ENGINE:
        raise RuntimeError("Le moteur cv-engine n'est pas disponible.")

    signature_path = _signature_file(letter.signature_image)
    signature_block = (
        f'#image("{signature_path}", height: 1.7cm)\n    #v(0.15em)'
        if signature_path else "#v(1.5cm)"
    )

    place_date = (
        f"{_esc(letter.place)}, le {_esc(letter.date)}"
        if letter.place else f"Le {_esc(letter.date)}"
    )

    source = TEMPLATE.format(
        sender_name=_esc(letter.sender_name) or "—",
        sender_contact=" \\\n".join(_esc(c) for c in letter.sender_contact) or "",
        recipient_name=_esc(letter.recipient_name),
        recipient_company=_esc(letter.recipient_company),
        place_date=place_date,
        subject_line=(
            f'#text(weight: "semibold")[Objet :] {_esc(letter.subject)}'
            if letter.subject else ""
        ),
        salutation=_esc(letter.salutation),
        body=_body_to_typst(letter.body),
        closing=_esc(letter.closing),
        signature_image=signature_block,
        signature_name=_esc(letter.signature_name or letter.sender_name),
    )

    try:
        return compile_typst_to_pdf(source)
    finally:
        if signature_path:
            signature_path.unlink(missing_ok=True)
