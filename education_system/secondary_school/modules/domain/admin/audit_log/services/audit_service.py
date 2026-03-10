"""Audit Log service."""

import logging
from education_system.secondary_school.core.exceptions import AuditError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

AUDIT_ACTIONS = ("login", "logout", "create", "update", "delete", "view", "export", "import", "config_change")


class AuditService:
    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def log(self, action, module=None, record_id=None, details=None,
            user_id=None, username=None):
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO audit_log
                   (user_id, username, action, module, record_id, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, action, module, record_id, details))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise AuditError(f"Failed: {e}") from e
        finally:
            conn.close()

    def list_entries(self, action=None, module=None, username=None, limit=500):
        conn = self._conn()
        try:
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            if action:
                sql += " AND action = ?"
                params.append(action)
            if module:
                sql += " AND module = ?"
                params.append(module)
            if username:
                sql += " AND username = ?"
                params.append(username)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def clear_old(self, days=365):
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM audit_log WHERE created_at < datetime('now', ?)",
                (f"-{days} days",))
            conn.commit()
        finally:
            conn.close()

    def entry_count(self):
        conn = self._conn()
        try:
            row = conn.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()
            return row["cnt"]
        finally:
            conn.close()
