"""Service for managing teaching observations."""

from datetime import datetime
from education_system.college_system.core.exceptions import ObservationError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class ObservationService:
    """Teaching Observations management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_observation(self, **kwargs) -> dict:
        """Create a new observation."""
        if not kwargs.get("teacher_id"):
            raise ValidationError("teacher_id is required.")
        if not kwargs.get("observation_type"):
            raise ValidationError("observation_type is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO teaching_observations (teacher_id, observer_id, scheduled_date, course_id, observation_type, grade, strengths, areas_for_development, action_points, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('teacher_id'), kwargs.get('observer_id'), kwargs.get('scheduled_date'), kwargs.get('course_id'), kwargs.get('observation_type'), kwargs.get('grade'), kwargs.get('strengths'), kwargs.get('areas_for_development'), kwargs.get('action_points'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM teaching_observations WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Observation created: id=%d", row["id"])
            return dict(row)
        except ObservationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ObservationError(f"Failed to create observation: {e}") from e
        finally:
            conn.close()

    def get_observation(self, pk: int) -> dict | None:
        """Get observation by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM teaching_observations WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_observations(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List observations with optional filters."""
        sql = "SELECT * FROM teaching_observations WHERE 1=1"
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

    def update_observation(self, pk: int, **kwargs) -> dict:
        """Update observation record."""
        allowed = {"teacher_id", "observer_id", "scheduled_date", "course_id", "observation_type", "grade", "strengths", "areas_for_development", "action_points", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE teaching_observations SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Observation updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM teaching_observations WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_observation(self, pk: int) -> bool:
        """Delete observation."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM teaching_observations WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise ObservationError("Observation not found.")
            conn.execute("DELETE FROM teaching_observations WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Observation deleted: pk=%d", pk)
            return True
        except ObservationError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ObservationError(f"Failed to delete observation: {e}") from e
        finally:
            conn.close()

    def count_observations(self, **filters) -> int:
        """Count observations."""
        sql = "SELECT COUNT(*) as cnt FROM teaching_observations WHERE 1=1"
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
