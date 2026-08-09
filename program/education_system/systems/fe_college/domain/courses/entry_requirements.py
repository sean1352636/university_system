"""Entry requirements and the admissions check they drive.

An FE course states a minimum profile (GCSE grades, prior level, age). The
admissions screen runs an applicant against it and gets back a decision plus
the reasons, so an offer is never made or refused without an audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    age_on,
)

# GCSE grades ranked so "at least a 4" is a comparison, not a string match.
_GCSE_RANK = {g: i for i, g in enumerate(("U", "1", "2", "3", "4", "5", "6", "7", "8", "9"))}

# Prior level ranked the same way, for "must hold Level 2 to start Level 3".
_LEVEL_RANK = {"": -1, "Entry": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


@dataclass
class EntryRequirement:
    """The minimum profile a course requires of an applicant."""

    course_id: str
    min_age: int = 16
    max_age: int = 0                 # 0 = no upper limit
    min_prior_level: str = ""        # e.g. "2" to require a Level 2 pass
    min_gcse_english: str = ""       # e.g. "4"
    min_gcse_maths: str = ""
    required_subjects: tuple[str, ...] = ()
    interview_required: bool = False
    dbs_required: bool = False
    portfolio_required: bool = False
    notes: str = ""

    def validate(self) -> None:
        if not self.course_id.strip():
            raise ValidationError("Entry requirements must belong to a course")
        if self.min_age < 14:
            raise ValidationError("Minimum age cannot be below 14")
        if self.max_age and self.max_age < self.min_age:
            raise ValidationError("Maximum age cannot be below the minimum age")
        for label, grade in (("English", self.min_gcse_english), ("maths", self.min_gcse_maths)):
            if grade and grade not in _GCSE_RANK:
                raise ValidationError(f"'{grade}' is not a valid GCSE {label} grade")
        if self.min_prior_level and self.min_prior_level not in _LEVEL_RANK:
            raise ValidationError(f"'{self.min_prior_level}' is not a valid prior level")

    def to_row(self) -> dict:
        return {
            "course_id": self.course_id.strip().upper(),
            "min_age": int(self.min_age),
            "max_age": int(self.max_age),
            "min_prior_level": self.min_prior_level,
            "min_gcse_english": self.min_gcse_english,
            "min_gcse_maths": self.min_gcse_maths,
            "required_subjects": ", ".join(self.required_subjects),
            "interview_required": 1 if self.interview_required else 0,
            "dbs_required": 1 if self.dbs_required else 0,
            "portfolio_required": 1 if self.portfolio_required else 0,
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "EntryRequirement":
        d = dict(row)
        subjects = (d.get("required_subjects") or "").strip()
        return cls(
            course_id=d.get("course_id") or "",
            min_age=int(d.get("min_age") or 16),
            max_age=int(d.get("max_age") or 0),
            min_prior_level=d.get("min_prior_level") or "",
            min_gcse_english=d.get("min_gcse_english") or "",
            min_gcse_maths=d.get("min_gcse_maths") or "",
            required_subjects=tuple(s.strip() for s in subjects.split(",") if s.strip()),
            interview_required=bool(d.get("interview_required")),
            dbs_required=bool(d.get("dbs_required")),
            portfolio_required=bool(d.get("portfolio_required")),
            notes=d.get("notes") or "",
        )


@dataclass(frozen=True)
class ApplicantProfile:
    """What an applicant brings, as captured on the admissions form."""

    date_of_birth: date | None = None
    prior_level: str = ""
    gcse_english: str = ""
    gcse_maths: str = ""
    subjects: tuple[str, ...] = ()
    has_portfolio: bool = False
    has_dbs: bool = False


@dataclass(frozen=True)
class EligibilityResult:
    """The outcome of checking an applicant against a course."""

    eligible: bool
    reasons: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        if self.eligible and not self.actions:
            return "Meets entry requirements"
        if self.eligible:
            return "Meets entry requirements — " + "; ".join(self.actions)
        return "; ".join(self.reasons)


def check_eligibility(
    requirement: EntryRequirement,
    applicant: ApplicantProfile,
    on: date | None = None,
) -> EligibilityResult:
    """Check an applicant against a course's entry requirements.

    Hard failures (age, prior level, GCSE grades) make the applicant
    ineligible. Outstanding *process* steps — an interview, a DBS check, a
    portfolio — are returned as actions instead: they don't disqualify anyone,
    they're things admissions still has to do before the offer is firm.
    """
    reasons: list[str] = []
    actions: list[str] = []
    ref = on or date.today()

    age = age_on(applicant.date_of_birth, ref)
    if age is None:
        actions.append("date of birth needed to confirm age")
    else:
        if age < requirement.min_age:
            reasons.append(f"aged {age}, course requires {requirement.min_age}+")
        if requirement.max_age and age > requirement.max_age:
            reasons.append(f"aged {age}, course upper age limit is {requirement.max_age}")

    if requirement.min_prior_level:
        have = _LEVEL_RANK.get(applicant.prior_level, -1)
        need = _LEVEL_RANK.get(requirement.min_prior_level, -1)
        if have < need:
            reasons.append(
                f"prior attainment Level {applicant.prior_level or 'none'}, "
                f"course requires Level {requirement.min_prior_level}"
            )

    for label, needed, held in (
        ("English", requirement.min_gcse_english, applicant.gcse_english),
        ("maths", requirement.min_gcse_maths, applicant.gcse_maths),
    ):
        if not needed:
            continue
        if _GCSE_RANK.get(held, -1) < _GCSE_RANK[needed]:
            # Below the entry grade is not a refusal on a 16-18 study
            # programme: the learner enrols with a compulsory resit alongside.
            actions.append(f"GCSE {label} below grade {needed} — enrol onto a resit")

    missing = [s for s in requirement.required_subjects if s not in applicant.subjects]
    if missing:
        reasons.append("missing required subject(s): " + ", ".join(missing))

    if requirement.interview_required:
        actions.append("interview required")
    if requirement.portfolio_required and not applicant.has_portfolio:
        actions.append("portfolio required")
    if requirement.dbs_required and not applicant.has_dbs:
        actions.append("DBS check required")

    return EligibilityResult(
        eligible=not reasons,
        reasons=tuple(reasons),
        actions=tuple(actions),
    )


__all__ = [
    "ApplicantProfile",
    "EligibilityResult",
    "EntryRequirement",
    "check_eligibility",
]
