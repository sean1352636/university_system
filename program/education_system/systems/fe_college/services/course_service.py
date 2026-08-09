"""Course use cases: the curriculum offer, units, groups and viability."""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import ACADEMIC_YEAR, CURRICULUM_AREAS
from education_system.systems.fe_college.domain.courses.entry_requirements import (
    ApplicantProfile,
    EligibilityResult,
    EntryRequirement,
    check_eligibility,
)
from education_system.systems.fe_college.domain.courses.models import Course
from education_system.systems.fe_college.domain.courses.modules import (
    CreditProgress,
    Unit,
    credit_progress,
)
from education_system.systems.fe_college.domain.staff.departments import department_for
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
)
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    assessment_repository as assessment_repo,
    attendance_repository as attendance_repo,
    course_repository as repo,
    student_repository as student_repo,
    timetable_repository as timetable_repo,
)


@dataclass(frozen=True)
class CourseDetail:
    """A course with everything the course screen shows."""

    course: Course
    units: list[Unit]
    groups: list
    sessions: list
    entry_requirement: EntryRequirement | None
    attendance_pct: float | None
    learners: list[Student]

    @property
    def total_credits(self) -> int:
        return sum(u.credits for u in self.units)


# ── Queries ─────────────────────────────────────────────────────────────────

def get(course_id: str) -> Course | None:
    return repo.get(course_id)


def search(query: str = "", **filters) -> list[Course]:
    return repo.list_courses(query=query, **filters)


def list_all(academic_year: str | None = None) -> list[Course]:
    return repo.list_courses(academic_year=academic_year)


def enrollable() -> list[Course]:
    """Courses a learner can still be enrolled onto."""
    return repo.list_courses(enrollable_only=True)


def detail(course_id: str) -> CourseDetail | None:
    with session():
        course = repo.get(course_id)
        if course is None:
            return None
        return CourseDetail(
            course=course,
            units=repo.list_units(course_id),
            groups=repo.list_groups(course_id=course_id),
            sessions=timetable_repo.list_sessions(course_id=course_id),
            entry_requirement=repo.get_entry_requirement(course_id),
            attendance_pct=attendance_repo.summary_for_course(course_id).attendance_pct,
            learners=student_repo.list_students(course_id=course_id),
        )


def curriculum_areas() -> list[str]:
    return list(CURRICULUM_AREAS)


def academic_years() -> list[str]:
    years = repo.academic_years()
    return years or [ACADEMIC_YEAR]


def by_area(academic_year: str | None = None) -> dict[str, list[Course]]:
    """Courses grouped by curriculum area, for the offer overview."""
    grouped: dict[str, list[Course]] = {}
    for course in repo.list_courses(academic_year=academic_year):
        grouped.setdefault(course.curriculum_area or "Unassigned", []).append(course)
    return dict(sorted(grouped.items()))


def viability_report(academic_year: str | None = None) -> list[Course]:
    """Courses ordered by how badly they are recruiting.

    The at-risk ones first: those are the decisions a college has to take
    before term starts.
    """
    courses = repo.list_courses(academic_year=academic_year)
    live = [c for c in courses if c.status in ("planned", "recruiting", "running", "full")]
    return sorted(live, key=lambda c: (c.fill_pct if c.fill_pct is not None else 999))


def check_applicant(course_id: str, applicant: ApplicantProfile) -> EligibilityResult:
    """Check an applicant against a course's entry requirements."""
    requirement = repo.get_entry_requirement(course_id)
    if requirement is None:
        # No stated requirements is an open-entry course, not a blocked one.
        return EligibilityResult(eligible=True, actions=("no entry requirements recorded",))
    return check_eligibility(requirement, applicant)


def learner_credit(student_id: str, course_id: str) -> CreditProgress:
    """A learner's credit position on one course."""
    with session():
        units = repo.list_units(course_id)
        grades = assessment_repo.grades_for_student(student_id)
    return credit_progress(units, grades)


# ── Commands ────────────────────────────────────────────────────────────────

def create(course: Course) -> Course:
    """Create a course, defaulting its academic year and department."""
    if not course.academic_year:
        course.academic_year = ACADEMIC_YEAR
    return repo.create(course)


def update(course: Course) -> Course:
    return repo.update(course)


def archive(course_id: str) -> None:
    """Archive a course — the safe alternative to deleting it.

    Enrolment history, results and attendance are all kept; the course simply
    stops appearing as enrollable.
    """
    with session():
        if repo.get(course_id) is None:
            raise ValidationError(f"No course with code {course_id}")
        repo.set_status(course_id, "archived")


def cancel(course_id: str) -> int:
    """Cancel a course that failed to recruit, withdrawing its learners.

    Returns the number of enrolments withdrawn. Cancelling without withdrawing
    would leave learners attached to a course that will never run, which is
    what breaks the funding return.
    """
    with session():
        course = repo.get(course_id)
        if course is None:
            raise ValidationError(f"No course with code {course_id}")
        enrolments = student_repo.list_enrolments(course_id=course_id, status="active")
        for enrolment in enrolments:
            student_repo.withdraw_enrolment(
                enrolment.enrolment_id, "Transferred to another course"
            )
        repo.set_status(course_id, "cancelled")
        return len(enrolments)


def delete(course_id: str) -> bool:
    """Delete a course and every record attached to it.

    Refuses while learners are still enrolled — losing their history to a
    mis-click is not recoverable. Cancel or archive first.
    """
    with session():
        active = student_repo.list_enrolments(course_id=course_id, status="active")
        if active:
            raise ValidationError(
                f"{len(active)} learner(s) are still enrolled — cancel or archive "
                "the course instead of deleting it"
            )
        return repo.delete(course_id)


def add_unit(unit: Unit) -> Unit:
    return repo.add_unit(unit)


def remove_unit(unit_id: str, course_id: str) -> bool:
    return repo.delete_unit(unit_id, course_id)


def set_entry_requirement(requirement: EntryRequirement) -> EntryRequirement:
    return repo.save_entry_requirement(requirement)


def units(course_id: str) -> list[Unit]:
    return repo.list_units(course_id)


def groups(course_id: str | None = None, teacher_id: str | None = None) -> list:
    return repo.list_groups(course_id=course_id, teacher_id=teacher_id)


def create_group(group) -> object:
    return repo.create_group(group)


def set_group_members(group_id: str, student_ids: list[str]) -> None:
    repo.set_group_members(group_id, student_ids)


def group_members(group_id: str) -> list[str]:
    return repo.group_members(group_id)


__all__ = [
    "CourseDetail",
    "academic_years",
    "add_unit",
    "archive",
    "by_area",
    "cancel",
    "check_applicant",
    "create",
    "create_group",
    "curriculum_areas",
    "delete",
    "detail",
    "enrollable",
    "get",
    "group_members",
    "groups",
    "learner_credit",
    "list_all",
    "remove_unit",
    "search",
    "set_entry_requirement",
    "set_group_members",
    "units",
    "update",
    "viability_report",
]
