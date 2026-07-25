"""Shared ``Person`` abstraction — the one identity behind five systems.

Each system models the same human in its own table (``pupils`` in the
K-12 systems, ``students`` in college/university) with its own copy of the
demographic columns. The canonical, never-changing facts about a person —
legal name, date of birth, NHS number, UPN — live in exactly one place:
the ``student_journey`` registry in ``auth.db`` (see
:mod:`education_system.platform.cross_system.identity_service`).

This module is the read/write face of that single record:

* :class:`Person` — an immutable view of the canonical demographics plus
  the per-system local ids the person is known by.
* :func:`get` / :func:`get_by_student` — resolve a person by ``journey_id``
  or by any system's local student id.
* :func:`demographics` — just the immutable identity fields, for callers
  (e.g. progression intake) that would otherwise copy them around.
* :func:`update_demographics` — correct the legal identity in one place.
* :func:`link_local_record` — stamp ``journey_id`` onto a system's own
  pupil/student row so the domain table FKs back to the shared identity.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from education_system.platform.identity.auth.db import connect
from education_system.platform.cross_system import identity_service
from education_system.platform.kernel.database.paths import SYSTEM_DB_PATHS

logger = logging.getLogger(__name__)

# Per-system local pupil/student table + primary-key column. Used to stamp
# the shared journey_id back onto the domain row ("FK to shared identity").
_LOCAL_TABLE: dict[str, tuple[str, str]] = {
    "nursery":    ("pupils", "pupil_id"),
    "primary":    ("pupils", "pupil_id"),
    "secondary":     ("pupils", "pupil_id"),
    "sixth_form":    ("students", "student_id"),
    "university": ("students", "student_id"),
}

# The immutable identity fields held canonically on student_journey.
DEMOGRAPHIC_FIELDS = (
    "legal_first_name", "legal_last_name", "date_of_birth",
    "nhs_number", "upn",
)


@dataclass(frozen=True)
class Person:
    """An immutable view of one human across all five systems."""

    journey_id: str
    legal_first_name: str
    legal_last_name: str
    date_of_birth: str | None
    nhs_number: str | None = None
    upn: str | None = None
    current_system: str | None = None
    status: str | None = None
    # system key -> local student/pupil id (only systems the person is in).
    local_ids: dict[str, str] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.legal_first_name} {self.legal_last_name}".strip()

    def local_id(self, system: str) -> str | None:
        """The id this person is known by in ``system`` (or None)."""
        return self.local_ids.get(system)

    @property
    def systems(self) -> list[str]:
        """The systems this person currently has a record in, in order."""
        from education_system.platform.cross_system.progression import PHASE_ORDER
        return [s for s in PHASE_ORDER if s in self.local_ids]

    def demographics(self) -> dict:
        """Just the canonical, never-changing identity fields."""
        return {f: getattr(self, f) for f in DEMOGRAPHIC_FIELDS}


def _from_journey_row(row: dict) -> Person:
    local_ids: dict[str, str] = {}
    for system, (_pk_col, id_col) in identity_service.SYSTEM_SLOTS.items():
        val = row.get(id_col)
        if val:
            local_ids[system] = val
    return Person(
        journey_id=row["journey_id"],
        legal_first_name=row.get("legal_first_name") or "",
        legal_last_name=row.get("legal_last_name") or "",
        date_of_birth=row.get("date_of_birth"),
        nhs_number=row.get("nhs_number"),
        upn=row.get("upn"),
        current_system=row.get("current_system"),
        status=row.get("status"),
        local_ids=local_ids,
    )


def get(journey_id: str, *, db_path: str | None = None) -> Person | None:
    """Resolve a :class:`Person` by canonical ``journey_id``."""
    row = identity_service.get(journey_id, db_path=db_path)
    return _from_journey_row(row) if row else None


def get_by_student(system: str, student_id: str, *,
                   db_path: str | None = None) -> Person | None:
    """Resolve a :class:`Person` by any system's local student id."""
    row = identity_service.find_by_student(system, student_id,
                                           db_path=db_path)
    return _from_journey_row(row) if row else None


def demographics(journey_id: str, *,
                 db_path: str | None = None) -> dict | None:
    """The immutable identity fields for a person, or None if unknown.

    Callers that move a person between systems should read demographics
    from here instead of copying name/DOB around by hand.
    """
    person = get(journey_id, db_path=db_path)
    return person.demographics() if person else None


def update_demographics(
    journey_id: str,
    *,
    legal_first_name: str | None = None,
    legal_last_name: str | None = None,
    date_of_birth: str | None = None,
    nhs_number: str | None = None,
    upn: str | None = None,
    db_path: str | None = None,
) -> Person:
    """Correct the canonical identity in the one place it lives.

    Only the fields passed (non-None) are changed. Returns the refreshed
    :class:`Person`. Raises ``ValueError`` if the journey doesn't exist.
    """
    updates = {
        "legal_first_name": legal_first_name,
        "legal_last_name": legal_last_name,
        "date_of_birth": date_of_birth,
        "nhs_number": nhs_number,
        "upn": upn,
    }
    sets, args = [], []
    for col, val in updates.items():
        if val is not None:
            sets.append(f"{col} = ?")
            args.append(val)
    if not sets:
        person = get(journey_id, db_path=db_path)
        if person is None:
            raise ValueError(f"No journey {journey_id}")
        return person
    sets.append("updated_at = datetime('now')")
    args.append(journey_id)
    conn = connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE student_journey SET {', '.join(sets)} "
            "WHERE journey_id = ?", args)
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"No journey {journey_id}")
    finally:
        conn.close()
    person = get(journey_id, db_path=db_path)
    assert person is not None
    logger.info("Updated canonical demographics for journey %s", journey_id)
    return person


def link_local_record(system: str, student_id: str, journey_id: str, *,
                      db_path: str | None = None) -> bool:
    """Stamp ``journey_id`` onto the system's own pupil/student row.

    Mirrors the university intake's ``_stamp_journey_id`` for every system:
    the domain table keeps its columns but now carries a foreign key back
    to the shared identity, so a local record can resolve its canonical
    person without a name match. Best-effort — returns True on success,
    False (logged at debug) on any problem; never raises.
    """
    spec = _LOCAL_TABLE.get(system)
    if not spec:
        return False
    table, pk_col = spec
    path = db_path or SYSTEM_DB_PATHS.get(system)
    if not path:
        return False
    try:
        conn = sqlite3.connect(str(path))
        try:
            cols = {r[1] for r in conn.execute(
                f"PRAGMA table_info({table})").fetchall()}
            if not cols:
                return False  # table not present in this db
            if "journey_id" not in cols:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN journey_id TEXT")
            conn.execute(
                f"UPDATE {table} SET journey_id = ? WHERE {pk_col} = ?",
                (journey_id, student_id))
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        logger.debug("link_local_record failed for %s/%s", system,
                     student_id, exc_info=True)
        return False


__all__ = [
    "Person",
    "DEMOGRAPHIC_FIELDS",
    "get",
    "get_by_student",
    "demographics",
    "update_demographics",
    "link_local_record",
]
