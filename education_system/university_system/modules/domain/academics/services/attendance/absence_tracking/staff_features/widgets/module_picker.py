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

from ..context import StaffContext

class ModulePicker:
    """Pick a module from the staff member's assigned list."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    def my_modules(self) -> list[tuple]:
        try:
            return self.ctx.db.get_courses(staff_id=self.ctx.uid) or []
        except Exception:
            logger.exception("get_courses failed for uid=%s", self.ctx.uid)
            return []

    def my_module_codes(self) -> list[str]:
        return [r[0] for r in self.my_modules()]

    def pick(self, prompt: str = "Pick one of your modules"
             ) -> Optional[tuple[str, str]]:
        mods = self.my_modules()
        if not mods:
            messagebox.showinfo("No modules",
                                "You are not assigned to any modules.",
                                parent=self.ctx.parent)
            return None
        m = {f"{r[1]} - {r[2]}": r[0] for r in mods}
        pick = _combo_dialog(self.ctx.parent, prompt, "Module:", list(m.keys()))
        if not pick:
            return None
        return m[pick], pick
