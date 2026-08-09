"""Learner use cases — the operations the interfaces actually invoke.

Services compose repositories and domain rules into whole operations. They are
the layer the GUI and the CLI share: everything a screen needs is one call
here, so the two interfaces can never drift into implementing the same rule
differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import ACADEMIC_YEAR
from education_system.systems.fe_college.domain.students.attendance import (
    AttendanceSummary,
)
from education_system.systems.fe_college.domain.students.enrolment import (
    Enrolment,
    check_study_programme,
)
from education_system.systems.fe_college.domain.students.models import (
    Student,
    ValidationError,
    next_student_id,
)
from education_system.systems.fe_college.domain.students.support import SupportPlan
from education_system.systems.fe_college.domain.students.targets import Target
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    attendance_repository as attendance_repo,
    course_repository as course_repo,
    finance_repository as finance_repo,
    pastoral_repository as pastoral_repo,
    student_repository as repo,
)


@dataclass(frozen=True)
class StudentProfile:
    """Everything the learner profile screen shows, gathered in one call."""

    student: Student
    enrolments: list[Enrolment]
    attendance: AttendanceSummary
    targets: list[Target]
    support: list[SupportPlan]
    balance: float
    warnings: list[str]

    @property
    def main_aim(self) -> Enrolment | None:
        return next((e for e in self.enrolments if e.is_active and e.is_main_aim), None)

    @property
    def course_titles(self) -> list[str]:
        return [e.course_id for e in self.enrolments if e.is_active]


# ── Queries ─────────────────────────────────────────────────────────────────

def get(student_id: str) -> Student | None:
    return repo.get(student_id)


def search(query: str = "", **filters) -> list[Student]:
    """Search learners by name, ID, email or ULN, with optional filters."""
    return repo.list_students(query=query, **filters)


def list_active() -> list[Student]:
    return repo.list_students(status="enrolled")


def profile(student_id: str) -> StudentProfile | None:
    """Assemble a learner's full profile.

    Held in one connection: the profile screen needs six different slices of
    the database and opening six connections to draw one page is wasteful.
    """
    with session():
        student = repo.get(student_id)
        if student is None:
            return None
        enrolments = repo.list_enrolments(student_id=student_id)
        return StudentProfile(
            student=student,
            enrolments=enrolments,
            attendance=attendance_repo.summary_for_student(student_id),
            targets=repo.list_targets(student_id=student_id),
            support=repo.list_support_plans(student_id=student_id),
            balance=finance_repo.account_for(student_id).balance,
            warnings=check_study_programme(enrolments),
        )


def next_reference() -> str:
    """The student ID that would be allocated to the next new learner."""
    return next_student_id(repo.all_student_ids())


def tutor_groups() -> list[str]:
    return repo.tutor_groups()


def counts() -> dict[str, int]:
    return repo.count_by_status()


# ── Commands ────────────────────────────────────────────────────────────────

def create(student: Student) -> Student:
    """Register a new learner (an applicant until they are enrolled)."""
    return repo.create(student)


def update(student: Student) -> Student:
    return repo.update(student)


def delete(student_id: str) -> bool:
    return repo.delete(student_id)


def enrol(student_id: str, course_id: str, *,
          academic_year: str = ACADEMIC_YEAR,
          is_main_aim: bool = True,
          funding_source: str = "",
          start_date: date | None = None) -> Enrolment:
    """Enrol a learner onto a course, enforcing the course's own rules.

    Checks that would otherwise be spread across the two interfaces live here:
    the course must exist and be accepting enrolments, and enrolling a learner
    promotes them from applicant to enrolled in the same transaction.
    """
    with session():
        student = repo.get(student_id)
        if student is None:
            raise ValidationError(f"No learner with ID {student_id}")
        course = course_repo.get(course_id)
        if course is None:
            raise ValidationError(f"No course with code {course_id}")
        if course.status in ("cancelled", "archived"):
            raise ValidationError(f"{course.title} is {course.status} and cannot take enrolments")
        if course.is_full:
            raise ValidationError(
                f"{course.title} is full ({course.enrolled}/{course.capacity})"
            )

        enrolment = repo.add_enrolment(Enrolment(
            enrolment_id=None,
            student_id=student_id,
            course_id=course_id,
            academic_year=academic_year,
            status="active",
            is_main_aim=is_main_aim,
            start_date=start_date or course.start_date or date.today(),
            expected_end_date=course.end_date,
            funding_source=funding_source,
        ))
        if student.status == "applicant":
            repo.set_status(student_id, "enrolled")
        return enrolment


def withdraw(enrolment_id: int, reason: str, on: date | None = None) -> None:
    """Withdraw a learner from one course.

    If it was their last active enrolment they leave the college, so their
    learner record is withdrawn too — otherwise they stay on roll for the
    courses they are still taking.
    """
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        repo.withdraw_enrolment(enrolment_id, reason, on)
        remaining = [
            e for e in repo.list_enrolments(student_id=enrolment.student_id, status="active")
            if e.enrolment_id != enrolment_id
        ]
        if not remaining:
            repo.set_status(enrolment.student_id, "withdrawn", on or date.today())


def transfer(enrolment_id: int, new_course_id: str, *,
             reason: str = "Transferred to another course") -> Enrolment:
    """Move a learner from one course to another, keeping the audit trail.

    The old enrolment is withdrawn rather than edited, so the college can still
    show what the learner originally started.
    """
    with session():
        enrolment = repo.get_enrolment(enrolment_id)
        if enrolment is None:
            raise ValidationError(f"No enrolment with ID {enrolment_id}")
        if enrolment.course_id == new_course_id:
            raise ValidationError("The learner is already on that course")
        repo.withdraw_enrolment(enrolment_id, reason)
        new = repo.add_enrolment(Enrolment(
            enrolment_id=None,
            student_id=enrolment.student_id,
            course_id=new_course_id,
            academic_year=enrolment.academic_year,
            status="active",
            is_main_aim=enrolment.is_main_aim,
            start_date=date.today(),
            funding_source=enrolment.funding_source,
        ))
        repo.set_status(enrolment.student_id, "enrolled")
        return new


def set_target(student_id: str, description: str, *, set_by: str,
               due_date: date | None = None, course_id: str = "") -> Target:
    return repo.add_target(Target(
        target_id=None,
        student_id=student_id,
        description=description,
        status="set",
        course_id=course_id,
        set_by=set_by,
        set_date=date.today(),
        due_date=due_date,
    ))


def complete_target(target_id: int, note: str = "") -> Target:
    with session():
        targets = [t for t in repo.list_targets() if t.target_id == target_id]
        if not targets:
            raise ValidationError(f"No target with ID {target_id}")
        target = targets[0]
        target.status = "achieved"
        target.completed_date = date.today()
        if note:
            target.review_note = note
        return repo.update_target(target)


def add_support(plan: SupportPlan) -> SupportPlan:
    return repo.add_support_plan(plan)


def at_risk(threshold_pct: float = 75.0) -> list[tuple[Student, AttendanceSummary]]:
    """Learners whose attendance has fallen below ``threshold_pct``.

    Ordered worst-first, because that is the order the pastoral team works it.
    """
    with session():
        summaries = attendance_repo.summaries_by_student()
        learners = {s.student_id: s for s in repo.list_students(status="enrolled")}
    rows = [
        (learners[sid], summary)
        for sid, summary in summaries.items()
        if sid in learners
        and summary.attendance_pct is not None
        and summary.attendance_pct < threshold_pct
    ]
    return sorted(rows, key=lambda r: r[1].attendance_pct or 0)


def tutorial_overdue() -> list[Student]:
    """Enrolled learners past due an individual tutorial review."""
    from education_system.systems.fe_college.domain.pastoral.tutorials import (
        is_tutorial_overdue,
    )

    with session():
        last = pastoral_repo.last_tutorial_dates()
        learners = repo.list_students(status="enrolled")
    return [s for s in learners if is_tutorial_overdue(last.get(s.student_id))]


__all__ = [
    "StudentProfile",
    "add_support",
    "at_risk",
    "complete_target",
    "counts",
    "create",
    "delete",
    "enrol",
    "get",
    "list_active",
    "next_reference",
    "profile",
    "search",
    "set_target",
    "transfer",
    "tutor_groups",
    "tutorial_overdue",
    "update",
    "withdraw",
]
