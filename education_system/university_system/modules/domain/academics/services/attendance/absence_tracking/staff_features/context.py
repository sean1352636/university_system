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

@dataclass
class StaffContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def uid(self) -> int:
        return int(self.user.get("id") or 0)

    @property
    def username(self) -> str:
        return str(self.user.get("username") or "")

    def require_uid(self) -> Optional[int]:
        if not self.uid:
            messagebox.showerror(
                "Missing user id",
                "Your user account is not linked to a staff record.",
                parent=self.parent,
            )
            return None
        return self.uid


def ensure_staff_tables(db) -> None:
    """Create staff-side support tables if missing."""
    db.cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_session_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id   INTEGER, module_code TEXT, date TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_session_status (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, status TEXT,
            set_by      INTEGER, set_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_staff_prefs (
            user_id INTEGER, key TEXT, value TEXT,
            PRIMARY KEY (user_id, key)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, name TEXT, UNIQUE(module_code, name)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER, student_id TEXT, UNIQUE(group_id, student_id)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_session_qr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, code TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_staff_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, task TEXT, done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            done_at TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_intervention_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, student_id TEXT, action TEXT, outcome TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_peer_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            observer_id INTEGER, subject_id INTEGER, module_code TEXT,
            date TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_seating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT, date TEXT, layout_json TEXT,
            UNIQUE(module_code, date)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_co_teachers (
            module_code TEXT, user_id INTEGER,
            PRIMARY KEY (module_code, user_id)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_ta_handoff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER, ta_id INTEGER, module_code TEXT, note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_route (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, routed_to INTEGER, reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.conn.commit()
