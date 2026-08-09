"""Attendance rewards for the Sixth Form System.

Sibling to :mod:`attendance`. Everything else in this package is built
around absence: chasing it, coding it, escalating it, writing home about
it. A learner with 97% attendance never appears in any of it, which
means the only attendance message the college ever sends is a negative
one, and it sends it only to the people already struggling.

Rewards fix the asymmetry. Two kinds, and the second matters more:

* **Attainment** — full attendance over a period. Easy to compute, easy
  to award, and only ever reaches learners for whom attendance was never
  difficult.
* **Improvement** — a meaningful gain on the previous period. The one
  that reaches the learner who went from 71% to 84%, which is a much
  harder thing to do than staying at 100% and is the behaviour a college
  actually wants to reinforce.

:func:`nominate` produces candidates; a person confirms them. Certificates
are rendered through the shared certificates feature where it is
available, and fall back to plain text where it is not, so a reward run
never fails because a template is missing.

**Nobody is nominated twice for the same period.** An award that arrives
repeatedly stops being an award.
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

FULL_ATTENDANCE: str = "Full attendance"
HIGH_ATTENDANCE: str = "High attendance"
MOST_IMPROVED: str = "Most improved"
PUNCTUALITY: str = "Punctuality"
SUSTAINED: str = "Sustained improvement"
AWARD_KINDS: tuple[str, ...] = (FULL_ATTENDANCE, HIGH_ATTENDANCE,
                                MOST_IMPROVED, PUNCTUALITY, SUSTAINED)

NOMINATED: str = "Nominated"
AWARDED: str = "Awarded"
ISSUED: str = "Issued"
DECLINED: str = "Declined"
STATES: tuple[str, ...] = (NOMINATED, AWARDED, ISSUED, DECLINED)

# What "high" means when it is not 100%.
HIGH_ATTENDANCE_PCT: float = 97.0

# A learner has to have enough sessions in the window for the figure to
# mean anything — 100% of three lessons is not an achievement.
MIN_SESSIONS: int = 10

# Sustained improvement: gain held across this many consecutive periods.
SUSTAINED_PERIODS: int = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_awards (
    award_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    period_from  TEXT NOT NULL,
    period_to    TEXT NOT NULL,
    period_label TEXT,
    percentage   REAL,
    improvement  REAL,
    state        TEXT NOT NULL DEFAULT 'Nominated',
    citation     TEXT,
    nominated_by TEXT,
    nominated_at TEXT DEFAULT (datetime('now')),
    awarded_by   TEXT,
    awarded_at   TEXT,
    issued_at    TEXT,
    certificate_ref TEXT,
    note         TEXT,
    UNIQUE(student_id, kind, period_from, period_to),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_award_state
    ON attendance_awards(state);
CREATE INDEX IF NOT EXISTS idx_att_award_student
    ON attendance_awards(student_id);
CREATE INDEX IF NOT EXISTS idx_att_award_period
    ON attendance_awards(period_from, period_to);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Award:
    """One reward, from nomination to certificate."""

    award_id: int
    student_id: str
    kind: str
    period_from: str
    period_to: str
    period_label: str | None
    percentage: float | None
    improvement: float | None
    state: str
    citation: str | None
    nominated_by: str | None
    nominated_at: str | None
    awarded_by: str | None
    awarded_at: str | None
    issued_at: str | None
    certificate_ref: str | None
    note: str | None
    student_name: str | None = None

    @property
    def is_open(self) -> bool:
        return self.state in (NOMINATED, AWARDED)

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        detail = ""
        if self.kind == MOST_IMPROVED and self.improvement is not None:
            detail = f" (+{self.improvement:.1f} points)"
        elif self.percentage is not None:
            detail = f" ({self.percentage:.1f}%)"
        return f"{who} — {self.kind}{detail}"


@dataclass
class Candidate:
    """Somebody who has earned a reward but not yet been given one."""

    student_id: str
    kind: str
    percentage: float | None
    improvement: float | None
    sessions: int
    citation: str
    student_name: str | None = None

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return f"{who} — {self.kind}: {self.citation}"


@dataclass
class NominationResult:
    period_from: str
    period_to: str
    candidates: list[Candidate] = field(default_factory=list)
    skipped_existing: int = 0

    def of_kind(self, kind: str) -> list[Candidate]:
        return [c for c in self.candidates if c.kind == kind]

    @property
    def summary(self) -> str:
        by_kind: dict[str, int] = {}
        for candidate in self.candidates:
            by_kind[candidate.kind] = by_kind.get(candidate.kind, 0) + 1
        parts = ", ".join(f"{n} {kind.lower()}"
                          for kind, n in sorted(by_kind.items()))
        return parts or "nobody eligible"


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
    logger.debug("Attendance award schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Award:
    return Award(
        award_id=r["award_id"], student_id=r["student_id"], kind=r["kind"],
        period_from=r["period_from"], period_to=r["period_to"],
        period_label=r["period_label"], percentage=r["percentage"],
        improvement=r["improvement"], state=r["state"],
        citation=r["citation"], nominated_by=r["nominated_by"],
        nominated_at=r["nominated_at"], awarded_by=r["awarded_by"],
        awarded_at=r["awarded_at"], issued_at=r["issued_at"],
        certificate_ref=r["certificate_ref"], note=r["note"])


def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for kind in AWARD_KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(AWARD_KINDS)}")


# ── Nominating ──────────────────────────────────────────────────────

def _previous_window(date_from: str, date_to: str) -> tuple[str, str]:
    span = (_dt.date.fromisoformat(date_to)
            - _dt.date.fromisoformat(date_from)).days or 1
    previous_to = (_dt.date.fromisoformat(date_from)
                   - _dt.timedelta(days=1)).isoformat()
    previous_from = (_dt.date.fromisoformat(previous_to)
                     - _dt.timedelta(days=span)).isoformat()
    return previous_from, previous_to


def nominate(
    *,
    period_from: str,
    period_to: str,
    period_label: str | None = None,
    group_id: int | None = None,
    min_sessions: int = MIN_SESSIONS,
    with_names: bool = True,
) -> NominationResult:
    """Work out who has earned what. Awards nothing.

    A learner can earn more than one — full attendance and best
    punctuality are different achievements — but never the same one
    twice for the same period.
    """
    init_db()
    period_from = core._validate_date(period_from)
    period_to = core._validate_date(period_to)
    if period_to < period_from:
        raise ValidationError("A period cannot end before it starts")
    result = NominationResult(period_from=period_from, period_to=period_to)

    reward_pct = thresholds.value_of(thresholds.REWARD_ATTENDANCE,
                                     default=100.0) or 100.0
    improvement_pts = thresholds.value_of(thresholds.REWARD_IMPROVEMENT,
                                          default=5.0) or 5.0
    previous_from, previous_to = _previous_window(period_from, period_to)

    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    wanted: set[str] | None = None
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        wanted = set(_cg.list_members(group_id))

    for student in _students.list_students():
        if wanted is not None and student.student_id not in wanted:
            continue
        if getattr(student, "status", "Active") not in ("Active", None):
            continue
        summary = core.summary_for_student(student.student_id,
                                           date_from=period_from,
                                           date_to=period_to)
        if summary.total < max(1, min_sessions) or summary.percentage is None:
            continue
        name = student.full_name if with_names else None

        earned: list[Candidate] = []
        if summary.percentage >= reward_pct:
            earned.append(Candidate(
                student_id=student.student_id, kind=FULL_ATTENDANCE,
                percentage=summary.percentage, improvement=None,
                sessions=summary.total, student_name=name,
                citation=f"{summary.percentage:.0f}% attendance across "
                         f"{summary.total} lessons"))
        elif summary.percentage >= HIGH_ATTENDANCE_PCT:
            earned.append(Candidate(
                student_id=student.student_id, kind=HIGH_ATTENDANCE,
                percentage=summary.percentage, improvement=None,
                sessions=summary.total, student_name=name,
                citation=f"{summary.percentage:.1f}% attendance"))

        previous = core.summary_for_student(student.student_id,
                                            date_from=previous_from,
                                            date_to=previous_to)
        if previous.total >= max(1, min_sessions) \
                and previous.percentage is not None:
            gain = round(summary.percentage - previous.percentage, 1)
            if gain >= improvement_pts:
                earned.append(Candidate(
                    student_id=student.student_id, kind=MOST_IMPROVED,
                    percentage=summary.percentage, improvement=gain,
                    sessions=summary.total, student_name=name,
                    citation=f"attendance up {gain:.1f} points, from "
                             f"{previous.percentage:.1f}% to "
                             f"{summary.percentage:.1f}%"))

        if summary.late == 0 and summary.attending == summary.total:
            earned.append(Candidate(
                student_id=student.student_id, kind=PUNCTUALITY,
                percentage=summary.percentage, improvement=None,
                sessions=summary.total, student_name=name,
                citation=f"present and on time for all {summary.total} "
                         "lessons"))

        for candidate in earned:
            if _already_nominated(candidate.student_id, candidate.kind,
                                  period_from, period_to):
                result.skipped_existing += 1
                continue
            result.candidates.append(candidate)

    result.candidates.sort(key=lambda c: (c.kind, -(c.improvement or 0),
                                          -(c.percentage or 0)))
    logger.info("Reward nominations %s→%s: %s", period_from, period_to,
                result.summary)
    return result


def _already_nominated(student_id: str, kind: str, period_from: str,
                       period_to: str) -> bool:
    with _connect() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS n FROM attendance_awards
                WHERE student_id = ? AND kind = ? AND period_from = ?
                  AND period_to = ?""",
            (student_id, kind, period_from, period_to)).fetchone()
    return bool(r["n"])


def most_improved(
    *,
    period_from: str,
    period_to: str,
    top: int = 10,
    group_id: int | None = None,
) -> list[Candidate]:
    """The biggest gains, ranked.

    The list to read out in assembly. Deliberately separate from
    :func:`nominate` so it can be produced without committing anything.
    """
    result = nominate(period_from=period_from, period_to=period_to,
                      group_id=group_id)
    ranked = sorted(result.of_kind(MOST_IMPROVED),
                    key=lambda c: -(c.improvement or 0))
    return ranked[:max(1, top)]


# ── Awarding ────────────────────────────────────────────────────────

def record(
    candidate: Candidate,
    *,
    period_from: str,
    period_to: str,
    period_label: str | None = None,
    nominated_by: str | None = None,
) -> Award:
    """Store a nomination for somebody to confirm."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO attendance_awards
                   (student_id, kind, period_from, period_to, period_label,
                    percentage, improvement, state, citation, nominated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, kind, period_from, period_to)
               DO NOTHING""",
            (candidate.student_id, candidate.kind,
             core._validate_date(period_from), core._validate_date(period_to),
             (period_label or "").strip() or None, candidate.percentage,
             candidate.improvement, NOMINATED, candidate.citation,
             (nominated_by or "").strip() or None))
        conn.commit()
    out = award_for(candidate.student_id, candidate.kind, period_from,
                    period_to)
    assert out is not None
    return out


def record_all(result: NominationResult, *, period_label: str | None = None,
               nominated_by: str | None = None) -> list[Award]:
    """Store a whole nomination run."""
    return [record(candidate, period_from=result.period_from,
                   period_to=result.period_to, period_label=period_label,
                   nominated_by=nominated_by)
            for candidate in result.candidates]


def confirm(award_id: int, *, awarded_by: str,
            note: str | None = None) -> Award:
    """Confirm a nomination — it is now an award."""
    init_db()
    award = get_award(award_id)
    if award is None:
        raise ValidationError(f"No award with id {award_id}")
    if award.state != NOMINATED:
        raise ValidationError(
            f"Award #{award_id} is already {award.state.lower()}")
    if not (awarded_by or "").strip():
        raise ValidationError("An award needs somebody to give it")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_awards
                  SET state = ?, awarded_by = ?, awarded_at = datetime('now'),
                      note = COALESCE(?, note)
                WHERE award_id = ?""",
            (AWARDED, awarded_by.strip(), (note or "").strip() or None,
             award_id))
        conn.commit()
    out = get_award(award_id)
    assert out is not None
    return out


def confirm_all(*, awarded_by: str,
                period_from: str | None = None) -> int:
    """Confirm every outstanding nomination in one go."""
    confirmed = 0
    for award in list_awards(state=NOMINATED, period_from=period_from,
                             limit=2000):
        confirm(award.award_id, awarded_by=awarded_by)
        confirmed += 1
    return confirmed


def decline(award_id: int, *, reason: str) -> Award:
    """Turn a nomination down — the figure was wrong, or the learner
    would rather not be named publicly."""
    init_db()
    if get_award(award_id) is None:
        raise ValidationError(f"No award with id {award_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to decline a nomination")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_awards SET state = ?, note = ? "
            "WHERE award_id = ?", (DECLINED, note, award_id))
        conn.commit()
    out = get_award(award_id)
    assert out is not None
    return out


# ── Certificates ────────────────────────────────────────────────────

def citation_text(award: Award) -> str:
    """The words on the certificate."""
    who = award.student_name or award.student_id
    period = award.period_label or f"{award.period_from} to {award.period_to}"
    return (f"Awarded to {who}\n"
            f"for {award.kind.lower()}\n"
            f"{award.citation or ''}\n"
            f"{period}").strip()


def issue_certificate(award_id: int, *, issued_by: str | None = None) -> Award:
    """Produce the certificate and mark the award issued.

    Renders through the shared certificates feature when it is
    available, and records a plain-text citation when it is not — a
    reward run should never fail because a template is missing.
    """
    init_db()
    award = get_award(award_id)
    if award is None:
        raise ValidationError(f"No award with id {award_id}")
    if award.state == NOMINATED:
        raise ValidationError(
            f"Award #{award_id} has not been confirmed yet")

    reference = None
    try:
        from education_system.platform.features.certificates.certificate_service import (  # noqa: E501
            CertificateService,
        )
        # The shared service already has an `attendance` certificate
        # type; `merit` fits the improvement awards better, since they
        # are not a statement about how much of the year somebody
        # attended.
        certificate_type = ("attendance"
                            if award.kind in (FULL_ATTENDANCE,
                                              HIGH_ATTENDANCE)
                            else "merit")
        issued = CertificateService(str(DB_PATH)).generate_certificate(
            student_id=award.student_id,
            certificate_type=certificate_type,
            course_name=award.kind,
            award_date=_dt.date.today().isoformat(),
            additional_info=citation_text(award),
            issued_by=issued_by)
        reference = (issued or {}).get("certificate_number")
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Certificate service unavailable; recording citation "
                     "only", exc_info=True)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_awards
                  SET state = ?, issued_at = datetime('now'),
                      certificate_ref = COALESCE(?, certificate_ref)
                WHERE award_id = ?""",
            (ISSUED, reference, award_id))
        conn.commit()
    out = get_award(award_id)
    assert out is not None
    return out


def issue_all(*, period_from: str | None = None,
              issued_by: str | None = None) -> int:
    """Print the batch."""
    issued = 0
    for award in list_awards(state=AWARDED, period_from=period_from,
                             limit=2000):
        try:
            issue_certificate(award.award_id, issued_by=issued_by)
            issued += 1
        except ValidationError as e:
            logger.warning("Could not issue award #%d: %s", award.award_id, e)
    return issued


# ── Reads ───────────────────────────────────────────────────────────

def get_award(award_id: int) -> Award | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_awards WHERE award_id = ?",
            (award_id,)).fetchone()
    return _row(r) if r else None


def award_for(student_id: str, kind: str, period_from: str,
              period_to: str) -> Award | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT * FROM attendance_awards
                WHERE student_id = ? AND kind = ? AND period_from = ?
                  AND period_to = ?""",
            (student_id.strip(), validate_kind(kind),
             core._validate_date(period_from),
             core._validate_date(period_to))).fetchone()
    return _row(r) if r else None


def list_awards(*, student_id: str | None = None, kind: str | None = None,
                state: str | None = None, period_from: str | None = None,
                with_names: bool = False,
                limit: int = 500) -> list[Award]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if period_from:
        clauses.append("period_from = ?")
        args.append(core._validate_date(period_from))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_awards {where} "
            "ORDER BY period_from DESC, kind, student_id LIMIT ?",
            args).fetchall()
    out = [_row(r) for r in rows]
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for award in out:
            award.student_name = index.get(award.student_id)
    return out


def pending_nominations(*, with_names: bool = True) -> list[Award]:
    """Nominations waiting to be confirmed."""
    return list_awards(state=NOMINATED, with_names=with_names, limit=1000)


def student_awards(student_id: str) -> list[Award]:
    """One learner's awards — worth naming in a reference."""
    return list_awards(student_id=student_id, limit=100)


def roll_of_honour(*, period_from: str,
                   period_to: str) -> dict[str, list[Award]]:
    """Awards for a period, grouped by kind, for reading out."""
    init_db()
    out: dict[str, list[Award]] = {kind: [] for kind in AWARD_KINDS}
    for award in list_awards(period_from=period_from, with_names=True,
                             limit=2000):
        if award.period_to != period_to or award.state == DECLINED:
            continue
        out.setdefault(award.kind, []).append(award)
    return {kind: awards for kind, awards in out.items() if awards}


def counts(*, period_from: str | None = None) -> dict[str, int]:
    """How many of each award have been given."""
    out: dict[str, int] = {}
    for award in list_awards(period_from=period_from, limit=5000):
        if award.state == DECLINED:
            continue
        out[award.kind] = out.get(award.kind, 0) + 1
    return out


def reach(*, period_from: str, period_to: str) -> dict[str, Any]:
    """How many learners the reward scheme actually reaches.

    The number worth watching. A scheme that only ever rewards the same
    twenty learners is a scheme that has stopped doing anything for
    anybody else, and the improvement award exists to widen it.
    """
    init_db()
    awards = [a for a in list_awards(period_from=period_from, limit=5000)
              if a.period_to == period_to and a.state != DECLINED]
    recipients = {a.student_id for a in awards}
    improvement_only = {a.student_id for a in awards
                        if a.kind in (MOST_IMPROVED, SUSTAINED)}
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    active = sum(1 for s in _students.list_students()
                 if getattr(s, "status", "Active") in ("Active", None))
    return {
        "awards": len(awards),
        "learners_rewarded": len(recipients),
        "active_learners": active,
        "share": (round(100.0 * len(recipients) / active, 1)
                  if active else None),
        "reached_by_improvement": len(improvement_only - {
            a.student_id for a in awards
            if a.kind in (FULL_ATTENDANCE, HIGH_ATTENDANCE)}),
    }
