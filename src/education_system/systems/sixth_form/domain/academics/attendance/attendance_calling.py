"""First-day calling for the Sixth Form System.

Sibling to :mod:`attendance`. A learner is marked absent at nine o'clock
with no explanation. By ten, somebody should have rung. Not because the
figure needs correcting — because on a small number of mornings a year,
the reason nobody knows where a sixteen-year-old is turns out to matter
enormously, and the only way to find out is to ask on the day.

This module builds that morning's call list and records what happened on
each call.

**Priority is the whole design.** Twenty unexplained absences and forty
minutes to work through them means the order is the decision. The list
is sorted by risk, not alphabetically: a learner with a safeguarding
flag comes before one with a pattern of Friday absence, who comes before
one who has never missed a day. :func:`priority_for` is where that
judgement lives, so it can be argued with and changed.

Absences that somebody has already explained — an absence report on
file, approved leave, a confirmed placement day — never reach the list.
Ringing a parent who phoned in at half past eight is how a college
teaches its parents that phoning in achieves nothing.
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
    attendance_thresholds as thresholds,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

PENDING: str = "Pending"
IN_PROGRESS: str = "In progress"
DONE: str = "Done"
UNREACHABLE: str = "Unreachable"
DEFERRED: str = "Deferred"
CALL_STATES: tuple[str, ...] = (PENDING, IN_PROGRESS, DONE, UNREACHABLE,
                                DEFERRED)

# What happened when somebody rang.
SPOKE_PARENT: str = "Spoke to parent"
SPOKE_STUDENT: str = "Spoke to student"
NO_ANSWER: str = "No answer"
VOICEMAIL: str = "Left voicemail"
WRONG_NUMBER: str = "Wrong number"
NO_NUMBER: str = "No number held"
ALREADY_EXPLAINED: str = "Already explained"
OUTCOMES: tuple[str, ...] = (
    SPOKE_PARENT, SPOKE_STUDENT, NO_ANSWER, VOICEMAIL, WRONG_NUMBER,
    NO_NUMBER, ALREADY_EXPLAINED,
)

# Outcomes that mean contact was actually made.
CONTACT_MADE: frozenset[str] = frozenset({
    SPOKE_PARENT, SPOKE_STUDENT, ALREADY_EXPLAINED,
})
# Outcomes that mean the number is no use.
BAD_NUMBER: frozenset[str] = frozenset({WRONG_NUMBER, NO_NUMBER})

# Priority bands, highest first.
URGENT: str = "Urgent"
HIGH: str = "High"
NORMAL: str = "Normal"
LOW: str = "Low"
PRIORITIES: tuple[str, ...] = (URGENT, HIGH, NORMAL, LOW)
_PRIORITY_RANK: dict[str, int] = {p: i for i, p in enumerate(PRIORITIES)}

# Attempts after which a learner counts as unreachable and the problem
# stops being a phone call and becomes a home visit.
MAX_ATTEMPTS: int = 3

# The hour by which the list should be clear.
TARGET_HOUR: str = "10:00"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_calls (
    call_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    priority     TEXT NOT NULL DEFAULT 'Normal',
    reason       TEXT,
    state        TEXT NOT NULL DEFAULT 'Pending',
    attempts     INTEGER NOT NULL DEFAULT 0,
    outcome      TEXT,
    contact_name TEXT,
    contact_number TEXT,
    called_by    TEXT,
    called_at    TEXT,
    notes        TEXT,
    resolved     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, date),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_call_attempts (
    attempt_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id     INTEGER NOT NULL,
    outcome     TEXT NOT NULL,
    number      TEXT,
    called_by   TEXT,
    called_at   TEXT DEFAULT (datetime('now')),
    notes       TEXT,
    FOREIGN KEY (call_id) REFERENCES attendance_calls(call_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_calls_date
    ON attendance_calls(date);
CREATE INDEX IF NOT EXISTS idx_att_calls_state
    ON attendance_calls(state);
CREATE INDEX IF NOT EXISTS idx_att_call_att_call
    ON attendance_call_attempts(call_id);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Call:
    """One learner to ring about."""

    call_id: int
    student_id: str
    date: str
    priority: str
    reason: str | None
    state: str
    attempts: int
    outcome: str | None
    contact_name: str | None
    contact_number: str | None
    called_by: str | None
    called_at: str | None
    notes: str | None
    resolved: bool
    created_at: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in (PENDING, IN_PROGRESS)

    @property
    def rank(self) -> int:
        return _PRIORITY_RANK.get(self.priority, len(PRIORITIES))

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        number = f" · {self.contact_number}" if self.contact_number else ""
        return f"[{self.priority}] {who}{number} — {self.reason or 'absent'}"


@dataclass
class Attempt:
    """One try at getting hold of somebody."""

    attempt_id: int
    call_id: int
    outcome: str
    number: str | None
    called_by: str | None
    called_at: str | None
    notes: str | None


@dataclass
class CallListResult:
    """What building the list found."""

    date: str
    created: int = 0
    already_open: int = 0
    skipped_explained: int = 0
    calls: list[Call] = field(default_factory=list)


@dataclass
class CallStats:
    """How the morning went."""

    date: str
    total: int = 0
    done: int = 0
    contact_made: int = 0
    unreachable: int = 0
    open: int = 0

    @property
    def completion_rate(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * (self.total - self.open) / self.total, 1)

    @property
    def contact_rate(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.contact_made / self.total, 1)


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
    thresholds.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calling schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Call:
    return Call(
        call_id=r["call_id"], student_id=r["student_id"], date=r["date"],
        priority=r["priority"], reason=r["reason"], state=r["state"],
        attempts=r["attempts"], outcome=r["outcome"],
        contact_name=r["contact_name"], contact_number=r["contact_number"],
        called_by=r["called_by"], called_at=r["called_at"], notes=r["notes"],
        resolved=bool(r["resolved"]), created_at=r["created_at"])


def validate_outcome(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        raise ValidationError("A call needs an outcome")
    for outcome in OUTCOMES:
        if s.lower() == outcome.lower():
            return outcome
    raise ValidationError(f"Outcome must be one of: {', '.join(OUTCOMES)}")


# ── Working out who to ring ─────────────────────────────────────────

def _already_explained(student_id: str, date: str) -> str | None:
    """Whether anybody has already accounted for this absence."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_absence_reports as _reports,
        )
        if _reports.explained(student_id, date):
            return "An absence report is on file"
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Absence-report lookup unavailable", exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_leave as _leave,
        )
        if any(r.student_id == student_id for r in _leave.on_leave(date)):
            return "Approved leave"
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Leave lookup unavailable", exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_placements as _placements,
        )
        if any(d.student_id == student_id
               for d in _placements.on_placement(date)):
            return "On a work placement"
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Placement lookup unavailable", exc_info=True)
    return None


def _safeguarding_flag(student_id: str) -> bool:
    """Whether this learner is known to the safeguarding team."""
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_safeguarding as _safeguarding,
        )
        return _safeguarding.is_flagged(student_id)
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Safeguarding lookup unavailable", exc_info=True)
        return False


def _recent_attendance(student_id: str, *, days: int = 42) -> float | None:
    """A rough recent percentage, for ranking rather than reporting."""
    date_to = _dt.date.today()
    date_from = date_to - _dt.timedelta(days=days)
    summary = core.summary_for_student(
        student_id, date_from=date_from.isoformat(),
        date_to=date_to.isoformat())
    return summary.percentage


def priority_for(student_id: str, date: str) -> tuple[str, str]:
    """How urgently this absence needs a phone call, and why.

    The ordering that decides which twenty calls get made before the
    morning runs out. Deliberately explicit rather than a score: the
    reason travels with the priority so the person ringing knows what
    they are ringing about.
    """
    if _safeguarding_flag(student_id):
        return URGENT, "Known to safeguarding"

    severe = thresholds.value_of(thresholds.SEVERE_ABSENCE, default=50.0)
    persistent = thresholds.value_of(thresholds.PERSISTENT_ABSENCE,
                                     default=90.0)
    percentage = _recent_attendance(student_id)
    if percentage is not None and severe is not None and percentage <= severe:
        return URGENT, f"Severe absence ({percentage:.0f}% recently)"

    yesterday = (_dt.date.fromisoformat(core._validate_date(date))
                 - _dt.timedelta(days=1)).isoformat()
    consecutive = any(
        codes.is_unauthorised_absence(r.code)
        for r in core.list_records(student_id=student_id, date=yesterday))
    if consecutive:
        return HIGH, "Second day of unexplained absence"

    if percentage is not None and persistent is not None \
            and percentage <= persistent:
        return HIGH, f"Persistent absence ({percentage:.0f}% recently)"

    if percentage is not None and percentage >= 97:
        # Out of character, which is its own kind of signal.
        return NORMAL, "Unexplained, and unusual for this learner"
    return NORMAL, "Unexplained absence"


def _contact_for(student_id: str) -> tuple[str | None, str | None]:
    """The best number to try, and whose it is.

    The primary contact first, then anyone with parental responsibility,
    then anybody at all — and the learner's own number only as a last
    resort, since a learner who is not where they should be is not
    reliably going to answer it.
    """
    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (  # noqa: E501
            parent_contacts as _contacts,
        )
        rows = _contacts.contacts_for_student(student_id)
        ordered = sorted(
            rows,
            key=lambda c: (not c.is_primary,
                           not c.has_parental_responsibility,
                           not c.is_emergency_contact))
        for contact in ordered:
            number = contact.primary_phone or contact.secondary_phone
            if number:
                return contact.full_name, number
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Parent-contact lookup unavailable", exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
            students as _students,
        )
        student = _students.get_student(student_id)
        number = getattr(student, "phone", None) if student else None
        return (student.full_name if student else None), number
    except Exception:                       # pragma: no cover - defensive
        return None, None


# ── Building the list ───────────────────────────────────────────────

def build_list(*, date: str | None = None,
               include_authorised: bool = False) -> CallListResult:
    """Build today's call list from the register.

    Unexplained absence only, by default: an absence somebody has
    already coded as illness is not a mystery, and ringing about it
    wastes the one hour that matters.
    """
    init_db()
    date = core._validate_date(date or _dt.date.today().isoformat())
    result = CallListResult(date=date)

    candidates: dict[str, str] = {}
    for record in core.list_records(date=date):
        if record.voided:
            continue
        if codes.is_unauthorised_absence(record.code):
            candidates.setdefault(record.student_id, record.code or "N")
        elif include_authorised and codes.is_absence(record.code):
            candidates.setdefault(record.student_id, record.code or "C")

    for student_id in sorted(candidates):
        explanation = _already_explained(student_id, date)
        if explanation:
            result.skipped_explained += 1
            continue
        existing = call_for(student_id, date)
        if existing is not None:
            result.already_open += 1
            result.calls.append(existing)
            continue
        priority, reason = priority_for(student_id, date)
        name, number = _contact_for(student_id)
        with _connect() as conn:
            conn.execute(
                """INSERT INTO attendance_calls
                       (student_id, date, priority, reason, state,
                        contact_name, contact_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, date) DO NOTHING""",
                (student_id, date, priority, reason, PENDING, name, number))
            conn.commit()
        created = call_for(student_id, date)
        if created is not None:
            result.created += 1
            result.calls.append(created)

    result.calls.sort(key=lambda c: (c.rank, c.student_id))
    logger.info("Call list for %s: %d new, %d already open, %d explained",
                date, result.created, result.already_open,
                result.skipped_explained)
    return result


def call_list(*, date: str | None = None, open_only: bool = True,
              with_names: bool = True) -> list[Call]:
    """Today's list, most urgent first."""
    date = core._validate_date(date or _dt.date.today().isoformat())
    out = list_calls(date=date)
    if open_only:
        out = [c for c in out if c.is_open]
    out.sort(key=lambda c: (c.rank, c.student_id))
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for call in out:
            call.student_name = index.get(call.student_id)
    return out


# ── Logging a call ──────────────────────────────────────────────────

def log_call(
    call_id: int,
    outcome: str,
    *,
    called_by: str | None = None,
    notes: str | None = None,
    number: str | None = None,
    resolves: bool | None = None,
) -> Call:
    """Record what happened on one attempt.

    Contact made closes the call. No answer leaves it open and bumps the
    attempt count; past :data:`MAX_ATTEMPTS` it becomes unreachable,
    which is a different problem needing a different response.
    """
    init_db()
    call = get_call(call_id)
    if call is None:
        raise ValidationError(f"No call with id {call_id}")
    outcome = validate_outcome(outcome)
    attempts = call.attempts + 1

    if resolves is None:
        resolves = outcome in CONTACT_MADE
    if resolves:
        state = DONE
    elif attempts >= MAX_ATTEMPTS or outcome in BAD_NUMBER:
        state = UNREACHABLE
    else:
        state = IN_PROGRESS

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_call_attempts
                   (call_id, outcome, number, called_by, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (call_id, outcome, (number or call.contact_number),
             (called_by or "").strip() or None,
             (notes or "").strip() or None))
        conn.execute(
            """UPDATE attendance_calls
                  SET state = ?, attempts = ?, outcome = ?,
                      called_by = ?, called_at = datetime('now'),
                      resolved = ?,
                      notes = CASE WHEN ? = '' THEN notes
                                   ELSE COALESCE(notes || '; ', '') || ? END
                WHERE call_id = ?""",
            (state, attempts, outcome, (called_by or "").strip() or None,
             1 if resolves else 0, (notes or "").strip(),
             (notes or "").strip(), call_id))
        conn.commit()
    logger.info("Call #%d: %s (%s)", call_id, outcome, state)
    out = get_call(call_id)
    assert out is not None
    return out


def defer(call_id: int, *, reason: str,
          actor: str | None = None) -> Call:
    """Park a call — the learner is known to be on a trip, say."""
    init_db()
    if get_call(call_id) is None:
        raise ValidationError(f"No call with id {call_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to defer a call")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_calls SET state = ?, called_by = ?, "
            "notes = COALESCE(notes || '; ', '') || ? WHERE call_id = ?",
            (DEFERRED, (actor or "").strip() or None,
             f"Deferred: {note}", call_id))
        conn.commit()
    out = get_call(call_id)
    assert out is not None
    return out


def record_explanation(
    call_id: int,
    *,
    reason_text: str,
    called_by: str | None = None,
    code: str | None = None,
) -> Call:
    """The call produced an explanation — file it as an absence report.

    Closes the loop: the reason given on the phone becomes a report in
    :mod:`attendance_absence_reports`, which somebody codes, rather than
    a note in a call log nobody reads.
    """
    init_db()
    call = get_call(call_id)
    if call is None:
        raise ValidationError(f"No call with id {call_id}")
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_absence_reports as _reports,
        )
        report = _reports.report_absence(
            call.student_id, call.date, channel=_reports.PHONE,
            reported_by=_reports.PARENT,
            reporter_name=call.contact_name,
            reason_text=reason_text,
            message=f"Given during first-day calling by {called_by or '?'}")
        if code:
            _reports.accept(report.report_id, code=code,
                            decided_by=called_by,
                            note="Explained during first-day calling")
    except Exception as e:                  # pragma: no cover - optional dep
        logger.warning("Could not file absence report from call #%d: %s",
                       call_id, e)
    return log_call(call_id, SPOKE_PARENT, called_by=called_by,
                    notes=reason_text, resolves=True)


# ── Reads ───────────────────────────────────────────────────────────

def get_call(call_id: int) -> Call | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_calls WHERE call_id = ?",
            (call_id,)).fetchone()
    return _row(r) if r else None


def call_for(student_id: str, date: str) -> Call | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_calls WHERE student_id = ? AND date = ?",
            (student_id.strip(), core._validate_date(date))).fetchone()
    return _row(r) if r else None


def list_calls(*, date: str | None = None, date_from: str | None = None,
               date_to: str | None = None, state: str | None = None,
               priority: str | None = None, student_id: str | None = None,
               limit: int = 500) -> list[Call]:
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
        if state not in CALL_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(CALL_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if priority:
        if priority not in PRIORITIES:
            raise ValidationError(
                f"Priority must be one of: {', '.join(PRIORITIES)}")
        clauses.append("priority = ?")
        args.append(priority)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_calls {where} "
            "ORDER BY date DESC, call_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def attempts_for(call_id: int) -> list[Attempt]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_call_attempts WHERE call_id = ? "
            "ORDER BY attempt_id", (call_id,)).fetchall()
    return [Attempt(attempt_id=r["attempt_id"], call_id=r["call_id"],
                    outcome=r["outcome"], number=r["number"],
                    called_by=r["called_by"], called_at=r["called_at"],
                    notes=r["notes"]) for r in rows]


def stats(*, date: str | None = None) -> CallStats:
    """How the morning went."""
    date = core._validate_date(date or _dt.date.today().isoformat())
    out = CallStats(date=date)
    for call in list_calls(date=date):
        out.total += 1
        if call.state == DONE:
            out.done += 1
        elif call.state == UNREACHABLE:
            out.unreachable += 1
        elif call.is_open:
            out.open += 1
        if call.outcome in CONTACT_MADE:
            out.contact_made += 1
    return out


def unreachable(*, date_from: str | None = None,
                date_to: str | None = None) -> list[Call]:
    """Learners nobody could get hold of.

    Repeated appearances here are the referral list: a family the
    college cannot contact is a safeguarding matter long before it is an
    attendance one.
    """
    return list_calls(state=UNREACHABLE, date_from=date_from,
                      date_to=date_to)


def repeat_unreachable(*, days: int = 30,
                       minimum: int = 2) -> list[tuple[str, int]]:
    """Learners unreachable more than once lately, most often first."""
    since = (_dt.date.today() - _dt.timedelta(days=max(1, days))).isoformat()
    counts: dict[str, int] = {}
    for call in unreachable(date_from=since):
        counts[call.student_id] = counts.get(call.student_id, 0) + 1
    out = [(sid, n) for sid, n in counts.items() if n >= max(1, minimum)]
    out.sort(key=lambda item: -item[1])
    return out


def outcome_breakdown(*, date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """What calls are actually achieving."""
    out: dict[str, int] = {}
    for call in list_calls(date_from=date_from, date_to=date_to, limit=5000):
        if call.outcome:
            out[call.outcome] = out.get(call.outcome, 0) + 1
    return out
