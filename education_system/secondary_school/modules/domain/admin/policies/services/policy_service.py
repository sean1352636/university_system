"""Policy Management service."""

import logging
from education_system.secondary_school.core.exceptions import PolicyError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

POLICY_CATEGORIES = ("general", "safeguarding", "health_safety", "hr", "curriculum",
                     "behaviour", "admissions", "send", "data_protection", "complaints")


class PolicyService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def add_policy(self, title, category="general", version="1.0", approved_by=None,
                   approval_date=None, review_date=None, summary=None, content=None):
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO policies
                   (title, category, version, approved_by, approval_date,
                    review_date, summary, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, category, version, approved_by, approval_date,
                 review_date, summary, content))
            conn.commit()
            return dict(conn.execute("SELECT * FROM policies WHERE id = ?", (cursor.lastrowid,)).fetchone())
        except Exception as e:
            conn.rollback()
            raise PolicyError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_policies(self, category=None, status="active"):
        conn = self._conn()
        try:
            sql = "SELECT * FROM policies WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY title"
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def delete_policy(self, policy_id):
        conn = self._conn()
        try:
            conn.execute("DELETE FROM policy_acknowledgements WHERE policy_id = ?", (policy_id,))
            conn.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
            conn.commit()
        finally:
            conn.close()

    def acknowledge(self, policy_id, staff_name):
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO policy_acknowledgements (policy_id, staff_name) VALUES (?, ?)",
                (policy_id, staff_name))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise PolicyError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_acknowledgements(self, policy_id):
        conn = self._conn()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM policy_acknowledgements WHERE policy_id = ? ORDER BY acknowledged_at",
                (policy_id,)).fetchall()]
        finally:
            conn.close()

    def acknowledgement_count(self, policy_id):
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM policy_acknowledgements WHERE policy_id = ?",
                (policy_id,)).fetchone()
            return row["cnt"]
        finally:
            conn.close()
