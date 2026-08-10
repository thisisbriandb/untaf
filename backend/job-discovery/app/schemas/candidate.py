"""Pydantic schemas for Candidate API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.matching import MatchingCriteria


class CandidateBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    headline: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    preferred_locations: list[str] = Field(default_factory=list)
    preferred_remote_policies: list[str] = Field(default_factory=list)
    preferred_contract_types: list[str] = Field(default_factory=list)


class CandidateCreate(CandidateBase):
    password: str = Field(min_length=8, max_length=128)
    resume_raw: str | None = None
    matching_criteria: MatchingCriteria | None = None


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None
    headline: str | None = None
    skills: list[str] | None = None
    experience_years: float | None = None
    preferred_locations: list[str] | None = None
    preferred_remote_policies: list[str] | None = None
    preferred_contract_types: list[str] | None = None
    resume_raw: str | None = None
    matching_criteria: MatchingCriteria | None = None


class CandidateOut(CandidateBase):
    id: UUID
    resume_raw: str | None
    matching_criteria: MatchingCriteria | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmtpSettingsUpdate(BaseModel):
    smtp_email: EmailStr
    app_password: str = Field(min_length=1, max_length=255)


class SmtpSettingsOut(BaseModel):
    smtp_email: str | None
    #: True si un mot de passe d'application est enregistré — jamais renvoyé
    #: lui-même, même chiffré : la seule information utile côté client est
    #: « configuré ou non ».
    configured: bool


class CvDesignUpdate(BaseModel):
    """
    Présentation du CV. Chaque champ est indépendant : renseigner une couleur
    ne change pas le modèle, et choisir un modèle n'impose pas sa palette.
    """
    mode: Literal["original", "template"] | None = None
    template_id: str | None = None
    color_hex: str | None = None
    show_photo: bool | None = None


class CvDesignOut(BaseModel):
    mode: Literal["original", "template"]
    template_id: str | None = None
    color_hex: str | None = None
    show_photo: bool = False
    has_original: bool = False
    original_filename: str | None = None
    # True dès que le candidat a exprimé un choix — sinon on est sur le défaut.
    is_explicit: bool = False


class EffectiveCriteriaOut(BaseModel):
    """Le mandat réellement appliqué, et s'il a été défini ou dérivé du profil."""
    criteria: MatchingCriteria
    is_explicit: bool


class ParsedCandidateProfile(BaseModel):
    full_name: str | None = Field(default=None, description="Extracted full name")
    email: str | None = Field(default=None, description="Extracted email address")
    phone: str | None = Field(default=None, description="Extracted phone number")
    github_url: str | None = Field(default=None, description="Extracted GitHub profile URL")
    linkedin_url: str | None = Field(default=None, description="Extracted LinkedIn profile URL")
    website_url: str | None = Field(default=None, description="Extracted personal website URL")
    headline: str | None = Field(default=None, description="Extracted professional title or headline")
    summary: str | None = Field(default=None, description="Extracted candidate executive summary or overview")
    skills: list[str] = Field(default_factory=list, description="Extracted technical and professional skills")
    experience_years: float | None = Field(default=None, description="Estimated total years of professional experience")
    preferred_locations: list[str] = Field(default_factory=list, description="Preferred locations mentioned or inferred")
    preferred_contract_types: list[str] = Field(default_factory=list, description="Contract types inferred (e.g. cdi, freelance)")
    extracted_text_preview: str | None = Field(default=None, description="Preview of raw extracted text")

    # ── Parcours ──────────────────────────────────────────
    # Absents jusqu'ici : la section Expériences de l'éditeur restait donc vide
    # quel que soit le CV importé, y compris quand il contenait des stages.
    experiences: list[dict] = Field(
        default_factory=list,
        description="Postes tenus : {jobTitle, company, location, startDate, "
                    "endDate, isCurrent, highlights[]}. Un stage ou une "
                    "alternance est une expérience à part entière.",
    )
    education: list[dict] = Field(
        default_factory=list,
        description="Formations : {degree, institution, location, startYear, endYear}.",
    )
    languages: list[dict] = Field(
        default_factory=list,
        description="Langues : {language, level}.",
    )


class CVAuditResult(BaseModel):
    ats_score: int
    score_label: str
    strengths: list[str]
    improvements: list[str]
    optimized_headline: str
    optimized_summary: str
    suggested_skills: list[str]




class CVRenderRequest(BaseModel):
    template_id: str = Field(default="classic", description="Selected template ID (classic, tech, minimalist, creative, executive, compact)")
    color_hex: str | None = Field(default="#2563eb", description="Hex code of selected theme color")
    show_photo: bool = Field(default=False, description="Whether photo should be rendered on CV")
    photo_url: str | None = Field(default=None, description="URL of candidate photo")
    full_name: str
    email: str
    phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: float | None = None
    linkedin_url: str | None = None
    location: str | None = None
    experiences: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    languages: list[dict] = Field(default_factory=list)


