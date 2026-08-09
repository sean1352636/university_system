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

from ..context import StaffContext

class StaffPicker:
    """Pick another staff/instructor user."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def pick(self, title: str, prompt: str,
             *, exclude_self: bool = True
             ) -> Optional[tuple[int, str]]:
        try:
            users = (self.ctx.db.get_users("instructor")
                     + self.ctx.db.get_users("staff"))
        except Exception:
            logger.exception("get_users failed")
            messagebox.showerror("Error", "Could not load staff list.",
                                 parent=self.ctx.parent)
            return None
        if not users:
            messagebox.showinfo("No staff", "No other staff users.",
                                parent=self.ctx.parent)
            return None
        m = {f"{r[3] or r[1]} ({r[1]})": r[0]
             for r in users
             if (not exclude_self) or r[0] != self.ctx.uid}
        if not m:
            messagebox.showinfo("No staff",
                                "No eligible staff users.",
                                parent=self.ctx.parent)
            return None
        pick = _combo_dialog(self.ctx.parent, title, prompt, list(m.keys()))
        if not pick:
            return None
        return m[pick], pick
