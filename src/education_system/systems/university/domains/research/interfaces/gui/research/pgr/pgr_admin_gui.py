"""PGR Administration window: project list + lifecycle detail over the PGR service.

Opened in-process by the main GUI (``open_window``) with the session auth, or
standalone (``main``) where the EDU_AUTH_* env vars carry the user. Staff-only;
nothing touches the database at import time.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui.subprocess_session import (
    actor_name,
    is_staff,
    session_user,
)
from education_system.platform.delivery.gui.treeview_helpers import (
    fill_tree as _fill,
    make_tree as _make_tree,
    selected_id,
)
from education_system.platform.delivery.gui.window_sizing import center as _center
from education_system.systems.university.domains.research.domain.research.pgr import service
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)
WINDOW_TITLE = "PGR Administration"
PROJECT_COLUMNS = ["project_id", "student_id", "proposal_title", "route", "status",
                   "department", "current_deadline"]

_TABS: list[tuple[str, str, list[str]]] = [
    ("Supervisors", "supervisors", ["allocation_id", "supervisor_id", "role", "workload_fte",
                                    "start_date", "active"]),
    ("Meetings", "meetings", ["meeting_id", "meeting_at", "progress_summary",
                              "next_meeting_date", "created_by"]),
    ("Training", "training_needs", ["need_id", "category", "description", "priority",
                                    "target_date", "status"]),
    ("Reviews", "reviews", ["review_id", "review_year", "due_date", "status", "outcome",
                            "approved_by"]),
    ("Approvals", "approvals", ["approval_id", "approval_type", "reference", "risk_level",
                                "status", "expires_at"]),
    ("Upgrades", "upgrades", ["upgrade_id", "submitted_at", "report_reference", "status",
                              "outcome", "decided_by"]),
    ("Thesis", "submissions", ["submission_id", "version", "thesis_title",
                               "repository_reference", "submitted_at", "status"]),
    ("Examiners", "examiners", ["nomination_id", "examiner_id", "examiner_type", "institution",
                                "status", "approved_by"]),
    ("Viva", "vivas", ["viva_id", "scheduled_at", "location", "chair_id", "status", "outcome"]),
    ("Corrections", "corrections", ["correction_id", "correction_type", "description",
                                    "due_date", "status", "approved_by"]),
    ("Deposit", "deposits", ["deposit_id", "repository_reference", "deposited_at",
                             "embargo_until", "licence", "checked_by"]),
    ("Milestones", "milestones", ["milestone_id", "milestone_type", "title", "due_date",
                                  "status", "extension_until"]),
    ("History", "history", ["created_at", "action", "from_status", "to_status", "actor_id",
                            "reason"]),
]


class PGRAdminWindow(ttk.Frame):
    """Projects on the left; the selected project's lifecycle records on the right."""

    def __init__(self, parent, auth: Any = None) -> None:
        super().__init__(parent)
        self.auth = auth
        self.user = session_user(auth) or {}
        self.actor = actor_name(self.user)
        self._tabs: dict[str, ttk.Treeview] = {}
        self._build()
        self.refresh()

    # ----- layout -------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self, padding=(10, 6))
        header.pack(fill="x")
        ttk.Label(header, text=_t("gui.academics.pgr.title", default=WINDOW_TITLE),
                  font=("Helvetica", 14, "bold")).pack(side="left")
        ttk.Label(header, text=f"Signed in: {self.actor} ({self.user.get('role', '-')})"
                  ).pack(side="right")
        rows = (
            (("New Proposal", self.create_project), ("Register", self.set_registration),
             ("Add Supervisor", self.add_supervisor), ("Workload", self.supervisor_workload),
             ("Log Meeting", self.log_meeting), ("Training Need", self.add_training_need),
             ("Schedule Review", self.schedule_review), ("Decide Review", self.decide_review),
             ("Approval", self.record_approval)),
            (("Submit Upgrade", self.submit_upgrade), ("Decide Upgrade", self.decide_upgrade),
             ("Submit Thesis", self.submit_thesis), ("Nominate Examiner", self.nominate_examiner),
             ("Approve Examiner", self.approve_examiner), ("Schedule Viva", self.schedule_viva),
             ("Viva Outcome", self.record_viva_outcome),
             ("Approve Corrections", self.approve_corrections),
             ("Final Deposit", self.final_deposit)),
            (("Add Milestone", self.add_milestone), ("Extend Milestone", self.extend_milestone),
             ("Escalate Overdue", self.escalate_overdue), ("Refresh", self.refresh)),
        )
        # Action bars are packed before the expanding panes (window-sizing convention).
        for buttons in rows:
            bar = ttk.Frame(self, padding=(10, 2))
            bar.pack(fill="x")
            for label, command in buttons:
                ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)

        filter_bar = ttk.Frame(self, padding=(10, 2))
        filter_bar.pack(fill="x")
        ttk.Label(filter_bar, text="Status filter:").pack(side="left")
        self.status_filter = ttk.Combobox(
            filter_bar, values=["", *sorted(service.PGR_STATES)], state="readonly", width=20)
        self.status_filter.pack(side="left", padx=4)
        self.status_filter.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=6)
        left = ttk.Frame(panes)
        self.projects = _make_tree(left, PROJECT_COLUMNS, width=90)
        self.projects.bind("<<TreeviewSelect>>", lambda _e: self.load_selected())
        panes.add(left, weight=2)
        right = ttk.Frame(panes)
        self.summary = ttk.Label(right, text="Select a project", font=("Helvetica", 11, "bold"))
        self.summary.pack(anchor="w", pady=(0, 4))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        for title, key, columns in _TABS:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            self._tabs[key] = _make_tree(frame, columns)
        panes.add(right, weight=3)

    # ----- data ---------------------------------------------------------
    def refresh(self) -> None:
        selected = selected_id(self.projects)
        try:
            rows = service.list_projects(self.status_filter.get() or None)
        except Exception as exc:  # schema missing, DB unavailable
            logger.exception("list_projects failed")
            messagebox.showerror("Error", str(exc), parent=self)
            return
        _fill(self.projects, rows, PROJECT_COLUMNS)
        if selected is not None and self.projects.exists(str(selected)):
            self.projects.selection_set(str(selected))
            self.load_selected()

    def load_selected(self) -> None:
        project_id = selected_id(self.projects)
        if project_id is None:
            return
        try:
            record = service.project_record(project_id)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        self.summary.configure(
            text=f"#{record['project_id']} {record['proposal_title']} - {record['student_id']} "
                 f"[{record['status']}] {record['route']}, deadline "
                 f"{record['current_deadline'] or '-'}")
        for _title, key, columns in _TABS:
            _fill(self._tabs[key], record.get(key, []), columns)

    def _require_project(self) -> int | None:
        project_id = selected_id(self.projects)
        if project_id is None:
            messagebox.showwarning("Selection", "Select a project first.", parent=self)
        return project_id

    def _require_row(self, key: str, what: str) -> int | None:
        row_id = selected_id(self._tabs[key])
        if row_id is None:
            messagebox.showwarning("Selection", f"Select {what} first.", parent=self)
        return row_id

    def _run(self, action, success: str) -> None:
        try:
            result = action()
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        messagebox.showinfo("Done", success.format(result=result), parent=self)
        self.refresh()

    # ----- project + supervision --------------------------------------
    def create_project(self) -> None:
        values = ask_form(self, "New research proposal", [
            Field("student_id", "Student ID"),
            Field("proposal_title", "Proposal title"),
            Field("abstract", "Abstract", kind="text"),
            Field("research_questions", "Research questions", kind="text", optional=True),
            Field("methodology", "Methodology", kind="text", optional=True),
            Field("department", "Department", optional=True),
            Field("route", "Route", default="MPhil/PhD"),
            Field("start_date", "Start date (YYYY-MM-DD)", optional=True),
            Field("expected_end_date", "Expected end date (YYYY-MM-DD)", optional=True),
        ])
        if values:
            self._run(lambda: service.create_project(
                values["student_id"], values["proposal_title"], values["abstract"],
                created_by=self.actor, research_questions=values["research_questions"] or "",
                methodology=values["methodology"] or "", department=values["department"] or "",
                route=values["route"], start_date=values["start_date"],
                expected_end_date=values["expected_end_date"]), "Project #{result} created")

    def set_registration(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Register project", [
            Field("route", "Route", kind="choice", options=["mphil", "phd"]),
        ])
        if values:
            self._run(lambda: service.set_registration(project_id, values["route"],
                                                       actor_id=self.actor),
                      "Registration recorded")

    def add_supervisor(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Add supervisor", [
            Field("supervisor_id", "Supervisor ID"),
            Field("role", "Role", kind="choice", options=["primary", "secondary", "advisor"]),
            Field("workload_fte", "Workload FTE", kind="float", default="0.5"),
            Field("start_date", "Start date (YYYY-MM-DD)"),
        ])
        if values:
            self._run(lambda: service.add_supervisor(
                project_id, values["supervisor_id"], values["role"],
                workload_fte=values["workload_fte"], start_date=values["start_date"]),
                "Supervisor allocation #{result} added")

    def supervisor_workload(self) -> None:
        values = ask_form(self, "Supervisor workload", [Field("supervisor_id", "Supervisor ID")])
        if not values:
            return
        workload = service.supervisor_workload(values["supervisor_id"])
        lines = [f"{p['project_id']}: {p['proposal_title']} ({p['role']}, {p['workload_fte']})"
                 for p in workload["projects"]]
        messagebox.showinfo(
            "Workload", f"Total FTE {workload['total_fte']:.2f}\n\n" + ("\n".join(lines) or "-"),
            parent=self)

    def log_meeting(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Log supervision meeting", [
            Field("meeting_at", "Meeting at (YYYY-MM-DD HH:MM)"),
            Field("attendees", "Attendees (comma-separated)", kind="list"),
            Field("progress_summary", "Progress summary", kind="text"),
            Field("actions", "Actions (comma-separated)", kind="list", optional=True),
            Field("next_meeting_date", "Next meeting date", optional=True),
        ])
        if values:
            self._run(lambda: service.log_supervision(
                project_id, values["meeting_at"], values["attendees"],
                progress_summary=values["progress_summary"],
                actions=[{"action": a} for a in values["actions"]], created_by=self.actor,
                next_meeting_date=values["next_meeting_date"]), "Meeting #{result} logged")

    def add_training_need(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Add training need", [
            Field("category", "Category"),
            Field("description", "Description", kind="text"),
            Field("priority", "Priority", kind="choice", options=["low", "normal", "high"],
                  default="normal"),
            Field("planned_activity", "Planned activity", optional=True),
            Field("target_date", "Target date (YYYY-MM-DD)", optional=True),
        ])
        if values:
            self._run(lambda: service.add_training_need(
                project_id, values["category"], values["description"],
                priority=values["priority"], planned_activity=values["planned_activity"] or "",
                target_date=values["target_date"]), "Training need #{result} added")

    # ----- reviews + approvals ------------------------------------------
    def schedule_review(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Schedule progress review", [
            Field("review_year", "Review year", kind="int", default="1"),
            Field("due_date", "Due date (YYYY-MM-DD)"),
        ])
        if values:
            self._run(lambda: service.schedule_review(project_id, values["review_year"],
                                                      values["due_date"]),
                      "Review #{result} scheduled")

    def decide_review(self) -> None:
        review_id = self._require_row("reviews", "a review")
        if review_id is None:
            return
        values = ask_form(self, f"Decide review #{review_id}", [
            Field("outcome", "Outcome", kind="choice",
                  options=["satisfactory", "conditional", "unsatisfactory"]),
            Field("panel", "Panel (comma-separated)", kind="list"),
            Field("student_report", "Student report", kind="text", optional=True),
            Field("supervisor_report", "Supervisor report", kind="text", optional=True),
            Field("conditions", "Conditions", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.decide_review(
                review_id, values["outcome"], panel=values["panel"], approved_by=self.actor,
                student_report=values["student_report"] or "",
                supervisor_report=values["supervisor_report"] or "",
                conditions=values["conditions"] or ""), "Review decided")

    def record_approval(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Record ethics / governance approval", [
            Field("approval_type", "Approval type", kind="choice",
                  options=["ethics", "data_governance", "sponsor"]),
            Field("reference", "Reference"),
            Field("status", "Status", kind="choice", options=["approved", "pending", "rejected"]),
            Field("risk_level", "Risk level", optional=True),
            Field("expires_at", "Expires at (YYYY-MM-DD)", optional=True),
            Field("conditions", "Conditions", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.record_approval(
                project_id, values["approval_type"], reference=values["reference"],
                status=values["status"], approved_by=self.actor,
                risk_level=values["risk_level"] or "", expires_at=values["expires_at"],
                conditions=values["conditions"] or ""), "Approval #{result} recorded")

    # ----- upgrade, thesis, examiners, viva -----------------------------
    def submit_upgrade(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Submit MPhil-to-PhD upgrade", [
            Field("report_reference", "Report reference"),
            Field("panel", "Panel (comma-separated)", kind="list"),
        ])
        if values:
            self._run(lambda: service.submit_upgrade(project_id, values["report_reference"],
                                                     values["panel"]),
                      "Upgrade #{result} submitted")

    def decide_upgrade(self) -> None:
        upgrade_id = self._require_row("upgrades", "an upgrade")
        if upgrade_id is None:
            return
        values = ask_form(self, f"Decide upgrade #{upgrade_id}", [
            Field("outcome", "Outcome", kind="choice",
                  options=["approved", "revisions", "rejected"]),
            Field("conditions", "Conditions", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.decide_upgrade(
                upgrade_id, values["outcome"], decided_by=self.actor,
                conditions=values["conditions"] or ""), "Upgrade decided")

    def submit_thesis(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Submit thesis", [
            Field("title", "Thesis title"),
            Field("repository_reference", "Repository reference"),
            Field("declaration_accepted", "Declaration accepted", kind="bool"),
        ])
        if values:
            self._run(lambda: service.submit_thesis(
                project_id, values["title"], values["repository_reference"],
                declaration_accepted=values["declaration_accepted"]),
                "Thesis submission #{result} recorded")

    def nominate_examiner(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Nominate examiner", [
            Field("examiner_id", "Examiner ID"),
            Field("examiner_type", "Type", kind="choice", options=["internal", "external"]),
            Field("institution", "Institution"),
            Field("expertise", "Expertise", kind="text"),
            Field("conflict_declaration", "Conflict declaration", kind="text"),
        ])
        if values:
            self._run(lambda: service.nominate_examiner(
                project_id, values["examiner_id"], values["examiner_type"],
                institution=values["institution"], expertise=values["expertise"],
                conflict_declaration=values["conflict_declaration"], nominated_by=self.actor),
                "Examiner nomination #{result} recorded")

    def approve_examiner(self) -> None:
        nomination_id = self._require_row("examiners", "an examiner nomination")
        if nomination_id is None:
            return
        if messagebox.askyesno("Approve", f"Approve examiner nomination #{nomination_id}?",
                               parent=self):
            self._run(lambda: service.approve_examiner(nomination_id, approved_by=self.actor),
                      "Examiner approved")

    def schedule_viva(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Schedule viva", [
            Field("scheduled_at", "Scheduled at (YYYY-MM-DD HH:MM)"),
            Field("location", "Location"),
            Field("chair_id", "Chair ID", default=self.actor),
        ])
        if values:
            self._run(lambda: service.schedule_viva(
                project_id, values["scheduled_at"], location=values["location"],
                chair_id=values["chair_id"]), "Viva #{result} scheduled")

    def record_viva_outcome(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Record viva outcome", [
            Field("outcome", "Outcome", kind="choice",
                  options=["pass", "minor_corrections", "major_corrections", "resubmit", "fail"]),
            Field("notes", "Notes", kind="text", optional=True),
            Field("corrections_due", "Corrections due (YYYY-MM-DD)", optional=True),
            Field("corrections", "Corrections required", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.record_viva_outcome(
                project_id, values["outcome"], decided_by=self.actor,
                notes=values["notes"] or "", corrections_due=values["corrections_due"],
                corrections=values["corrections"] or ""), "Viva outcome recorded")

    def approve_corrections(self) -> None:
        correction_id = self._require_row("corrections", "a correction")
        if correction_id is None:
            return
        if messagebox.askyesno("Approve", f"Approve corrections #{correction_id}?", parent=self):
            self._run(lambda: service.approve_corrections(correction_id, approved_by=self.actor),
                      "Corrections approved")

    def final_deposit(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Final thesis deposit", [
            Field("repository_reference", "Repository reference"),
            Field("licence", "Licence", default="CC BY"),
            Field("embargo_until", "Embargo until (YYYY-MM-DD)", optional=True),
        ])
        if values:
            self._run(lambda: service.final_deposit(
                project_id, values["repository_reference"], licence=values["licence"],
                checked_by=self.actor, embargo_until=values["embargo_until"]),
                "Deposit #{result} recorded; project completed")

    # ----- milestones ---------------------------------------------------
    def add_milestone(self) -> None:
        project_id = self._require_project()
        if project_id is None:
            return
        values = ask_form(self, "Add milestone", [
            Field("milestone_type", "Milestone type"),
            Field("title", "Title"),
            Field("due_date", "Due date (YYYY-MM-DD)"),
        ])
        if values:
            self._run(lambda: service.add_milestone(
                project_id, values["milestone_type"], values["title"], values["due_date"]),
                "Milestone #{result} added")

    def extend_milestone(self) -> None:
        milestone_id = self._require_row("milestones", "a milestone")
        if milestone_id is None:
            return
        values = ask_form(self, f"Extend milestone #{milestone_id}", [
            Field("extension_until", "Extension until (YYYY-MM-DD)"),
            Field("reason", "Reason", kind="text"),
        ])
        if values:
            self._run(lambda: service.extend_milestone(
                milestone_id, values["extension_until"], reason=values["reason"],
                approved_by=self.actor), "Milestone extended")

    def escalate_overdue(self) -> None:
        values = ask_form(self, "Escalate overdue items", [
            Field("as_of", "As of (YYYY-MM-DD, blank = today)", optional=True),
        ])
        if values:
            self._run(lambda: service.escalate_overdue(as_of=values["as_of"]),
                      "{result} escalation(s) created")


def open_window(master, auth: Any = None) -> tk.Toplevel | None:
    """Open the window as a Toplevel of ``master`` for a staff session."""
    if not is_staff(session_user(auth)):
        messagebox.showwarning(WINDOW_TITLE, "PGR administration is restricted to staff.",
                               parent=master)
        return None
    top = tk.Toplevel(master)
    top.title(_t("gui.academics.pgr.title", default=WINDOW_TITLE))
    _center(top, 1400, 900, minsize=(1200, 800))
    PGRAdminWindow(top, auth=auth).pack(fill="both", expand=True)
    return top


def main() -> None:
    """Standalone launch (subprocess fallback from the main GUI)."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    _center(root, 1400, 900, minsize=(1200, 800))
    if not is_staff(session_user()):
        messagebox.showwarning(WINDOW_TITLE, "PGR administration is restricted to staff.")
        root.destroy()
        return
    PGRAdminWindow(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
