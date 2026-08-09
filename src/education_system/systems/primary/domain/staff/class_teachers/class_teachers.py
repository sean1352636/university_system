"""Class teachers data layer.

Tracks which staff are assigned to which classes for an academic year.
Each class can have multiple assignments (a class teacher, a TA, a
cover teacher, etc.). Exactly one assignment per (class, year) may be
flagged ``is_primary=True``; that staff member is the named class
teacher and is mirrored back to ``classes.teacher`` for convenience.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.academics.classes import (
    classes as classes_data,
)
from education_system.systems.primary.domain.academics.classes.classes import (
    SchoolClass,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

ROLES: tuple[str, ...] = (
    "Class Teacher", "Teaching Assistant", "Support",
    "Cover Teacher", "Trainee", "Other",
)

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_teacher_assignments (
    assignment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id        INTEGER NOT NULL,
    staff_name      TEXT NOT NULL,
    staff_id        TEXT,
    academic_year   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'Class Teacher',
    is_primary      INTEGER NOT NULL DEFAULT 0,
    start_date      TEXT,
    end_date        TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(class_id, staff_name, academic_year, role),
    FOREIGN KEY(class_id) REFERENCES classes(class_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ct_class    ON class_teacher_assignments(class_id);
CREATE INDEX IF NOT EXISTS idx_ct_year     ON class_teacher_assignments(academic_year);
CREATE INDEX IF NOT EXISTS idx_ct_primary  ON class_teacher_assignments(class_id, academic_year, is_primary);
"""


@dataclass
class Assignment:
    assignment_id: int
    class_id: int
    staff_name: str
    staff_id: str | None
    academic_year: str
    role: str
    is_primary: bool
    start_date: str | None
    end_date: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    classes_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise class_teacher_assignments table")
        raise
    logger.info("Primary class_teacher_assignments table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Assignment:
    return Assignment(
        assignment_id=r["assignment_id"],
        class_id=r["class_id"],
        staff_name=r["staff_name"],
        staff_id=r["staff_id"],
        academic_year=r["academic_year"],
        role=r["role"],
        is_primary=bool(r["is_primary"]),
        start_date=r["start_date"],
        end_date=r["end_date"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cid_raw = data.get("class_id")
    if cid_raw in (None, ""):
        raise ValidationError("Class is required")
    try:
        out["class_id"] = int(cid_raw)
    except (TypeError, ValueError) as e:
        raise ValidationError("Class ID must be an integer") from e
    name = (data.get("staff_name") or "").strip()
    if not name:
        raise ValidationError("Staff name is required")
    if len(name) > 80:
        raise ValidationError("Staff name must be 80 characters or fewer")
    out["staff_name"] = name
    out["staff_id"] = (data.get("staff_id") or "").strip() or None
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    role = (data.get("role") or "Class Teacher").strip()
    if role not in ROLES:
        raise ValidationError(f"Role must be one of {', '.join(ROLES)}")
    out["role"] = role
    is_primary = data.get("is_primary")
    out["is_primary"] = bool(is_primary)
    sd = (data.get("start_date") or "").strip()
    if sd and not _DOB_RE.match(sd):
        raise ValidationError("Start date must be YYYY-MM-DD")
    ed = (data.get("end_date") or "").strip()
    if ed and not _DOB_RE.match(ed):
        raise ValidationError("End date must be YYYY-MM-DD")
    if sd and ed and ed < sd:
        raise ValidationError("End date cannot be before start date")
    out["start_date"] = sd or None
    out["end_date"] = ed or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def _sync_primary_to_class(class_id: int, academic_year: str) -> None:
    """Reflect the current ``is_primary`` assignment back to
    ``classes.teacher``. If none is primary, leave it untouched.
    """
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT staff_name FROM class_teacher_assignments "
                "WHERE class_id = ? AND academic_year = ? "
                "AND is_primary = 1 LIMIT 1",
                (class_id, academic_year),
            ).fetchone()
            if r is None:
                return
            conn.execute(
                "UPDATE classes SET teacher = ?, "
                "updated_at = datetime('now') WHERE class_id = ?",
                (r["staff_name"], class_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to sync primary teacher for class %d", class_id)


def create(data: dict[str, Any]) -> Assignment:
    init_db()
    payload = _validate(data)
    cls = classes_data.get(payload["class_id"])
    if cls is None:
        raise ValidationError(f"No class #{payload['class_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assignment_id FROM class_teacher_assignments "
                "WHERE class_id = ? AND staff_name = ? "
                "AND academic_year = ? AND role = ?",
                (payload["class_id"], payload["staff_name"],
                 payload["academic_year"], payload["role"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Staff {payload['staff_name']!r} already assigned to "
                    f"class #{payload['class_id']} as "
                    f"{payload['role']} in {payload['academic_year']} "
                    f"(#{dup['assignment_id']})")
            if payload["is_primary"]:
                # Demote any existing primary for this (class, year).
                conn.execute(
                    "UPDATE class_teacher_assignments SET is_primary = 0 "
                    "WHERE class_id = ? AND academic_year = ? "
                    "AND is_primary = 1",
                    (payload["class_id"], payload["academic_year"]),
                )
            cur = conn.execute(
                """INSERT INTO class_teacher_assignments
                       (class_id, staff_name, staff_id, academic_year,
                        role, is_primary, start_date, end_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["class_id"], payload["staff_name"],
                 payload["staff_id"], payload["academic_year"],
                 payload["role"], 1 if payload["is_primary"] else 0,
                 payload["start_date"], payload["end_date"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create class teacher assignment")
        raise
    if payload["is_primary"]:
        _sync_primary_to_class(payload["class_id"], payload["academic_year"])
    rec = get(new_id)
    assert rec is not None
    logger.info("Assigned %s to class %s (#%d) as %s (%s%s)",
                rec.staff_name, cls.name, cls.class_id, rec.role,
                rec.academic_year, ", primary" if rec.is_primary else "")
    return rec


def get(assignment_id: int) -> Assignment | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM class_teacher_assignments "
                "WHERE assignment_id = ?",
                (assignment_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get assignment(%s) failed", assignment_id)
        raise
    return _row(r) if r else None


def update(assignment_id: int, data: dict[str, Any]) -> Assignment:
    init_db()
    existing = get(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    merged = {
        "class_id":      data.get("class_id", existing.class_id),
        "staff_name":    data.get("staff_name", existing.staff_name),
        "staff_id":      data.get("staff_id", existing.staff_id),
        "academic_year": data.get("academic_year", existing.academic_year),
        "role":          data.get("role", existing.role),
        "is_primary":    data.get("is_primary", existing.is_primary),
        "start_date":    data.get("start_date", existing.start_date),
        "end_date":      data.get("end_date", existing.end_date),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if classes_data.get(payload["class_id"]) is None:
        raise ValidationError(f"No class #{payload['class_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT assignment_id FROM class_teacher_assignments "
                "WHERE class_id = ? AND staff_name = ? "
                "AND academic_year = ? AND role = ? "
                "AND assignment_id <> ?",
                (payload["class_id"], payload["staff_name"],
                 payload["academic_year"], payload["role"], assignment_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another assignment with the same "
                    f"class/staff/year/role already exists "
                    f"(#{dup['assignment_id']})")
            if payload["is_primary"]:
                conn.execute(
                    "UPDATE class_teacher_assignments SET is_primary = 0 "
                    "WHERE class_id = ? AND academic_year = ? "
                    "AND is_primary = 1 AND assignment_id <> ?",
                    (payload["class_id"], payload["academic_year"],
                     assignment_id),
                )
            conn.execute(
                """UPDATE class_teacher_assignments SET
                       class_id = ?, staff_name = ?, staff_id = ?,
                       academic_year = ?, role = ?, is_primary = ?,
                       start_date = ?, end_date = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE assignment_id = ?""",
                (payload["class_id"], payload["staff_name"],
                 payload["staff_id"], payload["academic_year"],
                 payload["role"], 1 if payload["is_primary"] else 0,
                 payload["start_date"], payload["end_date"],
                 payload["notes"], assignment_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update assignment #%d", assignment_id)
        raise
    if payload["is_primary"]:
        _sync_primary_to_class(payload["class_id"], payload["academic_year"])
    rec = get(assignment_id)
    assert rec is not None
    logger.info("Updated assignment #%d", assignment_id)
    return rec


def set_primary(assignment_id: int) -> Assignment:
    """Make this assignment the primary one for its (class, year)."""
    init_db()
    existing = get(assignment_id)
    if existing is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE class_teacher_assignments SET is_primary = 0 "
                "WHERE class_id = ? AND academic_year = ?",
                (existing.class_id, existing.academic_year),
            )
            conn.execute(
                "UPDATE class_teacher_assignments SET is_primary = 1, "
                "updated_at = datetime('now') WHERE assignment_id = ?",
                (assignment_id,),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("set_primary(%s) failed", assignment_id)
        raise
    _sync_primary_to_class(existing.class_id, existing.academic_year)
    rec = get(assignment_id)
    assert rec is not None
    logger.info("Assignment #%d set as primary for class %d / %s",
                assignment_id, existing.class_id, existing.academic_year)
    return rec


def delete(assignment_id: int) -> bool:
    init_db()
    existing = get(assignment_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM class_teacher_assignments "
                "WHERE assignment_id = ?",
                (assignment_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete assignment #%d", assignment_id)
        raise
    if deleted:
        logger.info("Deleted assignment #%d (was %s for class %d in %s)",
                    assignment_id, existing.staff_name,
                    existing.class_id, existing.academic_year)
    return deleted


def list_assignments(
    *, class_id: int | None = None,
    academic_year: str | None = None,
    role: str | None = None,
    staff_name: str | None = None,
) -> list[tuple[Assignment, SchoolClass | None]]:
    init_db()
    if role is not None and role not in ROLES:
        raise ValidationError(f"Role filter must be one of {', '.join(ROLES)}")
    where: list[str] = []
    params: list[Any] = []
    if class_id is not None:
        where.append("class_id = ?")
        params.append(class_id)
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if role:
        where.append("role = ?")
        params.append(role)
    if staff_name:
        where.append("staff_name LIKE ?")
        params.append(f"%{staff_name.strip()}%")
    sql = "SELECT * FROM class_teacher_assignments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, class_id, is_primary DESC, role, staff_name"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_assignments failed")
        raise
    out: list[tuple[Assignment, SchoolClass | None]] = []
    for r in rows:
        a = _row(r)
        cls = classes_data.get(a.class_id)
        out.append((a, cls))
    return out


def list_for_class(class_id: int,
                   academic_year: str | None = None) -> list[Assignment]:
    init_db()
    if classes_data.get(class_id) is None:
        raise ValidationError(f"No class #{class_id}")
    where = "WHERE class_id = ?"
    params: list[Any] = [class_id]
    if academic_year:
        where += " AND academic_year = ?"
        params.append(academic_year.strip())
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM class_teacher_assignments {where} "
                f"ORDER BY academic_year DESC, is_primary DESC, role, staff_name",
                tuple(params),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_class(%s) failed", class_id)
        raise
    return [_row(r) for r in rows]


def list_for_staff(staff_name: str) -> list[tuple[Assignment, SchoolClass | None]]:
    init_db()
    name = (staff_name or "").strip()
    if not name:
        raise ValidationError("Staff name is required")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM class_teacher_assignments "
                "WHERE staff_name LIKE ? "
                "ORDER BY academic_year DESC, class_id",
                (f"%{name}%",),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_staff(%s) failed", name)
        raise
    out: list[tuple[Assignment, SchoolClass | None]] = []
    for r in rows:
        a = _row(r)
        out.append((a, classes_data.get(a.class_id)))
    return out


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year "
                "FROM class_teacher_assignments "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]


def counts(academic_year: str | None = None) -> dict[str, int]:
    init_db()
    where = ""
    params: tuple = ()
    if academic_year:
        where = " WHERE academic_year = ?"
        params = (academic_year.strip(),)
    try:
        with _connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM class_teacher_assignments{where}",
                params,
            ).fetchone()[0]
            primary = conn.execute(
                f"SELECT COUNT(*) FROM class_teacher_assignments"
                f"{where + ' AND' if where else ' WHERE'} is_primary = 1",
                params,
            ).fetchone()[0]
            distinct_staff = conn.execute(
                f"SELECT COUNT(DISTINCT staff_name) "
                f"FROM class_teacher_assignments{where}",
                params,
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("counts failed")
        raise
    return {"total": total, "primary": primary, "staff": distinct_staff}
