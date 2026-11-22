"""Shared plumbing for the routes that move a learner between systems.

Every route — nursery→primary, a Year 11 post-16 application, a college
learner applying to university — begins the same way: find or create the
learner's journey, reuse an open transition on that boundary rather than
opening a second, make sure the source holds an enrolment row, open the
transition, and ask the destination's adapter for an applicant. The
orchestrators used to carry that sequence three times over, each with
direct imports of the systems at either end. It lives here once, and
reaches systems only through :mod:`.adapters.registry`.

:func:`transfer` runs all seven workflow steps in one call, for the
administrative moves a school makes on a single button press. It resumes:
if an earlier attempt stopped part-way, the next call finds the open
transition and carries on from its current step, and every adapter call
it makes is idempotent on the journey, so nothing is created twice.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.cross_system import (
    enrolments,
    handover,
    identity_service,
    transitions,
)
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    ApplicantResult,
    EnrolmentResult,
    HandoverRequest,
    PhaseAdapter,
)
from education_system.platform.governance.gdpr.consent_service import (
    verify_transition_handover_consent,
)

logger = logging.getLogger(__name__)

#: Transition statuses from which a route does not resume.
TERMINAL = frozenset({"completed", "cancelled"})

#: The keys the boundary specs file a learner's identity under — the
#: nursery spec says ``child_identity``, the school specs
#: ``student_identity``, the work-based ones ``learner_identity``.
IDENTITY_KEYS = ("child_identity", "student_identity", "learner_identity")


class RouteError(ValueError):
    """A route cannot proceed with what it was given."""


def adapter_for(system: str) -> PhaseAdapter:
    """The registered adapter for ``system``, loading it if declared."""
    return registry.require(system)


def identity_of(record: dict[str, Any]) -> dict[str, Any]:
    """The identity block of an exported record or released payload."""
    for key in IDENTITY_KEYS:
        value = record.get(key)
        if isinstance(value, dict) and value:
            return value
    return {}


def journey_for(identity: dict[str, Any], *, system: str, student_id: str,
                db_path: str | None = None) -> str:
    """The canonical journey for a learner, created if this is their first
    cross-system move. Needs legal name and date of birth to anchor it."""
    first = identity.get("first_name") or identity.get("given_name")
    last = identity.get("last_name") or identity.get("family_name")
    dob = identity.get("date_of_birth") or identity.get("dob")
    if not first or not last or not dob:
        raise RouteError(
            "The learner needs a first name, last name and date of birth "
            "on record before they can move between systems")
    return identity_service.get_or_create_journey(
        first_name=first, last_name=last, date_of_birth=dob, system=system,
        student_id=student_id, upn=identity.get("upn") or None,
        nhs_number=identity.get("nhs_number") or None, db_path=db_path)


def open_transition(journey_id: str, source_system: str,
                    destination_system: str, *,
                    db_path: str | None = None) -> dict | None:
    """The newest transition on this boundary that has not finished."""
    for row in reversed(transitions.list_transitions(journey_id, db_path=db_path)):
        if (row.get("source_system") == source_system
                and row.get("destination_system") == destination_system
                and row.get("status") not in TERMINAL):
            return row
    return None


def source_enrolment(journey_id: str, system: str, student_id: str, *,
                     year_group: str | None = None,
                     db_path: str | None = None) -> dict:
    """The source's open enrolment row, created or completed as needed."""
    row = enrolments.current_enrolment(journey_id, system, db_path=db_path)
    if row is None:
        return enrolments.create_enrolment(
            journey_id=journey_id, system=system, local_student_id=student_id,
            year_group=year_group, status="active", db_path=db_path)
    if not row.get("local_student_id"):
        enrolments.update_enrolment(
            row["enrolment_id"], local_student_id=student_id, db_path=db_path)
        row = dict(row, local_student_id=student_id)
    return row


def start(journey_id: str, *, source_system: str, destination_system: str,
          student_id: str, reason: str, actor_user_id: int | None = None,
          year_group: str | None = None,
          db_path: str | None = None) -> tuple[dict, bool]:
    """The open transition on this boundary, or a new one.

    Returns ``(row, created)``. Reusing the open row is the route-level
    idempotency: a double click, or a retry after an error, continues the
    learner's one application instead of opening a parallel one.
    """
    existing = open_transition(journey_id, source_system, destination_system,
                               db_path=db_path)
    if existing is not None:
        return existing, False
    source = source_enrolment(journey_id, source_system, student_id,
                              year_group=year_group, db_path=db_path)
    row = transitions.start_transition(
        journey_id=journey_id, source_system=source_system,
        source_enrolment_id=source["enrolment_id"],
        destination_system=destination_system, reason=reason,
        actor_user_id=actor_user_id, db_path=db_path)
    return row, True


def request_applicant(transition: dict, payload: dict, *,
                      consent_reference: str | None = None,
                      year_group: str | None = None,
                      institution_id: str | None = None) -> ApplicantResult:
    """Ask the destination's adapter for a pending admission record.

    ``payload`` must be the *released* handover — already filtered by
    :func:`handover.build_handover` — never the source's raw export.
    """
    destination = adapter_for(transition["destination_system"])
    return destination.create_applicant(HandoverRequest(
        journey_id=transition["journey_id"],
        source_system=transition.get("source_system") or "",
        destination_system=transition["destination_system"],
        payload=payload, transition_id=transition["transition_id"],
        consent_reference=consent_reference, year_group=year_group,
        institution_id=institution_id))


def source_local_id(transition: dict, *, db_path: str | None = None) -> str | None:
    """The source system's own id for the learner on this transition."""
    enrolment_id = transition.get("source_enrolment_id")
    if not enrolment_id:
        return None
    row = enrolments.get_enrolment(enrolment_id, db_path=db_path)
    return (row or {}).get("local_student_id")


def close_source(transition: dict, reason: str, *, db_path: str | None = None,
                 **details: Any) -> str | None:
    """Close the learner's record in the source system, through its adapter.

    Returns the local id that was closed, or ``None`` if the transition
    carries none. The adapter keeps the record; it never deletes.
    """
    local_id = source_local_id(transition, db_path=db_path)
    if local_id:
        adapter_for(transition["source_system"]).close_enrolment(
            local_id, reason, **details)
    return local_id


def adopt_destination_enrolment(journey_id: str, system: str,
                                local_student_id: str | None, *,
                                db_path: str | None = None) -> str | None:
    """The open enrolment already mirrored for this local record, if any.

    Creating a local record often registers the learner's journey, and
    that mirrors an ``active`` enrolment row for the destination before
    the workflow has admitted anyone. Passing the row to ``offer_place``
    makes it the transition's destination enrolment. Otherwise the
    workflow opens a second row beside it, and the mirror stays
    ``active`` after the learner has moved on.
    """
    if not local_student_id:
        return None
    for row in enrolments.list_enrolments(journey_id, system=system,
                                          include_closed=False, db_path=db_path):
        if str(row.get("local_student_id") or "") == str(local_student_id):
            return str(row["enrolment_id"])
    return None


def consent_reference(consent: bool | set[str] | frozenset[str] | None, *,
                      prefix: str = "handover-consent") -> str | None:
    """A stable, auditable label for what the consent covered.

    Never ``consent:`` or ``consent_records:``: those prefixes are reserved
    for ids in ``consent_records``. A label that looked like one would fail
    ``approve_handover``'s check, and every sensitive field would be
    withheld from the stored handover.
    """
    if consent is True:
        return f"{prefix}:all"
    if isinstance(consent, (set, frozenset)) and consent:
        return f"{prefix}:" + ",".join(sorted(consent))
    return None


def describe_missing(source_system: str, destination_system: str,
                     missing: list[str] | tuple[str, ...]) -> str:
    """Name each missing required field, flagging the ones that are only
    missing because consent was not given."""
    spec = handover.get_spec(source_system, destination_system)
    parts = []
    for key in missing:
        declared = spec.get(key) if spec is not None else None
        if declared is not None and declared.needs_consent:
            parts.append(f"{key} (needs consent to share)")
        else:
            parts.append(key)
    return ", ".join(parts)


def release(source_system: str, destination_system: str, student_id: str, *,
            consent: bool | set[str] | None = None,
            safeguarding_reference: str | None = None,
            extra_record: dict[str, Any] | None = None,
            ) -> tuple[dict[str, Any], handover.HandoverResult]:
    """Export from the source adapter and filter it through the spec.

    Returns ``(record, released)``: the raw gathered record (for reading
    identity) and the consent-filtered result that may actually cross.
    """
    exported = adapter_for(source_system).export_handover(
        student_id, consent, destination_system=destination_system)
    record = dict(exported.record)
    record.update({k: v for k, v in (extra_record or {}).items()
                   if v not in (None, "", [], {})})
    released = handover.build_handover(
        source_system, destination_system, record, consent=consent,
        safeguarding_reference=(safeguarding_reference
                                or exported.safeguarding_reference))
    return record, released


@dataclass
class TransferOutcome:
    """What :func:`transfer` did."""

    journey_id: str
    transition: dict
    released: handover.HandoverResult
    applicant: ApplicantResult | None = None
    enrolment: EnrolmentResult | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def local_student_id(self) -> str | None:
        if self.enrolment is not None:
            return self.enrolment.local_student_id
        return (self.applicant.local_applicant_id
                if self.applicant is not None else None)


def transfer(
    *,
    source_system: str,
    destination_system: str,
    student_id: str,
    reason: str,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
    recorded_consent: str | None = None,
    extra_record: dict[str, Any] | None = None,
    year_group: str | None = None,
    institution_id: str | None = None,
    accepted_by: str = "admissions",
    enrolment_details: dict[str, Any] | None = None,
    start_date: str | None = None,
    close_source_record: bool = True,
    close_details: dict[str, Any] | Callable[[TransferOutcome], dict[str, Any]] | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
) -> TransferOutcome:
    """Move a learner across one boundary, all seven steps, in one call.

    The source adapter exports, the boundary spec filters, the destination
    adapter creates the applicant and then the enrolment, and the source
    adapter closes (never deletes) its record. What crosses is exactly
    ``build_handover``'s payload — so, for example, a nursery's medical
    alerts reach the primary school only if the consent covers them.

    Raises :class:`RouteError` before anything is written when the
    handover is incomplete. After that point, a failure leaves the
    transition at the step it reached; calling again resumes it.

    ``close_details`` may be a callable taking the outcome so far, for a
    source that wants to record something only the destination knew —
    the new school email on a leavers register, for instance.

    ``recorded_consent`` is the consent's own reference — a
    ``consent_records`` id (``consent_service.transition_handover_reference``)
    or the sending system's consent id. Without one, a label describing
    ``consent`` is stored. A ``consent_records`` reference that fails
    verification withholds every sensitive field. That check runs here,
    before the applicant is created, so the destination's record and the
    approved handover never disagree about what crossed.
    """
    if handover.is_in_phase(source_system, destination_system):
        # The destination adapter is this system's own: asking it for an
        # applicant would re-register the learner in the database they are
        # leaving, and the completion step would then close that record.
        raise RouteError(
            f"A {source_system} → {destination_system} move is a change of "
            f"institution within the phase; use transfer_within_phase()")
    consent_ref = recorded_consent or consent_reference(consent)
    if verify_transition_handover_consent(consent_ref, db_path=db_path) is False:
        logger.warning("Consent %s is not a granted transition_handover "
                       "consent; sensitive fields will not cross", consent_ref)
        consent = None
    record, released = release(
        source_system, destination_system, student_id, consent=consent,
        safeguarding_reference=safeguarding_reference,
        extra_record=extra_record)
    if not released.complete:
        raise RouteError(
            f"The {source_system} → {destination_system} handover is missing "
            f"required information: "
            + describe_missing(source_system, destination_system,
                               released.missing_required))
    problems = handover.validate_handover(
        source_system, destination_system, released.payload)
    if problems:
        raise RouteError("; ".join(problems))
    # Resolve the far end before opening anything, so a system with no
    # adapter fails here rather than stranding a half-open transition.
    destination = adapter_for(destination_system)

    journey_id = journey_for(identity_of(record), system=source_system,
                             student_id=student_id, db_path=db_path)
    row, created = start(
        journey_id, source_system=source_system,
        destination_system=destination_system, student_id=student_id,
        reason=reason, actor_user_id=actor_user_id, db_path=db_path)
    if not created:
        logger.info("Resuming %s → %s transition %s at %s", source_system,
                    destination_system, row["transition_id"], row["status"])
    tid = row["transition_id"]
    outcome = TransferOutcome(journey_id=journey_id, transition=row,
                              released=released)

    if row["status"] == "expected":
        row = transitions.record_application(
            tid, application_reference=f"{source_system}:{student_id}",
            actor_user_id=actor_user_id, db_path=db_path)
    if row["status"] == "applied":
        outcome.applicant = request_applicant(
            row, released.payload, consent_reference=consent_ref,
            year_group=year_group, institution_id=institution_id)
        row = transitions.offer_place(
            tid, local_student_id=outcome.applicant.local_applicant_id,
            destination_enrolment_id=adopt_destination_enrolment(
                journey_id, destination_system,
                outcome.applicant.local_applicant_id, db_path=db_path),
            year_group=outcome.applicant.year_group or year_group,
            institution_id=institution_id, actor_user_id=actor_user_id,
            db_path=db_path)
    if row["status"] == "offered":
        row = transitions.accept_place(tid, accepted_by=accepted_by,
                                       actor_user_id=actor_user_id,
                                       db_path=db_path)
    if row["status"] == "accepted":
        row = transitions.approve_handover(
            tid, released, consent_reference=consent_ref,
            actor_user_id=actor_user_id, db_path=db_path)
    if row["status"] == "handover_approved":
        outcome.enrolment = destination.create_enrolment(
            journey_id,
            outcome.applicant.local_applicant_id if outcome.applicant else None,
            start_date=start_date, **(enrolment_details or {}))
        row = transitions.admit(
            tid, local_student_id=outcome.enrolment.local_student_id,
            year_group=outcome.enrolment.year_group or year_group,
            start_date=outcome.enrolment.start_date or start_date,
            institution_id=institution_id, actor_user_id=actor_user_id,
            db_path=db_path)
    if row["status"] == "admitted":
        row = transitions.complete(
            tid, start_date=start_date, close_source=close_source_record,
            source_exit_reason=reason, actor_user_id=actor_user_id,
            db_path=db_path)
    outcome.transition = row

    if close_source_record:
        try:
            extra = (close_details(outcome) if callable(close_details)
                     else close_details) or {}
            close_source(row, reason, db_path=db_path, end_date=start_date,
                         **extra)
        except Exception as exc:
            # The learner is already enrolled at the destination; failing
            # the whole move now would report a success as an error. Say
            # what is left to do instead.
            logger.exception("Could not close the %s record for transition %s",
                             source_system, tid)
            outcome.warnings.append(
                f"Enrolled at {destination_system}, but the {source_system} "
                f"record could not be closed: {exc}")
    return outcome


def _institution_label(institution: dict[str, Any] | str) -> str:
    if isinstance(institution, dict):
        return str(institution.get("name") or institution.get("urn")
                   or institution.get("ukprn") or "").strip()
    return str(institution or "").strip()


def transfer_within_phase(
    *,
    system: str,
    student_id: str,
    receiving_institution: dict[str, Any] | str,
    reason: str,
    leaving_date: str | None = None,
    expected_start: str | None = None,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
    recorded_consent: str | None = None,
    extra_record: dict[str, Any] | None = None,
    close_details: dict[str, Any] | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
) -> TransferOutcome:
    """Move a learner to another institution in the same phase.

    Each system runs one institution, so the receiver is outside this
    system's database: no destination adapter is called and no applicant
    is created. The handover is released through the boundary's in-phase
    spec (consent enforced as on every other route), stored on the
    transition for the receiving institution to be sent, the transition is
    completed with the source enrolment marked ``transferred``, and the
    local record is closed through the system's adapter (never deleted).

    ``receiving_institution`` is required — a name, or a dict with
    ``name`` and optionally ``urn`` / ``ukprn`` / ``contact``. Resumes an
    open transition on the same boundary, like :func:`transfer`.
    """
    if handover.get_spec(system, system) is None:
        raise RouteError(f"{system!r} has no in-phase transfer route")
    label = _institution_label(receiving_institution)
    if not label:
        raise RouteError("Name the institution the learner is moving to")
    if not (reason or "").strip():
        raise RouteError("A reason for the move is required")
    institution = (dict(receiving_institution)
                   if isinstance(receiving_institution, dict)
                   else {"name": label})

    consent_ref = recorded_consent or consent_reference(consent)
    if verify_transition_handover_consent(consent_ref, db_path=db_path) is False:
        logger.warning("Consent %s is not a granted transition_handover "
                       "consent; sensitive fields will not cross", consent_ref)
        consent = None
    record, released = release(
        system, system, student_id, consent=consent,
        safeguarding_reference=safeguarding_reference,
        extra_record={
            **(extra_record or {}),
            "receiving_institution": institution,
            "move_details": {"reason": reason.strip(),
                             "leaving_date": leaving_date,
                             "expected_start": expected_start},
        })
    if not released.complete:
        raise RouteError(
            f"The {system} → {label} handover is missing required "
            f"information: " + describe_missing(system, system,
                                                released.missing_required))
    problems = handover.validate_handover(system, system, released.payload)
    if problems:
        raise RouteError("; ".join(problems))

    journey_id = journey_for(identity_of(record), system=system,
                             student_id=student_id, db_path=db_path)
    # "Transferred" is what the FE and apprenticeship adapters read to mark
    # the record transferred rather than withdrawn.
    full_reason = f"Transferred to {label}: {reason.strip()}"
    row, created = start(
        journey_id, source_system=system, destination_system=system,
        student_id=student_id, reason=full_reason,
        actor_user_id=actor_user_id, db_path=db_path)
    if not created:
        logger.info("Resuming in-phase %s transition %s at %s", system,
                    row["transition_id"], row["status"])
    tid = row["transition_id"]
    outcome = TransferOutcome(journey_id=journey_id, transition=row,
                              released=released)

    if row["status"] in ("expected", "applied", "offered", "accepted"):
        row = transitions.approve_handover(
            tid, released, consent_reference=consent_ref,
            actor_user_id=actor_user_id, effective_date=leaving_date,
            db_path=db_path)
    if row["status"] in ("handover_approved", "admitted"):
        row = transitions.complete(
            tid, start_date=leaving_date, close_source=True,
            source_exit_reason=full_reason, source_status="transferred",
            actor_user_id=actor_user_id, effective_date=leaving_date,
            destination_detail=label, db_path=db_path)
    outcome.transition = row

    try:
        close_source(row, full_reason, db_path=db_path, end_date=leaving_date,
                     destination=label, destination_school=label,
                     destination_urn=institution.get("urn"),
                     **(close_details or {}))
    except Exception as exc:
        logger.exception("Could not close the %s record for transition %s",
                         system, tid)
        outcome.warnings.append(
            f"Transfer to {label} recorded, but the {system} record could "
            f"not be closed: {exc}")
    return outcome


__all__ = [
    "IDENTITY_KEYS",
    "RouteError",
    "TERMINAL",
    "TransferOutcome",
    "adapter_for",
    "adopt_destination_enrolment",
    "close_source",
    "consent_reference",
    "describe_missing",
    "identity_of",
    "journey_for",
    "open_transition",
    "release",
    "request_applicant",
    "source_enrolment",
    "source_local_id",
    "start",
    "transfer",
    "transfer_within_phase",
]
