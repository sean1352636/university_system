"""Service for managing activity feed."""

from datetime import datetime
from education_system.college_system.core.exceptions import ActivityFeedError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class ActivityFeedService:
    """Activity Feed management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_feed_item(self, **kwargs) -> dict:
        """Create a new feed_item."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        if not kwargs.get("activity_type"):
            raise ValidationError("activity_type is required.")
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO activity_feed_items (user_id, activity_type, title, description, entity_type, entity_id, target_role, target_user_id, is_read, dismissed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('user_id'), kwargs.get('activity_type'), kwargs.get('title'), kwargs.get('description'), kwargs.get('entity_type'), kwargs.get('entity_id'), kwargs.get('target_role'), kwargs.get('target_user_id'), kwargs.get('is_read'), kwargs.get('dismissed'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM activity_feed_items WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Feed_Item created: id=%d", row["id"])
            return dict(row)
        except ActivityFeedError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ActivityFeedError(f"Failed to create feed_item: {e}") from e
        finally:
            conn.close()

    def get_feed_item(self, pk: int) -> dict | None:
        """Get feed_item by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM activity_feed_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_feed_items(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List feed_items with optional filters."""
        sql = "SELECT * FROM activity_feed_items WHERE 1=1"
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

    def update_feed_item(self, pk: int, **kwargs) -> dict:
        """Update feed_item record."""
        allowed = {"user_id", "activity_type", "title", "description", "entity_type", "entity_id", "target_role", "target_user_id", "is_read", "dismissed"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE activity_feed_items SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Feed_Item updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM activity_feed_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_feed_item(self, pk: int) -> bool:
        """Delete feed_item."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM activity_feed_items WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise ActivityFeedError("Feed_Item not found.")
            conn.execute("DELETE FROM activity_feed_items WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Feed_Item deleted: pk=%d", pk)
            return True
        except ActivityFeedError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ActivityFeedError(f"Failed to delete feed_item: {e}") from e
        finally:
            conn.close()

    def count_feed_items(self, **filters) -> int:
        """Count feed_items."""
        sql = "SELECT COUNT(*) as cnt FROM activity_feed_items WHERE 1=1"
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
