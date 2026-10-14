"""Is this learner actually ready to be handed over to the university?

``handover`` declares *what* crosses the sixth form → university boundary
and ``university_handover`` assembles it. Neither answers the question
that comes first: **should this learner cross at all, today?**

Nothing used to ask it. The university's import picker listed every
active Year 13 student and let a member of staff turn any one of them
into an enrolled undergraduate in two clicks — no firm choice, no
accepted offer, no results, no consent. A learner who had put this
university down as their *insurance* choice, or who was still awaiting a
decision, was one mis-click from being enrolled here and marked Left at
their college.

This module is that missing gate. It reads the same sources
:func:`university_handover.build_record` does and turns them into a list
of named :class:`Check` results, each one either **blocking** (the
handover must not proceed) or advisory (it may, with the gap visible).

The split matters more than the individual rules. A blocking check
asserts something the platform can positively *disprove* — "the firm
choice names a different university", "the offer was rejected", "this
person is already a student here". An advisory check covers what the
platform merely cannot confirm — a college that has not configured its
home institution name, or has no exam-results module at all, must still
be able to transfer its leavers. Turning "we cannot tell" into a refusal
would break every deployment that does not use the full UCAS stack,
which is precisely the failure mode that made the original picker
unconditional.

Source-side only. Whether the *university* already holds an application
for this learner is a university-side question and is checked by the
importer, which can read its own admissions tables; see
``learners...student_crud_gui.importers``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.progression import (
    university_handover,
)

logger = logging.getLogger(__name__)

#: ``ucas_choices.decision_status`` values that are an actual offer.
#: "Awaiting" is a decision that has not been made; "Rejected" and
#: "Withdrawn" are decisions that went the other way.
OFFER_DECISIONS: tuple[str, ...] = ("Unconditional Offer", "Conditional Offer")

#: "Not supplied", as distinct from "supplied as None". Used for the
#: prefetched journey, where None is a real answer meaning "no journey".
_UNSET = object()

#: The ``ucas_applications.status`` that means the place is confirmed —
#: results are in and the conditions of a conditional offer were met.
CONFIRMED_APPLICATION_STATUS = "Confirmed"

#: Application statuses that also settle a conditional offer. Clearing is
#: a confirmed place too; it just did not come from the original offer.
SETTLED_APPLICATION_STATUSES: tuple[str, ...] = (
    CONFIRMED_APPLICATION_STATUS, "Clearing",
)


@dataclass(frozen=True)
class Check:
    """One eligibility question and its answer.

    ``blocking`` is a property of the *failure*, not of the question: a
    check that passes never blocks anything, and the same question can be
    blocking in one deployment and advisory in another depending on what
    evidence is available (see the module docstring).
    """

    key: str
    label: str
    passed: bool
    detail: str
    blocking: bool = True

    @property
    def failed_hard(self) -> bool:
        return not self.passed and self.blocking

    @property
    def failed_soft(self) -> bool:
        return not self.passed and not self.blocking


@dataclass(frozen=True)
class Readiness:
    """Every check for one learner, plus the destination they resolve to."""

    student_id: str
    full_name: str
    checks: tuple[Check, ...] = ()
    destination: university_handover.Destination | None = None
    #: The spec-keyed record the checks were read from, so a caller that
    #: is about to build a handover does not re-read every source module.
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def blockers(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.failed_hard)

    @property
    def warnings(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.failed_soft)

    @property
    def ready(self) -> bool:
        """No blocking check failed. Warnings may still be outstanding."""
        return not self.blockers

    @property
    def clean(self) -> bool:
        """Every check passed."""
        return all(c.passed for c in self.checks)

    def get(self, key: str) -> Check | None:
        for c in self.checks:
            if c.key == key:
                return c
        return None

    def passed(self, key: str) -> bool:
        c = self.get(key)
        return bool(c and c.passed)

    @property
    def status_label(self) -> str:
        """A one-word state for a table column."""
        if self.blockers:
            return "Blocked"
        if self.warnings:
            return "Check"
        return "Ready"

    def summary(self) -> str:
        """Human-readable reason text, blockers first. Empty when clean."""
        lines = [f"✗ {c.label}: {c.detail}" for c in self.blockers]
        lines += [f"! {c.label}: {c.detail}" for c in self.warnings]
        return "\n".join(lines)


def _course_label(destination: dict[str, Any] | None) -> str:
    if not destination:
        return ""
    name = (destination.get("course_name") or "").strip()
    code = (destination.get("course_code") or "").strip()
    if name and code:
        return f"{name} ({code})"
    return name or code


def _today() -> str:
    return _dt.date.today().isoformat()


# ── the individual checks ───────────────────────────────────────────

def _check_identity(student) -> Check:
    """Name + DOB, without which no canonical journey can be anchored."""
    missing = [
        label for label, value in (
            ("first name", student.first_name),
            ("last name", student.last_name),
            ("date of birth", student.date_of_birth),
        ) if not value
    ]
    return Check(
        "identity", "Identity",
        passed=not missing,
        detail=("Name and date of birth on record"
                if not missing else
                f"Missing {', '.join(missing)} — the cross-system journey "
                f"cannot be anchored without them"),
    )


def _check_not_transferred(student) -> Check:
    return Check(
        "not_transferred", "Not already transferred",
        passed=not student.transfer_complete,
        detail=(f"Already transferred on {student.transferred_at} — "
                f"re-importing would create a second university record"
                if student.transfer_complete
                else "No completed transfer on record"),
    )


def _check_destination(destination: university_handover.Destination,
                       firm: dict | None) -> Check:
    """Is *this* university the learner's confirmed destination?

    Blocking only when the platform can positively tell the answer is no.
    :func:`university_handover.resolve` deliberately falls back to this
    university when it cannot tell — that keeps leaver *routing* working
    for a college with no UCAS module — but "we could not tell" is not
    the same claim as "yes", and admitting somebody is the wrong place to
    let the two blur.
    """
    if not destination.is_home:
        return Check(
            "destination", "Confirmed destination",
            passed=False,
            detail=(f"Firm choice is {destination.institution or 'elsewhere'}"
                    f" — not this university"),
        )
    if firm is None:
        return Check(
            "destination", "Confirmed destination",
            passed=False,
            detail="No Firm UCAS choice recorded, so this university is not "
                   "a confirmed destination",
        )
    if not university_handover.home_university_names():
        return Check(
            "destination", "Confirmed destination",
            passed=False, blocking=False,
            detail=(f"Firm choice is {firm.get('university') or 'unnamed'}, "
                    f"but this platform has no configured institution name "
                    f"to compare it against (set "
                    f"{university_handover.HOME_UNIVERSITY_ENV})"),
        )
    return Check(
        "destination", "Confirmed destination",
        passed=True,
        detail=f"Firm UCAS choice: {destination.institution}",
    )


def _check_offer(firm: dict | None) -> Check:
    """A firm *accepted offer*, not merely a firm choice."""
    if firm is None:
        return Check(
            "offer", "Accepted offer", passed=False,
            detail="No Firm UCAS choice, so no accepted offer",
        )
    decision = (firm.get("decision_status") or "").strip()
    if decision in OFFER_DECISIONS:
        return Check(
            "offer", "Accepted offer", passed=True,
            detail=f"{decision} accepted as Firm",
        )
    return Check(
        "offer", "Accepted offer", passed=False,
        detail=(f"Firm choice decision is {decision or 'not recorded'} — "
                f"no offer has been made and accepted"),
    )


def _check_conditions(firm: dict | None,
                      application: dict | None) -> Check:
    """Have the offer's conditions been discharged?

    An unconditional offer has none. A conditional one is discharged by
    the application reaching Confirmed (or Clearing) — that *is* the
    record of results day going the learner's way, and it is a fact the
    college holds rather than a grade comparison this module would have
    to invent by parsing "AAB including Mathematics".
    """
    decision = (firm or {}).get("decision_status") or ""
    if decision == "Unconditional Offer":
        return Check(
            "conditions", "Offer conditions", passed=True,
            detail="Unconditional offer — no conditions to meet",
        )
    status = (application or {}).get("status") or ""
    if status in SETTLED_APPLICATION_STATUSES:
        return Check(
            "conditions", "Offer conditions", passed=True,
            detail=f"UCAS application {status.lower()}",
        )
    if decision != "Conditional Offer":
        # No offer at all — _check_offer already blocks on that, and
        # reporting the same fact twice as two blockers reads as two
        # separate problems.
        return Check(
            "conditions", "Offer conditions", passed=True, blocking=False,
            detail="Not assessed — there is no offer to attach conditions to",
        )
    return Check(
        "conditions", "Offer conditions", passed=False,
        detail=(f"Conditional offer and the UCAS application is still "
                f"{status.lower() or 'unset'} — conditions are not yet "
                f"confirmed as met"),
    )


def _check_results(firm: dict | None, record: dict[str, Any]) -> Check:
    """Released results on record.

    Blocking behind a conditional offer, where the results *are* the
    evidence the conditions were met. Advisory behind an unconditional
    one, and advisory when the college simply has no exam-results module
    to read — an absent source is not a failed learner.
    """
    achieved = record.get("achieved_qualifications") or []
    decision = (firm or {}).get("decision_status") or ""
    conditional = decision == "Conditional Offer"
    if achieved:
        return Check(
            "results", "Results confirmed", passed=True,
            detail=f"{len(achieved)} released result(s) on record",
        )
    return Check(
        "results", "Results confirmed", passed=False,
        blocking=conditional,
        detail=("No released exam results on record — they are the evidence "
                "the offer's conditions were met"
                if conditional else
                "No released exam results on record"),
    )


def _check_consent(record: dict[str, Any]) -> Check:
    """An active, unexpired consent for this specific handover.

    ``handover_consent`` is a *required* field of the boundary spec, so a
    handover without it is incomplete by declaration, not by opinion.
    """
    consent = record.get("handover_consent")
    if not consent:
        return Check(
            "consent", "Handover consent", passed=False,
            detail=(f"No active consent recorded for purpose "
                    f"'{university_handover.HANDOVER_CONSENT_PURPOSE}'"),
        )
    expires = (consent.get("expires_date") or "").strip()
    if expires and expires < _today():
        return Check(
            "consent", "Handover consent", passed=False,
            detail=f"Consent expired on {expires}",
        )
    granted = consent.get("granted_date") or "date not recorded"
    return Check(
        "consent", "Handover consent", passed=True,
        detail=f"Granted {granted}"
               + (f", expires {expires}" if expires else ""),
    )


#: Why right to study is *not* one of the checks above.
#:
#: It belongs on the destination's list, not the source's. The sixth form
#: holds no immigration evidence at all, so a check here could only ever
#: report "cannot tell" — and a check that fails for every learner in
#: every deployment is not a check, it is a permanent warning that trains
#: people to ignore the column it sits in. The university records it
#: properly as an ``admission_requirements`` row of type
#: ``right_to_study`` and gates conversion on it in
#: ``admissions_lifecycle.readiness_issues``. A UI that enrols directly
#: must obtain the acknowledgement itself; the import picker does.
RIGHT_TO_STUDY_NOTE = (
    "Right to study is not verifiable from the sixth form — the check is "
    "the university's, and must be completed at enrolment."
)


def _check_not_already_here(student, journey=_UNSET) -> Check:
    """Blocking: the journey registry already names a university student.

    Reads the canonical registry rather than the university's own tables
    so the sixth form does not have to import the university to ask.

    ``journey`` may be supplied by a caller that has already fetched it —
    :func:`candidates` prefetches the whole cohort in one query, because
    one connection per learner turns a Year 13 list into a visible stall.
    ``None`` means "looked, found nothing"; the sentinel means "not looked".
    """
    try:
        if journey is _UNSET:
            from education_system.platform.cross_system import identity_service
            # find_by_student returns the whole journey row, so there is no
            # second get() to make here.
            journey = identity_service.find_by_student(
                "sixth_form", student.student_id)
        if not journey:
            return Check(
                "not_already_here", "No existing university record",
                passed=True,
                detail="No cross-system journey yet — this transfer will "
                       "create one",
            )
        from education_system.platform.cross_system import identity_service
        _pk_col, id_col = identity_service.SYSTEM_SLOTS["university"]
        existing = journey.get(id_col)
        journey_id = journey.get("journey_id")
        if existing:
            return Check(
                "not_already_here", "No existing university record",
                passed=False,
                detail=f"Already university student {existing} on journey "
                       f"{journey_id}",
            )
        return Check(
            "not_already_here", "No existing university record", passed=True,
            detail=f"Journey {journey_id} has no university slot",
        )
    except Exception:
        logger.exception(
            "Could not check the journey registry for %s", student.student_id)
        return Check(
            "not_already_here", "No existing university record",
            passed=False, blocking=False,
            detail="Could not read the cross-system journey registry — "
                   "check by hand that they are not already enrolled",
        )


# ── the gate ────────────────────────────────────────────────────────

def assess(student, *, journey=_UNSET) -> Readiness:
    """Every eligibility check for one sixth-form student.

    ``journey`` is an optional prefetched registry row — pass it when
    assessing a cohort so the registry is read once rather than once per
    learner. ``None`` is a real value meaning "no journey exists".

    Never raises: a source module that will not load leaves its check
    failed-advisory with the reason in ``detail``, which is a more useful
    answer than an exception out of a list-building loop.
    """
    student_id = getattr(student, "student_id", "?")
    try:
        record = university_handover.build_record(student)
    except Exception:
        logger.exception("Could not assemble the handover record for %s",
                         student_id)
        record = {}
    try:
        destination = university_handover.resolve(student)
    except Exception:
        logger.exception("Could not resolve the destination for %s",
                         student_id)
        destination = university_handover.Destination(
            system=university_handover.DESTINATION_SYSTEM, institution=None,
            reason="Destination could not be resolved")

    firm = destination.firm_choice
    application = record.get("ucas_application")

    checks = (
        _check_identity(student),
        _check_not_transferred(student),
        _check_not_already_here(student, journey),
        _check_destination(destination, firm),
        _check_offer(firm),
        _check_conditions(firm, application),
        _check_results(firm, record),
        _check_consent(record),
    )
    return Readiness(
        student_id=student_id,
        full_name=getattr(student, "full_name", student_id),
        checks=checks, destination=destination, record=record,
    )


def assess_id(student_id: str) -> Readiness | None:
    """:func:`assess` for a student id, or ``None`` if there is no such row."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    return None if student is None else assess(student)


def candidates() -> list[tuple[Any, Readiness]]:
    """Every active Year 13 student paired with their readiness.

    Returns *all* of them, blocked ones included, deliberately: a picker
    that silently drops the ineligible tells a member of staff "this
    learner does not exist", when the useful answer is "this learner is
    not ready, and here is exactly what is missing". Filtering is the
    caller's decision — see :attr:`Readiness.ready`.
    """
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    cohort = _students.list_year_13_students()
    journeys = journeys_for([s.student_id for s in cohort])
    out: list[tuple[Any, Readiness]] = []
    for student in cohort:
        # A failed prefetch must fall back to the per-student lookup, not
        # be read as "no journey" — that would quietly turn the
        # already-enrolled check into a pass for the whole cohort.
        journey = (_UNSET if journeys is None
                   else journeys.get(student.student_id))
        out.append((student, assess(student, journey=journey)))
    ready = sum(1 for _s, r in out if r.ready)
    logger.info("Handover candidates: %d Year 13 student(s), %d ready, "
                "%d blocked", len(out), ready, len(out) - ready)
    return out


def journeys_for(student_ids) -> dict[str, dict] | None:
    """``{sixth_form_student_id: journey}`` for a whole cohort, in one query.

    ``None`` — not ``{}`` — when the registry could not be read. An empty
    mapping is a real answer ("none of them have a journey yet") and would
    make every already-enrolled check pass; ``None`` tells the caller to
    fall back to the per-student lookup, which reports its own failure as
    an advisory check rather than a silent pass.
    """
    try:
        from education_system.platform.cross_system import identity_service
        return identity_service.find_by_students("sixth_form", student_ids)
    except Exception:
        logger.exception(
            "Could not prefetch journeys for the Year 13 cohort — falling "
            "back to a lookup per student")
        return None


def eligible() -> list[Any]:
    """Only the students with no blocking check. Convenience over
    :func:`candidates` for callers that want the short list."""
    return [s for s, r in candidates() if r.ready]


def destination_course(readiness: Readiness) -> str:
    """The firm choice's course, for a picker column. May be empty."""
    return _course_label(readiness.record.get("confirmed_destination"))


__all__ = [
    "OFFER_DECISIONS",
    "CONFIRMED_APPLICATION_STATUS",
    "SETTLED_APPLICATION_STATUSES",
    "RIGHT_TO_STUDY_NOTE",
    "Check",
    "Readiness",
    "assess",
    "assess_id",
    "candidates",
    "journeys_for",
    "eligible",
    "destination_course",
]
