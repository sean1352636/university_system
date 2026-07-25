"""AuditGdprMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class AuditGdprMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def get_communication_audit_log(self, room_id=None, action_type=None, limit=200):
        """Read the communication_log table (already populated by the various
        moderation actions). Admin/staff or room admin only."""
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']
        role = (self.auth.current_user.get('role') or '').lower()

        def _get(cursor):
            global_admin = role in ('admin', 'staff')
            if room_id is not None and not global_admin:
                if not self._is_room_admin(cursor, room_id, user_id):
                    return []
            elif not global_admin:
                return []
            sql = '''SELECT cl.id, cl.user_id,
                            COALESCE(u.username, ''),
                            cl.action_type, cl.action_details, cl.performed_at
                     FROM communication_log cl
                     LEFT JOIN users u ON cl.user_id = u.id'''
            params, where = [], []
            if action_type:
                where.append('cl.action_type = ?')
                params.append(action_type)
            if room_id is not None:
                where.append('cl.action_details LIKE ?')
                params.append(f"%room {room_id}%")
            if where:
                sql += ' WHERE ' + ' AND '.join(where)
            sql += ' ORDER BY cl.performed_at DESC LIMIT ?'
            params.append(int(limit))
            cursor.execute(sql, params)
            return [
                {'id': r[0], 'user_id': r[1], 'username': r[2],
                 'action_type': r[3], 'details': r[4], 'performed_at': r[5]}
                for r in cursor.fetchall()
            ]

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting audit log: {e}")
            return []

    @handle_exception
    def export_user_chat_history(self, target_user_id=None):
        """GDPR-style export. Users may export their own data; admin/staff
        may export any user's. Returns a dict ready to be JSON-serialised."""
        if not self.auth or not self.auth.current_user:
            return None
        caller_id = self.auth.current_user['id']
        role = (self.auth.current_user.get('role') or '').lower()
        target_id = target_user_id or caller_id
        if target_id != caller_id and role not in ('admin', 'staff'):
            return None

        def _export(cursor):
            out = {'user_id': target_id, 'generated_at':
                   datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            cursor.execute(
                '''SELECT m.id, m.room_id, r.name, m.content, m.sent_at,
                          m.edited_at, COALESCE(m.is_deleted, 0)
                   FROM chat_messages m
                   JOIN chat_rooms r ON r.id = m.room_id
                   WHERE m.sender_id = ? ORDER BY m.sent_at''',
                (target_id,),
            )
            out['messages'] = [
                {'id': r[0], 'room_id': r[1], 'room_name': r[2],
                 'content': r[3], 'sent_at': r[4],
                 'edited_at': r[5], 'is_deleted': bool(r[6])}
                for r in cursor.fetchall()
            ]
            cursor.execute(
                '''SELECT v.option_id, o.label, p.question, v.voted_at
                   FROM chat_poll_votes v
                   JOIN chat_poll_options o ON o.id = v.option_id
                   JOIN chat_polls p ON p.message_id = o.message_id
                   WHERE v.user_id = ?''',
                (target_id,),
            )
            out['poll_votes'] = [
                {'option_id': r[0], 'option_label': r[1],
                 'question': r[2], 'voted_at': r[3]}
                for r in cursor.fetchall()
            ]
            cursor.execute(
                '''SELECT message_id, emoji, created_at
                   FROM chat_message_reactions WHERE user_id = ?''',
                (target_id,),
            )
            out['reactions'] = [
                {'message_id': r[0], 'emoji': r[1], 'created_at': r[2]}
                for r in cursor.fetchall()
            ]
            cursor.execute(
                '''SELECT room_id, joined_at, COALESCE(is_admin, 0)
                   FROM chat_room_members WHERE user_id = ?''',
                (target_id,),
            )
            out['memberships'] = [
                {'room_id': r[0], 'joined_at': r[1], 'is_admin': bool(r[2])}
                for r in cursor.fetchall()
            ]
            return out

        try:
            return execute_db_operation(_export)
        except Exception as e:
            log_event('error', f"Error exporting chat history: {e}")
            return None

    @handle_exception
    def erase_user_chat_history(self, target_user_id=None):
        """GDPR-style erasure. Soft-deletes message content and removes
        reactions/poll votes. Users may erase their own data; admin/staff any."""
        if not self.auth or not self.auth.current_user:
            return False
        caller_id = self.auth.current_user['id']
        role = (self.auth.current_user.get('role') or '').lower()
        target_id = target_user_id or caller_id
        if target_id != caller_id and role not in ('admin', 'staff'):
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _erase(cursor):
            cursor.execute(
                '''UPDATE chat_messages
                   SET is_deleted = 1, content = '', edited_at = ?
                   WHERE sender_id = ?''',
                (now, target_id),
            )
            cursor.execute(
                'DELETE FROM chat_message_reactions WHERE user_id = ?', (target_id,),
            )
            cursor.execute(
                'DELETE FROM chat_poll_votes WHERE user_id = ?', (target_id,),
            )
            cursor.execute(
                'DELETE FROM chat_typing WHERE user_id = ?', (target_id,),
            )
            cursor.execute(
                'DELETE FROM chat_presence WHERE user_id = ?', (target_id,),
            )
            self._log_communication_action(
                caller_id, "erase_user_chat_history",
                f"Erased chat history for user {target_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_erase)
        except Exception as e:
            log_event('error', f"Error erasing chat history: {e}")
            return False

