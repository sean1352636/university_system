"""Parents evening service."""

import logging
from education_system.secondary_school.core.exceptions import ParentsEveningError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class ParentsEveningService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_event(self, title, date, year_group=None, start_time="16:00",
                     end_time="19:00", slot_duration_minutes=5):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO parents_evening_events (title, year_group, date, start_time, end_time, slot_duration_minutes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, year_group, date, start_time, end_time, slot_duration_minutes))
            conn.commit()
            row = conn.execute("SELECT * FROM parents_evening_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise ParentsEveningError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_events(self):
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM parents_evening_events ORDER BY date DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_event(self, event_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM parents_evening_slots WHERE event_id = ?", (event_id,))
            conn.execute("DELETE FROM parents_evening_events WHERE id = ?", (event_id,))
            conn.commit()
        finally:
            conn.close()

    def book_slot(self, event_id, teacher, student_id, time_slot, parent_name=None):
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM parents_evening_slots WHERE event_id = ? AND teacher = ? AND time_slot = ?",
                (event_id, teacher, time_slot)).fetchone()
            if existing:
                raise ParentsEveningError(f"Slot {time_slot} with {teacher} is already booked.")
            cursor = conn.execute(
                """INSERT INTO parents_evening_slots (event_id, teacher, student_id, time_slot, parent_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_id, teacher, student_id, time_slot, parent_name))
            conn.commit()
            row = conn.execute("SELECT * FROM parents_evening_slots WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except ParentsEveningError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise ParentsEveningError(f"Failed to book: {e}") from e
        finally:
            conn.close()

    def list_slots(self, event_id):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT ps.*, s.student_id as sid, s.first_name, s.last_name
                   FROM parents_evening_slots ps JOIN students s ON ps.student_id = s.id
                   WHERE ps.event_id = ? ORDER BY ps.time_slot, ps.teacher""",
                (event_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def cancel_slot(self, slot_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM parents_evening_slots WHERE id = ?", (slot_id,))
            conn.commit()
        finally:
            conn.close()
