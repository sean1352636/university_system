"""Settings management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import SettingsError
import traceback

logger = logging.getLogger(__name__)


class SettingsService:
    """CRUD operations for system settings."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def get_setting(self, key):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    def set_setting(self, key, value, category="General", description=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO settings (key, value, category, description)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    description = COALESCE(excluded.description, settings.description),
                    updated_at = datetime('now')""",
                (key, value, category, description),
            )
            conn.commit()
            logger.info("Set setting: %s = %s", key, value)
            return {"key": key, "value": value, "category": category}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SettingsError(f"Failed to set setting: {e}") from e
        finally:
            conn.close()

    def get_all_settings(self, category=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM settings WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY category, key"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def delete_setting(self, key):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted setting: %s", key)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SettingsError(f"Failed to delete setting: {e}") from e
        finally:
            conn.close()
