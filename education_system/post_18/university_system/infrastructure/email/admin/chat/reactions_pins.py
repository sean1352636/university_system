"""ReactionsPinsMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class ReactionsPinsMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def add_chat_reaction(self, message_id, emoji):
        """Add a reaction. Idempotent (PRIMARY KEY on message_id+user_id+emoji)."""
        if not self.auth or not self.auth.current_user or not emoji:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _add(cursor):
            cursor.execute(
                '''SELECT m.room_id FROM chat_messages m
                   JOIN chat_room_members mem
                     ON mem.room_id = m.room_id AND mem.user_id = ?
                   WHERE m.id = ? AND COALESCE(m.is_deleted, 0) = 0''',
                (user_id, message_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                '''INSERT INTO chat_message_reactions (message_id, user_id, emoji, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(message_id, user_id, emoji) DO NOTHING''',
                (message_id, user_id, emoji, now),
            )
            return True

        try:
            return execute_db_operation(_add)
        except Exception as e:
            log_event('error', f"Error adding reaction: {e}")
            return False

    @handle_exception
    def remove_chat_reaction(self, message_id, emoji):
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _remove(cursor):
            cursor.execute(
                'DELETE FROM chat_message_reactions WHERE message_id = ? AND user_id = ? AND emoji = ?',
                (message_id, user_id, emoji),
            )
            return True

        try:
            return execute_db_operation(_remove)
        except Exception as e:
            log_event('error', f"Error removing reaction: {e}")
            return False

    @handle_exception
    def get_chat_reactions_for_messages(self, message_ids):
        """Return {message_id: [{emoji, count, mine}]} aggregate."""
        if not self.auth or not self.auth.current_user or not message_ids:
            return {}
        user_id = self.auth.current_user['id']
        ids = [int(m) for m in message_ids]
        placeholders = ','.join('?' for _ in ids)

        def _get(cursor):
            cursor.execute(
                f'''SELECT message_id, emoji, COUNT(*),
                          SUM(CASE WHEN user_id = ? THEN 1 ELSE 0 END)
                   FROM chat_message_reactions
                   WHERE message_id IN ({placeholders})
                   GROUP BY message_id, emoji
                   ORDER BY message_id, emoji''',
                [user_id, *ids],
            )
            out = {}
            for mid, emoji, count, mine in cursor.fetchall():
                out.setdefault(mid, []).append({
                    'emoji': emoji, 'count': count, 'mine': bool(mine),
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting reactions: {e}")
            return {}

    @handle_exception
    def pin_chat_message(self, message_id, pin=True):
        """Pin or unpin a message. Requires room membership; admins can pin
        anyone's message, members can pin/unpin their own."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _pin(cursor):
            cursor.execute(
                'SELECT sender_id, room_id, COALESCE(is_deleted, 0) FROM chat_messages WHERE id = ?',
                (message_id,),
            )
            row = cursor.fetchone()
            if not row or row[2]:
                return False
            sender_id, room_id = row[0], row[1]
            cursor.execute(
                'SELECT is_admin FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            mem = cursor.fetchone()
            if not mem:
                return False
            if sender_id != user_id and not mem[0]:
                return False
            if pin:
                cursor.execute(
                    'UPDATE chat_messages SET pinned_at = ?, pinned_by = ? WHERE id = ?',
                    (now, user_id, message_id),
                )
            else:
                cursor.execute(
                    'UPDATE chat_messages SET pinned_at = NULL, pinned_by = NULL WHERE id = ?',
                    (message_id,),
                )
            self._log_communication_action(
                user_id, "pin_chat_message" if pin else "unpin_chat_message",
                f"{'Pinned' if pin else 'Unpinned'} chat message {message_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_pin)
        except Exception as e:
            log_event('error', f"Error pinning message: {e}")
            return False

    @handle_exception
    def get_pinned_messages(self, room_id):
        """List pinned messages in a room (newest first)."""
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return []
            cursor.execute(
                '''SELECT m.id, m.content, m.sent_at,
                          COALESCE(u.username, 'User ' || m.sender_id),
                          COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                          m.pinned_at,
                          COALESCE(pu.username, '')
                   FROM chat_messages m
                   LEFT JOIN users u ON m.sender_id = u.id
                   LEFT JOIN users pu ON m.pinned_by = pu.id
                   WHERE m.room_id = ? AND m.pinned_at IS NOT NULL
                     AND COALESCE(m.is_deleted, 0) = 0
                   ORDER BY m.pinned_at DESC''',
                (room_id,),
            )
            out = []
            for r in cursor.fetchall():
                full = f"{r[4]} {r[5]}".strip()
                out.append({
                    'id': r[0], 'content': r[1], 'sent_at': r[2],
                    'sender': r[3], 'sender_name': full or r[3],
                    'pinned_at': r[6], 'pinned_by': r[7],
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting pinned messages: {e}")
            return []

    # ------------------------------------------------------------------
    # Room administration: edit, archive, delete, transfer, favourite,
    # member moderation (kick/ban/mute, promote/demote).
    # ------------------------------------------------------------------

