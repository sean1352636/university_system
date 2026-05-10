"""MessagesMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)
from ._helpers import _scan_filter_words, _ensure_room_key, _encrypt_with_key, _format_message_row


class MessagesMixin:
    """Methods grouped from the original _ChatMixin."""

    @handle_exception
    def send_chat_message(self, room_id, content, reply_to_id=None,
                          attachment_path=None, attachment_name=None,
                          attachment_mime=None, attachment_size=None):
        """Send a message to a chat room.

        Optional reply_to_id sets a parent message; attachment_* fields record
        a file reference (the file itself is stored on disk by the caller).
        """
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to send chat messages")
            return False

        has_text = bool(content and content.strip())
        has_attachment = bool(attachment_path)
        if not has_text and not has_attachment:
            log_event('error', "Message must have content or an attachment")
            return False

        def _send_message(cursor):
            user_id = self.auth.current_user['id']
            sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT COALESCE(is_banned, 0), muted_until FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))
            mem_row = cursor.fetchone()
            if not mem_row:
                log_event('error', f"User not a member of room {room_id}")
                return False
            if mem_row[0]:
                log_event('error', f"User banned from room {room_id}")
                return False
            if mem_row[1] and mem_row[1] >= datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                log_event('error', f"User muted in room {room_id} until {mem_row[1]}")
                return False

            cursor.execute(
                'SELECT is_active, COALESCE(announcement_mode, 0), oh_starts_at, oh_ends_at, '
                'COALESCE(slow_mode_seconds, 0), COALESCE(is_encrypted, 0) '
                'FROM chat_rooms WHERE id = ?', (room_id,),
            )
            room_data = cursor.fetchone()
            if not room_data or not room_data[0]:
                log_event('error', f"Room {room_id} not found or inactive")
                return False

            # Announcement-only and office-hours window guards (admins exempt).
            is_admin_in_room = self._is_room_admin(cursor, room_id, user_id) \
                if hasattr(self, '_is_room_admin') else False
            if room_data[1] and not is_admin_in_room:
                log_event('error', f"Room {room_id} is announcement-only")
                return False
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            oh_start, oh_end = room_data[2], room_data[3]
            if (oh_start or oh_end) and not is_admin_in_room:
                if oh_start and now_str < oh_start:
                    log_event('error', f"Office hours not yet open for room {room_id}")
                    return False
                if oh_end and now_str > oh_end:
                    log_event('error', f"Office hours closed for room {room_id}")
                    return False

            # Validate reply target belongs to the same room (if provided).
            reply_target = None
            if reply_to_id:
                cursor.execute(
                    'SELECT room_id FROM chat_messages WHERE id = ?',
                    (reply_to_id,),
                )
                row = cursor.fetchone()
                if row and row[0] == room_id:
                    reply_target = reply_to_id

            # Slow mode (admins exempt)
            slow_mode = int(room_data[4] or 0)
            if slow_mode > 0 and not is_admin_in_room:
                cursor.execute(
                    'SELECT MAX(sent_at) FROM chat_messages '
                    'WHERE room_id = ? AND sender_id = ?', (room_id, user_id),
                )
                last_row = cursor.fetchone()
                if last_row and last_row[0]:
                    from datetime import timedelta
                    last_dt = datetime.strptime(last_row[0], '%Y-%m-%d %H:%M:%S')
                    if datetime.now() - last_dt < timedelta(seconds=slow_mode):
                        log_event('error', f"Slow mode active for room {room_id}")
                        return False

            # Profanity / safeguarding scan
            raw_text = (content or '').strip()
            severity, matched_words = _scan_filter_words(cursor, raw_text)
            if severity == 'block' and not is_admin_in_room:
                log_event('error', "Message blocked by safeguarding filter")
                return False

            stored_content = raw_text
            is_encrypted_flag = 0
            if room_data[5]:
                key_b64 = _ensure_room_key(cursor, room_id, sent_at)
                if key_b64 and stored_content:
                    enc = _encrypt_with_key(stored_content, key_b64)
                    if enc is not None:
                        stored_content = enc
                        is_encrypted_flag = 1

            cursor.execute('''
            INSERT INTO chat_messages
                (room_id, sender_id, content, sent_at, reply_to_id,
                 attachment_path, attachment_name, attachment_mime, attachment_size,
                 flagged_at, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (room_id, user_id, stored_content, sent_at, reply_target,
                  attachment_path, attachment_name, attachment_mime, attachment_size,
                  sent_at if matched_words else None, is_encrypted_flag))

            new_id = cursor.lastrowid
            for word in matched_words:
                cursor.execute(
                    '''INSERT INTO safeguarding_flags
                       (message_id, room_id, user_id, matched_word, severity, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (new_id, room_id, user_id, word, severity or 'flag', sent_at),
                )
            # Mention-based notifications (best-effort; never fails the send)
            try:
                sender_name = self.auth.current_user.get('display_name') or \
                              self.auth.current_user.get('username') or 'Someone'
                self._emit_chat_mention_notifications(
                    cursor, room_id, user_id, sender_name, raw_text, new_id,
                )
            except Exception:
                pass
            return new_id

        try:
            result = execute_db_operation(_send_message)
            if result:
                log_event('info', f"Chat message sent to room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error sending chat message: {e}")
            return False

    @handle_exception
    def get_chat_messages(self, room_id, page=1, limit=20):
        """Get messages from a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view chat messages")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_messages(cursor):
            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

            # Get messages (most recent first, then reverse for display)
            cursor.execute('''
            SELECT m.id, m.content, m.sent_at,
                   COALESCE(u.username, 'User ' || m.sender_id),
                   COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                   m.sender_id, m.edited_at, COALESCE(m.is_deleted, 0),
                   m.reply_to_id, m.pinned_at,
                   m.attachment_path, m.attachment_name, m.attachment_mime, m.attachment_size,
                   r.content,
                   COALESCE(ru.username, 'User ' || r.sender_id),
                   COALESCE(r.is_deleted, 0),
                   u.role,
                   COALESCE(m.is_encrypted, 0), k.key_b64
            FROM chat_messages m
            LEFT JOIN users u ON m.sender_id = u.id
            LEFT JOIN chat_messages r ON m.reply_to_id = r.id
            LEFT JOIN users ru ON r.sender_id = ru.id
            LEFT JOIN chat_room_keys k ON k.room_id = m.room_id
            WHERE m.room_id = ?
            ORDER BY m.sent_at DESC
            LIMIT ? OFFSET ?
            ''', (room_id, limit, offset))

            messages = cursor.fetchall()

            # Get total count
            cursor.execute('''
            SELECT COUNT(*) FROM chat_messages WHERE room_id = ?
            ''', (room_id,))

            total_count = cursor.fetchone()[0]

            # Format message data (reverse to show oldest first)
            message_list = []
            for m in reversed(messages):
                full_name = f"{m[4]} {m[5]}".strip()
                message_list.append(_format_message_row(m, full_name))

            return {
                'messages': message_list,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_messages)
        except Exception as e:
            log_event('error', f"Error getting chat messages: {e}")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def get_chat_messages_since(self, room_id, since_message_id=0):
        """Return messages with id > since_message_id (oldest-first)."""
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
            # Cheap probe — skip the heavy join when nothing is newer than
            # what the caller already has. Hits the (room_id, id) index.
            cursor.execute(
                'SELECT MAX(id) FROM chat_messages WHERE room_id = ?',
                (room_id,),
            )
            mx = cursor.fetchone()
            if not mx or not mx[0] or mx[0] <= (since_message_id or 0):
                return []
            cursor.execute(
                '''
                SELECT m.id, m.content, m.sent_at,
                       COALESCE(u.username, 'User ' || m.sender_id),
                       COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                       m.sender_id, m.edited_at, COALESCE(m.is_deleted, 0),
                       m.reply_to_id, m.pinned_at,
                       m.attachment_path, m.attachment_name, m.attachment_mime, m.attachment_size,
                       r.content,
                       COALESCE(ru.username, 'User ' || r.sender_id),
                       COALESCE(r.is_deleted, 0),
                       u.role,
                       COALESCE(m.is_encrypted, 0), k.key_b64
                FROM chat_messages m
                LEFT JOIN users u ON m.sender_id = u.id
                LEFT JOIN chat_messages r ON m.reply_to_id = r.id
                LEFT JOIN users ru ON r.sender_id = ru.id
                LEFT JOIN chat_room_keys k ON k.room_id = m.room_id
                WHERE m.room_id = ? AND m.id > ?
                ORDER BY m.id ASC
                LIMIT 200
                ''',
                (room_id, since_message_id or 0),
            )
            out = []
            for row in cursor.fetchall():
                full_name = f"{row[4]} {row[5]}".strip()
                out.append(_format_message_row(row, full_name))
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting new chat messages: {e}")
            return []

    @handle_exception
    def mark_chat_messages_read(self, room_id, up_to_message_id=None):
        """Record that the current user has read up to a given message id.
        If up_to_message_id is None, uses the latest message in the room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _mark(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return False
            target = up_to_message_id
            if target is None:
                cursor.execute(
                    'SELECT MAX(id) FROM chat_messages WHERE room_id = ?',
                    (room_id,),
                )
                row = cursor.fetchone()
                target = row[0] if row and row[0] is not None else 0
            cursor.execute(
                '''
                INSERT INTO chat_message_reads (user_id, room_id, last_read_message_id, last_read_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, room_id) DO UPDATE SET
                    last_read_message_id = MAX(last_read_message_id, excluded.last_read_message_id),
                    last_read_at = excluded.last_read_at
                ''',
                (user_id, room_id, target, now),
            )
            return True

        try:
            return execute_db_operation(_mark)
        except Exception as e:
            log_event('error', f"Error marking messages read: {e}")
            return False

    @handle_exception
    def get_chat_message_readers(self, room_id, message_id):
        """Return the list of users who have read at least up to message_id
        (excluding the message's sender). Used for 'seen by' display."""
        if not self.auth or not self.auth.current_user:
            return []

        def _get(cursor):
            cursor.execute(
                'SELECT sender_id FROM chat_messages WHERE id = ? AND room_id = ?',
                (message_id, room_id),
            )
            row = cursor.fetchone()
            if not row:
                return []
            sender_id = row[0]
            cursor.execute(
                '''
                SELECT u.id, COALESCE(u.username, 'User ' || u.id),
                       COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                       r.last_read_at
                FROM chat_message_reads r
                JOIN users u ON r.user_id = u.id
                WHERE r.room_id = ? AND r.last_read_message_id >= ? AND r.user_id != ?
                ORDER BY r.last_read_at ASC
                ''',
                (room_id, message_id, sender_id),
            )
            out = []
            for r in cursor.fetchall():
                full = f"{r[2]} {r[3]}".strip()
                out.append({
                    'user_id': r[0],
                    'username': r[1],
                    'full_name': full or r[1],
                    'read_at': r[4],
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting message readers: {e}")
            return []

    @handle_exception
    def get_unread_chat_counts(self):
        """Return {room_id: unread_count} for every joined room of the current user."""
        if not self.auth or not self.auth.current_user:
            return {}
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                '''
                SELECT m.room_id,
                       COUNT(*) FILTER (WHERE m.id > COALESCE(r.last_read_message_id, 0)
                                        AND m.sender_id != ?)
                FROM chat_room_members mem
                JOIN chat_messages m ON m.room_id = mem.room_id
                LEFT JOIN chat_message_reads r
                  ON r.room_id = mem.room_id AND r.user_id = mem.user_id
                WHERE mem.user_id = ?
                GROUP BY m.room_id
                ''',
                (user_id, user_id),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting unread counts: {e}")
            return {}

    @handle_exception
    def edit_chat_message(self, message_id, new_content):
        """Edit own message. Returns True on success."""
        if not self.auth or not self.auth.current_user:
            return False
        if not new_content or not new_content.strip():
            return False
        user_id = self.auth.current_user['id']
        edited_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _edit(cursor):
            cursor.execute(
                'SELECT sender_id, COALESCE(is_deleted, 0) FROM chat_messages WHERE id = ?',
                (message_id,),
            )
            row = cursor.fetchone()
            if not row or row[0] != user_id or row[1]:
                return False
            cursor.execute(
                'UPDATE chat_messages SET content = ?, edited_at = ? WHERE id = ?',
                (new_content.strip(), edited_at, message_id),
            )
            self._log_communication_action(
                user_id, "edit_chat_message",
                f"Edited chat message {message_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_edit)
        except Exception as e:
            log_event('error', f"Error editing chat message: {e}")
            return False

    @handle_exception
    def delete_chat_message(self, message_id):
        """Soft-delete own message (or any message if user is room admin)."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _delete(cursor):
            cursor.execute(
                'SELECT sender_id, room_id, COALESCE(is_deleted, 0) FROM chat_messages WHERE id = ?',
                (message_id,),
            )
            row = cursor.fetchone()
            if not row or row[2]:
                return False
            sender_id, room_id = row[0], row[1]
            if sender_id != user_id:
                # Room admin override
                cursor.execute(
                    'SELECT is_admin FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, user_id),
                )
                admin_row = cursor.fetchone()
                if not admin_row or not admin_row[0]:
                    return False
            cursor.execute(
                'UPDATE chat_messages SET is_deleted = 1 WHERE id = ?', (message_id,),
            )
            self._log_communication_action(
                user_id, "delete_chat_message",
                f"Deleted chat message {message_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_delete)
        except Exception as e:
            log_event('error', f"Error deleting chat message: {e}")
            return False

    @handle_exception
    def search_chat_messages(self, query, room_id=None, limit=100):
        """Search chat messages the current user can see (rooms they're in).
        Case-insensitive substring match on content. Returns newest first."""
        if not self.auth or not self.auth.current_user:
            return []
        if not query or not query.strip():
            return []
        user_id = self.auth.current_user['id']
        pattern = f"%{query.strip()}%"

        def _search(cursor):
            params = [user_id, pattern]
            sql = '''
                SELECT m.id, m.room_id, r.name, m.content, m.sent_at,
                       COALESCE(u.username, 'User ' || m.sender_id),
                       COALESCE(u.first_name, ''), COALESCE(u.last_name, '')
                FROM chat_messages m
                JOIN chat_rooms r ON m.room_id = r.id
                JOIN chat_room_members mem ON mem.room_id = m.room_id AND mem.user_id = ?
                LEFT JOIN users u ON m.sender_id = u.id
                WHERE m.content LIKE ? AND COALESCE(m.is_deleted, 0) = 0
            '''
            if room_id is not None:
                sql += ' AND m.room_id = ?'
                params.append(room_id)
            sql += ' ORDER BY m.sent_at DESC LIMIT ?'
            params.append(int(limit))
            cursor.execute(sql, params)
            out = []
            for r in cursor.fetchall():
                full = f"{r[6]} {r[7]}".strip()
                out.append({
                    'id': r[0], 'room_id': r[1], 'room_name': r[2],
                    'content': r[3], 'sent_at': r[4],
                    'sender': r[5], 'sender_name': full or r[5],
                })
            return out

        try:
            return execute_db_operation(_search)
        except Exception as e:
            log_event('error', f"Error searching chat messages: {e}")
            return []

    # ------------------------------------------------------------------
    # Course / assignment-group room sync, polls, shared notes, queue.
    # ------------------------------------------------------------------

    @handle_exception
    def purge_expired_chat_messages(self):
        """Delete messages older than each room's retention_days. Admin/staff."""
        if not self.auth or not self.auth.current_user:
            return 0
        role = (self.auth.current_user.get('role') or '').lower()
        if role not in ('admin', 'staff'):
            return 0
        user_id = self.auth.current_user['id']

        def _purge(cursor):
            cursor.execute(
                'SELECT id, retention_days FROM chat_rooms '
                'WHERE retention_days IS NOT NULL AND retention_days > 0'
            )
            rooms = cursor.fetchall()
            total = 0
            for room_id, days in rooms:
                cursor.execute(
                    '''DELETE FROM chat_messages
                       WHERE room_id = ?
                         AND sent_at < datetime('now', ?)
                       AND id NOT IN (SELECT message_id FROM chat_polls)''',
                    (room_id, f'-{int(days)} days'),
                )
                total += cursor.rowcount or 0
            if total:
                self._log_communication_action(
                    user_id, "purge_expired_chat_messages",
                    f"Purged {total} expired chat messages",
                    cursor=cursor,
                )
            return total

        try:
            return execute_db_operation(_purge)
        except Exception as e:
            log_event('error', f"Error purging expired messages: {e}")
            return 0

