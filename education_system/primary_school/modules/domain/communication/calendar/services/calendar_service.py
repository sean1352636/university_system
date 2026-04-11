"""Calendar service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import CalendarError
import traceback

logger = logging.getLogger(__name__)


class CalendarService:
    """CRUD operations for school calendar events."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_event(self, title, start_date, end_date=None, start_time=None,
                     end_time=None, description=None, event_type="General",
                     location=None, all_day=0, year_groups=None,
                     created_by=None):
        """Create a new calendar event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO calendar_events (
                    title, start_date, end_date, start_time, end_time,
                    description, event_type, location, all_day,
                    year_groups, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (title, start_date, end_date or start_date, start_time,
                 end_time, description, event_type, location, all_day,
                 year_groups, created_by),
            )
            conn.commit()
            event_id = cursor.lastrowid
            logger.info("Created calendar event %s: %s on %s",
                        event_id, title, start_date)
            return {"id": event_id, "title": title, "start_date": start_date}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CalendarError(f"Failed to create calendar event: {e}") from e
        finally:
            conn.close()

    def get_event(self, event_id):
        """Get a single calendar event by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM calendar_events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_events(self, date_from=None, date_to=None, event_type=None,
                    year_groups=None):
        """List calendar events with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM calendar_events WHERE 1=1"
            params = []
            if date_from:
                sql += " AND start_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND start_date <= ?"
                params.append(date_to)
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            if year_groups:
                sql += " AND year_groups LIKE ?"
                params.append(f"%{year_groups}%")
            sql += " ORDER BY start_date, start_time"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_event(self, event_id, **kwargs):
        """Update a calendar event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in ("all_day", "description", "end_date", "end_time",
                        "event_type", "location", "start_date", "start_time",
                        "title", "year_groups"):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
            values.append(event_id)
            cursor.execute(
                f"UPDATE calendar_events SET {set_clause}, "
                "updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated calendar event %s", event_id)
            return self.get_event(event_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CalendarError(
                f"Failed to update calendar event: {e}") from e
        finally:
            conn.close()

    def delete_event(self, event_id):
        """Delete a calendar event."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM calendar_events WHERE id = ?", (event_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("Deleted calendar event %s", event_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CalendarError(
                f"Failed to delete calendar event: {e}") from e
        finally:
            conn.close()
