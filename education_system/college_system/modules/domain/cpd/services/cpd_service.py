"""Service for managing cpd records."""

from datetime import datetime
from education_system.college_system.core.exceptions import CPDError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class CPDService:
    """CPD Records management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, **kwargs) -> dict:
        """Create a new record."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        if not kwargs.get("cpd_type"):
            raise ValidationError("cpd_type is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'staff_id': kwargs.get('staff_id'),
                'title': kwargs.get('title'),
                'provider': kwargs.get('provider'),
                'cpd_type': kwargs.get('cpd_type'),
                'hours': kwargs.get('hours'),
                'certification': kwargs.get('certification'),
                'expiry_date': kwargs.get('expiry_date'),
                'evidence': kwargs.get('evidence'),
                'reflection': kwargs.get('reflection'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO cpd_records ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cpd_records WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Record created: id=%d", row["id"])
            return dict(row)
        except CPDError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CPDError(f"Failed to create record: {e}") from e
        finally:
            conn.close()

    def get_record(self, pk: int) -> dict | None:
        """Get record by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM cpd_records WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_records(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List records with optional filters."""
        sql = "SELECT * FROM cpd_records WHERE 1=1"
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

    def update_record(self, pk: int, **kwargs) -> dict:
        """Update record record."""
        allowed = {"staff_id", "title", "provider", "cpd_type", "hours", "certification", "expiry_date", "evidence", "reflection", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE cpd_records SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Record updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM cpd_records WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_record(self, pk: int) -> bool:
        """Delete record."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM cpd_records WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise CPDError("Record not found.")
            conn.execute("DELETE FROM cpd_records WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Record deleted: pk=%d", pk)
            return True
        except CPDError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CPDError(f"Failed to delete record: {e}") from e
        finally:
            conn.close()

    def count_records(self, **filters) -> int:
        """Count records."""
        sql = "SELECT COUNT(*) as cnt FROM cpd_records WHERE 1=1"
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
