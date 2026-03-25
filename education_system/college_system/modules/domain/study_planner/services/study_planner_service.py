"""Service for managing study planner."""

from datetime import datetime
from education_system.college_system.core.exceptions import StudyPlannerError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class StudyPlannerService:
    """Study Planner management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_session(self, **kwargs) -> dict:
        """Create a new session."""
        if not kwargs.get("student_id"):
            raise ValidationError("student_id is required.")
        if not kwargs.get("subject"):
            raise ValidationError("subject is required.")
        if not kwargs.get("planned_date"):
            raise ValidationError("planned_date is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'student_id': kwargs.get('student_id'),
                'subject': kwargs.get('subject'),
                'topic': kwargs.get('topic'),
                'planned_date': kwargs.get('planned_date'),
                'planned_duration': kwargs.get('planned_duration'),
                'actual_duration': kwargs.get('actual_duration'),
                'session_type': kwargs.get('session_type'),
                'completed': kwargs.get('completed'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO study_sessions ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM study_sessions WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Session created: id=%d", row["id"])
            return dict(row)
        except StudyPlannerError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyPlannerError(f"Failed to create session: {e}") from e
        finally:
            conn.close()

    def get_session(self, pk: int) -> dict | None:
        """Get session by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM study_sessions WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_sessions(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List sessions with optional filters."""
        sql = "SELECT * FROM study_sessions WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"
                params.append(val)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        conn = self._conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_session(self, pk: int, **kwargs) -> dict:
        """Update session record."""
        allowed = {"student_id", "subject", "topic", "planned_date", "planned_duration", "actual_duration", "session_type", "completed"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE study_sessions SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Session updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM study_sessions WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_session(self, pk: int) -> bool:
        """Delete session."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM study_sessions WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise StudyPlannerError("Session not found.")
            conn.execute("DELETE FROM study_sessions WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Session deleted: pk=%d", pk)
            return True
        except StudyPlannerError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise StudyPlannerError(f"Failed to delete session: {e}") from e
        finally:
            conn.close()

    def count_sessions(self, **filters) -> int:
        """Count sessions."""
        sql = "SELECT COUNT(*) as cnt FROM study_sessions WHERE 1=1"
        params: list = []
        for key, val in filters.items():
            if val is not None:
                sql += f" AND {validate_identifier(key)} = ?"
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
