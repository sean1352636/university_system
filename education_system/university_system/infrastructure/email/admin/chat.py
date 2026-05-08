"""Chat room mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


# ---- safety / encryption helpers (module level) -----------------------------

# Default starter wordlist; a deployment-grade list should be loaded from config.
_DEFAULT_FILTER_WORDS = (
    # Mild markers used as a smoke-test wordlist; severity='flag' means the
    # message still goes through but a safeguarding row is recorded.
    ('badword', 'flag'),
    ('killme', 'flag'),
    ('selfharm', 'flag'),
)

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    _FERNET_AVAILABLE = True
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    _FERNET_AVAILABLE = False


def _scan_filter_words(cursor, content):
    """Return (highest_severity, [matched_words]) for a piece of content.
    Severity is 'block' if any matched word is flagged that way, else 'flag'."""
    if not content:
        return None, []
    lowered = content.lower()
    try:
        cursor.execute('SELECT word, severity FROM chat_filter_words')
        rows = list(cursor.fetchall())
    except Exception:
        rows = []
    if not rows:
        rows = [(w, s) for (w, s) in _DEFAULT_FILTER_WORDS]
    matches, severity = [], None
    for word, sev in rows:
        if word and word.lower() in lowered:
            matches.append(word)
            if sev == 'block':
                severity = 'block'
            elif severity is None:
                severity = sev or 'flag'
    return severity, matches


def _ensure_room_key(cursor, room_id, now):
    """Fetch or create a Fernet key for a room. Returns base64 key or None."""
    if not _FERNET_AVAILABLE:
        return None
    cursor.execute('SELECT key_b64 FROM chat_room_keys WHERE room_id = ?', (room_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    new_key = Fernet.generate_key().decode('ascii')
    cursor.execute(
        'INSERT INTO chat_room_keys (room_id, key_b64, created_at) VALUES (?, ?, ?)',
        (room_id, new_key, now),
    )
    return new_key


def _encrypt_with_key(plaintext, key_b64):
    if not _FERNET_AVAILABLE or not key_b64:
        return None
    try:
        token = Fernet(key_b64.encode('ascii')).encrypt(plaintext.encode('utf-8'))
        return 'enc:v1:' + token.decode('ascii')
    except Exception:
        return None


def _decrypt_with_key(ciphertext, key_b64):
    if not ciphertext or not isinstance(ciphertext, str):
        return ciphertext
    if not ciphertext.startswith('enc:v1:'):
        return ciphertext
    if not _FERNET_AVAILABLE or not key_b64:
        return '[encrypted message — key unavailable]'
    try:
        token = ciphertext[len('enc:v1:'):].encode('ascii')
        return Fernet(key_b64.encode('ascii')).decrypt(token).decode('utf-8')
    except (InvalidToken, Exception):
        return '[encrypted message — could not decrypt]'


def _maybe_decrypt(cursor, room_id_for_key_lookup, msg_dict):
    """Decrypt msg_dict['content'] in place when the encrypted flag is on the
    underlying row. Caller passes a cursor so we can fetch the room key once
    per query if needed (cached in a closure-local dict by the caller)."""
    # No-op here — the GUI layer doesn't have direct access; we decrypt in
    # _format_message_row when row data carries an is_encrypted bit. This
    # helper is kept as a placeholder for any future per-row strategies.
    return msg_dict


def _format_message_row(row, full_name):
    """Translate a SELECT row from the canonical chat_messages query into the
    dict shape consumed by the GUI. Row layout (17 cols):

    id, content, sent_at, username, first, last, sender_id,
    edited_at, is_deleted, reply_to_id, pinned_at,
    att_path, att_name, att_mime, att_size,
    reply_content, reply_username, reply_is_deleted
    """
    is_deleted = bool(row[8])
    content = row[1] if not is_deleted else ''
    msg = {
        'id': row[0],
        'content': content,
        'sent_at': row[2],
        'sender': row[3],
        'sender_name': full_name or row[3],
        'sender_id': row[6],
        'edited_at': row[7],
        'is_deleted': is_deleted,
        'reply_to_id': row[9],
        'pinned_at': row[10],
        'attachment_path': row[11],
        'attachment_name': row[12],
        'attachment_mime': row[13],
        'attachment_size': row[14],
    }
    if row[9] and row[15] is not None:
        msg['reply_preview'] = {
            'sender': row[16],
            'content': '' if row[17] else (row[15] or ''),
            'is_deleted': bool(row[17]),
        }
    # Sender role (column 18) is optional — only present in extended queries.
    if len(row) > 18:
        msg['sender_role'] = row[18]
    # Encryption (cols 19/20) — decrypt content lazily for display.
    if len(row) > 20 and row[19]:
        decrypted = _decrypt_with_key(msg.get('content'), row[20])
        if decrypted is not None:
            msg['content'] = decrypted
        msg['is_encrypted'] = True
    return msg


class _ChatMixin:
    """Mixin providing chat room lifecycle, membership, and messaging."""

    @handle_exception
    def create_chat_room(self, name, description=None, room_type='public', max_members=None):
        """Create a new chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to create chat rooms")
            return False

        # Validate inputs
        if not name or not name.strip():
            log_event('error', "Chat room name is required")
            return False

        # Valid room types
        valid_types = ['public', 'private', 'course', 'department']
        if room_type not in valid_types:
            room_type = 'public'

        if max_members is not None:
            try:
                max_members = int(max_members)
            except (TypeError, ValueError):
                log_event('error', "max_members must be an integer")
                return False
            if max_members < 2:
                log_event('error', "max_members must be at least 2")
                return False

        def _create_room(cursor):
            creator_id = self.auth.current_user['id']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if room name already exists
            cursor.execute('SELECT id FROM chat_rooms WHERE name = ? AND is_active = 1', (name.strip(),))
            if cursor.fetchone():
                log_event('error', f"Chat room '{name}' already exists")
                return False

            # Create the chat room
            if max_members is not None:
                cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, max_members, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ''', (name.strip(), description, room_type, creator_id, created_at, max_members))
            else:
                cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                ''', (name.strip(), description, room_type, creator_id, created_at))

            room_id = cursor.lastrowid

            # Add creator as admin member
            cursor.execute('''
            INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
            VALUES (?, ?, ?, 1)
            ''', (room_id, creator_id, created_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                creator_id,
                "create_chat_room",
                f"Created chat room '{name}' (ID: {room_id})",
                cursor=cursor
            )

            return room_id

        try:
            result = execute_db_operation(_create_room)
            if result:
                log_event('info', f"Chat room '{name}' created successfully with ID {result}")
            return result
        except Exception as e:
            log_event('error', f"Error creating chat room: {e}")
            return False

    @handle_exception
    def join_chat_room(self, room_id):
        """Join a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to join chat rooms")
            return False

        def _join_room(cursor):
            user_id = self.auth.current_user['id']
            joined_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if room exists and is active
            cursor.execute('''
            SELECT name, room_type FROM chat_rooms
            WHERE id = ? AND is_active = 1
            ''', (room_id,))

            room_data = cursor.fetchone()
            if not room_data:
                log_event('error', f"Chat room {room_id} not found or inactive")
                return False

            room_name, room_type = room_data

            # Check if user is already a member
            cursor.execute('''
            SELECT id FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if cursor.fetchone():
                log_event('warning', f"User already member of room {room_id}")
                return "already_member"

            # For private rooms, check if user has an invitation
            if room_type == 'private':
                cursor.execute('''
                SELECT id FROM chat_room_invitations
                WHERE room_id = ? AND user_id = ? AND status = 'pending'
                ''', (room_id, user_id))

                if not cursor.fetchone():
                    log_event('error', f"No invitation found for private room {room_id}")
                    return False

                # Accept the invitation
                cursor.execute('''
                UPDATE chat_room_invitations
                SET status = 'accepted', responded_at = ?
                WHERE room_id = ? AND user_id = ? AND status = 'pending'
                ''', (joined_at, room_id, user_id))

            # Add user to room
            cursor.execute('''
            INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
            VALUES (?, ?, ?, 0)
            ''', (room_id, user_id, joined_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                user_id,
                "join_chat_room",
                f"Joined chat room '{room_name}' (ID: {room_id})",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_join_room)
            if result == True:
                log_event('info', f"Successfully joined chat room {room_id}")
            elif result == "already_member":
                log_event('info', f"User already member of chat room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error joining chat room: {e}")
            return False

    @handle_exception
    def leave_chat_room(self, room_id):
        """Leave a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to leave chat rooms")
            return False

        def _leave_room(cursor):
            user_id = self.auth.current_user['id']

            # Check if user is a member
            cursor.execute('''
            SELECT is_admin FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            member_data = cursor.fetchone()
            if not member_data:
                log_event('error', f"User not a member of room {room_id}")
                return False

            is_admin = member_data[0]

            # Get room info
            cursor.execute('SELECT name, created_by FROM chat_rooms WHERE id = ?', (room_id,))
            room_data = cursor.fetchone()
            if not room_data:
                return False

            room_name, created_by = room_data

            # Check if user is the creator/owner
            if created_by == user_id:
                # Transfer ownership to another admin or delete room
                cursor.execute('''
                SELECT user_id FROM chat_room_members
                WHERE room_id = ? AND user_id != ? AND is_admin = 1
                LIMIT 1
                ''', (room_id, user_id))

                next_admin = cursor.fetchone()
                if next_admin:
                    # Transfer ownership
                    cursor.execute('''
                    UPDATE chat_rooms SET created_by = ? WHERE id = ?
                    ''', (next_admin[0], room_id))
                    log_event('info', f"Transferred room ownership to user {next_admin[0]}")
                else:
                    # No other admins, check if there are other members
                    cursor.execute('''
                    SELECT COUNT(*) FROM chat_room_members
                    WHERE room_id = ? AND user_id != ?
                    ''', (room_id, user_id))

                    other_members = cursor.fetchone()[0]
                    if other_members == 0:
                        # No other members, deactivate the room
                        cursor.execute('''
                        UPDATE chat_rooms SET is_active = 0 WHERE id = ?
                        ''', (room_id,))
                        log_event('info', f"Deactivated empty room {room_id}")
                    else:
                        # Promote the most senior member to admin
                        cursor.execute('''
                        SELECT user_id FROM chat_room_members
                        WHERE room_id = ? AND user_id != ?
                        ORDER BY joined_at ASC LIMIT 1
                        ''', (room_id, user_id))

                        senior_member = cursor.fetchone()
                        if senior_member:
                            cursor.execute('''
                            UPDATE chat_room_members SET is_admin = 1
                            WHERE room_id = ? AND user_id = ?
                            ''', (room_id, senior_member[0]))

                            cursor.execute('''
                            UPDATE chat_rooms SET created_by = ? WHERE id = ?
                            ''', (senior_member[0], room_id))

                            log_event('info', f"Promoted user {senior_member[0]} to room admin")

            # Remove user from room
            cursor.execute('''
            DELETE FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                user_id,
                "leave_chat_room",
                f"Left chat room '{room_name}' (ID: {room_id})",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_leave_room)
            if result:
                log_event('info', f"Successfully left chat room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error leaving chat room: {e}")
            return False

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
    def get_chat_rooms(self, user_filter='joined', page=1, limit=10):
        """Get chat rooms (joined, public, or all)"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view chat rooms")
            return {'rooms': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_rooms(cursor):
            if user_filter == 'joined':
                # Get rooms user is a member of
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator, m.is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count,
                       r.category, r.icon, r.colour,
                       COALESCE(m.is_favourite, 0),
                       COALESCE(m.is_banned, 0), m.muted_until,
                       r.created_by,
                       r.linked_course_code, r.linked_assignment_group_id,
                       COALESCE(r.announcement_mode, 0),
                       r.oh_starts_at, r.oh_ends_at
                FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                JOIN users u ON r.created_by = u.id
                WHERE m.user_id = ? AND r.is_active = 1
                ORDER BY COALESCE(m.is_favourite, 0) DESC,
                         COALESCE(r.category, '~'), r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('''
                SELECT COUNT(*) FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                WHERE m.user_id = ? AND r.is_active = 1
                ''', (user_id,))

            elif user_filter == 'public':
                # Get public rooms user can join
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator, 0 as is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN users u ON r.created_by = u.id
                WHERE r.room_type = 'public' AND r.is_active = 1
                  AND r.id NOT IN (
                      SELECT room_id FROM chat_room_members WHERE user_id = ?
                  )
                ORDER BY r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('''
                SELECT COUNT(*) FROM chat_rooms r
                WHERE r.room_type = 'public' AND r.is_active = 1
                  AND r.id NOT IN (
                      SELECT room_id FROM chat_room_members WHERE user_id = ?
                  )
                ''', (user_id,))

            else:  # all
                # Get all active rooms (admin view)
                cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator,
                       COALESCE(m.is_admin, 0) as is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id) as member_count,
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN users u ON r.created_by = u.id
                LEFT JOIN chat_room_members m ON r.id = m.room_id AND m.user_id = ?
                WHERE r.is_active = 1
                ORDER BY r.name
                LIMIT ? OFFSET ?
                ''', (user_id, limit, offset))

                rooms = cursor.fetchall()

                # Get total count
                cursor.execute('SELECT COUNT(*) FROM chat_rooms WHERE is_active = 1')

            total_count = cursor.fetchone()[0]

            # Format room data. The 'joined' branch returns extra columns
            # (category/icon/colour/favourite/ban/mute/owner_id); the 'public'
            # branch only returns the first 9.
            room_list = []
            for room in rooms:
                entry = {
                    'id': room[0],
                    'name': room[1],
                    'description': room[2],
                    'room_type': room[3],
                    'created_at': room[4],
                    'creator': room[5],
                    'is_admin': bool(room[6]),
                    'member_count': room[7],
                    'message_count': room[8],
                }
                if len(room) > 9:
                    entry.update({
                        'category': room[9],
                        'icon': room[10],
                        'colour': room[11],
                        'is_favourite': bool(room[12]),
                        'is_banned': bool(room[13]),
                        'muted_until': room[14],
                        'created_by': room[15],
                    })
                if len(room) > 16:
                    entry.update({
                        'linked_course_code': room[16],
                        'linked_assignment_group_id': room[17],
                        'announcement_mode': bool(room[18]),
                        'oh_starts_at': room[19],
                        'oh_ends_at': room[20],
                    })
                room_list.append(entry)

            return {
                'rooms': room_list,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_rooms)
        except Exception as e:
            log_event('error', f"Error getting chat rooms: {e}")
            return {'rooms': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

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
    def invite_user_to_room(self, room_id, user_id_to_invite):
        """Invite a user to a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to invite users")
            return False

        def _invite_user(cursor):
            inviter_id = self.auth.current_user['id']
            invited_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check if inviter is an admin of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ? AND is_admin = 1
            ''', (room_id, inviter_id))

            if not cursor.fetchone():
                log_event('error', f"User not an admin of room {room_id}")
                return False

            # Check if user to invite exists
            cursor.execute('SELECT username FROM users WHERE id = ?', (user_id_to_invite,))
            user_data = cursor.fetchone()
            if not user_data:
                log_event('error', f"User {user_id_to_invite} not found")
                return False

            username = user_data[0]

            # Check if user is already a member
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id_to_invite))

            if cursor.fetchone():
                log_event('warning', f"User {user_id_to_invite} already a member")
                return "already_member"

            # Check if invitation already exists
            cursor.execute('''
            SELECT status FROM chat_room_invitations
            WHERE room_id = ? AND user_id = ?
            ORDER BY invited_at DESC LIMIT 1
            ''', (room_id, user_id_to_invite))

            existing_invitation = cursor.fetchone()
            if existing_invitation and existing_invitation[0] == 'pending':
                log_event('warning', f"Pending invitation already exists")
                return "already_invited"

            # Create invitation
            cursor.execute('''
            INSERT INTO chat_room_invitations (room_id, user_id, invited_by, invited_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            ''', (room_id, user_id_to_invite, inviter_id, invited_at))

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                inviter_id,
                "invite_user_to_room",
                f"Invited user {username} to room {room_id}",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_invite_user)
            if result == True:
                log_event('info', f"Successfully invited user {user_id_to_invite} to room {room_id}")
            return result
        except Exception as e:
            log_event('error', f"Error inviting user to room: {e}")
            return False

    @handle_exception
    def get_room_members(self, room_id):
        """Get members of a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view room members")
            return []

        def _get_members(cursor):
            user_id = self.auth.current_user['id']

            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))

            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return []

            # Get room members and creator id (for is_creator flag)
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            creator_row = cursor.fetchone()
            creator_id = creator_row[0] if creator_row else None

            cursor.execute('''
            SELECT m.user_id, u.username, u.first_name, u.last_name, u.email,
                   m.joined_at, m.is_admin,
                   COALESCE(m.is_banned, 0), m.muted_until
            FROM chat_room_members m
            JOIN users u ON m.user_id = u.id
            WHERE m.room_id = ?
            ORDER BY m.is_admin DESC, m.joined_at ASC
            ''', (room_id,))

            members = cursor.fetchall()

            # Format member data
            member_list = []
            for member in members:
                full_name = f"{member[2]} {member[3]}".strip()
                member_list.append({
                    'user_id': member[0],
                    'username': member[1],
                    'full_name': full_name if full_name else member[1],
                    'email': member[4],
                    'joined_at': member[5],
                    'is_admin': bool(member[6]),
                    'is_banned': bool(member[7]),
                    'muted_until': member[8],
                    'is_creator': member[0] == creator_id,
                })

            return member_list

        try:
            return execute_db_operation(_get_members)
        except Exception as e:
            log_event('error', f"Error getting room members: {e}")
            return []

    @handle_exception
    def get_pending_invitations(self):
        """Get pending chat room invitations for current user"""
        if not self.auth or not self.auth.current_user:
            return []

        def _get_invitations(cursor):
            user_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT i.id, i.room_id, r.name as room_name, r.description,
                   u.username as invited_by, i.invited_at
            FROM chat_room_invitations i
            JOIN chat_rooms r ON i.room_id = r.id
            JOIN users u ON i.invited_by = u.id
            WHERE i.user_id = ? AND i.status = 'pending'
            ORDER BY i.invited_at DESC
            ''', (user_id,))

            invitations = cursor.fetchall()

            invitation_list = []
            for inv in invitations:
                invitation_list.append({
                    'id': inv[0],
                    'room_id': inv[1],
                    'room_name': inv[2],
                    'room_description': inv[3],
                    'invited_by': inv[4],
                    'invited_at': inv[5]
                })

            return invitation_list

        try:
            return execute_db_operation(_get_invitations)
        except Exception as e:
            log_event('error', f"Error getting pending invitations: {e}")
            return []

    @handle_exception
    def respond_to_invitation(self, invitation_id, accept=True):
        """Accept or decline a chat room invitation"""
        if not self.auth or not self.auth.current_user:
            return False

        def _respond_invitation(cursor):
            user_id = self.auth.current_user['id']
            responded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Get invitation details
            cursor.execute('''
            SELECT room_id, user_id FROM chat_room_invitations
            WHERE id = ? AND status = 'pending'
            ''', (invitation_id,))

            invitation = cursor.fetchone()
            if not invitation:
                log_event('error', f"Invitation {invitation_id} not found or already processed")
                return False

            room_id, invited_user_id = invitation

            if invited_user_id != user_id:
                log_event('error', f"Invitation not for current user")
                return False

            status = 'accepted' if accept else 'declined'

            # Update invitation status
            cursor.execute('''
            UPDATE chat_room_invitations
            SET status = ?, responded_at = ?
            WHERE id = ?
            ''', (status, responded_at, invitation_id))

            # If accepted, join the room
            if accept:
                cursor.execute('''
                INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin)
                VALUES (?, ?, ?, 0)
                ''', (room_id, user_id, responded_at))

            return True

        try:
            result = execute_db_operation(_respond_invitation)
            if result:
                action = "accepted" if accept else "declined"
                log_event('info', f"Invitation {invitation_id} {action}")
            return result
        except Exception as e:
            log_event('error', f"Error responding to invitation: {e}")
            return False

    # ------------------------------------------------------------------
    # Live-update helpers: incremental fetch, read receipts, typing,
    # presence, and unread counts. Polled by the GUI; SQLite-friendly.
    # ------------------------------------------------------------------

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

    def _get_or_create_system_user_id(self, cursor, fallback_user_id):
        """Find or lazily create a 'system' bot user. Returns its id, or
        fallback_user_id if the users table doesn't accept the insert.

        The application `users` table has varying NOT NULL shapes across
        deployments (university: first_name/last_name/email/role NOT NULL;
        school: just username/role/password_hash NOT NULL), so we discover
        columns at runtime and supply safe defaults for any of them."""
        try:
            cursor.execute("PRAGMA table_info(users)")
            cols = {row[1] for row in cursor.fetchall()}
        except Exception:
            return fallback_user_id
        if 'username' not in cols:
            return fallback_user_id
        # Prefer the explicit service_account flag if the column exists.
        try:
            if 'service_account' in cols:
                cursor.execute(
                    "SELECT id FROM users WHERE COALESCE(service_account, 0) = 1 "
                    "ORDER BY id LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
            cursor.execute("SELECT id FROM users WHERE username = 'system' LIMIT 1")
            row = cursor.fetchone()
            if row:
                # Ensure the flag is set on a pre-existing 'system' user.
                if 'service_account' in cols:
                    cursor.execute(
                        "UPDATE users SET service_account = 1 WHERE id = ?",
                        (row[0],),
                    )
                return row[0]
        except Exception:
            return fallback_user_id
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        candidates = {
            'username': 'system',
            'first_name': 'System',
            'last_name': 'Bot',
            'display_name': 'System',
            'email': 'system@localhost',
            'role': 'system',
            'password_hash': '!locked!',
            'is_active': 0,
            'service_account': 1,
            'created_at': now,
            'updated_at': now,
        }
        used = {k: v for k, v in candidates.items() if k in cols}
        if not used:
            return fallback_user_id
        col_list = list(used.keys())
        sql = (
            f"INSERT INTO users ({', '.join(col_list)}) "
            f"VALUES ({', '.join('?' for _ in col_list)})"
        )
        try:
            cursor.execute(sql, [used[c] for c in col_list])
            new_id = cursor.lastrowid
            if new_id:
                return new_id
        except Exception:
            pass
        # If the insert failed (e.g., a NOT NULL we don't know about),
        # one last attempt: did a parallel writer create it meanwhile?
        try:
            cursor.execute("SELECT id FROM users WHERE username = 'system' LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0]
        except Exception:
            pass
        return fallback_user_id

    def _is_room_admin(self, cursor, room_id, user_id):
        cursor.execute(
            'SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,),
        )
        row = cursor.fetchone()
        if row and row[0] == user_id:
            return True
        cursor.execute(
            'SELECT COALESCE(is_admin, 0) FROM chat_room_members WHERE room_id = ? AND user_id = ?',
            (room_id, user_id),
        )
        r = cursor.fetchone()
        return bool(r and r[0])

    @handle_exception
    def update_chat_room(self, room_id, *, name=None, description=None,
                         room_type=None, category=None, icon=None, colour=None,
                         max_members=None, linked_course_code=None,
                         linked_assignment_group_id=None,
                         announcement_mode=None,
                         oh_starts_at=None, oh_ends_at=None,
                         retention_days=None, slow_mode_seconds=None,
                         is_encrypted=None):
        """Update room metadata. Caller must be a room admin or the creator.
        Pass None to leave a field unchanged; pass an empty string to clear."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        if room_type is not None and room_type not in ('public', 'private', 'course', 'department'):
            log_event('error', f"Invalid room_type: {room_type}")
            return False
        if max_members is not None:
            try:
                max_members = int(max_members)
            except (TypeError, ValueError):
                return False
            if max_members < 2:
                return False

        def _update(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            sets, params = [], []
            for col, val in (('name', name), ('description', description),
                             ('room_type', room_type), ('category', category),
                             ('icon', icon), ('colour', colour),
                             ('max_members', max_members),
                             ('linked_course_code', linked_course_code),
                             ('linked_assignment_group_id', linked_assignment_group_id),
                             ('announcement_mode',
                              None if announcement_mode is None else (1 if announcement_mode else 0)),
                             ('oh_starts_at', oh_starts_at),
                             ('oh_ends_at', oh_ends_at),
                             ('retention_days',
                              None if retention_days is None
                              else (int(retention_days) if str(retention_days).strip() else None)),
                             ('slow_mode_seconds',
                              None if slow_mode_seconds is None
                              else int(slow_mode_seconds)),
                             ('is_encrypted',
                              None if is_encrypted is None else (1 if is_encrypted else 0))):
                if val is not None:
                    sets.append(f"{col} = ?")
                    params.append(val if val != '' else None)
            if not sets:
                return True
            params.append(room_id)
            cursor.execute(
                f"UPDATE chat_rooms SET {', '.join(sets)} WHERE id = ?", params,
            )
            self._log_communication_action(
                user_id, "update_chat_room",
                f"Updated chat room {room_id}: {', '.join(sets)}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_update)
        except Exception as e:
            log_event('error', f"Error updating chat room: {e}")
            return False

    @handle_exception
    def archive_chat_room(self, room_id, archive=True):
        """Archive (hide from listings) or unarchive a chat room."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _arch(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            if archive:
                cursor.execute(
                    'UPDATE chat_rooms SET is_active = 0, archived_at = ?, archived_by = ? WHERE id = ?',
                    (now, user_id, room_id),
                )
            else:
                cursor.execute(
                    'UPDATE chat_rooms SET is_active = 1, archived_at = NULL, archived_by = NULL WHERE id = ?',
                    (room_id,),
                )
            self._log_communication_action(
                user_id, "archive_chat_room" if archive else "unarchive_chat_room",
                f"{'Archived' if archive else 'Unarchived'} chat room {room_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_arch)
        except Exception as e:
            log_event('error', f"Error archiving chat room: {e}")
            return False

    @handle_exception
    def delete_chat_room(self, room_id):
        """Permanently delete a chat room and all related data. Creator only."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _delete(cursor):
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if not row or row[0] != user_id:
                return False
            # Cascade manually since we don't rely on FK ON DELETE.
            cursor.execute(
                '''DELETE FROM chat_message_reactions WHERE message_id IN
                   (SELECT id FROM chat_messages WHERE room_id = ?)''',
                (room_id,),
            )
            for table in (
                'chat_messages', 'chat_room_members', 'chat_room_invitations',
                'chat_message_reads', 'chat_typing', 'chat_presence',
            ):
                try:
                    cursor.execute(f'DELETE FROM {table} WHERE room_id = ?', (room_id,))
                except Exception:
                    pass
            cursor.execute('DELETE FROM chat_rooms WHERE id = ?', (room_id,))
            self._log_communication_action(
                user_id, "delete_chat_room",
                f"Deleted chat room {room_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_delete)
        except Exception as e:
            log_event('error', f"Error deleting chat room: {e}")
            return False

    @handle_exception
    def transfer_room_ownership(self, room_id, new_owner_user_id):
        """Reassign created_by. Caller must be the current owner."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _transfer(cursor):
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if not row or row[0] != user_id:
                return False
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, new_owner_user_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                'UPDATE chat_rooms SET created_by = ? WHERE id = ?',
                (new_owner_user_id, room_id),
            )
            cursor.execute(
                'UPDATE chat_room_members SET is_admin = 1 WHERE room_id = ? AND user_id = ?',
                (room_id, new_owner_user_id),
            )
            self._log_communication_action(
                user_id, "transfer_room_ownership",
                f"Transferred chat room {room_id} ownership to user {new_owner_user_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_transfer)
        except Exception as e:
            log_event('error', f"Error transferring ownership: {e}")
            return False

    @handle_exception
    def set_room_admin(self, room_id, target_user_id, is_admin=True):
        """Promote or demote a member. Caller must be a room admin/creator.
        Cannot demote the creator."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _set(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id and not is_admin:
                return False
            cursor.execute(
                'UPDATE chat_room_members SET is_admin = ? WHERE room_id = ? AND user_id = ?',
                (1 if is_admin else 0, room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "set_room_admin",
                f"{'Promoted' if is_admin else 'Demoted'} user {target_user_id} in room {room_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_set)
        except Exception as e:
            log_event('error', f"Error setting admin: {e}")
            return False

    @handle_exception
    def kick_room_member(self, room_id, target_user_id):
        """Remove a member from a room. Admin/creator only; cannot kick the creator."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _kick(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id:
                return False
            cursor.execute(
                'DELETE FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "kick_room_member",
                f"Kicked user {target_user_id} from room {room_id}", cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_kick)
        except Exception as e:
            log_event('error', f"Error kicking member: {e}")
            return False

    @handle_exception
    def ban_room_member(self, room_id, target_user_id, banned=True):
        """Ban (or unban) a member. Banned users keep the membership row so
        the ban survives, but cannot send messages."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _ban(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute('SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,))
            row = cursor.fetchone()
            if row and row[0] == target_user_id and banned:
                return False
            cursor.execute(
                'UPDATE chat_room_members SET is_banned = ? WHERE room_id = ? AND user_id = ?',
                (1 if banned else 0, room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "ban_room_member" if banned else "unban_room_member",
                f"{'Banned' if banned else 'Unbanned'} user {target_user_id} in room {room_id}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_ban)
        except Exception as e:
            log_event('error', f"Error banning member: {e}")
            return False

    @handle_exception
    def mute_room_member(self, room_id, target_user_id, minutes=None):
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

        def _mute(cursor):
            if not self._is_room_admin(cursor, room_id, user_id):
                return False
            cursor.execute(
                'UPDATE chat_room_members SET muted_until = ? WHERE room_id = ? AND user_id = ?',
                (until, room_id, target_user_id),
            )
            self._log_communication_action(
                user_id, "mute_room_member",
                f"Muted user {target_user_id} in room {room_id} until {until}",
                cursor=cursor,
            )
            return True

        try:
            return execute_db_operation(_mute)
        except Exception as e:
            log_event('error', f"Error muting member: {e}")
            return False

    @handle_exception
    def set_favourite_room(self, room_id, favourite=True):
        """Mark or unmark a room as a favourite for the current user."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']

        def _fav(cursor):
            cursor.execute(
                'UPDATE chat_room_members SET is_favourite = ? WHERE room_id = ? AND user_id = ?',
                (1 if favourite else 0, room_id, user_id),
            )
            return cursor.rowcount > 0

        try:
            return execute_db_operation(_fav)
        except Exception as e:
            log_event('error', f"Error setting favourite: {e}")
            return False

    @handle_exception
    def list_chat_categories(self):
        """Return the distinct non-empty categories currently in use."""
        def _list(cursor):
            cursor.execute(
                "SELECT DISTINCT category FROM chat_rooms WHERE category IS NOT NULL "
                "AND TRIM(category) != '' ORDER BY category"
            )
            return [r[0] for r in cursor.fetchall()]

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing categories: {e}")
            return []

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
    def get_room_info(self, room_id):
        """Return full metadata for a single room (None if not visible)."""
        if not self.auth or not self.auth.current_user:
            return None
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                '''SELECT r.id, r.name, r.description, r.room_type, r.created_by,
                          COALESCE(r.announcement_mode, 0),
                          r.oh_starts_at, r.oh_ends_at,
                          r.linked_course_code, r.linked_assignment_group_id,
                          r.category, r.icon, r.colour,
                          COALESCE(m.is_admin, 0) AS is_admin
                   FROM chat_rooms r
                   LEFT JOIN chat_room_members m
                     ON m.room_id = r.id AND m.user_id = ?
                   WHERE r.id = ?''',
                (user_id, room_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'id': row[0], 'name': row[1], 'description': row[2],
                'room_type': row[3], 'created_by': row[4],
                'announcement_mode': bool(row[5]),
                'oh_starts_at': row[6], 'oh_ends_at': row[7],
                'linked_course_code': row[8],
                'linked_assignment_group_id': row[9],
                'category': row[10], 'icon': row[11], 'colour': row[12],
                'is_admin': bool(row[13]),
            }

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting room info: {e}")
            return None

    @handle_exception
    def sync_course_chat_rooms(self):
        """Best-effort: ensure a chat room exists for every module the
        current user is enrolled in or instructs, and that the user is a
        member. Returns the number of rooms created/updated."""
        if not self.auth or not self.auth.current_user:
            return 0
        user_id = self.auth.current_user['id']
        username = self.auth.current_user.get('username') or ''
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _sync(cursor):
            modules = []
            try:
                cursor.execute('''
                    SELECT m.module_code, m.module_name
                    FROM modules m
                    JOIN student_modules sm ON sm.module_code = m.module_code
                    JOIN students s ON s.student_id = sm.student_id
                    WHERE s.user_id = ? OR s.student_id = ?
                ''', (user_id, username))
                modules = list(cursor.fetchall())
            except Exception:
                # Schema may not be present in this DB; skip silently.
                modules = []
            try:
                cursor.execute('''
                    SELECT module_code, module_name FROM modules
                    WHERE instructor_id = ? OR instructor_id = ?
                ''', (user_id, str(user_id)))
                modules.extend(cursor.fetchall())
            except Exception:
                pass

            seen, count = set(), 0
            for code, name in modules:
                if not code or code in seen:
                    continue
                seen.add(code)
                cursor.execute(
                    'SELECT id FROM chat_rooms WHERE linked_course_code = ?', (code,),
                )
                row = cursor.fetchone()
                if row:
                    room_id = row[0]
                else:
                    room_name = f"{code} — {name}" if name else str(code)
                    cursor.execute(
                        '''INSERT INTO chat_rooms
                           (name, description, room_type, created_by, created_at,
                            is_active, category, linked_course_code)
                           VALUES (?, ?, 'course', ?, ?, 1, 'Courses', ?)''',
                        (room_name[:100], f"Auto-linked to module {code}",
                         user_id, now, code),
                    )
                    room_id = cursor.lastrowid
                    count += 1
                # Ensure the user is a member (admin if instructor, else member).
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, user_id),
                )
                if not cursor.fetchone():
                    cursor.execute(
                        '''INSERT INTO chat_room_members
                           (room_id, user_id, joined_at, is_admin)
                           VALUES (?, ?, ?, 0)''',
                        (room_id, user_id, now),
                    )
            return count

        try:
            return execute_db_operation(_sync)
        except Exception as e:
            log_event('error', f"Error syncing course chat rooms: {e}")
            return 0

    @handle_exception
    def sync_assignment_group_room(self, group_id):
        """Ensure a chat room exists for an assignment group and that all its
        members are joined. Caller must be a group member or an admin."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _sync(cursor):
            try:
                cursor.execute(
                    'SELECT group_name, assignment_id FROM assignment_groups WHERE id = ?',
                    (group_id,),
                )
                row = cursor.fetchone()
            except Exception:
                return False
            if not row:
                return False
            group_name = row[0]
            try:
                cursor.execute(
                    'SELECT student_id FROM assignment_group_members WHERE group_id = ?',
                    (group_id,),
                )
                member_ids = [r[0] for r in cursor.fetchall()]
            except Exception:
                member_ids = []

            cursor.execute(
                'SELECT id FROM chat_rooms WHERE linked_assignment_group_id = ?',
                (group_id,),
            )
            r = cursor.fetchone()
            if r:
                room_id = r[0]
            else:
                cursor.execute(
                    '''INSERT INTO chat_rooms
                       (name, description, room_type, created_by, created_at,
                        is_active, category, linked_assignment_group_id)
                       VALUES (?, ?, 'private', ?, ?, 1, 'Group projects', ?)''',
                    (f"Group: {group_name}"[:100],
                     f"Auto-linked to assignment group {group_id}",
                     user_id, now, group_id),
                )
                room_id = cursor.lastrowid
            for mid in set(member_ids + [user_id]):
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, mid),
                )
                if not cursor.fetchone():
                    is_admin = 1 if mid == user_id else 0
                    cursor.execute(
                        '''INSERT INTO chat_room_members
                           (room_id, user_id, joined_at, is_admin)
                           VALUES (?, ?, ?, ?)''',
                        (room_id, mid, now, is_admin),
                    )
            return room_id

        try:
            return execute_db_operation(_sync)
        except Exception as e:
            log_event('error', f"Error syncing group chat room: {e}")
            return False

    @handle_exception
    def create_chat_poll(self, room_id, question, options,
                         multi_choice=False, closes_at=None):
        """Create a poll as a special chat message. Returns the message id."""
        if not self.auth or not self.auth.current_user:
            return False
        if not question or not options or len(options) < 2:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _create(cursor):
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return False
            cursor.execute(
                '''INSERT INTO chat_messages (room_id, sender_id, content, sent_at)
                   VALUES (?, ?, ?, ?)''',
                (room_id, user_id, f"[poll] {question}", now),
            )
            mid = cursor.lastrowid
            cursor.execute(
                '''INSERT INTO chat_polls (message_id, question, multi_choice, closes_at)
                   VALUES (?, ?, ?, ?)''',
                (mid, question, 1 if multi_choice else 0, closes_at),
            )
            for i, label in enumerate(options):
                if not label or not str(label).strip():
                    continue
                cursor.execute(
                    '''INSERT INTO chat_poll_options (message_id, label, sort_order)
                       VALUES (?, ?, ?)''',
                    (mid, str(label).strip(), i),
                )
            # Auto-propose any date-formatted options as tentative calendar
            # events. Best-effort: failures are swallowed inside the helper.
            try:
                self._propose_poll_dates_inner(cursor, mid)
            except Exception:
                pass
            return mid

        try:
            return execute_db_operation(_create)
        except Exception as e:
            log_event('error', f"Error creating poll: {e}")
            return False

    @handle_exception
    def get_chat_poll(self, message_id):
        """Return a poll dict {question, multi_choice, closes_at, options:[
            {id, label, count, mine}
        ], total_voters}."""
        if not self.auth or not self.auth.current_user:
            return None
        user_id = self.auth.current_user['id']

        def _get(cursor):
            cursor.execute(
                'SELECT question, multi_choice, closes_at FROM chat_polls WHERE message_id = ?',
                (message_id,),
            )
            head = cursor.fetchone()
            if not head:
                return None
            cursor.execute(
                '''SELECT o.id, o.label,
                          (SELECT COUNT(*) FROM chat_poll_votes WHERE option_id = o.id),
                          (SELECT COUNT(*) FROM chat_poll_votes WHERE option_id = o.id AND user_id = ?)
                   FROM chat_poll_options o
                   WHERE o.message_id = ?
                   ORDER BY o.sort_order, o.id''',
                (user_id, message_id),
            )
            options = [{'id': r[0], 'label': r[1], 'count': r[2], 'mine': bool(r[3])}
                       for r in cursor.fetchall()]
            cursor.execute(
                '''SELECT COUNT(DISTINCT v.user_id)
                   FROM chat_poll_votes v
                   JOIN chat_poll_options o ON v.option_id = o.id
                   WHERE o.message_id = ?''',
                (message_id,),
            )
            total = (cursor.fetchone() or [0])[0]
            return {
                'message_id': message_id,
                'question': head[0],
                'multi_choice': bool(head[1]),
                'closes_at': head[2],
                'options': options,
                'total_voters': total,
            }

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting poll: {e}")
            return None

    @handle_exception
    def vote_chat_poll(self, message_id, option_ids):
        """Cast votes. For single-choice polls only the first option_id is used
        and any prior vote is replaced. For multi-choice the set is replaced."""
        if not self.auth or not self.auth.current_user:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if not option_ids:
            option_ids = []

        def _vote(cursor):
            cursor.execute(
                'SELECT multi_choice, closes_at FROM chat_polls WHERE message_id = ?',
                (message_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            if row[1] and row[1] < now:
                return False
            multi = bool(row[0])
            chosen = list(option_ids) if multi else option_ids[:1]
            # Validate options belong to this poll.
            placeholders = ','.join('?' for _ in chosen)
            valid_ids = set()
            if chosen:
                cursor.execute(
                    f'SELECT id FROM chat_poll_options WHERE message_id = ? AND id IN ({placeholders})',
                    [message_id, *chosen],
                )
                valid_ids = {r[0] for r in cursor.fetchall()}
            # Replace user's previous votes for this poll.
            cursor.execute(
                '''DELETE FROM chat_poll_votes
                   WHERE user_id = ? AND option_id IN (
                       SELECT id FROM chat_poll_options WHERE message_id = ?
                   )''',
                (user_id, message_id),
            )
            for oid in valid_ids:
                cursor.execute(
                    'INSERT INTO chat_poll_votes (option_id, user_id, voted_at) VALUES (?, ?, ?)',
                    (oid, user_id, now),
                )
            return True

        try:
            return execute_db_operation(_vote)
        except Exception as e:
            log_event('error', f"Error voting on poll: {e}")
            return False

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
                           VALUES (?, ?, ?, ?, ?, 'High', '["chat-report"]', 'Pending')''',
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

    @handle_exception
    def get_module_info(self, module_code):
        """Return {code, name, description, instructor, assignments:[...]} for
        a module. Best-effort; returns None if the academics tables aren't
        present."""
        if not module_code:
            return None

        def _get(cursor):
            try:
                cursor.execute(
                    '''SELECT module_code, module_name, description,
                              COALESCE(instructor_id, '')
                       FROM modules WHERE module_code = ?''',
                    (module_code,),
                )
                row = cursor.fetchone()
            except Exception:
                return None
            if not row:
                return None
            info = {
                'code': row[0], 'name': row[1],
                'description': row[2] or '', 'instructor': row[3] or '',
            }
            try:
                cursor.execute(
                    '''SELECT id, title, due_date, max_marks, assignment_type
                       FROM assignments
                       WHERE module_code = ? AND COALESCE(is_active, 1) = 1
                       ORDER BY due_date ASC LIMIT 50''',
                    (module_code,),
                )
                info['assignments'] = [
                    {'id': r[0], 'title': r[1], 'due_date': r[2],
                     'max_marks': r[3], 'type': r[4]}
                    for r in cursor.fetchall()
                ]
            except Exception:
                info['assignments'] = []
            return info

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting module info: {e}")
            return None

    @handle_exception
    def post_assignment_due_dates(self, room_id, days_ahead=30):
        """For a course-linked room, post a `[due]` system message for each
        upcoming assignment in the next `days_ahead` days. Idempotent: each
        (room, assignment) is posted at most once."""
        if not self.auth or not self.auth.current_user:
            return 0
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        def _post(cursor):
            cursor.execute(
                'SELECT linked_course_code FROM chat_rooms WHERE id = ?',
                (room_id,),
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return 0
            module_code = row[0]
            try:
                cursor.execute(
                    '''SELECT id, title, due_date FROM assignments
                       WHERE module_code = ?
                         AND COALESCE(is_active, 1) = 1
                         AND date(due_date) >= date('now')
                         AND date(due_date) <= date('now', ?)
                       ORDER BY due_date ASC''',
                    (module_code, f'+{int(days_ahead)} days'),
                )
                rows = cursor.fetchall()
            except Exception:
                return 0
            posted = 0
            for aid, title, due in rows:
                key = str(aid)
                cursor.execute(
                    'SELECT 1 FROM chat_system_posts WHERE room_id = ? AND kind = ? AND key = ?',
                    (room_id, 'assignment_due', key),
                )
                if cursor.fetchone():
                    continue
                content = f"[due] {title} — due {(due or '')[:16]}"
                sender_for_msg = self._get_or_create_system_user_id(cursor, user_id)
                cursor.execute(
                    '''INSERT INTO chat_messages
                       (room_id, sender_id, content, sent_at)
                       VALUES (?, ?, ?, ?)''',
                    (room_id, sender_for_msg, content, now),
                )
                mid = cursor.lastrowid
                cursor.execute(
                    '''INSERT INTO chat_system_posts
                       (room_id, kind, key, message_id, posted_at)
                       VALUES (?, ?, ?, ?, ?)''',
                    (room_id, 'assignment_due', key, mid, now),
                )
                posted += 1
            if posted:
                self._log_communication_action(
                    user_id, "post_assignment_due_dates",
                    f"Posted {posted} due-date notice(s) to room {room_id}",
                    cursor=cursor,
                )
            return posted

        try:
            return execute_db_operation(_post)
        except Exception as e:
            log_event('error', f"Error posting assignment due dates: {e}")
            return 0

    @handle_exception
    def list_staff_teams(self):
        """Return distinct staff departments (used as team mentions)
        with member count. Best-effort against staff_profiles."""
        def _list(cursor):
            try:
                cursor.execute(
                    '''SELECT department, COUNT(*)
                       FROM staff_profiles
                       WHERE department IS NOT NULL AND TRIM(department) != ''
                       GROUP BY department ORDER BY department'''
                )
                return [{'name': r[0], 'member_count': r[1]}
                        for r in cursor.fetchall()]
            except Exception:
                return []

        try:
            return execute_db_operation(_list)
        except Exception as e:
            log_event('error', f"Error listing staff teams: {e}")
            return []

    @handle_exception
    def get_team_members(self, team_name):
        """Return user dicts for staff in a given department (case-insensitive)."""
        if not team_name:
            return []

        def _get(cursor):
            out = []
            try:
                cursor.execute(
                    '''SELECT sp.user_id, sp.job_title,
                              COALESCE(u.username, ''),
                              COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                              COALESCE(u.email, '')
                       FROM staff_profiles sp
                       LEFT JOIN users u
                         ON CAST(u.id AS TEXT) = sp.user_id
                            OR u.username = sp.user_id
                       WHERE LOWER(sp.department) = LOWER(?)
                       ORDER BY u.first_name, u.last_name''',
                    (team_name,),
                )
            except Exception:
                return []
            for r in cursor.fetchall():
                full = f"{r[3]} {r[4]}".strip()
                out.append({
                    'user_id_str': r[0],
                    'job_title': r[1] or '',
                    'username': r[2] or '',
                    'full_name': full or (r[2] or ''),
                    'email': r[5] or '',
                })
            return out

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting team members: {e}")
            return []

    # ------------------------------------------------------------------
    # Generic entity linkage: events, clubs, residences, advisor OH, etc.
    # ------------------------------------------------------------------

    @handle_exception
    def get_or_create_linked_room(self, entity_type, entity_id, *, name,
                                  description=None, room_type='private',
                                  category=None, icon=None,
                                  invite_user_ids=None,
                                  oh_starts_at=None, oh_ends_at=None,
                                  announcement_mode=False):
        """Find or create a chat room linked to an external entity.

        Caller-supplied entity_type/entity_id pair is the unique key. If a room
        already exists, the caller is added as a member if missing, plus any
        users in invite_user_ids. Returns the room id (or False on failure)."""
        if not self.auth or not self.auth.current_user:
            return False
        if not entity_type or entity_id is None:
            return False
        user_id = self.auth.current_user['id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        eid_str = str(entity_id)

        def _go(cursor):
            cursor.execute(
                'SELECT id FROM chat_rooms WHERE linked_entity_type = ? AND linked_entity_id = ?',
                (entity_type, eid_str),
            )
            row = cursor.fetchone()
            if row:
                room_id = row[0]
            else:
                cursor.execute(
                    '''INSERT INTO chat_rooms
                       (name, description, room_type, created_by, created_at,
                        is_active, category, icon,
                        linked_entity_type, linked_entity_id,
                        oh_starts_at, oh_ends_at, announcement_mode)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)''',
                    (name[:100], description, room_type, user_id, now,
                     category, icon, entity_type, eid_str,
                     oh_starts_at, oh_ends_at,
                     1 if announcement_mode else 0),
                )
                room_id = cursor.lastrowid
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 1)''',
                    (room_id, user_id, now),
                )
                self._log_communication_action(
                    user_id, "create_linked_room",
                    f"Created linked room {room_id} for {entity_type}#{eid_str}",
                    cursor=cursor,
                )
            # Ensure caller is a member.
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 0)''',
                    (room_id, user_id, now),
                )
            # Add any extra invitees.
            for uid in (invite_user_ids or []):
                if not uid or uid == user_id:
                    continue
                cursor.execute(
                    'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                    (room_id, uid),
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    '''INSERT INTO chat_room_members
                       (room_id, user_id, joined_at, is_admin)
                       VALUES (?, ?, ?, 0)''',
                    (room_id, uid, now),
                )
            return room_id

        try:
            return execute_db_operation(_go)
        except Exception as e:
            log_event('error', f"Error get_or_create_linked_room: {e}")
            return False

    # Convenience wrappers per domain ---------------------------------

    def get_or_create_event_room(self, event_id, event_title):
        return self.get_or_create_linked_room(
            'event', event_id,
            name=f"Event: {event_title}",
            category='Events', icon='📅',
            room_type='public',
        )

    def get_or_create_club_room(self, club_id, club_name, member_user_ids=None):
        return self.get_or_create_linked_room(
            'club', club_id,
            name=f"Club: {club_name}",
            category='Clubs & Societies', icon='🎭',
            room_type='private',
            invite_user_ids=member_user_ids or [],
        )

    def get_or_create_residence_room(self, residence_id, residence_name,
                                     resident_user_ids=None):
        return self.get_or_create_linked_room(
            'residence', residence_id,
            name=f"Residence: {residence_name}",
            category='Housing', icon='🏠',
            room_type='private',
            invite_user_ids=resident_user_ids or [],
        )

    def get_or_create_advisor_oh_room(self, advisor_user_id, student_user_id,
                                      starts_at=None, ends_at=None):
        """An office-hours-style 1:1 room between a career advisor and a student."""
        if not advisor_user_id or not student_user_id:
            return False
        # Compose a stable key from the two participants + start time so the
        # same advisor/student get a fresh room per appointment.
        eid = f"{advisor_user_id}-{student_user_id}-{starts_at or 'nows'}"
        return self.get_or_create_linked_room(
            'advisor_oh', eid,
            name="Career advisor — office hours",
            description="Auto-created from appointment booking.",
            category='Career', icon='💼',
            room_type='private',
            invite_user_ids=[advisor_user_id, student_user_id],
            oh_starts_at=starts_at, oh_ends_at=ends_at,
        )

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

    @handle_exception
    def get_user_profile(self, user_id):
        """Return a profile snapshot for any user the current user can see.
        Joins users + staff_profiles (department/job_title/manager) and the
        student_id if available."""
        if not self.auth or not self.auth.current_user:
            return None

        def _get(cursor):
            cursor.execute(
                '''SELECT id, COALESCE(username, ''),
                          COALESCE(first_name, ''), COALESCE(last_name, ''),
                          COALESCE(email, ''), COALESCE(role, '')
                   FROM users WHERE id = ?''',
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            full = f"{row[2]} {row[3]}".strip()
            profile = {
                'user_id': row[0], 'username': row[1],
                'full_name': full or row[1], 'email': row[4],
                'role': row[5],
            }
            try:
                cursor.execute(
                    '''SELECT department, job_title, employment_type,
                              office_location, phone_extension, manager_id, bio,
                              expertise_areas
                       FROM staff_profiles
                       WHERE user_id = ? OR user_id = ?''',
                    (str(user_id), profile['username']),
                )
                sp = cursor.fetchone()
                if sp:
                    profile['staff'] = {
                        'department': sp[0], 'job_title': sp[1],
                        'employment_type': sp[2], 'office': sp[3],
                        'phone_ext': sp[4], 'manager_id': sp[5],
                        'bio': sp[6], 'expertise': sp[7],
                    }
            except Exception:
                profile['staff'] = None
            try:
                cursor.execute(
                    'SELECT student_id FROM students WHERE user_id = ?',
                    (user_id,),
                )
                sr = cursor.fetchone()
                if sr:
                    profile['student_id'] = sr[0]
            except Exception:
                pass
            return profile

        try:
            return execute_db_operation(_get)
        except Exception as e:
            log_event('error', f"Error getting user profile: {e}")
            return None

    @handle_exception
    def resolve_username_to_id(self, username):
        """Best-effort lookup. Returns user_id or None."""
        if not username:
            return None
        u = username.lstrip('@')

        def _q(cursor):
            cursor.execute('SELECT id FROM users WHERE username = ?', (u,))
            r = cursor.fetchone()
            return r[0] if r else None

        try:
            return execute_db_operation(_q)
        except Exception:
            return None

    def _emit_notification(self, cursor, user_id, title, message,
                           ntype='chat', data=None):
        """Best-effort INSERT into the central notifications table. The schema
        of `notifications` has been migrated multiple times in this repo, so
        we discover the actual columns at runtime and only fill what exists."""
        if not user_id:
            return
        try:
            cursor.execute("PRAGMA table_info(notifications)")
            cols = {row[1] for row in cursor.fetchall()}
        except Exception:
            return
        if not cols:
            return
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Candidate values keyed by column name. Each is set only if the
        # column actually exists in the deployed table. Two real shapes:
        #   - university `notifications` (student_records.db): channel +
        #     priority NOT NULL, source_system/source_id, metadata, created_at
        #   - school `notifications` (primary_school.db et al.): notification_type,
        #     link, created_at
        candidates = {
            'user_id': str(user_id),
            'recipient_id': str(user_id),
            'recipient_type': 'user',
            'channel': 'in_app',
            'priority': 'normal',
            'title': (title or '')[:200],
            'message': (message or '')[:500],
            'notification_type': ntype,
            'type': ntype,
            'source_system': 'chat',
            'source_id': (data or '')[:80],
            'metadata': (data or '')[:500],
            'link': (data or '')[:500],
            'data': (data or '')[:500],
            'is_read': 0,
            'is_archived': 0,
            'sent': 0,
            'created_datetime': now,
            'created_date': now,
            'created_at': now,
        }
        used = {k: v for k, v in candidates.items() if k in cols}
        if 'user_id' not in used and 'recipient_id' not in used:
            return
        col_list = list(used.keys())
        placeholders = ', '.join('?' for _ in col_list)
        sql = (
            f"INSERT INTO notifications ({', '.join(col_list)}) "
            f"VALUES ({placeholders})"
        )
        try:
            cursor.execute(sql, [used[c] for c in col_list])
        except Exception:
            # Don't propagate. Likely NOT NULL on a column we don't know about.
            pass

    def _emit_chat_mention_notifications(self, cursor, room_id, sender_id,
                                         sender_name, content, message_id):
        """Scan content for @user mentions and push a notification to each
        addressee (skip the sender)."""
        if not content:
            return
        import re
        seen = set()
        for m in re.finditer(r'@(\w+)', content):
            handle = m.group(1)
            if handle.startswith('team:'):
                continue
            if handle in seen:
                continue
            seen.add(handle)
            cursor.execute('SELECT id FROM users WHERE username = ?', (handle,))
            row = cursor.fetchone()
            if not row or row[0] == sender_id:
                continue
            self._emit_notification(
                cursor, row[0],
                f"{sender_name} mentioned you in chat",
                (content[:140] + '…') if len(content) > 140 else content,
                ntype='chat_mention',
                data=f"room={room_id};message={message_id}",
            )

    def _propose_poll_dates_inner(self, cursor, message_id, location=None,
                                  user_id=None, username=None):
        """Cursor-level helper used by both the public method and
        create_chat_poll's auto-propose path. Returns a list of
        {option, date} dicts for the inserts that succeeded."""
        if user_id is None and self.auth and self.auth.current_user:
            user_id = self.auth.current_user['id']
        if username is None and self.auth and self.auth.current_user:
            username = self.auth.current_user.get('username') or str(user_id)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            '''SELECT p.question, m.room_id, r.name
               FROM chat_polls p
               JOIN chat_messages m ON m.id = p.message_id
               JOIN chat_rooms r ON r.id = m.room_id
               WHERE p.message_id = ?''',
            (message_id,),
        )
        head = cursor.fetchone()
        if not head:
            return []
        question, _room_id, room_name = head
        cursor.execute(
            'SELECT id, label FROM chat_poll_options WHERE message_id = ?',
            (message_id,),
        )
        options = cursor.fetchall()
        import re
        iso = re.compile(r'(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}(?::\d{2})?))?')
        proposed = []
        for opt_id, label in options:
            m = iso.search(label or '')
            if not m:
                continue
            date_part = m.group(1)
            time_part = m.group(2) or ''
            date_iso = (date_part + ' ' + time_part) if time_part else date_part
            event_id = f"poll-{message_id}-{opt_id}"
            try:
                cursor.execute('SELECT 1 FROM events WHERE id = ?', (event_id,))
                if cursor.fetchone():
                    continue
                cursor.execute(
                    '''INSERT INTO events
                       (id, name, description, event_type, date,
                        date_start, all_day, location, created_by,
                        date_added, status, priority)
                       VALUES (?, ?, ?, 'Chat poll', ?, ?, 0, ?, ?, ?, 'tentative', 1)''',
                    (event_id,
                     f"[Tentative] {question}"[:120],
                     f"Proposed via chat poll in '{room_name}'.\n"
                     f"Option: {label}",
                     date_iso, date_iso, location or '', username, now),
                )
                proposed.append({'option': label, 'date': date_iso})
            except Exception:
                # events table may not exist or have a different schema
                return proposed
        if proposed:
            try:
                self._log_communication_action(
                    user_id, "propose_poll_dates_to_calendar",
                    f"Proposed {len(proposed)} dates from poll {message_id}",
                    cursor=cursor,
                )
            except Exception:
                pass
        return proposed

    @handle_exception
    def propose_poll_dates_to_calendar(self, message_id, location=None):
        """If a poll's options contain ISO date strings, insert each as a
        tentative event into the academic-calendar `events` table. Returns
        the list of date strings that were proposed."""
        if not self.auth or not self.auth.current_user:
            return []

        def _propose(cursor):
            return self._propose_poll_dates_inner(cursor, message_id, location)

        try:
            return execute_db_operation(_propose)
        except Exception as e:
            log_event('error', f"Error proposing poll dates: {e}")
            return []
