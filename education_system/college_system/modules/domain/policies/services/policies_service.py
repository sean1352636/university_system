"""Service for managing policies."""

from datetime import datetime
from education_system.college_system.core.exceptions import PolicyError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
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
                sql += f" AND {validate_identifier(key)} = ?"
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
        allowed = {"title", "category", "version", "author_id", "content", "file_path", "review_date", "status", "approved_by"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE policies SET {set_clause} WHERE id = ?", params)
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
                sql += f" AND {validate_identifier(key)} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
