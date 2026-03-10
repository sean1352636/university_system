"""Internal email service — DB-based messaging between system users."""

import logging
from education_system.secondary_school.core.exceptions import EmailError
from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)


class EmailService:
    """Send and receive internal emails stored in SQLite."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def send(self, sender_id: int, recipient_id: int,
             subject: str, body: str) -> dict:
        """Send an email from one user to another."""
        if sender_id == recipient_id:
            raise EmailError("You cannot send an email to yourself.")
        if not subject.strip():
            subject = "(no subject)"

        conn = self._conn()
        try:
            # Verify recipient exists
            recip = conn.execute(
                "SELECT id FROM users WHERE id = ? AND is_active = 1",
                (recipient_id,),
            ).fetchone()
            if not recip:
                raise EmailError("Recipient not found or inactive.")

            cursor = conn.execute(
                """INSERT INTO emails (sender_id, recipient_id, subject, body)
                   VALUES (?, ?, ?, ?)""",
                (sender_id, recipient_id, subject.strip(), body.strip()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM emails WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            logger.info("Email %d sent from user %d to user %d",
                        cursor.lastrowid, sender_id, recipient_id)
            return dict(row)
        except EmailError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise EmailError(f"Failed to send email: {e}") from e
        finally:
            conn.close()

    def get_inbox(self, user_id: int) -> list[dict]:
        """Get all received emails for a user (not deleted by recipient)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT e.*, u.username AS sender_name
                   FROM emails e
                   JOIN users u ON e.sender_id = u.id
                   WHERE e.recipient_id = ? AND e.recipient_deleted = 0
                   ORDER BY e.sent_at DESC""",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_sent(self, user_id: int) -> list[dict]:
        """Get all sent emails for a user (not deleted by sender)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT e.*, u.username AS recipient_name
                   FROM emails e
                   JOIN users u ON e.recipient_id = u.id
                   WHERE e.sender_id = ? AND e.sender_deleted = 0
                   ORDER BY e.sent_at DESC""",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_email(self, email_id: int, user_id: int) -> dict | None:
        """Get a single email if the user is sender or recipient."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT e.*,
                          s.username AS sender_name,
                          r.username AS recipient_name
                   FROM emails e
                   JOIN users u ON e.sender_id = u.id
                   JOIN users s ON e.sender_id = s.id
                   JOIN users r ON e.recipient_id = r.id
                   WHERE e.id = ?
                     AND (e.sender_id = ? OR e.recipient_id = ?)""",
                (email_id, user_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_read(self, email_id: int, user_id: int):
        """Mark an email as read (only the recipient can do this)."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE emails SET is_read = 1 WHERE id = ? AND recipient_id = ?",
                (email_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_email(self, email_id: int, user_id: int):
        """Soft-delete an email for the current user's view."""
        conn = self._conn()
        try:
            email = conn.execute(
                "SELECT * FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            if not email:
                return
            if email["sender_id"] == user_id:
                conn.execute(
                    "UPDATE emails SET sender_deleted = 1 WHERE id = ?",
                    (email_id,),
                )
            if email["recipient_id"] == user_id:
                conn.execute(
                    "UPDATE emails SET recipient_deleted = 1 WHERE id = ?",
                    (email_id,),
                )
            conn.commit()
        finally:
            conn.close()

    def get_unread_count(self, user_id: int) -> int:
        """Count unread emails in the user's inbox."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM emails
                   WHERE recipient_id = ? AND is_read = 0
                     AND recipient_deleted = 0""",
                (user_id,),
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_all_users(self, exclude_id: int | None = None) -> list[dict]:
        """Get all active users (for the recipient picker)."""
        conn = self._conn()
        try:
            sql = "SELECT id, username, role FROM users WHERE is_active = 1"
            params: list = []
            if exclude_id is not None:
                sql += " AND id != ?"
                params.append(exclude_id)
            sql += " ORDER BY username"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
