"""Functional Skills & GCSE Resits service layer."""

from education_system.college_system.core.exceptions import FunctionalSkillsError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class FunctionalSkillsService:
    """Service for managing Functional Skills enrollments, assessments, and reporting."""

    ENROLLMENT_ALLOWED = {
        "student_id", "subject", "qualification_type", "level", "entry_grade",
        "target_grade", "current_grade", "exam_board", "exam_series",
        "exam_date", "result", "attendance_pct", "status", "notes",
    }

    ASSESSMENT_ALLOWED = {
        "enrollment_id", "assessment_type", "assessment_date",
        "score", "grade", "feedback",
    }

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        conn = connect(self._db_path)
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        return conn

    # ------------------------------------------------------------------ #
    # Enrollments CRUD
    # ------------------------------------------------------------------ #

    def list_enrollments(self, subject=None, status=None,
                         qualification_type=None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT e.*, s.first_name, s.last_name
                     FROM functional_skills_enrollments e
                     LEFT JOIN students s ON e.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if subject:
                sql += " AND e.subject = ?"
                params.append(subject)
            if status:
                sql += " AND e.status = ?"
                params.append(status)
            if qualification_type:
                sql += " AND e.qualification_type = ?"
                params.append(qualification_type)
            sql += " ORDER BY e.created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_enrollment(self, enrollment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT e.*, s.first_name, s.last_name
                   FROM functional_skills_enrollments e
                   LEFT JOIN students s ON e.student_id = s.id
                   WHERE e.id = ?""",
                (enrollment_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_enrollment(self, student_id: int, subject: str, **kwargs) -> dict:
        conn = self._conn()
        try:
            col_names: list[str] = ["student_id", "subject"]
            insert_values: list = [student_id, subject]
            for col in ("attendance_pct", "current_grade", "entry_grade", "exam_board",
                        "exam_date", "exam_series", "level", "notes",
                        "qualification_type", "result", "status", "target_grade"):
                if col in kwargs and kwargs[col] is not None:
                    col_names.append(col)
                    insert_values.append(kwargs[col])
            cols = ", ".join(col_names)
            placeholders = ", ".join("?" for _ in col_names)
            conn.execute(
                f"INSERT INTO functional_skills_enrollments ({cols}) VALUES ({placeholders})",  # nosec B608
                insert_values,
            )
            conn.commit()
            logger.info("Enrollment created: student=%d subject=%s", student_id, subject)
            row = conn.execute(
                "SELECT * FROM functional_skills_enrollments WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to create enrollment: {e}") from e
        finally:
            conn.close()

    def update_enrollment(self, enrollment_id: int, **kwargs) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("attendance_pct", "current_grade", "entry_grade", "exam_board",
                    "exam_date", "exam_series", "level", "notes",
                    "qualification_type", "result", "status", "student_id",
                    "subject", "target_grade"):
            if col in kwargs and kwargs[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(kwargs[col])
        if not set_parts:
            raise FunctionalSkillsError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Enrollment not found.")
            set_clause = ", ".join(set_parts)
            vals.append(enrollment_id)
            conn.execute(
                f"UPDATE functional_skills_enrollments SET {set_clause}, updated_at = datetime('now') WHERE id = ?",  # nosec B608
                vals,
            )
            conn.commit()
            logger.info("Enrollment updated: id=%d", enrollment_id)
            row = conn.execute(
                "SELECT * FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            return row
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to update enrollment: {e}") from e
        finally:
            conn.close()

    def delete_enrollment(self, enrollment_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Enrollment not found.")
            conn.execute(
                "DELETE FROM functional_skills_assessments WHERE enrollment_id = ?",
                (enrollment_id,),
            )
            conn.execute(
                "DELETE FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            )
            conn.commit()
            logger.info("Enrollment deleted: id=%d", enrollment_id)
            return True
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to delete enrollment: {e}") from e
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Assessments CRUD
    # ------------------------------------------------------------------ #

    def list_assessments(self, enrollment_id=None,
                         assessment_type=None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM functional_skills_assessments WHERE 1=1"
            params: list = []
            if enrollment_id:
                sql += " AND enrollment_id = ?"
                params.append(enrollment_id)
            if assessment_type:
                sql += " AND assessment_type = ?"
                params.append(assessment_type)
            sql += " ORDER BY created_at DESC"
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def get_assessment(self, assessment_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM functional_skills_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
            return row
        finally:
            conn.close()

    def create_assessment(self, enrollment_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            # Verify enrollment exists
            enr = conn.execute(
                "SELECT id FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            if not enr:
                raise FunctionalSkillsError("Enrollment not found.")
            col_names: list[str] = ["enrollment_id"]
            insert_values: list = [enrollment_id]
            for col in ("assessment_date", "assessment_type", "feedback",
                        "grade", "score"):
                if col in kwargs and kwargs[col] is not None:
                    col_names.append(col)
                    insert_values.append(kwargs[col])
            cols = ", ".join(col_names)
            placeholders = ", ".join("?" for _ in col_names)
            conn.execute(
                f"INSERT INTO functional_skills_assessments ({cols}) VALUES ({placeholders})",  # nosec B608
                insert_values,
            )
            conn.commit()
            logger.info("Assessment created for enrollment=%d", enrollment_id)
            row = conn.execute(
                "SELECT * FROM functional_skills_assessments WHERE id = last_insert_rowid()"
            ).fetchone()
            return row
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to create assessment: {e}") from e
        finally:
            conn.close()

    def update_assessment(self, assessment_id: int, **kwargs) -> dict:
        set_parts: list[str] = []
        vals: list = []
        for col in ("assessment_date", "assessment_type", "enrollment_id",
                    "feedback", "grade", "score"):
            if col in kwargs and kwargs[col] is not None:
                set_parts.append(f"{col} = ?")
                vals.append(kwargs[col])
        if not set_parts:
            raise FunctionalSkillsError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Assessment not found.")
            set_clause = ", ".join(set_parts)
            vals.append(assessment_id)
            conn.execute(
                f"UPDATE functional_skills_assessments SET {set_clause} WHERE id = ?",  # nosec B608
                vals,
            )
            conn.commit()
            logger.info("Assessment updated: id=%d", assessment_id)
            row = conn.execute(
                "SELECT * FROM functional_skills_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
            return row
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to update assessment: {e}") from e
        finally:
            conn.close()

    def delete_assessment(self, assessment_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Assessment not found.")
            conn.execute(
                "DELETE FROM functional_skills_assessments WHERE id = ?",
                (assessment_id,),
            )
            conn.commit()
            logger.info("Assessment deleted: id=%d", assessment_id)
            return True
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to delete assessment: {e}") from e
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Workflow
    # ------------------------------------------------------------------ #

    def record_result(self, enrollment_id: int, result: str,
                      grade: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Enrollment not found.")
            conn.execute(
                """UPDATE functional_skills_enrollments
                   SET result = ?, current_grade = COALESCE(?, current_grade),
                       status = 'completed', updated_at = datetime('now')
                   WHERE id = ?""",
                (result, grade, enrollment_id),
            )
            conn.commit()
            logger.info("Result recorded: enrollment=%d result=%s", enrollment_id, result)
            row = conn.execute(
                "SELECT * FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            return row
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to record result: {e}") from e
        finally:
            conn.close()

    def book_exam(self, enrollment_id: int, exam_date: str,
                  exam_series: str | None = None) -> dict:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            if not existing:
                raise FunctionalSkillsError("Enrollment not found.")
            conn.execute(
                """UPDATE functional_skills_enrollments
                   SET exam_date = ?, exam_series = COALESCE(?, exam_series),
                       status = 'exam_booked', updated_at = datetime('now')
                   WHERE id = ?""",
                (exam_date, exam_series, enrollment_id),
            )
            conn.commit()
            logger.info("Exam booked: enrollment=%d date=%s", enrollment_id, exam_date)
            row = conn.execute(
                "SELECT * FROM functional_skills_enrollments WHERE id = ?",
                (enrollment_id,),
            ).fetchone()
            return row
        except FunctionalSkillsError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise FunctionalSkillsError(f"Failed to book exam: {e}") from e
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def get_student_progress(self, student_id: int) -> list[dict]:
        """Return all enrollments with their assessments for a student."""
        conn = self._conn()
        try:
            enrollments = conn.execute(
                """SELECT e.*, s.first_name, s.last_name
                   FROM functional_skills_enrollments e
                   LEFT JOIN students s ON e.student_id = s.id
                   WHERE e.student_id = ?
                   ORDER BY e.created_at DESC""",
                (student_id,),
            ).fetchall()
            result = []
            for enr in enrollments:
                assessments = conn.execute(
                    """SELECT * FROM functional_skills_assessments
                       WHERE enrollment_id = ?
                       ORDER BY assessment_date DESC, created_at DESC""",
                    (enr["id"],),
                ).fetchall()
                enr_copy = dict(enr)
                enr_copy["assessments"] = assessments
                result.append(enr_copy)
            return result
        finally:
            conn.close()

    def condition_of_funding_report(self) -> list[dict]:
        """Students who need maths/english (condition of funding requirement).

        Returns students enrolled in maths or english functional skills /
        GCSE resits who have not yet achieved a pass.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT s.id as student_id, s.first_name, s.last_name,
                          e.id as enrollment_id, e.subject, e.qualification_type,
                          e.level, e.entry_grade, e.target_grade, e.current_grade,
                          e.exam_date, e.result, e.status, e.attendance_pct
                   FROM functional_skills_enrollments e
                   JOIN students s ON e.student_id = s.id
                   WHERE LOWER(e.subject) IN ('maths', 'math', 'mathematics',
                                               'english', 'english language')
                     AND e.status != 'withdrawn'
                     AND (e.result IS NULL OR LOWER(e.result) NOT IN ('pass', 'achieved'))
                   ORDER BY s.last_name, s.first_name, e.subject"""
            ).fetchall()
            return rows
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def get_stats(self) -> dict:
        conn = self._conn()
        try:
            total_enrollments = conn.execute(
                "SELECT COUNT(*) as cnt FROM functional_skills_enrollments"
            ).fetchone()["cnt"]

            by_subject_rows = conn.execute(
                """SELECT subject, COUNT(*) as cnt
                   FROM functional_skills_enrollments
                   GROUP BY subject ORDER BY cnt DESC"""
            ).fetchall()
            by_subject = {r["subject"]: r["cnt"] for r in by_subject_rows}

            by_status_rows = conn.execute(
                """SELECT status, COUNT(*) as cnt
                   FROM functional_skills_enrollments
                   GROUP BY status ORDER BY cnt DESC"""
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in by_status_rows}

            by_qual_rows = conn.execute(
                """SELECT qualification_type, COUNT(*) as cnt
                   FROM functional_skills_enrollments
                   GROUP BY qualification_type ORDER BY cnt DESC"""
            ).fetchall()
            by_qualification_type = {r["qualification_type"]: r["cnt"] for r in by_qual_rows}

            total_assessments = conn.execute(
                "SELECT COUNT(*) as cnt FROM functional_skills_assessments"
            ).fetchone()["cnt"]

            avg_row = conn.execute(
                "SELECT AVG(score) as avg_score FROM functional_skills_assessments WHERE score IS NOT NULL"
            ).fetchone()
            avg_score = round(avg_row["avg_score"], 1) if avg_row["avg_score"] else 0.0

            total_completed = conn.execute(
                "SELECT COUNT(*) as cnt FROM functional_skills_enrollments WHERE status = 'completed'"
            ).fetchone()["cnt"]
            total_passed = conn.execute(
                """SELECT COUNT(*) as cnt FROM functional_skills_enrollments
                   WHERE status = 'completed'
                     AND LOWER(result) IN ('pass', 'achieved')"""
            ).fetchone()["cnt"]
            pass_rate = round((total_passed / total_completed * 100), 1) if total_completed > 0 else 0.0

            return {
                "total_enrollments": total_enrollments,
                "by_subject": by_subject,
                "by_status": by_status,
                "by_qualification_type": by_qualification_type,
                "total_assessments": total_assessments,
                "avg_score": avg_score,
                "pass_rate": pass_rate,
            }
        finally:
            conn.close()
