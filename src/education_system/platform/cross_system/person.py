"""Shared ``Person`` abstraction — the one identity behind every system.

Each system models the same human in its own table (``pupils`` in the
K-12 systems, ``students`` in college/university, ``apprentices`` in
apprenticeships) with its own copy of the demographic columns. The
canonical, never-changing facts about a person — legal name, date of
birth, NHS number, UPN — live in exactly one place: the ``student_journey``
registry in ``auth.db`` (see
:mod:`education_system.platform.cross_system.identity_service`).

This module is the read/write face of that single record:

* :class:`Person` — an immutable view of the canonical demographics plus
  the per-system local ids the person is known by.
* :func:`get` / :func:`get_by_student` — resolve a person by ``journey_id``
  (following a merge to the survivor) or by any system's local student id.
* :func:`demographics` — just the immutable identity fields, for callers
  (e.g. progression intake) that would otherwise copy them around.
* :func:`update_demographics` — correct the legal identity in one place.
* :func:`link_local_record` — stamp ``journey_id`` onto a system's own
  pupil/student row so the domain table FKs back to the shared identity.
* :func:`all_local_records` — every (system, local id) the person has had,
  from the enrolment history as well as the latest-only slots.
* :func:`register_local_learner` — the one call a system's create path
  makes to join a new learner to the registry (never raises).
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from education_system.platform.identity.auth.db import connect
from education_system.platform.cross_system import identity_service
from education_system.paths import (
    SYSTEM_DB_PATHS,
    SYSTEM_LEARNER_TABLE,
    SYSTEM_ORDER,
)

logger = logging.getLogger(__name__)

# Per-system local pupil/student table + primary-key column. Used to stamp
# the shared journey_id back onto the domain row ("FK to shared identity").
#
# Sourced from the one registry rather than redeclared here: apprenticeships
# keeps ``apprentices``/``apprentice_id``, so the old "pupils for the K-12
# systems, students for everyone else" rule is no longer true and must not
# be re-derived per module.
_LOCAL_TABLE: dict[str, tuple[str, str]] = dict(SYSTEM_LEARNER_TABLE)

# The immutable identity fields held canonically on student_journey.
DEMOGRAPHIC_FIELDS = (
    "legal_first_name", "legal_last_name", "date_of_birth",
    "nhs_number", "upn",
)


@dataclass(frozen=True)
class Person:
    """An immutable view of one human across all systems."""

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
        """The systems this person currently has a record in, in order.

        Ordered by SYSTEM_ORDER, not by ``progression.PHASE_ORDER``: the
        latter is the five-phase *recommendation* chain and excludes
        fe_college and apprenticeships, which would silently drop an FE
        learner or an apprentice from their own list of systems.
        """
        return [s for s in SYSTEM_ORDER if s in self.local_ids]

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
    """Resolve a :class:`Person` by canonical ``journey_id``.

    A merged (tombstoned) id resolves to the surviving person, so an id
    captured before a merge keeps working.
    """
    resolved = identity_service.resolve_journey_id(journey_id,
                                                   db_path=db_path)
    if resolved is None:
        return None
    row = identity_service.get(resolved, db_path=db_path)
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
    Publishes ``learner.updated`` naming the changed fields (not their
    values: the bus is read by every system, identity corrections are not).
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
    changed = sorted(k for k, v in updates.items() if v is not None)
    row = identity_service.get(journey_id, db_path=db_path) or {}
    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    identity_service._publish(
        cross_system_bus.EVENT_LEARNER_UPDATED, journey_id=journey_id,
        idempotency_key=(f"learner.updated:demographics:{journey_id}:"
                         f"{row.get('updated_at')}:{','.join(changed)}"),
        db_path=db_path, scope="demographics", changed_fields=changed)
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
    # sqlite3.connect creates a missing file; stamping must never conjure
    # an empty system database into existence.
    if not path or not Path(path).exists():
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


def all_local_records(journey_id: str, *,
                      db_path: str | None = None) -> list[tuple[str, str]]:
    """Every (system, local id) this person has been known by.

    The slots hold only the latest id per system; the enrolment history
    holds every spell — a second primary school, a returning learner's new
    id, a merged duplicate's record. Ordered by SYSTEM_ORDER, then by
    first appearance; systems outside the registry (``employment``...) are
    excluded because there is no local database to read.
    """
    out: list[tuple[str, str]] = []
    try:
        from education_system.platform.cross_system import enrolments
        for e in enrolments.list_enrolments(journey_id, db_path=db_path):
            pair = (e["system"], str(e.get("local_student_id") or ""))
            if pair[1] and pair[0] in _LOCAL_TABLE and pair not in out:
                out.append(pair)
    except Exception:
        logger.debug("Enrolment read failed for %s", journey_id,
                     exc_info=True)
    row = identity_service.get(journey_id, db_path=db_path) or {}
    for system, (_pk, id_col) in identity_service.SYSTEM_SLOTS.items():
        val = row.get(id_col)
        if val and (system, str(val)) not in out:
            out.append((system, str(val)))
    order = {s: i for i, s in enumerate(SYSTEM_ORDER)}
    return sorted(out, key=lambda p: order.get(p[0], len(order)))


def register_local_learner(
    system: str,
    *,
    student_id: str,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: str | None,
    pk: int | None = None,
    nhs_number: str | None = None,
    upn: str | None = None,
    programme: str | None = None,
    institution_id: str | None = None,
    start_date: str | None = None,
    source_module: str | None = None,
    auth_db: str | None = None,
    system_db_path: str | None = None,
) -> str | None:
    """Join a freshly created local learner to the registry. Never raises.

    The same three steps the nursery/primary/secondary/sixth-form/university
    create paths take — ``progression.register_local_student`` then
    ``link_local_record`` — plus filling the mirrored enrolment's
    programme/source and announcing ``journey.registered``. The announcement
    shares its idempotency key with the mint path, so a new learner yields
    one event, and a known person arriving in a new system yields one too.

    Returns the journey id, or None if registration was skipped (no name
    and DOB) or failed. The caller's record has already been written and
    must stand either way.
    """
    try:
        from education_system.platform.cross_system import (
            enrolments,
            progression,
        )
        jid = progression.register_local_student(
            system, student_id=str(student_id), first_name=first_name,
            last_name=last_name, date_of_birth=date_of_birth, pk=pk,
            nhs_number=nhs_number, upn=upn, db_path=auth_db)
        if not jid:
            return None
        link_local_record(system, str(student_id), jid,
                          db_path=system_db_path)
        try:
            enrolments.link_local_enrolment(
                journey_id=jid, system=system,
                local_student_id=str(student_id), status="active",
                institution_id=institution_id, start_date=start_date,
                programme=programme, source_system=system, db_path=auth_db)
        except Exception:
            logger.debug("Enrolment annotation failed for %s/%s", system,
                         student_id, exc_info=True)
        identity_service.publish_registered(
            jid, system, str(student_id), source_module=source_module,
            db_path=auth_db)
        return jid
    except Exception:
        logger.exception("Journey registration failed for %s/%s (record "
                         "still created)", system, student_id)
        return None


__all__ = [
    "Person",
    "DEMOGRAPHIC_FIELDS",
    "get",
    "get_by_student",
    "demographics",
    "update_demographics",
    "link_local_record",
    "all_local_records",
    "register_local_learner",
]
