"""PollsMixin — extracted from chat.py."""
from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
)


class PollsMixin:
    """Methods grouped from the original _ChatMixin."""

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

    # ------------------------------------------------------------------
    # Batched per-tick fetch and per-poll hydration. The per-window poll
    # loop used to make 5–7 separate execute_db_operation calls (each
    # opening a fresh connection); these helpers do everything inside one
    # cursor so the connection-open overhead is paid once per tick.
    # ------------------------------------------------------------------

    @handle_exception
    def get_chat_polls_for_messages(self, message_ids):
        """Return {message_id: poll_dict} for any poll messages in the list.
        Single round trip per table — replaces N+1 calls to get_chat_poll."""
        if not self.auth or not self.auth.current_user or not message_ids:
            return {}
        user_id = self.auth.current_user['id']
        ids = [int(m) for m in message_ids]
        placeholders = ','.join('?' for _ in ids)

        def _go(cursor):
            cursor.execute(
                f'''SELECT message_id, question, multi_choice, closes_at
                    FROM chat_polls WHERE message_id IN ({placeholders})''',
                ids,
            )
            polls = {row[0]: {
                'message_id': row[0], 'question': row[1],
                'multi_choice': bool(row[2]), 'closes_at': row[3],
                'options': [], 'total_voters': 0,
            } for row in cursor.fetchall()}
            if not polls:
                return {}
            poll_ids = list(polls.keys())
            placeholders2 = ','.join('?' for _ in poll_ids)
            # Options + totals + my-vote in one go
            cursor.execute(
                f'''SELECT o.id, o.message_id, o.label, o.sort_order,
                          (SELECT COUNT(*) FROM chat_poll_votes WHERE option_id = o.id),
                          (SELECT COUNT(*) FROM chat_poll_votes
                            WHERE option_id = o.id AND user_id = ?)
                   FROM chat_poll_options o
                   WHERE o.message_id IN ({placeholders2})
                   ORDER BY o.message_id, o.sort_order, o.id''',
                [user_id, *poll_ids],
            )
            for opt_id, mid, label, _so, count, mine in cursor.fetchall():
                polls[mid]['options'].append({
                    'id': opt_id, 'label': label, 'count': count,
                    'mine': bool(mine),
                })
            # Distinct voter counts per poll
            cursor.execute(
                f'''SELECT o.message_id, COUNT(DISTINCT v.user_id)
                    FROM chat_poll_votes v
                    JOIN chat_poll_options o ON v.option_id = o.id
                    WHERE o.message_id IN ({placeholders2})
                    GROUP BY o.message_id''',
                poll_ids,
            )
            for mid, total in cursor.fetchall():
                if mid in polls:
                    polls[mid]['total_voters'] = total
            return polls

        try:
            return execute_db_operation(_go)
        except Exception as e:
            log_event('error', f"Error batching polls: {e}")
            return {}

