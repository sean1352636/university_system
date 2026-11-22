"""The sixth form's side of the ``SIXTH_FORM_TO_UNIVERSITY`` handover.

``platform.cross_system.handover`` declares *what* crosses this boundary;
this module is what fills it in.

Before it existed the two ends of the transfer disagreed silently. The
sixth form published eight loose keys — names, DOB, gender, title,
``sf_student_id`` — while the university intake read nine different ones:
``ucas_application_id``, ``email``, ``phone``, ``sixth_form_name``,
``programme_name``, ``programme_code``, ``entry_year``, ``semester``.
Only ``sf_student_id`` was common to both, so every bus-driven transfer
produced an applicant with no contact details, no course, and
``programme_code='UNDECLARED'``. Nothing detected it, because each read
was a defensive ``.get(...) or ""``.

Each spec field is assembled from the module that already owns the data:

======================================  ================================
``student_identity``                    ``learners.students``
``ucas_application``                    ``progression.ucas``
``choices``                             ``progression.ucas``
``confirmed_destination``               the choice that placed the learner —
                                        Firm, Insurance (Firm missed), or a
                                        Clearing / Adjustment / Extra
                                        placement (``post_offer``), with
                                        entry year and deferral
                                        (``deferral``)
``offer_conditions``                    ``progression.offers``
``personal_statement``                  ``progression.personal_statements``
``reference``                           ``progression.references`` — only a
                                        reference whose sign-off is final
``predicted_qualifications``            ``assessment.predicted_grades``,
                                        with when and by whom each grade
                                        was made and last changed
``achieved_qualifications``             ``assessment.exam_results``
``handover_consent``                    ``governance.gdpr``
``contextual_flags``                    finance (free meals, bursaries),
                                        pastoral vulnerable-groups register
                                        (care, young carers), alumni
                                        (first generation in HE) — only
                                        under the "Contextual admissions
                                        data" consent
``handover_advisories``                 this module: what was withheld or
                                        is not held, and why
======================================  ================================

Every source is optional and independently guarded: a college that does
not use the UCAS module still transfers students, it just hands over
less. What is missing is *reported* rather than defaulted —
:attr:`~handover.HandoverResult.missing_required` names any required
field that could not be filled, so a thin handover is visible at both
ends instead of arriving as a row of empty strings.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from education_system.platform.cross_system import handover

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "sixth_form"
DESTINATION_SYSTEM = "university"

#: Recorded when a leaver's Firm choice is an institution this platform
#: does not run. One of ``progression.NON_PHASE_DESTINATIONS``: the
#: learner has still gone somewhere, and the journey should say so.
EXTERNAL_DESTINATION = "external"

#: Comma-separated institution names that mean "the university this
#: platform runs". Overrides the university system's configured
#: ``institution_name``, and takes a list because ``ucas_choices.university``
#: is free text a member of staff typed — "Teesside University",
#: "University of Teesside" and "Teesside" are the same place, and matching
#: them by fuzzy comparison would sooner or later match the wrong one.
HOME_UNIVERSITY_ENV = "SIXTH_FORM_HOME_UNIVERSITY"

#: The UCAS decision naming a learner's first-choice offer. The Firm
#: choice — not the application as a whole — is what determines the
#: course, entry year and offer conditions that cross, until results day
#: says otherwise (see :func:`_destination_choice`).
FIRM_DECISION = "Firm"
INSURANCE_DECISION = "Insurance"

# ── Routes: which choice actually placed the learner ────────────────
ROUTE_FIRM = "Firm"
ROUTE_INSURANCE = "Insurance"
ROUTE_CLEARING = "Clearing"
ROUTE_ADJUSTMENT = "Adjustment"
ROUTE_EXTRA = "Extra"
#: Firm and Insurance both missed (or the place released) and no
#: Clearing placement recorded: the learner holds no place anywhere.
ROUTE_UNPLACED = "Unplaced"

#: ``post_offer`` results-day outcomes that move the destination.
_OUTCOME_INSURANCE = "Insurance confirmed"
#: Firm decision states that free the Insurance place.
_FIRM_LOST_STATUSES = ("Rejected", "Withdrawn")
_OUTCOMES_NO_PLACE = ("Unsuccessful at Firm and Insurance",
                      "Released (decline my place)")

#: ``gdpr_consents.purpose`` that releases ``contextual_flags``. Kept
#: identical to ``gdpr.CONTEXTUAL_ADMISSIONS_PURPOSE``.
CONTEXTUAL_CONSENT_PURPOSE = "Contextual admissions data"

#: A Clearing-style area band. The sixth form holds no such column, so
#: this is only ever reported as *not held* — never derived from a
#: postcode, never invented.
_AREA_BAND_NOTE = ("No POLAR/TUNDRA participation band is held by the "
                   "sixth form — none is sent")

#: ``gdpr_consents.purpose`` that releases this handover. An exact value
#: rather than a keyword search: "did the learner consent to this?" must
#: be answerable by a lookup, not by a heuristic over free text. A
#: college that has not recorded it gets ``handover_consent`` reported as
#: missing, which is the truthful answer.
HANDOVER_CONSENT_PURPOSE = "university_handover"


@dataclass(frozen=True)
class Destination:
    """Where a leaving sixth-former is actually going.

    ``firm_choice`` keeps its historical name but holds the choice that
    *placed* the learner — the Firm, or the Insurance once the Firm was
    missed, or a Clearing / Adjustment / Extra placement — because every
    reader of it (the eligibility gate, the transfer router) means "the
    place they are taking up". ``route`` says which.
    """

    system: str
    institution: str | None
    reason: str
    firm_choice: dict | None = None
    route: str | None = None
    #: The results-day confirmation outcome recorded in ``post_offer``.
    confirmation: str | None = None

    @property
    def is_home(self) -> bool:
        """True when the learner is coming to this platform's university."""
        return self.system == DESTINATION_SYSTEM

    @property
    def choice(self) -> dict | None:
        return self.firm_choice

    @property
    def deferred(self) -> bool:
        return bool((self.firm_choice or {}).get("deferred"))

    @property
    def entry_year(self) -> Any:
        return (self.firm_choice or {}).get("entry_year")

    @property
    def entry_label(self) -> str:
        """"Deferred to 2028", or "" for an ordinary current-cycle entry."""
        if not self.deferred:
            return ""
        year = self.entry_year
        return f"Deferred to {year}" if year else "Deferred entry"


def _normalise_institution(name: str | None) -> str:
    """Fold an institution name so trivial spelling differences match."""
    folded = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    folded = re.sub(r"\s+", " ", folded).strip()
    return folded[4:] if folded.startswith("the ") else folded


def home_university_names() -> set[str]:
    """Normalised names that mean "us", or an empty set if unknown.

    Prefers the explicit environment list; otherwise asks the university
    what it publishes as its own name. The import is lazy and guarded, so
    a sixth form running without the university installed still works — it
    just cannot route by institution.
    """
    raw = os.getenv(HOME_UNIVERSITY_ENV, "")
    names = [part for part in raw.split(",") if part.strip()]
    if not names:
        try:
            from education_system.platform.cross_system.adapters import route_support
            configured = route_support.adapter_for("university").institution_name()
            names = [configured] if configured else []
        except Exception:
            logger.debug("Could not read the university's institution name",
                         exc_info=True)
            names = []
    return {n for n in (_normalise_institution(x) for x in names) if n}


def is_home_university(institution: str | None) -> bool:
    """Does *institution* name this platform's own university?

    The question every write to a UCAS choice has to ask before it decides
    whether the sixth form is allowed to answer it. Folded through
    ``_normalise_institution`` so "Teesside University" and "the teesside
    university" are the same institution, and false whenever we cannot
    establish who we are — a sixth form that does not know the university
    is there must keep its own fields editable, not lock them against an
    owner that will never claim them.
    """
    folded = _normalise_institution(institution)
    return bool(folded) and folded in home_university_names()


def _route_phrase(route: str | None, outcome: str | None = None) -> str:
    """How a route reads in a reason line."""
    return {
        ROUTE_FIRM: "Firm UCAS choice",
        ROUTE_INSURANCE: ("Insurance UCAS choice (Firm not met"
                          + (f" — {outcome}" if outcome else "") + ")"),
        ROUTE_CLEARING: "Clearing placement",
        ROUTE_ADJUSTMENT: "Adjustment placement",
        ROUTE_EXTRA: "UCAS Extra placement",
    }.get(route or "", "UCAS choice")


def resolve(student) -> Destination:
    """Decide where a leaving sixth-former's record should be sent.

    The choice that placed the learner is the only thing that says they
    are coming *here*. Until results day that is the Firm choice; after
    it, ``post_offer`` may say otherwise:

    * **Insurance confirmed** — the Firm was missed and the Insurance
      choice is the place.
    * **Clearing / Adjustment placement** — a placed post-offer route names
      the institution and course directly, and outranks both.
    * **Unsuccessful at Firm and Insurance / place released**, with no
      placement — the learner holds no place, so nothing routes here.
    * **UCAS Extra placement** — the Extra offer accepted stands in for the
      Firm the learner never had.

    An unconfirmed Insurance choice, or a rejected offer, is not an
    arrival, and announcing one creates an applicant in a university the
    learner never accepted.

    Routing is on evidence, never inference. Two cases fall back to this
    university rather than to ``external``:

    * **No placing choice recorded.** A college that does not use the UCAS
      module, or a learner whose decisions were never entered, would
      otherwise stop transferring anyone the day this check landed. A
      member of staff has explicitly marked the learner transferred; with
      nothing to contradict them, that stands.
    * **Home institution unknown.** If this platform cannot say what its
      own university is called, it cannot conclude that some other name is
      a different place.

    Only a placing choice that positively names a *different* institution
    — or results-day evidence that there is no place at all — routes away.
    """
    student_id = getattr(student, "student_id", "?")
    application, choices, _firm = _ucas(student_id)
    firm, route, outcome = _destination_choice(application, choices)

    if route == ROUTE_UNPLACED:
        return Destination(
            system=EXTERNAL_DESTINATION, institution=None, firm_choice=None,
            route=route, confirmation=outcome,
            reason=(f"No confirmed place: results day recorded "
                    f"'{outcome}' and no Clearing placement is recorded"))

    if not firm:
        return Destination(
            system=DESTINATION_SYSTEM, institution=None, firm_choice=None,
            route=route, confirmation=outcome,
            reason="No Firm UCAS choice recorded — routed to this university "
                   "on the strength of the staff transfer")

    phrase = _route_phrase(route, outcome)
    institution = (firm.get("university") or "").strip()
    home = home_university_names()
    if not home:
        logger.debug(
            "No home university configured (set %s) — cannot route %s by "
            "institution", HOME_UNIVERSITY_ENV, student_id)
        return Destination(
            system=DESTINATION_SYSTEM, institution=institution or None,
            firm_choice=firm, route=route, confirmation=outcome,
            reason="Home university not configured — routed here by default")

    if _normalise_institution(institution) in home:
        return Destination(
            system=DESTINATION_SYSTEM, institution=institution,
            firm_choice=firm, route=route, confirmation=outcome,
            reason=f"{phrase}: {institution}")

    return Destination(
        system=EXTERNAL_DESTINATION, institution=institution or None,
        firm_choice=firm, route=route, confirmation=outcome,
        reason=(f"{phrase} is {institution or 'another institution'}, "
                f"which this platform does not run"))


def _identity(student) -> dict[str, Any]:
    """The learner as the destination needs to know them."""
    return {
        "sixth_form_student_id": student.student_id,
        "title": student.title,
        "first_name": student.first_name,
        "middle_name": student.middle_name,
        "last_name": student.last_name,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "email": student.email,
        "phone": student.phone,
    }


def _ucas(student_id: str) -> tuple[dict | None, list[dict], dict | None]:
    """``(application, choices, firm_choice)`` — any part may be absent."""
    try:
        from education_system.systems.sixth_form.domain.progression.university import ucas
    except Exception:
        logger.debug("UCAS module unavailable for %s", student_id, exc_info=True)
        return None, [], None

    try:
        application = ucas.get_application_for_student(student_id)
        if application is None:
            return None, [], None
        choices = ucas.list_choices(application.application_id)
    except Exception:
        logger.exception("Could not read the UCAS application for %s", student_id)
        return None, [], None

    app_out = {
        "application_id": application.application_id,
        "ucas_id": application.ucas_id,
        "cycle_year": application.cycle_year,
        "status": application.status,
        "submitted_at": application.submitted_at,
    }
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            deferral,
        )
        flags = deferral.flags_for(c.choice_id for c in choices)
    except Exception:
        logger.exception("Could not read deferral flags for %s", student_id)
        deferral, flags = None, {}
    choices_out = []
    for c in choices:
        flag = flags.get(c.choice_id, False)
        deferred = (deferral.is_deferred(c, cycle_year=application.cycle_year,
                                         flag=flag)
                    if deferral is not None else False)
        choices_out.append({
            "choice_id": c.choice_id,
            "choice_order": c.choice_order,
            "university": c.university,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "entry_year": c.entry_year,
            "deferred": deferred,
            "decision_status": c.decision_status,
            "offer_terms": c.offer_terms,
            "final_decision": c.final_decision,
        })
    firm = next((c for c in choices_out
                 if c["final_decision"] == FIRM_DECISION), None)
    return app_out, choices_out, firm


def _post_offer(application_id: int | None
                ) -> tuple[str | None, list[dict]]:
    """``(results-day outcome, placed post-offer routes newest first)``."""
    if not application_id:
        return None, []
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            post_offer,
        )
        confirmation = post_offer.get_confirmation(int(application_id))
        placed = []
        for route in post_offer.list_routes(application_id=int(application_id),
                                            status="Placed"):
            choice = (post_offer.get_choice(int(route["placed_choice_id"]))
                      if route.get("placed_choice_id") else None)
            if choice:
                placed.append({**route, "placed_choice": choice})
    except Exception:
        logger.exception("Could not read post-offer routes for UCAS "
                         "application %s", application_id)
        return None, []
    placed.sort(key=lambda r: (r.get("closed_on") or "", r.get("route_id") or 0),
                reverse=True)
    return (confirmation or {}).get("outcome"), placed


def _placement_choice(route: dict, application: dict | None) -> dict:
    """A post-offer placement in the shape of a UCAS choice.

    Clearing places are for entry in the cycle applied in, so the entry
    year is the application's cycle — the same year UCAS would show.
    """
    placed = route["placed_choice"]
    return {
        "choice_id": None,
        "po_choice_id": placed.get("po_choice_id"),
        "route_id": route.get("route_id"),
        "choice_order": None,
        "university": placed.get("university"),
        "course_code": placed.get("course_code"),
        "course_name": placed.get("course_name"),
        "entry_year": (application or {}).get("cycle_year"),
        "deferred": False,
        "decision_status": None,
        "offer_terms": placed.get("entry_requirements"),
        "final_decision": None,
        "placed_on": route.get("closed_on"),
    }


def _destination_choice(application: dict | None, choices: list[dict]
                        ) -> tuple[dict | None, str | None, str | None]:
    """``(placing choice, route, results-day outcome)``.

    See :func:`resolve` for the precedence. The choice may be ``None``
    with a route — Insurance confirmed but no Insurance choice on record,
    or :data:`ROUTE_UNPLACED`.
    """
    firm = next((c for c in choices
                 if c.get("final_decision") == FIRM_DECISION), None)
    insurance = next((c for c in choices
                      if c.get("final_decision") == INSURANCE_DECISION), None)
    outcome, placed = _post_offer((application or {}).get("application_id"))

    for route in placed:
        if route.get("route") in (ROUTE_CLEARING, ROUTE_ADJUSTMENT):
            return _placement_choice(route, application), route["route"], outcome
    if outcome == _OUTCOME_INSURANCE:
        return insurance, ROUTE_INSURANCE, outcome
    if outcome in _OUTCOMES_NO_PLACE:
        return None, ROUTE_UNPLACED, outcome
    if (insurance and not outcome
            and (application or {}).get("status") == "Confirmed"
            and (firm is None
                 or firm.get("decision_status") in _FIRM_LOST_STATUSES)):
        # The university confirmed the Insurance place itself (it may only
        # do so once the Firm is declined), with nothing recorded here on
        # results day: the confirmation alone says where the learner goes.
        return insurance, ROUTE_INSURANCE, outcome
    if firm:
        return firm, ROUTE_FIRM, outcome
    for route in placed:
        if route.get("route") == ROUTE_EXTRA:
            return _placement_choice(route, application), ROUTE_EXTRA, outcome
    return None, None, outcome


def _placement_offer(choice: dict, route: str) -> dict:
    """What stands for offer conditions on a post-offer placement.

    A Clearing or Adjustment place is offered against results already in,
    so there is no grade condition left to meet — recording one would hold
    the university's conversion gate closed on a condition nobody can
    discharge. The entry requirements quoted travel as a note.
    """
    notes = [f"Place confirmed through {route}"
             + (f" on {choice['placed_on']}" if choice.get("placed_on") else "")]
    if choice.get("offer_terms"):
        notes.append(f"Entry requirements quoted: {choice['offer_terms']}")
    return {
        "grade_requirement": None,
        "grade_alternative": None,
        "reply_deadline": None,
        "expiry_date": None,
        "scholarship": None,
        "accommodation_guaranteed": False,
        "notes": ". ".join(notes),
        "confirmed_place": True,
        "route": route,
    }


def _offer_conditions(choice_id: int) -> dict | None:
    """The offer attached to a choice, as conditions the destination can act on."""
    try:
        from education_system.systems.sixth_form.domain.progression.university import offers
        details = offers.get_details_for_choice(choice_id)
    except Exception:
        logger.exception("Could not read offer details for choice %s", choice_id)
        return None
    if details is None:
        return None
    return {
        "grade_requirement": details.grade_requirement,
        "grade_alternative": details.grade_alternative,
        "reply_deadline": details.reply_deadline,
        "expiry_date": details.expiry_date,
        "scholarship": details.scholarship,
        "accommodation_guaranteed": bool(details.accommodation_guaranteed),
        "notes": details.notes,
    }


def _personal_statement(student_id: str) -> dict | None:
    """The most recently updated statement, with the status it was left in.

    The status travels with it deliberately: a destination reading a
    statement should be able to tell a reviewed final draft from a
    work-in-progress.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import statements as personal_statements
        statements = personal_statements.statements_for_student(student_id)
    except Exception:
        logger.exception("Could not read personal statements for %s", student_id)
        return None
    if not statements:
        return None
    latest = max(statements, key=lambda s: (s.updated_at or "", s.statement_id))
    return {
        "body": latest.body,
        "status": latest.status,
        "word_count": latest.word_count,
        "updated_at": latest.updated_at,
    }


#: Sign-off stages at which a structured reference is final: the head of
#: sixth form has approved it (and it may since have been sent).
_FINAL_SIGNOFF_STAGES = ("Approved", "Sent")


def _reference_state(student_id: str) -> tuple[dict | None, str | None]:
    """``(released reference, why none was released)``.

    Only a *final* reference crosses: a three-section reference once the
    head of sixth form has approved it (stage Approved or Sent), or a
    single-text reference once Submitted with a body. Anything earlier is
    a working document by members of staff — a tutor's draft is not what
    the college says about the learner — and is withheld and reported.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import references
        refs = references.references_for_student(student_id)
    except Exception:
        logger.exception("Could not read references for %s", student_id)
        return None, "References could not be read"
    if not refs:
        return None, "No academic reference is recorded"

    final: list[tuple[str, dict]] = []
    pending: list[str] = []
    for ref in refs:
        try:
            detail = references.get_structured(ref.reference_id) or {}
        except Exception:
            logger.exception("Could not read reference #%s", ref.reference_id)
            continue
        structured = detail.get("structure") == references.STRUCTURE_THREE
        stage = detail.get("signoff_stage") or "Draft"
        if structured:
            if stage in _FINAL_SIGNOFF_STAGES and ref.body:
                when = (detail.get("sent_at") or detail.get("approved_at")
                        or ref.submitted_at or "")
                final.append((when, {
                    "referee": ref.referee,
                    "referee_role": ref.referee_role,
                    "body": ref.body,
                    "structure": "three_section",
                    "sections": {col: detail.get(col)
                                 for col, _h in references.SECTIONS},
                    "signoff_stage": stage,
                    "tutor_signed_by": detail.get("tutor_signed_by"),
                    "tutor_signed_at": detail.get("tutor_signed_at"),
                    "approved_by": detail.get("approved_by"),
                    "approved_at": detail.get("approved_at"),
                    "sent_by": detail.get("sent_by"),
                    "sent_at": detail.get("sent_at"),
                    "submitted_at": ref.submitted_at or detail.get("sent_at"),
                    # Frozen at approval: what was predicted when it was
                    # signed, which may differ from today's predictions.
                    "predicted_grades_at_approval": (
                        detail.get("predicted_grades")
                        if detail.get("predicted_grades_frozen") else None),
                }))
            else:
                pending.append(f"#{ref.reference_id} at sign-off stage "
                               f"'{stage}'")
        elif ref.status == "Submitted" and ref.body:
            final.append((ref.submitted_at or "", {
                "referee": ref.referee,
                "referee_role": ref.referee_role,
                "body": ref.body,
                "structure": "single",
                "signoff_stage": "Submitted",
                "submitted_at": ref.submitted_at,
            }))
        else:
            pending.append(f"#{ref.reference_id} {ref.status}")

    if final:
        final.sort(key=lambda item: item[0])
        return final[-1][1], None
    return None, ("Reference not yet approved (" + "; ".join(pending)
                  + ") — withheld until sign-off is complete")


def _reference(student_id: str) -> dict | None:
    """The final academic reference, if there is one (see
    :func:`_reference_state`)."""
    return _reference_state(student_id)[0]


def _predicted_qualifications(student_id: str) -> list[dict] | None:
    try:
        from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
            predicted_grades,
        )
        predictions = predicted_grades.list_predictions(student_id=student_id)
    except Exception:
        logger.exception("Could not read predicted grades for %s", student_id)
        return None
    if not predictions:
        return None
    out = []
    for p in predictions:
        changed_at = getattr(p, "grade_changed_at", None)
        out.append({
            "subject": p.subject,
            "grade": p.grade,
            "confidence": p.confidence,
            # Who made the prediction and when — so the university can tell
            # an October prediction from a January revision.
            "predicted_by": p.predicted_by,
            "predicted_at": p.predicted_at,
            "grade_changed_at": changed_at,
            "grade_changed_by": getattr(p, "grade_changed_by", None),
            # The best date for "how current is this grade": the recorded
            # grade change, else the last edit of any kind (rows saved
            # before grade changes were recorded), and the basis says which.
            "last_changed_at": changed_at or p.updated_at,
            "last_changed_basis": ("grade change" if changed_at
                                   else "last edit (grade change not "
                                        "recorded)"),
        })
    return out


def _achieved_qualifications(student_id: str) -> list[dict] | None:
    """Released exam results only — an unreleased grade is not yet a fact."""
    try:
        from education_system.systems.sixth_form.domain.assessment.exam_results import (
            exam_results,
        )
        rows = exam_results.results_for_student(student_id)
    except Exception:
        logger.exception("Could not read exam results for %s", student_id)
        return None
    released = [r for r in rows if r.result and r.result.released_at]
    if not released:
        return None
    return [
        {
            "subject": r.subject,
            "grade": r.result.grade,
            "exam_board": r.exam_board,
            "season": r.season,
            "year": r.year,
        }
        for r in released
    ]


def _handover_consent(student_id: str) -> dict | None:
    """The learner's active consent for this specific handover, if recorded."""
    try:
        from education_system.systems.sixth_form.domain.governance.gdpr import gdpr
        consents = gdpr.list_consents(
            subject_ref=student_id,
            purpose=HANDOVER_CONSENT_PURPOSE,
            active_only=True,
        )
    except Exception:
        logger.exception("Could not read handover consent for %s", student_id)
        return None
    if not consents:
        return None
    latest = max(consents, key=lambda c: (c.granted_date or "", c.consent_id))
    return {
        "consent_id": latest.consent_id,
        "purpose": latest.purpose,
        "granted_date": latest.granted_date,
        "expires_date": latest.expires_date,
        "source": latest.source,
    }


def _contextual_consent(student_id: str) -> dict | None:
    """The learner's active consent to share contextual admissions data."""
    try:
        from education_system.systems.sixth_form.domain.governance.gdpr import gdpr
        consents = gdpr.list_consents(
            subject_ref=student_id, purpose=CONTEXTUAL_CONSENT_PURPOSE,
            active_only=True)
    except Exception:
        logger.exception("Could not read contextual consent for %s",
                         student_id)
        return None
    if not consents:
        return None
    latest = max(consents, key=lambda c: (c.granted_date or "", c.consent_id))
    return {
        "consent_id": latest.consent_id,
        "purpose": latest.purpose,
        "granted_date": latest.granted_date,
        "expires_date": latest.expires_date,
    }


def _contextual_flags(student_id: str, consent: dict) -> dict:
    """Contextual flags the sixth form holds a real record of.

    Each flag is read from the module that owns the fact and appears only
    when that record says so; a missing record is "not held", never
    "no". Nothing is derived — in particular no area-based participation
    band, because the sixth form holds none. Amounts, benefit bases, local
    authorities and caseworkers never cross: the flag and its category is
    the whole of what contextual admissions needs.
    """
    flags: dict[str, dict] = {}
    not_held: list[str] = []
    unreadable: list[str] = []

    # Care experienced — the vulnerable-groups register (not casework).
    try:
        from education_system.systems.sixth_form.domain.pastoral.wellbeing import (
            wellbeing,
        )
        care = wellbeing.list_care_records(student_id=student_id)
        if care:
            latest = max(care, key=lambda r: (r.start_date or "", r.record_id))
            flags["care_experienced"] = {"value": True,
                                         "category": latest.care_status}
        else:
            not_held.append("care_experienced")
        carers = wellbeing.list_young_carers(student_id=student_id)
        if carers:
            latest = max(carers, key=lambda r: (r.identified_on or "",
                                                r.carer_id))
            flags["young_carer"] = {"value": True,
                                    "identified_on": latest.identified_on,
                                    "current": bool(latest.active)}
        else:
            not_held.append("young_carer")
    except Exception as exc:
        logger.info("Care / young-carer records not readable for %s: %s",
                    student_id, exc)
        unreadable += ["care_experienced", "young_carer"]

    # Free school meals — an entitlement, not a benefit basis.
    try:
        from education_system.systems.sixth_form.domains.finance.domain.free_meals import (
            free_meals,
        )
        ents = [e for e in free_meals.list_entitlements(student_id=student_id)
                if e.status in ("Active", "Ended", "Suspended")]
        if ents:
            latest = max(ents, key=lambda e: (e.start_date or "",
                                              e.entitlement_id))
            flags["free_school_meals"] = {
                "value": True, "academic_year": latest.academic_year,
                "current": latest.status == "Active"}
        else:
            not_held.append("free_school_meals")
    except Exception:
        logger.exception("Free-meal entitlements not readable for %s",
                         student_id)
        unreadable.append("free_school_meals")

    # 16-19 bursary — vulnerable or discretionary, awarded; no amounts.
    try:
        from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
            bursaries,
        )
        awards = [a for a in bursaries.list_applications(
                      student_id=student_id, approved_only=True)
                  if a.bursary_type in (bursaries.VULNERABLE_TYPE,
                                        bursaries.DISCRETIONARY_TYPE)]
        if awards:
            latest = max(awards, key=lambda a: (a.application_date or "",
                                                a.application_id))
            flag = {"value": True, "category": latest.bursary_type,
                    "academic_year": latest.academic_year}
            if latest.bursary_type == bursaries.VULNERABLE_TYPE \
                    and latest.vulnerable_category:
                flag["vulnerable_category"] = latest.vulnerable_category
            flags["bursary_16_19"] = flag
        else:
            not_held.append("bursary_16_19")
    except Exception:
        logger.exception("Bursary awards not readable for %s", student_id)
        unreadable.append("bursary_16_19")

    # First generation in HE — only ever recorded on the alumni record.
    try:
        from education_system.systems.sixth_form.domain.learners.alumni import (
            outcomes as alumni_outcomes,
        )
        if alumni_outcomes.first_gen_he_for_student(student_id):
            flags["first_generation_he"] = {"value": True}
        else:
            not_held.append("first_generation_he")
    except Exception:
        logger.exception("First-generation HE not readable for %s",
                         student_id)
        unreadable.append("first_generation_he")

    not_held.append("polar_tundra_band")
    return {
        "consent": consent,
        "flags": flags,
        "not_held": not_held,
        "unreadable": unreadable,
    }


def consent_for(student_id: str) -> dict | None:
    """The learner's active consent for this handover, or ``None``.

    Public because the consent is not only a *field* of the payload —
    it is the authority for releasing the sensitive parts of it, and the
    receiving side has to be able to ask about it on its own. The
    university's medical import gates on exactly this.
    """
    return _handover_consent(student_id)


def build_record(student, *, include_contextual: bool = True
                 ) -> dict[str, Any]:
    """Assemble the spec-keyed record for one sixth-form student.

    Keys are :class:`~handover.HandoverSpec` field keys, which is what
    ``build_handover`` filters against. A source with nothing to say
    omits its key entirely rather than contributing an empty value —
    absent and empty mean different things to ``missing_required``.

    ``include_contextual=False`` skips reading the contextual flags
    themselves (the consent is still checked): the eligibility list builds
    a record for every Year 13 learner on each refresh, and reading a
    vulnerable-groups register a few hundred times to draw a table writes
    an access-log row for each one. Only the released handover needs them.
    """
    student_id = student.student_id
    record: dict[str, Any] = {"student_identity": _identity(student)}
    advisories: list[dict[str, str]] = []

    application, choices, _firm = _ucas(student_id)
    if application:
        record["ucas_application"] = application
    if choices:
        record["choices"] = choices
    placing, route, outcome = _destination_choice(application, choices)
    if placing:
        deferred = bool(placing.get("deferred"))
        entry_year = placing.get("entry_year")
        record["confirmed_destination"] = {
            "university": placing["university"],
            "course_code": placing["course_code"],
            "course_name": placing["course_name"],
            "entry_year": entry_year,
            "decision_status": placing["decision_status"],
            "route": route,
            "deferred": deferred,
            "cycle_year": (application or {}).get("cycle_year"),
            "results_day_outcome": outcome,
            "choice_id": placing.get("choice_id"),
            "po_choice_id": placing.get("po_choice_id"),
        }
        if placing.get("choice_id"):
            conditions = _offer_conditions(placing["choice_id"])
        else:
            conditions = _placement_offer(placing, route or "")
        if conditions:
            record["offer_conditions"] = conditions
        if deferred:
            advisories.append({
                "key": "confirmed_destination",
                "note": (f"Deferred entry to {entry_year or 'a later year'} "
                         f"(gap year) — not an arrival for the "
                         f"{(application or {}).get('cycle_year') or 'current'}"
                         f" cycle")})
        if route and route != ROUTE_FIRM:
            advisories.append({
                "key": "confirmed_destination",
                "note": f"Destination is the {_route_phrase(route, outcome)}"})
    elif route == ROUTE_UNPLACED:
        advisories.append({
            "key": "confirmed_destination",
            "note": f"No confirmed place ({outcome})"})

    reference, reference_note = _reference_state(student_id)
    if reference:
        record["reference"] = reference
    elif reference_note:
        advisories.append({"key": "reference", "note": reference_note})

    for key, value in (
        ("personal_statement", _personal_statement(student_id)),
        ("predicted_qualifications", _predicted_qualifications(student_id)),
        ("achieved_qualifications", _achieved_qualifications(student_id)),
        ("handover_consent", _handover_consent(student_id)),
    ):
        if value:
            record[key] = value

    contextual_consent = _contextual_consent(student_id)
    if contextual_consent is None:
        advisories.append({
            "key": "contextual_flags",
            "note": (f"Withheld — no active '{CONTEXTUAL_CONSENT_PURPOSE}' "
                     f"consent is recorded")})
    elif include_contextual:
        record["contextual_flags"] = _contextual_flags(
            student_id, contextual_consent)
        if not record["contextual_flags"]["flags"]:
            advisories.append({
                "key": "contextual_flags",
                "note": "Consent recorded; the sixth form holds no "
                        "contextual flags for this learner"})
        if record["contextual_flags"]["unreadable"]:
            advisories.append({
                "key": "contextual_flags",
                "note": ("Could not be read under the transferring "
                         "account's access, so not sent: "
                         + ", ".join(record["contextual_flags"]["unreadable"]))})
        advisories.append({"key": "contextual_flags",
                           "note": _AREA_BAND_NOTE})
    else:
        record["_contextual_consent"] = contextual_consent

    if advisories:
        record["handover_advisories"] = advisories
    return record


def build(student, *, consent: bool | set[str] | None = None,
          safeguarding_reference: str | None = None) -> handover.HandoverResult:
    """Build the released payload for ``student``.

    ``consent`` gates the spec's *sensitive* fields (the academic
    reference, the support referral) and is the caller's decision, since
    only the transfer flow knows what was agreed. It is separate from the
    ``handover_consent`` field, which is the recorded consent itself.

    Never raises: a handover that could not be assembled is an empty one,
    and the transfer it accompanies has already happened.
    """
    try:
        record = build_record(student)
    except Exception:
        logger.exception("Could not assemble the university handover for %s",
                         getattr(student, "student_id", "?"))
        record = {}

    # The contextual flags carry their own authority: they are only in the
    # record at all when the learner consented to exactly this purpose, so
    # that recorded consent — not the caller's general ``consent`` — is
    # what releases them.
    if record.get("contextual_flags") and consent is not True:
        consent = set(consent or ()) | {"contextual_flags"}

    result = handover.build_handover(
        SOURCE_SYSTEM, DESTINATION_SYSTEM, record,
        consent=consent, safeguarding_reference=safeguarding_reference)

    # Say *why* a sensitive field did not travel. The receiver otherwise
    # sees only an absent key, which reads the same as "not held".
    withheld = [k for k in result.withheld_no_consent if k != "contextual_flags"]
    if withheld:
        notes = list(result.payload.get("handover_advisories") or [])
        notes += [{"key": key,
                   "note": "Held by the sixth form but withheld — the "
                           "transfer was not given consent to release it"}
                  for key in withheld]
        result.payload["handover_advisories"] = notes
        if "handover_advisories" not in result.included:
            result.included.append("handover_advisories")

    if result.missing_required:
        logger.warning(
            "Sixth-form handover for %s is incomplete — missing %s. The "
            "transfer still proceeds; the university will admit on what "
            "arrived and chase the rest.",
            getattr(student, "student_id", "?"),
            ", ".join(result.missing_required))
    return result


# ── Reroutes: Insurance confirmed, Clearing, Extra, Adjustment ───────

@dataclass(frozen=True)
class RerouteResult:
    """What :func:`reroute` did for one learner."""

    student_id: str
    action: str          # "none", "rerouted_home", "rerouted_away"
    detail: str
    journey_id: str | None = None

    @property
    def changed(self) -> bool:
        return self.action != "none"


def progression_payload(student, released: handover.HandoverResult, *,
                        moved_by: str | None = None) -> dict[str, Any]:
    """The ``student.progression.completed`` payload for a released handover.

    The same two layers the transfer publishes (``students._publish_
    progression``): the flat identity envelope keys the platform's intakes
    match on, then the spec-keyed dataset.
    """
    payload = {
        "sf_student_id": student.student_id,
        "first_name": student.first_name,
        "middle_name": student.middle_name,
        "last_name": student.last_name,
        "date_of_birth": student.date_of_birth,
        "gender": student.gender,
        "title": student.title,
        "moved_by": moved_by,
        "handover_boundary": released.boundary,
        "handover_missing": released.missing_required,
    }
    payload.update(released.payload)
    return payload


def _describe(destination: Destination) -> dict[str, Any]:
    choice = destination.choice or {}
    return {
        "route": destination.route,
        "institution": destination.institution,
        "course_code": choice.get("course_code"),
        "course_name": choice.get("course_name"),
        "entry_year": choice.get("entry_year"),
        "deferred": destination.deferred,
        "is_home": destination.is_home,
    }


def _route_key(d: dict[str, Any] | None) -> tuple:
    d = d or {}
    return (
        bool(d.get("is_home")),
        _normalise_institution(d.get("institution")),
        (d.get("course_code") or "").strip().upper(),
        (d.get("course_name") or "").strip().lower(),
        str(d.get("entry_year") or ""),
        bool(d.get("deferred")),
    )


def last_handed_over(journey_id: str) -> dict[str, Any] | None:
    """The destination the university was last told about, or ``None``.

    Read back off the durable outbox — the newest sixth-form progression
    handover or reroute notice for the journey — so the comparison is
    against what was actually *sent*, not against what the college now
    believes it sent.
    """
    from education_system.platform.integrations.external import cross_system_bus
    events = cross_system_bus.events_for_journeys([journey_id]).get(
        str(journey_id), [])
    for env in events:
        name = env.get("event_name")
        payload = env.get("payload") or {}
        if name == handover.EVENT_UCAS_HANDOVER_REROUTED:
            return {
                "route": payload.get("to_route"),
                "institution": payload.get("to_institution"),
                "course_code": payload.get("to_course_code"),
                "course_name": payload.get("to_course_name"),
                "entry_year": payload.get("to_entry_year"),
                "deferred": bool(payload.get("to_deferred")),
                "is_home": bool(payload.get("to_home")),
                "event_id": env.get("event_id"),
            }
        if (name == cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED
                and env.get("source_system") == SOURCE_SYSTEM):
            dest = payload.get("confirmed_destination") or {}
            return {
                "route": dest.get("route") or (ROUTE_FIRM if dest else None),
                "institution": dest.get("university"),
                "course_code": dest.get("course_code")
                               or payload.get("programme_code"),
                "course_name": dest.get("course_name")
                               or payload.get("programme_name"),
                "entry_year": dest.get("entry_year"),
                "deferred": bool(dest.get("deferred")),
                "is_home": True,
                "event_id": env.get("event_id"),
            }
    return None


def reroute(student, *, actor: str | None = None) -> RerouteResult:
    """Re-run the handover when a learner's destination has changed.

    Called after results day moves the place: the Insurance confirmed
    because the Firm was missed, a Clearing / Adjustment placement, an
    Extra offer accepted, or a released place. Compares :func:`resolve`
    with what the university was last sent and, when they differ:

    * publishes ``ucas.handover.rerouted`` — routing metadata only (which
      institution, course, entry year and route) — so the university can
      mark its application withdrawn-by-reroute when the learner is now
      going elsewhere, or move it to the new course when they are coming
      here by another route;
    * when the new destination is this university, re-sends the handover
      through the progression event (the existing mechanism, with its own
      idempotency key per destination) so the university *updates* the
      application it already holds for the journey rather than creating a
      second one.

    Does nothing for a learner nobody has handed over yet: their transfer
    will simply resolve the new destination when it happens. Never raises.
    """
    sid = getattr(student, "student_id", str(student))
    try:
        if isinstance(student, str):
            from education_system.systems.sixth_form.domain.learners.students import (
                students as _students,
            )
            student = _students.get_student(sid)
            if student is None:
                return RerouteResult(sid, "none", "No such student")
        from education_system.platform.cross_system import identity_service
        from education_system.platform.integrations.external import cross_system_bus

        journey = identity_service.find_by_student(SOURCE_SYSTEM, sid)
        if not journey:
            return RerouteResult(sid, "none",
                                 "Not handed over yet — the transfer will "
                                 "use the new destination")
        journey_id = journey["journey_id"]
        prior = last_handed_over(journey_id)
        if prior is None and not student.transfer_complete:
            return RerouteResult(sid, "none",
                                 "Not handed over yet — the transfer will "
                                 "use the new destination", journey_id)
        destination = resolve(student)
        new = _describe(destination)
        if prior is not None and _route_key(prior) == _route_key(new):
            return RerouteResult(sid, "none", "Destination unchanged",
                                 journey_id)
        if prior is None and not new["is_home"]:
            # Transferred elsewhere and still going elsewhere: the
            # university was never told anything, so there is nothing to
            # correct there.
            return RerouteResult(sid, "none",
                                 "Never handed to this university and still "
                                 "not coming here", journey_id)

        token = "|".join(str(v) for v in _route_key(new))
        import hashlib
        digest = hashlib.sha1(token.encode("utf-8"),
                              usedforsecurity=False).hexdigest()[:16]
        prior = prior or {}
        reason = destination.reason
        notice = {
            "sf_student_id": sid,
            "from_route": prior.get("route"),
            "from_institution": prior.get("institution"),
            "from_course_code": prior.get("course_code"),
            "from_course_name": prior.get("course_name"),
            "from_home": bool(prior.get("is_home")),
            "to_route": new["route"],
            "to_institution": new["institution"],
            "to_course_code": new["course_code"],
            "to_course_name": new["course_name"],
            "to_entry_year": new["entry_year"],
            "to_deferred": new["deferred"],
            "to_home": new["is_home"],
            "results_day_outcome": destination.confirmation,
            "reason": reason,
            "rerouted_by": actor,
        }
        cross_system_bus.publish_cross_system(
            handover.EVENT_UCAS_HANDOVER_REROUTED,
            source_system=SOURCE_SYSTEM,
            source_module="sixth_form.progression.university_handover",
            journey_id=journey_id, target_system=DESTINATION_SYSTEM,
            idempotency_key=f"sixth_form:ucas_reroute:{sid}:{digest}",
            **notice)

        if destination.is_home:
            released = build(student)
            payload = progression_payload(student, released, moved_by=actor)
            payload["handover_reroute"] = {
                k: notice[k] for k in ("from_route", "from_institution",
                                       "from_course_code", "to_route",
                                       "results_day_outcome", "reason")}
            cross_system_bus.publish_cross_system(
                cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
                source_system=SOURCE_SYSTEM,
                source_module="sixth_form.progression.university_handover",
                journey_id=journey_id, target_system=DESTINATION_SYSTEM,
                idempotency_key=(f"sixth_form:progression:{sid}:"
                                 f"reroute:{digest}"),
                **payload)
            identity_service.record_transition_once(
                journey_id, from_system=SOURCE_SYSTEM,
                to_system=DESTINATION_SYSTEM, reason=reason)
            action = "rerouted_home"
        else:
            identity_service.record_transition_once(
                journey_id, from_system=SOURCE_SYSTEM,
                to_system=destination.system, reason=reason)
            action = "rerouted_away"
        logger.info("Handover for %s rerouted (%s): %s", sid, action, reason)
        return RerouteResult(sid, action, reason, journey_id)
    except Exception:
        logger.exception("Could not re-route the university handover for %s",
                         sid)
        return RerouteResult(sid, "none",
                             "Reroute failed — see the log; nothing was sent")


def reroute_for_ucas_application(application_id: int, *,
                                 actor: str | None = None) -> RerouteResult | None:
    """:func:`reroute` for the learner a UCAS application belongs to.

    The hook ``post_offer`` calls after recording a results-day outcome or
    closing a route as Placed. ``None`` when the application is unknown.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import (
            ucas,
        )
        application = ucas.get_application(int(application_id))
    except Exception:
        logger.exception("Could not read UCAS application %s for a reroute",
                         application_id)
        return None
    if application is None:
        return None
    return reroute(application.student_id, actor=actor)


__all__ = [
    "ROUTE_FIRM",
    "ROUTE_INSURANCE",
    "ROUTE_CLEARING",
    "ROUTE_ADJUSTMENT",
    "ROUTE_EXTRA",
    "ROUTE_UNPLACED",
    "CONTEXTUAL_CONSENT_PURPOSE",
    "RerouteResult",
    "reroute",
    "reroute_for_ucas_application",
    "last_handed_over",
    "progression_payload",
    "SOURCE_SYSTEM",
    "DESTINATION_SYSTEM",
    "EXTERNAL_DESTINATION",
    "FIRM_DECISION",
    "HANDOVER_CONSENT_PURPOSE",
    "HOME_UNIVERSITY_ENV",
    "Destination",
    "home_university_names",
    "resolve",
    "consent_for",
    "build_record",
    "build",
]
