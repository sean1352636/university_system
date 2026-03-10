"""Audit trail logging for security-relevant events."""
import logging

from datetime import datetime

from education_system.college_system.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class AuditLogger:
    """Logs security and data-change events to the audit_log table."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def log(self, action: str, resource: str | None = None,
            details: str | None = None, user_id: int | None = None,
            username: str | None = None, ip_address: str | None = None):
        """Record an audit event."""
        conn = connect(self._db_path)
        try:
            conn.execute(
                """INSERT INTO audit_log
                   (user_id, username, action, resource, details, ip_address, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, username, action, resource, details, ip_address,
                 datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.debug("Audit logged: %s %s", action, resource or '')
        finally:
            conn.close()

    def get_logs(self, limit: int = 100, user_id: int | None = None,
                 action: str | None = None) -> list[dict]:
        """Retrieve audit log entries."""
        conn = connect(self._db_path)
        try:
            sql = "SELECT * FROM audit_log WHERE 1=1"
            params = []

            if user_id is not None:
                sql += " AND user_id = ?"
                params.append(user_id)
            if action:
                sql += " AND action = ?"
                params.append(action)

            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
