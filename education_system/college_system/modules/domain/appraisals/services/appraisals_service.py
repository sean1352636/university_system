"""Service for managing staff appraisals."""

from datetime import datetime
from education_system.college_system.core.exceptions import AppraisalError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class AppraisalService:
    """Staff Appraisals management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_appraisal(self, **kwargs) -> dict:
        """Create a new appraisal."""
        if not kwargs.get("staff_id"):
            raise ValidationError("staff_id is required.")
        if not kwargs.get("academic_year"):
            raise ValidationError("academic_year is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO appraisals (staff_id, appraiser_id, academic_year, appraisal_type, overall_rating, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (kwargs.get('staff_id'), kwargs.get('appraiser_id'), kwargs.get('academic_year'), kwargs.get('appraisal_type'), kwargs.get('overall_rating'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM appraisals WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Appraisal created: id=%d", row["id"])
            return dict(row)
        except AppraisalError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AppraisalError(f"Failed to create appraisal: {e}") from e
        finally:
            conn.close()

    def get_appraisal(self, pk: int) -> dict | None:
        """Get appraisal by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM appraisals WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_appraisals(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List appraisals with optional filters."""
        sql = "SELECT * FROM appraisals WHERE 1=1"
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

    def update_appraisal(self, pk: int, **kwargs) -> dict:
        """Update appraisal record."""
        allowed = {"staff_id", "appraiser_id", "academic_year", "appraisal_type", "overall_rating", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE appraisals SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Appraisal updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM appraisals WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_appraisal(self, pk: int) -> bool:
        """Delete appraisal."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM appraisals WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AppraisalError("Appraisal not found.")
            conn.execute("DELETE FROM appraisals WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Appraisal deleted: pk=%d", pk)
            return True
        except AppraisalError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AppraisalError(f"Failed to delete appraisal: {e}") from e
        finally:
            conn.close()

    def count_appraisals(self, **filters) -> int:
        """Count appraisals."""
        sql = "SELECT COUNT(*) as cnt FROM appraisals WHERE 1=1"
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
