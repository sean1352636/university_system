"""Service for managing attachments."""

from datetime import datetime
from education_system.college_system.core.exceptions import AttachmentError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
import logging

logger = logging.getLogger(__name__)


class AttachmentService:
    """Attachments management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_attachment(self, **kwargs) -> dict:
        """Create a new attachment."""
        if not kwargs.get("uploaded_by"):
            raise ValidationError("uploaded_by is required.")
        if not kwargs.get("filename"):
            raise ValidationError("filename is required.")
        if not kwargs.get("original_filename"):
            raise ValidationError("original_filename is required.")
        if not kwargs.get("file_path"):
            raise ValidationError("file_path is required.")
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO attachments (uploaded_by, filename, original_filename, file_path, file_type, file_size, entity_type, entity_id, is_public)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kwargs.get('uploaded_by'), kwargs.get('filename'), kwargs.get('original_filename'), kwargs.get('file_path'), kwargs.get('file_type'), kwargs.get('file_size'), kwargs.get('entity_type'), kwargs.get('entity_id'), kwargs.get('is_public'),),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM attachments WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Attachment created: id=%d", row["id"])
            return dict(row)
        except AttachmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttachmentError(f"Failed to create attachment: {e}") from e
        finally:
            conn.close()

    def get_attachment(self, pk: int) -> dict | None:
        """Get attachment by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM attachments WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_attachments(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List attachments with optional filters."""
        sql = "SELECT * FROM attachments WHERE 1=1"
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

    def update_attachment(self, pk: int, **kwargs) -> dict:
        """Update attachment record."""
        allowed = {"uploaded_by", "filename", "original_filename", "file_path", "file_type", "file_size", "entity_type", "entity_id", "is_public"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            raise ValidationError("No valid fields to update.")
        updates["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [pk]
        conn = self._conn()
        try:
            conn.execute(f"UPDATE attachments SET {set_clause} WHERE id = ?", params)
            conn.commit()
            logger.info("Attachment updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM attachments WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_attachment(self, pk: int) -> bool:
        """Delete attachment."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM attachments WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise AttachmentError("Attachment not found.")
            conn.execute("DELETE FROM attachments WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Attachment deleted: pk=%d", pk)
            return True
        except AttachmentError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise AttachmentError(f"Failed to delete attachment: {e}") from e
        finally:
            conn.close()

    def count_attachments(self, **filters) -> int:
        """Count attachments."""
        sql = "SELECT COUNT(*) as cnt FROM attachments WHERE 1=1"
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
