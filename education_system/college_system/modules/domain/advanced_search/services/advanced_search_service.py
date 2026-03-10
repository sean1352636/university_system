"""Service for managing advanced search."""

from datetime import datetime
from education_system.college_system.core.exceptions import AdvancedSearchError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class AdvancedSearchService:
    """Advanced Search management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_search(self, **kwargs) -> dict:
        """Create a new search."""
        if not kwargs.get("user_id"):
            raise ValidationError("user_id is required.")
        if not kwargs.get("query"):
            raise ValidationError("query is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO search_history (user_id, query, module_filter, result_count, searched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (kwargs.get('user_id'), kwargs.get('query'), kwargs.get('module_filter'), kwargs.get('result_count'), kwargs.get('searched_at'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM search_history WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Search created: id=%d", row["id"])
            return dict(row)
        except AdvancedSearchError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AdvancedSearchError(f"Failed to create search: {e}") from e
        finally:
            conn.close()

    def get_search(self, pk: int) -> dict | None:
        """Get search by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM search_history WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_searches(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List searches with optional filters."""
        sql = "SELECT * FROM search_history WHERE 1=1"
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

    def update_search(self, pk: int, **kwargs) -> dict:
        """Update search record."""
        allowed = {"user_id", "query", "module_filter", "result_count", "searched_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE search_history SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Search updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM search_history WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_search(self, pk: int) -> bool:
        """Delete search."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM search_history WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AdvancedSearchError("Search not found.")
            conn.execute("DELETE FROM search_history WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Search deleted: pk=%d", pk)
            return True
        except AdvancedSearchError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AdvancedSearchError(f"Failed to delete search: {e}") from e
        finally:
            conn.close()

    def count_searches(self, **filters) -> int:
        """Count searches."""
        sql = "SELECT COUNT(*) as cnt FROM search_history WHERE 1=1"
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
