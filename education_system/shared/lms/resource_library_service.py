"""LMS resource library service."""
import sqlite3


class ResourceLibraryService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upload_resource(self, title, description, file_path, resource_type="document", uploaded_by=None, course_id=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_resources (title, description, file_path, resource_type, course_id, uploaded_by) VALUES (?, ?, ?, ?, ?, ?)",
                (title, description, file_path, resource_type, course_id, uploaded_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_resources(self, course_id=None, resource_type=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM lms_resources WHERE 1=1"
            params = []
            if course_id:
                sql += " AND course_id = ?"; params.append(course_id)
            if resource_type:
                sql += " AND resource_type = ?"; params.append(resource_type)
            return [dict(r) for r in conn.execute(sql + " ORDER BY created_at DESC", params).fetchall()]
        finally:
            conn.close()

    def download_resource(self, resource_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE lms_resources SET download_count = download_count + 1 WHERE id = ?", (resource_id,))
            conn.commit()
            row = conn.execute("SELECT * FROM lms_resources WHERE id = ?", (resource_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_resources(self, query):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_resources WHERE title LIKE ? OR description LIKE ?",
                (f"%{query}%", f"%{query}%")).fetchall()]
        finally:
            conn.close()

    def delete_resource(self, resource_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM lms_resources WHERE id = ?", (resource_id,))
            conn.commit()
        finally:
            conn.close()
