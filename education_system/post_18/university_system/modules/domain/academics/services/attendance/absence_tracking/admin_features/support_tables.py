"""Support-table DDL, settings helpers, and the soft-delete shim."""
from __future__ import annotations

import json
import sqlite3

from .context import logger


def ensure_support_tables(db) -> None:
    """Create all support tables used by the admin features if missing."""
    cur = db.cur
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS abs_tracker_audit (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id     INTEGER, username TEXT,
            action      TEXT, target TEXT, target_id TEXT, details TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_trash (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            deleted_at     TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by     TEXT,
            original_table TEXT, original_id INTEGER, payload TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_settings (
            key   TEXT PRIMARY KEY, value TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_module_policy (
            module_code      TEXT PRIMARY KEY,
            min_percent      REAL,
            late_as_absent   INTEGER, grace_minutes INTEGER, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_statuses (
            code TEXT PRIMARY KEY, label TEXT, counts_as TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_auto_excuse_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT, status TEXT DEFAULT 'excused',
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, file_path TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER, author TEXT, body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_request_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, body TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_delegations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER, to_user INTEGER,
            active_from TEXT, active_to TEXT
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_scheduled_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, frequency TEXT, recipients TEXT,
            report_type TEXT, last_run TEXT, enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS abs_tracker_retention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy TEXT, years INTEGER, applied_at TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance_grade_penalties (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id   TEXT NOT NULL,
            module_code  TEXT NOT NULL,
            threshold    REAL,
            pct          REAL,
            applied_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            applied_by   TEXT,
            grade_row_id INTEGER,
            UNIQUE(student_id, module_code)
        );
    """)
    cur.executemany(
        "INSERT OR IGNORE INTO abs_tracker_statuses (code, label, counts_as) VALUES (?,?,?)",
        [("present", "Present", "present"),
         ("absent",  "Absent",  "absent"),
         ("late",    "Late",    "late"),
         ("excused", "Excused", "excused")])
    db.conn.commit()


# ===========================================================================
# Settings + dialog helpers (module-level, public API)
# ===========================================================================

def _get_setting(db, key, default=None):
    try:
        r = db.cur.execute(
            "SELECT value FROM abs_tracker_settings WHERE key=?",
            (key,)).fetchone()
        return r[0] if r else default
    except sqlite3.Error:
        logger.exception("get_setting failed key=%s", key)
        return default


def _set_setting(db, key, value):
    try:
        db.cur.execute(
            "INSERT OR REPLACE INTO abs_tracker_settings (key, value) VALUES (?, ?)",
            (key, str(value)))
        db.conn.commit()
    except sqlite3.Error:
        db.conn.rollback()
        logger.exception("set_setting failed key=%s", key)
        raise


def install_soft_delete(db) -> None:
    """Wrap Database.delete_absence so deletions land in the 24h trash."""
    if getattr(db, "_soft_delete_installed", False):
        return
    original = db.delete_absence

    def soft_delete(absence_id: int) -> None:
        try:
            row = db.cur.execute(
                """SELECT id, student_id, module_code, date, status, reason
                   FROM attendance WHERE id=?""", (absence_id,)).fetchone()
            if row:
                payload = json.dumps({
                    "id": row[0], "student_id": row[1],
                    "module_code": row[2], "date": row[3],
                    "status": row[4], "reason": row[5],
                })
                db.cur.execute(
                    """INSERT INTO abs_tracker_trash
                       (deleted_by, original_table, original_id, payload)
                       VALUES (?, 'attendance', ?, ?)""",
                    ("admin", row[0], payload))
        except sqlite3.Error:
            logger.exception("soft-delete snapshot failed id=%s", absence_id)
        original(absence_id)

    db.delete_absence = soft_delete
    db._soft_delete_installed = True

