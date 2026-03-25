"""Baseline Assessment service for managing baseline assessments and progress checkpoints."""

from education_system.college_system.core.exceptions import BaselineAssessmentError
from education_system.college_system.infrastructure.database.db import connect

from education_system.college_system.core.sql_safety import escape_like
import logging

logger = logging.getLogger(__name__)


class BaselineAssessmentService:
    """Baseline Assessment service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Baselines ──────────────────────────────────────────────────────

    def create_baseline(self, student_id: int, **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"student_id": student_id, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO baseline_assessments ({cols}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM baseline_assessments WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(f"Failed to create baseline: {e}") from e
        finally:
            conn.close()

    def list_baselines(self, academic_year=None, assessment_type=None,
                       search=None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT ba.*, s.first_name, s.last_name
                     FROM baseline_assessments ba
                     LEFT JOIN students s ON ba.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if academic_year:
                sql += " AND ba.academic_year = ?"
                params.append(academic_year)
            if assessment_type:
                sql += " AND ba.assessment_type = ?"
                params.append(assessment_type)
            if search:
                sql += " AND (s.first_name LIKE ? OR s.last_name LIKE ?)"
                escaped = escape_like(search)
                params.extend([f"%{escaped}%", f"%{escaped}%"])
            sql += " ORDER BY ba.created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_baseline(self, baseline_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT ba.*, s.first_name, s.last_name
                   FROM baseline_assessments ba
                   LEFT JOIN students s ON ba.student_id = s.id
                   WHERE ba.id = ?""",
                (baseline_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_baseline(self, baseline_id: int, **kwargs) -> dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise BaselineAssessmentError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [baseline_id]
            conn.execute(
                f"UPDATE baseline_assessments SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_baseline(baseline_id)
        except BaselineAssessmentError:
            raise
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(f"Failed to update baseline: {e}") from e
        finally:
            conn.close()

    def delete_baseline(self, baseline_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM baseline_assessments WHERE id = ?", (baseline_id,)
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(f"Failed to delete baseline: {e}") from e
        finally:
            conn.close()

    # ── Checkpoints ────────────────────────────────────────────────────

    def create_checkpoint(self, student_id: int, checkpoint_date: str,
                          **kwargs) -> dict:
        conn = self._conn()
        try:
            fields = {"student_id": student_id,
                      "checkpoint_date": checkpoint_date, **kwargs}
            cols = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            vals = list(fields.values())
            conn.execute(
                f"INSERT INTO progress_checkpoints ({cols}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM progress_checkpoints WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(
                f"Failed to create checkpoint: {e}"
            ) from e
        finally:
            conn.close()

    def list_checkpoints(self, student_id=None, course_id=None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT pc.*, s.first_name, s.last_name
                     FROM progress_checkpoints pc
                     LEFT JOIN students s ON pc.student_id = s.id
                     WHERE 1=1"""
            params: list = []
            if student_id is not None:
                sql += " AND pc.student_id = ?"
                params.append(student_id)
            if course_id is not None:
                sql += " AND pc.course_id = ?"
                params.append(course_id)
            sql += " ORDER BY pc.checkpoint_date DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_checkpoint(self, checkpoint_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT pc.*, s.first_name, s.last_name
                   FROM progress_checkpoints pc
                   LEFT JOIN students s ON pc.student_id = s.id
                   WHERE pc.id = ?""",
                (checkpoint_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_checkpoint(self, checkpoint_id: int, **kwargs) -> dict:
        updates = {k: v for k, v in kwargs.items() if v is not None}
        if not updates:
            raise BaselineAssessmentError("No valid fields to update.")
        conn = self._conn()
        try:
            sets = ", ".join(f"{k} = ?" for k in updates)
            vals = list(updates.values()) + [checkpoint_id]
            conn.execute(
                f"UPDATE progress_checkpoints SET {sets} WHERE id = ?", vals
            )
            conn.commit()
            return self.get_checkpoint(checkpoint_id)
        except BaselineAssessmentError:
            raise
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(
                f"Failed to update checkpoint: {e}"
            ) from e
        finally:
            conn.close()

    def delete_checkpoint(self, checkpoint_id: int) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM progress_checkpoints WHERE id = ?",
                (checkpoint_id,),
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise BaselineAssessmentError(
                f"Failed to delete checkpoint: {e}"
            ) from e
        finally:
            conn.close()

    # ── Aggregates ─────────────────────────────────────────────────────

    def get_student_progress(self, student_id: int) -> dict:
        """Return baseline data plus all checkpoints for a student."""
        conn = self._conn()
        try:
            baseline_rows = conn.execute(
                """SELECT ba.*, s.first_name, s.last_name
                   FROM baseline_assessments ba
                   LEFT JOIN students s ON ba.student_id = s.id
                   WHERE ba.student_id = ?
                   ORDER BY ba.assessment_date DESC""",
                (student_id,),
            ).fetchall()
            checkpoint_rows = conn.execute(
                """SELECT pc.*
                   FROM progress_checkpoints pc
                   WHERE pc.student_id = ?
                   ORDER BY pc.checkpoint_date ASC""",
                (student_id,),
            ).fetchall()
            return {
                "baselines": [dict(r) for r in baseline_rows],
                "checkpoints": [dict(r) for r in checkpoint_rows],
            }
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Return summary statistics for baselines and checkpoints."""
        conn = self._conn()
        try:
            totals = conn.execute(
                "SELECT COUNT(*) AS total_baselines FROM baseline_assessments"
            ).fetchone()
            total_baselines = totals["total_baselines"] if totals else 0

            by_type_rows = conn.execute(
                """SELECT assessment_type, COUNT(*) AS cnt
                   FROM baseline_assessments
                   GROUP BY assessment_type"""
            ).fetchall()
            by_type = {r["assessment_type"]: r["cnt"] for r in by_type_rows}

            cp_totals = conn.execute(
                "SELECT COUNT(*) AS total_checkpoints FROM progress_checkpoints"
            ).fetchone()
            total_checkpoints = cp_totals["total_checkpoints"] if cp_totals else 0

            avgs = conn.execute(
                """SELECT AVG(english_score) AS avg_english,
                          AVG(maths_score)   AS avg_maths,
                          AVG(ict_score)     AS avg_ict
                   FROM baseline_assessments"""
            ).fetchone()

            return {
                "total_baselines": total_baselines,
                "by_type": by_type,
                "total_checkpoints": total_checkpoints,
                "avg_english": round(avgs["avg_english"], 2) if avgs and avgs["avg_english"] else None,
                "avg_maths": round(avgs["avg_maths"], 2) if avgs and avgs["avg_maths"] else None,
                "avg_ict": round(avgs["avg_ict"], 2) if avgs and avgs["avg_ict"] else None,
            }
        finally:
            conn.close()
