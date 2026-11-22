"""Standalone Tk window for the shared case register.

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``), so the
signed-in user arrives through the ``EDU_AUTH_*`` env bundle and is resolved
by ``require_launcher_auth``. Staff only. Backed entirely by
``application.case_management``; nothing touches the DB at import time. The
"Academic Appeals" tab runs the appeals procedure (``appeals_panel``).
"""
from __future__ import annotations

import logging
import pathlib
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

from education_system.systems.university.application import case_management  # noqa: E402
from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

logger = logging.getLogger(__name__)

STATUSES = ("open", "triage", "investigation", "hearing", "decision", "review", "closed")
STAFF_ROLES = ("admin", "administrator", "staff")


class CaseManagementApp(tk.Frame):
    """List of cases on the left, the selected case's record and events on the right."""

    def __init__(self, parent, user=None):
        super().__init__(parent)
        self._user = user or {}
        self._actor = str(self._user.get("username") or self._user.get("id") or "unknown")
        self._build()
        self.refresh()

    # ---- layout -------------------------------------------------------
    def _build(self):
        header = tk.Frame(self, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("gui.governance.case_management.title", default="Case Management"),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=16, pady=8)
        tk.Label(header, text=f"Signed in: {self._actor} ({self._user.get('role') or '-'})",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)

        # The shared register and the academic appeals procedure, one tab each.
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        register = tk.Frame(notebook)
        notebook.add(register, text="Case Register")
        try:
            from education_system.systems.university.domains.governance.interfaces.gui.case_management.appeals_panel import (  # noqa: E501
                AppealsPanel,
            )
            notebook.add(AppealsPanel(notebook, user=self._user), text="Academic Appeals")
        except Exception:
            logger.exception("Academic appeals panel unavailable")

        # Action bar is packed before the expanding panes (memory: window sizing).
        bar = tk.Frame(register)
        bar.pack(fill="x", padx=8, pady=6)
        tk.Label(bar, text="Type:").pack(side="left")
        self._type_var = tk.StringVar(value="")
        ttk.Combobox(bar, textvariable=self._type_var, width=22, state="readonly",
                     values=("",) + tuple(sorted(case_management.CASE_TYPES))).pack(side="left", padx=4)
        tk.Label(bar, text="Status:").pack(side="left")
        self._status_var = tk.StringVar(value="")
        ttk.Combobox(bar, textvariable=self._status_var, width=14, state="readonly",
                     values=("",) + STATUSES).pack(side="left", padx=4)
        for label, cmd in (("Refresh", self.refresh), ("Open Case", self.open_case),
                           ("Change Status", self.transition)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)

        panes = ttk.PanedWindow(register, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("case_id", "case_type", "subject_id", "status", "opened_at")
        self._tree = ttk.Treeview(panes, columns=cols, show="headings")
        for col, width in zip(cols, (260, 150, 90, 100, 140)):
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=width, stretch=col == "case_id")
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self.show_detail())
        panes.add(self._tree, weight=3)
        self._detail = tk.Text(panes, wrap="word", state="disabled", width=50)
        panes.add(self._detail, weight=2)

    # ---- data ---------------------------------------------------------
    def _selected_id(self) -> str | None:
        sel = self._tree.focus()
        return self._tree.item(sel, "values")[0] if sel else None

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        try:
            rows = case_management.list_cases(
                case_type=self._type_var.get() or None, status=self._status_var.get() or None)
        except Exception as exc:
            logger.exception("Case list failed")
            messagebox.showerror("Error", f"Could not load cases:\n{exc}", parent=self)
            return
        for case in rows:
            self._tree.insert("", "end", values=(
                case["case_id"], case["case_type"], case["subject_id"] or "",
                case["status"] or "", str(case["opened_at"] or "")[:19]))
        self._set_detail("")

    def _set_detail(self, text: str):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def show_detail(self):
        case_id = self._selected_id()
        if not case_id:
            return
        try:
            record = case_management.case_record(case_id)
        except ValueError as exc:
            self._set_detail(str(exc))
            return
        events = record.pop("events", [])
        lines = [f"{key}: {value}" for key, value in record.items()]
        lines.append(f"\nEvents ({len(events)}):")
        for event in events:
            lines.append(f"  {str(event.get('created_at') or '')[:19]}  {event.get('event_type')}  "
                         f"by {event.get('actor_id') or '-'}\n    {event.get('payload_json') or ''}")
        self._set_detail("\n".join(lines))

    # ---- actions ------------------------------------------------------
    def open_case(self):
        case_type = simpledialog.askstring(
            "Open Case", "Case type:\n" + ", ".join(sorted(case_management.CASE_TYPES)), parent=self)
        if not case_type:
            return
        subject = simpledialog.askstring("Open Case", "Subject (student/staff id):", parent=self)
        summary = simpledialog.askstring("Open Case", "Summary:", parent=self)
        if subject is None or summary is None:
            return
        try:
            case_id = case_management.open_case(
                case_type.strip(), subject.strip(), summary.strip(), opened_by=self._actor)
        except ValueError as exc:
            messagebox.showerror("Open Case", str(exc), parent=self)
            return
        messagebox.showinfo("Open Case", f"Case {case_id} opened.", parent=self)
        self.refresh()

    def transition(self):
        case_id = self._selected_id()
        if not case_id:
            messagebox.showwarning("Change Status", "Select a case first.", parent=self)
            return
        status = simpledialog.askstring(
            "Change Status", "New status:\n" + ", ".join(STATUSES), parent=self)
        if not status:
            return
        reason = simpledialog.askstring("Change Status", "Reason:", parent=self)
        if reason is None:
            return
        try:
            case_management.transition_case(
                case_id, status.strip(), actor_id=self._actor, reason=reason.strip())
        except ValueError as exc:
            messagebox.showerror("Change Status", str(exc), parent=self)
            return
        self.refresh()


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.shell.gui.auth.launch_guard import require_launcher_auth

    user = require_launcher_auth("Case Management")
    if user is None:
        return
    if str(user.get("role", "")).lower() not in STAFF_ROLES:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Case Management", "Case management is available to staff only.")
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.governance.case_management.title", default="Case Management"))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    CaseManagementApp(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
