"""Results day: turning conditional offers into places, or not.

The offer email this module's neighbour sends has always told applicants
that if their final grades meet the conditions they "will be confirmed
automatically on results day". Nothing implemented that. There was no path
anywhere from *conditional offer + achieved grades* to Confirmed — the
university made the promise and left the sixth form to keep it by hand,
which it did by a member of staff moving the application status to
Confirmed and the handover treating that as the record of results day
going the learner's way.

This is the missing path. It reads the grades the sixth form has actually
recorded, compares them against the condition we set, and gives an
admissions officer a board of every firm applicant with a verdict against
each one.

**What is and is not automatic.** A grade profile — "ABB", "A*AA" — is
machine-comparable, and where the whole condition is one, this will
confirm it without being asked. A condition with prose in it — "ABB
including B in Mathematics" — is not: the profile half can be checked and
the subject half cannot, so those come back as :data:`REVIEW` with the
evidence attached and a person decides. Pretending otherwise would mean
silently confirming an applicant who got their B in the wrong subject,
which is a worse failure than asking.

Grades are read, never written. Confirming goes through
``record_decision``, so a confirmation is attributed, audited and emailed
exactly like any other decision.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = [
    "MET", "MISSED", "REVIEW", "PENDING",
    "Candidate",
    "auto_confirm",
    "board",
    "confirm_place",
    "decline_place",
    "parse_grade_profile",
    "profile_is_met",
]

#: Verdicts.
MET = "Met"          #: Condition checked in full and satisfied.
MISSED = "Missed"    #: Condition checked in full and not satisfied.
REVIEW = "Review"    #: Needs a person — prose condition, or partial results.
PENDING = "Pending"  #: No results published for this applicant yet.

#: A-level grades, best first. ``A*`` must be tried before ``A``.
_GRADE_ORDER = ("A*", "A", "B", "C", "D", "E")
_GRADE_RANK = {g: i for i, g in enumerate(_GRADE_ORDER)}
_PROFILE_RE = re.compile(r"^(?:A\*|[A-E])+$")
_GRADE_TOKEN_RE = re.compile(r"A\*|[A-E]")


# ── Grade arithmetic ───────────────────────────────────────────────

def parse_grade_profile(text: str | None) -> list[str] | None:
    """The grade profile a condition demands, or ``None`` if it isn't one.

    ``"ABB"`` → ``["A", "B", "B"]``. Prose returns ``None`` rather than a
    guess: the point of this function is to be certain, and a condition it
    cannot be certain about belongs in front of a person.

    A profile followed by prose ("ABB including B in Maths") still parses
    to its profile — the caller pairs that with the fact that prose was
    present and asks for review rather than deciding.
    """
    if not text:
        return None
    first = str(text).strip().split()[0] if str(text).strip() else ""
    first = first.upper().rstrip(",;:")
    if not first or not _PROFILE_RE.match(first):
        return None
    return _GRADE_TOKEN_RE.findall(first)


def _has_prose(text: str | None) -> bool:
    """Is there more to this condition than a grade profile?"""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    parts = stripped.split()
    return len(parts) > 1


def profile_is_met(required: list[str], achieved: list[str]) -> bool:
    """Does *achieved* satisfy *required*?

    Both are sorted best-first and compared position by position, which is
    how a grade profile actually works: "ABB" is met by A, A, B but not by
    A, B, C, and an extra fourth subject never hurts. Fewer results than
    the offer asks for is not met — that is a decision on incomplete
    evidence, and the caller reports it as pending instead.
    """
    if not required:
        return False
    if len(achieved) < len(required):
        return False
    want = sorted(required, key=lambda g: _GRADE_RANK.get(g, 99))
    got = sorted(achieved, key=lambda g: _GRADE_RANK.get(g, 99))
    return all(_GRADE_RANK.get(got[i], 99) <= _GRADE_RANK.get(want[i], 99)
               for i in range(len(want)))


def _clean_grade(raw: str | None) -> str | None:
    """Normalise a recorded grade to one this module can rank."""
    g = str(raw or "").strip().upper().replace(" ", "")
    return g if g in _GRADE_RANK else None


# ── The board ──────────────────────────────────────────────────────

@dataclass
class Candidate:
    """One firm or insurance applicant awaiting a results-day decision."""

    choice_id: int
    application_id: int
    student_id: str
    student_name: str
    course_name: str
    course_code: str | None
    final_decision: str | None      # 'Firm' / 'Insurance'
    condition: str | None           # what we asked for, as written
    required_profile: list[str] | None
    achieved: dict[str, str] = field(default_factory=dict)  # subject -> grade
    verdict: str = PENDING
    reason: str = ""

    @property
    def achieved_profile(self) -> list[str]:
        return [g for g in self.achieved.values() if g]

    @property
    def is_firm(self) -> bool:
        return self.final_decision == "Firm"

    @property
    def achieved_label(self) -> str:
        if not self.achieved:
            return "—"
        return ", ".join(f"{subject} {grade}"
                         for subject, grade in sorted(self.achieved.items()))


def _achieved_grades(student_id: str, year: int | None) -> dict[str, str]:
    """``{subject: grade}`` from the sixth form's published exam results."""
    try:
        from education_system.systems.sixth_form.domain.assessment.exam_results import (
            exam_results as _results,
        )
        rows = _results.results_for_student(student_id, year=year)
    except Exception:
        logger.info("Exam results unavailable for %s", student_id,
                    exc_info=True)
        return {}
    out: dict[str, str] = {}
    for row in rows:
        grade = _clean_grade(getattr(row.result, "grade", None))
        if not grade:
            continue
        subject = (row.subject or "").strip()
        if not subject:
            continue
        # Best grade wins where a subject was sat more than once — a
        # resit is the grade that counts, and we do not know which row is
        # the resit, only which is better.
        current = out.get(subject)
        if current is None or _GRADE_RANK[grade] < _GRADE_RANK[current]:
            out[subject] = grade
    return out


def _condition_for(choice) -> str | None:
    """What we actually asked of this applicant.

    Prefers the structured ``grade_requirement`` an officer entered on the
    offer over the one-line summary on the choice: the summary is written
    for the applicant to read, the requirement is written to be checked.
    """
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            offer_terms as _terms,
        )
        issued = _terms.get_terms(choice.choice_id)
        if issued is not None and (issued.grade_requirement or "").strip():
            return issued.grade_requirement
    except Exception:
        logger.debug("Could not read issued terms for choice #%s",
                     getattr(choice, "choice_id", "?"), exc_info=True)
    return getattr(choice, "offer_terms", None)


def _judge(candidate: Candidate) -> None:
    """Fill in *candidate*'s verdict and the reason for it."""
    if not candidate.achieved:
        candidate.verdict = PENDING
        candidate.reason = "No results published yet."
        return
    if candidate.required_profile is None:
        candidate.verdict = REVIEW
        candidate.reason = (
            "The condition is not a grade profile, so it cannot be "
            "checked automatically.")
        return

    achieved = candidate.achieved_profile
    if len(achieved) < len(candidate.required_profile):
        candidate.verdict = PENDING
        candidate.reason = (
            f"Only {len(achieved)} of "
            f"{len(candidate.required_profile)} results are in.")
        return

    met = profile_is_met(candidate.required_profile, achieved)
    if _has_prose(candidate.condition):
        candidate.verdict = REVIEW
        candidate.reason = (
            "Grades "
            + ("meet" if met else "do not meet")
            + " the profile, but the condition names a subject "
              "requirement that has to be checked by hand.")
        return
    candidate.verdict = MET if met else MISSED
    candidate.reason = (
        "".join(candidate.required_profile) + " required, "
        + "".join(sorted(achieved,
                          key=lambda g: _GRADE_RANK.get(g, 99))) + " achieved.")


def board(
    *,
    cycle_year: int | None = None,
    university_name: str | None = None,
    include_insurance: bool = True,
) -> list[Candidate]:
    """Every applicant holding a conditional offer from us, with a verdict.

    Firm choices first — those are the places we are actually holding —
    then insurance, then within each the ones needing a decision before
    the ones that do not.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    applicants = _ucas.list_applicants(
        university_name=university_name,
        decision_status="Conditional Offer",
        cycle_year=cycle_year,
    )

    wanted_finals = {"Firm"} | ({"Insurance"} if include_insurance else set())
    out: list[Candidate] = []
    for a in applicants:
        if a.final_decision not in wanted_finals:
            continue
        choice = _ucas._sf().get_choice(a.choice_id)
        condition = _condition_for(choice) if choice else a.offer_terms
        candidate = Candidate(
            choice_id=a.choice_id,
            application_id=a.application_id,
            student_id=a.student_id,
            student_name=a.student_name,
            course_name=a.course_name,
            course_code=a.course_code,
            final_decision=a.final_decision,
            condition=condition,
            required_profile=parse_grade_profile(condition),
            achieved=_achieved_grades(a.student_id, a.entry_year or cycle_year),
        )
        _judge(candidate)
        out.append(candidate)

    order = {MET: 0, MISSED: 1, REVIEW: 2, PENDING: 3}
    out.sort(key=lambda c: (0 if c.is_firm else 1,
                            order.get(c.verdict, 9),
                            c.student_name))
    logger.info("Results-day board: %d candidate(s)", len(out))
    return out


# ── Decisions ──────────────────────────────────────────────────────

def confirm_place(choice_id: int, *, decided_by: str | None = None,
                  note: str | None = None):
    """Confirm an applicant's place — the promise the offer email made.

    Goes through ``record_decision`` so the confirmation is attributed,
    audited, linked and emailed like every other decision, then moves the
    sixth form's application to ``Confirmed``, which is what the handover
    reads as the record of results day going the learner's way.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    out = _ucas.record_decision(
        choice_id,
        "Unconditional Offer",
        offer_terms="Confirmed on results day — conditions met",
        notes=note,
        issued_by=decided_by,
    )
    _settle_application(out, "Confirmed")
    logger.info("Confirmed place for UCAS choice #%d (by %s)",
                choice_id, decided_by or "—")
    return out


def decline_place(choice_id: int, *, decided_by: str | None = None,
                  reason: str | None = None):
    """Turn down an applicant who missed their conditions.

    Left as an explicit call rather than something ``auto_confirm`` does
    to the rest of the list: confirming a met condition is the promise we
    already made, whereas declining a missed one is a judgement — near
    misses get taken anyway every year, and a program should not make that
    call on the university's behalf.
    """
    from education_system.systems.university.domains.admissions.domain.ucas import (
        ucas as _ucas,
    )
    out = _ucas.record_decision(
        choice_id,
        "Rejected",
        notes=(reason or "Conditions of the offer were not met."),
        issued_by=decided_by,
    )
    logger.info("Declined UCAS choice #%d on results (by %s)",
                choice_id, decided_by or "—")
    return out


def _settle_application(choice, status: str) -> None:
    """Move the sixth form's application to its end state. Best-effort —
    the university's decision is already recorded either way."""
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import (
            ucas as _ucas,
        )
        sf = _ucas._sf()
        app = sf.get_application(choice.application_id)
        if app is None or app.status == status:
            return
        sf.update_application(choice.application_id, {"status": status})
        logger.info("UCAS application #%d -> %s",
                    choice.application_id, status)
    except Exception:
        logger.exception(
            "Could not move application #%s to %s "
            "(the decision itself is recorded)",
            getattr(choice, "application_id", "?"), status)


def auto_confirm(
    *,
    cycle_year: int | None = None,
    university_name: str | None = None,
    decided_by: str | None = None,
    dry_run: bool = True,
) -> list[Candidate]:
    """Confirm every firm applicant whose condition is met in full.

    Defaults to a dry run, because the first thing anybody wants on
    results day is to see what *would* happen. Only :data:`MET` firm
    candidates are touched — insurance choices are settled by what the
    firm university does, and are not ours to resolve.

    Returns the candidates confirmed (or that would have been).
    """
    candidates = [c for c in board(cycle_year=cycle_year,
                                   university_name=university_name)
                  if c.is_firm and c.verdict == MET]
    if dry_run:
        logger.info("auto_confirm dry run: %d place(s) would be confirmed",
                    len(candidates))
        return candidates

    confirmed: list[Candidate] = []
    for candidate in candidates:
        try:
            confirm_place(candidate.choice_id, decided_by=decided_by,
                          note=candidate.reason)
            confirmed.append(candidate)
        except Exception:
            # One applicant's email bouncing must not stop the rest of
            # results day.
            logger.exception(
                "Could not confirm UCAS choice #%d", candidate.choice_id)
    logger.info("auto_confirm: %d of %d place(s) confirmed",
                len(confirmed), len(candidates))
    return confirmed
