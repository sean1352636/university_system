"""Service for managing markbook."""

from datetime import datetime
from education_system.college_system.core.exceptions import MarkbookError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class MarkbookService:
    """Markbook management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_column(self, **kwargs) -> dict:
        """Create a new column."""
        if not kwargs.get("course_id"):
            raise ValidationError("course_id is required.")
        if not kwargs.get("column_name"):
            raise ValidationError("column_name is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO markbook_columns (course_id, column_name, column_type, max_score, weight, due_date, display_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('course_id'), kwargs.get('column_name'), kwargs.get('column_type'), kwargs.get('max_score'), kwargs.get('weight'), kwargs.get('due_date'), kwargs.get('display_order'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM markbook_columns WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Column created: id=%d", row["id"])
            return dict(row)
        except MarkbookError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarkbookError(f"Failed to create column: {e}") from e
        finally:
            conn.close()

    def get_column(self, pk: int) -> dict | None:
        """Get column by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM markbook_columns WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_columns(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List columns with optional filters."""
        sql = "SELECT * FROM markbook_columns WHERE 1=1"
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

    def update_column(self, pk: int, **kwargs) -> dict:
        """Update column record."""
        allowed = {"course_id", "column_name", "column_type", "max_score", "weight", "due_date", "display_order"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE markbook_columns SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Column updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM markbook_columns WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_column(self, pk: int) -> bool:
        """Delete column."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM markbook_columns WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise MarkbookError("Column not found.")
            conn.execute("DELETE FROM markbook_columns WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Column deleted: pk=%d", pk)
            return True
        except MarkbookError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MarkbookError(f"Failed to delete column: {e}") from e
        finally:
            conn.close()

    def count_columns(self, **filters) -> int:
        """Count columns."""
        sql = "SELECT COUNT(*) as cnt FROM markbook_columns WHERE 1=1"
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
