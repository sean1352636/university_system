"""SEND (Special Educational Needs & Disabilities) service."""

import logging
from education_system.secondary_school.core.sql_safety import validate_identifier  # nosec B608
from education_system.secondary_school.core.exceptions import SENDError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

SEN_TYPES = ("SEN Support", "EHCP", "Monitoring")
PRIMARY_NEEDS = ("Cognition & Learning", "Communication & Interaction",
                 "Social, Emotional & Mental Health", "Sensory and/or Physical Needs")


class SENDService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_record(self, student_id, sen_type="SEN Support", primary_need=None,
                      ehcp=False, key_worker=None, diagnosis=None,
                      strategies=None, access_arrangements=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO send_records (student_id, sen_type, primary_need, ehcp,
                   key_worker, diagnosis, strategies, access_arrangements, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_id, sen_type, primary_need, int(ehcp),
                 key_worker, diagnosis, strategies, access_arrangements, notes))
            conn.commit()
            row = conn.execute("SELECT * FROM send_records WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise SENDError(f"Failed to create SEND record: {e}") from e
        finally:
            conn.close()

    def list_records(self, status=None):
        conn = self._conn()
        try:
            sql = """SELECT sr.*, s.student_id as sid, s.first_name, s.last_name, s.year_group
                     FROM send_records sr JOIN students s ON sr.student_id = s.id WHERE 1=1"""
            params = []
            if status:
                sql += " AND sr.status = ?"
                params.append(status)
            sql += " ORDER BY s.last_name"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def update_record(self, record_id, **kwargs):
        allowed = {"sen_type", "primary_need", "ehcp", "key_worker", "ehcp_review_date",
                    "external_agencies", "diagnosis", "strategies", "access_arrangements", "notes", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{validate_identifier(k)} = ?" for k in updates)
            conn.execute(f"UPDATE send_records SET {set_clause}, updated_at = datetime('now') WHERE id = ?",  # nosec B608
                         (*updates.values(), record_id))
            conn.commit()
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM send_provisions WHERE send_record_id = ?", (record_id,))
            conn.execute("DELETE FROM send_records WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()

    def add_provision(self, send_record_id, provision_type, description=None,
                      frequency=None, staff_responsible=None, start_date=None, end_date=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO send_provisions (send_record_id, provision_type, description,
                   frequency, staff_responsible, start_date, end_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (send_record_id, provision_type, description, frequency,
                 staff_responsible, start_date, end_date))
            conn.commit()
            row = conn.execute("SELECT * FROM send_provisions WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise SENDError(f"Failed to add provision: {e}") from e
        finally:
            conn.close()

    def list_provisions(self, send_record_id):
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM send_provisions WHERE send_record_id = ? ORDER BY start_date",
                                (send_record_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
