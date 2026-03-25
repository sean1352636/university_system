"""LMS learning progress tracking service."""
import sqlite3
from datetime import datetime


class LearningProgressService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def mark_lesson_complete(self, student_id, lesson_id):
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM lms_progress WHERE student_id = ? AND lesson_id = ?",
                (student_id, lesson_id)).fetchone()
            if existing:
                conn.execute("UPDATE lms_progress SET completed = 1, completed_at = ? WHERE id = ?",
                             (datetime.now().isoformat(), existing["id"]))
            else:
                conn.execute("INSERT INTO lms_progress (student_id, lesson_id, completed, completed_at) VALUES (?, ?, 1, ?)",
                             (student_id, lesson_id, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()

    def get_student_progress(self, student_id, course_id):
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM lms_lessons l JOIN lms_modules m ON l.module_id = m.id WHERE m.course_id = ?",
                (course_id,)).fetchone()[0]
            completed = conn.execute(
                """SELECT COUNT(*) FROM lms_progress p JOIN lms_lessons l ON p.lesson_id = l.id
                   JOIN lms_modules m ON l.module_id = m.id
                   WHERE p.student_id = ? AND m.course_id = ? AND p.completed = 1""",
                (student_id, course_id)).fetchone()[0]
            pct = round((completed / total * 100) if total > 0 else 0, 1)
            return {"completed": completed, "total": total, "percentage": pct}
        finally:
            conn.close()

    def get_module_progress(self, student_id, module_id):
        """Get progress for a student within a single module."""
        conn = self._conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM lms_lessons WHERE module_id = ?",
                (module_id,)).fetchone()[0]
            completed = conn.execute(
                """SELECT COUNT(*) FROM lms_progress p
                   JOIN lms_lessons l ON p.lesson_id = l.id
                   WHERE p.student_id = ? AND l.module_id = ? AND p.completed = 1""",
                (student_id, module_id)).fetchone()[0]
            pct = round((completed / total * 100) if total > 0 else 0, 1)
            return {"completed": completed, "total": total, "percentage": pct}
        finally:
            conn.close()

    def get_next_lesson(self, student_id, course_id):
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT l.* FROM lms_lessons l JOIN lms_modules m ON l.module_id = m.id
                   WHERE m.course_id = ? AND l.id NOT IN (
                       SELECT lesson_id FROM lms_progress WHERE student_id = ? AND completed = 1
                   ) ORDER BY m.order_index, l.order_index LIMIT 1""",
                (course_id, student_id)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_completed_lessons(self, student_id, course_id=None):
        """Return all completed lesson records for a student."""
        conn = self._conn()
        try:
            if course_id is not None:
                rows = conn.execute(
                    """SELECT p.*, l.title AS lesson_title, m.title AS module_title
                       FROM lms_progress p
                       JOIN lms_lessons l ON p.lesson_id = l.id
                       JOIN lms_modules m ON l.module_id = m.id
                       WHERE p.student_id = ? AND m.course_id = ? AND p.completed = 1
                       ORDER BY p.completed_at""",
                    (student_id, course_id)).fetchall()
            else:
                rows = conn.execute(
                    """SELECT p.*, l.title AS lesson_title, m.title AS module_title
                       FROM lms_progress p
                       JOIN lms_lessons l ON p.lesson_id = l.id
                       JOIN lms_modules m ON l.module_id = m.id
                       WHERE p.student_id = ? AND p.completed = 1
                       ORDER BY p.completed_at""",
                    (student_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_course_completion_stats(self, course_id):
        """Aggregate completion statistics for all students in a course."""
        conn = self._conn()
        try:
            total_lessons = conn.execute(
                """SELECT COUNT(*) FROM lms_lessons l
                   JOIN lms_modules m ON l.module_id = m.id
                   WHERE m.course_id = ?""",
                (course_id,)).fetchone()[0]
            if total_lessons == 0:
                return {"total_students": 0, "avg_percentage": 0.0,
                        "fully_completed": 0, "total_lessons": 0}
            rows = conn.execute(
                """SELECT p.student_id, COUNT(*) AS done
                   FROM lms_progress p
                   JOIN lms_lessons l ON p.lesson_id = l.id
                   JOIN lms_modules m ON l.module_id = m.id
                   WHERE m.course_id = ? AND p.completed = 1
                   GROUP BY p.student_id""",
                (course_id,)).fetchall()
            if not rows:
                return {"total_students": 0, "avg_percentage": 0.0,
                        "fully_completed": 0, "total_lessons": total_lessons}
            total_students = len(rows)
            total_done = sum(r["done"] for r in rows)
            fully_completed = sum(1 for r in rows if r["done"] >= total_lessons)
            avg_pct = round(total_done / (total_students * total_lessons) * 100, 1)
            return {"total_students": total_students, "avg_percentage": avg_pct,
                    "fully_completed": fully_completed, "total_lessons": total_lessons}
        finally:
            conn.close()
