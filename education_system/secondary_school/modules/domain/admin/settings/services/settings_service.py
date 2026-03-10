"""School settings service."""

import logging
from education_system.secondary_school.core.exceptions import SettingsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CATEGORIES = ("general", "academic", "attendance", "behaviour", "communication", "display")

DEFAULT_SETTINGS = [
    ("school_name", "Secondary School", "general", "Name of the school"),
    ("school_address", "", "general", "School address"),
    ("school_phone", "", "general", "Main phone number"),
    ("school_email", "", "general", "Main email address"),
    ("headteacher", "", "general", "Headteacher name"),
    ("academic_year", "2025/2026", "academic", "Current academic year"),
    ("autumn_term_start", "2025-09-01", "academic", "Autumn term start date"),
    ("autumn_term_end", "2025-12-19", "academic", "Autumn term end date"),
    ("spring_term_start", "2026-01-05", "academic", "Spring term start date"),
    ("spring_term_end", "2026-03-27", "academic", "Spring term end date"),
    ("summer_term_start", "2026-04-13", "academic", "Summer term start date"),
    ("summer_term_end", "2026-07-17", "academic", "Summer term end date"),
    ("periods_per_day", "6", "academic", "Number of periods per day"),
    ("registration_time", "08:40", "attendance", "Morning registration time"),
    ("school_start_time", "08:50", "attendance", "First lesson start time"),
    ("school_end_time", "15:10", "attendance", "School day end time"),
    ("late_threshold_minutes", "10", "attendance", "Minutes after which a student is marked late"),
    ("positive_points_default", "1", "behaviour", "Default positive behaviour points"),
    ("negative_points_default", "-1", "behaviour", "Default negative behaviour points"),
]


class SettingsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def seed_defaults(self):
        conn = self._conn()
        try:
            for key, value, category, description in DEFAULT_SETTINGS:
                existing = conn.execute("SELECT id FROM school_settings WHERE key = ?", (key,)).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT INTO school_settings (key, value, category, description) VALUES (?, ?, ?, ?)",
                        (key, value, category, description))
            conn.commit()
        finally:
            conn.close()

    def get(self, key, default=None):
        conn = self._conn()
        try:
            row = conn.execute("SELECT value FROM school_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set(self, key, value, updated_by=None):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE school_settings SET value = ?, updated_by = ?, updated_at = datetime('now') WHERE key = ?",
                (value, updated_by, key))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise SettingsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_settings(self, category=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM school_settings WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY category, key"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
