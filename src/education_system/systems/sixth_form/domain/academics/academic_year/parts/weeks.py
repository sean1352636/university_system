"""Timetable cycle weeks (A/B…) and teaching-week numbers.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    CYCLE_LABELS,
    DEFAULT_TERM_KIND,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _validate_date,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (
    get_year,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.teaching_days import (
    _break_ranges,
    _covered_by_break,
    find_term_on,
)


# ── Timetable cycle (Week A / Week B) ─────────────────────────────

def cycle_week_on(year_id: int, date_iso: str) -> int | None:
    """Which week of the timetable cycle ``date_iso`` falls in.

    Returns 1..``cycle_weeks``, or ``None`` if the date is outside
    the year. A year with ``cycle_weeks == 1`` always returns 1.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    s = _validate_date(date_iso, "Date")
    if s < year.start_date or s > year.end_date:
        return None
    anchor = _dt.date.fromisoformat(year.effective_cycle_anchor)
    d = _dt.date.fromisoformat(s)
    # Compare Monday-of-week to Monday-anchor so any day in the same
    # week gets the same cycle position.
    monday = d - _dt.timedelta(days=d.weekday())
    weeks = (monday - anchor).days // 7
    return int(weeks % max(1, year.cycle_weeks)) + 1


def cycle_week_label(year_id: int, date_iso: str) -> str | None:
    """``cycle_week_on`` as 'A' / 'B' / …. ``None`` outside the year."""
    n = cycle_week_on(year_id, date_iso)
    if n is None:
        return None
    return CYCLE_LABELS[n - 1] if n <= len(CYCLE_LABELS) else str(n)


def week_number_on(year_id: int, date_iso: str, *,
                    group_label: str | None = None
                    ) -> dict[str, Any] | None:
    """Teaching-week numbering for a date.

    Returns ``{"year_week", "term_week", "term", "cycle_week",
    "cycle_label"}`` — where ``year_week`` counts weeks containing at
    least one teaching day since the start of the year, and
    ``term_week`` does the same within the containing term. Weeks
    that are entirely break/weekend are not counted, so "Week 7"
    means the seventh week students were actually in.

    ``None`` if the date is outside the year.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    s = _validate_date(date_iso, "Date")
    if s < year.start_date or s > year.end_date:
        return None

    term = find_term_on(year_id, s, group_label=group_label,
                          kind=DEFAULT_TERM_KIND)
    target = _dt.date.fromisoformat(s)
    target_monday = target - _dt.timedelta(days=target.weekday())

    def _teaching_weeks_upto(from_iso: str) -> int:
        """Count Mondays whose week holds >= 1 teaching day, from
        ``from_iso`` up to and including the target's week."""
        start = _dt.date.fromisoformat(from_iso)
        monday = start - _dt.timedelta(days=start.weekday())
        breaks = _break_ranges(year_id, group_label=group_label)
        count = 0
        week = monday
        while week <= target_monday:
            for offset in range(5):  # Mon..Fri
                day = week + _dt.timedelta(days=offset)
                iso = day.isoformat()
                if iso < year.start_date or iso > year.end_date:
                    continue
                if from_iso and iso < from_iso:
                    continue
                if not _covered_by_break(iso, breaks):
                    count += 1
                    break
            week += _dt.timedelta(days=7)
        return count

    return {
        "date": s,
        "year_week": _teaching_weeks_upto(year.start_date) or None,
        "term_week": (_teaching_weeks_upto(term.start_date)
                      if term else None),
        "term": term.name if term else None,
        "cycle_week": cycle_week_on(year_id, s),
        "cycle_label": cycle_week_label(year_id, s),
    }
