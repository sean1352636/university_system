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

from education_system.systems.university.domains.teaching.domain.attendance.absence_tracking.admin_features import (
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

from .context import StaffContext, ensure_staff_tables
from .facade import StaffServices
from .registry import FEATURES, FeatureSpec

#: Tab (title text) -> the features shown as actions on it. Anything not
#: listed goes under "More tools", grouped by category.
PLACEMENT = {
    "Record Attendance": [1, 2, 6, 7, 8, 9, 3, 4, 5, 10, 47, 48],
    "Absence Requests": [16, 17, 18, 19, 20, 21],
    "Records": [22, 23, 24, 25, 27, 28, 26],
    "My Modules": [11, 12, 13, 14, 15, 46],
}

def build_staff_tab(notebook: ttk.Notebook, ctx: StaffContext) -> None:
    """Place the staff tools on the tabs they belong to.

    They used to be a separate "Staff Tools (50)" tab of numbered
    buttons. Each now appears as an action on the related tab; the rest are
    under "More tools" in the sidebar."""
    try:
        ensure_support_tables(ctx.db)
        ensure_staff_tables(ctx.db)
    except sqlite3.Error:
        logger.exception("could not ensure staff tables")
        messagebox.showerror(
            "Staff Tools",
            "Could not initialise staff-tools tables. See log.",
            parent=ctx.parent)
        return

    services = StaffServices.for_context(ctx)

    notebook.place_features(FEATURES, services, PLACEMENT)
    logger.info("staff tools placed on tabs (%d features)", len(FEATURES))
