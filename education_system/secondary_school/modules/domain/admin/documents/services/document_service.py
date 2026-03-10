"""Document store service."""

import logging
from education_system.secondary_school.core.exceptions import DocumentError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

DOC_CATEGORIES = ("policy", "procedure", "consent_form", "safeguarding", "curriculum",
                  "student_record", "staff_record", "template", "other")


class DocumentService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_document(self, title, filename, file_path, category="policy",
                     description=None, uploaded_by=None, version="1.0",
                     requires_acknowledgement=False):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO documents
                   (title, category, description, filename, file_path, uploaded_by, version, requires_acknowledgement)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, category, description, filename, file_path, uploaded_by, version,
                 int(requires_acknowledgement)))
            conn.commit()
            return dict(conn.execute("SELECT * FROM documents WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise DocumentError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_documents(self, category=None, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM documents WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY title"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_document(self, doc_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM document_acknowledgements WHERE document_id = ?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()

    def acknowledge(self, doc_id, user_id):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO document_acknowledgements (document_id, user_id) VALUES (?, ?)",
                (doc_id, user_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise DocumentError(f"Failed: {e}") from e
        finally:
            conn.close()

    def acknowledgement_count(self, doc_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM document_acknowledgements WHERE document_id = ?",
                               (doc_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
