"""Service for managing quality assurance."""

from datetime import datetime
from education_system.college_system.core.exceptions import QualityAssuranceError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
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
            conn.execute(
                """INSERT INTO quality_reviews (review_type, academic_year, title, lead_reviewer_id, overall_grade, key_findings, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('review_type'), kwargs.get('academic_year'), kwargs.get('title'), kwargs.get('lead_reviewer_id'), kwargs.get('overall_grade'), kwargs.get('key_findings'), kwargs.get('status'),),
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

    def update_review(self, pk: int, **kwargs) -> dict:
        """Update review record."""
        allowed = {"review_type", "academic_year", "title", "lead_reviewer_id", "overall_grade", "key_findings", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE quality_reviews SET {set_clause} WHERE id = ?", params)
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
                sql += f" AND {key} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
