"""Consent management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import ConsentError
from education_system.primary_school.core.sql_safety import validate_identifier
import traceback

logger = logging.getLogger(__name__)


class ConsentService:
    """CRUD operations for parental consent records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, pupil_id, consent_type, description=None,
                      granted=0, granted_by=None, granted_date=None,
                      expiry_date=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO consent_records (
                    pupil_id, consent_type, description, granted,
                    granted_by, granted_date, expiry_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, consent_type, description, granted,
                    granted_by, granted_date, expiry_date, notes,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Created consent record for pupil %s type=%s (id=%s)",
                pupil_id, consent_type, record_id,
            )
            return {"id": record_id, "pupil_id": pupil_id, "consent_type": consent_type}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ConsentError(f"Failed to create consent record: {e}") from e
        finally:
            conn.close()

    def get_records(self, pupil_id=None, consent_type=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM consent_records WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            if consent_type:
                sql += " AND consent_type = ?"
                params.append(consent_type)
            sql += " ORDER BY pupil_id, consent_type"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "consent_type", "description", "granted", "granted_by",
                "granted_date", "expiry_date", "notes",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            values = list(updates.values())
            values.append(record_id)
            cursor.execute(
                f"UPDATE consent_records SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated consent record id=%s", record_id)
            cursor.execute(
                "SELECT * FROM consent_records WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ConsentError(f"Failed to update consent record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM consent_records WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted consent record id=%s", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise ConsentError(f"Failed to delete consent record: {e}") from e
        finally:
            conn.close()

    def get_outstanding_consents(self, consent_type=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = """SELECT cr.*, p.first_name, p.last_name, p.year_group, p.class_name
                FROM consent_records cr
                JOIN pupils p ON p.pupil_id = cr.pupil_id
                WHERE cr.granted = 0"""
            params = []
            if consent_type:
                sql += " AND cr.consent_type = ?"
                params.append(consent_type)
            sql += " ORDER BY p.last_name, p.first_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
