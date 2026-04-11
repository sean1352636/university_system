"""Room booking service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import RoomBookingError
import traceback

logger = logging.getLogger(__name__)


class RoomBookingService:
    """CRUD operations for room bookings."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_booking(self, room_name, booked_by, booking_date, start_time,
                       end_time, purpose=None, recurring=0):
        """Create a new room booking."""
        if not self.check_availability(room_name, booking_date,
                                       start_time, end_time):
            raise RoomBookingError(
                f"Room '{room_name}' is not available on {booking_date} "
                f"from {start_time} to {end_time}")
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO room_bookings (
                    room_name, booked_by, booking_date, start_time,
                    end_time, purpose, recurring, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Confirmed', datetime('now'))""",
                (room_name, booked_by, booking_date, start_time,
                 end_time, purpose, recurring),
            )
            conn.commit()
            booking_id = cursor.lastrowid
            logger.info("Created room booking %s: %s on %s %s-%s",
                        booking_id, room_name, booking_date,
                        start_time, end_time)
            return {"id": booking_id, "room_name": room_name,
                    "booking_date": booking_date}
        except RoomBookingError:
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RoomBookingError(
                f"Failed to create room booking: {e}") from e
        finally:
            conn.close()

    def get_booking(self, booking_id):
        """Get a single room booking by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM room_bookings WHERE id = ?", (booking_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_bookings(self, room_name=None, booking_date=None,
                      booked_by=None):
        """List room bookings with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM room_bookings WHERE 1=1"
            params = []
            if room_name:
                sql += " AND room_name = ?"
                params.append(room_name)
            if booking_date:
                sql += " AND booking_date = ?"
                params.append(booking_date)
            if booked_by:
                sql += " AND booked_by = ?"
                params.append(booked_by)
            sql += " ORDER BY booking_date, start_time"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_booking(self, booking_id, **kwargs):
        """Update a room booking."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in (
                "booked_by", "booking_date", "end_time", "purpose",
                "recurring", "room_name", "start_time", "status",
            ):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
            values.append(booking_id)
            cursor.execute(
                f"UPDATE room_bookings SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated room booking %s", booking_id)
            return self.get_booking(booking_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RoomBookingError(
                f"Failed to update room booking: {e}") from e
        finally:
            conn.close()

    def delete_booking(self, booking_id):
        """Delete a room booking."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM room_bookings WHERE id = ?", (booking_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted room booking %s", booking_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise RoomBookingError(
                f"Failed to delete room booking: {e}") from e
        finally:
            conn.close()

    def check_availability(self, room_name, booking_date, start_time,
                           end_time):
        """Check if a room is available for the given date and time range."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT COUNT(*) FROM room_bookings
                   WHERE room_name = ?
                     AND booking_date = ?
                     AND status != 'Cancelled'
                     AND start_time < ?
                     AND end_time > ?""",
                (room_name, booking_date, end_time, start_time),
            )
            return cursor.fetchone()[0] == 0
        finally:
            conn.close()
