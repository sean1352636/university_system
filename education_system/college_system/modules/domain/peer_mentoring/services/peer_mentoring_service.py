"""Service for managing peer mentoring."""

from datetime import datetime
from education_system.college_system.core.exceptions import PeerMentoringError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class PeerMentoringService:
    """Peer Mentoring management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_pair(self, **kwargs) -> dict:
        """Create a new pair."""
        if not kwargs.get("mentor_id"):
            raise ValidationError("mentor_id is required.")
        if not kwargs.get("mentee_id"):
            raise ValidationError("mentee_id is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO mentoring_pairs (mentor_id, mentee_id, matched_by, subject_area, start_date, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (kwargs.get('mentor_id'), kwargs.get('mentee_id'), kwargs.get('matched_by'), kwargs.get('subject_area'), kwargs.get('start_date'), kwargs.get('status'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM mentoring_pairs WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Pair created: id=%d", row["id"])
            return dict(row)
        except PeerMentoringError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PeerMentoringError(f"Failed to create pair: {e}") from e
        finally:
            conn.close()

    def get_pair(self, pk: int) -> dict | None:
        """Get pair by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM mentoring_pairs WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_pairs(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List pairs with optional filters."""
        sql = "SELECT * FROM mentoring_pairs WHERE 1=1"
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

    def update_pair(self, pk: int, **kwargs) -> dict:
        """Update pair record."""
        allowed = {"mentor_id", "mentee_id", "matched_by", "subject_area", "start_date", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE mentoring_pairs SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Pair updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM mentoring_pairs WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_pair(self, pk: int) -> bool:
        """Delete pair."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM mentoring_pairs WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise PeerMentoringError("Pair not found.")
            conn.execute("DELETE FROM mentoring_pairs WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Pair deleted: pk=%d", pk)
            return True
        except PeerMentoringError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise PeerMentoringError(f"Failed to delete pair: {e}") from e
        finally:
            conn.close()

    def count_pairs(self, **filters) -> int:
        """Count pairs."""
        sql = "SELECT COUNT(*) as cnt FROM mentoring_pairs WHERE 1=1"
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
