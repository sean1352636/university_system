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
            # Iterate over a literal column tuple so user-supplied keys
            # never flow into the SQL identifier positions (py/sql-injection).
            _insert_cols: list[str] = []
            _insert_phs: list[str] = []
            _insert_vals: list = []
            for col in ('staff_id', 'title', 'provider', 'cpd_type', 'hours', 'certification', 'expiry_date', 'evidence', 'reflection', 'status'):
                val = kwargs.get(col)
                if val is not None:
                    _insert_cols.append(col)
                    _insert_phs.append('?')
                    _insert_vals.append(val)
            cols_sql = ', '.join(_insert_cols)
            ph_sql = ', '.join(_insert_phs)
            conn.execute(
                f"INSERT INTO cpd_records ({cols_sql}) VALUES ({ph_sql})",
                _insert_vals,
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
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("staff_id", "title", "provider", "cpd_type", "hours", "certification", "expiry_date", "evidence", "reflection", "status"):
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
