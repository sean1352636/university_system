"""Shared helpers for the financial aid report builders.

Split out of ``reports`` so the builders can live in two modules without a
circular import.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from education_system.systems.university.infrastructure.i18n import get_text

_T = "financial_aid.admin_portal.reports"
_RULE = "=" * 80
_LINE = "-" * 80


def _t(key: str, default: str = "", **kwargs: Any) -> str:
    """``get_text`` whose English default is formatted too.

    The i18n engine formats a translated string but returns ``default``
    verbatim; the report keys have no translations yet, so the defaults carry
    the placeholders and must be formatted here.
    """
    text = get_text(key, default=default, **kwargs)
    if kwargs and "{" in text:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            pass
    return text


def _default_connect():
    from education_system.systems.university.infrastructure.database.db import get_connection

    return get_connection()


def format_currency(amount: Any) -> str:
    return f"£{float(amount or 0):,.2f}"


def format_date(value: Any) -> str:
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d")
        except (ValueError, TypeError):
            return value
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return str(value)


def get_current_academic_year() -> str:
    """``YYYY-YYYY`` for today; the academic year starts in August."""
    today = date.today()
    if today.month >= 8:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"


def _stamp() -> str:
    return f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _ratio_pct(part: float, whole: float) -> float:
    return (part / whole) * 100 if whole else 0.0



__all__ = [
    "_LINE", "_RULE", "_T", "_default_connect", "_ratio_pct", "_stamp", "_t", "_table_exists",
    "format_currency", "format_date", "get_current_academic_year",
]
