"""Trips & Visits service."""

import logging
from education_system.secondary_school.core.exceptions import TripsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

TRIP_STATUSES = ("planned", "approved", "in_progress", "completed", "cancelled")


class TripsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_trip(self, title, date, destination=None, return_date=None,
                    departure_time=None, return_time=None, year_group=None,
                    lead_teacher=None, max_students=None, cost_per_student=0.0,
                    transport=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO trips
                   (title, destination, date, return_date, departure_time, return_time,
                    year_group, lead_teacher, max_students, cost_per_student, transport, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, destination, date, return_date, departure_time, return_time,
                 year_group, lead_teacher, max_students, cost_per_student, transport, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM trips WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise TripsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_trips(self, status=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM trips WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_status(self, trip_id, status):
        conn = self._conn()
        try:
            conn.execute("UPDATE trips SET status = ? WHERE id = ?", (status, trip_id))
            conn.commit()
        finally:
            conn.close()

    def mark_risk_assessment(self, trip_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE trips SET risk_assessment_done = 1 WHERE id = ?", (trip_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_trip(self, trip_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM trip_students WHERE trip_id = ?", (trip_id,))
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Trip Students ---

    def add_student(self, trip_id, student_id, emergency_contact=None, emergency_phone=None, medical_notes=None):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO trip_students (trip_id, student_id, emergency_contact, emergency_phone, medical_notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (trip_id, student_id, emergency_contact, emergency_phone, medical_notes))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise TripsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_trip_students(self, trip_id):
        conn = self._conn()
        try:
            sql = """SELECT ts.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM trip_students ts
                     JOIN students s ON ts.student_id = s.id
                     WHERE ts.trip_id = ?
                     ORDER BY s.last_name"""
            return [dict(r) for r in conn.execute(sql, (trip_id,)).fetchall()]
        finally:
            conn.close()

    def update_consent(self, trip_student_id, consent=True):
        conn = self._conn()
        try:
            conn.execute("UPDATE trip_students SET consent_received = ? WHERE id = ?",
                         (int(consent), trip_student_id))
            conn.commit()
        finally:
            conn.close()

    def update_payment(self, trip_student_id, paid=True):
        conn = self._conn()
        try:
            conn.execute("UPDATE trip_students SET paid = ? WHERE id = ?",
                         (int(paid), trip_student_id))
            conn.commit()
        finally:
            conn.close()

    def remove_student(self, trip_student_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM trip_students WHERE id = ?", (trip_student_id,))
            conn.commit()
        finally:
            conn.close()
