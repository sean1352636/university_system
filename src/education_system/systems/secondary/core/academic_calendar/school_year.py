"""School-year helpers shared by the domain modules.

The school year runs from :func:`academic_year_start` (1 September); its label
is ``"2026/27"``.
"""

from __future__ import annotations

import datetime as _dt


def academic_year_start(today: _dt.date | None = None) -> _dt.date:
    """1 September of the current academic year."""
    today = today or _dt.date.today()
    year = today.year if today.month >= 9 else today.year - 1
    return _dt.date(year, 9, 1)


def today() -> _dt.date:
    return _dt.date.today()


def label(start_year: int) -> str:
    """``2026`` -> ``"2026/27"``."""
    return f"{start_year}/{(start_year + 1) % 100:02d}"


def current_year(today: _dt.date | None = None) -> str:
    """The school year *today* (default: the real today) falls in, e.g. ``"2026/27"``."""
    return label(academic_year_start(today).year)


def year_of(day: str) -> str:
    """The school year an ISO date (``"2026-11-04"``) falls in."""
    return current_year(_dt.date.fromisoformat(day))


def next_year(year: str) -> str:
    """``"2026/27"`` -> ``"2027/28"``."""
    return label(int(year[:4]) + 1)
