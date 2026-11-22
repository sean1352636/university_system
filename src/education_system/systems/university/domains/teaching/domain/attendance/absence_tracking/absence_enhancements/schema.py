"""Enhanced absence tables and their one-time bootstrap."""

from __future__ import annotations

import sqlite3

from .log import logger


# ===========================================================================
# Schema
# ===========================================================================

SCHEMA_SQL = [
    """CREATE TABLE IF NOT EXISTS absence_request_categories (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         name TEXT UNIQUE NOT NULL,
         description TEXT,
         requires_evidence INTEGER DEFAULT 0,
         approval_route TEXT DEFAULT 'instructor',
         auto_approve INTEGER DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS attendance_kiosks (
         kiosk_id TEXT PRIMARY KEY,
         room TEXT, lat REAL, lon REAL,
         radius_m REAL DEFAULT 50,
         active INTEGER DEFAULT 1
       )""",
    """CREATE TABLE IF NOT EXISTS absence_push_queue (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         user_id TEXT NOT NULL,
         title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         delivered_at TEXT, status TEXT DEFAULT 'pending'
       )""",
    """CREATE TABLE IF NOT EXISTS ukvi_engagement_events (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, event_type TEXT NOT NULL,
         event_date TEXT NOT NULL, notes TEXT, recorded_by TEXT,
         recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    """CREATE TABLE IF NOT EXISTS absence_evidence_signatures (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         request_id INTEGER NOT NULL, file_path TEXT NOT NULL,
         sha256 TEXT NOT NULL, signed_by TEXT,
         signed_at TEXT DEFAULT CURRENT_TIMESTAMP
       )""",
    """CREATE TABLE IF NOT EXISTS attendance_anomalies (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         kind TEXT NOT NULL,
         student_id TEXT, module_code TEXT, details TEXT,
         severity TEXT DEFAULT 'medium',
         detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
         resolved INTEGER DEFAULT 0
       )""",
    """CREATE TABLE IF NOT EXISTS lms_access_grants (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         student_id TEXT NOT NULL, module_code TEXT NOT NULL,
         session_date TEXT NOT NULL, resource TEXT NOT NULL,
         granted INTEGER DEFAULT 0, reason TEXT,
         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
         UNIQUE(student_id, module_code, session_date, resource)
       )""",
    """CREATE TABLE IF NOT EXISTS absence_settings (
         key TEXT PRIMARY KEY, value TEXT
       )""",
]

SEED_CATEGORIES = [
    ("medical",        "Illness / medical appointment",  1, "instructor", 0),
    ("bereavement",    "Family bereavement",             0, "dept_head",  1),
    ("religious",      "Religious observance",           0, "instructor", 1),
    ("representative", "University representative duty", 0, "instructor", 1),
    ("other",          "Other — requires narrative",     0, "instructor", 0),
]


def ensure_enhanced_schema(conn: sqlite3.Connection) -> None:
    """Create / migrate every table the enhancement features need."""
    try:
        cur = conn.cursor()
        for ddl in SCHEMA_SQL:
            cur.execute(ddl)
        # Add category_id + date_end columns to absence_requests if missing.
        cur.execute("PRAGMA table_info(absence_requests)")
        cols = {r[1] for r in cur.fetchall()}
        if "category_id" not in cols:
            try:
                cur.execute(
                    "ALTER TABLE absence_requests ADD COLUMN category_id INTEGER")
            except sqlite3.OperationalError:
                logger.debug("category_id ALTER skipped", exc_info=True)
        if "date_end" not in cols:
            try:
                cur.execute(
                    "ALTER TABLE absence_requests ADD COLUMN date_end TEXT")
            except sqlite3.OperationalError:
                logger.debug("date_end ALTER skipped", exc_info=True)
        cur.execute("SELECT COUNT(*) FROM absence_request_categories")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                """INSERT INTO absence_request_categories
                     (name, description, requires_evidence,
                      approval_route, auto_approve)
                   VALUES (?, ?, ?, ?, ?)""",
                SEED_CATEGORIES)
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        logger.exception("ensure_enhanced_schema failed")
        raise


__all__ = [
    "SCHEMA_SQL",
    "SEED_CATEGORIES",
    "ensure_enhanced_schema",
]
