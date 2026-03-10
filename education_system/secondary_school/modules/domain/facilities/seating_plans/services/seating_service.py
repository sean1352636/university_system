"""Seating Plans service."""

import logging
from education_system.secondary_school.core.exceptions import SeatingPlanError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class SeatingService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_plan(self, name, room, subject_id=None, year_group=None,
                    teacher=None, rows=5, columns=6):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO seating_plans
                   (name, room, subject_id, year_group, teacher, rows, columns)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, room, subject_id, year_group, teacher, rows, columns))
            conn.commit()
            return dict(conn.execute("SELECT * FROM seating_plans WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise SeatingPlanError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_plans(self, room=None, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM seating_plans WHERE 1=1"
            params = []
            if room:
                sql += " AND room = ?"
                params.append(room)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_plan(self, plan_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM seating_assignments WHERE plan_id = ?", (plan_id,))
            conn.execute("DELETE FROM seating_plans WHERE id = ?", (plan_id,))
            conn.commit()
        finally:
            conn.close()

    def assign_seat(self, plan_id, student_id, seat_row, seat_col):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO seating_assignments
                   (plan_id, student_id, seat_row, seat_col)
                   VALUES (?, ?, ?, ?)""",
                (plan_id, student_id, seat_row, seat_col))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise SeatingPlanError(f"Failed: {e}") from e
        finally:
            conn.close()

    def remove_seat(self, assignment_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM seating_assignments WHERE id = ?", (assignment_id,))
            conn.commit()
        finally:
            conn.close()

    def list_assignments(self, plan_id):
        conn = self._conn()
        try:
            sql = """SELECT sa.*, s.first_name, s.last_name, s.student_id AS stu_code
                     FROM seating_assignments sa
                     JOIN students s ON sa.student_id = s.id
                     WHERE sa.plan_id = ?
                     ORDER BY sa.seat_row, sa.seat_col"""
            return [dict(r) for r in conn.execute(sql, (plan_id,)).fetchall()]
        finally:
            conn.close()

    def seat_count(self, plan_id):
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM seating_assignments WHERE plan_id = ?",
                (plan_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
