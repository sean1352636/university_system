"""Timetable commands — viewing grids, placing sessions, finding rooms."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import ROOM_TYPES
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.timetable import Session
from education_system.systems.fe_college.interfaces.cli import shell as sh


def _print(timetable, ctl) -> None:
    """Print a timetable as the shared text grid."""
    print()
    print(ctl.timetable.as_text(timetable))


def college(ctl) -> None:
    """The whole college's weekly grid."""
    sh.header("College timetable")
    _print(ctl.timetable.whole_college(), ctl)


def by_course(ctl) -> None:
    """One course's weekly grid."""
    courses = ctl.courses.list_all()
    if not courses:
        sh.note("No courses have been set up.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    if course is sh.CANCEL:
        return
    _print(ctl.timetable.for_course(course.course_id), ctl)


def by_staff(ctl) -> None:
    """One member of staff's weekly grid."""
    staff = ctl.staff.teaching_staff()
    if not staff:
        sh.note("No teaching staff on record.")
        return
    member = sh.choose_object(
        "Staff member", staff, lambda s: f"{s.staff_id} — {s.full_name}"
    )
    if member is sh.CANCEL:
        return
    _print(ctl.timetable.for_staff(member.staff_id), ctl)


def mine(ctl) -> None:
    """The signed-in user's own timetable, whichever view they are in."""
    if ctl.identity.is_student and ctl.student_id:
        _print(ctl.timetable.for_student(ctl.student_id), ctl)
        return
    if ctl.staff_id:
        timetable = ctl.timetable.for_staff(ctl.staff_id)
        _print(timetable, ctl)
        workload = next(
            (wl for wl in ctl.staff.workloads() if wl.staff_id == ctl.staff_id), None
        )
        if workload:
            sh.key_values([
                ("Assigned", f"{workload.assigned_hours:g}h of "
                             f"{workload.contracted_hours:g}h contracted"),
                ("Load", workload.band),
            ])
        return
    sh.note("Your account is not linked to a staff or learner record.")


def add_session(ctl) -> None:
    """Place a session in the grid, refusing a clash."""
    courses = ctl.courses.list_all()
    if not courses:
        sh.note("No courses have been set up.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    if course is sh.CANCEL:
        return

    teachers = ctl.staff.teaching_staff()
    teacher = sh.choose_object(
        "Teacher", teachers, lambda s: f"{s.staff_id} — {s.full_name}"
    ) if teachers else sh.CANCEL
    teacher_id = "" if teacher is sh.CANCEL else teacher.staff_id

    rooms = ctl.timetable.rooms(bookable_only=True)
    room = sh.choose_object(
        "Room", rooms, lambda r: r.display_name
    ) if rooms else sh.CANCEL
    room_id = "" if room is sh.CANCEL else room.room_id

    groups = ctl.courses.groups(course.course_id)
    group = sh.choose_object(
        "Class group", groups, lambda g: f"{g.group_id} — {g.name}"
    ) if groups else sh.CANCEL
    group_id = "" if group is sh.CANCEL else group.group_id

    # Offer slots that are already known to be free, rather than making the
    # user guess and be told no.
    suggestions = ctl.timetable.suggest_slots(
        course.course_id, teacher_id=teacher_id, room_id=room_id, limit=10
    )
    if suggestions:
        sh.note("Slots with no clash:")
        picked = sh.choose(
            "Slot", [f"{day} {period}" for day, period in suggestions]
        )
        if picked is sh.CANCEL:
            return
        day, period = picked.split(" ")
    else:
        sh.warn("No clash-free slot was found — choose one anyway.")
        day = sh.choose("Day", list(ctl.timetable.days()[:6]))
        if day is sh.CANCEL:
            return
        period = sh.choose("Period", list(ctl.timetable.period_codes()))
        if period is sh.CANCEL:
            return

    session = Session(
        session_id=None,
        course_id=course.course_id,
        group_id=group_id,
        teacher_id=teacher_id,
        room_id=room_id,
        day=day,
        period=period,
        academic_year=ctl.academic_year,
    )
    clashes = ctl.timetable.check_clashes(session)
    if clashes:
        sh.warn("That slot clashes:")
        sh.bullet_list(clashes)
        if not sh.confirm("Place it anyway?"):
            return

    try:
        ctl.timetable.place(session, force=bool(clashes))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"{course.course_id} placed in {day} {period}")


def remove_session(ctl) -> None:
    """Take a session out of the grid."""
    courses = ctl.courses.list_all()
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    ) if courses else sh.CANCEL
    if course is sh.CANCEL:
        return

    from education_system.systems.fe_college.infrastructure.persistence.repositories import (
        timetable_repository,
    )
    sessions = timetable_repository.list_sessions(course_id=course.course_id)
    if not sessions:
        sh.note("That course has no timetabled sessions.")
        return

    session = sh.choose_object(
        "Session", sessions,
        lambda s: f"{s.label} · group {s.group_id or '—'} · room {s.room_id or '—'}",
    )
    if session is sh.CANCEL:
        return
    if not sh.confirm(f"Remove {course.course_id} from {session.label}?"):
        return
    ctl.timetable.remove(session.session_id)
    sh.success("Session removed.")


def rooms(ctl) -> None:
    """List rooms."""
    sh.header("Rooms")
    sh.table(
        [("id", "Code"), ("name", "Name"), ("type", "Type"),
         ("capacity", "Capacity"), ("building", "Building"),
         ("status", "Status"), ("access", "Accessible")],
        [
            {"id": r.room_id, "name": r.name, "type": r.room_type,
             "capacity": r.capacity, "building": r.building,
             "status": r.status, "access": r.is_accessible}
            for r in ctl.timetable.rooms()
        ],
        empty="No rooms on record.",
    )


def free_rooms(ctl) -> None:
    """Find a free room in a slot."""
    day = sh.choose("Day", list(ctl.timetable.days()[:6]))
    if day is sh.CANCEL:
        return
    period = sh.choose("Period", list(ctl.timetable.period_codes()))
    if period is sh.CANCEL:
        return
    capacity = sh.ask_int("Minimum capacity", 0)
    if capacity is sh.CANCEL:
        return
    room_type = sh.choose("Room type", ["any", *ROOM_TYPES])
    if room_type is sh.CANCEL:
        return

    free = ctl.timetable.free_rooms(
        day, period, min_capacity=capacity,
        room_type=None if room_type == "any" else room_type,
    )
    sh.header(f"Free rooms — {day} {period}")
    sh.table(
        [("id", "Code"), ("name", "Name"), ("type", "Type"), ("capacity", "Capacity")],
        [{"id": r.room_id, "name": r.name, "type": r.room_type,
          "capacity": r.capacity} for r in free],
        empty="Nothing free that matches.",
    )


def lesson_plans(ctl) -> None:
    """A lecturer's lesson plans."""
    if not ctl.staff_id:
        sh.note("Your account is not linked to a staff record.")
        return
    sh.header("My lesson plans")
    plans = ctl.timetable.lesson_plans(teacher_id=ctl.staff_id)
    sh.table(
        [("title", "Plan"), ("course", "Course"), ("group", "Group"),
         ("unit", "Unit"), ("date", "Date"), ("status", "Status")],
        [
            {"title": p.title, "course": p.course_id, "group": p.group_id,
             "unit": p.unit_id, "date": p.lesson_date, "status": p.status}
            for p in plans
        ],
        empty="You have no lesson plans.",
    )
    if not plans:
        return
    if not sh.confirm("Read one?"):
        return
    plan = sh.choose_object("Plan", plans, lambda p: f"{p.course_id} · {p.title}")
    if plan is sh.CANCEL:
        return

    sh.header(plan.title, f"{plan.course_id} · {plan.status}")
    for heading, body in (
        ("Learning objectives", plan.objectives),
        ("Activities", plan.activities),
        ("Differentiation", plan.differentiation),
        ("Assessment", plan.assessment),
        ("Resources", plan.resources),
        ("Homework", plan.homework),
        ("Evaluation", plan.evaluation),
    ):
        if body:
            sh.section(heading)
            sh.note(body)


__all__ = [
    "add_session", "by_course", "by_staff", "college", "free_rooms",
    "lesson_plans", "mine", "remove_session", "rooms",
]
