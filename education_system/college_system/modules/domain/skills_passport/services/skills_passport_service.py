"""Service for managing skills passport."""

from datetime import datetime
from education_system.college_system.core.exceptions import SkillsPassportError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class SkillsPassportService:
    """Skills Passport management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_category(self, **kwargs) -> dict:
        """Create a new category."""
        if not kwargs.get("name"):
            raise ValidationError("name is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'name': kwargs.get('name'),
                'description': kwargs.get('description'),
                'display_order': kwargs.get('display_order'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO skill_categories ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM skill_categories WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Category created: id=%d", row["id"])
            return dict(row)
        except SkillsPassportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SkillsPassportError(f"Failed to create category: {e}") from e
        finally:
            conn.close()

    def get_category(self, pk: int) -> dict | None:
        """Get category by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM skill_categories WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_categories(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List categories with optional filters."""
        sql = "SELECT * FROM skill_categories WHERE 1=1"
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

    def update_category(self, pk: int, **kwargs) -> dict:
        """Update category record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("name", "description", "display_order"):
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
            conn.execute(f"UPDATE skill_categories SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Category updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM skill_categories WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_category(self, pk: int) -> bool:
        """Delete category."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM skill_categories WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise SkillsPassportError("Category not found.")
            conn.execute("DELETE FROM skill_categories WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Category deleted: pk=%d", pk)
            return True
        except SkillsPassportError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SkillsPassportError(f"Failed to delete category: {e}") from e
        finally:
            conn.close()

    def count_categories(self, **filters) -> int:
        """Count categories."""
        sql = "SELECT COUNT(*) as cnt FROM skill_categories WHERE 1=1"
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
