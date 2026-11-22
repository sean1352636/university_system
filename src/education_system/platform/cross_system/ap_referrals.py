"""Primary / Secondary ↔ Alternative Provision, through the platform.

The integration layer's half of four links on the platform diagram:

* **Primary → AP** and **Secondary → AP**: a school refers a pupil. The
  school's adapter exports what it holds, ``handover.*_TO_ALTERNATIVE_
  PROVISION`` decides what may cross (behaviour, exclusions, SEN and medical
  only with the parent's consent; safeguarding only as a reference), and
  the AP's adapter creates a referred pupil and an open referral. The AP
  decides there:

  - **accepted** → :func:`accept` (steps 4-5: accepted, handover approved);
  - **declined / withdrawn** → :func:`decline` / :func:`withdraw`;
  - **first placement starts** → :func:`place` (steps 6-7). With *dual
    registration* the pupil stays on the school's roll (a concurrent
    enrolment); with *sole registration* (after a permanent exclusion) the
    school's record is closed as a leaver.

* **AP → Primary** and **AP → Secondary**: the pupil leaves the AP
  (:func:`end_placement`):

  - back to the home school while still dual registered: nothing to admit,
    the AP enrolment is closed and the journey points at the school again;
  - to a primary school after sole registration: the whole move in one
    call (``route_support.transfer``) - the primary adapter creates the
    pupil and puts them on roll;
  - to a secondary school after sole registration: the referral is handed
    over and lands in the school's incoming-pupils queue, where admissions
    match or create the pupil (as they do for Year 6 → 7);
  - anywhere else: the AP enrolment is closed.

Both ends are reached only through the adapter registry; nothing here
imports a system, and no system imports another.
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
from education_system.platform.cross_system.adapters.base import AdapterError

DESTINATION = "alternative_provision"
SCHOOLS = frozenset({"primary", "secondary"})
SCHOOL_LABELS = {"primary": "Primary School", "secondary": "Secondary School"}
LABEL = "Alternative Provision"

#: Referral reasons - the same list as the AP system's referral form.
REASONS = ("Permanent exclusion", "Suspension (sixth-day provision)",
           "At risk of permanent exclusion", "Health needs (unable to attend school)",
           "Managed move", "No school place", "Other")
EXCLUSION_REASONS = frozenset(REASONS[:2])
DUAL, SOLE = "dual", "sole"
REGISTRATIONS = {DUAL: "Dual registration (stays on the school's roll)",
                 SOLE: "Sole registration (comes off the school's roll)"}

#: How a placement ends (:func:`end_placement`).
HOME_SCHOOL, LEFT = "home_school", "left"
ENDINGS = {HOME_SCHOOL: "Back to the home school (dual registration)",
           "primary": "To a primary school on this platform",
           "secondary": "To a secondary school on this platform",
           LEFT: "Elsewhere (not on this platform)"}

#: What the school sees for each step of its referral.
STATUS_LABELS = {"expected": "Being sent", "applied": "Being sent",
                 "offered": "With the AP (to decide)", "accepted": "Accepted",
                 "handover_approved": "Accepted - placement to start",
                 "admitted": "Placed", "completed": "Placed",
                 "cancelled": "Declined / withdrawn"}


class ReferralError(ValueError):
    """A referral can't be made or moved on in its current state."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise ReferralError(str(exc)) from exc


def _check_school(system: str) -> None:
    if system not in SCHOOLS:
        raise ReferralError(f"{system!r} doesn't refer pupils to alternative provision")


def _clean_date(value: Any, what: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        raise ReferralError(f"{what} isn't a date (YYYY-MM-DD)") from None


def released_handover(school: str, pupil_id: str, details: dict[str, Any], *,
                      consent: bool | set[str] | None,
                      safeguarding_reference: str | None = None):
    """The consent-filtered handover the school would release to the AP."""
    _check_school(school)
    exported = _adapter(school).export_handover(
        str(pupil_id), consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["referral_details"] = dict(details)
    return handover.build_handover(
        school, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


# ── School → AP ──────────────────────────────────────────────────────

def refer(school: str, pupil_id: str, *, reason: str, registration: str = DUAL,
          excluded_from: str | None = None, summary: str = "",
          referrer: str = "", consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None,
          actor_user_id: int | None = None, db_path: str | None = None) -> dict:
    """Refer a school's pupil to the AP. Returns the transition (offered).

    Idempotent: an open referral the AP already holds is returned as it is;
    one the AP refused to record is retried.
    """
    _check_school(school)
    if reason not in REASONS:
        raise ReferralError("Choose the reason for the referral")
    if registration not in REGISTRATIONS:
        raise ReferralError("Choose dual or sole registration")
    excluded_from = _clean_date(excluded_from, "The exclusion start")
    if reason in EXCLUSION_REASONS and not excluded_from:
        raise ReferralError("Give the first day of the exclusion: provision has to start "
                            "by the sixth school day")
    if reason == REASONS[0] and registration != SOLE:
        raise ReferralError("A permanently excluded pupil comes off the school's roll: "
                            "use sole registration")
    details = {"reason": reason, "registration": registration,
               "excluded_from": excluded_from, "summary": (summary or "").strip(),
               "referred_by": SCHOOL_LABELS[school],
               "referrer": (referrer or "").strip(),
               "consent": bool(consent),
               "safeguarding_reference": bool(safeguarding_reference)}
    released = released_handover(school, pupil_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=school,
            student_id=str(pupil_id), db_path=db_path)
    except route_support.RouteError as exc:
        raise ReferralError(str(exc)) from exc
    existing = route_support.open_transition(journey_id, school, DESTINATION,
                                             db_path=db_path)
    # An open referral the AP already holds is returned as it is. One stuck
    # before the AP recorded it (the AP refused the details) carries on, so a
    # retry after fixing the record reaches the AP instead of stopping here.
    if existing is not None and existing["status"] not in ("expected", "applied"):
        return existing
    if released.missing_required:
        raise ReferralError("The referral is missing: " + route_support.describe_missing(
            school, DESTINATION, released.missing_required))
    problems = handover.validate_handover(school, DESTINATION, released.payload)
    if problems:
        raise ReferralError("; ".join(problems))
    ident = route_support.identity_of(released.payload)
    transition, _created = route_support.start(
        journey_id, source_system=school, destination_system=DESTINATION,
        student_id=str(pupil_id), reason=reason, actor_user_id=actor_user_id,
        year_group=ident.get("year_group"), db_path=db_path)
    tid = transition["transition_id"]
    if transition["status"] == "expected":
        transition = transitions.record_application(
            tid, application_reference=f"{school}:{pupil_id}",
            actor_user_id=actor_user_id, db_path=db_path)
    if transition["status"] == "applied":
        consent_ref = route_support.consent_reference(consent, prefix="parent-consent")
        try:
            applicant = route_support.request_applicant(
                transition, released.payload, consent_reference=consent_ref,
                year_group=ident.get("year_group"))
        except Exception as exc:  # noqa: BLE001 - the AP adapter's own message
            raise ReferralError(f"{exc} The referral is saved; send it again once the "
                                "pupil's record is put right.") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            destination_enrolment_id=route_support.adopt_destination_enrolment(
                journey_id, DESTINATION, applicant.local_applicant_id, db_path=db_path),
            year_group=applicant.year_group, actor_user_id=actor_user_id,
            db_path=db_path)
    return transition


def _referral(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SCHOOLS:
        raise ReferralError("Not a school referral to alternative provision")
    return row


def accept(transition_id: str, *, accepted_by: str = "alternative provision",
           consent: bool | set[str] | None = None,
           safeguarding_reference: str | None = None,
           db_path: str | None = None) -> dict:
    """The AP accepted the referral: accept, and approve the handover the
    school released (fresh from the school, with the consent it gave)."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] in ("handover_approved", "admitted", "completed"):
        return row
    if row["status"] not in ("offered", "accepted"):
        raise ReferralError(f"The referral is {row['status']} - it can't be accepted")
    local_id = route_support.source_local_id(row, db_path=db_path)
    if not local_id:
        raise ReferralError("The referral has no school pupil linked to it")
    released = released_handover(
        row["source_system"], local_id, {"reason": row.get("reason") or "Referral"},
        consent=consent, safeguarding_reference=safeguarding_reference)
    if row["status"] == "offered":
        transitions.accept_place(transition_id, accepted_by=accepted_by, db_path=db_path)
    return transitions.approve_handover(
        transition_id, released,
        consent_reference=route_support.consent_reference(consent, prefix="parent-consent"),
        db_path=db_path)


def decline(transition_id: str, *, reason: str, db_path: str | None = None) -> dict:
    """The AP declined the referral; the school sees the reason."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.reject(transition_id, reason=(reason or "Declined").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def withdraw(transition_id: str, *, reason: str = "Referral withdrawn",
             db_path: str | None = None) -> dict:
    """The referral was withdrawn (by the school, or recorded at the AP)."""
    row = _referral(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.cancel(transition_id, reason=(reason or "Withdrawn").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def place(transition_id: str, *, local_student_id: str, registration: str = DUAL,
          start_date: str | None = None, year_group: str | None = None,
          db_path: str | None = None) -> dict:
    """The first placement started: the pupil is admitted at the AP.

    Dual registration leaves the school's record open (a concurrent
    enrolment). Sole registration closes it: the school records a leaver.
    """
    row = _referral(transition_id, db_path=db_path)
    if row["status"] == "completed":
        return row
    if row["status"] not in ("handover_approved", "admitted"):
        raise ReferralError("Accept the referral before the placement starts")
    start = _clean_date(start_date, "The start date") or date.today().isoformat()
    sole = registration == SOLE
    if row["status"] == "handover_approved":
        row = transitions.admit(transition_id, local_student_id=str(local_student_id),
                                year_group=year_group, start_date=start, db_path=db_path)
    exclusion = row.get("reason") == REASONS[0]
    why = ("Permanently excluded - placed in alternative provision" if exclusion
           else "Moved to alternative provision (sole registration)")
    if sole:
        # The school records the leaver first: if it refuses (a leaving date
        # before the pupil's admission, say), the referral stays admitted and
        # saving the placement again retries, instead of the platform saying
        # "placed" while the pupil is still on the school's roll.
        try:
            route_support.close_source(row, why, db_path=db_path, end_date=start,
                                       destination_school=LABEL, exclusion=exclusion)
        except Exception as exc:  # noqa: BLE001 - the school adapter's own message
            raise ReferralError(f"{SCHOOL_LABELS.get(row['source_system'], 'The school')} "
                                f"couldn't record the pupil as a leaver: {exc}") from exc
    return transitions.complete(
        transition_id, start_date=start, close_source=sole,
        source_exit_reason=why if sole else None,
        concurrent_enrolment=not sole, db_path=db_path)


# ── AP → school ──────────────────────────────────────────────────────

def home_school(journey_id: str, *, db_path: str | None = None) -> dict | None:
    """The school that made the pupil's latest completed referral:
    ``{"system", "local_student_id", "transition_id", "registration"}``."""
    for row in reversed(transitions.list_transitions(journey_id, db_path=db_path)):
        if row.get("destination_system") == DESTINATION and \
                row.get("source_system") in SCHOOLS and row.get("status") == "completed":
            src = enrolments.get_enrolment(row.get("source_enrolment_id") or "",
                                           db_path=db_path) or {}
            return {"system": row["source_system"],
                    "local_student_id": src.get("local_student_id"),
                    "transition_id": row["transition_id"],
                    "still_on_roll": src.get("status") in enrolments.OPEN_STATUSES}
    return None


def end_placement(ap_pupil_id: str, *, ending: str, journey_id: str | None = None,
                  reason: str = "", end_date: str | None = None,
                  reintegration_plan: dict[str, Any] | None = None,
                  consent: bool | set[str] | None = None,
                  safeguarding_reference: str | None = None,
                  db_path: str | None = None) -> dict[str, Any]:
    """The pupil left the AP. Returns what happened: ``{"ending", "note",
    "transition_id"}``."""
    if ending not in ENDINGS:
        raise ReferralError("Say where the pupil is going")
    when = _clean_date(end_date, "The leaving date") or date.today().isoformat()
    why = (reason or "").strip()
    if not journey_id:
        found = identity_service.find_by_student(DESTINATION, str(ap_pupil_id),
                                                 db_path=db_path)
        journey_id = (found or {}).get("journey_id")
    if not journey_id:
        raise ReferralError("This pupil isn't linked to the platform (they weren't "
                            "referred by a school on it)")

    if ending in (HOME_SCHOOL, LEFT):
        enrolments.end_local_enrolment(
            DESTINATION, str(ap_pupil_id), status="completed" if ending == HOME_SCHOOL
            else "withdrawn", end_date=when,
            reason=why or ("Reintegrated to the home school" if ending == HOME_SCHOOL
                           else "Left alternative provision"), db_path=db_path)
        if ending == LEFT:
            return {"ending": ending, "note": "the platform's AP record is closed",
                    "transition_id": None}
        home = home_school(journey_id, db_path=db_path)
        if home is None or not home["still_on_roll"]:
            raise ReferralError("The pupil isn't on a home school's roll here (sole "
                                "registration) - choose the school they are going to")
        identity_service.record_transition(
            journey_id, from_system=DESTINATION, to_system=home["system"],
            reason=why or "Reintegrated to the home school", db_path=db_path)
        return {"ending": ending, "transition_id": None,
                "note": f"back on the {SCHOOL_LABELS[home['system']]} record only"}

    school = ending
    plan = dict(reintegration_plan or {})
    plan.setdefault("full_return", when)
    if school == "primary":
        ident = route_support.identity_of(_adapter(DESTINATION).export_handover(
            str(ap_pupil_id), None, destination_system=school).record)
        if not ident.get("year_group"):
            raise ReferralError("The pupil isn't of primary school age - choose another "
                                "school")
        try:
            outcome = route_support.transfer(
                source_system=DESTINATION, destination_system="primary",
                student_id=str(ap_pupil_id), reason=why or "Reintegrated to primary school",
                consent=consent, safeguarding_reference=safeguarding_reference,
                extra_record={"reintegration_plan": plan}, start_date=when,
                year_group=str(ident["year_group"]),
                accepted_by="alternative provision", db_path=db_path)
        except (route_support.RouteError, AdapterError) as exc:
            raise ReferralError(str(exc)) from exc
        note = "on roll at the primary school"
        if outcome.warnings:
            note += " (" + "; ".join(outcome.warnings) + ")"
        return {"ending": ending, "note": note,
                "transition_id": outcome.transition["transition_id"]}

    # Secondary: handed over; the school's admissions match or create the pupil.
    exported = _adapter(DESTINATION).export_handover(
        str(ap_pupil_id), consent, destination_system=school)
    record = dict(exported.record)
    record["reintegration_plan"] = plan
    released = handover.build_handover(DESTINATION, school, record, consent=consent,
                                       safeguarding_reference=safeguarding_reference)
    if released.missing_required:
        raise ReferralError("The handover is missing: " + route_support.describe_missing(
            DESTINATION, school, released.missing_required))
    transition, _created = route_support.start(
        journey_id, source_system=DESTINATION, destination_system=school,
        student_id=str(ap_pupil_id), reason=why or "Reintegration from alternative "
        "provision", db_path=db_path)
    tid = transition["transition_id"]
    if transition["status"] == "expected":
        transition = transitions.record_application(
            tid, application_reference=f"{DESTINATION}:{ap_pupil_id}", db_path=db_path)
    if transition["status"] == "applied":
        applicant = route_support.request_applicant(transition, released.payload)
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            year_group=applicant.year_group, db_path=db_path)
    if transition["status"] == "offered":
        transition = transitions.accept_place(tid, accepted_by="alternative provision",
                                              db_path=db_path)
    if transition["status"] == "accepted":
        transition = transitions.approve_handover(
            tid, released,
            consent_reference=route_support.consent_reference(consent,
                                                              prefix="parent-consent"),
            db_path=db_path)
    return {"ending": ending, "transition_id": tid,
            "note": "handed over: the secondary school's admissions take it from "
                    "Incoming pupils"}


# ── Queues ───────────────────────────────────────────────────────────

def _all_into(destination: str, *, db_path: str | None) -> list[dict]:
    rows = transitions.pending_transitions(destination, db_path=db_path)
    for status in ("completed", "cancelled"):
        rows += transitions.pending_transitions(destination, status=status,
                                                db_path=db_path)
    return rows


def referrals_from(school: str, *, include_closed: bool = True,
                   db_path: str | None = None) -> list[dict]:
    """A school's referrals to the AP, newest first, each with ``label``
    (what the school sees), ``pupil`` and ``placement_ended``."""
    _check_school(school)
    out = []
    for row in _all_into(DESTINATION, db_path=db_path):
        if row.get("source_system") != school:
            continue
        if not include_closed and row["status"] in ("completed", "cancelled"):
            continue
        j = identity_service.get(row["journey_id"], db_path=db_path) or {}
        item = dict(row)
        item["pupil"] = " ".join(x for x in (j.get("legal_first_name"),
                                             j.get("legal_last_name")) if x)
        item["school_pupil_id"] = route_support.source_local_id(row, db_path=db_path)
        item["label"] = STATUS_LABELS.get(row["status"], row["status"])
        ended = None
        if row["status"] == "completed":
            dest = enrolments.get_enrolment(row.get("destination_enrolment_id") or "",
                                            db_path=db_path) or {}
            if dest and dest.get("status") not in enrolments.OPEN_STATUSES:
                ended = dest.get("end_date") or ""
                item["label"] = "Left the AP"
        if row["status"] == "cancelled":
            item["label"] = ("Declined" if row.get("decision") == "rejected"
                             else "Withdrawn")
        item["placement_ended"] = ended
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


__all__ = ["DESTINATION", "SCHOOLS", "SCHOOL_LABELS", "REASONS", "EXCLUSION_REASONS",
           "DUAL", "SOLE", "REGISTRATIONS", "HOME_SCHOOL", "LEFT", "ENDINGS",
           "STATUS_LABELS", "ReferralError", "released_handover", "refer", "accept",
           "decline", "withdraw", "place", "home_school", "end_placement",
           "referrals_from"]
