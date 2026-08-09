"""Assignments a lecturer has set — drafting, issuing and tracking hand-ins.

Issuing is the meaningful step: it creates a row for every enrolled learner, so
the hand-in position is visible immediately rather than only once someone
submits. A draft stays invisible to learners until then.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from tkinter import ttk

from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.assignments import (
    ASSIGNMENT_STATUSES,
    Assignment,
)
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Assignments"


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
            "Briefs you have set. Issuing one opens it to learners and starts "
            "tracking hand-ins.",
            actions=[
                ("+ New assignment", self.new),
                ("↻ Refresh", self.refresh),
            ],
        )

        if not self.ctl.staff_id:
            w.empty_state(parent, "Your account is not linked to a staff record, "
                                  "so you have no assignments.")
            return

        self.filters = w.FilterBar(
            parent, self.refresh, search=False,
            filters=[
                ("course_id", "Course", [c.course_id for c in self.ctl.my_courses()]),
                ("status", "Status", ASSIGNMENT_STATUSES),
            ],
        )

        self.table = w.DataTable(parent, [
            ("title", "Assignment", 250),
            ("course", "Course", 95),
            ("unit", "Unit", 70),
            ("status", "Status", 85),
            ("issued", "Issued", 95),
            ("due", "Due", 95),
            ("in", "Handed in", 90, "e"),
            ("marked", "Marked", 80, "e"),
            ("missing", "Missing", 75, "e"),
            ("criteria", "Criteria", 130),
        ], on_double_click=lambda _a: self.open_marking())

        w.button_bar(parent, [
            ("Open marking", self.open_marking),
            ("Edit", self.edit),
            ("Issue to learners", self.issue),
            ("View brief", self.view_brief),
            ("Delete", self.delete),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            assignments = self.ctl.assessment.list_assignments(
                set_by=self.ctl.staff_id, **self.filters.values()
            )
        except Exception as exc:
            logger.exception("Could not list FE College assignments")
            w.error(self.host, TITLE, f"Could not load assignments: {exc}")
            return

        rows = []
        for a in assignments:
            stats = (
                self.ctl.assessment.assignment_detail(a.assignment_id).stats
                if a.status != "draft" else None
            )
            rows.append({
                "title": a.title,
                "course": a.course_id,
                "unit": a.unit_id or "—",
                "status": a.status,
                "issued": w.when(a.issue_date),
                "due": w.when(a.due_date),
                "in": f"{stats.submitted}/{stats.expected}" if stats else "—",
                "marked": stats.marked if stats else "—",
                "missing": stats.missing if stats else "—",
                "criteria": a.criteria or "—",
                "_tone": (
                    "muted" if a.status in ("draft", "archived")
                    else "bad" if a.is_overdue() and stats and stats.missing
                    else "good" if stats and stats.missing == 0
                    else "plain"
                ),
                "_obj": a,
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "assignment")
        self.host.set_status(f"{len(rows)} assignment(s)")

    # ── Actions ────────────────────────────────────────────────────────────

    def _form(self, assignment: Assignment | None):
        courses = self.ctl.my_courses()
        if not courses:
            w.info(self.host, TITLE, "You are not assigned to any courses.")
            return None
        course_options = [f"{c.course_id} — {c.title}" for c in courses]

        selected_course = assignment.course_id if assignment else courses[0].course_id
        units = [""] + [u.unit_id for u in self.ctl.courses.units(selected_course)]
        groups = [""] + [g.group_id for g in self.ctl.courses.groups(selected_course)]

        return w.ask(
            self.host,
            "New assignment" if assignment is None else f"Edit {assignment.title}",
            [
                ("course", "Course", "choice", course_options),
                ("title", "Title", "text"),
                ("unit_id", "Unit", "choice", units),
                ("group_id", "Class group (blank = whole course)", "choice", groups),
                ("status", "Status", "choice", ASSIGNMENT_STATUSES),
                ("issue_date", "Hand-out date", "date"),
                ("due_date", "Hand-in date", "date"),
                ("criteria", "Criteria (e.g. P1, P2, M1)", "text"),
                ("max_marks", "Maximum marks", "int"),
                ("brief", "Brief", "multiline"),
            ],
            initial={
                "course": next(
                    (o for o in course_options if o.startswith(selected_course)),
                    course_options[0],
                ),
                "title": assignment.title if assignment else "",
                "unit_id": assignment.unit_id if assignment else "",
                "group_id": assignment.group_id if assignment else "",
                "status": assignment.status if assignment else "draft",
                "issue_date": w.when(
                    assignment.issue_date if assignment else date.today(), ""
                ),
                "due_date": w.when(
                    assignment.due_date if assignment
                    else date.today() + timedelta(weeks=3), ""
                ),
                "criteria": assignment.criteria if assignment else "",
                "max_marks": assignment.max_marks if assignment else 100,
                "brief": assignment.brief if assignment else "",
            },
        )

    def new(self) -> None:
        result = self._form(None)
        if result is None:
            return
        try:
            self.ctl.assessment.create_assignment(Assignment(
                assignment_id=None,
                course_id=result["course"].split(" — ")[0],
                title=result["title"],
                unit_id=result["unit_id"],
                group_id=result["group_id"],
                status=result["status"],
                set_by=self.ctl.staff_id,
                issue_date=result["issue_date"],
                due_date=result["due_date"],
                criteria=result["criteria"],
                max_marks=result["max_marks"],
                brief=result["brief"],
            ))
        except ValidationError as exc:
            w.error(self.host, "New assignment", str(exc))
            return
        self.refresh()

    def edit(self) -> None:
        assignment = self.table.require_selection("an assignment")
        if assignment is None:
            return
        result = self._form(assignment)
        if result is None:
            return
        assignment.course_id = result["course"].split(" — ")[0]
        assignment.title = result["title"]
        assignment.unit_id = result["unit_id"]
        assignment.group_id = result["group_id"]
        assignment.status = result["status"]
        assignment.issue_date = result["issue_date"]
        assignment.due_date = result["due_date"]
        assignment.criteria = result["criteria"]
        assignment.max_marks = result["max_marks"]
        assignment.brief = result["brief"]
        try:
            self.ctl.assessment.update_assignment(assignment)
        except ValidationError as exc:
            w.error(self.host, "Edit assignment", str(exc))
            return
        self.refresh()

    def issue(self) -> None:
        assignment = self.table.require_selection("an assignment")
        if assignment is None:
            return
        if assignment.status == "issued":
            w.info(self.host, "Issue", "That assignment is already issued.")
            return
        if not w.confirm(
            self.host, "Issue assignment",
            f"Issue '{assignment.title}' to everyone enrolled on "
            f"{assignment.course_id}?\n\nHand-in tracking starts immediately.",
        ):
            return
        try:
            self.ctl.assessment.issue_assignment(assignment.assignment_id)
        except ValidationError as exc:
            w.error(self.host, "Issue", str(exc))
            return
        self.refresh()

    def view_brief(self) -> None:
        assignment = self.table.require_selection("an assignment")
        if assignment is None:
            return
        detail = self.ctl.assessment.assignment_detail(assignment.assignment_id)
        stats = detail.stats if detail else None
        body = [
            assignment.title,
            "=" * 64,
            f"Course     : {assignment.course_id}",
            f"Unit       : {assignment.unit_id or '—'}",
            f"Group      : {assignment.group_id or 'whole course'}",
            f"Status     : {assignment.status}",
            f"Handed out : {w.when(assignment.issue_date)}",
            f"Hand-in    : {w.when(assignment.due_date)}",
            f"Resubmission by: {w.when(assignment.resubmission_deadline)}",
            f"Criteria   : {', '.join(assignment.criteria_list) or '—'}",
            f"Max marks  : {assignment.max_marks}",
        ]
        if stats:
            body += [
                "",
                "Hand-in position",
                "-" * 64,
                f"  {stats.submitted} of {stats.expected} handed in "
                f"({w.pct(stats.submission_rate)})",
                f"  {stats.marked} marked ({w.pct(stats.marking_progress)} of those in)",
                f"  {stats.referred} referred · {stats.missing} missing",
            ]
        body += ["", "Brief", "-" * 64, assignment.brief or "  (no brief written)"]
        w.show_text(self.host, assignment.title, "\n".join(body))

    def open_marking(self) -> None:
        assignment = self.table.require_selection("an assignment")
        if assignment is None:
            return
        self.host.open_screen("marking", assignment_id=assignment.assignment_id)

    def delete(self) -> None:
        assignment = self.table.require_selection("an assignment")
        if assignment is None:
            return
        if not w.confirm(
            self.host, "Delete assignment",
            f"Delete '{assignment.title}'?\n\n"
            "Every submission, grade and piece of feedback against it goes too.",
        ):
            return
        self.ctl.assessment.delete_assignment(assignment.assignment_id)
        self.refresh()


__all__ = ["TITLE", "Screen", "open_window"]
