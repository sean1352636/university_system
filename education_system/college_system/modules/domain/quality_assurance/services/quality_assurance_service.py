"""Service for managing quality assurance."""

from datetime import datetime
from education_system.college_system.core.exceptions import QualityAssuranceError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class QualityAssuranceService:
    """Quality Assurance management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_review(self, **kwargs) -> dict:
        """Create a new review."""
        if not kwargs.get("review_type"):
            raise ValidationError("review_type is required.")
        if not kwargs.get("academic_year"):
            raise ValidationError("academic_year is required.")
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            # Iterate over a literal column tuple so user-supplied keys
            # never flow into the SQL identifier positions (py/sql-injection).
            _insert_cols: list[str] = []
            _insert_phs: list[str] = []
            _insert_vals: list = []
            for col in ('review_type', 'academic_year', 'title', 'lead_reviewer_id', 'overall_grade', 'key_findings', 'status'):
                val = kwargs.get(col)
                if val is not None:
                    _insert_cols.append(col)
                    _insert_phs.append('?')
                    _insert_vals.append(val)
            cols_sql = ', '.join(_insert_cols)
            ph_sql = ', '.join(_insert_phs)
            conn.execute(
                f"INSERT INTO quality_reviews ({cols_sql}) VALUES ({ph_sql})",
                _insert_vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM quality_reviews WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Review created: id=%d", row["id"])
            return dict(row)
        except QualityAssuranceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise QualityAssuranceError(f"Failed to create review: {e}") from e
        finally:
            conn.close()

    def get_review(self, pk: int) -> dict | None:
        """Get review by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM quality_reviews WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_reviews(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List reviews with optional filters."""
        sql = "SELECT * FROM quality_reviews WHERE 1=1"
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

    def update_review(self, pk: int, **kwargs) -> dict:
        """Update review record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("review_type", "academic_year", "title", "lead_reviewer_id", "overall_grade", "key_findings", "status"):
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
            conn.execute(f"UPDATE quality_reviews SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Review updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM quality_reviews WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_review(self, pk: int) -> bool:
        """Delete review."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM quality_reviews WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise QualityAssuranceError("Review not found.")
            conn.execute("DELETE FROM quality_reviews WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Review deleted: pk=%d", pk)
            return True
        except QualityAssuranceError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise QualityAssuranceError(f"Failed to delete review: {e}") from e
        finally:
            conn.close()

    def count_reviews(self, **filters) -> int:
        """Count reviews."""
        sql = "SELECT COUNT(*) as cnt FROM quality_reviews WHERE 1=1"
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
