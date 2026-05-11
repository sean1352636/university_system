"""Enrolment data layer for the Sixth Form System.

An *enrolment* is a per-academic-year record linking a student to a
year group, tutor group, and status. A student typically gets two
enrolments across their sixth-form career (Year 12 + Year 13) but the
model allows any number (e.g. resit years).

Shares the same SQLite file as `students` so cross-table joins and
``ON DELETE CASCADE`` from ``students.student_id`` just work.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.sixthform_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ENROLMENTS_DB

YEAR_GROUPS: tuple[int, ...] = (12, 13)
STATUSES: tuple[str, ...] = ("Enrolled", "Pending", "Withdrawn", "Completed")
DEFAULT_STATUS: str = "Enrolled"

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}/\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolments (
    enrolment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    year_group     INTEGER NOT NULL,
    tutor_group    TEXT,
    start_date     TEXT,
    status         TEXT NOT NULL DEFAULT 'Enrolled',
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, academic_year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_enrolments_student ON enrolments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrolments_year    ON enrolments(academic_year);
CREATE INDEX IF NOT EXISTS idx_enrolments_status  ON enrolments(status);
"""


@dataclass
class Enrolment:
    enrolment_id: int
    student_id: str
    academic_year: str
    year_group: int
    tutor_group: str | None
    start_date: str | None
    status: str
    notes: str | None
    created_at: str


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    # Ensure the students schema exists too, since our FK references it.
    from education_system.sixthform_system import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Enrolments schema ready at %s", DB_PATH)


def _row(r: sqlite3.Row) -> Enrolment:
    return Enrolment(
        enrolment_id=r["enrolment_id"],
        student_id=r["student_id"],
        academic_year=r["academic_year"],
        year_group=r["year_group"],
        tutor_group=r["tutor_group"],
        start_date=r["start_date"],
        status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


# ── Validation ──────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid enrolment-form input."""


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _validate_payload(data: dict[str, Any], *, expect_student: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if expect_student:
        out["student_id"] = _require(data.get("student_id"), "Student ID")

    year = _require(data.get("academic_year"), "Academic year")
    if not _ACADEMIC_YEAR_RE.match(year):
        raise ValidationError("Academic year must look like '2025/26'")
    out["academic_year"] = year

    yg_raw = data.get("year_group")
    if yg_raw is None or yg_raw == "":
        raise ValidationError("Year group is required")
    try:
        yg = int(yg_raw)
    except (TypeError, ValueError):
        raise ValidationError("Year group must be a whole number") from None
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(str(y) for y in YEAR_GROUPS)}")
    out["year_group"] = yg

    out["tutor_group"] = (data.get("tutor_group") or "").strip() or None

    sd = (data.get("start_date") or "").strip()
    if sd and not _DATE_RE.match(sd):
        raise ValidationError("Start date must be YYYY-MM-DD")
    out["start_date"] = sd or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ────────────────────────────────────────────────────────────

def create_enrolment(data: dict[str, Any]) -> Enrolment:
    """Insert a new enrolment row. Raises ``ValidationError`` on bad
    input and when the referenced ``student_id`` doesn't exist."""
    init_db()
    try:
        payload = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_enrolment validation failed: %s", e)
        raise

    sid = payload["student_id"]
    from education_system.sixthform_system import students as _students
    if _students.get_student(sid) is None:
        logger.warning("create_enrolment: unknown student_id %s", sid)
        raise ValidationError(f"No student with id {sid}")

    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO enrolments
                    (student_id, academic_year, year_group, tutor_group,
                     start_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    payload["academic_year"],
                    payload["year_group"],
                    payload["tutor_group"],
                    payload["start_date"],
                    payload["status"],
                    payload["notes"],
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "create_enrolment: duplicate (%s, %s)",
                sid, payload["academic_year"],
            )
            raise ValidationError(
                f"{sid} already has an enrolment for {payload['academic_year']}"
            ) from e
        logger.exception("create_enrolment DB error")
        raise ValidationError(f"Database error: {e}") from e

    enrolment = get_enrolment(new_id)
    assert enrolment is not None
    logger.info(
        "Created enrolment #%d for %s (%s, Year %d, status=%s)",
        new_id, sid, payload["academic_year"], payload["year_group"], payload["status"],
    )
    return enrolment


def get_enrolment(enrolment_id: int) -> Enrolment | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        ).fetchone()
        return _row(row) if row else None


def list_enrolments(
    *,
    student_id: str | None = None,
    academic_year: str | None = None,
    year_group: int | None = None,
    status: str | None = None,
) -> list[Enrolment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year)
    if year_group is not None:
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        clauses.append("status = ?")
        args.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT * FROM enrolments "
        f"{where} ORDER BY academic_year DESC, year_group, student_id"
    )
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [_row(r) for r in rows]


def list_for_student(student_id: str) -> list[Enrolment]:
    return list_enrolments(student_id=student_id)


def update_enrolment(enrolment_id: int, data: dict[str, Any]) -> Enrolment:
    """Update an enrolment. ``student_id`` is immutable."""
    init_db()
    existing = get_enrolment(enrolment_id)
    if existing is None:
        logger.warning("update_enrolment: unknown id %d", enrolment_id)
        raise ValidationError(f"No enrolment with id {enrolment_id}")

    try:
        payload = _validate_payload(data, expect_student=False)
    except ValidationError as e:
        logger.warning("update_enrolment(%d) validation failed: %s", enrolment_id, e)
        raise

    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE enrolments SET
                    academic_year = ?, year_group = ?, tutor_group = ?,
                    start_date = ?, status = ?, notes = ?
                WHERE enrolment_id = ?
                """,
                (
                    payload["academic_year"],
                    payload["year_group"],
                    payload["tutor_group"],
                    payload["start_date"],
                    payload["status"],
                    payload["notes"],
                    enrolment_id,
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            logger.warning(
                "update_enrolment(%d): duplicate (%s, %s)",
                enrolment_id, existing.student_id, payload["academic_year"],
            )
            raise ValidationError(
                f"{existing.student_id} already has an enrolment for "
                f"{payload['academic_year']}"
            ) from e
        logger.exception("update_enrolment DB error")
        raise ValidationError(f"Database error: {e}") from e

    enrolment = get_enrolment(enrolment_id)
    assert enrolment is not None
    logger.info("Updated enrolment #%d (status=%s)", enrolment_id, payload["status"])
    return enrolment


def delete_enrolment(enrolment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM enrolments WHERE enrolment_id = ?", (enrolment_id,)
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted enrolment #%d", enrolment_id)
            return True
        logger.warning("delete_enrolment: unknown id %d", enrolment_id)
        return False
