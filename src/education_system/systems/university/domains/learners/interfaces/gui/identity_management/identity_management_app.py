"""Standalone Tk window for controlled student identity changes.

Launched as a subprocess by the main GUI (``_NEW_FEATURE_MODULES``); the
signed-in user arrives via ``require_launcher_auth``. Admin only: merges and
reversals are dual-control, so the signed-in user is the requester and a
different approver must be named. Backed by
``domains.learners.application.identity_management``; no DB access at import.
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

from education_system.systems.university.domains.learners.application import (  # noqa: E402
    identity_management,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t  # noqa: E402

logger = logging.getLogger(__name__)

ADMIN_ROLES = ("admin", "administrator")


class IdentityManagementApp(tk.Frame):
    """Merge register on the left; a looked-up student's identity and history on the right."""

    def __init__(self, parent, user=None):
        super().__init__(parent)
        self._user = user or {}
        self._actor = str(self._user.get("username") or self._user.get("id") or "unknown")
        self._build()
        self.refresh()

    def _build(self):
        header = tk.Frame(self, bg="#2c3e50")
        header.pack(fill="x")
        tk.Label(header, text=_t("gui.learners.identity_management.title",
                                 default="Student Identity Management"),
                 font=("Helvetica", 14, "bold"), bg="#2c3e50", fg="white").pack(side="left", padx=16, pady=8)
        tk.Label(header, text=f"Signed in: {self._actor} ({self._user.get('role') or '-'})",
                 bg="#2c3e50", fg="#bdc3c7").pack(side="right", padx=16)

        bar = tk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        tk.Label(bar, text="Student ID:").pack(side="left")
        self._student_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self._student_var, width=16)
        entry.pack(side="left", padx=4)
        entry.bind("<Return>", lambda _e: self.lookup())
        for label, cmd in (("Look Up", self.lookup), ("Correct Identity", self.correct),
                           ("Merge Students", self.merge), ("Reverse Merge", self.reverse),
                           ("Refresh", self.refresh)):
            ttk.Button(bar, text=label, command=cmd).pack(side="left", padx=4)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = ("merge_id", "survivor_id", "merged_id", "status", "requested_by", "approved_by", "created_at")
        self._tree = ttk.Treeview(panes, columns=cols, show="headings")
        for col, width in zip(cols, (260, 90, 90, 80, 100, 100, 140)):
            self._tree.heading(col, text=col.replace("_", " ").title())
            self._tree.column(col, width=width, stretch=col == "merge_id")
        self._tree.bind("<<TreeviewSelect>>", lambda _e: self.show_merge())
        panes.add(self._tree, weight=3)
        self._detail = tk.Text(panes, wrap="word", state="disabled", width=55)
        panes.add(self._detail, weight=2)

    def _selected_merge(self) -> str | None:
        sel = self._tree.focus()
        return self._tree.item(sel, "values")[0] if sel else None

    def _set_detail(self, text: str):
        self._detail.config(state="normal")
        self._detail.delete("1.0", "end")
        self._detail.insert("1.0", text)
        self._detail.config(state="disabled")

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        try:
            rows = identity_management.list_merges()
        except Exception as exc:
            logger.exception("Merge list failed")
            messagebox.showerror("Error", f"Could not load merges:\n{exc}", parent=self)
            return
        for row in rows:
            self._tree.insert("", "end", values=(
                row["merge_id"], row["survivor_id"], row["merged_id"], row["status"] or "",
                row["requested_by"] or "", row["approved_by"] or "", str(row["created_at"] or "")[:19]))

    def show_merge(self):
        merge_id = self._selected_merge()
        if not merge_id:
            return
        values = self._tree.item(self._tree.focus(), "values")
        lines = [f"merge_id: {values[0]}", f"survivor: {values[1]}", f"merged: {values[2]}",
                 f"status: {values[3]}", f"requested_by: {values[4]}", f"approved_by: {values[5]}",
                 f"created_at: {values[6]}"]
        self._set_detail("\n".join(lines))

    def lookup(self):
        student_id = self._student_var.get().strip()
        if not student_id:
            messagebox.showwarning("Look Up", "Enter a student ID.", parent=self)
            return
        try:
            record = identity_management.student_identity(student_id)
            changes = identity_management.list_identity_changes(student_id)
        except ValueError as exc:
            self._set_detail(str(exc))
            return
        lines = [f"{key}: {value}" for key, value in record.items()]
        lines.append(f"\nIdentity changes ({len(changes)}):")
        for change in changes:
            lines.append(f"  {str(change['created_at'] or '')[:19]}  {change['change_type']}  "
                         f"{change['before_json']} -> {change['after_json']}\n"
                         f"    reason: {change['reason']}  "
                         f"[{change['requested_by']} / {change['approved_by']}]")
        self._set_detail("\n".join(lines))

    def correct(self):
        student_id = self._student_var.get().strip()
        if not student_id:
            messagebox.showwarning("Correct Identity", "Enter a student ID first.", parent=self)
            return
        field = simpledialog.askstring(
            "Correct Identity", "Field:\n" + ", ".join(sorted(identity_management.IDENTITY_FIELDS)),
            parent=self)
        if not field:
            return
        value = simpledialog.askstring("Correct Identity", f"New value for {field}:", parent=self)
        reason = simpledialog.askstring("Correct Identity", "Reason:", parent=self)
        approver = simpledialog.askstring("Correct Identity", "Approved by (must differ from you):",
                                          parent=self)
        if value is None or reason is None or not approver:
            return
        try:
            change_id = identity_management.correct_identity(
                student_id, {field.strip(): value.strip()}, reason=reason.strip(),
                requested_by=self._actor, approved_by=approver.strip())
        except ValueError as exc:
            messagebox.showerror("Correct Identity", str(exc), parent=self)
            return
        messagebox.showinfo("Correct Identity", f"Correction {change_id} applied.", parent=self)
        self.lookup()

    def merge(self):
        survivor = simpledialog.askstring("Merge Students", "Survivor student ID:",
                                          initialvalue=self._student_var.get().strip(), parent=self)
        merged = simpledialog.askstring("Merge Students", "Merged (duplicate) student ID:", parent=self)
        reason = simpledialog.askstring("Merge Students", "Reason:", parent=self)
        approver = simpledialog.askstring("Merge Students", "Approved by (must differ from you):",
                                          parent=self)
        if not survivor or not merged or reason is None or not approver:
            return
        if not messagebox.askyesno("Merge Students", f"Mark {merged} as merged into {survivor}?",
                                   parent=self):
            return
        try:
            merge_id = identity_management.merge_students(
                survivor.strip(), merged.strip(), reason=reason.strip(),
                requested_by=self._actor, approved_by=approver.strip())
        except ValueError as exc:
            messagebox.showerror("Merge Students", str(exc), parent=self)
            return
        messagebox.showinfo("Merge Students", f"Merge {merge_id} recorded.", parent=self)
        self.refresh()

    def reverse(self):
        merge_id = self._selected_merge()
        if not merge_id:
            messagebox.showwarning("Reverse Merge", "Select a merge first.", parent=self)
            return
        reason = simpledialog.askstring("Reverse Merge", "Reason:", parent=self)
        if reason is None:
            return
        try:
            identity_management.reverse_merge(merge_id, reversed_by=self._actor, reason=reason.strip())
        except ValueError as exc:
            messagebox.showerror("Reverse Merge", str(exc), parent=self)
            return
        self.refresh()


def main() -> None:
    from education_system.platform.delivery.gui.window_sizing import install
    from education_system.systems.university.shell.gui.auth.launch_guard import require_launcher_auth

    user = require_launcher_auth("Student Identity Management")
    if user is None:
        return
    if str(user.get("role", "")).lower() not in ADMIN_ROLES:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Identity Management",
                             "Identity management is available to administrators only.")
        root.destroy()
        return
    install()
    root = tk.Tk()
    root.title(_t("gui.learners.identity_management.title", default="Student Identity Management"))
    root.geometry("1400x900")
    root.minsize(1200, 800)
    IdentityManagementApp(root, user=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
