"""Trip management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import TripsError
import traceback

logger = logging.getLogger(__name__)


class TripService:
    """CRUD operations for school trips and attendees."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_trip(self, trip_name, trip_date, destination=None, description=None,
                    return_date=None, year_groups=None, lead_staff_id=None,
                    cost=0, max_places=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO trips (
                    trip_name, trip_date, destination, description,
                    return_date, year_groups, lead_staff_id, cost, max_places
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trip_name, trip_date, destination, description,
                    return_date, year_groups, lead_staff_id, cost, max_places,
                ),
            )
            conn.commit()
            trip_id = cursor.lastrowid
            logger.info("Created trip: %s (id=%s)", trip_name, trip_id)
            return {"id": trip_id, "trip_name": trip_name, "trip_date": trip_date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TripsError(f"Failed to create trip: {e}") from e
        finally:
            conn.close()

    def get_trip(self, trip_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_trips(self, status=None, year_groups=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM trips WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_groups:
                sql += " AND year_groups LIKE ?"
                params.append(f"%{year_groups}%")
            sql += " ORDER BY trip_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_trip(self, trip_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "trip_name", "trip_date", "destination", "description",
                "return_date", "year_groups", "lead_staff_id", "cost",
                "max_places", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(trip_id)
            cursor.execute(
                f"UPDATE trips SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated trip id=%s", trip_id)
            return self.get_trip(trip_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TripsError(f"Failed to update trip: {e}") from e
        finally:
            conn.close()

    def delete_trip(self, trip_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trip_attendees WHERE trip_id = ?", (trip_id,))
            cursor.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted trip id=%s", trip_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TripsError(f"Failed to delete trip: {e}") from e
        finally:
            conn.close()

    def add_attendee(self, trip_id, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO trip_attendees (trip_id, pupil_id) VALUES (?, ?)",
                (trip_id, pupil_id),
            )
            conn.commit()
            logger.info("Added pupil %s to trip id=%s", pupil_id, trip_id)
            return True
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TripsError(f"Failed to add trip attendee: {e}") from e
        finally:
            conn.close()

    def update_attendee(self, trip_id, pupil_id, consent_received=None,
                        payment_received=None, medical_info=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            updates = {}
            if consent_received is not None:
                updates["consent_received"] = consent_received
            if payment_received is not None:
                updates["payment_received"] = payment_received
            if medical_info is not None:
                updates["medical_info"] = medical_info
            if not updates:
                return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.extend([trip_id, pupil_id])
            cursor.execute(
                f"UPDATE trip_attendees SET {set_clause} WHERE trip_id = ? AND pupil_id = ?",
                values,
            )
            conn.commit()
            logger.info(
                "Updated attendee pupil %s for trip id=%s", pupil_id, trip_id,
            )
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TripsError(f"Failed to update trip attendee: {e}") from e
        finally:
            conn.close()

    def get_attendees(self, trip_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT p.pupil_id, p.first_name, p.last_name, p.year_group,
                    ta.consent_received, ta.payment_received, ta.medical_info
                FROM trip_attendees ta
                JOIN pupils p ON p.pupil_id = ta.pupil_id
                WHERE ta.trip_id = ?
                ORDER BY p.last_name, p.first_name""",
                (trip_id,),
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
