"""A learner's assignments — what is set, what is due, and handing it in.

Hand-in here records that work was submitted; it does not upload a file. That
is deliberate — the file store exists (``FE_COLLEGE_SUBMISSIONS_DIR``) but a
desktop file picker writing into it is a separate piece of work, and recording
the hand-in is what the marking queue and the deadline tracking need.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "My assignments"


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
            "Everything set on your courses, with what you have handed in and "
            "what you were given for it.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.student_id:
            w.empty_state(parent, "Your account is not linked to a learner record.")
            return

        self.summary_holder = ttk.Frame(parent)
        self.summary_holder.pack(fill="x")

        self.filters = w.FilterBar(
            parent, self.refresh, search=False,
            filters=[("course_id", "Course",
                      [c.course_id for c in self.ctl.my_courses()])],
        )

        self.table = w.DataTable(parent, [
            ("title", "Assignment", 250),
            ("course", "Course", 90),
            ("unit", "Unit", 65),
            ("due", "Due", 100),
            ("days", "Days left", 75, "e"),
            ("status", "My status", 130),
            ("grade", "Grade", 105),
            ("criteria", "Criteria", 120),
        ], on_double_click=lambda _a: self.view())

        w.button_bar(parent, [
            ("View brief & feedback", self.view),
            ("Hand in", self.submit),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            assignments = self.ctl.assessment.list_assignments(
                student_id=self.ctl.student_id, **self.filters.values()
            )
            submissions = {
                s.assignment_id: s
                for s in self.ctl.assessment.submissions_for(self.ctl.student_id)
            }
        except Exception as exc:
            logger.exception("Could not load FE College learner assignments")
            w.error(self.host, TITLE, f"Could not load your assignments: {exc}")
            return

        # Drafts belong to the lecturer until issued — a learner should not see
        # an assignment that has not been set yet.
        assignments = [a for a in assignments if a.status != "draft"]

        rows = []
        for a in assignments:
            submission = submissions.get(a.assignment_id)
            status = submission.status.replace("_", " ") if submission else "not handed in"
            handed_in = submission is not None and submission.status not in (
                "not_submitted", "not_attempted"
            )
            rows.append({
                "title": a.title,
                "course": a.course_id,
                "unit": a.unit_id or "—",
                "due": w.when(a.due_date),
                "days": a.days_remaining() if a.days_remaining() is not None else "—",
                "status": status,
                "grade": (submission.grade if submission and submission.grade else "—"),
                "criteria": a.criteria or "—",
                "_tone": (
                    "good" if submission and submission.grade
                    and submission.grade != "Referred"
                    else "bad" if (a.is_overdue() and not handed_in)
                    or (submission and submission.status == "referred")
                    else "warn" if not handed_in
                    else "plain"
                ),
                "_obj": (a, submission),
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "assignment")
        self._summary(assignments, submissions)

    def _summary(self, assignments, submissions) -> None:
        w.clear(self.summary_holder)
        issued = [a for a in assignments if a.status == "issued"]
        outstanding = [
            a for a in issued
            if a.assignment_id not in submissions
            or submissions[a.assignment_id].status in ("not_submitted", "referred")
        ]
        overdue = [a for a in outstanding if a.is_overdue()]
        graded = [s for s in submissions.values() if s.grade]

        w.kpi_row(self.summary_holder, [
            ("Set", str(len(assignments)), "on your courses", "plain"),
            ("Outstanding", str(len(outstanding)),
             f"{len(overdue)} overdue",
             "bad" if overdue else "warn" if outstanding else "good"),
            ("Graded", str(len(graded)), "marked and returned", "good"),
        ])
        self.host.set_status(
            f"{len(outstanding)} outstanding · {len(overdue)} overdue"
        )

    # ── Actions ────────────────────────────────────────────────────────────

    def view(self) -> None:
        selected = self.table.require_selection("an assignment")
        if selected is None:
            return
        assignment, submission = selected

        lines = [
            assignment.title,
            "=" * 64,
            f"Course   : {assignment.course_id}",
            f"Unit     : {assignment.unit_id or '—'}",
            f"Handed out: {w.when(assignment.issue_date)}",
            f"Hand in by: {w.when(assignment.due_date)}",
            f"Criteria : {', '.join(assignment.criteria_list) or '—'}",
            f"Marks    : out of {assignment.max_marks}",
            "",
            "Brief",
            "-" * 64,
            assignment.brief or "  (no brief written)",
            "",
            "My submission",
            "-" * 64,
        ]
        if submission is None or submission.status == "not_submitted":
            lines.append("  Not handed in yet.")
            if assignment.is_overdue():
                lines.append("  This is past its hand-in date.")
        else:
            lines += [
                f"  Status      : {submission.status.replace('_', ' ')}",
                f"  Handed in   : {w.when(submission.submitted_at)}",
                f"  Grade       : {submission.grade or 'not yet marked'}",
                f"  Marks       : "
                f"{submission.marks if submission.marks is not None else '—'}",
            ]
            if submission.is_capped:
                lines.append(
                    "  This is a resubmission, so it is capped at a Pass."
                )
            if submission.status == "referred":
                lines += [
                    "",
                    "  Your work was referred — you may resubmit once, by "
                    f"{w.when(assignment.resubmission_deadline)}.",
                ]
            if submission.feedback:
                lines += ["", "Feedback", "-" * 64, f"  {submission.feedback}"]
            if submission.submission_id:
                for item in self.ctl.assessment.feedback_for(submission.submission_id):
                    lines += [
                        f"  [{item.feedback_type}] {w.when(item.given_at)}",
                        f"    {item.body}",
                    ]
                    if item.improvements:
                        lines.append(f"    To improve: {item.improvements}")
        w.show_text(self.host, assignment.title, "\n".join(lines))

    def submit(self) -> None:
        selected = self.table.require_selection("an assignment")
        if selected is None:
            return
        assignment, submission = selected

        if assignment.status != "issued":
            w.info(self.host, "Hand in",
                   "That assignment is not open for hand-ins.")
            return
        if submission is not None and submission.grade and submission.status != "referred":
            w.info(self.host, "Hand in",
                   "That has already been marked — nothing more to hand in.")
            return

        resubmission = submission is not None and submission.status == "referred"
        note = (
            "This is a resubmission. Awarding-body rules cap a resubmitted "
            "piece of work at a Pass.\n\n"
            if resubmission else ""
        )
        if assignment.is_overdue() and not resubmission:
            note += (
                "This is past its hand-in date, so it will be recorded as "
                "late.\n\n"
            )
        if not w.confirm(
            self.host, "Hand in",
            f"{note}Record that you have handed in '{assignment.title}'?",
        ):
            return

        try:
            self.ctl.assessment.submit(
                assignment.assignment_id, self.ctl.student_id, on=date.today()
            )
        except ValidationError as exc:
            w.error(self.host, "Hand in", str(exc))
            return
        self.refresh()
        self.host.set_status(f"Handed in: {assignment.title}")


__all__ = ["TITLE", "Screen", "open_window"]
