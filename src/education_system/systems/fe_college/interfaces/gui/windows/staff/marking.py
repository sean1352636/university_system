"""Marking — working through the queue of submitted work.

Two ways in: the whole queue across every assignment (what a lecturer does on a
Friday), or one assignment at a time (what they do after a hand-in date). Both
end at the same grade-and-feedback dialog, which validates the grade against
the course's qualification scale.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.feedback import IV_OUTCOMES
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Marking"


def open_window(host, assignment_id: int | None = None) -> None:
    Screen(host, assignment_id)


class Screen:
    def __init__(self, host, assignment_id: int | None = None):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "Grades are checked against the course's qualification scale, so a "
            "BTEC unit can't be given a GCSE grade.",
            actions=[("↻ Refresh", self.refresh)],
        )

        if not self.ctl.staff_id:
            w.empty_state(parent, "Your account is not linked to a staff record, "
                                  "so you have no marking queue.")
            return

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Show:").pack(side="left")
        self.scope_var = tk.StringVar(value="My whole queue")

        assignments = self.ctl.assessment.list_assignments(set_by=self.ctl.staff_id)
        self._assignments = {
            f"{a.course_id} · {a.title}": a for a in assignments
        }
        options = ["My whole queue", *sorted(self._assignments)]
        combo = ttk.Combobox(bar, textvariable=self.scope_var, values=options,
                             state="readonly", width=52)
        combo.pack(side="left", padx=(4, 12))
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        if assignment_id is not None:
            for label, a in self._assignments.items():
                if a.assignment_id == assignment_id:
                    self.scope_var.set(label)
                    break

        self.stats_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.stats_var,
                  foreground=w.TONE["muted"]).pack(side="right")

        self.table = w.DataTable(parent, [
            ("student", "Learner", 180),
            ("assignment", "Assignment", 230),
            ("unit", "Unit", 70),
            ("submitted", "Submitted", 100),
            ("status", "Status", 110),
            ("late", "Late", 55),
            ("grade", "Grade", 110),
            ("marks", "Marks", 65, "e"),
        ], height=18, on_double_click=lambda _r: self.mark())

        w.button_bar(parent, [
            ("Mark / grade", self.mark),
            ("View feedback", self.view_feedback),
            ("Internally verify", self.verify),
            ("Record a hand-in", self.record_submission),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        scope = self.scope_var.get()
        try:
            if scope == "My whole queue":
                rows = self.ctl.assessment.marking_queue(self.ctl.staff_id)
                self.stats_var.set(f"{len(rows)} piece(s) waiting")
                self._set_rows(rows, unmarked_only=True)
            else:
                assignment = self._assignments[scope]
                detail = self.ctl.assessment.assignment_detail(assignment.assignment_id)
                if detail is None:
                    return
                s = detail.stats
                self.stats_var.set(
                    f"{s.submitted}/{s.expected} handed in · {s.marked} marked · "
                    f"{s.missing} missing"
                )
                self._set_rows(detail.rows, unmarked_only=False)
        except Exception as exc:
            logger.exception("Could not load the FE College marking queue")
            w.error(self.host, TITLE, f"Could not load marking: {exc}")

    def _set_rows(self, rows, *, unmarked_only: bool) -> None:
        self.table.set_rows([
            {
                "student": row.student.full_name,
                "assignment": row.assignment.title,
                "unit": row.assignment.unit_id or "—",
                "submitted": w.when(row.submission.submitted_at),
                "status": row.submission.status.replace("_", " "),
                "late": w.yes_no(row.is_late),
                "grade": row.submission.grade or "—",
                "marks": row.submission.marks if row.submission.marks is not None else "—",
                "_tone": (
                    "muted" if row.submission.status == "not_submitted"
                    else "bad" if row.submission.status == "referred"
                    else "good" if row.submission.grade
                    else "warn" if row.is_late
                    else "plain"
                ),
                "_obj": row,
            }
            for row in rows
        ])
        self.host.set_status(f"{len(rows)} submission(s)")

    # ── Actions ────────────────────────────────────────────────────────────

    def mark(self) -> None:
        row = self.table.require_selection("a submission")
        if row is None:
            return
        if row.submission.status == "not_submitted":
            w.info(self.host, "Mark",
                   f"{row.student.full_name} has not handed this in yet. "
                   "Use 'Record a hand-in' first.")
            return

        detail = self.ctl.assessment.assignment_detail(row.assignment.assignment_id)
        grades = list(detail.valid_grades) if detail else []
        if "Referred" not in grades:
            grades = [*grades, "Referred"]

        result = w.ask(
            self.host, f"Mark — {row.student.full_name}", [
                ("grade", "Grade", "choice", grades),
                ("marks", f"Marks (max {row.assignment.max_marks})", "int"),
                ("feedback", "Feedback", "multiline"),
            ],
            initial={
                "grade": row.submission.grade or (grades[0] if grades else ""),
                "marks": row.submission.marks or 0,
                "feedback": row.submission.feedback,
            },
            submit_label="Save grade",
        )
        if result is None:
            return
        try:
            self.ctl.assessment.mark(
                row.assignment.assignment_id, row.student.student_id,
                result["grade"],
                marked_by=self.ctl.staff_id,
                marks=result["marks"] or None,
                feedback_text=result["feedback"],
            )
        except ValidationError as exc:
            w.error(self.host, "Mark", str(exc))
            return
        self.refresh()
        self.host.set_status(
            f"Graded {row.student.full_name}: {result['grade']}"
        )

    def record_submission(self) -> None:
        row = self.table.require_selection("a learner")
        if row is None:
            return
        result = w.ask(self.host, f"Record hand-in — {row.student.full_name}", [
            ("submitted_at", "Handed in on", "date"),
        ], initial={"submitted_at": date.today().isoformat()})
        if result is None:
            return
        try:
            self.ctl.assessment.submit(
                row.assignment.assignment_id, row.student.student_id,
                on=result["submitted_at"],
            )
        except ValidationError as exc:
            w.error(self.host, "Record hand-in", str(exc))
            return
        self.refresh()

    def view_feedback(self) -> None:
        row = self.table.require_selection("a submission")
        if row is None:
            return
        if row.submission.submission_id is None:
            w.info(self.host, "Feedback", "Nothing has been recorded yet.")
            return
        items = self.ctl.assessment.feedback_for(row.submission.submission_id)
        body = [
            f"{row.student.full_name} — {row.assignment.title}",
            "=" * 64,
            f"Status : {row.submission.status.replace('_', ' ')}",
            f"Grade  : {row.submission.grade or 'not yet graded'}",
            f"Marks  : {row.submission.marks if row.submission.marks is not None else '—'}"
            f" of {row.assignment.max_marks}",
            f"Criteria: {', '.join(row.assignment.criteria_list) or '—'}",
        ]
        if row.submission.is_capped:
            body.append(
                "This is a resubmission — awarding-body rules cap it at a Pass."
            )
        body += ["", "Feedback", "-" * 64]
        if row.submission.feedback:
            body.append(f"  {row.submission.feedback}")
        for item in items:
            body += [
                f"  [{item.feedback_type}] {w.when(item.given_at)} by {item.author_id}",
                f"    {item.body}",
            ]
        if not items and not row.submission.feedback:
            body.append("  None recorded")
        w.show_text(self.host, "Feedback", "\n".join(body))

    def verify(self) -> None:
        """Record an internal verification decision on a marked submission."""
        row = self.table.require_selection("a marked submission")
        if row is None:
            return
        if not row.submission.grade:
            w.info(self.host, "Internal verification",
                   "Only marked work can be verified.")
            return
        if row.submission.marked_by == self.ctl.staff_id:
            w.warn(self.host, "Internal verification",
                   "You marked this yourself. Internal verification has to be "
                   "done by someone other than the assessor.")
            return
        result = w.ask(self.host, "Internal verification", [
            ("outcome", "Outcome", "choice", list(IV_OUTCOMES)),
            ("comments", "Comments", "multiline"),
        ])
        if result is None:
            return
        try:
            self.ctl.assessment.verify(
                row.submission.submission_id, self.ctl.staff_id,
                result["outcome"], result["comments"],
            )
        except ValidationError as exc:
            w.error(self.host, "Internal verification", str(exc))
            return
        self.host.set_status(
            f"Verified {row.student.full_name}: {result['outcome']}"
        )


__all__ = ["TITLE", "Screen", "open_window"]
