"""The university's side of the University Progression board.

The receiving half of the sixth-form handover, as one screen: who has
arrived, what they arrived with, what is wrong with it, and the three
things admissions can do about each one.

Everything on this board already existed somewhere. The applicant is a
row in ``admission_applications``; the offer conditions are rows in
``admission_conditions``; the outstanding checks are rows in
``admission_requirements``; and the record of *what the sixth form
actually sent* is the event still sitting in the durable outbox. The last
one is the piece nobody could see: the intake reads a payload, creates an
applicant from it and moves on, so "which fields crossed, and which were
withheld for want of consent?" was answerable only from a log line.
:func:`board` reads the outbox back and puts the answer on the row.

Three operations, matching the three stages the handover contract already
implies:

:func:`accept`
    Admissions acknowledges the handover and takes the applicant into
    review. A transition, audited — not a flag.
:func:`request_information`
    Raise the gaps as real ``admission_requirements`` rows, so the chase
    lives on the application's own checklist instead of in somebody's
    inbox. Idempotent per field.
:func:`complete_enrolment`
    Delegates to :func:`admissions_lifecycle.convert_to_student`, which
    is the *only* supported way to turn an applicant into a student and
    which refuses until conditions, right to study and registration are
    all settled. This board never creates a student itself; it surfaces
    the refusal reasons instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.platform.cross_system import handover as _handover
from education_system.platform.cross_system import identity_service
from education_system.platform.integrations.external import cross_system_bus
from education_system.systems.university.domains.admissions.domain import (
    sixthform_handover_records as handover_records,
)
from education_system.systems.university.domains.admissions.domain.services import (
    admissions_lifecycle as lifecycle,
)
from education_system.systems.university.services.boundary_errors import (
    AdmissionsBoundaryError,
)

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "sixth_form"
CONSUMER_SYSTEM = "university"

#: ``admission_prospects.source`` written by the bus intake. What marks an
#: application as having arrived over this boundary rather than through
#: the ordinary CRM.
HANDOVER_SOURCE = "sixth_form_progression"

#: Every prospect source the bus intake has written. ``sixthform_intake``
#: stages its prospects as ``college_progression`` — the value it has
#: always used — so a board matching on :data:`HANDOVER_SOURCE` alone
#: listed nobody the intake had actually staged.
HANDOVER_SOURCES: tuple[str, ...] = (HANDOVER_SOURCE, "college_progression")

# ── Row states ──────────────────────────────────────────────────────
#
# Deliberately *not* the raw application status. Admissions has fourteen
# of those and this board is about one journey through them, so the states
# here answer "whose turn is it?" — which is the question a person
# standing at the screen has.

#: Arrived, nobody has looked at it.
AWAITING_REVIEW = "Awaiting review"
#: Accepted into review; information has been requested or is outstanding.
IN_PROGRESS = "In progress"
#: Every gate satisfied — Complete enrolment will work.
READY_TO_ENROL = "Ready to enrol"
#: Converted; the applicant is a student.
ENROLLED = "Enrolled"
#: Something is wrong with the record itself, not with its progress.
NEEDS_ATTENTION = "Needs attention"
#: The sixth form re-routed the learner elsewhere (Insurance / Clearing at
#: another institution, or no place at all). Kept on the board, last.
WITHDRAWN_REROUTED = "Withdrawn (rerouted)"

STATE_ORDER: tuple[str, ...] = (
    NEEDS_ATTENTION, AWAITING_REVIEW, IN_PROGRESS, READY_TO_ENROL, ENROLLED,
    WITHDRAWN_REROUTED,
)


@dataclass(frozen=True)
class Row:
    """One incoming applicant's line on the board."""

    application_id: int
    journey_id: str
    full_name: str
    state: str
    status: str
    source_sixth_form: str = ""
    sixth_form_student_id: str = ""
    ucas_id: str = ""
    programme: str = ""
    entry_year: str = ""
    offer_status: str = ""
    qualification_status: str = ""
    converted_student_id: str | None = None
    #: Handover spec fields that arrived.
    included: tuple[str, ...] = ()
    #: Declared by the spec, absent from the payload.
    withheld: tuple[str, ...] = ()
    #: Outstanding requirements and unsatisfied conditions.
    outstanding: tuple[str, ...] = ()
    #: Something a human must look at: two applications on one journey, a
    #: name/DOB match against an existing student, an unreadable payload.
    warnings: tuple[str, ...] = ()
    #: Which choice placed the learner (Firm, Insurance, Clearing…).
    route: str = ""
    #: "Deferred to 2028" for a gap-year entry, else "".
    entry_label: str = ""
    #: ``active`` or ``withdrawn_by_reroute``.
    routing_status: str = ""
    reroute_reason: str = ""
    #: "Approved by … on …", or why no reference arrived.
    reference_status: str = ""
    #: One line per predicted grade, with when and by whom it was made
    #: and last changed.
    predictions: tuple[str, ...] = ()
    #: Whether contextual flags arrived — never the flags themselves; those
    #: are read through :func:`contextual_for` by admissions staff only.
    contextual_status: str = ""
    #: The sender's own notes on what was withheld or not held, and why.
    advisories: tuple[str, ...] = ()

    @property
    def can_accept(self) -> bool:
        return self.state == AWAITING_REVIEW

    @property
    def can_enrol(self) -> bool:
        return self.converted_student_id is None and self.state in (
            READY_TO_ENROL, IN_PROGRESS)

    @property
    def sort_key(self) -> tuple[int, str]:
        try:
            rank = STATE_ORDER.index(self.state)
        except ValueError:
            rank = len(STATE_ORDER)
        return rank, self.full_name.lower()


@dataclass(frozen=True)
class ActionResult:
    application_id: int
    ok: bool
    detail: str
    student_id: str | None = None


@dataclass
class Board:
    rows: list[Row] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {state: 0 for state in STATE_ORDER}
        for row in self.rows:
            out[row.state] = out.get(row.state, 0) + 1
        return out

    def get(self, application_id: int) -> Row | None:
        return next((r for r in self.rows
                     if r.application_id == application_id), None)

    @property
    def enrollable(self) -> list[Row]:
        return [r for r in self.rows if r.state == READY_TO_ENROL]

    def summary_line(self) -> str:
        counts = self.counts()
        parts = [f"{counts[s]} {s.lower()}" for s in STATE_ORDER
                 if counts.get(s)]
        return f"{len(self.rows)} applicant(s): " + (", ".join(parts) or "none")


# ── Reading the handover back off the bus ───────────────────────────

def _handover_fields(envelope: dict | None) -> tuple[tuple[str, ...],
                                                     tuple[str, ...]]:
    """``(included, withheld)`` spec field keys for one progression event.

    "Withheld" here means *declared by the spec and not present*, which
    conflates a field the source had no consent to send with one it simply
    does not hold. The distinction lives on the producing side and does not
    cross — ``build_handover`` reports it, the payload does not carry it —
    so the honest label on this screen is "not received", and chasing it is
    what :func:`request_information` is for.
    """
    spec = _handover.get_spec(SOURCE_SYSTEM, CONSUMER_SYSTEM)
    if spec is None or envelope is None:
        return (), ()
    payload = envelope.get("payload") or {}
    included: list[str] = []
    withheld: list[str] = []
    for key in spec.field_keys():
        (included if payload.get(key) is not None else withheld).append(key)
    return tuple(included), tuple(withheld)


def _offer_status(application: dict) -> str:
    conditions = [c for c in application.get("conditions") or []
                  if c.get("status") != "superseded"]
    if not conditions:
        return "No conditions recorded"
    unsatisfied = [c for c in conditions if c.get("status") != "satisfied"]
    if not unsatisfied:
        return f"All {len(conditions)} condition(s) satisfied"
    return f"{len(unsatisfied)} of {len(conditions)} condition(s) outstanding"


def _qualification_status(envelope: dict | None) -> str:
    """Achieved beats predicted; a handover carrying neither says so."""
    payload = (envelope or {}).get("payload") or {}
    achieved = payload.get("achieved_qualifications") or []
    predicted = payload.get("predicted_qualifications") or []
    if achieved:
        grades = ", ".join(
            f"{q.get('subject')} {q.get('grade')}" for q in achieved[:4]
            if isinstance(q, dict))
        return f"Achieved: {grades}" if grades else "Achieved results received"
    if predicted:
        grades = ", ".join(
            f"{q.get('subject')} {q.get('grade')}" for q in predicted[:4]
            if isinstance(q, dict))
        return (f"Predicted only: {grades}" if grades
                else "Predicted grades only")
    return "No qualifications received"


def _outstanding(application: dict) -> tuple[str, ...]:
    out: list[str] = []
    for requirement in application.get("requirements") or []:
        if requirement.get("required") and requirement.get("status") != "verified":
            out.append(f"Requirement: {requirement.get('description') or requirement.get('requirement_type')}")
    for condition in application.get("conditions") or []:
        if condition.get("status") not in lifecycle.CLOSED_CONDITION_STATES:
            out.append(f"Condition: {condition.get('description') or condition.get('condition_type')}")
    return tuple(out)


def _state_for(application: dict, warnings: tuple[str, ...],
               routing: dict | None = None) -> str:
    if application.get("converted_student_id"):
        return ENROLLED
    if (routing or {}).get("routing_status") == handover_records.ROUTING_WITHDRAWN:
        return WITHDRAWN_REROUTED
    if warnings:
        return NEEDS_ATTENTION
    status = (application.get("status") or "").strip().lower()
    if status == lifecycle.READY_TO_ENROL:
        return READY_TO_ENROL
    if status in (lifecycle.SUBMITTED, lifecycle.DOCUMENTS_PENDING):
        return AWAITING_REVIEW
    return IN_PROGRESS


# ── Duplicate detection ─────────────────────────────────────────────

def _duplicate_warnings(rows_by_journey: dict[str, list[int]],
                        application: dict, journey: dict | None) -> tuple[str, ...]:
    """What a human needs to look at before enrolling this person.

    Two shapes, and they fail in opposite directions. *Two applications on
    one journey* is one person wearing two records — the intake now
    prevents it, but rows created before that fix are still there. *Two
    journeys for one name and date of birth* is the identity registry
    having failed to match, which is the shape that produces a duplicate
    student later on.
    """
    out: list[str] = []
    journey_id = application.get("journey_id") or ""
    siblings = rows_by_journey.get(journey_id, [])
    if len(siblings) > 1:
        others = [str(a) for a in siblings
                  if a != application["application_id"]]
        out.append(
            f"Journey {journey_id} also carries application(s) "
            f"{', '.join(others)} — one learner, more than one applicant "
            f"record")

    if journey:
        university_id = journey.get("university_student_id")
        if university_id and not application.get("converted_student_id"):
            out.append(
                f"The journey is already university student {university_id}, "
                f"but this application was never converted — it was most "
                f"likely enrolled directly from the students GUI")
        twin = _identity_twin(journey)
        if twin:
            out.append(twin)
    return tuple(out)


def _identity_twin(journey: dict) -> str | None:
    """A second journey with the same legal name and date of birth."""
    first = journey.get("legal_first_name")
    last = journey.get("legal_last_name")
    dob = journey.get("date_of_birth")
    if not (first and last and dob):
        return None
    try:
        match = identity_service.find_by_identity(first, last, dob)
    except Exception:
        logger.exception("Identity duplicate check failed for journey %s",
                         journey.get("journey_id"))
        return None
    if match and match.get("journey_id") != journey.get("journey_id"):
        return (f"Another journey ({match['journey_id']}) holds the same "
                f"name and date of birth — confirm these are two people "
                f"before enrolling")
    return None


# ── Building the board ──────────────────────────────────────────────

def _handover_applications() -> list[dict]:
    """Every application that arrived over the sixth-form boundary.

    Matched on the prospect's ``source`` rather than on "has a journey_id":
    an ordinary CRM application can acquire a journey the moment identity
    matching links it to a school record, and that does not make it a
    handover.
    """
    from education_system.systems.university.domains.admissions.domain import (
        sixthform_intake,
    )
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    # The lifecycle columns are ALTERed on rather than declared, so a
    # database where the intake has never run does not have them yet.
    if not sixthform_intake.ensure_schema():
        return []
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT a.application_id, a.journey_id, a.status,
                          a.converted_student_id, a.external_reference,
                          a.program_applied, a.academic_year,
                          p.first_name, p.last_name, p.high_school
                     FROM admission_applications a
                     JOIN admission_prospects p
                       ON p.prospect_id = a.prospect_id
                    WHERE p.source IN (?, ?)
                    ORDER BY a.application_id DESC""",
                HANDOVER_SOURCES,
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("Could not list sixth-form handover applications")
        return []


def board() -> Board:
    """Assemble the board: one row per incoming sixth-form applicant."""
    summaries = _handover_applications()
    if not summaries:
        logger.info("University progression board: no sixth-form handovers")
        return Board(rows=[])

    journey_ids = [s["journey_id"] for s in summaries if s.get("journey_id")]
    rows_by_journey: dict[str, list[int]] = {}
    for summary in summaries:
        jid = summary.get("journey_id") or ""
        rows_by_journey.setdefault(jid, []).append(summary["application_id"])

    try:
        events = cross_system_bus.events_for_journeys(
            journey_ids,
            event_name=cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED)
    except Exception:
        logger.exception(
            "Could not read the progression outbox — handover field detail "
            "will be unavailable on this board")
        events = {}

    journeys: dict[str, dict] = {}
    for jid in journey_ids:
        if jid in journeys:
            continue
        try:
            found = identity_service.get(jid)
        except Exception:
            logger.exception("Could not read journey %s", jid)
            found = None
        if found:
            journeys[jid] = found

    try:
        routings = handover_records.routing_for(
            s["application_id"] for s in summaries)
    except Exception:
        logger.exception("Could not read handover routing for the board")
        routings = {}
    try:
        contextual = handover_records.contextual_statuses(
            s["application_id"] for s in summaries)
    except Exception:
        logger.exception("Could not read contextual status for the board")
        contextual = None

    rows: list[Row] = []
    for summary in summaries:
        app_id = int(summary["application_id"])
        rows.append(_row_for(
            summary, events, journeys, rows_by_journey, routings.get(app_id),
            contextual=(None if contextual is None else
                        contextual.get(app_id, {"status": "not_received"}))))
    rows.sort(key=lambda r: r.sort_key)
    out = Board(rows=rows)
    logger.info("University progression board: %s", out.summary_line())
    return out


def _reference_status(payload: dict, advisories: tuple[str, ...]) -> str:
    ref = payload.get("reference") or {}
    if ref:
        stage = ref.get("signoff_stage") or "Submitted"
        by = ref.get("approved_by") or ref.get("referee") or "referee"
        when = (ref.get("approved_at") or ref.get("sent_at")
                or ref.get("submitted_at") or "")
        return f"{stage} — {by}" + (f" on {when[:10]}" if when else "")
    note = next((a for a in advisories if a.startswith("reference:")), "")
    return (note.split(":", 1)[1].strip() if note
            else "Not received (withheld for consent or not sent)")


def _prediction_lines(payload: dict) -> tuple[str, ...]:
    """Each predicted grade with its provenance.

    A university reading "A" needs to know whether that is the October
    prediction or a January revision, and who made it.
    """
    out = []
    for p in payload.get("predicted_qualifications") or []:
        if not isinstance(p, dict):
            continue
        made = (p.get("predicted_at") or "")[:10]
        line = f"{p.get('subject')}: {p.get('grade')}"
        bits = []
        if made:
            bits.append(f"first predicted {made}")
        if p.get("grade_changed_at"):
            who = p.get("grade_changed_by") or p.get("predicted_by")
            bits.append(f"this grade set {p['grade_changed_at'][:10]}"
                        + (f" by {who}" if who else ""))
        elif p.get("last_changed_at"):
            # A row saved before grade changes were recorded: only the
            # last edit of any kind is known, and the line says so.
            bits.append(f"last edited {p['last_changed_at'][:10]}"
                        + (f" by {p['predicted_by']}" if p.get("predicted_by")
                           else "")
                        + " (grade-change date not recorded)")
        elif p.get("predicted_by"):
            bits.append(f"by {p['predicted_by']}")
        if p.get("confidence"):
            bits.append(f"{p['confidence']} confidence")
        out.append(line + (f"  ({'; '.join(bits)})" if bits else ""))
    return tuple(out)


def _contextual_line(application_id: int, payload: dict,
                     advisories: tuple[str, ...],
                     held: dict | None = None) -> str:
    if held is None:
        try:
            held = handover_records.contextual_status(application_id)
        except Exception:
            logger.exception("Could not read contextual status for %s",
                             application_id)
            held = {"status": "unavailable"}
    if held.get("status") == handover_records.CONTEXTUAL_RELEASED:
        return (f"Released under consent — {held.get('count', 0)} flag(s); "
                f"visible to admissions decision-makers only")
    if held.get("status") == handover_records.CONTEXTUAL_WITHHELD:
        reason = (held.get("reason") or "no consent recorded").strip()
        return reason if reason.lower().startswith("withheld") \
            else f"Withheld — {reason}"
    note = next((a for a in advisories if a.startswith("contextual_flags:")), "")
    if note:
        reason = note.split(":", 1)[1].strip()
        return reason if reason.lower().startswith("withheld") \
            else f"Withheld — {reason}"
    return "Not received"


def contextual_for(application_id: int, *, viewer: Any) -> dict | None:
    """The released contextual flags, for admissions staff only.

    ``None`` when the viewer lacks the admissions-decision permission or
    nothing was released. Every call is access-logged.
    """
    return handover_records.contextual_flags(application_id, viewer=viewer)


def can_view_contextual(viewer: Any) -> bool:
    return handover_records.can_view_contextual(viewer)


def _row_for(summary: dict, events: dict, journeys: dict,
             rows_by_journey: dict, routing: dict | None = None, *,
             contextual: dict | None = None) -> Row:
    application_id = int(summary["application_id"])
    journey_id = summary.get("journey_id") or ""
    try:
        application = lifecycle.get_application(application_id)
    except Exception:
        logger.exception("Could not load application %s", application_id)
        application = dict(summary)
        application.setdefault("requirements", [])
        application.setdefault("conditions", [])

    envelope = (events.get(journey_id) or [None])[0]
    payload = (envelope or {}).get("payload") or {}
    # Either name the specs use: the colleges file identity under
    # ``student_identity``, APPRENTICESHIPS_TO_UNIVERSITY under
    # ``learner_identity``, and build_handover emits only its own spec's
    # keys — so reading one name blanks the other route's applicants.
    identity = (payload.get("student_identity")
                or payload.get("learner_identity") or {})
    ucas = payload.get("ucas_application") or {}
    destination = payload.get("confirmed_destination") or {}

    included, withheld = _handover_fields(envelope)
    journey = journeys.get(journey_id)
    warnings = _duplicate_warnings(rows_by_journey, application, journey)
    if envelope is None and journey_id:
        warnings = warnings + (
            "No progression event found for this journey — the handover "
            "detail below is unavailable and the applicant may have been "
            "created by hand",)

    full_name = " ".join(
        p for p in (summary.get("first_name"), summary.get("last_name")) if p
    ).strip() or f"Application {application_id}"

    advisories = tuple(
        f"{a.get('key')}: {a.get('note')}"
        for a in payload.get("handover_advisories") or []
        if isinstance(a, dict) and a.get("note"))
    routing = routing or {}
    entry_label = handover_records.entry_label(routing) or (
        f"Deferred to {destination.get('entry_year')}"
        if destination.get("deferred") and destination.get("entry_year")
        else "")

    return Row(
        application_id=application_id,
        journey_id=journey_id,
        full_name=full_name,
        state=_state_for(application, warnings, routing),
        status=(application.get("status") or "").strip(),
        source_sixth_form=(summary.get("high_school")
                           or payload.get("sixth_form_name") or ""),
        sixth_form_student_id=(identity.get("sixth_form_student_id")
                               or payload.get("sf_student_id") or ""),
        ucas_id=str(ucas.get("ucas_id")
                    or summary.get("external_reference") or ""),
        programme=(destination.get("course_name")
                   or summary.get("program_applied") or ""),
        entry_year=str(destination.get("entry_year")
                       or summary.get("academic_year") or ""),
        offer_status=_offer_status(application),
        qualification_status=_qualification_status(envelope),
        converted_student_id=summary.get("converted_student_id"),
        included=included,
        withheld=withheld,
        outstanding=_outstanding(application),
        warnings=warnings,
        route=str(routing.get("route") or destination.get("route") or ""),
        entry_label=entry_label,
        routing_status=str(routing.get("routing_status") or ""),
        reroute_reason=str(routing.get("reroute_reason") or ""),
        reference_status=_reference_status(payload, advisories),
        predictions=_prediction_lines(payload),
        contextual_status=_contextual_line(application_id, payload,
                                           advisories, contextual),
        advisories=advisories,
    )


# ── Actions ─────────────────────────────────────────────────────────

def accept(application_id: int, *, actor_id: str = "") -> ActionResult:
    """Acknowledge the handover and take the applicant into review."""
    try:
        lifecycle.transition(
            application_id, lifecycle.UNDER_REVIEW,
            reason=f"Sixth-form handover accepted by "
                   f"{actor_id or 'admissions'}",
            actor_id=actor_id)
    except AdmissionsBoundaryError as exc:
        return ActionResult(application_id, False, str(exc))
    except Exception as exc:
        logger.exception("Accepting handover %s failed", application_id)
        return ActionResult(application_id, False, f"Unexpected: {exc}")
    return ActionResult(application_id, True,
                        "Handover accepted; application is under review")


def request_information(application_id: int, fields,
                        *, actor_id: str = "",
                        due_date: str = "") -> ActionResult:
    """Raise the missing handover fields as requirements on the application.

    On the checklist rather than in an email, because the checklist is
    what ``readiness_issues`` consults before allowing enrolment — a chase
    that lives in somebody's inbox cannot hold the gate closed.

    Idempotent per field: asking twice for the same thing does not add a
    second row, so the button is safe to press again when a colleague
    already pressed it.
    """
    wanted = [str(f).strip() for f in fields if str(f).strip()]
    if not wanted:
        return ActionResult(application_id, False,
                            "Nothing selected to request")
    try:
        application = lifecycle.get_application(application_id)
    except Exception as exc:
        return ActionResult(application_id, False,
                            f"Could not load the application: {exc}")

    existing = {
        (r.get("requirement_type") or "").strip()
        for r in application.get("requirements") or []
    }
    added: list[str] = []
    for key in wanted:
        if key in existing:
            continue
        try:
            lifecycle.add_requirement(
                application_id, key,
                f"Requested from the sixth form: {key.replace('_', ' ')}",
                due_date=due_date)
            added.append(key)
        except Exception:
            logger.exception(
                "Could not add requirement %s to application %s",
                key, application_id)

    if not added:
        return ActionResult(application_id, True,
                            "Already requested — nothing further added")
    try:
        lifecycle.transition(
            application_id, lifecycle.DOCUMENTS_PENDING,
            reason=f"Information requested from the sixth form: "
                   f"{', '.join(added)}",
            actor_id=actor_id, force=True)
    except Exception:
        # The requirements are the substance; the status is presentation.
        logger.exception(
            "Requirements were added to application %s but the status could "
            "not be moved to documents_pending", application_id)
    return ActionResult(
        application_id, True,
        f"Requested {len(added)} item(s): {', '.join(added)}")


def enrolment_blockers(application_id: int) -> list[str]:
    """Why :func:`complete_enrolment` would refuse. Empty means it will not."""
    try:
        return lifecycle.readiness_issues(application_id)
    except Exception as exc:
        logger.exception("Readiness check failed for %s", application_id)
        return [f"Readiness could not be evaluated: {exc}"]


def complete_enrolment(application_id: int, *,
                       actor_id: str = "") -> ActionResult:
    """Convert the applicant into a student, or report why not.

    Delegates entirely. ``convert_to_student`` writes the student,
    registration, programme registration, lifecycle history, downstream
    actions, journey link and outbox event in one transaction, and refuses
    until every gate is satisfied. This board's job is to show the refusal
    in words a person can act on, not to find a way around it.
    """
    try:
        student_id = lifecycle.convert_to_student(
            application_id, actor_id=actor_id or "admissions")
    except AdmissionsBoundaryError as exc:
        return ActionResult(application_id, False, str(exc))
    except Exception as exc:
        logger.exception("Enrolment failed for application %s", application_id)
        return ActionResult(application_id, False, f"Unexpected: {exc}")
    return ActionResult(application_id, True,
                        f"Enrolled as university student {student_id}",
                        student_id=student_id)


def complete_enrolment_many(application_ids, *,
                            actor_id: str = "") -> list[ActionResult]:
    """Bulk conversion after results day, one result per applicant.

    Never stops on the first refusal — a batch that aborts halfway leaves
    an operator guessing which half went through. Each applicant's
    validation failure is reported against that applicant.
    """
    results: list[ActionResult] = []
    for application_id in application_ids:
        try:
            results.append(complete_enrolment(int(application_id),
                                              actor_id=actor_id))
        except Exception as exc:
            logger.exception("Bulk enrolment crashed for %s", application_id)
            results.append(ActionResult(int(application_id), False,
                                        f"Crashed: {exc}"))
    ok = sum(1 for r in results if r.ok)
    logger.info("Bulk enrolment: %d/%d converted", ok, len(results))
    return results


__all__ = [
    "SOURCE_SYSTEM", "CONSUMER_SYSTEM", "HANDOVER_SOURCE",
    "AWAITING_REVIEW", "IN_PROGRESS", "READY_TO_ENROL", "ENROLLED",
    "NEEDS_ATTENTION", "WITHDRAWN_REROUTED", "STATE_ORDER",
    "HANDOVER_SOURCES", "contextual_for", "can_view_contextual",
    "Row", "ActionResult", "Board",
    "board", "accept", "request_information", "enrolment_blockers",
    "complete_enrolment", "complete_enrolment_many",
]
