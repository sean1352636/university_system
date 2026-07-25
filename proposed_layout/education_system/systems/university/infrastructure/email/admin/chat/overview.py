"""OverviewMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.systems.university.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)
from ._helpers import _format_message_row


class OverviewMixin:
    """Methods grouped from the original _ChatMixin."""

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
    def get_room_realtime_state(self, room_id, since_message_id=0,
                                include_members=False, typing_ttl_seconds=5,
                                presence_window_seconds=30):
        """One-shot fetch for the chat-window polling loop.

        Returns a dict with keys:
          - 'messages':       list of message dicts (oldest-first), only if
                              there are new ones
          - 'last_message_id': max id at fetch time
          - 'typing_users':   list of display names (excluding self)
          - 'presence':       {'online': N, 'total': M}
          - 'unread_count':   count for current user (incl. all rooms? No —
                              just this room) — useful for badge updates
          - 'members':        only when include_members; same shape as
                              get_room_members + presence merged in
        """
        if not self.auth or not self.auth.current_user:
            return {}
        user_id = self.auth.current_user['id']
        from datetime import timedelta
        now = datetime.now()
        typing_cutoff = (now - timedelta(seconds=typing_ttl_seconds)).strftime(
            '%Y-%m-%d %H:%M:%S'
        )
        presence_cutoff = (now - timedelta(seconds=presence_window_seconds)).strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        def _go(cursor):
            # 1. Membership check
            cursor.execute(
                'SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?',
                (room_id, user_id),
            )
            if not cursor.fetchone():
                return {}

            out = {'messages': [], 'last_message_id': since_message_id or 0,
                   'typing_users': [], 'presence': {'online': 0, 'total': 0},
                   'unread_count': 0}

            # 2. MAX(id) probe; skip heavy join if nothing new
            cursor.execute(
                'SELECT MAX(id) FROM chat_messages WHERE room_id = ?',
                (room_id,),
            )
            mx_row = cursor.fetchone()
            max_id = (mx_row and mx_row[0]) or 0
            out['last_message_id'] = max_id
            if max_id and max_id > (since_message_id or 0):
                cursor.execute(
                    '''
                    SELECT m.id, m.content, m.sent_at,
                           COALESCE(u.username, 'User ' || m.sender_id),
                           COALESCE(u.first_name, ''), COALESCE(u.last_name, ''),
                           m.sender_id, m.edited_at, COALESCE(m.is_deleted, 0),
                           m.reply_to_id, m.pinned_at,
                           m.attachment_path, m.attachment_name,
                           m.attachment_mime, m.attachment_size,
                           r.content,
                           COALESCE(ru.username, 'User ' || r.sender_id),
                           COALESCE(r.is_deleted, 0),
                           u.role,
                           COALESCE(m.is_encrypted, 0), k.key_b64
                    FROM chat_messages m
                    LEFT JOIN users u  ON m.sender_id = u.id
                    LEFT JOIN chat_messages r ON m.reply_to_id = r.id
                    LEFT JOIN users ru ON r.sender_id = ru.id
                    LEFT JOIN chat_room_keys k ON k.room_id = m.room_id
                    WHERE m.room_id = ? AND m.id > ?
                    ORDER BY m.id ASC
                    LIMIT 200
                    ''',
                    (room_id, since_message_id or 0),
                )
                for row in cursor.fetchall():
                    full_name = f"{row[4]} {row[5]}".strip()
                    out['messages'].append(_format_message_row(row, full_name))

            # 3. Typing indicators
            cursor.execute(
                '''
                SELECT COALESCE(u.username, 'User ' || u.id),
                       COALESCE(u.first_name, ''), COALESCE(u.last_name, '')
                FROM chat_typing t
                JOIN users u ON u.id = t.user_id
                WHERE t.room_id = ? AND t.user_id != ? AND t.started_at >= ?
                ORDER BY t.started_at ASC
                ''',
                (room_id, user_id, typing_cutoff),
            )
            for row in cursor.fetchall():
                full = f"{row[1]} {row[2]}".strip()
                out['typing_users'].append(full or row[0])

            # 4. Presence summary (and optional members list)
            cursor.execute(
                '''
                SELECT mem.user_id, p.last_seen_at,
                       CASE WHEN p.last_seen_at IS NOT NULL AND p.last_seen_at >= ?
                            THEN 1 ELSE 0 END,
                       mem.is_admin
                FROM chat_room_members mem
                LEFT JOIN chat_presence p
                  ON p.room_id = mem.room_id AND p.user_id = mem.user_id
                WHERE mem.room_id = ?
                ''',
                (presence_cutoff, room_id),
            )
            presence_rows = cursor.fetchall()
            online = sum(1 for r in presence_rows if r[2])
            out['presence'] = {'online': online, 'total': len(presence_rows)}

            if include_members:
                cursor.execute(
                    'SELECT created_by FROM chat_rooms WHERE id = ?', (room_id,),
                )
                creator_row = cursor.fetchone()
                creator_id = creator_row[0] if creator_row else None
                cursor.execute(
                    '''
                    SELECT m.user_id, u.username, u.first_name, u.last_name,
                           u.email, m.joined_at, m.is_admin,
                           COALESCE(m.is_banned, 0), m.muted_until
                    FROM chat_room_members m
                    JOIN users u ON m.user_id = u.id
                    WHERE m.room_id = ?
                    ORDER BY m.is_admin DESC, m.joined_at ASC
                    ''',
                    (room_id,),
                )
                presence_map = {
                    r[0]: {'last_seen_at': r[1], 'is_online': bool(r[2])}
                    for r in presence_rows
                }
                members = []
                for row in cursor.fetchall():
                    full = f"{row[2]} {row[3]}".strip()
                    p = presence_map.get(row[0], {})
                    members.append({
                        'user_id': row[0], 'username': row[1],
                        'full_name': full or row[1],
                        'email': row[4], 'joined_at': row[5],
                        'is_admin': bool(row[6]),
                        'is_banned': bool(row[7]),
                        'muted_until': row[8],
                        'is_creator': row[0] == creator_id,
                        'is_online': p.get('is_online', False),
                        'last_seen_at': p.get('last_seen_at'),
                    })
                out['members'] = members

            # 5. Unread count for this room (small index lookup now)
            cursor.execute(
                '''
                SELECT COUNT(*)
                FROM chat_messages m
                LEFT JOIN chat_message_reads r
                  ON r.room_id = m.room_id AND r.user_id = ?
                WHERE m.room_id = ?
                  AND m.id > COALESCE(r.last_read_message_id, 0)
                  AND m.sender_id != ?
                ''',
                (user_id, room_id, user_id),
            )
            row = cursor.fetchone()
            out['unread_count'] = row[0] if row else 0

            return out

        try:
            return execute_db_operation(_go)
        except Exception as e:
            log_event('error', f"Error in get_room_realtime_state: {e}")
            return {}

    @handle_exception
    def get_my_rooms_overview(self):
        """One-shot fetch for the My Rooms / Public Rooms tab refresh.

        Replaces three separate execute_db_operation calls (joined, unread,
        public) with one cursor pass — the per-call connection-open overhead
        was the dominant cost on actions like 'Join Room'.

        Returns {'joined': [...], 'public': [...], 'unread': {room_id: n}}."""
        if not self.auth or not self.auth.current_user:
            return {'joined': [], 'public': [], 'unread': {}}
        user_id = self.auth.current_user['id']

        def _go(cursor):
            # Joined rooms (with the same shape get_chat_rooms('joined') yields).
            cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username as creator, m.is_admin,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id),
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id),
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
            ''', (user_id,))
            joined = []
            for row in cursor.fetchall():
                joined.append({
                    'id': row[0], 'name': row[1], 'description': row[2],
                    'room_type': row[3], 'created_at': row[4],
                    'creator': row[5], 'is_admin': bool(row[6]),
                    'member_count': row[7], 'message_count': row[8],
                    'category': row[9], 'icon': row[10], 'colour': row[11],
                    'is_favourite': bool(row[12]),
                    'is_banned': bool(row[13]),
                    'muted_until': row[14],
                    'created_by': row[15],
                    'linked_course_code': row[16],
                    'linked_assignment_group_id': row[17],
                    'announcement_mode': bool(row[18]),
                    'oh_starts_at': row[19], 'oh_ends_at': row[20],
                })

            # Public rooms the user isn't already in.
            cursor.execute('''
                SELECT r.id, r.name, r.description, r.room_type, r.created_at,
                       u.username, 0,
                       (SELECT COUNT(*) FROM chat_room_members WHERE room_id = r.id),
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id)
                FROM chat_rooms r
                JOIN users u ON r.created_by = u.id
                WHERE r.room_type = 'public' AND r.is_active = 1
                  AND r.id NOT IN (
                      SELECT room_id FROM chat_room_members WHERE user_id = ?
                  )
                ORDER BY r.name
            ''', (user_id,))
            public = [
                {'id': row[0], 'name': row[1], 'description': row[2],
                 'room_type': row[3], 'created_at': row[4],
                 'creator': row[5], 'is_admin': False,
                 'member_count': row[7], 'message_count': row[8]}
                for row in cursor.fetchall()
            ]

            # Unread counts per room (single aggregate over the chat_messages
            # index — fast post-migration).
            cursor.execute('''
                SELECT m.room_id,
                       COUNT(*) FILTER (WHERE m.id > COALESCE(r.last_read_message_id, 0)
                                        AND m.sender_id != ?)
                FROM chat_room_members mem
                JOIN chat_messages m ON m.room_id = mem.room_id
                LEFT JOIN chat_message_reads r
                  ON r.room_id = mem.room_id AND r.user_id = mem.user_id
                WHERE mem.user_id = ?
                GROUP BY m.room_id
            ''', (user_id, user_id))
            unread = {row[0]: row[1] for row in cursor.fetchall()}

            return {'joined': joined, 'public': public, 'unread': unread}

        try:
            return execute_db_operation(_go)
        except Exception as e:
            log_event('error', f"Error in get_my_rooms_overview: {e}")
            return {'joined': [], 'public': [], 'unread': {}}
