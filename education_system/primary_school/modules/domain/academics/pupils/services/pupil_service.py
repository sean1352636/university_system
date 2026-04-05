"""Pupil management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.infrastructure.validation.validators import (
    validate_non_empty, validate_year_group,
)
from education_system.primary_school.core.defaults import KEY_STAGES, PUPIL_ID_PREFIX
from education_system.primary_school.core.exceptions import PupilError
from education_system.primary_school.core.sql_safety import escape_like
import traceback

logger = logging.getLogger(__name__)


class PupilService:
    """CRUD operations for pupils."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def _generate_pupil_id(self):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pupil_id FROM pupils ORDER BY pupil_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                last_num = int(row["pupil_id"].replace(PUPIL_ID_PREFIX, ""))
                return f"{PUPIL_ID_PREFIX}{last_num + 1:04d}"
            return f"{PUPIL_ID_PREFIX}0001"
        finally:
            conn.close()

    def create_pupil(self, first_name, last_name, year_group, **kwargs):
        first_name = validate_non_empty(first_name, "First name")
        last_name = validate_non_empty(last_name, "Last name")
        year_group = validate_year_group(year_group)
        key_stage = KEY_STAGES.get(year_group, "")
        pupil_id = self._generate_pupil_id()

        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO pupils (
                    pupil_id, first_name, last_name, year_group, key_stage,
                    preferred_name, date_of_birth, gender, class_name,
                    ethnicity, first_language, eal, pupil_premium,
                    free_school_meals, sen_status, looked_after,
                    parent1_name, parent1_email, parent1_phone, parent1_relationship,
                    parent2_name, parent2_email, parent2_phone, parent2_relationship,
                    emergency_contact_name, emergency_contact_phone,
                    emergency_contact_relationship, address,
                    medical_notes, dietary_requirements, photo_consent
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (
                    pupil_id, first_name, last_name, year_group, key_stage,
                    kwargs.get("preferred_name"),
                    kwargs.get("date_of_birth"),
                    kwargs.get("gender"),
                    kwargs.get("class_name"),
                    kwargs.get("ethnicity"),
                    kwargs.get("first_language", "English"),
                    kwargs.get("eal", 0),
                    kwargs.get("pupil_premium", 0),
                    kwargs.get("free_school_meals", 0),
                    kwargs.get("sen_status", "No SEN"),
                    kwargs.get("looked_after", 0),
                    kwargs.get("parent1_name"),
                    kwargs.get("parent1_email"),
                    kwargs.get("parent1_phone"),
                    kwargs.get("parent1_relationship", "Parent"),
                    kwargs.get("parent2_name"),
                    kwargs.get("parent2_email"),
                    kwargs.get("parent2_phone"),
                    kwargs.get("parent2_relationship"),
                    kwargs.get("emergency_contact_name"),
                    kwargs.get("emergency_contact_phone"),
                    kwargs.get("emergency_contact_relationship"),
                    kwargs.get("address"),
                    kwargs.get("medical_notes"),
                    kwargs.get("dietary_requirements"),
                    kwargs.get("photo_consent", 1),
                ),
            )
            conn.commit()
            logger.info("Created pupil: %s %s (%s)", first_name, last_name, pupil_id)
            return {"pupil_id": pupil_id, "first_name": first_name, "last_name": last_name, "year_group": year_group}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PupilError(f"Failed to create pupil: {e}") from e
        finally:
            conn.close()

    def get_pupil(self, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_pupils(self, status="Active", year_group=None, class_name=None, search=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM pupils WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            if class_name:
                sql += " AND class_name = ?"
                params.append(class_name)
            if search:
                sql += " AND (first_name LIKE ? OR last_name LIKE ? OR pupil_id LIKE ?)"
                escaped = escape_like(search)
                term = f"%{escaped}%"
                params.extend([term, term, term])
            sql += " ORDER BY year_group, last_name, first_name"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_pupil(self, pupil_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "first_name", "last_name", "preferred_name", "date_of_birth",
                "gender", "year_group", "class_name", "ethnicity", "first_language",
                "eal", "pupil_premium", "free_school_meals", "sen_status",
                "looked_after", "parent1_name", "parent1_email", "parent1_phone",
                "parent1_relationship", "parent2_name", "parent2_email",
                "parent2_phone", "parent2_relationship", "emergency_contact_name",
                "emergency_contact_phone", "emergency_contact_relationship",
                "address", "medical_notes", "dietary_requirements", "photo_consent",
                "status", "leaving_date",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None

            if "year_group" in updates:
                updates["key_stage"] = KEY_STAGES.get(updates["year_group"], "")

            set_parts = []
            values = []
            for k, v in updates.items():
                if k == "updated_at":
                    continue
                # All keys are validated against 'allowed' set above
                set_parts.append(f"{k} = ?")
                values.append(v)
            set_parts.append("updated_at = datetime('now')")
            set_clause = ", ".join(set_parts)
            values.append(pupil_id)
            cursor.execute(f"UPDATE pupils SET {set_clause} WHERE pupil_id = ?", values)  # nosec B608  # keys validated against allowlist
            conn.commit()
            logger.info("Updated pupil: %s", pupil_id)
            return self.get_pupil(pupil_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PupilError(f"Failed to update pupil: {e}") from e
        finally:
            conn.close()

    def delete_pupil(self, pupil_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            # Cascade delete related records
            for table in ("assessments", "attendance_records", "behaviour_records",
                          "rewards", "reading_records", "homework_submissions",
                          "phonics_results", "sats_results", "progress_records",
                          "send_records", "send_provisions", "pastoral_notes",
                          "communication_log", "consent_records", "meals",
                          "transport", "medical_records", "club_members",
                          "trip_attendees", "library_loans"):
                cursor.execute(f"DELETE FROM {table} WHERE pupil_id = ?", (pupil_id,))

            cursor.execute("DELETE FROM pupils WHERE pupil_id = ?", (pupil_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted pupil: %s", pupil_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PupilError(f"Failed to delete pupil: {e}") from e
        finally:
            conn.close()

    def count_pupils(self, status="Active", year_group=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT COUNT(*) FROM pupils WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group = ?"
                params.append(year_group)
            cursor.execute(sql, params)
            return cursor.fetchone()[0]
        finally:
            conn.close()
