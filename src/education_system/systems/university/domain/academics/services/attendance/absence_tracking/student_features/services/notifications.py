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

from education_system.systems.university.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
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

class NotificationService:
    """Reminders, alerts, channel preferences, and DND hours."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #17 -----------------------------------------------------------
    @safe("Class reminder")
    def set_class_reminder(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        current = self.prefs.get_int(sid, "reminder_mins", 0)
        mins = simpledialog.askinteger(
            "Minutes",
            f"Remind me how many minutes before class? (current {current})",
            parent=self.ctx.parent, minvalue=0, maxvalue=240)
        if mins is None:
            return
        try:
            self.prefs.set(sid, "reminder_mins", mins)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.reminder", "prefs", sid, f"mins={mins}")
        messagebox.showinfo("Saved",
                            f"Reminder = {mins} min before class.",
                            parent=self.ctx.parent)

    # --- #18 -----------------------------------------------------------
    @safe("Low-attendance alert")
    def set_low_attendance_alert(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        current = self.prefs.get_float(sid, "self_threshold", 80.0)
        pct = simpledialog.askfloat(
            "Threshold",
            f"Alert me if I drop below %? (current {current:g})",
            parent=self.ctx.parent, minvalue=0, maxvalue=100)
        if pct is None:
            return
        try:
            self.prefs.set(sid, "self_threshold", pct)
            row = self.ctx.db.cur.execute(
                """SELECT SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)*1.0
                          /NULLIF(COUNT(*),0)*100
                   FROM attendance WHERE student_id=?""", (sid,)).fetchone()
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        current_pct = row[0] if row and row[0] is not None else None
        msg = f"Self-threshold saved: {pct}%"
        if current_pct is not None and current_pct < pct:
            msg += f"\n⚠ Already below: {current_pct:.1f}%"
        audit(self.ctx, "student.self_threshold", "prefs", sid, str(pct))
        messagebox.showinfo("Saved", msg, parent=self.ctx.parent)

    # --- #19 -----------------------------------------------------------
    @safe("Deadline alerts")
    def show_upcoming_deadlines(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, name, event_type FROM academic_calendar_events
                   WHERE date >= date('now') ORDER BY date LIMIT 30"""
            ).fetchall()
        except sqlite3.Error:
            logger.exception("deadlines fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Upcoming deadlines",
                    ("date", "name", "type"), rows, widths=[110, 500, 160])

    # --- #20 -----------------------------------------------------------
    @safe("Parent notifications log")
    def show_parent_notifications_log(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT created_date, notification_type,
                          notification_content, read_status
                   FROM parent_notifications WHERE student_id=?
                   ORDER BY created_date DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("parent notifs fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Notifications sent about me",
                    ("when", "type", "content", "read?"), rows,
                    widths=[160, 140, 450, 80])

    # --- #21 -----------------------------------------------------------
    @safe("Notification preferences")
    def edit_channel_preferences(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        win = tk.Toplevel(self.ctx.parent)
        win.title("Notification channels")
        win.geometry("320x220")
        vars_: dict[str, tk.IntVar] = {}
        for key, label in [("notif_email", "Email"),
                           ("notif_inapp", "In-app"),
                           ("notif_sms", "SMS")]:
            v = tk.IntVar(value=self.prefs.get_int(sid, key, 1))
            vars_[key] = v
            tk.Checkbutton(win, text=label, variable=v
                           ).pack(anchor="w", padx=20, pady=4)

        def save():
            try:
                for k, v in vars_.items():
                    self.prefs.set(sid, k, v.get())
            except sqlite3.Error as e:
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "student.notif_prefs", "prefs", sid,
                  json.dumps({k: v.get() for k, v in vars_.items()}))
            messagebox.showinfo("Saved", "Preferences updated.", parent=win)
            win.destroy()

        tk.Button(win, text="Save", command=save, bg="#2563eb", fg="white",
                  relief="flat", padx=20, pady=6).pack(pady=10)

    # --- #22 -----------------------------------------------------------
    @safe("DND hours")
    def set_dnd_hours(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        cur_start = self.prefs.get(sid, "dnd_start", "22:00")
        cur_end   = self.prefs.get(sid, "dnd_end", "07:00")
        start = Prompt.hhmm(self.ctx.parent, "DND start",
                            "Start (HH:MM):", initial=cur_start)
        if start is None:
            return
        end = Prompt.hhmm(self.ctx.parent, "DND end",
                          "End (HH:MM):", initial=cur_end)
        if end is None:
            return
        try:
            self.prefs.set(sid, "dnd_start", start)
            self.prefs.set(sid, "dnd_end", end)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.dnd", "prefs", sid, f"{start}-{end}")
        messagebox.showinfo("Saved", "Do-not-disturb hours updated.",
                            parent=self.ctx.parent)


# ===========================================================================
# PlanningService — features #23–#28
# ===========================================================================

