"""PayrollService service for the Primary School."""

import logging
import traceback
from datetime import datetime

from education_system.primary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class PayrollService:
    """CRUD operations for payroll record."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        """Create a new payroll record record."""
        conn = self._conn()
        try:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO payroll_records ({cols}) VALUES ({placeholders})",
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
        """List payroll record records with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM payroll_records WHERE 1=1"
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
        """Get a single payroll record by ID."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payroll_records WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        """Update a payroll record record."""
        if not kwargs:
            return False
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [record_id]
            conn.execute(
                f"UPDATE payroll_records SET {set_clause} WHERE id = ?",
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
        """Delete a payroll record record."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM payroll_records WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

