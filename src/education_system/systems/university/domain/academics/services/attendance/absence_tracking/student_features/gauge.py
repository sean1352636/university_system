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

@dataclass(frozen=True)
class GaugeThresholds:
    good: float = 85.0
    warn: float = 70.0

    def band(self, pct: float) -> str:
        if pct >= self.good:
            return "good"
        if pct >= self.warn:
            return "warn"
        return "poor"


_GAUGE_COLOURS = {"good": "#16a34a", "warn": "#f59e0b", "poor": "#dc2626"}
_GAUGE_LABELS = {"good": "On track", "warn": "At risk", "poor": "Below threshold"}


def _load_gauge_thresholds(db) -> GaugeThresholds:
    try:
        good = float(_get_setting(db, "gauge.good_pct", "85"))
        warn = float(_get_setting(db, "gauge.warn_pct", "70"))
        if 0 < warn < good <= 100:
            return GaugeThresholds(good=good, warn=warn)
    except Exception:
        logger.debug("gauge thresholds settings unreadable, using defaults",
                     exc_info=True)
    return GaugeThresholds()


