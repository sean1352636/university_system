"""Exam room registers for the Sixth Form System.

Sibling to :mod:`attendance`, and the attendance half of
:mod:`exam_entries`. That module knows who is entered for 9MA0/01; this
one records who was in the hall on the morning, in which seat, and what
happened to the ones who were not.

An exam register is not a lesson register wearing a hat. The rules are
different and the consequences are larger:

* **Seats are the record.** A candidate is identified by seat and
  candidate number, not by a name a teacher recognises, and the seating
  plan is a retained document.
* **Late is not one thing.** A candidate admitted five minutes in sits
  the paper normally. One admitted after the first hour may still sit
  it, but the fact has to be reported to the board, which is what
  :data:`VERY_LATE_MINUTES` marks. That distinction is the whole reason
  arrival times get written down.
* **An absence is an incident.** A missing candidate means a phone call
  during the exam, and afterwards a decision about whether the entry
  was withdrawn, absent, or ill with evidence.
* **Somebody signs it.** The invigilator's sign-off closes the register,
  after which it takes a reason to reopen — the same discipline as a
  lesson register, for much better reasons.

Nothing here writes to the lesson register. A candidate sitting an exam
is accounted for by the sitting, and :func:`sync_to_register` exists so
a college that wants the timetable to agree can ask for it explicitly.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# What happened to one candidate.
PRESENT: str = "Present"
LATE: str = "Late"
VERY_LATE: str = "Very late"        # after the reportable threshold
ABSENT: str = "Absent"
WITHDRAWN: str = "Withdrawn"
REMOVED: str = "Removed"            # taken out during the paper
CANDIDATE_STATES: tuple[str, ...] = (
    PRESENT, LATE, VERY_LATE, ABSENT, WITHDRAWN, REMOVED,
)

# Sat the paper, whatever else happened.
SAT_STATES: frozenset[str] = frozenset({PRESENT, LATE, VERY_LATE, REMOVED})

# Minutes after the published start after which a late arrival stops
# being an internal matter and becomes something the board is told
# about. One hour is the sector's line.
VERY_LATE_MINUTES: int = 60

# Sitting lifecycle.
PLANNED: str = "Planned"
OPEN: str = "Open"
SIGNED_OFF: str = "Signed off"
SITTING_STATES: tuple[str, ...] = (PLANNED, OPEN, SIGNED_OFF)

# Why a candidate was absent, decided after the paper.
ABSENCE_REASONS: tuple[str, ...] = (
    "Unexplained",
    "Illness (evidence received)",
    "Illness (no evidence)",
    "Bereavement",
    "Transport failure",
    "Clash resolved elsewhere",
    "Withdrawn before the exam",
    "Other",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_exam_sittings (
    sitting_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_code   TEXT NOT NULL,
    paper_title  TEXT,
    subject      TEXT,
    exam_board   TEXT,
    date         TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    room         TEXT,
    series       TEXT,
    year         INTEGER,
    state        TEXT NOT NULL DEFAULT 'Planned',
    invigilator  TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    reopen_reason TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(paper_code, date, start_time, room)
);

CREATE TABLE IF NOT EXISTS attendance_exam_candidates (
    candidate_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sitting_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    seat         TEXT,
    candidate_no TEXT,
    state        TEXT,
    arrival_time TEXT,
    minutes_late INTEGER,
    departure_time TEXT,
    absence_reason TEXT,
    access_arrangements TEXT,
    notes        TEXT,
    recorded_by  TEXT,
    recorded_at  TEXT,
    UNIQUE(sitting_id, student_id),
    FOREIGN KEY (sitting_id) REFERENCES attendance_exam_sittings(sitting_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_exam_sit_date
    ON attendance_exam_sittings(date);
CREATE INDEX IF NOT EXISTS idx_att_exam_cand_student
    ON attendance_exam_candidates(student_id);
CREATE INDEX IF NOT EXISTS idx_att_exam_cand_state
    ON attendance_exam_candidates(state);
"""

# Columns added for the exams office. Candidates carry the access
# arrangements copied from the SEN record when the sitting is populated
# (and their own finish time once extra time is applied); sittings carry
# the timetable row they came from and the latest extra-time finish.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "attendance_exam_sittings": {
        "timetable_id": "INTEGER",
        "extended_end_time": "TEXT",
    },
    "attendance_exam_candidates": {
        "extra_time_pct": "INTEGER NOT NULL DEFAULT 0",
        "reader": "INTEGER NOT NULL DEFAULT 0",
        "scribe": "INTEGER NOT NULL DEFAULT 0",
        "word_processor": "INTEGER NOT NULL DEFAULT 0",
        "separate_room": "INTEGER NOT NULL DEFAULT 0",
        "rest_breaks": "INTEGER NOT NULL DEFAULT 0",
        "finish_time": "TEXT",
        "arrangement_flags": "TEXT",
    },
}


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Sitting:
    """One paper, in one room, at one time."""

    sitting_id: int
    paper_code: str
    paper_title: str | None
    subject: str | None
    exam_board: str | None
    date: str
    start_time: str
    end_time: str | None
    room: str | None
    series: str | None
    year: int | None
    state: str
    invigilator: str | None
    signed_off_by: str | None
    signed_off_at: str | None
    reopen_reason: str | None
    notes: str | None
    created_at: str | None
    timetable_id: int | None = None
    extended_end_time: str | None = None

    @property
    def duration_minutes(self) -> int | None:
        if not self.end_time:
            return None
        return _minutes(self.end_time) - _minutes(self.start_time)

    @property
    def is_signed_off(self) -> bool:
        return self.state == SIGNED_OFF

    @property
    def label(self) -> str:
        return (f"{self.paper_code} {self.date} {self.start_time}"
                + (f" · {self.room}" if self.room else ""))

    @property
    def very_late_after(self) -> str:
        """The clock time after which an arrival is reportable."""
        h, m = self.start_time.split(":")
        total = int(h) * 60 + int(m) + VERY_LATE_MINUTES
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"


@dataclass
class Candidate:
    """One candidate's place in one sitting."""

    candidate_row_id: int
    sitting_id: int
    student_id: str
    seat: str | None
    candidate_no: str | None
    state: str | None
    arrival_time: str | None
    minutes_late: int | None
    departure_time: str | None
    absence_reason: str | None
    access_arrangements: str | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str | None
    full_name: str | None = None
    extra_time_pct: int = 0
    reader: bool = False
    scribe: bool = False
    word_processor: bool = False
    separate_room: bool = False
    rest_breaks: bool = False
    finish_time: str | None = None
    arrangement_flags: str | None = None

    @property
    def marked(self) -> bool:
        return self.state is not None

    @property
    def sat(self) -> bool:
        return self.state in SAT_STATES

    @property
    def reportable(self) -> bool:
        """Whether the board has to be told about this candidate."""
        return self.state in (VERY_LATE, REMOVED)

    @property
    def label(self) -> str:
        seat = f"seat {self.seat}" if self.seat else "unseated"
        return (f"{self.candidate_no or self.student_id} "
                f"{self.full_name or ''} ({seat}) — "
                f"{self.state or 'unmarked'}").replace("  ", " ")


@dataclass
class SittingSummary:
    """The numbers an exams officer reads out afterwards."""

    sitting: Sitting
    entered: int = 0
    present: int = 0
    late: int = 0
    very_late: int = 0
    absent: int = 0
    withdrawn: int = 0
    removed: int = 0
    unmarked: int = 0

    @property
    def sat(self) -> int:
        return self.present + self.late + self.very_late + self.removed

    @property
    def complete(self) -> bool:
        return self.unmarked == 0

    @property
    def attendance_rate(self) -> float | None:
        expected = self.entered - self.withdrawn
        if expected <= 0:
            return None
        return round(100.0 * self.sat / expected, 1)


@dataclass
class SeatingPlan:
    """The seating plan, as printed."""

    sitting: Sitting
    rows: list[Candidate] = field(default_factory=list)
    unseated: list[Candidate] = field(default_factory=list)


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
        for table, cols in _ADDED_COLUMNS.items():
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for name, decl in cols.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                    logger.info("Added %s.%s", table, name)
        conn.commit()
    logger.debug("Exam-register schema ready at %s", DB_PATH)
    _DB_READY = True


def _sitting_row(r: sqlite3.Row) -> Sitting:
    keys = r.keys()
    return Sitting(
        sitting_id=r["sitting_id"],
        paper_code=r["paper_code"],
        paper_title=r["paper_title"],
        subject=r["subject"],
        exam_board=r["exam_board"],
        date=r["date"],
        start_time=r["start_time"],
        end_time=r["end_time"],
        room=r["room"],
        series=r["series"],
        year=r["year"],
        state=r["state"],
        invigilator=r["invigilator"],
        signed_off_by=r["signed_off_by"],
        signed_off_at=r["signed_off_at"],
        reopen_reason=r["reopen_reason"],
        notes=r["notes"],
        created_at=r["created_at"],
        timetable_id=r["timetable_id"] if "timetable_id" in keys else None,
        extended_end_time=(r["extended_end_time"]
                           if "extended_end_time" in keys else None),
    )


def _candidate_row(r: sqlite3.Row) -> Candidate:
    keys = r.keys()
    return Candidate(
        candidate_row_id=r["candidate_row_id"],
        sitting_id=r["sitting_id"],
        student_id=r["student_id"],
        seat=r["seat"],
        candidate_no=r["candidate_no"],
        state=r["state"],
        arrival_time=r["arrival_time"],
        minutes_late=r["minutes_late"],
        departure_time=r["departure_time"],
        absence_reason=r["absence_reason"],
        access_arrangements=r["access_arrangements"],
        notes=r["notes"],
        recorded_by=r["recorded_by"],
        recorded_at=r["recorded_at"],
        full_name=r["full_name"] if "full_name" in keys else None,
        extra_time_pct=(r["extra_time_pct"] or 0) if "extra_time_pct" in keys else 0,
        reader=bool(r["reader"]) if "reader" in keys else False,
        scribe=bool(r["scribe"]) if "scribe" in keys else False,
        word_processor=(bool(r["word_processor"])
                        if "word_processor" in keys else False),
        separate_room=bool(r["separate_room"]) if "separate_room" in keys else False,
        rest_breaks=bool(r["rest_breaks"]) if "rest_breaks" in keys else False,
        finish_time=r["finish_time"] if "finish_time" in keys else None,
        arrangement_flags=(r["arrangement_flags"]
                           if "arrangement_flags" in keys else None),
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_state(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for state in CANDIDATE_STATES:
        if s.lower() == state.lower():
            return state
    raise ValidationError(
        f"State must be one of: {', '.join(CANDIDATE_STATES)}")


def validate_absence_reason(value: Any) -> str | None:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return None
    for reason in ABSENCE_REASONS:
        if s.lower() == reason.lower():
            return reason
    raise ValidationError(
        f"Absence reason must be one of: {', '.join(ABSENCE_REASONS)}")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def state_for_arrival(sitting: Sitting, arrival_time: str) -> tuple[str, int]:
    """Classify an arrival against the published start.

    Returns ``(state, minutes_late)``. The hour threshold is the line
    between "the invigilator deals with it" and "the board is told".
    """
    late = max(0, _minutes(arrival_time) - _minutes(sitting.start_time))
    if late == 0:
        return PRESENT, 0
    return (VERY_LATE if late > VERY_LATE_MINUTES else LATE), late


# ── Sittings ────────────────────────────────────────────────────────

def create_sitting(data: dict[str, Any]) -> Sitting:
    """Schedule a paper."""
    init_db()
    paper_code = (data.get("paper_code") or "").strip()
    if not paper_code:
        raise ValidationError("Paper code is required")
    date = core._validate_date(data.get("date"))
    start_time = reg._validate_time(data.get("start_time"), "Start time")
    end_time = (reg._validate_time(data.get("end_time"), "End time")
                if data.get("end_time") else None)
    if end_time and _minutes(end_time) <= _minutes(start_time):
        raise ValidationError("End time must be after the start time")
    year = data.get("year")
    if year not in (None, ""):
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise ValidationError("Year must be a number") from None
    else:
        year = _dt.date.fromisoformat(date).year

    def text(key: str, limit: int = 120) -> str | None:
        value = data.get(key)
        s = (value or "").strip() if isinstance(value, str) else ""
        if len(s) > limit:
            raise ValidationError(
                f"{key.replace('_', ' ').title()} must be {limit} characters "
                "or fewer")
        return s or None

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_exam_sittings
                   (paper_code, paper_title, subject, exam_board, date,
                    start_time, end_time, room, series, year, state,
                    invigilator, notes, timetable_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_code, text("paper_title"), text("subject"),
             text("exam_board"), date, start_time, end_time, text("room"),
             text("series", 40), year, PLANNED, text("invigilator"),
             text("notes", 500), data.get("timetable_id") or None))
        conn.commit()
        sitting_id = int(cur.lastrowid or 0)
    logger.info("Created exam sitting #%d: %s on %s", sitting_id, paper_code,
                date)
    out = get_sitting(sitting_id)
    assert out is not None
    return out


def get_sitting(sitting_id: int) -> Sitting | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_exam_sittings WHERE sitting_id = ?",
            (sitting_id,)).fetchone()
    return _sitting_row(r) if r else None


def list_sittings(*, date: str | None = None, date_from: str | None = None,
                  date_to: str | None = None, state: str | None = None,
                  paper_code: str | None = None,
                  room: str | None = None) -> list[Sitting]:
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
    if state:
        if state not in SITTING_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(SITTING_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if paper_code:
        clauses.append("paper_code = ?")
        args.append(paper_code.strip())
    if room:
        clauses.append("room = ?")
        args.append(room.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_exam_sittings {where} "
            "ORDER BY date, start_time, paper_code", args).fetchall()
    return [_sitting_row(r) for r in rows]


def delete_sitting(sitting_id: int) -> bool:
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting and sitting.is_signed_off:
        raise ValidationError(
            "A signed-off exam register cannot be deleted — it is a retained "
            "document")
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_exam_sittings WHERE sitting_id = ?",
            (sitting_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Candidates ──────────────────────────────────────────────────────

def add_candidate(sitting_id: int, student_id: str, *,
                  seat: str | None = None,
                  candidate_no: str | None = None,
                  access_arrangements: str | None = None) -> Candidate:
    """Put one candidate into a sitting."""
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    _assert_open(sitting)
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    seat = (seat or "").strip() or None
    if seat:
        clash = next((c for c in list_candidates(sitting_id)
                      if c.seat == seat and c.student_id != student_id), None)
        if clash:
            raise ValidationError(
                f"Seat {seat} is already {clash.student_id}'s")

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_exam_candidates
                   (sitting_id, student_id, seat, candidate_no,
                    access_arrangements)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(sitting_id, student_id) DO UPDATE SET
                   seat = COALESCE(excluded.seat,
                                   attendance_exam_candidates.seat),
                   candidate_no = COALESCE(
                       excluded.candidate_no,
                       attendance_exam_candidates.candidate_no),
                   access_arrangements = COALESCE(
                       excluded.access_arrangements,
                       attendance_exam_candidates.access_arrangements)""",
            (sitting_id, student_id.strip(), seat,
             (candidate_no or "").strip() or None,
             (access_arrangements or "").strip() or None))
        conn.commit()
    out = get_candidate(sitting_id, student_id)
    assert out is not None
    return out


def populate_from_entries(sitting_id: int, *,
                          auto_seat: bool = True,
                          exclude: set[str] | None = None) -> int:
    """Fill a sitting from the exam entries for its paper.

    The candidate list already exists in :mod:`exam_entries`; retyping it
    is how a candidate ends up missing from the hall with an entry the
    board is expecting. Withdrawn entries and anyone in ``exclude`` (e.g.
    a candidate whose clash moves this paper) are left out.

    Each candidate's number comes from the student record when it holds
    one, else the entry; their exam access arrangements are copied on
    and their finish time reflects any extra time.
    """
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        candidates as _cands,
    )
    kwargs: dict[str, Any] = {"paper_code": sitting.paper_code}
    if sitting.year:
        kwargs["year"] = sitting.year
    if sitting.series:
        kwargs["season"] = sitting.series
    try:
        entries = _entries.list_entries(**kwargs)
    except (TypeError, ValidationError):        # pragma: no cover - signature drift
        entries = [e for e in _entries.list_entries()
                   if e.paper_code == sitting.paper_code]
    skip = exclude or set()
    entries = [e for e in entries
               if e.status != "Withdrawn" and e.student_id not in skip]
    idents = _cands.identities(sorted({e.student_id for e in entries}))

    added = 0
    for index, entry in enumerate(sorted(entries,
                                         key=lambda e: e.student_id), 1):
        ident = idents.get(entry.student_id)
        cand_no = (ident.candidate_no if ident and ident.source == "student record"
                   else None) or entry.candidate_no or (
                       ident.candidate_no if ident else None)
        add_candidate(sitting_id, entry.student_id,
                      seat=str(index) if auto_seat else None,
                      candidate_no=cand_no)
        added += 1
    apply_access_arrangements(sitting_id)
    logger.info("Populated sitting #%d with %d candidate(s)", sitting_id, added)
    return added


def apply_access_arrangements(sitting_id: int) -> int:
    """Copy every candidate's exam access arrangements onto the sitting.

    Reads the arrangements recorded under "Exam Access" in the SEN
    record (expired ones are flagged, not applied), sets the candidate's
    flags and finish time (start + duration x (1 + extra time)), and
    stores the latest finish on the sitting. Returns the number of
    candidates with an arrangement.
    """
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    _assert_open(sitting)
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        access_arrangements as _access,
    )
    duration = sitting.duration_minutes
    latest = sitting.end_time
    with_arrangements = 0
    # Read everything first: the arrangement lookups open their own
    # connections, which must not wait on this one's write lock.
    pairs = [(cand, _access.for_student(cand.student_id))
             for cand in list_candidates(sitting_id)]
    with _connect() as conn:
        for cand, arr in pairs:
            finish = None
            if duration is not None:
                extra = round(duration * arr.extra_time_pct / 100)
                total = _minutes(sitting.start_time) + duration + extra
                finish = f"{(total // 60) % 24:02d}:{total % 60:02d}"
                if latest is None or finish > latest:
                    latest = finish
            if arr.any or arr.flags:
                with_arrangements += 1
            conn.execute(
                """UPDATE attendance_exam_candidates
                      SET extra_time_pct = ?, reader = ?, scribe = ?,
                          word_processor = ?, separate_room = ?,
                          rest_breaks = ?, finish_time = ?,
                          arrangement_flags = ?,
                          access_arrangements = ?
                    WHERE sitting_id = ? AND student_id = ?""",
                (arr.extra_time_pct, int(arr.reader), int(arr.scribe),
                 int(arr.word_processor), int(arr.separate_room),
                 int(arr.rest_breaks), finish,
                 "; ".join(arr.flags) or None, arr.summary() or None,
                 sitting_id, cand.student_id))
        conn.execute(
            "UPDATE attendance_exam_sittings SET extended_end_time = ? "
            "WHERE sitting_id = ?",
            (latest if latest != sitting.end_time else None, sitting_id))
        conn.commit()
    return with_arrangements


def move_candidates_to_room(sitting_id: int, student_ids: list[str],
                            room: str) -> Sitting:
    """Move candidates (e.g. those needing a separate room) to the same
    paper in another room, creating that room's sitting if needed."""
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    _assert_open(sitting)
    room = (room or "").strip()
    if not room:
        raise ValidationError("Room is required")
    if room == (sitting.room or ""):
        raise ValidationError("That is the room they are already in")
    target = next((s for s in list_sittings(date=sitting.date,
                                            paper_code=sitting.paper_code,
                                            room=room)
                   if s.start_time == sitting.start_time), None)
    if target is None:
        target = create_sitting({
            "paper_code": sitting.paper_code, "paper_title": sitting.paper_title,
            "subject": sitting.subject, "exam_board": sitting.exam_board,
            "date": sitting.date, "start_time": sitting.start_time,
            "end_time": sitting.end_time, "room": room,
            "series": sitting.series, "year": sitting.year,
            "timetable_id": sitting.timetable_id,
            "notes": f"Separate room for {sitting.label}"})
    _assert_open(target)
    for sid in student_ids:
        cand = get_candidate(sitting_id, sid)
        if cand is None:
            continue
        add_candidate(target.sitting_id, sid, candidate_no=cand.candidate_no)
        remove_candidate(sitting_id, sid)
    apply_access_arrangements(target.sitting_id)
    apply_access_arrangements(sitting_id)
    out = get_sitting(target.sitting_id)
    assert out is not None
    return out


def get_candidate(sitting_id: int, student_id: str) -> Candidate | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_exam_candidates "
            "WHERE sitting_id = ? AND student_id = ?",
            (sitting_id, student_id.strip())).fetchone()
    return _candidate_row(r) if r else None


def list_candidates(sitting_id: int, *,
                    state: str | None = None,
                    with_names: bool = False) -> list[Candidate]:
    init_db()
    clauses = ["sitting_id = ?"]
    args: list[Any] = [sitting_id]
    if state:
        clauses.append("state = ?")
        args.append(validate_state(state))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_exam_candidates "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY CAST(seat AS INTEGER), seat, student_id",
            args).fetchall()
    out = [_candidate_row(r) for r in rows]
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name
                 for s in _students.list_students()}
        for candidate in out:
            candidate.full_name = index.get(candidate.student_id)
    return out


def remove_candidate(sitting_id: int, student_id: str) -> bool:
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting:
        _assert_open(sitting)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_exam_candidates "
            "WHERE sitting_id = ? AND student_id = ?",
            (sitting_id, student_id.strip()))
        conn.commit()
    return bool(cur.rowcount)


def seat_candidate(sitting_id: int, student_id: str, seat: str) -> Candidate:
    """Move a candidate to a different seat."""
    return add_candidate(sitting_id, student_id, seat=seat)


def seating_plan(sitting_id: int) -> SeatingPlan:
    """The plan as printed, with anyone still unseated called out."""
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    candidates = list_candidates(sitting_id, with_names=True)
    return SeatingPlan(
        sitting=sitting,
        rows=[c for c in candidates if c.seat],
        unseated=[c for c in candidates if not c.seat])


def seating_plan_text(sitting_id: int) -> str:
    """The seating plan as printable text, with access arrangements."""
    plan = seating_plan(sitting_id)
    s = plan.sitting
    lines = [f"SEATING PLAN — {s.paper_code} {s.paper_title or ''}",
             f"{s.date}  {s.start_time}-{s.end_time or ''}"
             + (f" (latest finish {s.extended_end_time})" if s.extended_end_time else "")
             + f"  Room: {s.room or '-'}"
             + (f"  Invigilators: {s.invigilator}" if s.invigilator else ""), "",
             f"{'Seat':<6}{'Cand #':<8}{'Name':<28}{'Finish':<8}Access arrangements"]
    for c in plan.rows:
        lines.append(f"{c.seat or '':<6}{c.candidate_no or '':<8}"
                     f"{(c.full_name or c.student_id)[:27]:<28}{c.finish_time or '':<8}"
                     f"{c.access_arrangements or ''}")
    if plan.unseated:
        lines += ["", "UNSEATED:"]
        lines += [f"  {c.candidate_no or ''} {c.full_name or c.student_id}"
                  for c in plan.unseated]
    return "\n".join(lines) + "\n"


# ── Marking the register ────────────────────────────────────────────

def _assert_open(sitting: Sitting) -> None:
    if sitting.is_signed_off:
        raise ValidationError(
            f"Exam register for {sitting.label} was signed off by "
            f"{sitting.signed_off_by or '?'} — reopen it to make changes")


def mark_candidate(
    sitting_id: int,
    student_id: str,
    state: str,
    *,
    arrival_time: str | None = None,
    departure_time: str | None = None,
    absence_reason: str | None = None,
    notes: str | None = None,
    actor: str | None = None,
) -> Candidate:
    """Record what happened to one candidate.

    Giving an ``arrival_time`` with a present-ish state re-derives the
    state from the clock, so an invigilator writing down 09:47 does not
    also have to decide whether that counts as very late.
    """
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    _assert_open(sitting)
    if get_candidate(sitting_id, student_id) is None:
        raise ValidationError(
            f"{student_id} is not a candidate in this sitting")

    state = validate_state(state)
    minutes: int | None = None
    if arrival_time:
        arrival_time = reg._validate_time(arrival_time, "Arrival time")
        if state in SAT_STATES:
            state, minutes = state_for_arrival(sitting, arrival_time)
    if departure_time:
        departure_time = reg._validate_time(departure_time, "Departure time")
    reason = validate_absence_reason(absence_reason)
    if state == ABSENT and reason is None:
        reason = "Unexplained"
    if state not in (ABSENT, WITHDRAWN):
        reason = reason if state == REMOVED else None

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_exam_candidates
                  SET state = ?, arrival_time = ?, minutes_late = ?,
                      departure_time = COALESCE(?, departure_time),
                      absence_reason = ?,
                      notes = COALESCE(?, notes),
                      recorded_by = ?, recorded_at = datetime('now')
                WHERE sitting_id = ? AND student_id = ?""",
            (state, arrival_time, minutes, departure_time, reason,
             (notes or "").strip() or None, (actor or "").strip() or None,
             sitting_id, student_id.strip()))
        conn.execute(
            "UPDATE attendance_exam_sittings SET state = ? "
            "WHERE sitting_id = ? AND state = ?",
            (OPEN, sitting_id, PLANNED))
        conn.commit()
    out = get_candidate(sitting_id, student_id)
    assert out is not None
    return out


def record_arrival(sitting_id: int, student_id: str, arrival_time: str, *,
                   actor: str | None = None) -> Candidate:
    """Admit a late candidate, deriving how late from the clock."""
    return mark_candidate(sitting_id, student_id, PRESENT,
                          arrival_time=arrival_time, actor=actor)


def mark_all_present(sitting_id: int, *,
                     actor: str | None = None) -> int:
    """Mark every unmarked candidate present.

    An exam register is filled by exception: the invigilator walks the
    room, notes the empty seats, and everybody else was there.
    """
    init_db()
    marked = 0
    for candidate in list_candidates(sitting_id):
        if candidate.marked:
            continue
        mark_candidate(sitting_id, candidate.student_id, PRESENT, actor=actor)
        marked += 1
    return marked


def mark_absent(sitting_id: int, student_ids: list[str], *,
                reason: str | None = None,
                actor: str | None = None) -> int:
    """Mark the empty seats."""
    for student_id in student_ids:
        mark_candidate(sitting_id, student_id, ABSENT,
                       absence_reason=reason, actor=actor)
    return len(student_ids)


def set_absence_reason(sitting_id: int, student_id: str,
                       reason: str) -> Candidate:
    """Decide, afterwards, why a candidate was not there."""
    init_db()
    candidate = get_candidate(sitting_id, student_id)
    if candidate is None:
        raise ValidationError(
            f"{student_id} is not a candidate in this sitting")
    if candidate.state not in (ABSENT, WITHDRAWN, REMOVED):
        raise ValidationError(
            f"{student_id} was marked {candidate.state} — an absence reason "
            "does not apply")
    decided = validate_absence_reason(reason)
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_exam_candidates SET absence_reason = ? "
            "WHERE sitting_id = ? AND student_id = ?",
            (decided, sitting_id, student_id.strip()))
        conn.commit()
    out = get_candidate(sitting_id, student_id)
    assert out is not None
    return out


# ── Sign-off ────────────────────────────────────────────────────────

def sign_off(sitting_id: int, *, invigilator: str,
             notes: str | None = None,
             allow_incomplete: bool = False) -> Sitting:
    """Close the register. Refuses while any candidate is unmarked."""
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    if sitting.is_signed_off:
        raise ValidationError(f"{sitting.label} is already signed off")
    who = (invigilator or "").strip()
    if not who:
        raise ValidationError("An invigilator has to sign the register")

    candidates = list_candidates(sitting_id)
    if not candidates:
        raise ValidationError("This sitting has no candidates")
    unmarked = [c.student_id for c in candidates if not c.marked]
    if unmarked and not allow_incomplete:
        shown = ", ".join(unmarked[:5])
        more = f" (+{len(unmarked) - 5} more)" if len(unmarked) > 5 else ""
        raise ValidationError(
            f"{len(unmarked)} candidate(s) still unmarked: {shown}{more}")

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_exam_sittings
                  SET state = ?, signed_off_by = ?,
                      signed_off_at = datetime('now'),
                      invigilator = COALESCE(?, invigilator),
                      notes = COALESCE(?, notes)
                WHERE sitting_id = ?""",
            (SIGNED_OFF, who, who, (notes or "").strip() or None, sitting_id))
        conn.commit()
    logger.info("Exam register #%d signed off by %s", sitting_id, who)
    out = get_sitting(sitting_id)
    assert out is not None
    return out


def reopen(sitting_id: int, *, reason: str,
           actor: str | None = None) -> Sitting:
    """Unlock a signed-off register. The reason is mandatory and kept."""
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    if not sitting.is_signed_off:
        raise ValidationError(f"{sitting.label} is not signed off")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to reopen an exam register")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_exam_sittings
                  SET state = ?, reopen_reason = ?
                WHERE sitting_id = ?""",
            (OPEN, f"{note} ({actor})" if actor else note, sitting_id))
        conn.commit()
    logger.info("Exam register #%d reopened: %s", sitting_id, note)
    out = get_sitting(sitting_id)
    assert out is not None
    return out


# ── Reporting ───────────────────────────────────────────────────────

def summary(sitting_id: int) -> SittingSummary:
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    out = SittingSummary(sitting=sitting)
    for candidate in list_candidates(sitting_id):
        out.entered += 1
        if candidate.state == PRESENT:
            out.present += 1
        elif candidate.state == LATE:
            out.late += 1
        elif candidate.state == VERY_LATE:
            out.very_late += 1
        elif candidate.state == ABSENT:
            out.absent += 1
        elif candidate.state == WITHDRAWN:
            out.withdrawn += 1
        elif candidate.state == REMOVED:
            out.removed += 1
        else:
            out.unmarked += 1
    return out


def absentees(*, date: str | None = None, date_from: str | None = None,
              date_to: str | None = None) -> list[tuple[Sitting, Candidate]]:
    """Every candidate who missed a paper, for the morning's phone calls."""
    out: list[tuple[Sitting, Candidate]] = []
    for sitting in list_sittings(date=date, date_from=date_from,
                                 date_to=date_to):
        for candidate in list_candidates(sitting.sitting_id, state=ABSENT,
                                         with_names=True):
            out.append((sitting, candidate))
    return out


def reportable(*, date_from: str | None = None,
               date_to: str | None = None
               ) -> list[tuple[Sitting, Candidate]]:
    """Candidates the board has to be told about — very late, or removed."""
    out: list[tuple[Sitting, Candidate]] = []
    for sitting in list_sittings(date_from=date_from, date_to=date_to):
        for candidate in list_candidates(sitting.sitting_id, with_names=True):
            if candidate.reportable:
                out.append((sitting, candidate))
    return out


def student_record(student_id: str) -> list[tuple[Sitting, Candidate]]:
    """One candidate's exam attendance across every sitting."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT s.sitting_id FROM attendance_exam_sittings s
               JOIN attendance_exam_candidates c
                 ON c.sitting_id = s.sitting_id
              WHERE c.student_id = ?
              ORDER BY s.date, s.start_time""",
            (student_id.strip(),)).fetchall()
    out: list[tuple[Sitting, Candidate]] = []
    for r in rows:
        sitting = get_sitting(r["sitting_id"])
        candidate = get_candidate(r["sitting_id"], student_id)
        if sitting and candidate:
            out.append((sitting, candidate))
    return out


def unsigned_registers(*, date_from: str | None = None,
                       date_to: str | None = None) -> list[Sitting]:
    """Sittings that happened and were never signed off."""
    today = _dt.date.today().isoformat()
    return [s for s in list_sittings(date_from=date_from,
                                     date_to=date_to or today)
            if not s.is_signed_off]


def sync_to_register(sitting_id: int) -> int:
    """Write the sitting through to the college's lesson registers.

    Off by default and asked for explicitly, because a college that runs
    study leave during exams has nothing to write to. Candidates who sat
    the paper get `B` (off-site educational activity, which counts as
    attending); absentees are left for the pastoral team rather than
    being coded automatically — an exam absence is a conversation, not a
    data entry.
    """
    init_db()
    sitting = get_sitting(sitting_id)
    if sitting is None:
        raise ValidationError(f"No sitting with id {sitting_id}")
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_weeks as _weeks,
    )
    weekday = _dt.date.fromisoformat(sitting.date).weekday() + 1
    written = 0
    for candidate in list_candidates(sitting_id):
        if not candidate.sat:
            continue
        slots = [s for s in _tt.list_slots(student_id=candidate.student_id)
                 if s.day == weekday]
        for slot in _weeks.filter_slots(slots, sitting.date):
            if reg.is_locked(slot.slot_id, sitting.date):
                continue
            try:
                written += core.save_register(
                    slot.slot_id, sitting.date,
                    {candidate.student_id: {
                        "code": "B",
                        "notes": f"Exam: {sitting.paper_code}",
                        "is_offsite": True,
                        "offsite_location": sitting.room or "Exam hall",
                        "data_source": "sync"}},
                    reason=f"Sat {sitting.paper_code}", allow_retro=True)
            except ValidationError as e:
                logger.debug("Exam sync skipped slot #%d: %s", slot.slot_id, e)
    logger.info("Exam sitting #%d synced to %d lesson mark(s)",
                sitting_id, written)
    return written
