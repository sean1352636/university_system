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

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
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

class PlanningService:
    """Goals, budgets, term forecast, ICS export, recovery, wellbeing check-in."""

    def __init__(self, ctx: StudentContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #23 -----------------------------------------------------------
    @safe("Attendance goals")
    def set_per_module_goal(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        pct = simpledialog.askfloat("Target", "Target %:",
                                    parent=self.ctx.parent,
                                    minvalue=0, maxvalue=100, initialvalue=90)
        if pct is None:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_student_goals
                   (student_id, module_code, target_pct) VALUES (?,?,?)""",
                (sid, mcode, pct))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.goal", "abs_tracker_student_goals", sid,
              f"{mcode} {pct}")
        messagebox.showinfo("Saved", f"Goal saved: {mlabel} = {pct}%",
                            parent=self.ctx.parent)

    # --- #24 -----------------------------------------------------------
    @safe("Attendance budget")
    def show_attendance_budget(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        def_pct = float(_get_setting(self.ctx.db, "default_min_pct", 80) or 80)
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS p,
                          COUNT(*) AS n,
                          COALESCE(p.min_percent, ?) AS thr
                   FROM attendance a
                   LEFT JOIN abs_tracker_module_policy p
                          ON p.module_code = a.module_code
                   WHERE a.student_id=?
                   GROUP BY a.module_code""", (def_pct, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("budget fetch failed")
            rows = []
        out = []
        for mc, p, n, thr in rows:
            if not n:
                continue
            k = 0
            while (p / (n + k + 1)) * 100 >= thr and k < 500:
                k += 1
            out.append((mc, f"{p / n * 100:.1f}%", f"{thr:.0f}%", k))
        _show_table(self.ctx.parent, "Attendance budget",
                    ("module", "current", "threshold", "can miss"), out)

    # --- #25 -----------------------------------------------------------
    @safe("Term forecast")
    def show_term_forecast(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT module_code,
                          SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                            *1.0/NULLIF(COUNT(*),0)*100,
                          COUNT(*)
                   FROM attendance WHERE student_id=?
                   GROUP BY module_code""", (sid,)).fetchall()
            sem = self.ctx.db.cur.execute(
                "SELECT start_date, end_date FROM semesters "
                "ORDER BY start_date DESC LIMIT 1").fetchone()
        except sqlite3.Error:
            logger.exception("term forecast fetch failed")
            rows, sem = [], None
        est_weeks = 12
        if sem and sem[0] and sem[1]:
            try:
                est_weeks = max(1, (datetime.fromisoformat(sem[1])
                                    - datetime.fromisoformat(sem[0])).days // 7)
            except ValueError:
                logger.debug("semester dates unparseable", exc_info=True)
        out = [(mc, f"{(pct or 0):.1f}%", n, est_weeks, f"{(pct or 0):.1f}%")
               for mc, pct, n in rows]
        _show_table(self.ctx.parent, "Term forecast (current rate)",
                    ("module", "now", "sessions", "est weeks", "projected"), out)

    # --- #26 -----------------------------------------------------------
    @safe("Calendar sync")
    def export_calendar_ics(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, module_code, status FROM attendance
                   WHERE student_id=? ORDER BY date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("ics fetch failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Nothing", "No attendance rows to export.",
                                parent=self.ctx.parent)
            return
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".ics",
            initialfile=f"attendance_{sid}.ics")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                         "PRODID:-//AbsenceTracker//EN\r\n")
                for d, mc, st in rows:
                    try:
                        dt = datetime.strptime(d, "%Y-%m-%d").strftime("%Y%m%d")
                    except ValueError:
                        continue
                    fh.write(f"BEGIN:VEVENT\r\nUID:{sid}-{mc}-{d}@abs\r\n"
                             f"DTSTART;VALUE=DATE:{dt}\r\nDTEND;VALUE=DATE:{dt}\r\n"
                             f"SUMMARY:{mc} — {st}\r\nEND:VEVENT\r\n")
                fh.write("END:VCALENDAR\r\n")
        except OSError as e:
            messagebox.showerror("Write failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.ics", "attendance", sid, path)
        messagebox.showinfo("Exported", f"ICS written:\n{path}",
                            parent=self.ctx.parent)

    # --- #27 -----------------------------------------------------------
    @safe("Recovery plan")
    def show_recovery_plan(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, module_code, COALESCE(reason,'')
                   FROM attendance
                   WHERE student_id=? AND status IN ('absent','late')
                   ORDER BY date DESC LIMIT 10""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("recovery fetch failed")
            rows = []
        suggestions = [
            (d, mc,
             "Request notes + review recording; book office hours this week.")
            for d, mc, _r in rows
        ]
        _show_table(self.ctx.parent, "Recovery plan",
                    ("date", "module", "suggested action"),
                    suggestions, widths=[100, 120, 620])

    # --- #28 -----------------------------------------------------------
    @safe("Wellbeing check-in")
    def log_wellbeing_checkin(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        abs_id = simpledialog.askinteger("Attendance id",
                                         "Attendance row id (from My Absences):",
                                         parent=self.ctx.parent)
        if abs_id is None:
            return
        note = Prompt.non_empty(self.ctx.parent, "Note",
                                "Private note to self:", min_len=1)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_wellbeing_flags
                   (student_id, attendance_id, note) VALUES (?,?,?)""",
                (sid, abs_id, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.wellbeing",
              "abs_tracker_wellbeing_flags", sid, str(abs_id))
        messagebox.showinfo("Saved", "Check-in saved.",
                            parent=self.ctx.parent)


# ===========================================================================
# SupportService — features #29–#35
# ===========================================================================

