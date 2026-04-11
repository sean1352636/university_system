"""Policy management service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import PolicyError
import traceback

logger = logging.getLogger(__name__)


class PolicyService:
    """CRUD operations for school policies."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_policy(self, title, category=None, content=None, version="1.0",
                      approved_by=None, review_date=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO policies (title, category, content, version, approved_by, review_date)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (title, category, content, version, approved_by, review_date),
            )
            conn.commit()
            policy_id = cursor.lastrowid
            logger.info("Created policy: %s (id=%s)", title, policy_id)
            return {"id": policy_id, "title": title, "version": version}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PolicyError(f"Failed to create policy: {e}") from e
        finally:
            conn.close()

    def get_policy(self, policy_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM policies WHERE id = ?", (policy_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_policies(self, category=None, status="Active"):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM policies WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(category)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY title"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_policy(self, policy_id, **kwargs):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            set_parts: list[str] = []
            values: list = []
            for col in ("approved_by", "category", "content", "review_date",
                        "status", "title", "version"):
                if col in kwargs:
                    set_parts.append(f"{col} = ?")
                    values.append(kwargs[col])
            if not set_parts:
                return None
            set_clause = ", ".join(set_parts)
            values.append(policy_id)
            cursor.execute(
                f"UPDATE policies SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                values,
            )
            conn.commit()
            logger.info("Updated policy id=%s", policy_id)
            return self.get_policy(policy_id)
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PolicyError(f"Failed to update policy: {e}") from e
        finally:
            conn.close()

    def delete_policy(self, policy_id):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            if deleted:
                logger.info("Deleted policy id=%s", policy_id)
            return deleted
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise PolicyError(f"Failed to delete policy: {e}") from e
        finally:
            conn.close()
