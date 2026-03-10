"""School calendar service."""

import logging
from education_system.secondary_school.core.exceptions import CalendarError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

EVENT_TYPES = ("general", "term_date", "inset_day", "exam_period", "parents_evening",
               "sports_day", "trip", "assembly", "open_day", "holiday")


class CalendarService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_event(self, title, date, event_type="general", description=None,
                  end_date=None, start_time=None, end_time=None, location=None,
                  year_group=None, is_whole_school=False, created_by=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO school_events (title, description, event_type, date, end_date,
                   start_time, end_time, location, year_group, is_whole_school, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, event_type, date, end_date, start_time, end_time,
                 location, year_group, int(is_whole_school), created_by))
            conn.commit()
            row = conn.execute("SELECT * FROM school_events WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise CalendarError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_events(self, event_type=None, year_group=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM school_events WHERE 1=1"
            params = []
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            if year_group:
                sql += " AND (year_group = ? OR is_whole_school = 1)"
                params.append(year_group)
            sql += " ORDER BY date"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_event(self, event_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM school_events WHERE id = ?", (event_id,))
            conn.commit()
        finally:
            conn.close()
