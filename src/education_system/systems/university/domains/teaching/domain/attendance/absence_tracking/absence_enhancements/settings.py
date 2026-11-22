"""Small key/value settings store over ``absence_settings``."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from .log import logger


# ===========================================================================
# EnhancementSettings — KV store
# ===========================================================================

class EnhancementSettings:
    """KV settings store backed by absence_settings."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            row = self.conn.execute(
                "SELECT value FROM absence_settings WHERE key=?",
                (key,)).fetchone()
            return row[0] if row else default
        except sqlite3.Error:
            logger.exception("settings.get failed key=%s", key)
            return default

    def set(self, key: str, value: Any) -> None:
        try:
            self.conn.execute(
                "INSERT INTO absence_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))
            self.conn.commit()
        except sqlite3.Error:
            self.conn.rollback()
            logger.exception("settings.set failed key=%s", key)
            raise


# Module-level legacy aliases preserved for any older code path.
def get_setting(conn, key, default=None):
    return EnhancementSettings(conn).get(key, default)


def set_setting(conn, key, value):
    EnhancementSettings(conn).set(key, value)


__all__ = [
    "EnhancementSettings",
    "get_setting",
    "set_setting",
]
