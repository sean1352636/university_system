"""Progress tracking service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ProgressError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class ProgressService:
    """CRUD operations for pupil progress records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_progress(self, pupil_id, subject_code, term, academic_year,
                        year_group=None, baseline_level=None,
                        current_level=None, target_level=None, on_track=1,
                        intervention_needed=0, comments=None, assessed_by=None):
        if not pupil_id:
            raise ProgressError("Pupil ID is required")
        if not subject_code:
            raise ProgressError("Subject code is required")
        if not term:
            raise ProgressError("Term is required")
        if not academic_year:
            raise ProgressError("Academic year is required")

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO progress_records (
                    pupil_id, subject_code, term, academic_year, year_group,
                    baseline_level, current_level, target_level, on_track,
                    intervention_needed, comments, assessed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, subject_code, term, academic_year, year_group,
                 baseline_level, current_level, target_level, on_track,
                 intervention_needed, comments, assessed_by),
            )
            conn.commit()
            progress_id = cursor.lastrowid
            logger.info("Recorded progress %d for pupil %s in %s (%s %s)",
                        progress_id, pupil_id, subject_code, term,
                        academic_year)
            return {"progress_id": progress_id, "pupil_id": pupil_id,
                    "subject_code": subject_code, "term": term}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ProgressError(f"Failed to record progress: {e}") from e
        finally:
            conn.close()

    def get_progress(self, pupil_id=None, subject_code=None,
                     academic_year=None, term=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM progress_records WHERE 1=1"
            params = []
            if pupil_id is not None:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if subject_code is not None:
                sql += " AND subject_code = ?"
                params.append(subject_code)
            if academic_year is not None:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            if term is not None:
                sql += " AND term = ?"
                params.append(term)
            sql += " ORDER BY academic_year DESC, term DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_progress(self, progress_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {"baseline_level", "current_level", "target_level",
                       "on_track", "intervention_needed", "comments",
                       "assessed_by", "year_group"}
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(progress_id)
            cursor.execute(
                f"UPDATE progress_records SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated progress record: %d", progress_id)
            cursor.execute("SELECT * FROM progress_records WHERE id = ?",
                           (progress_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ProgressError(f"Failed to update progress: {e}") from e
        finally:
            conn.close()

    def delete_progress(self, progress_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM progress_records WHERE id = ?", (progress_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted progress record: %d", progress_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ProgressError(f"Failed to delete progress: {e}") from e
        finally:
            conn.close()
