"""NotesMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class NotesMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def get_room_notes(self, room_id):
        """Return shared notes as {content, updated_at, updated_by_username, version}."""
        if not self.auth or not self.auth.current_user:
            return None
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return None
            cursor.execute(
                '''SELECT n.content, n.updated_at, COALESCE(u.username, ''),
                          COALESCE(n.version, 1)
                   FROM chat_room_notes n
                   LEFT JOIN users u ON n.updated_by = u.id
                   WHERE n.room_id = ?''',
                (room_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {'content': '', 'updated_at': None,
                        'updated_by_username': None, 'version': 0}
            return {
                'content': row[0] or '',
                'updated_at': row[1],
                'updated_by_username': row[2] or None,
                'version': int(row[3] or 1),
            }

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting room notes: {e}")
            return None

    @handle_exception
    def set_room_notes(self, room_id, content, expected_version=None):
        """Save shared notes for a room. Any room member can edit.

        If expected_version is supplied, the save is rejected with the string
        'version_conflict' when the on-disk version no longer matches — the
        caller should reload and reapply. Returns True on success."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _set(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return False
            current_version = 0
            cursor.execute(
                'SELECT COALESCE(version, 1) FROM chat_room_notes WHERE room_id = ?',
                (room_id,),
            )
            row = cursor.fetchone()
            if row:
                current_version = int(row[0] or 1)
            if expected_version is not None and current_version and \
                    int(expected_version) != current_version:
                return 'version_conflict'
            new_version = (current_version or 0) + 1
            cursor.execute(
                '''INSERT INTO chat_room_notes
                       (room_id, content, updated_at, updated_by, version)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(room_id) DO UPDATE SET
                       content = excluded.content,
                       updated_at = excluded.updated_at,
                       updated_by = excluded.updated_by,
                       version = excluded.version''',
                (room_id, content or '', now, user_id, new_version),
            )
            return True

        try:
            return execute_db_operation(_set)
        except Exception as e:
            log_event('error', f"Error saving room notes: {e}")
            return False

