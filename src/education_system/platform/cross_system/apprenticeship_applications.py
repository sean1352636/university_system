"""Progression into an apprenticeship, from a college or the university.

This is the orchestration layer shared by Sixth Form, FE College and the
University. It uses the platform transition contract and never reads
another system's database: both ends are reached through the adapter
registry. The destination adapter creates an Applicant; only
:func:`start_programme` may turn that record into an apprentice who is
On Programme.

From the University this is a degree apprenticeship — a dual
registration — so the university enrolment stays open, exactly as the
FE enrolment usually does. Sixth form closes by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from education_system.platform.cross_system import (
    enrolments,
    handover,
    route_support,
    transitions,
)
from education_system.platform.cross_system.adapters.base import HandoverRequest

DESTINATION = "apprenticeships"
#: The systems that send learners into an apprenticeship through this board.
SOURCE_SYSTEMS = frozenset({"sixth_form", "fe_college", "university"})
#: The old name, kept for callers that imported it.
COLLEGE_SYSTEMS = SOURCE_SYSTEMS
#: Sources whose own enrolment stays open when the apprenticeship starts.
CONCURRENT_BY_DEFAULT = frozenset({"fe_college", "university"})
TERMINAL = frozenset({"completed", "cancelled"})


class ApplicationError(ValueError):
    """The requested apprenticeship application action is not valid."""


@dataclass(frozen=True)
class ApplicationPreview:
    source_system: str
    student_id: str
    boundary: str
    payload: dict[str, Any]
    included: tuple[str, ...]
    withheld_no_consent: tuple[str, ...]
    withheld_restricted: tuple[str, ...]
    missing_required: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_required


STATUS_LABELS = {
    "expected": "Draft",
    "applied": "Submitted",
    "offered": "Employer required / Offer",
    "accepted": "Accepted",
    "handover_approved": "Accepted",
    "admitted": "On Programme",
    "completed": "On Programme",
    "cancelled": "Cancelled",
}


def _adapters(source_system: str):
    """``(source, destination)`` adapters, from the platform registry."""
    if source_system not in SOURCE_SYSTEMS:
        raise ApplicationError(
            f"{source_system!r} does not progress learners to apprenticeships")
    return (route_support.adapter_for(source_system),
            route_support.adapter_for(DESTINATION))


def preview(
    source_system: str,
    student_id: str,
    *,
    intended_programme: dict[str, Any] | str,
    eligibility_evidence: Any,
    prior_attainment: Any | None = None,
    careers_record: Any | None = None,
    preferred_vacancy: Any | None = None,
    employer_details: Any | None = None,
    functional_skills: Any | None = None,
    predicted_qualifications: Any | None = None,
    achieved_qualifications: Any | None = None,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
) -> ApplicationPreview:
    """Return the exact consent-filtered payload before anything is saved."""
    if not intended_programme:
        raise ApplicationError("An intended apprenticeship programme is required")
    source, _ = _adapters(source_system)
    exported = source.export_handover(
        student_id, consent, destination_system=DESTINATION)
    record = dict(exported.record)
    # Every apprenticeship spec files identity as ``learner_identity``; the
    # sixth form exports it as ``student_identity``. Without this the
    # sixth-form route reported its own required identity as missing.
    if not record.get("learner_identity") and record.get("student_identity"):
        record["learner_identity"] = record["student_identity"]
    record.update({
        "intended_programme": intended_programme,
        "eligibility_evidence": eligibility_evidence,
    })
    optional = {
        "prior_attainment": prior_attainment,
        "careers_record": careers_record,
        "preferred_vacancy": preferred_vacancy,
        "employer_details": employer_details,
        "functional_skills": functional_skills,
        "predicted_qualifications": predicted_qualifications,
        "achieved_qualifications": achieved_qualifications,
    }
    record.update({key: value for key, value in optional.items()
                   if value not in (None, "", [], {})})
    released = handover.build_handover(
        source_system, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)
    return ApplicationPreview(
        source_system=source_system, student_id=student_id,
        boundary=released.boundary, payload=released.payload,
        included=tuple(released.included),
        withheld_no_consent=tuple(released.withheld_no_consent),
        withheld_restricted=tuple(released.withheld_restricted),
        missing_required=tuple(released.missing_required))


def submit(source_system: str, student_id: str, *, reason: str,
           actor_user_id: int | None = None, db_path: str | None = None,
           **preview_fields: Any) -> dict:
    """Submit an application and idempotently create a destination Applicant."""
    if not reason.strip():
        raise ApplicationError("An application reason is required")
    released = preview(source_system, student_id, **preview_fields)
    if not released.ready:
        raise ApplicationError(
            "Handover is incomplete: " + ", ".join(released.missing_required))
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=source_system,
            student_id=student_id, db_path=db_path)
    except route_support.RouteError as exc:
        raise ApplicationError(
            "The learner needs a first name, last name and date of birth "
            "before an apprenticeship application can be created") from exc
    existing = route_support.open_transition(
        journey_id, source_system, DESTINATION, db_path=db_path)
    if existing is not None:
        return application_view(existing)

    row, _created = route_support.start(
        journey_id, source_system=source_system,
        destination_system=DESTINATION, student_id=student_id,
        reason=reason.strip(), actor_user_id=actor_user_id, db_path=db_path)
    programme = preview_fields["intended_programme"]
    reference = (programme.get("reference") if isinstance(programme, dict)
                 else str(programme))
    row = transitions.record_application(
        row["transition_id"], application_reference=reference,
        intended_programme=programme, db_path=db_path)
    _, destination = _adapters(source_system)
    applicant = destination.create_applicant(HandoverRequest(
        journey_id=journey_id, source_system=source_system,
        destination_system=DESTINATION, payload=released.payload,
        transition_id=row["transition_id"],
        consent_reference=_consent_reference(preview_fields.get("consent"))))
    row = transitions.offer_place(
        row["transition_id"], local_student_id=applicant.local_applicant_id,
        conditions="Employer, eligibility and programme checks required",
        intended_programme=programme, db_path=db_path)
    return application_view(row)


def accept_offer(transition_id: str, *, accepted_by: str,
                 consent: bool | set[str] | None,
                 db_path: str | None = None, **preview_fields: Any) -> dict:
    """Accept an offer and persist the consent-filtered, auditable handover."""
    row = _require(transition_id, db_path=db_path, statuses={"offered"})
    local_id = route_support.source_local_id(row, db_path=db_path)
    if not local_id:
        raise ApplicationError("The application has no linked source learner")
    released = preview(
        row["source_system"], local_id, consent=consent, **preview_fields)
    if not released.ready:
        raise ApplicationError(
            "Handover is incomplete: " + ", ".join(released.missing_required))
    transitions.accept_place(
        transition_id, accepted_by=accepted_by, db_path=db_path)
    approved = transitions.approve_handover(
        transition_id, released.payload,
        consent_reference=_consent_reference(consent), db_path=db_path)
    return application_view(approved)


def start_programme(transition_id: str, *, programme_id: int, employer_id: int,
                    start_date: str | None = None, workplace_id: int | None = None,
                    concurrent: bool | None = None, actor: str = "platform",
                    db_path: str | None = None) -> dict:
    """Put an accepted Applicant On Programme and complete the transition.

    ``concurrent`` defaults to True from FE College and the University,
    whose enrolments run alongside the apprenticeship, and False from the
    sixth form.
    """
    row = _require(
        transition_id, db_path=db_path, statuses={"handover_approved"})
    if not programme_id or not employer_id:
        raise ApplicationError(
            "A programme and employer are required before starting")
    source_adapter, destination = _adapters(row["source_system"])
    result = destination.create_enrolment(
        row["journey_id"], programme_id=programme_id,
        employer_id=employer_id, workplace_id=workplace_id,
        start_date=start_date, actor=actor,
        reason=f"{row['source_system']} progression application accepted")
    transitions.admit(
        transition_id, local_student_id=result.local_student_id,
        start_date=result.start_date, db_path=db_path)
    if concurrent is None:
        concurrent = row["source_system"] in CONCURRENT_BY_DEFAULT
    completed = transitions.complete(
        transition_id, start_date=result.start_date,
        close_source=not concurrent, concurrent_enrolment=concurrent,
        db_path=db_path)
    if not concurrent:
        local_id = route_support.source_local_id(row, db_path=db_path)
        if local_id:
            source_adapter.close_enrolment(
                local_id, "Progressed to apprenticeship",
                end_date=result.start_date, actor=actor)
    return application_view(completed)


def list_applications(*, source_system: str | None = None,
                      journey_id: str | None = None,
                      db_path: str | None = None) -> list[dict]:
    """Application dashboard rows for a source system or Apprenticeships."""
    if journey_id:
        rows = transitions.list_transitions(journey_id, db_path=db_path)
    else:
        # Every row, completed included, for dashboard history.
        from education_system.platform.cross_system.enrolment_schema import (
            ensure_enrolment_schema,
        )
        from education_system.platform.identity.auth.db import connect
        ensure_enrolment_schema(db_path)
        conn = connect(db_path)
        try:
            rows = [transitions.hydrate(dict(r)) for r in conn.execute(
                "SELECT * FROM learner_transition WHERE destination_system = ? "
                "ORDER BY initiated_at DESC", (DESTINATION,)).fetchall()]
        finally:
            conn.close()
    return [application_view(row) for row in rows
            if row.get("destination_system") == DESTINATION
            and (source_system is None or row.get("source_system") == source_system)]


def application_view(row: dict) -> dict:
    out = dict(row)
    out["application_status"] = STATUS_LABELS.get(
        str(row.get("status")), str(row.get("status", "Unknown")).title())
    out["college_system"] = row.get("source_system")
    out["apprenticeship_record_id"] = row.get("destination_enrolment_id")
    return out


def _require(transition_id: str, *, db_path: str | None,
             statuses: set[str]) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SOURCE_SYSTEMS:
        raise ApplicationError("Not an application into an apprenticeship")
    if row.get("status") not in statuses:
        raise ApplicationError(
            f"Application is {row.get('status')}; expected "
            f"{', '.join(sorted(statuses))}")
    return row


def _consent_reference(consent: bool | set[str] | None) -> str | None:
    return route_support.consent_reference(consent, prefix="learner-consent")


__all__ = [
    "ApplicationError", "ApplicationPreview", "STATUS_LABELS",
    "SOURCE_SYSTEMS", "CONCURRENT_BY_DEFAULT",
    "preview", "submit", "accept_offer", "start_programme",
    "list_applications", "application_view",
]
