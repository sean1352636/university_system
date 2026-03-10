"""Email service for the Primary School Management System.

Placeholder/log-based service — does not actually send emails.
"""

import logging
from datetime import datetime

from education_system.primary_school.infrastructure.database.db import connect
from education_system.primary_school.core.exceptions import EmailError
import traceback

logger = logging.getLogger(__name__)


class EmailService:
    """Placeholder email operations (logs only, no SMTP)."""

    def __init__(self, db_path=None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def send_email(self, to_address, subject, body, from_address=None):
        """Log an email send request (does not actually send)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO email_log (
                    to_address, subject, body, from_address,
                    status, sent_at
                ) VALUES (?, ?, ?, ?, 'Logged', datetime('now'))""",
                (to_address, subject, body, from_address),
            )
            conn.commit()
            email_id = cursor.lastrowid
            logger.info(
                "Email logged (not sent): to=%s subject='%s' id=%s",
                to_address, subject, email_id,
            )
            return {"id": email_id, "status": "Logged"}
        except Exception as e:
            traceback.print_exc()
            conn.rollback()
            raise EmailError(f"Failed to log email: {e}") from e
        finally:
            conn.close()

    def get_sent_emails(self, date_from=None, date_to=None):
        """Return logged emails (placeholder — returns from DB or empty list)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            sql = "SELECT * FROM email_log WHERE 1=1"
            params = []
            if date_from:
                sql += " AND sent_at >= ?"
                params.append(date_from)
            if date_to:
                sql += " AND sent_at <= ?"
                params.append(date_to)
            sql += " ORDER BY sent_at DESC"
            cursor.execute(sql, params)
            return [dict(r) for r in cursor.fetchall()]
        except Exception:
            traceback.print_exc()
            logger.debug("email_log table may not exist yet — returning empty list")
            return []
        finally:
            conn.close()
