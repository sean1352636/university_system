"""Student Records tools: a student's change history, reinstating a
withdrawn student, and the data check (issues and confirmed fixes).

Rules live in ``university/application`` (``student_record_rules``,
``student_lifecycle_service``, ``student_data_quality``).
"""

import logging
import secrets
import tkinter as tk
from contextlib import closing
from tkinter import messagebox, simpledialog, ttk

from education_system.platform.delivery.gui.tk_callback_filter import (
    install_clean_close as _install_clean_close,
)
from education_system.systems.university.infrastructure.database.db import get_connection

from .authorization import require_student_permission

logger = logging.getLogger(__name__)


def _actor(self):
    user = getattr(getattr(self, "auth", None), "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _read(parent, fn, *args, write=False):
    try:
        with closing(get_connection(row_factory=False)) as conn:
            result = fn(conn, *args)
            if write:
                conn.commit()
            return result
    except Exception as exc:
        logger.exception("student records tool failed")
        messagebox.showerror("Student records", f"That did not work: {exc}", parent=parent)
        return None


def _table(win, columns, height=14):
    tree = ttk.Treeview(win, columns=[c for c, _t, _w in columns], show="headings",
                        height=height)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w")
    bar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    bar.pack(side=tk.RIGHT, fill=tk.Y, pady=8)
    tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    return tree


def show_change_history(self, student_id):
    """Every recorded change to the student: field edits (from, to, reason,
    by) and registration-status changes."""
    from education_system.systems.university.application.students import (
        record_rules as student_record_rules,
    )
    rows = _read(self.root, student_record_rules.change_history, str(student_id))
    if rows is None:
        return
    win = tk.Toplevel(self.root)
    _install_clean_close(win)
    win.title(f"Changes — {student_id}")
    win.geometry("980x480")
    tree = _table(win, (("when", "When", 150), ("what", "What", 150), ("old", "From", 170),
                        ("new", "To", 170), ("reason", "Reason", 220), ("by", "By", 100)))
    for i, r in enumerate(rows):
        tree.insert("", "end", iid=str(i), values=(r["when"], r["what"], r["old"] or "",
                                                   r["new"] or "", r["reason"] or "",
                                                   r["by"] or ""))
    if not rows:
        tree.insert("", "end", values=("", "No changes recorded yet", "", "", "", ""))


def reinstate_student(self, student_id):
    """Undo a withdrawal: back to Active with sign-in switched on."""
    if not require_student_permission(self, "update_any_student", "reinstate"):
        return False
    reason = simpledialog.askstring("Reinstate", f"Why is {student_id} being reinstated?",
                                    parent=self.root)
    if not reason or not reason.strip():
        return False
    from education_system.systems.university.application.students.lifecycle import (
        StudentLifecycleService,
        StudentValidationError,
    )
    try:
        StudentLifecycleService().restore(
            str(student_id), actor_id=_actor(self), reason=reason.strip(),
            idempotency_key=f"gui:student:{student_id}:reinstate:{secrets.token_urlsafe(12)}")
    except StudentValidationError as exc:
        messagebox.showerror("Reinstate", "; ".join(exc.errors.values()), parent=self.root)
        return False
    messagebox.showinfo("Reinstate", f"{student_id} is Active again and can sign in.",
                        parent=self.root)
    return True


def data_check_dialog(self):
    """List the problems in the student records; apply the safe fixes for
    the rows the user ticks (selects) and confirms."""
    if not require_student_permission(self, "update_any_student", "correct"):
        return
    from education_system.systems.university.application.students import (
        data_quality as student_data_quality,
    )
    win = tk.Toplevel(self.root)
    _install_clean_close(win)
    win.title("Student records — data check")
    win.geometry("1000x520")
    ttk.Label(win, padding=8, wraplength=960, text=(
        "Select the rows to fix and press 'Apply selected fixes'. Rows without a fix need "
        "someone to correct the record by hand. Every fix is written to the student's "
        "change history.")).pack(anchor="w")
    tree = _table(win, (("student", "Student", 100), ("name", "Name", 170),
                        ("kind", "Problem", 90), ("detail", "Detail", 360),
                        ("fix", "Fix", 220)))
    tree.configure(selectmode="extended")

    def load():
        tree.delete(*tree.get_children())
        for issue in _read(win, student_data_quality.issues) or []:
            fix = ", ".join(f"{k} → {v}" for k, v in (issue["fix"] or {}).items())
            tree.insert("", "end", iid=issue["key"], values=(
                issue["student_id"], issue["name"], issue["kind"], issue["detail"],
                fix or "— needs a person"))

    def apply():
        keys = list(tree.selection())
        if not keys or not messagebox.askyesno(
                "Data check", f"Apply the fixes for {len(keys)} selected row(s)?", parent=win):
            return
        changed = _read(win, lambda conn: student_data_quality.apply_fixes(
            conn, keys, _actor(self)), write=True)
        if changed is not None:
            messagebox.showinfo("Data check", f"{changed} record(s) corrected.", parent=win)
            load()

    bar = ttk.Frame(win)
    bar.pack(fill=tk.X, padx=8, pady=(0, 8))
    ttk.Button(bar, text="Apply selected fixes", command=apply).pack(side=tk.LEFT)
    ttk.Button(bar, text="Refresh", command=load).pack(side=tk.LEFT, padx=6)
    load()
