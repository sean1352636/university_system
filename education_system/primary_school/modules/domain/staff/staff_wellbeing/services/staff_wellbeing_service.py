"""StaffWellbeingService service for the Primary School."""

import logging
import traceback
from datetime import datetime

from education_system.primary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class StaffWellbeingService:
    """CRUD operations for staff wellbeing."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        """Create a new staff wellbeing record."""
        conn = self._conn()
        try:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO staff_wellbeing_surveys ({cols}) VALUES ({placeholders})",
                list(kwargs.values()),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        """List staff wellbeing records with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM staff_wellbeing_surveys WHERE 1=1"
            params = []
            for key, val in filters.items():
                if val is not None:
                    sql += f" AND {key} = ?"
                    params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        """Get a single staff wellbeing by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM staff_wellbeing_surveys WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        """Update a staff wellbeing record."""
        if not kwargs:
            return False
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [record_id]
            conn.execute(
                f"UPDATE staff_wellbeing_surveys SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        """Delete a staff wellbeing record."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM staff_wellbeing_surveys WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

