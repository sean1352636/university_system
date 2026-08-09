"""Non-lesson registers for Sixth Form Attendance.

Sibling to :mod:`attendance`. A sixth-former's week is not made of
lessons alone. Tutorial, assembly, enrichment, EPQ supervision,
intervention sessions, and — the one that defines the phase — supervised
private study, where a learner with a free period is expected to be in
the study centre and frequently is not.

None of that fits :mod:`attendance`, whose every row hangs off a
timetable slot belonging to a class group. An enrichment club draws
eleven learners from six different groups; a tutorial roster is a tutor
group, not a teaching one. Forcing them into the timetable would mean
inventing fake class groups, and then every attendance percentage in the
college would quietly include the choir.

So activities get their own roster and their own marks, sharing the mark
codes in :mod:`attendance_codes` so the vocabulary stays one vocabulary.
Two flags carry the meaning that matters:

* ``required`` — whether missing it counts. Assembly usually does;
  a voluntary badminton club does not, and reporting a learner as 62%
  attender because they stopped going to badminton helps nobody.
* ``week`` — which half of an A/B cycle it runs in, so a fortnightly
  tutorial does not appear to be missed every other Tuesday.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_weeks as weeks,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

KINDS: tuple[str, ...] = (
    "Tutorial",
    "Assembly",
    "Enrichment",
    "EPQ supervision",
    "Supervised study",
    "Intervention",
    "Sport",
    "Careers",
    "Other",
)
DEFAULT_KIND: str = "Other"

# Kinds a college would normally expect everyone on the roster to
# attend. Used only as the default for `required` at creation time —
# every activity can override it.
NORMALLY_REQUIRED: frozenset[str] = frozenset({
    "Tutorial", "Assembly", "EPQ supervision", "Supervised study",
    "Intervention",
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'Other',
    day         INTEGER,
    period      INTEGER,
    start_time  TEXT,
    end_time    TEXT,
    room        TEXT,
    staff       TEXT,
    week        TEXT NOT NULL DEFAULT 'Both',
    start_date  TEXT,
    end_date    TEXT,
    required    INTEGER NOT NULL DEFAULT 1,
    active      INTEGER NOT NULL DEFAULT 1,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS attendance_activity_members (
    activity_id INTEGER NOT NULL,
    student_id  TEXT NOT NULL,
    joined_on   TEXT,
    left_on     TEXT,
    PRIMARY KEY (activity_id, student_id),
    FOREIGN KEY (activity_id) REFERENCES attendance_activities(activity_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_activity_marks (
    mark_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id  INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    code         TEXT NOT NULL,
    status       TEXT NOT NULL,
    minutes_late INTEGER,
    notes        TEXT,
    recorded_by  TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(activity_id, student_id, date),
    FOREIGN KEY (activity_id) REFERENCES attendance_activities(activity_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_act_marks_date
    ON attendance_activity_marks(date);
CREATE INDEX IF NOT EXISTS idx_att_act_marks_student
    ON attendance_activity_marks(student_id, date);
CREATE INDEX IF NOT EXISTS idx_att_act_members_student
    ON attendance_activity_members(student_id);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Activity:
    """Something on the roster that is not a lesson."""

    activity_id: int
    name: str
    kind: str
    day: int | None
    period: int | None
    start_time: str | None
    end_time: str | None
    room: str | None
    staff: str | None
    week: str
    start_date: str | None
    end_date: str | None
    required: bool
    active: bool
    notes: str | None
    created_at: str | None

    @property
    def is_recurring(self) -> bool:
        """Whether this has a weekly slot, as opposed to being ad hoc."""
        return self.day is not None

    @property
    def label(self) -> str:
        from education_system.systems.sixth_form.domain.academics.timetable import (
            timetable as _tt,
        )
        when = (f"{_tt.day_name(self.day)}"
                + (f" P{self.period}" if self.period else "")
                if self.day else "ad hoc")
        week = "" if self.week == weeks.BOTH else f" (week {self.week})"
        return f"{self.name} — {self.kind}, {when}{week}"


@dataclass
class ActivityMark:
    """One learner's mark for one activity on one date."""

    mark_id: int
    activity_id: int
    student_id: str
    date: str
    code: str
    status: str
    minutes_late: int | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str | None

    @property
    def attending(self) -> bool:
        return codes.counts_as_present(self.code)

    @property
    def possible(self) -> bool:
        return codes.counts_toward_possible(self.code)


@dataclass
class ActivityEntry:
    """One row of a fillable activity register."""

    student_id: str
    full_name: str
    mark: ActivityMark | None


@dataclass
class ActivitySummary:
    """Attendance at one activity, or one learner's across all of them."""

    sessions: int = 0
    attending: int = 0
    authorised: int = 0
    unauthorised: int = 0
    not_counted: int = 0

    @property
    def possible(self) -> int:
        return max(0, self.sessions - self.not_counted)

    @property
    def percentage(self) -> float | None:
        if self.possible == 0:
            return None
        return round(100.0 * self.attending / self.possible, 1)


@dataclass
class MissingActivityRegister:
    """An activity that met on a date with nobody marked."""

    activity: Activity
    date: str
    marked: int
    expected: int


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
    # Marks share the code vocabulary; members FK onto students.
    codes.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Activity schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=r["activity_id"],
        name=r["name"],
        kind=r["kind"],
        day=r["day"],
        period=r["period"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        room=r["room"],
        staff=r["staff"],
        week=r["week"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        required=bool(r["required"]),
        active=bool(r["active"]),
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _mark_row(r: sqlite3.Row) -> ActivityMark:
    return ActivityMark(
        mark_id=r["mark_id"],
        activity_id=r["activity_id"],
        student_id=r["student_id"],
        date=r["date"],
        code=r["code"],
        status=r["status"],
        minutes_late=r["minutes_late"],
        notes=r["notes"],
        recorded_by=r["recorded_by"],
        recorded_at=r["recorded_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return DEFAULT_KIND
    for kind in KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")


def _validate_payload(data: dict[str, Any], *,
                      partial: bool = False) -> dict[str, Any]:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    out: dict[str, Any] = {}

    if "name" in data or not partial:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValidationError("Activity name is required")
        if len(name) > 100:
            raise ValidationError("Name must be 100 characters or fewer")
        out["name"] = name

    if "kind" in data or not partial:
        out["kind"] = validate_kind(data.get("kind"))

    if "day" in data or not partial:
        day = data.get("day")
        if day in (None, ""):
            out["day"] = None
        else:
            try:
                day = int(day)
            except (TypeError, ValueError):
                raise ValidationError("Day must be a number 1–5") from None
            if day not in _tt.DAY_NUMBERS:
                raise ValidationError("Day must be 1 (Mon) to 5 (Fri)")
            out["day"] = day

    if "period" in data or not partial:
        period = data.get("period")
        if period in (None, ""):
            out["period"] = None
        else:
            try:
                period = int(period)
            except (TypeError, ValueError):
                raise ValidationError("Period must be a number") from None
            if period not in _tt.PERIODS:
                raise ValidationError(
                    f"Period must be one of: "
                    f"{', '.join(str(p) for p in _tt.PERIODS)}")
            out["period"] = period

    for field_name in ("start_time", "end_time"):
        if field_name in data or not partial:
            value = data.get(field_name)
            out[field_name] = (
                _validate_time(value, field_name.replace("_", " ").title())
                if value else None)

    for field_name in ("room", "staff", "notes"):
        if field_name in data or not partial:
            value = data.get(field_name)
            text = (value or "").strip() if isinstance(value, str) else ""
            out[field_name] = text or None

    if "week" in data or not partial:
        out["week"] = weeks.validate_week(data.get("week") or weeks.BOTH)

    for field_name in ("start_date", "end_date"):
        if field_name in data or not partial:
            value = data.get(field_name)
            out[field_name] = core._validate_date(value) if value else None
    if out.get("start_date") and out.get("end_date") and \
            out["end_date"] < out["start_date"]:
        raise ValidationError("End date must be on or after the start date")

    if "required" in data:
        out["required"] = 1 if data.get("required") else 0
    elif not partial:
        out["required"] = 1 if out.get("kind") in NORMALLY_REQUIRED else 0

    if "active" in data:
        out["active"] = 1 if data.get("active") else 0
    elif not partial:
        out["active"] = 1
    return out


def _validate_time(value: Any, label: str) -> str:
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_register as _reg,
    )
    return _reg._validate_time(value, label)


# ── Activity CRUD ───────────────────────────────────────────────────

def create_activity(data: dict[str, Any]) -> Activity:
    """Set up a tutorial, club, assembly or study session."""
    init_db()
    payload = _validate_payload(data)
    with _connect() as conn:
        clash = conn.execute(
            "SELECT activity_id FROM attendance_activities WHERE name = ?",
            (payload["name"],)).fetchone()
        if clash:
            raise ValidationError(
                f"An activity called {payload['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO attendance_activities
                   (name, kind, day, period, start_time, end_time, room,
                    staff, week, start_date, end_date, required, active, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload["name"], payload["kind"], payload["day"],
             payload["period"], payload["start_time"], payload["end_time"],
             payload["room"], payload["staff"], payload["week"],
             payload["start_date"], payload["end_date"], payload["required"],
             payload["active"], payload["notes"]))
        conn.commit()
        activity_id = int(cur.lastrowid or 0)
    logger.info("Created activity #%d: %s", activity_id, payload["name"])
    out = get_activity(activity_id)
    assert out is not None
    return out


def get_activity(activity_id: int) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_activities WHERE activity_id = ?",
            (activity_id,)).fetchone()
    return _row(r) if r else None


def list_activities(*, kind: str | None = None, day: int | None = None,
                    active_only: bool = True,
                    required_only: bool = False) -> list[Activity]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if required_only:
        clauses.append("required = 1")
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if day is not None:
        clauses.append("day = ?")
        args.append(day)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_activities {where} "
            "ORDER BY kind, name", args).fetchall()
    return [_row(r) for r in rows]


def update_activity(activity_id: int, data: dict[str, Any]) -> Activity:
    init_db()
    existing = get_activity(activity_id)
    if existing is None:
        raise ValidationError(f"No activity with id {activity_id}")
    payload = _validate_payload(data, partial=True)
    if not payload:
        return existing
    sets = ", ".join(f"{k} = ?" for k in payload)
    with _connect() as conn:
        conn.execute(
            f"UPDATE attendance_activities SET {sets} WHERE activity_id = ?",
            (*payload.values(), activity_id))
        conn.commit()
    out = get_activity(activity_id)
    assert out is not None
    return out


def archive_activity(activity_id: int) -> Activity:
    """Stop an activity running without losing its history."""
    return update_activity(activity_id, {"active": False})


def delete_activity(activity_id: int) -> bool:
    """Remove an activity and every mark against it.

    Prefer :func:`archive_activity` for anything that ever ran — the
    marks are attendance evidence.
    """
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_activities WHERE activity_id = ?",
            (activity_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Roster ──────────────────────────────────────────────────────────

def add_member(activity_id: int, student_id: str, *,
               joined_on: str | None = None) -> bool:
    init_db()
    if get_activity(activity_id) is None:
        raise ValidationError(f"No activity with id {activity_id}")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_activity_members
                   (activity_id, student_id, joined_on)
               VALUES (?, ?, ?)
               ON CONFLICT(activity_id, student_id) DO UPDATE SET
                   left_on = NULL,
                   joined_on = COALESCE(excluded.joined_on,
                                        attendance_activity_members.joined_on)""",
            (activity_id, student_id.strip(),
             core._validate_date(joined_on) if joined_on else None))
        conn.commit()
    return bool(cur.rowcount)


def remove_member(activity_id: int, student_id: str, *,
                  left_on: str | None = None,
                  hard: bool = False) -> bool:
    """Take a learner off the roster.

    By default this dates them out rather than deleting them, so their
    marks up to that point still make sense.
    """
    init_db()
    with _connect() as conn:
        if hard:
            cur = conn.execute(
                "DELETE FROM attendance_activity_members "
                "WHERE activity_id = ? AND student_id = ?",
                (activity_id, student_id.strip()))
        else:
            cur = conn.execute(
                "UPDATE attendance_activity_members SET left_on = ? "
                "WHERE activity_id = ? AND student_id = ?",
                (core._validate_date(left_on) if left_on
                 else _dt.date.today().isoformat(),
                 activity_id, student_id.strip()))
        conn.commit()
    return bool(cur.rowcount)


def list_members(activity_id: int, *, on: str | None = None) -> list[str]:
    """Who is on the roster, optionally as at a date."""
    init_db()
    when = core._validate_date(on) if on else None
    with _connect() as conn:
        rows = conn.execute(
            "SELECT student_id, joined_on, left_on "
            "FROM attendance_activity_members WHERE activity_id = ? "
            "ORDER BY student_id", (activity_id,)).fetchall()
    out: list[str] = []
    for r in rows:
        if when:
            if r["joined_on"] and r["joined_on"] > when:
                continue
            if r["left_on"] and r["left_on"] < when:
                continue
        elif r["left_on"]:
            continue
        out.append(r["student_id"])
    return out


def count_members(activity_id: int, *, on: str | None = None) -> int:
    return len(list_members(activity_id, on=on))


def activities_for_student(student_id: str, *,
                           active_only: bool = True) -> list[Activity]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.* FROM attendance_activities a
               JOIN attendance_activity_members m
                 ON m.activity_id = a.activity_id
              WHERE m.student_id = ? AND m.left_on IS NULL
              ORDER BY a.kind, a.name""",
            (student_id.strip(),)).fetchall()
    out = [_row(r) for r in rows]
    return [a for a in out if a.active] if active_only else out


def enrol_class_group(activity_id: int, group_id: int) -> int:
    """Put a whole teaching group on an activity roster."""
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    members = _cg.list_members(group_id)
    if not members:
        raise ValidationError(f"Class group #{group_id} has no members")
    for sid in members:
        add_member(activity_id, sid)
    return len(members)


# ── Does it meet? ───────────────────────────────────────────────────

def meets_on(activity_id: int, date: str) -> bool:
    """Whether an activity runs on a given date.

    Weekday, A/B week and the activity's own date range, all of which
    have to agree before a missing mark means anything.
    """
    activity = get_activity(activity_id)
    if activity is None or not activity.active:
        return False
    date = core._validate_date(date)
    if activity.start_date and date < activity.start_date:
        return False
    if activity.end_date and date > activity.end_date:
        return False
    if not activity.is_recurring:
        # Ad hoc: it meets when somebody says it met, which is when a
        # register exists for it.
        return bool(list_marks(activity_id=activity_id, date=date))
    if _dt.date.fromisoformat(date).weekday() + 1 != activity.day:
        return False
    if activity.week != weeks.BOTH:
        pattern = weeks.get_pattern()
        if pattern.is_cycling and \
                weeks.week_for_date(date, pattern=pattern) != activity.week:
            return False
    return True


def meeting_dates(activity_id: int, date_from: str,
                  date_to: str) -> list[str]:
    """Every date in the window on which this activity runs."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_sessions as _sessions,
    )
    return [d for d in _sessions.teaching_dates(date_from, date_to)
            if meets_on(activity_id, d)]


# ── Marking ─────────────────────────────────────────────────────────

def register_view(activity_id: int, date: str) -> list[ActivityEntry]:
    """The fillable register: roster joined to any marks already taken."""
    init_db()
    date = core._validate_date(date)
    if get_activity(activity_id) is None:
        raise ValidationError(f"No activity with id {activity_id}")
    members = list_members(activity_id, on=date)
    marks = {m.student_id: m
             for m in list_marks(activity_id=activity_id, date=date)}
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    index = {s.student_id: s for s in _students.list_students()}
    return [ActivityEntry(
        student_id=sid,
        full_name=(index[sid].full_name if sid in index else "(unknown)"),
        mark=marks.get(sid)) for sid in members]


def save_register(
    activity_id: int,
    date: str,
    entries: dict[str, dict[str, Any]],
    *,
    actor: str | None = None,
) -> int:
    """Upsert marks for an activity register in one transaction.

    Same payload shape as :func:`attendance.save_register`: ``status``
    and ``code`` are interchangeable, and everything else is optional.
    """
    init_db()
    date = core._validate_date(date)
    activity = get_activity(activity_id)
    if activity is None:
        raise ValidationError(f"No activity with id {activity_id}")
    roster = set(list_members(activity_id, on=date))

    cleaned: list[tuple[str, dict[str, Any]]] = []
    for sid, payload in entries.items():
        sid = str(sid).strip()
        if sid not in roster:
            raise ValidationError(
                f"{sid} is not on the roster for {activity.name}")
        try:
            status, code, _session = core.resolve_marks(payload)
        except ValidationError as e:
            raise ValidationError(f"{sid}: {e}") from None
        minutes = core._validate_minutes(payload.get("minutes_late"), status)
        notes = (payload.get("notes") or "").strip() or None
        cleaned.append((sid, {"status": status, "code": code,
                              "minutes_late": minutes, "notes": notes}))

    with _connect() as conn:
        for sid, values in cleaned:
            conn.execute(
                """INSERT INTO attendance_activity_marks
                       (activity_id, student_id, date, code, status,
                        minutes_late, notes, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(activity_id, student_id, date) DO UPDATE SET
                       code = excluded.code,
                       status = excluded.status,
                       minutes_late = excluded.minutes_late,
                       notes = excluded.notes,
                       recorded_by = excluded.recorded_by,
                       recorded_at = datetime('now')""",
                (activity_id, sid, date, values["code"], values["status"],
                 values["minutes_late"], values["notes"],
                 (actor or "").strip() or None))
        conn.commit()
    logger.info("Saved activity register: #%d %s, %d mark(s)",
                activity_id, date, len(cleaned))
    return len(cleaned)


def mark_all(activity_id: int, date: str, code: str, *,
             student_ids: list[str] | None = None,
             actor: str | None = None) -> int:
    """Mark the whole roster (or a selection) with one code."""
    code = codes.validate_code(code)
    members = list_members(activity_id, on=date)
    if student_ids is not None:
        wanted = set(student_ids)
        unknown = wanted - set(members)
        if unknown:
            raise ValidationError(
                "Not on this roster: " + ", ".join(sorted(unknown)))
        members = [m for m in members if m in wanted]
    if not members:
        raise ValidationError("No students to mark")
    return save_register(activity_id, date,
                         {sid: {"code": code} for sid in members},
                         actor=actor)


def list_marks(*, activity_id: int | None = None,
               student_id: str | None = None,
               date: str | None = None,
               date_from: str | None = None,
               date_to: str | None = None,
               code: str | None = None) -> list[ActivityMark]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if activity_id is not None:
        clauses.append("activity_id = ?")
        args.append(activity_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if code:
        clauses.append("code = ?")
        args.append(codes.validate_code(code))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_activity_marks {where} "
            "ORDER BY date DESC, activity_id, student_id", args).fetchall()
    return [_mark_row(r) for r in rows]


def delete_mark(activity_id: int, student_id: str, date: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_activity_marks "
            "WHERE activity_id = ? AND student_id = ? AND date = ?",
            (activity_id, student_id.strip(), core._validate_date(date)))
        conn.commit()
    return bool(cur.rowcount)


# ── Summaries ───────────────────────────────────────────────────────

def _summarise(marks: list[ActivityMark]) -> ActivitySummary:
    summary = ActivitySummary(sessions=len(marks))
    for mark in marks:
        meaning = codes.meaning_for_code(mark.code)
        if meaning in codes.ATTENDING_MEANINGS:
            summary.attending += 1
        elif meaning == codes.AUTHORISED:
            summary.authorised += 1
        elif meaning == codes.UNAUTHORISED:
            summary.unauthorised += 1
        else:
            summary.not_counted += 1
    return summary


def summary_for_activity(activity_id: int, *, date_from: str | None = None,
                         date_to: str | None = None) -> ActivitySummary:
    return _summarise(list_marks(activity_id=activity_id,
                                 date_from=date_from, date_to=date_to))


def summary_for_student(student_id: str, *, date_from: str | None = None,
                        date_to: str | None = None,
                        required_only: bool = True) -> ActivitySummary:
    """One learner across their activities.

    ``required_only`` by default: a voluntary club that somebody drifted
    away from should not drag down the figure a tutor acts on.
    """
    marks = list_marks(student_id=student_id, date_from=date_from,
                       date_to=date_to)
    if required_only:
        required = {a.activity_id for a in list_activities(
            active_only=False, required_only=True)}
        marks = [m for m in marks if m.activity_id in required]
    return _summarise(marks)


def per_student_summary(activity_id: int, *, date_from: str | None = None,
                        date_to: str | None = None
                        ) -> dict[str, ActivitySummary]:
    marks = list_marks(activity_id=activity_id, date_from=date_from,
                       date_to=date_to)
    grouped: dict[str, list[ActivityMark]] = {}
    for mark in marks:
        grouped.setdefault(mark.student_id, []).append(mark)
    return {sid: _summarise(rows) for sid, rows in grouped.items()}


def missing_registers(*, date_from: str, date_to: str,
                      kind: str | None = None
                      ) -> list[MissingActivityRegister]:
    """Activities that met and nobody marked.

    The enrichment equivalent of the lesson chase list, and rather more
    necessary: nobody chases a club register unprompted.
    """
    init_db()
    out: list[MissingActivityRegister] = []
    for activity in list_activities(kind=kind):
        if not activity.is_recurring:
            continue
        for date in meeting_dates(activity.activity_id, date_from, date_to):
            marked = len(list_marks(activity_id=activity.activity_id,
                                    date=date))
            expected = count_members(activity.activity_id, on=date)
            if expected and marked < expected:
                out.append(MissingActivityRegister(
                    activity=activity, date=date, marked=marked,
                    expected=expected))
    out.sort(key=lambda m: (m.date, m.activity.name))
    return out


def today_activities(date: str | None = None) -> list[Activity]:
    """Everything meeting today, in period order."""
    day = core._validate_date(date or _dt.date.today().isoformat())
    running = [a for a in list_activities()
               if meets_on(a.activity_id, day)]
    running.sort(key=lambda a: (a.period or 99, a.name))
    return running
