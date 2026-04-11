"""Service for managing student portfolio."""

from datetime import datetime
from education_system.college_system.core.exceptions import PortfolioError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
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
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'student_id': kwargs.get('student_id'),
                'title': kwargs.get('title'),
                'item_type': kwargs.get('item_type'),
                'description': kwargs.get('description'),
                'file_path': kwargs.get('file_path'),
                'subject_area': kwargs.get('subject_area'),
                'is_public': kwargs.get('is_public'),
                'tags': kwargs.get('tags'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO portfolio_items ({cols}) VALUES ({placeholders})",
                list(fields.values()),
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

    def update_item(self, pk: int, **kwargs) -> dict:
        """Update item record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("student_id", "title", "item_type", "description", "file_path", "subject_area", "is_public", "tags"):
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
            conn.execute(f"UPDATE portfolio_items SET {set_clause} WHERE id = ?", params)  # nosec B608
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
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
