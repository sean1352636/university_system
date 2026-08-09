"""A learner's results — unit grades, exam results and credit progress.

Also carries the post-results services, because a learner who wants a review of
marking has a hard deadline from results day and the system knows what it is.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.fe_college.domain.exams.results import (
    POST_RESULT_SERVICES,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My results"


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
            "Grades awarded for your work, exam results, and how much credit "
            "you have towards each qualification.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.summary_holder = ttk.Frame(parent)
        self.summary_holder.pack(fill="x")

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, pady=(4, 0))
        self.work_tab = ttk.Frame(notebook, padding=8)
        self.exams_tab = ttk.Frame(notebook, padding=8)
        self.credit_tab = ttk.Frame(notebook, padding=8)
        notebook.add(self.work_tab, text="Coursework")
        notebook.add(self.exams_tab, text="Exams")
        notebook.add(self.credit_tab, text="Credit progress")
        self.refresh()

    def refresh(self) -> None:
        try:
            self._summary()
            self._coursework()
            self._exams()
            self._credit()
        except Exception as exc:
            logger.exception("Could not load FE College learner results")
            w.error(self.host, TITLE, f"Could not load your results: {exc}")

    # ── Panels ─────────────────────────────────────────────────────────────

    def _summary(self) -> None:
        w.clear(self.summary_holder)
        stats = self.ctl.reports.student_stats(self.ctl.student_id)
        w.kpi_row(self.summary_holder, [
            ("Grades awarded", str(stats.grades_awarded), "so far this year", "plain"),
            ("Pass rate", w.pct(stats.pass_rate),
             "of the work that has been marked",
             "good" if (stats.pass_rate or 0) >= 90 else "warn"),
            ("Credits", f"{stats.credits_achieved}/{stats.credits_required}"
             if stats.credits_required else "—",
             "towards your qualification(s)", "plain"),
        ])
        self.host.set_status(
            f"{stats.grades_awarded} grade(s) · {w.pct(stats.pass_rate)} passed"
        )

    def _coursework(self) -> None:
        w.clear(self.work_tab)
        submissions = self.ctl.assessment.submissions_for(self.ctl.student_id)
        graded = [s for s in submissions if s.grade]
        if not graded:
            w.empty_state(self.work_tab, "Nothing of yours has been marked yet.")
            return

        assignments = {
            a.assignment_id: a
            for a in self.ctl.assessment.list_assignments(student_id=self.ctl.student_id)
        }
        table = w.DataTable(self.work_tab, [
            ("assignment", "Assignment", 260),
            ("course", "Course", 95),
            ("unit", "Unit", 65),
            ("marked", "Marked on", 100),
            ("grade", "Grade", 110),
            ("marks", "Marks", 90, "e"),
            ("capped", "Resubmission", 105),
        ], height=16)
        table.set_rows([
            {
                "assignment": (
                    assignments[s.assignment_id].title
                    if s.assignment_id in assignments else f"#{s.assignment_id}"
                ),
                "course": (
                    assignments[s.assignment_id].course_id
                    if s.assignment_id in assignments else "—"
                ),
                "unit": (
                    assignments[s.assignment_id].unit_id or "—"
                    if s.assignment_id in assignments else "—"
                ),
                "marked": w.when(s.marked_at),
                "grade": s.grade,
                "marks": (
                    f"{s.marks}/{assignments[s.assignment_id].max_marks}"
                    if s.marks is not None and s.assignment_id in assignments
                    else "—"
                ),
                "capped": w.yes_no(s.is_capped),
                "_tone": "bad" if s.grade == "Referred" else "good",
            }
            for s in graded
        ])

    def _exams(self) -> None:
        w.clear(self.exams_tab)
        results = self.ctl.assessment.results_for(self.ctl.student_id)
        entries = self.ctl.assessment.entries(student_id=self.ctl.student_id)

        if entries:
            panel = ttk.LabelFrame(self.exams_tab, text="Entries", padding=8)
            panel.pack(fill="x", pady=(0, 8))
            table = w.DataTable(panel, [
                ("candidate", "Candidate no.", 120),
                ("status", "Status", 110),
                ("type", "Entry type", 120),
                ("entered", "Entered on", 105),
                ("seat", "Seat", 80),
            ], height=min(6, len(entries)))
            table.set_rows([
                {
                    "candidate": e.candidate_number or "—",
                    "status": e.status.replace("_", " "),
                    "type": e.entry_type,
                    "entered": w.when(e.entered_on),
                    "seat": e.seat_number or "—",
                    "_tone": "good" if e.is_active else "muted",
                }
                for e in entries
            ])

        if not results:
            w.empty_state(self.exams_tab, "No exam results have been released yet.")
            return

        panel = ttk.LabelFrame(self.exams_tab, text="Results", padding=8)
        panel.pack(fill="both", expand=True)
        table = w.DataTable(panel, [
            ("unit", "Unit", 100),
            ("grade", "Grade", 100),
            ("marks", "Marks", 80, "e"),
            ("ums", "UMS", 70, "e"),
            ("status", "Status", 110),
            ("released", "Released", 100),
            ("review", "Review by", 110),
        ], height=10)
        table.set_rows([
            {
                "unit": r.unit_id,
                "grade": r.grade or "—",
                "marks": r.marks if r.marks is not None else "—",
                "ums": r.ums if r.ums is not None else "—",
                "status": r.status.replace("_", " "),
                "released": w.when(r.released_on),
                "review": w.when(r.review_deadline()),
                "_tone": "good" if r.achieved else "warn",
                "_obj": r,
            }
            for r in results
        ])
        self.results_table = table
        w.button_bar(panel, [
            ("Post-results services", self.post_results),
        ])

    def _credit(self) -> None:
        w.clear(self.credit_tab)
        profile = self.ctl.students.profile(self.ctl.student_id)
        active = [e for e in profile.enrolments if e.is_active] if profile else []
        if not active:
            w.empty_state(self.credit_tab, "You have no active enrolments.")
            return

        for enrolment in active:
            course = self.ctl.courses.get(enrolment.course_id)
            progress = self.ctl.courses.learner_credit(
                self.ctl.student_id, enrolment.course_id
            )
            panel = ttk.LabelFrame(
                self.credit_tab,
                text=course.title if course else enrolment.course_id, padding=10,
            )
            panel.pack(fill="x", pady=(0, 8))

            if progress.credits_required:
                bar = ttk.Progressbar(panel, maximum=progress.credits_required,
                                      length=320)
                bar["value"] = min(progress.credits_achieved, progress.credits_required)
                bar.pack(anchor="w", pady=(0, 6))

            w.kv_panel(panel, "", [
                ("Credits achieved",
                 f"{progress.credits_achieved} of {progress.credits_required}"),
                ("Progress", w.pct(progress.pct)),
                ("Mandatory units outstanding",
                 ", ".join(progress.mandatory_outstanding) or "none",
                 "warn" if progress.mandatory_outstanding else "good"),
                ("Ready to be awarded", w.yes_no(progress.can_be_awarded),
                 "good" if progress.can_be_awarded else "plain"),
            ]).pack(fill="x")

    # ── Actions ────────────────────────────────────────────────────────────

    def post_results(self) -> None:
        result_row = self.results_table.require_selection("a result")
        if result_row is None:
            return
        available = [
            service for service in POST_RESULT_SERVICES
            if result_row.can_request(service)
        ]
        if not available:
            w.info(
                self.host, "Post-results services",
                "The deadline for requesting a review or a copy of your script "
                f"has passed (results were released {w.when(result_row.released_on)}).",
            )
            return
        lines = [
            f"Unit {result_row.unit_id} — grade {result_row.grade or '—'}",
            f"Released {w.when(result_row.released_on)}",
            "",
            "You can still request:",
        ]
        lines += [
            f"  • {service} — by {w.when(result_row.review_deadline(service))}"
            for service in available
        ]
        lines += [
            "",
            "Requests go through the exams officer. Speak to Student Services "
            "or your course leader to start one — a review can lower a grade as "
            "well as raise it, so they will talk it through with you first.",
        ]
        w.show_text(self.host, "Post-results services", "\n".join(lines),
                    width=76, height=16)


__all__ = ["TITLE", "Screen", "open_window"]
