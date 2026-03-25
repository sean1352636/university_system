"""Cross-system calendar service stored in the shared auth database.

Provides a shared events calendar that spans all education systems, enabling
coordination of open days, transition events, training days, holidays, etc.
"""

import sqlite3
from datetime import datetime, timedelta

from education_system.shared.auth.db import AUTH_DB_FILE, connect as auth_connect
from education_system.college_system.core.sql_safety import validate_identifier

EVENT_TYPES = ("open_day", "transition", "training", "holiday", "meeting", "other")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cross_system_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT    NOT NULL,
    description     TEXT,
    event_date      TEXT    NOT NULL,
    event_time      TEXT,
    end_date        TEXT,
    systems         TEXT    NOT NULL DEFAULT 'all',
    event_type      TEXT    NOT NULL DEFAULT 'other',
    created_by      TEXT,
    created_system  TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class CrossSystemCalendarService:
    """Manage cross-system calendar events in the shared auth DB."""

    def __init__(self, db_path=None):
        self._db_path = db_path or str(AUTH_DB_FILE)
        self._ensure_table()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _conn(self):
        return auth_connect(self._db_path)

    def _ensure_table(self):
        """Create the cross_system_events table if it does not exist."""
        conn = self._conn()
        try:
            conn.executescript(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def create_event(self, title, description, date, time, end_date,
                     systems, event_type, created_by, created_system):
        """Create a new cross-system event.

        Parameters
        ----------
        title : str
        description : str
        date : str  -- ISO date (YYYY-MM-DD)
        time : str  -- HH:MM or empty
        end_date : str -- ISO date or empty
        systems : str -- comma-separated system keys or 'all'
        event_type : str -- one of EVENT_TYPES
        created_by : str -- display name or user id
        created_system : str -- system key of creator

        Returns the newly created event dict.
        """
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO cross_system_events
                   (title, description, event_date, event_time, end_date,
                    systems, event_type, created_by, created_system)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description or "", date, time or "", end_date or "",
                 systems or "all", event_type or "other",
                 created_by or "", created_system or ""),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cross_system_events WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_events(self, system=None, month=None, year=None):
        """Get events, optionally filtered by system and/or month/year.

        If *system* is given, returns events where the systems field contains
        that system key or is 'all'.
        """
        conn = self._conn()
        try:
            sql = "SELECT * FROM cross_system_events WHERE 1=1"
            params = []

            if system:
                sql += " AND (systems = 'all' OR systems LIKE ?)"
                params.append(f"%{system}%")

            if month and year:
                # Match YYYY-MM prefix
                prefix = f"{int(year):04d}-{int(month):02d}"
                sql += " AND event_date LIKE ?"
                params.append(f"{prefix}%")
            elif year:
                sql += " AND event_date LIKE ?"
                params.append(f"{int(year):04d}%")

            sql += " ORDER BY event_date, event_time"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_upcoming(self, system=None, days=30):
        """Get events in the next *days* days."""
        today = datetime.now().strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        conn = self._conn()
        try:
            sql = (
                "SELECT * FROM cross_system_events "
                "WHERE event_date >= ? AND event_date <= ?"
            )
            params = [today, end]

            if system:
                sql += " AND (systems = 'all' OR systems LIKE ?)"
                params.append(f"%{system}%")

            sql += " ORDER BY event_date, event_time"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_event(self, event_id, **fields):
        """Update an existing event. Only provided fields are changed.

        Valid field names: title, description, event_date, event_time,
        end_date, systems, event_type.
        """
        allowed = {
            "title", "description", "event_date", "event_time",
            "end_date", "systems", "event_type",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False

        set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
        params = list(updates.values()) + [event_id]

        conn = self._conn()
        try:
            conn.execute(
                f"UPDATE cross_system_events SET {set_clause} WHERE id = ?",
                params,
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_event(self, event_id):
        """Delete an event by ID."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM cross_system_events WHERE id = ?", (event_id,)
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_event(self, event_id):
        """Get a single event by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_events WHERE id = ?", (event_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
