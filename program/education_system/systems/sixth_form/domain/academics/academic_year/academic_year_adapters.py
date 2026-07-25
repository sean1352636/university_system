"""Adapters for other modules to consume the Academic Year cleanly.

Other domain modules SHOULD NOT call the data layer directly for
calendar questions — they go through these helpers so the contract
is centralised and easy to test. Each function answers one specific
question in language matching the caller's intent.

| Item | Caller       | Function                          |
|------|--------------|-----------------------------------|
| 17   | Attendance   | ``attendance_denominator``        |
| 18   | Timetable    | ``can_schedule_lesson``           |
| 19   | Reports      | ``report_header_phrase``          |
| 20   | UCAS         | ``ucas_deadline_check``           |
| 21   | Assessment   | ``mock_exam_window``              |
| 22   | Trips        | ``trip_collision_check``          |
| 23   | HR           | ``staff_proratio``                |
| 24   | Safeguarding | ``classify_incident_date``        |
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    Break,
    Term,
)

logger = logging.getLogger(__name__)


# 17 — Attendance
def attendance_denominator(year_id: int, *,
                              date_from: str | None = None,
                              date_to: str | None = None) -> int:
    """Number of teaching days in the window — the denominator the
    attendance module should divide present-days by."""
    return data.teaching_days_in(year_id,
                                    date_from=date_from, date_to=date_to)


# 18 — Timetable
@dataclass
class ScheduleCheck:
    allowed: bool
    reason: str | None
    break_name: str | None = None


def can_schedule_lesson(year_id: int, date_iso: str) -> ScheduleCheck:
    """Tell the timetable scheduler whether a lesson can land on
    ``date_iso``. Refuses INSET / Bank Holiday / weekends."""
    try:
        d = _dt.date.fromisoformat(date_iso)
    except ValueError as e:
        return ScheduleCheck(False, f"bad date: {e}")
    if d.weekday() >= 5:
        return ScheduleCheck(False, "weekend")
    brk = data.is_break(year_id, date_iso)
    if brk is not None:
        return ScheduleCheck(False, f"break: {brk.type}",
                                break_name=brk.name)
    return ScheduleCheck(True, None)


# 19 — Reports
def report_header_phrase(year_id: int,
                            date_iso: str | None = None) -> str:
    """Returns the standard report header phrase, e.g.
    'Term: Autumn 2025, week 6 of 14'. Returns '' if the date is
    outside any term."""
    d_iso = date_iso or _dt.date.today().isoformat()
    term = data.find_term_on(year_id, d_iso)
    year = data.get_year(year_id)
    if term is None or year is None:
        return ""
    try:
        ts = _dt.date.fromisoformat(term.start_date)
        te = _dt.date.fromisoformat(term.end_date)
        d = _dt.date.fromisoformat(d_iso)
    except ValueError:
        return ""
    week_n = ((d - ts).days // 7) + 1
    weeks_total = ((te - ts).days // 7) + 1
    return (f"Term: {term.name} {year.name}, "
             f"week {week_n} of {weeks_total}")


# 20 — UCAS
@dataclass
class DeadlineCheck:
    ok: bool
    reason: str
    term_name: str | None = None


def ucas_deadline_check(year_id: int, deadline_iso: str
                          ) -> DeadlineCheck:
    """Verify a UCAS deadline lands inside an Active term — not in a
    holiday and not on a weekend. We don't move the deadline; this
    just surfaces a warning to staff."""
    try:
        d = _dt.date.fromisoformat(deadline_iso)
    except ValueError as e:
        return DeadlineCheck(False, f"bad date: {e}")
    year = data.get_year(year_id)
    if year is None or year.status != "Active":
        return DeadlineCheck(False, "year is not Active")
    term = data.find_term_on(year_id, deadline_iso)
    if term is None:
        return DeadlineCheck(False, "outside any term")
    brk = data.is_break(year_id, deadline_iso)
    if brk is not None:
        return DeadlineCheck(False, f"on {brk.type} ({brk.name})",
                                term_name=term.name)
    if d.weekday() >= 5:
        return DeadlineCheck(False, "weekend", term_name=term.name)
    return DeadlineCheck(True, "ok", term_name=term.name)


# 21 — Assessment / mock exams
def mock_exam_window(year_id: int) -> tuple[str, str] | None:
    """Return the first Mock-Exam Week term's date range, if any."""
    terms = data.list_terms(year_id=year_id, kind="Mock-Exam Week")
    if not terms:
        return None
    t = terms[0]
    return (t.start_date, t.end_date)


# 22 — Trips
@dataclass
class TripCheck:
    ok: bool
    warning: str | None
    break_name: str | None = None


def trip_collision_check(year_id: int, start_iso: str,
                            end_iso: str) -> TripCheck:
    """Warn (don't block) if a trip's date range overlaps a Half-Term
    or Holiday break."""
    try:
        s = _dt.date.fromisoformat(start_iso)
        e = _dt.date.fromisoformat(end_iso)
    except ValueError as ex:
        return TripCheck(False, f"bad date: {ex}")
    if e < s:
        return TripCheck(False, "end before start")
    for b in data.list_breaks(year_id=year_id):
        if b.type not in ("Half-Term", "Holiday", "Bank Holiday"):
            continue
        if not (b.end_date < start_iso or b.start_date > end_iso):
            return TripCheck(False,
                                f"overlaps {b.type}",
                                break_name=b.name)
    return TripCheck(True, None)


# 23 — HR
def staff_proratio(year_id: int, contract_days_per_year: float) -> float:
    """Return a float in [0,1] for how much of the contract-day quota
    has elapsed (teaching days only). HR uses this for pro-rata salary
    calculations."""
    year = data.get_year(year_id)
    if year is None or contract_days_per_year <= 0:
        return 0.0
    today = _dt.date.today().isoformat()
    so_far = data.teaching_days_in(
        year_id, date_from=year.start_date,
        date_to=min(today, year.end_date))
    return min(1.0, so_far / contract_days_per_year)


# 24 — Safeguarding
def classify_incident_date(year_id: int, date_iso: str) -> str:
    """Bucket an incident date — safeguarding workflows route holiday
    incidents differently from term-time ones."""
    term = data.find_term_on(year_id, date_iso)
    brk = data.is_break(year_id, date_iso)
    if brk is not None:
        return f"holiday:{brk.type}"
    if term is not None:
        try:
            d = _dt.date.fromisoformat(date_iso)
            if d.weekday() >= 5:
                return "term-weekend"
        except ValueError:
            return "term-time"
        return "term-time"
    return "outside-year"
