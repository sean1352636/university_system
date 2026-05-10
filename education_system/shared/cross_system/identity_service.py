"""Cross-system student identity service.

Owns the ``student_journey`` table in the shared auth database — the
canonical link between a single student and their per-system primary
keys (primary / secondary / college / university). Every cross-system
event references a ``journey_id`` from this table rather than a raw
per-system pk.

This is **separate** from ``journey_service.JourneyService`` (in this
same package), which is a read-only journey *reconstructor* that scans
across DBs by name. The two are complementary: this module is the
write side that maintains an authoritative link, the other is the
read-only fallback used by the dashboard for un-linked students.

Step 1 of the cross-system integration plan — identity continuity.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from typing import Any

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)


SYSTEMS = ("primary", "school", "college", "university")
TRANSITION_REASONS = (
    "registration", "progression", "transfer", "withdrawal",
    "graduation", "gdpr_redaction",
)

# Per-system column suffixes on student_journey.
_PK_COLUMN = {
    "primary":    "primary_pk",
    "school":     "school_pk",
    "college":    "college_pk",
    "university": "university_pk",
}
_SID_COLUMN = {
    "primary":    "primary_student_id",
    "school":     "school_student_id",
    "college":    "college_student_id",
    "university": "university_student_id",
}


class IdentityError(ValueError):
    """Raised on invalid system keys, missing rows, or constraint conflicts."""


def _validate_system(system: str) -> None:
    if system not in SYSTEMS:
        raise IdentityError(
            f"Unknown system {system!r}; expected one of {SYSTEMS}.")


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Journey lifecycle
# ---------------------------------------------------------------------------

def get_or_create_journey(
    *,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    current_system: str,
    nhs_number: str | None = None,
    upn: str | None = None,
    db_path: str | None = None,
) -> str:
    """Return the ``journey_id`` for a student, creating one if necessary.

    Match strategy is the unique ``(date_of_birth, last_name, first_name)``
    index. Names are normalised (stripped + casefolded) before comparison
    so ``"O'Brien"`` doesn't fork on whitespace differences.

    The ``current_system`` field is only set on a fresh insert — existing
    rows are never mutated by this call. To record a transition use
    ``record_transition``.
    """
    _validate_system(current_system)
    if not first_name or not last_name or not date_of_birth:
        raise IdentityError(
            "first_name, last_name and date_of_birth are required to "
            "create or look up a journey.")
    fn = first_name.strip()
    ln = last_name.strip()
    dob = date_of_birth.strip()

    conn = connect(db_path)
    try:
        row = conn.execute(
            """SELECT journey_id FROM student_journey
                WHERE date_of_birth = ?
                  AND lower(legal_last_name) = lower(?)
                  AND lower(legal_first_name) = lower(?)""",
            (dob, ln, fn),
        ).fetchone()
        if row:
            return row["journey_id"]

        journey_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO student_journey
                (journey_id, legal_first_name, legal_last_name,
                 date_of_birth, nhs_number, upn, current_system, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active')""",
            (journey_id, fn, ln, dob, nhs_number, upn, current_system),
        )
        conn.execute(
            """INSERT INTO student_journey_transitions
                (journey_id, from_system, to_system, reason)
                VALUES (?, NULL, ?, 'registration')""",
            (journey_id, current_system),
        )
        conn.commit()
        logger.info(
            "Journey created: %s (%s %s, dob=%s, system=%s)",
            journey_id, fn, ln, dob, current_system,
        )
        return journey_id
    finally:
        conn.close()


def attach_system_record(
    journey_id: str, system: str,
    *, pk: int | None = None, student_id: str | None = None,
    db_path: str | None = None,
) -> None:
    """Link a per-system student record (``pk`` and/or ``student_id``) to a
    journey.

    At least one of ``pk`` / ``student_id`` must be supplied. The
    university subsystem uses a TEXT primary key on its ``students``
    table, so for that system only ``student_id`` is meaningful and
    ``pk`` should be left ``None``.

    Idempotent: re-linking the same ``(system, pk, student_id)`` triple
    is a no-op. Conflict detection is by intent — if a different pk or
    student_id is already attached for this system, raises
    ``IdentityError`` rather than silently overwriting.
    """
    _validate_system(system)
    if pk is None and not student_id:
        raise IdentityError("attach_system_record requires pk or student_id.")
    pk_col = _PK_COLUMN[system]
    sid_col = _SID_COLUMN[system]

    conn = connect(db_path)
    try:
        row = conn.execute(
            f"SELECT {pk_col} AS pk, {sid_col} AS sid "
            "FROM student_journey WHERE journey_id = ?",
            (journey_id,),
        ).fetchone()
        if not row:
            raise IdentityError(f"No journey with id={journey_id!r}.")

        existing_pk = row["pk"]
        existing_sid = row["sid"]
        if pk is not None and existing_pk is not None and existing_pk != pk:
            raise IdentityError(
                f"Journey {journey_id} already linked to {system} pk="
                f"{existing_pk}; refusing to overwrite with {pk}.")
        if (student_id and existing_sid is not None
                and existing_sid != student_id):
            raise IdentityError(
                f"Journey {journey_id} already linked to {system} "
                f"student_id={existing_sid!r}; refusing to overwrite with "
                f"{student_id!r}.")
        if (existing_pk == pk or pk is None) and (
                (existing_sid or "") == (student_id or "")):
            return  # already attached, nothing to do

        new_pk = pk if pk is not None else existing_pk
        new_sid = student_id if student_id else existing_sid
        # Literal column whitelist (_PK_COLUMN / _SID_COLUMN) keeps the
        # identifiers untainted as far as CodeQL is concerned.
        conn.execute(
            f"UPDATE student_journey "
            f"   SET {pk_col} = ?, {sid_col} = ?, "
            f"       updated_at = datetime('now') "
            f" WHERE journey_id = ?",  # nosec B608
            (new_pk, new_sid, journey_id),
        )
        conn.commit()
        logger.info(
            "Journey %s linked to %s pk=%s (student_id=%s)",
            journey_id, system, new_pk, new_sid,
        )
    finally:
        conn.close()


def record_transition(
    journey_id: str,
    *,
    from_system: str | None,
    to_system: str,
    reason: str,
    actor_user_id: int | None = None,
    notes: str | None = None,
    db_path: str | None = None,
) -> None:
    """Append a transition row and update ``current_system`` accordingly.

    ``reason`` must be one of ``TRANSITION_REASONS``. ``from_system`` may be
    ``None`` for a first-touch registration.
    """
    _validate_system(to_system)
    if from_system is not None:
        _validate_system(from_system)
    if reason not in TRANSITION_REASONS:
        raise IdentityError(
            f"Invalid reason {reason!r}; expected one of {TRANSITION_REASONS}.")

    conn = connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT journey_id FROM student_journey WHERE journey_id = ?",
            (journey_id,),
        )
        if not cursor.fetchone():
            raise IdentityError(f"No journey with id={journey_id!r}.")

        conn.execute(
            """INSERT INTO student_journey_transitions
                (journey_id, from_system, to_system, reason,
                 actor_user_id, notes)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (journey_id, from_system, to_system, reason, actor_user_id, notes),
        )
        conn.execute(
            "UPDATE student_journey "
            "   SET current_system = ?, updated_at = datetime('now') "
            " WHERE journey_id = ?",
            (to_system, journey_id),
        )
        conn.commit()
        logger.info(
            "Journey %s transitioned %s -> %s (reason=%s actor=%s)",
            journey_id, from_system or "(new)", to_system, reason,
            actor_user_id,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------

def get_journey(journey_id: str, *, db_path: str | None = None) -> dict | None:
    """Return the journey row as a dict, or ``None`` if not found."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM student_journey WHERE journey_id = ?",
            (journey_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def find_journey_by_system_pk(
    system: str, pk: int,
    *, db_path: str | None = None,
) -> dict | None:
    """Find the journey that a given per-system pk is attached to."""
    _validate_system(system)
    pk_col = _PK_COLUMN[system]
    conn = connect(db_path)
    try:
        row = conn.execute(
            f"SELECT * FROM student_journey WHERE {pk_col} = ?",  # nosec B608
            (pk,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def find_journey_by_student_id(
    system: str, student_id: str,
    *, db_path: str | None = None,
) -> dict | None:
    """Find the journey by the per-system human-readable student id."""
    _validate_system(system)
    sid_col = _SID_COLUMN[system]
    conn = connect(db_path)
    try:
        row = conn.execute(
            f"SELECT * FROM student_journey WHERE {sid_col} = ?",  # nosec B608
            (student_id,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_transitions(
    journey_id: str, *, db_path: str | None = None,
) -> list[dict]:
    """Return all transition rows for ``journey_id`` in chronological order."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM student_journey_transitions "
            " WHERE journey_id = ? ORDER BY occurred_at, id",
            (journey_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


__all__ = [
    "SYSTEMS", "TRANSITION_REASONS", "IdentityError",
    "get_or_create_journey", "attach_system_record", "record_transition",
    "get_journey", "find_journey_by_system_pk", "find_journey_by_student_id",
    "list_transitions",
]
