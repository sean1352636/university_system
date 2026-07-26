"""NotificationService — features #27–#30.

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
from .reporting import _parents_of


class NotificationService:
    """Threshold alerts, parent notifications, bulk announcements, SMS."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #27 ----------------------------------------------------------
    @safe("Threshold alerts")
    def create_threshold_alerts(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Alert below %:",
            parent=self.ctx.parent, initialvalue=75) or 75
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                   FROM attendance a GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("threshold scan failed")
            messagebox.showerror("Error", "Could not scan attendance.",
                                 parent=self.ctx.parent)
            return
        created = 0
        try:
            for sid, pct in rows:
                # FIX: original used parent_id='' which orphaned every alert.
                # Insert one row per real linked parent; if none exist, leave
                # the alert with parent_id='' so an admin can still see it.
                parents = _parents_of(self.ctx.db, sid) or [""]
                for pid in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'attendance_alert', ?, ?, 0)""",
                        (pid, sid,
                         f"Attendance at {pct:.1f}% (below {threshold:.0f}%)",
                         datetime.now().isoformat(timespec="seconds")))
                    created += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("threshold alert insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "threshold_alerts", "parent_notifications", "",
              f"threshold={threshold} created={created}")
        messagebox.showinfo("Alerts",
                            f"Created {created} alert row(s).",
                            parent=self.ctx.parent)

    # --- #28 ----------------------------------------------------------
    @safe("Parent notifications")
    def notify_parents_for_student(self) -> None:
        sid = self.student_picker.pick("Notify parents of which student?")
        if not sid:
            return
        parents = _parents_of(self.ctx.db, sid)
        if not parents:
            messagebox.showinfo(
                "No parents",
                "No parents linked to this student.",
                parent=self.ctx.parent)
            return
        try:
            recent = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id=? ORDER BY date DESC LIMIT 10""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recent attendance fetch failed sid=%s", sid)
            recent = []
        content = "Recent attendance: " + "; ".join(
            f"{d}={s}" for d, s in recent)
        try:
            for pid in parents:
                self.ctx.db.cur.execute(
                    """INSERT INTO parent_notifications
                       (parent_id, student_id, notification_type,
                        notification_content, created_date, read_status)
                       VALUES (?, ?, 'attendance_update', ?, ?, 0)""",
                    (pid, sid, content,
                     datetime.now().isoformat(timespec="seconds")))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("parent notify failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "parent_notify", "parent_notifications", sid,
              f"parents={len(parents)}")
        messagebox.showinfo("Sent", f"Notified {len(parents)} parent(s).",
                            parent=self.ctx.parent)

    # --- #29 ----------------------------------------------------------
    @safe("Bulk announcement")
    def post_bulk_announcement(self) -> None:
        mc = self.module_picker.pick("Announce to which module?")
        if not mc:
            return
        msg = Prompt.non_empty(self.ctx.parent, "Message",
                               "Announcement text:", min_len=2)
        if not msg:
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
        n_rows = 0
        try:
            for sid, *_ in roster:
                # FIX: original wrote parent_id='' so nothing was actually
                # routed. Resolve parents per student; fall back to '' so the
                # row still exists for the admin view.
                parents = _parents_of(self.ctx.db, sid) or [""]
                for pid in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'announcement', ?, ?, 0)""",
                        (pid, sid, msg,
                         datetime.now().isoformat(timespec="seconds")))
                    n_rows += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("bulk announcement failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_announcement",
              "parent_notifications", mc,
              f"students={len(roster)} rows={n_rows} msg={msg[:80]}")
        messagebox.showinfo("Sent",
                            f"Announcement posted for {len(roster)} "
                            f"student(s) ({n_rows} notification rows).",
                            parent=self.ctx.parent)

    # --- #30 ----------------------------------------------------------
    @safe("SMS fallback")
    def queue_sms_fallback(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=70) or 70
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS abs_tracker_sms_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT, body TEXT,
                    queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'queued')""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                   FROM attendance a GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
            queued = 0
            for sid, pct in rows:
                self.ctx.db.cur.execute(
                    "INSERT INTO abs_tracker_sms_queue (recipient, body) VALUES (?,?)",
                    (sid, f"ALERT: attendance {pct:.1f}% "
                          f"below {threshold:.0f}%"))
                queued += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("SMS queue failed threshold=%s", threshold)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "sms_queue", "abs_tracker_sms_queue", "", f"n={queued}")
        messagebox.showinfo("Queued",
                            f"{queued} SMS message(s) queued.",
                            parent=self.ctx.parent)


# ===========================================================================
# IntegrationService — features #31–#37
# ===========================================================================
