"""LMS course management service — handles LMS courses, content, video lectures, and enrollment."""
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CourseManagementService:
    def __init__(self, db_path):
        self._db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ---- Courses ----

    def create_course(self, module_code, instructor_id, description="",
                      syllabus_url="", start_date="", end_date="", enrollment_limit=0):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO lms_courses
                   (module_code, instructor_id, course_description, syllabus_url,
                    start_date, end_date, enrollment_limit)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (module_code, instructor_id, description, syllabus_url,
                 start_date, end_date, enrollment_limit))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def publish_course(self, course_id):
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE lms_courses SET is_published = 1, updated_at = ? WHERE lms_course_id = ?",
                (datetime.now().isoformat(), course_id))
            conn.commit()
        finally:
            conn.close()

    def get_course_details(self, course_id):
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM lms_courses WHERE lms_course_id = ?", (course_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_all_courses(self):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_courses ORDER BY created_at DESC").fetchall()]
        finally:
            conn.close()

    def get_instructor_courses(self, instructor_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_courses WHERE instructor_id = ? ORDER BY created_at DESC",
                (instructor_id,)).fetchall()]
        finally:
            conn.close()

    # ---- Content ----

    def add_content(self, course_id, content_type, title, description="",
                    content_url="", content_order=0, release_date=""):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO lms_course_content
                   (lms_course_id, content_type, title, description,
                    content_url, content_order, release_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (course_id, content_type, title, description,
                 content_url, content_order, release_date))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_course_content(self, course_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM lms_course_content WHERE lms_course_id = ? ORDER BY content_order",
                (course_id,)).fetchall()]
        finally:
            conn.close()

    # ---- Video Lectures ----

    def add_video_lecture(self, content_id, video_url, duration_minutes=0,
                         thumbnail_url="", transcript_url="", video_quality="720p"):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO lms_video_lectures
                   (content_id, video_url, duration_minutes, thumbnail_url,
                    transcript_url, video_quality)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (content_id, video_url, duration_minutes, thumbnail_url,
                 transcript_url, video_quality))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    # ---- Enrollment ----

    def enrol_student(self, course_id, student_id):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO lms_student_enrollment (lms_course_id, student_id) VALUES (?, ?)",
                (course_id, student_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_enrolled_courses(self, student_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                """SELECT e.*, c.module_code, c.instructor_id, c.start_date, c.end_date
                   FROM lms_student_enrollment e
                   JOIN lms_courses c ON e.lms_course_id = c.lms_course_id
                   WHERE e.student_id = ?
                   ORDER BY e.enrolled_at DESC""",
                (student_id,)).fetchall()]
        finally:
            conn.close()

    def get_available_courses(self, student_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM lms_courses
                   WHERE is_published = 1
                   AND lms_course_id NOT IN (
                       SELECT lms_course_id FROM lms_student_enrollment WHERE student_id = ?
                   )
                   ORDER BY module_code""",
                (student_id,)).fetchall()]
        finally:
            conn.close()
