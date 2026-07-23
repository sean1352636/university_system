"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
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
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StudentContext, ensure_student_tables
from ..prefs import StudentPrefs
from ..gauge import GaugeThresholds, _load_gauge_thresholds
from ..timeline_filter import _TimelineFilter
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.calendar_window import _CalendarWindow
from ..widgets.wheel_bind import _bind_wheel, _unbind_wheel

class SupportService:
    """Notes, office hours, study buddies, recordings, wellbeing, advising."""

    def __init__(self, ctx: StudentContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #29 -----------------------------------------------------------
    @safe("Request notes")
    def request_classmate_notes(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, _ = picked
        d = Prompt.iso_date(self.ctx.parent, "Date", "Session date (YYYY-MM-DD):")
        if not d:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_note_requests
                   (requester_id, module_code, date) VALUES (?,?,?)""",
                (sid, mcode, d))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.note_request", "abs_tracker_note_requests",
              sid, f"{mcode} {d}")
        messagebox.showinfo("Requested",
                            "Classmates will see your request on the peer board.",
                            parent=self.ctx.parent)

    # --- #30 -----------------------------------------------------------
    @safe("Book office hours")
    def book_office_hours(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS office_hour_bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, module_code TEXT,
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending')""")
            self.ctx.db.cur.execute(
                "INSERT INTO office_hour_bookings (student_id, module_code) VALUES (?,?)",
                (sid, mcode))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.office_hours", "office_hour_bookings",
              sid, mcode)
        messagebox.showinfo("Requested",
                            f"Office-hours request logged for {mlabel}.",
                            parent=self.ctx.parent)

    # --- #31 -----------------------------------------------------------
    @safe("Study buddy")
    def join_study_buddy_pool(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        try:
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO abs_tracker_study_buddies
                   (student_id, module_code) VALUES (?,?)""", (sid, mcode))
            self.ctx.db.conn.commit()
            others = self.ctx.db.cur.execute(
                """SELECT b.student_id,
                          TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,''))
                   FROM abs_tracker_study_buddies b
                   LEFT JOIN students s ON s.student_id = b.student_id
                   WHERE b.module_code=? AND b.student_id<>?""",
                (mcode, sid)).fetchall()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.study_buddy", "abs_tracker_study_buddies",
              sid, mcode)
        _show_table(self.ctx.parent, f"Study buddies for {mlabel}",
                    ("student_id", "name"), others, widths=[140, 320])

    # --- #32 -----------------------------------------------------------
    @safe("Recorded lectures")
    def show_recorded_lectures(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS virtual_recordings (
                    id INTEGER PRIMARY KEY,
                    module_code TEXT, date TEXT, url TEXT, title TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.date, a.module_code,
                          COALESCE(vr.title,''), COALESCE(vr.url,'')
                   FROM attendance a
                   LEFT JOIN virtual_recordings vr
                          ON vr.module_code = a.module_code AND vr.date = a.date
                   WHERE a.student_id=? AND a.status IN ('absent','excused')
                   ORDER BY a.date DESC LIMIT 30""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recordings fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Recordings for my missed sessions",
                    ("date", "module", "title", "url"), rows,
                    widths=[100, 110, 300, 340])

    # --- #33 -----------------------------------------------------------
    @safe("Wellbeing flag")
    def submit_wellbeing_flag(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        note = Prompt.non_empty(
            self.ctx.parent, "Confidential note",
            "Brief note (visible to wellbeing staff only):", min_len=3)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_wellbeing_flags
                   (student_id, attendance_id, note) VALUES (?, NULL, ?)""",
                (sid, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.wellbeing_flag",
              "abs_tracker_wellbeing_flags", sid, "(redacted)")
        messagebox.showinfo("Flagged",
                            "Thanks — wellbeing staff will review your flag.",
                            parent=self.ctx.parent)

    # --- #34 -----------------------------------------------------------
    @safe("Support resources")
    def show_support_resources(self) -> None:
        resources = [
            ("Counselling & Wellbeing", "Book: /student-support/counselling"),
            ("Disability Services",      "Contact: disability@university.edu"),
            ("Academic Advising",        "Portal: /advising"),
            ("Tutoring",                 "Find a tutor: /tutoring"),
            ("Financial Hardship",       "Apply: /financial-aid/hardship"),
            ("Chaplaincy",               "Quiet space: Campus centre rm 12"),
        ]
        _show_table(self.ctx.parent, "Support resources",
                    ("service", "how"), resources, widths=[240, 520])

    # --- #35 -----------------------------------------------------------
    @safe("Self-refer to advising")
    def self_refer_to_advising(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        topic = Prompt.non_empty(self.ctx.parent, "Topic",
                                 "What's it about?", min_len=3)
        if not topic:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS advising_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT, topic TEXT,
                    requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending')""")
            self.ctx.db.cur.execute(
                "INSERT INTO advising_appointments (student_id, topic) VALUES (?,?)",
                (sid, topic))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.advising", "advising_appointments",
              sid, topic[:120])
        messagebox.showinfo("Submitted", "Advising request submitted.",
                            parent=self.ctx.parent)


# ===========================================================================
# SocialService — features #36–#39
# ===========================================================================

