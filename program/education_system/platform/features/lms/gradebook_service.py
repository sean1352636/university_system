"""LMS gradebook service."""
import sqlite3
import logging

logger = logging.getLogger(__name__)


class GradebookService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_grade_entry(self, course_id, student_id, assignment_type, assignment_id,
                        score, max_score, weight=1.0, feedback="", graded_by=""):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO lms_gradebook
                   (lms_course_id, student_id, assignment_type, assignment_id,
                    score, max_score, weight, feedback, graded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (course_id, student_id, assignment_type, assignment_id,
                 score, max_score, weight, feedback, graded_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_student_grades(self, course_id, student_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM lms_gradebook
                   WHERE lms_course_id = ? AND student_id = ?
                   ORDER BY graded_at DESC""",
                (course_id, student_id)).fetchall()]
        finally:
            conn.close()

    def calculate_course_grade(self, course_id, student_id):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT score, max_score, weight FROM lms_gradebook
                   WHERE lms_course_id = ? AND student_id = ?""",
                (course_id, student_id)).fetchall()
            if not rows:
                return 0.0
            total_weighted = sum((r["score"] / r["max_score"]) * r["weight"] for r in rows if r["max_score"] > 0)
            total_weight = sum(r["weight"] for r in rows if r["max_score"] > 0)
            if total_weight == 0:
                return 0.0
            return round((total_weighted / total_weight) * 100, 2)
        finally:
            conn.close()
