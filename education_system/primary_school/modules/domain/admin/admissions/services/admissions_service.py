"""Admissions management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AdmissionsError
import traceback

logger = logging.getLogger(__name__)


class AdmissionsService:
    """CRUD operations for admission applications."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_application(self, first_name, last_name, year_group_applied, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO admissions (
                    first_name, last_name, year_group_applied,
                    date_of_birth, gender, parent_name, parent_email,
                    parent_phone, address, previous_school, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    first_name, last_name, year_group_applied,
                    kwargs.get("date_of_birth"),
                    kwargs.get("gender"),
                    kwargs.get("parent_name"),
                    kwargs.get("parent_email"),
                    kwargs.get("parent_phone"),
                    kwargs.get("address"),
                    kwargs.get("previous_school"),
                    kwargs.get("notes"),
                ),
            )
            conn.commit()
            app_id = cursor.lastrowid
            logger.info(
                "Created admission application: %s %s (id=%s)",
                first_name, last_name, app_id,
            )
            return {
                "id": app_id,
                "first_name": first_name,
                "last_name": last_name,
                "year_group_applied": year_group_applied,
                "status": "Pending",
            }
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AdmissionsError(f"Failed to create application: {e}") from e
        finally:
            conn.close()

    def get_application(self, app_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admissions WHERE id = ?", (app_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_applications(self, status=None, year_group=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM admissions WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group_applied = ?"
                params.append(year_group)
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_application(self, app_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            allowed = {
                "first_name", "last_name", "year_group_applied",
                "date_of_birth", "gender", "parent_name", "parent_email",
                "parent_phone", "address", "previous_school", "notes", "status",
            }
            updates = {k: v for k, v in kwargs.items() if k in allowed}
            if not updates:
                return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(app_id)
            cursor.execute(
                f"UPDATE admissions SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated admission application id=%s", app_id)
            return self.get_application(app_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AdmissionsError(f"Failed to update application: {e}") from e
        finally:
            conn.close()

    def approve_application(self, app_id):
        logger.info("Approved admission application id=%s", app_id)
        return self.update_application(app_id, status="Approved")

    def reject_application(self, app_id):
        logger.info("Rejected admission application id=%s", app_id)
        return self.update_application(app_id, status="Rejected")
