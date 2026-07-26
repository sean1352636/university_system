"""Inter-system messaging service for teacher-to-teacher communication.

Messages are stored in the shared auth database and are associated with
specific students to facilitate handover conversations during transfers.
"""

import sqlite3
from datetime import datetime

from education_system.platform.identity.auth.db import AUTH_DB_FILE, connect as auth_connect

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cross_system_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id       INTEGER NOT NULL,
    sender_system   TEXT    NOT NULL,
    sender_name     TEXT,
    recipient_id    INTEGER NOT NULL,
    recipient_system TEXT   NOT NULL,
    recipient_name  TEXT,
    student_name    TEXT,
    student_id      TEXT,
    subject         TEXT    NOT NULL,
    body            TEXT,
    is_read         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class InterSystemMessagingService:
    """Send and receive messages between staff across education systems."""

    def __init__(self, db_path=None):
        self._db_path = db_path or str(AUTH_DB_FILE)
        self._ensure_table()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _conn(self):
        return auth_connect(self._db_path)

    def _ensure_table(self):
        """Create the cross_system_messages table if it does not exist."""
        conn = self._conn()
        try:
            conn.executescript(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def send_message(self, sender_id, sender_system, sender_name,
                     recipient_id, recipient_system, recipient_name,
                     student_name, student_id, subject, body):
        """Send a message from one staff member to another.

        Returns the newly created message dict.
        """
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO cross_system_messages
                   (sender_id, sender_system, sender_name,
                    recipient_id, recipient_system, recipient_name,
                    student_name, student_id, subject, body)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sender_id, sender_system, sender_name or "",
                 recipient_id, recipient_system, recipient_name or "",
                 student_name or "", student_id or "",
                 subject, body or ""),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cross_system_messages WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_inbox(self, user_id, system=None):
        """Get messages received by *user_id*, newest first.

        If *system* is given, filters to messages sent TO that system.
        """
        conn = self._conn()
        try:
            if system:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE recipient_id = ? AND recipient_system = ? "
                    "ORDER BY created_at DESC",
                    (user_id, system),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE recipient_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_sent(self, user_id, system=None):
        """Get messages sent by *user_id*, newest first."""
        conn = self._conn()
        try:
            if system:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE sender_id = ? AND sender_system = ? "
                    "ORDER BY created_at DESC",
                    (user_id, system),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE sender_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_message(self, msg_id):
        """Get a single message by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_messages WHERE id = ?", (msg_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_read(self, msg_id):
        """Mark a message as read."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE cross_system_messages SET is_read = 1 WHERE id = ?",
                (msg_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_staff_list(self, system):
        """Get staff/admin/teacher users in a given system.

        Returns a list of dicts with keys: id, display_name, username, role.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT u.id, u.display_name, u.username, us.role "
                "FROM users u "
                "JOIN user_systems us ON u.id = us.user_id "
                "WHERE us.system_key = ? AND us.role IN ('admin', 'staff', 'teacher', 'instructor') "
                "AND u.is_active = 1 "
                "ORDER BY u.display_name",
                (system,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_messages(self, user_id, system, query):
        """Search messages (inbox and sent) by subject, body, or student name.

        Returns messages where the user is sender or recipient matching query.
        """
        conn = self._conn()
        try:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                "SELECT * FROM cross_system_messages "
                "WHERE (recipient_id = ? OR sender_id = ?) "
                "AND (subject LIKE ? OR body LIKE ? OR student_name LIKE ?) "
                "ORDER BY created_at DESC",
                (user_id, user_id, like, like, like),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_unread_count(self, user_id, system=None):
        """Get the count of unread messages for a user."""
        conn = self._conn()
        try:
            if system:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_messages "
                    "WHERE recipient_id = ? AND recipient_system = ? AND is_read = 0",
                    (user_id, system),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_messages "
                    "WHERE recipient_id = ? AND is_read = 0",
                    (user_id,),
                ).fetchone()
            return row["cnt"]
        finally:
            conn.close()
