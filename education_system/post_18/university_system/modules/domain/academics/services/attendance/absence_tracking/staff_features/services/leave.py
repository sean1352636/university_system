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

_DEFAULT_LEAVE_TYPES = [
    (1, "Annual leave"),
    (2, "Sick leave"),
    (3, "Personal"),
    (4, "Bereavement"),
    (5, "Training"),
]


class LeaveService:
    """File a staff leave request via leave_requests."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def _ensure_default_types(self) -> None:
        try:
            self.ctx.db.cur.executemany(
                """INSERT OR IGNORE INTO leave_types
                   (leave_type_id, name, requires_approval, is_active)
                   VALUES (?, ?, 1, 1)""", _DEFAULT_LEAVE_TYPES)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("leave_types seed failed")

    @safe("Request time off")
    def request_time_off(self) -> None:
        if self.ctx.require_uid() is None:
            return
        self._ensure_default_types()
        try:
            types = self.ctx.db.cur.execute(
                """SELECT leave_type_id, name FROM leave_types
                   WHERE is_active=1 ORDER BY name""").fetchall()
        except sqlite3.Error:
            logger.exception("leave_types fetch failed")
            messagebox.showerror("Error", "Could not load leave types.",
                                 parent=self.ctx.parent)
            return
        if not types:
            messagebox.showinfo("None", "No active leave types.",
                                parent=self.ctx.parent)
            return
        tmap = {r[1]: r[0] for r in types}
        tpick = _combo_dialog(self.ctx.parent, "Leave type",
                              "Type:", list(tmap.keys()))
        if not tpick:
            return
        rng = pick_date_range(self.ctx.parent, "Leave dates")
        if not rng:
            return
        start, end = rng
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
        reason = (simpledialog.askstring("Reason", "Reason:",
                                         parent=self.ctx.parent) or "").strip()
        total = (d1 - d0).days + 1
        now = datetime.now().isoformat(timespec="seconds")
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO leave_requests
                   (user_id, leave_type_id, start_date, end_date,
                    total_days, reason, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (str(self.ctx.uid), tmap[tpick], start, end, total, reason,
                 now, now))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("leave request insert failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.request_time_off", "leave_requests",
              self.ctx.uid, f"{tpick} {start}..{end} ({total}d)")
        messagebox.showinfo(
            "Submitted",
            f"Leave request ({tpick}, {total} day{'s' if total != 1 else ''}) "
            f"submitted for {start} → {end}.",
            parent=self.ctx.parent)

