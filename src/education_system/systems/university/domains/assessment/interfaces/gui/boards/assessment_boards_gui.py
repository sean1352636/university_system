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
from education_system.systems.university.domains.assessment.domain.boards import service
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
]


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
        except ValueError as exc:
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
