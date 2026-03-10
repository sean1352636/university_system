"""Internal messaging service."""

from education_system.college_system.core.exceptions import MessageError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class MessageService:
    """Service for internal user-to-user messaging."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    # ------------------------------------------------------------------
    # Display-name helper (reused in several queries)
    # ------------------------------------------------------------------

    _DISPLAY_NAME_SQL = """
        COALESCE(
            (SELECT s.first_name || ' ' || s.last_name
             FROM staff s WHERE s.user_id = {alias}.id),
            (SELECT st.first_name || ' ' || st.last_name
             FROM students st WHERE st.user_id = {alias}.id),
            {alias}.username
        )
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_message(self, sender_id: int, recipient_id: int,
                     subject: str, body: str | None = None) -> dict:
        """Send a message from one user to another."""
        if not subject or not subject.strip():
            raise MessageError("Subject is required.")
        if sender_id == recipient_id:
            raise MessageError("Cannot send a message to yourself.")

        conn = self._conn()
        try:
            # Validate sender exists
            sender = conn.execute(
                "SELECT id FROM users WHERE id = ? AND is_active = 1",
                (sender_id,),
            ).fetchone()
            if not sender:
                raise MessageError("Sender not found.")

            # Validate recipient exists
            recipient = conn.execute(
                "SELECT id FROM users WHERE id = ? AND is_active = 1",
                (recipient_id,),
            ).fetchone()
            if not recipient:
                raise MessageError("Recipient not found.")

            conn.execute(
                """INSERT INTO messages (sender_id, recipient_id, subject, body)
                   VALUES (?, ?, ?, ?)""",
                (sender_id, recipient_id, subject.strip(), body),
            )
            conn.commit()
            logger.info("Message sent: sender=%d recipient=%d subject='%s'", sender_id, recipient_id, subject.strip())

            row = conn.execute(
                "SELECT * FROM messages WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row)
        except MessageError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MessageError(f"Failed to send message: {e}") from e
        finally:
            conn.close()

    def get_inbox(self, user_id: int, unread_only: bool = False,
                  limit: int = 50) -> list[dict]:
        """Get received messages for a user."""
        conn = self._conn()
        try:
            sender_name = self._DISPLAY_NAME_SQL.format(alias="u")
            sql = f"""
                SELECT m.*,
                       {sender_name} AS sender_name
                FROM messages m
                JOIN users u ON u.id = m.sender_id
                WHERE m.recipient_id = ? AND m.recipient_deleted = 0
            """
            params: list = [user_id]

            if unread_only:
                sql += " AND m.is_read = 0"

            sql += " ORDER BY m.created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_sent(self, user_id: int, limit: int = 50) -> list[dict]:
        """Get sent messages for a user."""
        conn = self._conn()
        try:
            recipient_name = self._DISPLAY_NAME_SQL.format(alias="u")
            sql = f"""
                SELECT m.*,
                       {recipient_name} AS recipient_name
                FROM messages m
                JOIN users u ON u.id = m.recipient_id
                WHERE m.sender_id = ? AND m.sender_deleted = 0
                ORDER BY m.created_at DESC LIMIT ?
            """
            rows = conn.execute(sql, (user_id, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_message(self, message_id: int, user_id: int) -> dict | None:
        """Get a single message (only if the user is sender or recipient)."""
        conn = self._conn()
        try:
            sender_name = self._DISPLAY_NAME_SQL.format(alias="su")
            recipient_name = self._DISPLAY_NAME_SQL.format(alias="ru")
            sql = f"""
                SELECT m.*,
                       {sender_name} AS sender_name,
                       {recipient_name} AS recipient_name
                FROM messages m
                JOIN users su ON su.id = m.sender_id
                JOIN users ru ON ru.id = m.recipient_id
                WHERE m.id = ?
                  AND (
                      (m.sender_id = ? AND m.sender_deleted = 0)
                      OR (m.recipient_id = ? AND m.recipient_deleted = 0)
                  )
            """
            row = conn.execute(sql, (message_id, user_id, user_id)).fetchone()
            if not row:
                return None

            msg = dict(row)

            # Auto-mark as read if the user is the recipient
            if msg["recipient_id"] == user_id and not msg["is_read"]:
                conn.execute(
                    "UPDATE messages SET is_read = 1 WHERE id = ?",
                    (message_id,),
                )
                conn.commit()
                msg["is_read"] = 1

            return msg
        finally:
            conn.close()

    def mark_read(self, message_id: int, user_id: int) -> bool:
        """Mark a message as read (only the recipient can do this)."""
        conn = self._conn()
        try:
            result = conn.execute(
                "UPDATE messages SET is_read = 1 WHERE id = ? AND recipient_id = ?",
                (message_id, user_id),
            )
            conn.commit()
            if result.rowcount == 0:
                raise MessageError("Message not found or you are not the recipient.")
            return True
        except MessageError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def count_unread(self, user_id: int) -> int:
        """Count unread messages for a user."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COUNT(*) AS cnt FROM messages
                   WHERE recipient_id = ? AND is_read = 0 AND recipient_deleted = 0""",
                (user_id,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()

    def delete_message(self, message_id: int, user_id: int) -> bool:
        """Soft-delete a message for the requesting user."""
        conn = self._conn()
        try:
            msg = conn.execute(
                "SELECT sender_id, recipient_id FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if not msg:
                raise MessageError("Message not found.")

            if msg["sender_id"] == user_id:
                conn.execute(
                    "UPDATE messages SET sender_deleted = 1 WHERE id = ?",
                    (message_id,),
                )
            elif msg["recipient_id"] == user_id:
                conn.execute(
                    "UPDATE messages SET recipient_deleted = 1 WHERE id = ?",
                    (message_id,),
                )
            else:
                raise MessageError("You do not have access to this message.")

            conn.commit()
            logger.info("Message deleted: id=%d by user_id=%d", message_id, user_id)
            return True
        except MessageError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise MessageError(f"Failed to delete message: {e}") from e
        finally:
            conn.close()

    def get_all_users(self) -> list[dict]:
        """Get all active users with display names for the recipient picker."""
        conn = self._conn()
        try:
            display_name = self._DISPLAY_NAME_SQL.format(alias="u")
            sql = f"""
                SELECT u.id, u.username, u.role,
                       {display_name} AS display_name
                FROM users u
                WHERE u.is_active = 1
                ORDER BY u.username
            """
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
