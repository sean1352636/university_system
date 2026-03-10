"""Admissions service."""

import logging
from education_system.secondary_school.core.exceptions import AdmissionsError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

APPLICATION_STATUSES = ("received", "under_review", "interview_scheduled", "offered", "accepted", "rejected", "withdrawn")


class AdmissionsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_application(self, first_name, last_name, year_group, parent_name,
                           date_of_birth=None, gender=None, address=None,
                           parent_email=None, parent_phone=None, previous_school=None,
                           sen_needs=None, medical_info=None, additional_info=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO admissions_applications
                   (applicant_first_name, applicant_last_name, date_of_birth, gender, address,
                    year_group_applying, parent_name, parent_email, parent_phone,
                    previous_school, sen_needs, medical_info, additional_info)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (first_name, last_name, date_of_birth, gender, address,
                 year_group, parent_name, parent_email, parent_phone,
                 previous_school, sen_needs, medical_info, additional_info))
            conn.commit()
            return dict(conn.execute("SELECT * FROM admissions_applications WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise AdmissionsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_applications(self, status=None, year_group=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM admissions_applications WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            if year_group:
                sql += " AND year_group_applying = ?"
                params.append(year_group)
            sql += " ORDER BY application_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_status(self, app_id, status, decision_by=None):
        conn = self._conn()
        try:
            if status in ("offered", "accepted", "rejected"):
                conn.execute(
                    "UPDATE admissions_applications SET status = ?, decision_by = ?, decision_date = date('now') WHERE id = ?",
                    (status, decision_by, app_id))
            else:
                conn.execute("UPDATE admissions_applications SET status = ? WHERE id = ?", (status, app_id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise AdmissionsError(f"Failed: {e}") from e
        finally:
            conn.close()

    def delete_application(self, app_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM admissions_applications WHERE id = ?", (app_id,))
            conn.commit()
        finally:
            conn.close()

    def status_summary(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM admissions_applications GROUP BY status ORDER BY cnt DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
