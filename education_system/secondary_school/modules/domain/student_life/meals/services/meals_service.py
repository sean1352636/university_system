"""School meals service."""

import logging
from education_system.secondary_school.core.exceptions import MealsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

MEAL_PREFERENCES = ("standard", "vegetarian", "vegan", "halal", "kosher", "gluten_free", "other")
MEAL_TYPES = ("breakfast", "lunch", "snack")


class MealsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Registrations ---

    def register_student(self, student_id, free_school_meals=False,
                         dietary_requirements=None, allergies=None,
                         meal_preference="standard", notes=None):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO meal_registrations
                   (student_id, free_school_meals, dietary_requirements, allergies, meal_preference, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, int(free_school_meals), dietary_requirements, allergies, meal_preference, notes))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MealsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_registrations(self, fsm_only=False):
        conn = self._conn()
        try:
            sql = """SELECT mr.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM meal_registrations mr
                     JOIN students s ON mr.student_id = s.id
                     WHERE mr.status = 'active'"""
            if fsm_only:
                sql += " AND mr.free_school_meals = 1"
            sql += " ORDER BY s.last_name"
            return [dict(r) for r in conn.execute(sql).fetchall()]
        finally:
            conn.close()

    def delete_registration(self, reg_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM meal_registrations WHERE id = ?", (reg_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Bookings ---

    def book_meal(self, student_id, date, meal_type="lunch", menu_choice=None):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO meal_bookings (student_id, date, meal_type, menu_choice) VALUES (?, ?, ?, ?)",
                (student_id, date, meal_type, menu_choice))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise MealsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_bookings(self, date=None, student_id=None):
        conn = self._conn()
        try:
            sql = """SELECT mb.*, s.first_name, s.last_name, s.student_id as stu_code
                     FROM meal_bookings mb
                     JOIN students s ON mb.student_id = s.id WHERE 1=1"""
            params = []
            if date:
                sql += " AND mb.date = ?"
                params.append(date)
            if student_id:
                sql += " AND mb.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY mb.date DESC, s.last_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def cancel_booking(self, booking_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE meal_bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            conn.commit()
        finally:
            conn.close()

    def fsm_count(self):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM meal_registrations WHERE free_school_meals = 1 AND status = 'active'").fetchone()
            return row["cnt"]
        finally:
            conn.close()
