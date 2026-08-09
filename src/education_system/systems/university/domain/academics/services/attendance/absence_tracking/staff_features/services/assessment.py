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

from education_system.systems.university.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
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

class AssessmentIntegrationService:
    """Link assignments / exams / lab safety to attendance state."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #40 ----------------------------------------------------------
    @safe("Assignment link")
    def show_pre_deadline_absence_risk(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY,
                    module_code TEXT, title TEXT, due_date TEXT)""")
            # FIX: previous query used `HAVING 4 >= 2` — a literal-only
            # comparison that's always true. Now requires ≥2 absences in
            # the 14 days before the assignment due date.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id, ass.title, ass.due_date,
                          SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END)
                              AS absences
                   FROM attendance a
                   JOIN assignments ass ON ass.module_code = a.module_code
                     AND ass.due_date >= date('now')
                   WHERE a.module_code=?
                     AND a.date BETWEEN date(ass.due_date,'-14 days')
                                    AND ass.due_date
                   GROUP BY a.student_id, ass.id
                   HAVING absences >= 2
                   ORDER BY ass.due_date""", (mc,)).fetchall()
        except sqlite3.Error:
            logger.exception("assignment link query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, "Pre-deadline absence risk",
                    ("student", "assignment", "due", "absences in 14d"), rows)

    # --- #41 ----------------------------------------------------------
    @safe("Exam eligibility")
    def show_exam_ineligible_students(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            thr_row = self.ctx.db.cur.execute(
                """SELECT min_percent FROM abs_tracker_module_policy
                   WHERE module_code=?""", (mc,)).fetchone()
        except sqlite3.Error:
            logger.exception("policy fetch failed mc=%s", mc)
            thr_row = None
        thr = thr_row[0] if thr_row else float(
            _get_setting(self.ctx.db, "default_min_pct", 80) or 80)
        try:
            # FIX: `HAVING 2 < ?` was a literal compare. Now correctly
            # checks the aggregate attendance percentage.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100 AS pct
                   FROM attendance a WHERE a.module_code=?
                   GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (mc, thr)).fetchall()
        except sqlite3.Error:
            logger.exception("exam eligibility query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"Ineligible (<{thr:.0f}%) — {mc}",
                    ("student", "%"),
                    [(s, f"{p:.1f}") for s, p in rows])

    # --- #42 ----------------------------------------------------------
    @safe("Lab safety")
    def show_missing_safety_briefing(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT sm.student_id
                   FROM student_modules sm
                   WHERE sm.module_code=?
                     AND sm.student_id NOT IN (
                         SELECT DISTINCT student_id FROM attendance
                         WHERE module_code=?
                           AND COALESCE(reason,'') LIKE '%safety%'
                           AND status='present')""",
                (mc, mc)).fetchall()
        except sqlite3.Error:
            logger.exception("lab safety query failed mc=%s", mc)
            rows = []
        _show_table(self.ctx.parent, f"{mc} — missed safety briefing",
                    ("student",), rows, widths=[180])
