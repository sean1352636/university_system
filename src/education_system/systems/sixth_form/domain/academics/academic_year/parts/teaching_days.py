"""Calendar gaps, term/break lookups, teaching days/sessions and the year summary.

Split out of ``academic_year.py``, which re-exports every name here and keeps
the database/RBAC/audit state (DB_PATH, CURRENT_ACTOR, ...). Import from
``academic_year``, not from here.
"""

from __future__ import annotations

from typing import Any
import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    _connect,
    DEFAULT_TERM_KIND,
    init_db,
    _row_break,
    _row_term,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.models import (
    Break,
    CalendarGap,
    Term,
    YearSummary,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.validation import (
    _validate_date,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.years import (
    get_year,
)
from education_system.systems.sixth_form.domain.academics.academic_year.parts.terms_breaks import (
    list_breaks,
    list_terms,
)


# ── Coverage gaps ─────────────────────────────────────────────────

def find_calendar_gaps(year_id: int, *,
                        group_label: str | None = None,
                        ignore_breaks: bool = False
                        ) -> list[CalendarGap]:
    """Weekdays inside the year that no term covers.

    By default a gap that is entirely accounted for by a break (a
    holiday between terms) is not reported — those are expected. Set
    ``ignore_breaks=True`` to see every uncovered stretch.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    terms = [t for t in list_terms(year_id=year_id,
                                     kind=DEFAULT_TERM_KIND,
                                     group_label=group_label)]
    term_ranges = [(t.start_date, t.end_date) for t in terms]
    breaks = ([] if ignore_breaks
              else _break_ranges(year_id, group_label=group_label))

    gaps: list[CalendarGap] = []
    run: list[str] = []
    cur = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    one = _dt.timedelta(days=1)

    def _flush() -> None:
        if not run:
            return
        gaps.append(CalendarGap(
            start_date=run[0], end_date=run[-1], weekdays=len(run),
            group_label=group_label))
        run.clear()

    while cur <= end:
        iso = cur.isoformat()
        if cur.weekday() >= 5:
            cur += one
            continue          # weekends are never a gap
        covered = any(s <= iso <= e for (s, e) in term_ranges) \
            or _covered_by_break(iso, breaks)
        if covered:
            _flush()
        else:
            run.append(iso)
        cur += one
    _flush()
    return gaps


# ── Lookups ───────────────────────────────────────────────────────

def _break_ranges(year_id: int, *, group_label: str | None = None
                   ) -> list[tuple[str, str, str]]:
    """(start, end, am_pm) for the breaks that apply to a group."""
    return [(b.start_date, b.end_date, b.am_pm)
            for b in list_breaks(year_id=year_id,
                                   group_label=group_label)
            if group_label is not None or b.group_label is None]


def _covered_by_break(date_iso: str,
                       ranges: list[tuple[str, str, str]]) -> bool:
    """True only for a *full*-day closure — an AM/PM half day still
    counts as a day the college was open."""
    return any(s <= date_iso <= e and ap == "FULL"
               for (s, e, ap) in ranges)


def find_term_on(year_id: int, date_iso: str, *,
                  group_label: str | None = None,
                  kind: str | None = None) -> Term | None:
    """Return the term containing ``date_iso`` (if any).

    Pass ``kind='Term'`` to ignore nested Mock-Exam Weeks and Study
    Leave. ``group_label`` prefers a term scoped to that year group
    over the college-wide one.
    """
    init_db()
    s = _validate_date(date_iso, "Date")
    clauses = ["year_id = ?", "deleted_at IS NULL",
               "start_date <= ?", "end_date >= ?"]
    args: list[Any] = [year_id, s, s]
    if kind is not None:
        clauses.append("kind = ?")
        args.append(kind)
    if group_label is not None:
        clauses.append("(group_label IS NULL OR group_label = ?)")
        args.append(group_label)
    else:
        clauses.append("group_label IS NULL")
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_terms WHERE {' AND '.join(clauses)} "
            # A group-specific row wins over the college-wide one.
            "ORDER BY group_label IS NULL ASC, start_date ASC LIMIT 1",
            args).fetchone()
        return _row_term(r) if r else None


def is_break(year_id: int, date_iso: str, *,
              group_label: str | None = None) -> Break | None:
    """Return the break covering ``date_iso`` (if any)."""
    init_db()
    s = _validate_date(date_iso, "Date")
    clauses = ["year_id = ?", "deleted_at IS NULL",
               "start_date <= ?", "end_date >= ?"]
    args: list[Any] = [year_id, s, s]
    if group_label is not None:
        clauses.append("(group_label IS NULL OR group_label = ?)")
        args.append(group_label)
    else:
        clauses.append("group_label IS NULL")
    with _connect() as conn:
        r = conn.execute(
            f"SELECT * FROM academic_breaks WHERE {' AND '.join(clauses)} "
            # Prefer a full-day closure over a half day, and a
            # group-specific row over the college-wide one.
            "ORDER BY am_pm = 'FULL' DESC, group_label IS NULL ASC, "
            "start_date ASC LIMIT 1",
            args).fetchone()
        return _row_break(r) if r else None


def teaching_days_in(
    year_id: int, *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_label: str | None = None,
    half_days: bool = False,
) -> float:
    """Teaching days in [from, to] — Mon–Fri, minus closures. Defaults
    to the full year span.

    A day is worth 1.0 when the college is open all day, 0.5 when an
    AM- or PM-only break closes half of it, and 0.0 when a full-day
    break covers it or it falls inside a term marked non-teaching
    (study leave). With ``half_days=False`` (the default) the halves
    are rounded back up to whole days, so the return value is a whole
    number; pass ``half_days=True`` for the exact figure an attendance
    denominator wants.

    With no ``group_label`` only college-wide rows apply, so a
    Y13-only study-leave block doesn't shrink the whole college's
    denominator. Pass a label to count that group's own calendar.
    """
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    df = _validate_date(date_from or year.start_date, "From")
    dt = _validate_date(date_to or year.end_date, "To")
    if dt < df:
        return 0.0
    breaks = _break_ranges(year_id, group_label=group_label)
    closed = _non_teaching_term_ranges(year_id, group_label=group_label)

    start = _dt.date.fromisoformat(df)
    end = _dt.date.fromisoformat(dt)
    total = 0.0
    cur = start
    one = _dt.timedelta(days=1)
    while cur <= end:
        # Mon=0..Fri=4; exclude Sat=5 / Sun=6
        if cur.weekday() < 5:
            total += _day_weight(cur.isoformat(), breaks, closed,
                                   half_days=half_days)
        cur += one
    return total if half_days else int(total)


def _day_weight(date_iso: str,
                 breaks: list[tuple[str, str, str]],
                 closed: list[tuple[str, str]], *,
                 half_days: bool) -> float:
    """How much of one weekday is taught: 1.0, 0.5, or 0.0."""
    if any(s <= date_iso <= e for (s, e) in closed):
        return 0.0
    covering = [ap for (s, e, ap) in breaks if s <= date_iso <= e]
    if not covering:
        return 1.0
    if "FULL" in covering:
        return 0.0
    if not half_days:
        # An AM-only INSET still leaves an afternoon of teaching —
        # don't drop the whole day from a whole-day count.
        return 1.0
    # AM and PM breaks on the same day add up to a full closure.
    return 0.0 if {"AM", "PM"} <= set(covering) else 0.5


def _non_teaching_term_ranges(year_id: int, *,
                               group_label: str | None = None
                               ) -> list[tuple[str, str]]:
    """Ranges covered by a term flagged ``is_teaching = 0``."""
    return [(t.start_date, t.end_date)
            for t in list_terms(year_id=year_id,
                                  group_label=group_label)
            if not t.is_teaching
            and (group_label is not None or t.group_label is None)]


def teaching_sessions_in(
    year_id: int, *,
    date_from: str | None = None,
    date_to: str | None = None,
    group_label: str | None = None,
) -> int:
    """The same window counted in AM/PM sessions — two per full day,
    one per half day. The unit an attendance register actually uses.
    """
    days = teaching_days_in(year_id, date_from=date_from,
                              date_to=date_to, group_label=group_label,
                              half_days=True)
    return int(round(days * 2))


def year_summary(year_id: int, *,
                  group_label: str | None = None) -> YearSummary:
    year = get_year(year_id)
    if year is None:
        raise ValidationError(f"No academic year #{year_id}")
    terms = list_terms(year_id=year_id, group_label=group_label)
    breaks = list_breaks(year_id=year_id, group_label=group_label)

    teaching = teaching_days_in(year_id, group_label=group_label)
    # Total Mon-Fri count, regardless of breaks
    start = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    weekdays = 0
    weekends = 0
    cur, one = start, _dt.timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            weekdays += 1
        else:
            weekends += 1
        cur += one
    non_teaching = weekdays - teaching

    return YearSummary(
        year=year,
        terms=terms,
        breaks=breaks,
        teaching_days=teaching,
        non_teaching_days=non_teaching,
        weekend_days=weekends,
    )
