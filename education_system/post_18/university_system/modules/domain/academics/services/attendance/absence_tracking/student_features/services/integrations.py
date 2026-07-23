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

class IntegrationsService:
    """Timetable, grade impact, assignments, library search, exam-day check."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    # --- #43 -----------------------------------------------------------
    @safe("My timetable")
    def show_my_timetable(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.module_code, ms.day_of_week, ms.start_time,
                          ms.end_time, ms.room_id, ms.semester
                   FROM module_schedule ms
                   JOIN student_modules sm ON sm.module_code = ms.module_code
                   WHERE sm.student_id=?
                   ORDER BY ms.day_of_week, ms.start_time""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("timetable fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My timetable",
                    ("module", "day", "start", "end", "room", "semester"), rows)

    # --- #44 -----------------------------------------------------------
    @safe("Grade impact")
    def show_grade_vs_attendance(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_grades (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, module_code TEXT, grade TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE((SELECT grade FROM student_grades
                                    WHERE student_id=? AND module_code=m.module_code
                                    ORDER BY id DESC LIMIT 1), '—') AS grade,
                          COALESCE((SELECT
                             SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100
                             FROM attendance
                             WHERE student_id=? AND module_code=m.module_code), 0)
                          AS pct
                   FROM student_modules sm
                   JOIN modules m ON m.module_code=sm.module_code
                   WHERE sm.student_id=?""",
                (sid, sid, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("grade impact fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Grades vs attendance",
                    ("module", "grade", "attendance %"),
                    [(mc, g, f"{p:.1f}") for mc, g, p in rows])

    # --- #45 -----------------------------------------------------------
    @safe("My assignments")
    def show_my_assignments(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY, module_code TEXT, title TEXT,
                    due_date TEXT, status TEXT)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code, a.title, a.due_date,
                          COALESCE(a.status,'')
                   FROM assignments a
                   JOIN student_modules sm ON sm.module_code = a.module_code
                   WHERE sm.student_id=?
                   ORDER BY a.due_date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("assignments fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My assignments",
                    ("module", "title", "due", "status"), rows,
                    widths=[110, 380, 110, 120])

    # --- #46 -----------------------------------------------------------
    @safe("Library resources")
    def search_library(self) -> None:
        q = Prompt.non_empty(self.ctx.parent, "Library search",
                             "Search term:", min_len=2)
        if not q:
            return
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY,
                    title TEXT, author TEXT, shelf TEXT)""")
            like = f"%{q}%"
            rows = self.ctx.db.cur.execute(
                """SELECT title, COALESCE(author,''), COALESCE(shelf,'')
                   FROM books WHERE title LIKE ? OR author LIKE ? LIMIT 50""",
                (like, like)).fetchall()
        except sqlite3.Error:
            logger.exception("library search failed")
            rows = []
        _show_table(self.ctx.parent, f"Library — '{q}'",
                    ("title", "author", "shelf"), rows)

    # --- #47 -----------------------------------------------------------
    @safe("Exam-day check")
    def show_exam_day_check(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT m.module_code, e.date, e.name
                   FROM academic_calendar_events e
                   JOIN student_modules sm ON 1=1
                   JOIN modules m ON m.module_code = sm.module_code
                   WHERE sm.student_id=? AND e.event_type LIKE '%exam%'
                     AND e.date >= date('now')
                   ORDER BY e.date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("exam check fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Upcoming exam dates (must attend)",
                    ("module", "date", "event"), rows, widths=[120, 110, 500])


# ===========================================================================
# CustomisationService — features #48–#50
# ===========================================================================

