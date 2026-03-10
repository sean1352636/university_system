"""Medical records service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import MedicalError
import traceback

logger = logging.getLogger(__name__)


class MedicalService:
    """CRUD operations for pupil medical records."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, pupil_id, condition=None, medication=None,
                      dosage=None, administration_time=None, care_plan=0,
                      allergy=None, allergy_severity=None,
                      emergency_protocol=None, doctor_name=None,
                      doctor_phone=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO medical_records (
                    pupil_id, condition, medication, dosage,
                    administration_time, care_plan, allergy, allergy_severity,
                    emergency_protocol, doctor_name, doctor_phone, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pupil_id, condition, medication, dosage,
                    administration_time, care_plan, allergy, allergy_severity,
                    emergency_protocol, doctor_name, doctor_phone, notes,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(
                "Created medical record for pupil %s (id=%s)", pupil_id, record_id,
            )
            return {"id": record_id, "pupil_id": pupil_id}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise MedicalError(f"Failed to create medical record: {e}") from e
        finally:
            conn.close()

    def get_records(self, pupil_id=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM medical_records WHERE 1=1"
            params = []
            if pupil_id:
                sql += " AND pupil_id = ?"
                params.append(pupil_id)
            sql += " ORDER BY pupil_id, created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "condition", "medication", "dosage", "administration_time",
                "care_plan", "allergy", "allergy_severity",
                "emergency_protocol", "doctor_name", "doctor_phone", "notes",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(record_id)
            cursor.execute(
                f"UPDATE medical_records SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated medical record id=%s", record_id)
            cursor.execute(
                "SELECT * FROM medical_records WHERE id = ?", (record_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise MedicalError(f"Failed to update medical record: {e}") from e
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM medical_records WHERE id = ?", (record_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted medical record id=%s", record_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise MedicalError(f"Failed to delete medical record: {e}") from e
        finally:
            conn.close()

    def get_allergies(self):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT mr.*, p.first_name, p.last_name, p.year_group, p.class_name
                FROM medical_records mr
                JOIN pupils p ON p.pupil_id = mr.pupil_id
                WHERE mr.allergy IS NOT NULL AND mr.allergy != ''
                ORDER BY p.last_name, p.first_name""",
            )
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
