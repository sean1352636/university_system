"""Service for managing feedback."""

from datetime import datetime
from education_system.college_system.core.exceptions import FeedbackError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class FeedbackService:
    """Feedback management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_feedback(self, **kwargs) -> dict:
        """Create a new feedback."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO feedback_items (submitted_by, title, description, category, is_anonymous, upvote_count, admin_response, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('submitted_by'), kwargs.get('title'), kwargs.get('description'), kwargs.get('category'), kwargs.get('is_anonymous'), kwargs.get('upvote_count'), kwargs.get('admin_response'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM feedback_items WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Feedback created: id=%d", row["id"])
            return dict(row)
        except FeedbackError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FeedbackError(f"Failed to create feedback: {e}") from e
        finally:
            conn.close()

    def get_feedback(self, pk: int) -> dict | None:
        """Get feedback by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM feedback_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_feedbacks(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List feedbacks with optional filters."""
        sql = "SELECT * FROM feedback_items WHERE 1=1"
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

    def update_feedback(self, pk: int, **kwargs) -> dict:
        """Update feedback record."""
        allowed = {"submitted_by", "title", "description", "category", "is_anonymous", "upvote_count", "admin_response", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE feedback_items SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Feedback updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM feedback_items WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_feedback(self, pk: int) -> bool:
        """Delete feedback."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM feedback_items WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise FeedbackError("Feedback not found.")
            conn.execute("DELETE FROM feedback_items WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Feedback deleted: pk=%d", pk)
            return True
        except FeedbackError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FeedbackError(f"Failed to delete feedback: {e}") from e
        finally:
            conn.close()

    def count_feedbacks(self, **filters) -> int:
        """Count feedbacks."""
        sql = "SELECT COUNT(*) as cnt FROM feedback_items WHERE 1=1"
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
