"""Service for managing multi-language."""

from datetime import datetime
from education_system.college_system.core.exceptions import MultiLanguageError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class MultiLanguageService:
    """Multi-Language management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_override(self, **kwargs) -> dict:
        """Create a new override."""
        if not kwargs.get("locale"):
            raise ValidationError("locale is required.")
        if not kwargs.get("key"):
            raise ValidationError("key is required.")
        if not kwargs.get("value"):
            raise ValidationError("value is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO translation_overrides (locale, key, value)
                   VALUES (?, ?, ?)""",
                (kwargs.get('locale'), kwargs.get('key'), kwargs.get('value'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM translation_overrides WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Override created: id=%d", row["id"])
            return dict(row)
        except MultiLanguageError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MultiLanguageError(f"Failed to create override: {e}") from e
        finally:
            conn.close()

    def get_override(self, pk: int) -> dict | None:
        """Get override by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM translation_overrides WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_overrides(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List overrides with optional filters."""
        sql = "SELECT * FROM translation_overrides WHERE 1=1"
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

    def update_override(self, pk: int, **kwargs) -> dict:
        """Update override record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("locale", "key", "value"):
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
            conn.execute(f"UPDATE translation_overrides SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Override updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM translation_overrides WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_override(self, pk: int) -> bool:
        """Delete override."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM translation_overrides WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise MultiLanguageError("Override not found.")
            conn.execute("DELETE FROM translation_overrides WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Override deleted: pk=%d", pk)
            return True
        except MultiLanguageError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MultiLanguageError(f"Failed to delete override: {e}") from e
        finally:
            conn.close()

    def count_overrides(self, **filters) -> int:
        """Count overrides."""
        sql = "SELECT COUNT(*) as cnt FROM translation_overrides WHERE 1=1"
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
