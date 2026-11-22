"""ReportingService — features #19–#26 (+ _parents_of).

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


class ReportingService:
    """At-risk, module health, cohorts, trends, scheduled reports, heatmap."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    # --- #19 ----------------------------------------------------------
    @safe("At-risk students")
    def show_at_risk_students(self) -> None:
        threshold = simpledialog.askfloat(
            "Threshold", "Below what % counts as at-risk?",
            parent=self.ctx.parent, minvalue=0, maxvalue=100,
            initialvalue=80) or 80
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          COALESCE(s.first_name||' '||s.last_name,
                                   a.student_id) AS name,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct,
                          COUNT(*) AS total
                   FROM attendance a
                   LEFT JOIN students s ON s.student_id = a.student_id
                   GROUP BY a.student_id
                   HAVING pct IS NOT NULL AND pct < ?
                   ORDER BY pct ASC""", (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("at-risk query failed")
            messagebox.showerror("Error", "Could not run report.",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "at_risk_report", "attendance", "",
              f"threshold={threshold} n={len(rows)}")
        _report_window(self.ctx.parent, f"At-risk (<{threshold:.0f}%)",
                       ("student_id", "name", "pct", "sessions"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 260, 90, 90])

    # --- #20 ----------------------------------------------------------
    @safe("Module health")
    def show_module_health(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.module_code,
                          COALESCE(m.module_name, a.module_code) AS name,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100,
                          COUNT(*) AS total
                   FROM attendance a
                   LEFT JOIN modules m ON m.module_code = a.module_code
                   GROUP BY a.module_code ORDER BY 3 ASC""").fetchall()
        except sqlite3.Error:
            logger.exception("module health query failed")
            rows = []
        _report_window(self.ctx.parent, "Module health",
                       ("module", "name", "avg %", "rows"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 360, 90, 90])

    # --- #21 ----------------------------------------------------------
    @safe("Cohort compare")
    def compare_cohorts(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT COALESCE(s.course,'(none)') AS cohort,
                          COUNT(DISTINCT s.student_id) AS students,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS avg_pct
                   FROM students s
                   LEFT JOIN attendance a ON a.student_id = s.student_id
                   GROUP BY cohort ORDER BY 3 DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("cohort compare failed")
            rows = []
        _report_window(self.ctx.parent, "Cohort comparison",
                       ("cohort", "students", "avg %"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[320, 110, 110])

    # --- #22 ----------------------------------------------------------
    @safe("Trend chart")
    def show_weekly_trend(self) -> None:
        try:
            weeks = self.ctx.db.cur.execute(
                """SELECT strftime('%Y-%W', date) AS wk,
                          a.module_code,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(*),0) * 100
                   FROM attendance a
                   GROUP BY wk, a.module_code ORDER BY wk""").fetchall()
        except sqlite3.Error:
            logger.exception("trend query failed")
            weeks = []
        _report_window(self.ctx.parent, "Weekly % per module",
                       ("week", "module", "pct"), weeks,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[110, 140, 120])

    # --- #23 ----------------------------------------------------------
    @safe("Term compare")
    def compare_terms(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT s.name AS semester, s.start_date, s.end_date,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS pct,
                          COUNT(a.id) AS rows
                   FROM semesters s
                   LEFT JOIN attendance a
                       ON a.date BETWEEN s.start_date AND s.end_date
                   GROUP BY s.id ORDER BY s.start_date""").fetchall()
        except sqlite3.Error:
            logger.exception("term compare failed")
            rows = []
        _report_window(self.ctx.parent, "Term-over-term",
                       ("semester", "start", "end", "pct", "rows"), rows,
                       db=self.ctx.db, user=self.ctx.user)

    # --- #24 ----------------------------------------------------------
    @safe("Schedule report")
    def schedule_recurring_report(self) -> None:
        name = Prompt.non_empty(self.ctx.parent, "Name",
                                "Report name:", min_len=2)
        if not name:
            return
        freq = _combo_dialog(self.ctx.parent, "Frequency", "Frequency:",
                             ["daily", "weekly", "monthly"]) or "weekly"
        recips = simpledialog.askstring(
            "Recipients", "Comma-separated emails:",
            parent=self.ctx.parent) or ""
        rtype = _combo_dialog(
            self.ctx.parent, "Type", "Report type:",
            ["at_risk", "module_health", "cohort_compare"]) or "at_risk"
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_scheduled_reports
                   (name, frequency, recipients, report_type)
                   VALUES (?,?,?,?)""",
                (name, freq, recips, rtype))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("scheduled report insert failed name=%s", name)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "schedule_report",
              "abs_tracker_scheduled_reports", "",
              f"{name} {freq} {rtype}")
        messagebox.showinfo(
            "Scheduled",
            f"{name} ({freq}) → {recips or '(none)'}",
            parent=self.ctx.parent)

    # --- #25 ----------------------------------------------------------
    @safe("Consecutive absences")
    def show_top_absentees(self) -> None:
        n = simpledialog.askinteger("Top N", "How many to show?",
                                    parent=self.ctx.parent,
                                    minvalue=1, initialvalue=20) or 20
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT student_id, COUNT(*) AS absences
                   FROM attendance WHERE status='absent'
                   GROUP BY student_id
                   ORDER BY absences DESC LIMIT ?""", (n,)).fetchall()
        except sqlite3.Error:
            logger.exception("absentee query failed")
            rows = []
        _report_window(self.ctx.parent, f"Top {n} by absence count",
                       ("student", "absences"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[180, 120])

    # --- #26 ----------------------------------------------------------
    @safe("Heatmap")
    def show_dayofweek_heatmap(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT CASE strftime('%w', date)
                            WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon'
                            WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed'
                            WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
                            WHEN '6' THEN 'Sat' END AS dow,
                          COUNT(*) AS absences
                   FROM attendance WHERE status='absent'
                   GROUP BY dow ORDER BY dow""").fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            rows = []
        _report_window(self.ctx.parent, "Absences by day-of-week",
                       ("day", "absences"), rows,
                       db=self.ctx.db, user=self.ctx.user,
                       widths=[140, 140])


# ===========================================================================
# NotificationService — features #27–#30
# ===========================================================================

def _parents_of(db, sid: str) -> list[str]:
    """Return parent_ids linked to a student. Empty list on error."""
    try:
        return [str(r[0]) for r in db.cur.execute(
            "SELECT parent_id FROM parent_student_links WHERE student_id=?",
            (sid,)).fetchall()]
    except sqlite3.Error:
        logger.exception("parents lookup failed sid=%s", sid)
        return []

