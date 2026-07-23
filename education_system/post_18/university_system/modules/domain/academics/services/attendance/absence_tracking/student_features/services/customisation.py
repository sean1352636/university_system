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

class CustomisationService:
    """Accessibility, language, dashboard layout."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #48 -----------------------------------------------------------
    @safe("Accessibility mode")
    def toggle_accessibility_mode(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        on = self.prefs.get(sid, "a11y", "0") != "1"
        try:
            self.prefs.set(sid, "a11y", "1" if on else "0")
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        try:
            style = ttk.Style()
            if on:
                style.configure("Treeview", rowheight=34, font=("Arial", 13))
                style.configure("Treeview.Heading", font=("Arial", 13, "bold"))
                self.ctx.parent.option_add("*Font", "Arial 13")
            else:
                style.configure("Treeview", rowheight=26, font=("Arial", 10))
                style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
                self.ctx.parent.option_add("*Font", "Arial 10")
        except tk.TclError:
            logger.exception("a11y style apply failed")
        audit(self.ctx, "student.a11y", "prefs", sid, "on" if on else "off")
        messagebox.showinfo("Accessibility",
                            f"Accessibility mode is now {'ON' if on else 'OFF'}.",
                            parent=self.ctx.parent)

    # --- #49 -----------------------------------------------------------
    @safe("Language")
    def set_language(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        lang = _combo_dialog(self.ctx.parent, "Language", "Language:",
                             ["en", "fr", "es", "de", "zh", "ar"])
        if not lang:
            return
        try:
            self.prefs.set(sid, "language", lang)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.language", "prefs", sid, lang)
        messagebox.showinfo("Saved",
                            f"Language set to '{lang}'. Restart to apply everywhere.",
                            parent=self.ctx.parent)

    # --- #50 -----------------------------------------------------------
    @safe("Dashboard layout")
    def edit_dashboard_layout(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        default = ("📚 My Modules,📋 My Absences,📤 Submit Request,"
                   "📨 My Requests,📊 My Stats,🧑‍🎓 Student Tools (50)")
        current = self.prefs.get(sid, "dashboard_tabs", default)
        new = simpledialog.askstring(
            "Tabs order",
            "Comma-separated tab names in desired order:",
            parent=self.ctx.parent, initialvalue=current)
        if new is None:
            return
        try:
            self.prefs.set(sid, "dashboard_tabs", new)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "student.layout", "prefs", sid, new)
        messagebox.showinfo("Saved",
                            "Layout saved. It'll take effect next time you open the tracker.",
                            parent=self.ctx.parent)
