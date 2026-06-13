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

@dataclass
class StudentContext:
    db: Any
    parent: tk.Misc
    user: dict

    @property
    def sid(self) -> Optional[str]:
        return self.user.get("student_id")

    def require_sid(self) -> Optional[str]:
        if not self.sid:
            messagebox.showerror(
                "Missing student_id",
                "Your user account is not linked to a student record.",
                parent=self.parent,
            )
            return None
        return self.sid


def ensure_student_tables(db) -> None:
    """Create student-side support tables if missing."""
    db.cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_student_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, target_pct REAL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_drafts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT, date TEXT, reason TEXT,
            saved_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_prefs (
            student_id TEXT, key TEXT, value TEXT,
            PRIMARY KEY(student_id, key)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_attendance_disputes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT, attendance_id INTEGER, reason TEXT,
            status        TEXT DEFAULT 'open',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at   TEXT, outcome TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_note_requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT, module_code TEXT, date TEXT,
            status       TEXT DEFAULT 'open',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            fulfiller_id TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_study_buddies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, module_code TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, module_code)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_wellbeing_flags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, attendance_id INTEGER, note TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_note_share (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id     TEXT, module_code TEXT, date TEXT,
            file_path    TEXT, title TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_student_badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, badge TEXT, awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, badge)
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_appeals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT, request_id INTEGER, reason TEXT,
            status      TEXT DEFAULT 'open',
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.conn.commit()


# ===========================================================================
# Preferences (typed wrapper around abs_tracker_student_prefs)
# ===========================================================================
