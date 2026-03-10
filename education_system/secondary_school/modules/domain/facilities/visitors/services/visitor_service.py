"""Visitor management service."""

import logging
from education_system.secondary_school.core.exceptions import VisitorError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class VisitorService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def sign_in(self, visitor_name, purpose, visiting=None, organisation=None,
                badge_number=None, dbs_checked=False, car_registration=None, notes=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO visitors
                   (visitor_name, organisation, purpose, visiting, badge_number,
                    dbs_checked, car_registration, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (visitor_name, organisation, purpose, visiting, badge_number,
                 int(dbs_checked), car_registration, notes))
            conn.commit()
            return dict(conn.execute("SELECT * FROM visitors WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise VisitorError(f"Failed: {e}") from e
        finally:
            conn.close()

    def sign_out(self, visitor_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE visitors SET sign_out_time = datetime('now') WHERE id = ?",
                         (visitor_id,))
            conn.commit()
        finally:
            conn.close()

    def list_visitors(self, on_site_only=False, date=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM visitors WHERE 1=1"
            params = []
            if on_site_only:
                sql += " AND sign_out_time IS NULL"
            if date:
                sql += " AND date(sign_in_time) = ?"
                params.append(date)
            sql += " ORDER BY sign_in_time DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_visitor(self, visitor_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM visitors WHERE id = ?", (visitor_id,))
            conn.commit()
        finally:
            conn.close()

    def on_site_count(self):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM visitors WHERE sign_out_time IS NULL").fetchone()
            return row["cnt"]
        finally:
            conn.close()
