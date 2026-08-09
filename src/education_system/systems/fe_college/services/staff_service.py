"""Staff use cases: directory, availability, workload and department roll-ups."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.staff.availability import Availability
from education_system.systems.fe_college.domain.staff.departments import (
    DEPARTMENTS,
    Department,
    areas_in,
)
from education_system.systems.fe_college.domain.staff.models import Staff, next_staff_id
from education_system.systems.fe_college.domain.staff.workload import Workload
from education_system.systems.fe_college.domain.staff.workload import (
    summarise as summarise_workload,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence import session
from education_system.systems.fe_college.infrastructure.persistence.repositories import (
    assessment_repository as assessment_repo,
    course_repository as course_repo,
    staff_repository as repo,
    timetable_repository as timetable_repo,
)


@dataclass(frozen=True)
class StaffProfile:
    """A member of staff with everything the staff screen shows."""

    staff: Staff
    workload: Workload
    courses_led: list[str]
    groups_taught: list[str]
    availability: Availability
    marking_outstanding: int


# ── Queries ─────────────────────────────────────────────────────────────────

def get(staff_id: str) -> Staff | None:
    return repo.get(staff_id)


def find_by_email(email: str) -> Staff | None:
    """Resolve a signed-in account to its staff record.

    Shared auth holds the account; this college holds the staff record. Email
    is the only field both carry, so it is the join.
    """
    return repo.get_by_email(email)


def search(query: str = "", **filters) -> list[Staff]:
    return repo.list_staff(query=query, **filters)


def teaching_staff() -> list[Staff]:
    """Staff who may be timetabled — the teacher picker's source."""
    return repo.list_staff(active_only=True, teaching_only=True)


def profile(staff_id: str) -> StaffProfile | None:
    with session():
        member = repo.get(staff_id)
        if member is None:
            return None
        loads = {w.staff_id: w for w in repo.workloads()}
        return StaffProfile(
            staff=member,
            workload=loads.get(staff_id, Workload(
                staff_id=staff_id,
                staff_name=member.full_name,
                contracted_hours=member.contracted_hours,
            )),
            courses_led=[c.course_id for c in course_repo.list_courses(course_leader=staff_id)],
            groups_taught=[g.group_id for g in course_repo.list_groups(teacher_id=staff_id)],
            availability=repo.get_availability(staff_id),
            marking_outstanding=len(assessment_repo.marking_queue(staff_id)),
        )


def next_reference() -> str:
    return next_staff_id(repo.all_staff_ids())


def departments() -> list[str]:
    """Configured departments, plus any extras staff records have picked up."""
    known = list(DEPARTMENTS)
    for name in repo.departments():
        if name not in known:
            known.append(name)
    return known


def department_summary() -> list[Department]:
    """Headcount, courses and learners per department, for the admin screen."""
    with session():
        staff = repo.list_staff(active_only=True)
        courses = course_repo.list_courses()
    result: list[Department] = []
    for name in DEPARTMENTS:
        areas = areas_in(name)
        dept_courses = [c for c in courses if c.curriculum_area in areas]
        result.append(Department(
            name=name,
            curriculum_areas=areas,
            staff_count=sum(1 for s in staff if s.department == name),
            course_count=len(dept_courses),
            student_count=sum(c.enrolled for c in dept_courses),
        ))
    return result


def workloads(department: str | None = None) -> list[Workload]:
    return repo.workloads(department)


def workload_summary(department: str | None = None) -> dict[str, float | int]:
    return summarise_workload(repo.workloads(department))


def availability(staff_id: str) -> Availability:
    return repo.get_availability(staff_id)


# ── Commands ────────────────────────────────────────────────────────────────

def create(member: Staff) -> Staff:
    return repo.create(member)


def update(member: Staff) -> Staff:
    return repo.update(member)


def delete(staff_id: str) -> bool:
    """Remove a staff record outright.

    Prefer :func:`mark_leaver` — deleting loses the history of who taught and
    marked what, whereas a leaver keeps it and drops out of every picker.
    """
    return repo.delete(staff_id)


def mark_leaver(staff_id: str, on: date | None = None) -> Staff:
    with session():
        member = repo.get(staff_id)
        if member is None:
            raise ValidationError(f"No staff member with ID {staff_id}")
        member.employment_status = "Left"
        member.end_date = on or date.today()
        return repo.update(member)


def set_availability(staff_id: str, blocked: list[tuple[str, str]],
                     reason: str = "") -> Availability:
    """Replace a member of staff's blocked slots."""
    av = Availability(staff_id=staff_id, reason=reason)
    for day, period in blocked:
        av.block(day, period, reason)
    repo.save_availability(av)
    return av


def unassigned_teaching() -> list[str]:
    """Courses with no course leader — the gap a curriculum manager fills."""
    return [
        c.course_id for c in course_repo.list_courses()
        if not c.course_leader and c.status in ("recruiting", "running")
    ]


def sampling_shortfalls() -> list[tuple[Staff, int, int, int]]:
    """Assessors whose marking is under-sampled by internal verification.

    Returns ``(staff, marked, verified, shortfall)`` for anyone short of the
    20% rule — the quality manager's action list.
    """
    from education_system.systems.fe_college.domain.teaching.feedback import (
        sampling_shortfall,
    )

    rows: list[tuple[Staff, int, int, int]] = []
    with session():
        for member in repo.list_staff(active_only=True, teaching_only=True):
            marked, verified = assessment_repo.verification_counts(member.staff_id)
            short = sampling_shortfall(marked, verified)
            if short:
                rows.append((member, marked, verified, short))
    return sorted(rows, key=lambda r: r[3], reverse=True)


__all__ = [
    "StaffProfile",
    "availability",
    "create",
    "delete",
    "department_summary",
    "departments",
    "find_by_email",
    "get",
    "mark_leaver",
    "next_reference",
    "profile",
    "sampling_shortfalls",
    "search",
    "set_availability",
    "teaching_staff",
    "unassigned_teaching",
    "update",
    "workload_summary",
    "workloads",
]
