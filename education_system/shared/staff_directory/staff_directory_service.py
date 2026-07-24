"""Cross-system staff directory — one record per real staff member.

The auth layer already lets one user hold roles in several systems
(``user_systems``), but each system still keeps its *own* ``staff`` row, so
a teacher who works across secondary and sixth form is two unrelated HR
records. This is the missing HR-domain link: a ``staff_directory`` registry
(in ``auth.db``) with one row per person and a per-system slot for each
local ``staff_id`` — the staff parallel to ``student_journey``.

Staff have no shared natural key (system emails are derived per system),
so people are matched on legal name. Callers that know two records are the
same person can also link them explicitly via :func:`link_system`.
"""

from __future__ import annotations

import logging
import uuid

from education_system.shared.auth.db import connect
from education_system.shared.auth.schema import initialise_auth_db

logger = logging.getLogger(__name__)

# system key -> staff-id slot column in staff_directory.
STAFF_SLOTS: dict[str, str] = {
    "nursery":    "nursery_staff_id",
    "primary":    "primary_staff_id",
    "secondary":     "school_staff_id",
    "sixth_form":    "college_staff_id",
    "university": "university_staff_id",
}

_initialised: set[str] = set()


def _ensure(db_path: str | None) -> None:
    key = db_path or "<default>"
    if key in _initialised:
        return
    try:
        initialise_auth_db(db_path)
    except Exception:
        logger.debug("staff_directory: auth schema init skipped",
                     exc_info=True)
    _initialised.add(key)


def _slot(system: str) -> str:
    if system not in STAFF_SLOTS:
        raise ValueError(
            f"Unknown system {system!r}; expected one of "
            f"{', '.join(STAFF_SLOTS)}")
    return STAFF_SLOTS[system]


def _row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def get(staff_person_id: str, *, db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM staff_directory WHERE staff_person_id = ?",
            (staff_person_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def find_by_name(first_name: str, last_name: str, *,
                 db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM staff_directory WHERE legal_last_name = ? "
            "AND legal_first_name = ?", (last_name, first_name)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def get_by_staff(system: str, staff_id: str, *,
                 db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    col = _slot(system)
    conn = connect(db_path)
    try:
        r = conn.execute(
            f"SELECT * FROM staff_directory WHERE {col} = ?",
            (staff_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def link_system(staff_person_id: str, system: str, *, staff_id: str,
                db_path: str | None = None) -> dict:
    """Point a system's slot at this staff person. Idempotent."""
    _ensure(db_path)
    col = _slot(system)
    conn = connect(db_path)
    try:
        conn.execute(
            f"UPDATE staff_directory SET {col} = ?, "
            "updated_at = datetime('now') WHERE staff_person_id = ?",
            (staff_id, staff_person_id))
        conn.commit()
    finally:
        conn.close()
    out = get(staff_person_id, db_path=db_path)
    if out is None:
        raise ValueError(f"No staff person {staff_person_id}")
    return out


def register_staff(system: str, *, staff_id: str, first_name: str,
                   last_name: str, email: str | None = None,
                   role: str | None = None,
                   db_path: str | None = None) -> str:
    """Return the canonical ``staff_person_id`` for a staff member, creating
    the directory row if this is the first system to employ them, and
    linking this system's slot. Matched on legal name."""
    _ensure(db_path)
    if not (first_name and last_name):
        raise ValueError("first_name and last_name are required")
    existing = find_by_name(first_name, last_name, db_path=db_path)
    if existing is not None:
        spid = existing["staff_person_id"]
        link_system(spid, system, staff_id=staff_id, db_path=db_path)
        return spid

    col = _slot(system)
    spid = str(uuid.uuid4())
    conn = connect(db_path)
    try:
        conn.execute(
            f"""INSERT INTO staff_directory
                 (staff_person_id, legal_first_name, legal_last_name,
                  email, primary_role, {col})
                 VALUES (?, ?, ?, ?, ?, ?)""",
            (spid, first_name, last_name, email, role, staff_id))
        conn.commit()
    finally:
        conn.close()
    logger.info("Created staff_directory %s for %s %s (%s) in %s",
                spid, first_name, last_name, role or "?", system)
    return spid


def register_local_staff(system: str, *, staff_id: str, first_name: str,
                         last_name: str, email: str | None = None,
                         role: str | None = None,
                         db_path: str | None = None) -> str | None:
    """Best-effort wrapper for create-staff hooks: never raises."""
    try:
        return register_staff(system, staff_id=staff_id,
                              first_name=first_name, last_name=last_name,
                              email=email, role=role, db_path=db_path)
    except Exception:
        logger.debug("Staff directory registration skipped for %s/%s",
                     system, staff_id, exc_info=True)
        return None


def systems_for(staff_person_id: str, *,
                db_path: str | None = None) -> dict[str, str]:
    """Return {system: local_staff_id} for every system this person is in."""
    row = get(staff_person_id, db_path=db_path)
    if not row:
        return {}
    return {sys: row[col] for sys, col in STAFF_SLOTS.items() if row.get(col)}


__all__ = [
    "STAFF_SLOTS",
    "get",
    "find_by_name",
    "get_by_staff",
    "link_system",
    "register_staff",
    "register_local_staff",
    "systems_for",
]
