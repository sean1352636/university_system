"""Attendance data layer for the Sixth Form System.

One row per ``(slot, student, date)`` triple, recording whether the
student was Present / Late / Absent / Authorised. Built so that staff
can "take the register" for a class group: load the roster, mark
each student, save once.

The headline operations are:

* ``register_view(slot_id, date)`` — returns the roster joined to any
  existing records, so the GUI/CLI can render a fillable register.
* ``save_register(slot_id, date, records)`` — upserts every entry in
  one transaction; missing entries leave existing rows untouched.
* ``summary_for_student`` / ``summary_for_group`` — present-rate stats.

Cascades: deleting a slot or a student wipes their attendance rows.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.sixthform_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ATTENDANCE_DB

STATUSES: tuple[str, ...] = (
    "Present", "Late", "Absent", "Authorised",
)
DEFAULT_STATUS: str = "Present"
ATTENDING_STATUSES: tuple[str, ...] = ("Present", "Late")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id      INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    status       TEXT NOT NULL,
    minutes_late INTEGER,
    notes        TEXT,
    recorded_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(slot_id, student_id, date),
    FOREIGN KEY (slot_id)    REFERENCES timetable_slots(slot_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_slot    ON attendance_records(slot_id);
CREATE INDEX IF NOT EXISTS idx_att_student ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_att_date    ON attendance_records(date);
"""


@dataclass
class AttendanceRecord:
    record_id: int
    slot_id: int
    student_id: str
    date: str
    status: str
    minutes_late: int | None
    notes: str | None
    recorded_at: str


@dataclass
class RegisterEntry:
    """One row in a fillable register: a student + any existing record."""
    student_id: str
    full_name: str
    record: AttendanceRecord | None


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    # FKs target slots + students, so make sure those schemas exist too.
    from education_system.sixthform_system import timetable as _tt
    _tt.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Attendance schema ready at %s", DB_PATH)


def _row(r: sqlite3.Row) -> AttendanceRecord:
    return AttendanceRecord(
        record_id=r["record_id"],
        slot_id=r["slot_id"],
        student_id=r["student_id"],
        date=r["date"],
        status=r["status"],
        minutes_late=r["minutes_late"],
        notes=r["notes"],
        recorded_at=r["recorded_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid attendance input."""


def _validate_date(d: str) -> str:
    d = (d or "").strip()
    if not d:
        raise ValidationError("Date is required")
    if not _DATE_RE.match(d):
        raise ValidationError("Date must be YYYY-MM-DD")
    return d


def _validate_status(s: str) -> str:
    s = (s or "").strip()
    if s not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return s


def _validate_minutes(value, status: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        m = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Minutes late must be a whole number") from None
    if m < 0 or m > 1000:
        raise ValidationError("Minutes late must be between 0 and 1000")
    if m and status != "Late":
        # Non-blocking detail: allow but warn via log.
        logger.debug("minutes_late=%d set with status=%s", m, status)
    return m


# ── Roster + register view ─────────────────────────────────────────

def _resolve_group_for_slot(slot_id: int) -> int | None:
    from education_system.sixthform_system import timetable as _tt
    slot = _tt.get_slot(slot_id)
    return slot.group_id if slot else None


def register_view(slot_id: int, date: str) -> list[RegisterEntry]:
    """Return one `RegisterEntry` per student in the slot's class group,
    joined to any existing record for ``date`` (or `None`)."""
    init_db()
    date = _validate_date(date)
    group_id = _resolve_group_for_slot(slot_id)
    if group_id is None:
        raise ValidationError(f"No slot with id {slot_id}")

    from education_system.sixthform_system import (
        class_groups as _cg,
        students as _students,
    )
    members = _cg.list_members(group_id)
    student_index = {s.student_id: s for s in _students.list_students()
                     if s.student_id in members}

    with _connect() as conn:
        rows = {
            r["student_id"]: _row(r)
            for r in conn.execute(
                "SELECT * FROM attendance_records "
                "WHERE slot_id = ? AND date = ?",
                (slot_id, date),
            ).fetchall()
        }

    out: list[RegisterEntry] = []
    for sid in members:
        student = student_index.get(sid)
        out.append(RegisterEntry(
            student_id=sid,
            full_name=student.full_name if student else "(unknown)",
            record=rows.get(sid),
        ))
    return out


def save_register(
    slot_id: int,
    date: str,
    entries: dict[str, dict[str, Any]],
) -> int:
    """Upsert attendance records for a slot/date in one transaction.

    ``entries`` maps ``student_id`` → ``{"status", "minutes_late", "notes"}``.
    Missing students are left untouched (use ``delete_record`` to remove
    a row explicitly). Returns the number of rows written.
    """
    init_db()
    date = _validate_date(date)
    if _resolve_group_for_slot(slot_id) is None:
        raise ValidationError(f"No slot with id {slot_id}")

    # Pre-validate all entries before touching the DB, so a single bad
    # row doesn't leave the register half-saved.
    cleaned: list[tuple[str, str, int | None, str | None]] = []
    for sid, payload in entries.items():
        status = _validate_status(payload.get("status", ""))
        minutes = _validate_minutes(payload.get("minutes_late"), status)
        notes = (payload.get("notes") or "").strip() or None
        cleaned.append((sid, status, minutes, notes))

    written = 0
    try:
        with _connect() as conn:
            for sid, status, minutes, notes in cleaned:
                # UPSERT keyed on the UNIQUE(slot_id, student_id, date) constraint.
                conn.execute(
                    """INSERT INTO attendance_records
                          (slot_id, student_id, date, status,
                           minutes_late, notes)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(slot_id, student_id, date) DO UPDATE SET
                          status = excluded.status,
                          minutes_late = excluded.minutes_late,
                          notes = excluded.notes,
                          recorded_at = datetime('now')""",
                    (slot_id, sid, date, status, minutes, notes),
                )
                written += 1
            conn.commit()
    except sqlite3.Error as e:
        logger.exception("save_register DB error")
        raise ValidationError(f"Database error: {e}") from e

    logger.info(
        "Saved register: slot #%d, %s, %d row(s)", slot_id, date, written,
    )
    return written


# ── CRUD (individual records) ──────────────────────────────────────

def get_record(record_id: int) -> AttendanceRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return _row(r) if r else None


def list_records(
    *,
    student_id: str | None = None,
    slot_id: int | None = None,
    group_id: int | None = None,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
) -> list[AttendanceRecord]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("ar.student_id = ?")
        args.append(student_id)
    if slot_id is not None:
        clauses.append("ar.slot_id = ?")
        args.append(slot_id)
    if date:
        clauses.append("ar.date = ?")
        args.append(_validate_date(date))
    if date_from:
        clauses.append("ar.date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("ar.date <= ?")
        args.append(_validate_date(date_to))
    if status:
        clauses.append("ar.status = ?")
        args.append(_validate_status(status))
    if group_id is not None:
        clauses.append(
            "ar.slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)"
        )
        args.append(group_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT ar.* FROM attendance_records ar "
        f"{where} ORDER BY ar.date DESC, ar.slot_id, ar.student_id"
    )
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def update_record(record_id: int, data: dict[str, Any]) -> AttendanceRecord:
    """Update a single attendance row's status / minutes_late / notes."""
    init_db()
    existing = get_record(record_id)
    if existing is None:
        logger.warning("update_record: unknown id %d", record_id)
        raise ValidationError(f"No record with id {record_id}")

    status = _validate_status(data.get("status", existing.status))
    minutes = _validate_minutes(
        data.get("minutes_late", existing.minutes_late), status)
    notes = (data.get("notes") if "notes" in data else existing.notes)
    notes = (notes or "").strip() or None if isinstance(notes, str) else notes

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
               SET status = ?, minutes_late = ?, notes = ?,
                   recorded_at = datetime('now')
               WHERE record_id = ?""",
            (status, minutes, notes, record_id),
        )
        conn.commit()
    logger.info(
        "Updated attendance record #%d (student=%s, status=%s)",
        record_id, existing.student_id, status,
    )
    out = get_record(record_id)
    assert out is not None
    return out


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_records WHERE record_id = ?",
            (record_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted attendance record #%d", record_id)
            return True
        logger.warning("delete_record: unknown id %d", record_id)
        return False


# ── Summaries ──────────────────────────────────────────────────────

@dataclass
class AttendanceSummary:
    total:      int
    present:    int
    late:       int
    absent:     int
    authorised: int

    @property
    def attending(self) -> int:
        """Counted as attending: Present + Late."""
        return self.present + self.late

    @property
    def percentage(self) -> float | None:
        if self.total == 0:
            return None
        return round(100.0 * self.attending / self.total, 1)


def _summarize(rows: list[sqlite3.Row]) -> AttendanceSummary:
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    return AttendanceSummary(
        total=sum(counts.values()),
        present=counts["Present"],
        late=counts["Late"],
        absent=counts["Absent"],
        authorised=counts["Authorised"],
    )


def summary_for_student(
    student_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    slot_id: int | None = None,
) -> AttendanceSummary:
    init_db()
    clauses = ["student_id = ?"]
    args: list[Any] = [student_id]
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT status, COUNT(*) AS n FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY status"
    )
    with _connect() as conn:
        return _summarize(conn.execute(sql, args).fetchall())


def summary_for_group(
    group_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> AttendanceSummary:
    init_db()
    clauses = [
        "slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)"
    ]
    args: list[Any] = [group_id]
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT status, COUNT(*) AS n FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY status"
    )
    with _connect() as conn:
        return _summarize(conn.execute(sql, args).fetchall())


def per_student_summary_for_group(
    group_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, AttendanceSummary]:
    """One AttendanceSummary per student in the group (over the date range)."""
    init_db()
    from education_system.sixthform_system import class_groups as _cg
    members = _cg.list_members(group_id)
    if not members:
        return {}

    placeholders = ",".join("?" * len(members))
    clauses = [
        f"student_id IN ({placeholders})",
        "slot_id IN (SELECT slot_id FROM timetable_slots WHERE group_id = ?)",
    ]
    args: list[Any] = [*members, group_id]
    if date_from:
        clauses.append("date >= ?")
        args.append(_validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(_validate_date(date_to))
    sql = (
        "SELECT student_id, status, COUNT(*) AS n "
        "FROM attendance_records "
        f"WHERE {' AND '.join(clauses)} GROUP BY student_id, status"
    )
    by_student: dict[str, dict[str, int]] = {sid: {s: 0 for s in STATUSES}
                                              for sid in members}
    with _connect() as conn:
        for r in conn.execute(sql, args).fetchall():
            by_student[r["student_id"]][r["status"]] = r["n"]
    out: dict[str, AttendanceSummary] = {}
    for sid, counts in by_student.items():
        out[sid] = AttendanceSummary(
            total=sum(counts.values()),
            present=counts["Present"],
            late=counts["Late"],
            absent=counts["Absent"],
            authorised=counts["Authorised"],
        )
    return out
