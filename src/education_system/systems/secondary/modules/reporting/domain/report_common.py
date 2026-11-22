"""Shared helpers for the read-only report screens (attendance, behaviour,
results, census, data export).

Nothing here stores data: every figure is worked out from the tables the
other areas own. The helpers cover who may run a report, the date range
(default: this school year to date), the pupil set a report covers (including
pupils who left part-way through the range), weekly buckets, rates per 100
pupils and a formula-safe CSV writer.
"""

from __future__ import annotations

import csv
import datetime as _dt
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import DATA_MANAGERS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

YEARS: tuple[int, ...] = P.YEAR_GROUPS
WEEKDAYS: tuple[str, ...] = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                             "Saturday", "Sunday")


# ── Who ──────────────────────────────────────────────────────────────

def is_data_manager(actor: Principal) -> bool:
    return actor.role in DATA_MANAGERS


def require_staff(actor: Principal, action: str) -> None:
    if actor.role not in STAFF_ROLES:
        activity_log.record(action, outcome="denied", principal=actor)
        raise PermissionDenied("Only staff can run reports.")


def require_data_manager(actor: Principal, action: str, what: str = "that") -> None:
    if not is_data_manager(actor):
        activity_log.record(action, outcome="denied", principal=actor)
        raise PermissionDenied(f"Only the data manager can do {what}.")


# ── Dates ────────────────────────────────────────────────────────────

def as_date(value: Any, label: str, problems: list[str]) -> _dt.date | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def date_range(start: Any = None, end: Any = None, *, cap_today: bool = True
               ) -> tuple[_dt.date, _dt.date]:
    """``(start, end)``: default this school year (1 September) to today.
    The end is never after today when *cap_today*."""
    problems: list[str] = []
    s = as_date(start, "From date", problems)
    e = as_date(end, "To date", problems)
    if problems:
        raise ValidationError(problems)
    today = _today()
    s = s or P.academic_year_start(today)
    e = e or today
    if cap_today:
        e = min(e, today)
    if e < s:
        raise ValidationError(["The end date is before the start date"])
    return s, e


def week_start(day: str | _dt.date) -> str:
    """The Monday of *day*'s week, as ISO text."""
    d = day if isinstance(day, _dt.date) else _dt.date.fromisoformat(str(day)[:10])
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def weekday_name(day: str | _dt.date) -> str:
    d = day if isinstance(day, _dt.date) else _dt.date.fromisoformat(str(day)[:10])
    return WEEKDAYS[d.weekday()]


# ── Pupils ───────────────────────────────────────────────────────────

def on_roll_between(p: P.Pupil, start: str, end: str) -> bool:
    """On roll for at least one day of *start*..*end*."""
    return p.admission_date <= end and (p.leaving_date is None or p.leaving_date >= start)


def on_roll_on(p: P.Pupil, day: str) -> bool:
    return p.admission_date <= day and (p.leaving_date is None or p.leaving_date >= day)


def int_or_none(value: Any) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(str(value).strip())
    except ValueError as e:
        raise ValidationError([f"'{value}' is not a whole number"]) from e


def cohort(start: str, end: str, *, year_group: Any = None, form: str | None = None,
           pupil_id: Any = None) -> list[P.Pupil]:
    """Pupils on roll at some point in the range (leavers included), filtered."""
    yg, pid = int_or_none(year_group), int_or_none(pupil_id)
    out = []
    for p in P.list_pupils(roll_status=None, year_group=yg, form_group=form or None):
        if pid is not None and p.pupil_id != pid:
            continue
        if on_roll_between(p, start, end):
            out.append(p)
    return out


def name(p: P.Pupil) -> str:
    return f"{p.legal_last_name}, {p.preferred_name or p.legal_first_name}"


#: Pupil groups for comparisons: (label, test). Only fields the pupil record holds.
GROUPS: tuple[tuple[str, Any], ...] = (
    ("All pupils", lambda p: True),
    ("Female", lambda p: p.gender == "Female"),
    ("Male", lambda p: p.gender == "Male"),
    ("Other / not stated", lambda p: p.gender not in ("Female", "Male")),
    ("No SEN (N)", lambda p: p.sen_status == "N"),
    ("SEN support (K)", lambda p: p.sen_status == "K"),
    ("EHC plan (E)", lambda p: p.sen_status == "E"),
    ("FSM eligible", lambda p: bool(p.fsm_eligible)),
    ("Not FSM", lambda p: not p.fsm_eligible),
    ("EAL", lambda p: bool(p.eal)),
    ("Not EAL", lambda p: not p.eal),
    *((f"Year {y}", (lambda y: lambda p: p.year_group == y)(y)) for y in P.YEAR_GROUPS),
)


# ── Numbers ──────────────────────────────────────────────────────────

def pct(n: float, d: float, places: int = 1) -> float | None:
    return round(100.0 * n / d, places) if d else None


def per_100(n: float, pupils: int) -> float | None:
    return round(100.0 * n / pupils, 2) if pupils else None


def mean(values: Iterable[float], places: int = 2) -> float | None:
    vals = list(values)
    return round(sum(vals) / len(vals), places) if vals else None


def show(v: Any) -> str:
    """A cell for a table: blank for None, numbers without trailing .0."""
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


# ── CSV ──────────────────────────────────────────────────────────────

def write_csv(path: str | Path, headings: Sequence[str], rows: Iterable[Sequence[Any]],
              *, actor: Principal, action: str, **log: Any) -> int:
    """Write a CSV with every cell made formula-safe; log the row count only."""
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([safe_cell(h) for h in headings])
        for row in rows:
            w.writerow([safe_cell(show(v)) for v in row])
            n += 1
    activity_log.record(action, principal=actor, rows=n, **log)
    return n
