"""Assessment management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AssessmentError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class AssessmentService:
    """CRUD operations for assessments."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_assessment(self, pupil_id, subject_code, level,
                          assessment_type="Formative", term=None,
                          academic_year=None, year_group=None, score=None,
                          max_score=None, assessed_by=None, comments=None):
        if not pupil_id:
            raise AssessmentError("Pupil ID is required")
        if not subject_code:
            raise AssessmentError("Subject code is required")
        if not level:
            raise AssessmentError("Level is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO assessments (
                    pupil_id, subject_code, level, assessment_type, term,
                    academic_year, year_group, score, max_score, assessed_by,
                    comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, subject_code, level, assessment_type, term,
                 academic_year, year_group, score, max_score, assessed_by,
                 comments),
            )
            conn.commit()
            assessment_id = cursor.lastrowid
            logger.info("Recorded assessment %d for pupil %s in %s",
                        assessment_id, pupil_id, subject_code)
            return {"assessment_id": assessment_id, "pupil_id": pupil_id,
                    "subject_code": subject_code, "level": level}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssessmentError(f"Failed to record assessment: {e}") from e
        finally:
            conn.close()

    def get_assessments(self, pupil_id=None, subject_code=None, term=None,
                        academic_year=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM assessments WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if subject_code is not None:
                sql += " AND subject_code = ?"
                params.append(subject_code)
            if term is not None:
                sql += " AND term = ?"
                params.append(term)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_assessment(self, assessment_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"level", "assessment_type", "term", "academic_year",
                       "year_group", "score", "max_score", "assessed_by",
                       "comments"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(assessment_id)
            cursor.execute(
                f"UPDATE assessments SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated assessment: %d", assessment_id)
            cursor.execute("SELECT * FROM assessments WHERE id = ?",
                           (assessment_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssessmentError(f"Failed to update assessment: {e}") from e
        finally:
            conn.close()

    def delete_assessment(self, assessment_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM assessments WHERE id = ?", (assessment_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted assessment: %d", assessment_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AssessmentError(f"Failed to delete assessment: {e}") from e
        finally:
            conn.close()

    def get_pupil_summary(self, pupil_id):
        """Return the latest assessment per subject for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT a.* FROM assessments a
                   INNER JOIN (
                       SELECT subject_code, MAX(created_at) AS latest
                       FROM assessments WHERE pupil_id = ?
                       GROUP BY subject_code
                   ) latest_a
                   ON a.subject_code = latest_a.subject_code
                   AND a.created_at = latest_a.latest
                   WHERE a.pupil_id = ?
                   ORDER BY a.subject_code""",
                (pupil_id, pupil_id),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
