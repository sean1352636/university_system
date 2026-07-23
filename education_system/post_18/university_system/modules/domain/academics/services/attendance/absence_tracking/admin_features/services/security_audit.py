"""SecurityAuditService — features #42–#46.

Sliced verbatim from the original admin_features.py during the package split.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

from ..context import AdminContext, audit, logger, safe
from ..export_email import (
    _email_admin,
    _export_rows_to_csv,
    _report_window,
    _rows_to_pdf,
    _rows_to_txt,
)
from ..support_tables import _get_setting, _set_setting
from ..ui_dialogs import (
    ModulePicker,
    Prompt,
    StudentPicker,
    _combo_dialog,
    _pick_module,
    _pick_student,
    _show_table,
    pick_date,
    pick_date_range,
)


class SecurityAuditService:
    """Permission matrix, audit trail, impersonation, retention, GDPR."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker
                 ) -> None:
        self.ctx = ctx
        self.student_picker = student_picker

    # --- #42 ----------------------------------------------------------
    @safe("Permission matrix")
    def show_permission_matrix(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT u.username, u.role, im.module_code
                   FROM users u
                   LEFT JOIN instructor_modules im
                       ON im.instructor_id = u.id
                   WHERE u.role IN ('admin','staff','instructor')
                   ORDER BY u.username""").fetchall()
        except sqlite3.Error:
            logger.exception("permission matrix failed")
            rows = []
        _show_table(self.ctx.parent, "Permission matrix",
                    ("user", "role", "module"), rows)

    # --- #43 ----------------------------------------------------------
    @safe("Full audit trail")
    def show_full_audit_trail(self) -> None:
        user = simpledialog.askstring(
            "Filter", "Filter by username (blank = all):",
            parent=self.ctx.parent) or ""
        q = ("SELECT ts, username, action, target, target_id, details "
             "FROM abs_tracker_audit")
        p: list = []
        if user:
            q += " WHERE username LIKE ?"
            p.append(f"%{user}%")
        q += " ORDER BY ts DESC LIMIT 1000"
        try:
            rows = self.ctx.db.cur.execute(q, p).fetchall()
        except sqlite3.Error:
            logger.exception("audit trail fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Full audit trail",
                    ("ts", "user", "action", "target", "id", "details"),
                    rows, widths=[150, 120, 140, 100, 100, 350])

    # --- #44 ----------------------------------------------------------
    @safe("Impersonate")
    def impersonate_user_readonly(self) -> None:
        username = Prompt.non_empty(
            self.ctx.parent, "Impersonate",
            "Username to view as:", min_len=1)
        if not username:
            return
        try:
            other = self.ctx.db.lookup_user_by_username(username)
        except Exception:
            logger.exception("user lookup failed username=%s", username)
            other = None
        if not other:
            messagebox.showerror("Not found",
                                 f"No user '{username}'",
                                 parent=self.ctx.parent)
            return
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking import (  # noqa: E501
                absence_tracker as at,
            )
            new_root = tk.Toplevel(self.ctx.parent)
            at.launch_dashboard(new_root, self.ctx.db, other)
        except Exception as e:
            logger.exception("impersonate launch failed")
            messagebox.showerror("Failed",
                                 f"Could not launch impersonated session:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "impersonate", "users", other["id"], username)

    # --- #45 ----------------------------------------------------------
    @safe("Retention purge")
    def purge_per_retention_policy(self) -> None:
        years = simpledialog.askinteger(
            "Retention", "Purge attendance older than (years)?",
            parent=self.ctx.parent, minvalue=1, maxvalue=30)
        if not years:
            return
        cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
        if not Prompt.confirm(
                self.ctx.parent, "Confirm purge",
                f"Permanently delete attendance rows before {cutoff}?\n"
                "This cannot be undone."):
            return
        try:
            cur = self.ctx.db.cur.execute(
                "DELETE FROM attendance WHERE date < ?", (cutoff,))
            removed = cur.rowcount
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_retention
                   (policy, years, applied_at) VALUES (?,?,?)""",
                (f"attendance<{cutoff}", years,
                 datetime.now().isoformat(timespec="seconds")))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("retention purge failed years=%s", years)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "retention_purge", "attendance", "",
              f"years={years} removed={removed}")
        messagebox.showinfo("Purged",
                            f"Removed {removed} row(s) before {cutoff}.",
                            parent=self.ctx.parent)

    # --- #46 ----------------------------------------------------------
    @safe("GDPR export")
    def gdpr_subject_export(self) -> None:
        sid = self.student_picker.pick("Export data for which student?")
        if not sid:
            return
        try:
            att = self.ctx.db.cur.execute(
                "SELECT * FROM attendance WHERE student_id=?",
                (sid,)).fetchall()
            req = self.ctx.db.cur.execute(
                "SELECT * FROM absence_requests WHERE student_id=?",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("GDPR fetch failed sid=%s", sid)
            messagebox.showerror("Error", "Could not load student data.",
                                 parent=self.ctx.parent)
            return
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".json",
            initialfile=f"gdpr_{sid}.json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "student_id": sid,
                    "attendance": [list(r) for r in att],
                    "absence_requests": [list(r) for r in req],
                }, fh, indent=2, default=str)
        except OSError as e:
            logger.exception("GDPR write failed path=%s", path)
            messagebox.showerror("Save failed", str(e),
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "gdpr_export", "students", sid, path)
        messagebox.showinfo("Exported", f"Data written:\n{path}",
                            parent=self.ctx.parent)


# ===========================================================================
# DiagnosticsService — features #47–#50
# ===========================================================================
