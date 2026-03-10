"""Settings management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import SettingsError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing user and system settings."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- User Settings ---

    def get_user_setting(self, user_id: int, key: str,
                         default: str | None = None) -> str | None:
        """Get a single user setting."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT setting_value FROM user_settings WHERE user_id = ? AND setting_key = ?",
                (user_id, key),
            ).fetchone()
            return row["setting_value"] if row else default
        finally:
            conn.close()

    def set_user_setting(self, user_id: int, key: str,
                         value: str | None) -> None:
        """Set a user setting (INSERT OR REPLACE)."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO user_settings (user_id, setting_key, setting_value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, setting_key)
                   DO UPDATE SET setting_value = excluded.setting_value""",
                (user_id, key, value),
            )
            conn.commit()
            logger.debug("User setting saved: user=%d key=%s", user_id, key)
        except Exception as e:
            conn.rollback()
            raise SettingsError(f"Failed to save setting: {e}") from e
        finally:
            conn.close()

    def get_all_user_settings(self, user_id: int) -> dict:
        """Get all settings for a user as a dict."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT setting_key, setting_value FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            return {r["setting_key"]: r["setting_value"] for r in rows}
        finally:
            conn.close()

    # --- System Settings ---

    def get_system_setting(self, key: str,
                           default: str | None = None) -> str | None:
        """Get a single system setting."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = ?",
                (key,),
            ).fetchone()
            return row["setting_value"] if row else default
        finally:
            conn.close()

    def set_system_setting(self, key: str, value: str | None,
                           updated_by: int | None = None) -> None:
        """Set a system setting (INSERT OR REPLACE)."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO system_settings (setting_key, setting_value, updated_by, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(setting_key)
                   DO UPDATE SET setting_value = excluded.setting_value,
                                 updated_by = excluded.updated_by,
                                 updated_at = excluded.updated_at""",
                (key, value, updated_by, datetime.now().isoformat()),
            )
            conn.commit()
            logger.info("System setting saved: key=%s", key)
        except Exception as e:
            conn.rollback()
            raise SettingsError(f"Failed to save system setting: {e}") from e
        finally:
            conn.close()

    def get_all_system_settings(self) -> dict:
        """Get all system settings as a dict."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT setting_key, setting_value FROM system_settings"
            ).fetchall()
            return {r["setting_key"]: r["setting_value"] for r in rows}
        finally:
            conn.close()
