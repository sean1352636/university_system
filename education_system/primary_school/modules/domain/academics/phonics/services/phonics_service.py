"""Phonics screening service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import PhonicsError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class PhonicsService:
    """CRUD operations for phonics screening results."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_result(self, pupil_id, academic_year, year_group, score,
                      threshold=32, is_resit=0, assessment_date=None):
        if not pupil_id:
            raise PhonicsError("Pupil ID is required")
        if not academic_year:
            raise PhonicsError("Academic year is required")
        if not year_group:
            raise PhonicsError("Year group is required")
        if score is None:
            raise PhonicsError("Score is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            passed = 1 if score >= threshold else 0
            cursor.execute(
                """INSERT INTO phonics_results (
                    pupil_id, academic_year, year_group, score, threshold,
                    passed, is_resit, assessment_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, academic_year, year_group, score, threshold,
                 passed, is_resit, assessment_date),
            )
            conn.commit()
            result_id = cursor.lastrowid
            logger.info("Recorded phonics result %d for pupil %s: %d/%d (%s)",
                        result_id, pupil_id, score, threshold,
                        "pass" if passed else "fail")
            return {"result_id": result_id, "pupil_id": pupil_id,
                    "score": score, "passed": passed}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PhonicsError(f"Failed to record phonics result: {e}") from e
        finally:
            conn.close()

    def get_results(self, pupil_id=None, academic_year=None, year_group=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM phonics_results WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if year_group is not None:
                sql += " AND year_group = ?"
                params.append(year_group)
            sql += " ORDER BY academic_year DESC, year_group"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_result(self, result_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"score", "threshold", "is_resit", "assessment_date"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            # Recalculate passed if score or threshold changed
            if "score" in updates or "threshold" in updates:
                cursor.execute(
                    "SELECT score, threshold FROM phonics_results WHERE id = ?",
                    (result_id,),
                )
                current = cursor.fetchone()
                if current:
                    new_score = updates.get("score", current["score"])
                    new_threshold = updates.get("threshold", current["threshold"])
                    updates["passed"] = 1 if new_score >= new_threshold else 0

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(result_id)
            cursor.execute(
                f"UPDATE phonics_results SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated phonics result: %d", result_id)
            cursor.execute("SELECT * FROM phonics_results WHERE id = ?",
                           (result_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PhonicsError(f"Failed to update phonics result: {e}") from e
        finally:
            conn.close()

    def delete_result(self, result_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM phonics_results WHERE id = ?", (result_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted phonics result: %d", result_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PhonicsError(f"Failed to delete phonics result: {e}") from e
        finally:
            conn.close()

    def get_cohort_summary(self, academic_year, year_group=None):
        """Return pass rate and score statistics for a cohort."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = """SELECT
                         COUNT(*) AS total,
                         SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed_count,
                         AVG(score) AS avg_score,
                         MIN(score) AS min_score,
                         MAX(score) AS max_score
                     FROM phonics_results
                     WHERE academic_year = ?"""
            params = [academic_year]
            if year_group is not None:
                sql += " AND year_group = ?"
                params.append(year_group)
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if not row or row["total"] == 0:
                return {"total": 0, "passed": 0, "pass_rate": 0,
                        "avg_score": 0, "min_score": 0, "max_score": 0}
            total = row["total"]
            passed = row["passed_count"]
            return {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round((passed / total) * 100, 1),
                "avg_score": round(row["avg_score"], 1) if row["avg_score"] else 0,
                "min_score": row["min_score"],
                "max_score": row["max_score"],
            }
        finally:
            conn.close()
