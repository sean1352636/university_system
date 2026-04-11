"""Service for managing lesson plans."""

from datetime import datetime
from education_system.college_system.core.exceptions import LessonPlanError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class LessonPlanService:
    """Lesson Plans management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_plan(self, **kwargs) -> dict:
        """Create a new plan."""
        if not kwargs.get("course_id"):
            raise ValidationError("course_id is required.")
        if not kwargs.get("teacher_id"):
            raise ValidationError("teacher_id is required.")
        if not kwargs.get("lesson_date"):
            raise ValidationError("lesson_date is required.")
        if not kwargs.get("topic"):
            raise ValidationError("topic is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'course_id': kwargs.get('course_id'),
                'teacher_id': kwargs.get('teacher_id'),
                'lesson_date': kwargs.get('lesson_date'),
                'topic': kwargs.get('topic'),
                'learning_objectives': kwargs.get('learning_objectives'),
                'starter_activity': kwargs.get('starter_activity'),
                'main_activity': kwargs.get('main_activity'),
                'plenary': kwargs.get('plenary'),
                'differentiation': kwargs.get('differentiation'),
                'resources': kwargs.get('resources'),
                'homework': kwargs.get('homework'),
                'reflection': kwargs.get('reflection'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO lesson_plans ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM lesson_plans WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Plan created: id=%d", row["id"])
            return dict(row)
        except LessonPlanError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LessonPlanError(f"Failed to create plan: {e}") from e
        finally:
            conn.close()

    def get_plan(self, pk: int) -> dict | None:
        """Get plan by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM lesson_plans WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_plans(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List plans with optional filters."""
        sql = "SELECT * FROM lesson_plans WHERE 1=1"
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

    def update_plan(self, pk: int, **kwargs) -> dict:
        """Update plan record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("course_id", "teacher_id", "lesson_date", "topic", "learning_objectives", "starter_activity", "main_activity", "plenary", "differentiation", "resources", "homework", "reflection", "status"):
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
            conn.execute(f"UPDATE lesson_plans SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Plan updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM lesson_plans WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_plan(self, pk: int) -> bool:
        """Delete plan."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM lesson_plans WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise LessonPlanError("Plan not found.")
            conn.execute("DELETE FROM lesson_plans WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Plan deleted: pk=%d", pk)
            return True
        except LessonPlanError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise LessonPlanError(f"Failed to delete plan: {e}") from e
        finally:
            conn.close()

    def count_plans(self, **filters) -> int:
        """Count plans."""
        sql = "SELECT COUNT(*) as cnt FROM lesson_plans WHERE 1=1"
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
