"""BlockingMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class BlockingMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def block_user(self, target_user_id):
        """Block a user from sending you direct messages."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        if user_id == target_user_id:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _block(cursor):
            cursor.execute(
                '''INSERT INTO dm_blocks (user_id, blocked_user_id, created_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, blocked_user_id) DO NOTHING''',
                (user_id, target_user_id, now),
            )
            return True

        try:
            return execute_db_operation(_block)
        except Exception as e:
            log_event('error', f"Error blocking user: {e}")
            return False

    @handle_exception
    def unblock_user(self, target_user_id):
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _unblock(cursor):
            cursor.execute(
                'DELETE FROM dm_blocks WHERE user_id = ? AND blocked_user_id = ?',
                (user_id, target_user_id),
            )
            return True

        try:
            return execute_db_operation(_unblock)
        except Exception as e:
            log_event('error', f"Error unblocking user: {e}")
            return False

    @handle_exception
    def list_blocked_users(self):
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']

        def _list(cursor):
            cursor.execute(
                '''SELECT b.blocked_user_id, COALESCE(u.username, ''),
                          COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                          b.created_at
                   FROM dm_blocks b
                   LEFT JOIN users u ON b.blocked_user_id = u.id
                   WHERE b.user_id = ?
                   ORDER BY u.username''',
                (user_id,),
            )
            out = []
            for r in cursor.fetchall():
                full = f"{r[2]} {r[3]}".strip()
                out.append({
                    'user_id': r[0], 'username': r[1],
                    'full_name': full or r[1],
                    'created_at': r[4],
                })
            return out

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing blocks: {e}")
            return []

    @handle_exception
    def is_user_blocked(self, owner_user_id, target_user_id):
        """Return True if target_user_id is blocked by owner_user_id."""
        def _q(cursor):
            cursor.execute(
                'SELECT 1 FROM dm_blocks WHERE user_id = ? AND blocked_user_id = ?',
                (owner_user_id, target_user_id),
            )
            return cursor.fetchone() is not None

        try:
            return execute_db_operation(_q)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Cross-module integration: academics (assignments / module info) and
    # staff_hr (department-as-team mentions).
    # ------------------------------------------------------------------

