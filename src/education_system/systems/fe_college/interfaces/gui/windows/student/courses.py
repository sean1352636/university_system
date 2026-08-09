"""A learner's courses and their progress through each one's units.

Credit progress is the useful number here: on a unit-based qualification it is
what says whether the learner is on course to be awarded, and it makes the
distinction between passing units and passing the *mandatory* units visible.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My courses"


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "What you are enrolled on, and how far through each one you are.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.holder = ttk.Frame(parent)
        self.holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self) -> None:
        w.clear(self.holder)
        try:
            profile = self.ctl.students.profile(self.ctl.student_id)
        except Exception as exc:
            logger.exception("Could not load FE College learner courses")
            w.error(self.host, TITLE, f"Could not load your courses: {exc}")
            return

        if profile is None:
            w.empty_state(self.holder, "Your learner record could not be found.")
            return

        active = [e for e in profile.enrolments if e.is_active]
        if not active:
            w.empty_state(
                self.holder,
                "You are not enrolled on any courses yet. If that looks wrong, "
                "talk to college administration.",
            )
            return

        inner, _canvas = w.scrollable(self.holder)
        for enrolment in active:
            self._course_panel(inner, enrolment)

        past = [e for e in profile.enrolments if not e.is_active]
        if past:
            panel = ttk.LabelFrame(inner, text="Previous enrolments", padding=8)
            panel.pack(fill="x", pady=(4, 8))
            table = w.DataTable(panel, [
                ("course", "Course", 110),
                ("year", "Year", 90),
                ("status", "Status", 110),
                ("grade", "Grade", 110),
                ("reason", "Reason", 240),
            ], height=min(6, len(past)))
            table.set_rows([
                {
                    "course": e.course_id,
                    "year": e.academic_year,
                    "status": e.status,
                    "grade": e.final_grade or "—",
                    "reason": e.withdrawal_reason or "—",
                    "_tone": "muted",
                }
                for e in past
            ])

        self.host.set_status(f"{len(active)} active course(s)")

    def _course_panel(self, parent, enrolment) -> None:
        course = self.ctl.courses.get(enrolment.course_id)
        if course is None:
            return

        panel = ttk.LabelFrame(
            parent, text=f"{course.title}  ({course.course_id})", padding=10)
        panel.pack(fill="x", pady=(0, 12))

        attendance = self.ctl.attendance.for_student(
            self.ctl.student_id, course_id=course.course_id
        )
        progress = self.ctl.courses.learner_credit(
            self.ctl.student_id, course.course_id
        )

        top = ttk.Frame(panel)
        top.pack(fill="x")
        top.columnconfigure(0, weight=1, uniform="cp")
        top.columnconfigure(1, weight=1, uniform="cp")

        w.kv_panel(top, "Course", [
            ("Qualification", f"{course.qualification_type} (Level {course.level})"),
            ("Awarding body", course.awarding_body or "—"),
            ("Mode", course.mode_of_study),
            ("Runs", f"{w.when(course.start_date)} → {w.when(course.end_date)}"),
            ("This is your", "main aim" if enrolment.is_main_aim else "additional aim"),
        ]).grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        credit_line = (
            f"{progress.credits_achieved} of {progress.credits_required}"
            if progress.credits_required else "—"
        )
        outstanding = (
            ", ".join(progress.mandatory_outstanding)
            if progress.mandatory_outstanding else "none"
        )
        w.kv_panel(top, "My progress", [
            ("Attendance", w.pct(attendance.attendance_pct),
             w.tone_for(attendance.band)),
            ("Credits achieved", credit_line),
            ("Credit progress", w.pct(progress.pct)),
            ("Mandatory units outstanding", outstanding,
             "warn" if progress.mandatory_outstanding else "good"),
            ("Ready to be awarded", w.yes_no(progress.can_be_awarded),
             "good" if progress.can_be_awarded else "plain"),
        ]).grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        units = self.ctl.courses.units(course.course_id)
        if not units:
            return
        grades = {
            s.assignment_id: s
            for s in self.ctl.assessment.submissions_for(self.ctl.student_id)
        }
        assignments = self.ctl.assessment.list_assignments(course_id=course.course_id)
        unit_grades: dict[str, str] = {}
        for assignment in assignments:
            submission = grades.get(assignment.assignment_id)
            if submission and submission.grade and assignment.unit_id:
                unit_grades[assignment.unit_id] = submission.grade

        table = w.DataTable(panel, [
            ("code", "Unit", 70),
            ("title", "Title", 280),
            ("type", "Type", 95),
            ("credits", "Credits", 65, "e"),
            ("method", "Assessed by", 170),
            ("grade", "My grade", 110),
        ], height=min(8, len(units)))
        table.set_rows([
            {
                "code": u.unit_id,
                "title": u.title,
                "type": u.unit_type,
                "credits": u.credits,
                "method": u.assessment_method,
                "grade": unit_grades.get(u.unit_id, "not yet graded"),
                "_tone": (
                    "good" if u.unit_id in unit_grades
                    else "warn" if u.is_mandatory else "plain"
                ),
            }
            for u in units
        ])


__all__ = ["TITLE", "Screen", "open_window"]
