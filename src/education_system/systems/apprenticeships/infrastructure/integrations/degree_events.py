"""Durable degree-apprenticeship event publishers and projections."""

from __future__ import annotations

from typing import Any

from education_system.platform.integrations.external import cross_system_bus as bus
from education_system.platform.cross_system import enrolments
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    apprentice_repository,
    degree_apprenticeship_repository as repo,
)

_registered = False
_ACADEMIC_EVENTS = (
    bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED,
    bus.EVENT_UNIVERSITY_CREDITS_UPDATED,
    bus.EVENT_UNIVERSITY_DEGREE_AWARDED,
)


def _consume_reconciliation(envelope: dict[str, Any]) -> None:
    journey_id = str(envelope.get("journey_id") or "")
    link = repo.get_link_by_journey(journey_id)
    if link is None:
        return
    payload = dict(envelope.get("payload") or {})
    repo.set_reconciliation(
        link.apprentice_id,
        str(payload.get("reconciliation_state") or "Pending Review"),
    )


def publish(event_name: str, *, journey_id: str, target_system: str | None = None,
            db_path: str | None = None, idempotency_key: str | None = None,
            **payload: Any) -> str:
    return bus.publish_cross_system(
        event_name, source_system="apprenticeships",
        source_module="degree_apprenticeship_service", journey_id=journey_id,
        target_system=target_system, idempotency_key=idempotency_key,
        db_path=db_path, **payload,
    )


def _consume_academic(envelope: dict[str, Any]) -> None:
    journey_id = str(envelope.get("journey_id") or "")
    link = repo.get_link_by_journey(journey_id)
    if link is None:
        return
    payload = dict(envelope.get("payload") or {})
    if str(payload.get("university_student_id") or "") != link.university_student_id:
        repo.set_reconciliation(link.apprentice_id, "Identity Mismatch")
        raise ValueError("University event student does not match the linked learner")
    payload.setdefault("university_degree_program_id", link.university_degree_program_id)
    repo.project_academic_progress(link.apprentice_id, envelope["event_id"], payload)
    if envelope.get("event_name") == bus.EVENT_UNIVERSITY_REGISTRATION_CHANGED:
        link = repo.activate_link(link.apprentice_id)
        enrolments.link_local_enrolment(
            journey_id=journey_id, system="university",
            local_student_id=link.university_student_id, status="active",
        )
        apprentice = apprentice_repository.get(link.apprentice_id)
        if apprentice and apprentice.username:
            from education_system.systems.apprenticeships.application.programmes.degree_apprenticeship_service import (
                grant_shared_account_access,
            )
            try:
                grant_shared_account_access(apprentice.username)
            except Exception:
                # Registration and the academic projection are authoritative;
                # account repair remains visible but must not poison replay.
                import logging
                logging.getLogger(__name__).exception(
                    "Could not grant dual-system access to %s",
                    apprentice.username,
                )
    _reconcile(link.apprentice_id, envelope["event_name"], payload, journey_id)


def _reconcile(apprentice_id: int, event_name: str, payload: dict[str, Any],
               journey_id: str) -> None:
    apprentice = apprentice_repository.get(apprentice_id)
    if apprentice is None:
        return
    degree_complete = event_name == bus.EVENT_UNIVERSITY_DEGREE_AWARDED or bool(
        payload.get("degree_outcome")
    )
    apprenticeship_complete = apprentice.status == "Completed"
    if degree_complete == apprenticeship_complete:
        repo.set_reconciliation(apprentice_id, "In Sync")
        return
    state = (
        "Degree Complete; Apprenticeship Incomplete" if degree_complete
        else "Apprenticeship Complete; Degree Incomplete"
    )
    repo.set_reconciliation(apprentice_id, state)
    publish(
        bus.EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED,
        journey_id=journey_id, target_system=None,
        idempotency_key=f"reconcile:{journey_id}:{state}",
        apprentice_id=apprentice_id, reconciliation_state=state,
    )


def register_consumers() -> None:
    global _registered
    if _registered:
        return
    for event_name in _ACADEMIC_EVENTS:
        bus.subscribe(event_name, _consume_academic,
                      handler_name=f"apprenticeships.degree_projection:{event_name}")
    bus.subscribe(
        bus.EVENT_DEGREE_APPRENTICESHIP_RECONCILIATION_REQUIRED,
        _consume_reconciliation,
        handler_name="apprenticeships.degree_projection:reconciliation",
    )
    _registered = True
