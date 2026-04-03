"""
Chat Manager
Handles virtual session chat and Q&A
"""

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

class ChatManager:
    """Manager for virtual session chat operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def send_message(
        self,
        session_id: int,
        user_id: int,
        user_name: str,
        message_text: str,
        message_type: str = 'public',
        recipient_id: Optional[int] = None,
        replied_to: Optional[int] = None
    ) -> Optional[int]:
        """Send a chat message"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                valid_types = ['public', 'private', 'announcement']
                if message_type not in valid_types:
                    raise ValueError(f"Invalid message type. Must be one of: {valid_types}")

                if message_type == 'private' and not recipient_id:
                    raise ValueError("recipient_id required for private messages")

                cursor.execute("""
                    INSERT INTO virtual_chat_messages (
                        session_id, user_id, user_name, message_text,
                        message_type, recipient_id, replied_to
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, user_id, user_name, message_text,
                      message_type, recipient_id, replied_to))

                # Update participant chat message count
                cursor.execute("""
                    UPDATE session_participants
                    SET chat_message_count = chat_message_count + 1
                    WHERE session_id = ? AND user_id = ?
                """, (session_id, user_id))

                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error sending message: {e}")
            return None

    def delete_message(self, message_id: int) -> bool:
        """Soft delete a message"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_chat_messages
                    SET is_deleted = 1
                    WHERE message_id = ?
                """, (message_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False

    def add_reaction(
        self,
        message_id: int,
        emoji: str,
        increment: bool = True
    ) -> bool:
        """Add or remove a reaction to a message"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get current reactions
                cursor.execute("""
                    SELECT reactions FROM virtual_chat_messages
                    WHERE message_id = ?
                """, (message_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                reactions = json.loads(row[0]) if row[0] else {}

                # Update reaction count
                if increment:
                    reactions[emoji] = reactions.get(emoji, 0) + 1
                else:
                    if emoji in reactions:
                        reactions[emoji] = max(0, reactions[emoji] - 1)
                        if reactions[emoji] == 0:
                            del reactions[emoji]

                cursor.execute("""
                    UPDATE virtual_chat_messages
                    SET reactions = ?
                    WHERE message_id = ?
                """, (json.dumps(reactions), message_id))

                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding reaction: {e}")
            return False

    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Get a message by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_chat_messages
                    WHERE message_id = ?
                """, (message_id,))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    result = dict(zip(columns, row))
                    if result.get('reactions'):
                        result['reactions'] = json.loads(result['reactions'])
                    return result
                return None
        except Exception as e:
            print(f"Error getting message: {e}")
            return None

    def get_session_messages(
        self,
        session_id: int,
        message_type: Optional[str] = None,
        user_id: Optional[int] = None,
        include_deleted: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM virtual_chat_messages WHERE session_id = ?"
                params = [session_id]

                if message_type:
                    query += " AND message_type = ?"
                    params.append(message_type)

                if user_id:
                    query += " AND (user_id = ? OR recipient_id = ?)"
                    params.extend([user_id, user_id])

                if not include_deleted:
                    query += " AND is_deleted = 0"

                query += " ORDER BY timestamp DESC, message_id DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('reactions'):
                        result['reactions'] = json.loads(result['reactions'])
                    results.append(result)

                return results
        except Exception as e:
            print(f"Error getting session messages: {e}")
            return []

    def get_thread_messages(
        self,
        parent_message_id: int
    ) -> List[Dict[str, Any]]:
        """Get all replies to a message"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_chat_messages
                    WHERE replied_to = ? AND is_deleted = 0
                    ORDER BY timestamp ASC
                """, (parent_message_id,))

                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('reactions'):
                        result['reactions'] = json.loads(result['reactions'])
                    results.append(result)

                return results
        except Exception as e:
            print(f"Error getting thread messages: {e}")
            return []

    def search_messages(
        self,
        session_id: int,
        search_term: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search messages by text"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM virtual_chat_messages
                    WHERE session_id = ?
                    AND message_text LIKE ?
                    AND is_deleted = 0
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, f"%{escape_like(search_term)}%", limit))

                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('reactions'):
                        result['reactions'] = json.loads(result['reactions'])
                    results.append(result)

                return results
        except Exception as e:
            print(f"Error searching messages: {e}")
            return []

    def get_chat_statistics(self, session_id: int) -> Dict[str, Any]:
        """Get chat statistics for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total messages
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_messages,
                        COUNT(DISTINCT user_id) as active_users,
                        SUM(CASE WHEN message_type = 'public' THEN 1 ELSE 0 END) as public_messages,
                        SUM(CASE WHEN message_type = 'private' THEN 1 ELSE 0 END) as private_messages,
                        SUM(CASE WHEN message_type = 'announcement' THEN 1 ELSE 0 END) as announcements
                    FROM virtual_chat_messages
                    WHERE session_id = ? AND is_deleted = 0
                """, (session_id,))

                stats = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))

                # Top contributors
                cursor.execute("""
                    SELECT user_name, COUNT(*) as message_count
                    FROM virtual_chat_messages
                    WHERE session_id = ? AND is_deleted = 0
                    GROUP BY user_id, user_name
                    ORDER BY message_count DESC
                    LIMIT 5
                """, (session_id,))

                stats['top_contributors'] = [
                    {'user_name': row[0], 'message_count': row[1]}
                    for row in cursor.fetchall()
                ]

                return stats
        except Exception as e:
            print(f"Error getting chat statistics: {e}")
            return {}

    def clear_session_chat(self, session_id: int) -> bool:
        """Clear all messages for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE virtual_chat_messages
                    SET is_deleted = 1
                    WHERE session_id = ?
                """, (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error clearing session chat: {e}")
            return False
