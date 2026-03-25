"""CPD (Continuing Professional Development) service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import CPDError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class CPDService:
    """CRUD operations for CPD records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, staff_id, title, provider=None, description=None,
                      cpd_type=None, hours=None, completion_date=None,
                      certificate=None, impact=None, status="Planned"):
        """Create a CPD record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO cpd_records (
                    staff_id, title, provider, description, cpd_type,
                    hours, completion_date, certificate, impact, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    staff_id, title, provider, description, cpd_type,
                    hours, completion_date, certificate, impact, status,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Created CPD record for staff %s (id=%s, title=%s)",
                staff_id, record_id, title,
            )
            return record_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CPDError(f"Failed to create CPD record: {e}") from e
        finally:
            conn.close()

    def get_records(self, staff_id=None, status=None):
        """Retrieve CPD records with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM cpd_records WHERE 1=1"
            params = []
            if staff_id:
                sql += " AND staff_id = ?"
                params.append(staff_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY completion_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        """Update a CPD record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "title", "provider", "description", "cpd_type",
                "hours", "completion_date", "certificate", "impact", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values()) + [record_id]
            cursor.execute(
                f"UPDATE cpd_records SET {set_clause} WHERE id = ?", values,
            )
            conn.commit()
            logger.info("Updated CPD record: %s", record_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CPDError(f"Failed to update CPD record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        """Delete a CPD record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM cpd_records WHERE id = ?", (record_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted CPD record: %s", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise CPDError(f"Failed to delete CPD record: {e}") from e
        finally:
            conn.close()
