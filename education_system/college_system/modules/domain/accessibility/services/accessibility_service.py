"""Service for managing accessibility."""

from datetime import datetime
from education_system.college_system.core.exceptions import AccessibilityError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class AccessibilityService:
    """Accessibility management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_preference(self, **kwargs) -> dict:
        """Create a new preference."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO accessibility_preferences (user_id, theme, font_size, font_family, reduce_animations, screen_reader_mode, high_contrast)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('user_id'), kwargs.get('theme'), kwargs.get('font_size'), kwargs.get('font_family'), kwargs.get('reduce_animations'), kwargs.get('screen_reader_mode'), kwargs.get('high_contrast'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM accessibility_preferences WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Preference created: id=%d", row["id"])
            return dict(row)
        except AccessibilityError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AccessibilityError(f"Failed to create preference: {e}") from e
        finally:
            conn.close()

    def get_preference(self, pk: int) -> dict | None:
        """Get preference by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM accessibility_preferences WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_preferences(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List preferences with optional filters."""
        sql = "SELECT * FROM accessibility_preferences WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {key} = ?"
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_preference(self, pk: int, **kwargs) -> dict:
        """Update preference record."""
        allowed = {"user_id", "theme", "font_size", "font_family", "reduce_animations", "screen_reader_mode", "high_contrast"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE accessibility_preferences SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Preference updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM accessibility_preferences WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_preference(self, pk: int) -> bool:
        """Delete preference."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM accessibility_preferences WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AccessibilityError("Preference not found.")
            conn.execute("DELETE FROM accessibility_preferences WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Preference deleted: pk=%d", pk)
            return True
        except AccessibilityError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AccessibilityError(f"Failed to delete preference: {e}") from e
        finally:
            conn.close()

    def count_preferences(self, **filters) -> int:
        """Count preferences."""
        sql = "SELECT COUNT(*) as cnt FROM accessibility_preferences WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {key} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
