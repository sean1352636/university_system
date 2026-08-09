"""The common transition workflow, shared by every phase boundary.

Nursery→primary and sixth_form→university are the same seven steps with
different paperwork, so they run through one state machine here rather
than each system inventing its own transfer flow::

    1. expected           source identifies who is likely to move
    2. applied            destination has an application on file
    3. offered            destination creates a pending admission record
    4. accepted           learner/parent/admissions confirm the destination
    5. handover_approved  source approves the information to release
    6. admitted           destination creates its local learner id
    7. completed          journey updated; source enrolment closed

Each step publishes a durable bus event, so a system that is not running
when a learner progresses picks the work up on its next poll.

Direction of travel
-------------------
Steps only move forward, and a transition may jump ahead — a learner
joining from an external institution mid-year goes straight to
``admitted`` with no application or offer, and a backdated administrative
record can be entered as ``completed`` in one call. Skipped steps are
logged, not rejected. :func:`cancel` is reachable from anywhere before
``completed``.

The destination is never inferred from a fixed chain.
``progression.next_phase`` supplies a *recommendation* when the caller
does not name one, but any destination is permitted: another school in
the same phase, an apprenticeship, employment, home education, or an
external provider.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from typing import Any

from education_system.platform.cross_system import enrolments, identity_service
from education_system.platform.cross_system.enrolment_schema import (
    TRANSITION_CANCELLED,
    TRANSITION_STATUSES,
    ensure_enrolment_schema,
)
from education_system.platform.cross_system.handover import HandoverResult
from education_system.platform.identity.auth.db import connect
from education_system.platform.integrations.external import cross_system_bus

logger = logging.getLogger(__name__)

_SOURCE_MODULE = "platform.cross_system.transitions"

# Workflow step -> the event published on entering it.
STEP_EVENTS: dict[str, str] = {
    "expected":          cross_system_bus.EVENT_PROGRESSION_EXPECTED,
    "applied":           cross_system_bus.EVENT_APPLICATION_SUBMITTED,
    "offered":           cross_system_bus.EVENT_PLACE_OFFERED,
    "accepted":          cross_system_bus.EVENT_PLACE_ACCEPTED,
    "handover_approved": cross_system_bus.EVENT_HANDOVER_APPROVED,
    "admitted":          cross_system_bus.EVENT_ENROLMENT_CREATED,
    "completed":         cross_system_bus.EVENT_PROGRESSION_COMPLETED,
    TRANSITION_CANCELLED: cross_system_bus.EVENT_PROGRESSION_CANCELLED,
}

_STEP_INDEX: dict[str, int] = {s: i for i, s in enumerate(TRANSITION_STATUSES)}


class TransitionError(ValueError):
    """An illegal move in the transition workflow."""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


def _publish(event: str, transition: dict, **payload: Any) -> None:
    """Publish a workflow event, plus its legacy twin where one exists.

    Best-effort: a bus failure must not roll back a transition that has
    already been recorded in the database.
    """
    # NB: no "source_system" key — the envelope already carries that as a
    # column, and duplicating it here collides with the explicit keyword
    # below. Payload callers read it from the envelope.
    body = {
        "transition_id": transition["transition_id"],
        "source_enrolment_id": transition.get("source_enrolment_id"),
        "destination_system": transition["destination_system"],
        "destination_enrolment_id": transition.get(
            "destination_enrolment_id"),
        "status": transition["status"],
        **payload,
    }
    names = [event]
    twin = cross_system_bus.LEGACY_EVENT_TWINS.get(event)
    if twin:
        names.append(twin)
    for name in names:
        try:
            cross_system_bus.publish_cross_system(
                name,
                source_system=transition.get("source_system") or "platform",
                source_module=_SOURCE_MODULE,
                journey_id=transition["journey_id"],
                target_system=transition["destination_system"],
                actor_user_id=transition.get("actor_user_id"),
                db_path=transition.get("_db_path"),
                **body)
        except Exception:
            logger.exception(
                "Failed to publish %s for transition %s (state already "
                "saved)", name, transition["transition_id"])


def _advance(transition_id: str, to_status: str, *,
             db_path: str | None = None, **fields: Any) -> dict:
    """Move a transition forward to ``to_status`` and patch ``fields``."""
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")

    now = current["status"]
    if now in ("completed", TRANSITION_CANCELLED):
        raise TransitionError(
            f"Transition {transition_id} is already {now} and cannot move "
            f"to {to_status}")

    if to_status != TRANSITION_CANCELLED:
        if to_status not in _STEP_INDEX:
            raise TransitionError(f"Unknown workflow step {to_status!r}")
        here, there = _STEP_INDEX[now], _STEP_INDEX[to_status]
        if there <= here:
            raise TransitionError(
                f"Transition {transition_id} is at {now!r}; the workflow "
                f"only moves forward, so it cannot go to {to_status!r}")
        if there > here + 1:
            logger.info(
                "Transition %s jumping %s -> %s, skipping %s", transition_id,
                now, to_status,
                ", ".join(TRANSITION_STATUSES[here + 1:there]))

    sets = [f"{k} = ?" for k in fields]
    args = list(fields.values())
    sets.append("status = ?")
    args.append(to_status)
    sets.append("updated_at = datetime('now')")
    if to_status == "completed":
        sets.append("completed_at = datetime('now')")
    args.append(transition_id)

    conn = connect(db_path)
    try:
        conn.execute(
            f"UPDATE learner_transition SET {', '.join(sets)} "
            "WHERE transition_id = ?", args)
        conn.commit()
    finally:
        conn.close()

    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    logger.info("Transition %s: %s -> %s (%s -> %s)", transition_id, now,
                to_status, out.get("source_system") or "?",
                out["destination_system"])
    return out


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_transition(transition_id: str, *,
                   db_path: str | None = None) -> dict | None:
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return _row(conn.execute(
            "SELECT * FROM learner_transition WHERE transition_id = ?",
            (transition_id,)).fetchone())
    finally:
        conn.close()


def list_transitions(journey_id: str, *, db_path: str | None = None
                     ) -> list[dict]:
    """Every transition attempted for a journey, oldest first — including
    the ones that were cancelled, because "applied and was rejected" is
    part of the history."""
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM learner_transition WHERE journey_id = ? "
            "ORDER BY initiated_at, rowid", (journey_id,)).fetchall()]
    finally:
        conn.close()


def pending_transitions(destination_system: str, *,
                        status: str | None = None,
                        db_path: str | None = None) -> list[dict]:
    """Transitions heading into one system that have not completed.

    This is the destination's work queue — the admissions view of "who is
    coming and how far along are they".
    """
    ensure_enrolment_schema(db_path)
    sql = ["SELECT * FROM learner_transition WHERE destination_system = ?"]
    args: list = [destination_system]
    if status:
        sql.append("AND status = ?")
        args.append(status)
    else:
        sql.append("AND status NOT IN ('completed', ?)")
        args.append(TRANSITION_CANCELLED)
    sql.append("ORDER BY initiated_at")
    conn = connect(db_path)
    try:
        return [dict(r) for r in conn.execute(" ".join(sql), args).fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Step 1 — expected progression
# ---------------------------------------------------------------------------

def start_transition(
    *,
    journey_id: str,
    destination_system: str | None = None,
    source_system: str | None = None,
    source_enrolment_id: str | None = None,
    reason: str | None = None,
    actor_user_id: int | None = None,
    status: str = "expected",
    db_path: str | None = None,
) -> dict:
    """Open a transition. Step 1 of the workflow.

    ``destination_system`` defaults to the *recommended* next phase after
    ``source_system``, but any destination is accepted — including ones
    that are not phases at all (``apprenticeship``, ``employment``,
    ``home_education``, ``external``).
    """
    if not journey_id:
        raise TransitionError("journey_id is required")
    ensure_enrolment_schema(db_path)

    if source_enrolment_id and not source_system:
        src = enrolments.get_enrolment(source_enrolment_id, db_path=db_path)
        if src is not None:
            source_system = src["system"]

    # Import locally: progression imports identity_service, and keeping this
    # out of the module header avoids a load-order dependency.
    from education_system.platform.cross_system.progression import (
        next_phase,
        normalise_system,
    )

    # Fold legacy spellings onto their real system key before anything is
    # stored. A journey recorded against ``apprenticeship`` (the old label,
    # from before the system joined the registry) has to reach the same
    # adapter and the same slot as one recorded against ``apprenticeships``,
    # or the two spellings become two parallel histories for one learner.
    source_system = normalise_system(source_system)
    destination_system = normalise_system(destination_system)

    if not destination_system:
        destination_system = next_phase(source_system or "")
        if not destination_system:
            raise TransitionError(
                f"No destination given and no phase follows "
                f"{source_system!r} — name the destination explicitly")
        logger.debug("Transition destination defaulted to recommended "
                     "next phase %s", destination_system)

    if status not in _STEP_INDEX:
        raise TransitionError(f"Unknown workflow step {status!r}")

    transition_id = str(uuid.uuid4())
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT INTO learner_transition
                 (transition_id, journey_id, source_enrolment_id,
                  source_system, destination_system, status, reason,
                  actor_user_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (transition_id, journey_id, source_enrolment_id, source_system,
             destination_system, status, reason, actor_user_id))
        conn.commit()
    finally:
        conn.close()

    out = get_transition(transition_id, db_path=db_path)
    assert out is not None
    out["_db_path"] = db_path
    logger.info("Opened transition %s for journey %s (%s -> %s) at %s",
                transition_id, journey_id, source_system or "?",
                destination_system, status)
    _publish(STEP_EVENTS[status], out, reason=reason)
    return out


# ---------------------------------------------------------------------------
# Step 2 — application submitted
# ---------------------------------------------------------------------------

def record_application(transition_id: str, *,
                       application_reference: str | None = None,
                       db_path: str | None = None, **payload: Any) -> dict:
    """Step 2: an application exists at the destination."""
    out = _advance(transition_id, "applied", db_path=db_path)
    _publish(STEP_EVENTS["applied"], out,
             application_reference=application_reference, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 3 — place offered
# ---------------------------------------------------------------------------

def offer_place(
    transition_id: str,
    *,
    destination_enrolment_id: str | None = None,
    local_student_id: str | None = None,
    institution_id: str | None = None,
    year_group: str | None = None,
    conditions: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 3: the destination holds a pending admission record.

    Creates the destination's ``applicant`` enrolment when one was not
    supplied, and marks it ``offered``. This is where a learner first
    exists in the destination system — as an applicant, never as an
    enrolled learner.
    """
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")

    if destination_enrolment_id is None:
        destination_enrolment_id = current.get("destination_enrolment_id")
    if destination_enrolment_id is None:
        created = enrolments.create_enrolment(
            journey_id=current["journey_id"],
            system=current["destination_system"],
            local_student_id=local_student_id,
            institution_id=institution_id,
            year_group=year_group,
            status="offered",
            notes=f"created by transition {transition_id}",
            db_path=db_path)
        destination_enrolment_id = created["enrolment_id"]
    else:
        enrolments.set_status(destination_enrolment_id, "offered",
                              db_path=db_path)

    out = _advance(transition_id, "offered", db_path=db_path,
                   destination_enrolment_id=destination_enrolment_id)
    _publish(STEP_EVENTS["offered"], out, conditions=conditions,
             local_student_id=local_student_id,
             institution_id=institution_id, year_group=year_group, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 4 — offer accepted
# ---------------------------------------------------------------------------

def accept_place(transition_id: str, *, accepted_by: str | None = None,
                 db_path: str | None = None, **payload: Any) -> dict:
    """Step 4: the learner, parent or admissions team confirms."""
    out = _advance(transition_id, "accepted", db_path=db_path)
    if out.get("destination_enrolment_id"):
        enrolments.set_status(out["destination_enrolment_id"], "accepted",
                              db_path=db_path)
    _publish(STEP_EVENTS["accepted"], out, accepted_by=accepted_by, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 5 — handover prepared and approved
# ---------------------------------------------------------------------------

def approve_handover(
    transition_id: str,
    handover: HandoverResult | dict,
    *,
    consent_reference: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Step 5: the source approves the information to release.

    Accepts either a :class:`~.handover.HandoverResult` (the normal path,
    built by the source adapter) or a plain payload dict. The approved
    payload is stored on the transition, so what was released is
    auditable after the fact.

    The payload itself is *not* put on the bus — the event carries the
    field names and a pointer to the transition, and the destination
    reads the payload back through :func:`get_handover`. Bus rows are
    long-lived and broadly readable; a learner's SEND and medical detail
    should not be sitting in them.
    """
    if isinstance(handover, HandoverResult):
        payload = handover.payload
        summary = {
            "included": handover.included,
            "withheld_no_consent": handover.withheld_no_consent,
            "withheld_restricted": handover.withheld_restricted,
            "missing_required": handover.missing_required,
        }
    else:
        payload = dict(handover)
        summary = {"included": sorted(payload)}

    out = _advance(
        transition_id, "handover_approved", db_path=db_path,
        handover_json=json.dumps(payload, default=str),
        consent_reference=consent_reference,
        handover_approved_at=_now(db_path))
    _publish(STEP_EVENTS["handover_approved"], out,
             consent_reference=consent_reference, **summary)
    return out


def get_handover(transition_id: str, *,
                 db_path: str | None = None) -> dict | None:
    """The approved handover payload, or ``None`` if not yet approved."""
    row = get_transition(transition_id, db_path=db_path)
    if row is None or not row.get("handover_json"):
        return None
    try:
        loaded: dict = json.loads(row["handover_json"])
        return loaded
    except (TypeError, ValueError):
        logger.exception("Transition %s has unreadable handover_json",
                         transition_id)
        return None


def _now(db_path: str | None) -> str:
    conn = connect(db_path)
    try:
        stamp: str = conn.execute("SELECT datetime('now')").fetchone()[0]
        return stamp
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Step 6 — destination admits
# ---------------------------------------------------------------------------

def admit(
    transition_id: str,
    *,
    local_student_id: str,
    year_group: str | None = None,
    start_date: str | None = None,
    institution_id: str | None = None,
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 6: the destination has created its local learner id.

    The destination enrolment is created if the workflow jumped straight
    here (a learner arriving from an external institution has no offer
    record), and stamped with the local id.
    """
    if not local_student_id:
        raise TransitionError("local_student_id is required to admit")
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")

    dest_id = current.get("destination_enrolment_id")
    if dest_id:
        enrolments.update_enrolment(
            dest_id, db_path=db_path, local_student_id=local_student_id,
            **{k: v for k, v in (("year_group", year_group),
                                 ("institution_id", institution_id))
               if v is not None})
    else:
        created = enrolments.create_enrolment(
            journey_id=current["journey_id"],
            system=current["destination_system"],
            local_student_id=local_student_id,
            institution_id=institution_id, year_group=year_group,
            start_date=start_date, status="accepted",
            notes=f"created by transition {transition_id}", db_path=db_path)
        dest_id = created["enrolment_id"]

    out = _advance(transition_id, "admitted", db_path=db_path,
                   destination_enrolment_id=dest_id)
    _publish(STEP_EVENTS["admitted"], out,
             local_student_id=local_student_id, year_group=year_group,
             start_date=start_date, **payload)
    return out


# ---------------------------------------------------------------------------
# Step 7 — complete, and close the source
# ---------------------------------------------------------------------------

def complete(
    transition_id: str,
    *,
    start_date: str | None = None,
    close_source: bool = True,
    source_exit_reason: str | None = None,
    source_status: str = "transferred",
    db_path: str | None = None,
    **payload: Any,
) -> dict:
    """Step 7: activate the destination enrolment and close the source.

    Also updates the canonical journey — linking the destination system's
    slot and appending a ``student_journey_transitions`` row — so the
    legacy slot readers stay correct while enrolments are authoritative.

    ``close_source=False`` leaves the source enrolment open, which is what
    a genuinely concurrent enrolment (school plus a college course) needs.
    """
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")

    dest_id = current.get("destination_enrolment_id")
    local_id = None
    if dest_id:
        dest = enrolments.activate(dest_id, start_date=start_date,
                                   db_path=db_path)
        local_id = dest.get("local_student_id")

    if close_source and current.get("source_enrolment_id"):
        enrolments.close_enrolment(
            current["source_enrolment_id"],
            reason=source_exit_reason or
            f"progressed to {current['destination_system']}",
            status=source_status, end_date=start_date, db_path=db_path)

    _sync_journey(current, local_id, db_path=db_path)

    out = _advance(transition_id, "completed", db_path=db_path)
    _publish(STEP_EVENTS["completed"], out, local_student_id=local_id,
             target_student_id=local_id, start_date=start_date, **payload)
    return out


def _sync_journey(transition: dict, local_student_id: str | None, *,
                  db_path: str | None) -> None:
    """Keep ``student_journey`` in step with a completed transition.

    Best-effort. The destination may be somewhere with no slot at all
    (an apprenticeship, an external provider); the transition audit row
    is still written so the journey shows where the learner went.
    """
    journey_id = transition["journey_id"]
    dest = transition["destination_system"]
    try:
        if dest in identity_service.SYSTEM_SLOTS and local_student_id:
            identity_service.link_system(
                journey_id, dest, student_id=local_student_id,
                set_current=True, db_path=db_path)
        identity_service.record_transition(
            journey_id, from_system=transition.get("source_system"),
            to_system=dest, actor_user_id=transition.get("actor_user_id"),
            reason=transition.get("reason") or
            f"{transition.get('source_system') or '?'} → {dest} transition",
            db_path=db_path)
    except Exception:
        logger.exception(
            "Journey sync failed for transition %s (enrolments are still "
            "correct)", transition["transition_id"])


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def cancel(transition_id: str, *, reason: str,
           cancel_destination_enrolment: bool = True,
           db_path: str | None = None, **payload: Any) -> dict:
    """Abandon a transition at any point before it completes.

    The row is kept — a place applied for and not taken is part of the
    journey. The destination's applicant/offer enrolment is closed as
    ``cancelled`` unless the caller wants to keep it open (a deferred
    entry that will be picked up next cycle).
    """
    current = get_transition(transition_id, db_path=db_path)
    if current is None:
        raise TransitionError(f"No transition {transition_id}")

    if cancel_destination_enrolment and current.get(
            "destination_enrolment_id"):
        try:
            enrolments.close_enrolment(
                current["destination_enrolment_id"], reason=reason,
                status="cancelled", db_path=db_path)
        except Exception:
            logger.exception(
                "Could not cancel destination enrolment for transition %s",
                transition_id)

    out = _advance(transition_id, TRANSITION_CANCELLED, db_path=db_path,
                   cancelled_reason=reason)
    _publish(STEP_EVENTS[TRANSITION_CANCELLED], out, reason=reason, **payload)
    return out


__all__ = [
    "TransitionError",
    "STEP_EVENTS",
    "get_transition",
    "list_transitions",
    "pending_transitions",
    "start_transition",
    "record_application",
    "offer_place",
    "accept_place",
    "approve_handover",
    "get_handover",
    "admit",
    "complete",
    "cancel",
]
