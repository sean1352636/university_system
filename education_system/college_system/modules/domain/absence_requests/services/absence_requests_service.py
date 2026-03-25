"""Service for managing absence requests."""

from datetime import datetime
from education_system.college_system.core.exceptions import AbsenceRequestError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class AbsenceRequestService:
    """Absence Requests management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_request(self, **kwargs) -> dict:
        """Create a new request."""
        if not kwargs.get("staff_id"):
            raise ValidationError("staff_id is required.")
        if not kwargs.get("absence_type"):
            raise ValidationError("absence_type is required.")
        if not kwargs.get("start_date"):
            raise ValidationError("start_date is required.")
        if not kwargs.get("end_date"):
            raise ValidationError("end_date is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'staff_id': kwargs.get('staff_id'),
                'absence_type': kwargs.get('absence_type'),
                'start_date': kwargs.get('start_date'),
                'end_date': kwargs.get('end_date'),
                'reason': kwargs.get('reason'),
                'status': kwargs.get('status'),
                'approved_by': kwargs.get('approved_by'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO absence_requests ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM absence_requests WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Request created: id=%d", row["id"])
            return dict(row)
        except AbsenceRequestError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AbsenceRequestError(f"Failed to create request: {e}") from e
        finally:
            conn.close()

    def get_request(self, pk: int) -> dict | None:
        """Get request by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_requests(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List requests with optional filters."""
        sql = "SELECT * FROM absence_requests WHERE 1=1"
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

    def update_request(self, pk: int, **kwargs) -> dict:
        """Update request record."""
        allowed = {"staff_id", "absence_type", "start_date", "end_date", "reason", "status", "approved_by"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE absence_requests SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Request updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_request(self, pk: int) -> bool:
        """Delete request."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM absence_requests WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AbsenceRequestError("Request not found.")
            conn.execute("DELETE FROM absence_requests WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Request deleted: pk=%d", pk)
            return True
        except AbsenceRequestError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AbsenceRequestError(f"Failed to delete request: {e}") from e
        finally:
            conn.close()

    def count_requests(self, **filters) -> int:
        """Count requests."""
        sql = "SELECT COUNT(*) as cnt FROM absence_requests WHERE 1=1"
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
