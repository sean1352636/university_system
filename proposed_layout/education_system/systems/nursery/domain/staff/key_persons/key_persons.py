"""Domain layer for Key Person Assignment (Nursery System).

The EYFS requires every child to have a named *key person* — a practitioner
responsible for their care, settling and development. This module manages those
assignments. It does not own a new table: the assignment lives in the existing
``pupils.key_person`` column (FK to ``staff``), so this module reads and writes
that column directly and presents it two ways — per child, and as each
practitioner's caseload.

Follows the 4-layer pattern: validation + SQLite access here, CLI in
``key_persons_cli.py``, Tk GUI in ``key_persons_views.py``.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.nursery.infrastructure.database import connect, init_db

logger = logging.getLogger(__name__)

FEATURE_NAME = "Key Person Assignment"
CATEGORY = "Children & Admissions"


class ValidationError(ValueError):
    """Raised for invalid key-person assignment input."""


@dataclass
class Assignment:
    pupil_id: str
    child_name: str
    room: str | None
    key_person: str | None
    key_person_name: str | None
    funded_hours: str | None

    @property
    def has_key_person(self) -> bool:
        return bool(self.key_person)


@dataclass
class Caseload:
    staff_id: str
    staff_name: str
    room: str | None
    children: list[Assignment] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.children)


def _ensure_schema() -> None:
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for key persons")
        raise


_SELECT = """
SELECT p.pupil_id,
       TRIM(p.first_name || ' ' || p.last_name) AS child_name,
       p.room, p.key_person, p.funded_hours,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS key_person_name
FROM pupils p
LEFT JOIN staff s ON s.staff_id = p.key_person
WHERE p.status = 'active'
"""


def _row(r: sqlite3.Row) -> Assignment:
    return Assignment(
        pupil_id=r["pupil_id"],
        child_name=r["child_name"],
        room=r["room"],
        key_person=r["key_person"],
        key_person_name=(r["key_person_name"] or None),
        funded_hours=r["funded_hours"],
    )


# ── Reads ────────────────────────────────────────────────────────────────────

def list_assignments(*, room: str | None = None,
                     unassigned_only: bool = False) -> list[Assignment]:
    _ensure_schema()
    sql = _SELECT
    params: list[Any] = []
    if room:
        sql += " AND p.room = ?"
        params.append(room)
    if unassigned_only:
        sql += " AND (p.key_person IS NULL OR p.key_person = '')"
    sql += " ORDER BY p.room, child_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_assignments failed")
        raise
    return [_row(r) for r in rows]


def list_unassigned() -> list[Assignment]:
    """Active children with no key person — an EYFS compliance gap."""
    return list_assignments(unassigned_only=True)


def get_assignment(pupil_id: str) -> Assignment | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " AND p.pupil_id = ?", (pupil_id,)).fetchone()
    except sqlite3.Error:
        logger.exception("get_assignment(%s) failed", pupil_id)
        raise
    return _row(row) if row else None


def list_staff_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id) — room")`` pairs for key-person pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name, room FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_staff_choices failed")
        raise
    out = []
    for r in rows:
        room = f" — {r['room']}" if r["room"] else ""
        out.append((r["staff_id"],
                    f"{r['first_name']} {r['last_name']} ({r['staff_id']}){room}"))
    return out


def list_caseloads(*, include_unassigned: bool = True) -> list[Caseload]:
    """Group active children by their key person (practitioner caseloads)."""
    _ensure_schema()
    assignments = list_assignments()
    try:
        with connect() as conn:
            staff_rows = conn.execute(
                "SELECT staff_id, first_name, last_name, room FROM staff "
                "ORDER BY last_name, first_name").fetchall()
    except sqlite3.Error:
        logger.exception("list_caseloads failed")
        raise

    by_staff: dict[str, Caseload] = {
        r["staff_id"]: Caseload(
            staff_id=r["staff_id"],
            staff_name=f"{r['first_name']} {r['last_name']}",
            room=r["room"],
        )
        for r in staff_rows
    }
    unassigned = Caseload(staff_id="", staff_name="(no key person)", room=None)
    for a in assignments:
        if a.key_person and a.key_person in by_staff:
            by_staff[a.key_person].children.append(a)
        else:
            unassigned.children.append(a)

    result = list(by_staff.values())
    if include_unassigned and unassigned.children:
        result.append(unassigned)
    return result


def summary() -> dict[str, int]:
    """Counts for the header: total active, assigned, unassigned."""
    assignments = list_assignments()
    assigned = sum(1 for a in assignments if a.has_key_person)
    return {
        "total": len(assignments),
        "assigned": assigned,
        "unassigned": len(assignments) - assigned,
    }


# ── Writes ───────────────────────────────────────────────────────────────────

def _staff_exists(conn: sqlite3.Connection, staff_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM staff WHERE staff_id = ?", (staff_id,)).fetchone() is not None


def assign(pupil_id: str, staff_id: str | None) -> Assignment:
    """Set (or clear, with ``None``/empty) a child's key person."""
    _ensure_schema()
    staff_id = (staff_id or "").strip() or None
    try:
        with connect() as conn:
            if not conn.execute(
                    "SELECT 1 FROM pupils WHERE pupil_id = ?",
                    (pupil_id,)).fetchone():
                raise ValidationError(f"No child on roll with id {pupil_id}")
            if staff_id is not None and not _staff_exists(conn, staff_id):
                raise ValidationError(f"No staff member with id {staff_id}")
            conn.execute(
                "UPDATE pupils SET key_person = ? WHERE pupil_id = ?",
                (staff_id, pupil_id))
            conn.commit()
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Database error assigning key person for %s", pupil_id)
        raise
    a = get_assignment(pupil_id)
    if a is None:
        raise ValidationError(f"No child on roll with id {pupil_id}")
    logger.info("Set key person for %s -> %s", pupil_id, staff_id or "(none)")
    return a


def assign_room(room: str, staff_id: str) -> int:
    """Assign one key person to every unassigned child in a room. Returns count."""
    _ensure_schema()
    staff_id = (staff_id or "").strip()
    if not staff_id:
        raise ValidationError("A staff member is required")
    try:
        with connect() as conn:
            if not _staff_exists(conn, staff_id):
                raise ValidationError(f"No staff member with id {staff_id}")
            cur = conn.execute(
                "UPDATE pupils SET key_person = ? WHERE status = 'active' "
                "AND room = ? AND (key_person IS NULL OR key_person = '')",
                (staff_id, room))
            conn.commit()
            n = cur.rowcount
    except sqlite3.Error as e:
        if isinstance(e, ValidationError):
            raise
        logger.exception("Bulk key-person assign failed for room %s", room)
        raise
    logger.info("Bulk-assigned key person %s to %d unassigned child(ren) in %s",
                staff_id, n, room)
    return n
