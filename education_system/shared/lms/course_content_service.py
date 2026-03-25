"""LMS course content management service."""
import sqlite3
import logging

logger = logging.getLogger(__name__)


class CourseContentService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_module(self, course_id, title, description=None, order_index=0, created_by=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_modules (course_id, title, description, order_index, created_by) VALUES (?, ?, ?, ?, ?)",
                (course_id, title, description, order_index, created_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_modules(self, course_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_modules WHERE course_id = ? ORDER BY order_index", (course_id,)).fetchall()]
        finally:
            conn.close()

    def create_lesson(self, module_id, title, content_type="text", content=None, order_index=0, duration_mins=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_lessons (module_id, title, content_type, content, order_index, duration_mins) VALUES (?, ?, ?, ?, ?, ?)",
                (module_id, title, content_type, content, order_index, duration_mins))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_lessons(self, module_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_lessons WHERE module_id = ? ORDER BY order_index", (module_id,)).fetchall()]
        finally:
            conn.close()

    def get_lesson(self, lesson_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM lms_lessons WHERE id = ?", (lesson_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_lesson(self, lesson_id, **kwargs):
        if not kwargs:
            return
        from education_system.shared.database.sql_safety import validate_identifier
        conn = self._conn()
        try:
            sets = ", ".join(f"{validate_identifier(k)} = ?" for k in kwargs)
            conn.execute(f"UPDATE lms_lessons SET {sets} WHERE id = ?", list(kwargs.values()) + [lesson_id])
            conn.commit()
        finally:
            conn.close()

    def delete_lesson(self, lesson_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM lms_progress WHERE lesson_id = ?", (lesson_id,))
            conn.execute("DELETE FROM lms_lessons WHERE id = ?", (lesson_id,))
            conn.commit()
        finally:
            conn.close()

    def reorder_lessons(self, module_id, lesson_ids_in_order):
        """Reorder lessons within a module by setting order_index sequentially."""
        conn = self._conn()
        try:
            for idx, lesson_id in enumerate(lesson_ids_in_order):
                conn.execute(
                    "UPDATE lms_lessons SET order_index = ? WHERE id = ? AND module_id = ?",
                    (idx, lesson_id, module_id))
            conn.commit()
        finally:
            conn.close()

    def publish_module(self, module_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE lms_modules SET published = 1 WHERE id = ?", (module_id,))
            conn.commit()
        finally:
            conn.close()

    def unpublish_module(self, module_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE lms_modules SET published = 0 WHERE id = ?", (module_id,))
            conn.commit()
        finally:
            conn.close()
