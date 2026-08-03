"""String processing utilities for CV content.

Provides keyword bolding, placeholder substitution, and URL cleaning.
Extracted from rendercv and adapted for standalone use.
"""

import functools
import re
from collections.abc import Callable
from typing import overload


@overload
def apply_string_processors(
    string: None, string_processors: list[Callable[[str], str]]
) -> None: ...
@overload
def apply_string_processors(
    string: str, string_processors: list[Callable[[str], str]]
) -> str: ...
def apply_string_processors(
    string: str | None, string_processors: list[Callable[[str], str]]
) -> str | None:
    """Apply sequence of string transformation functions via reduce."""
    if string is None:
        return string
    return functools.reduce(lambda v, f: f(v), string_processors, string)


@functools.lru_cache(maxsize=64)
def build_keyword_matcher_pattern(
    keywords: frozenset[str], word_boundary: bool = False
) -> re.Pattern:
    """Build cached regex pattern for matching keywords with longest-first priority."""
    if not keywords:
        raise ValueError("Keywords cannot be empty")

    if word_boundary:
        parts: list[str] = []
        for k in keywords:
            esc = re.escape(k)
            prefix = r"\b" if re.match(r"\w", k[0]) else ""
            suffix = r"\b" if re.match(r"\w", k[-1]) else ""
            parts.append(f"{prefix}{esc}{suffix}")
        parts.sort(key=len, reverse=True)
        pattern = "(" + "|".join(parts) + ")"
    else:
        escaped: list[str] = [re.escape(k) for k in keywords]
        escaped.sort(key=len, reverse=True)
        pattern = "(" + "|".join(escaped) + ")"

    return re.compile(pattern)


def make_keywords_bold(string: str, keywords: list[str]) -> str:
    """Wrap all keyword occurrences in Markdown bold syntax.

    Example:
        >>> make_keywords_bold("Expert in Python and Java", ["Python"])
        'Expert in **Python** and Java'
    """
    if not keywords:
        return string

    pattern = build_keyword_matcher_pattern(frozenset(keywords), word_boundary=True)
    return pattern.sub(lambda m: f"**{m.group(0)}**", string)


def substitute_placeholders(string: str, placeholders: dict[str, str]) -> str:
    """Replace all placeholder occurrences with their values (longest-first).

    Example:
        >>> substitute_placeholders("NAME_CV_YEAR.pdf", {"NAME": "John", "YEAR": "2025"})
        'John_CV_2025.pdf'
    """
    if not placeholders:
        return string

    pattern = build_keyword_matcher_pattern(frozenset(placeholders.keys()))
    return pattern.sub(lambda m: placeholders[m.group(0)], string).strip()


def clean_url(url: str) -> str:
    """Remove protocol and trailing slashes from URL.

    Example:
        >>> clean_url("https://www.example.com/")
        'www.example.com'
    """
    return str(url).replace("https://", "").replace("http://", "").rstrip("/")
