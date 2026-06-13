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

class StudentPrefs:
    """Typed accessor for per-student key/value preferences."""

    def __init__(self, db) -> None:
        self.db = db

    def get(self, sid: str, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            r = self.db.cur.execute(
                "SELECT value FROM abs_tracker_student_prefs WHERE student_id=? AND key=?",
                (sid, key),
            ).fetchone()
            return r[0] if r else default
        except sqlite3.Error:
            logger.exception("StudentPrefs.get failed (sid=%s key=%s)", sid, key)
            return default

    def set(self, sid: str, key: str, value: Any) -> None:
        try:
            self.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_student_prefs
                   (student_id, key, value) VALUES (?, ?, ?)""",
                (sid, key, str(value)),
            )
            self.db.conn.commit()
        except sqlite3.Error:
            self.db.conn.rollback()
            logger.exception("StudentPrefs.set failed (sid=%s key=%s)", sid, key)
            raise

    def get_int(self, sid: str, key: str, default: int = 0) -> int:
        try:
            return int(self.get(sid, key, str(default)))
        except (TypeError, ValueError):
            return default

    def get_float(self, sid: str, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(sid, key, str(default)))
        except (TypeError, ValueError):
            return default


# ===========================================================================
# Dialog + validation helpers
# ===========================================================================

