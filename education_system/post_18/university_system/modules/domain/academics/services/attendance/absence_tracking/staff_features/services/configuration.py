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

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
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

class ConfigurationService:
    """Module policy, range-excuses, seating chart import."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker) -> None:
        self.ctx = ctx
        self.picker = picker

    # --- #46 ----------------------------------------------------------
    @safe("Module policy quick-edit")
    def edit_module_policy(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        pct = simpledialog.askfloat(
            "Min %", "Minimum attendance % (0-100):",
            parent=self.ctx.parent,
            initialvalue=80, minvalue=0, maxvalue=100)
        if pct is None:
            return
        grace = simpledialog.askinteger(
            "Grace", "Grace minutes for late→present:",
            parent=self.ctx.parent,
            initialvalue=5, minvalue=0, maxvalue=60)
        if grace is None:
            grace = 0
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_module_policy
                   (module_code, min_percent, late_as_absent, grace_minutes,
                    notes)
                   VALUES (?, ?, 0, ?, ?)""",
                (mc, pct, grace,
                 f"edited by {self.ctx.username}"))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("policy save failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.policy", "abs_tracker_module_policy", mc,
              f"pct={pct} grace={grace}")
        messagebox.showinfo("Saved", f"{mc}: ≥{pct}%, grace={grace}m",
                            parent=self.ctx.parent)

    # --- #47 ----------------------------------------------------------
    @safe("Excuse range")
    def excuse_date_range(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, mlabel = picked
        rng = pick_date_range(self.ctx.parent, "Excuse date range")
        if not rng:
            return
        start, end = rng
        reason = (simpledialog.askstring("Reason", "Reason:",
                                         parent=self.ctx.parent
                                         ) or "field trip").strip()
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date()
            d1 = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError as e:
            messagebox.showerror("Bad date", str(e), parent=self.ctx.parent)
            return
        if d1 < d0:
            messagebox.showerror("Bad range",
                                 "End date is before start date.",
                                 parent=self.ctx.parent)
            return
        try:
            roster = self.ctx.db.get_course_students(mc)
        except Exception:
            logger.exception("roster fetch failed mc=%s", mc)
            messagebox.showerror("Error", "Could not load roster.",
                                 parent=self.ctx.parent)
            return
        days = (d1 - d0).days + 1
        if not Prompt.confirm(
                self.ctx.parent, "Confirm",
                f"Excuse {len(roster)} student(s) for {days} day(s) "
                f"on {mlabel}?"):
            return
        n = 0
        try:
            d = d0
            while d <= d1:
                for sid, *_ in roster:
                    self.ctx.db.record_absence(
                        sid, mc, d.isoformat(), "excused", reason)
                    n += 1
                d += timedelta(days=1)
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("excuse range failed mc=%s", mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.excuse_range", "attendance", mc,
              f"{start}..{end} n={n}")
        messagebox.showinfo("Excused",
                            f"{n} rows written {start} → {end}.",
                            parent=self.ctx.parent)

    # --- #48 ----------------------------------------------------------
    @safe("Seating chart")
    def import_seating_chart(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            layout = p.read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("Read failed", str(e),
                                 parent=self.ctx.parent)
            return
        # Validate JSON early so we don't store garbage that breaks
        # downstream consumers.
        try:
            json.loads(layout)
        except json.JSONDecodeError as e:
            messagebox.showerror("Invalid JSON", f"Not valid JSON: {e}",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_seating
                   (module_code, date, layout_json) VALUES (?,?,?)""",
                (mc, d, layout))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("seating chart save failed mc=%s d=%s", mc, d)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.seating", "abs_tracker_seating", mc,
              f"{d} {p.name}")
        messagebox.showinfo("Saved", "Seating plan saved.",
                            parent=self.ctx.parent)
