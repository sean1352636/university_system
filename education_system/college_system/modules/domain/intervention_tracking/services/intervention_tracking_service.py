"""Service for managing intervention tracking."""

from datetime import datetime
from education_system.college_system.core.exceptions import InterventionError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class InterventionService:
    """Intervention Tracking management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_intervention(self, **kwargs) -> dict:
        """Create a new intervention."""
        if not kwargs.get("student_id"):
            raise ValidationError("student_id is required.")
        if not kwargs.get("staff_id"):
            raise ValidationError("staff_id is required.")
        if not kwargs.get("intervention_type"):
            raise ValidationError("intervention_type is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO academic_interventions (student_id, staff_id, intervention_type, subject_area, sessions_total, sessions_completed, pre_assessment_score, post_assessment_score, value_added, impact_notes, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('student_id'), kwargs.get('staff_id'), kwargs.get('intervention_type'), kwargs.get('subject_area'), kwargs.get('sessions_total'), kwargs.get('sessions_completed'), kwargs.get('pre_assessment_score'), kwargs.get('post_assessment_score'), kwargs.get('value_added'), kwargs.get('impact_notes'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM academic_interventions WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Intervention created: id=%d", row["id"])
            return dict(row)
        except InterventionError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise InterventionError(f"Failed to create intervention: {e}") from e
        finally:
            conn.close()

    def get_intervention(self, pk: int) -> dict | None:
        """Get intervention by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM academic_interventions WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_interventions(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List interventions with optional filters."""
        sql = "SELECT * FROM academic_interventions WHERE 1=1"
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

    def update_intervention(self, pk: int, **kwargs) -> dict:
        """Update intervention record."""
        allowed = {"student_id", "staff_id", "intervention_type", "subject_area", "sessions_total", "sessions_completed", "pre_assessment_score", "post_assessment_score", "value_added", "impact_notes", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE academic_interventions SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Intervention updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM academic_interventions WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_intervention(self, pk: int) -> bool:
        """Delete intervention."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM academic_interventions WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise InterventionError("Intervention not found.")
            conn.execute("DELETE FROM academic_interventions WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Intervention deleted: pk=%d", pk)
            return True
        except InterventionError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise InterventionError(f"Failed to delete intervention: {e}") from e
        finally:
            conn.close()

    def count_interventions(self, **filters) -> int:
        """Count interventions."""
        sql = "SELECT COUNT(*) as cnt FROM academic_interventions WHERE 1=1"
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
