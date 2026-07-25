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

class StaffPrefs:
    """Typed accessor for per-user staff preferences."""

    def __init__(self, db) -> None:
        self.db = db

    def get(self, uid: int, key: str,
            default: Optional[str] = None) -> Optional[str]:
        try:
            r = self.db.cur.execute(
                "SELECT value FROM abs_tracker_staff_prefs WHERE user_id=? AND key=?",
                (uid, key)).fetchone()
            return r[0] if r else default
        except sqlite3.Error:
            logger.exception("StaffPrefs.get failed (uid=%s key=%s)", uid, key)
            return default

    def set(self, uid: int, key: str, value: Any) -> None:
        try:
            self.db.cur.execute(
                """INSERT OR REPLACE INTO abs_tracker_staff_prefs
                   (user_id, key, value) VALUES (?, ?, ?)""",
                (uid, key, str(value)))
            self.db.conn.commit()
        except sqlite3.Error:
            self.db.conn.rollback()
            logger.exception("StaffPrefs.set failed (uid=%s key=%s)", uid, key)
            raise
