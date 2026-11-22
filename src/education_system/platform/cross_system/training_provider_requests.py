"""Apprenticeships / FE College → Training Provider, through the platform.

The integration layer's half of two links (the other directions, Training
Provider → Apprenticeships and → FE College, are the existing
:mod:`.apprenticeship_applications` and :mod:`.fe_applications` boards):

An apprenticeship provider or an FE college asks the training provider to
train one of its learners on a short course - first aid, health and
safety, a licence to practise. The sender's adapter exports what it holds,
``handover.*_TO_TRAINING_PROVIDER`` decides what may cross (support needs
only with the learner's consent; safeguarding only as a reference), and
the training provider's adapter finds or adds the learner and records the
request on its *Training Requests* page. The training provider decides:

* **declined / withdrawn** → :func:`decline` / :func:`withdraw` (the sender sees why);
* **booked on a session** → :func:`booked`: accepted, the handover approved
  (fresh from the sender, with the learner's consent), admitted and
  completed - concurrently, the learner's programme stays open;
* **certificate issued** (or a fail / did not attend) → :func:`record_outcome`:
  logged on the request for the sender and passed to the sender's adapter
  (``receive_training_result``, when it has one) - Apprenticeships makes it
  off-the-job hours awaiting approval, FE College adds it to prior attainment.

Both ends are reached only through the adapter registry; nothing here
imports a system, and no system imports another.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from education_system.platform.cross_system import (
    handover,
    identity_service,
    route_support,
    transitions,
)
from education_system.platform.cross_system.adapters.base import AdapterError

logger = logging.getLogger(__name__)

DESTINATION = "training_provider"
SOURCE_SYSTEMS = frozenset({"apprenticeships", "fe_college"})
SOURCE_LABELS = {"apprenticeships": "Apprenticeships", "fe_college": "FE College"}
LABEL = "Training Provider"
PAYERS = ("Sender pays (purchase order)", "Employer pays", "Learner pays",
          "Funded (grant / skills fund)")
#: Step name of an outcome note on the request's log.
OUTCOME_STEP = "training_outcome"

#: What the sender sees for each step of its request.
STATUS_LABELS = {"expected": "Being sent", "applied": "Being sent",
                 "offered": "With the training provider", "accepted": "Accepted",
                 "handover_approved": "Accepted - to book",
                 "admitted": "Booked", "completed": "Booked",
                 "cancelled": "Declined / withdrawn"}


class RequestError(ValueError):
    """A request can't be made or moved on in its current state."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise RequestError(str(exc)) from exc


def _check_source(system: str) -> None:
    if system not in SOURCE_SYSTEMS:
        raise RequestError(f"{system!r} doesn't send learners to the training provider")


def _clean_date(value: Any, what: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        raise RequestError(f"{what} isn't a date (YYYY-MM-DD)") from None


def released_handover(source_system: str, student_id: str, details: dict[str, Any], *,
                      consent: bool | set[str] | None,
                      safeguarding_reference: str | None = None):
    """The consent-filtered handover the sender would release."""
    _check_source(source_system)
    exported = _adapter(source_system).export_handover(
        str(student_id), consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["referral_details"] = dict(details)
    return handover.build_handover(
        source_system, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


def request(source_system: str, student_id: str, *, course: str, reason: str,
            needed_by: str | None = None, payer: str = PAYERS[0],
            po_number: str = "", referrer: str = "",
            consent: bool | set[str] | None = None,
            safeguarding_reference: str | None = None,
            actor_user_id: int | None = None, db_path: str | None = None) -> dict:
    """Ask the training provider to train a learner. Returns the transition
    (``offered``: the training provider has it to decide).

    Idempotent: an open request the provider already holds is returned as
    it is; one it refused to record is retried.
    """
    _check_source(source_system)
    if not (course or "").strip() or not (reason or "").strip():
        raise RequestError("Give the course and the reason for the request")
    if payer not in PAYERS:
        raise RequestError("Say who pays for the course")
    needed = _clean_date(needed_by, "The needed-by date")
    details = {"course": course.strip(), "reason": reason.strip(), "needed_by": needed,
               "payer": payer, "po_number": (po_number or "").strip(),
               "requested_by": SOURCE_LABELS[source_system],
               "referrer": (referrer or "").strip(), "consent": bool(consent),
               "request_date": date.today().isoformat()}
    released = released_handover(source_system, student_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=source_system,
            student_id=str(student_id), db_path=db_path)
    except route_support.RouteError as exc:
        raise RequestError(str(exc)) from exc
    existing = route_support.open_transition(journey_id, source_system, DESTINATION,
                                             db_path=db_path)
    if existing is not None and existing["status"] not in ("expected", "applied"):
        return existing
    if released.missing_required:
        raise RequestError("The request is missing: " + route_support.describe_missing(
            source_system, DESTINATION, released.missing_required))
    transition, _created = route_support.start(
        journey_id, source_system=source_system, destination_system=DESTINATION,
        student_id=str(student_id), reason=reason.strip(), actor_user_id=actor_user_id,
        db_path=db_path)
    tid = transition["transition_id"]
    if transition["status"] == "expected":
        # The course asked for is the reference the sender's board shows.
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
            raise RequestError(f"{exc} The request is saved; send it again once the "
                               "learner's record is put right.") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            destination_enrolment_id=route_support.adopt_destination_enrolment(
                journey_id, DESTINATION, applicant.local_applicant_id, db_path=db_path),
            actor_user_id=actor_user_id, db_path=db_path)
    return transition


def _request(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SOURCE_SYSTEMS:
        raise RequestError("Not a training request to the training provider")
    return row


def decline(transition_id: str, *, reason: str, db_path: str | None = None) -> dict:
    """The training provider declined the request; the sender sees why."""
    row = _request(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.reject(transition_id, reason=(reason or "Declined").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def withdraw(transition_id: str, *, reason: str = "Request withdrawn",
             db_path: str | None = None) -> dict:
    """The request was withdrawn."""
    row = _request(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.cancel(transition_id, reason=(reason or "Withdrawn").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def booked(transition_id: str, *, local_student_id: str, start_date: str | None = None,
           consent: bool | set[str] | None = None,
           accepted_by: str = "training provider", db_path: str | None = None) -> dict:
    """The learner is booked on a session: accept, approve the handover the
    sender released, admit and complete - concurrently, so the sender's
    programme stays open."""
    row = _request(transition_id, db_path=db_path)
    if row["status"] == "completed":
        return row
    if row["status"] not in ("offered", "accepted", "handover_approved", "admitted"):
        raise RequestError(f"The request is {row['status']} - it can't be booked")
    start = min(_clean_date(start_date, "The start date") or date.today().isoformat(),
                date.today().isoformat())
    if row["status"] in ("offered", "accepted"):
        local_id = route_support.source_local_id(row, db_path=db_path)
        if not local_id:
            raise RequestError("The request has no sending learner linked to it")
        released = released_handover(
            row["source_system"], local_id,
            {"course": row.get("application_reference") or "",
             "reason": row.get("reason") or "Training request"}, consent=consent)
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


def describe(outcome: dict[str, Any]) -> str:
    """One line for the sender's log."""
    course = outcome.get("course") or "the course"
    if outcome.get("kind") == "certificate":
        level = f" ({outcome['level']})" if outcome.get("level") else ""
        expires = f", valid to {outcome['expires_on']}" if outcome.get("expires_on") else ""
        return (f"Training provider: certificate {outcome.get('cert_no') or ''} issued for "
                f"{course}{level} on {outcome.get('issued_on') or ''}{expires}")
    return (f"Training provider: {course} - {outcome.get('outcome') or 'update'}"
            f" ({outcome.get('on') or date.today().isoformat()})")


def record_outcome(transition_id: str, outcome: dict[str, Any], *,
                   db_path: str | None = None) -> list[str]:
    """A certificate, fail or no-show on a booked request: logged for the
    sender and passed to its adapter's ``receive_training_result``.
    Returns lines for the person who saved."""
    row = _request(transition_id, db_path=db_path)
    note = describe(outcome)
    transitions.add_note(transition_id, note, step=OUTCOME_STEP, db_path=db_path)
    sender = SOURCE_LABELS.get(row["source_system"], row["source_system"])
    local_id = route_support.source_local_id(row, db_path=db_path)
    receiver = getattr(_adapter(row["source_system"]), "receive_training_result", None)
    if not (local_id and callable(receiver)):
        return [f"{sender} can see it on their request."]
    done = receiver(local_id, dict(outcome))
    return [f"{sender} has it: {done}" if done else f"{sender} can see it on their request."]


# ── Queues ───────────────────────────────────────────────────────────

def _all_into(*, db_path: str | None) -> list[dict]:
    rows = transitions.pending_transitions(DESTINATION, db_path=db_path)
    for status in ("completed", "cancelled"):
        rows += transitions.pending_transitions(DESTINATION, status=status,
                                                db_path=db_path)
    return rows


def outcomes_for(transition_id: str, *, db_path: str | None = None) -> list[dict]:
    """The training provider's outcome notes on a request, oldest first."""
    return [{"note": e.get("note") or "", "at": e.get("at") or e.get("created_at")}
            for e in transitions.list_transition_events(transition_id, db_path=db_path)
            if e.get("step") == OUTCOME_STEP]


def requests_from(source_system: str, *, include_closed: bool = True,
                  db_path: str | None = None) -> list[dict]:
    """A sender's requests, newest first, each with ``label``, ``learner``,
    ``course`` and ``latest`` (the newest outcome, if any)."""
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
        item["course"] = row.get("application_reference") or ""
        item["label"] = STATUS_LABELS.get(row["status"], row["status"])
        if row["status"] == "cancelled":
            item["label"] = ("Declined" if row.get("decision") == "rejected"
                             else "Withdrawn")
        notes = outcomes_for(row["transition_id"], db_path=db_path)
        item["latest"] = (notes[-1]["note"].removeprefix("Training provider: ")
                          if notes else "")
        if notes and "certificate" in notes[-1]["note"]:
            item["label"] = "Certificated"
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


__all__ = ["DESTINATION", "SOURCE_SYSTEMS", "SOURCE_LABELS", "LABEL", "PAYERS",
           "STATUS_LABELS", "OUTCOME_STEP", "RequestError", "released_handover", "request",
           "decline", "withdraw", "booked", "describe", "record_outcome", "outcomes_for",
           "requests_from"]
