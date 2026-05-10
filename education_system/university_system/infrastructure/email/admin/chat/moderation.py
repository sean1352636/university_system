"""ModerationMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class ModerationMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def kick_room_member(self, room_id, target_user_id, reason=None):
        """Remove a member from a room. Admin/creator only; cannot kick the creator."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        room_name_for_email = ''

        def _kick(cursor):
            nonlocal room_name_for_email
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by, name FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id:
                return False
            if row:
                room_name_for_email = row[1] or ''
            cursor.execute(
                'DELETE FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "kick_room_member",
                f"Kicked user {target_user_id} from room {room_id}"
                + (f" — reason: {reason}" if reason else ""),
                cursor=cursor,
            )
            return True

        try:
            ok = execute_db_operation(_kick)
        except Exception as e:
            log_event('error', f"Error kicking member: {e}")
            return False
        if ok:
            self._email_room_action_notice(
                target_user_id, action='kicked',
                room_name=room_name_for_email, reason=reason,
            )
        return ok

    @handle_exception
    def ban_room_member(self, room_id, target_user_id, banned=True, reason=None):
        """Ban (or unban) a user from a room.

        Ban: records (room_id, user_id) in chat_room_bans AND removes any
        existing membership row, so the ban survives a leave/rejoin attempt
        on a public room. The legacy `is_banned` flag on chat_room_members
        is also flipped if a row remains, for backwards compatibility.

        Unban: deletes the chat_room_bans row; the user can then rejoin
        public rooms or be re-invited."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        room_name_for_email = ''

        def _ban(cursor):
            nonlocal room_name_for_email
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by, name FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id and banned:
                # Can't ban the creator.
                return False
            if row:
                room_name_for_email = row[1] or ''
            if banned:
                cursor.execute(
                    '''INSERT INTO chat_room_bans
                       (room_id, user_id, banned_at, banned_by, reason)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(room_id, user_id) DO UPDATE SET
                           banned_at = excluded.banned_at,
                           banned_by = excluded.banned_by,
                           reason = excluded.reason''',
                    (room_id, target_user_id, now, user_id, reason or ''),
                )
                # Remove from membership so they're no longer in the room.
                cursor.execute(
                    'DELETE FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, target_user_id),
                )
                # Cancel any pending invitations.
                try:
                    cursor.execute(
                        '''UPDATE chat_room_invitations SET status = 'revoked'
                           WHERE room_id = ? AND user_id = ? AND status = 'pending' ''',
                        (room_id, target_user_id),
                    )
                except Exception:
                    pass
            else:
                cursor.execute(
                    'DELETE FROM chat_room_bans WHERE room_id = ? AND user_id = ?',
                    (room_id, target_user_id),
                )
                # Clear legacy flag if a stale membership row still exists.
                cursor.execute(
                    'UPDATE chat_room_members SET is_banned = 0 '
                    'WHERE room_id = ? AND user_id = ?',
                    (room_id, target_user_id),
                )
            self._log_communication_action(
                user_id, "ban_room_member" if banned else "unban_room_member",
                f"{'Banned' if banned else 'Unbanned'} user {target_user_id} in room {room_id}"
                + (f" — reason: {reason}" if banned and reason else ""),
                cursor=cursor,
            )
            return True

        try:
            ok = execute_db_operation(_ban)
        except Exception as e:
            log_event('error', f"Error banning member: {e}")
            return False
        if ok:
            self._email_room_action_notice(
                target_user_id,
                action='banned' if banned else 'unbanned',
                room_name=room_name_for_email, reason=reason,
            )
        return ok

    @handle_exception
    def list_room_bans(self, room_id):
        """List active bans for a room. Admin/creator only."""
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']

        def _list(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return []
            cursor.execute(
                '''SELECT b.user_id,
                          COALESCE(u.username, ''),
                          COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                          b.banned_at,
                          COALESCE(bu.username, ''),
                          b.reason
                   FROM chat_room_bans b
                   LEFT JOIN users u ON b.user_id = u.id
                   LEFT JOIN users bu ON b.banned_by = bu.id
                   WHERE b.room_id = ?
                   ORDER BY b.banned_at DESC''',
                (room_id,),
            )
            out = []
            for r in cursor.fetchall():
                full = f"{r[2]} {r[3]}".strip()
                out.append({
                    'user_id': r[0], 'username': r[1],
                    'full_name': full or r[1],
                    'banned_at': r[4],
                    'banned_by': r[5] or '',
                    'reason': r[6] or '',
                })
            return out

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing room bans: {e}")
            return []

    @handle_exception
    def mute_room_member(self, room_id, target_user_id, minutes=None, reason=None):
        """Mute a member for the given minutes; pass minutes=None to unmute."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        from datetime import timedelta
        if minutes is None or int(minutes) <= 0:
            until = None
        else:
            until = (datetime.now() + timedelta(minutes=int(minutes))).strftime(
                '%Y-%m-%d %H:%M:%S'
            )
        room_name_for_email = ''

        def _mute(cursor):
            nonlocal room_name_for_email
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT name FROM chat_rooms WHERE id = ?', (room_id,))
            r = cursor.fetchone()
            if r:
                room_name_for_email = r[0] or ''
            cursor.execute(
                'UPDATE chat_room_members SET muted_until = ? WHERE room_id = ? AND user_id = ?',
                (until, room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "mute_room_member",
                f"Muted user {target_user_id} in room {room_id} until {until}"
                + (f" — reason: {reason}" if reason else ""),
                cursor=cursor,
            )
            return True

        try:
            ok = execute_db_operation(_mute)
        except Exception as e:
            log_event('error', f"Error muting member: {e}")
            return False
        if ok and until:  # only email when actually muting (not unmuting)
            self._email_room_action_notice(
                target_user_id, action='muted',
                room_name=room_name_for_email, reason=reason,
                muted_until=until,
            )
        return ok

    def _email_room_action_notice(self, target_user_id, *, action,
                                  room_name='', reason=None, muted_until=None):
        """Send a templated email telling a user they've been kicked / banned /
        unbanned / muted. Best-effort: failures are logged and swallowed so a
        moderation action never fails because of an email-side issue."""
        templates = {
            'kicked': 'communications/chat_room_kicked',
            'banned': 'communications/chat_room_banned',
            'muted': 'communications/chat_room_muted',
        }
        template_path = templates.get(action)
        if not template_path:
            return
        try:
            from education_system.university_system.infrastructure.email.template_utils import (
                load_template,
            )
            from education_system.university_system.infrastructure.email.email_service.queue import (
                queue_email,
            )
        except Exception as e:
            log_event('debug', f"Email template/queue not available: {e}")
            return

        def _lookup(cursor):
            cursor.execute(
                '''SELECT COALESCE(email, ''),
                          COALESCE(first_name, ''), COALESCE(last_name, ''),
                          COALESCE(username, '')
                   FROM users WHERE id = ?''',
                (target_user_id,),
            )
            target = cursor.fetchone()
            actor_name = ''
            if self.auth and self.auth.current_user:
                actor_name = (self.auth.current_user.get('display_name')
                              or self.auth.current_user.get('username') or '')
            return target, actor_name

        try:
            target_row, actor_name = execute_db_operation(_lookup)
        except Exception as e:
            log_event('debug', f"Couldn't look up target for email notice: {e}")
            return
        if not target_row or not target_row[0]:
            return  # no email address on file
        recipient_email = target_row[0]
        full_name = f"{target_row[1]} {target_row[2]}".strip() or target_row[3]

        try:
            template = load_template(template_path)
        except Exception as e:
            log_event('warning', f"Could not load email template {template_path}: {e}")
            return
        if not template:
            log_event('warning', f"Email template {template_path} not found")
            return

        from string import Template as _StrTemplate
        variables = {
            'user_name': full_name,
            'room_name': room_name or '(unnamed room)',
            'actor_name': actor_name or 'A room admin',
            'action_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'reason': (reason or 'No reason provided.'),
            'muted_until': muted_until or 'Until lifted by an admin',
        }
        try:
            subject = _StrTemplate(template.get('subject') or '').safe_substitute(variables)
            body = _StrTemplate(template.get('body') or '').safe_substitute(variables)
        except Exception as e:
            log_event('warning', f"Email template substitution failed: {e}")
            return
        try:
            queue_email(recipient_email, subject, body)
            log_event('info',
                      f"Sent room-{action} notice email to {recipient_email}")
        except Exception as e:
            log_event('warning', f"Could not send room-{action} notice email: {e}")

