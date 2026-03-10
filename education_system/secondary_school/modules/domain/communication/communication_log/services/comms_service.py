"""Communication Log service."""

import logging
from education_system.secondary_school.core.exceptions import CommunicationLogError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CONTACT_TYPES = ("phone_call", "email", "letter", "meeting", "home_visit", "text_message", "other")
DIRECTIONS = ("outgoing", "incoming")


class CommsService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_entry(self, student_id, contact_with, summary, contact_type="phone_call",
                  direction="outgoing", subject=None, outcome=None,
                  follow_up_needed=False, follow_up_date=None, recorded_by=None,
                  contact_date=None):
        conn = self._conn()
        try:
            sql = """INSERT INTO communication_log
                     (student_id, contact_type, contact_with, direction, subject,
                      summary, outcome, follow_up_needed, follow_up_date, recorded_by"""
            params = [student_id, contact_type, contact_with, direction, subject,
                      summary, outcome, int(follow_up_needed), follow_up_date, recorded_by]
            if contact_date:
                sql += ", contact_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                params.append(contact_date)
            else:
                sql += ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor = conn.execute(sql, params)
            conn.commit()
            return dict(conn.execute("SELECT * FROM communication_log WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise CommunicationLogError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_entries(self, student_id=None, contact_type=None, follow_up_only=False):
        conn = self._conn()
        try:
            sql = """SELECT cl.*, s.first_name, s.last_name, s.student_id AS stu_code, s.year_group
                     FROM communication_log cl JOIN students s ON cl.student_id = s.id WHERE 1=1"""
            params = []
            if student_id:
                sql += " AND cl.student_id = ?"
                params.append(student_id)
            if contact_type:
                sql += " AND cl.contact_type = ?"
                params.append(contact_type)
            if follow_up_only:
                sql += " AND cl.follow_up_needed = 1 AND cl.follow_up_done = 0"
            sql += " ORDER BY cl.contact_date DESC, cl.created_at DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def mark_follow_up_done(self, entry_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE communication_log SET follow_up_done = 1 WHERE id = ?", (entry_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_entry(self, entry_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM communication_log WHERE id = ?", (entry_id,))
            conn.commit()
        finally:
            conn.close()
