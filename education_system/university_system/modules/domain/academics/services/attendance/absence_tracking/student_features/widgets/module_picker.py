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

from ..context import StudentContext

class ModulePicker:
    """Pick a module from a student's enrolments."""

    def __init__(self, ctx: StudentContext) -> None:
        self.ctx = ctx

    def pick(self, sid: str, title: str = "Module"
             ) -> Optional[tuple[str, str]]:
        """Return (module_code, label) or None if the student has none / cancels."""
        try:
            modules = self.ctx.db.get_courses(student_id=sid)
        except Exception:
            logger.exception("get_courses failed for sid=%s", sid)
            messagebox.showerror("Error",
                                 "Could not load your enrolments.",
                                 parent=self.ctx.parent)
            return None
        if not modules:
            messagebox.showinfo("No modules",
                                "You are not enrolled in any modules.",
                                parent=self.ctx.parent)
            return None
        mmap = {f"{c[1]} - {c[2]}": c[0] for c in modules}
        pick = _combo_dialog(self.ctx.parent, title, "Module:", list(mmap.keys()))
        if not pick:
            return None
        return mmap[pick], pick

