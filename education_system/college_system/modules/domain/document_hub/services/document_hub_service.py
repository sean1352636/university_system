"""Service for managing document hub."""

from datetime import datetime
from education_system.college_system.core.exceptions import DocumentHubError, ValidationError
from education_system.college_system.infrastructure.database.db import connect
from education_system.college_system.core.sql_safety import validate_identifier  # nosec B608
import logging

logger = logging.getLogger(__name__)


class DocumentHubService:
    """Document Hub management service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_document(self, **kwargs) -> dict:
        """Create a new document."""
        if not kwargs.get("title"):
            raise ValidationError("title is required.")
        if not kwargs.get("uploaded_by"):
            raise ValidationError("uploaded_by is required.")
        conn = self._conn()
        try:
            # Build INSERT with only non-None values so DB defaults apply
            fields = {k: v for k, v in {
                'title': kwargs.get('title'),
                'category': kwargs.get('category'),
                'file_path': kwargs.get('file_path'),
                'file_type': kwargs.get('file_type'),
                'file_size': kwargs.get('file_size'),
                'version': kwargs.get('version'),
                'uploaded_by': kwargs.get('uploaded_by'),
                'target_role': kwargs.get('target_role'),
                'download_count': kwargs.get('download_count'),
            }.items() if v is not None}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            conn.execute(
                f"INSERT INTO documents ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM documents WHERE id = last_insert_rowid()"
            ).fetchone()
            logger.info("Document created: id=%d", row["id"])
            return dict(row)
        except DocumentHubError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DocumentHubError(f"Failed to create document: {e}") from e
        finally:
            conn.close()

    def get_document(self, pk: int) -> dict | None:
        """Get document by ID."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_documents(self, *, limit: int = 100, offset: int = 0, **filters) -> list[dict]:
        """List documents with optional filters."""
        sql = "SELECT * FROM documents WHERE 1=1"
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

    def update_document(self, pk: int, **kwargs) -> dict:
        """Update document record."""
        # Iterate over a literal allowed-column tuple so CodeQL recognises
        # the column names as untainted (py/sql-injection).
        set_parts: list[str] = []
        params: list = []
        for col in ("title", "category", "file_path", "file_type", "file_size", "version", "uploaded_by", "target_role", "download_count"):
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
            conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", params)  # nosec B608
            conn.commit()
            logger.info("Document updated: pk=%d", pk)
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (pk,)).fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    def delete_document(self, pk: int) -> bool:
        """Delete document."""
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM documents WHERE id = ?", (pk,)).fetchone()
            if not existing:
                raise DocumentHubError("Document not found.")
            conn.execute("DELETE FROM documents WHERE id = ?", (pk,))
            conn.commit()
            logger.info("Document deleted: pk=%d", pk)
            return True
        except DocumentHubError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise DocumentHubError(f"Failed to delete document: {e}") from e
        finally:
            conn.close()

    def count_documents(self, **filters) -> int:
        """Count documents."""
        sql = "SELECT COUNT(*) as cnt FROM documents WHERE 1=1"
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
