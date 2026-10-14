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
``confirmed_destination``               the Firm choice
``offer_conditions``                    ``progression.offers``
``personal_statement``                  ``progression.personal_statements``
``reference``                           ``progression.references``
``predicted_qualifications``            ``assessment.predicted_grades``
``achieved_qualifications``             ``assessment.exam_results``
``handover_consent``                    ``governance.gdpr``
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
#: course, entry year and offer conditions that cross.
FIRM_DECISION = "Firm"

#: ``gdpr_consents.purpose`` that releases this handover. An exact value
#: rather than a keyword search: "did the learner consent to this?" must
#: be answerable by a lookup, not by a heuristic over free text. A
#: college that has not recorded it gets ``handover_consent`` reported as
#: missing, which is the truthful answer.
HANDOVER_CONSENT_PURPOSE = "university_handover"


@dataclass(frozen=True)
class Destination:
    """Where a leaving sixth-former is actually going."""

    system: str
    institution: str | None
    reason: str
    firm_choice: dict | None = None

    @property
    def is_home(self) -> bool:
        """True when the learner is coming to this platform's university."""
        return self.system == DESTINATION_SYSTEM


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
            from education_system.systems.university.application import (
                prospectus,
            )
            configured = prospectus.institution_name()
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


def resolve(student) -> Destination:
    """Decide where a leaving sixth-former's record should be sent.

    The Firm choice is the only thing that says a learner is coming *here*
    — an Insurance choice or a rejected offer is not an arrival, and
    announcing one creates an applicant in a university the learner never
    accepted.

    Routing is on evidence, never inference. Two cases fall back to this
    university rather than to ``external``:

    * **No Firm choice recorded.** A college that does not use the UCAS
      module, or a learner whose decisions were never entered, would
      otherwise stop transferring anyone the day this check landed. A
      member of staff has explicitly marked the learner transferred; with
      nothing to contradict them, that stands.
    * **Home institution unknown.** If this platform cannot say what its
      own university is called, it cannot conclude that some other name is
      a different place.

    Only a Firm choice that positively names a *different* institution
    routes away, because only that is evidence of anything.
    """
    student_id = getattr(student, "student_id", "?")
    _application, _choices, firm = _ucas(student_id)

    if not firm:
        return Destination(
            system=DESTINATION_SYSTEM, institution=None, firm_choice=None,
            reason="No Firm UCAS choice recorded — routed to this university "
                   "on the strength of the staff transfer")

    institution = (firm.get("university") or "").strip()
    home = home_university_names()
    if not home:
        logger.debug(
            "No home university configured (set %s) — cannot route %s by "
            "institution", HOME_UNIVERSITY_ENV, student_id)
        return Destination(
            system=DESTINATION_SYSTEM, institution=institution or None,
            firm_choice=firm,
            reason="Home university not configured — routed here by default")

    if _normalise_institution(institution) in home:
        return Destination(
            system=DESTINATION_SYSTEM, institution=institution,
            firm_choice=firm,
            reason=f"Firm UCAS choice: {institution}")

    return Destination(
        system=EXTERNAL_DESTINATION, institution=institution or None,
        firm_choice=firm,
        reason=(f"Firm UCAS choice is {institution or 'another institution'}, "
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
    choices_out = [
        {
            "choice_id": c.choice_id,
            "choice_order": c.choice_order,
            "university": c.university,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "entry_year": c.entry_year,
            "decision_status": c.decision_status,
            "offer_terms": c.offer_terms,
            "final_decision": c.final_decision,
        }
        for c in choices
    ]
    firm = next((c for c in choices_out
                 if c["final_decision"] == FIRM_DECISION), None)
    return app_out, choices_out, firm


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


def _reference(student_id: str) -> dict | None:
    """The submitted academic reference, if there is one.

    Drafts are withheld: an unsubmitted reference is a working note by a
    member of staff, not a document the learner's next institution is
    entitled to read.
    """
    try:
        from education_system.systems.sixth_form.domain.progression.university import references
        refs = references.references_for_student(student_id)
    except Exception:
        logger.exception("Could not read references for %s", student_id)
        return None
    submitted = [r for r in refs if r.submitted_at and r.body]
    if not submitted:
        return None
    latest = max(submitted, key=lambda r: (r.submitted_at or "", r.reference_id))
    return {
        "referee": latest.referee,
        "referee_role": latest.referee_role,
        "body": latest.body,
        "submitted_at": latest.submitted_at,
    }


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
    return [
        {"subject": p.subject, "grade": p.grade, "confidence": p.confidence}
        for p in predictions
    ]


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


def consent_for(student_id: str) -> dict | None:
    """The learner's active consent for this handover, or ``None``.

    Public because the consent is not only a *field* of the payload —
    it is the authority for releasing the sensitive parts of it, and the
    receiving side has to be able to ask about it on its own. The
    university's medical import gates on exactly this.
    """
    return _handover_consent(student_id)


def build_record(student) -> dict[str, Any]:
    """Assemble the spec-keyed record for one sixth-form student.

    Keys are :class:`~handover.HandoverSpec` field keys, which is what
    ``build_handover`` filters against. A source with nothing to say
    omits its key entirely rather than contributing an empty value —
    absent and empty mean different things to ``missing_required``.
    """
    student_id = student.student_id
    record: dict[str, Any] = {"student_identity": _identity(student)}

    application, choices, firm = _ucas(student_id)
    if application:
        record["ucas_application"] = application
    if choices:
        record["choices"] = choices
    if firm:
        record["confirmed_destination"] = {
            "university": firm["university"],
            "course_code": firm["course_code"],
            "course_name": firm["course_name"],
            "entry_year": firm["entry_year"],
            "decision_status": firm["decision_status"],
        }
        conditions = _offer_conditions(firm["choice_id"])
        if conditions:
            record["offer_conditions"] = conditions

    for key, value in (
        ("personal_statement", _personal_statement(student_id)),
        ("reference", _reference(student_id)),
        ("predicted_qualifications", _predicted_qualifications(student_id)),
        ("achieved_qualifications", _achieved_qualifications(student_id)),
        ("handover_consent", _handover_consent(student_id)),
    ):
        if value:
            record[key] = value

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

    result = handover.build_handover(
        SOURCE_SYSTEM, DESTINATION_SYSTEM, record,
        consent=consent, safeguarding_reference=safeguarding_reference)

    if result.missing_required:
        logger.warning(
            "Sixth-form handover for %s is incomplete — missing %s. The "
            "transfer still proceeds; the university will admit on what "
            "arrived and chase the rest.",
            getattr(student, "student_id", "?"),
            ", ".join(result.missing_required))
    return result


__all__ = [
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
