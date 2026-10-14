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
Repeats a year               One enrolment; :func:`set_year_group`
                             updates ``year_group`` and appends a
                             ``repeated`` row to the year history
Leaves and returns           Two enrolments, same ``local_student_id``
Transfers university         Two ``university`` enrolments, different
                             ``institution_id``
Skips sixth form             No ``sixth_form`` enrolment at all
Apprenticeship first         An ``apprenticeship`` enrolment between
                             ``sixth_form`` and ``university``
Dual enrolment               Two concurrently ``active`` enrolments
===========================  =====================================

Each row also carries ``programme`` (course of study), ``outcome`` (how
the spell ended — a grade, a destination) and ``source_system`` (which
system wrote it: the lineage the Learner 360 shows).

Nothing here deletes. Closing an enrolment sets ``status`` and
``exit_reason``; the row survives so the journey stays auditable. Closing
publishes ``enrolment.ended``; a year-group, programme or institution
change on an open enrolment publishes ``learner.updated``.
"""

from __future__ import annotations

import json
import logging
import re
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

_SOURCE_MODULE = "platform.cross_system.enrolments"

# Fields whose change on an open enrolment is news to other systems.
_ANNOUNCED_FIELDS = ("year_group", "programme", "institution_id")


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
# Events and year history (both best-effort: the row is already committed)
# ---------------------------------------------------------------------------

def _publish(event_name: str, enrolment: dict, *, idempotency_key: str,
             db_path: str | None, **payload: Any) -> None:
    from education_system.platform.cross_system import identity_service
    system = enrolment.get("system")
    identity_service._publish(
        event_name, journey_id=enrolment["journey_id"],
        idempotency_key=idempotency_key,
        source_system=system if system in identity_service.SYSTEM_SLOTS
        else "platform",
        source_module=_SOURCE_MODULE, db_path=db_path,
        enrolment_id=enrolment["enrolment_id"], system=system,
        local_student_id=enrolment.get("local_student_id"), **payload)


def _year_change_type(before: str | None, after: str) -> str:
    if before in (None, ""):
        return "started"
    if str(before).strip() == str(after).strip():
        return "repeated"
    b, a = re.sub(r"\D", "", str(before)), re.sub(r"\D", "", str(after))
    if b and a:
        return "promoted" if int(a) > int(b) else "moved_back"
    return "changed"


def _record_year(enrolment: dict, before: str | None, *,
                 change_type: str | None = None,
                 academic_year: str | None = None, note: str | None = None,
                 db_path: str | None) -> dict | None:
    after = enrolment.get("year_group")
    if after in (None, ""):
        return None
    kind = change_type or _year_change_type(before, after)
    try:
        conn = connect(db_path)
        try:
            cur = conn.execute(
                "INSERT INTO enrolment_year_history (enrolment_id, "
                "journey_id, system, from_year_group, to_year_group, "
                "change_type, academic_year, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (enrolment["enrolment_id"], enrolment["journey_id"],
                 enrolment["system"], before, after, kind, academic_year,
                 note))
            conn.commit()
            history_id = cur.lastrowid
        finally:
            conn.close()
    except Exception:
        logger.exception("Year history write failed for enrolment %s",
                         enrolment["enrolment_id"])
        return None
    return {"history_id": history_id, "change_type": kind,
            "from_year_group": before, "to_year_group": after}


def _after_update(before: dict, after: dict, *, db_path: str | None,
                  year_repeat: bool = False,
                  academic_year: str | None = None,
                  note: str | None = None) -> None:
    from education_system.platform.integrations.external import (
        cross_system_bus,
    )
    history = None
    if year_repeat or before.get("year_group") != after.get("year_group"):
        history = _record_year(after, before.get("year_group"),
                               academic_year=academic_year, note=note,
                               db_path=db_path)

    changes = {f: after.get(f) for f in _ANNOUNCED_FIELDS
               if before.get(f) != after.get(f)}
    if (changes or history) and after.get("status") in OPEN_STATUSES:
        # Keyed on the history row where there is one (so two genuine
        # repeats are two events) and on the new values otherwise.
        marker = (history or {}).get("history_id") or json.dumps(
            changes, sort_keys=True, default=str)
        _publish(
            cross_system_bus.EVENT_LEARNER_UPDATED, after,
            idempotency_key=(f"learner.updated:{after['enrolment_id']}:"
                             f"{after.get('updated_at')}:{marker}"),
            db_path=db_path, scope="enrolment", changes=changes,
            year_change=(history or {}).get("change_type"))

    if (before.get("status") in OPEN_STATUSES
            and after.get("status") in CLOSED_STATUSES):
        _publish(
            cross_system_bus.EVENT_ENROLMENT_ENDED, after,
            idempotency_key=(f"enrolment.ended:{after['enrolment_id']}:"
                             f"{after['status']}"),
            db_path=db_path, status=after["status"],
            exit_reason=after.get("exit_reason"),
            end_date=after.get("end_date"), outcome=after.get("outcome"),
            programme=after.get("programme"),
            institution_id=after.get("institution_id"))


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
    programme: str | None = None,
    outcome: str | None = None,
    source_system: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Create one enrolment row and return it.

    ``system`` is not validated against the phases: an enrolment at an
    external provider or an employer is a first-class part of the journey
    and must be recordable. ``source_system`` defaults to ``system``.
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
                  year_group, exit_reason, notes, programme, outcome,
                  source_system)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (enrolment_id, journey_id, system, institution_id,
             local_student_id, start_date, end_date, status,
             year_group, exit_reason, notes, programme, outcome,
             source_system or system))
        conn.commit()
    finally:
        conn.close()
    logger.info("Created %s enrolment %s for journey %s (local id %s)",
                system, enrolment_id, journey_id, local_student_id or "-")
    out = get_enrolment(enrolment_id, db_path=db_path)
    assert out is not None  # just inserted
    if year_group:
        _record_year(out, None, db_path=db_path)
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
    # rowid breaks ties: two spells written in the same second (a transfer
    # and the new school's registration) must still read in insert order.
    sql.append("ORDER BY COALESCE(start_date, created_at), created_at, rowid")
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
            "ORDER BY created_at DESC, rowid DESC",
            (system, local_student_id)).fetchall())
    finally:
        conn.close()


def year_group_history(*, enrolment_id: str | None = None,
                       journey_id: str | None = None,
                       db_path: str | None = None) -> list[dict]:
    """Year-group changes, oldest first, for one enrolment or one journey."""
    if not (enrolment_id or journey_id):
        raise EnrolmentError("enrolment_id or journey_id is required")
    ensure_enrolment_schema(db_path)
    col, val = (("enrolment_id", enrolment_id) if enrolment_id
                else ("journey_id", journey_id))
    conn = connect(db_path)
    try:
        return _rows(conn.execute(
            f"SELECT * FROM enrolment_year_history WHERE {col} = ? "  # nosec B608 - fixed column
            "ORDER BY recorded_at, history_id", (val,)).fetchall())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

_UPDATABLE = ("institution_id", "local_student_id", "start_date",
              "end_date", "status", "year_group", "exit_reason", "notes",
              "programme", "outcome", "source_system")


def _update(enrolment_id: str, fields: dict, *, db_path: str | None,
            year_repeat: bool = False, academic_year: str | None = None,
            note: str | None = None) -> dict:
    unknown = set(fields) - set(_UPDATABLE)
    if unknown:
        raise EnrolmentError(
            f"Cannot update {', '.join(sorted(unknown))}; updatable "
            f"fields are {', '.join(_UPDATABLE)}")
    if "status" in fields:
        _check_status(fields["status"])
    before = get_enrolment(enrolment_id, db_path=db_path)
    if before is None:
        raise EnrolmentError(f"No enrolment {enrolment_id}")
    if not fields:
        return before

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
    after = get_enrolment(enrolment_id, db_path=db_path)
    assert after is not None
    try:
        _after_update(before, after, db_path=db_path,
                      year_repeat=year_repeat, academic_year=academic_year,
                      note=note)
    except Exception:
        logger.exception("Post-update hooks failed for enrolment %s",
                         enrolment_id)
    return after


def update_enrolment(enrolment_id: str, *, db_path: str | None = None,
                     **fields: Any) -> dict:
    """Patch one enrolment. Unknown fields are rejected rather than
    silently dropped, so a typo'd column surfaces immediately."""
    return _update(enrolment_id, fields, db_path=db_path)


def set_status(enrolment_id: str, status: str, *,
               exit_reason: str | None = None,
               end_date: str | None = None,
               outcome: str | None = None,
               db_path: str | None = None) -> dict:
    """Move an enrolment to ``status``, stamping closure fields when the
    new status is terminal."""
    _check_status(status)
    fields: dict = {"status": status}
    if exit_reason is not None:
        fields["exit_reason"] = exit_reason
    if end_date is not None:
        fields["end_date"] = end_date
    if outcome is not None:
        fields["outcome"] = outcome
    return update_enrolment(enrolment_id, db_path=db_path, **fields)


def set_year_group(enrolment_id: str, year_group: str, *,
                   academic_year: str | None = None,
                   note: str | None = None,
                   db_path: str | None = None) -> dict:
    """Move a learner up (or, for a repeated year, back into) a year group
    without creating a second enrolment at the same institution.

    Always appends to the year history — including when ``year_group`` is
    unchanged, which is exactly what a repeated year looks like and what
    the single ``year_group`` column used to lose.
    """
    return _update(enrolment_id, {"year_group": year_group},
                   db_path=db_path, year_repeat=True,
                   academic_year=academic_year, note=note)


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
                    outcome: str | None = None,
                    db_path: str | None = None) -> dict:
    """Close an enrolment out. Never deletes.

    ``status`` must be a terminal one — ``completed`` for finishing the
    phase normally, ``transferred`` for leaving mid-phase for somewhere
    else, ``withdrawn`` for leaving without completing, ``cancelled`` for
    an application that never became a place. ``outcome`` records how it
    ended (a final grade, a destination). Publishes ``enrolment.ended``.
    """
    if status not in CLOSED_STATUSES:
        raise EnrolmentError(
            f"{status!r} does not close an enrolment; expected one of "
            f"{', '.join(sorted(CLOSED_STATUSES))}")
    return set_status(enrolment_id, status, exit_reason=reason,
                      end_date=end_date, outcome=outcome, db_path=db_path)


def end_local_enrolment(system: str, local_student_id: str, *,
                        reason: str, status: str = "completed",
                        end_date: str | None = None,
                        outcome: str | None = None,
                        db_path: str | None = None) -> dict | None:
    """Close the newest open enrolment for one system's local record.

    For a system's own lifecycle hooks (a withdrawal, a completion), which
    know their local id but not the enrolment id. Returns the closed row,
    or None when that record has no open enrolment.
    """
    for row in find_by_local_id(system, str(local_student_id),
                                db_path=db_path):
        if row["status"] in OPEN_STATUSES:
            return close_enrolment(row["enrolment_id"], reason=reason,
                                   status=status, end_date=end_date,
                                   outcome=outcome, db_path=db_path)
    return None


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
    programme: str | None = None,
    source_system: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Ensure an open enrolment exists for (journey, system, local id).

    Reuses an open enrolment rather than creating a duplicate, so a
    repeated ``link_system`` call or a redelivered bus event is a no-op.
    Blank fields on the reused row are filled; set ones are never
    overwritten. A *closed* enrolment is never reused — a learner
    returning to a system they previously left starts a new spell.
    """
    existing = current_enrolment(journey_id, system, db_path=db_path)
    if existing is not None:
        patch: dict = {}
        for key, value in (("local_student_id", local_student_id),
                           ("institution_id", institution_id),
                           ("year_group", year_group),
                           ("programme", programme),
                           ("source_system", source_system),
                           ("start_date", start_date)):
            if value and not existing.get(key):
                patch[key] = value
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
        programme=programme, source_system=source_system, db_path=db_path)


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
        "year_history": year_group_history(journey_id=journey_id,
                                           db_path=db_path),
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
    "year_group_history",
    "update_enrolment",
    "set_status",
    "set_year_group",
    "activate",
    "close_enrolment",
    "end_local_enrolment",
    "link_local_enrolment",
    "journey_history",
]
