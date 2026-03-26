"""SQLite-backed chat service for real-time messaging.

Provides room management, message persistence, and read-receipt tracking
shared across all four education sub-systems.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    room_type   TEXT NOT NULL DEFAULT 'group',  -- 'direct', 'group', 'system'
    system_key  TEXT,
    created_by  INTEGER,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_participants (
    room_id     INTEGER NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL,
    joined_at   TEXT NOT NULL,
    PRIMARY KEY (room_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      INTEGER NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    sender_id    INTEGER,
    message_text TEXT NOT NULL,
    message_type TEXT NOT NULL DEFAULT 'text',  -- 'text', 'image', 'file', 'system'
    created_at   TEXT NOT NULL,
    edited_at    TEXT
);

CREATE TABLE IF NOT EXISTS read_receipts (
    message_id  INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL,
    read_at     TEXT NOT NULL,
    PRIMARY KEY (message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_participants_user ON chat_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_read_receipts_user ON read_receipts(user_id);
"""


def init_chat_db(db_path: str) -> None:
    """Create chat tables in the given SQLite database (idempotent)."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.info("Chat DB initialised at %s", db_path)
    finally:
        conn.close()


class ChatService:
    """Service layer for all chat operations."""

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        init_chat_db(self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    # ------------------------------------------------------------------
    # Room management
    # ------------------------------------------------------------------
    def create_room(
        self,
        name: str,
        room_type: str = "group",
        system_key: str | None = None,
        created_by: int | None = None,
    ) -> dict:
        """Create a new chat room and return its record."""
        now = self._now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO chat_rooms (name, room_type, system_key, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, room_type, system_key, created_by, now),
            )
            conn.commit()
            room_id = cur.lastrowid
            logger.info("Created chat room id=%s name=%r", room_id, name)
            return {"id": room_id, "name": name, "room_type": room_type,
                    "system_key": system_key, "created_by": created_by, "created_at": now}
        finally:
            conn.close()

    def get_room(self, room_id: int) -> dict | None:
        """Return a room record or None."""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM chat_rooms WHERE id = ?", (room_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Participant management
    # ------------------------------------------------------------------
    def add_participant(self, room_id: int, user_id: int) -> bool:
        """Add a user to a room (idempotent)."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO chat_participants (room_id, user_id, joined_at) "
                "VALUES (?, ?, ?)",
                (room_id, user_id, self._now()),
            )
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("add_participant failed: %s", exc)
            return False
        finally:
            conn.close()

    def remove_participant(self, room_id: int, user_id: int) -> bool:
        """Remove a user from a room."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM chat_participants WHERE room_id = ? AND user_id = ?",
                (room_id, user_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_room_participants(self, room_id: int) -> list[dict]:
        """Return all participants of a room."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM chat_participants WHERE room_id = ?", (room_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_user_rooms(self, user_id: int) -> list[dict]:
        """Return all rooms a user participates in, with unread count."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT r.*,
                       COUNT(DISTINCT m.id) AS total_messages,
                       COUNT(DISTINCT m.id) - COUNT(DISTINCT rr.message_id) AS unread_count
                FROM chat_rooms r
                JOIN chat_participants cp ON cp.room_id = r.id AND cp.user_id = ?
                LEFT JOIN chat_messages m ON m.room_id = r.id
                LEFT JOIN read_receipts rr ON rr.message_id = m.id AND rr.user_id = ?
                GROUP BY r.id
                ORDER BY r.created_at DESC
                """,
                (user_id, user_id),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------
    def send_message(
        self,
        room_id: int,
        sender_id: int | None,
        message_text: str,
        message_type: str = "text",
    ) -> dict:
        """Persist a message and return its record."""
        now = self._now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO chat_messages (room_id, sender_id, message_text, message_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (room_id, sender_id, message_text, message_type, now),
            )
            conn.commit()
            msg_id = cur.lastrowid
            return {
                "id": msg_id, "room_id": room_id, "sender_id": sender_id,
                "message_text": message_text, "message_type": message_type,
                "created_at": now, "edited_at": None,
            }
        finally:
            conn.close()

    def get_messages(
        self,
        room_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Return paginated messages for a room (newest last)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE room_id = ?
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
                """,
                (room_id, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def edit_message(self, message_id: int, new_text: str) -> bool:
        """Edit an existing message."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE chat_messages SET message_text = ?, edited_at = ? WHERE id = ?",
                (new_text, self._now(), message_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def delete_message(self, message_id: int) -> bool:
        """Soft-delete a message by replacing its text."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE chat_messages SET message_text = '[deleted]', "
                "message_type = 'deleted', edited_at = ? WHERE id = ?",
                (self._now(), message_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Read receipts
    # ------------------------------------------------------------------
    def mark_read(self, message_id: int, user_id: int) -> bool:
        """Mark a message as read by a user (idempotent)."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO read_receipts (message_id, user_id, read_at) "
                "VALUES (?, ?, ?)",
                (message_id, user_id, self._now()),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def mark_room_read(self, room_id: int, user_id: int) -> int:
        """Mark all messages in a room as read. Returns count of newly-read messages."""
        conn = self._conn()
        try:
            # Find all unread messages in the room for this user
            unread = conn.execute(
                """
                SELECT m.id FROM chat_messages m
                WHERE m.room_id = ?
                  AND m.id NOT IN (
                      SELECT message_id FROM read_receipts WHERE user_id = ?
                  )
                """,
                (room_id, user_id),
            ).fetchall()
            now = self._now()
            conn.executemany(
                "INSERT OR IGNORE INTO read_receipts (message_id, user_id, read_at) VALUES (?, ?, ?)",
                [(row["id"], user_id, now) for row in unread],
            )
            conn.commit()
            return len(unread)
        finally:
            conn.close()

    def get_unread_count(self, user_id: int) -> int:
        """Return total unread message count across all of the user's rooms."""
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM chat_messages m
                JOIN chat_participants cp ON cp.room_id = m.room_id AND cp.user_id = ?
                WHERE m.id NOT IN (
                    SELECT message_id FROM read_receipts WHERE user_id = ?
                )
                """,
                (user_id, user_id),
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()
