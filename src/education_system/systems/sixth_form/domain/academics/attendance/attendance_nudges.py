"""Register-taking nudges for the Sixth Form System.

Sibling to :mod:`attendance`. :func:`attendance_register.unsubmitted_registers`
already knows which registers were never taken. Nothing does anything
with that knowledge, so the list sits there growing, and by half term
the coverage report is unusable.

This module chases. A missing register produces a nudge to whoever
should have taken it; a nudge nobody acts on escalates to their head of
department; past that it goes to the person who owns attendance for the
college. Each stage is recorded, so "nobody told me" is checkable.

**Escalation is per register, not per person.** A teacher who forgot one
Tuesday does not want a weekly summary of their sins, and a head of
department needs the specific lesson, not a name. What arrives at each
stage is the list of registers still outstanding, addressed to the
person who can now do something about them.

Nudges are queued through :mod:`attendance_notifications`, so they go
out the same way everything else does and can be inspected before they
do.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_cover as cover,
    attendance_register as reg,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

TEACHER: str = "Teacher"
HEAD_OF_DEPARTMENT: str = "Head of department"
SLT: str = "SLT"
STAGES: tuple[str, ...] = (TEACHER, HEAD_OF_DEPARTMENT, SLT)
_STAGE_RANK: dict[str, int] = {s: i for i, s in enumerate(STAGES)}

OPEN: str = "Open"
RESOLVED: str = "Resolved"
DISMISSED: str = "Dismissed"
NUDGE_STATES: tuple[str, ...] = (OPEN, RESOLVED, DISMISSED)

# Teaching days a register may go unsubmitted before each stage fires.
# One day is a reminder; three is a problem; a week is somebody else's
# problem now.
STAGE_AFTER_DAYS: dict[str, int] = {
    TEACHER: 1,
    HEAD_OF_DEPARTMENT: 3,
    SLT: 7,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_nudges (
    nudge_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id      INTEGER NOT NULL,
    date         TEXT NOT NULL,
    group_id     INTEGER,
    owner        TEXT,
    stage        TEXT NOT NULL DEFAULT 'Teacher',
    state        TEXT NOT NULL DEFAULT 'Open',
    age_days     INTEGER NOT NULL DEFAULT 0,
    marked       INTEGER NOT NULL DEFAULT 0,
    expected     INTEGER NOT NULL DEFAULT 0,
    first_sent_at TEXT DEFAULT (datetime('now')),
    last_sent_at  TEXT DEFAULT (datetime('now')),
    sent_count   INTEGER NOT NULL DEFAULT 0,
    resolved_at  TEXT,
    note         TEXT,
    UNIQUE(slot_id, date)
);

CREATE INDEX IF NOT EXISTS idx_att_nudge_state
    ON attendance_nudges(state);
CREATE INDEX IF NOT EXISTS idx_att_nudge_owner
    ON attendance_nudges(owner);
CREATE INDEX IF NOT EXISTS idx_att_nudge_stage
    ON attendance_nudges(stage);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Nudge:
    """One outstanding register somebody is being chased about."""

    nudge_id: int
    slot_id: int
    date: str
    group_id: int | None
    owner: str | None
    stage: str
    state: str
    age_days: int
    marked: int
    expected: int
    first_sent_at: str | None
    last_sent_at: str | None
    sent_count: int
    resolved_at: str | None
    note: str | None

    @property
    def is_open(self) -> bool:
        return self.state == OPEN

    @property
    def partly_marked(self) -> bool:
        return 0 < self.marked < self.expected

    @property
    def label(self) -> str:
        state = ("never started" if self.marked == 0
                 else f"{self.marked}/{self.expected} marked")
        return (f"slot #{self.slot_id} on {self.date} — {state}, "
                f"{self.age_days} day(s) old [{self.stage}]")


@dataclass
class SweepResult:
    """What a chase run found and did."""

    raised: int = 0
    escalated: int = 0
    resolved: int = 0
    unchanged: int = 0
    notified: int = 0
    nudges: list[Nudge] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.raised} raised, {self.escalated} escalated, "
                f"{self.resolved} cleared, {self.notified} message(s) queued")


@dataclass
class OwnerDigest:
    """Everything one person is being chased about."""

    owner: str
    stage: str
    nudges: list[Nudge] = field(default_factory=list)

    @property
    def oldest_days(self) -> int:
        return max((n.age_days for n in self.nudges), default=0)

    def body(self) -> str:
        """The message that actually goes out."""
        lines = [f"{len(self.nudges)} register(s) still outstanding:"]
        for nudge in sorted(self.nudges, key=lambda n: (n.date, n.slot_id)):
            lines.append(f"  {nudge.label}")
        lines.append("")
        lines.append("Please take or complete these registers. An unmarked "
                     "lesson counts against the college, not the learner.")
        return "\n".join(lines)


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
    reg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Nudge schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Nudge:
    return Nudge(
        nudge_id=r["nudge_id"], slot_id=r["slot_id"], date=r["date"],
        group_id=r["group_id"], owner=r["owner"], stage=r["stage"],
        state=r["state"], age_days=r["age_days"], marked=r["marked"],
        expected=r["expected"], first_sent_at=r["first_sent_at"],
        last_sent_at=r["last_sent_at"], sent_count=r["sent_count"],
        resolved_at=r["resolved_at"], note=r["note"])


# ── Who owns a register ─────────────────────────────────────────────

def owner_of(slot_id: int, date: str) -> str | None:
    """Who should have taken this register.

    The cover teacher when there is one, otherwise whoever normally
    teaches it. Chasing the absent teacher for a lesson somebody else
    covered is how a chase list loses its credibility.
    """
    try:
        return cover.who_should_mark(slot_id, date)
    except Exception:                       # pragma: no cover - defensive
        logger.debug("Cover lookup failed for slot #%d", slot_id,
                     exc_info=True)
        return None


def _head_of_department(owner: str | None) -> str | None:
    """The line manager to escalate to, if the staff directory knows one."""
    if not owner:
        return None
    try:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        matches = _staff.search_staff(owner)
        for member in matches:
            if member.line_manager:
                return member.line_manager
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Staff lookup unavailable", exc_info=True)
    return None


def stage_for(age_days: int) -> str:
    """Which stage a register of this age has reached."""
    stage = TEACHER
    for candidate in STAGES:
        if age_days >= STAGE_AFTER_DAYS[candidate]:
            stage = candidate
    return stage


# ── The sweep ───────────────────────────────────────────────────────

def _teaching_age(date: str, *, today: str | None = None) -> int:
    """How many teaching days old a register is.

    Counted in teaching days, not calendar days: a Friday register
    chased on Monday is one day late, not three, and treating half term
    as four days of negligence is how a chase list gets ignored.
    """
    now = core._validate_date(today or _dt.date.today().isoformat())
    if date >= now:
        return 0
    return max(0, len(calendar.teaching_days(date, now)) - 1)


def sweep(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    today: str | None = None,
    notify: bool = False,
    group_id: int | None = None,
) -> SweepResult:
    """Find outstanding registers, raise or escalate nudges, clear the rest.

    Idempotent, and safe to run daily: a register that has since been
    submitted closes its nudge rather than being chased again.
    """
    init_db()
    now = core._validate_date(today or _dt.date.today().isoformat())
    date_to = core._validate_date(date_to or now)
    date_from = core._validate_date(
        date_from or (_dt.date.fromisoformat(date_to)
                      - _dt.timedelta(days=21)).isoformat())
    result = SweepResult()

    missing = reg.unsubmitted_registers(date_from=date_from, date_to=date_to,
                                        group_id=group_id)
    outstanding = {(m.slot_id, m.date): m for m in missing
                   if m.date < now and m.expected > 0}

    # Close anything that has since been done.
    for nudge in list_nudges(state=OPEN):
        if (nudge.slot_id, nudge.date) not in outstanding \
                and date_from <= nudge.date <= date_to:
            resolve(nudge.nudge_id, note="Register submitted")
            result.resolved += 1

    for (slot_id, date), entry in sorted(outstanding.items()):
        age = _teaching_age(date, today=now)
        if age < STAGE_AFTER_DAYS[TEACHER]:
            continue
        stage = stage_for(age)
        owner = owner_of(slot_id, date)
        if stage == HEAD_OF_DEPARTMENT:
            owner = _head_of_department(owner) or owner
        elif stage == SLT:
            owner = None            # the college-level list, addressed later

        existing = nudge_for(slot_id, date)
        if existing is None:
            with _connect() as conn:
                conn.execute(
                    """INSERT INTO attendance_nudges
                           (slot_id, date, group_id, owner, stage, state,
                            age_days, marked, expected)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slot_id, date, entry.group_id, owner, stage, OPEN, age,
                     entry.marked, entry.expected))
                conn.commit()
            result.raised += 1
        else:
            escalated = _STAGE_RANK[stage] > _STAGE_RANK[existing.stage]
            with _connect() as conn:
                conn.execute(
                    """UPDATE attendance_nudges
                          SET stage = ?, owner = ?, age_days = ?,
                              marked = ?, expected = ?
                        WHERE nudge_id = ?""",
                    (stage, owner, age, entry.marked, entry.expected,
                     existing.nudge_id))
                conn.commit()
            if escalated:
                result.escalated += 1
            else:
                result.unchanged += 1
        raised = nudge_for(slot_id, date)
        if raised is not None:
            result.nudges.append(raised)

    if notify:
        result.notified = send_digests()
    logger.info("Nudge sweep: %s", result.summary)
    return result


# ── Digests ─────────────────────────────────────────────────────────

def digests(*, stage: str | None = None) -> list[OwnerDigest]:
    """Group open nudges by the person now responsible for them."""
    grouped: dict[tuple[str, str], OwnerDigest] = {}
    for nudge in list_nudges(state=OPEN, stage=stage):
        key = (nudge.owner or "(unassigned)", nudge.stage)
        grouped.setdefault(key, OwnerDigest(owner=key[0], stage=key[1]))
        grouped[key].nudges.append(nudge)
    out = list(grouped.values())
    out.sort(key=lambda d: (-_STAGE_RANK[d.stage], -d.oldest_days))
    return out


def send_digests(*, stage: str | None = None, sender=None) -> int:
    """Send one message per person, listing everything they still owe.

    One message, not one per register — the whole point of a digest is
    that it can be read in one sitting and acted on in one sitting.

    Deliberately *not* routed through
    :mod:`attendance_notifications`: everything in that queue is a
    message about a learner, keyed to one, and a nudge is a message to a
    member of staff about their own registers. Forcing it through would
    mean inventing a learner for it and putting staff performance in the
    parent-facing message history.

    ``sender`` is a callable taking ``(email, subject, body)``. Without
    one, the college's email service is used; without that configured,
    the digests are returned unsent by :func:`digests` and this reports
    zero, which is honest rather than convenient.
    """
    init_db()
    sent = 0
    for digest in digests(stage=stage):
        if digest.owner == "(unassigned)":
            continue
        address = _staff_email(digest.owner)
        if not address:
            logger.debug("No email for %s — digest not sent", digest.owner)
            continue
        subject = f"{len(digest.nudges)} register(s) outstanding"
        try:
            if sender is not None:
                sender(address, subject, digest.body())
            else:
                _send_email(address, subject, digest.body())
        except Exception as e:
            logger.warning("Could not send nudge digest to %s: %s",
                           digest.owner, e)
            continue
        _mark_sent([n.nudge_id for n in digest.nudges])
        sent += 1
    return sent


def _send_email(address: str, subject: str, body: str) -> None:
    from education_system.platform.integrations.email.email_service import (
        EmailService,
    )
    service = EmailService()
    if not service.is_configured():
        raise RuntimeError("Email is not configured on this installation")
    service.send_email(to=address, subject=subject, body=body)


def _staff_email(name: str) -> str | None:
    try:
        from education_system.systems.sixth_form.domain.staff import staff as _staff
        for member in _staff.search_staff(name):
            if member.email:
                return member.email
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Staff email lookup unavailable", exc_info=True)
    return None


def _mark_sent(nudge_ids: list[int]) -> None:
    if not nudge_ids:
        return
    with _connect() as conn:
        conn.executemany(
            "UPDATE attendance_nudges SET sent_count = sent_count + 1, "
            "last_sent_at = datetime('now') WHERE nudge_id = ?",
            [(nudge_id,) for nudge_id in nudge_ids])
        conn.commit()


# ── Managing nudges ─────────────────────────────────────────────────

def resolve(nudge_id: int, *, note: str | None = None) -> Nudge:
    """Close a nudge — the register got taken."""
    init_db()
    if get_nudge(nudge_id) is None:
        raise ValidationError(f"No nudge with id {nudge_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_nudges SET state = ?, "
            "resolved_at = datetime('now'), note = COALESCE(?, note) "
            "WHERE nudge_id = ?", (RESOLVED, note, nudge_id))
        conn.commit()
    out = get_nudge(nudge_id)
    assert out is not None
    return out


def dismiss(nudge_id: int, *, reason: str) -> Nudge:
    """Stop chasing — the lesson did not happen, and never will.

    A cancelled lesson, a group that was on a trip, a slot left on the
    timetable by mistake. Recorded rather than deleted so the same
    register does not reappear on tomorrow's sweep.
    """
    init_db()
    if get_nudge(nudge_id) is None:
        raise ValidationError(f"No nudge with id {nudge_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to dismiss a nudge")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_nudges SET state = ?, "
            "resolved_at = datetime('now'), note = ? WHERE nudge_id = ?",
            (DISMISSED, note, nudge_id))
        conn.commit()
    out = get_nudge(nudge_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_nudge(nudge_id: int) -> Nudge | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_nudges WHERE nudge_id = ?",
            (nudge_id,)).fetchone()
    return _row(r) if r else None


def nudge_for(slot_id: int, date: str) -> Nudge | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_nudges WHERE slot_id = ? AND date = ?",
            (slot_id, core._validate_date(date))).fetchone()
    return _row(r) if r else None


def list_nudges(*, state: str | None = None, stage: str | None = None,
                owner: str | None = None, date_from: str | None = None,
                date_to: str | None = None,
                limit: int = 500) -> list[Nudge]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        if state not in NUDGE_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(NUDGE_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if stage:
        if stage not in STAGES:
            raise ValidationError(f"Stage must be one of: {', '.join(STAGES)}")
        clauses.append("stage = ?")
        args.append(stage)
    if owner:
        clauses.append("owner = ?")
        args.append(owner.strip())
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
            f"SELECT * FROM attendance_nudges {where} "
            "ORDER BY date, slot_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def open_count(*, stage: str | None = None) -> int:
    return len(list_nudges(state=OPEN, stage=stage))


def worst_offenders(*, date_from: str | None = None,
                    date_to: str | None = None,
                    minimum: int = 3) -> list[tuple[str, int]]:
    """Who is missing the most registers.

    For a conversation, not a league table — but the conversation is
    much easier to have with a number in it.
    """
    counts: dict[str, int] = {}
    for nudge in list_nudges(date_from=date_from, date_to=date_to,
                             limit=5000):
        if nudge.state == DISMISSED or not nudge.owner:
            continue
        counts[nudge.owner] = counts.get(nudge.owner, 0) + 1
    out = [(owner, n) for owner, n in counts.items() if n >= max(1, minimum)]
    out.sort(key=lambda item: -item[1])
    return out


def slot_offenders(*, date_from: str | None = None,
                   date_to: str | None = None,
                   minimum: int = 3) -> list[tuple[int, int]]:
    """Slots whose register is habitually missing.

    Often a timetable problem rather than a person problem — a lesson
    that moved rooms, or a slot nobody actually teaches any more.
    """
    counts: dict[int, int] = {}
    for nudge in list_nudges(date_from=date_from, date_to=date_to,
                             limit=5000):
        if nudge.state == DISMISSED:
            continue
        counts[nudge.slot_id] = counts.get(nudge.slot_id, 0) + 1
    out = [(slot, n) for slot, n in counts.items() if n >= max(1, minimum)]
    out.sort(key=lambda item: -item[1])
    return out


def chase_sheet(*, stage: str | None = None) -> list[str]:
    """A printable list for a briefing — one line per outstanding register."""
    lines: list[str] = []
    for digest in digests(stage=stage):
        lines.append(f"{digest.owner} ({digest.stage}) — "
                     f"{len(digest.nudges)} outstanding")
        for nudge in sorted(digest.nudges, key=lambda n: (n.date, n.slot_id)):
            group = tt.get_slot(nudge.slot_id)
            where = (f"P{group.period} {group.room or ''}".strip()
                     if group else "")
            lines.append(f"    {nudge.date}  slot #{nudge.slot_id} {where}")
    return lines
