"""Attendance mark appeals for the Sixth Form System.

Sibling to :mod:`attendance`. A register is taken by a person under
time pressure in front of thirty people, and sometimes it is wrong. The
learner who was in the room and marked absent has, at present, exactly
one route: find the teacher, hope they remember, hope they get round to
it. That is not a process, and its failure mode is a learner deciding
the figure is nonsense and disengaging from it entirely.

So an appeal is a record. A learner disputes a mark, says what they say
happened, and it goes to their tutor. The tutor upholds it — which
recodes the mark through the ordinary amendment path, so the change
carries a reason and an author — or rejects it, which is also recorded.
Either way there is an answer and a date.

**The upheld rate is the interesting number.** One appeal is a
correction. A teaching group with a quarter of its marks successfully
appealed does not have honest learners, it has a register nobody is
taking properly, and :func:`upheld_rate` is where that becomes visible.

Appeals have a deadline (:data:`APPEAL_WINDOW_DAYS`) for the same reason
the retro-marking window exists: a mark disputed four months later
cannot be checked against anybody's memory.
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
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

SUBMITTED: str = "Submitted"
UNDER_REVIEW: str = "Under review"
UPHELD: str = "Upheld"
REJECTED: str = "Rejected"
WITHDRAWN: str = "Withdrawn"
STATES: tuple[str, ...] = (SUBMITTED, UNDER_REVIEW, UPHELD, REJECTED,
                           WITHDRAWN)

OPEN_STATES: frozenset[str] = frozenset({SUBMITTED, UNDER_REVIEW})

# What the learner says happened.
WAS_PRESENT: str = "I was there"
WAS_LATE_NOT_ABSENT: str = "I was late, not absent"
WRONG_LEARNER: str = "That was not me"
HAD_PERMISSION: str = "I had permission"
REASON_NOT_RECORDED: str = "My reason was not recorded"
OTHER: str = "Other"
GROUNDS: tuple[str, ...] = (
    WAS_PRESENT, WAS_LATE_NOT_ABSENT, WRONG_LEARNER, HAD_PERMISSION,
    REASON_NOT_RECORDED, OTHER,
)

# The code an upheld appeal defaults to, per ground.
DEFAULT_OUTCOME_CODE: dict[str, str] = {
    WAS_PRESENT: "/",
    WAS_LATE_NOT_ABSENT: "L",
    WRONG_LEARNER: "/",
    HAD_PERMISSION: "C",
    REASON_NOT_RECORDED: "C",
    OTHER: "C",
}

# Days after the marked date within which an appeal can be lodged.
APPEAL_WINDOW_DAYS: int = 14

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_appeals (
    appeal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id     INTEGER NOT NULL,
    student_id    TEXT NOT NULL,
    date          TEXT NOT NULL,
    slot_id       INTEGER,
    disputed_code TEXT,
    grounds       TEXT NOT NULL DEFAULT 'Other',
    statement     TEXT,
    submitted_by  TEXT,
    submitted_at  TEXT DEFAULT (datetime('now')),
    assigned_to   TEXT,
    state         TEXT NOT NULL DEFAULT 'Submitted',
    outcome_code  TEXT,
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT,
    UNIQUE(record_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_appeal_state
    ON attendance_appeals(state);
CREATE INDEX IF NOT EXISTS idx_att_appeal_student
    ON attendance_appeals(student_id);
CREATE INDEX IF NOT EXISTS idx_att_appeal_assigned
    ON attendance_appeals(assigned_to);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Appeal:
    """One disputed mark."""

    appeal_id: int
    record_id: int
    student_id: str
    date: str
    slot_id: int | None
    disputed_code: str | None
    grounds: str
    statement: str | None
    submitted_by: str | None
    submitted_at: str | None
    assigned_to: str | None
    state: str
    outcome_code: str | None
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    @property
    def days_waiting(self) -> int:
        if not self.submitted_at:
            return 0
        try:
            lodged = _dt.date.fromisoformat(self.submitted_at[:10])
        except ValueError:                  # pragma: no cover - defensive
            return 0
        return (_dt.date.today() - lodged).days

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who} · {self.date} · {self.disputed_code or '?'} "
                f"disputed — {self.grounds}")


@dataclass
class AppealStats:
    """How appeals are going, for one scope."""

    total: int = 0
    upheld: int = 0
    rejected: int = 0
    open: int = 0

    @property
    def decided(self) -> int:
        return self.upheld + self.rejected

    @property
    def upheld_rate(self) -> float | None:
        """Share of decided appeals that were upheld.

        A high figure is not a compliment to the appeals process — it
        says the marks being appealed were wrong.
        """
        if self.decided == 0:
            return None
        return round(100.0 * self.upheld / self.decided, 1)


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
    logger.debug("Appeal schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Appeal:
    return Appeal(
        appeal_id=r["appeal_id"], record_id=r["record_id"],
        student_id=r["student_id"], date=r["date"], slot_id=r["slot_id"],
        disputed_code=r["disputed_code"], grounds=r["grounds"],
        statement=r["statement"], submitted_by=r["submitted_by"],
        submitted_at=r["submitted_at"], assigned_to=r["assigned_to"],
        state=r["state"], outcome_code=r["outcome_code"],
        decided_by=r["decided_by"], decided_at=r["decided_at"],
        decision_note=r["decision_note"])


def validate_grounds(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return OTHER
    for ground in GROUNDS:
        if s.lower() == ground.lower():
            return ground
    raise ValidationError(f"Grounds must be one of: {', '.join(GROUNDS)}")


# ── Lodging ─────────────────────────────────────────────────────────

def _tutor_for(student_id: str) -> str | None:
    """The learner's tutor, if the tutor-group module knows one."""
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (  # noqa: E501
            tutor_groups as _tg,
        )
        group = _tg.group_for_student(student_id)
        return group.tutor if group else None
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Tutor lookup unavailable", exc_info=True)
        return None


def lodge(
    record_id: int,
    *,
    grounds: str = OTHER,
    statement: str | None = None,
    submitted_by: str | None = None,
    assigned_to: str | None = None,
    on: str | None = None,
) -> Appeal:
    """A learner disputes a mark.

    Refused outside the appeal window, and refused for a mark that is
    already being disputed — a second appeal against the same row is a
    complaint about the first one's answer, which is a different
    conversation.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No attendance record with id {record_id}")
    if record.voided:
        raise ValidationError(
            "That mark has already been voided — there is nothing to appeal")
    grounds = validate_grounds(grounds)

    today = core._validate_date(on or _dt.date.today().isoformat())
    age = (_dt.date.fromisoformat(today)
           - _dt.date.fromisoformat(record.date)).days
    if age > APPEAL_WINDOW_DAYS:
        raise ValidationError(
            f"That mark is {age} days old; appeals close after "
            f"{APPEAL_WINDOW_DAYS} days. Raise it with your tutor instead")

    existing = for_record(record_id)
    if existing is not None and existing.is_open:
        raise ValidationError(
            f"Appeal #{existing.appeal_id} against that mark is already "
            f"{existing.state.lower()}")

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_appeals
                   (record_id, student_id, date, slot_id, disputed_code,
                    grounds, statement, submitted_by, assigned_to, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(record_id) DO UPDATE SET
                   grounds = excluded.grounds,
                   statement = excluded.statement,
                   submitted_by = excluded.submitted_by,
                   submitted_at = datetime('now'),
                   assigned_to = excluded.assigned_to,
                   state = excluded.state,
                   outcome_code = NULL,
                   decided_by = NULL,
                   decided_at = NULL,
                   decision_note = NULL""",
            (record_id, record.student_id, record.date, record.slot_id,
             record.code, grounds, (statement or "").strip() or None,
             (submitted_by or "").strip() or record.student_id,
             (assigned_to or "").strip() or _tutor_for(record.student_id),
             SUBMITTED))
        conn.commit()
    logger.info("Appeal lodged against record #%d (%s, %s)", record_id,
                record.student_id, record.date)
    out = for_record(record_id)
    assert out is not None
    return out


def assign(appeal_id: int, to: str) -> Appeal:
    """Route an appeal to whoever will decide it."""
    init_db()
    if get_appeal(appeal_id) is None:
        raise ValidationError(f"No appeal with id {appeal_id}")
    who = (to or "").strip()
    if not who:
        raise ValidationError("An appeal has to be assigned to somebody")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_appeals SET assigned_to = ?, state = ? "
            "WHERE appeal_id = ? AND state IN (?, ?)",
            (who, UNDER_REVIEW, appeal_id, SUBMITTED, UNDER_REVIEW))
        conn.commit()
    out = get_appeal(appeal_id)
    assert out is not None
    return out


# ── Deciding ────────────────────────────────────────────────────────

def uphold(
    appeal_id: int,
    *,
    decided_by: str,
    code: str | None = None,
    note: str | None = None,
) -> Appeal:
    """Agree with the learner and recode the mark.

    Routed through :func:`attendance_codes.set_code`, so the correction
    lands in the amendment trail with the decider's name — the appeal
    and the mark's history end up telling the same story.
    """
    init_db()
    appeal = get_appeal(appeal_id)
    if appeal is None:
        raise ValidationError(f"No appeal with id {appeal_id}")
    if not appeal.is_open:
        raise ValidationError(
            f"Appeal #{appeal_id} was already {appeal.state.lower()}")
    if not (decided_by or "").strip():
        raise ValidationError("An appeal has to be decided by somebody named")

    outcome = (codes.validate_code(code) if code
               else DEFAULT_OUTCOME_CODE.get(appeal.grounds, "/"))
    codes.set_code(
        appeal.record_id, outcome, actor=decided_by,
        note=f"Appeal upheld: {appeal.grounds}"
             + (f" — {note}" if note else ""))

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_appeals
                  SET state = ?, outcome_code = ?, decided_by = ?,
                      decided_at = datetime('now'), decision_note = ?
                WHERE appeal_id = ?""",
            (UPHELD, outcome, decided_by.strip(),
             (note or "").strip() or None, appeal_id))
        conn.commit()
    logger.info("Appeal #%d upheld: record #%d recoded to %s", appeal_id,
                appeal.record_id, outcome)
    out = get_appeal(appeal_id)
    assert out is not None
    return out


def reject(appeal_id: int, *, decided_by: str, reason: str) -> Appeal:
    """Disagree with the learner. The mark stands, and the reason is kept.

    The reason is mandatory: an appeal turned down without one is
    indistinguishable from an appeal nobody read, and the learner will
    correctly treat it as such.
    """
    init_db()
    appeal = get_appeal(appeal_id)
    if appeal is None:
        raise ValidationError(f"No appeal with id {appeal_id}")
    if not appeal.is_open:
        raise ValidationError(
            f"Appeal #{appeal_id} was already {appeal.state.lower()}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to reject an appeal")
    if not (decided_by or "").strip():
        raise ValidationError("An appeal has to be decided by somebody named")

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_appeals
                  SET state = ?, decided_by = ?, decided_at = datetime('now'),
                      decision_note = ?
                WHERE appeal_id = ?""",
            (REJECTED, decided_by.strip(), note, appeal_id))
        conn.commit()
    out = get_appeal(appeal_id)
    assert out is not None
    return out


def withdraw(appeal_id: int, *, reason: str | None = None) -> Appeal:
    """The learner drops it."""
    init_db()
    appeal = get_appeal(appeal_id)
    if appeal is None:
        raise ValidationError(f"No appeal with id {appeal_id}")
    if not appeal.is_open:
        raise ValidationError(
            f"Appeal #{appeal_id} was already {appeal.state.lower()}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_appeals SET state = ?, "
            "decided_at = datetime('now'), decision_note = ? "
            "WHERE appeal_id = ?",
            (WITHDRAWN, (reason or "").strip() or None, appeal_id))
        conn.commit()
    out = get_appeal(appeal_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_appeal(appeal_id: int) -> Appeal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_appeals WHERE appeal_id = ?",
            (appeal_id,)).fetchone()
    return _row(r) if r else None


def for_record(record_id: int) -> Appeal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_appeals WHERE record_id = ?",
            (record_id,)).fetchone()
    return _row(r) if r else None


def list_appeals(*, student_id: str | None = None, state: str | None = None,
                 assigned_to: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 open_only: bool = False,
                 limit: int = 200) -> list[Appeal]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if open_only:
        clauses.append("state IN (?, ?)")
        args.extend([SUBMITTED, UNDER_REVIEW])
    elif state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if assigned_to:
        clauses.append("assigned_to = ?")
        args.append(assigned_to.strip())
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_appeals {where} "
            "ORDER BY submitted_at, appeal_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def queue(*, assigned_to: str | None = None,
          with_names: bool = True) -> list[Appeal]:
    """Appeals waiting on a decision, longest-waiting first."""
    out = list_appeals(open_only=True, assigned_to=assigned_to)
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for appeal in out:
            appeal.student_name = index.get(appeal.student_id)
    return out


def overdue(*, days: int = 5) -> list[Appeal]:
    """Open appeals nobody has answered within a reasonable time."""
    return [a for a in queue() if a.days_waiting > max(0, days)]


def stats(*, date_from: str | None = None, date_to: str | None = None,
          slot_id: int | None = None) -> AppealStats:
    """How appeals are going. Watch the upheld rate, not the count."""
    out = AppealStats()
    for appeal in list_appeals(date_from=date_from, date_to=date_to,
                               limit=5000):
        if slot_id is not None and appeal.slot_id != slot_id:
            continue
        out.total += 1
        if appeal.state == UPHELD:
            out.upheld += 1
        elif appeal.state == REJECTED:
            out.rejected += 1
        elif appeal.is_open:
            out.open += 1
    return out


def upheld_rate(*, slot_id: int | None = None,
                date_from: str | None = None,
                date_to: str | None = None) -> float | None:
    """Shorthand for the number that says whether marking is trustworthy."""
    return stats(date_from=date_from, date_to=date_to,
                 slot_id=slot_id).upheld_rate


def by_slot(*, date_from: str | None = None,
            date_to: str | None = None,
            min_appeals: int = 3) -> list[tuple[int, AppealStats]]:
    """Slots attracting appeals, worst upheld rate first.

    A register that keeps being successfully appealed is not a discipline
    problem; it is a marking problem, and this is the list that finds it.
    """
    grouped: dict[int, AppealStats] = {}
    for appeal in list_appeals(date_from=date_from, date_to=date_to,
                               limit=5000):
        if appeal.slot_id is None:
            continue
        entry = grouped.setdefault(appeal.slot_id, AppealStats())
        entry.total += 1
        if appeal.state == UPHELD:
            entry.upheld += 1
        elif appeal.state == REJECTED:
            entry.rejected += 1
        elif appeal.is_open:
            entry.open += 1
    out = [(slot, entry) for slot, entry in grouped.items()
           if entry.total >= max(1, min_appeals)]
    out.sort(key=lambda item: -(item[1].upheld_rate or 0))
    return out
