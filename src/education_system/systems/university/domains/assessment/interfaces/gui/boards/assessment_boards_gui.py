"""Assessment Boards window: board list + agenda/decision detail over the boards service.

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
from education_system.systems.university.domains.assessment.domain.boards import (
    classification_admin,
    progression,
    service,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)
WINDOW_TITLE = "Assessment Boards"
BOARD_COLUMNS = ["board_id", "board_type", "name", "academic_year", "programme_code",
                 "module_code", "status", "version", "chair_id"]
AGENDA_COLUMNS = ["student_id", "programme_code", "current_level", "credits", "average_mark",
                  "proposed_classification", "status"]

_TABS: list[tuple[str, str, list[str]]] = [
    ("Agenda", "agenda", AGENDA_COLUMNS),
    ("Decisions", "decisions", ["decision_id", "student_id", "module_code", "decision_type",
                                "original_result", "confirmed_result", "credits_affected",
                                "classification", "decided_by", "supersedes_decision_id"]),
    ("Members", "members", ["member_id", "role"]),
    ("Rules", "rules", ["rule_id", "rule_type", "minimum_mark", "maximum_credits",
                        "exclude_core_modules", "active", "notes"]),
    ("Awards", "awards", ["award_id", "student_id", "award_name", "classification", "status",
                          "release_authorised", "ratified_by"]),
    ("Progression", "progression", ["outcome_id", "student_id", "outcome", "from_year",
                                    "to_year", "trailing_credits", "exit_award",
                                    "proposed_outcome", "status", "released", "rollover_note"]),
]
MY_OUTCOME_COLUMNS = ["outcome_id", "board_name", "academic_year", "label", "from_year",
                      "to_year", "exit_award", "exit_classification", "released_at"]


class AssessmentBoardsWindow(ttk.Frame):
    """Boards on the left; the selected board's agenda, decisions and minutes on the right."""

    def __init__(self, parent, auth: Any = None) -> None:
        super().__init__(parent)
        self.auth = auth
        self.user = session_user(auth) or {}
        self.actor = actor_name(self.user)
        self.board: dict[str, Any] | None = None
        self._tabs: dict[str, ttk.Treeview] = {}
        self._build()
        self.refresh()

    # ----- layout -------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self, padding=(10, 6))
        header.pack(fill="x")
        ttk.Label(header, text=_t("gui.assessment.boards.title", default=WINDOW_TITLE),
                  font=("Helvetica", 14, "bold")).pack(side="left")
        ttk.Label(header, text=f"Signed in: {self.actor} ({self.user.get('role', '-')})"
                  ).pack(side="right")
        rows = (
            (("New Board", self.create_board), ("Add Member", self.add_member),
             ("Add Rule", self.add_rule), ("Generate Agenda", self.generate_agenda),
             ("Lock Agenda", self.lock_agenda), ("Record Decision", self.record_decision)),
            (("Save Minutes", self.save_minutes), ("Chair Approve", self.chair_approve),
             ("Ratify", self.ratify), ("Reopen", self.reopen),
             ("Releasable Award", self.releasable_award), ("Refresh", self.refresh)),
            (("Propose Outcome", self.propose_outcome),
             ("Record Progression Outcome", self.record_outcome),
             ("Release Outcomes", self.release_outcomes), ("Rollover", self.rollover),
             ("Classification Rules", self.classification_rules),
             ("Preview Classification", self.preview_classification)),
        )
        # Action bars are packed before the expanding panes (window-sizing convention).
        for buttons in rows:
            bar = ttk.Frame(self, padding=(10, 2))
            bar.pack(fill="x")
            for label, command in buttons:
                ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)

        filter_bar = ttk.Frame(self, padding=(10, 2))
        filter_bar.pack(fill="x")
        ttk.Label(filter_bar, text="Academic year:").pack(side="left")
        self.year_filter = ttk.Entry(filter_bar, width=12)
        self.year_filter.pack(side="left", padx=4)
        ttk.Button(filter_bar, text="Apply", command=self.refresh).pack(side="left")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10, pady=6)
        left = ttk.Frame(panes)
        self.boards = _make_tree(left, BOARD_COLUMNS, width=80)
        self.boards.bind("<<TreeviewSelect>>", lambda _e: self.load_selected())
        panes.add(left, weight=2)

        right = ttk.Frame(panes)
        self.summary = ttk.Label(right, text="Select a board", font=("Helvetica", 11, "bold"))
        self.summary.pack(anchor="w", pady=(0, 4))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        for title, key, columns in _TABS:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            self._tabs[key] = _make_tree(frame, columns)
        minutes_frame = ttk.Frame(notebook)
        notebook.add(minutes_frame, text="Minutes")
        self.minutes_state = ttk.Label(minutes_frame, text="")
        self.minutes_state.pack(anchor="w", padx=4, pady=2)
        self.minutes = tk.Text(minutes_frame, wrap="word", height=10)
        self.minutes.pack(fill="both", expand=True, padx=4, pady=4)
        panes.add(right, weight=3)

    # ----- data ---------------------------------------------------------
    def refresh(self) -> None:
        selected = selected_id(self.boards)
        try:
            rows = service.list_boards(self.year_filter.get().strip() or None)
        except Exception as exc:  # schema missing, DB unavailable
            logger.exception("list_boards failed")
            messagebox.showerror("Error", str(exc), parent=self)
            return
        _fill(self.boards, rows, BOARD_COLUMNS)
        if selected is not None and self.boards.exists(str(selected)):
            self.boards.selection_set(str(selected))
            self.load_selected()

    def load_selected(self) -> None:
        board_id = selected_id(self.boards)
        if board_id is None:
            return
        try:
            self.board = service.get_board(board_id)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        board = self.board
        self.summary.configure(
            text=f"#{board['board_id']} {board['name']} ({board['board_type']}, "
                 f"{board['academic_year']}) [{board['status']}] v{board['version']} "
                 f"chair {board['chair_id'] or '-'}")
        try:
            board["progression"] = progression.outcomes(board["board_id"])
        except Exception:  # outcome table not created yet on this database
            logger.exception("progression outcomes unavailable")
            board["progression"] = []
        for _title, key, columns in _TABS:
            _fill(self._tabs[key], board.get(key, []), columns)
        minutes = board.get("minutes")
        self.minutes.delete("1.0", "end")
        if minutes:
            self.minutes.insert("1.0", minutes["minutes_text"])
            state = "locked" if minutes["locked"] else "editable"
            self.minutes_state.configure(
                text=f"Minutes {state}; updated {minutes['updated_at']} by {minutes['updated_by']}")
        else:
            self.minutes_state.configure(text="No minutes recorded.")

    def _require_board(self) -> int | None:
        board_id = selected_id(self.boards)
        if board_id is None:
            messagebox.showwarning("Selection", "Select a board first.", parent=self)
        return board_id

    def _selected_student(self) -> str:
        selection = self._tabs["agenda"].selection()
        if not selection:
            return ""
        return str(self._tabs["agenda"].item(selection[0], "values")[0])

    def _run(self, action, success: str) -> None:
        try:
            result = action()
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        messagebox.showinfo("Done", success.format(result=result), parent=self)
        self.refresh()

    # ----- setup --------------------------------------------------------
    def create_board(self) -> None:
        values = ask_form(self, "New assessment board", [
            Field("board_type", "Board type", kind="choice", options=sorted(service.BOARD_TYPES),
                  default="progression_award"),
            Field("name", "Board name"),
            Field("academic_year", "Academic year", default="2026/27"),
            Field("programme_code", "Programme code (blank = all)", optional=True),
            Field("module_code", "Module code (blank = all)", optional=True),
            Field("meeting_at", "Meeting at (YYYY-MM-DD HH:MM)", optional=True),
            Field("chair_id", "Chair ID", optional=True),
        ])
        if values:
            self._run(lambda: service.create_board(
                values["board_type"], values["name"], values["academic_year"],
                created_by=self.actor, programme_code=values["programme_code"],
                module_code=values["module_code"], meeting_at=values["meeting_at"],
                chair_id=values["chair_id"]), "Board #{result} created")

    def add_member(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Add board member", [
            Field("member_id", "Member ID"),
            Field("role", "Role", kind="choice",
                  options=["chair", "secretary", "member", "external_examiner"], default="member"),
        ])
        if values:
            self._run(lambda: service.add_member(board_id, values["member_id"], values["role"]),
                      "Member added")

    def add_rule(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Add compensation / condonation rule", [
            Field("rule_type", "Rule type", kind="choice", options=["compensation", "condonation"]),
            Field("minimum_mark", "Minimum mark", kind="float", optional=True),
            Field("maximum_credits", "Maximum credits", kind="float", optional=True),
            Field("exclude_core_modules", "Exclude core modules", kind="bool", default="true"),
            Field("notes", "Notes", kind="text", optional=True),
        ])
        if values:
            self._run(lambda: service.add_rule(
                board_id, values["rule_type"], minimum_mark=values["minimum_mark"],
                maximum_credits=values["maximum_credits"],
                exclude_core_modules=values["exclude_core_modules"],
                notes=values["notes"] or ""), "Rule #{result} added")

    # ----- agenda + decisions ------------------------------------------
    def generate_agenda(self) -> None:
        board_id = self._require_board()
        if board_id is not None:
            self._run(lambda: service.generate_agenda(board_id),
                      "Agenda generated: {result} student(s)")

    def lock_agenda(self) -> None:
        board_id = self._require_board()
        if board_id is not None and messagebox.askyesno(
                "Lock", f"Lock the agenda for board #{board_id}?", parent=self):
            self._run(lambda: service.lock_agenda(board_id, actor_id=self.actor), "Agenda locked")

    def record_decision(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Record board decision", [
            Field("student_id", "Student ID", default=self._selected_student()),
            Field("decision_type", "Decision", kind="choice", options=sorted(service.DECISIONS)),
            Field("rationale", "Rationale", kind="text"),
            Field("module_code", "Module code", optional=True),
            Field("original_result", "Original result", optional=True),
            Field("confirmed_result", "Confirmed result", optional=True),
            Field("credits_affected", "Credits affected", kind="float", optional=True),
            Field("classification", "Classification (award decisions)", optional=True),
            Field("supersedes_decision_id", "Supersedes decision ID", kind="int", optional=True),
        ])
        if values:
            self._run(lambda: service.record_decision(
                board_id, values.pop("student_id"), values.pop("decision_type"),
                decided_by=self.actor, **values), "Decision #{result} recorded")

    # ----- minutes, approval, ratification -----------------------------
    def save_minutes(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        text = self.minutes.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Minutes", "Enter the minutes text first.", parent=self)
            return
        self._run(lambda: service.save_minutes(board_id, text, actor_id=self.actor),
                  "Minutes saved")

    def chair_approve(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Chair approval", [Field("chair_id", "Chair ID",
                                                         default=self.actor)])
        if values:
            self._run(lambda: service.chair_approve(board_id, chair_id=values["chair_id"]),
                      "Board chair-approved; minutes locked")

    def ratify(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Ratify board", [
            Field("award_name", "Award name", default="University Award"),
        ])
        if values:
            self._run(lambda: service.ratify(board_id, ratified_by=self.actor,
                                             award_name=values["award_name"]),
                      "Board ratified; {result} award(s) released")

    def reopen(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Reopen board (independent approval required)", [
            Field("requested_by", "Requested by", default=self.actor),
            Field("approved_by", "Approved by (must differ)"),
            Field("reason", "Reason", kind="text"),
            Field("decision_id", "Decision ID under correction", kind="int", optional=True),
        ])
        if values:
            self._run(lambda: service.reopen(board_id, **values),
                      "Board reopened; correction #{result} logged")

    def releasable_award(self) -> None:
        values = ask_form(self, "Releasable award lookup", [
            Field("student_id", "Student ID", default=self._selected_student()),
        ])
        if not values:
            return
        award = service.releasable_award(values["student_id"])
        if award is None:
            messagebox.showinfo("Lookup", "No releasable award.", parent=self)
            return
        messagebox.showinfo(
            "Lookup",
            f"{award['award_name']} - {award['classification']}\n{award['programme_code']} "
            f"{award['academic_year']}\nratified {award['ratified_at']} by {award['ratified_by']}",
            parent=self)

    # ----- progression outcomes ----------------------------------------
    def propose_outcome(self) -> None:
        board_id = self._require_board()
        student = self._selected_student()
        if board_id is None:
            return
        if not student:
            messagebox.showwarning("Selection", "Select a student on the Agenda tab.",
                                   parent=self)
            return
        try:
            proposal = progression.propose(board_id, student)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        lines = [f"Proposed: {proposal['label']}", proposal["reason"],
                 f"Year {proposal['from_year']} -> {proposal['to_year'] or '-'}"]
        if proposal["trailing_modules"]:
            lines.append("Trailing: " + ", ".join(proposal["trailing_modules"]))
        if proposal["resit_modules"]:
            lines.append("Resit: " + ", ".join(proposal["resit_modules"]))
        lines.append(f"Exit award the credit already meets: {proposal['exit_award'] or 'none'}")
        messagebox.showinfo(f"Proposal for {student}", "\n".join(lines), parent=self)

    def record_outcome(self) -> None:
        board_id = self._require_board()
        if board_id is None:
            return
        values = ask_form(self, "Record progression outcome", [
            Field("student_id", "Student ID", default=self._selected_student()),
            Field("outcome", "Outcome", kind="choice", options=list(progression.OUTCOMES),
                  default="progress"),
            Field("rationale", "Rationale", kind="text"),
            Field("trailing_modules", "Trailing modules (comma-separated)", optional=True),
            Field("resit_modules", "Resit modules (blank = all failed)", optional=True),
            Field("exit_award", "Exit award (blank = highest the credit meets)", optional=True),
            Field("to_year", "Year of study next (blank = by outcome)", kind="int",
                  optional=True),
        ])
        if not values:
            return

        def split(text):
            return [m.strip() for m in (text or "").split(",") if m.strip()] or None
        self._run(lambda: progression.record_outcome(
            board_id, values["student_id"], values["outcome"], decided_by=self.actor,
            rationale=values["rationale"] or "", trailing_modules=split(values["trailing_modules"]),
            resit_modules=split(values["resit_modules"]), exit_award=values["exit_award"] or None,
            to_year=values["to_year"]), "Progression outcome #{result} recorded")

    def release_outcomes(self) -> None:
        board_id = self._require_board()
        if board_id is not None and messagebox.askyesno(
                "Release", f"Release board #{board_id}'s ratified outcomes to its students?",
                parent=self):
            self._run(lambda: progression.release(board_id, released_by=self.actor),
                      "{result} outcome(s) released; students notified")

    def rollover(self) -> None:
        board_id = self._require_board()
        if board_id is None or not messagebox.askyesno(
                "Rollover", "Apply the ratified outcomes now? Progressing students move to the "
                            "next year of study; withdrawals are applied.", parent=self):
            return
        try:
            result = progression.rollover(board_id, actor_id=self.actor)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        lines = [f"{a['student_id']}: {a['note']}" for a in result["applied"]]
        messagebox.showinfo("Rollover", "\n".join(lines) or "Nothing left to roll over.",
                            parent=self)
        self.refresh()

    def preview_classification(self) -> None:
        values = ask_form(self, "Preview classification", [
            Field("student_id", "Student ID", default=self._selected_student())])
        if not values:
            return
        try:
            result = classification_admin.preview(values["student_id"])
        except ValueError as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        award = result.get("exit_award")
        messagebox.showinfo("Classification", "\n".join([
            f"Rules: {result['rule_set']} ({result['scheme']}; {result['basis']})",
            f"Average: {result['average'] if result['average'] is not None else '-'}",
            f"Classification: {result['classification'] or '-'}"
            + (" (borderline)" if result["borderline"] else ""),
            result.get("note") or "",
            f"Exit award met: {award['name'] if award else 'none'}"]), parent=self)

    def classification_rules(self) -> None:
        ClassificationRulesWindow(self.winfo_toplevel(), self.actor,
                                  str(self.user.get("role") or ""))


class ClassificationRulesWindow(tk.Toplevel):
    """Rule sets and their bindings to regulation versions / programmes."""

    SET_COLUMNS = ["rule_set_id", "name", "scheme", "bindings", "retired", "created_by"]
    BIND_COLUMNS = ["binding_id", "version_id", "programme_code", "rule_set_id", "name",
                    "scheme", "bound_by", "bound_at"]

    def __init__(self, master, actor: str, role: str) -> None:
        super().__init__(master)
        self.actor, self.role = actor, role
        self.title("Classification Rules")
        _center(self, 1400, 900, minsize=(1200, 800))
        self.transient(master)
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(fill="x")
        for label, command in (("New Rule Set", self.create), ("View Rules", self.view),
                               ("Bind to Regulation / Programme", self.bind),
                               ("Remove Binding", self.unbind), ("Refresh", self.refresh)):
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        ttk.Label(self, padding=(10, 0), text=(
            "Students on unbound regulations keep the university default (Level 5 x1, "
            "Level 6 x2, 2-mark borderline flag).")).pack(anchor="w")
        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=10, pady=6)
        top, bottom = ttk.Frame(panes), ttk.Frame(panes)
        panes.add(top, weight=1)
        panes.add(bottom, weight=1)
        self.sets = _make_tree(top, self.SET_COLUMNS)
        self.binds = _make_tree(bottom, self.BIND_COLUMNS)
        self.refresh()

    def refresh(self) -> None:
        try:
            _fill(self.sets, classification_admin.rule_sets(), self.SET_COLUMNS)
            _fill(self.binds, classification_admin.bindings(), self.BIND_COLUMNS)
        except Exception as exc:
            logger.exception("classification rules unavailable")
            messagebox.showerror("Error", str(exc), parent=self)

    def _do(self, action, success: str) -> None:
        try:
            result = action()
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Error", str(exc), parent=self)
            return
        messagebox.showinfo("Done", success.format(result=result), parent=self)
        self.refresh()

    def create(self) -> None:
        first = ask_form(self, "New rule set", [
            Field("scheme", "Scheme", kind="choice", options=list(classification_admin.SCHEMES),
                  default="ug_honours")])
        if not first:
            return
        values = ask_form(self, "New rule set", [
            Field("name", "Name (e.g. UG Honours 2026 regulations)"),
            Field("config", "Rules (JSON; sector-norm starting point shown)", kind="text",
                  default=classification_admin.template(first["scheme"])),
            Field("notes", "Notes", kind="text", optional=True),
        ])
        if values:
            self._do(lambda: classification_admin.create(
                values["name"], first["scheme"], values["config"], actor=self.actor,
                role=self.role, notes=values["notes"] or ""), "Rule set #{result} created")

    def view(self) -> None:
        rule_set_id = selected_id(self.sets)
        if rule_set_id is None:
            messagebox.showwarning("Selection", "Select a rule set.", parent=self)
            return
        found = classification_admin.show(rule_set_id)
        import json as _json
        messagebox.showinfo(found["name"], f"Scheme: {found['scheme']}\n\n"
                            + _json.dumps(found["config"], indent=2), parent=self)

    def bind(self) -> None:
        values = ask_form(self, "Bind rule set", [
            Field("rule_set_id", "Rule set ID", kind="int",
                  default=str(selected_id(self.sets) or "")),
            Field("version_id", "Regulation version ID (programme governance)", kind="int",
                  optional=True),
            Field("programme_code", "or Programme code (ungoverned programmes)", optional=True),
        ])
        if values:
            self._do(lambda: classification_admin.bind(
                values["rule_set_id"], actor=self.actor, role=self.role,
                version_id=values["version_id"], programme_code=values["programme_code"]),
                "Binding #{result} saved")

    def unbind(self) -> None:
        binding_id = selected_id(self.binds)
        if binding_id is None:
            messagebox.showwarning("Selection", "Select a binding.", parent=self)
            return
        if messagebox.askyesno("Remove", f"Remove binding #{binding_id}?", parent=self):
            self._do(lambda: classification_admin.unbind(binding_id, role=self.role),
                     "Binding removed")


def open_my_outcomes(master, auth: Any = None) -> tk.Toplevel | None:
    """A student's own released progression outcomes (nothing before release)."""
    user = session_user(auth) or {}
    student_id = progression.student_id_for(user)
    if not student_id:
        messagebox.showwarning("My Progression", "Sign in as a student to see your outcome.",
                               parent=master)
        return None
    top = tk.Toplevel(master)
    top.title("My Progression Outcome")
    _center(top, 1400, 900, minsize=(1200, 800))
    ttk.Label(top, padding=10, font=("Helvetica", 13, "bold"),
              text=f"Progression outcomes for {student_id}").pack(anchor="w")
    tree = _make_tree(top, MY_OUTCOME_COLUMNS, width=140)
    try:
        rows = progression.my_outcomes(student_id)
    except Exception:
        logger.exception("my outcomes failed")
        rows = []
    _fill(tree, rows, MY_OUTCOME_COLUMNS)
    if not rows:
        ttk.Label(top, padding=10, text="No outcome has been released to you yet. Outcomes "
                  "appear here once the assessment board has ratified and released them."
                  ).pack(anchor="w")
    return top


def open_window(master, auth: Any = None) -> tk.Toplevel | None:
    """Open the window as a Toplevel of ``master`` for a staff session."""
    if not is_staff(session_user(auth)):
        messagebox.showwarning(WINDOW_TITLE, "Assessment boards are restricted to staff.",
                               parent=master)
        return None
    top = tk.Toplevel(master)
    top.title(_t("gui.assessment.boards.title", default=WINDOW_TITLE))
    _center(top, 1400, 900, minsize=(1200, 800))
    AssessmentBoardsWindow(top, auth=auth).pack(fill="both", expand=True)
    return top


def main() -> None:
    """Standalone launch (subprocess fallback from the main GUI)."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    _center(root, 1400, 900, minsize=(1200, 800))
    if not is_staff(session_user()):
        messagebox.showwarning(WINDOW_TITLE, "Assessment boards are restricted to staff.")
        root.destroy()
        return
    AssessmentBoardsWindow(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
