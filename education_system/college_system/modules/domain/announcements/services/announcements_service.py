"""Service for managing announcements."""

from datetime import datetime
from education_system.college_system.core.exceptions import AnnouncementError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier
import logging

logger = logging.getLogger(__name__)


class AnnouncementService:
    """Announcements management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_announcement(self, **kwargs) -> dict:
        """Create a new announcement."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        if not kwargs.get("content"):
            raise ValidationError("content is required.")
        if not kwargs.get("author_id"):
            raise ValidationError("author_id is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'title': kwargs.get('title'),
                'content': kwargs.get('content'),
                'author_id': kwargs.get('author_id'),
                'category': kwargs.get('category'),
                'target_role': kwargs.get('target_role'),
                'is_pinned': kwargs.get('is_pinned'),
                'publish_date': kwargs.get('publish_date'),
                'expiry_date': kwargs.get('expiry_date'),
                'status': kwargs.get('status'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO announcements ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM announcements WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Announcement created: id=%d", row["id"])
            return dict(row)
        except AnnouncementError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AnnouncementError(f"Failed to create announcement: {e}") from e
        finally:
            conn.close()

    def get_announcement(self, pk: int) -> dict | None:
        """Get announcement by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM announcements WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_announcements(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List announcements with optional filters."""
        sql = "SELECT * FROM announcements WHERE 1=1"
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

    def update_announcement(self, pk: int, **kwargs) -> dict:
        """Update announcement record."""
        allowed = {"title", "content", "author_id", "category", "target_role", "is_pinned", "publish_date", "expiry_date", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE announcements SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Announcement updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM announcements WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_announcement(self, pk: int) -> bool:
        """Delete announcement."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM announcements WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AnnouncementError("Announcement not found.")
            conn.execute("DELETE FROM announcements WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Announcement deleted: pk=%d", pk)
            return True
        except AnnouncementError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AnnouncementError(f"Failed to delete announcement: {e}") from e
        finally:
            conn.close()

    def count_announcements(self, **filters) -> int:
        """Count announcements."""
        sql = "SELECT COUNT(*) as cnt FROM announcements WHERE 1=1"
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
