"""BulkOperationsService — features #38–#41.

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


class BulkOperationsService:
    """Whole-class roll, copy previous day, recurring absence, reassign."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #38 ----------------------------------------------------------
    @safe("Bulk present")
    def mark_module_all_present(self) -> None:
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        if not roster:
            messagebox.showinfo("Empty", "No students enrolled.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Mark {len(roster)} student(s) present on {d}?"):
            return
        try:
            for sid, *_ in roster:
                self.ctx.db.record_absence(sid, mc, d, "present",
                                           "bulk-present")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk present failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_present", "attendance", mc,
              f"date={d} n={len(roster)}")
        messagebox.showinfo("Saved",
                            f"Marked {len(roster)} present on {d}.",
                            parent=self.ctx.parent)

    # --- #39 ----------------------------------------------------------
    @safe("Copy previous day")
    def copy_previous_day_roll(self) -> None:
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent, "Copy to date",
                            "Target date (YYYY-MM-DD):")
        if not d:
            return
        try:
            last = self.ctx.db.cur.execute(
                """SELECT MAX(date) FROM attendance
                   WHERE module_code=? AND date<?""",
                (mc, d)).fetchone()[0]
        except sqlite3.Error:
            logger.exception("previous-day lookup failed mc=%s", mc)
            messagebox.showerror("Error", "Could not look up previous roll.",
                                 parent=self.ctx.parent)
            return
        if not last:
            messagebox.showinfo("Nothing to copy",
                                "No prior attendance rows.",
                                parent=self.ctx.parent)
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT student_id, status, reason FROM attendance
                   WHERE module_code=? AND date=?""",
                (mc, last)).fetchall()
            for sid, status, reason in rows:
                self.ctx.db.record_absence(sid, mc, d, status, reason or "")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("copy previous day failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "copy_prev_day", "attendance", mc,
              f"from={last} to={d} n={len(rows)}")
        messagebox.showinfo("Copied",
                            f"Copied {len(rows)} row(s) {last} → {d}.",
                            parent=self.ctx.parent)

    # --- #40 ----------------------------------------------------------
    @safe("Recurring absence")
    def create_recurring_absence(self) -> None:
        sid = self.student_picker.pick("Student:")
        if not sid:
            return
        mc = self.module_picker.pick("Module:")
        if not mc:
            return
        start = Prompt.iso_date(self.ctx.parent, "First date",
                                "First date (YYYY-MM-DD):")
        if not start:
            return
        weeks = simpledialog.askinteger(
            "Weeks", "How many weeks?",
            parent=self.ctx.parent, minvalue=1, maxvalue=52)
        if not weeks:
            return
        status = _combo_dialog(
            self.ctx.parent, "Status", "Status:",
            ["absent", "excused", "late", "present"]) or "absent"
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
        try:
            for w in range(weeks):
                d = (d0 + timedelta(days=7 * w)).isoformat()
                self.ctx.db.record_absence(sid, mc, d, status, "recurring")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("recurring absence failed sid=%s mc=%s",
                             sid, mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "recurring_absence", "attendance", sid,
              f"{mc} {start} x{weeks} {status}")
        messagebox.showinfo("Saved",
                            f"Created {weeks} rows for {sid}.",
                            parent=self.ctx.parent)

    # --- #41 ----------------------------------------------------------
    @safe("Reassign records")
    def reassign_records_on_transfer(self) -> None:
        sid = self.student_picker.pick("Student:")
        if not sid:
            return
        src = self.module_picker.pick("Source module:")
        if not src:
            return
        dst = self.module_picker.pick("Destination module:")
        if not dst:
            return
        if src == dst:
            messagebox.showerror("Same module",
                                 "Source and destination are identical.",
                                 parent=self.ctx.parent)
            return
        try:
            cur = self.ctx.db.cur.execute(
                """UPDATE attendance SET module_code=?
                   WHERE student_id=? AND module_code=?""",
                (dst, sid, src))
            n = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("reassign failed sid=%s %s→%s", sid, src, dst)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "reassign", "attendance", sid,
              f"{src}→{dst} n={n}")
        messagebox.showinfo("Reassigned",
                            f"Moved {n} row(s) {src} → {dst}.",
                            parent=self.ctx.parent)


# ===========================================================================
# SecurityAuditService — features #42–#46
# ===========================================================================
