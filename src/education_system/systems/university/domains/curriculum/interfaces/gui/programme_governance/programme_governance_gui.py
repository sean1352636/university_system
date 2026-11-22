"""Programme Governance window: list + detail over the governance service.

Opened in-process by the main GUI (``open_window``) with the session auth,
or standalone (``main``) where the EDU_AUTH_* env vars carry the user, the
same way room_booking_app does. Staff-only; nothing touches the database at
import time.
"""
from __future__ import annotations

import json
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
from education_system.systems.university.domains.curriculum.domain.programme_governance import (
    service,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)
WINDOW_TITLE = "Programme Governance"

_TABS: list[tuple[str, str, list[str]]] = [
    ("Versions", "versions", ["version_id", "version_number", "effective_academic_year",
                              "status", "validation_outcome", "approved_by", "snapshot_hash"]),
    ("Proposals", "proposals", ["proposal_id", "proposed_start_year", "status", "rationale",
                                "market_need", "strategic_alignment"]),
    ("Business cases", "business_cases", ["business_case_id", "proposal_id", "approved",
                                          "approved_by", "approved_at", "staffing_plan"]),
    ("Amendments", "amendments", ["amendment_id", "source_version_id", "target_version_id",
                                  "amendment_type", "status", "summary", "requested_by"]),
    ("Validations", "validations", ["validation_id", "version_id", "committee_id", "meeting_at",
                                    "outcome", "minutes_reference", "chair_id"]),
    ("Accreditations", "accreditations", ["accreditation_id", "body_name", "status",
                                          "accreditation_reference", "valid_from", "valid_until"]),
    ("Teach-out", "teach_out_plans", ["plan_id", "version_id", "last_intake_year",
                                      "final_delivery_year", "status", "approved_by"]),
    ("History", "history", ["created_at", "action", "actor_id", "version_id", "reason"]),
]


class ProgrammeGovernanceWindow(ttk.Frame):
    """List of governed programmes on the left, governance artefacts on the right."""

    def __init__(self, parent, auth: Any = None) -> None:
        super().__init__(parent)
        self.auth = auth
        self.user = session_user(auth) or {}
        self.actor = actor_name(self.user)
        self.record: dict[str, Any] | None = None
        self._tabs: dict[str, ttk.Treeview] = {}
        self._build()
        self.refresh()

    # ----- layout -------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self, padding=(10, 6))
        header.pack(fill="x")
        ttk.Label(header, text=_t("gui.academics.programme_governance.title",
                                  default=WINDOW_TITLE),
                  font=("Helvetica", 14, "bold")).pack(side="left")
        ttk.Label(header, text=f"Signed in: {self.actor} ({self.user.get('role', '-')})"
                  ).pack(side="right")

        # Action bar is packed before the expanding panes (window-sizing convention).
        actions = ttk.Frame(self, padding=(10, 2))
        actions.pack(fill="x")
        for label, command in (
            ("New Proposal", self.create_proposal),
            ("Business Case", self.record_business_case),
            ("Approve Business Case", self.approve_business_case),
            ("New Draft Version", self.create_version),
            ("Amend Draft", self.amend_draft),
            ("Propose Amendment", self.propose_amendment),
            ("Validate Version", self.validate_version),
            ("Approve Version", self.approve_version),
        ):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=2)
        actions2 = ttk.Frame(self, padding=(10, 2))
        actions2.pack(fill="x")
        for label, command in (
            ("Committees", self.show_committees),
            ("Accreditation", self.record_accreditation),
            ("Teach-out Plan", self.create_teach_out),
            ("Set Status", self.set_status),
            ("Assign Student", self.assign_student),
            ("Student Lookup", self.student_lookup),
            ("Refresh", self.refresh),
        ):
            ttk.Button(actions2, text=label, command=command).pack(side="left", padx=2)

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=6)
        left = ttk.Frame(panes)
        self.programmes = _make_tree(
            left, ["programme_id", "programme_code", "programme_name", "award_type",
                   "status", "latest_version"], width=90)
        self.programmes.bind("<<TreeviewSelect>>", lambda _e: self.load_selected())
        panes.add(left, weight=2)

        right = ttk.Frame(panes)
        self.summary = ttk.Label(right, text="Select a programme", font=("Helvetica", 11, "bold"))
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
        selected = self.selected_programme_id()
        try:
            rows = service.list_programmes()
        except Exception as exc:  # schema missing, DB unavailable
            logger.exception("list_programmes failed")
            messagebox.showerror("Error", str(exc), parent=self)
            return
        _fill(self.programmes, rows, ["programme_id", "programme_code", "programme_name",
                                      "award_type", "status", "latest_version"])
        if selected is not None and self.programmes.exists(str(selected)):
            self.programmes.selection_set(str(selected))
            self.load_selected()

    def selected_programme_id(self) -> int | None:
        return selected_id(self.programmes)

    def load_selected(self) -> None:
        programme_id = self.selected_programme_id()
        if programme_id is None:
            return
        try:
            self.record = service.programme_record(programme_id)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        record = self.record
        self.summary.configure(
            text=f"{record['programme_code']} - {record['programme_name']} "
                 f"[{record['status']}] {record['award_type']} / {record['owning_school'] or '-'}")
        for _title, key, columns in _TABS:
            _fill(self._tabs[key], record.get(key, []), columns)

    def _require_programme(self) -> int | None:
        programme_id = self.selected_programme_id()
        if programme_id is None:
            messagebox.showwarning("Selection", "Select a programme first.", parent=self)
        return programme_id

    def _selected_in(self, key: str) -> int | None:
        return selected_id(self._tabs[key])

    def _run(self, action, success: str) -> None:
        """Call a service function, report the outcome, and refresh."""
        try:
            result = action()
        except (ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        messagebox.showinfo("Done", success.format(result=result), parent=self)
        self.refresh()

    # ----- actions ------------------------------------------------------
    def create_proposal(self) -> None:
        values = ask_form(self, "New programme proposal", [
            Field("programme_code", "Programme code"),
            Field("programme_name", "Programme name"),
            Field("award_type", "Award type", default="BSc"),
            Field("proposed_start_year", "Proposed start year", default="2027/28"),
            Field("owning_school", "Owning school", optional=True),
            Field("rationale", "Rationale", kind="text"),
            Field("market_need", "Market need", kind="text", optional=True),
            Field("strategic_alignment", "Strategic alignment", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.create_proposal(
                values["programme_code"], values["programme_name"], values["award_type"],
                values["proposed_start_year"], created_by=self.actor,
                rationale=values["rationale"], market_need=values["market_need"] or "",
                strategic_alignment=values["strategic_alignment"] or "",
                owning_school=values["owning_school"] or ""),
                "Programme and proposal created: {result}")

    def record_business_case(self) -> None:
        proposal_id = self._selected_in("proposals")
        values = ask_form(self, "Record business case", [
            Field("proposal_id", "Proposal ID", kind="int",
                  default=str(proposal_id or "")),
            Field("forecast_students", "Forecast students (JSON)", kind="json",
                  default='{"year1": 30}'),
            Field("income", "Income (JSON)", kind="json", default='{"year1": 0}'),
            Field("costs", "Costs (JSON)", kind="json", default='{"year1": 0}'),
            Field("staffing_plan", "Staffing plan", kind="text"),
            Field("facilities_plan", "Facilities plan", kind="text"),
            Field("risk_register", "Risk register", kind="text"),
        ])
        if values:
            self._run(lambda: service.record_business_case(
                values.pop("proposal_id"), **values), "Business case #{result} recorded")

    def approve_business_case(self) -> None:
        case_id = self._selected_in("business_cases")
        if case_id is None:
            messagebox.showwarning("Selection", "Select a business case first.", parent=self)
            return
        if messagebox.askyesno("Approve", f"Approve business case #{case_id}?", parent=self):
            self._run(lambda: service.approve_business_case(case_id, approved_by=self.actor),
                      "Business case approved")

    def create_version(self) -> None:
        programme_id = self._require_programme()
        if programme_id is None:
            return
        values = ask_form(self, "New draft version", [
            Field("effective_academic_year", "Effective academic year", default="2027/28"),
            Field("curriculum", "Curriculum (JSON)", kind="json", default='{"modules": []}'),
            Field("regulations", "Regulations (JSON)", kind="json", default='{"pass_mark": 40}'),
            Field("supersedes_version_id", "Supersedes version ID", kind="int", optional=True),
        ])
        if values:
            self._run(lambda: service.create_version(
                programme_id, values["effective_academic_year"],
                curriculum=values["curriculum"], regulations=values["regulations"],
                created_by=self.actor,
                supersedes_version_id=values["supersedes_version_id"]),
                "Draft version #{result} created")

    def amend_draft(self) -> None:
        version_id = self._selected_in("versions")
        if version_id is None:
            messagebox.showwarning("Selection", "Select a draft version first.", parent=self)
            return
        values = ask_form(self, f"Amend draft version #{version_id}", [
            Field("curriculum", "Curriculum (JSON, blank keeps)", kind="json", optional=True),
            Field("regulations", "Regulations (JSON, blank keeps)", kind="json", optional=True),
        ])
        if values:
            self._run(lambda: service.amend_draft(
                version_id, curriculum=values["curriculum"], regulations=values["regulations"],
                actor_id=self.actor), "Draft amended")

    def propose_amendment(self) -> None:
        version_id = self._selected_in("versions")
        if version_id is None:
            messagebox.showwarning("Selection", "Select the approved source version first.",
                                   parent=self)
            return
        values = ask_form(self, f"Propose amendment to version #{version_id}", [
            Field("amendment_type", "Amendment type", kind="choice",
                  options=["minor", "major"], default="minor"),
            Field("effective_academic_year", "Effective academic year"),
            Field("summary", "Summary", kind="text"),
            Field("impact_assessment", "Impact assessment", kind="text"),
        ])
        if values:
            self._run(lambda: service.propose_amendment(
                version_id, values["amendment_type"], values["summary"],
                values["impact_assessment"], requested_by=self.actor,
                effective_academic_year=values["effective_academic_year"]),
                "Amendment and new draft created: {result}")

    def validate_version(self) -> None:
        version_id = self._selected_in("versions")
        if version_id is None:
            messagebox.showwarning("Selection", "Select a draft version first.", parent=self)
            return
        values = ask_form(self, f"Validate version #{version_id}", [
            Field("committee_id", "Committee ID", kind="int"),
            Field("meeting_at", "Meeting at (YYYY-MM-DD HH:MM)"),
            Field("members", "Members present (comma-separated)", kind="list"),
            Field("external_advisers", "External advisers", kind="list", optional=True),
            Field("outcome", "Outcome", kind="choice",
                  options=["approved", "conditional", "rejected"]),
            Field("conditions", "Conditions", kind="list", optional=True),
            Field("minutes_reference", "Minutes reference"),
            Field("chair_id", "Chair ID", default=self.actor),
        ])
        if values:
            self._run(lambda: service.validate_version(
                version_id, values["committee_id"], values["meeting_at"], values["members"],
                external_advisers=values["external_advisers"], outcome=values["outcome"],
                conditions=values["conditions"], minutes_reference=values["minutes_reference"],
                chair_id=values["chair_id"]), "Validation #{result} recorded")

    def approve_version(self) -> None:
        version_id = self._selected_in("versions")
        if version_id is None:
            messagebox.showwarning("Selection", "Select a validated version first.", parent=self)
            return
        if messagebox.askyesno("Approve", f"Approve and freeze version #{version_id}?",
                               parent=self):
            self._run(lambda: service.approve_version(version_id, approved_by=self.actor),
                      "Version approved")

    def show_committees(self) -> None:
        top = tk.Toplevel(self)
        top.title("Approval committees")
        _center(top, 700, 400)
        bar = ttk.Frame(top, padding=6)
        bar.pack(fill="x")
        tree = _make_tree(top, ["committee_id", "name", "committee_type", "quorum", "active"])

        def reload() -> None:
            _fill(tree, service.list_committees(),
                  ["committee_id", "name", "committee_type", "quorum", "active"])

        def create() -> None:
            values = ask_form(top, "New committee", [
                Field("name", "Committee name"),
                Field("committee_type", "Committee type", default="validation"),
                Field("quorum", "Quorum", kind="int", default="3"),
            ])
            if values:
                try:
                    service.create_committee(values["name"], values["committee_type"],
                                             values["quorum"])
                except ValueError as exc:
                    messagebox.showerror("Error", str(exc), parent=top)
                    return
                reload()

        ttk.Button(bar, text="New Committee", command=create).pack(side="left")
        ttk.Button(bar, text="Close", command=top.destroy).pack(side="right")
        reload()

    def record_accreditation(self) -> None:
        programme_id = self._require_programme()
        if programme_id is None:
            return
        values = ask_form(self, "Record accreditation", [
            Field("body_name", "Accrediting body"),
            Field("status", "Status", kind="choice",
                  options=["accredited", "conditional", "pending", "withdrawn"]),
            Field("version_id", "Version ID", kind="int", optional=True),
            Field("accreditation_reference", "Reference", optional=True),
            Field("valid_from", "Valid from (YYYY-MM-DD)", optional=True),
            Field("valid_until", "Valid until (YYYY-MM-DD)", optional=True),
            Field("conditions", "Conditions", kind="text", optional=True),
            Field("evidence_reference", "Evidence reference", optional=True),
        ])
        if values:
            self._run(lambda: service.record_accreditation(
                programme_id, values["body_name"], values["status"],
                version_id=values["version_id"],
                accreditation_reference=values["accreditation_reference"] or "",
                valid_from=values["valid_from"], valid_until=values["valid_until"],
                conditions=values["conditions"] or "",
                evidence_reference=values["evidence_reference"] or ""),
                "Accreditation #{result} recorded")

    def create_teach_out(self) -> None:
        programme_id = self._require_programme()
        if programme_id is None:
            return
        values = ask_form(self, "Create teach-out plan", [
            Field("version_id", "Version ID", kind="int", optional=True),
            Field("last_intake_year", "Last intake year"),
            Field("final_delivery_year", "Final delivery year"),
            Field("student_communication", "Student communication", kind="text"),
            Field("staffing_commitment", "Staffing commitment", kind="text"),
            Field("module_availability", "Module availability (JSON)", kind="json",
                  default="{}"),
        ])
        if values:
            self._run(lambda: service.create_teach_out(
                programme_id, approved_by=self.actor, **values),
                "Teach-out plan #{result} created")

    def set_status(self) -> None:
        programme_id = self._require_programme()
        if programme_id is None:
            return
        values = ask_form(self, "Set programme status", [
            Field("status", "Status", kind="choice",
                  options=["active", "suspended", "teach_out", "closed"]),
            Field("reason", "Reason", kind="text"),
        ])
        if values:
            self._run(lambda: service.set_programme_status(
                programme_id, values["status"], actor_id=self.actor, reason=values["reason"]),
                "Programme status updated")

    def assign_student(self) -> None:
        programme_id = self._require_programme()
        if programme_id is None:
            return
        version_id = self._selected_in("versions")
        values = ask_form(self, "Assign student to approved regulations", [
            Field("student_id", "Student ID"),
            Field("version_id", "Approved version ID", kind="int",
                  default=str(version_id or "")),
            Field("reason", "Reason", default="Regulation assignment"),
        ])
        if values:
            self._run(lambda: service.assign_student(
                values["student_id"], programme_id, values["version_id"],
                assigned_by=self.actor, reason=values["reason"]),
                "Assignment #{result} recorded")

    def student_lookup(self) -> None:
        values = ask_form(self, "Student regulation lookup", [
            Field("student_id", "Student ID"),
            Field("programme_id", "Programme ID", kind="int", optional=True),
        ])
        if not values:
            return
        try:
            record = service.regulation_for_student(values["student_id"], values["programme_id"])
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        if record is None:
            messagebox.showinfo("Lookup", "No active regulation assignment.", parent=self)
            return
        messagebox.showinfo(
            "Lookup",
            f"{record['programme_code']} v{record['version_number']} "
            f"({record['effective_academic_year']})\nhash {record['snapshot_hash']}\n\n"
            f"{json.dumps(record['regulations'], indent=2)[:1500]}", parent=self)


def open_window(master, auth: Any = None) -> tk.Toplevel | None:
    """Open the window as a Toplevel of ``master`` for a staff session."""
    user = session_user(auth)
    if not is_staff(user):
        messagebox.showwarning(WINDOW_TITLE, "Programme governance is restricted to staff.",
                               parent=master)
        return None
    top = tk.Toplevel(master)
    top.title(_t("gui.academics.programme_governance.title", default=WINDOW_TITLE))
    _center(top, 1400, 900, minsize=(1200, 800))
    ProgrammeGovernanceWindow(top, auth=auth).pack(fill="both", expand=True)
    return top


def main() -> None:
    """Standalone launch (subprocess fallback from the main GUI)."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    _center(root, 1400, 900, minsize=(1200, 800))
    if not is_staff(session_user()):
        messagebox.showwarning(WINDOW_TITLE, "Programme governance is restricted to staff.")
        root.destroy()
        return
    ProgrammeGovernanceWindow(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
