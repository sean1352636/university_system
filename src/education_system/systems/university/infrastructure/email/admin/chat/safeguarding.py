"""SafeguardingMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class SafeguardingMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def add_filter_word(self, word, severity='flag'):
        """Append a word to the safeguarding wordlist. Admin role required."""
        if not self.auth or not self.auth.current_user:
            return False
        role = (self.auth.current_user.get('role') or '').lower()
        if role not in ('admin', 'staff'):
            return False
        word = (word or '').strip().lower()
        if not word:
            return False
        if severity not in ('flag', 'block'):
            severity = 'flag'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _add(cursor):
            cursor.execute(
                '''INSERT INTO chat_filter_words (word, severity, created_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(word) DO UPDATE SET severity = excluded.severity''',
                (word, severity, now),
            )
            return True

        try:
            return execute_db_operation(_add)
        except Exception as e:
            log_event('error', f"Error adding filter word: {e}")
            return False

    @handle_exception
    def remove_filter_word(self, word):
        if not self.auth or not self.auth.current_user:
            return False
        role = (self.auth.current_user.get('role') or '').lower()
        if role not in ('admin', 'staff'):
            return False
        word = (word or '').strip().lower()

        def _rm(cursor):
            cursor.execute('DELETE FROM chat_filter_words WHERE word = ?', (word,))
            return True

        try:
            return execute_db_operation(_rm)
        except Exception as e:
            log_event('error', f"Error removing filter word: {e}")
            return False

    @handle_exception
    def list_filter_words(self):
        def _ls(cursor):
            cursor.execute(
                'SELECT word, severity, created_at FROM chat_filter_words ORDER BY word'
            )
            return [{'word': r[0], 'severity': r[1], 'created_at': r[2]}
                    for r in cursor.fetchall()]

        try:
            return execute_db_operation(_ls)
        except Exception as e:
            log_event('error', f"Error listing filter words: {e}")
            return []

    @handle_exception
    def get_safeguarding_flags(self, room_id=None, status='all'):
        """Return safeguarding flag rows, newest first. Admin/staff or room admin only."""
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
            sql = '''SELECT f.id, f.message_id, f.room_id, f.user_id,
                            COALESCE(u.username, ''),
                            f.matched_word, f.severity, f.created_at,
                            m.content
                     FROM safeguarding_flags f
                     LEFT JOIN users u ON f.user_id = u.id
                     LEFT JOIN chat_messages m ON f.message_id = m.id'''
            params = []
            if room_id is not None:
                sql += ' WHERE f.room_id = ?'
                params.append(room_id)
            sql += ' ORDER BY f.created_at DESC LIMIT 500'
            cursor.execute(sql, params)
            return [
                {'id': r[0], 'message_id': r[1], 'room_id': r[2],
                 'user_id': r[3], 'username': r[4],
                 'matched_word': r[5], 'severity': r[6], 'created_at': r[7],
                 'message_excerpt': (r[8] or '')[:120]}
                for r in cursor.fetchall()
            ]

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting safeguarding flags: {e}")
            return []

    @handle_exception
    def report_chat_message(self, message_id, reason, escalate_safeguarding=False):
        """Open a report against a specific message. Any logged-in user can
        report. If escalate_safeguarding=True and the safeguarding tables are
        present, also create a safeguarding_submissions row and link it."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        username = self.auth.current_user.get('username') or ''
        full_name = self.auth.current_user.get('display_name') or username
        role = self.auth.current_user.get('role') or ''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _report(cursor):
            cursor.execute(
                'SELECT room_id, sender_id, content FROM chat_messages WHERE id = ?',
                (message_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            sg_id = None
            if escalate_safeguarding:
                try:
                    excerpt = (row[2] or '')[:500]
                    cursor.execute(
                        '''INSERT INTO safeguarding_submissions
                           (username, full_name, role, content, submitted_at,
                            severity, categories, status)
                           VALUES (?, ?, ?, ?, ?, 'High', '{"chat-report": []}', 'Pending')''',
                        (username, full_name, role,
                         f"Chat report (msg #{message_id}): {(reason or '')}"
                         f"\n\nExcerpt:\n{excerpt}", now),
                    )
                    sg_id = cursor.lastrowid
                except Exception:
                    sg_id = None

            cursor.execute(
                '''INSERT INTO chat_reports
                   (reporter_id, target_message_id, target_user_id, room_id,
                    reason, status, created_at, safeguarding_submission_id)
                   VALUES (?, ?, ?, ?, ?, 'open', ?, ?)''',
                (user_id, message_id, row[1], row[0], reason or '', now, sg_id),
            )
            self._log_communication_action(
                user_id, "report_chat_message",
                f"Reported message {message_id}"
                + (f" (safeguarding submission {sg_id})" if sg_id else "")
                + f": {(reason or '')[:80]}",
                cursor=cursor,
            )
            # Notify room admins so the reports panel doesn't have to be polled.
            try:
                cursor.execute(
                    '''SELECT user_id FROM chat_room_members
                       WHERE room_id = ? AND COALESCE(is_admin, 0) = 1''',
                    (row[0],),
                )
                for (admin_id,) in cursor.fetchall():
                    if admin_id == user_id:
                        continue
                    self._emit_notification(
                        cursor, admin_id,
                        "New chat report",
                        (reason or '(no reason given)')[:140],
                        ntype='chat_report',
                        data=f"message={message_id}",
                    )
            except Exception:
                pass
            return True

        try:
            return execute_db_operation(_report)
        except Exception as e:
            log_event('error', f"Error reporting message: {e}")
            return False

    @handle_exception
    def report_user(self, target_user_id, reason):
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        if user_id == target_user_id:
            return False
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _report(cursor):
            cursor.execute(
                '''INSERT INTO chat_reports
                   (reporter_id, target_user_id, reason, status, created_at)
                   VALUES (?, ?, ?, 'open', ?)''',
                (user_id, target_user_id, reason or '', now),
            )
            self._log_communication_action(
                user_id, "report_user",
                f"Reported user {target_user_id}: {(reason or '')[:80]}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_report)
        except Exception as e:
            log_event('error', f"Error reporting user: {e}")
            return False

    @handle_exception
    def list_chat_reports(self, status='open', room_id=None):
        """List reports. Admin/staff see all; room admins see their room's reports."""
        if not self.auth or not self.auth.current_user:
            return []
        user_id = self.auth.current_user['id']
        role = (self.auth.current_user.get('role') or '').lower()

        def _list(cursor):
            global_admin = role in ('admin', 'staff')
            params = []
            sql = '''SELECT r.id, r.reporter_id,
                            COALESCE(ur.username, ''),
                            r.target_message_id, r.target_user_id,
                            COALESCE(ut.username, ''),
                            r.room_id, COALESCE(rm.name, ''),
                            r.reason, r.status, r.created_at,
                            r.resolved_by, r.resolved_at, r.resolution_note,
                            (SELECT content FROM chat_messages WHERE id = r.target_message_id),
                            r.safeguarding_submission_id
                     FROM chat_reports r
                     LEFT JOIN users ur ON r.reporter_id = ur.id
                     LEFT JOIN users ut ON r.target_user_id = ut.id
                     LEFT JOIN chat_rooms rm ON r.room_id = rm.id'''
            wheres = []
            if status and status != 'all':
                wheres.append('r.status = ?')
                params.append(status)
            if room_id is not None:
                wheres.append('r.room_id = ?')
                params.append(room_id)
            elif not global_admin:
                # Limit non-global admins to rooms they administer.
                wheres.append('''r.room_id IN (
                    SELECT room_id FROM chat_room_members
                    WHERE user_id = ? AND COALESCE(is_admin, 0) = 1
                )''')
                params.append(user_id)
            if wheres:
                sql += ' WHERE ' + ' AND '.join(wheres)
            sql += ' ORDER BY r.created_at DESC LIMIT 500'
            cursor.execute(sql, params)
            return [
                {'id': r[0], 'reporter_id': r[1], 'reporter': r[2],
                 'target_message_id': r[3], 'target_user_id': r[4],
                 'target_user': r[5], 'room_id': r[6], 'room_name': r[7],
                 'reason': r[8], 'status': r[9], 'created_at': r[10],
                 'resolved_by': r[11], 'resolved_at': r[12],
                 'resolution_note': r[13],
                 'message_excerpt': (r[14] or '')[:160],
                 'safeguarding_submission_id': r[15]}
                for r in cursor.fetchall()
            ]

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing reports: {e}")
            return []

    @handle_exception
    def resolve_chat_report(self, report_id, resolution_note=''):
        """Mark a report resolved. Admin/staff or relevant room admin."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        role = (self.auth.current_user.get('role') or '').lower()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _resolve(cursor):
            cursor.execute('SELECT room_id FROM chat_reports WHERE id = ?', (report_id,))
            row = cursor.fetchone()
            if not row:
                return False
            global_admin = role in ('admin', 'staff')
            if not global_admin:
                if row[0] is None or not self._is_room_admin(cursor, row[0], user_id):
                    return False
            cursor.execute(
                '''UPDATE chat_reports
                   SET status = 'resolved', resolved_by = ?, resolved_at = ?,
                       resolution_note = ?
                   WHERE id = ?''',
                (user_id, now, resolution_note or '', report_id),
            )
            self._log_communication_action(
                user_id, "resolve_chat_report",
                f"Resolved report {report_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_resolve)
        except Exception as e:
            log_event('error', f"Error resolving report: {e}")
            return False

    @handle_exception
    def get_safeguarding_submission(self, submission_id):
        """Return the safeguarding case row, or None. Admin/staff only."""
        if not self.auth or not self.auth.current_user:
            return None
        role = (self.auth.current_user.get('role') or '').lower()
        if role not in ('admin', 'staff'):
            return None

        def _get(cursor):
            try:
                cursor.execute(
                    '''SELECT id, username, full_name, role, content, submitted_at,
                              severity, categories, status, reviewer, review_note, reviewed_at
                       FROM safeguarding_submissions WHERE id = ?''',
                    (submission_id,),
                )
                row = cursor.fetchone()
            except Exception:
                return None
            if not row:
                return None
            return {
                'id': row[0], 'username': row[1], 'full_name': row[2],
                'role': row[3], 'content': row[4], 'submitted_at': row[5],
                'severity': row[6], 'categories': row[7], 'status': row[8],
                'reviewer': row[9], 'review_note': row[10], 'reviewed_at': row[11],
            }

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting safeguarding submission: {e}")
            return None

    # ------------------------------------------------------------------
    # Cross-cutting: user profile lookup, notifications hub emission,
    # and proposing chat-poll dates as tentative calendar events.
    # ------------------------------------------------------------------

