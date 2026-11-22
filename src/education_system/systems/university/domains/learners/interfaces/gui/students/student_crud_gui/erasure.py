"""Permanent erasure of a student's personal data, under dual control.

The rules are in ``university/application/students/erasure``; this module
only presents them: raise a request from the withdraw dialog, and decide or
carry out requests from Student Records > Erasure requests.
"""

import logging
import tkinter as tk
from contextlib import closing
from tkinter import messagebox, simpledialog, ttk

from education_system.platform.delivery.gui.tk_callback_filter import (
    install_clean_close as _install_clean_close,
)
from education_system.systems.university.infrastructure.database.db import get_connection

from .authorization import require_student_permission

logger = logging.getLogger(__name__)
TITLE = "Erasure"


def _rules():
    from education_system.systems.university.application.students import erasure as student_erasure
    return student_erasure


def _username(self):
    user = getattr(getattr(self, "auth", None), "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _run(parent, fn, *args, write=False, **kwargs):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args, **kwargs)
            if write:
                conn.commit()
            return True if result is None else result
    except ValueError as exc:
        messagebox.showerror(TITLE, str(exc), parent=parent)
    except Exception as exc:
        logger.exception("erasure action failed")
        messagebox.showerror(TITLE, f"That did not work: {exc}", parent=parent)
    return None


def request_erasure_dialog(self, parent, student_id):
    """Record an erasure request (case reference + reason)."""
    if not require_student_permission(self, "delete_any_student", "request erasure for"):
        return
    win = tk.Toplevel(parent)
    _install_clean_close(win)
    win.title(f"Request erasure — {student_id}")
    body = ttk.Frame(win, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, wraplength=460, justify="left", text=(
        "Permanent erasure removes the student's personal data. Results, finance and "
        "status history are kept under an anonymous id; transcripts can no longer be "
        "produced. The student must already be withdrawn. Someone else must approve the "
        "request (with their password) before it can be carried out.")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    entries = {}
    for row, (key, label) in enumerate((("case", "Case reference *"), ("reason", "Reason *")), 1):
        ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=3)
        entries[key] = ttk.Entry(body, width=44)
        entries[key].grid(row=row, column=1, sticky="w", pady=3)

    def submit():
        rid = _run(win, _rules().request, str(student_id), entries["case"].get(),
                   entries["reason"].get(), _username(self), write=True)
        if rid:
            messagebox.showinfo(TITLE, f"Request #{rid} recorded. It now needs approval under "
                                "Student Records > Erasure requests.", parent=win)
            win.destroy()
    ttk.Button(body, text="Submit request", command=submit).grid(row=3, column=1, sticky="w",
                                                                pady=8)


def manage_erasure_requests(self):
    """List requests; approve or reject (password re-entry, not the
    requester); carry out approved ones."""
    if not require_student_permission(self, "delete_any_student", "manage erasure of"):
        return
    win = tk.Toplevel(self.root)
    _install_clean_close(win)
    win.title("Erasure requests")
    win.geometry("980x520")
    tree = ttk.Treeview(win, columns=("id", "student", "case", "status", "by", "decided", "holds"),
                        show="headings", height=12)
    for key, title, width in (("id", "#", 50), ("student", "Student", 110),
                              ("case", "Case", 120), ("status", "Status", 90),
                              ("by", "Requested by", 110), ("decided", "Decided by", 110),
                              ("holds", "Rows affected", 300)):
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    rows = {}

    def load():
        tree.delete(*tree.get_children())
        rows.clear()
        for r in _run(win, _rules().requests) or []:
            rows[str(r["request_id"])] = r
            affected = sum(v["rows"] for v in r["impact"].values())
            tree.insert("", "end", iid=str(r["request_id"]), values=(
                r["request_id"], r["student_id"], r["case_reference"], r["status"],
                r["requested_by"], r["decided_by"] or "", f"{affected} rows in "
                f"{len(r['impact'])} tables"))

    def selected():
        r = rows.get((tree.selection() or [""])[0])
        if not r:
            messagebox.showinfo(TITLE, "Select a request first.", parent=win)
        return r

    def decide(approve):
        r = selected()
        if not r:
            return
        password = simpledialog.askstring(TITLE, "Re-enter your password to decide:",
                                          show="*", parent=win)
        if password is None:
            return
        from education_system.systems.university.services.student_provisioning import (
            verify_staff_password,
        )
        ok = verify_staff_password(_username(self), password)
        note = simpledialog.askstring(TITLE, "Note (optional):", parent=win) or ""
        if _run(win, _rules().decide, r["request_id"], approve, _username(self),
                reauthenticated=ok, note=note, write=True):
            load()

    def details():
        r = selected()
        if r:
            holds = _run(win, _rules().legal_holds, r["student_id"]) or []
            lines = [f"{k}: {v['rows']} row(s), {v['fate']}" for k, v in r["impact"].items()]
            messagebox.showinfo(TITLE, f"Reason: {r['reason']}\n\nLegal holds now: "
                                f"{'; '.join(holds) if holds else 'none'}\n\n"
                                + "\n".join(lines[:40]), parent=win)

    def execute():
        r = selected()
        if not r or not messagebox.askyesno(
                TITLE, f"Permanently erase student {r['student_id']}'s personal data?\n\n"
                "This cannot be undone.", parent=win):
            return
        result = _run(win, _rules().execute, r["request_id"], _username(self), write=True)
        if result:
            from education_system.systems.university.services.student_provisioning import (
                erase_student_login,
            )
            erase_student_login(result["login"])
            messagebox.showinfo(TITLE, f"Done. The record is now {result['anonymous_id']}.",
                                parent=win)
            load()

    bar = ttk.Frame(win)
    bar.pack(fill=tk.X, padx=8, pady=(0, 8))
    for label, command in (("Details…", details), ("Approve…", lambda: decide(True)),
                           ("Reject…", lambda: decide(False)), ("Carry out…", execute),
                           ("Refresh", load)):
        ttk.Button(bar, text=label, command=command).pack(side=tk.LEFT, padx=2)
    load()
