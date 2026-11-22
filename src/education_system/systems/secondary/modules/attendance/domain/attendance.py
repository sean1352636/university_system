"""Registers and attendance: the statutory AM/PM register plus lesson registers.

**Session register.** Each pupil gets one mark per session (AM and PM) on each
school day, using the DfE attendance codes (2024 list, :data:`CODES`). One row
per ``(pupil, date, session)`` in ``attendance_marks``. Every change is kept in
``attendance_audit`` with the old and new code, so an amended register still
shows what was first entered, by whom and when.

* Marks go on school days only: the academic calendar decides (holidays and
  INSET days are refused). With no calendar recorded, Monday to Friday.
* No future dates, and only while the pupil is on roll (from the admission
  date up to the leaving date).
* Teachers and other staff take **today's** register with ``/`` (present),
  ``L`` (late) and ``N`` (absent, no reason yet). Reasons (illness, leave...),
  other dates and deletions are for :data:`ATTENDANCE_EDITORS` - the
  attendance office. A teacher's register never overwrites a reason the office
  has already entered.
* A late arrival is ``L`` up to the time the register closes and ``U``
  (unauthorised) after it; the minutes late are kept.

**Lesson registers.** For each timetabled lesson on a day, the teacher marks the
group P / L / A / X (X = away on a school activity or a known absence). A pupil
marked present for the session but absent from a lesson is listed under
"missing from lessons" - the internal truancy check.

**Figures.** Attendance % = sessions present (incl. approved off-site
activity) / possible sessions; codes "not counted" (D, X, Q, Y1-Y7, Z, #) are
not possible sessions. Persistent absence is missing 10% or more, severe 50%.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import ATTENDANCE_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

SESSIONS: tuple[str, ...] = ("AM", "PM")

PRESENT, AEA, AUTHORISED, UNAUTHORISED, NOT_COUNTED = (
    "present", "aea", "authorised", "unauthorised", "not_counted")
CATEGORY_LABELS = {
    PRESENT: "Present",
    AEA: "Approved educational activity (counts as present)",
    AUTHORISED: "Authorised absence",
    UNAUTHORISED: "Unauthorised absence",
    NOT_COUNTED: "Not counted (not a possible session)",
}

#: DfE attendance codes (from August 2024): code -> (label, category).
CODES: dict[str, tuple[str, str]] = {
    "/": ("Present (AM)", PRESENT),
    "\\": ("Present (PM)", PRESENT),
    "L": ("Late, before the register closed", PRESENT),
    "K": ("Education arranged by the local authority", AEA),
    "V": ("Educational visit or trip", AEA),
    "P": ("Approved sporting activity", AEA),
    "W": ("Work experience", AEA),
    "B": ("Other approved off-site education", AEA),
    "C": ("Leave of absence - exceptional circumstances", AUTHORISED),
    "C1": ("Leave - regulated performance or employment", AUTHORISED),
    "C2": ("Part-time timetable", AUTHORISED),
    "E": ("Suspended or excluded, no alternative provision", AUTHORISED),
    "I": ("Illness", AUTHORISED),
    "J1": ("Interview", AUTHORISED),
    "M": ("Medical or dental appointment", AUTHORISED),
    "R": ("Religious observance", AUTHORISED),
    "S": ("Study leave", AUTHORISED),
    "T": ("Mobile child (Traveller), travelling", AUTHORISED),
    "G": ("Holiday not agreed", UNAUTHORISED),
    "N": ("Reason not yet provided", UNAUTHORISED),
    "O": ("Other unauthorised absence", UNAUTHORISED),
    "U": ("Arrived after the register closed", UNAUTHORISED),
    "D": ("Dual registered - at the other school", NOT_COUNTED),
    "X": ("Not required to attend (non-compulsory age)", NOT_COUNTED),
    "Q": ("Unable to attend - no access arrangements", NOT_COUNTED),
    "Y1": ("Unable to attend - transport not provided", NOT_COUNTED),
    "Y2": ("Unable to attend - widespread transport disruption", NOT_COUNTED),
    "Y3": ("Unable to attend - part of the school closed", NOT_COUNTED),
    "Y4": ("Unable to attend - whole school closed unexpectedly", NOT_COUNTED),
    "Y5": ("Unable to attend - criminal justice detention", NOT_COUNTED),
    "Y6": ("Unable to attend - public health guidance or law", NOT_COUNTED),
    "Y7": ("Unable to attend - other unavoidable cause", NOT_COUNTED),
    "Z": ("Not yet on roll", NOT_COUNTED),
    "#": ("Planned whole-school closure", NOT_COUNTED),
}

#: Codes any member of staff may enter on today's register.
TEACHER_CODES = frozenset({"/", "\\", "L", "N"})

#: Lesson register marks.
LESSON_MARKS: dict[str, str] = {
    "P": "Present",
    "L": "Late",
    "A": "Absent",
    "X": "Away - school activity or known absence",
}

PERSISTENT_ABSENCE = 10.0   # % of possible sessions missed
SEVERE_ABSENCE = 50.0

DEFAULT_TIMES = {"am_start": "08:40", "am_close": "09:10",
                 "pm_start": "13:40", "pm_close": "14:05"}
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_marks (
    mark_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id     INTEGER NOT NULL REFERENCES pupils (pupil_id),
    date         TEXT NOT NULL,
    session      TEXT NOT NULL CHECK (session IN ('AM', 'PM')),
    code         TEXT NOT NULL,
    minutes_late INTEGER,
    notes        TEXT,
    recorded_at  TEXT NOT NULL DEFAULT (datetime('now')),
    recorded_by  TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by   TEXT,
    UNIQUE (pupil_id, date, session)
);
CREATE INDEX IF NOT EXISTS ix_attendance_marks_date ON attendance_marks (date, session);
CREATE TABLE IF NOT EXISTS attendance_registers (
    register_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    session     TEXT NOT NULL CHECK (session IN ('AM', 'PM')),
    form_group  TEXT NOT NULL COLLATE NOCASE,
    year_group  INTEGER NOT NULL,
    taken_by    TEXT,
    taken_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (date, session, year_group, form_group)
);
CREATE TABLE IF NOT EXISTS lesson_registers (
    register_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    lesson_id   INTEGER REFERENCES timetable_lessons (lesson_id) ON DELETE SET NULL,
    group_id    INTEGER NOT NULL REFERENCES teaching_groups (group_id) ON DELETE CASCADE,
    period      INTEGER NOT NULL,
    session     TEXT NOT NULL CHECK (session IN ('AM', 'PM')),
    taken_by    TEXT,
    taken_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (date, group_id, period)
);
CREATE TABLE IF NOT EXISTS lesson_marks (
    register_id  INTEGER NOT NULL REFERENCES lesson_registers (register_id) ON DELETE CASCADE,
    pupil_id     INTEGER NOT NULL REFERENCES pupils (pupil_id),
    mark         TEXT NOT NULL CHECK (mark IN ('P', 'L', 'A', 'X')),
    minutes_late INTEGER,
    notes        TEXT,
    PRIMARY KEY (register_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_lesson_marks_pupil ON lesson_marks (pupil_id);
CREATE TABLE IF NOT EXISTS attendance_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS attendance_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id  INTEGER,
    date      TEXT,
    session   TEXT,
    action    TEXT NOT NULL CHECK (action IN ('mark', 'change', 'delete', 'register',
                                              'lesson_register', 'settings')),
    old_code  TEXT,
    new_code  TEXT,
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_attendance_audit_pupil ON attendance_audit (pupil_id, date);
"""

database.register_schema("attendance", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


# ── Records ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Mark:
    mark_id: int
    pupil_id: int
    date: str
    session: str
    code: str
    minutes_late: int | None
    notes: str | None
    recorded_at: str
    recorded_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def label(self) -> str:
        return code_label(self.code)

    @property
    def category(self) -> str:
        return category_of(self.code)


@dataclass(frozen=True)
class RegisterRow:
    pupil: P.Pupil
    mark: Mark | None


@dataclass(frozen=True)
class RegisterStatus:
    year_group: int
    form_group: str
    on_roll: int
    marked: int
    taken_by: str | None
    taken_at: str | None

    @property
    def complete(self) -> bool:
        return self.on_roll > 0 and self.marked >= self.on_roll


@dataclass(frozen=True)
class Summary:
    possible: int = 0
    present: int = 0        # / \ L
    aea: int = 0            # approved off-site education
    authorised: int = 0
    unauthorised: int = 0
    not_counted: int = 0
    late: int = 0           # L and U
    unmarked: int = 0       # school days on roll with no mark yet

    @property
    def attended(self) -> int:
        return self.present + self.aea

    @property
    def absent(self) -> int:
        return self.authorised + self.unauthorised

    @property
    def attendance_pct(self) -> float | None:
        return round(100.0 * self.attended / self.possible, 1) if self.possible else None

    @property
    def absence_pct(self) -> float | None:
        return round(100.0 * self.absent / self.possible, 1) if self.possible else None

    @property
    def band(self) -> str:
        """'severe', 'persistent' or '' (DfE measures, by absence %)."""
        a = self.absence_pct
        if a is None:
            return ""
        return "severe" if a >= SEVERE_ABSENCE else ("persistent" if a >= PERSISTENT_ABSENCE
                                                     else "")


@dataclass(frozen=True)
class LessonRow:
    pupil: P.Pupil
    mark: str | None
    minutes_late: int | None
    notes: str | None
    session_code: str | None   # the pupil's AM/PM code that day, if any

    @property
    def suggested(self) -> str:
        """What to pre-fill: the saved mark; else from the session register - X for a
        known absence or off-site activity, A for an unexplained absence, L for a
        pupil who arrived after the register closed; else P."""
        if self.mark:
            return self.mark
        code = self.session_code
        if code == "U":
            return "L"
        cat = category_of(code) if code else ""
        if cat in (AEA, AUTHORISED, NOT_COUNTED):
            return "X"
        return "A" if cat == UNAUTHORISED else "P"


@dataclass(frozen=True)
class LessonRegister:
    lesson: TT.Lesson
    date: str
    session: str
    rows: list[LessonRow]
    taken_by: str | None
    taken_at: str | None


def code_label(code: str) -> str:
    return CODES.get(code, (code, ""))[0]


def category_of(code: str) -> str:
    return CODES.get(code, ("", ""))[1]


# ── Helpers ──────────────────────────────────────────────────────────

def _row(r) -> Mark:
    return Mark(**{k: r[k] for k in Mark.__dataclass_fields__})


def _is_editor(actor: Principal) -> bool:
    return actor.role in ATTENDANCE_EDITORS


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.is_staff:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only school staff can take registers.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not _is_editor(actor):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Only the attendance office can do this.")


def _audit(conn, action: str, actor: Principal, *, pupil_id: int | None = None,
           date: str | None = None, session: str | None = None, old: str | None = None,
           new: str | None = None, detail: dict | None = None) -> None:
    conn.execute("INSERT INTO attendance_audit (pupil_id, date, session, action, old_code, "
                 "new_code, actor, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (pupil_id, date, session, action, old, new, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def _date(value: Any, problems: list[str] | None = None) -> _dt.date | None:
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value or "").strip())
    except ValueError:
        msg = "Date must be YYYY-MM-DD"
        if problems is None:
            raise ValidationError([msg]) from None
        problems.append(msg)
        return None


def _session(value: Any) -> str:
    s = str(value or "").strip().upper()
    if s not in SESSIONS:
        raise ValidationError(["Session must be AM or PM"])
    return s


def clean_code(value: Any, session: str) -> str:
    """Normalise a typed code: upper-case, and ``/`` or ``\\`` to the right session."""
    code = str(value or "").strip().upper()
    if code in ("/", "\\"):
        code = "/" if session == "AM" else "\\"
    if code not in CODES:
        raise ValidationError([f"'{value}' is not an attendance code"])
    return code


def school_day(day: _dt.date) -> tuple[bool, str]:
    """(is it a school day, what kind of day). No calendar: weekdays."""
    info = AY.day_info(day)
    if info.year is None:
        return day.weekday() < 5, ("Weekend" if day.weekday() >= 5
                                   else "No academic calendar recorded")
    return info.is_school_day, info.label


def school_days(start: _dt.date, end: _dt.date) -> list[_dt.date]:
    """School days from *start* to *end* inclusive (calendar, else weekdays)."""
    out: list[_dt.date] = []
    d = _dt.date(start.year, start.month, 1)
    while d <= end:
        for day, info in AY.month_info(d.year, d.month).items():
            if start <= day <= end and (info.is_school_day if info.year is not None
                                        else day.weekday() < 5):
                out.append(day)
        d = _dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def _on_roll(p: P.Pupil, day: str) -> bool:
    return p.admission_date <= day and (p.leaving_date is None or day <= p.leaving_date)


def _check_day(day: _dt.date, problems: list[str]) -> None:
    if day > _today():
        problems.append("Registers can't be marked for a future date")
        return
    ok, label = school_day(day)
    if not ok:
        problems.append(f"{day:%a %d %b %Y} isn't a school day ({label})")


def _minutes(value: Any, problems: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        n = -1
    if not 0 <= n <= 300:
        problems.append("Minutes late must be from 0 to 300")
        return None
    return n


def _existing(conn, pupil_id: int, day: str, session: str):
    return conn.execute("SELECT * FROM attendance_marks WHERE pupil_id = ? AND date = ? AND "
                        "session = ?", (pupil_id, day, session)).fetchone()


# ── Settings ─────────────────────────────────────────────────────────

def session_times() -> dict[str, str]:
    out = dict(DEFAULT_TIMES)
    with database.connect() as conn:
        for r in conn.execute("SELECT key, value FROM attendance_settings"):
            if r["key"] in out and r["value"]:
                out[r["key"]] = r["value"]
    return out


def set_session_times(times: dict[str, Any], *, actor: Principal) -> dict[str, str]:
    """Set when each session starts and its register closes (HH:MM)."""
    _require_editor(actor, "attendance.settings")
    new = session_times()
    problems: list[str] = []
    for key in DEFAULT_TIMES:
        if key in times and times[key] not in (None, ""):
            v = str(times[key]).strip()
            if not _TIME_RE.match(v):
                problems.append(f"{key.replace('_', ' ').title()}: times must be HH:MM")
            new[key] = v
    if not problems:
        if not new["am_start"] < new["am_close"] < new["pm_start"] < new["pm_close"]:
            problems.append("Times must run in order: AM start, AM register closes, "
                            "PM start, PM register closes")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for k, v in new.items():
            conn.execute("INSERT INTO attendance_settings (key, value) VALUES (?, ?) "
                         "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (k, v))
        _audit(conn, "settings", actor, detail=new)
    activity_log.record("attendance.settings", principal=actor)
    return new


def session_for_period(period: int) -> str:
    """AM or PM for a timetable period, by its start time."""
    p = next((x for x in TT.periods() if x.period == period), None)
    return "PM" if p and p.start_time >= session_times()["pm_start"] else "AM"


# ── Reading the session register ─────────────────────────────────────

def get(mark_id: int) -> Mark:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM attendance_marks WHERE mark_id = ?",
                         (int(mark_id),)).fetchone()
    if r is None:
        raise NotFound(f"No attendance mark #{mark_id}")
    return _row(r)


def get_for(pupil_id: int, day: Any, session: str) -> Mark | None:
    d = _date(day)
    with database.connect() as conn:
        r = _existing(conn, int(pupil_id), d.isoformat(), _session(session))
    return _row(r) if r else None


def list_for_date(day: Any, session: str | None = None) -> list[Mark]:
    d = _date(day)
    sql, params = "SELECT * FROM attendance_marks WHERE date = ?", [d.isoformat()]
    if session:
        sql += " AND session = ?"
        params.append(_session(session))
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql + " ORDER BY pupil_id, session", params)]


def register(day: Any, session: str, *, year_group: int | None = None,
             form: str | None = None) -> list[RegisterRow]:
    """Pupils on roll that day (optionally one year / form) with their mark."""
    d = _date(day).isoformat()
    s = _session(session)
    pupils = [p for p in P.list_pupils(year_group=year_group, form_group=form or None,
                                       roll_status=None) if _on_roll(p, d)]
    marks = {m.pupil_id: m for m in list_for_date(d, s)}
    return [RegisterRow(p, marks.get(p.pupil_id)) for p in pupils]


def register_status(day: Any, session: str) -> list[RegisterStatus]:
    """Every form with pupils that day: how many are marked and who took it."""
    d = _date(day).isoformat()
    s = _session(session)
    on_roll: Counter = Counter()
    marked: Counter = Counter()
    marks = {m.pupil_id for m in list_for_date(d, s)}
    for p in P.list_pupils(roll_status=None):
        if _on_roll(p, d):
            key = (p.year_group, (p.form_group or "").upper())
            on_roll[key] += 1
            marked[key] += p.pupil_id in marks
    for f in FG.list_forms():
        on_roll.setdefault((f.year_group, f.name.upper()), 0)
    with database.connect() as conn:
        taken = {(r["year_group"], r["form_group"].upper()): (r["taken_by"], r["taken_at"])
                 for r in conn.execute("SELECT * FROM attendance_registers WHERE date = ? "
                                       "AND session = ?", (d, s))}
    return [RegisterStatus(y, f, n, marked[(y, f)], *taken.get((y, f), (None, None)))
            for (y, f), n in sorted(on_roll.items())]


def pupil_history(pupil_id: int, start: Any = None, end: Any = None) -> list[Mark]:
    sql, params = "SELECT * FROM attendance_marks WHERE pupil_id = ?", [int(pupil_id)]
    if start:
        sql += " AND date >= ?"
        params.append(_date(start).isoformat())
    if end:
        sql += " AND date <= ?"
        params.append(_date(end).isoformat())
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql + " ORDER BY date DESC, session DESC",
                                              params)]


def history(pupil_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Changes to marks (old and new code, who, when), newest first."""
    sql, params = "SELECT * FROM attendance_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?", (*params, limit))
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "pupil_id": r["pupil_id"], "date": r["date"], "session": r["session"],
                 "old": r["old_code"], "new": r["new_code"],
                 "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


# ── Figures ──────────────────────────────────────────────────────────

def _year_bounds(start: Any, end: Any) -> tuple[_dt.date, _dt.date]:
    s = _date(start) if start else P.academic_year_start(_today())
    e = _date(end) if end else _today()
    if e < s:
        raise ValidationError(["The end date is before the start date"])
    return s, min(e, _today())


def _summarise(marks: Iterable[Mark], expected: int) -> Summary:
    c: Counter = Counter()
    n = 0
    for m in marks:
        n += 1
        c[m.category] += 1
        if m.code in ("L", "U"):
            c["late"] += 1
    possible = n - c[NOT_COUNTED]
    return Summary(possible=possible, present=c[PRESENT], aea=c[AEA],
                   authorised=c[AUTHORISED], unauthorised=c[UNAUTHORISED],
                   not_counted=c[NOT_COUNTED], late=c["late"],
                   unmarked=max(0, expected - n))


def _expected(p: P.Pupil, days: list[_dt.date]) -> int:
    return 2 * sum(1 for d in days if _on_roll(p, d.isoformat()))


def pupil_summary(pupil_id: int, start: Any = None, end: Any = None) -> Summary:
    """One pupil's figures, this academic year to date unless dates are given."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    s, e = _year_bounds(start, end)
    return _summarise(pupil_history(p.pupil_id, s, e), _expected(p, school_days(s, e)))


def summaries(start: Any = None, end: Any = None, *, year_group: int | None = None,
              form: str | None = None) -> list[tuple[P.Pupil, Summary]]:
    """Figures for every pupil on roll today (filtered), lowest attendance first."""
    s, e = _year_bounds(start, end)
    days = school_days(s, e)
    pupils = P.list_pupils(year_group=year_group, form_group=form or None)
    by: dict[int, list[Mark]] = {}
    with database.connect() as conn:
        for r in conn.execute("SELECT * FROM attendance_marks WHERE date BETWEEN ? AND ?",
                              (s.isoformat(), e.isoformat())):
            by.setdefault(r["pupil_id"], []).append(_row(r))
    out = [(p, _summarise(by.get(p.pupil_id, []), _expected(p, days))) for p in pupils]
    return sorted(out, key=lambda t: (t[1].attendance_pct is None,
                                      t[1].attendance_pct or 0, t[0].legal_last_name.lower()))


def persistent_absentees(start: Any = None, end: Any = None, **filters: Any
                         ) -> list[tuple[P.Pupil, Summary]]:
    return [t for t in summaries(start, end, **filters) if t[1].band]


def daily_summary(day: Any) -> dict[str, dict[str, Any]]:
    """Per session: counts by code and by category, and how many are unmarked."""
    d = _date(day).isoformat()
    roll = sum(1 for p in P.list_pupils(roll_status=None) if _on_roll(p, d))
    out: dict[str, dict[str, Any]] = {}
    for s in SESSIONS:
        marks = list_for_date(d, s)
        by_cat = Counter(m.category for m in marks)
        out[s] = {"on_roll": roll, "marked": len(marks), "unmarked": max(0, roll - len(marks)),
                  "codes": dict(Counter(m.code for m in marks)),
                  **{k: by_cat[k] for k in CATEGORY_LABELS}}
    return out


def calling_list(day: Any, session: str = "AM") -> list[tuple[P.Pupil, Mark, list]]:
    """Pupils with N (no reason yet) for the session, with contacts to ring (priority order)."""
    d = _date(day).isoformat()
    s = _session(session)
    out = []
    for m in list_for_date(d, s):
        if m.code == "N":
            p = P.get_pupil(m.pupil_id)
            if p is not None:
                out.append((p, m, sorted(C.list_for_pupil(p.pupil_id),
                                         key=lambda c: c.priority)))
    return sorted(out, key=lambda t: (t[0].year_group, t[0].legal_last_name.lower()))


# ── Changing the session register ────────────────────────────────────

def _write(conn, p: P.Pupil, day: str, session: str, code: str, actor: Principal, *,
           notes: str | None, minutes_late: int | None, keep_reasons: bool) -> str:
    """Insert or change one mark. Returns 'new', 'changed', 'same' or 'kept'."""
    old = _existing(conn, p.pupil_id, day, session)
    if old is not None:
        if keep_reasons and old["code"] not in TEACHER_CODES:
            return "kept"
        if (old["code"], old["notes"], old["minutes_late"]) == (code, notes, minutes_late):
            return "same"
        conn.execute("UPDATE attendance_marks SET code = ?, notes = ?, minutes_late = ?, "
                     "updated_at = datetime('now'), updated_by = ? WHERE mark_id = ?",
                     (code, notes, minutes_late, actor.username, old["mark_id"]))
        _audit(conn, "change", actor, pupil_id=p.pupil_id, date=day, session=session,
               old=old["code"], new=code)
        return "changed"
    conn.execute("INSERT INTO attendance_marks (pupil_id, date, session, code, minutes_late, "
                 "notes, recorded_by, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (p.pupil_id, day, session, code, minutes_late, notes, actor.username,
                  actor.username))
    _audit(conn, "mark", actor, pupil_id=p.pupil_id, date=day, session=session, new=code)
    return "new"


def _may_mark(actor: Principal, day: _dt.date, code: str, problems: list[str]) -> None:
    if _is_editor(actor):
        return
    if day != _today():
        problems.append("Only the attendance office can mark or change a past register")
    if code not in TEACHER_CODES:
        problems.append(f"Only the attendance office can enter '{code}' "
                        "(staff use / present, L late, N absent)")


def record_mark(pupil_id: int, day: Any, session: str, code: str, *, actor: Principal,
                notes: str | None = None, minutes_late: Any = None) -> Mark:
    """Set one pupil's mark for a session (insert or change, keeping the old one in the audit)."""
    _require_staff(actor, "attendance.mark", f"id:{pupil_id}")
    problems: list[str] = []
    d = _date(day, problems)
    s = _session(session)
    try:
        c = clean_code(code, s)
    except ValidationError as e:
        problems.extend(e.problems)
        c = ""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    if d is not None:
        _check_day(d, problems)
        if not _on_roll(p, d.isoformat()):
            problems.append(f"{p.admission_no} wasn't on roll on {d.isoformat()}")
        if c:
            _may_mark(actor, d, c, problems)
    mins = _minutes(minutes_late, problems)
    if problems:
        activity_log.record("attendance.mark", target=f"id:{pupil_id}", outcome="invalid",
                            principal=actor)
        raise ValidationError(problems)
    with database.connect() as conn:
        if not _is_editor(actor):
            old = _existing(conn, p.pupil_id, d.isoformat(), s)
            if old is not None and old["code"] not in TEACHER_CODES:
                raise ValidationError([f"The office has already recorded '{old['code']}' "
                                       f"({code_label(old['code'])}) - ask them to change it"])
        what = _write(conn, p, d.isoformat(), s, c, actor, notes=P._clean_text(notes, 500),
                      minutes_late=mins, keep_reasons=False)
    activity_log.record("attendance.mark", target=f"id:{p.pupil_id}", principal=actor,
                        session=s, code=c, result=what)
    return get_for(p.pupil_id, d, s)  # type: ignore[return-value]


def save_register(day: Any, session: str, marks: dict[int, Any], *, actor: Principal,
                  year_group: int | None = None, form: str | None = None
                  ) -> tuple[int, list[str]]:
    """Save a register: *marks* maps pupil_id -> code, or (code, notes, minutes_late).

    Pupils are checked one by one (a bad row doesn't stop the rest). Staff never
    overwrite a reason the office has entered - those rows are kept and reported.
    When a form's register is complete it is recorded as taken.
    Returns (marks saved or changed, notes about rows not saved).
    """
    _require_staff(actor, "attendance.register")
    problems: list[str] = []
    d = _date(day, problems)
    s = _session(session)
    if d is not None:
        _check_day(d, problems)
        if not _is_editor(actor) and d != _today():
            problems.append("Only the attendance office can mark or change a past register")
    if problems:
        raise ValidationError(problems)
    iso = d.isoformat()
    saved, notes_out = 0, []
    with database.connect() as conn:
        for pid, value in marks.items():
            code, note, mins = (list(value) + [None, None])[:3] if isinstance(
                value, (tuple, list)) else (value, None, None)
            p = P.get_pupil(int(pid))
            if p is None:
                notes_out.append(f"#{pid}: no such pupil")
                continue
            if not code:
                continue
            row_problems: list[str] = []
            try:
                c = clean_code(code, s)
            except ValidationError as e:
                notes_out.append(f"{p.admission_no}: {e.problems[0]}")
                continue
            if not _on_roll(p, iso):
                row_problems.append("not on roll that day")
            if not _is_editor(actor) and c not in TEACHER_CODES:
                row_problems.append(f"only the office can enter '{c}'")
            m = _minutes(mins, row_problems)
            if row_problems:
                notes_out.append(f"{p.admission_no}: {'; '.join(row_problems)}")
                continue
            what = _write(conn, p, iso, s, c, actor, notes=P._clean_text(note, 500),
                          minutes_late=m, keep_reasons=not _is_editor(actor))
            if what == "kept":
                notes_out.append(f"{p.admission_no}: kept the office's "
                                 f"'{_existing(conn, p.pupil_id, iso, s)['code']}'")
            elif what in ("new", "changed"):
                saved += 1
        taken = _mark_taken(conn, iso, s, actor, year_group, form)
    activity_log.record("attendance.register", principal=actor, session=s, saved=saved,
                        skipped=len(notes_out), forms_taken=taken)
    return saved, notes_out


def _mark_taken(conn, day: str, session: str, actor: Principal, year_group: int | None,
                form: str | None) -> int:
    """Record each form (within the filter) whose register is now complete."""
    marked = {r[0] for r in conn.execute("SELECT pupil_id FROM attendance_marks WHERE "
                                         "date = ? AND session = ?", (day, session))}
    forms: dict[tuple[int, str], list[bool]] = {}
    for p in P.list_pupils(year_group=year_group, form_group=form or None, roll_status=None):
        if _on_roll(p, day) and p.form_group:
            forms.setdefault((p.year_group, p.form_group.upper()), []).append(
                p.pupil_id in marked)
    n = 0
    for (y, f), done in forms.items():
        if all(done):
            cur = conn.execute(
                "INSERT INTO attendance_registers (date, session, form_group, year_group, "
                "taken_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (day, session, f, y, actor.username))
            if cur.rowcount:
                _audit(conn, "register", actor, date=day, session=session,
                       detail={"year_group": y, "form": f})
                n += 1
    return n


def record_late(pupil_id: int, day: Any, session: str, arrived: str, *, actor: Principal,
                notes: str | None = None) -> Mark:
    """Sign a pupil in late: L up to the register closing time, U after it."""
    s = _session(session)
    a = str(arrived or "").strip()
    if not _TIME_RE.match(a):
        raise ValidationError(["Arrival time must be HH:MM"])
    t = session_times()
    start, close = (t["am_start"], t["am_close"]) if s == "AM" else (t["pm_start"],
                                                                      t["pm_close"])

    def mins(hhmm: str) -> int:
        return int(hhmm[:2]) * 60 + int(hhmm[3:])
    late = max(0, mins(a) - mins(start))
    code = "L" if a <= close else "U"
    if code == "U" and not _is_editor(actor):
        # U is an unauthorised absence: the office records it.
        raise ValidationError([f"Arrived after the register closed at {close} - the "
                               "attendance office records this as U"])
    return record_mark(pupil_id, day, s, code, actor=actor, notes=notes, minutes_late=late)


def record_range(pupil_id: int, start: Any, end: Any, code: str, *, actor: Principal,
                 sessions: Iterable[str] = SESSIONS, notes: str | None = None,
                 overwrite: bool = False) -> tuple[int, int]:
    """Office: one code over several days (illness, agreed leave, study leave...).

    Non-school days are skipped, and so are sessions that already have a mark
    other than N unless *overwrite*. Returns (saved, skipped).
    """
    _require_editor(actor, "attendance.range", f"id:{pupil_id}")
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    problems: list[str] = []
    s, e = _date(start, problems), _date(end, problems)
    if s and e and e < s:
        problems.append("The end date is before the start date")
    if e and e > _today():
        problems.append("Registers can't be marked for a future date")
    sess = [_session(x) for x in sessions]
    if not sess:
        problems.append("Choose AM, PM or both")
    try:
        for x in sess:
            clean_code(code, x)
    except ValidationError as err:
        problems.extend(err.problems)
    if s and e and not problems and (e - s).days > 200:
        problems.append("At most 200 days at a time")
    if problems:
        raise ValidationError(problems)
    saved = skipped = 0
    note = P._clean_text(notes, 500)
    with database.connect() as conn:
        for day in school_days(s, e):
            iso = day.isoformat()
            for x in sess:
                old = _existing(conn, p.pupil_id, iso, x)
                if not _on_roll(p, iso) or (old is not None and old["code"] != "N"
                                            and not overwrite):
                    skipped += 1
                    continue
                if _write(conn, p, iso, x, clean_code(code, x), actor, notes=note,
                          minutes_late=None, keep_reasons=False) in ("new", "changed"):
                    saved += 1
    activity_log.record("attendance.range", target=f"id:{p.pupil_id}", principal=actor,
                        code=code, saved=saved, skipped=skipped)
    return saved, skipped


def delete_mark(mark_id: int, *, actor: Principal, reason: str) -> Mark:
    """Office: remove a mark entered in error (kept in the audit with the reason)."""
    _require_editor(actor, "attendance.delete", f"mark:{mark_id}")
    m = get(mark_id)
    why = P._clean_text(reason, 300)
    if not why:
        raise ValidationError(["Give a reason for removing the mark"])
    with database.connect() as conn:
        conn.execute("DELETE FROM attendance_marks WHERE mark_id = ?", (m.mark_id,))
        _audit(conn, "delete", actor, pupil_id=m.pupil_id, date=m.date, session=m.session,
               old=m.code, detail={"reason": why})
    activity_log.record("attendance.delete", target=f"mark:{m.mark_id}", principal=actor)
    return m


# ── Lesson registers ─────────────────────────────────────────────────

def lessons_due(day: Any, *, teacher: str | None = None
                ) -> tuple[list[tuple[TT.Lesson, bool]], str]:
    """(lessons on *day* with whether their register is taken, what kind of day)."""
    d = _date(day)
    lessons, label = TT.lessons_on(d, **({"teacher": teacher} if teacher else {}))
    with database.connect() as conn:
        done = {(r["group_id"], r["period"]) for r in conn.execute(
            "SELECT group_id, period FROM lesson_registers WHERE date = ?", (d.isoformat(),))}
    return [(x, (x.group_id, x.period) in done) for x in lessons], label


def _lesson_on(lesson_id: int, d: _dt.date) -> TT.Lesson:
    x = TT.get(int(lesson_id))
    lessons, label = TT.lessons_on(d)
    if not any(y.lesson_id == x.lesson_id for y in lessons):
        raise ValidationError([f"{x.group_code} has no lesson in {x.slot_label} on "
                               f"{d:%a %d %b %Y} ({label})"])
    return x


def lesson_register(lesson_id: int, day: Any) -> LessonRegister:
    d = _date(day)
    x = _lesson_on(lesson_id, d)
    s = session_for_period(x.period)
    iso = d.isoformat()
    with database.connect() as conn:
        reg = conn.execute("SELECT * FROM lesson_registers WHERE date = ? AND group_id = ? "
                           "AND period = ?", (iso, x.group_id, x.period)).fetchone()
        saved = {r["pupil_id"]: r for r in conn.execute(
            "SELECT * FROM lesson_marks WHERE register_id = ?",
            (reg["register_id"] if reg else -1,))}
    session_codes = {m.pupil_id: m.code for m in list_for_date(iso, s)}
    rows = []
    for p in TG.members(x.group_id, include_left=True):
        if not _on_roll(p, iso):
            continue
        r = saved.get(p.pupil_id)
        rows.append(LessonRow(p, r["mark"] if r else None, r["minutes_late"] if r else None,
                              r["notes"] if r else None, session_codes.get(p.pupil_id)))
    return LessonRegister(x, iso, s, rows, reg["taken_by"] if reg else None,
                          reg["taken_at"] if reg else None)


def save_lesson_register(lesson_id: int, day: Any, marks: dict[int, Any], *,
                         actor: Principal) -> int:
    """Save a lesson register: pupil_id -> mark, or (mark, notes, minutes_late)."""
    _require_staff(actor, "attendance.lesson_register", f"L{lesson_id}")
    problems: list[str] = []
    d = _date(day, problems)
    if d is not None:
        if d > _today():
            problems.append("Registers can't be marked for a future date")
        elif not _is_editor(actor) and d != _today():
            problems.append("Only the attendance office can change a past lesson register")
    if problems:
        raise ValidationError(problems)
    reg = lesson_register(lesson_id, d)
    members = {r.pupil.pupil_id: r for r in reg.rows}
    clean: dict[int, tuple[str, str | None, int | None]] = {}
    for pid, value in marks.items():
        mark, note, mins = (list(value) + [None, None])[:3] if isinstance(
            value, (tuple, list)) else (value, None, None)
        row = members.get(int(pid))
        name = row.pupil.admission_no if row else f"#{pid}"
        if row is None:
            problems.append(f"{name} isn't in {reg.lesson.group_code}")
            continue
        m = str(mark or "").strip().upper()
        if m not in LESSON_MARKS:
            problems.append(f"{name}: mark must be P, L, A or X")
            continue
        clean[int(pid)] = (m, P._clean_text(note, 300), _minutes(mins, problems))
    if problems:
        raise ValidationError(problems)
    x = reg.lesson
    with database.connect() as conn:
        conn.execute("INSERT INTO lesson_registers (date, lesson_id, group_id, period, session, "
                     "taken_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (date, group_id, period) "
                     "DO UPDATE SET taken_by = excluded.taken_by, taken_at = datetime('now'), "
                     "lesson_id = excluded.lesson_id",
                     (reg.date, x.lesson_id, x.group_id, x.period, reg.session, actor.username))
        rid = conn.execute("SELECT register_id FROM lesson_registers WHERE date = ? AND "
                           "group_id = ? AND period = ?",
                           (reg.date, x.group_id, x.period)).fetchone()[0]
        for pid, (m, note, mins) in clean.items():
            conn.execute("INSERT INTO lesson_marks (register_id, pupil_id, mark, minutes_late, "
                         "notes) VALUES (?, ?, ?, ?, ?) ON CONFLICT (register_id, pupil_id) "
                         "DO UPDATE SET mark = excluded.mark, minutes_late = "
                         "excluded.minutes_late, notes = excluded.notes",
                         (rid, pid, m, mins, note))
        _audit(conn, "lesson_register", actor, date=reg.date, session=reg.session,
               detail={"lesson_id": x.lesson_id, "group_id": x.group_id, "marks": len(clean),
                       "absent": sum(1 for v in clean.values() if v[0] == "A")})
    activity_log.record("attendance.lesson_register", target=f"L{x.lesson_id}",
                        principal=actor, marks=len(clean))
    return len(clean)


def missing_from_lessons(day: Any) -> list[tuple[P.Pupil, TT.Lesson, str]]:
    """Pupils marked absent (A) in a lesson while present for that session -
    (pupil, lesson, their session code)."""
    d = _date(day).isoformat()
    codes = {(m.pupil_id, m.session): m.code for m in list_for_date(d)}
    out = []
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT r.lesson_id, r.session, m.pupil_id FROM lesson_marks m JOIN "
            "lesson_registers r USING (register_id) WHERE r.date = ? AND m.mark = 'A' "
            "AND r.lesson_id IS NOT NULL ORDER BY r.period", (d,)).fetchall()
    for r in rows:
        code = codes.get((r["pupil_id"], r["session"]))
        if code and category_of(code) == PRESENT:
            p = P.get_pupil(r["pupil_id"])
            if p is not None:
                out.append((p, TT.get(r["lesson_id"]), code))
    return out


def lesson_summary(pupil_id: int, start: Any = None, end: Any = None) -> dict[str, int]:
    """Lesson marks for a pupil over a period: counts of P, L, A, X."""
    s, e = _year_bounds(start, end)
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT m.mark, COUNT(*) FROM lesson_marks m JOIN lesson_registers r "
            "USING (register_id) WHERE m.pupil_id = ? AND r.date BETWEEN ? AND ? "
            "GROUP BY m.mark", (int(pupil_id), s.isoformat(), e.isoformat())).fetchall()
    out = {k: 0 for k in LESSON_MARKS}
    out.update({r[0]: r[1] for r in rows})
    return out


# ── Export ───────────────────────────────────────────────────────────

def export_summaries(path: str | Path, rows: list[tuple[P.Pupil, Summary]], *,
                     actor: Principal) -> int:
    """Write attendance figures to CSV (spreadsheet formulas escaped)."""
    _require_staff(actor, "attendance.export")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Surname", "First name", "Year", "Form", "Possible",
                    "Attended", "Authorised", "Unauthorised", "Late", "Not counted",
                    "Unmarked", "Attendance %", "Absence %", "Band"])
        for p, s in rows:
            w.writerow([_safe(v) for v in (
                p.admission_no, p.legal_last_name, p.preferred_name or p.legal_first_name,
                p.year_group, p.form_group, s.possible, s.attended, s.authorised,
                s.unauthorised, s.late, s.not_counted, s.unmarked, s.attendance_pct,
                s.absence_pct, s.band)])
    activity_log.record("attendance.export", principal=actor, rows=len(rows))
    return len(rows)
