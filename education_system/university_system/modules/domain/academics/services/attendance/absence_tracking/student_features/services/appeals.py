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

class AppealsService:
    """Disputes against attendance records and appeals on rejected requests."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    # --- #40 -----------------------------------------------------------
    @safe("Dispute record")
    def dispute_attendance_record(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        aid = simpledialog.askinteger("Attendance id",
                                      "Row id (from My Absences):",
                                      parent=self.ctx.parent)
        if aid is None:
            return
        reason = Prompt.non_empty(
            self.ctx.parent, "Reason",
            "Why do you believe this is wrong?", min_len=10)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_attendance_disputes
                   (student_id, attendance_id, reason) VALUES (?,?,?)""",
                (sid, aid, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.dispute",
              "abs_tracker_attendance_disputes", sid, f"aid={aid}")
        messagebox.showinfo("Submitted", "Dispute raised.",
                            parent=self.ctx.parent)

    # --- #41 -----------------------------------------------------------
    @safe("Dispute history")
    def show_dispute_history(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, attendance_id, reason, status, created_at,
                          COALESCE(outcome,''), COALESCE(resolved_at,'')
                   FROM abs_tracker_attendance_disputes
                   WHERE student_id=? ORDER BY created_at DESC""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("dispute history fetch failed")
            rows = []
        _show_table(self.ctx.parent, "My disputes",
                    ("id", "attendance id", "reason", "status",
                     "created", "outcome", "resolved"), rows,
                    widths=[60, 120, 260, 100, 150, 140, 150])

    # --- #42 -----------------------------------------------------------
    @safe("Appeal")
    def appeal_rejected_request(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code FROM absence_requests
                   WHERE student_id=? AND status='rejected'""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("rejected fetch failed")
            messagebox.showerror("Error", "Could not load rejected requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("None", "No rejected requests to appeal.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Appeal",
                             "Which request?", list(m.keys()))
        if not pick:
            return
        reason = Prompt.non_empty(self.ctx.parent, "Grounds",
                                  "Grounds for appeal:", min_len=10)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_appeals
                   (student_id, request_id, reason) VALUES (?,?,?)""",
                (sid, m[pick], reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.appeal", "abs_tracker_appeals",
              sid, f"req={m[pick]}")
        messagebox.showinfo("Submitted", "Appeal filed.",
                            parent=self.ctx.parent)


# ===========================================================================
# IntegrationsService — features #43–#47
# ===========================================================================

