"""Document management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import DocumentError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class DocumentService:
    """CRUD operations for school documents."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_document(self, title, category=None, file_path=None, file_type=None,
                        description=None, uploaded_by=None, access_level="Staff"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO documents (title, category, file_path, file_type,
                    description, uploaded_by, access_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, category, file_path, file_type, description,
                 uploaded_by, access_level),
            )
            conn.commit()
            doc_id = cursor.lastrowid
            logger.info("Created document: %s (id=%s)", title, doc_id)
            return {"id": doc_id, "title": title, "access_level": access_level}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise DocumentError(f"Failed to create document: {e}") from e
        finally:
            conn.close()

    def get_document(self, doc_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_documents(self, category=None, access_level=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM documents WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if access_level:
                sql += " AND access_level = ?"
                params.append(access_level)
            sql += " ORDER BY title"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_document(self, doc_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "title", "category", "file_path", "file_type",
                "description", "uploaded_by", "access_level",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(doc_id)
            cursor.execute(
                f"UPDATE documents SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated document id=%s", doc_id)
            return self.get_document(doc_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise DocumentError(f"Failed to update document: {e}") from e
        finally:
            conn.close()

    def delete_document(self, doc_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted document id=%s", doc_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise DocumentError(f"Failed to delete document: {e}") from e
        finally:
            conn.close()
