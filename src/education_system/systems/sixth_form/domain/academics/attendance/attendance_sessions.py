"""Expected sessions and AM/PM statutory marks for Sixth Form Attendance.

Sibling to :mod:`attendance`. Fixes the two things a per-lesson register
cannot tell you on its own.

**What was supposed to happen.** The summaries in :mod:`attendance`
divide by the number of rows that exist. A lesson nobody took a register
for contributes nothing to either side of the fraction, so a group whose
Friday registers are never filled in reads as 100%. That is precisely
backwards. This module expands the timetable across a date window —
skipping weekends, and skipping closures when an academic year is
configured — to produce the *expected* lessons, and then reports what is
missing against them. :func:`true_summary` divides by expectation, not
by evidence.

**AM and PM.** Statutory attendance is counted in two sessions a day,
not in periods. A learner with a free period 1 and a lesson at 10am is
present for the morning session; a learner who leaves at lunch is
present for one session and absent for the other. Per-lesson marks
cannot be summed into that without a rule, so this module holds the
rule: :func:`roll_up_day` collapses a day's lesson marks into an AM mark
and a PM mark, taking the most favourable meaning present in each half
(if the learner was in the room for any of it, they attended). Sessions
can also be marked directly, for the days where there is no lesson to
infer from.

Rolled-up marks are flagged ``derived``, so a later re-run can overwrite
them while leaving anything a human typed alone.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_weeks as weeks,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# The two statutory sessions, plus the marker a per-lesson row carries.
SESSIONS: tuple[str, ...] = ("AM", "PM")
LESSON: str = "Lesson"
SESSION_KINDS: tuple[str, ...] = (*SESSIONS, LESSON)

# A lesson starting at or after this belongs to the afternoon session.
# 13:00 is the start of lunch in `timetable.DEFAULT_PERIOD_TIMES`, which
# puts periods 1–4 in the morning and 5–6 in the afternoon.
AM_PM_CUTOFF: str = "13:00"

# The canonical present mark for each session — `/` in the morning,
# `\` in the afternoon.
PRESENT_CODE_FOR_SESSION: dict[str, str] = {"AM": "/", "PM": "\\"}

# Which meaning wins when a session's lessons disagree. Being in the
# room for any part of a session means the learner attended it, so
# Present outranks everything; a session made up entirely of "not
# counted" lessons is not a possible attendance at all.
_MEANING_RANK: dict[str, int] = {
    codes.PRESENT: 0,
    codes.APPROVED: 1,
    codes.AUTHORISED: 2,
    codes.UNAUTHORISED: 3,
    codes.NOT_COUNTED: 4,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_daily_sessions (
    daily_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    session     TEXT NOT NULL,
    code        TEXT NOT NULL,
    status      TEXT NOT NULL,
    reason_id   INTEGER,
    notes       TEXT,
    derived     INTEGER NOT NULL DEFAULT 0,
    recorded_by TEXT,
    recorded_at TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, date, session),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_daily_date
    ON attendance_daily_sessions(date);
CREATE INDEX IF NOT EXISTS idx_att_daily_student
    ON attendance_daily_sessions(student_id, date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class SessionMark:
    """One AM or PM statutory mark."""

    daily_id: int
    student_id: str
    date: str
    session: str
    code: str
    status: str
    reason_id: int | None
    notes: str | None
    derived: bool
    recorded_by: str | None
    recorded_at: str | None

    @property
    def attending(self) -> bool:
        return codes.counts_as_present(self.code)

    @property
    def possible(self) -> bool:
        return codes.counts_toward_possible(self.code)


@dataclass
class ExpectedLesson:
    """A lesson the timetable says should have happened."""

    date: str
    slot_id: int
    group_id: int
    day: int
    period: int
    start_time: str | None
    end_time: str | None
    session: str

    @property
    def label(self) -> str:
        return (f"{self.date} {tt.day_name(self.day)} P{self.period} "
                f"(slot #{self.slot_id})")


@dataclass
class MissingMark:
    """An expected lesson with no attendance row against it."""

    lesson: ExpectedLesson
    student_id: str
    student_name: str

    @property
    def label(self) -> str:
        return f"{self.student_name} — {self.lesson.label}"


@dataclass
class Coverage:
    """How much of what was expected actually got marked."""

    expected: int = 0
    recorded: int = 0

    @property
    def missing(self) -> int:
        return max(0, self.expected - self.recorded)

    @property
    def percentage(self) -> float | None:
        if self.expected == 0:
            return None
        return round(100.0 * self.recorded / self.expected, 1)


@dataclass
class TrueSummary:
    """An attendance summary whose denominator is what was timetabled.

    ``percentage`` is the figure that belongs on a report: attending
    marks over *possible* sessions, where an unrecorded lesson counts
    against the learner's college rather than in their favour.
    """

    expected: int = 0
    recorded: int = 0
    present: int = 0
    approved: int = 0
    authorised: int = 0
    unauthorised: int = 0
    not_counted: int = 0
    dates: list[str] = field(default_factory=list)

    @property
    def unrecorded(self) -> int:
        return max(0, self.expected - self.recorded)

    @property
    def attending(self) -> int:
        return self.present + self.approved

    @property
    def possible(self) -> int:
        """Expected sessions, less the ones that were never possible."""
        return max(0, self.expected - self.not_counted)

    @property
    def percentage(self) -> float | None:
        """Attendance against what was timetabled."""
        if self.possible == 0:
            return None
        return round(100.0 * self.attending / self.possible, 1)

    @property
    def recorded_percentage(self) -> float | None:
        """The old figure — attendance against marks that exist.

        Kept so the two can be shown side by side: a wide gap between
        them is a register-taking problem, not an attendance problem.
        """
        counted = self.recorded - self.not_counted
        if counted <= 0:
            return None
        return round(100.0 * self.attending / counted, 1)

    @property
    def unauthorised_percentage(self) -> float | None:
        if self.possible == 0:
            return None
        return round(100.0 * self.unauthorised / self.possible, 1)


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
    codes.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Daily-session schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> SessionMark:
    return SessionMark(
        daily_id=r["daily_id"],
        student_id=r["student_id"],
        date=r["date"],
        session=r["session"],
        code=r["code"],
        status=r["status"],
        reason_id=r["reason_id"],
        notes=r["notes"],
        derived=bool(r["derived"]),
        recorded_by=r["recorded_by"],
        recorded_at=r["recorded_at"],
    )


# ── Session identification ──────────────────────────────────────────

def validate_session(value: Any) -> str:
    """Normalise 'am' / 'PM' / 'lesson' to one of :data:`SESSION_KINDS`."""
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError("Session is required")
    for kind in SESSION_KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(
        f"Session must be one of: {', '.join(SESSION_KINDS)}")


def session_for_time(hhmm: str | None) -> str:
    """Which half of the day a clock time falls in.

    An unparseable or missing time is treated as morning — a mark has to
    land somewhere, and AM is the safer default because it is the
    session a late arrival is most likely to concern.
    """
    if not hhmm or not isinstance(hhmm, str):
        return "AM"
    return "PM" if hhmm.strip() >= AM_PM_CUTOFF else "AM"


def session_for_slot(slot_id: int) -> str:
    """Which session a timetable slot belongs to.

    Falls back to the period's default times when the slot has none, and
    to AM if the slot has vanished — this is called from a write path,
    and refusing to save a mark over a missing start time would be a
    poor trade.
    """
    slot = tt.get_slot(slot_id)
    if slot is None:
        return "AM"
    start = slot.start_time
    if not start:
        start = tt.DEFAULT_PERIOD_TIMES.get(slot.period, ("09:00", ""))[0]
    return session_for_time(start)


# ── Expected sessions ───────────────────────────────────────────────

def _current_year_id() -> int | None:
    """The active academic year, if one is set up.

    Everything here degrades to plain Monday-to-Friday when there isn't
    one: a college that has not built its calendar yet should still get
    a usable expectation, just one that does not know about half term.
    """
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (  # noqa: E501
            academic_year as ay,
        )
        year = ay.current_year()
        return year.year_id if year else None
    except Exception:                     # pragma: no cover - optional dep
        logger.debug("Academic year unavailable; using plain weekdays",
                     exc_info=True)
        return None


def teaching_dates(date_from: str, date_to: str, *,
                   group_label: str | None = None) -> list[str]:
    """Every weekday in the window the college is actually open.

    Closures come from the academic-year calendar when there is one.
    """
    date_from = core._validate_date(date_from)
    date_to = core._validate_date(date_to)
    start = _dt.date.fromisoformat(date_from)
    end = _dt.date.fromisoformat(date_to)
    if end < start:
        return []

    closed: set[str] = set()
    year_id = _current_year_id()
    if year_id is not None:
        try:
            from education_system.systems.sixth_form.domain.academics.academic_year import (  # noqa: E501
                academic_year as ay,
            )
            cursor = start
            while cursor <= end:
                iso = cursor.isoformat()
                if cursor.weekday() < 5:
                    brk = ay.is_break(year_id, iso, group_label=group_label)
                    # An AM- or PM-only closure still leaves half a day
                    # of teaching, so only a FULL break drops the date.
                    if brk is not None and getattr(
                            brk, "am_pm", "FULL") == "FULL":
                        closed.add(iso)
                cursor += _dt.timedelta(days=1)
        except Exception:                 # pragma: no cover - optional dep
            logger.debug("Break lookup failed; ignoring closures",
                         exc_info=True)
            closed = set()

    out: list[str] = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        if cursor.weekday() < 5 and iso not in closed:
            out.append(iso)
        cursor += _dt.timedelta(days=1)
    return out


def expected_lessons(
    *,
    student_id: str | None = None,
    group_id: int | None = None,
    slot_id: int | None = None,
    date_from: str,
    date_to: str,
) -> list[ExpectedLesson]:
    """Expand the timetable across a date window.

    One entry per (date, slot) the timetable says should happen. Filter
    by learner, group or single slot; with none of those, the whole
    college's timetable comes back.
    """
    init_db()
    slots = tt.list_slots(group_id=group_id, student_id=student_id)
    if slot_id is not None:
        slots = [s for s in slots if s.slot_id == slot_id]
    if not slots:
        return []

    by_day: dict[int, list[Any]] = {}
    for slot in slots:
        by_day.setdefault(slot.day, []).append(slot)

    # On an A/B timetable, half of these slots do not run in any given
    # week. Expanding them all would invent lessons nobody was meant to
    # teach and then report them as unmarked. Read the map once.
    pattern = weeks.get_pattern()
    week_map = weeks.week_map() if pattern.is_cycling else {}

    out: list[ExpectedLesson] = []
    for iso in teaching_dates(date_from, date_to):
        # `timetable.day` is 1-based with Monday = 1.
        day = _dt.date.fromisoformat(iso).weekday() + 1
        todays = weeks.filter_slots(by_day.get(day, []), iso,
                                    pattern=pattern, mapping=week_map)
        for slot in sorted(todays, key=lambda s: s.period):
            out.append(ExpectedLesson(
                date=iso,
                slot_id=slot.slot_id,
                group_id=slot.group_id,
                day=slot.day,
                period=slot.period,
                start_time=slot.start_time,
                end_time=slot.end_time,
                session=session_for_slot(slot.slot_id),
            ))
    return out


def expected_count(**kwargs: Any) -> int:
    """How many lessons the timetable expects. See :func:`expected_lessons`."""
    return len(expected_lessons(**kwargs))


def missing_marks(
    *,
    student_id: str | None = None,
    group_id: int | None = None,
    date_from: str,
    date_to: str,
) -> list[MissingMark]:
    """Expected lessons with no attendance row — the real coverage gap.

    One entry per learner per missing lesson, because "period 3 was
    never marked" and "one learner was left off period 3" are different
    problems with the same fix.
    """
    init_db()
    lessons = expected_lessons(student_id=student_id, group_id=group_id,
                               date_from=date_from, date_to=date_to)
    if not lessons:
        return []

    from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
        class_groups as cg,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as students_mod,
    )

    rosters: dict[int, list[str]] = {}
    for lesson in lessons:
        if lesson.group_id not in rosters:
            members = cg.list_members(lesson.group_id)
            if student_id is not None:
                members = [m for m in members if m == student_id]
            rosters[lesson.group_id] = members

    have = {(r.slot_id, r.date, r.student_id) for r in core.list_records(
        student_id=student_id, group_id=group_id,
        date_from=date_from, date_to=date_to)}

    wanted = {sid for members in rosters.values() for sid in members}
    names = {s.student_id: s.full_name
             for s in students_mod.list_students()
             if s.student_id in wanted}

    out: list[MissingMark] = []
    for lesson in lessons:
        for sid in rosters.get(lesson.group_id, []):
            if (lesson.slot_id, lesson.date, sid) in have:
                continue
            out.append(MissingMark(lesson=lesson, student_id=sid,
                                   student_name=names.get(sid, sid)))
    return out


def coverage(*, group_id: int | None = None,
             student_id: str | None = None,
             date_from: str, date_to: str) -> Coverage:
    """What share of the expected marks actually exist."""
    init_db()
    lessons = expected_lessons(student_id=student_id, group_id=group_id,
                               date_from=date_from, date_to=date_to)
    if not lessons:
        return Coverage()

    from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
        class_groups as cg,
    )
    rosters: dict[int, int] = {}
    for lesson in lessons:
        if lesson.group_id not in rosters:
            members = cg.list_members(lesson.group_id)
            if student_id is not None:
                members = [m for m in members if m == student_id]
            rosters[lesson.group_id] = len(members)

    expected = sum(rosters.get(lesson.group_id, 0) for lesson in lessons)
    recorded = len(core.list_records(
        student_id=student_id, group_id=group_id,
        date_from=date_from, date_to=date_to))
    # A register can hold marks for learners who have since left the
    # group, so cap rather than reporting over 100% coverage.
    return Coverage(expected=expected, recorded=min(recorded, expected))


def true_summary(
    student_id: str,
    *,
    date_from: str,
    date_to: str,
    group_id: int | None = None,
) -> TrueSummary:
    """A learner's attendance measured against their timetable.

    Unlike :func:`attendance.summary_for_student`, a lesson nobody
    marked still lands in the denominator. The gap between
    :attr:`TrueSummary.percentage` and
    :attr:`TrueSummary.recorded_percentage` is the size of the
    register-taking problem sitting behind the headline figure.
    """
    init_db()
    lessons = expected_lessons(student_id=student_id, group_id=group_id,
                               date_from=date_from, date_to=date_to)
    records = core.list_records(student_id=student_id, group_id=group_id,
                                date_from=date_from, date_to=date_to)

    out = TrueSummary(expected=len(lessons), recorded=len(records),
                      dates=sorted({lesson.date for lesson in lessons}))
    for record in records:
        mark = codes.get_code(record.code)
        meaning = (mark.meaning if mark
                   else _meaning_for_status(record.status))
        if meaning == codes.PRESENT:
            out.present += 1
        elif meaning == codes.APPROVED:
            out.approved += 1
        elif meaning == codes.AUTHORISED:
            out.authorised += 1
        elif meaning == codes.UNAUTHORISED:
            out.unauthorised += 1
        else:
            out.not_counted += 1
    return out


def _meaning_for_status(status: str) -> str:
    """Best guess at a meaning for a row written before codes existed."""
    return {
        "Present": codes.PRESENT,
        "Late": codes.PRESENT,
        "Authorised": codes.AUTHORISED,
        "Absent": codes.UNAUTHORISED,
    }.get(status, codes.UNAUTHORISED)


# ── AM/PM session marks ─────────────────────────────────────────────

def _validate_statutory_session(value: Any) -> str:
    session = validate_session(value)
    if session == LESSON:
        raise ValidationError(
            "A statutory mark is AM or PM — 'Lesson' is for period rows")
    return session


def mark_session(
    student_id: str,
    date: str,
    session: str,
    code: str,
    *,
    reason_id: int | None = None,
    notes: str | None = None,
    recorded_by: str | None = None,
    derived: bool = False,
) -> SessionMark:
    """Record (or replace) one AM/PM statutory mark.

    A mark a human typed will not be overwritten by a later roll-up —
    only another explicit call can replace it.
    """
    init_db()
    date = core._validate_date(date)
    session = _validate_statutory_session(session)
    code = codes.validate_code(code)
    if reason_id is not None:
        reason_id = codes.validate_reason_id(reason_id)

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_daily_sessions
                   (student_id, date, session, code, status, reason_id,
                    notes, derived, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, date, session) DO UPDATE SET
                   code = excluded.code,
                   status = excluded.status,
                   reason_id = excluded.reason_id,
                   notes = excluded.notes,
                   derived = excluded.derived,
                   recorded_by = excluded.recorded_by,
                   recorded_at = datetime('now')""",
            (student_id, date, session, code, codes.status_for_code(code),
             reason_id, (notes or "").strip() or None,
             1 if derived else 0, (recorded_by or "").strip() or None))
        conn.commit()
    out = get_session_mark(student_id, date, session)
    assert out is not None
    return out


def get_session_mark(student_id: str, date: str,
                     session: str) -> SessionMark | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_daily_sessions "
            "WHERE student_id = ? AND date = ? AND session = ?",
            (student_id, core._validate_date(date),
             _validate_statutory_session(session))).fetchone()
    return _row(r) if r else None


def list_session_marks(*, student_id: str | None = None,
                       date: str | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       session: str | None = None,
                       derived_only: bool = False) -> list[SessionMark]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if session:
        clauses.append("session = ?")
        args.append(_validate_statutory_session(session))
    if derived_only:
        clauses.append("derived = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_daily_sessions {where} "
            "ORDER BY date, student_id, session", args).fetchall()
    return [_row(r) for r in rows]


def delete_session_mark(student_id: str, date: str, session: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_daily_sessions "
            "WHERE student_id = ? AND date = ? AND session = ?",
            (student_id, core._validate_date(date),
             _validate_statutory_session(session)))
        conn.commit()
    return bool(cur.rowcount)


# ── Rolling lesson marks up into sessions ───────────────────────────

def _best_mark(records: list[core.AttendanceRecord]) -> str | None:
    """The code that should represent a session, given its lessons.

    Ranked by meaning, most favourable first: attending any part of a
    session means attending the session. Within a meaning the first
    lesson's code wins, so an authorised session keeps the specific
    reason code (`I`, `M`) rather than collapsing to a generic one.
    """
    best: tuple[int, str] | None = None
    for record in records:
        code = record.code or codes.default_code_for_status(record.status)
        mark = codes.get_code(code)
        if mark is None:
            continue
        rank = _MEANING_RANK.get(mark.meaning, 99)
        if best is None or rank < best[0]:
            best = (rank, code)
    return best[1] if best else None


def roll_up_day(student_id: str, date: str, *,
                recorded_by: str | None = None,
                overwrite_manual: bool = False) -> list[SessionMark]:
    """Derive a learner's AM and PM marks from their lesson marks.

    Sessions with no lessons at all are left alone — there is nothing to
    infer from, and writing an absence would be inventing one. A mark a
    human entered is preserved unless ``overwrite_manual`` says
    otherwise.
    """
    init_db()
    date = core._validate_date(date)
    records = core.list_records(student_id=student_id, date=date)
    if not records:
        return []

    buckets: dict[str, list[core.AttendanceRecord]] = {"AM": [], "PM": []}
    for record in records:
        session = record.session
        if session not in SESSIONS:
            session = session_for_slot(record.slot_id)
        buckets[session].append(record)

    out: list[SessionMark] = []
    for session, in_session in buckets.items():
        if not in_session:
            continue
        existing = get_session_mark(student_id, date, session)
        if existing and not existing.derived and not overwrite_manual:
            continue
        code = _best_mark(in_session)
        if code is None:
            continue
        # A present session takes the session's own present code, so an
        # afternoon reads `\` rather than whichever lesson won.
        if codes.meaning_for_code(code) == codes.PRESENT:
            code = PRESENT_CODE_FOR_SESSION[session]
        out.append(mark_session(
            student_id, date, session, code,
            recorded_by=recorded_by, derived=True,
            notes=f"Derived from {len(in_session)} lesson mark(s)"))
    return out


def roll_up_range(*, date_from: str, date_to: str,
                  student_id: str | None = None,
                  group_id: int | None = None,
                  recorded_by: str | None = None,
                  overwrite_manual: bool = False) -> int:
    """Roll up every learner and day in a window. Returns marks written.

    Idempotent — re-running rewrites the derived marks and leaves the
    manual ones, so this is safe as a nightly job.
    """
    init_db()
    records = core.list_records(student_id=student_id, group_id=group_id,
                                date_from=date_from, date_to=date_to)
    pairs = sorted({(r.student_id, r.date) for r in records})
    written = 0
    for sid, date in pairs:
        written += len(roll_up_day(sid, date, recorded_by=recorded_by,
                                   overwrite_manual=overwrite_manual))
    if written:
        logger.info("Rolled up %d session mark(s) over %s..%s",
                    written, date_from, date_to)
    return written


# ── Session-level reporting ─────────────────────────────────────────

@dataclass
class SessionSummary:
    """Statutory attendance for one learner, counted in sessions."""

    student_id: str
    possible: int = 0
    attended: int = 0
    authorised: int = 0
    unauthorised: int = 0
    not_counted: int = 0

    @property
    def absences(self) -> int:
        return self.authorised + self.unauthorised

    @property
    def percentage(self) -> float | None:
        if self.possible == 0:
            return None
        return round(100.0 * self.attended / self.possible, 1)

    @property
    def unauthorised_percentage(self) -> float | None:
        if self.possible == 0:
            return None
        return round(100.0 * self.unauthorised / self.possible, 1)

    @property
    def persistently_absent(self) -> bool:
        """Below 90% — the sector's persistent-absence threshold."""
        pct = self.percentage
        return pct is not None and pct < 90.0


def session_summary(student_id: str, *, date_from: str | None = None,
                    date_to: str | None = None) -> SessionSummary:
    """Roll a learner's AM/PM marks into the statutory headline figures."""
    marks = list_session_marks(student_id=student_id, date_from=date_from,
                               date_to=date_to)
    out = SessionSummary(student_id=student_id)
    for mark in marks:
        if not mark.possible:
            out.not_counted += 1
            continue
        out.possible += 1
        if mark.attending:
            out.attended += 1
        elif codes.is_authorised_absence(mark.code):
            out.authorised += 1
        else:
            out.unauthorised += 1
    return out


def sessions_expected(*, date_from: str, date_to: str,
                      group_label: str | None = None) -> int:
    """How many AM/PM sessions the window holds — two per open day."""
    return 2 * len(teaching_dates(date_from, date_to,
                                  group_label=group_label))
