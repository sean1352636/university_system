"""Progression into FE College, from the sixth form, an apprenticeship,
adult education or a training provider.

The integration layer's half of two links on the platform diagram:

* Sixth Form → FE College (a vocational or mixed post-16 pathway), and
* Apprenticeship ↔ FE College — the apprenticeship side of the two-way
  link (FE → Apprenticeship is :mod:`.apprenticeship_applications`).
* Adult Education → FE College: an adult moving from a community course
  onto an FE course (FE → Adult Education is
  :mod:`.adult_education_applications`).
* Training Provider → FE College: a learner trained on a short course going
  on to an FE course (FE → Training Provider is
  :mod:`.training_provider_requests`).

Both ends are reached only through the adapter registry; nothing here
imports a system, so each keeps its own database. The flow is the
platform's transition steps: refer (FE applicant created) → accept and
approve the consent-filtered handover → enrol. Enrolment is concurrent by
default — the learner usually keeps the sixth-form place or the
apprenticeship while taking the FE course (dual enrolment).
"""

from __future__ import annotations

from typing import Any

from education_system.platform.cross_system import (
    handover,
    route_support,
    transitions,
)
from education_system.platform.cross_system.adapters.base import AdapterError

DESTINATION = "fe_college"
SOURCE_SYSTEMS = frozenset({"sixth_form", "apprenticeships", "adult_education",
                            "training_provider"})
SOURCE_LABELS = {"sixth_form": "Sixth Form", "apprenticeships": "Apprenticeship",
                 "adult_education": "Adult Education",
                 "training_provider": "Training Provider"}


class PathwayError(ValueError):
    """A referral cannot be made or advanced in its current state."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise PathwayError(str(exc)) from exc


def _check_source(source_system: str) -> None:
    if source_system not in SOURCE_SYSTEMS:
        raise PathwayError(f"{source_system!r} does not refer learners to FE College")


def released_handover(source_system: str, student_id: str,
                      referral_details: dict[str, Any], *,
                      consent: bool | set[str] | None,
                      safeguarding_reference: str | None = None):
    """The consent-filtered handover the source would release to FE."""
    _check_source(source_system)
    exported = _adapter(source_system).export_handover(
        student_id, consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["referral_details"] = dict(referral_details)
    return handover.build_handover(
        source_system, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


def refer(source_system: str, student_id: str, *, pathway: str, reason: str,
          intended_start: str | None = None,
          consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None,
          actor_user_id: int | None = None,
          db_path: str | None = None) -> dict:
    """Refer a learner and create an idempotent FE applicant record."""
    _check_source(source_system)
    if not pathway.strip() or not reason.strip():
        raise PathwayError("pathway and reason are required")
    details = {"pathway": pathway.strip(), "reason": reason.strip()}
    if intended_start:
        details["intended_start"] = intended_start
    released = released_handover(source_system, student_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload),
            system=source_system, student_id=student_id, db_path=db_path)
    except route_support.RouteError as exc:
        raise PathwayError("A first name, last name and date of birth are required "
                           "before referral") from exc
    existing = route_support.open_transition(
        journey_id, source_system, DESTINATION, db_path=db_path)
    if existing is not None:
        return existing
    if released.missing_required:
        raise PathwayError("Handover is incomplete: " + ", ".join(released.missing_required))
    transition, _created = route_support.start(
        journey_id, source_system=source_system, destination_system=DESTINATION,
        student_id=student_id, reason=reason, actor_user_id=actor_user_id,
        db_path=db_path)
    transition = transitions.record_application(
        transition["transition_id"], db_path=db_path, pathway=pathway)
    applicant = route_support.request_applicant(transition, released.payload)
    return transitions.offer_place(
        transition["transition_id"], local_student_id=applicant.local_applicant_id,
        start_date=intended_start, db_path=db_path)


def _referral(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SOURCE_SYSTEMS:
        raise PathwayError("Not a referral into FE College")
    return row


def accept_referral(transition_id: str, *, accepted_by: str,
                    consent: bool | set[str] | None = None,
                    safeguarding_reference: str | None = None,
                    db_path: str | None = None) -> dict:
    """Accept the FE offer and approve the auditable information handover."""
    row = _referral(transition_id, db_path=db_path)
    local_id = route_support.source_local_id(row, db_path=db_path)
    if not local_id:
        raise PathwayError("Referral has no linked source learner")
    details = {"reason": row.get("reason") or "FE pathway referral"}
    released = released_handover(row["source_system"], local_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    transitions.accept_place(transition_id, accepted_by=accepted_by, db_path=db_path)
    return transitions.approve_handover(
        transition_id, released,
        consent_reference=route_support.consent_reference(consent, prefix="learner-consent"),
        db_path=db_path)


def enrol_referral(transition_id: str, *, concurrent: bool = True,
                   start_date: str | None = None,
                   db_path: str | None = None) -> dict:
    """Create the FE enrolment; close the source record unless concurrent."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] != "handover_approved":
        raise PathwayError("Referral must be accepted and its handover approved first")
    result = _adapter(DESTINATION).create_enrolment(row["journey_id"], start_date=start_date)
    transitions.admit(transition_id, local_student_id=result.local_student_id,
                      start_date=result.start_date, db_path=db_path)
    completed = transitions.complete(
        transition_id, start_date=result.start_date, close_source=not concurrent,
        concurrent_enrolment=concurrent, db_path=db_path)
    if not concurrent:
        local_id = route_support.source_local_id(row, db_path=db_path)
        if local_id:
            _adapter(row["source_system"]).close_enrolment(
                local_id, "Transferred to FE College", end_date=result.start_date)
    return completed


def incoming_referrals(*, source_system: str | None = None, status: str | None = None,
                       db_path: str | None = None) -> list[dict]:
    """FE admissions' queue of referrals, from one source or all of them."""
    return [r for r in transitions.pending_transitions(
        DESTINATION, status=status, db_path=db_path)
        if r.get("source_system") in SOURCE_SYSTEMS
        and (source_system is None or r.get("source_system") == source_system)]


__all__ = ["PathwayError", "SOURCE_SYSTEMS", "SOURCE_LABELS", "released_handover",
           "refer", "accept_referral", "enrol_referral", "incoming_referrals"]
