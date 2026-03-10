"""Medical / First Aid service."""

import logging
from education_system.secondary_school.core.exceptions import MedicalError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

SEVERITIES = ("low", "medium", "high", "critical")


class MedicalService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Medical Conditions ---

    def add_condition(self, student_id, condition_name, severity="low",
                      medications=None, allergies=None, care_plan=None,
                      emergency_protocol=None, doctor_name=None, doctor_phone=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO medical_conditions
                   (student_id, condition_name, severity, medications, allergies,
                    care_plan, emergency_protocol, doctor_name, doctor_phone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, condition_name, severity, medications, allergies,
                 care_plan, emergency_protocol, doctor_name, doctor_phone, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM medical_conditions WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise MedicalError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_conditions(self, student_id=None, status="active"):
        conn = self._conn()
        try:
            sql = """SELECT mc.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM medical_conditions mc
                     JOIN students s ON mc.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND mc.student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND mc.status = ?"
                params.append(status)
            sql += " ORDER BY mc.severity DESC, s.last_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_condition(self, condition_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM medical_conditions WHERE id = ?", (condition_id,))
            conn.commit()
        finally:
            conn.close()

    # --- First Aid Log ---

    def log_incident(self, student_id, description, incident_date=None, incident_time=None,
                     location=None, treatment=None, treated_by=None,
                     parent_notified=False, sent_home=False, ambulance_called=False, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO first_aid_log
                   (student_id, description, incident_date, incident_time, location,
                    treatment, treated_by, parent_notified, sent_home, ambulance_called, notes)
                   VALUES (?, ?, COALESCE(?, date('now')), ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, description, incident_date, incident_time, location,
                 treatment, treated_by, int(parent_notified), int(sent_home),
                 int(ambulance_called), notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM first_aid_log WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise MedicalError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_incidents(self, student_id=None, date_from=None, date_to=None):
        conn = self._conn()
        try:
            sql = """SELECT fa.*, s.first_name, s.last_name, s.student_id as stu_code, s.year_group
                     FROM first_aid_log fa
                     JOIN students s ON fa.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND fa.student_id = ?"
                params.append(student_id)
            if date_from:
                sql += " AND fa.incident_date >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND fa.incident_date <= ?"
                params.append(date_to)
            sql += " ORDER BY fa.incident_date DESC, fa.incident_time DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_incident(self, incident_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM first_aid_log WHERE id = ?", (incident_id,))
            conn.commit()
        finally:
            conn.close()
