"""FE College → Adult Education, through the platform.

The integration layer's half of the FE → Adult Education link (the other
direction, Adult Education → FE College, is :mod:`.fe_applications`, and
Adult Education → University is :mod:`.university_applications`).

FE College refers an adult - to a community English, maths, ESOL or
digital skills course, or a part-time course after or beside their FE
programme. The FE adapter exports what the college holds,
``handover.FE_COLLEGE_TO_ADULT_EDUCATION`` decides what may cross (support
needs only with the learner's consent; safeguarding only as a reference),
and the Adult Education adapter finds or adds the learner (as an Enquiry)
and records the referral on its *Referrals from FE College* page. The
service decides there:

* **declined / withdrawn** → :func:`decline` / :func:`withdraw` (FE sees why);
* **enrolled on a class** → :func:`enrol`: accepted, the handover approved
  (fresh from FE, with the consent the learner gave), admitted and
  completed. The FE place stays open - adult courses run alongside.

Both ends are reached only through the adapter registry; nothing here
imports a system, and no system imports another.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from education_system.platform.cross_system import (
    handover,
    identity_service,
    route_support,
    transitions,
)
from education_system.platform.cross_system.adapters.base import AdapterError

DESTINATION = "adult_education"
SOURCE_SYSTEMS = frozenset({"fe_college"})
SOURCE_LABELS = {"fe_college": "FE College"}
LABEL = "Adult Education"

#: What the referring college sees for each step of its referral.
STATUS_LABELS = {"expected": "Being sent", "applied": "Being sent",
                 "offered": "With Adult Education", "accepted": "Accepted",
                 "handover_approved": "Accepted - to enrol",
                 "admitted": "Enrolled", "completed": "Enrolled",
                 "cancelled": "Declined / withdrawn"}


class ReferralError(ValueError):
    """A referral can't be made or moved on in its current state."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise ReferralError(str(exc)) from exc


def _check_source(system: str) -> None:
    if system not in SOURCE_SYSTEMS:
        raise ReferralError(f"{system!r} doesn't refer learners to adult education")


def _clean_date(value: Any, what: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        raise ReferralError(f"{what} isn't a date (YYYY-MM-DD)") from None


def released_handover(source_system: str, student_id: str, details: dict[str, Any], *,
                      consent: bool | set[str] | None,
                      safeguarding_reference: str | None = None):
    """The consent-filtered handover FE would release to Adult Education."""
    _check_source(source_system)
    exported = _adapter(source_system).export_handover(
        str(student_id), consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["referral_details"] = dict(details)
    return handover.build_handover(
        source_system, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


def refer(source_system: str, student_id: str, *, course: str, reason: str,
          intended_start: str | None = None, referrer: str = "",
          consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None,
          actor_user_id: int | None = None, db_path: str | None = None) -> dict:
    """Refer an FE learner to Adult Education. Returns the transition
    (``offered``: Adult Education has it to decide).

    Idempotent: an open referral Adult Education already holds is returned
    as it is; one it refused to record is retried.
    """
    _check_source(source_system)
    if not (course or "").strip() or not (reason or "").strip():
        raise ReferralError("Give the course or subject and the reason for the referral")
    start = _clean_date(intended_start, "The intended start")
    details = {"course": course.strip(), "reason": reason.strip(),
               "intended_start": start, "referred_by": SOURCE_LABELS[source_system],
               "referrer": (referrer or "").strip(), "consent": bool(consent),
               "referral_date": date.today().isoformat()}
    released = released_handover(source_system, student_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=source_system,
            student_id=str(student_id), db_path=db_path)
    except route_support.RouteError as exc:
        raise ReferralError(str(exc)) from exc
    existing = route_support.open_transition(journey_id, source_system, DESTINATION,
                                             db_path=db_path)
    if existing is not None and existing["status"] not in ("expected", "applied"):
        return existing
    if released.missing_required:
        raise ReferralError("The referral is missing: " + route_support.describe_missing(
            source_system, DESTINATION, released.missing_required))
    transition, _created = route_support.start(
        journey_id, source_system=source_system, destination_system=DESTINATION,
        student_id=str(student_id), reason=reason.strip(), actor_user_id=actor_user_id,
        db_path=db_path)
    tid = transition["transition_id"]
    if transition["status"] == "expected":
        # The course asked for is what the referral applies for: it is the
        # reference the college's board shows.
        transition = transitions.record_application(
            tid, application_reference=course.strip()[:200],
            actor_user_id=actor_user_id, db_path=db_path)
    if transition["status"] == "applied":
        try:
            applicant = route_support.request_applicant(
                transition, released.payload,
                consent_reference=route_support.consent_reference(
                    consent, prefix="learner-consent"))
        except Exception as exc:  # noqa: BLE001 - the adapter's own message
            raise ReferralError(f"{exc} The referral is saved; send it again once the "
                                "learner's record is put right.") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id, start_date=start,
            destination_enrolment_id=route_support.adopt_destination_enrolment(
                journey_id, DESTINATION, applicant.local_applicant_id, db_path=db_path),
            actor_user_id=actor_user_id, db_path=db_path)
    return transition


def _referral(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SOURCE_SYSTEMS:
        raise ReferralError("Not an FE College referral to adult education")
    return row


def decline(transition_id: str, *, reason: str, db_path: str | None = None) -> dict:
    """Adult Education declined the referral; FE sees the reason."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.reject(transition_id, reason=(reason or "Declined").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def withdraw(transition_id: str, *, reason: str = "Referral withdrawn",
             db_path: str | None = None) -> dict:
    """The referral was withdrawn (the learner changed their mind, say)."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.cancel(transition_id, reason=(reason or "Withdrawn").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def enrol(transition_id: str, *, local_student_id: str, start_date: str | None = None,
          consent: bool | set[str] | None = None, accepted_by: str = "adult education",
          db_path: str | None = None) -> dict:
    """The referred learner enrolled on an adult education class: accept,
    approve the handover FE released, admit and complete - concurrently,
    so the FE place stays open."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] == "completed":
        return row
    if row["status"] not in ("offered", "accepted", "handover_approved", "admitted"):
        raise ReferralError(f"The referral is {row['status']} - it can't be enrolled")
    start = _clean_date(start_date, "The start date") or date.today().isoformat()
    if row["status"] in ("offered", "accepted"):
        local_id = route_support.source_local_id(row, db_path=db_path)
        if not local_id:
            raise ReferralError("The referral has no FE learner linked to it")
        released = released_handover(
            row["source_system"], local_id,
            {"course": row.get("application_reference") or "",
             "reason": row.get("reason") or "Referral"},
            consent=consent)
        if row["status"] == "offered":
            transitions.accept_place(transition_id, accepted_by=accepted_by,
                                     db_path=db_path)
        row = transitions.approve_handover(
            transition_id, released,
            consent_reference=route_support.consent_reference(consent,
                                                              prefix="learner-consent"),
            db_path=db_path)
    if row["status"] == "handover_approved":
        row = transitions.admit(transition_id, local_student_id=str(local_student_id),
                                start_date=start, db_path=db_path)
    return transitions.complete(transition_id, start_date=start, close_source=False,
                                concurrent_enrolment=True, db_path=db_path)


# ── Queues ───────────────────────────────────────────────────────────

def _all_into(*, db_path: str | None) -> list[dict]:
    rows = transitions.pending_transitions(DESTINATION, db_path=db_path)
    for status in ("completed", "cancelled"):
        rows += transitions.pending_transitions(DESTINATION, status=status,
                                                db_path=db_path)
    return rows


def referrals_from(source_system: str, *, include_closed: bool = True,
                   db_path: str | None = None) -> list[dict]:
    """A college's referrals to Adult Education, newest first, each with
    ``label`` (what the college sees), ``learner`` (the learner's name) and
    ``course`` (what was asked for)."""
    _check_source(source_system)
    out = []
    for row in _all_into(db_path=db_path):
        if row.get("source_system") != source_system:
            continue
        if not include_closed and row["status"] in ("completed", "cancelled"):
            continue
        j = identity_service.get(row["journey_id"], db_path=db_path) or {}
        item = dict(row)
        item["learner"] = " ".join(x for x in (j.get("legal_first_name"),
                                               j.get("legal_last_name")) if x)
        item["source_learner_id"] = route_support.source_local_id(row, db_path=db_path)
        item["course"] = row.get("application_reference") or ""
        item["label"] = STATUS_LABELS.get(row["status"], row["status"])
        if row["status"] == "cancelled":
            item["label"] = ("Declined" if row.get("decision") == "rejected"
                             else "Withdrawn")
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


__all__ = ["DESTINATION", "SOURCE_SYSTEMS", "SOURCE_LABELS", "LABEL", "STATUS_LABELS",
           "ReferralError", "released_handover", "refer", "decline", "withdraw", "enrol",
           "referrals_from"]
