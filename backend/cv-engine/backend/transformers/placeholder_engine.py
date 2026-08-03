"""Placeholder engine for CV entry templates.

Substitutes field placeholders (COMPANY, POSITION, HIGHLIGHTS, etc.) into
configurable entry templates, with smart cleanup of missing fields.
Extracted from rendercv and adapted for standalone use.
"""

import re
import textwrap
from datetime import date as Date

from .date_formatter import (
    compute_time_span_string,
    format_date_range,
    format_single_date,
)
from .string_utils import clean_url, substitute_placeholders

uppercase_word_pattern = re.compile(r"\b[A-Z_]+\b")

# Matches a bare connector word between placeholders
connector_word_pattern = re.compile(r"(?<=\s)(?![A-Z])[^\W\d_]\S*(?=\s)")


def remove_connectors_of_missing_placeholders(
    template: str, not_provided_placeholders: set[str]
) -> str:
    """Remove connector words ('in', 'at') between placeholders when an adjacent
    placeholder is missing.

    Example:
        >>> remove_connectors_of_missing_placeholders(
        ...     "**INSTITUTION**, DEGREE in AREA", {"DEGREE"}
        ... )
        '**INSTITUTION**, DEGREE  AREA'
    """
    tokens = re.split(r"(\b[A-Z_]+\b)", template)

    for i, token in enumerate(tokens):
        if uppercase_word_pattern.fullmatch(token):
            continue

        prev_ph = next(
            (
                tokens[j]
                for j in range(i - 1, -1, -1)
                if uppercase_word_pattern.fullmatch(tokens[j])
            ),
            None,
        )
        next_ph = next(
            (
                tokens[j]
                for j in range(i + 1, len(tokens))
                if uppercase_word_pattern.fullmatch(tokens[j])
            ),
            None,
        )

        if (
            prev_ph is not None
            and next_ph is not None
            and (
                prev_ph in not_provided_placeholders
                or next_ph in not_provided_placeholders
            )
        ):
            tokens[i] = connector_word_pattern.sub("", token)

    return "".join(tokens)


unwanted_trailing_parts_pattern = re.compile(r"[^A-Za-z0-9.!?\[\]\(\)\*_%]+$")


def clean_trailing_parts(text: str) -> str:
    """Remove trailing characters except alphanumeric and markdown formatting chars."""
    new_lines = []
    for line in text.splitlines():
        new_line = line.rstrip()
        if new_line == "":
            continue
        new_lines.append(unwanted_trailing_parts_pattern.sub("", new_line).rstrip())
    return "\n".join(new_lines)


def remove_not_provided_placeholders(
    entry_templates: dict[str, str], entry_fields: dict[str, str]
) -> dict[str, str]:
    """Remove template placeholders for missing optional fields and surrounding
    punctuation.

    Example:
        >>> templates = {"title": "POSITION at COMPANY, LOCATION"}
        >>> fields = {"POSITION": "Engineer", "COMPANY": "Acme"}
        >>> remove_not_provided_placeholders(templates, fields)
        {'title': 'POSITION at COMPANY'}
    """
    used_placeholders: set[str] = set(
        uppercase_word_pattern.findall(" ".join(entry_templates.values()))
    )
    not_provided: set[str] = used_placeholders - set(entry_fields.keys())

    if not_provided:
        # Remove connector words
        entry_templates = {
            key: re.sub(
                r" {2,}",
                " ",
                remove_connectors_of_missing_placeholders(value, not_provided),
            )
            for key, value in entry_templates.items()
        }

        # Remove placeholders themselves and adjacent non-space chars
        sorted_placeholders = sorted(not_provided, key=len, reverse=True)
        pattern = re.compile(
            r"\S*\b(?:" + "|".join(sorted_placeholders) + r")\b\S*"
        )
        entry_templates = {
            key: clean_trailing_parts(
                re.sub(r" {2,}", " ", pattern.sub("", value))
            )
            for key, value in entry_templates.items()
        }

    return entry_templates


def process_highlights(highlights: list[str]) -> str:
    """Convert highlight list to Markdown unordered list with nested items.

    ' - ' separators within a highlight create nested sub-bullets.

    Example:
        >>> process_highlights(["Led team", "Reduced costs - Server opt - DB indexing"])
        '- Led team\\n- Reduced costs\\n  - Server opt\\n  - DB indexing'
    """
    highlights = ["- " + h.replace(" - ", "\n  - ") for h in highlights]
    return "\n".join(highlights)


def process_authors(authors: list[str]) -> str:
    """Join author names with comma separation."""
    return ", ".join(authors)


def process_date(
    *,
    date: str | int | None,
    start_date: str | int | None,
    end_date: str | int | None,
    locale: dict,
    current_date: Date,
    show_time_span: bool,
    single_date_template: str,
    date_range_template: str,
    time_span_template: str,
) -> str:
    """Format date field as single date or range with optional time span."""
    if date and not (start_date or end_date):
        return format_single_date(
            date, locale=locale, single_date_template=single_date_template
        )
    if start_date and end_date:
        date_range = format_date_range(
            start_date,
            end_date,
            locale=locale,
            single_date_template=single_date_template,
            date_range_template=date_range_template,
        )
        if show_time_span:
            time_span = compute_time_span_string(
                start_date,
                end_date,
                locale=locale,
                current_date=current_date,
                time_span_template=time_span_template,
            )
            return f"{date_range}\n\n{time_span}"

        return date_range

    raise ValueError("No date provided for this entry.")


def process_url(entry: dict) -> str:
    """Format entry URL as Markdown link with cleaned display text."""
    if entry.get("doi"):
        return process_doi(entry)
    if entry.get("url"):
        url = str(entry["url"])
        return f"[{clean_url(url)}]({url})"
    raise ValueError("URL is not provided for this entry.")


def process_doi(entry: dict) -> str:
    """Format publication DOI as Markdown link."""
    doi = entry.get("doi", "")
    return f"[{doi}](https://doi.org/{doi})"


def process_summary(summary: str) -> str:
    """Wrap summary text in Markdown admonition syntax for Typst rendering."""
    return f"!!! summary\n{textwrap.indent(summary, '    ')}"


def render_entry_templates(
    entry: dict,
    *,
    templates: dict[str, str],
    locale: dict,
    show_time_span: bool = False,
    current_date: Date | None = None,
    single_date_template: str = "MONTH_ABBREVIATION YEAR",
    date_range_template: str = "START_DATE – END_DATE",
    time_span_template: str = "HOW_MANY_YEARS YEARS HOW_MANY_MONTHS MONTHS",
    phrases: dict[str, str] | None = None,
) -> dict:
    """Expand entry templates by substituting field placeholders with processed values.

    This is the main function that transforms raw entry data + templates into
    display-ready fields for Typst rendering.

    Args:
        entry: Dict with entry fields (company, position, highlights, etc.)
        templates: Dict of template strings (main_column, date_and_location_column, etc.)
        locale: Locale dict for date formatting
        show_time_span: Whether to include duration in date display
        current_date: Reference date for 'present' calculation
        single_date_template: Template for formatting individual dates
        date_range_template: Template for date ranges
        time_span_template: Template for duration display
        phrases: Optional locale phrases (e.g., {"degree_with_area": "DEGREE in AREA"})

    Returns:
        Entry dict with template-generated display fields added.
    """
    if current_date is None:
        current_date = Date.today()

    if phrases is None:
        phrases = {}

    entry_templates = dict(templates)

    entry_fields: dict[str, str] = {
        key.upper(): str(value)
        for key, value in entry.items()
        if value is not None and value != "" and not key.startswith("_")
    }

    # Expand locale phrases into templates
    for phrase_name, phrase_template in phrases.items():
        phrase_placeholder = phrase_name.upper()
        entry_templates = {
            key: template.replace(phrase_placeholder, phrase_template)
            for key, template in entry_templates.items()
        }

    # Handle special placeholders
    if "HIGHLIGHTS" in entry_fields:
        highlights = entry.get("highlights")
        if isinstance(highlights, list):
            entry_fields["HIGHLIGHTS"] = process_highlights(highlights)

    if "AUTHORS" in entry_fields:
        authors = entry.get("authors")
        if isinstance(authors, list):
            entry_fields["AUTHORS"] = process_authors(authors)

    if (
        "DATE" in entry_fields
        or "START_DATE" in entry_fields
        or "END_DATE" in entry_fields
    ):
        entry_fields["DATE"] = process_date(
            date=entry.get("date"),
            start_date=entry.get("start_date"),
            end_date=entry.get("end_date"),
            locale=locale,
            show_time_span=show_time_span,
            current_date=current_date,
            single_date_template=single_date_template,
            date_range_template=date_range_template,
            time_span_template=time_span_template,
        )

    if "START_DATE" in entry_fields:
        entry_fields["START_DATE"] = format_single_date(
            entry["start_date"], locale=locale, single_date_template=single_date_template
        )

    if "END_DATE" in entry_fields:
        entry_fields["END_DATE"] = format_single_date(
            entry["end_date"], locale=locale, single_date_template=single_date_template
        )

    if "URL" in entry_fields:
        entry_fields["URL"] = process_url(entry)

    if "DOI" in entry_fields:
        entry_fields["URL"] = process_url(entry)
        entry_fields["DOI"] = process_doi(entry)

    if "SUMMARY" in entry_fields:
        summary_is_standalone = any(
            line.strip() == "SUMMARY"
            for template in entry_templates.values()
            for line in template.split("\n")
        )
        if summary_is_standalone:
            entry_fields["SUMMARY"] = process_summary(entry_fields["SUMMARY"])

    entry_templates = remove_not_provided_placeholders(entry_templates, entry_fields)

    # Substitute placeholders in templates and add to entry
    result = dict(entry)
    for template_name, template in entry_templates.items():
        result[template_name] = substitute_placeholders(template, entry_fields)

    return result
