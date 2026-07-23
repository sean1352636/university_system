"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StaffContext, ensure_staff_tables
from ..prefs import StaffPrefs
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.staff_picker import StaffPicker

class CommunicationService:
    """Email, announcements, catch-ups, parent outreach, office hours."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #29 ----------------------------------------------------------
    @safe("Email student")
    def email_single_student(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student ID",
                               "Student ID:", min_len=1)
        if not sid:
            return
        subject = Prompt.non_empty(self.ctx.parent, "Subject",
                                   "Subject:", min_len=2)
        if not subject:
            return
        body = Prompt.non_empty(self.ctx.parent, "Body",
                                "Body:", min_len=2)
        if not body:
            return
        try:
            cur = self.ctx.db.cur.execute(
                """INSERT INTO emails (recipient, subject, body, sent_at, status)
                   SELECT email_address, ?, ?, CURRENT_TIMESTAMP, 'queued'
                   FROM students WHERE student_id=?""",
                (subject, body, sid))
            inserted = cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("email insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        if inserted == 0:
            messagebox.showwarning("Not found",
                                   f"No student record for '{sid}'.",
                                   parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.email", "emails", sid, subject[:80])
        messagebox.showinfo("Queued", "Email queued.",
                            parent=self.ctx.parent)

    # --- #30 ----------------------------------------------------------
    @safe("Email at-risk list")
    def email_at_risk_summary(self) -> None:
        to = simpledialog.askstring("Recipient", "Pastoral email:",
                                    parent=self.ctx.parent
                                    ) or "pastoral@university.edu"
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=75) or 75
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            # FIX: original used `HAVING 2 < ?` which is a literal-vs-literal
            # compare (always true if threshold>2). Aliased the aggregate so
            # the threshold actually filters by attendance percentage.
            rows = self.ctx.db.cur.execute(
                f"""SELECT student_id,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY student_id
                    HAVING pct IS NOT NULL AND pct < ?""",
                (*mine, threshold)).fetchall()
        except sqlite3.Error:
            logger.exception("at-risk query failed")
            messagebox.showerror("Error", "Could not compute at-risk list.",
                                 parent=self.ctx.parent)
            return
        body = f"At-risk students (<{threshold:.0f}%):\n" + "\n".join(
            f"  {sid}: {p:.1f}%" for sid, p in rows)
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO emails (recipient, subject, body, sent_at, status)
                   VALUES (?, 'At-risk attendance', ?,
                           CURRENT_TIMESTAMP, 'queued')""", (to, body))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("at-risk email insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.email_at_risk", "emails", to, f"n={len(rows)}")
        messagebox.showinfo("Queued",
                            f"Emailed summary of {len(rows)} student(s) to {to}.",
                            parent=self.ctx.parent)

    # --- #31 ----------------------------------------------------------
    @safe("Announcement")
    def post_module_announcement(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        msg = Prompt.non_empty(self.ctx.parent, "Announcement",
                               "Message:", min_len=2)
        if not msg:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT, content TEXT,
                    author_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO announcements (module_code, content, author_id)
                   VALUES (?,?,?)""", (mc, msg, self.ctx.uid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("announcement insert failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.announce", "announcements", mc, msg[:80])
        messagebox.showinfo("Posted", "Announcement posted.",
                            parent=self.ctx.parent)

    # --- #32 ----------------------------------------------------------
    @safe("Catch-up message")
    def send_catchup_to_absentees(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent, "Date", "Session date:")
        if not d:
            return
        msg = Prompt.non_empty(self.ctx.parent, "Message",
                               "Catch-up message:", min_len=5)
        if not msg:
            return
        try:
            absent = self.ctx.db.cur.execute(
                """SELECT a.student_id, s.email_address FROM attendance a
                   JOIN students s ON s.student_id = a.student_id
                   WHERE a.module_code=? AND a.date=?
                     AND a.status IN ('absent','late')""",
                (mc, d)).fetchall()
            for sid, email in absent:
                self.ctx.db.cur.execute(
                    """INSERT INTO emails
                       (recipient, subject, body, sent_at, status)
                       VALUES (?, 'Catch up', ?,
                               CURRENT_TIMESTAMP, 'queued')""",
                    (email or sid, msg))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("catchup batch failed mc=%s d=%s", mc, d)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.catchup", "emails", mc,
              f"{d} n={len(absent)}")
        messagebox.showinfo("Sent", f"Queued {len(absent)} email(s).",
                            parent=self.ctx.parent)

    # --- #33 ----------------------------------------------------------
    @safe("Parent outreach")
    def notify_parents_of_low_attendance(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=70) or 70
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            # FIX: replaced bogus `HAVING 2 < ?` with a real predicate over
            # the aggregated percentage column.
            low = self.ctx.db.cur.execute(
                f"""SELECT student_id,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY student_id
                    HAVING pct IS NOT NULL AND pct < ?""",
                (*mine, threshold)).fetchall()
        except sqlite3.Error:
            logger.exception("parent outreach lookup failed")
            messagebox.showerror("Error",
                                 "Could not compute below-threshold list.",
                                 parent=self.ctx.parent)
            return
        n = 0
        try:
            for sid, pct in low:
                parents = self.ctx.db.cur.execute(
                    """SELECT parent_id FROM parent_student_links
                       WHERE student_id=?""", (sid,)).fetchall()
                for (pid,) in parents:
                    self.ctx.db.cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?,?,?,?,?,0)""",
                        (str(pid), sid, "attendance_alert",
                         f"{sid} attendance {pct:.1f}% "
                         f"(below {threshold:.0f}%)",
                         datetime.now().isoformat(timespec="seconds")))
                    n += 1
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("parent notification insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.parent_outreach", "parent_notifications", "",
              f"n={n} threshold={threshold}")
        messagebox.showinfo("Sent", f"Notified {n} parent(s).",
                            parent=self.ctx.parent)

    # --- #34 ----------------------------------------------------------
    @safe("Office hours")
    def publish_office_hours(self) -> None:
        slot = Prompt.non_empty(
            self.ctx.parent, "Slot",
            "Slot (e.g. 'Wed 14:00-15:00'):", min_len=3)
        if not slot:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS office_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id INTEGER, slot TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                "INSERT INTO office_hours (staff_id, slot) VALUES (?,?)",
                (self.ctx.uid, slot))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("office hours insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.office_hours", "office_hours",
              self.ctx.uid, slot)
        messagebox.showinfo("Published", f"Office hours: {slot}",
                            parent=self.ctx.parent)
