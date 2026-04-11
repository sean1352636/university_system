"""Service for managing academic year."""

from datetime import datetime
from education_system.college_system.core.exceptions import AcademicYearError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class AcademicYearService:
    """Academic Year management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_year(self, **kwargs) -> dict:
        """Create a new year."""
        if not kwargs.get("name"):
            raise ValidationError("name is required.")
        if not kwargs.get("start_date"):
            raise ValidationError("start_date is required.")
        if not kwargs.get("end_date"):
            raise ValidationError("end_date is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'name': kwargs.get('name'),
                'start_date': kwargs.get('start_date'),
                'end_date': kwargs.get('end_date'),
                'is_current': kwargs.get('is_current'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO academic_years ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM academic_years WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Year created: id=%d", row["id"])
            return dict(row)
        except AcademicYearError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AcademicYearError(f"Failed to create year: {e}") from e
        finally:
            conn.close()

    def get_year(self, pk: int) -> dict | None:
        """Get year by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM academic_years WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_years(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List years with optional filters."""
        sql = "SELECT * FROM academic_years WHERE 1=1"
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

    def update_year(self, pk: int, **kwargs) -> dict:
        """Update year record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("name", "start_date", "end_date", "is_current", "status"):
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
            conn.execute(f"UPDATE academic_years SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Year updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM academic_years WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_year(self, pk: int) -> bool:
        """Delete year."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM academic_years WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AcademicYearError("Year not found.")
            conn.execute("DELETE FROM academic_years WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Year deleted: pk=%d", pk)
            return True
        except AcademicYearError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AcademicYearError(f"Failed to delete year: {e}") from e
        finally:
            conn.close()

    def count_years(self, **filters) -> int:
        """Count years."""
        sql = "SELECT COUNT(*) as cnt FROM academic_years WHERE 1=1"
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
