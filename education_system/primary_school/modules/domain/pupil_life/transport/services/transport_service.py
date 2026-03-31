"""Transport management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import TransportError
from education_system.primary_school.core.sql_safety import validate_identifier  # nosec B608
import traceback

logger = logging.getLogger(__name__)


class TransportService:
    """CRUD operations for pupil transport records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, pupil_id, transport_type, route=None,
                      pickup_point=None, pickup_time=None, dropoff_time=None,
                      contact_name=None, contact_phone=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO transport (
                    pupil_id, transport_type, route, pickup_point,
                    pickup_time, dropoff_time, contact_name, contact_phone, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, transport_type, route, pickup_point,
                    pickup_time, dropoff_time, contact_name, contact_phone, notes,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Created transport record for pupil %s (id=%s)",
                pupil_id, record_id,
            )
            return {"id": record_id, "pupil_id": pupil_id, "transport_type": transport_type}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TransportError(f"Failed to create transport record: {e}") from e
        finally:
            conn.close()

    def get_record(self, record_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transport WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_records(self, transport_type=None, status="Active"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM transport WHERE 1=1"
            params = []
            if transport_type:
                sql += " AND transport_type = ?"
                params.append(transport_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY pupil_id"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "transport_type", "route", "pickup_point", "pickup_time",
                "dropoff_time", "contact_name", "contact_phone", "notes", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(record_id)
            cursor.execute(
                f"UPDATE transport SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated transport record id=%s", record_id)
            return self.get_record(record_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TransportError(f"Failed to update transport record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transport WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted transport record id=%s", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise TransportError(f"Failed to delete transport record: {e}") from e
        finally:
            conn.close()
