"""Progress Tracking service."""

import logging
from education_system.secondary_school.core.exceptions import ProgressError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

GCSE_GRADES = ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U")
EFFORT_GRADES = ("1", "2", "3", "4")


class ProgressService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def set_target(self, student_id, subject_id, academic_year="2025/2026",
                   baseline_grade=None, target_grade=None):
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM progress_targets WHERE student_id = ? AND subject_id = ? AND academic_year = ?",
                (student_id, subject_id, academic_year)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE progress_targets SET baseline_grade = ?, target_grade = ?, updated_at = datetime('now') WHERE id = ?",
                    (baseline_grade, target_grade, existing["id"]))
            else:
                conn.execute(
                    """INSERT INTO progress_targets
                       (student_id, subject_id, academic_year, baseline_grade, target_grade)
                       VALUES (?, ?, ?, ?, ?)""",
                    (student_id, subject_id, academic_year, baseline_grade, target_grade))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ProgressError(f"Failed: {e}") from e
        finally:
            conn.close()

    def update_grade(self, target_id, term, grade, effort=None, comment=None):
        conn = self._conn()
        try:
            updates = [f"updated_at = datetime('now')"]
            params = []
            if term in ("autumn", "spring", "summer"):
                updates.append(f"{term}_grade = ?")
                params.append(grade)
            updates.append("current_grade = ?")
            params.append(grade)
            if effort:
                updates.append("effort = ?")
                params.append(effort)
            if comment:
                updates.append("teacher_comment = ?")
                params.append(comment)
            params.append(target_id)
            conn.execute(f"UPDATE progress_targets SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ProgressError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_student_progress(self, student_id, academic_year=None):
        conn = self._conn()
        try:
            sql = """SELECT pt.*, sub.title AS subject_name, sub.subject_code
                     FROM progress_targets pt
                     JOIN subjects sub ON pt.subject_id = sub.id
                     WHERE pt.student_id = ?"""
            params = [student_id]
            if academic_year:
                sql += " AND pt.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY sub.title"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def list_subject_progress(self, subject_id, academic_year=None):
        conn = self._conn()
        try:
            sql = """SELECT pt.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM progress_targets pt
                     JOIN students s ON pt.student_id = s.id
                     WHERE pt.subject_id = ?"""
            params = [subject_id]
            if academic_year:
                sql += " AND pt.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY s.last_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def list_all(self, year_group=None, academic_year="2025/2026"):
        conn = self._conn()
        try:
            sql = """SELECT pt.*, s.first_name, s.last_name, s.student_id AS stu_code,
                            s.year_group, sub.title AS subject_name
                     FROM progress_targets pt
                     JOIN students s ON pt.student_id = s.id
                     JOIN subjects sub ON pt.subject_id = sub.id
                     WHERE pt.academic_year = ?"""
            params = [academic_year]
            if year_group:
                sql += " AND s.year_group = ?"
                params.append(year_group)
            sql += " ORDER BY s.last_name, sub.title"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_target(self, target_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM progress_targets WHERE id = ?", (target_id,))
            conn.commit()
        finally:
            conn.close()
