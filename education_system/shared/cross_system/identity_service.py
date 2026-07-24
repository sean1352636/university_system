"""Canonical cross-system student identity (the ``student_journey`` registry).

One ``student_journey`` row per real person, identified by a stable
``journey_id`` and matched across systems on (date_of_birth, last_name,
first_name). Each system links its local student id into its own slot
(``school_*`` / ``college_*`` / ``university_*`` / ``primary_*``) rather
than every system duplicating and re-keying demographics on transfer.

The sixth-form system is the ``college`` slot; the university system is
the ``university`` slot (matching the launcher's auth seed keys).

This is the service the schema comment in ``shared/auth/schema.py``
refers to; the table already exists there and is created by
``initialise_auth_db``.
"""

from __future__ import annotations

import logging
import uuid

from education_system.shared.auth.db import connect
from education_system.shared.auth.schema import initialise_auth_db

logger = logging.getLogger(__name__)

# system key -> (pk_column, student_id_column) in student_journey
SYSTEM_SLOTS: dict[str, tuple[str, str]] = {
    "nursery":    ("nursery_pk", "nursery_student_id"),
    "primary":    ("primary_pk", "primary_student_id"),
    "secondary":     ("school_pk", "school_student_id"),
    "sixth_form":    ("college_pk", "college_student_id"),
    "university": ("university_pk", "university_student_id"),
}

_initialised: set[str] = set()


def _ensure(db_path: str | None) -> None:
    key = db_path or "<default>"
    if key in _initialised:
        return
    try:
        initialise_auth_db(db_path)
    except Exception:
        logger.debug("identity_service: auth schema init skipped",
                     exc_info=True)
    _initialised.add(key)


def _slots(system: str) -> tuple[str, str]:
    if system not in SYSTEM_SLOTS:
        raise ValueError(
            f"Unknown system {system!r}; expected one of "
            f"{', '.join(SYSTEM_SLOTS)}")
    return SYSTEM_SLOTS[system]


def _row_to_dict(row) -> dict | None:
    return dict(row) if row is not None else None


def get(journey_id: str, *, db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM student_journey WHERE journey_id = ?",
            (journey_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def find_by_identity(first_name: str, last_name: str,
                     date_of_birth: str, *,
                     db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    conn = connect(db_path)
    try:
        r = conn.execute(
            "SELECT * FROM student_journey "
            "WHERE date_of_birth = ? AND legal_last_name = ? "
            "AND legal_first_name = ?",
            (date_of_birth, last_name, first_name)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def find_by_student(system: str, student_id: str, *,
                    db_path: str | None = None) -> dict | None:
    _ensure(db_path)
    _pk, id_col = _slots(system)
    conn = connect(db_path)
    try:
        r = conn.execute(
            f"SELECT * FROM student_journey WHERE {id_col} = ?",
            (student_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_dict(r)


def link_system(journey_id: str, system: str, *,
                student_id: str | None = None, pk: int | None = None,
                set_current: bool = False,
                db_path: str | None = None) -> dict:
    """Point a system's slot at this journey. Idempotent."""
    _ensure(db_path)
    pk_col, id_col = _slots(system)
    sets, args = [], []
    if student_id is not None:
        sets.append(f"{id_col} = ?")
        args.append(student_id)
    if pk is not None:
        sets.append(f"{pk_col} = ?")
        args.append(pk)
    if set_current:
        sets.append("current_system = ?")
        args.append(system)
    sets.append("updated_at = datetime('now')")
    args.append(journey_id)
    conn = connect(db_path)
    try:
        conn.execute(
            f"UPDATE student_journey SET {', '.join(sets)} "
            "WHERE journey_id = ?", args)
        conn.commit()
    finally:
        conn.close()
    out = get(journey_id, db_path=db_path)
    if out is None:
        raise ValueError(f"No journey {journey_id}")
    return out


def get_or_create_journey(*, first_name: str, last_name: str,
                          date_of_birth: str, system: str,
                          student_id: str | None = None,
                          pk: int | None = None,
                          nhs_number: str | None = None,
                          upn: str | None = None,
                          db_path: str | None = None) -> str:
    """Return the canonical ``journey_id`` for a person, creating the
    registry row if this is the first system to see them. Links the
    calling system's slot to ``student_id`` and marks it current."""
    _ensure(db_path)
    if not (first_name and last_name and date_of_birth):
        raise ValueError(
            "first_name, last_name and date_of_birth are required "
            "to register a journey")
    existing = find_by_identity(first_name, last_name, date_of_birth,
                                db_path=db_path)
    if existing is not None:
        jid = existing["journey_id"]
        link_system(jid, system, student_id=student_id, pk=pk,
                    set_current=True, db_path=db_path)
        return jid

    pk_col, id_col = _slots(system)
    jid = str(uuid.uuid4())
    conn = connect(db_path)
    try:
        conn.execute(
            f"""INSERT INTO student_journey
                 (journey_id, legal_first_name, legal_last_name,
                  date_of_birth, nhs_number, upn, current_system,
                  status, {id_col}, {pk_col})
                 VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (jid, first_name, last_name, date_of_birth, nhs_number,
             upn, system, student_id, pk))
        conn.commit()
    finally:
        conn.close()
    logger.info("Created student_journey %s for %s %s (%s) in %s",
                jid, first_name, last_name, date_of_birth, system)
    return jid


def record_transition(journey_id: str, *, to_system: str,
                      from_system: str | None = None,
                      reason: str | None = None,
                      actor_user_id: int | None = None,
                      notes: str | None = None,
                      db_path: str | None = None) -> None:
    """Append an audit row and update the journey's current system."""
    _ensure(db_path)
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO student_journey_transitions
                 (journey_id, from_system, to_system, reason,
                  actor_user_id, notes)
                 VALUES (?, ?, ?, ?, ?, ?)""",
            (journey_id, from_system, to_system, reason,
             actor_user_id, notes))
        conn.execute(
            "UPDATE student_journey SET current_system = ?, "
            "updated_at = datetime('now') WHERE journey_id = ?",
            (to_system, journey_id))
        conn.commit()
    finally:
        conn.close()
    logger.info("Journey %s transitioned %s -> %s", journey_id,
                from_system or "?", to_system)
