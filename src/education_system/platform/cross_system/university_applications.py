"""Sixth Form, FE College and Apprenticeship progression into University admissions.

Both ends are reached through the platform adapter registry. The
university's admissions operations this board drives — recording an
offer, a firm choice, looking the application up — are methods on the
university's own adapter, so nothing here imports the university.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from education_system.platform.cross_system import (
    handover, route_support, transitions,
)
from education_system.platform.cross_system.adapters.base import HandoverRequest

logger = logging.getLogger(__name__)

DESTINATION = "university"
SOURCES = frozenset({"sixth_form", "fe_college", "apprenticeships"})

#: Sources whose application *is* a UCAS application. An apprentice
#: progressing onto a degree or top-up is admitted on their standard and
#: EPA grade instead, so requiring a UCAS id of them would block the one
#: route ``APPRENTICESHIPS_TO_UNIVERSITY`` exists to describe.
UCAS_SOURCES = frozenset({"sixth_form", "fe_college"})

#: A UCAS Personal ID is ten digits. Same rule the sixth form's own UCAS
#: module enforces (``progression.ucas._UCAS_ID_RE``) — a reference that
#: passes there and fails here, or vice versa, is a link that only breaks
#: once the learner has already been told they applied.
_UCAS_ID_RE = re.compile(r"^\d{10}$")

#: UCAS allows five choices in the main scheme.
MAX_CHOICES = 5


class UniversityApplicationError(ValueError):
    pass


def normalise_ucas_id(value: Any) -> str:
    """A UCAS Personal ID, with the spacing people type it with removed.

    Raises :class:`UniversityApplicationError` if it is not ten digits —
    the id is the key the two systems match a learner on, and a mistyped
    one links this application to nobody or, worse, to somebody else.
    """
    cleaned = re.sub(r"[\s-]", "", str(value or ""))
    if not _UCAS_ID_RE.match(cleaned):
        raise UniversityApplicationError(
            "A UCAS personal ID is 10 digits — "
            f"{str(value or '').strip()!r} is not")
    return cleaned


#: Where a consent record may carry its date. Two shapes reach this
#: boundary: one built by :func:`consent_record` here, and one read out of
#: the sixth form's own GDPR register, which dates consent as
#: ``granted_date``. Both are real records; neither is the only spelling.
CONSENT_DATE_KEYS = ("recorded_at", "granted_date", "date")

#: Where it may carry who or what attested to it.
CONSENT_ACTOR_KEYS = ("recorded_by", "source", "consent_id")

#: Where it may carry its own reference.
CONSENT_REFERENCE_KEYS = ("reference", "consent_id")


def consent_reference(record: dict[str, Any] | None) -> str:
    """The consent record's own reference, under whichever key it uses."""
    for key in CONSENT_REFERENCE_KEYS:
        value = (record or {}).get(key)
        if value:
            return str(value)
    return "consent"


def consent_record(*, recorded_by: str, scope: tuple[str, ...] = (),
                   method: str = "recorded in the college's own system",
                   ucas_id: str | None = None,
                   recorded_at: str | None = None) -> dict[str, Any]:
    """The learner's consent to this handover, as a record that says who.

    A consent artefact derived from a UCAS number alone documents nothing:
    it names no person who took the consent, no date it was taken, and no
    scope it covers, so there is nothing to check it against later. The
    caller must supply the member of staff attesting to it.
    """
    if not recorded_by:
        raise UniversityApplicationError(
            "Record who took the learner's consent")
    record: dict[str, Any] = {
        "reference": f"HANDOVER-{DESTINATION.upper()}-"
                     f"{ucas_id or recorded_by}-{recorded_at or date.today().isoformat()}",
        "recorded_at": recorded_at or date.today().isoformat(),
        "recorded_by": recorded_by,
        "method": method,
        "scope": list(scope),
    }
    if ucas_id:
        record["ucas_id"] = ucas_id
    return record


@dataclass(frozen=True)
class Preview:
    payload: dict[str, Any]
    included: tuple[str, ...]
    withheld_no_consent: tuple[str, ...]
    withheld_restricted: tuple[str, ...]
    missing_required: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing_required


DISPLAY_STATUS = {
    "expected": "Planning",
    "applied": "Application submitted / Awaiting decisions",
    "offered": "Conditional/unconditional offer",
    "accepted": "Firm/insurance selected",
    "handover_approved": "Results pending",
    "admitted": "Place confirmed",
    "completed": "Enrolled",
    "cancelled": "Cancelled",
}

UNIVERSITY_STATUS_LABELS = {
    "submitted": "Application submitted",
    "documents_pending": "Awaiting decisions",
    "under_review": "Awaiting decisions",
    "decision_pending": "Awaiting decisions",
    "conditional_offer": "Conditional offer",
    "unconditional_offer": "Unconditional offer",
    "accepted": "Firm/insurance selected",
    "conditions_met": "Results confirmed",
    "right_to_study": "Place confirmed",
    "registration_pending": "Place confirmed",
    "ready_to_enrol": "Place confirmed",
    "enrolled": "Enrolled",
    "declined": "Declined",
    "deferred": "Deferred",
    "lapsed": "Lapsed",
}


def _source_adapter(system: str):
    """The source system's adapter, from the platform registry."""
    if system not in SOURCES:
        raise UniversityApplicationError(
            f"{system!r} does not progress learners to the university")
    return route_support.adapter_for(system)


def _university_adapter():
    """The university's adapter, from the platform registry."""
    return route_support.adapter_for(DESTINATION)


def _identity_key(source_system: str) -> str:
    """The key *this route's* spec files the learner's identity under.

    The college specs call it ``student_identity``;
    ``APPRENTICESHIPS_TO_UNIVERSITY`` requires ``learner_identity``.
    """
    return "learner_identity" if source_system == "apprenticeships" else "student_identity"


def payload_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """The identity block of a released payload, whichever key it uses.

    ``build_handover`` emits only the keys its spec declares, so an
    apprenticeship payload carries ``learner_identity`` and nothing else.
    Reading ``student_identity`` unconditionally raised ``KeyError`` on the
    one route the apprenticeship spec exists to describe.
    """
    return payload.get("student_identity") or payload.get("learner_identity") or {}


def _normalise_source_record(source_system: str, student_id: str,
                             consent: bool | set[str] | None) -> dict:
    record = dict(_source_adapter(source_system).export_handover(
        student_id, consent, destination_system=DESTINATION).record)
    identity = record.get("student_identity") or record.get("learner_identity") or {}
    contact = record.get("contact_details") or {}
    identity = dict(identity)
    identity.update({key: value for key, value in contact.items()
                     if key in {"email", "phone", "address", "postcode"} and value})
    identity["college_student_id"] = student_id
    # Name the identity the way *this route's* spec asks for it, or the
    # route permanently reports its own required identity field as
    # missing. Readers of the *released* payload must go through
    # ``payload_identity`` for the same reason.
    identity_key = _identity_key(source_system)
    record.pop("student_identity", None)
    record.pop("learner_identity", None)
    record[identity_key] = identity
    if source_system == "fe_college":
        record.setdefault("current_programme", record.get("vocational_profile"))
        record.setdefault("qualification_profile", record.get("vocational_profile"))
        record.setdefault("recognised_prior_learning", record.get("prior_learning"))
        record.setdefault("support_referral", record.get("send_support"))
    return record


def preview(source_system: str, student_id: str, *,
            ucas_application: dict[str, Any] | None = None,
            choices: list[dict[str, Any]] | None = None,
            handover_consent: dict[str, Any] | None = None,
            personal_statement: str | None = None,
            academic_reference: str | None = None,
            predicted_qualifications: Any | None = None,
            achieved_qualifications: Any | None = None,
            qualification_profile: Any | None = None,
            offer_conditions: Any | None = None,
            confirmed_destination: Any | None = None,
            support_indicators: Any | None = None,
            consent: bool | set[str] | None = None,
            safeguarding_reference: str | None = None) -> Preview:
    """Build the exact payload the learner can review before submission."""
    if source_system in UCAS_SOURCES:
        if not ucas_application or not ucas_application.get("ucas_id"):
            raise UniversityApplicationError("A linked UCAS personal ID is required")
        ucas_application = dict(ucas_application)
        ucas_application["ucas_id"] = normalise_ucas_id(
            ucas_application["ucas_id"])
        if not choices:
            raise UniversityApplicationError("At least one university course choice is required")
        if len(choices) > MAX_CHOICES:
            raise UniversityApplicationError(
                f"UCAS allows {MAX_CHOICES} choices; {len(choices)} were given")
    if not handover_consent:
        raise UniversityApplicationError("A handover consent record is required")
    if not any(handover_consent.get(k) for k in CONSENT_DATE_KEYS):
        # Consent with no date is not evidence of anything, and a record
        # derived from a UCAS number alone has none. Build it with
        # ``consent_record``, or read a real one out of the college's own
        # GDPR register, which dates and attributes it.
        raise UniversityApplicationError(
            "The handover consent record must say when consent was given")
    if not any(handover_consent.get(k) for k in CONSENT_ACTOR_KEYS):
        logger.warning(
            "Handover consent %r for %s/%s names nobody and no system that "
            "recorded it", consent_reference(handover_consent),
            source_system, student_id)
    record = _normalise_source_record(source_system, student_id, consent)
    # Only contribute the keys this route actually carries — an absent key
    # and an empty one mean different things to ``missing_required``.
    record["handover_consent"] = handover_consent
    if ucas_application:
        record["ucas_application"] = ucas_application
    if choices:
        record["choices"] = choices
    additions = {
        "personal_statement": personal_statement,
        "reference": academic_reference,
        "predicted_qualifications": predicted_qualifications,
        "achieved_qualifications": achieved_qualifications,
        "qualification_profile": qualification_profile,
        "offer_conditions": offer_conditions,
        "confirmed_destination": confirmed_destination,
        "support_indicators": support_indicators,
    }
    record.update({k: v for k, v in additions.items()
                   if v not in (None, "", [], {})})
    released = handover.build_handover(
        source_system, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)
    return Preview(
        payload=released.payload, included=tuple(released.included),
        withheld_no_consent=tuple(released.withheld_no_consent),
        withheld_restricted=tuple(released.withheld_restricted),
        missing_required=tuple(released.missing_required))


def submit(source_system: str, student_id: str, *, actor_user_id: int | None = None,
           db_path: str | None = None, **fields: Any) -> dict:
    """Submit to UCAS/University and create an idempotent University Applicant."""
    released = preview(source_system, student_id, **fields)
    if not released.ready:
        raise UniversityApplicationError(
            "Handover is incomplete: " + ", ".join(released.missing_required))
    try:
        journey_id = route_support.journey_for(
            payload_identity(released.payload), system=source_system,
            student_id=student_id, db_path=db_path)
    except route_support.RouteError as exc:
        raise UniversityApplicationError(str(exc)) from exc
    existing = route_support.open_transition(
        journey_id, source_system, DESTINATION, db_path=db_path)
    if existing is not None:
        return application_view(existing)
    ucas_id = (released.payload.get("ucas_application") or {}).get("ucas_id")
    if ucas_id:
        _reject_reused_ucas_id(str(ucas_id), journey_id, db_path=db_path)
    row, _created = route_support.start(
        journey_id, source_system=source_system,
        destination_system=DESTINATION, student_id=student_id,
        reason="University application", actor_user_id=actor_user_id,
        db_path=db_path)
    # An apprentice has no UCAS id or choice list; their reference is the
    # standard they completed, which is what the offer is made against.
    # Read it from the *released payload*: ``standard_completed`` is not
    # one of preview()'s keyword arguments and never can be — it comes off
    # the apprenticeship adapter's own export, so looking for it in
    # ``fields`` found nothing and left the route with no reference at all.
    # From the released payload, not ``fields``: preview() normalised the
    # UCAS id there, and the stored reference must be the normalised form
    # or two spellings of one id stop matching each other.
    ucas = released.payload.get("ucas_application") or {}
    reference = ucas.get("ucas_id")
    if not reference:
        standard = released.payload.get("standard_completed") or {}
        if isinstance(standard, dict):
            reference = (standard.get("reference") or standard.get("title")
                         or standard.get("standard") or None)
        elif standard:
            reference = str(standard)
    row = transitions.record_application(
        row["transition_id"], application_reference=reference,
        choices=fields.get("choices") or [], db_path=db_path)
    applicant = _university_adapter().create_applicant(HandoverRequest(
        journey_id=journey_id, source_system=source_system,
        destination_system=DESTINATION, payload=released.payload,
        transition_id=row["transition_id"],
        consent_reference=consent_reference(fields.get("handover_consent"))))
    out = application_view(row)
    out["university_application_id"] = applicant.local_applicant_id
    return out


def record_offer(transition_id: str, *, unconditional: bool,
                 conditions: list[dict[str, Any]] | None = None,
                 db_path: str | None = None) -> dict:
    """University-owned decision: record an offer and its conditions."""
    row, application_id = _application(transition_id, db_path=db_path,
                                       expected={"applied"})
    _university_adapter().record_decision(
        application_id, unconditional=unconditional, conditions=conditions)
    # Deliberately no local_student_id: an offer does not create a student,
    # and this used to park the *application* id in the slot that names one
    # — overwritten by the real student id at admit, read by nobody in
    # between, and wrong to anyone who looked at it meanwhile. The
    # application is found through the journey, which is how ``_application``
    # resolved it here in the first place.
    row = transitions.offer_place(
        transition_id,
        conditions="Unconditional" if unconditional else "Conditional",
        db_path=db_path)
    return application_view(row)


def select_firm_choice(transition_id: str, *, choice_id: int,
                       accepted_by: str, consent_payload: Preview,
                       consent_reference: str,
                       db_path: str | None = None) -> dict:
    """Learner selects a firm choice and approves the final handover."""
    _row, application_id = _application(transition_id, db_path=db_path,
                                        expected={"offered"})
    _university_adapter().accept_choice(
        application_id, choice_id, accepted_by=accepted_by)
    transitions.accept_place(transition_id, accepted_by=accepted_by, db_path=db_path)
    row = transitions.approve_handover(
        transition_id, consent_payload.payload,
        consent_reference=consent_reference, db_path=db_path)
    return application_view(row)


def confirm_place(transition_id: str, *, actor_id: str,
                  start_date: str | None = None,
                  db_path: str | None = None) -> dict:
    """Convert only a University-ready applicant, then close college."""
    row, application_id = _application(
        transition_id, db_path=db_path, expected={"handover_approved"})
    result = _university_adapter().create_enrolment(
        row["journey_id"], application_id=str(application_id),
        actor_id=actor_id, start_date=start_date)
    transitions.admit(
        transition_id, local_student_id=result.local_student_id,
        start_date=start_date, db_path=db_path)
    completed = transitions.complete(
        transition_id, start_date=start_date, close_source=True,
        source_exit_reason="Progressed to university", db_path=db_path)
    local_id = route_support.source_local_id(row, db_path=db_path)
    if local_id:
        _source_adapter(row["source_system"]).close_enrolment(
            local_id, "Progressed to university",
            end_date=start_date, actor=actor_id)
    return application_view(completed)


def list_applications(*, source_system: str | None = None,
                      db_path: str | None = None) -> list[dict]:
    from education_system.platform.identity.auth.db import connect
    from education_system.platform.cross_system.enrolment_schema import ensure_enrolment_schema
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        sql = ["SELECT * FROM learner_transition WHERE destination_system = ?"]
        args: list[Any] = [DESTINATION]
        if source_system is not None:
            sql.append("AND source_system = ?")
            args.append(source_system)
        sql.append("ORDER BY initiated_at DESC")
        rows = [transitions.hydrate(dict(r))
                for r in conn.execute(" ".join(sql), args).fetchall()]
    finally:
        conn.close()
    # One batched university lookup for the whole list. Asking per row
    # costs a fresh connection to the university database each time —
    # about a tenth of a second while it parses the schema — which turned
    # a two-hundred-strong admissions list into a twenty-second stall.
    apps, ok = _university_applications([r["journey_id"] for r in rows])
    out = [application_view(r, app=apps.get(str(r["journey_id"])))
           for r in rows]
    if not ok:
        for view in out:
            view["university_lookup_failed"] = True
    return out


_MISSING = object()


def _university_applications(journey_ids) -> tuple[dict[str, dict], bool]:
    """The university's own row for each journey, in one query.

    Returns ``(applications, ok)``. ``ok`` is False when the university
    could not be read at all — which is not the same as nobody having
    applied, and must not be shown as if it were.
    """
    if not journey_ids:
        return {}, True
    try:
        return _university_adapter().find_applications(
            journey_ids, strict=True), True
    except Exception:
        logger.exception(
            "Could not read the university's applications for %d journey(s); "
            "their university status is unavailable, not absent",
            len(journey_ids))
        return {}, False


def application_view(row: dict, app: dict | None | object = _MISSING) -> dict:
    """A transition row, plus the university's own view of the application.

    ``app`` may be passed by a caller that has already batched the
    university-side lookup; left out, it is fetched for this one row.
    """
    out = dict(row)
    out.setdefault("choices", [])
    out["application_status"] = DISPLAY_STATUS.get(
        str(row.get("status")), str(row.get("status") or "Unknown").title())
    out["university_lookup_failed"] = False
    if app is _MISSING:
        try:
            app = _university_adapter().find_application(row["journey_id"])
        except Exception:
            # Do not pass this off as "no application": a university that
            # cannot be read and a learner who has not applied look
            # identical downstream, and only one of them is a fact.
            logger.exception(
                "Could not read the university's application for journey %s",
                row.get("journey_id"))
            app = None
            out["university_lookup_failed"] = True
    app = app if isinstance(app, dict) else None
    out["university_application_id"] = app.get("application_id") if app else None
    out["university_status"] = app.get("status") if app else None
    # The reference the application is filed under at both ends. The
    # transition holds what the college quoted; the university's
    # external_reference is the same value once it has been through
    # intake, and is the fallback for rows written before the transition
    # stored one at all. This is the key a reader can match a UCAS row on.
    out["application_reference"] = (row.get("application_reference")
                                    or (app or {}).get("external_reference"))
    if app and app.get("status") in UNIVERSITY_STATUS_LABELS:
        out["application_status"] = UNIVERSITY_STATUS_LABELS[app["status"]]
    return out


def _reject_reused_ucas_id(ucas_id: str, journey_id: str, *,
                           db_path: str | None = None) -> None:
    """Refuse a UCAS id already attached to a different learner.

    The intake already tolerates one learner arriving under two references
    — a college correcting a number. The reverse is not a correction: two
    people quoting one UCAS id means one of the two applications belongs
    to somebody else, and admitting the second silently merges them.
    """
    from education_system.platform.identity.auth.db import connect
    from education_system.platform.cross_system.enrolment_schema import ensure_enrolment_schema
    ensure_enrolment_schema(db_path)
    conn = connect(db_path)
    try:
        clash = conn.execute(
            "SELECT transition_id, journey_id FROM learner_transition "
            "WHERE destination_system = ? AND application_reference = ? "
            "AND journey_id <> ? AND status <> 'cancelled' LIMIT 1",
            (DESTINATION, ucas_id, journey_id)).fetchone()
    finally:
        conn.close()
    if clash is not None:
        raise UniversityApplicationError(
            f"UCAS personal ID {ucas_id} is already on application "
            f"{clash['transition_id']} for a different learner")


def _application(transition_id: str, *, db_path: str | None,
                 expected: set[str]) -> tuple[dict, int]:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if not row or row.get("source_system") not in SOURCES \
            or row.get("destination_system") != DESTINATION:
        raise UniversityApplicationError("Not a college-to-university application")
    if row.get("status") not in expected:
        raise UniversityApplicationError(
            f"Application is {row.get('status')}; expected {', '.join(sorted(expected))}")
    app = _university_adapter().find_application(row["journey_id"])
    if not app:
        raise UniversityApplicationError("University applicant record is missing")
    return row, int(app["application_id"])


__all__ = [
    "UniversityApplicationError", "Preview", "DISPLAY_STATUS",
    "UNIVERSITY_STATUS_LABELS", "MAX_CHOICES", "normalise_ucas_id",
    "consent_record", "consent_reference", "payload_identity", "preview",
    "submit", "record_offer", "select_firm_choice", "confirm_place",
    "list_applications", "application_view",
]
