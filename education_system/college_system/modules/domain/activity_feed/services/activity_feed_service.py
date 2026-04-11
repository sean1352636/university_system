"""Service for managing activity feed."""

from datetime import datetime
from education_system.college_system.core.exceptions import ActivityFeedError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
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
            # Build INSERT with only non-None values so DB defaults apply
            # Iterate over a literal column tuple so user-supplied keys
            # never flow into the SQL identifier positions (py/sql-injection).
            _insert_cols: list[str] = []
            _insert_phs: list[str] = []
            _insert_vals: list = []
            for col in ('user_id', 'activity_type', 'title', 'description', 'entity_type', 'entity_id', 'target_role', 'target_user_id', 'is_read', 'dismissed'):
                val = kwargs.get(col)
                if val is not None:
                    _insert_cols.append(col)
                    _insert_phs.append('?')
                    _insert_vals.append(val)
            cols_sql = ', '.join(_insert_cols)
            ph_sql = ', '.join(_insert_phs)
            conn.execute(
                f"INSERT INTO activity_feed_items ({cols_sql}) VALUES ({ph_sql})",
                _insert_vals,
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
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
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
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("user_id", "activity_type", "title", "description", "entity_type", "entity_id", "target_role", "target_user_id", "is_read", "dismissed"):
            val = kwargs.get(col)
            if val is not None:
                set_parts.append(f"{validate_identifier(col)} = ?")
                params.append(val)
        if not set_parts:
            raise ValidationError("No valid fields to update.")
        set_parts.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(pk)
        set_clause = ", ".join(set_parts)
        conn = self._conn()
        try:
            conn.execute(f"UPDATE activity_feed_items SET {set_clause} WHERE id = ?", params)  # nosec B608
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
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
