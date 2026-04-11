"""SEND (Special Educational Needs and Disabilities) service for the Primary School Management System."""

import logging

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import SENDError
import traceback

logger = logging.getLogger(__name__)


class SENDService:
    """CRUD operations for SEND records and provisions."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, pupil_id, sen_status, primary_need,
                      secondary_need=None, ehcp_status=None,
                      ehcp_review_date=None, funding_band=None,
                      key_worker_staff_id=None, external_agencies=None,
                      notes=None):
        """Create a SEND record for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO send_records (
                    pupil_id, sen_status, primary_need, secondary_need,
                    ehcp_status, ehcp_review_date, funding_band,
                    key_worker_staff_id, external_agencies, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, sen_status, primary_need, secondary_need,
                    ehcp_status, ehcp_review_date, funding_band,
                    key_worker_staff_id, external_agencies, notes,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Created SEND record for pupil %s (id=%s, status=%s)",
                pupil_id, record_id, sen_status,
            )
            return record_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SENDError(f"Failed to create SEND record: {e}") from e
        finally:
            conn.close()

    def get_record(self, pupil_id):
        """Get the SEND record for a pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM send_records WHERE pupil_id = ?", (pupil_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_records(self, sen_status=None, primary_need=None):
        """List SEND records with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM send_records WHERE 1=1"
            params = []
            if sen_status:
                sql += " AND sen_status = ?"
                params.append(sen_status)
            if primary_need:
                sql += " AND primary_need = ?"
                params.append(primary_need)
            sql += " ORDER BY pupil_id"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, pupil_id, **kwargs):
        """Update a SEND record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in (
                "ehcp_review_date", "ehcp_status", "external_agencies",
                "funding_band", "key_worker_staff_id", "notes",
                "primary_need", "secondary_need", "sen_status",
            ):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
            values.append(pupil_id)
            cursor.execute(
                f"UPDATE send_records SET {set_clause} WHERE pupil_id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated SEND record for pupil: %s", pupil_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SENDError(f"Failed to update SEND record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, pupil_id):
        """Delete a SEND record."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM send_records WHERE pupil_id = ?", (pupil_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted SEND record for pupil: %s", pupil_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SENDError(f"Failed to delete SEND record: {e}") from e
        finally:
            conn.close()

    def add_provision(self, pupil_id, provision_type, description=None,
                      frequency=None, delivered_by=None, start_date=None,
                      review_date=None):
        """Add a provision for a SEND pupil."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO send_provisions (
                    pupil_id, provision_type, description, frequency,
                    delivered_by, start_date, review_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')""",
                (
                    pupil_id, provision_type, description, frequency,
                    delivered_by, start_date, review_date,
                ),
            )
            conn.commit()
            provision_id = cursor.lastrowid
            logger.info(
                "Added provision for pupil %s (id=%s, type=%s)",
                pupil_id, provision_id, provision_type,
            )
            return provision_id
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SENDError(f"Failed to add provision: {e}") from e
        finally:
            conn.close()

    def get_provisions(self, pupil_id=None, status="Active"):
        """Get provisions with optional filters."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM send_provisions WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY start_date DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_provision(self, provision_id, **kwargs):
        """Update a provision."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in (
                "delivered_by", "description", "frequency",
                "provision_type", "review_date", "start_date", "status",
            ):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
            values.append(provision_id)
            cursor.execute(
                f"UPDATE send_provisions SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated provision: %s", provision_id)
            return cursor.rowcount > 0
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise SENDError(f"Failed to update provision: {e}") from e
        finally:
            conn.close()
