"""Lightweight CV data models and locale definitions.

Simple dataclasses and dicts instead of heavy Pydantic models.
Structure inspired by rendercv but stripped to essentials.
"""

from dataclasses import dataclass, field
from datetime import date as Date


# ─── Locale (simple dict-based) ──────────────────────────────────────────────

LOCALE_EN: dict = {
    "language": "english",
    "language_code": "en",
    "last_updated": "Last updated in",
    "present": "present",
    "month": "month",
    "months": "months",
    "year": "year",
    "years": "years",
    "month_abbreviations": [
        "Jan", "Feb", "Mar", "Apr", "May", "June",
        "July", "Aug", "Sept", "Oct", "Nov", "Dec",
    ],
    "month_names": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "phrases": {
        "degree_with_area": "DEGREE in AREA",
    },
}

LOCALE_FR: dict = {
    "language": "french",
    "language_code": "fr",
    "last_updated": "Dernière mise à jour en",
    "present": "présent",
    "month": "mois",
    "months": "mois",
    "year": "an",
    "years": "ans",
    "month_abbreviations": [
        "Janv.", "Fév.", "Mars", "Avr.", "Mai", "Juin",
        "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc.",
    ],
    "month_names": [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    ],
    "phrases": {
        "degree_with_area": "DEGREE en AREA",
    },
}

LOCALES: dict[str, dict] = {
    "en": LOCALE_EN,
    "english": LOCALE_EN,
    "fr": LOCALE_FR,
    "french": LOCALE_FR,
}


def get_locale(language: str = "en") -> dict:
    """Get locale dict by language code or name."""
    return LOCALES.get(language, LOCALE_EN)


# ─── Design defaults ────────────────────────────────────────────────────────

DEFAULT_DESIGN: dict = {
    "theme": "classic",
    "header_style": "banner",
    "page": {
        "size": "us-letter",
        "top_margin": "0.7in",
        "bottom_margin": "0.7in",
        "left_margin": "0.7in",
        "right_margin": "0.7in",
        "show_footer": True,
        "show_top_note": True,
    },
    "colors": {
        "body": "rgb(30, 41, 59)",
        "name": "rgb(0, 79, 144)",
        "headline": "rgb(0, 79, 144)",
        "connections": "rgb(0, 79, 144)",
        "banner_bg": "rgb(35, 76, 106)",
        "section_titles": "rgb(0, 79, 144)",
        "links": "rgb(0, 79, 144)",
        "footer": "rgb(128, 128, 128)",
        "top_note": "rgb(128, 128, 128)",
    },
    "typography": {
        "line_spacing": "0.6em",
        "alignment": "justified",
        "date_and_location_column_alignment": "right",
        "font_family": {
            "body": "Source Sans 3",
            "name": "Source Sans 3",
            "headline": "Source Sans 3",
            "connections": "Source Sans 3",
            "section_titles": "Source Sans 3",
        },
        "font_size": {
            "body": "10pt",
            "name": "30pt",
            "headline": "10pt",
            "connections": "10pt",
            "section_titles": "1.4em",
        },
        "small_caps": {
            "name": False,
            "headline": False,
            "connections": False,
            "section_titles": False,
        },
        "bold": {
            "name": True,
            "headline": False,
            "connections": False,
            "section_titles": True,
        },
    },
    "links": {
        "underline": False,
        "show_external_link_icon": False,
    },
    "header": {
        "alignment": "center",
        "photo_width": "3.5cm",
        "photo_position": "left",
        "photo_space_left": "0.4cm",
        "photo_space_right": "0.4cm",
        "space_below_name": "0.7cm",
        "space_below_headline": "0.7cm",
        "space_below_connections": "0.7cm",
        "connections": {
            "phone_number_format": "national",
            "hyperlink": True,
            "show_icons": True,
            "display_urls_instead_of_usernames": False,
            "separator": "",
            "space_between_connections": "0.5cm",
        },
    },
    "section_titles": {
        "type": "with_partial_line",
        "line_thickness": "0.5pt",
        "space_above": "0.5cm",
        "space_below": "0.3cm",
    },
    "sections": {
        "allow_page_break": True,
        "space_between_regular_entries": "1.2em",
        "space_between_text_based_entries": "0.3em",
        "show_time_spans_in": ["experience"],
    },
    "entries": {
        "date_and_location_width": "4.15cm",
        "side_space": "0.2cm",
        "space_between_columns": "0.1cm",
        "allow_page_break": False,
        "short_second_row": True,
        "degree_width": "1cm",
        "summary": {"space_above": "0cm", "space_left": "0cm"},
        "highlights": {
            "bullet": "•",
            "nested_bullet": "•",
            "space_left": "0.15cm",
            "space_above": "0cm",
            "space_between_items": "0cm",
            "space_between_bullet_and_text": "0.5em",
        },
    },
    "templates": {
        "footer": "*NAME -- PAGE_NUMBER/TOTAL_PAGES*",
        "top_note": "*LAST_UPDATED CURRENT_DATE*",
        "single_date": "MONTH_ABBREVIATION YEAR",
        "date_range": "START_DATE – END_DATE",
        "time_span": "HOW_MANY_YEARS YEARS HOW_MANY_MONTHS MONTHS",
        "one_line_entry": {"main_column": "**LABEL:** DETAILS"},
        "education_entry": {
            "main_column": "**INSTITUTION**, AREA\nSUMMARY\nHIGHLIGHTS",
            "degree_column": "**DEGREE**",
            "date_and_location_column": "LOCATION\nDATE",
        },
        "normal_entry": {
            "main_column": "**NAME**\nSUMMARY\nHIGHLIGHTS",
            "date_and_location_column": "LOCATION\nDATE",
        },
        "experience_entry": {
            "main_column": "**COMPANY**, POSITION\nSUMMARY\nHIGHLIGHTS",
            "date_and_location_column": "LOCATION\nDATE",
        },
        "publication_entry": {
            "main_column": "**TITLE**\nSUMMARY\nAUTHORS\nURL (JOURNAL)",
            "date_and_location_column": "DATE",
        },
    },
}


# ─── Entry type detection ────────────────────────────────────────────────────

# Maps characteristic fields to entry type names
ENTRY_TYPE_SIGNATURES: dict[str, set[str]] = {
    "ExperienceEntry": {"company", "position"},
    "EducationEntry": {"institution", "area"},
    "PublicationEntry": {"title", "authors"},
    "NormalEntry": {"name"},
    "OneLineEntry": {"label", "details"},
    "BulletEntry": {"bullet"},
    "NumberedEntry": {"number"},
    "ReversedNumberedEntry": {"reversed_number"},
}


def detect_entry_type(entry: dict | str) -> str:
    """Detect entry type from its fields.

    Returns entry type name (e.g., 'ExperienceEntry', 'TextEntry').
    """
    if isinstance(entry, str):
        return "TextEntry"

    for entry_type, characteristic_fields in ENTRY_TYPE_SIGNATURES.items():
        if characteristic_fields & set(entry.keys()):
            return entry_type

    return "TextEntry"


def detect_section_entry_type(entries: list[dict | str]) -> str:
    """Detect entry type for a section from its first identifiable entry."""
    for entry in entries:
        entry_type = detect_entry_type(entry)
        if entry_type != "TextEntry" or isinstance(entry, str):
            return entry_type
    return "TextEntry"


# ─── Section title formatting ────────────────────────────────────────────────

WORDS_NOT_CAPITALIZED = {
    "a", "and", "as", "at", "but", "by", "for", "from", "if", "in", "into",
    "like", "near", "nor", "of", "off", "on", "onto", "or", "over", "so",
    "than", "that", "to", "upon", "when", "with", "yet",
}


def format_section_title(key: str) -> str:
    """Convert snake_case section key to title case.

    Example:
        >>> format_section_title("work_experience")
        'Work Experience'
    """
    if " " in key or any(c.isupper() for c in key):
        return key

    return " ".join(
        word.capitalize() if word not in WORDS_NOT_CAPITALIZED else word
        for word in key.replace("_", " ").split()
    )


# ─── FontAwesome icon mapping ───────────────────────────────────────────────

FONTAWESOME_ICONS: dict[str, str] = {
    "LinkedIn": "linkedin",
    "GitHub": "github",
    "GitLab": "gitlab",
    "Instagram": "instagram",
    "ORCID": "orcid",
    "StackOverflow": "stack-overflow",
    "YouTube": "youtube",
    "Google Scholar": "graduation-cap",
    "Telegram": "telegram",
    "WhatsApp": "whatsapp",
    "X": "x-twitter",
    "Bluesky": "bluesky",
    "Reddit": "reddit",
    "location": "location-dot",
    "email": "envelope",
    "phone": "phone",
    "website": "link",
}
