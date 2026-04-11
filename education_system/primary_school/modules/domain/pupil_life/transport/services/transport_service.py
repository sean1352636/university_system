"""Transport management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import TransportError
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
            set_parts: list[str] = []
            values: list = []
            for col in (
                "contact_name", "contact_phone", "dropoff_time", "notes",
                "pickup_point", "pickup_time", "route", "status",
                "transport_type",
            ):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
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
