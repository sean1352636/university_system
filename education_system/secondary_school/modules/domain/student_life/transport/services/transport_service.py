"""School transport service."""

import logging
from education_system.secondary_school.core.exceptions import TransportError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

VEHICLE_TYPES = ("bus", "minibus", "coach", "taxi")


class TransportService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Routes ---

    def create_route(self, route_name, operator=None, vehicle_type="bus",
                     capacity=None, driver_name=None, driver_phone=None,
                     departure_time=None, return_time=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO transport_routes
                   (route_name, operator, vehicle_type, capacity, driver_name,
                    driver_phone, departure_time, return_time, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (route_name, operator, vehicle_type, capacity, driver_name,
                 driver_phone, departure_time, return_time, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM transport_routes WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise TransportError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_routes(self, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM transport_routes WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY route_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_route(self, route_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM transport_students WHERE route_id = ?", (route_id,))
            conn.execute("DELETE FROM transport_stops WHERE route_id = ?", (route_id,))
            conn.execute("DELETE FROM transport_routes WHERE id = ?", (route_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Stops ---

    def add_stop(self, route_id, stop_name, pickup_time=None, dropoff_time=None, sort_order=0):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO transport_stops (route_id, stop_name, pickup_time, dropoff_time, sort_order) VALUES (?, ?, ?, ?, ?)",
                (route_id, stop_name, pickup_time, dropoff_time, sort_order))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise TransportError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_stops(self, route_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM transport_stops WHERE route_id = ? ORDER BY sort_order", (route_id,)).fetchall()]
        finally:
            conn.close()

    # --- Students ---

    def assign_student(self, route_id, student_id, stop_id=None):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO transport_students (route_id, student_id, stop_id) VALUES (?, ?, ?)",
                (route_id, student_id, stop_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise TransportError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_route_students(self, route_id):
        conn = self._conn()
        try:
            sql = """SELECT ts.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group,
                     tp.stop_name
                     FROM transport_students ts
                     JOIN students s ON ts.student_id = s.id
                     LEFT JOIN transport_stops tp ON ts.stop_id = tp.id
                     WHERE ts.route_id = ?
                     ORDER BY s.last_name"""
            return [dict(r) for r in conn.execute(sql, (route_id,)).fetchall()]
        finally:
            conn.close()

    def remove_student(self, transport_student_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM transport_students WHERE id = ?", (transport_student_id,))
            conn.commit()
        finally:
            conn.close()

    def student_count(self, route_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM transport_students WHERE route_id = ? AND status = 'active'",
                               (route_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
