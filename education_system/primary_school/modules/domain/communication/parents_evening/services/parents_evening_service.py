"""Parents evening service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ParentsEveningError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class ParentsEveningService:
    """CRUD operations for parents evening events and appointment slots."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ── Events ────────────────────────────────────────────────────────────

    def create_event(self, title, event_date, start_time=None,
                     end_time=None, slot_duration=10, year_groups=None):
        """Create a new parents evening event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO parents_evening_events (
                    title, event_date, start_time, end_time,
                    slot_duration, year_groups, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled', datetime('now'))""",
                (title, event_date, start_time, end_time,
                 slot_duration, year_groups),
            )
            conn.commit()
            event_id = cursor.lastrowid
            logger.info("Created parents evening event %s: %s on %s",
                        event_id, title, event_date)
            return {"id": event_id, "title": title, "event_date": event_date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to create parents evening event: {e}") from e
        finally:
            conn.close()

    def get_event(self, event_id):
        """Get a single parents evening event by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM parents_evening_events WHERE id = ?",
                (event_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_events(self, status=None):
        """List parents evening events with optional status filter."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM parents_evening_events WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY event_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_event(self, event_id, **kwargs):
        """Update a parents evening event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "title", "event_date", "start_time", "end_time",
                "slot_duration", "year_groups", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(event_id)
            cursor.execute(
                f"UPDATE parents_evening_events SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated parents evening event %s", event_id)
            return self.get_event(event_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to update parents evening event: {e}") from e
        finally:
            conn.close()

    def delete_event(self, event_id):
        """Delete a parents evening event and its slots."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM parents_evening_slots WHERE event_id = ?",
                (event_id,),
            )
            cursor.execute(
                "DELETE FROM parents_evening_events WHERE id = ?",
                (event_id,),
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted parents evening event %s", event_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to delete parents evening event: {e}") from e
        finally:
            conn.close()

    # ── Slots ─────────────────────────────────────────────────────────────

    def create_slot(self, event_id, teacher_staff_id, slot_time,
                    pupil_id=None, parent_name=None):
        """Create an appointment slot for a parents evening."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            status = "Booked" if pupil_id else "Available"
            cursor.execute(
                """INSERT INTO parents_evening_slots (
                    event_id, teacher_staff_id, slot_time,
                    pupil_id, parent_name, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                (event_id, teacher_staff_id, slot_time,
                 pupil_id, parent_name, status),
            )
            conn.commit()
            slot_id = cursor.lastrowid
            logger.info("Created slot %s for event %s, teacher %s at %s",
                        slot_id, event_id, teacher_staff_id, slot_time)
            return {"id": slot_id, "event_id": event_id, "status": status}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to create slot: {e}") from e
        finally:
            conn.close()

    def get_slots(self, event_id, teacher_staff_id=None, status=None):
        """Get appointment slots for a parents evening event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM parents_evening_slots WHERE event_id = ?"
            params = [event_id]
            if teacher_staff_id:
                sql += " AND teacher_staff_id = ?"
                params.append(teacher_staff_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY slot_time"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def book_slot(self, slot_id, pupil_id, parent_name):
        """Book an available slot for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE parents_evening_slots
                   SET pupil_id = ?, parent_name = ?, status = 'Booked',
                       updated_at = datetime('now')
                   WHERE id = ? AND status = 'Available'""",
                (pupil_id, parent_name, slot_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise ParentsEveningError(
                    f"Slot {slot_id} is not available for booking")
            logger.info("Booked slot %s for pupil %s", slot_id, pupil_id)
            return True
        except ParentsEveningError:
            raise
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to book slot: {e}") from e
        finally:
            conn.close()

    def cancel_slot(self, slot_id):
        """Cancel a booked slot, making it available again."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE parents_evening_slots
                   SET pupil_id = NULL, parent_name = NULL,
                       status = 'Available', updated_at = datetime('now')
                   WHERE id = ?""",
                (slot_id,),
            )
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info("Cancelled slot %s", slot_id)
            return updated
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ParentsEveningError(
                f"Failed to cancel slot: {e}") from e
        finally:
            conn.close()
