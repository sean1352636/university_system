"""Service for managing policies."""

from datetime import datetime
from education_system.college_system.core.exceptions import PolicyError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class PolicyService:
    """Policies management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_policy(self, **kwargs) -> dict:
        """Create a new policy."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        if not kwargs.get("category"):
            raise ValidationError("category is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'title': kwargs.get('title'),
                'category': kwargs.get('category'),
                'version': kwargs.get('version'),
                'author_id': kwargs.get('author_id'),
                'content': kwargs.get('content'),
                'file_path': kwargs.get('file_path'),
                'review_date': kwargs.get('review_date'),
                'status': kwargs.get('status'),
                'approved_by': kwargs.get('approved_by'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO policies ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM policies WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Policy created: id=%d", row["id"])
            return dict(row)
        except PolicyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PolicyError(f"Failed to create policy: {e}") from e
        finally:
            conn.close()

    def get_policy(self, pk: int) -> dict | None:
        """Get policy by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM policies WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_policies(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List policies with optional filters."""
        sql = "SELECT * FROM policies WHERE 1=1"
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

    def update_policy(self, pk: int, **kwargs) -> dict:
        """Update policy record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("title", "category", "version", "author_id", "content", "file_path", "review_date", "status", "approved_by"):
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
            conn.execute(f"UPDATE policies SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Policy updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM policies WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_policy(self, pk: int) -> bool:
        """Delete policy."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM policies WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise PolicyError("Policy not found.")
            conn.execute("DELETE FROM policies WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Policy deleted: pk=%d", pk)
            return True
        except PolicyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PolicyError(f"Failed to delete policy: {e}") from e
        finally:
            conn.close()

    def count_policies(self, **filters) -> int:
        """Count policies."""
        sql = "SELECT COUNT(*) as cnt FROM policies WHERE 1=1"
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
