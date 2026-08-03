"""Date formatting utilities for CV entries.

Handles date ranges, single dates, time span calculations with i18n support.
Extracted from rendercv and adapted for standalone use.
"""

import re
from datetime import date as Date

from .string_utils import substitute_placeholders


def get_date_object(date: str | int, current_date: Date | None = None) -> Date:
    """Convert date string/int to Python Date object.

    Handles YYYY-MM-DD, YYYY-MM, YYYY formats and 'present' keyword.

    Example:
        >>> get_date_object("2023-05")
        datetime.date(2023, 5, 1)
    """
    if isinstance(date, int):
        return Date(date, 1, 1)
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return Date.fromisoformat(date)
    elif re.fullmatch(r"\d{4}-\d{2}", date):
        return Date.fromisoformat(f"{date}-01")
    elif re.fullmatch(r"\d{4}", date):
        return Date.fromisoformat(f"{date}-01-01")
    elif date == "present":
        if current_date is None:
            current_date = Date.today()
        return current_date
    else:
        raise ValueError(f"Invalid date format: {date}")


def build_date_placeholders(date: Date, *, locale: dict) -> dict[str, str]:
    """Build all date-related template placeholders from a date and locale.

    Args:
        date: Date to extract components from.
        locale: Locale dict with 'month_names' and 'month_abbreviations' lists.

    Returns:
        Dict mapping placeholder names to their string values.
    """
    month = date.month
    day = date.day
    year = date.year

    return {
        "MONTH_NAME": locale["month_names"][month - 1],
        "MONTH_ABBREVIATION": locale["month_abbreviations"][month - 1],
        "MONTH": str(month),
        "MONTH_IN_TWO_DIGITS": f"{month:02d}",
        "DAY": str(day),
        "DAY_IN_TWO_DIGITS": f"{day:02d}",
        "YEAR": str(year),
        "YEAR_IN_TWO_DIGITS": f"{year % 100:02d}",
    }


def date_object_to_string(
    date: Date, *, locale: dict, single_date_template: str
) -> str:
    """Convert date object to localized string using template placeholders.

    Example:
        >>> date_object_to_string(Date(2025, 3, 15), locale=EN_LOCALE, single_date_template="MONTH_ABBREVIATION YEAR")
        'Mar 2025'
    """
    return substitute_placeholders(
        single_date_template, build_date_placeholders(date, locale=locale)
    )


def format_date_range(
    start_date: str | int,
    end_date: str | int,
    *,
    locale: dict,
    single_date_template: str,
    date_range_template: str,
) -> str:
    """Format date range with localized start and end dates.

    Example:
        >>> format_date_range("2020-06", "present", locale=EN_LOCALE,
        ...     single_date_template="MONTH_ABBREVIATION YEAR",
        ...     date_range_template="START_DATE – END_DATE")
        'June 2020 – present'
    """
    if isinstance(start_date, int):
        start_date_str = str(start_date)
    else:
        date_object = get_date_object(start_date)
        start_date_str = date_object_to_string(
            date_object, locale=locale, single_date_template=single_date_template
        )

    if end_date == "present":
        end_date_str = locale.get("present", "present")
    elif isinstance(end_date, int):
        end_date_str = str(end_date)
    else:
        date_object = get_date_object(end_date)
        end_date_str = date_object_to_string(
            date_object, locale=locale, single_date_template=single_date_template
        )

    placeholders: dict[str, str] = {
        "START_DATE": start_date_str,
        "END_DATE": end_date_str,
    }

    return substitute_placeholders(date_range_template, placeholders)


def format_single_date(
    date: str | int, *, locale: dict, single_date_template: str
) -> str:
    """Format single date with locale-aware template or pass through custom strings.

    Custom date strings like 'Fall 2023' are preserved as-is.
    """
    if isinstance(date, int):
        return str(date)
    elif date == "present":
        return locale.get("present", "present")
    else:
        try:
            date_object = get_date_object(date)
            return date_object_to_string(
                date_object, locale=locale, single_date_template=single_date_template
            )
        except ValueError:
            # Custom date string (e.g., "Spring 2024")
            return str(date)


def compute_time_span_string(
    start_date: str | int,
    end_date: str | int,
    *,
    locale: dict,
    current_date: Date,
    time_span_template: str,
) -> str:
    """Calculate and format duration between dates with localized units.

    Example:
        >>> compute_time_span_string("2020-06", "2023-09", locale=EN_LOCALE,
        ...     current_date=Date(2025, 1, 1),
        ...     time_span_template="HOW_MANY_YEARS YEARS HOW_MANY_MONTHS MONTHS")
        '3 years 4 months'
    """
    if isinstance(start_date, int) or isinstance(end_date, int):
        start_year = get_date_object(start_date, current_date).year
        end_year = get_date_object(end_date, current_date).year

        time_span_in_years = end_year - start_year

        if time_span_in_years < 2:
            how_many_years = "1"
            locale_years = locale.get("year", "year")
        else:
            how_many_years = str(time_span_in_years)
            locale_years = locale.get("years", "years")

        placeholders: dict[str, str] = {
            "HOW_MANY_YEARS": how_many_years,
            "YEARS": locale_years,
            "HOW_MANY_MONTHS": "",
            "MONTHS": "",
        }

        return substitute_placeholders(time_span_template, placeholders)

    end_date_object = get_date_object(end_date, current_date)
    start_date_object = get_date_object(start_date, current_date)

    timespan_in_days = (end_date_object - start_date_object).days

    how_many_years_int = timespan_in_days // 365
    how_many_months_int = (timespan_in_days % 365) // 30 + 1
    how_many_years_int += how_many_months_int // 12
    how_many_months_int %= 12

    if how_many_years_int == 0:
        how_many_years = ""
        locale_years = ""
    elif how_many_years_int == 1:
        how_many_years = "1"
        locale_years = locale.get("year", "year")
    else:
        how_many_years = str(how_many_years_int)
        locale_years = locale.get("years", "years")

    if how_many_months_int == 0:
        how_many_months = ""
        locale_months = ""
    elif how_many_months_int == 1:
        how_many_months = "1"
        locale_months = locale.get("month", "month")
    else:
        how_many_months = str(how_many_months_int)
        locale_months = locale.get("months", "months")

    placeholders = {
        "HOW_MANY_YEARS": how_many_years,
        "YEARS": locale_years,
        "HOW_MANY_MONTHS": how_many_months,
        "MONTHS": locale_months,
    }
    return substitute_placeholders(time_span_template, placeholders)
