"""Attendance commands — taking registers and reading the rates back."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import ATTENDANCE_MARKS
from education_system.systems.fe_college.domain.students.attendance import MARK_LABELS
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.cli import shell as sh

# Single-letter entry, matching the GUI's register shortcuts.
KEYS = {
    "p": "present",
    "l": "late",
    "a": "authorised",
    "u": "unauthorised",
    "e": "excused",
}


def take_register(ctl) -> None:
    """Walk a class list, one learner at a time.

    Enter steps past a learner leaving them present, which is what makes a
    thirty-name register bearable: only the exceptions need a keystroke.
    """
    courses = ctl.my_courses()
    if not courses:
        sh.note("You are not assigned to any courses.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    if course is sh.CANCEL:
        return

    on = sh.ask_date("Date", date.today(), allow_blank=False)
    if on is sh.CANCEL:
        return
    period = sh.choose("Period", ["(none)", *ctl.timetable.period_codes()])
    if period is sh.CANCEL:
        return
    period = "" if period == "(none)" else period

    try:
        register = ctl.attendance.build_register(course.course_id, on, period)
    except ValidationError as exc:
        sh.error(str(exc))
        return

    if not register.rows:
        sh.note("Nobody is enrolled on that course.")
        return

    sh.header(
        f"Register — {register.course_title}",
        f"{register.session_date} {period}".strip()
        + ("  (already taken — showing what was recorded)"
           if register.already_taken else ""),
    )
    sh.note("Enter = leave as is · p present · l late · a authorised · "
            "u unauthorised · e excused · q finish early")

    for i, row in enumerate(register.rows, 1):
        rate = sh.pct(row.attendance_pct)
        flag = "  ⚠ at risk" if (
            row.attendance_pct is not None and row.attendance_pct < 75
        ) else ""
        answer = sh.prompt(
            f"{i:2d}/{len(register.rows)} {row.student.full_name:<28} "
            f"[{rate:>6}]{flag}  {row.mark}"
        )
        if answer is sh.CANCEL:
            sh.note("Cancelled — nothing saved.")
            return
        answer = answer.strip().lower()
        if answer == "q":
            break
        if not answer:
            continue
        if answer in KEYS:
            row.mark = KEYS[answer]
            if row.mark == "late":
                minutes = sh.ask_int("   Minutes late", 5)
                row.minutes_late = 0 if minutes is sh.CANCEL else minutes
            else:
                row.minutes_late = 0
        elif answer in ATTENDANCE_MARKS:
            row.mark = answer
        else:
            sh.warn(f"'{answer}' is not a mark — left as {row.mark}")

    present = register.present_count
    sh.blank()
    sh.note(f"{present} of {len(register.rows)} attending.")
    if not sh.confirm("Save this register?", default=True):
        sh.note("Not saved.")
        return

    try:
        written = ctl.attendance.save_register(register, recorded_by=ctl.staff_id)
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Saved {written} mark(s) for {course.course_id} on {on}")


def by_course(ctl) -> None:
    """Attendance per course, worst first."""
    sh.header("Attendance by course")
    rows = ctl.reports.attendance_report()
    sh.table(
        [("course_id", "Code"), ("title", "Title"), ("sessions", "Sessions"),
         ("attendance_pct", "Attendance"), ("punctuality_pct", "Punctuality"),
         ("unauthorised", "Unauth."), ("band", "Band")],
        [
            {**r,
             "attendance_pct": sh.pct(r["attendance_pct"]),
             "punctuality_pct": sh.pct(r["punctuality_pct"])}
            for r in rows
        ],
        empty="No registers have been taken.",
    )


def by_learner(ctl) -> None:
    """Attendance per learner on one course."""
    courses = ctl.courses.list_all()
    if not courses:
        sh.note("No courses have been set up.")
        return
    course = sh.choose_object(
        "Course", courses, lambda c: f"{c.course_id} — {c.title}"
    )
    if course is sh.CANCEL:
        return

    sh.header(f"Attendance — {course.title}")
    rows = ctl.attendance.by_student(course_id=course.course_id)
    sh.table(
        [("id", "ID"), ("name", "Name"), ("attendance", "Attendance"),
         ("punctuality", "Punctuality"), ("sessions", "Sessions"),
         ("unauth", "Unauth."), ("band", "Band")],
        [
            {
                "id": learner.student_id,
                "name": learner.full_name,
                "attendance": sh.pct(summary.attendance_pct),
                "punctuality": sh.pct(summary.punctuality_pct),
                "sessions": summary.total,
                "unauth": summary.unauthorised,
                "band": summary.band,
            }
            for learner, summary in rows
        ],
        empty="No registers taken for that course.",
        limit=50,
    )


def trend(ctl) -> None:
    """Attendance week by week."""
    courses = ctl.courses.list_all()
    course = sh.choose_object(
        "Course (or cancel for the whole college)", courses,
        lambda c: f"{c.course_id} — {c.title}",
    ) if courses else sh.CANCEL
    course_id = None if course is sh.CANCEL else course.course_id

    sh.header("Attendance trend",
              course_id or "Whole college, last eight weeks.")
    rows = ctl.attendance.weekly_trend(course_id, weeks=8)
    sh.table(
        [("week", "Week beginning"), ("attendance", "Attendance"), ("bar", "")],
        [
            {
                "week": week,
                "attendance": sh.pct(value),
                # A coarse bar makes the shape obvious without a chart.
                "bar": "█" * int((value or 0) / 5) if value is not None else "",
            }
            for week, value in rows
        ],
        empty="No attendance recorded.",
    )


def my_attendance(ctl) -> None:
    """A learner's own attendance."""
    if not ctl.student_id:
        sh.note("Your account is not linked to a learner record.")
        return

    summary = ctl.attendance.for_student(ctl.student_id)
    sh.header("My attendance", f"{summary.band}")
    sh.key_values([
        ("Attendance", sh.pct(summary.attendance_pct)),
        ("Punctuality", sh.pct(summary.punctuality_pct)),
        ("Sessions attended", f"{summary.attended} of {summary.total - summary.excused}"),
        ("Authorised absences", summary.authorised),
        ("Unauthorised absences", summary.unauthorised),
        ("Late arrivals", summary.late),
    ])

    profile = ctl.students.profile(ctl.student_id)
    if profile:
        # One summary per course, reused for all three columns — querying the
        # same figure three times per row is a habit that gets expensive fast.
        per_course = [
            (e.course_id,
             ctl.attendance.for_student(ctl.student_id, course_id=e.course_id))
            for e in profile.enrolments if e.is_active
        ]
        sh.section("By course")
        sh.table(
            [("course", "Course"), ("attendance", "Attendance"),
             ("sessions", "Sessions"), ("band", "Band")],
            [
                {
                    "course": course_id,
                    "attendance": sh.pct(summary.attendance_pct),
                    "sessions": summary.total,
                    "band": summary.band,
                }
                for course_id, summary in per_course
            ],
            empty="No active courses.",
        )

    from education_system.systems.fe_college.infrastructure.persistence.repositories import (
        attendance_repository,
    )
    recent = attendance_repository.list_marks(student_id=ctl.student_id, limit=20)
    sh.section("Recent sessions")
    sh.table(
        [("date", "Date"), ("course", "Course"), ("period", "Period"),
         ("mark", "Mark"), ("note", "Note")],
        [
            {
                "date": m.session_date,
                "course": m.course_id,
                "period": m.period,
                "mark": MARK_LABELS.get(m.mark, m.mark)
                + (f" ({m.minutes_late} min)" if m.minutes_late else ""),
                "note": m.note,
            }
            for m in recent
        ],
        empty="No marks recorded.",
    )


__all__ = ["by_course", "by_learner", "my_attendance", "take_register", "trend"]
