"""Academic years, terms and breaks: the shape of the school year.

Rules shared by the GUI and CLI:

* **Years** are named like the rest of the system ("2026/27") and always run
  1 September - 31 August, the same boundary the year-group, admissions and
  year-end rollover rules use, so the calendar can never disagree with them.
  Status: ``Planning`` (being prepared) → ``Active`` (the current year; set
  with :func:`set_current`, which archives the old one) → ``Archived`` (past;
  locked - change its status back to Planning to correct it).
* **Terms** sit inside their year and never overlap. Either three terms
  (Autumn / Spring / Summer, with half-terms recorded as breaks) or six
  (Autumn 1 ... Summer 2) work.
* **Breaks** are holidays, half-terms, INSET days, bank holidays and other
  closures - plus exam periods, which are recorded but don't close the school.
* **School days** are weekdays inside a term that no closure covers. INSET
  days are staff days but not pupil days. :func:`check_year` counts them
  against the usual 190 pupil days and 5 INSET days and reports problems.
* **Helpers**: England & Wales bank holidays (:func:`add_bank_holidays`) and
  copying last year's pattern 52 weeks on (:func:`copy_from`).

Everyone on the staff can read the calendar; only
:data:`access.CALENDAR_EDITORS` can change years, terms and breaks.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field, fields
from typing import Any, Iterable

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.academic_calendar import school_year
from education_system.systems.secondary.core.permissions.access import CALENDAR_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

YEAR_STATUSES: tuple[str, ...] = ("Planning", "Active", "Archived")
TERM_NAMES: tuple[str, ...] = (
    "Autumn", "Autumn 1", "Autumn 2",
    "Spring", "Spring 1", "Spring 2",
    "Summer", "Summer 1", "Summer 2",
)
BREAK_TYPES: tuple[str, ...] = (
    "Holiday", "Half-Term", "INSET", "Bank Holiday", "Exam Period", "Other",
)
#: Break types that close the school to pupils.
CLOSURE_TYPES = frozenset({"Holiday", "Half-Term", "INSET", "Bank Holiday", "Other"})
PUPIL_DAYS = 190
INSET_DAYS = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS academic_years (
    year_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'Planning'
               CHECK (status IN ('Planning', 'Active', 'Archived')),
    notes      TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT
);
-- At most one Active year.
CREATE UNIQUE INDEX IF NOT EXISTS ux_academic_years_active
    ON academic_years (status) WHERE status = 'Active';

CREATE TABLE IF NOT EXISTS academic_terms (
    term_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id    INTEGER NOT NULL REFERENCES academic_years(year_id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    notes      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT,
    UNIQUE (year_id, name)
);
CREATE INDEX IF NOT EXISTS ix_academic_terms ON academic_terms (start_date, end_date);

CREATE TABLE IF NOT EXISTS academic_breaks (
    break_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id    INTEGER NOT NULL REFERENCES academic_years(year_id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL CHECK (type IN ('Holiday', 'Half-Term', 'INSET',
                                              'Bank Holiday', 'Exam Period', 'Other')),
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    notes      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT
);
CREATE INDEX IF NOT EXISTS ix_academic_breaks ON academic_breaks (start_date, end_date);
"""

database.register_schema("academic_year", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


@dataclass(frozen=True)
class AcademicYear:
    year_id: int
    name: str
    start_date: str
    end_date: str
    status: str
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def locked(self) -> bool:
        return self.status == "Archived"


@dataclass(frozen=True)
class Term:
    term_id: int
    year_id: int
    name: str
    start_date: str
    end_date: str
    notes: str | None
    updated_at: str
    updated_by: str | None


@dataclass(frozen=True)
class Break:
    break_id: int
    year_id: int
    name: str
    type: str
    start_date: str
    end_date: str
    notes: str | None
    updated_at: str
    updated_by: str | None

    @property
    def closes_school(self) -> bool:
        return self.type in CLOSURE_TYPES


def _make(cls, r):
    return cls(**{f.name: r[f.name] for f in fields(cls)})


# ── Helpers ─────────────────────────────────────────────────────────

_NAME_RE = re.compile(r"^(\d{4})/(\d{2})$")


def year_name_for(day: _dt.date) -> str:
    return school_year.current_year(day)


def bounds(name: str) -> tuple[str, str]:
    m = _NAME_RE.match(name or "")
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValidationError(["A year is named like 2026/27"])
    start = int(m.group(1))
    return _dt.date(start, 9, 1).isoformat(), _dt.date(start + 1, 8, 31).isoformat()


def _d(value: str) -> _dt.date:
    return _dt.date.fromisoformat(value)


def _days(start: str, end: str) -> Iterable[_dt.date]:
    d, last = _d(start), _d(end)
    while d <= last:
        yield d
        d += _dt.timedelta(days=1)


def _require(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in CALENDAR_EDITORS:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account can view the calendar but not change the "
                               "school year, terms or holidays.")


def _invalid(action: str, actor: Principal, target: Any, problems: list[str]) -> None:
    activity_log.record(action, target=target, outcome="invalid", principal=actor,
                        problems=len(problems))
    raise ValidationError(problems)


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    d = P._parse_date(value, label, problems)
    if d is None and not any(p.startswith(label) for p in problems):
        problems.append(f"{label} is required")
    return d


# ── Years ────────────────────────────────────────────────────────────

def list_years() -> list[AcademicYear]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM academic_years ORDER BY name DESC").fetchall()
    return [_make(AcademicYear, r) for r in rows]


def get_year(year_id: int) -> AcademicYear | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM academic_years WHERE year_id = ?",
                         (int(year_id),)).fetchone()
    return _make(AcademicYear, r) if r else None


def get_year_by_name(name: str) -> AcademicYear | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM academic_years WHERE name = ?", (name,)).fetchone()
    return _make(AcademicYear, r) if r else None


def year_for(day: _dt.date) -> AcademicYear | None:
    """The recorded year a date falls in (any status)."""
    return get_year_by_name(year_name_for(day))


def current_year(today: _dt.date | None = None) -> AcademicYear | None:
    """The Active year, or failing that the recorded year today falls in."""
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM academic_years WHERE status = 'Active'").fetchone()
    return _make(AcademicYear, r) if r else year_for(today or _dt.date.today())


def _year_or_raise(year_id: int, action: str, actor: Principal, *,
                   editable: bool = False) -> AcademicYear:
    y = get_year(year_id)
    if y is None:
        activity_log.record(action, target=f"year:{year_id}", outcome="not_found",
                            principal=actor)
        raise NotFound(f"No academic year {year_id}")
    if editable and y.locked:
        _invalid(action, actor, y.name, [f"{y.name} is archived - set its status back to "
                                         "Planning to change it"])
    return y


def create_year(name: str, *, actor: Principal, notes: str | None = None) -> AcademicYear:
    _require(actor, "calendar.year.create", name)
    name = (name or "").strip()
    try:
        start, end = bounds(name)
    except ValidationError as e:
        _invalid("calendar.year.create", actor, name, e.problems)
    if get_year_by_name(name):
        _invalid("calendar.year.create", actor, name, [f"{name} already exists"])
    with database.connect() as conn:
        y_id = conn.execute(
            "INSERT INTO academic_years (name, start_date, end_date, notes, created_by, "
            "updated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (name, start, end, P._clean_text(notes, 1000), actor.username,
             actor.username)).lastrowid
    activity_log.record("calendar.year.create", target=name, principal=actor)
    return get_year(y_id)  # type: ignore[return-value]


def update_year(year_id: int, *, actor: Principal, notes: str | None = None,
                status: str | None = None) -> AcademicYear:
    """Change notes, or move the status between Planning and Archived (use
    :func:`set_current` to make a year Active)."""
    _require(actor, "calendar.year.update", f"year:{year_id}")
    y = _year_or_raise(year_id, "calendar.year.update", actor)
    changes: dict[str, Any] = {}
    if notes is not None:
        changes["notes"] = P._clean_text(notes, 1000)
    if status is not None and status != y.status:
        if status not in YEAR_STATUSES:
            _invalid("calendar.year.update", actor, y.name,
                     ["Status must be " + ", ".join(YEAR_STATUSES)])
        if status == "Active":
            return set_current(year_id, actor=actor)
        changes["status"] = status
    if changes:
        with database.connect() as conn:
            conn.execute(f"UPDATE academic_years SET {', '.join(f'{k} = ?' for k in changes)}, "
                         "updated_at = datetime('now'), updated_by = ? WHERE year_id = ?",
                         [*changes.values(), actor.username, year_id])
    activity_log.record("calendar.year.update", target=y.name, principal=actor,
                        fields=sorted(changes) or None)
    return get_year(year_id)  # type: ignore[return-value]


def set_current(year_id: int, *, actor: Principal,
                today: _dt.date | None = None) -> AcademicYear:
    """Make a year the Active one (the old Active year is archived). It must
    have terms, pass :func:`check_year` without errors, and be this year or
    one starting within the next 3 months."""
    today = today or _dt.date.today()
    _require(actor, "calendar.year.current", f"year:{year_id}")
    y = _year_or_raise(year_id, "calendar.year.current", actor)
    problems = []
    if y.status == "Active":
        problems.append(f"{y.name} is already the current year")
    if _d(y.end_date) < today:
        problems.append(f"{y.name} has already ended")
    elif _d(y.start_date) > today + _dt.timedelta(days=92):
        problems.append(f"{y.name} doesn't start for over 3 months")
    if not list_terms(year_id):
        problems.append(f"Add {y.name}'s terms first")
    problems += check_year(year_id).errors
    if problems:
        _invalid("calendar.year.current", actor, y.name, problems)
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE academic_years SET status = 'Archived', updated_at = "
                     "datetime('now'), updated_by = ? WHERE status = 'Active'",
                     (actor.username,))
        conn.execute("UPDATE academic_years SET status = 'Active', updated_at = "
                     "datetime('now'), updated_by = ? WHERE year_id = ?",
                     (actor.username, year_id))
    activity_log.record("calendar.year.current", target=y.name, principal=actor)
    return get_year(year_id)  # type: ignore[return-value]


def delete_year(year_id: int, *, actor: Principal) -> AcademicYear:
    """Remove a year (and its terms and breaks). Not the Active year."""
    _require(actor, "calendar.year.delete", f"year:{year_id}")
    y = _year_or_raise(year_id, "calendar.year.delete", actor)
    if y.status == "Active":
        _invalid("calendar.year.delete", actor, y.name,
                 ["The current year can't be deleted"])
    with database.connect() as conn:
        conn.execute("DELETE FROM academic_years WHERE year_id = ?", (year_id,))
    activity_log.record("calendar.year.delete", target=y.name, principal=actor)
    return y


# ── Terms ────────────────────────────────────────────────────────────

def list_terms(year_id: int | None = None) -> list[Term]:
    sql, params = "SELECT * FROM academic_terms", []
    if year_id is not None:
        sql += " WHERE year_id = ?"
        params.append(int(year_id))
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY start_date", params).fetchall()
    return [_make(Term, r) for r in rows]


def get_term(term_id: int) -> Term | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM academic_terms WHERE term_id = ?",
                         (int(term_id),)).fetchone()
    return _make(Term, r) if r else None


def _check_range(y: AcademicYear, start: str | None, end: str | None,
                 problems: list[str]) -> None:
    if start and end:
        if end < start:
            problems.append("The end date can't be before the start date")
        if start < y.start_date or end > y.end_date:
            problems.append(f"Dates must be inside {y.name} ({y.start_date} to {y.end_date})")


def _save_term(year_id: int, data: dict[str, Any], actor: Principal,
               term_id: int | None) -> Term:
    action = "calendar.term." + ("update" if term_id else "create")
    _require(actor, action, f"year:{year_id}")
    y = _year_or_raise(year_id, action, actor, editable=True)
    problems: list[str] = []
    name = P._clean_text(data.get("name"), 20)
    if name not in TERM_NAMES:
        problems.append("Term name must be one of: " + ", ".join(TERM_NAMES))
    start = _date(data.get("start_date"), "Start date", problems)
    end = _date(data.get("end_date"), "End date", problems)
    _check_range(y, start, end, problems)
    for t in list_terms(year_id):
        if t.term_id == term_id:
            continue
        if t.name == name:
            problems.append(f"{y.name} already has a {name} term")
        if start and end and start <= t.end_date and end >= t.start_date:
            problems.append(f"Overlaps {t.name} ({t.start_date} to {t.end_date})")
    if problems:
        _invalid(action, actor, y.name, problems)
    notes = P._clean_text(data.get("notes"), 500)
    with database.connect() as conn:
        if term_id:
            conn.execute("UPDATE academic_terms SET name = ?, start_date = ?, end_date = ?, "
                         "notes = ?, updated_at = datetime('now'), updated_by = ? "
                         "WHERE term_id = ?", (name, start, end, notes, actor.username, term_id))
        else:
            term_id = conn.execute(
                "INSERT INTO academic_terms (year_id, name, start_date, end_date, notes, "
                "updated_by) VALUES (?, ?, ?, ?, ?, ?)",
                (year_id, name, start, end, notes, actor.username)).lastrowid
    activity_log.record(action, target=f"{y.name} {name}", principal=actor)
    return get_term(term_id)  # type: ignore[arg-type,return-value]


def add_term(year_id: int, data: dict[str, Any], *, actor: Principal) -> Term:
    return _save_term(year_id, data, actor, None)


def update_term(term_id: int, data: dict[str, Any], *, actor: Principal) -> Term:
    t = get_term(term_id)
    if t is None:
        raise NotFound(f"No term {term_id}")
    merged = {"name": t.name, "start_date": t.start_date, "end_date": t.end_date,
              "notes": t.notes, **data}
    return _save_term(t.year_id, merged, actor, term_id)


def delete_term(term_id: int, *, actor: Principal) -> Term:
    _require(actor, "calendar.term.delete", f"term:{term_id}")
    t = get_term(term_id)
    if t is None:
        raise NotFound(f"No term {term_id}")
    y = _year_or_raise(t.year_id, "calendar.term.delete", actor, editable=True)
    with database.connect() as conn:
        conn.execute("DELETE FROM academic_terms WHERE term_id = ?", (term_id,))
    activity_log.record("calendar.term.delete", target=f"{y.name} {t.name}", principal=actor)
    return t


# ── Breaks ───────────────────────────────────────────────────────────

def list_breaks(year_id: int | None = None, *, type_: str | None = None) -> list[Break]:
    where, params = [], []
    if year_id is not None:
        where.append("year_id = ?")
        params.append(int(year_id))
    if type_:
        where.append("type = ?")
        params.append(type_)
    sql = "SELECT * FROM academic_breaks" + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY start_date, break_id", params).fetchall()
    return [_make(Break, r) for r in rows]


def get_break(break_id: int) -> Break | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM academic_breaks WHERE break_id = ?",
                         (int(break_id),)).fetchone()
    return _make(Break, r) if r else None


def _save_break(year_id: int, data: dict[str, Any], actor: Principal,
                break_id: int | None) -> Break:
    action = "calendar.break." + ("update" if break_id else "create")
    _require(actor, action, f"year:{year_id}")
    y = _year_or_raise(year_id, action, actor, editable=True)
    problems: list[str] = []
    name = P._clean_text(data.get("name"), 80)
    if not name:
        problems.append("Name is required")
    type_ = P._clean_text(data.get("type"), 20) or "Holiday"
    if type_ not in BREAK_TYPES:
        problems.append("Type must be one of: " + ", ".join(BREAK_TYPES))
    start = _date(data.get("start_date"), "Start date", problems)
    end = _date(data.get("end_date") or data.get("start_date"), "End date", problems)
    _check_range(y, start, end, problems)
    if start and end and not problems:
        for b in list_breaks(year_id):
            if b.break_id != break_id and b.type == type_ and start <= b.end_date \
                    and end >= b.start_date:
                problems.append(f"Overlaps {b.name} ({b.start_date} to {b.end_date})")
    if problems:
        _invalid(action, actor, y.name, problems)
    notes = P._clean_text(data.get("notes"), 500)
    with database.connect() as conn:
        if break_id:
            conn.execute("UPDATE academic_breaks SET name = ?, type = ?, start_date = ?, "
                         "end_date = ?, notes = ?, updated_at = datetime('now'), updated_by = ? "
                         "WHERE break_id = ?",
                         (name, type_, start, end, notes, actor.username, break_id))
        else:
            break_id = conn.execute(
                "INSERT INTO academic_breaks (year_id, name, type, start_date, end_date, notes, "
                "updated_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (year_id, name, type_, start, end, notes, actor.username)).lastrowid
    activity_log.record(action, target=f"{y.name} {type_}", principal=actor)
    return get_break(break_id)  # type: ignore[arg-type,return-value]


def add_break(year_id: int, data: dict[str, Any], *, actor: Principal) -> Break:
    return _save_break(year_id, data, actor, None)


def update_break(break_id: int, data: dict[str, Any], *, actor: Principal) -> Break:
    b = get_break(break_id)
    if b is None:
        raise NotFound(f"No break {break_id}")
    merged = {"name": b.name, "type": b.type, "start_date": b.start_date,
              "end_date": b.end_date, "notes": b.notes, **data}
    return _save_break(b.year_id, merged, actor, break_id)


def delete_break(break_id: int, *, actor: Principal) -> Break:
    _require(actor, "calendar.break.delete", f"break:{break_id}")
    b = get_break(break_id)
    if b is None:
        raise NotFound(f"No break {break_id}")
    y = _year_or_raise(b.year_id, "calendar.break.delete", actor, editable=True)
    with database.connect() as conn:
        conn.execute("DELETE FROM academic_breaks WHERE break_id = ?", (break_id,))
    activity_log.record("calendar.break.delete", target=f"{y.name} {b.type}", principal=actor)
    return b


# ── Bank holidays + copying a year ───────────────────────────────────

def _easter(year: int) -> _dt.date:
    """Easter Sunday (Gregorian, anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return _dt.date(year, month, day)


def _first_monday(year: int, month: int) -> _dt.date:
    d = _dt.date(year, month, 1)
    return d + _dt.timedelta(days=(7 - d.weekday()) % 7)


def _last_monday(year: int, month: int) -> _dt.date:
    nxt = _dt.date(year + (month == 12), month % 12 + 1, 1)
    d = nxt - _dt.timedelta(days=1)
    return d - _dt.timedelta(days=d.weekday())


def england_bank_holidays(year: int) -> list[tuple[_dt.date, str]]:
    """Regular England & Wales bank holidays in a calendar year (one-off
    extra days, like coronations, aren't included)."""
    easter = _easter(year)
    out = []
    ny = _dt.date(year, 1, 1)
    out.append((ny + _dt.timedelta(days={5: 2, 6: 1}.get(ny.weekday(), 0)),
                "New Year's Day" + (" (substitute)" if ny.weekday() >= 5 else "")))
    out += [(easter - _dt.timedelta(days=2), "Good Friday"),
            (easter + _dt.timedelta(days=1), "Easter Monday"),
            (_first_monday(year, 5), "Early May bank holiday"),
            (_last_monday(year, 5), "Spring bank holiday"),
            (_last_monday(year, 8), "Summer bank holiday")]
    xmas, boxing = _dt.date(year, 12, 25), _dt.date(year, 12, 26)
    if xmas.weekday() == 5:      # Sat: Mon 27 + Tue 28
        out += [(_dt.date(year, 12, 27), "Christmas Day (substitute)"),
                (_dt.date(year, 12, 28), "Boxing Day (substitute)")]
    elif xmas.weekday() == 6:    # Sun: Boxing Mon 26, Christmas sub Tue 27
        out += [(boxing, "Boxing Day"), (_dt.date(year, 12, 27), "Christmas Day (substitute)")]
    elif xmas.weekday() == 4:    # Fri: Boxing Sat → Mon 28
        out += [(xmas, "Christmas Day"), (_dt.date(year, 12, 28), "Boxing Day (substitute)")]
    else:
        out += [(xmas, "Christmas Day"), (boxing, "Boxing Day")]
    return out


def add_bank_holidays(year_id: int, *, actor: Principal) -> list[Break]:
    """Add the year's England & Wales bank holidays that fall on a school
    day (ones already inside a closure are skipped). Returns those added."""
    _require(actor, "calendar.bank_holidays", f"year:{year_id}")
    y = _year_or_raise(year_id, "calendar.bank_holidays", actor, editable=True)
    start, end = _d(y.start_date), _d(y.end_date)
    days = [(d, n) for yr in (start.year, end.year) for d, n in england_bank_holidays(yr)
            if start <= d <= end]
    closures = [b for b in list_breaks(year_id) if b.closes_school]
    added = []
    for d, name in sorted(days):
        iso = d.isoformat()
        if any(b.start_date <= iso <= b.end_date for b in closures):
            continue
        if term_for(d, year_id=year_id) is None:
            continue  # school holiday anyway
        added.append(add_break(year_id, {"name": name, "type": "Bank Holiday",
                                         "start_date": iso, "end_date": iso}, actor=actor))
    activity_log.record("calendar.bank_holidays", target=y.name, principal=actor,
                        added=len(added))
    return added


def copy_from(year_id: int, source_year_id: int, *, actor: Principal) -> tuple[int, int]:
    """Copy another year's terms and breaks into an empty year, moved by whole
    weeks so each date keeps its weekday. Bank holidays aren't copied (add
    them with :func:`add_bank_holidays` - their dates move differently).
    Returns (terms, breaks) copied. Check the dates afterwards."""
    _require(actor, "calendar.copy", f"year:{year_id}")
    y = _year_or_raise(year_id, "calendar.copy", actor, editable=True)
    src = _year_or_raise(source_year_id, "calendar.copy", actor)
    if list_terms(year_id) or list_breaks(year_id):
        _invalid("calendar.copy", actor, y.name,
                 [f"{y.name} already has terms or breaks - copying only fills an empty year"])
    weeks = round((_d(y.start_date) - _d(src.start_date)).days / 7)
    shift = _dt.timedelta(weeks=weeks)
    lo, hi = y.start_date, y.end_date

    def move(a: str, b: str) -> tuple[str, str] | None:
        s, e = (_d(a) + shift).isoformat(), (_d(b) + shift).isoformat()
        s, e = max(s, lo), min(e, hi)
        return (s, e) if s <= e else None

    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        terms = breaks = 0
        for t in list_terms(source_year_id):
            r = move(t.start_date, t.end_date)
            if r:
                conn.execute("INSERT INTO academic_terms (year_id, name, start_date, end_date, "
                             "updated_by) VALUES (?, ?, ?, ?, ?)",
                             (year_id, t.name, *r, actor.username))
                terms += 1
        for b in list_breaks(source_year_id):
            r = move(b.start_date, b.end_date)
            if r and b.type != "Bank Holiday":
                conn.execute("INSERT INTO academic_breaks (year_id, name, type, start_date, "
                             "end_date, updated_by) VALUES (?, ?, ?, ?, ?, ?)",
                             (year_id, b.name, b.type, *r, actor.username))
                breaks += 1
    activity_log.record("calendar.copy", target=y.name, principal=actor, source=src.name,
                        terms=terms, breaks=breaks)
    return terms, breaks


# ── Asking about dates ───────────────────────────────────────────────

@dataclass(frozen=True)
class DayInfo:
    date: _dt.date
    year: AcademicYear | None
    term: Term | None
    breaks: list[Break]
    week: int | None

    @property
    def is_weekend(self) -> bool:
        return self.date.weekday() >= 5

    @property
    def closure(self) -> Break | None:
        return next((b for b in self.breaks if b.closes_school), None)

    @property
    def is_staff_day(self) -> bool:
        return bool(self.term) and not self.is_weekend and not any(
            b.closes_school and b.type != "INSET" for b in self.breaks)

    @property
    def is_school_day(self) -> bool:
        """Pupils are in school."""
        return self.is_staff_day and self.closure is None

    @property
    def label(self) -> str:
        if self.year is None:
            return "No academic year recorded"
        if self.is_weekend:
            return "Weekend"
        if self.closure:
            return f"{self.closure.type}: {self.closure.name}"
        if self.term is None:
            return "School holiday (between terms)"
        return f"{self.term.name} term" + (f", week {self.week}" if self.week else "")


def term_for(day: _dt.date, *, year_id: int | None = None) -> Term | None:
    iso = day.isoformat()
    with database.connect() as conn:
        sql = "SELECT * FROM academic_terms WHERE start_date <= ? AND end_date >= ?"
        params: list[Any] = [iso, iso]
        if year_id is not None:
            sql += " AND year_id = ?"
            params.append(year_id)
        r = conn.execute(sql, params).fetchone()
    return _make(Term, r) if r else None


def week_of_term(day: _dt.date, term: Term) -> int:
    """Week number in the term, counted from the Monday of its first week."""
    first = _d(term.start_date)
    first -= _dt.timedelta(days=first.weekday())
    return (day - first).days // 7 + 1


def day_info(day: _dt.date) -> DayInfo:
    iso = day.isoformat()
    year = year_for(day)
    term = term_for(day)
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM academic_breaks WHERE start_date <= ? AND "
                            "end_date >= ? ORDER BY start_date", (iso, iso)).fetchall()
    return DayInfo(day, year, term, [_make(Break, r) for r in rows],
                   week_of_term(day, term) if term else None)


def month_info(year: int, month: int) -> dict[_dt.date, DayInfo]:
    """Every day of a month, for the month grid (few queries)."""
    first = _dt.date(year, month, 1)
    last = _dt.date(year + (month == 12), month % 12 + 1, 1) - _dt.timedelta(days=1)
    lo, hi = first.isoformat(), last.isoformat()
    with database.connect() as conn:
        terms = [_make(Term, r) for r in conn.execute(
            "SELECT * FROM academic_terms WHERE start_date <= ? AND end_date >= ?", (hi, lo))]
        breaks = [_make(Break, r) for r in conn.execute(
            "SELECT * FROM academic_breaks WHERE start_date <= ? AND end_date >= ?", (hi, lo))]
    years = {n: get_year_by_name(n) for n in {year_name_for(first), year_name_for(last)}}
    out = {}
    for d in _days(lo, hi):
        iso = d.isoformat()
        term = next((t for t in terms if t.start_date <= iso <= t.end_date), None)
        out[d] = DayInfo(d, years[year_name_for(d)], term,
                         [b for b in breaks if b.start_date <= iso <= b.end_date],
                         week_of_term(d, term) if term else None)
    return out


def school_days_between(start: _dt.date, end: _dt.date) -> int:
    n = 0
    d = _dt.date(start.year, start.month, 1)
    while d <= end:
        for day, info in month_info(d.year, d.month).items():
            if start <= day <= end and info.is_school_day:
                n += 1
        d = _dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return n


@dataclass
class YearCheck:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pupil_days: int = 0
    staff_days: int = 0
    inset_days: int = 0


def check_year(year_id: int) -> YearCheck:
    """Problems with a year's dates, and its school-day counts."""
    y = get_year(year_id)
    out = YearCheck()
    if y is None:
        out.errors.append("No such year")
        return out
    terms, brks = list_terms(year_id), list_breaks(year_id)
    if not terms:
        out.warnings.append("No terms recorded yet")
        return out
    for i, t in enumerate(terms):
        if t.start_date < y.start_date or t.end_date > y.end_date:
            out.errors.append(f"{t.name} is outside {y.name}")
        if t.end_date < t.start_date:
            out.errors.append(f"{t.name} ends before it starts")
        if i and t.start_date <= terms[i - 1].end_date:
            out.errors.append(f"{t.name} overlaps {terms[i - 1].name}")
        for label, date in (("starts", t.start_date), ("ends", t.end_date)):
            if _d(date).weekday() >= 5:
                out.warnings.append(f"{t.name} {label} on a {_d(date):%A}")
    for b in brks:
        if b.start_date < y.start_date or b.end_date > y.end_date:
            out.errors.append(f"{b.name} is outside {y.name}")
    for t in terms:
        for d in _days(t.start_date, t.end_date):
            if d.weekday() >= 5:
                continue
            iso = d.isoformat()
            closing = [b for b in brks if b.closes_school and b.start_date <= iso <= b.end_date]
            if not closing:
                out.pupil_days += 1
                out.staff_days += 1
            elif all(b.type == "INSET" for b in closing):
                out.inset_days += 1
                out.staff_days += 1
    if out.pupil_days != PUPIL_DAYS:
        out.warnings.append(f"{out.pupil_days} pupil days (schools normally open for "
                            f"{PUPIL_DAYS})")
    if out.inset_days != INSET_DAYS:
        out.warnings.append(f"{out.inset_days} INSET days (normally {INSET_DAYS})")
    return out


def upcoming_breaks(today: _dt.date | None = None, limit: int = 5) -> list[Break]:
    iso = (today or _dt.date.today()).isoformat()
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM academic_breaks WHERE end_date >= ? AND type != "
                            "'Exam Period' ORDER BY start_date LIMIT ?", (iso, limit)).fetchall()
    return [_make(Break, r) for r in rows]
