"""Service for managing bulk operations."""

from datetime import datetime
from education_system.college_system.core.exceptions import BulkOperationError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
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
            # Build INSERT with only non-None values so DB defaults apply
            # Iterate over a literal column tuple so user-supplied keys
            # never flow into the SQL identifier positions (py/sql-injection).
            _insert_cols: list[str] = []
            _insert_phs: list[str] = []
            _insert_vals: list = []
            for col in ('job_type', 'initiated_by', 'file_path', 'total_rows', 'processed_rows', 'success_count', 'error_count', 'error_log', 'status'):
                val = kwargs.get(col)
                if val is not None:
                    _insert_cols.append(col)
                    _insert_phs.append('?')
                    _insert_vals.append(val)
            cols_sql = ', '.join(_insert_cols)
            ph_sql = ', '.join(_insert_phs)
            conn.execute(
                f"INSERT INTO bulk_jobs ({cols_sql}) VALUES ({ph_sql})",
                _insert_vals,
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

    def update_job(self, pk: int, **kwargs) -> dict:
        """Update job record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("job_type", "initiated_by", "file_path", "total_rows", "processed_rows", "success_count", "error_count", "error_log", "status"):
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
            conn.execute(f"UPDATE bulk_jobs SET {set_clause} WHERE id = ?", params)  # nosec B608
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
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
