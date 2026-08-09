"""Admissions and enrolment use cases.

Sits between :mod:`student_service` (which owns the learner record) and
:mod:`course_service` (which owns the offer): applying, checking eligibility,
making an offer and converting it into an enrolment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import ACADEMIC_YEAR
from education_system.systems.fe_college.domain.courses.entry_requirements import (
    ApplicantProfile,
    EligibilityResult,
)
from education_system.systems.fe_college.domain.courses.learning_aims import (
    LearningAim,
)
from education_system.systems.fe_college.domain.students.enrolment import (
    WITHDRAWAL_REASONS,
    Enrolment,
    check_study_programme,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    course_repository as course_repo,
    student_repository as repo,
)
from education_system.systems.fe_college.services import (
    course_service,
    student_service,
)


@dataclass(frozen=True)
class EnrolmentOutcome:
    """The result of an enrolment attempt, including any advisory actions."""

    student: Student
    enrolment: Enrolment | None
    eligibility: EligibilityResult
    actions: tuple[str, ...] = ()

    @property
    def enrolled(self) -> bool:
        return self.enrolment is not None


def withdrawal_reasons() -> tuple[str, ...]:
    return WITHDRAWAL_REASONS


def applicants() -> list[Student]:
    """Learners who have applied but are not yet enrolled."""
    return repo.list_students(status="applicant")


def check(course_id: str, student_id: str) -> EligibilityResult:
    """Check an existing learner record against a course's entry rules."""
    student = repo.get(student_id)
    if student is None:
        raise ValidationError(f"No learner with ID {student_id}")
    return course_service.check_applicant(course_id, _profile_of(student))


def _profile_of(student: Student) -> ApplicantProfile:
    """Build the admissions profile from what the learner record holds.

    GCSE grades are not modelled as separate fields on the learner — a college
    stores them in prior attainment — so the eligibility check treats them as
    unknown and reports the resit action rather than inventing a grade.
    """
    return ApplicantProfile(
        date_of_birth=student.date_of_birth,
        prior_level=_level_from_attainment(student.prior_attainment),
    )


def _level_from_attainment(prior_attainment: str) -> str:
    text = (prior_attainment or "").lower()
    if "level 3" in text:
        return "3"
    if "level 2" in text:
        return "2"
    if "level 1" in text:
        return "1"
    return ""


def enrol(student_id: str, course_id: str, *,
          academic_year: str = ACADEMIC_YEAR,
          is_main_aim: bool = True,
          funding_source: str = "",
          override_eligibility: bool = False) -> EnrolmentOutcome:
    """Enrol a learner, checking entry requirements first.

    A learner who fails the entry check is refused unless
    ``override_eligibility`` is set — colleges do admit on interview against a
    stated requirement, but that has to be a deliberate act, not a default.
    """
    with session():
        student = repo.get(student_id)
        if student is None:
            raise ValidationError(f"No learner with ID {student_id}")

        eligibility = course_service.check_applicant(course_id, _profile_of(student))
        if not eligibility.eligible and not override_eligibility:
            return EnrolmentOutcome(
                student=student,
                enrolment=None,
                eligibility=eligibility,
                actions=eligibility.reasons,
            )

        enrolment = student_service.enrol(
            student_id, course_id,
            academic_year=academic_year,
            is_main_aim=is_main_aim,
            funding_source=funding_source or _default_funding(student),
        )
        return EnrolmentOutcome(
            student=student,
            enrolment=enrolment,
            eligibility=eligibility,
            actions=eligibility.actions,
        )


def _default_funding(student: Student) -> str:
    """The funding stream a learner falls into, from their learner type."""
    if student.learner_type.startswith("19+"):
        return "ESFA Adult Skills Fund"
    if student.learner_type.startswith("16-18"):
        return "ESFA 16-18"
    if student.learner_type == "Higher Education":
        return "Higher Education (OfS)"
    return "Self Funded"


def study_programme(student_id: str) -> tuple[list[Enrolment], list[str]]:
    """A learner's enrolments plus any warnings about the shape of them."""
    enrolments = repo.list_enrolments(student_id=student_id)
    return enrolments, check_study_programme(enrolments)


def withdraw(enrolment_id: int, reason: str, on: date | None = None) -> None:
    if reason not in WITHDRAWAL_REASONS:
        raise ValidationError(
            f"'{reason}' is not a recognised withdrawal reason — expected one of "
            + ", ".join(WITHDRAWAL_REASONS)
        )
    student_service.withdraw(enrolment_id, reason, on)


def transfer(enrolment_id: int, new_course_id: str) -> Enrolment:
    return student_service.transfer(enrolment_id, new_course_id)


def complete(enrolment_id: int, final_grade: str = "", on: date | None = None) -> Enrolment:
    """Mark an enrolment complete and record the achieved grade."""
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        course = course_repo.get(enrolment.course_id)
        if final_grade and course is not None:
            from education_system.systems.fe_college.domain.students.grades import (
                validate_grade,
            )
            validate_grade(final_grade, course.qualification_type)
        enrolment.status = "completed"
        enrolment.final_grade = final_grade
        enrolment.end_date = on or date.today()
        return repo.update_enrolment(enrolment)


def retention(course_id: str | None = None,
              academic_year: str = ACADEMIC_YEAR) -> dict[str, float | int]:
    """Retention and achievement for a course (or the whole college).

    Retention counts learners who did not withdraw; achievement counts those
    who completed with a passing grade. Both are expressed against starts,
    which is the measure the ESFA and Ofsted use.
    """
    from education_system.systems.fe_college.domain.students.grades import is_pass

    enrolments = repo.list_enrolments(course_id=course_id, academic_year=academic_year)
    starts = len(enrolments)
    if not starts:
        return {"starts": 0, "retained": 0, "completed": 0, "achieved": 0,
                "retention_pct": 0.0, "achievement_pct": 0.0}

    withdrawn = sum(1 for e in enrolments if e.status == "withdrawn")
    completed = sum(1 for e in enrolments if e.status == "completed")
    achieved = sum(1 for e in enrolments if e.status == "completed" and is_pass(e.final_grade))
    retained = starts - withdrawn
    return {
        "starts": starts,
        "retained": retained,
        "completed": completed,
        "achieved": achieved,
        "retention_pct": round(retained / starts * 100, 1),
        "achievement_pct": round(achieved / starts * 100, 1),
    }


def add_learning_aim(enrolment_id: int, lars_code: str, *,
                     funding_model: int = 35,
                     funding_value: float = 0.0) -> LearningAim:
    """Attach a fundable learning aim to an enrolment."""
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        aim = LearningAim(
            aim_id=None,
            enrolment_id=enrolment_id,
            lars_code=lars_code,
            aim_type="Programme aim" if enrolment.is_main_aim else "Component aim",
            funding_model=funding_model,
            start_date=enrolment.start_date,
            planned_end_date=enrolment.expected_end_date,
            funding_value=funding_value,
        )
        aim.validate()
        row = aim.to_row()
        placeholders = ", ".join("?" for _ in row)
        from education_system.systems.fe_college.infrastructure.persistence import (
            transaction,
        )
        with transaction() as conn:
            cur = conn.execute(
                f"INSERT INTO learning_aims ({', '.join(row)}) VALUES ({placeholders})",
                list(row.values()),
            )
            aim.aim_id = cur.lastrowid
        return aim


__all__ = [
    "EnrolmentOutcome",
    "add_learning_aim",
    "applicants",
    "check",
    "complete",
    "enrol",
    "retention",
    "study_programme",
    "transfer",
    "withdraw",
    "withdrawal_reasons",
]
