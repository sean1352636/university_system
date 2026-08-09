"""Attendance calendar for the Sixth Form System.

Sibling to :mod:`attendance`. Everything in this package that divides by
"how many sessions were possible" needs to know which days the college
was actually open, and until now it approximated: Monday to Friday,
minus whatever the academic-year module happened to know about.

That approximation is not harmless. Count half term as teaching days and
every learner's attendance drops by a fortnight's worth of absence they
never had. Miss an INSET day and a whole college reads as 0% attendance
on a day nobody was expected in.

So the calendar is explicit here: term dates, closures, INSET days, bank
holidays and study leave, each with the kind of day it is and who it
applies to. :func:`is_open` and :func:`teaching_days` are what the rest
of the package asks.

**Study leave is the sixth-form-specific one.** A Year 13 on study leave
in May is not absent and is not in college; those sessions must leave
the denominator for that year group while Year 12 carries on normally.
That is why closures carry a year group and an AM/PM half, rather than
being a plain list of dates.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# What kind of non-teaching day this is. The distinction matters for the
# census: a bank holiday is not a closure the college chose, and study
# leave is not a closure at all — it is a cohort being elsewhere.
HOLIDAY: str = "Holiday"
HALF_TERM: str = "Half term"
BANK_HOLIDAY: str = "Bank holiday"
INSET: str = "INSET"
CLOSURE: str = "Exceptional closure"
STUDY_LEAVE: str = "Study leave"
EXAM_PERIOD: str = "Exam period"
DAY_KINDS: tuple[str, ...] = (
    HOLIDAY, HALF_TERM, BANK_HOLIDAY, INSET, CLOSURE, STUDY_LEAVE,
    EXAM_PERIOD,
)

# Kinds that remove the session from the attendance denominator
# entirely. An exam period does not — learners still have lessons
# around their papers.
NON_TEACHING: frozenset[str] = frozenset({
    HOLIDAY, HALF_TERM, BANK_HOLIDAY, INSET, CLOSURE, STUDY_LEAVE,
})

# Which half of the day a closure covers.
FULL: str = "FULL"
AM: str = "AM"
PM: str = "PM"
HALVES: tuple[str, ...] = (FULL, AM, PM)

# The mark an exceptional closure earns when one is written through to
# the register: `Y`, which counts for nothing on either side.
CLOSURE_CODE: str = "Y"
# Study leave is `S` — authorised, and the learner's own time.
STUDY_LEAVE_CODE: str = "S"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_calendar_terms (
    term_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    academic_year TEXT,
    start_date  TEXT NOT NULL,
    end_date    TEXT NOT NULL,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(name, academic_year)
);

CREATE TABLE IF NOT EXISTS attendance_calendar_days (
    day_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'Holiday',
    half        TEXT NOT NULL DEFAULT 'FULL',
    year_group  INTEGER,
    name        TEXT,
    notes       TEXT,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(date, kind, half, year_group)
);

CREATE INDEX IF NOT EXISTS idx_att_cal_days_date
    ON attendance_calendar_days(date);
CREATE INDEX IF NOT EXISTS idx_att_cal_days_year
    ON attendance_calendar_days(year_group);
CREATE INDEX IF NOT EXISTS idx_att_cal_terms_dates
    ON attendance_calendar_terms(start_date, end_date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Term:
    """One term of the academic year."""

    term_id: int
    name: str
    academic_year: str | None
    start_date: str
    end_date: str
    notes: str | None
    created_at: str | None

    def covers(self, date: str) -> bool:
        return self.start_date <= date <= self.end_date

    @property
    def label(self) -> str:
        return (f"{self.name}"
                + (f" {self.academic_year}" if self.academic_year else "")
                + f" ({self.start_date} → {self.end_date})")


@dataclass
class CalendarDay:
    """One non-teaching day, or half of one."""

    day_id: int
    date: str
    kind: str
    half: str
    year_group: int | None
    name: str | None
    notes: str | None
    created_by: str | None
    created_at: str | None

    @property
    def is_non_teaching(self) -> bool:
        return self.kind in NON_TEACHING

    @property
    def applies_to_everybody(self) -> bool:
        return self.year_group is None

    @property
    def label(self) -> str:
        who = ("all" if self.year_group is None
               else f"Year {self.year_group}")
        half = "" if self.half == FULL else f" ({self.half} only)"
        return f"{self.date} {self.kind}{half} — {who}"


@dataclass
class DayStatus:
    """Whether the college is open on a date, and why not."""

    date: str
    open: bool
    weekday: int
    sessions: tuple[str, ...]      # which of AM/PM are teaching
    reason: str | None = None
    entries: list[CalendarDay] | None = None

    @property
    def is_weekend(self) -> bool:
        return self.weekday > 5

    @property
    def half_day(self) -> bool:
        return len(self.sessions) == 1


@dataclass
class CalendarSummary:
    """What a window contains."""

    date_from: str
    date_to: str
    weekdays: int = 0
    teaching_days: int = 0
    half_days: int = 0
    closed_days: int = 0
    by_kind: dict[str, int] | None = None

    @property
    def sessions(self) -> int:
        """Teaching sessions — two per full day, one per half."""
        return self.teaching_days * 2 - self.half_days


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Attendance calendar schema ready at %s", DB_PATH)
    _DB_READY = True


def _term_row(r: sqlite3.Row) -> Term:
    return Term(term_id=r["term_id"], name=r["name"],
                academic_year=r["academic_year"],
                start_date=r["start_date"], end_date=r["end_date"],
                notes=r["notes"], created_at=r["created_at"])


def _day_row(r: sqlite3.Row) -> CalendarDay:
    return CalendarDay(day_id=r["day_id"], date=r["date"], kind=r["kind"],
                       half=r["half"], year_group=r["year_group"],
                       name=r["name"], notes=r["notes"],
                       created_by=r["created_by"], created_at=r["created_at"])


# ── Validation ──────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return HOLIDAY
    for kind in DAY_KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(DAY_KINDS)}")


def validate_half(value: Any) -> str:
    s = (value or "").strip().upper() if isinstance(value, str) else ""
    if not s:
        return FULL
    if s not in HALVES:
        raise ValidationError(f"Half must be one of: {', '.join(HALVES)}")
    return s


def _validate_year_group(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be a whole number") from None
    if year < 1 or year > 15:
        raise ValidationError("Year group must be between 1 and 15")
    return year


def _dates_between(date_from: str, date_to: str) -> list[str]:
    start = _dt.date.fromisoformat(core._validate_date(date_from))
    end = _dt.date.fromisoformat(core._validate_date(date_to))
    if end < start:
        raise ValidationError("From date must be on or before To date")
    if (end - start).days > 731:
        raise ValidationError("Date range is limited to two years")
    return [(start + _dt.timedelta(days=i)).isoformat()
            for i in range((end - start).days + 1)]


# ── Terms ───────────────────────────────────────────────────────────

def add_term(name: str, start_date: str, end_date: str, *,
             academic_year: str | None = None,
             notes: str | None = None) -> Term:
    """Record a term. Everything outside every term is holiday."""
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Term name is required")
    start_date = core._validate_date(start_date)
    end_date = core._validate_date(end_date)
    if end_date < start_date:
        raise ValidationError("A term cannot end before it starts")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_calendar_terms
                   (name, academic_year, start_date, end_date, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(name, academic_year) DO UPDATE SET
                   start_date = excluded.start_date,
                   end_date = excluded.end_date,
                   notes = COALESCE(excluded.notes,
                                    attendance_calendar_terms.notes)""",
            (name, (academic_year or "").strip() or None, start_date,
             end_date, (notes or "").strip() or None))
        conn.commit()
        term_id = int(cur.lastrowid or 0)
    logger.info("Term recorded: %s %s → %s", name, start_date, end_date)
    out = get_term(term_id) or term_for(start_date)
    assert out is not None
    return out


def get_term(term_id: int) -> Term | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_calendar_terms WHERE term_id = ?",
            (term_id,)).fetchone()
    return _term_row(r) if r else None


def list_terms(*, academic_year: str | None = None) -> list[Term]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_calendar_terms {where} "
            "ORDER BY start_date", args).fetchall()
    return [_term_row(r) for r in rows]


def term_for(date: str) -> Term | None:
    """Which term a date falls in, if any."""
    init_db()
    date = core._validate_date(date)
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_calendar_terms "
            "WHERE start_date <= ? AND end_date >= ? "
            "ORDER BY start_date LIMIT 1", (date, date)).fetchone()
    return _term_row(r) if r else None


def in_term(date: str) -> bool:
    """Whether a date is inside a term.

    With no terms configured this is ``True`` for everything, so a
    college that has not built its calendar is not suddenly told it is
    permanently on holiday.
    """
    init_db()
    if not list_terms():
        return True
    return term_for(date) is not None


def delete_term(term_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_calendar_terms WHERE term_id = ?",
            (term_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Non-teaching days ───────────────────────────────────────────────

def add_day(
    date: str,
    *,
    kind: str = HOLIDAY,
    half: str = FULL,
    year_group: int | None = None,
    name: str | None = None,
    notes: str | None = None,
    actor: str | None = None,
) -> CalendarDay:
    """Mark a date (or half of one) as non-teaching."""
    init_db()
    date = core._validate_date(date)
    kind = validate_kind(kind)
    half = validate_half(half)
    year_group = _validate_year_group(year_group)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_calendar_days
                   (date, kind, half, year_group, name, notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date, kind, half, year_group) DO UPDATE SET
                   name = COALESCE(excluded.name,
                                   attendance_calendar_days.name),
                   notes = COALESCE(excluded.notes,
                                    attendance_calendar_days.notes)""",
            (date, kind, half, year_group, (name or "").strip() or None,
             (notes or "").strip() or None, (actor or "").strip() or None))
        conn.commit()
    out = next((d for d in list_days(date=date)
                if d.kind == kind and d.half == half
                and d.year_group == year_group), None)
    assert out is not None
    return out


def add_range(
    date_from: str,
    date_to: str,
    *,
    kind: str = HOLIDAY,
    year_group: int | None = None,
    name: str | None = None,
    weekdays_only: bool = True,
    actor: str | None = None,
) -> int:
    """Mark a span — half term, a holiday, a study-leave fortnight.

    Weekends are skipped by default: recording them as closures would
    double-count days that were never teaching days to begin with.
    """
    added = 0
    for date in _dates_between(date_from, date_to):
        if weekdays_only and _dt.date.fromisoformat(date).weekday() >= 5:
            continue
        add_day(date, kind=kind, year_group=year_group, name=name,
                actor=actor)
        added += 1
    logger.info("Calendar: %d day(s) marked %s (%s → %s)", added, kind,
                date_from, date_to)
    return added


def list_days(*, date: str | None = None, date_from: str | None = None,
              date_to: str | None = None, kind: str | None = None,
              year_group: int | None = None,
              include_all_years: bool = True) -> list[CalendarDay]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if year_group is not None:
        year = _validate_year_group(year_group)
        if include_all_years:
            clauses.append("(year_group IS NULL OR year_group = ?)")
        else:
            clauses.append("year_group = ?")
        args.append(year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_calendar_days {where} "
            "ORDER BY date, kind", args).fetchall()
    return [_day_row(r) for r in rows]


def remove_day(day_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_calendar_days WHERE day_id = ?", (day_id,))
        conn.commit()
    return bool(cur.rowcount)


def clear_range(date_from: str, date_to: str, *,
                kind: str | None = None) -> int:
    """Undo a span — a closure that was entered against the wrong week."""
    init_db()
    clauses = ["date >= ?", "date <= ?"]
    args: list[Any] = [core._validate_date(date_from),
                       core._validate_date(date_to)]
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    with _connect() as conn:
        cur = conn.execute(
            f"DELETE FROM attendance_calendar_days "
            f"WHERE {' AND '.join(clauses)}", args)
        conn.commit()
    return int(cur.rowcount)


# ── The questions everything else asks ──────────────────────────────

def day_status(date: str, *, year_group: int | None = None) -> DayStatus:
    """Whether the college is open on a date, for whom, and which halves."""
    init_db()
    date = core._validate_date(date)
    weekday = _dt.date.fromisoformat(date).weekday() + 1
    if weekday > 5:
        return DayStatus(date=date, open=False, weekday=weekday,
                         sessions=(), reason="Weekend")
    if not in_term(date):
        return DayStatus(date=date, open=False, weekday=weekday,
                         sessions=(), reason="Outside term")

    entries = [d for d in list_days(date=date, year_group=year_group)
               if d.is_non_teaching]
    if year_group is None:
        # Asking about the college as a whole: a Year 13 study-leave day
        # does not close the college.
        entries = [d for d in entries if d.applies_to_everybody]

    open_sessions = {AM, PM}
    reason = None
    for entry in entries:
        reason = reason or f"{entry.kind}{f' — {entry.name}' if entry.name else ''}"
        if entry.half == FULL:
            open_sessions.clear()
            break
        open_sessions.discard(entry.half)

    sessions = tuple(s for s in (AM, PM) if s in open_sessions)
    return DayStatus(date=date, open=bool(sessions), weekday=weekday,
                     sessions=sessions,
                     reason=reason if not sessions or len(sessions) < 2
                     else None,
                     entries=entries)


def is_open(date: str, *, year_group: int | None = None) -> bool:
    """Whether any teaching happens on a date."""
    return day_status(date, year_group=year_group).open


def teaching_days(date_from: str, date_to: str, *,
                  year_group: int | None = None) -> list[str]:
    """Every date in the window the college teaches on.

    The replacement for the Monday-to-Friday guess. Anything dividing by
    "sessions possible" should be counting these.
    """
    return [date for date in _dates_between(date_from, date_to)
            if is_open(date, year_group=year_group)]


def teaching_sessions(date_from: str, date_to: str, *,
                      year_group: int | None = None) -> int:
    """AM/PM sessions in the window — the statutory denominator."""
    return sum(len(day_status(date, year_group=year_group).sessions)
               for date in _dates_between(date_from, date_to))


def next_teaching_day(after: str, *, year_group: int | None = None) -> str | None:
    """The next date the college is open. Used by anything that defers."""
    cursor = _dt.date.fromisoformat(core._validate_date(after))
    for _ in range(120):
        cursor += _dt.timedelta(days=1)
        if is_open(cursor.isoformat(), year_group=year_group):
            return cursor.isoformat()
    return None


def summary(date_from: str, date_to: str, *,
            year_group: int | None = None) -> CalendarSummary:
    """What a window contains, for a calendar screen."""
    out = CalendarSummary(date_from=core._validate_date(date_from),
                          date_to=core._validate_date(date_to), by_kind={})
    for date in _dates_between(date_from, date_to):
        status = day_status(date, year_group=year_group)
        if status.is_weekend:
            continue
        out.weekdays += 1
        if status.open:
            out.teaching_days += 1
            if status.half_day:
                out.half_days += 1
        else:
            out.closed_days += 1
        for entry in (status.entries or []):
            out.by_kind[entry.kind] = out.by_kind.get(entry.kind, 0) + 1
    return out


# ── Writing a closure through to the register ───────────────────────

def apply_closure(date: str, *, year_group: int | None = None,
                  actor: str | None = None) -> int:
    """Code every lesson on a closed date so nobody reads as absent.

    An unexpected closure — snow, a burst pipe — leaves a day of
    registers nobody took. Left alone those become unmarked lessons that
    count against the college; coded `Y` they count for nothing, which
    is the truth.
    """
    init_db()
    date = core._validate_date(date)
    status = day_status(date, year_group=year_group)
    if status.open:
        raise ValidationError(
            f"{date} is not marked as a closure — add it to the calendar "
            "first")
    kind = (status.entries or [None])[0]
    code = (STUDY_LEAVE_CODE if kind is not None and kind.kind == STUDY_LEAVE
            else CLOSURE_CODE)

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_register as _reg,
        attendance_weeks as _weeks,
    )
    weekday = _dt.date.fromisoformat(date).weekday() + 1
    slots = [s for s in _tt.list_slots() if s.day == weekday]
    slots = _weeks.filter_slots(slots, date)

    written = 0
    for slot in slots:
        if _reg.is_locked(slot.slot_id, date):
            continue
        members = _cg.list_members(slot.group_id)
        if not members:
            continue
        try:
            written += core.save_register(
                slot.slot_id, date,
                {sid: {"code": code, "notes": f"{kind.kind if kind else 'Closure'}",
                       "data_source": "derived"} for sid in members},
                actor=actor, reason=f"College closed: {date}",
                allow_retro=True)
        except ValidationError as e:
            logger.debug("Closure skipped slot #%d on %s: %s",
                         slot.slot_id, date, e)
    logger.info("Applied closure for %s: %d mark(s) coded %s", date, written,
                code)
    return written


def seed_bank_holidays(year: int, *, actor: str | None = None) -> int:
    """Add the fixed-date English bank holidays for a calendar year.

    Only the ones that fall on a fixed date — the movable feasts (Easter,
    the Mondays) vary by year and are better entered than guessed at.
    Christmas and Boxing Day shift to the next weekday when they land on
    a weekend, which is the rule that actually catches people out.
    """
    added = 0
    fixed = [(1, 1, "New Year's Day"), (12, 25, "Christmas Day"),
             (12, 26, "Boxing Day")]
    for month, day, name in fixed:
        date = _dt.date(year, month, day)
        while date.weekday() >= 5:
            date += _dt.timedelta(days=1)
        add_day(date.isoformat(), kind=BANK_HOLIDAY, name=name, actor=actor)
        added += 1
    logger.info("Seeded %d bank holiday(s) for %d", added, year)
    return added
