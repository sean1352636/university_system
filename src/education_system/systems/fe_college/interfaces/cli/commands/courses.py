"""Course commands — the curriculum offer, units and viability."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import (
    ACADEMIC_YEAR,
    CURRICULUM_AREAS,
    MODES_OF_STUDY,
    QUALIFICATION_LEVELS,
    QUALIFICATION_TYPES,
)
from education_system.systems.fe_college.domain.courses.models import (
    COURSE_STATUSES,
    Course,
)
from education_system.systems.fe_college.domain.courses.modules import (
    ASSESSMENT_METHODS,
    UNIT_TYPES,
    Unit,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.cli import shell as sh


def catalogue(ctl) -> None:
    """The whole offer, grouped by curriculum area."""
    sh.header("Courses", f"The offer for {ctl.academic_year}.")
    grouped = ctl.courses.by_area()
    if not grouped:
        sh.note("No courses have been set up.")
        return
    for area, courses in grouped.items():
        sh.section(area)
        sh.table(
            [("code", "Code"), ("title", "Title"), ("qual", "Qualification"),
             ("level", "Lvl"), ("on", "On"), ("cap", "Cap"),
             ("fill", "Filled"), ("status", "Status"), ("viability", "Viability")],
            [
                {
                    "code": c.course_id,
                    "title": c.title,
                    "qual": c.qualification_type,
                    "level": c.level,
                    "on": c.enrolled,
                    "cap": c.capacity or sh.DASH,
                    "fill": sh.pct(c.fill_pct),
                    "status": c.status,
                    "viability": c.viability,
                }
                for c in courses
            ],
        )


def view(ctl) -> None:
    """One course in full, with its units and cohort."""
    course = _pick(ctl)
    if course is None:
        return
    detail = ctl.courses.detail(course.course_id)
    if detail is None:
        sh.error("That course no longer exists.")
        return

    c = detail.course
    sh.header(c.display_name,
              f"{c.qualification_type} (Level {c.level}) · {c.curriculum_area}")
    sh.key_values([
        ("Academic year", c.academic_year),
        ("Awarding body", c.awarding_body),
        ("Department", c.department),
        ("Course leader", c.course_leader),
        ("Mode", f"{c.mode_of_study} · {c.campus}"),
        ("Guided learning hours", c.guided_learning_hours),
        ("Duration", f"{c.duration_weeks} weeks"),
        ("Runs", f"{sh.fmt(c.start_date)} → {sh.fmt(c.end_date)}"),
        ("Enrolled", f"{c.enrolled} of {c.capacity or '∞'} ({c.viability})"),
        ("Attendance", sh.pct(detail.attendance_pct)),
        ("Fee", sh.money(c.fee)),
    ])

    sh.section(f"Units ({detail.total_credits} credits)")
    sh.table(
        [("code", "Code"), ("title", "Unit"), ("type", "Type"),
         ("credits", "Credits"), ("method", "Assessed by")],
        [
            {"code": u.unit_id, "title": u.title, "type": u.unit_type,
             "credits": u.credits, "method": u.assessment_method}
            for u in detail.units
        ],
        empty="No units defined.",
    )

    if detail.entry_requirement:
        r = detail.entry_requirement
        sh.section("Entry requirements")
        sh.key_values([
            ("Minimum age", r.min_age),
            ("Maximum age", r.max_age or "none"),
            ("Prior level", r.min_prior_level or "none"),
            ("GCSE English", r.min_gcse_english or "none"),
            ("GCSE maths", r.min_gcse_maths or "none"),
            ("Interview", r.interview_required),
            ("DBS check", r.dbs_required),
            ("Portfolio", r.portfolio_required),
        ])

    sh.section("Groups")
    sh.table(
        [("id", "Group"), ("name", "Name"), ("teacher", "Teacher"),
         ("members", "Members")],
        [{"id": g.group_id, "name": g.name, "teacher": g.teacher_id,
          "members": g.members} for g in detail.groups],
        empty="No class groups.",
    )


def create(ctl) -> None:
    """Add a course to the offer."""
    sh.header("New course")
    leaders = [s.staff_id for s in ctl.staff.teaching_staff()]
    result = sh.form("Course details", [
        ("course_id", "Course code", "text"),
        ("title", "Title", "text"),
        ("qualification_type", "Qualification", "choice", QUALIFICATION_TYPES),
        ("level", "Level", "choice", QUALIFICATION_LEVELS),
        ("curriculum_area", "Curriculum area", "choice", CURRICULUM_AREAS),
        ("academic_year", "Academic year", "text"),
        ("mode_of_study", "Mode of study", "choice", MODES_OF_STUDY),
        ("status", "Status", "choice", COURSE_STATUSES),
        ("course_leader", "Course leader", "choice", leaders),
        ("awarding_body", "Awarding body", "text"),
        ("guided_learning_hours", "Guided learning hours", "int"),
        ("duration_weeks", "Duration (weeks)", "int"),
        ("capacity", "Capacity", "int"),
        ("start_date", "Start date", "date"),
        ("fee", "Fee (£)", "float"),
    ], initial={"academic_year": ACADEMIC_YEAR, "guided_learning_hours": 1080,
                "duration_weeks": 36, "capacity": 20, "start_date": date.today()})
    if result is sh.CANCEL:
        return

    try:
        created = ctl.courses.create(Course(
            course_id=result["course_id"],
            title=result["title"],
            qualification_type=result["qualification_type"] or QUALIFICATION_TYPES[0],
            level=result["level"] or "3",
            curriculum_area=result["curriculum_area"],
            academic_year=result["academic_year"],
            mode_of_study=result["mode_of_study"] or MODES_OF_STUDY[0],
            status=result["status"] or "recruiting",
            course_leader=result["course_leader"],
            awarding_body=result["awarding_body"],
            guided_learning_hours=result["guided_learning_hours"],
            duration_weeks=result["duration_weeks"],
            capacity=result["capacity"],
            start_date=result["start_date"],
            fee=result["fee"],
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Created {created.display_name}")


def add_unit(ctl) -> None:
    """Add a unit to a course."""
    course = _pick(ctl)
    if course is None:
        return
    result = sh.form(f"New unit on {course.course_id}", [
        ("unit_id", "Unit code", "text"),
        ("title", "Title", "text"),
        ("unit_type", "Type", "choice", UNIT_TYPES),
        ("credits", "Credits", "int"),
        ("guided_learning_hours", "Guided learning hours", "int"),
        ("assessment_method", "Assessment method", "choice", ASSESSMENT_METHODS),
        ("sequence", "Order", "int"),
    ], initial={"credits": 10, "guided_learning_hours": 60, "sequence": 0})
    if result is sh.CANCEL:
        return

    try:
        ctl.courses.add_unit(Unit(
            unit_id=result["unit_id"],
            course_id=course.course_id,
            title=result["title"],
            unit_type=result["unit_type"] or UNIT_TYPES[0],
            credits=result["credits"],
            guided_learning_hours=result["guided_learning_hours"],
            assessment_method=result["assessment_method"] or ASSESSMENT_METHODS[1],
            sequence=result["sequence"],
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Added {result['unit_id']} to {course.course_id}")


def viability(ctl) -> None:
    """Recruitment against capacity, worst first."""
    sh.header("Course viability",
              "Courses recruiting badly are the decisions to take before term.")
    rows = ctl.reports.viability_report()
    sh.table(
        [("course_id", "Code"), ("title", "Title"), ("area", "Area"),
         ("enrolled", "On"), ("capacity", "Cap"), ("fill_pct", "Filled"),
         ("viability", "Viability")],
        [{**r, "fill_pct": sh.pct(r["fill_pct"])} for r in rows],
        empty="No courses to assess.",
    )


def archive(ctl) -> None:
    """Archive or cancel a course."""
    course = _pick(ctl)
    if course is None:
        return
    action = sh.choose(
        "What should happen to it?",
        ["archive — stop enrolments, keep all history",
         f"cancel — withdraw its {course.enrolled} active enrolment(s) too"],
    )
    if action is sh.CANCEL:
        return

    try:
        if action.startswith("archive"):
            ctl.courses.archive(course.course_id)
            sh.success(f"Archived {course.course_id}")
        else:
            if not sh.confirm(
                f"Cancel {course.course_id} and withdraw {course.enrolled} learner(s)?"
            ):
                return
            withdrawn = ctl.courses.cancel(course.course_id)
            sh.success(f"Cancelled {course.course_id}; withdrew {withdrawn} enrolment(s)")
    except ValidationError as exc:
        sh.error(str(exc))


def _pick(ctl):
    courses = ctl.courses.list_all()
    if not courses:
        sh.note("No courses have been set up.")
        return None
    chosen = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    return None if chosen is sh.CANCEL else chosen


__all__ = ["add_unit", "archive", "catalogue", "create", "view", "viability"]
