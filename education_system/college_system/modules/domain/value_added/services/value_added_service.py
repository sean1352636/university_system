"""Value-Added Analysis service."""

from education_system.college_system.core.exceptions import ValueAddedError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class ValueAddedService:
    """Value-Added Analysis service."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def set_baseline(self, student_id: int, academic_year: str | None = None,
                     gcse_average: float | None = None, gcse_english: int | None = None,
                     gcse_maths: int | None = None, data_source: str = "gcse") -> dict:
        conn = self._conn()
        try:
            baseline = gcse_average or 0
            conn.execute(
                """INSERT INTO value_added_baselines
                   (student_id, academic_year, gcse_average, gcse_english, gcse_maths, baseline_score, data_source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, academic_year, gcse_average, gcse_english, gcse_maths, baseline, data_source),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM value_added_baselines WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ValueAddedError(f"Failed to set baseline: {e}") from e
        finally:
            conn.close()

    def get_baseline(self, student_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM value_added_baselines WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def set_prediction(self, student_id: int, course_id: int, predicted_grade: str,
                       target_grade: str | None = None, academic_year: str | None = None) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO value_added_predictions
                   (student_id, course_id, academic_year, predicted_grade, target_grade)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, course_id, academic_year, predicted_grade, target_grade),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM value_added_predictions WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ValueAddedError(f"Failed to set prediction: {e}") from e
        finally:
            conn.close()

    def update_actual_grade(self, prediction_id: int, actual_grade: str) -> dict:
        grade_map = {"A*": 6, "A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "U": 0}
        conn = self._conn()
        try:
            pred = conn.execute("SELECT * FROM value_added_predictions WHERE id = ?", (prediction_id,)).fetchone()
            if not pred:
                raise ValueAddedError("Prediction not found.")
            predicted_val = grade_map.get(pred["predicted_grade"], 0)
            actual_val = grade_map.get(actual_grade, 0)
            va_score = actual_val - predicted_val
            conn.execute(
                "UPDATE value_added_predictions SET actual_grade = ?, value_added_score = ?, updated_at = datetime('now') WHERE id = ?",
                (actual_grade, va_score, prediction_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM value_added_predictions WHERE id = ?", (prediction_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ValueAddedError(f"Failed to update grade: {e}") from e
        finally:
            conn.close()

    def list_predictions(self, student_id: int | None = None, course_id: int | None = None,
                         academic_year: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = """SELECT p.*, s.first_name, s.last_name, s.student_id as sid, c.title as course_title
                     FROM value_added_predictions p
                     JOIN students s ON p.student_id = s.id
                     JOIN courses c ON p.course_id = c.id WHERE 1=1"""
            params: list = []
            if student_id:
                sql += " AND p.student_id = ?"
                params.append(student_id)
            if course_id:
                sql += " AND p.course_id = ?"
                params.append(course_id)
            if academic_year:
                sql += " AND p.academic_year = ?"
                params.append(academic_year)
            sql += " ORDER BY p.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_subject_value_added(self, course_id: int, academic_year: str | None = None) -> dict:
        conn = self._conn()
        try:
            sql = "SELECT AVG(value_added_score) as avg_va, COUNT(*) as count FROM value_added_predictions WHERE course_id = ? AND value_added_score IS NOT NULL"
            params: list = [course_id]
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            row = conn.execute(sql, params).fetchone()
            return {"average_value_added": row["avg_va"] or 0, "student_count": row["count"]}
        finally:
            conn.close()

    def get_college_value_added(self, academic_year: str | None = None) -> dict:
        conn = self._conn()
        try:
            sql = "SELECT AVG(value_added_score) as avg_va, COUNT(*) as count FROM value_added_predictions WHERE value_added_score IS NOT NULL"
            params: list = []
            if academic_year:
                sql += " AND academic_year = ?"
                params.append(academic_year)
            row = conn.execute(sql, params).fetchone()
            return {"average_value_added": row["avg_va"] or 0, "student_count": row["count"]}
        finally:
            conn.close()

