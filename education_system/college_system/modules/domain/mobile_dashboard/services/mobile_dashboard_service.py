"""Service for managing mobile dashboard."""

from datetime import datetime
from education_system.college_system.core.exceptions import MobileDashboardError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class MobileDashboardService:
    """Mobile Dashboard management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_widget(self, **kwargs) -> dict:
        """Create a new widget."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        if not kwargs.get("widget_type"):
            raise ValidationError("widget_type is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO mobile_widget_config (user_id, widget_type, display_order, is_visible, config)
                   VALUES (?, ?, ?, ?, ?)""",
                (kwargs.get('user_id'), kwargs.get('widget_type'), kwargs.get('display_order'), kwargs.get('is_visible'), kwargs.get('config'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM mobile_widget_config WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Widget created: id=%d", row["id"])
            return dict(row)
        except MobileDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MobileDashboardError(f"Failed to create widget: {e}") from e
        finally:
            conn.close()

    def get_widget(self, pk: int) -> dict | None:
        """Get widget by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM mobile_widget_config WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_widgets(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List widgets with optional filters."""
        sql = "SELECT * FROM mobile_widget_config WHERE 1=1"
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

    def update_widget(self, pk: int, **kwargs) -> dict:
        """Update widget record."""
        allowed = {"user_id", "widget_type", "display_order", "is_visible", "config"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE mobile_widget_config SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Widget updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM mobile_widget_config WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_widget(self, pk: int) -> bool:
        """Delete widget."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM mobile_widget_config WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise MobileDashboardError("Widget not found.")
            conn.execute("DELETE FROM mobile_widget_config WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Widget deleted: pk=%d", pk)
            return True
        except MobileDashboardError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MobileDashboardError(f"Failed to delete widget: {e}") from e
        finally:
            conn.close()

    def count_widgets(self, **filters) -> int:
        """Count widgets."""
        sql = "SELECT COUNT(*) as cnt FROM mobile_widget_config WHERE 1=1"
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
