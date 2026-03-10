"""Service for managing bulk operations."""

from datetime import datetime
from education_system.college_system.core.exceptions import BulkOperationError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class BulkOperationService:
    """Bulk Operations management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_job(self, **kwargs) -> dict:
        """Create a new job."""
        if not kwargs.get("job_type"):
            raise ValidationError("job_type is required.")
        if not kwargs.get("initiated_by"):
            raise ValidationError("initiated_by is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO bulk_jobs (job_type, initiated_by, file_path, total_rows, processed_rows, success_count, error_count, error_log, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('job_type'), kwargs.get('initiated_by'), kwargs.get('file_path'), kwargs.get('total_rows'), kwargs.get('processed_rows'), kwargs.get('success_count'), kwargs.get('error_count'), kwargs.get('error_log'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM bulk_jobs WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Job created: id=%d", row["id"])
            return dict(row)
        except BulkOperationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise BulkOperationError(f"Failed to create job: {e}") from e
        finally:
            conn.close()

    def get_job(self, pk: int) -> dict | None:
        """Get job by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM bulk_jobs WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_jobs(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List jobs with optional filters."""
        sql = "SELECT * FROM bulk_jobs WHERE 1=1"
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

    def update_job(self, pk: int, **kwargs) -> dict:
        """Update job record."""
        allowed = {"job_type", "initiated_by", "file_path", "total_rows", "processed_rows", "success_count", "error_count", "error_log", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE bulk_jobs SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Job updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM bulk_jobs WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_job(self, pk: int) -> bool:
        """Delete job."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM bulk_jobs WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise BulkOperationError("Job not found.")
            conn.execute("DELETE FROM bulk_jobs WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Job deleted: pk=%d", pk)
            return True
        except BulkOperationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise BulkOperationError(f"Failed to delete job: {e}") from e
        finally:
            conn.close()

    def count_jobs(self, **filters) -> int:
        """Count jobs."""
        sql = "SELECT COUNT(*) as cnt FROM bulk_jobs WHERE 1=1"
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
