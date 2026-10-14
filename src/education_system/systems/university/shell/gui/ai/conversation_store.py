"""Persistent, user-scoped conversation storage for the chatbot GUI."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from education_system.paths import UNIVERSITY_CHATBOT_DATA_DIR


class ConversationStore:
    """Small SQLite repository for titled conversations and ordered messages."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or (UNIVERSITY_CHATBOT_DATA_DIR / "gui_conversations.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS gui_conversations (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_gui_conversations_user_updated
                    ON gui_conversations(username, updated_at DESC);
                CREATE TABLE IF NOT EXISTS gui_conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES gui_conversations(id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS gui_conversation_feedback (
                    message_id INTEGER PRIMARY KEY,
                    helpful INTEGER NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (message_id) REFERENCES gui_conversation_messages(id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS gui_conversation_preferences (
                    username TEXT PRIMARY KEY,
                    history_enabled INTEGER NOT NULL DEFAULT 1,
                    retention_days INTEGER NOT NULL DEFAULT 90,
                    draft TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gui_conversation_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    scan_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES gui_conversations(id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS gui_conversation_drafts (
                    conversation_id TEXT PRIMARY KEY,
                    draft TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES gui_conversations(id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS gui_chat_memories (username TEXT, memory_key TEXT, memory_value TEXT, created_at TEXT, PRIMARY KEY(username,memory_key));
                CREATE TABLE IF NOT EXISTS gui_chat_handoffs (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, conversation_id TEXT, diagnostic_reference TEXT, status TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS gui_chat_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT);
                CREATE TABLE IF NOT EXISTS gui_chat_metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, event TEXT, duration_ms INTEGER, details TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS gui_chat_schema_version (version INTEGER NOT NULL);
            """)
            if connection.execute("SELECT COUNT(*) FROM gui_chat_schema_version").fetchone()[0] == 0:
                connection.execute("INSERT INTO gui_chat_schema_version VALUES (2)")
            columns = {row['name'] for row in connection.execute(
                "PRAGMA table_info(gui_conversations)"
            ).fetchall()}
            if 'pinned' not in columns:
                connection.execute(
                    "ALTER TABLE gui_conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"
                )
            if 'folder' not in columns:
                connection.execute(
                    "ALTER TABLE gui_conversations ADD COLUMN folder TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def create(self, username: str, title: str = "New conversation") -> str:
        conversation_id = uuid4().hex
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO gui_conversations "
                "(id, username, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, username, title, now, now),
            )
        return conversation_id

    def add_message(self, conversation_id: str, sender: str, message: str,
                    message_type: str) -> int:
        now = self._now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO gui_conversation_messages "
                "(conversation_id, sender, message, message_type, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, sender, message, message_type, now),
            )
            connection.execute(
                "UPDATE gui_conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            return int(cursor.lastrowid)

    def list(self, username: str, query: str = "", limit: int = 100, offset: int = 0) -> list[dict]:
        like = f"%{query.strip()}%"
        with self._connect() as connection:
            rows = connection.execute("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       c.pinned, c.folder,
                       COUNT(m.id) AS message_count
                FROM gui_conversations c
                LEFT JOIN gui_conversation_messages m ON m.conversation_id = c.id
                WHERE c.username = ? AND (? = '' OR c.title LIKE ? OR EXISTS (
                    SELECT 1 FROM gui_conversation_messages sm
                    WHERE sm.conversation_id = c.id AND sm.message LIKE ?
                ))
                GROUP BY c.id
                ORDER BY c.pinned DESC, c.updated_at DESC LIMIT ? OFFSET ?
            """, (username, query.strip(), like, like, min(500, limit), max(0, offset))).fetchall()
        return [dict(row) for row in rows]

    def messages(self, conversation_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sender, message, message_type, created_at "
                "FROM gui_conversation_messages WHERE conversation_id = ? "
                "ORDER BY id", (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def rename(self, conversation_id: str, title: str):
        title = title.strip()
        if not title:
            raise ValueError("Conversation title cannot be empty")
        with self._connect() as connection:
            connection.execute(
                "UPDATE gui_conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title[:120], self._now(), conversation_id),
            )

    def delete(self, conversation_id: str):
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM gui_conversations WHERE id = ?", (conversation_id,)
            )

    def delete_all(self, username: str):
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM gui_conversations WHERE username = ?", (username,)
            )

    def set_organisation(self, conversation_id: str, *, pinned=None, folder=None):
        updates = []
        values = []
        if pinned is not None:
            updates.append('pinned = ?')
            values.append(int(bool(pinned)))
        if folder is not None:
            updates.append('folder = ?')
            values.append(folder.strip()[:60])
        if not updates:
            return
        values.extend((self._now(), conversation_id))
        with self._connect() as connection:
            # db-audit: ignore[DBW001] - join over a code-controlled list
            connection.execute(
                f"UPDATE gui_conversations SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
                values,
            )

    def save_feedback(self, message_id: int, helpful: bool, comment: str = ''):
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO gui_conversation_feedback
                    (message_id, helpful, comment, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    helpful=excluded.helpful, comment=excluded.comment,
                    created_at=excluded.created_at
            """, (message_id, int(helpful), comment.strip()[:1000], self._now()))

    def preferences(self, username: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT history_enabled, retention_days, draft "
                "FROM gui_conversation_preferences WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else {'history_enabled': 1, 'retention_days': 90, 'draft': ''}

    def save_preferences(self, username: str, *, history_enabled: bool,
                         retention_days: int, draft: str = ''):
        retention_days = min(3650, max(1, int(retention_days)))
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO gui_conversation_preferences
                    (username, history_enabled, retention_days, draft, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    history_enabled=excluded.history_enabled,
                    retention_days=excluded.retention_days,
                    draft=excluded.draft, updated_at=excluded.updated_at
            """, (username, int(history_enabled), retention_days, draft[:10000], self._now()))

    def purge_expired(self, username: str, retention_days: int):
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM gui_conversations WHERE username = ? "
                "AND datetime(updated_at) < datetime('now', ?)",
                (username, f'-{max(1, int(retention_days))} days'),
            )

    def add_attachment(self, conversation_id: str, filename: str, path: str,
                       size: int, sha256: str, scan_status: str):
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO gui_conversation_attachments
                    (conversation_id, filename, path, size, sha256, scan_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (conversation_id, filename, path, size, sha256, scan_status, self._now()))

    def save_draft(self, conversation_id: str, draft: str):
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO gui_conversation_drafts (conversation_id, draft, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    draft=excluded.draft, updated_at=excluded.updated_at
            """, (conversation_id, draft[:10000], self._now()))

    def draft(self, conversation_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT draft FROM gui_conversation_drafts WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return row['draft'] if row else ''

    def memories(self, username):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT memory_key,memory_value FROM gui_chat_memories WHERE username=?", (username,))]

    def delete_memory(self, username, key):
        with self._connect() as c:
            c.execute("DELETE FROM gui_chat_memories WHERE username=? AND memory_key=?", (username, key))

    def create_handoff(self, username, conversation_id, reference=''):
        with self._connect() as c:
            cur = c.execute("INSERT INTO gui_chat_handoffs (username,conversation_id,diagnostic_reference,status,created_at) VALUES (?,?,?,?,?)", (username, conversation_id, reference, 'open', self._now()))
            c.execute("INSERT INTO gui_chat_notifications (username,message,created_at) VALUES (?,?,?)", (username, f'Support request #{cur.lastrowid} created.', self._now()))
            return cur.lastrowid

    def notifications(self, username):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT id,message,created_at FROM gui_chat_notifications WHERE username=? AND is_read=0 ORDER BY id DESC", (username,))]

    def metric(self, username, event, duration_ms=0, details=''):
        with self._connect() as c:
            c.execute("INSERT INTO gui_chat_metrics (username,event,duration_ms,details,created_at) VALUES (?,?,?,?,?)", (username,event,int(duration_ms),details[:500],self._now()))

    def metrics_summary(self, username):
        with self._connect() as c:
            rows=c.execute("SELECT event,COUNT(*) count,ROUND(AVG(duration_ms)) average_ms FROM gui_chat_metrics WHERE username=? GROUP BY event",(username,)).fetchall()
        return [dict(r) for r in rows]

    def cleanup_attachments(self, max_per_conversation=20):
        with self._connect() as c:
            c.execute("DELETE FROM gui_conversation_attachments WHERE id NOT IN (SELECT id FROM gui_conversation_attachments a2 WHERE a2.conversation_id=gui_conversation_attachments.conversation_id ORDER BY id DESC LIMIT ?)", (max_per_conversation,))

    def backup(self, destination):
        """Create a recoverable snapshot after committing the current schema."""
        destination=Path(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        return destination

    def schema_version(self):
        with self._connect() as c:
            return c.execute("SELECT MAX(version) FROM gui_chat_schema_version").fetchone()[0]

    def title_from_first_message(self, conversation_id: str, message: str):
        title = " ".join(message.split())[:60]
        if title:
            with self._connect() as connection:
                connection.execute("""
                    UPDATE gui_conversations SET title = ?, updated_at = ?
                    WHERE id = ? AND title = 'New conversation'
                """, (title, self._now(), conversation_id))
