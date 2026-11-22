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

from education_system.systems.university.domains.teaching.domain.attendance.absence_tracking.admin_features import (
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

from .context import StudentContext, ensure_student_tables
from .facade import StudentServices
from .registry import FEATURES, FeatureSpec



# ===========================================================================
# Tab renderer
# ===========================================================================

#: Tab (title text) -> the features shown as actions on it. Anything not
#: listed goes under "More tools", grouped by category.
PLACEMENT = {
    "My Stats": [1, 2, 3, 4, 8, 6, 7, 5, 23, 24, 25, 27, 26, 44],
    "Submit Request": [52, 51, 9, 14, 15],
    "My Requests": [11, 10, 12, 13, 42, 16],
    "My Absences": [40, 41],
    "My Modules": [43, 45, 47, 46, 32, 30],
}

def build_student_tab(notebook: ttk.Notebook, ctx: StudentContext) -> None:
    """Place the student tools on the tabs they belong to.

    They used to be a separate "Student Tools (50)" tab of numbered
    buttons. Each now appears as an action on the related tab; the rest are
    under "More tools" in the sidebar."""
    try:
        ensure_support_tables(ctx.db)
        ensure_student_tables(ctx.db)
    except sqlite3.Error:
        logger.exception("could not ensure student tables")
        messagebox.showerror(
            "Student Tools",
            "Could not initialise student-tools tables. See log.",
            parent=ctx.parent)
        return

    services = StudentServices.for_context(ctx)

    notebook.place_features(FEATURES, services, PLACEMENT)
    logger.info("student tools placed on tabs (%d features)", len(FEATURES))

