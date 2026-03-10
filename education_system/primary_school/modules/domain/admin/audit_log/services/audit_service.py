"""Audit log service for the Primary School Management System."""

import logging
from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import AuditError
import traceback

logger = logging.getLogger(__name__)


class AuditService:
    """Operations for recording and querying audit log entries."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def log_action(self, username, action, table_name=None, record_id=None,
                   details=None):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO audit_log (username, action, table_name, record_id, details)
                VALUES (?, ?, ?, ?, ?)""",
                (username, action, table_name, record_id, details),
            )
            conn.commit()
            logger.info("Audit: %s performed '%s' on %s", username, action, table_name)
            return cursor.lastrowid
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise AuditError(f"Failed to log action: {e}") from e
        finally:
            conn.close()

    def get_log(self, username=None, action=None, date_from=None, date_to=None,
                limit=100):
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            if username:
                sql += " AND username = ?"
                params.append(username)
            if action:
                sql += " AND action = ?"
                params.append(action)
            if date_from:
                sql += " AND created_at >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND created_at <= ?"
                params.append(date_to)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
