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

def _bind_wheel(canvas: tk.Canvas) -> None:
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    canvas.bind_all("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda _e: canvas.yview_scroll(+1, "units"))


def _unbind_wheel(canvas: tk.Canvas) -> None:
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.unbind_all(seq)
