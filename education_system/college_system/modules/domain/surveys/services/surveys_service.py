"""Service for managing surveys."""

from datetime import datetime
from education_system.college_system.core.exceptions import SurveyError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class SurveyService:
    """Surveys management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_survey(self, **kwargs) -> dict:
        """Create a new survey."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        if not kwargs.get("created_by"):
            raise ValidationError("created_by is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'title': kwargs.get('title'),
                'created_by': kwargs.get('created_by'),
                'survey_type': kwargs.get('survey_type'),
                'is_anonymous': kwargs.get('is_anonymous'),
                'target_role': kwargs.get('target_role'),
                'open_date': kwargs.get('open_date'),
                'close_date': kwargs.get('close_date'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO surveys ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM surveys WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Survey created: id=%d", row["id"])
            return dict(row)
        except SurveyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SurveyError(f"Failed to create survey: {e}") from e
        finally:
            conn.close()

    def get_survey(self, pk: int) -> dict | None:
        """Get survey by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM surveys WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_surveys(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List surveys with optional filters."""
        sql = "SELECT * FROM surveys WHERE 1=1"
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

    def update_survey(self, pk: int, **kwargs) -> dict:
        """Update survey record."""
        allowed = {"title", "created_by", "survey_type", "is_anonymous", "target_role", "open_date", "close_date", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE surveys SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Survey updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM surveys WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_survey(self, pk: int) -> bool:
        """Delete survey."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM surveys WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise SurveyError("Survey not found.")
            conn.execute("DELETE FROM surveys WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Survey deleted: pk=%d", pk)
            return True
        except SurveyError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise SurveyError(f"Failed to delete survey: {e}") from e
        finally:
            conn.close()

    def count_surveys(self, **filters) -> int:
        """Count surveys."""
        sql = "SELECT COUNT(*) as cnt FROM surveys WHERE 1=1"
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
