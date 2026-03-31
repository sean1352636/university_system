"""Service for managing visitor management."""

from datetime import datetime
from education_system.college_system.core.exceptions import VisitorError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class VisitorService:
    """Visitor Management management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_visitor(self, **kwargs) -> dict:
        """Create a new visitor."""
        if not kwargs.get("first_name"):
            raise ValidationError("first_name is required.")
        if not kwargs.get("last_name"):
            raise ValidationError("last_name is required.")
        if not kwargs.get("purpose"):
            raise ValidationError("purpose is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'first_name': kwargs.get('first_name'),
                'last_name': kwargs.get('last_name'),
                'organization': kwargs.get('organization'),
                'purpose': kwargs.get('purpose'),
                'visiting_staff_id': kwargs.get('visiting_staff_id'),
                'dbs_checked': kwargs.get('dbs_checked'),
                'safeguarding_briefed': kwargs.get('safeguarding_briefed'),
                'badge_number': kwargs.get('badge_number'),
                'sign_in_time': kwargs.get('sign_in_time'),
                'sign_out_time': kwargs.get('sign_out_time'),
                'vehicle_reg': kwargs.get('vehicle_reg'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO visitors ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM visitors WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Visitor created: id=%d", row["id"])
            return dict(row)
        except VisitorError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise VisitorError(f"Failed to create visitor: {e}") from e
        finally:
            conn.close()

    def get_visitor(self, pk: int) -> dict | None:
        """Get visitor by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM visitors WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_visitors(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List visitors with optional filters."""
        sql = "SELECT * FROM visitors WHERE 1=1"
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

    def update_visitor(self, pk: int, **kwargs) -> dict:
        """Update visitor record."""
        allowed = {"first_name", "last_name", "organization", "purpose", "visiting_staff_id", "dbs_checked", "safeguarding_briefed", "badge_number", "sign_in_time", "sign_out_time", "vehicle_reg", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE visitors SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Visitor updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM visitors WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_visitor(self, pk: int) -> bool:
        """Delete visitor."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM visitors WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise VisitorError("Visitor not found.")
            conn.execute("DELETE FROM visitors WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Visitor deleted: pk=%d", pk)
            return True
        except VisitorError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise VisitorError(f"Failed to delete visitor: {e}") from e
        finally:
            conn.close()

    def count_visitors(self, **filters) -> int:
        """Count visitors."""
        sql = "SELECT COUNT(*) as cnt FROM visitors WHERE 1=1"
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
