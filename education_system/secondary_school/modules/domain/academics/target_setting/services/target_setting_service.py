"""Target setting management service."""

import logging
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class TargetSettingService:
    """Target setting management."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create(self, **kwargs):
        conn = self._conn()
        try:
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            cursor = conn.execute(
                f"INSERT INTO student_targets ({cols}) VALUES ({placeholders})",
                list(kwargs.values()))
            conn.commit()
            row = conn.execute("SELECT * FROM student_targets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return dict(row) if row else {"id": cursor.lastrowid}
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_all(self, limit=100, offset=0, **filters):
        conn = self._conn()
        try:
            sql = "SELECT * FROM student_targets WHERE 1=1"
            params = []
            for key, val in filters.items():
                if val is not None:
                    sql += f" AND {key} = ?"
                    params.append(val)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get(self, record_id):
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM student_targets WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, record_id, **kwargs):
        if not kwargs:
            return None
        conn = self._conn()
        try:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [record_id]
            conn.execute(f"UPDATE student_targets SET {set_clause} WHERE id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM student_targets WHERE id = ?", (record_id,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete(self, record_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM student_targets WHERE id = ?", (record_id,))
            conn.commit()
            return True
        finally:
            conn.close()

