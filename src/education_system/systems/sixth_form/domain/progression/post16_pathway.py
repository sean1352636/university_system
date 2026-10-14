"""Sixth Form to FE College referral and enrolment workflow.

The FE College is reached only through the platform registry — this module
never imports the college's code. The sixth form's own adapter is imported
directly, because it is this system's.
"""

from __future__ import annotations

from typing import Any

from education_system.platform.cross_system import (
    enrolments,
    handover,
    identity_service,
    route_support,
    transitions,
)
from education_system.systems.sixth_form.domain.progression.cross_system_adapter import (
    ADAPTER as SIXTH_FORM_ADAPTER,
)

SOURCE = "sixth_form"
DESTINATION = "fe_college"


class PathwayError(ValueError):
    """A referral cannot be advanced in its current state."""


def _fe_adapter():
    """The FE College's adapter, from the platform registry."""
    return route_support.adapter_for(DESTINATION)


def _student(student_id: str):
    from education_system.systems.sixth_form.domain.learners.students import students

    student = students.get_student(student_id)
    if student is None:
        raise PathwayError(f"No sixth-form learner {student_id}")
    if not student.date_of_birth:
        raise PathwayError("A date of birth is required before referral")
    return student


def _journey(student_id: str, *, db_path: str | None = None) -> str:
    student = _student(student_id)
    return identity_service.get_or_create_journey(
        first_name=student.first_name,
        last_name=student.last_name,
        date_of_birth=student.date_of_birth,
        system=SOURCE,
        student_id=student.student_id,
        db_path=db_path,
    )


def _source_enrolment(journey_id: str, *, db_path: str | None = None) -> dict:
    row = enrolments.current_enrolment(journey_id, SOURCE, db_path=db_path)
    if row is None:
        row = enrolments.create_enrolment(
            journey_id=journey_id, system=SOURCE, status="active", db_path=db_path)
    return row


def _released_handover(student_id: str, referral_details: dict[str, Any], *,
                       consent: bool | set[str] | None,
                       safeguarding_reference: str | None = None):
    exported = SIXTH_FORM_ADAPTER.export_handover(
        student_id, consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["referral_details"] = dict(referral_details)
    return handover.build_handover(
        SOURCE, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


def refer(student_id: str, *, pathway: str, reason: str,
          intended_start: str | None = None,
          consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None,
          actor_user_id: int | None = None,
          db_path: str | None = None) -> dict:
    """Refer a learner and create an idempotent FE applicant record."""
    if not pathway.strip() or not reason.strip():
        raise PathwayError("pathway and reason are required")
    journey_id = _journey(student_id, db_path=db_path)
    existing = route_support.open_transition(
        journey_id, SOURCE, DESTINATION, db_path=db_path)
    if existing is not None:
        return existing

    details = {"pathway": pathway.strip(), "reason": reason.strip()}
    if intended_start:
        details["intended_start"] = intended_start
    released = _released_handover(
        student_id, details, consent=consent,
        safeguarding_reference=safeguarding_reference)

    transition, _created = route_support.start(
        journey_id, source_system=SOURCE, destination_system=DESTINATION,
        student_id=student_id, reason=reason, actor_user_id=actor_user_id,
        db_path=db_path)
    transition = transitions.record_application(
        transition["transition_id"], db_path=db_path, pathway=pathway)
    applicant = route_support.request_applicant(transition, released.payload)
    return transitions.offer_place(
        transition["transition_id"], local_student_id=applicant.local_applicant_id,
        start_date=intended_start, db_path=db_path)


def accept_referral(transition_id: str, *, accepted_by: str,
                    consent: bool | set[str] | None = None,
                    safeguarding_reference: str | None = None,
                    db_path: str | None = None) -> dict:
    """Accept the FE offer and approve the auditable information handover."""
    transition = transitions.get_transition(transition_id, db_path=db_path)
    if transition is None or transition["source_system"] != SOURCE \
            or transition["destination_system"] != DESTINATION:
        raise PathwayError("Not a Sixth Form to FE College referral")
    source = enrolments.get_enrolment(transition["source_enrolment_id"], db_path=db_path)
    if source is None or not source.get("local_student_id"):
        raise PathwayError("Referral has no linked sixth-form learner")
    details = {"reason": transition.get("reason") or "FE pathway referral"}
    released = _released_handover(
        source["local_student_id"], details, consent=consent,
        safeguarding_reference=safeguarding_reference)
    transitions.accept_place(transition_id, accepted_by=accepted_by, db_path=db_path)
    return transitions.approve_handover(
        transition_id, released, consent_reference=str(consent) if consent else None,
        db_path=db_path)


def enrol_referral(transition_id: str, *, concurrent: bool = True,
                   start_date: str | None = None,
                   db_path: str | None = None) -> dict:
    """Create the FE enrolment and optionally close the Sixth Form record."""
    transition = transitions.get_transition(transition_id, db_path=db_path)
    if transition is None or transition["status"] != "handover_approved":
        raise PathwayError("Referral must be accepted and its handover approved first")
    result = _fe_adapter().create_enrolment(
        transition["journey_id"], start_date=start_date)
    transitions.admit(
        transition_id, local_student_id=result.local_student_id,
        start_date=result.start_date, db_path=db_path)
    completed = transitions.complete(
        transition_id, start_date=result.start_date,
        close_source=not concurrent, db_path=db_path,
        concurrent_enrolment=concurrent)
    if not concurrent:
        source = enrolments.get_enrolment(
            transition["source_enrolment_id"], db_path=db_path)
        if source and source.get("local_student_id"):
            SIXTH_FORM_ADAPTER.close_enrolment(
                source["local_student_id"], "Transferred to FE College",
                end_date=result.start_date)
    return completed


def incoming_referrals(*, status: str | None = None,
                       db_path: str | None = None) -> list[dict]:
    """The FE admissions work queue for Sixth Form referrals."""
    return [row for row in transitions.pending_transitions(
        DESTINATION, status=status, db_path=db_path)
        if row.get("source_system") == SOURCE]


__all__ = ["PathwayError", "refer", "accept_referral", "enrol_referral",
           "incoming_referrals"]
