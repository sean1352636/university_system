"""Primary / Secondary ↔ the SEND service, through the platform.

The SEND system (``systems/special_education``) is a SEND service - the
register, SEN support plans, the EHCP statutory process, provision and
high-needs funding - for pupils who stay at their own school. So the link
is a *case* shared alongside the school place, not a move:

* **School → SEND** (:func:`refer`): the school asks for SEND advice and
  support, or makes an EHC needs assessment request. The school's adapter
  exports what it holds, ``handover.*_TO_SPECIAL_EDUCATION`` decides what
  may cross (SEN, medical and support details only with the parent's
  consent; safeguarding only as a reference), and the SEND adapter puts the
  pupil on its register with a school request (and, for an assessment
  request, an EHCP at *Requested*). The transition runs straight through to
  completed with a *concurrent* enrolment: the pupil never leaves the
  school's roll.

* **SEND → school** (:func:`record_update`): the SEND service's EHCP
  decisions go to whichever school on the platform has the pupil on roll
  now (a Year 6 pupil who has moved up reaches the secondary): the
  assessment request, decision, plan issued (the school's SEN status
  becomes EHC plan), not issued, ceased (back to SEN support). Annual
  review outcomes and register changes are logged for the school without
  changing its record. Each update is a note on the school's request, so
  the school sees it on its board and in the step log.

* **Case closed** (:func:`close_case`): the SEND service archives the
  pupil - its platform enrolment ends; the school is told.

Both ends are reached only through the adapter registry. A school adapter
takes updates through an optional ``receive_send_update(local_id, update)``;
nothing here imports a system.
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

DESTINATION = "special_education"
SCHOOLS = frozenset({"primary", "secondary"})
SCHOOL_LABELS = {"primary": "Primary School", "secondary": "Secondary School"}
LABEL = "SEND service"

ADVICE = "SEND advice and support"
EHCNA = "EHC needs assessment request"
REQUESTS = (ADVICE, EHCNA)

#: The SEND service's EHCP stages (its EHCP Tracker), as the school reads them.
EHCP_STAGE_TEXT = {
    "Requested": "EHC needs assessment requested",
    "Assessing": "agreed to assess",
    "Refused to assess": "refused to assess",
    "Draft issued": "draft EHC plan issued",
    "Final issued": "EHC plan issued",
    "Not issued": "assessed - EHC plan not issued",
    "Ceased": "EHC plan ceased",
}

#: What the school sees for each step of its request.
STATUS_LABELS = {"expected": "Being sent", "applied": "Being sent",
                 "offered": "Being sent", "accepted": "Being sent",
                 "handover_approved": "Being sent", "admitted": "Being sent",
                 "completed": "Open case", "cancelled": "Withdrawn"}

UPDATE_STEP = "send_update"


class ReferralError(ValueError):
    """A request can't be made, or an update passed on, as things stand."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise ReferralError(str(exc)) from exc


def _check_school(system: str) -> None:
    if system not in SCHOOLS:
        raise ReferralError(f"{system!r} doesn't make requests to the SEND service")


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
    """The consent-filtered handover the school would release to SEND."""
    _check_school(school)
    exported = _adapter(school).export_handover(
        str(pupil_id), consent, destination_system=DESTINATION)
    record = dict(exported.record)
    record["request_details"] = dict(details)
    return handover.build_handover(
        school, DESTINATION, record, consent=consent,
        safeguarding_reference=safeguarding_reference)


# ── School → SEND ────────────────────────────────────────────────────

def refer(school: str, pupil_id: str, *, request: str, summary: str = "",
          tried: str = "", referrer: str = "",
          consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None,
          request_date: str | None = None,
          actor_user_id: int | None = None, db_path: str | None = None) -> dict:
    """Send a school's request to the SEND service. Returns the transition
    (completed: the case is open, the pupil stays on the school's roll).

    A request stuck part-way (the SEND service refused the details) carries
    on when sent again.
    """
    _check_school(school)
    if request not in REQUESTS:
        raise ReferralError("Choose what you are asking the SEND service for")
    when = _clean_date(request_date, "The request date") or date.today().isoformat()
    if when > date.today().isoformat():
        raise ReferralError("The request date can't be in the future")
    if request == EHCNA and not (summary or "").strip():
        raise ReferralError("Say why the pupil needs an EHC needs assessment")
    details = {"request": request, "request_date": when,
               "summary": (summary or "").strip(), "tried": (tried or "").strip(),
               "referred_by": SCHOOL_LABELS[school],
               "referrer": (referrer or "").strip(), "consent": bool(consent),
               "safeguarding_reference": bool(safeguarding_reference)}
    released = released_handover(school, pupil_id, details, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=school,
            student_id=str(pupil_id), db_path=db_path)
    except route_support.RouteError as exc:
        raise ReferralError(str(exc)) from exc
    if released.missing_required:
        raise ReferralError("The request is missing: " + route_support.describe_missing(
            school, DESTINATION, released.missing_required))
    problems = handover.validate_handover(school, DESTINATION, released.payload)
    if problems:
        raise ReferralError("; ".join(problems))
    ident = route_support.identity_of(released.payload)
    transition, _created = route_support.start(
        journey_id, source_system=school, destination_system=DESTINATION,
        student_id=str(pupil_id), reason=request, actor_user_id=actor_user_id,
        year_group=ident.get("year_group"), db_path=db_path)
    tid = transition["transition_id"]
    consent_ref = route_support.consent_reference(consent, prefix="parent-consent")
    if transition["status"] == "expected":
        transition = transitions.record_application(
            tid, application_reference=f"{school}:{pupil_id}",
            actor_user_id=actor_user_id, db_path=db_path)
    if transition["status"] == "applied":
        try:
            applicant = route_support.request_applicant(
                transition, released.payload, consent_reference=consent_ref,
                year_group=ident.get("year_group"))
        except Exception as exc:  # noqa: BLE001 - the SEND adapter's own message
            raise ReferralError(f"{exc} The request is saved; send it again once the "
                                "pupil's record is put right.") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            destination_enrolment_id=route_support.adopt_destination_enrolment(
                journey_id, DESTINATION, applicant.local_applicant_id, db_path=db_path),
            year_group=applicant.year_group, actor_user_id=actor_user_id,
            db_path=db_path)
    if transition["status"] == "offered":
        transition = transitions.accept_place(tid, accepted_by=LABEL, db_path=db_path)
    if transition["status"] == "accepted":
        transition = transitions.approve_handover(tid, released,
                                                  consent_reference=consent_ref,
                                                  db_path=db_path)
    if transition["status"] == "handover_approved":
        transition = transitions.admit(
            tid, local_student_id=_send_local_id(transition, db_path=db_path),
            year_group=ident.get("year_group"), start_date=when, db_path=db_path)
    if transition["status"] == "admitted":
        # The school place carries on: a case alongside it, not a move.
        transition = transitions.complete(
            tid, start_date=when, close_source=False, concurrent_enrolment=True,
            db_path=db_path)
    return transition


def _send_local_id(transition: dict, *, db_path: str | None) -> str:
    dest = enrolments.get_enrolment(transition.get("destination_enrolment_id") or "",
                                    db_path=db_path) or {}
    local = dest.get("local_student_id")
    if not local:
        raise ReferralError("The SEND service has no record of this pupil yet")
    return str(local)


def withdraw(transition_id: str, *, reason: str = "Request withdrawn",
             db_path: str | None = None) -> dict:
    """A request still being sent is withdrawn (an open case is closed by
    the SEND service instead)."""
    row = _request(transition_id, db_path=db_path)
    if row["status"] in ("completed", "cancelled"):
        return row
    return transitions.cancel(transition_id, reason=(reason or "Withdrawn").strip()[:500],
                              actor_user_id=None, db_path=db_path)


def _request(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None or row.get("destination_system") != DESTINATION \
            or row.get("source_system") not in SCHOOLS:
        raise ReferralError("Not a school request to the SEND service")
    return row


# ── SEND → school ────────────────────────────────────────────────────

def _journey_of(send_learner_id: str, journey_id: str | None, *,
                db_path: str | None) -> str | None:
    if journey_id:
        return identity_service.resolve_journey_id(journey_id, db_path=db_path)
    found = identity_service.find_by_student(DESTINATION, str(send_learner_id),
                                             db_path=db_path)
    return (found or {}).get("journey_id")


def schools_holding(journey_id: str, *, db_path: str | None = None
                    ) -> list[tuple[str, str]]:
    """``(system, local pupil id)`` for each school with the pupil on roll."""
    out = []
    for row in enrolments.list_enrolments(journey_id, include_closed=False,
                                          db_path=db_path):
        if row.get("system") in SCHOOLS and row.get("local_student_id"):
            out.append((row["system"], str(row["local_student_id"])))
    return out


def _latest_request(journey_id: str, school: str, *, db_path: str | None) -> dict | None:
    rows = [r for r in transitions.list_transitions(journey_id, db_path=db_path)
            if r.get("destination_system") == DESTINATION
            and r.get("source_system") == school and r.get("status") != "cancelled"]
    return rows[-1] if rows else None


def describe(update: dict[str, Any]) -> str:
    """One line for the school: what the SEND service decided (or, with
    ``by``, whoever sent the EHC decision - the local authority uses this
    too)."""
    kind = update.get("kind")
    by = update.get("by") or "SEND service"
    if kind == "ehcp":
        stage = update.get("stage") or ""
        when = (update.get("final_date") if stage == "Final issued" else
                update.get("cease_date") if stage == "Ceased" else
                update.get("draft_date") if stage == "Draft issued" else
                update.get("request_date") if stage == "Requested" else
                update.get("decision_date"))
        text = f"{by}: " + EHCP_STAGE_TEXT.get(stage, stage.lower() or "EHCP updated")
        return f"{text} ({when})" if when else text
    if kind == "annual_review":
        bits = [f"annual review held {update.get('meeting_date') or ''}".strip()]
        if update.get("recommendation"):
            bits.append(f"recommended: {str(update['recommendation']).lower()}")
        if update.get("outcome") and update["outcome"] != "Pending":
            bits.append(f"LA decided: {str(update['outcome']).lower()}")
        return f"{by}: " + ", ".join(bits)
    if kind == "register":
        return f"{by}: SEN status recorded as {update.get('sen_status')}"
    if kind == "closed":
        return f"{by}: case closed" + (f" - {update['reason']}"
                                             if update.get("reason") else "")
    return f"{by}: updated"


def record_update(send_learner_id: str, update: dict[str, Any], *,
                  journey_id: str | None = None,
                  db_path: str | None = None) -> list[str]:
    """Pass a SEND decision to the pupil's school(s). Returns lines saying
    what happened, one per school (empty if no school on the platform has
    the pupil on roll)."""
    journey_id = _journey_of(send_learner_id, journey_id, db_path=db_path)
    if not journey_id:
        return []
    text = describe(update)
    out = []
    for school, local_id in schools_holding(journey_id, db_path=db_path):
        receive = getattr(_adapter(school), "receive_send_update", None)
        result = None
        if callable(receive) and update.get("kind") == "ehcp":
            try:
                result = receive(local_id, dict(update))
            except Exception as exc:  # noqa: BLE001 - say so; the note still goes
                out.append(f"{SCHOOL_LABELS[school]} couldn't update its SEN record: "
                           f"{exc}")
        req = _latest_request(journey_id, school, db_path=db_path)
        if req is not None:
            transitions.add_note(req["transition_id"], text, step=UPDATE_STEP,
                                 db_path=db_path)
        if result:
            out.append(f"{SCHOOL_LABELS[school]}: {result}")
        elif req is not None:
            out.append(f"{SCHOOL_LABELS[school]} has been told.")
    return out


def close_case(send_learner_id: str, *, reason: str = "", end_date: str | None = None,
               journey_id: str | None = None, db_path: str | None = None) -> list[str]:
    """The SEND service closed the pupil's case (archived them)."""
    when = _clean_date(end_date, "The closing date") or date.today().isoformat()
    journey_id = _journey_of(send_learner_id, journey_id, db_path=db_path)
    if not journey_id:
        return []
    enrolments.end_local_enrolment(
        DESTINATION, str(send_learner_id), status="completed", end_date=when,
        reason=(reason or "SEND case closed").strip()[:500], db_path=db_path)
    return record_update(send_learner_id, {"kind": "closed", "reason": reason},
                         journey_id=journey_id, db_path=db_path)


def reopen_case(send_learner_id: str, *, journey_id: str | None = None,
                db_path: str | None = None) -> bool:
    """An archived pupil made active again: their SEND enrolment re-opens
    (a new one, so the closed one keeps its dates). True if re-opened."""
    journey_id = _journey_of(send_learner_id, journey_id, db_path=db_path)
    if not journey_id:
        return False
    if any(r.get("system") == DESTINATION for r in enrolments.list_enrolments(
            journey_id, include_closed=False, db_path=db_path)):
        return False
    enrolments.link_local_enrolment(journey_id=journey_id, system=DESTINATION,
                                    local_student_id=str(send_learner_id),
                                    start_date=date.today().isoformat(), db_path=db_path)
    return True


# ── The school's board ───────────────────────────────────────────────

def requests_from(school: str, *, db_path: str | None = None) -> list[dict]:
    """A school's requests to the SEND service, newest first, each with
    ``label`` (what the school sees), ``pupil``, ``latest`` (the SEND
    service's latest update) and ``latest_at``."""
    _check_school(school)
    rows = transitions.pending_transitions(DESTINATION, db_path=db_path)
    for status in ("completed", "cancelled"):
        rows += transitions.pending_transitions(DESTINATION, status=status,
                                                db_path=db_path)
    out = []
    for row in rows:
        if row.get("source_system") != school:
            continue
        j = identity_service.get(row["journey_id"], db_path=db_path) or {}
        item = dict(row)
        item["pupil"] = " ".join(x for x in (j.get("legal_first_name"),
                                             j.get("legal_last_name")) if x)
        item["school_pupil_id"] = route_support.source_local_id(row, db_path=db_path)
        item["label"] = STATUS_LABELS.get(row["status"], row["status"])
        if row["status"] == "completed":
            dest = enrolments.get_enrolment(row.get("destination_enrolment_id") or "",
                                            db_path=db_path) or {}
            if dest and dest.get("status") not in enrolments.OPEN_STATUSES:
                item["label"] = "Case closed"
        notes = [e for e in transitions.list_transition_events(
            row["transition_id"], db_path=db_path) if e.get("step") == UPDATE_STEP]
        item["latest"] = notes[-1]["note"].removeprefix("SEND service: ") if notes else ""
        item["latest_at"] = (notes[-1].get("at") or "")[:10] if notes else ""
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


def updates_for(transition_id: str, *, db_path: str | None = None) -> list[dict]:
    """The SEND service's updates on one request, oldest first."""
    return [e for e in transitions.list_transition_events(transition_id, db_path=db_path)
            if e.get("step") == UPDATE_STEP]


__all__ = ["DESTINATION", "SCHOOLS", "SCHOOL_LABELS", "LABEL", "ADVICE", "EHCNA",
           "REQUESTS", "EHCP_STAGE_TEXT", "STATUS_LABELS", "ReferralError",
           "released_handover", "refer", "withdraw", "schools_holding", "describe",
           "record_update", "close_case", "reopen_case", "requests_from", "updates_for"]
