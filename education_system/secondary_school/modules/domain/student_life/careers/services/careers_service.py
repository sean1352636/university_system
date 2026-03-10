"""Careers & Work Experience service."""

import logging
from education_system.secondary_school.core.exceptions import CareersError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

WE_STATUSES = ("planned", "confirmed", "in_progress", "completed", "cancelled")


class CareersService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # --- Careers meetings ---

    def add_meeting(self, student_id, meeting_date, adviser=None,
                    career_interests=None, action_points=None, destination=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO careers_records
                   (student_id, meeting_date, adviser, career_interests,
                    action_points, destination, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, meeting_date, adviser, career_interests,
                 action_points, destination, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM careers_records WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise CareersError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_meetings(self, student_id=None):
        conn = self._conn()
        try:
            sql = """SELECT cr.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM careers_records cr JOIN students s ON cr.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND cr.student_id = ?"
                params.append(student_id)
            sql += " ORDER BY cr.meeting_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_meeting(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM careers_records WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Work experience ---

    def add_placement(self, student_id, employer, start_date, end_date, role=None,
                      contact_name=None, contact_phone=None, contact_email=None, address=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO work_experience
                   (student_id, employer, contact_name, contact_phone, contact_email,
                    address, role, start_date, end_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, employer, contact_name, contact_phone, contact_email,
                 address, role, start_date, end_date))
            conn.commit()
            return dict(conn.execute("SELECT * FROM work_experience WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise CareersError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_placements(self, student_id=None, status=None):
        conn = self._conn()
        try:
            sql = """SELECT we.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM work_experience we JOIN students s ON we.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND we.student_id = ?"
                params.append(student_id)
            if status:
                sql += " AND we.status = ?"
                params.append(status)
            sql += " ORDER BY we.start_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_placement_status(self, placement_id, status):
        conn = self._conn()
        try:
            conn.execute("UPDATE work_experience SET status = ? WHERE id = ?", (status, placement_id))
            conn.commit()
        finally:
            conn.close()

    def update_checks(self, placement_id, risk_assessment=None, parent_consent=None, insurance=None):
        conn = self._conn()
        try:
            if risk_assessment is not None:
                conn.execute("UPDATE work_experience SET risk_assessment_done = ? WHERE id = ?",
                             (int(risk_assessment), placement_id))
            if parent_consent is not None:
                conn.execute("UPDATE work_experience SET parent_consent = ? WHERE id = ?",
                             (int(parent_consent), placement_id))
            if insurance is not None:
                conn.execute("UPDATE work_experience SET insurance_confirmed = ? WHERE id = ?",
                             (int(insurance), placement_id))
            conn.commit()
        finally:
            conn.close()

    def delete_placement(self, placement_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM work_experience WHERE id = ?", (placement_id,))
            conn.commit()
        finally:
            conn.close()
