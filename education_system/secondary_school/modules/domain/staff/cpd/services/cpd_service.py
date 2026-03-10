"""CPD (Continuing Professional Development) service."""

import logging
from education_system.secondary_school.core.exceptions import CPDError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

CPD_CATEGORIES = ("general", "safeguarding", "first_aid", "curriculum", "leadership",
                  "behaviour_management", "sen", "ict", "assessment", "wellbeing")


class CPDService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_record(self, staff_name, training_title, date, category="general",
                   provider=None, duration_hours=None, cost=0.0,
                   certificate=False, impact=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO cpd_records
                   (staff_name, training_title, provider, category, date,
                    duration_hours, cost, certificate, impact, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (staff_name, training_title, provider, category, date,
                 duration_hours, cost, int(certificate), impact, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM cpd_records WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise CPDError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_records(self, staff_name=None, category=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM cpd_records WHERE 1=1"
            params = []
            if staff_name:
                sql += " AND staff_name = ?"
                params.append(staff_name)
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_record(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM cpd_records WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()

    def staff_summary(self):
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT staff_name, COUNT(*) as courses, SUM(COALESCE(duration_hours, 0)) as total_hours
                   FROM cpd_records GROUP BY staff_name ORDER BY total_hours DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
