"""High-level helpers wiring student lifecycle changes onto the
cross-system identity table + the durable event bus.

Step 3 of the cross-system integration plan. Each system's
``create_student`` (or ``create_pupil``) calls
``register_student_journey`` after a successful insert; cross-system
transfers call ``record_student_transition``.

**Failure isolation is the most important property here.** A broken
identity or bus call must never propagate to the caller and roll back
a student record that's otherwise fine. Every helper is best-effort
and logs on error — this matches how ``shared/transfer/`` and the
existing notification fan-outs behave.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.shared.cross_system import identity_service as ids
from education_system.shared.integrations import cross_system_bus as bus

logger = logging.getLogger(__name__)


def register_student_journey(
    *,
    system: str,
    pk: int | None,
    student_id: str | None,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: str | None,
    nhs_number: str | None = None,
    upn: str | None = None,
    actor_user_id: int | None = None,
    source_module: str = "register_student_journey",
    extra_payload: dict[str, Any] | None = None,
    auth_db_path: str | None = None,
) -> str | None:
    """Ensure a journey row exists for this student, attach the per-system
    record, and publish ``journey.registered`` on the durable bus.

    Returns the ``journey_id`` on success or ``None`` if the call failed
    for any reason (the identity layer, the bus, missing keys, etc.).
    Callers that want to write the resulting ``journey_id`` back onto
    their local row can use the return value.

    Best-effort: on any error this returns ``None`` and logs, never
    raises.
    """
    if not (first_name and last_name and date_of_birth):
        logger.debug(
            "register_student_journey skipped: missing identity keys "
            "(system=%s, student_id=%s)", system, student_id,
        )
        return None

    try:
        journey_id = ids.get_or_create_journey(
            first_name=first_name, last_name=last_name,
            date_of_birth=date_of_birth, current_system=system,
            nhs_number=nhs_number, upn=upn, db_path=auth_db_path,
        )
    except Exception:
        logger.exception(
            "register_student_journey: get_or_create_journey failed "
            "for system=%s student_id=%s", system, student_id,
        )
        return None

    try:
        ids.attach_system_record(
            journey_id, system, pk=pk, student_id=student_id,
            db_path=auth_db_path,
        )
    except Exception:
        logger.exception(
            "register_student_journey: attach_system_record failed "
            "for journey=%s system=%s", journey_id, system,
        )
        # Carry on — the journey row is usable even without the FK.

    payload: dict[str, Any] = {"system": system}
    if pk is not None:
        payload["pk"] = pk
    if student_id:
        payload["student_id"] = student_id
    if extra_payload:
        payload.update(extra_payload)

    try:
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_REGISTERED,
            source_system=system, source_module=source_module,
            journey_id=journey_id, target_system=None,  # broadcast
            actor_user_id=actor_user_id, db_path=auth_db_path,
            **payload,
        )
    except Exception:
        logger.exception(
            "register_student_journey: bus publish failed for "
            "journey=%s", journey_id,
        )
        # Identity is still linked; the bus event is the lossy part.

    return journey_id


def record_student_transition(
    journey_id: str,
    *,
    from_system: str | None,
    to_system: str,
    reason: str = "transfer",
    actor_user_id: int | None = None,
    notes: str | None = None,
    source_module: str = "record_student_transition",
    extra_payload: dict[str, Any] | None = None,
    auth_db_path: str | None = None,
) -> bool:
    """Record a system transition + publish ``journey.transitioned``.

    Returns ``True`` if both the transition row and the bus event were
    written, ``False`` if either step failed. Best-effort — never raises.
    """
    transition_ok = False
    try:
        ids.record_transition(
            journey_id, from_system=from_system, to_system=to_system,
            reason=reason, actor_user_id=actor_user_id, notes=notes,
            db_path=auth_db_path,
        )
        transition_ok = True
    except Exception:
        logger.exception(
            "record_student_transition: record_transition failed for "
            "journey=%s %s -> %s", journey_id, from_system, to_system,
        )

    payload: dict[str, Any] = {
        "from_system": from_system, "to_system": to_system,
        "reason": reason,
    }
    if notes:
        payload["notes"] = notes
    if extra_payload:
        payload.update(extra_payload)

    bus_ok = False
    try:
        bus.publish_cross_system(
            bus.EVENT_JOURNEY_TRANSITIONED,
            source_system=from_system or to_system,
            source_module=source_module,
            journey_id=journey_id, target_system=None,  # broadcast
            actor_user_id=actor_user_id, db_path=auth_db_path,
            **payload,
        )
        bus_ok = True
    except Exception:
        logger.exception(
            "record_student_transition: bus publish failed for "
            "journey=%s", journey_id,
        )

    return transition_ok and bus_ok


def journey_id_for_system_record(
    system: str, *, pk: int | None = None, student_id: str | None = None,
    auth_db_path: str | None = None,
) -> str | None:
    """Convenience lookup wrapping ``identity_service`` finders.

    Tries pk first (only meaningful when the system has an integer pk
    column), then falls back to student_id. Returns ``None`` if neither
    resolves to a journey.
    """
    try:
        if pk is not None:
            row = ids.find_journey_by_system_pk(system, pk,
                                                  db_path=auth_db_path)
            if row:
                return row["journey_id"]
        if student_id:
            row = ids.find_journey_by_student_id(system, student_id,
                                                   db_path=auth_db_path)
            if row:
                return row["journey_id"]
    except Exception:
        logger.exception(
            "journey_id_for_system_record lookup failed: system=%s "
            "pk=%s student_id=%s", system, pk, student_id,
        )
    return None


__all__ = [
    "register_student_journey",
    "record_student_transition",
    "journey_id_for_system_record",
]
