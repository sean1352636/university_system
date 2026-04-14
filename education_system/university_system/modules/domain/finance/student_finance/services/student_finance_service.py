"""StudentFinanceService service for the University System."""

import logging
import traceback
from datetime import datetime

from education_system.university_system.infrastructure.database.db import connect
from education_system.university_system.core.sql_safety import validate_identifier

logger = logging.getLogger(__name__)


class StudentFinanceService:
    """CRUD operations for fee record."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        """Create a new fee record record."""
        conn = self._conn()
        try:
            cols = ", ".join(validate_identifier(k, "column") for k in kwargs)
            placeholders = ", ".join("?" for _ in kwargs)
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO student_fees ({cols}) VALUES ({placeholders})",
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
        """List fee record records with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM student_fees WHERE 1=1"
            params = []
            for key, val in filters.items():
                if val is not None:
                    sql += f" AND {validate_identifier(key, 'column')} = ?"
                    params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        """Get a single fee record by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM student_fees WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        """Update a fee record record."""
        if not kwargs:
            return False
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k, 'column')} = ?" for k in kwargs)
            values = list(kwargs.values()) + [record_id]
            conn.execute(
                f"UPDATE student_fees SET {set_clause} WHERE id = ?",
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
        """Delete a fee record record."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM student_fees WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

