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

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
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

class PastoralService:
    """Pastoral flags, check-ins, safeguarding, meetings, intervention log."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    # --- #35 ----------------------------------------------------------
    @safe("Flag pastoral")
    def flag_pastoral_concern(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        note = Prompt.non_empty(self.ctx.parent, "Concern",
                                "Concern:", min_len=5)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS early_warning_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, author_id INTEGER, content TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO early_warning_notifications
                   (student_id, author_id, content) VALUES (?,?,?)""",
                (sid, self.ctx.uid, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("pastoral flag insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.ew_flag", "early_warning_notifications",
              sid, note[:80])
        messagebox.showinfo("Flagged", "Pastoral team notified.",
                            parent=self.ctx.parent)

    # --- #36 ----------------------------------------------------------
    @safe("Check-in log")
    def log_checkin_conversation(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        outcome = Prompt.non_empty(self.ctx.parent, "Notes",
                                   "Outcome / notes:", min_len=2)
        if not outcome:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_intervention_log
                   (staff_id, student_id, action, outcome)
                   VALUES (?,?,?,?)""",
                (self.ctx.uid, sid, "check-in", outcome))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("checkin insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.checkin", "abs_tracker_intervention_log",
              sid, outcome[:80])
        messagebox.showinfo("Logged", "Check-in saved.",
                            parent=self.ctx.parent)

    # --- #37 ----------------------------------------------------------
    @safe("Escalate safeguarding")
    def escalate_safeguarding_incident(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        desc = Prompt.non_empty(self.ctx.parent, "Details",
                                "Details:", min_len=10)
        if not desc:
            return
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              "Escalate to safeguarding? "
                              "This is a high-priority alert."):
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, category TEXT, details TEXT,
                    raised_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO incidents
                   (student_id, category, details, raised_by)
                   VALUES (?, 'safeguarding', ?, ?)""",
                (sid, desc, self.ctx.uid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("safeguarding escalation failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.safeguard", "incidents", sid, "(redacted)")
        messagebox.showinfo("Escalated",
                            "Safeguarding team has been notified.",
                            parent=self.ctx.parent)

    # --- #38 ----------------------------------------------------------
    @safe("Meeting scheduler")
    def schedule_student_meeting(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student",
                               "Student ID:", min_len=1)
        if not sid:
            return
        when = Prompt.iso_datetime(self.ctx.parent, "When",
                                   "Meeting time (YYYY-MM-DD HH:MM):")
        if not when:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS parent_conferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, staff_id INTEGER,
                    scheduled_for TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            self.ctx.db.cur.execute(
                """INSERT INTO parent_conferences
                   (student_id, staff_id, scheduled_for) VALUES (?,?,?)""",
                (sid, self.ctx.uid, when))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("meeting schedule failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.meeting", "parent_conferences", sid, when)
        messagebox.showinfo("Scheduled", f"Meeting {when} with {sid}.",
                            parent=self.ctx.parent)

    # --- #39 ----------------------------------------------------------
    @safe("Intervention tracker")
    def show_intervention_history(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_at, student_id, action, outcome
                   FROM abs_tracker_intervention_log
                   WHERE staff_id=? ORDER BY created_at DESC""",
                (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("intervention list fetch failed")
            rows = []
        _show_table(self.ctx.parent, f"My interventions ({len(rows)})",
                    ("when", "student", "action", "outcome"), rows,
                    widths=[160, 120, 140, 420])
