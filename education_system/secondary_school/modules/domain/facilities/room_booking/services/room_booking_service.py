"""Room booking service."""

import logging
from education_system.secondary_school.core.exceptions import RoomBookingError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class RoomBookingService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def book_room(self, room, date, start_time, end_time, purpose,
                  booked_by=None, equipment_needed=None, notes=None):
        conn = self._conn()
        try:
            # Check for clashes
            clash = conn.execute(
                """SELECT id FROM room_bookings
                   WHERE room = ? AND date = ? AND status = 'confirmed'
                   AND start_time < ? AND end_time > ?""",
                (room, date, end_time, start_time)).fetchone()
            if clash:
                raise RoomBookingError("Room already booked for this time slot.")
            cursor = conn.execute(
                """INSERT INTO room_bookings
                   (room, date, start_time, end_time, purpose, booked_by, equipment_needed, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (room, date, start_time, end_time, purpose, booked_by, equipment_needed, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM room_bookings WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except RoomBookingError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RoomBookingError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_bookings(self, room=None, date=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM room_bookings WHERE 1=1"
            params = []
            if room:
                sql += " AND room = ?"
                params.append(room)
            if date:
                sql += " AND date = ?"
                params.append(date)
            sql += " ORDER BY date, start_time"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def cancel_booking(self, booking_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE room_bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_booking(self, booking_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM room_bookings WHERE id = ?", (booking_id,))
            conn.commit()
        finally:
            conn.close()

    def get_rooms(self):
        conn = self._conn()
        try:
            rows = conn.execute("SELECT DISTINCT room FROM room_bookings ORDER BY room").fetchall()
            return [r["room"] for r in rows]
        finally:
            conn.close()
