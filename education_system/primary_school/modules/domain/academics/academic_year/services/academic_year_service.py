"""Academic year management service."""

import logging
from education_system.primary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class AcademicYearService:
    """Academic year management."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_year(self, name, start_date, end_date, is_current=0):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO academic_years (name, start_date, end_date, is_current) VALUES (?, ?, ?, ?)",
                (name, start_date, end_date, is_current))
            conn.commit()
            row = conn.execute("SELECT * FROM academic_years WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_years(self, status=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM academic_years WHERE 1=1"
            params = []
            if status:
                sql += " AND status = ?"; params.append(status)
            sql += " ORDER BY start_date DESC"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_year(self, year_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM academic_years WHERE id = ?", (year_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_year(self, year_id, **kwargs):
        conn = self._conn()
        try:
            allowed = {"name", "start_date", "end_date", "is_current", "status"}
            updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
            if not updates: return None
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE academic_years SET {set_clause} WHERE id = ?", list(updates.values()) + [year_id])
            conn.commit()
            return self.get_year(year_id)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_year(self, year_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM academic_years WHERE id = ?", (year_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def get_current_year(self):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM academic_years WHERE is_current = 1").fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def set_current_year(self, year_id):
        conn = self._conn()
        try:
            conn.execute("UPDATE academic_years SET is_current = 0")
            conn.execute("UPDATE academic_years SET is_current = 1 WHERE id = ?", (year_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_term(self, academic_year_id, name, term_number, start_date, end_date):
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO academic_terms (academic_year_id, name, term_number, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
                (academic_year_id, name, term_number, start_date, end_date))
            conn.commit()
            row = conn.execute("SELECT * FROM academic_terms WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_terms(self, year_id=None):
        conn = self._conn()
        try:
            sql = "SELECT * FROM academic_terms WHERE 1=1"
            params = []
            if year_id:
                sql += " AND academic_year_id = ?"; params.append(year_id)
            sql += " ORDER BY term_number"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

