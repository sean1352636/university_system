"""Academic Appeals panel: the appeals procedure over ``application.cases.appeals``.

Embedded as the "Academic Appeals" tab of the Case Management window (staff)
and as the whole of the Academic Appeals window (``appeals_app``), where a
student sees only their own appeals. Every dialog is parented to this panel's
window; nothing touches the database at import time.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any

from education_system.platform.delivery.gui.form_dialog import Field, ask_form
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.platform.delivery.gui.treeview_helpers import (
    fill_tree as _fill,
    make_tree as _make_tree,
    selected_id,
)
from education_system.systems.university.application.cases import appeals
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)

COLUMNS = ["appeal_id", "student_id", "stage", "grounds", "module_code", "board_id", "handler",
           "stage_due", "overdue", "outcome", "submitted_at", "closed_at"]
ACTION_COLUMNS = ["action_id", "action_type", "status", "assigned_to", "result", "created_at",
                  "completed_at"]


class AppealsPanel(ttk.Frame):
    """Appeals list on the left; the selected appeal, its actions and history on the right."""

    def __init__(self, parent, user: dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.who = appeals.who_from_user(user)
        self._build()
        self.refresh()

    # ----- layout -------------------------------------------------------
    def _buttons(self):
        if not self.who.is_staff:
            return ((("Submit Appeal", self.submit), ("Request Review", self.request_review),
                     ("Withdraw", self.withdraw), ("Save COP Letter", self.save_letter),
                     ("Refresh", self.refresh)),)
        return (
            (("Submit Appeal", self.submit), ("Assign Handler", self.assign),
             ("Start Eligibility", self.start_eligibility),
             ("Decide Eligibility", self.decide_eligibility),
             ("Record Outcome", self.record_outcome), ("Complete Action", self.complete_action),
             ("Retry Board Reconvene", self.retry_action)),
            (("Decide Review", self.decide_review), ("Close + COP Letter", self.close),
             ("Withdraw", self.withdraw), ("Save COP Letter", self.save_letter),
             ("Send Reminders", self.send_reminders), ("OIA Statistics", self.statistics),
             ("Refresh", self.refresh)),
        )

    def _build(self) -> None:
        # Action bars are packed before the expanding panes (window-sizing convention).
        for row in self._buttons():
            bar = ttk.Frame(self, padding=(8, 2))
            bar.pack(fill="x")
            for label, command in row:
                ttk.Button(bar, text=label, command=command).pack(side="left", padx=2)
        filters = ttk.Frame(self, padding=(8, 2))
        filters.pack(fill="x")
        ttk.Label(filters, text="Stage:").pack(side="left")
        self.stage_var = tk.StringVar(value="")
        stage = ttk.Combobox(filters, textvariable=self.stage_var, width=14, state="readonly",
                             values=("",) + appeals.STAGES)
        stage.pack(side="left", padx=4)
        stage.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        self.overdue_var = tk.BooleanVar(value=False)
        if self.who.is_staff:
            ttk.Checkbutton(filters, text="Overdue only", variable=self.overdue_var,
                            command=self.refresh).pack(side="left", padx=8)
        self.status = ttk.Label(filters, text="")
        self.status.pack(side="right")

        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(panes)
        self.tree = _make_tree(left, COLUMNS, width=90)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        panes.add(left, weight=3)
        right = ttk.Frame(panes)
        self.detail = tk.Text(right, wrap="word", height=18, state="disabled")
        self.detail.pack(fill="both", expand=True)
        ttk.Label(right, text="Actions").pack(anchor="w", pady=(6, 0))
        actions = ttk.Frame(right, height=160)
        actions.pack(fill="both", expand=False)
        self.actions = _make_tree(actions, ACTION_COLUMNS, width=90)
        panes.add(right, weight=2)

    # ----- data ---------------------------------------------------------
    def refresh(self) -> None:
        try:
            rows = appeals.list_appeals(self.who, stage=self.stage_var.get() or None)
        except Exception as exc:
            logger.exception("Appeals list failed")
            messagebox.showerror("Appeals", f"Could not load appeals:\n{exc}", parent=self)
            return
        if self.overdue_var.get():
            rows = [r for r in rows if r["overdue"]]
        for row in rows:
            row["overdue"] = "yes" if row["overdue"] else ""
        _fill(self.tree, rows, COLUMNS)
        if not rows:
            self.status.configure(text="No appeals to show.")
        else:
            self.status.configure(text=f"{len(rows)} appeal(s)")
        self._set_detail("")
        _fill(self.actions, [], ACTION_COLUMNS)

    def _set_detail(self, text: str) -> None:
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.config(state="disabled")

    def show_detail(self) -> None:
        appeal_id = selected_id(self.tree)
        if appeal_id is None:
            return
        try:
            record = appeals.detail(self.who, appeal_id)
        except (ValueError, PermissionError) as exc:
            self._set_detail(str(exc))
            return
        _fill(self.actions, record.pop("actions"), ACTION_COLUMNS)
        events = record.pop("events", [])
        board = record.pop("board_state", None)
        lines = [f"{record['reference']}  [{record['stage']}]  due {record['stage_due'] or '-'}",
                 f"Grounds: {appeals.GROUNDS.get(record['grounds'], record['grounds'])}", ""]
        for key in ("student_id", "module_code", "assessment_name", "current_result", "board_id",
                    "board_decision_id", "progression_outcome_id", "submitted_at",
                    "submission_deadline", "late_reason", "handler", "eligibility_decision",
                    "eligibility_reason", "outcome", "outcome_rationale", "final_decision_date",
                    "review_reason", "review_outcome", "review_rationale", "cop_issued_at",
                    "cop_path", "ticket_id"):
            if record.get(key) not in (None, ""):
                lines.append(f"{key.replace('_', ' ')}: {record[key]}")
        lines += ["", "Statement:", record["statement"]]
        if record["issues_considered"]:
            lines += ["", "Issues considered:"] + [f"  - {i}" for i in record["issues_considered"]]
        if board and board.get("board"):
            award = board.get("award")
            lines += ["", f"Board {record['board_id']}: {board['board']['status']} "
                          f"(version {board['board']['version']})",
                      "Current award: " + (f"{award['award_name']} {award['classification'] or ''}"
                                           f" [{award['status']}]" if award else "none")]
        if events:
            lines += ["", f"Case history ({len(events)}):"]
            lines += [f"  {str(e.get('created_at') or '')[:19]}  {e.get('event_type')}  by "
                      f"{e.get('actor_id') or '-'}" for e in events]
        self._set_detail("\n".join(lines))

    def _selected(self) -> int | None:
        appeal_id = selected_id(self.tree)
        if appeal_id is None:
            messagebox.showwarning("Appeals", "Select an appeal first.", parent=self)
        return appeal_id

    def _run(self, action, success: str) -> None:
        try:
            result = action()
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Appeals", str(exc), parent=self)
            return
        except Exception as exc:
            logger.exception("Appeal action failed")
            messagebox.showerror("Appeals", f"The action failed:\n{exc}", parent=self)
            return
        messagebox.showinfo("Appeals", success.format(result=result), parent=self)
        self.refresh()

    # ----- actions ------------------------------------------------------
    def submit(self) -> None:
        fields = [Field("grounds", "Grounds", kind="choice", options=list(appeals.GROUNDS)),
                  Field("statement", "What happened and why the decision should change",
                        kind="text"),
                  Field("module_code", "Module code (if a module result)", optional=True),
                  Field("assessment_name", "Assessment (optional)", optional=True),
                  Field("board_id", "Board ID (if a board decision)", kind="int", optional=True),
                  Field("results_released_on", "Results released on (YYYY-MM-DD)",
                        optional=True),
                  Field("late_reason", "Reason if late", optional=True)]
        if self.who.is_staff:
            fields.insert(0, Field("student_id", "Student ID"))
        values = ask_form(self, "Submit an academic appeal", fields)
        if not values:
            return
        student_id = values.pop("student_id", None) or self.who.student_id
        self._run(lambda: appeals.submit(self.who, student_id, values.pop("grounds"),
                                         values.pop("statement"), **values),
                  "Appeal APL-{result:05d} submitted.")

    def assign(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Assign handler", [Field("handler",
                                                                       "Handler username")])
        if values:
            self._run(lambda: appeals.assign(self.who, appeal_id, values["handler"]),
                      "Handler assigned.")

    def start_eligibility(self) -> None:
        appeal_id = self._selected()
        if appeal_id:
            self._run(lambda: appeals.start_eligibility(self.who, appeal_id),
                      "Eligibility check started.")

    def decide_eligibility(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Eligibility decision", [
            Field("eligible", "Eligible (admissible grounds, in time or late with good reason)",
                  kind="bool", default="true"),
            Field("reason", "Reason", kind="text")])
        if values:
            self._run(lambda: appeals.decide_eligibility(self.who, appeal_id, values["eligible"],
                                                         values["reason"]),
                      "Eligibility decided.")

    def record_outcome(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Record the appeal outcome", [
            Field("outcome", "Outcome", kind="choice",
                  options=["upheld", "partly_upheld", "not_upheld"]),
            Field("rationale", "Reasons", kind="text"),
            Field("issues", "Issues considered (one per line)", kind="text"),
            Field("remark", "Action: re-mark the module result", kind="bool"),
            Field("remarker", "Re-marker (username)", optional=True),
            Field("uncapped_resit", "Action: uncapped resit", kind="bool"),
            Field("board_reconvene", "Action: reconvene the assessment board", kind="bool"),
            Field("approved_by", "Independent approver for the reconvene", optional=True)])
        if not values:
            return
        actions = []
        if values["remark"]:
            actions.append({"type": "remark", "assigned_to": values["remarker"]})
        if values["uncapped_resit"]:
            actions.append({"type": "uncapped_resit"})
        if values["board_reconvene"]:
            actions.append({"type": "board_reconvene", "approved_by": values["approved_by"]})
        self._run(lambda: appeals.record_outcome(self.who, appeal_id, values["outcome"],
                                                 values["rationale"], values["issues"],
                                                 actions),
                  "Outcome recorded; actions: {result[actions]}")

    def _selected_action(self) -> int | None:
        action_id = selected_id(self.actions)
        if action_id is None:
            messagebox.showwarning("Appeals", "Select an action first.", parent=self)
        return action_id

    def complete_action(self) -> None:
        action_id = self._selected_action()
        values = action_id and ask_form(self, "Complete action", [
            Field("result", "What it produced (e.g. new mark, resit arranged)", kind="text")])
        if values:
            self._run(lambda: appeals.complete_action(self.who, action_id, values["result"]),
                      "Action completed.")

    def retry_action(self) -> None:
        action_id = self._selected_action()
        if action_id:
            self._run(lambda: appeals.retry_action(self.who, action_id),
                      "Board reconvene: {result[status]}")

    def request_review(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Request a review", [
            Field("reason", "Why the outcome should be reviewed", kind="text")])
        if values:
            self._run(lambda: appeals.request_review(self.who, appeal_id, values["reason"]),
                      "Review requested.")

    def decide_review(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Review decision", [
            Field("review_outcome", "Review outcome", kind="choice",
                  options=list(appeals.REVIEW_OUTCOMES)),
            Field("rationale", "Reasons", kind="text")])
        if values:
            self._run(lambda: appeals.decide_review(self.who, appeal_id, values["review_outcome"],
                                                    values["rationale"]),
                      "Review decided.")

    def close(self) -> None:
        appeal_id = self._selected()
        if appeal_id and messagebox.askyesno(
                "Close appeal", "Close the appeal and issue the Completion of Procedures "
                                "letter?", parent=self):
            self._run(lambda: appeals.close(self.who, appeal_id),
                      "Closed. Letter: {result[path]}\nOIA deadline: {result[oia_deadline]}")

    def withdraw(self) -> None:
        appeal_id = self._selected()
        values = appeal_id and ask_form(self, "Withdraw appeal", [
            Field("reason", "Reason", optional=True)])
        if values is not None and values:
            self._run(lambda: appeals.withdraw(self.who, appeal_id, values["reason"] or ""),
                      "Appeal withdrawn.")

    def save_letter(self) -> None:
        appeal_id = self._selected()
        if not appeal_id:
            return
        try:
            data = appeals.cop_letter_pdf(self.who, appeal_id)
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Appeals", str(exc), parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".pdf",
                                            initialfile=f"COP-APL-{appeal_id:05d}.pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if path:
            with open(path, "wb") as handle:
                handle.write(data)
            messagebox.showinfo("Appeals", f"Saved {path}", parent=self)

    def send_reminders(self) -> None:
        self._run(lambda: appeals.send_reminders(self.who),
                  "Reminders sent for {result} overdue appeal(s).")

    def statistics(self) -> None:
        values = ask_form(self, "OIA case statistics", [
            Field("date_from", "From (YYYY-MM-DD)", optional=True),
            Field("date_to", "To (YYYY-MM-DD)", optional=True)])
        if values is None:
            return
        try:
            stats = appeals.statistics(self.who, values["date_from"], values["date_to"])
        except (ValueError, PermissionError) as exc:
            messagebox.showerror("Appeals", str(exc), parent=self)
            return
        top = tk.Toplevel(self)
        top.title(_t("gui.governance.appeals.statistics", default="Appeals — OIA statistics"))
        top.transient(self.winfo_toplevel())
        bar = ttk.Frame(top, padding=6)
        bar.pack(fill="x")
        text = tk.Text(top, wrap="none", width=70, height=30)
        ttk.Button(bar, text="Save CSV", command=lambda: self._save_csv(top, stats)).pack(
            side="left")
        text.pack(fill="both", expand=True)
        text.insert("1.0", appeals.statistics_text(stats))
        text.config(state="disabled")

    def _save_csv(self, parent, stats) -> None:
        path = filedialog.asksaveasfilename(parent=parent, defaultextension=".csv",
                                            initialfile="appeals_oia_statistics.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(appeals.statistics_csv(stats))
            messagebox.showinfo("Appeals", f"Saved {path}", parent=parent)
