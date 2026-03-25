"""Meal management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import MealsError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class MealService:
    """CRUD operations for school meals."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def record_meal(self, pupil_id, date, meal_type, meal_choice=None,
                    entitlement="Paid", recorded_by=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO meals (pupil_id, date, meal_type, meal_choice,
                    entitlement, recorded_by)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (pupil_id, date, meal_type, meal_choice, entitlement, recorded_by),
            )
            conn.commit()
            meal_id = cursor.lastrowid
            logger.info(
                "Recorded meal for pupil %s on %s (id=%s)", pupil_id, date, meal_id,
            )
            return {"id": meal_id, "pupil_id": pupil_id, "date": date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise MealsError(f"Failed to record meal: {e}") from e
        finally:
            conn.close()

    def get_meals(self, pupil_id=None, date=None, meal_type=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM meals WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if date:
                sql += " AND date = ?"
                params.append(date)
            if meal_type:
                sql += " AND meal_type = ?"
                params.append(meal_type)
            sql += " ORDER BY date DESC, pupil_id"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_meal(self, meal_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "meal_type", "meal_choice", "entitlement", "recorded_by",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(meal_id)
            cursor.execute(
                f"UPDATE meals SET {set_clause} WHERE id = ?", values,
            )
            conn.commit()
            logger.info("Updated meal id=%s", meal_id)
            cursor.execute("SELECT * FROM meals WHERE id = ?", (meal_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise MealsError(f"Failed to update meal: {e}") from e
        finally:
            conn.close()

    def get_daily_summary(self, date):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT meal_type, entitlement, COUNT(*) as count
                FROM meals WHERE date = ?
                GROUP BY meal_type, entitlement
                ORDER BY meal_type, entitlement""",
                (date,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
