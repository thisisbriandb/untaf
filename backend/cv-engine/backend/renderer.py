"""CV Renderer — Orchestrates Jinja2 template rendering to generate Typst source.

Takes structured CV data (dict) + design config and produces a complete .typ file
ready for compilation to PDF.
"""

import pathlib
from collections.abc import Callable
from datetime import date as Date

import jinja2

from .models import (
    DEFAULT_DESIGN,
    FONTAWESOME_ICONS,
    LOCALE_EN,
    detect_entry_type,
    detect_section_entry_type,
    format_section_title,
    get_locale,
)
from .transformers.date_formatter import (
    build_date_placeholders,
    date_object_to_string,
)
from .transformers.markdown_to_typst import markdown_to_typst
from .transformers.placeholder_engine import render_entry_templates
from .transformers.string_utils import (
    apply_string_processors,
    clean_url,
    make_keywords_bold,
    substitute_placeholders,
)

templates_directory = pathlib.Path(__file__).parent / "templates"


def _get_jinja2_environment() -> jinja2.Environment:
    """Create Jinja2 environment with template loaders and filters."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([templates_directory]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["clean_url"] = clean_url
    env.filters["strip"] = lambda string: string.strip()
    return env


def _compute_connections_typst(
    cv: dict, design: dict
) -> list[str]:
    """Format connections as Typst markup strings."""
    connections: list[str] = []
    header_cfg = design.get("header", {}).get("connections", {})
    show_icon = header_cfg.get("show_icons", True)
    if design.get("header_style") == "banner":
        show_icon = False
    hyperlink = header_cfg.get("hyperlink", True)
    display_urls = header_cfg.get("display_urls_instead_of_usernames", False)

    # Location
    if cv.get("location"):
        body = markdown_to_typst(cv["location"])
        if show_icon:
            body = f'#connection-with-icon("{FONTAWESOME_ICONS["location"]}")[{body}]'
        connections.append(body)

    # Email(s)
    emails = cv.get("email")
    if emails:
        if not isinstance(emails, list):
            emails = [emails]
        for email in emails:
            body = markdown_to_typst(str(email))
            if show_icon:
                body = f'#connection-with-icon("{FONTAWESOME_ICONS["email"]}")[{body}]'
            if hyperlink:
                body = f'#link("mailto:{email}", icon: false, if-underline: false, if-color: false)[{body}]'
            connections.append(body)

    # Phone(s)
    phones = cv.get("phone")
    if phones:
        if not isinstance(phones, list):
            phones = [phones]
        for phone in phones:
            body = markdown_to_typst(str(phone))
            if show_icon:
                body = f'#connection-with-icon("{FONTAWESOME_ICONS["phone"]}")[{body}]'
            if hyperlink:
                body = f'#link("{phone}", icon: false, if-underline: false, if-color: false)[{body}]'
            connections.append(body)

    # Website(s)
    websites = cv.get("website")
    if websites:
        if not isinstance(websites, list):
            websites = [websites]
        for website in websites:
            url = str(website)
            display = clean_url(url)
            body = markdown_to_typst(display)
            if show_icon:
                body = f'#connection-with-icon("{FONTAWESOME_ICONS["website"]}")[{body}]'
            if hyperlink:
                body = f'#link("{url}", icon: false, if-underline: false, if-color: false)[{body}]'
            connections.append(body)

    # Social networks
    for sn in cv.get("social_networks", []):
        network = sn.get("network", "")
        username = sn.get("username", "")
        url = sn.get("url", "")
        icon = FONTAWESOME_ICONS.get(network, "link")
        display = clean_url(url) if display_urls else username
        body = markdown_to_typst(display)
        if show_icon:
            body = f'#connection-with-icon("{icon}")[{body}]'
        if hyperlink and url:
            body = f'#link("{url}", icon: false, if-underline: false, if-color: false)[{body}]'
        connections.append(body)

    return connections


def _render_footer(
    footer_template: str,
    *,
    locale: dict,
    current_date: Date,
    name: str,
    single_date_template: str,
    string_processors: list[Callable[[str], str]],
) -> str:
    """Render footer with Typst context block for page numbers."""
    placeholders: dict[str, str] = {
        "CURRENT_DATE": date_object_to_string(
            current_date, locale=locale, single_date_template=single_date_template
        ),
        "NAME": name or "",
        "PAGE_NUMBER": "#str(here().page())",
        "TOTAL_PAGES": "#str(counter(page).final().first())",
        **build_date_placeholders(current_date, locale=locale),
    }
    content = apply_string_processors(
        substitute_placeholders(footer_template, placeholders), string_processors
    )
    return f"context {{ [{content}] }}"


def _render_top_note(
    top_note_template: str,
    *,
    locale: dict,
    current_date: Date,
    name: str,
    single_date_template: str,
    string_processors: list[Callable[[str], str]],
) -> str:
    """Render top note with date and name placeholders."""
    placeholders: dict[str, str] = {
        "CURRENT_DATE": date_object_to_string(
            current_date, locale=locale, single_date_template=single_date_template
        ),
        "LAST_UPDATED": locale.get("last_updated", "Last updated in"),
        "NAME": name or "",
        **build_date_placeholders(current_date, locale=locale),
    }
    return apply_string_processors(
        substitute_placeholders(top_note_template, placeholders), string_processors
    )


def _deep_get(d: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d


def render_cv(
    cv_data: dict,
    design: dict | None = None,
    locale: dict | str | None = None,
    current_date: Date | None = None,
    bold_keywords: list[str] | None = None,
) -> str:
    """Render complete CV document as Typst source string.

    This is the main entry point for CV generation.

    Args:
        cv_data: CV content dict with keys: name, headline, location, email,
                 phone, website, social_networks, sections.
        design: Design config dict (merged with DEFAULT_DESIGN).
        locale: Locale dict or language string (e.g., 'fr').
        current_date: Date for 'last updated' and 'present' calculations.
        bold_keywords: Keywords to auto-bold in content.

    Returns:
        Complete Typst source string ready for compilation.

    Example:
        >>> typst_source = render_cv({
        ...     "name": "John Doe",
        ...     "email": "john@example.com",
        ...     "sections": {
        ...         "experience": [
        ...             {"company": "Acme", "position": "Engineer",
        ...              "start_date": "2020-01", "end_date": "present",
        ...              "highlights": ["Built stuff"]}
        ...         ]
        ...     }
        ... })
    """
    if current_date is None:
        current_date = Date.today()

    # Resolve locale
    if locale is None:
        locale_dict = LOCALE_EN
    elif isinstance(locale, str):
        locale_dict = get_locale(locale)
    else:
        locale_dict = locale

    # Merge design with defaults
    if design is None:
        design_cfg = dict(DEFAULT_DESIGN)
    else:
        design_cfg = _merge_dicts(DEFAULT_DESIGN, design)

    templates_cfg = design_cfg.get("templates", {})
    single_date_template = templates_cfg.get("single_date", "MONTH_ABBREVIATION YEAR")
    date_range_template = templates_cfg.get("date_range", "START_DATE – END_DATE")
    time_span_template = templates_cfg.get("time_span", "HOW_MANY_YEARS YEARS HOW_MANY_MONTHS MONTHS")

    # String processors pipeline
    string_processors: list[Callable[[str], str]] = []
    if bold_keywords:
        string_processors.append(
            lambda s: make_keywords_bold(s, bold_keywords)
        )
    string_processors.append(markdown_to_typst)

    # Process CV fields
    plain_name = cv_data.get("name", "")
    processed_name = apply_string_processors(plain_name, string_processors)
    processed_headline = apply_string_processors(cv_data.get("headline"), string_processors)
    connections = _compute_connections_typst(cv_data, design_cfg)

    # Footer and top note
    footer = _render_footer(
        templates_cfg.get("footer", ""),
        locale=locale_dict,
        current_date=current_date,
        name=processed_name or "",
        single_date_template=single_date_template,
        string_processors=string_processors,
    )
    top_note = _render_top_note(
        templates_cfg.get("top_note", ""),
        locale=locale_dict,
        current_date=current_date,
        name=processed_name or "",
        single_date_template=single_date_template,
        string_processors=string_processors,
    )

    # Build a context object that mimics what the Jinja2 templates expect
    class _Namespace:
        """Simple namespace to allow dot-access in Jinja2 templates."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                if isinstance(v, dict):
                    setattr(self, k, _Namespace(**v))
                else:
                    setattr(self, k, v)

        def __getattr__(self, name):
            return None

    # Build cv namespace
    cv_ns = _Namespace(
        name=processed_name,
        _plain_name=plain_name,
        headline=processed_headline,
        _connections=connections,
        _footer=footer,
        _top_note=top_note,
        photo=cv_data.get("photo"),
    )

    # Build design namespace (deep)
    design_ns = _dict_to_namespace(design_cfg)

    # Build locale namespace
    locale_ns = _Namespace(
        language_iso_639_1=locale_dict.get("language_code", "en"),
        is_rtl=locale_dict.get("language") in ("arabic", "hebrew", "persian"),
    )

    # Build settings namespace
    settings_ns = _Namespace(
        pdf_title=f"{plain_name}'s CV",
        _resolved_current_date=current_date,
    )

    # Render preamble
    env = _get_jinja2_environment()
    preamble_template = env.get_template("Preamble.j2.typ")
    preamble = preamble_template.render(
        cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns
    )

    # Render header
    header_template = env.get_template("Header.j2.typ")
    header = header_template.render(
        cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns
    )

    code = f"{preamble}\n\n{header}\n"

    # Render sections
    sections = cv_data.get("sections", {})
    phrases = locale_dict.get("phrases", {})
    show_time_spans_in = _deep_get(design_cfg, "sections", "show_time_spans_in", default=["experience"])

    theme = design_cfg.get("theme", "classic")
    is_sidebar_layout = theme in ("tech", "creative", "left-sidebar", "compact")

    main_section_codes = []
    sidebar_section_codes = []
    sidebar_keys = {"competences", "skills", "langues", "languages", "certifications"}

    for section_key, entries in sections.items():
        section_title = format_section_title(section_key)
        processed_title = apply_string_processors(section_title, string_processors)
        entry_type = detect_section_entry_type(entries)

        # Section beginning
        section_begin = env.get_template("SectionBeginning.j2.typ")
        section_beginning = section_begin.render(
            section_title=processed_title,
            snake_case_section_title=section_key.lower().replace(" ", "_"),
            entry_type=entry_type,
            cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns,
        )

        # Section ending
        section_end = env.get_template("SectionEnding.j2.typ")
        section_ending = section_end.render(
            entry_type=entry_type,
            cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns,
        )

        # Process and render each entry
        snake_title = section_key.lower().replace(" ", "_")
        show_time_span = snake_title in show_time_spans_in

        entry_codes = []
        for entry in entries:
            # Get the right template for this entry type
            et = detect_entry_type(entry)
            template_name = f"entries/{et}.j2.typ"

            if isinstance(entry, str):
                # TextEntry
                processed_entry_str = apply_string_processors(entry, string_processors)
                entry_template = env.get_template(template_name)
                entry_code = entry_template.render(
                    entry=processed_entry_str,
                    cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns,
                )
            else:
                # Get entry-specific templates from design config
                et_snake = _camel_to_snake(et)
                entry_templates = templates_cfg.get(et_snake, {})
                if isinstance(entry_templates, dict) and entry_templates:
                    processed_entry = render_entry_templates(
                        entry,
                        templates=entry_templates,
                        locale=locale_dict,
                        show_time_span=show_time_span,
                        current_date=current_date,
                        single_date_template=single_date_template,
                        date_range_template=date_range_template,
                        time_span_template=time_span_template,
                        phrases=phrases,
                    )
                else:
                    processed_entry = dict(entry)

                # Apply string processors to all string fields
                for field_name, value in list(processed_entry.items()):
                    if field_name.startswith("_"):
                        continue
                    if field_name in ("start_date", "end_date", "doi", "url"):
                        continue
                    if isinstance(value, str):
                        processed_entry[field_name] = apply_string_processors(
                            value, string_processors
                        )
                    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                        processed_entry[field_name] = [
                            apply_string_processors(v, string_processors) for v in value
                        ]

                entry_ns = _Namespace(**processed_entry)
                entry_template = env.get_template(template_name)
                entry_code = entry_template.render(
                    entry=entry_ns,
                    cv=cv_ns, design=design_ns, locale=locale_ns, settings=settings_ns,
                )

            entry_codes.append(entry_code)

        entries_code = "\n\n".join(entry_codes)
        sec_code = f"{section_beginning}\n{entries_code}\n{section_ending}"

        if is_sidebar_layout and section_key.lower().replace(" ", "_") in sidebar_keys:
            sidebar_section_codes.append(sec_code)
        else:
            main_section_codes.append(sec_code)

    if is_sidebar_layout and sidebar_section_codes:
        main_part = "\n".join(main_section_codes)
        side_part = "\n".join(sidebar_section_codes)
        code += f"\n#grid(columns: (2.2fr, 1fr), column-gutter: 15pt, [\n{main_part}\n], [\n{side_part}\n])\n"
    else:
        code += "\n" + "\n".join(main_section_codes + sidebar_section_codes)

    return code


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    import re
    s1 = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return s1.lower()


def _merge_dicts(base: dict, override: dict) -> dict:
    """Deep merge two dicts, override takes priority."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


class ColorString(str):
    """String wrapper that supports as_rgb() for Jinja2 templates."""
    def as_rgb(self) -> str:
        s = str(self).strip()
        if s.startswith("#"):
            h = s.lstrip("#")
            if len(h) == 6:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"rgb({r}, {g}, {b})"
            elif len(h) == 3:
                r, g, b = int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)
                return f"rgb({r}, {g}, {b})"
        return s


def _dict_to_namespace(d: dict) -> object:
    """Recursively convert a dict to a namespace with dot-access."""
    class _NS:
        def __getattr__(self, name):
            return None

    ns = _NS()
    for key, value in d.items():
        if isinstance(value, dict):
            setattr(ns, key, _dict_to_namespace(value))
        elif isinstance(value, str) and (value.startswith("rgb") or value.startswith("hsl") or value.startswith("#") or key in ("body", "name", "headline", "connections", "banner_bg", "section_titles", "links", "footer", "top_note")):
            setattr(ns, key, ColorString(value))
        else:
            setattr(ns, key, value)
    return ns
