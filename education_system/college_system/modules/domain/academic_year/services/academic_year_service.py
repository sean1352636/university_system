"""Service for managing academic year."""

from datetime import datetime
from education_system.college_system.core.exceptions import AcademicYearError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
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
            conn.execute(
                """INSERT INTO academic_years (name, start_date, end_date, is_current, status)
                   VALUES (?, ?, ?, ?, ?)""",
                (kwargs.get('name'), kwargs.get('start_date'), kwargs.get('end_date'), kwargs.get('is_current'), kwargs.get('status'),),
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

    def update_year(self, pk: int, **kwargs) -> dict:
        """Update year record."""
        allowed = {"name", "start_date", "end_date", "is_current", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE academic_years SET {set_clause} WHERE id = ?", params)
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
                sql += f" AND {key} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
