"""Service for managing student portfolio."""

from datetime import datetime
from education_system.college_system.core.exceptions import PortfolioError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class PortfolioService:
    """Student Portfolio management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_item(self, **kwargs) -> dict:
        """Create a new item."""
        if not kwargs.get("student_id"):
            raise ValidationError("student_id is required.")
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO portfolio_items (student_id, title, item_type, description, file_path, subject_area, is_public, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('student_id'), kwargs.get('title'), kwargs.get('item_type'), kwargs.get('description'), kwargs.get('file_path'), kwargs.get('subject_area'), kwargs.get('is_public'), kwargs.get('tags'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM portfolio_items WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Item created: id=%d", row["id"])
            return dict(row)
        except PortfolioError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PortfolioError(f"Failed to create item: {e}") from e
        finally:
            conn.close()

    def get_item(self, pk: int) -> dict | None:
        """Get item by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM portfolio_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_items(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List items with optional filters."""
        sql = "SELECT * FROM portfolio_items WHERE 1=1"
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

    def update_item(self, pk: int, **kwargs) -> dict:
        """Update item record."""
        allowed = {"student_id", "title", "item_type", "description", "file_path", "subject_area", "is_public", "tags"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE portfolio_items SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Item updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM portfolio_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_item(self, pk: int) -> bool:
        """Delete item."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM portfolio_items WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise PortfolioError("Item not found.")
            conn.execute("DELETE FROM portfolio_items WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Item deleted: pk=%d", pk)
            return True
        except PortfolioError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PortfolioError(f"Failed to delete item: {e}") from e
        finally:
            conn.close()

    def count_items(self, **filters) -> int:
        """Count items."""
        sql = "SELECT COUNT(*) as cnt FROM portfolio_items WHERE 1=1"
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
