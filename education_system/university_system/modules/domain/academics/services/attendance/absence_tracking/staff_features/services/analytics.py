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

class AnalyticsService:
    """Heatmap, drop-off detection, comparisons, profiles, correlations."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #22 ----------------------------------------------------------
    @safe("Heatmap")
    def show_my_heatmap(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT strftime('%Y-%W', date) AS week,
                           CASE strftime('%w', date)
                                WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
                                WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu'
                                WHEN '5' THEN 'Fri' END AS dow,
                           SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END)
                                AS absences
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY week, dow
                    HAVING dow IS NOT NULL
                    ORDER BY week DESC""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            rows = []
        _show_table(self.ctx.parent, "My modules — heatmap",
                    ("week", "day", "absences"), rows)

    # --- #23 ----------------------------------------------------------
    @safe("Drop-off")
    def show_dropoff_students(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        cutoff = (date.today() - timedelta(days=28)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT student_id, recent, prior
                    FROM (
                        SELECT student_id,
                               SUM(CASE WHEN status='present' AND date >= ?
                                        THEN 1 ELSE 0 END)*1.0 /
                                  NULLIF(SUM(CASE WHEN date >= ?
                                                  THEN 1 ELSE 0 END),0) * 100
                                  AS recent,
                               SUM(CASE WHEN status='present' AND date <  ?
                                        THEN 1 ELSE 0 END)*1.0 /
                                  NULLIF(SUM(CASE WHEN date <  ?
                                                  THEN 1 ELSE 0 END),0) * 100
                                  AS prior
                        FROM attendance
                        WHERE module_code IN ({ph})
                        GROUP BY student_id
                    )
                    WHERE recent IS NOT NULL AND prior IS NOT NULL
                      AND (prior - recent) > 20
                    ORDER BY (prior - recent) DESC""",
                (cutoff, cutoff, cutoff, cutoff, *mine)).fetchall()
        except sqlite3.Error:
            logger.exception("dropoff query failed")
            rows = []
        _show_table(self.ctx.parent, "Drop-off (>20%)",
                    ("student", "recent %", "prior %"),
                    [(s, f"{r:.1f}", f"{p:.1f}") for s, r, p in rows])

    # --- #24 ----------------------------------------------------------
    @safe("Compare my modules")
    def compare_my_modules(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            rows = self.ctx.db.cur.execute(
                f"""SELECT module_code,
                           SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100,
                           COUNT(*)
                    FROM attendance WHERE module_code IN ({ph})
                    GROUP BY module_code ORDER BY 2 DESC""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("module comparison failed")
            rows = []
        _show_table(self.ctx.parent, "My modules compared",
                    ("module", "%", "sessions"),
                    [(m, f"{(p or 0):.1f}", n) for m, p, n in rows])

    # --- #25 ----------------------------------------------------------
    @safe("Historical cohort")
    def compare_terms_for_module(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            sems = self.ctx.db.cur.execute(
                """SELECT name, start_date, end_date FROM semesters
                   ORDER BY start_date DESC LIMIT 2""").fetchall()
        except sqlite3.Error:
            logger.exception("semesters fetch failed")
            sems = []
        out = []
        for name, s, e in sems:
            try:
                r = self.ctx.db.cur.execute(
                    """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100
                       FROM attendance
                       WHERE module_code=? AND date BETWEEN ? AND ?""",
                    (mc, s, e)).fetchone()
            except sqlite3.Error:
                logger.exception("cohort query failed")
                r = (0,)
            out.append((name, s, e, f"{(r[0] or 0):.1f}"))
        _show_table(self.ctx.parent, f"{mc} — term compare",
                    ("semester", "start", "end", "%"), out)

    # --- #26 ----------------------------------------------------------
    @safe("Module report")
    def export_module_report(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        try:
            rows = self.ctx.db.get_absences(course_id=mc)
        except Exception:
            logger.exception("absences fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Empty", "No data for this module.",
                                parent=self.ctx.parent)
            return
        path = _export_rows_to_csv(
            rows, ("id", "student", "module_code", "module_name",
                   "date", "status", "reason"), self.ctx.parent)
        if path:
            audit(self.ctx, "staff.module_report", "attendance", mc, path)
            messagebox.showinfo("Saved",
                                f"Exported {len(rows)} rows → {path}",
                                parent=self.ctx.parent)

    # --- #27 ----------------------------------------------------------
    @safe("Student profile")
    def show_student_profile(self) -> None:
        sid = Prompt.non_empty(self.ctx.parent, "Student ID",
                               "Student ID:", min_len=1)
        if not sid:
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title(f"Profile — {sid}")
        win.geometry("920x620")
        nb = ttk.Notebook(win); nb.pack(fill="both", expand=True)
        try:
            sections = [
                ("Attendance",
                 self.ctx.db.cur.execute(
                    """SELECT date, module_code, status, COALESCE(reason,'')
                       FROM attendance WHERE student_id=?
                       ORDER BY date DESC""", (sid,)).fetchall(),
                 ("date", "module", "status", "reason")),
                ("Requests",
                 self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at
                       FROM absence_requests WHERE student_id=?
                       ORDER BY submitted_at DESC""", (sid,)).fetchall(),
                 ("id", "date", "module", "status", "submitted")),
                ("Risk",
                 self.ctx.db.cur.execute(
                    """SELECT assessment_date, risk_level, risk_score
                       FROM student_risk_assessment WHERE student_id=?
                       ORDER BY assessment_date DESC""", (sid,)).fetchall(),
                 ("date", "level", "score")),
            ]
        except sqlite3.Error:
            logger.exception("student profile fetch failed sid=%s", sid)
            messagebox.showerror("Error", "Could not load profile.",
                                 parent=win)
            return
        for label, rows, cols in sections:
            tab = ttk.Frame(nb); nb.add(tab, text=f"{label} ({len(rows)})")
            tree = ttk.Treeview(tab, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c)
                tree.column(c, width=180)
            tree.pack(fill="both", expand=True)
            for r in rows:
                tree.insert("", "end", values=r)
        audit(self.ctx, "staff.student_profile", "students", sid, "view")

    # --- #28 ----------------------------------------------------------
    @safe("Correlation")
    def show_attendance_vs_grade(self) -> None:
        mine = self.picker.my_module_codes()
        if not mine:
            messagebox.showinfo("No modules", "No modules.",
                                parent=self.ctx.parent)
            return
        ph = ",".join("?" * len(mine))
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_grades (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, module_code TEXT, grade TEXT)""")
            rows = self.ctx.db.cur.execute(
                f"""SELECT a.student_id, a.module_code,
                           SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              *1.0/NULLIF(COUNT(*),0)*100,
                           COALESCE((SELECT grade FROM student_grades g
                                     WHERE g.student_id=a.student_id
                                       AND g.module_code=a.module_code
                                     ORDER BY id DESC LIMIT 1),'')
                    FROM attendance a WHERE a.module_code IN ({ph})
                    GROUP BY a.student_id, a.module_code""", mine).fetchall()
        except sqlite3.Error:
            logger.exception("correlation query failed")
            rows = []
        _show_table(self.ctx.parent, "Attendance vs grade",
                    ("student", "module", "%", "grade"),
                    [(s, m, f"{(p or 0):.1f}", g) for s, m, p, g in rows])
