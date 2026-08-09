"""Attendance-linked bursary for the Sixth Form System.

Sibling to :mod:`attendance`, and the most sixth-form-specific thing in
the package. The 16–19 Bursary Fund pays learners directly, and almost
every college in the country makes payment conditional on attendance.
Which means somebody, every fortnight, cross-references a payment run
against an attendance report by hand.

This module does that cross-reference and keeps the result.

**Holding money is a serious act, so the design is cautious:**

* A hold is a *recommendation* until somebody confirms it
  (:func:`assess` produces decisions; :func:`apply_decision` acts on
  them). No payment is ever stopped by a sweep alone.
* Authorised absence does not cost a learner their bursary. The
  condition is on unauthorised absence, because a learner in hospital
  has not broken an agreement — and a scheme that punishes illness
  drives learners to come in ill.
* A held payment is *held*, not cancelled. :func:`release` pays it when
  attendance recovers, which is what makes the condition an incentive
  rather than a fine.
* Hardship overrides everything (:func:`add_exemption`). A learner whose
  attendance is poor *because* they cannot afford the bus is the exact
  case where withholding travel money makes attendance worse.

The threshold comes from :mod:`attendance_thresholds`
(``bursary_hold``), so a college sets it once.
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

# Bursary types, which behave differently. Vulnerable-group awards are
# a statutory entitlement and are never held on attendance grounds.
VULNERABLE: str = "Vulnerable group"
DISCRETIONARY: str = "Discretionary"
TRAVEL: str = "Travel"
MEALS: str = "Free meals"
EQUIPMENT: str = "Equipment"
AWARD_TYPES: tuple[str, ...] = (VULNERABLE, DISCRETIONARY, TRAVEL, MEALS,
                                EQUIPMENT)

# Award types that attendance conditions must never touch.
NEVER_HELD: frozenset[str] = frozenset({VULNERABLE, MEALS})

PAY: str = "Pay"
HOLD: str = "Hold"
PART_PAY: str = "Part pay"
DECISIONS: tuple[str, ...] = (PAY, HOLD, PART_PAY)

PENDING: str = "Pending"
PAID: str = "Paid"
HELD: str = "Held"
RELEASED: str = "Released"
FORFEITED: str = "Forfeited"
PAYMENT_STATES: tuple[str, ...] = (PENDING, PAID, HELD, RELEASED, FORFEITED)

# Reasons a learner is exempt from the attendance condition.
EXEMPTION_REASONS: tuple[str, ...] = (
    "Hardship", "Medical", "Young carer", "Pregnancy or parenthood",
    "Disability or SEND", "Safeguarding", "Other",
)

# How long a held payment waits before it is written off, in payment
# periods. Long enough to be recoverable, short enough to be finite.
FORFEIT_AFTER_PERIODS: int = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_bursary_awards (
    award_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    award_type   TEXT NOT NULL DEFAULT 'Discretionary',
    amount       REAL NOT NULL DEFAULT 0,
    period       TEXT NOT NULL DEFAULT 'Fortnightly',
    start_date   TEXT,
    end_date     TEXT,
    conditional  INTEGER NOT NULL DEFAULT 1,
    active       INTEGER NOT NULL DEFAULT 1,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_bursary_payments (
    payment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    award_id     INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    period_from  TEXT NOT NULL,
    period_to    TEXT NOT NULL,
    amount       REAL NOT NULL DEFAULT 0,
    attendance_pct REAL,
    threshold_pct REAL,
    decision     TEXT,
    state        TEXT NOT NULL DEFAULT 'Pending',
    decided_by   TEXT,
    decided_at   TEXT,
    released_at  TEXT,
    released_by  TEXT,
    note         TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(award_id, period_from, period_to),
    FOREIGN KEY (award_id) REFERENCES attendance_bursary_awards(award_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attendance_bursary_exemptions (
    exemption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    reason       TEXT NOT NULL,
    detail       TEXT,
    start_date   TEXT NOT NULL,
    end_date     TEXT,
    granted_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_burs_award_student
    ON attendance_bursary_awards(student_id);
CREATE INDEX IF NOT EXISTS idx_att_burs_pay_state
    ON attendance_bursary_payments(state);
CREATE INDEX IF NOT EXISTS idx_att_burs_pay_student
    ON attendance_bursary_payments(student_id, period_from);
CREATE INDEX IF NOT EXISTS idx_att_burs_exempt_student
    ON attendance_bursary_exemptions(student_id);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Award:
    """One learner's bursary entitlement."""

    award_id: int
    student_id: str
    award_type: str
    amount: float
    period: str
    start_date: str | None
    end_date: str | None
    conditional: bool
    active: bool
    notes: str | None
    created_at: str | None

    @property
    def attendance_linked(self) -> bool:
        """Whether attendance may affect this award at all."""
        return self.conditional and self.award_type not in NEVER_HELD

    @property
    def label(self) -> str:
        return (f"{self.student_id} · {self.award_type} · £{self.amount:.2f} "
                f"{self.period.lower()}"
                + ("" if self.attendance_linked else " (unconditional)"))


@dataclass
class Payment:
    """One period's payment, and what was decided about it."""

    payment_id: int
    award_id: int
    student_id: str
    period_from: str
    period_to: str
    amount: float
    attendance_pct: float | None
    threshold_pct: float | None
    decision: str | None
    state: str
    decided_by: str | None
    decided_at: str | None
    released_at: str | None
    released_by: str | None
    note: str | None
    created_at: str | None

    @property
    def is_held(self) -> bool:
        return self.state == HELD

    @property
    def label(self) -> str:
        pct = ("—" if self.attendance_pct is None
               else f"{self.attendance_pct:.1f}%")
        return (f"{self.student_id} · {self.period_from}→{self.period_to} · "
                f"£{self.amount:.2f} · {pct} · {self.state}")


@dataclass
class Exemption:
    """A learner the attendance condition does not apply to."""

    exemption_id: int
    student_id: str
    reason: str
    detail: str | None
    start_date: str
    end_date: str | None
    granted_by: str | None
    created_at: str | None

    def covers(self, date: str) -> bool:
        if date < self.start_date:
            return False
        return self.end_date is None or date <= self.end_date


@dataclass
class Assessment:
    """A recommendation about one payment. Nothing has been done."""

    student_id: str
    award: Award
    period_from: str
    period_to: str
    amount: float
    attendance_pct: float | None
    threshold_pct: float
    decision: str
    reason: str
    exempt: bool = False
    student_name: str | None = None

    @property
    def would_hold(self) -> bool:
        return self.decision == HOLD

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        pct = ("no data" if self.attendance_pct is None
               else f"{self.attendance_pct:.1f}%")
        return f"{who} · {pct} · {self.decision} — {self.reason}"


@dataclass
class RunResult:
    """A whole payment run's recommendations."""

    period_from: str
    period_to: str
    assessments: list[Assessment] = field(default_factory=list)

    @property
    def to_pay(self) -> list[Assessment]:
        return [a for a in self.assessments if a.decision == PAY]

    @property
    def to_hold(self) -> list[Assessment]:
        return [a for a in self.assessments if a.decision == HOLD]

    @property
    def total_payable(self) -> float:
        return round(sum(a.amount for a in self.to_pay), 2)

    @property
    def total_held(self) -> float:
        return round(sum(a.amount for a in self.to_hold), 2)

    @property
    def summary(self) -> str:
        return (f"{len(self.to_pay)} to pay (£{self.total_payable:.2f}), "
                f"{len(self.to_hold)} to hold (£{self.total_held:.2f})")


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
    logger.debug("Bursary schema ready at %s", DB_PATH)
    _DB_READY = True


def _award_row(r: sqlite3.Row) -> Award:
    return Award(award_id=r["award_id"], student_id=r["student_id"],
                 award_type=r["award_type"], amount=r["amount"],
                 period=r["period"], start_date=r["start_date"],
                 end_date=r["end_date"], conditional=bool(r["conditional"]),
                 active=bool(r["active"]), notes=r["notes"],
                 created_at=r["created_at"])


def _payment_row(r: sqlite3.Row) -> Payment:
    return Payment(
        payment_id=r["payment_id"], award_id=r["award_id"],
        student_id=r["student_id"], period_from=r["period_from"],
        period_to=r["period_to"], amount=r["amount"],
        attendance_pct=r["attendance_pct"], threshold_pct=r["threshold_pct"],
        decision=r["decision"], state=r["state"], decided_by=r["decided_by"],
        decided_at=r["decided_at"], released_at=r["released_at"],
        released_by=r["released_by"], note=r["note"],
        created_at=r["created_at"])


def _exemption_row(r: sqlite3.Row) -> Exemption:
    return Exemption(exemption_id=r["exemption_id"],
                     student_id=r["student_id"], reason=r["reason"],
                     detail=r["detail"], start_date=r["start_date"],
                     end_date=r["end_date"], granted_by=r["granted_by"],
                     created_at=r["created_at"])


def validate_award_type(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return DISCRETIONARY
    for award_type in AWARD_TYPES:
        if s.lower() == award_type.lower():
            return award_type
    raise ValidationError(
        f"Award type must be one of: {', '.join(AWARD_TYPES)}")


# ── Awards ──────────────────────────────────────────────────────────

def create_award(
    student_id: str,
    *,
    amount: float,
    award_type: str = DISCRETIONARY,
    period: str = "Fortnightly",
    start_date: str | None = None,
    end_date: str | None = None,
    conditional: bool = True,
    notes: str | None = None,
) -> Award:
    """Record a learner's bursary award."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    try:
        value = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValidationError("Amount must be a number") from None
    if value < 0 or value > 10000:
        raise ValidationError("Amount is out of range")
    award_type = validate_award_type(award_type)

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_bursary_awards
                   (student_id, award_type, amount, period, start_date,
                    end_date, conditional, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, award_type, value, period,
             core._validate_date(start_date) if start_date else None,
             core._validate_date(end_date) if end_date else None,
             1 if conditional else 0, (notes or "").strip() or None))
        conn.commit()
        award_id = int(cur.lastrowid or 0)
    out = get_award(award_id)
    assert out is not None
    return out


def get_award(award_id: int) -> Award | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_bursary_awards WHERE award_id = ?",
            (award_id,)).fetchone()
    return _award_row(r) if r else None


def list_awards(*, student_id: str | None = None, active_only: bool = True,
                award_type: str | None = None,
                limit: int = 500) -> list[Award]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if award_type:
        clauses.append("award_type = ?")
        args.append(validate_award_type(award_type))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_bursary_awards {where} "
            "ORDER BY student_id LIMIT ?", args).fetchall()
    return [_award_row(r) for r in rows]


def end_award(award_id: int, *, on: str | None = None) -> Award:
    init_db()
    if get_award(award_id) is None:
        raise ValidationError(f"No award with id {award_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_bursary_awards SET active = 0, end_date = ? "
            "WHERE award_id = ?",
            (core._validate_date(on or _dt.date.today().isoformat()),
             award_id))
        conn.commit()
    out = get_award(award_id)
    assert out is not None
    return out


# ── Exemptions ──────────────────────────────────────────────────────

def add_exemption(
    student_id: str,
    *,
    reason: str,
    start_date: str | None = None,
    end_date: str | None = None,
    detail: str | None = None,
    granted_by: str | None = None,
) -> Exemption:
    """Exempt a learner from the attendance condition.

    The most important function here. A learner whose attendance is poor
    because they cannot afford to travel is precisely the learner for
    whom withholding travel money makes everything worse, and a scheme
    without this escape hatch does harm.
    """
    init_db()
    if reason not in EXEMPTION_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(EXEMPTION_REASONS)}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_bursary_exemptions
                   (student_id, reason, detail, start_date, end_date,
                    granted_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (student_id.strip(), reason, (detail or "").strip() or None,
             core._validate_date(start_date or
                                 _dt.date.today().isoformat()),
             core._validate_date(end_date) if end_date else None,
             (granted_by or "").strip() or None))
        conn.commit()
        exemption_id = int(cur.lastrowid or 0)
    logger.info("Bursary exemption for %s: %s", student_id, reason)
    out = get_exemption(exemption_id)
    assert out is not None
    return out


def get_exemption(exemption_id: int) -> Exemption | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_bursary_exemptions "
            "WHERE exemption_id = ?", (exemption_id,)).fetchone()
    return _exemption_row(r) if r else None


def list_exemptions(*, student_id: str | None = None) -> list[Exemption]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_bursary_exemptions {where} "
            "ORDER BY exemption_id DESC", args).fetchall()
    return [_exemption_row(r) for r in rows]


def is_exempt(student_id: str, *, on: str | None = None) -> bool:
    date = core._validate_date(on or _dt.date.today().isoformat())
    return any(e.covers(date) for e in list_exemptions(student_id=student_id))


def remove_exemption(exemption_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_bursary_exemptions WHERE exemption_id = ?",
            (exemption_id,))
        conn.commit()
    return bool(cur.rowcount)


# ── Assessing a payment run ─────────────────────────────────────────

def _unauthorised_percentage(student_id: str, date_from: str,
                             date_to: str) -> tuple[float | None, int]:
    """Attendance counting only unauthorised absence against the learner.

    Authorised absence is excluded from the denominator entirely: a
    learner off sick for a week has not failed a condition, and a scheme
    that says otherwise teaches learners to come in ill.
    """
    summary = core.summary_for_student(student_id, date_from=date_from,
                                       date_to=date_to)
    countable = summary.total - summary.authorised
    if countable <= 0:
        return None, summary.total
    return round(100.0 * summary.attending / countable, 1), summary.total


def assess(
    *,
    period_from: str,
    period_to: str,
    threshold_pct: float | None = None,
    with_names: bool = True,
) -> RunResult:
    """Work out what should happen to each payment. Changes nothing.

    Produces recommendations for a person to look at. Nothing is held
    until :func:`apply_decision` is called on it — a payment run that
    could stop somebody's bus fare on its own is not a design anybody
    should ship.
    """
    init_db()
    period_from = core._validate_date(period_from)
    period_to = core._validate_date(period_to)
    if period_to < period_from:
        raise ValidationError("A payment period cannot end before it starts")
    threshold = (threshold_pct if threshold_pct is not None
                 else thresholds.value_of(thresholds.BURSARY_HOLD,
                                          default=85.0))
    assert threshold is not None

    result = RunResult(period_from=period_from, period_to=period_to)
    names: dict[str, str] = {}
    if with_names:
        from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
            students as _students,
        )
        names = {s.student_id: s.full_name for s in _students.list_students()}

    for award in list_awards():
        if award.start_date and award.start_date > period_to:
            continue
        if award.end_date and award.end_date < period_from:
            continue

        if not award.attendance_linked:
            result.assessments.append(Assessment(
                student_id=award.student_id, award=award,
                period_from=period_from, period_to=period_to,
                amount=award.amount, attendance_pct=None,
                threshold_pct=threshold, decision=PAY,
                reason=f"{award.award_type} is not attendance-conditional",
                student_name=names.get(award.student_id)))
            continue

        if is_exempt(award.student_id, on=period_to):
            result.assessments.append(Assessment(
                student_id=award.student_id, award=award,
                period_from=period_from, period_to=period_to,
                amount=award.amount, attendance_pct=None,
                threshold_pct=threshold, decision=PAY,
                reason="Exempt from the attendance condition", exempt=True,
                student_name=names.get(award.student_id)))
            continue

        percentage, sessions = _unauthorised_percentage(
            award.student_id, period_from, period_to)
        if percentage is None or sessions == 0:
            result.assessments.append(Assessment(
                student_id=award.student_id, award=award,
                period_from=period_from, period_to=period_to,
                amount=award.amount, attendance_pct=percentage,
                threshold_pct=threshold, decision=PAY,
                reason="No attendance data for the period — paid by default",
                student_name=names.get(award.student_id)))
            continue

        if percentage >= threshold:
            decision, reason = PAY, f"{percentage:.1f}% meets {threshold:g}%"
        else:
            decision = HOLD
            reason = (f"{percentage:.1f}% is below {threshold:g}% "
                      "(unauthorised absence only)")
        result.assessments.append(Assessment(
            student_id=award.student_id, award=award,
            period_from=period_from, period_to=period_to,
            amount=award.amount, attendance_pct=percentage,
            threshold_pct=threshold, decision=decision, reason=reason,
            student_name=names.get(award.student_id)))

    result.assessments.sort(key=lambda a: (a.decision != HOLD,
                                           a.attendance_pct or 0))
    logger.info("Bursary run %s→%s: %s", period_from, period_to,
                result.summary)
    return result


def apply_decision(
    assessment: Assessment,
    *,
    decided_by: str,
    override: str | None = None,
    note: str | None = None,
) -> Payment:
    """Commit one recommendation, or a person's override of it.

    ``override`` is how somebody pays a learner the model said to hold —
    which happens, and should, and should be recorded with a name.
    """
    init_db()
    if not (decided_by or "").strip():
        raise ValidationError("A bursary decision must name who made it")
    decision = override or assessment.decision
    if decision not in DECISIONS:
        raise ValidationError(f"Decision must be one of: {', '.join(DECISIONS)}")
    state = HELD if decision == HOLD else PAID

    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_bursary_payments
                   (award_id, student_id, period_from, period_to, amount,
                    attendance_pct, threshold_pct, decision, state,
                    decided_by, decided_at, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
               ON CONFLICT(award_id, period_from, period_to) DO UPDATE SET
                   decision = excluded.decision, state = excluded.state,
                   attendance_pct = excluded.attendance_pct,
                   decided_by = excluded.decided_by,
                   decided_at = datetime('now'),
                   note = COALESCE(excluded.note,
                                   attendance_bursary_payments.note)""",
            (assessment.award.award_id, assessment.student_id,
             assessment.period_from, assessment.period_to, assessment.amount,
             assessment.attendance_pct, assessment.threshold_pct, decision,
             state, decided_by.strip(),
             (note or assessment.reason).strip() or None))
        conn.commit()
    out = payment_for(assessment.award.award_id, assessment.period_from,
                      assessment.period_to)
    assert out is not None
    if state == HELD:
        logger.info("Bursary held for %s (%s): %s", assessment.student_id,
                    assessment.period_from, assessment.reason)
    return out


def apply_run(result: RunResult, *, decided_by: str,
              pay_only: bool = False) -> dict[str, int]:
    """Commit a whole assessed run.

    ``pay_only`` commits the payments and leaves the holds for somebody
    to look at individually, which is the cautious way to run this the
    first few times.
    """
    counts = {PAY: 0, HOLD: 0}
    for assessment in result.assessments:
        if pay_only and assessment.decision == HOLD:
            continue
        apply_decision(assessment, decided_by=decided_by)
        counts[assessment.decision] = counts.get(assessment.decision, 0) + 1
    return counts


# ── Releasing and forfeiting ────────────────────────────────────────

def release(payment_id: int, *, released_by: str,
            note: str | None = None) -> Payment:
    """Pay a held payment — attendance recovered, or somebody decided.

    The half of the scheme that makes it an incentive. A condition with
    no way back is a fine, and a fine does not change behaviour in the
    way a recoverable hold does.
    """
    init_db()
    payment = get_payment(payment_id)
    if payment is None:
        raise ValidationError(f"No payment with id {payment_id}")
    if payment.state != HELD:
        raise ValidationError(
            f"Payment #{payment_id} is {payment.state.lower()}, not held")
    if not (released_by or "").strip():
        raise ValidationError("A release must name who authorised it")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_bursary_payments
                  SET state = ?, released_at = datetime('now'),
                      released_by = ?, note = COALESCE(?, note)
                WHERE payment_id = ?""",
            (RELEASED, released_by.strip(), (note or "").strip() or None,
             payment_id))
        conn.commit()
    logger.info("Bursary payment #%d released for %s", payment_id,
                payment.student_id)
    out = get_payment(payment_id)
    assert out is not None
    return out


def release_on_recovery(
    *,
    date_from: str,
    date_to: str,
    released_by: str,
    threshold_pct: float | None = None,
) -> list[Payment]:
    """Release held payments for learners whose attendance has recovered.

    Run after each period. A learner who fixes their attendance should
    get their money back without having to ask, and certainly without
    having to know they can.
    """
    init_db()
    threshold = (threshold_pct if threshold_pct is not None
                 else thresholds.value_of(thresholds.BURSARY_HOLD,
                                          default=85.0))
    assert threshold is not None
    released: list[Payment] = []
    for payment in list_payments(state=HELD, limit=1000):
        percentage, _sessions = _unauthorised_percentage(
            payment.student_id, date_from, date_to)
        if percentage is None or percentage < threshold:
            continue
        released.append(release(
            payment.payment_id, released_by=released_by,
            note=f"Attendance recovered to {percentage:.1f}% "
                 f"({date_from}→{date_to})"))
    logger.info("Released %d held bursary payment(s) on recovery",
                len(released))
    return released


def forfeit(payment_id: int, *, reason: str, by: str) -> Payment:
    """Write a held payment off. Deliberately hard to reach."""
    init_db()
    payment = get_payment(payment_id)
    if payment is None:
        raise ValidationError(f"No payment with id {payment_id}")
    if payment.state != HELD:
        raise ValidationError("Only a held payment can be forfeited")
    note = (reason or "").strip()
    if not note or not (by or "").strip():
        raise ValidationError(
            "Forfeiting a bursary payment needs a reason and a named person")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_bursary_payments SET state = ?, note = ?, "
            "released_by = ? WHERE payment_id = ?",
            (FORFEITED, note, by.strip(), payment_id))
        conn.commit()
    out = get_payment(payment_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_payment(payment_id: int) -> Payment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_bursary_payments WHERE payment_id = ?",
            (payment_id,)).fetchone()
    return _payment_row(r) if r else None


def payment_for(award_id: int, period_from: str,
                period_to: str) -> Payment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_bursary_payments "
            "WHERE award_id = ? AND period_from = ? AND period_to = ?",
            (award_id, period_from, period_to)).fetchone()
    return _payment_row(r) if r else None


def list_payments(*, student_id: str | None = None, state: str | None = None,
                  period_from: str | None = None,
                  limit: int = 500) -> list[Payment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in PAYMENT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(PAYMENT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if period_from:
        clauses.append("period_from = ?")
        args.append(core._validate_date(period_from))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_bursary_payments {where} "
            "ORDER BY period_from DESC, student_id LIMIT ?", args).fetchall()
    return [_payment_row(r) for r in rows]


def held_payments(*, with_names: bool = True) -> list[Payment]:
    """Money currently being withheld. Should be reviewed every period."""
    return list_payments(state=HELD, limit=1000)


def held_total() -> float:
    return round(sum(p.amount for p in list_payments(state=HELD, limit=5000)),
                 2)


def student_history(student_id: str) -> list[Payment]:
    """One learner's payment history — read before any conversation."""
    return list_payments(student_id=student_id, limit=200)


def run_summary(*, period_from: str) -> dict[str, Any]:
    """What a committed run did."""
    payments = list_payments(period_from=period_from, limit=2000)
    return {
        "period_from": period_from,
        "payments": len(payments),
        "paid": sum(1 for p in payments if p.state == PAID),
        "held": sum(1 for p in payments if p.state == HELD),
        "released": sum(1 for p in payments if p.state == RELEASED),
        "amount_paid": round(sum(p.amount for p in payments
                                 if p.state in (PAID, RELEASED)), 2),
        "amount_held": round(sum(p.amount for p in payments
                                 if p.state == HELD), 2),
    }


def impact_report(*, periods: int = 6) -> dict[str, Any]:
    """Does holding money improve attendance here?

    Compares attendance in the period after a hold against the period
    that caused it. Worth running before defending the policy, and worth
    acting on if the answer is no.
    """
    init_db()
    held = [p for p in list_payments(state=RELEASED, limit=2000)][:periods * 50]
    improved = worsened = 0
    for payment in held:
        span = (_dt.date.fromisoformat(payment.period_to)
                - _dt.date.fromisoformat(payment.period_from)).days or 14
        after_from = payment.period_to
        after_to = (_dt.date.fromisoformat(payment.period_to)
                    + _dt.timedelta(days=span)).isoformat()
        after, _ = _unauthorised_percentage(payment.student_id, after_from,
                                            after_to)
        if after is None or payment.attendance_pct is None:
            continue
        if after > payment.attendance_pct:
            improved += 1
        elif after < payment.attendance_pct:
            worsened += 1
    total = improved + worsened
    return {
        "holds_reviewed": total,
        "improved": improved,
        "worsened": worsened,
        "improvement_rate": (round(100.0 * improved / total, 1)
                             if total else None),
    }
