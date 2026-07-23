"""PresenceMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class PresenceMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def set_chat_typing(self, room_id):
        """Mark the current user as typing in a room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _set(cursor):
            cursor.execute(
                '''
                INSERT INTO chat_typing (user_id, room_id, started_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, room_id) DO UPDATE SET started_at = excluded.started_at
                ''',
                (user_id, room_id, now),
            )
            return True

        try:
            return execute_db_operation(_set)
        except Exception as e:
            log_event('error', f"Error setting typing: {e}")
            return False

    @handle_exception
    def clear_chat_typing(self, room_id):
        """Clear the current user's typing flag in a room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _clear(cursor):
            cursor.execute(
                'DELETE FROM chat_typing WHERE user_id = ? AND room_id = ?',
                (user_id, room_id),
            )
            return True

        try:
            return execute_db_operation(_clear)
        except Exception as e:
            log_event('error', f"Error clearing typing: {e}")
            return False

    @handle_exception
    def get_chat_typing_users(self, room_id, max_age_seconds=5):
        """Return display names of room members typing within the last N seconds,
        excluding the current user."""
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        def _get(cursor):
            cursor.execute(
                '''
                SELECT COALESCE(u.username, 'User ' || u.id),
                       COALESCE(u.first_name, ''), COALESCE(u.last_name, '')
                FROM chat_typing t
                JOIN users u ON u.id = t.user_id
                WHERE t.room_id = ? AND t.user_id != ? AND t.started_at >= ?
                ORDER BY t.started_at ASC
                ''',
                (room_id, user_id, cutoff),
            )
            names = []
            for row in cursor.fetchall():
                full = f"{row[1]} {row[2]}".strip()
                names.append(full or row[0])
            return names

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting typing users: {e}")
            return []

    @handle_exception
    def update_chat_presence(self, room_id):
        """Heartbeat: mark current user as active in a room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _hb(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                '''
                INSERT INTO chat_presence (user_id, room_id, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, room_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
                ''',
                (user_id, room_id, now),
            )
            return True

        try:
            return execute_db_operation(_hb)
        except Exception as e:
            log_event('error', f"Error updating presence: {e}")
            return False

    @handle_exception
    def get_chat_presence(self, room_id, online_window_seconds=30):
        """Return a list of {user_id, last_seen_at, is_online} for room members."""
        if not self.auth or not self.auth.current_user:
            return []
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(seconds=online_window_seconds)).strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        def _get(cursor):
            cursor.execute(
                '''
                SELECT mem.user_id, p.last_seen_at,
                       CASE WHEN p.last_seen_at IS NOT NULL AND p.last_seen_at >= ? THEN 1 ELSE 0 END
                FROM chat_room_members mem
                LEFT JOIN chat_presence p
                  ON p.room_id = mem.room_id AND p.user_id = mem.user_id
                WHERE mem.room_id = ?
                ''',
                (cutoff, room_id),
            )
            return [
                {'user_id': r[0], 'last_seen_at': r[1], 'is_online': bool(r[2])}
                for r in cursor.fetchall()
            ]

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting presence: {e}")
            return []

    # ------------------------------------------------------------------
    # Edit / delete / reply / reactions / pin / search
    # ------------------------------------------------------------------

    @handle_exception
    def raise_hand(self, room_id):
        """Add the current user to a room's queue (idempotent)."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _raise(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                '''SELECT 1 FROM chat_room_queue
                   WHERE room_id = ? AND user_id = ? AND status = 'waiting' ''',
                (room_id, user_id),
            )
            if cursor.fetchone():
                return True
            cursor.execute(
                '''INSERT INTO chat_room_queue (room_id, user_id, joined_at, status)
                   VALUES (?, ?, ?, 'waiting')''',
                (room_id, user_id, now),
            )
            return True

        try:
            return execute_db_operation(_raise)
        except Exception as e:
            log_event('error', f"Error raising hand: {e}")
            return False

    @handle_exception
    def lower_hand(self, room_id):
        """Remove the current user from the queue."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _lower(cursor):
            cursor.execute(
                '''DELETE FROM chat_room_queue
                   WHERE room_id = ? AND user_id = ? AND status = 'waiting' ''',
                (room_id, user_id),
            )
            return True

        try:
            return execute_db_operation(_lower)
        except Exception as e:
            log_event('error', f"Error lowering hand: {e}")
            return False

    @handle_exception
    def get_room_queue(self, room_id):
        """Return waiting queue (oldest first) as list of {user_id, username, full_name, joined_at, mine}."""
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
                '''SELECT q.user_id, COALESCE(u.username, ''),
                          COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                          q.joined_at
                   FROM chat_room_queue q
                   LEFT JOIN users u ON q.user_id = u.id
                   WHERE q.room_id = ? AND q.status = 'waiting'
                   ORDER BY q.joined_at ASC''',
                (room_id,),
            )
            out = []
            for r in cursor.fetchall():
                full = f"{r[2]} {r[3]}".strip()
                out.append({
                    'user_id': r[0], 'username': r[1],
                    'full_name': full or r[1],
                    'joined_at': r[4],
                    'mine': r[0] == user_id,
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting queue: {e}")
            return []

    @handle_exception
    def call_next_in_queue(self, room_id):
        """Mark the head of the queue as 'called'. Admin/creator only.
        Returns the called member dict or None."""
        if not self.auth or not self.auth.current_user:
            return None
        user_id = self.auth.current_user['id']

        def _call(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return None
            cursor.execute(
                '''SELECT id, user_id FROM chat_room_queue
                   WHERE room_id = ? AND status = 'waiting'
                   ORDER BY joined_at ASC LIMIT 1''',
                (room_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                "UPDATE chat_room_queue SET status = 'called' WHERE id = ?",
                (row[0],),
            )
            cursor.execute(
                '''SELECT COALESCE(u.username, ''),
                          COALESCE(u.first_name, ''), COALESCE(u.last_name, '')
                   FROM users u WHERE u.id = ?''',
                (row[1],),
            )
            r = cursor.fetchone() or ('', '', '')
            full = f"{r[1]} {r[2]}".strip()
            # Post a system message that @mentions the called user. The
            # mention pipeline picks this up and emits a notification.
            sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            handle = r[0] or f"User {row[1]}"
            content = f"@{handle} you're up — please join the conversation."
            sender_for_msg = self._get_or_create_system_user_id(cursor, user_id)
            cursor.execute(
                '''INSERT INTO chat_messages
                   (room_id, sender_id, content, sent_at)
                   VALUES (?, ?, ?, ?)''',
                (room_id, sender_for_msg, content, sent_at),
            )
            new_msg_id = cursor.lastrowid
            try:
                self._emit_chat_mention_notifications(
                    cursor, room_id, sender_for_msg, 'System', content, new_msg_id,
                )
            except Exception:
                pass
            return {'user_id': row[1], 'username': r[0], 'full_name': full or r[0]}

        try:
            return execute_db_operation(_call)
        except Exception as e:
            log_event('error', f"Error calling next in queue: {e}")
            return None

    # ------------------------------------------------------------------
    # Safety & compliance: filter wordlist, reports, audit log, GDPR,
    # retention, rate-limit (already wired in send_chat_message),
    # at-rest encryption (per-room key), DM block list.
    # ------------------------------------------------------------------

