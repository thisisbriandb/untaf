"""Schémas de la lettre de motivation."""

from pydantic import BaseModel, Field


class CoverLetterResult(BaseModel):
    """
    Une lettre complète, pas seulement un corps de texte.

    Les blocs conventionnels (expéditeur, destinataire, lieu et date, objet,
    politesse, signature) sont des champs distincts plutôt que du Markdown :
    c'est ce qui permet de les mettre en page proprement et de les réutiliser
    d'une lettre à l'autre sans que le modèle ait à les réécrire.
    """

    # ── En-tête ────────────────────────────────────────────
    sender_name: str = ""
    sender_contact: list[str] = Field(
        default_factory=list,
        description="Email, téléphone, LinkedIn — une entrée par ligne.",
    )
    recipient_name: str = Field(default="Service Recrutement")
    recipient_company: str = ""
    place: str | None = None
    date: str = ""

    # ── Contenu ────────────────────────────────────────────
    subject: str = ""
    salutation: str = "Madame, Monsieur,"
    body: str = Field(default="", description="Corps de la lettre, en Markdown.")
    closing: str = ""

    # ── Signature ──────────────────────────────────────────
    signature_name: str = ""
    signature_image: str | None = Field(
        default=None, description="Data URL PNG de la signature manuscrite."
    )

    # ── Traçabilité ────────────────────────────────────────
    grounded_on_posting: bool = False
    grounded_on_experiences: bool = False
    source: str = "llm"


class SignatureUpdate(BaseModel):
    image: str = Field(description="Data URL PNG (data:image/png;base64,...).")
