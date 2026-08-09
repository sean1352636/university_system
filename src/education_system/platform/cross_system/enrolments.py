"""Learner enrolment records — the authoritative phase history.

Where ``identity_service`` answers *who is this person*, this module
answers *where have they been, and where are they now*. One
:func:`create_enrolment` row per spell at one institution, so the shapes
a single per-phase slot cannot express all become ordinary queries:

===========================  =====================================
Situation                    Representation
===========================  =====================================
Changes primary school       Two ``primary`` enrolments, the first
                             closed ``transferred``
Attends two nurseries        Two ``nursery`` enrolments
Repeats a year               One enrolment, ``year_group`` updated
                             via :func:`set_year_group`
Leaves and returns           Two enrolments, same ``local_student_id``
Transfers university         Two ``university`` enrolments, different
                             ``institution_id``
Skips sixth form             No ``sixth_form`` enrolment at all
Apprenticeship first         An ``apprenticeship`` enrolment between
                             ``sixth_form`` and ``university``
Dual enrolment               Two concurrently ``active`` enrolments
===========================  =====================================

Nothing here deletes. Closing an enrolment sets ``status`` and
``exit_reason``; the row survives so the journey stays auditable.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Iterable
from typing import Any

from education_system.platform.cross_system.enrolment_schema import (
    CLOSED_STATUSES,
    ENROLMENT_STATUSES,
    OPEN_STATUSES,
    ensure_enrolment_schema,
)
from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)


class EnrolmentError(ValueError):
    """Invalid enrolment operation (unknown status, missing row)."""


def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


def _rows(rs: Iterable[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rs]


def _check_status(status: str) -> str:
    if status not in ENROLMENT_STATUSES:
        raise EnrolmentError(
            f"Unknown enrolment status {status!r}; expected one of "
            f"{', '.join(sorted(ENROLMENT_STATUSES))}")
    return status


# ---------------------------------------------------------------------------
# Create / read
# ---------------------------------------------------------------------------

def create_enrolment(
    *,
    journey_id: str,
    system: str,
    local_student_id: str | None = None,
    institution_id: str | None = None,
    status: str = "applicant",
    start_date: str | None = None,
    end_date: str | None = None,
    year_group: str | None = None,
    exit_reason: str | None = None,
    notes: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Create one enrolment row and return it.

    ``system`` is not validated against the five phases: an enrolment at
    an external provider, an apprenticeship or an employer is a first-
    class part of the journey and must be recordable.
    """
    if not journey_id:
        raise EnrolmentError("journey_id is required")
    if not system:
        raise EnrolmentError("system is required")
    _check_status(status)
    ensure_enrolment_schema(db_path)

    enrolment_id = str(uuid.uuid4())
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO learner_enrolment
                 (enrolment_id, journey_id, system, institution_id,
                  local_student_id, start_date, end_date, status,
                  year_group, exit_reason, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (enrolment_id, journey_id, system, institution_id,
             local_student_id, start_date, end_date, status,
             year_group, exit_reason, notes))
        conn.commit()
    finally:
        conn.close()
    logger.info("Created %s enrolment %s for journey %s (local id %s)",
                system, enrolment_id, journey_id, local_student_id or "-")
    out = get_enrolment(enrolment_id, db_path=db_path)
    assert out is not None  # just inserted
    return out


def get_enrolment(enrolment_id: str, *,
                  db_path: str | None = None) -> dict | None:
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return _row(conn.execute(
            "SELECT * FROM learner_enrolment WHERE enrolment_id = ?",
            (enrolment_id,)).fetchone())
    finally:
        conn.close()


def list_enrolments(journey_id: str, *, system: str | None = None,
                    status: str | None = None,
                    include_closed: bool = True,
                    db_path: str | None = None) -> list[dict]:
    """Every enrolment for one journey, oldest first."""
    ensure_enrolment_schema(db_path)
    sql = ["SELECT * FROM learner_enrolment WHERE journey_id = ?"]
    args: list = [journey_id]
    if system:
        sql.append("AND system = ?")
        args.append(system)
    if status:
        sql.append("AND status = ?")
        args.append(status)
    elif not include_closed:
        placeholders = ", ".join("?" * len(OPEN_STATUSES))
        sql.append(f"AND status IN ({placeholders})")
        args.extend(sorted(OPEN_STATUSES))
    sql.append("ORDER BY COALESCE(start_date, created_at), created_at")
    conn = connect(db_path)
    try:
        return _rows(conn.execute(" ".join(sql), args).fetchall())
    finally:
        conn.close()


def active_enrolments(journey_id: str, *,
                      db_path: str | None = None) -> list[dict]:
    """Currently active enrolments — a list, because concurrent enrolment
    (school plus a college course, dual registration) is legitimate."""
    return list_enrolments(journey_id, status="active", db_path=db_path)


def open_enrolments(journey_id: str, *,
                    db_path: str | None = None) -> list[dict]:
    """Every enrolment not yet closed out, including applicant/offered."""
    return list_enrolments(journey_id, include_closed=False, db_path=db_path)


def current_enrolment(journey_id: str, system: str, *,
                      db_path: str | None = None) -> dict | None:
    """The one open enrolment for this journey in this system, if any.

    When several are open (an applicant record raised while the previous
    spell is still active) the most advanced is returned, so callers see
    ``active`` in preference to ``accepted`` in preference to
    ``applicant``.
    """
    rank = {"active": 5, "deferred": 4, "accepted": 3, "offered": 2,
            "applicant": 1}
    rows = [r for r in list_enrolments(
        journey_id, system=system, include_closed=False, db_path=db_path)]
    if not rows:
        return None
    return max(rows, key=lambda r: (rank.get(r["status"], 0),
                                    r.get("created_at") or ""))


def find_by_local_id(system: str, local_student_id: str, *,
                     db_path: str | None = None) -> list[dict]:
    """Every enrolment matching one system's local id, newest first."""
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return _rows(conn.execute(
            "SELECT * FROM learner_enrolment "
            "WHERE system = ? AND local_student_id = ? "
            "ORDER BY created_at DESC",
            (system, local_student_id)).fetchall())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

_UPDATABLE = ("institution_id", "local_student_id", "start_date",
              "end_date", "status", "year_group", "exit_reason", "notes")


def update_enrolment(enrolment_id: str, *, db_path: str | None = None,
                     **fields: Any) -> dict:
    """Patch one enrolment. Unknown fields are rejected rather than
    silently dropped, so a typo'd column surfaces immediately."""
    unknown = set(fields) - set(_UPDATABLE)
    if unknown:
        raise EnrolmentError(
            f"Cannot update {', '.join(sorted(unknown))}; updatable "
            f"fields are {', '.join(_UPDATABLE)}")
    if "status" in fields:
        _check_status(fields["status"])
    if not fields:
        out = get_enrolment(enrolment_id, db_path=db_path)
        if out is None:
            raise EnrolmentError(f"No enrolment {enrolment_id}")
        return out

    ensure_enrolment_schema(db_path)
    sets = [f"{k} = ?" for k in fields]
    args = list(fields.values())
    sets.append("updated_at = datetime('now')")
    args.append(enrolment_id)
    conn = connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE learner_enrolment SET {', '.join(sets)} "
            "WHERE enrolment_id = ?", args)
        conn.commit()
        if cur.rowcount == 0:
            raise EnrolmentError(f"No enrolment {enrolment_id}")
    finally:
        conn.close()
    out = get_enrolment(enrolment_id, db_path=db_path)
    assert out is not None
    return out


def set_status(enrolment_id: str, status: str, *,
               exit_reason: str | None = None,
               end_date: str | None = None,
               db_path: str | None = None) -> dict:
    """Move an enrolment to ``status``, stamping closure fields when the
    new status is terminal."""
    _check_status(status)
    fields: dict = {"status": status}
    if exit_reason is not None:
        fields["exit_reason"] = exit_reason
    if end_date is not None:
        fields["end_date"] = end_date
    return update_enrolment(enrolment_id, db_path=db_path, **fields)


def set_year_group(enrolment_id: str, year_group: str, *,
                   db_path: str | None = None) -> dict:
    """Move a learner up (or, for a repeated year, back into) a year group
    without creating a second enrolment at the same institution."""
    return update_enrolment(enrolment_id, year_group=year_group,
                            db_path=db_path)


def activate(enrolment_id: str, *, start_date: str | None = None,
             year_group: str | None = None,
             local_student_id: str | None = None,
             db_path: str | None = None) -> dict:
    """Promote an applicant/offered/accepted enrolment to ``active``."""
    fields: dict = {"status": "active"}
    if start_date is not None:
        fields["start_date"] = start_date
    if year_group is not None:
        fields["year_group"] = year_group
    if local_student_id is not None:
        fields["local_student_id"] = local_student_id
    return update_enrolment(enrolment_id, db_path=db_path, **fields)


def close_enrolment(enrolment_id: str, *, reason: str,
                    status: str = "completed",
                    end_date: str | None = None,
                    db_path: str | None = None) -> dict:
    """Close an enrolment out. Never deletes.

    ``status`` must be a terminal one — ``completed`` for finishing the
    phase normally, ``transferred`` for leaving mid-phase for somewhere
    else, ``withdrawn`` for leaving without completing, ``cancelled`` for
    an application that never became a place.
    """
    if status not in CLOSED_STATUSES:
        raise EnrolmentError(
            f"{status!r} does not close an enrolment; expected one of "
            f"{', '.join(sorted(CLOSED_STATUSES))}")
    return set_status(enrolment_id, status, exit_reason=reason,
                      end_date=end_date, db_path=db_path)


# ---------------------------------------------------------------------------
# Idempotent link (used by the identity_service dual-write)
# ---------------------------------------------------------------------------

def link_local_enrolment(
    *,
    journey_id: str,
    system: str,
    local_student_id: str | None,
    status: str = "active",
    institution_id: str | None = None,
    year_group: str | None = None,
    start_date: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Ensure an open enrolment exists for (journey, system, local id).

    Reuses an open enrolment rather than creating a duplicate, so a
    repeated ``link_system`` call or a redelivered bus event is a no-op.
    A *closed* enrolment is never reused — a learner returning to a
    system they previously left starts a new spell.
    """
    existing = current_enrolment(journey_id, system, db_path=db_path)
    if existing is not None:
        patch: dict = {}
        if local_student_id and not existing.get("local_student_id"):
            patch["local_student_id"] = local_student_id
        if institution_id and not existing.get("institution_id"):
            patch["institution_id"] = institution_id
        if year_group and not existing.get("year_group"):
            patch["year_group"] = year_group
        # Only ever advance the status here; never demote an active
        # enrolment back to applicant because a late event arrived.
        if status == "active" and existing.get("status") != "active":
            patch["status"] = "active"
            if start_date:
                patch["start_date"] = start_date
        if patch:
            return update_enrolment(existing["enrolment_id"],
                                    db_path=db_path, **patch)
        return existing

    return create_enrolment(
        journey_id=journey_id, system=system,
        local_student_id=local_student_id, institution_id=institution_id,
        status=status, year_group=year_group, start_date=start_date,
        db_path=db_path)


# ---------------------------------------------------------------------------
# Journey-level summary
# ---------------------------------------------------------------------------

def journey_history(journey_id: str, *,
                    db_path: str | None = None) -> dict:
    """Everything known about one learner's path, for dashboards and the
    handover UI: enrolments oldest-first plus the derived current phases."""
    rows = list_enrolments(journey_id, db_path=db_path)
    active = [r for r in rows if r["status"] == "active"]
    return {
        "journey_id": journey_id,
        "enrolments": rows,
        "active": active,
        "current_phases": [r["system"] for r in active],
        "systems_attended": sorted({r["system"] for r in rows}),
        "open": [r for r in rows if r["status"] in OPEN_STATUSES],
    }


__all__ = [
    "EnrolmentError",
    "create_enrolment",
    "get_enrolment",
    "list_enrolments",
    "active_enrolments",
    "open_enrolments",
    "current_enrolment",
    "find_by_local_id",
    "update_enrolment",
    "set_status",
    "set_year_group",
    "activate",
    "close_enrolment",
    "link_local_enrolment",
    "journey_history",
]
