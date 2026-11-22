"""Primary / Secondary ↔ the Local Authority, through the platform.

The Local Authority Education system (``systems/local_authority``) is the
authority's record of a child: admissions, attendance and welfare,
exclusions and SEND. It sits *beside* the school, so the links are of two
kinds.

**School → LA: notifications** (:func:`notify`). The school tells the
authority what the law says it must, or asks for what only the authority
can do:

* an attendance referral (persistent or severe absence after the school's
  own support) - an attendance case;
* a suspension or a permanent exclusion - the authority's exclusion record
  (the sixth-day provision and the review dates are worked out there);
* a child missing education (taken off roll with no known destination, or
  10+ school days of unexplained absence) - a CME case;
* a parent's notice of elective home education - an EHE record;
* an EHC needs assessment request - an EHC needs assessment.

The school's adapter exports what it holds; ``handover.*_TO_LOCAL_AUTHORITY``
decides what may cross (SEN, medical and exclusion history only with the
parent's consent; safeguarding only as a reference). The authority's
adapter finds or adds the child and records the notification. The
transition runs straight through to completed with a *concurrent*
enrolment, and the school stays the child's current system: the child never
leaves the school's roll because the authority knows about them.

**LA → school: what the authority decided** (:func:`record_update`). The
authority's EHC decisions go onto the school's SEN record (the same
``receive_send_update`` hook the SEND service uses, labelled as the local
authority); attendance stages and penalty notices, exclusion reviews, CME
and EHE outcomes are notes on the school's notification, so the school sees
them on its board.

**LA → school: school places** (:func:`place`). An accepted offer (or a fair
access allocation) at a school on this platform hands the child to that
school: the primary adds an accepted admissions application (enrolling it
puts the child on roll and tells the platform, :func:`admitted`); the
secondary lists the child under Incoming pupils, where admissions match or
create the record. A Year 7 place for a child already coming from the
platform's primary is a note on that transfer, not a second one.

Both ends are reached only through the adapter registry; nothing here
imports a system.
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

LA = "local_authority"
DESTINATION = LA
SCHOOLS = frozenset({"primary", "secondary"})
SCHOOL_LABELS = {"primary": "Primary School", "secondary": "Secondary School"}
LABEL = "Local authority"

ATTENDANCE = "Attendance referral"
SUSPENSION = "Suspension"
PERMANENT_EXCLUSION = "Permanent exclusion"
CME = "Child missing education"
EHE = "Elective home education"
EHCNA = "EHC needs assessment request"
KINDS = (ATTENDANCE, SUSPENSION, PERMANENT_EXCLUSION, CME, EHE, EHCNA)
EXCLUSIONS = frozenset({SUSPENSION, PERMANENT_EXCLUSION})

#: Why a child is missing education (the school's two duties to tell the LA).
CME_REASONS = ("Taken off roll - destination not known",
               "Unexplained absence of 10 school days or more")
#: The DfE exclusion reasons - the same list as the authority's exclusion form.
EXCLUSION_REASONS = (
    "Physical assault against a pupil", "Physical assault against an adult",
    "Verbal abuse or threatening behaviour against a pupil",
    "Verbal abuse or threatening behaviour against an adult",
    "Use or threat of use of an offensive weapon or prohibited item", "Bullying",
    "Racist abuse", "Abuse against sexual orientation or gender identity",
    "Abuse relating to disability",
    "Inappropriate use of social media or online technology", "Damage", "Theft",
    "Drug and alcohol related", "Sexual misconduct",
    "Persistent or general disruptive behaviour", "Other")

#: What each notification asks for: ``(key, label, input, choices)`` with
#: input ``line`` / ``text`` / ``choice`` / ``date`` (the boards build their
#: forms from this; :func:`check_details` is the rule).
NOTICE_FIELDS: dict[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]] = {
    ATTENDANCE: (("attendance_pct", "Attendance this year (%)", "line", ()),
                 ("sessions_missed", "Unauthorised sessions (last 10 weeks)", "line", ()),
                 ("support_tried", "Support the school has put in place", "text", ())),
    SUSPENSION: (("start_date", "First day (YYYY-MM-DD)", "date", ()),
                 ("days", "Length in days (halves allowed)", "line", ()),
                 ("reason", "Reason", "choice", EXCLUSION_REASONS),
                 ("background", "What happened", "text", ())),
    PERMANENT_EXCLUSION: (("start_date", "First day (YYYY-MM-DD)", "date", ()),
                          ("reason", "Reason", "choice", EXCLUSION_REASONS),
                          ("background", "What happened", "text", ())),
    CME: (("reason", "Why", "choice", CME_REASONS),
          ("last_seen", "Last day seen (YYYY-MM-DD)", "date", ()),
          ("enquiries", "Enquiries the school has made", "text", ())),
    EHE: (("notice_date", "Date of the parent's written notice (YYYY-MM-DD)", "date", ()),
          ("background", "Anything the authority should know", "text", ())),
    EHCNA: (("summary", "Why the pupil needs an assessment", "text", ()),
            ("tried", "What the school has tried (graduated approach)", "text", ())),
}

#: The authority's EHC stages, in the SEND service's vocabulary (the
#: schools' ``receive_send_update`` reads it).
EHCP_STAGE_TEXT = {
    "Requested": "EHC needs assessment requested",
    "Assessing": "agreed to assess",
    "Refused to assess": "refused to assess",
    "Draft issued": "draft EHC plan issued",
    "Final issued": "EHC plan issued",
    "Not issued": "assessed - EHC plan not issued",
    "Ceased": "EHC plan ceased",
}

#: What the school sees for each step of a notification.
NOTICE_LABELS = {"expected": "Being sent", "applied": "Being sent", "offered": "Being sent",
                 "accepted": "Being sent", "handover_approved": "Being sent",
                 "admitted": "Being sent", "completed": "With the LA",
                 "cancelled": "Withdrawn"}
#: ... and for a school place from the authority.
PLACE_LABELS = {"expected": "Being sent", "applied": "Being sent", "offered": "Being sent",
                "accepted": "Being sent", "handover_approved": "Place allocated - to admit",
                "admitted": "Admitted", "completed": "On roll", "cancelled": "Withdrawn"}

UPDATE_STEP = "la_update"


class LinkError(ValueError):
    """A notification, update or place can't go through as things stand."""


def _adapter(system: str):
    try:
        return route_support.adapter_for(system)
    except AdapterError as exc:
        raise LinkError(str(exc)) from exc


def _check_school(system: str) -> None:
    if system not in SCHOOLS:
        raise LinkError(f"{system!r} isn't a school linked to the local authority")


def _clean_date(value: Any, what: str, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise LinkError(f"Give {what.lower()}")
        return None
    try:
        out = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise LinkError(f"{what} isn't a date (YYYY-MM-DD)") from None
    return out.isoformat()


def _not_future(when: str | None, what: str) -> None:
    if when and when > date.today().isoformat():
        raise LinkError(f"{what} can't be in the future")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _keep_current(journey_id: str, system: str, local_id: str, *,
                  db_path: str | None) -> None:
    """Completing a transition makes its destination the journey's current
    system; the authority isn't where the child is taught, so point it back."""
    try:
        identity_service.link_system(journey_id, system, student_id=str(local_id),
                                     set_current=True, db_path=db_path)
    except Exception:  # noqa: BLE001 - only the pointer; enrolments are right
        pass


# ── School → LA: notifications ──────────────────────────────────────

def check_details(kind: str, details: dict[str, Any]) -> dict[str, Any]:
    """The notification's details, checked and tidied (raises LinkError)."""
    if kind not in KINDS:
        raise LinkError("Choose what you are telling the local authority")
    d = {k: (_text(v) if isinstance(v, str) else v) for k, v in details.items()}
    if kind == ATTENDANCE:
        try:
            pct = float(d.get("attendance_pct"))
        except (TypeError, ValueError):
            raise LinkError("Give the pupil's attendance as a percentage") from None
        if not 0 <= pct <= 100:
            raise LinkError("Attendance is a percentage, 0-100")
        d["attendance_pct"] = round(pct, 1)
        if d.get("sessions_missed") not in (None, ""):
            try:
                d["sessions_missed"] = int(d["sessions_missed"])
            except (TypeError, ValueError):
                raise LinkError("Unauthorised sessions is a whole number") from None
            if d["sessions_missed"] < 0:
                raise LinkError("Unauthorised sessions can't be negative")
        if not d.get("support_tried"):
            raise LinkError("Say what support the school has already put in place")
    elif kind in EXCLUSIONS:
        d["start_date"] = _clean_date(d.get("start_date"), "The first day", required=True)
        if d.get("reason") not in EXCLUSION_REASONS:
            raise LinkError("Choose the reason for the exclusion")
        if kind == SUSPENSION:
            try:
                days = float(d.get("days"))
            except (TypeError, ValueError):
                raise LinkError("Give the length of the suspension in days") from None
            if days <= 0 or days * 2 != int(days * 2):
                raise LinkError("A suspension is a number of days, in halves (e.g. 1.5)")
            d["days"] = days
        else:
            d.pop("days", None)
    elif kind == CME:
        if d.get("reason") not in CME_REASONS:
            raise LinkError("Say why the pupil is missing education")
        d["last_seen"] = _clean_date(d.get("last_seen"), "The last day seen")
        _not_future(d["last_seen"], "The last day seen")
        if not d.get("enquiries"):
            raise LinkError("Record the enquiries the school has made (calls, home visit, "
                            "contacts, other schools)")
    elif kind == EHE:
        d["notice_date"] = _clean_date(d.get("notice_date"), "The date of the parent's notice",
                                       required=True)
        _not_future(d["notice_date"], "The parent's notice")
    elif kind == EHCNA:
        if not d.get("summary"):
            raise LinkError("Say why the pupil needs an EHC needs assessment")
    return d


def released_handover(school: str, pupil_id: str, details: dict[str, Any], *,
                      consent: bool | set[str] | None,
                      safeguarding_reference: str | None = None):
    """The consent-filtered handover the school would release to the LA."""
    _check_school(school)
    exported = _adapter(school).export_handover(str(pupil_id), consent,
                                                destination_system=LA)
    record = dict(exported.record)
    record["notification_details"] = dict(details)
    return handover.build_handover(school, LA, record, consent=consent,
                                   safeguarding_reference=safeguarding_reference)


def notify(school: str, pupil_id: str, *, kind: str, details: dict[str, Any] | None = None,
           referrer: str = "", consent: bool | set[str] | None = None,
           safeguarding_reference: str | None = None,
           actor_user_id: int | None = None, db_path: str | None = None) -> dict:
    """Send a school's notification to the local authority. Returns the
    transition (completed: the authority has it; the pupil stays on roll).
    One stuck part-way (the authority refused the details) carries on when
    sent again."""
    _check_school(school)
    d = check_details(kind, dict(details or {}))
    d.update({"kind": kind, "notified_on": date.today().isoformat(),
              "school": SCHOOL_LABELS[school], "referrer": _text(referrer),
              "consent": bool(consent),
              "safeguarding_reference": bool(safeguarding_reference)})
    released = released_handover(school, pupil_id, d, consent=consent,
                                 safeguarding_reference=safeguarding_reference)
    try:
        journey_id = route_support.journey_for(
            route_support.identity_of(released.payload), system=school,
            student_id=str(pupil_id), db_path=db_path)
    except route_support.RouteError as exc:
        raise LinkError(str(exc)) from exc
    if released.missing_required:
        raise LinkError("The notification is missing: " + route_support.describe_missing(
            school, LA, released.missing_required))
    problems = handover.validate_handover(school, LA, released.payload)
    if problems:
        raise LinkError("; ".join(problems))
    ident = route_support.identity_of(released.payload)
    transition, _created = route_support.start(
        journey_id, source_system=school, destination_system=LA,
        student_id=str(pupil_id), reason=kind, actor_user_id=actor_user_id,
        year_group=ident.get("year_group"), db_path=db_path)
    tid = transition["transition_id"]
    if transition.get("reason") != kind and transition["status"] in ("expected", "applied"):
        # A different notification left part-way: withdraw it, start this one.
        transitions.cancel(tid, reason="Replaced by a new notification",
                           actor_user_id=actor_user_id, db_path=db_path)
        transition, _created = route_support.start(
            journey_id, source_system=school, destination_system=LA,
            student_id=str(pupil_id), reason=kind, actor_user_id=actor_user_id,
            year_group=ident.get("year_group"), db_path=db_path)
        tid = transition["transition_id"]
    consent_ref = route_support.consent_reference(consent, prefix="parent-consent")
    if transition["status"] == "expected":
        transition = transitions.record_application(
            tid, application_reference=f"{school}:{pupil_id}:{kind}",
            actor_user_id=actor_user_id, db_path=db_path)
    if transition["status"] == "applied":
        try:
            applicant = route_support.request_applicant(
                transition, released.payload, consent_reference=consent_ref,
                year_group=ident.get("year_group"))
        except Exception as exc:  # noqa: BLE001 - the authority's own message
            raise LinkError(f"{exc} The notification is saved; send it again once the "
                            "details are put right.") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            destination_enrolment_id=route_support.adopt_destination_enrolment(
                journey_id, LA, applicant.local_applicant_id, db_path=db_path),
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
            tid, local_student_id=_la_local_id(transition, db_path=db_path),
            year_group=ident.get("year_group"), start_date=d["notified_on"],
            db_path=db_path)
    if transition["status"] == "admitted":
        transition = transitions.complete(
            tid, start_date=d["notified_on"], close_source=False,
            concurrent_enrolment=True, db_path=db_path)
        _keep_current(journey_id, school, str(pupil_id), db_path=db_path)
    return transition


def _la_local_id(transition: dict, *, db_path: str | None) -> str:
    dest = enrolments.get_enrolment(transition.get("destination_enrolment_id") or "",
                                    db_path=db_path) or {}
    local = dest.get("local_student_id")
    if not local:
        raise LinkError("The local authority has no record of this child yet")
    return str(local)


def _transition(transition_id: str, *, db_path: str | None) -> dict:
    row = transitions.get_transition(transition_id, db_path=db_path)
    if row is None:
        raise LinkError("No such notification or place")
    return row


# ── LA → school: what the authority decided ─────────────────────────

def _journey_of(la_child_id: str, journey_id: str | None, *,
                db_path: str | None) -> str | None:
    if journey_id:
        return identity_service.resolve_journey_id(journey_id, db_path=db_path)
    found = identity_service.find_by_student(LA, str(la_child_id), db_path=db_path)
    return (found or {}).get("journey_id")


def schools_holding(journey_id: str, *, db_path: str | None = None
                    ) -> list[tuple[str, str]]:
    """``(system, local pupil id)`` for each school with the child on roll."""
    out = []
    for row in enrolments.list_enrolments(journey_id, include_closed=False,
                                          db_path=db_path):
        if row.get("system") in SCHOOLS and row.get("local_student_id"):
            out.append((row["system"], str(row["local_student_id"])))
    return out


def _notifications(journey_id: str, school: str, *, db_path: str | None) -> list[dict]:
    return [t for t in transitions.list_transitions(journey_id, db_path=db_path)
            if t.get("destination_system") == LA and t.get("source_system") == school
            and t.get("status") != "cancelled"]


def _note_target(journey_id: str, school: str, update: dict[str, Any], *,
                 db_path: str | None) -> dict | None:
    """The notification an update answers: the one it names, else the
    latest of the same kind from that school, else the latest of any."""
    rows = _notifications(journey_id, school, db_path=db_path)
    tid = update.get("transition_id")
    if tid:
        named = [t for t in rows if t["transition_id"] == tid]
        if named:
            return named[0]
    kinds = {"attendance": (ATTENDANCE,), "penalty_notice": (ATTENDANCE,),
             "exclusion": tuple(EXCLUSIONS), "cme": (CME,), "ehe": (EHE,),
             "ehcp": (EHCNA,)}.get(update.get("kind") or "", ())
    same = [t for t in rows if t.get("reason") in kinds]
    if same:
        return same[-1]
    return rows[-1] if rows and update.get("kind") == "ehcp" else None


def describe(update: dict[str, Any]) -> str:
    """One line for the school: what the authority decided."""
    kind = update.get("kind")
    when = update.get("on")
    if kind == "ehcp":
        stage = update.get("stage") or ""
        when = (update.get("final_date") if stage == "Final issued" else
                update.get("cease_date") if stage == "Ceased" else
                update.get("draft_date") if stage == "Draft issued" else
                update.get("request_date") if stage == "Requested" else
                update.get("decision_date"))
        text = EHCP_STAGE_TEXT.get(stage, stage.lower() or "EHC plan updated")
    elif kind == "attendance":
        text = (f"attendance case closed - {update['outcome']}" if update.get("closed")
                else f"attendance case: {str(update.get('stage') or 'opened').lower()}")
        if update.get("officer") and not update.get("closed"):
            text += f" (officer: {update['officer']})"
    elif kind == "penalty_notice":
        text = f"penalty notice {str(update.get('status') or 'issued').lower()}"
        if update.get("reason"):
            text += f" ({str(update['reason']).lower()})"
    elif kind == "exclusion":
        text = update.get("text") or "exclusion record updated"
    elif kind == "cme":
        text = f"missing education case: {str(update.get('outcome') or 'open').lower()}"
    elif kind == "ehe":
        text = update.get("text") or "home education record updated"
    elif kind == "received":
        text = f"received - {update.get('what') or 'recorded'}"
    else:
        text = update.get("text") or "updated"
    line = f"{LABEL}: {text}"
    return f"{line} ({when})" if when else line


def record_update(la_child_id: str, update: dict[str, Any], *,
                  journey_id: str | None = None, db_path: str | None = None) -> list[str]:
    """Pass an authority decision to the child's school(s) on this platform.
    Returns lines saying what happened (empty if no school here has the
    child on roll, or none has a notification it answers)."""
    journey_id = _journey_of(la_child_id, journey_id, db_path=db_path)
    if not journey_id:
        return []
    update = dict(update, by=LABEL)
    text = describe(update)
    out = []
    for school, local_id in schools_holding(journey_id, db_path=db_path):
        result = None
        if update.get("kind") == "ehcp":
            receive = getattr(_adapter(school), "receive_send_update", None)
            if callable(receive):
                try:
                    result = receive(local_id, dict(update))
                except Exception as exc:  # noqa: BLE001 - say so; the note still goes
                    out.append(f"{SCHOOL_LABELS[school]} couldn't update its SEN record: "
                               f"{exc}")
        target = _note_target(journey_id, school, update, db_path=db_path)
        if target is not None:
            transitions.add_note(target["transition_id"], text, step=UPDATE_STEP,
                                 db_path=db_path)
        if result:
            out.append(f"{SCHOOL_LABELS[school]}: {result}")
        elif target is not None:
            out.append(f"{SCHOOL_LABELS[school]} has been told.")
    return out


# ── LA → school: school places ──────────────────────────────────────

def _place_transition(journey_id: str, school: str, *, db_path: str | None) -> dict | None:
    return route_support.open_transition(journey_id, LA, school, db_path=db_path)


def place(la_child_id: str, school: str, *, details: dict[str, Any],
          journey_id: str | None = None, actor_user_id: int | None = None,
          db_path: str | None = None) -> tuple[dict | None, list[str]]:
    """Hand an allocated school place to a school on this platform.

    *details* describe the place (``round``, ``basis``, ``entry_year``,
    ``start_date``, ``year_group``, ``reference``). Returns ``(transition or
    None, lines)``; ``None`` when nothing new was started (the child is
    already on the school's roll, or is already on the way from the
    platform's primary)."""
    _check_school(school)
    la = _adapter(LA)
    exported = la.export_handover(str(la_child_id), True, destination_system=school)
    record = dict(exported.record)
    ident = route_support.identity_of(record)
    year = str(details.get("year_group") or ident.get("year_group") or "")
    record["placement_details"] = dict(details, school=SCHOOL_LABELS[school])
    if journey_id is None:
        try:
            journey_id = route_support.journey_for(ident, system=LA,
                                                   student_id=str(la_child_id),
                                                   db_path=db_path)
        except route_support.RouteError as exc:
            raise LinkError(str(exc)) from exc
    journey_id = identity_service.resolve_journey_id(journey_id, db_path=db_path)
    label = SCHOOL_LABELS[school]
    if any(s == school for s, _ in schools_holding(journey_id, db_path=db_path)):
        return None, [f"{label} already has the child on roll."]
    if school == "secondary":
        coming = route_support.open_transition(journey_id, "primary", "secondary",
                                               db_path=db_path)
        if coming is not None:
            transitions.add_note(coming["transition_id"],
                                 f"{LABEL}: place offered and accepted here "
                                 f"({details.get('basis') or 'allocated'})",
                                 step=UPDATE_STEP, db_path=db_path)
            return None, [f"The child is already on the way to {label} from the platform's "
                          "primary school; the transfer there has a note of the offer."]
    # The child's guardians and identity travel; SEN and medical details only
    # as the authority's record holds them, filtered like any handover (no
    # parental consent is recorded on an admission, so they are withheld).
    released = handover.build_handover(LA, school, record, consent=None)
    if released.missing_required:
        raise LinkError("The place is missing: " + route_support.describe_missing(
            LA, school, released.missing_required))
    problems = handover.validate_handover(LA, school, released.payload)
    if problems:
        raise LinkError("; ".join(problems))
    transition, _created = route_support.start(
        journey_id, source_system=LA, destination_system=school,
        student_id=str(la_child_id), reason=str(details.get("round") or "School place"),
        actor_user_id=actor_user_id, year_group=year or None, db_path=db_path)
    tid = transition["transition_id"]
    if transition["status"] == "expected":
        transition = transitions.record_application(
            tid, application_reference=str(details.get("reference") or f"la:{la_child_id}"),
            actor_user_id=actor_user_id, db_path=db_path)
    if transition["status"] == "applied":
        try:
            applicant = route_support.request_applicant(transition, released.payload,
                                                        year_group=year or None)
        except Exception as exc:  # noqa: BLE001 - the school's own message
            raise LinkError(f"{label} couldn't take the place: {exc}") from exc
        transition = transitions.offer_place(
            tid, local_student_id=applicant.local_applicant_id,
            year_group=applicant.year_group, actor_user_id=actor_user_id,
            db_path=db_path)
    if transition["status"] == "offered":
        transition = transitions.accept_place(tid, accepted_by="parent (through the "
                                              "local authority)", db_path=db_path)
    if transition["status"] == "accepted":
        transition = transitions.approve_handover(tid, released, db_path=db_path)
    start = _clean_date(details.get("start_date"), "The start date")
    if start and transition["status"] == "handover_approved" \
            and not transition.get("effective_date"):
        transition = transitions.set_effective_date(tid, start, db_path=db_path)
    where = ("listed under its admissions as accepted - enrolling the child puts them "
             "on roll" if school == "primary" else "listed under Incoming pupils")
    return transition, [f"{label} has the place: {where}."]


def withdraw_place(transition_id: str, *, reason: str, db_path: str | None = None) -> dict:
    """The place was declined or withdrawn before the child started."""
    row = _transition(transition_id, db_path=db_path)
    if row.get("source_system") != LA or row.get("destination_system") not in SCHOOLS:
        raise LinkError("Not a school place from the local authority")
    if row["status"] in ("admitted", "completed"):
        raise LinkError(f"The child has already started at "
                        f"{SCHOOL_LABELS[row['destination_system']]}")
    if row["status"] == "cancelled":
        return row
    dest = enrolments.get_enrolment(row.get("destination_enrolment_id") or "",
                                    db_path=db_path) or {}
    out = transitions.cancel(transition_id, reason=(_text(reason) or "Place withdrawn")[:500],
                             actor_user_id=None, db_path=db_path)
    # The school's own record of the place (an optional adapter method).
    drop = getattr(_adapter(row["destination_system"]), "place_withdrawn", None)
    if callable(drop) and dest.get("local_student_id"):
        drop(str(dest["local_student_id"]), _text(reason) or "Place withdrawn")
    return out


def admitted(transition_id: str, *, local_student_id: str, start_date: str | None = None,
             year_group: str | None = None, db_path: str | None = None) -> dict:
    """The school has put the child on roll: admit and complete the place.
    The authority keeps its record (a concurrent enrolment)."""
    row = _transition(transition_id, db_path=db_path)
    if row.get("source_system") != LA:
        raise LinkError("Not a school place from the local authority")
    if row["status"] == "handover_approved":
        row = transitions.admit(transition_id, local_student_id=str(local_student_id),
                                year_group=year_group, start_date=start_date,
                                db_path=db_path)
    if row["status"] == "admitted":
        row = transitions.complete(transition_id, start_date=start_date, close_source=False,
                                   db_path=db_path)
    return row


def school_for_place(transition_id: str, *, db_path: str | None = None) -> str | None:
    row = transitions.get_transition(transition_id, db_path=db_path) or {}
    return row.get("destination_system") if row.get("source_system") == LA else None


# ── The school's board ──────────────────────────────────────────────

def _name(journey_id: str, *, db_path: str | None) -> str:
    j = identity_service.get(journey_id, db_path=db_path) or {}
    return " ".join(x for x in (j.get("legal_first_name"), j.get("legal_last_name")) if x)


def updates_for(transition_id: str, *, db_path: str | None = None) -> list[dict]:
    """The authority's updates on one notification or place, oldest first."""
    return [e for e in transitions.list_transition_events(transition_id, db_path=db_path)
            if e.get("step") == UPDATE_STEP]


def _all(destination: str, *, db_path: str | None) -> list[dict]:
    rows = transitions.pending_transitions(destination, db_path=db_path)
    for status in ("completed", "cancelled"):
        rows += transitions.pending_transitions(destination, status=status, db_path=db_path)
    return rows


def notifications_from(school: str, *, db_path: str | None = None) -> list[dict]:
    """A school's notifications to the authority, newest first, each with
    ``label``, ``pupil``, ``school_pupil_id``, ``latest`` (the authority's
    latest update) and ``latest_at``."""
    _check_school(school)
    out = []
    for row in _all(LA, db_path=db_path):
        if row.get("source_system") != school:
            continue
        item = dict(row)
        item["pupil"] = _name(row["journey_id"], db_path=db_path)
        item["school_pupil_id"] = route_support.source_local_id(row, db_path=db_path)
        item["label"] = NOTICE_LABELS.get(row["status"], row["status"])
        notes = updates_for(row["transition_id"], db_path=db_path)
        item["latest"] = notes[-1]["note"].removeprefix(f"{LABEL}: ") if notes else ""
        item["latest_at"] = (notes[-1].get("at") or "")[:10] if notes else ""
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


def places_for(school: str, *, db_path: str | None = None) -> list[dict]:
    """School places the authority has allocated at *school*, newest first."""
    _check_school(school)
    out = []
    for row in _all(school, db_path=db_path):
        if row.get("source_system") != LA:
            continue
        item = dict(row)
        item["pupil"] = _name(row["journey_id"], db_path=db_path)
        item["label"] = PLACE_LABELS.get(row["status"], row["status"])
        h = transitions.get_handover(row["transition_id"], db_path=db_path) or {}
        item["place"] = dict(h.get("placement_details") or {})
        out.append(item)
    return sorted(out, key=lambda x: x.get("initiated_at") or "", reverse=True)


__all__ = ["LA", "DESTINATION", "SCHOOLS", "SCHOOL_LABELS", "LABEL", "ATTENDANCE",
           "SUSPENSION", "PERMANENT_EXCLUSION", "CME", "EHE", "EHCNA", "KINDS", "EXCLUSIONS",
           "CME_REASONS", "EXCLUSION_REASONS", "NOTICE_FIELDS", "EHCP_STAGE_TEXT", "NOTICE_LABELS",
           "PLACE_LABELS", "UPDATE_STEP", "LinkError", "check_details",
           "released_handover", "notify", "schools_holding", "describe", "record_update",
           "place", "withdraw_place", "admitted", "school_for_place", "updates_for",
           "notifications_from", "places_for"]
