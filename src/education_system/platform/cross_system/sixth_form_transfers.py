"""FE College to Sixth Form change-of-provider workflow.

Part of the platform's integration layer: both colleges are reached through
the adapter registry — the FE learner through FE's ``export_handover``, the
A-level catalogue through the sixth form's ``offered_subjects()`` — so the
FE College's screens and the Sixth Form's incoming queue share it without
either system importing the other.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from education_system.platform.cross_system import (
    enrolments,
    handover,
    identity_service,
    route_support,
    transitions,
)

SOURCE = "fe_college"
DESTINATION = "sixth_form"


class TransferError(ValueError):
    pass


def _sixth_form_adapter():
    """The Sixth Form's adapter, from the platform registry."""
    return route_support.adapter_for(DESTINATION)


def _sixth_form_catalogue() -> set[str]:
    """The Sixth Form's A-level list, asked of its adapter rather than imported.

    Empty when the adapter publishes none (a test double, say). The unknown-
    subject check is then skipped: the Sixth Form's own intake still refuses
    a malformed choice when the applicant is created.
    """
    offered = getattr(_sixth_form_adapter(), "offered_subjects", None)
    return set(offered()) if callable(offered) else set()


def _fe_adapter():
    """The FE College's adapter, from the platform registry."""
    return route_support.adapter_for(SOURCE)


def _fe_student(student_id: str) -> dict:
    """The FE learner's identity, as FE's own adapter exports it."""
    from education_system.platform.cross_system.adapters.base import AdapterError

    try:
        exported = _fe_adapter().export_handover(
            str(student_id).strip(), False, destination_system=DESTINATION)
    except AdapterError as exc:
        raise TransferError(f"No FE learner {student_id}") from exc
    identity = route_support.identity_of(dict(exported.record))
    if not identity:
        raise TransferError(f"No FE learner {student_id}")
    return identity


def request_transfer(student_id: str, *, reason: str, intended_start: str | None = None,
                     consent: bool | set[str] | None = None,
                     safeguarding_reference: str | None = None,
                     actor_user_id: int | None = None,
                     db_path: str | None = None) -> dict:
    """Open an application while deliberately leaving FE active."""
    learner = _fe_student(student_id)
    if not learner.get("date_of_birth"):
        raise TransferError("A date of birth is required before transfer")
    if not reason.strip():
        raise TransferError("A transfer reason is required")
    journey_id = identity_service.get_or_create_journey(
        first_name=learner["first_name"], last_name=learner["last_name"],
        date_of_birth=learner["date_of_birth"], system=SOURCE,
        student_id=student_id, db_path=db_path)
    for row in reversed(transitions.list_transitions(journey_id, db_path=db_path)):
        if (row["source_system"], row["destination_system"]) == (SOURCE, DESTINATION) \
                and row["status"] not in ("completed", "cancelled"):
            return row
    source = enrolments.current_enrolment(journey_id, SOURCE, db_path=db_path)
    assert source is not None
    row = transitions.start_transition(
        journey_id=journey_id, source_system=SOURCE,
        source_enrolment_id=source["enrolment_id"], destination_system=DESTINATION,
        reason=reason.strip(), actor_user_id=actor_user_id, db_path=db_path)
    return transitions.record_application(
        row["transition_id"], application_reference=f"FE-{student_id}",
        intended_start=intended_start, consent=bool(consent),
        safeguarding_reference=safeguarding_reference, db_path=db_path)


def review_application(transition_id: str, *, subjects: list[str],
                       gcse_eligible: bool, available_subjects: set[str] | None = None,
                       reviewed_by: str = "Sixth Form admissions",
                       db_path: str | None = None) -> dict:
    """Reject, or create a Sixth Form applicant and offer after checks."""
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or (row["source_system"], row["destination_system"]) != (SOURCE, DESTINATION):
        raise TransferError("Not an FE College to Sixth Form application")
    choices = [s.strip() for s in subjects if s and s.strip()]
    if len(choices) != 3 or len(set(choices)) != 3:
        raise TransferError("Exactly three distinct A-level subjects are required")
    catalogue = _sixth_form_catalogue()
    unknown = set(choices) - catalogue if catalogue else set()
    if unknown:
        raise TransferError(f"Unknown A-level subject(s): {', '.join(sorted(unknown))}")
    unavailable = set(choices) - (available_subjects or catalogue or set(choices))
    if not gcse_eligible or unavailable:
        reasons = []
        if not gcse_eligible:
            reasons.append("GCSE entry requirements not met")
        if unavailable:
            reasons.append(f"no capacity in {', '.join(sorted(unavailable))}")
        return transitions.cancel(
            transition_id, reason="; ".join(reasons), cancelled_by=reviewed_by,
            db_path=db_path)

    source = enrolments.get_enrolment(row["source_enrolment_id"], db_path=db_path)
    assert source and source.get("local_student_id")
    exported = _fe_adapter().export_handover(
        source["local_student_id"], destination_system=DESTINATION)
    transfer_request: dict[str, Any] = {
        "reason": row.get("reason"), "subjects": choices, "reviewed_by": reviewed_by}
    record = dict(exported.record)
    record["transfer_request"] = transfer_request
    released = handover.build_handover(SOURCE, DESTINATION, record, consent=False)
    applicant = route_support.request_applicant(row, released.payload)
    offered = transitions.offer_place(
        transition_id, local_student_id=applicant.local_applicant_id,
        destination_enrolment_id=route_support.adopt_destination_enrolment(
            row["journey_id"], DESTINATION, applicant.local_applicant_id,
            db_path=db_path),
        year_group="12", conditions="GCSE evidence verified", db_path=db_path)
    return offered


def accept_offer(transition_id: str, *, accepted_by: str,
                 consent: bool | set[str] | None = None,
                 safeguarding_reference: str | None = None,
                 db_path: str | None = None) -> dict:
    row = transitions.accept_place(transition_id, accepted_by=accepted_by, db_path=db_path)
    source = enrolments.get_enrolment(row["source_enrolment_id"], db_path=db_path)
    assert source and source.get("local_student_id")
    exported = _fe_adapter().export_handover(
        source["local_student_id"], consent, destination_system=DESTINATION)
    payload = transitions.get_transition(transition_id, db_path=db_path)
    record = dict(exported.record)
    # Subject choices are already present on the idempotent local applicant.
    record["transfer_request"] = {"reason": payload.get("reason")}
    released = handover.build_handover(
        SOURCE, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)
    return transitions.approve_handover(
        transition_id, released, consent_reference=str(consent) if consent else None,
        db_path=db_path)


def enrol(transition_id: str, *, start_date: str,
          allow_early: bool = False, db_path: str | None = None) -> dict:
    """Admit on/after the start date, then and only then close FE."""
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row["status"] != "handover_approved":
        raise TransferError("The offer must be accepted and handover approved first")
    if date.fromisoformat(start_date) > date.today() and not allow_early:
        raise TransferError("The agreed start date has not been reached; FE remains active")
    result = _sixth_form_adapter().create_enrolment(
        row["journey_id"], start_date=start_date)
    transitions.admit(
        transition_id, local_student_id=result.local_student_id,
        year_group="12", start_date=start_date, db_path=db_path)
    completed = transitions.complete(
        transition_id, start_date=start_date, close_source=True, db_path=db_path)
    source = enrolments.get_enrolment(row["source_enrolment_id"], db_path=db_path)
    if source and source.get("local_student_id"):
        _fe_adapter().close_enrolment(
            source["local_student_id"], "Transferred to Sixth Form", end_date=start_date)
    return completed


def incoming(*, status: str | None = None, db_path: str | None = None) -> list[dict]:
    return [row for row in transitions.pending_transitions(
        DESTINATION, status=status, db_path=db_path) if row.get("source_system") == SOURCE]


__all__ = ["TransferError", "request_transfer", "review_application",
           "accept_offer", "enrol", "incoming"]
