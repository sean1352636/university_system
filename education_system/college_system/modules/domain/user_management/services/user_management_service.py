"""Service for managing user management."""

from datetime import datetime
from education_system.college_system.core.exceptions import UserManagementError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class UserManagementService:
    """User Management management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_template(self, **kwargs) -> dict:
        """Create a new template."""
        if not kwargs.get("template_name"):
            raise ValidationError("template_name is required.")
        if not kwargs.get("role"):
            raise ValidationError("role is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO permission_templates (template_name, role, permissions, description)
                   VALUES (?, ?, ?, ?)""",
                (kwargs.get('template_name'), kwargs.get('role'), kwargs.get('permissions'), kwargs.get('description'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM permission_templates WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Template created: id=%d", row["id"])
            return dict(row)
        except UserManagementError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise UserManagementError(f"Failed to create template: {e}") from e
        finally:
            conn.close()

    def get_template(self, pk: int) -> dict | None:
        """Get template by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM permission_templates WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_templates(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List templates with optional filters."""
        sql = "SELECT * FROM permission_templates WHERE 1=1"
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

    def update_template(self, pk: int, **kwargs) -> dict:
        """Update template record."""
        allowed = {"template_name", "role", "permissions", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE permission_templates SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Template updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM permission_templates WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_template(self, pk: int) -> bool:
        """Delete template."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM permission_templates WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise UserManagementError("Template not found.")
            conn.execute("DELETE FROM permission_templates WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Template deleted: pk=%d", pk)
            return True
        except UserManagementError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise UserManagementError(f"Failed to delete template: {e}") from e
        finally:
            conn.close()

    def count_templates(self, **filters) -> int:
        """Count templates."""
        sql = "SELECT COUNT(*) as cnt FROM permission_templates WHERE 1=1"
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
