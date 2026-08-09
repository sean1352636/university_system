"""Amendment trail and voiding for Sixth Form Attendance.

Sibling to :mod:`attendance`. Two jobs, both about being able to answer
"who changed this, and what did it say before?" a year later.

**The amendment trail.** A register is evidence. Once it has been
submitted, every subsequent change to it is a change to evidence, and
needs to be visible as one. :func:`log_changes` diffs the row before
against the row after and writes one entry per field that moved — so the
trail reads as a list of facts ("status: Absent → Authorised, by jsmith,
because 'hospital letter received'") rather than a pile of row dumps.

The trail is deliberately *not* the undo buffer. Undo
(:mod:`attendance_register`) is a short, bounded stack a teacher uses to
take back the last thing they did. This is an unbounded, append-only
record nobody can pop.

**Voiding.** ``delete_record`` destroys a row, which is the wrong answer
for a mark that was real and is now wrong: the fact that somebody once
recorded it is itself part of the story. :func:`void_record` sets a flag
instead. Voided rows are excluded from every read and every calculation
in :mod:`attendance`, but they are still there, still attributable, and
:func:`restore_record` puts them back.

The one place a row really does disappear is :func:`purge_voided`, which
exists so retention policy can be honoured on a schedule rather than by
hand.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# What kind of change an entry describes.
ACTIONS: tuple[str, ...] = (
    "edit",          # a mark or one of its details changed
    "code",          # recoded
    "authorise",     # absence signed off
    "unauthorise",   # sign-off withdrawn
    "offsite",       # off-site placement set or cleared
    "void",          # soft-deleted
    "restore",       # un-voided
    "purge",         # hard-deleted under retention policy
)

# Which record fields are worth a trail entry when they move. Deliberately
# excludes `recorded_at`, which changes on every write and would drown
# the signal.
TRACKED_FIELDS: tuple[str, ...] = (
    "status", "code", "reason_id", "session", "minutes_late", "notes",
    "arrival_time", "departure_time", "authorised_by", "authorisation_note",
    "is_offsite", "offsite_location", "data_source", "voided", "void_reason",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_amendments (
    amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id    INTEGER,
    slot_id      INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    action       TEXT NOT NULL,
    field        TEXT,
    old_value    TEXT,
    new_value    TEXT,
    reason       TEXT,
    amended_by   TEXT,
    amended_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_att_amend_record
    ON attendance_amendments(record_id);
CREATE INDEX IF NOT EXISTS idx_att_amend_student
    ON attendance_amendments(student_id, date);
CREATE INDEX IF NOT EXISTS idx_att_amend_when
    ON attendance_amendments(amended_at);
"""


@dataclass
class Amendment:
    """One recorded change to one attendance row."""

    amendment_id: int
    record_id: int | None
    slot_id: int
    student_id: str
    date: str
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str | None
    amended_by: str | None
    amended_at: str | None

    @property
    def summary(self) -> str:
        who = self.amended_by or "unknown"
        if self.field:
            return (f"{self.field}: {self.old_value or '—'} → "
                    f"{self.new_value or '—'} (by {who})")
        return f"{self.action} (by {who})"


@dataclass
class VoidResult:
    """What a void or restore did."""

    record_id: int
    student_id: str
    date: str
    action: str


@dataclass
class PurgeResult:
    purged: int
    before_date: str


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
        conn.commit()
    logger.debug("Attendance amendment schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Amendment:
    return Amendment(
        amendment_id=r["amendment_id"],
        record_id=r["record_id"],
        slot_id=r["slot_id"],
        student_id=r["student_id"],
        date=r["date"],
        action=r["action"],
        field=r["field"],
        old_value=r["old_value"],
        new_value=r["new_value"],
        reason=r["reason"],
        amended_by=r["amended_by"],
        amended_at=r["amended_at"],
    )


def _validate_action(action: str) -> str:
    s = (action or "").strip().lower()
    if s not in ACTIONS:
        raise ValidationError(
            f"Action must be one of: {', '.join(ACTIONS)}")
    return s


def _text(value: Any) -> str | None:
    """Render a field value for the trail.

    Booleans become yes/no rather than 0/1, because a human reads this.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


# ── Writing the trail ───────────────────────────────────────────────

def record_amendment(
    *,
    record: core.AttendanceRecord | None = None,
    record_id: int | None = None,
    slot_id: int | None = None,
    student_id: str | None = None,
    date: str | None = None,
    action: str,
    field: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
    actor: str | None = None,
) -> Amendment:
    """Append one entry to the trail.

    Pass ``record`` to take the slot/student/date from it, or give them
    directly — the latter matters for :func:`purge_voided`, which writes
    the entry after the row is gone.
    """
    init_db()
    action = _validate_action(action)
    if record is not None:
        record_id = record_id if record_id is not None else record.record_id
        slot_id = slot_id if slot_id is not None else record.slot_id
        student_id = student_id or record.student_id
        date = date or record.date
    if slot_id is None or not student_id or not date:
        raise ValidationError(
            "An amendment needs a slot, a student and a date")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_amendments
                   (record_id, slot_id, student_id, date, action, field,
                    old_value, new_value, reason, amended_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (record_id, slot_id, student_id, date, action, field,
             _text(old_value), _text(new_value),
             (reason or "").strip() or None,
             (actor or "").strip() or None))
        conn.commit()
        amendment_id = int(cur.lastrowid or 0)
    logger.info("Amendment #%d: %s on %s/%s by %s",
                amendment_id, action, student_id, date, actor or "unknown")
    out = get_amendment(amendment_id)
    assert out is not None
    return out


def log_changes(
    before: core.AttendanceRecord | None,
    after: core.AttendanceRecord,
    *,
    action: str = "edit",
    actor: str | None = None,
    reason: str | None = None,
    fields: tuple[str, ...] = TRACKED_FIELDS,
) -> list[Amendment]:
    """Diff two versions of a row and log one entry per changed field.

    A ``None`` ``before`` means the row is new, which is not an
    amendment — nothing is written and an empty list comes back. Same
    for a change that moved nothing: re-saving an unchanged register
    should not fill the trail with noise.
    """
    if before is None:
        return []
    out: list[Amendment] = []
    for field in fields:
        old = getattr(before, field, None)
        new = getattr(after, field, None)
        if _text(old) == _text(new):
            continue
        out.append(record_amendment(
            record=after, action=action, field=field,
            old_value=old, new_value=new, reason=reason, actor=actor))
    return out


# ── Reading the trail ───────────────────────────────────────────────

def get_amendment(amendment_id: int) -> Amendment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_amendments WHERE amendment_id = ?",
            (amendment_id,)).fetchone()
    return _row(r) if r else None


def list_amendments(
    *,
    record_id: int | None = None,
    student_id: str | None = None,
    slot_id: int | None = None,
    group_id: int | None = None,
    action: str | None = None,
    actor: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
) -> list[Amendment]:
    """The trail, newest first.

    ``date_from`` / ``date_to`` filter on the *register* date — the
    lesson being amended — not on when the amendment was made. That is
    almost always the question being asked ("what has been changed about
    last term?").
    """
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if record_id is not None:
        clauses.append("record_id = ?")
        args.append(record_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if group_id is not None:
        clauses.append("slot_id IN (SELECT slot_id FROM timetable_slots "
                       "WHERE group_id = ?)")
        args.append(group_id)
    if action:
        clauses.append("action = ?")
        args.append(_validate_action(action))
    if actor:
        clauses.append("LOWER(amended_by) = LOWER(?)")
        args.append(actor.strip())
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM attendance_amendments {where} "
           "ORDER BY amendment_id DESC")
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def amendment_trail(record_id: int) -> list[Amendment]:
    """Everything that ever happened to one row, oldest first."""
    return list(reversed(list_amendments(record_id=record_id)))


def amendment_summary(*, date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """Counts by action over a window — the governance headline."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT action, COUNT(*) AS n FROM attendance_amendments "
            f"{where} GROUP BY action", args).fetchall()
    out = {action: 0 for action in ACTIONS}
    for r in rows:
        out[r["action"]] = int(r["n"])
    return out


def most_amended(*, date_from: str | None = None,
                 date_to: str | None = None,
                 limit: int = 10) -> list[tuple[str, int]]:
    """Students whose marks are changed most often, commonest first.

    A learner who needs their register amended every week is either
    being mismarked or is a safeguarding question. Either way it is
    worth surfacing.
    """
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT student_id, COUNT(*) AS n FROM attendance_amendments "
            f"{where} GROUP BY student_id ORDER BY n DESC, student_id "
            f"LIMIT {int(limit)}", args).fetchall()
    return [(r["student_id"], int(r["n"])) for r in rows]


# ── Voiding ─────────────────────────────────────────────────────────

def void_record(record_id: int, *, reason: str,
                actor: str | None = None,
                force: bool = False) -> VoidResult:
    """Soft-delete one attendance row.

    A reason is mandatory: an unexplained void is indistinguishable from
    a cover-up, and the whole point of the flag over a delete is that
    somebody has to own the decision.

    Refuses on a submitted register unless ``force`` is set, matching
    every other write path — reopen the register, or say explicitly that
    you are overriding it.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A void needs a reason")
    if record.voided:
        raise ValidationError(
            f"Record #{record_id} is already voided")
    if not force:
        core._lifecycle().assert_unlocked(record.slot_id, record.date)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
                  SET voided = 1, voided_by = ?, voided_at = datetime('now'),
                      void_reason = ?
                WHERE record_id = ?""",
            ((actor or "").strip() or None, reason, record_id))
        conn.commit()
    record_amendment(record=record, action="void", field="voided",
                     old_value=False, new_value=True,
                     reason=reason, actor=actor)
    logger.info("Voided attendance record #%d (%s on %s): %s",
                record_id, record.student_id, record.date, reason)
    return VoidResult(record_id=record_id, student_id=record.student_id,
                      date=record.date, action="void")


def restore_record(record_id: int, *, actor: str | None = None,
                   reason: str | None = None,
                   force: bool = False) -> VoidResult:
    """Bring a voided row back into the counts."""
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    if not record.voided:
        raise ValidationError(f"Record #{record_id} is not voided")
    if not force:
        core._lifecycle().assert_unlocked(record.slot_id, record.date)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
                  SET voided = 0, voided_by = NULL, voided_at = NULL,
                      void_reason = NULL
                WHERE record_id = ?""",
            (record_id,))
        conn.commit()
    record_amendment(record=record, action="restore", field="voided",
                     old_value=True, new_value=False,
                     reason=reason or "Void reversed", actor=actor)
    logger.info("Restored attendance record #%d", record_id)
    return VoidResult(record_id=record_id, student_id=record.student_id,
                      date=record.date, action="restore")


def list_voided(*, student_id: str | None = None,
                group_id: int | None = None,
                date_from: str | None = None,
                date_to: str | None = None
                ) -> list[core.AttendanceRecord]:
    """Voided rows, for review before they are purged."""
    return core.list_records(
        student_id=student_id, group_id=group_id,
        date_from=date_from, date_to=date_to, voided_only=True)


def void_reason_for(record_id: int) -> str | None:
    record = core.get_record(record_id)
    return record.void_reason if record and record.voided else None


def purge_voided(*, before_date: str, actor: str | None = None,
                 dry_run: bool = False) -> PurgeResult:
    """Hard-delete voided rows dated before ``before_date``.

    The retention valve. Every purge leaves an amendment entry behind,
    so the trail still shows that a row existed and was removed even
    though the row itself is gone.

    ``dry_run`` counts what would go without touching anything — always
    worth running first, because this is the one operation here that
    cannot be undone.
    """
    init_db()
    before_date = core._validate_date(before_date)
    doomed = core.list_records(date_to=before_date, voided_only=True)
    # `date_to` is inclusive; retention is "before", so drop the boundary.
    doomed = [r for r in doomed if r.date < before_date]
    if dry_run:
        return PurgeResult(purged=len(doomed), before_date=before_date)

    for record in doomed:
        record_amendment(
            record_id=None, slot_id=record.slot_id,
            student_id=record.student_id, date=record.date,
            action="purge", field="record_id",
            old_value=record.record_id, new_value=None,
            reason=f"Retention purge of voided row ({record.void_reason})",
            actor=actor)
    if doomed:
        with _connect() as conn:
            conn.executemany(
                "DELETE FROM attendance_records WHERE record_id = ?",
                [(r.record_id,) for r in doomed])
            conn.commit()
        logger.info("Purged %d voided attendance row(s) before %s",
                    len(doomed), before_date)
    return PurgeResult(purged=len(doomed), before_date=before_date)
