"""Calendar event management service."""

from datetime import datetime

from education_system.college_system.core.exceptions import CalendarError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)

_EVENT_TYPES = ("personal", "academic", "college", "deadline")


class CalendarService:
    """Service for managing calendar events."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_event(self, user_id: int | None, title: str, event_date: str,
                     start_time: str | None = None, end_time: str | None = None,
                     event_type: str = "personal", description: str | None = None,
                     is_all_day: bool = False) -> dict:
        """Create a new calendar event."""
        if not title or not title.strip():
            raise CalendarError("Title is required.")
        if not event_date:
            raise CalendarError("Event date is required.")
        if event_type not in _EVENT_TYPES:
            raise CalendarError(f"Event type must be one of: {', '.join(_EVENT_TYPES)}")

        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO calendar_events
                   (user_id, title, description, event_date, start_time, end_time,
                    event_type, is_all_day)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, title.strip(), description, event_date, start_time,
                 end_time, event_type, 1 if is_all_day else 0),
            )
            conn.commit()
            event_id = cursor.lastrowid
            logger.info("Calendar event created: id=%d", event_id)
            return self._get_event_by_id(conn, event_id)
        except CalendarError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CalendarError(f"Failed to create event: {e}") from e
        finally:
            conn.close()

    def _get_event_by_id(self, conn, event_id: int) -> dict:
        row = conn.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            raise CalendarError("Event not found.")
        return dict(row)

    def list_events(self, user_id: int | None = None,
                    month: int | None = None, year: int | None = None) -> list[dict]:
        """List calendar events with optional filters."""
        conn = self._conn()
        try:
            conditions = []
            params: list = []

            if user_id is not None:
                conditions.append("(user_id = ? OR event_type = 'college')")
                params.append(user_id)

            if month is not None and year is not None:
                conditions.append(
                    "substr(event_date, 1, 7) = ?"
                )
                params.append(f"{year:04d}-{month:02d}")

            sql = "SELECT * FROM calendar_events"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY event_date, start_time"

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_events_for_date(self, user_id: int, date_str: str) -> list[dict]:
        """Get events for a specific date."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM calendar_events
                   WHERE event_date = ? AND (user_id = ? OR event_type = 'college')
                   ORDER BY start_time""",
                (date_str, user_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_event(self, event_id: int, user_id: int, is_admin: bool = False,
                     **kwargs) -> dict:
        """Update a calendar event (verify ownership or admin)."""
        conn = self._conn()
        try:
            event = conn.execute("SELECT * FROM calendar_events WHERE id = ?",
                                 (event_id,)).fetchone()
            if not event:
                raise CalendarError("Event not found.")
            if not is_admin and event["user_id"] != user_id:
                raise CalendarError("You can only edit your own events.")

            set_parts: list[str] = []
            vals: list = []
            for col in ("description", "end_time", "event_date", "event_type",
                        "is_all_day", "start_time", "title"):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    vals.append(kwargs[col])
            if not set_parts:
                raise CalendarError("No valid fields to update.")

            sets = ", ".join(set_parts)
            vals.append(event_id)
            conn.execute(f"UPDATE calendar_events SET {sets} WHERE id = ?", vals)  # nosec B608
            conn.commit()
            logger.info("Calendar event updated: id=%d", event_id)
            return self._get_event_by_id(conn, event_id)
        except CalendarError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CalendarError(f"Failed to update event: {e}") from e
        finally:
            conn.close()

    def delete_event(self, event_id: int, user_id: int,
                     is_admin: bool = False) -> bool:
        """Delete a calendar event (verify ownership or admin)."""
        conn = self._conn()
        try:
            event = conn.execute("SELECT * FROM calendar_events WHERE id = ?",
                                 (event_id,)).fetchone()
            if not event:
                raise CalendarError("Event not found.")
            if not is_admin and event["user_id"] != user_id:
                raise CalendarError("You can only delete your own events.")

            conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
            conn.commit()
            logger.info("Calendar event deleted: id=%d", event_id)
            return True
        except CalendarError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise CalendarError(f"Failed to delete event: {e}") from e
        finally:
            conn.close()
