"""Service for managing peer mentoring."""

from datetime import datetime
from education_system.college_system.core.exceptions import PeerMentoringError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
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
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'mentor_id': kwargs.get('mentor_id'),
                'mentee_id': kwargs.get('mentee_id'),
                'matched_by': kwargs.get('matched_by'),
                'subject_area': kwargs.get('subject_area'),
                'start_date': kwargs.get('start_date'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO mentoring_pairs ({cols}) VALUES ({placeholders})",
                list(fields.values()),
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

    def update_pair(self, pk: int, **kwargs) -> dict:
        """Update pair record."""
        allowed = {"mentor_id", "mentee_id", "matched_by", "subject_area", "start_date", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE mentoring_pairs SET {set_clause} WHERE id = ?", params)  # nosec B608
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
                sql += f" AND {validate_identifier(key)} = ?"  # nosec B608
                params.append(val)
        conn = self._conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"]
        finally:
            conn.close()
