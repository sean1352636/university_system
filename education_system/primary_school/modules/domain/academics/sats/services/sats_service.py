"""SATs management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import SATsError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class SATsService:
    """CRUD operations for SATs results."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_result(self, pupil_id, academic_year, key_stage, subject,
                      raw_score=None, scaled_score=None, outcome=None,
                      teacher_assessment=None, assessment_date=None):
        if not pupil_id:
            raise SATsError("Pupil ID is required")
        if not academic_year:
            raise SATsError("Academic year is required")
        if not key_stage:
            raise SATsError("Key stage is required")
        if not subject:
            raise SATsError("Subject is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO sats_results (
                    pupil_id, academic_year, key_stage, subject, raw_score,
                    scaled_score, outcome, teacher_assessment, assessment_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, academic_year, key_stage, subject, raw_score,
                 scaled_score, outcome, teacher_assessment, assessment_date),
            )
            conn.commit()
            result_id = cursor.lastrowid
            logger.info("Recorded SATs result %d for pupil %s: %s KS%s",
                        result_id, pupil_id, subject, key_stage)
            return {"result_id": result_id, "pupil_id": pupil_id,
                    "subject": subject, "key_stage": key_stage}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SATsError(f"Failed to record SATs result: {e}") from e
        finally:
            conn.close()

    def get_results(self, pupil_id=None, academic_year=None, key_stage=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM sats_results WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if key_stage is not None:
                sql += " AND key_stage = ?"
                params.append(key_stage)
            sql += " ORDER BY academic_year DESC, subject"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_result(self, result_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"raw_score", "scaled_score", "outcome",
                       "teacher_assessment", "assessment_date"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(result_id)
            cursor.execute(
                f"UPDATE sats_results SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            logger.info("Updated SATs result: %d", result_id)
            cursor.execute("SELECT * FROM sats_results WHERE id = ?",
                           (result_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SATsError(f"Failed to update SATs result: {e}") from e
        finally:
            conn.close()

    def delete_result(self, result_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sats_results WHERE id = ?", (result_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted SATs result: %d", result_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SATsError(f"Failed to delete SATs result: {e}") from e
        finally:
            conn.close()

    def get_cohort_summary(self, academic_year, key_stage):
        """Return percentage of pupils at each outcome level for a cohort."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT subject, outcome, COUNT(*) AS count
                   FROM sats_results
                   WHERE academic_year = ? AND key_stage = ?
                   GROUP BY subject, outcome
                   ORDER BY subject, outcome""",
                (academic_year, key_stage),
            )
            rows = [dict(r) for r in cursor.fetchall()]

            # Calculate totals per subject for percentage computation
            subject_totals = {}
            for row in rows:
                subj = row["subject"]
                subject_totals[subj] = subject_totals.get(subj, 0) + row["count"]

            summary = {}
            for row in rows:
                subj = row["subject"]
                total = subject_totals[subj]
                if subj not in summary:
                    summary[subj] = {"total": total, "outcomes": {}}
                pct = round((row["count"] / total) * 100, 1) if total else 0
                summary[subj]["outcomes"][row["outcome"]] = {
                    "count": row["count"],
                    "percentage": pct,
                }
            return summary
        finally:
            conn.close()
