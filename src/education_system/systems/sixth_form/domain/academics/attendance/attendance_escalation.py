"""Attendance escalation, contracts and meetings for the Sixth Form System.

Sibling to :mod:`attendance_concerns`. That module records *that* there
is a concern. This one records what is being done about it, by whom, and
by when — the three things a flat concern list cannot hold, and the
three things anybody reviewing a case actually asks for.

Three related records:

* **Stages** — the ladder a case climbs: tutor conversation, tutor
  meeting, head-of-year meeting, formal review, referral. Each stage has
  an owner and a review date, and a case sitting past its review date
  with nothing recorded is the single most useful list in the module
  (:func:`overdue_reviews`).
* **Contracts** — an attendance agreement with a target, a period and a
  review. Its whole value is that it can be measured afterwards:
  :func:`contract_progress` compares attendance since the contract was
  signed against the target, so "did it work" is a fact rather than an
  impression.
* **Meetings** — who was in the room, what was agreed, what happened
  next. Attached to the case, so the history reads in order.

**Nothing escalates itself.** :func:`suggest_stage` will say what the
ladder implies, but moving a case is always somebody's decision with
their name on it. Automatic escalation produces cases nobody owns.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# The ladder, in order. Each rung is a real thing somebody does.
TUTOR_CONVERSATION: str = "Tutor conversation"
TUTOR_MEETING: str = "Tutor meeting"
HEAD_OF_YEAR: str = "Head of year meeting"
FORMAL_REVIEW: str = "Formal review"
REFERRAL: str = "External referral"
STAGES: tuple[str, ...] = (TUTOR_CONVERSATION, TUTOR_MEETING, HEAD_OF_YEAR,
                           FORMAL_REVIEW, REFERRAL)
_STAGE_RANK: dict[str, int] = {s: i for i, s in enumerate(STAGES)}

# Attendance bands that suggest each stage. Read from thresholds so a
# college that moves its figures moves the ladder with them.
_STAGE_THRESHOLD: dict[str, str] = {
    TUTOR_CONVERSATION: thresholds.LETTER_1,
    TUTOR_MEETING: thresholds.LETTER_2,
    HEAD_OF_YEAR: thresholds.LETTER_3,
    FORMAL_REVIEW: thresholds.PERSISTENT_ABSENCE,
    REFERRAL: thresholds.SEVERE_ABSENCE,
}

OPEN: str = "Open"
MONITORING: str = "Monitoring"
CLOSED: str = "Closed"
CASE_STATES: tuple[str, ...] = (OPEN, MONITORING, CLOSED)

# Contract lifecycle.
ACTIVE: str = "Active"
MET: str = "Met"
NOT_MET: str = "Not met"
ABANDONED: str = "Abandoned"
CONTRACT_STATES: tuple[str, ...] = (ACTIVE, MET, NOT_MET, ABANDONED)

# Meeting kinds.
MEETING_KINDS: tuple[str, ...] = (
    "Tutor meeting", "Head of year meeting", "Formal review",
    "Parent meeting", "Multi-agency", "Phone call", "Other",
)

# Days a stage runs before it wants reviewing.
DEFAULT_REVIEW_DAYS: int = 14

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_cases (
    case_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    stage        TEXT NOT NULL DEFAULT 'Tutor conversation',
    state        TEXT NOT NULL DEFAULT 'Open',
    owner        TEXT,
    opened_on    TEXT NOT NULL,
    opened_by    TEXT,
    review_on    TEXT,
    baseline_pct REAL,
    concern_id   INTEGER,
    summary      TEXT,
    closed_on    TEXT,
    closed_by    TEXT,
    outcome      TEXT,
    updated_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_case_stages (
    entry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id    INTEGER NOT NULL,
    stage      TEXT NOT NULL,
    owner      TEXT,
    entered_on TEXT NOT NULL,
    entered_by TEXT,
    review_on  TEXT,
    note       TEXT,
    FOREIGN KEY (case_id) REFERENCES attendance_cases(case_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_contracts (
    contract_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      INTEGER,
    student_id   TEXT NOT NULL,
    target_pct   REAL NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    review_on    TEXT,
    baseline_pct REAL,
    terms        TEXT,
    support      TEXT,
    signed_by_student INTEGER NOT NULL DEFAULT 0,
    signed_by_guardian INTEGER NOT NULL DEFAULT 0,
    signed_by_staff TEXT,
    state        TEXT NOT NULL DEFAULT 'Active',
    outcome_pct  REAL,
    closed_on    TEXT,
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_meetings (
    meeting_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER,
    student_id  TEXT NOT NULL,
    date        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'Tutor meeting',
    attendees   TEXT,
    notes       TEXT,
    actions     TEXT,
    outcome     TEXT,
    next_review TEXT,
    recorded_by TEXT,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_case_student
    ON attendance_cases(student_id);
CREATE INDEX IF NOT EXISTS idx_att_case_state
    ON attendance_cases(state);
CREATE INDEX IF NOT EXISTS idx_att_case_review
    ON attendance_cases(review_on);
CREATE INDEX IF NOT EXISTS idx_att_contract_student
    ON attendance_contracts(student_id);
CREATE INDEX IF NOT EXISTS idx_att_meeting_student
    ON attendance_meetings(student_id, date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Case:
    """One learner's attendance case, at whatever stage it has reached."""

    case_id: int
    student_id: str
    stage: str
    state: str
    owner: str | None
    opened_on: str
    opened_by: str | None
    review_on: str | None
    baseline_pct: float | None
    concern_id: int | None
    summary: str | None
    closed_on: str | None
    closed_by: str | None
    outcome: str | None
    updated_at: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in (OPEN, MONITORING)

    @property
    def stage_number(self) -> int:
        return _STAGE_RANK.get(self.stage, 0) + 1

    def is_overdue(self, *, on: str | None = None) -> bool:
        if not self.review_on or not self.is_open:
            return False
        return self.review_on < (on or _dt.date.today().isoformat())

    @property
    def days_open(self) -> int:
        return (_dt.date.today()
                - _dt.date.fromisoformat(self.opened_on)).days

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who} · stage {self.stage_number} ({self.stage}) · "
                f"{self.owner or 'unowned'}")


@dataclass
class StageEntry:
    """One rung of the ladder, as it was climbed."""

    entry_id: int
    case_id: int
    stage: str
    owner: str | None
    entered_on: str
    entered_by: str | None
    review_on: str | None
    note: str | None


@dataclass
class Contract:
    """An attendance agreement with a measurable target."""

    contract_id: int
    case_id: int | None
    student_id: str
    target_pct: float
    start_date: str
    end_date: str
    review_on: str | None
    baseline_pct: float | None
    terms: str | None
    support: str | None
    signed_by_student: bool
    signed_by_guardian: bool
    signed_by_staff: str | None
    state: str
    outcome_pct: float | None
    closed_on: str | None
    note: str | None
    created_at: str | None

    @property
    def fully_signed(self) -> bool:
        return bool(self.signed_by_student and self.signed_by_staff)

    @property
    def is_active(self) -> bool:
        return self.state == ACTIVE

    @property
    def label(self) -> str:
        return (f"{self.student_id} · target {self.target_pct:g}% "
                f"({self.start_date} → {self.end_date}) [{self.state}]")


@dataclass
class ContractProgress:
    """Whether a contract is being kept."""

    contract: Contract
    achieved_pct: float | None
    days_elapsed: int
    days_total: int

    @property
    def on_track(self) -> bool | None:
        if self.achieved_pct is None:
            return None
        return self.achieved_pct >= self.contract.target_pct

    @property
    def gap(self) -> float | None:
        if self.achieved_pct is None:
            return None
        return round(self.achieved_pct - self.contract.target_pct, 1)

    @property
    def elapsed_share(self) -> float:
        if self.days_total <= 0:
            return 1.0
        return min(1.0, self.days_elapsed / self.days_total)

    @property
    def label(self) -> str:
        achieved = ("—" if self.achieved_pct is None
                    else f"{self.achieved_pct:.1f}%")
        return (f"{achieved} against {self.contract.target_pct:g}% "
                f"({self.days_elapsed}/{self.days_total} days)")


@dataclass
class Meeting:
    """One meeting, and what came out of it."""

    meeting_id: int
    case_id: int | None
    student_id: str
    date: str
    kind: str
    attendees: str | None
    notes: str | None
    actions: str | None
    outcome: str | None
    next_review: str | None
    recorded_by: str | None
    recorded_at: str | None


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
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Escalation schema ready at %s", DB_PATH)
    _DB_READY = True


def _case_row(r: sqlite3.Row) -> Case:
    return Case(
        case_id=r["case_id"], student_id=r["student_id"], stage=r["stage"],
        state=r["state"], owner=r["owner"], opened_on=r["opened_on"],
        opened_by=r["opened_by"], review_on=r["review_on"],
        baseline_pct=r["baseline_pct"], concern_id=r["concern_id"],
        summary=r["summary"], closed_on=r["closed_on"],
        closed_by=r["closed_by"], outcome=r["outcome"],
        updated_at=r["updated_at"])


def _contract_row(r: sqlite3.Row) -> Contract:
    return Contract(
        contract_id=r["contract_id"], case_id=r["case_id"],
        student_id=r["student_id"], target_pct=r["target_pct"],
        start_date=r["start_date"], end_date=r["end_date"],
        review_on=r["review_on"], baseline_pct=r["baseline_pct"],
        terms=r["terms"], support=r["support"],
        signed_by_student=bool(r["signed_by_student"]),
        signed_by_guardian=bool(r["signed_by_guardian"]),
        signed_by_staff=r["signed_by_staff"], state=r["state"],
        outcome_pct=r["outcome_pct"], closed_on=r["closed_on"],
        note=r["note"], created_at=r["created_at"])


def _meeting_row(r: sqlite3.Row) -> Meeting:
    return Meeting(
        meeting_id=r["meeting_id"], case_id=r["case_id"],
        student_id=r["student_id"], date=r["date"], kind=r["kind"],
        attendees=r["attendees"], notes=r["notes"], actions=r["actions"],
        outcome=r["outcome"], next_review=r["next_review"],
        recorded_by=r["recorded_by"], recorded_at=r["recorded_at"])


def validate_stage(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return TUTOR_CONVERSATION
    for stage in STAGES:
        if s.lower() == stage.lower():
            return stage
    raise ValidationError(f"Stage must be one of: {', '.join(STAGES)}")


def validate_meeting_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return MEETING_KINDS[0]
    for kind in MEETING_KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(MEETING_KINDS)}")


# ── Cases ───────────────────────────────────────────────────────────

def _current_percentage(student_id: str, *, days: int = 42) -> float | None:
    date_to = _dt.date.today()
    date_from = date_to - _dt.timedelta(days=days)
    return core.summary_for_student(student_id,
                                    date_from=date_from.isoformat(),
                                    date_to=date_to.isoformat()).percentage


def suggest_stage(student_id: str, *,
                  year_group: int | None = None) -> str | None:
    """What the ladder implies for this learner's current figure.

    A suggestion, never an action. Somebody decides whether a case moves,
    and their name goes on it — an automatically escalated case is one
    nobody owns and nobody works.
    """
    percentage = _current_percentage(student_id)
    if percentage is None:
        return None
    suggested = None
    for stage in STAGES:
        key = _STAGE_THRESHOLD.get(stage)
        if key and thresholds.is_breached(key, percentage,
                                          year_group=year_group):
            suggested = stage
    return suggested


def open_case(
    student_id: str,
    *,
    stage: str = TUTOR_CONVERSATION,
    owner: str | None = None,
    opened_by: str | None = None,
    review_days: int = DEFAULT_REVIEW_DAYS,
    summary: str | None = None,
    concern_id: int | None = None,
    on: str | None = None,
) -> Case:
    """Open a case, or return the one already open for this learner."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    existing = open_case_for(student.student_id)
    if existing is not None:
        return existing

    stage = validate_stage(stage)
    today = core._validate_date(on or _dt.date.today().isoformat())
    review = (_dt.date.fromisoformat(today)
              + _dt.timedelta(days=max(1, review_days))).isoformat()
    baseline = _current_percentage(student.student_id)

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_cases
                   (student_id, stage, state, owner, opened_on, opened_by,
                    review_on, baseline_pct, concern_id, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, stage, OPEN, (owner or "").strip() or None,
             today, (opened_by or "").strip() or None, review, baseline,
             concern_id, (summary or "").strip() or None))
        conn.commit()
        case_id = int(cur.lastrowid or 0)
    _log_stage(case_id, stage, owner=owner, entered_by=opened_by,
               entered_on=today, review_on=review, note="Case opened")
    logger.info("Attendance case #%d opened for %s at %s", case_id,
                student.student_id, stage)
    out = get_case(case_id)
    assert out is not None
    return out


def _log_stage(case_id: int, stage: str, *, owner: str | None,
               entered_by: str | None, entered_on: str,
               review_on: str | None, note: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_case_stages
                   (case_id, stage, owner, entered_on, entered_by,
                    review_on, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, stage, (owner or "").strip() or None, entered_on,
             (entered_by or "").strip() or None, review_on,
             (note or "").strip() or None))
        conn.commit()


def escalate(
    case_id: int,
    *,
    to: str | None = None,
    owner: str | None = None,
    actor: str | None = None,
    review_days: int = DEFAULT_REVIEW_DAYS,
    note: str | None = None,
) -> Case:
    """Move a case up the ladder. Somebody's decision, with their name."""
    init_db()
    case = get_case(case_id)
    if case is None:
        raise ValidationError(f"No case with id {case_id}")
    if not case.is_open:
        raise ValidationError(f"Case #{case_id} is closed")

    if to is None:
        index = _STAGE_RANK.get(case.stage, 0) + 1
        if index >= len(STAGES):
            raise ValidationError(
                f"Case #{case_id} is already at {case.stage}, the top of the "
                "ladder")
        stage = STAGES[index]
    else:
        stage = validate_stage(to)
        if _STAGE_RANK[stage] <= _STAGE_RANK.get(case.stage, 0):
            raise ValidationError(
                f"{stage} is not above {case.stage} — use set_stage to move "
                "a case back down deliberately")

    today = _dt.date.today().isoformat()
    review = (_dt.date.today()
              + _dt.timedelta(days=max(1, review_days))).isoformat()
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cases
                  SET stage = ?, owner = COALESCE(?, owner), review_on = ?,
                      state = ?, updated_at = datetime('now')
                WHERE case_id = ?""",
            (stage, (owner or "").strip() or None, review, OPEN, case_id))
        conn.commit()
    _log_stage(case_id, stage, owner=owner or case.owner, entered_by=actor,
               entered_on=today, review_on=review, note=note)
    logger.info("Case #%d escalated to %s by %s", case_id, stage,
                actor or "?")
    out = get_case(case_id)
    assert out is not None
    return out


def set_stage(case_id: int, stage: str, *, actor: str | None = None,
              owner: str | None = None, note: str | None = None,
              review_days: int = DEFAULT_REVIEW_DAYS) -> Case:
    """Move a case to any stage, including back down.

    De-escalation is a real event — a learner whose attendance recovers
    should visibly come back down the ladder rather than staying at
    formal review because nobody had a way to move them.
    """
    init_db()
    case = get_case(case_id)
    if case is None:
        raise ValidationError(f"No case with id {case_id}")
    stage = validate_stage(stage)
    review = (_dt.date.today()
              + _dt.timedelta(days=max(1, review_days))).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_cases SET stage = ?, owner = COALESCE(?, owner),"
            " review_on = ?, updated_at = datetime('now') WHERE case_id = ?",
            (stage, (owner or "").strip() or None, review, case_id))
        conn.commit()
    _log_stage(case_id, stage, owner=owner or case.owner, entered_by=actor,
               entered_on=_dt.date.today().isoformat(), review_on=review,
               note=note or "Stage changed")
    out = get_case(case_id)
    assert out is not None
    return out


def set_review(case_id: int, review_on: str) -> Case:
    """Push the review date — a meeting moved, a learner is off sick."""
    init_db()
    if get_case(case_id) is None:
        raise ValidationError(f"No case with id {case_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_cases SET review_on = ?, "
            "updated_at = datetime('now') WHERE case_id = ?",
            (core._validate_date(review_on), case_id))
        conn.commit()
    out = get_case(case_id)
    assert out is not None
    return out


def close_case(case_id: int, *, outcome: str,
               closed_by: str | None = None) -> Case:
    """Close a case with a stated outcome."""
    init_db()
    case = get_case(case_id)
    if case is None:
        raise ValidationError(f"No case with id {case_id}")
    note = (outcome or "").strip()
    if not note:
        raise ValidationError("A case needs an outcome to be closed")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_cases
                  SET state = ?, closed_on = ?, closed_by = ?, outcome = ?,
                      updated_at = datetime('now')
                WHERE case_id = ?""",
            (CLOSED, _dt.date.today().isoformat(),
             (closed_by or "").strip() or None, note, case_id))
        conn.commit()
    out = get_case(case_id)
    assert out is not None
    return out


def get_case(case_id: int) -> Case | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM attendance_cases WHERE case_id = ?",
                         (case_id,)).fetchone()
    return _case_row(r) if r else None


def open_case_for(student_id: str) -> Case | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_cases WHERE student_id = ? "
            "AND state IN (?, ?) ORDER BY case_id DESC LIMIT 1",
            (student_id.strip(), OPEN, MONITORING)).fetchone()
    return _case_row(r) if r else None


def list_cases(*, student_id: str | None = None, state: str | None = None,
               stage: str | None = None, owner: str | None = None,
               open_only: bool = False, limit: int = 200) -> list[Case]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if open_only:
        clauses.append("state IN (?, ?)")
        args.extend([OPEN, MONITORING])
    elif state:
        if state not in CASE_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(CASE_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if stage:
        clauses.append("stage = ?")
        args.append(validate_stage(stage))
    if owner:
        clauses.append("owner = ?")
        args.append(owner.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_cases {where} "
            "ORDER BY review_on, case_id LIMIT ?", args).fetchall()
    return [_case_row(r) for r in rows]


def stage_history(case_id: int) -> list[StageEntry]:
    """How this case got to where it is."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_case_stages WHERE case_id = ? "
            "ORDER BY entry_id", (case_id,)).fetchall()
    return [StageEntry(entry_id=r["entry_id"], case_id=r["case_id"],
                       stage=r["stage"], owner=r["owner"],
                       entered_on=r["entered_on"], entered_by=r["entered_by"],
                       review_on=r["review_on"], note=r["note"])
            for r in rows]


def overdue_reviews(*, on: str | None = None,
                    with_names: bool = True) -> list[Case]:
    """Open cases past their review date.

    The most useful list here. A case with an owner and a date that has
    quietly slipped is worse than no case at all — it looks like
    somebody is dealing with it.
    """
    today = core._validate_date(on or _dt.date.today().isoformat())
    out = [c for c in list_cases(open_only=True, limit=1000)
           if c.is_overdue(on=today)]
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for case in out:
            case.student_name = index.get(case.student_id)
    out.sort(key=lambda c: (c.review_on or "", -c.stage_number))
    return out


def caseload(owner: str) -> list[Case]:
    """Everything one person is carrying."""
    return list_cases(owner=owner, open_only=True)


def stage_counts() -> dict[str, int]:
    """How many open cases sit at each rung."""
    out = {stage: 0 for stage in STAGES}
    for case in list_cases(open_only=True, limit=2000):
        out[case.stage] = out.get(case.stage, 0) + 1
    return out


# ── Contracts ───────────────────────────────────────────────────────

def create_contract(
    student_id: str,
    *,
    target_pct: float,
    start_date: str,
    end_date: str,
    case_id: int | None = None,
    terms: str | None = None,
    support: str | None = None,
    review_on: str | None = None,
    signed_by_staff: str | None = None,
) -> Contract:
    """Agree an attendance target for a fixed period.

    ``support`` is not decoration: a contract that asks a learner to
    improve without recording what the college is doing to help is a
    warning with a signature line, and it does not work.
    """
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    try:
        target = float(target_pct)
    except (TypeError, ValueError):
        raise ValidationError("Target must be a number") from None
    if not (0 < target <= 100):
        raise ValidationError("Target must be between 1 and 100")
    start_date = core._validate_date(start_date)
    end_date = core._validate_date(end_date)
    if end_date <= start_date:
        raise ValidationError("A contract must end after it starts")

    baseline = _current_percentage(student.student_id)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_contracts
                   (case_id, student_id, target_pct, start_date, end_date,
                    review_on, baseline_pct, terms, support, signed_by_staff,
                    state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, student.student_id, round(target, 1), start_date,
             end_date, core._validate_date(review_on) if review_on else None,
             baseline, (terms or "").strip() or None,
             (support or "").strip() or None,
             (signed_by_staff or "").strip() or None, ACTIVE))
        conn.commit()
        contract_id = int(cur.lastrowid or 0)
    logger.info("Attendance contract #%d for %s: %g%% to %s", contract_id,
                student.student_id, target, end_date)
    out = get_contract(contract_id)
    assert out is not None
    return out


def sign_contract(contract_id: int, *, by_student: bool = False,
                  by_guardian: bool = False,
                  by_staff: str | None = None) -> Contract:
    """Record a signature."""
    init_db()
    contract = get_contract(contract_id)
    if contract is None:
        raise ValidationError(f"No contract with id {contract_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_contracts
                  SET signed_by_student = MAX(signed_by_student, ?),
                      signed_by_guardian = MAX(signed_by_guardian, ?),
                      signed_by_staff = COALESCE(?, signed_by_staff)
                WHERE contract_id = ?""",
            (1 if by_student else 0, 1 if by_guardian else 0,
             (by_staff or "").strip() or None, contract_id))
        conn.commit()
    out = get_contract(contract_id)
    assert out is not None
    return out


def contract_progress(contract_id: int, *,
                      on: str | None = None) -> ContractProgress:
    """How the learner is doing against the target, so far.

    Measured from the contract's start date, not from the learner's
    whole year: the point of a contract is what has happened since it
    was signed, and a full-year figure buries that under the months that
    caused it.
    """
    init_db()
    contract = get_contract(contract_id)
    if contract is None:
        raise ValidationError(f"No contract with id {contract_id}")
    today = core._validate_date(on or _dt.date.today().isoformat())
    measure_to = min(today, contract.end_date)
    summary = core.summary_for_student(contract.student_id,
                                       date_from=contract.start_date,
                                       date_to=measure_to)
    days_total = (_dt.date.fromisoformat(contract.end_date)
                  - _dt.date.fromisoformat(contract.start_date)).days
    days_elapsed = max(0, (_dt.date.fromisoformat(measure_to)
                           - _dt.date.fromisoformat(contract.start_date)).days)
    return ContractProgress(contract=contract,
                            achieved_pct=summary.percentage,
                            days_elapsed=days_elapsed,
                            days_total=max(1, days_total))


def close_contract(contract_id: int, *, note: str | None = None,
                   on: str | None = None) -> Contract:
    """Settle a contract as met or not met, from the actual figure."""
    init_db()
    progress = contract_progress(contract_id, on=on)
    state = MET if progress.on_track else NOT_MET
    if progress.achieved_pct is None:
        state = ABANDONED
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_contracts
                  SET state = ?, outcome_pct = ?, closed_on = ?, note = ?
                WHERE contract_id = ?""",
            (state, progress.achieved_pct, _dt.date.today().isoformat(),
             (note or "").strip() or None, contract_id))
        conn.commit()
    logger.info("Contract #%d closed as %s (%s)", contract_id, state,
                progress.label)
    out = get_contract(contract_id)
    assert out is not None
    return out


def get_contract(contract_id: int) -> Contract | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_contracts WHERE contract_id = ?",
            (contract_id,)).fetchone()
    return _contract_row(r) if r else None


def list_contracts(*, student_id: str | None = None,
                   state: str | None = None, case_id: int | None = None,
                   limit: int = 200) -> list[Contract]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in CONTRACT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(CONTRACT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if case_id is not None:
        clauses.append("case_id = ?")
        args.append(case_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_contracts {where} "
            "ORDER BY contract_id DESC LIMIT ?", args).fetchall()
    return [_contract_row(r) for r in rows]


def contracts_due_review(*, on: str | None = None) -> list[Contract]:
    """Live contracts past their review date, or past their end date."""
    today = core._validate_date(on or _dt.date.today().isoformat())
    return [c for c in list_contracts(state=ACTIVE, limit=1000)
            if (c.review_on and c.review_on <= today) or c.end_date <= today]


def contract_effectiveness(*, date_from: str | None = None,
                           date_to: str | None = None) -> dict[str, Any]:
    """Do contracts work here?

    The question a college should be able to answer about its own
    intervention and almost never can. Compares the figure at signing
    with the figure at close, across every settled contract.
    """
    init_db()
    settled = [c for c in list_contracts(limit=2000)
               if c.state in (MET, NOT_MET) and c.outcome_pct is not None
               and c.baseline_pct is not None]
    if date_from:
        settled = [c for c in settled if c.start_date >= date_from]
    if date_to:
        settled = [c for c in settled if c.start_date <= date_to]
    if not settled:
        return {"contracts": 0, "met": 0, "average_change": None,
                "improved": 0}
    changes = [c.outcome_pct - c.baseline_pct for c in settled]
    return {
        "contracts": len(settled),
        "met": sum(1 for c in settled if c.state == MET),
        "met_rate": round(100.0 * sum(1 for c in settled if c.state == MET)
                          / len(settled), 1),
        "average_change": round(sum(changes) / len(changes), 1),
        "improved": sum(1 for change in changes if change > 0),
    }


# ── Meetings ────────────────────────────────────────────────────────

def log_meeting(
    student_id: str,
    date: str,
    *,
    kind: str = "Tutor meeting",
    case_id: int | None = None,
    attendees: str | None = None,
    notes: str | None = None,
    actions: str | None = None,
    outcome: str | None = None,
    next_review: str | None = None,
    recorded_by: str | None = None,
) -> Meeting:
    """Record a meeting. Updates the case's review date if one is given."""
    init_db()
    date = core._validate_date(date)
    kind = validate_meeting_kind(kind)
    if next_review:
        next_review = core._validate_date(next_review)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_meetings
                   (case_id, student_id, date, kind, attendees, notes,
                    actions, outcome, next_review, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, student_id.strip(), date, kind,
             (attendees or "").strip() or None,
             (notes or "").strip() or None,
             (actions or "").strip() or None,
             (outcome or "").strip() or None, next_review,
             (recorded_by or "").strip() or None))
        conn.commit()
        meeting_id = int(cur.lastrowid or 0)
    if case_id is not None and next_review:
        set_review(case_id, next_review)
    out = get_meeting(meeting_id)
    assert out is not None
    return out


def get_meeting(meeting_id: int) -> Meeting | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_meetings WHERE meeting_id = ?",
            (meeting_id,)).fetchone()
    return _meeting_row(r) if r else None


def list_meetings(*, student_id: str | None = None,
                  case_id: int | None = None, kind: str | None = None,
                  date_from: str | None = None, date_to: str | None = None,
                  limit: int = 200) -> list[Meeting]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if case_id is not None:
        clauses.append("case_id = ?")
        args.append(case_id)
    if kind:
        clauses.append("kind = ?")
        args.append(validate_meeting_kind(kind))
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
            f"SELECT * FROM attendance_meetings {where} "
            "ORDER BY date DESC, meeting_id DESC LIMIT ?", args).fetchall()
    return [_meeting_row(r) for r in rows]


def case_file(student_id: str) -> dict[str, Any]:
    """Everything on one learner, in the order it happened.

    What somebody reads before a meeting, instead of opening four
    screens and assembling it from memory.
    """
    init_db()
    cases = list_cases(student_id=student_id, limit=50)
    return {
        "student_id": student_id,
        "cases": cases,
        "stages": [entry for case in cases
                   for entry in stage_history(case.case_id)],
        "contracts": list_contracts(student_id=student_id),
        "meetings": list_meetings(student_id=student_id),
        "current_percentage": _current_percentage(student_id),
        "suggested_stage": suggest_stage(student_id),
    }
