"""
Communication Hub Manager

Provides functionality for:
- Forum creation and membership management
- Thread creation, viewing, and moderation
- Threaded replies with solution marking
- Poll creation, voting, and results
- Pinned messages with expiration
- Cross-entity search across threads and replies
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier


class CommHubManager:
    """Manager for forums, threads, replies, polls, pinned messages, and search."""

    # ==================== FORUM MANAGEMENT ====================

    @staticmethod
    def create_forum(name: str, description: str, forum_type: str,
                     department: str, visibility: str,
                     created_by: str) -> int:
        """Create a new forum.

        Args:
            name: Forum name.
            description: Purpose or description of the forum.
            forum_type: Type of forum (e.g. 'general', 'department', 'project').
            department: Department the forum belongs to.
            visibility: Visibility level (e.g. 'public', 'private', 'department').
            created_by: User ID of the creator.

        Returns:
            The ID of the newly created forum.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO comm_hub_forums (
                    name, description, forum_type, department,
                    visibility, is_archived, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            ''', (
                name, description, forum_type, department,
                visibility, created_by,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            forum_id = cursor.lastrowid
            log_activity('create', 'comm_hub_forum', details={
                'forum_id': forum_id, 'name': name,
                'created_by': created_by,
            })
            return forum_id

    @staticmethod
    def get_forums(forum_type: str = None,
                   department: str = None) -> List[Dict[str, Any]]:
        """Get forums with optional filters, excluding archived forums.

        Args:
            forum_type: Filter by forum type.
            department: Filter by department name.

        Returns:
            A list of forum dicts ordered by name, excluding archived forums.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM comm_hub_forums WHERE is_archived = 0'
            params: list = []

            if forum_type:
                query += ' AND forum_type = ?'
                params.append(forum_type)

            if department:
                query += ' AND department = ?'
                params.append(department)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_forum(forum_id: int) -> Optional[Dict[str, Any]]:
        """Get a single forum by ID.

        Args:
            forum_id: The forum's primary key.

        Returns:
            A dict of the forum row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM comm_hub_forums WHERE forum_id = ?
            ''', (forum_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_forum(forum_id: int, **data) -> None:
        """Update allowed fields on a forum.

        Allowed fields: name, description, forum_type, visibility, is_archived.

        Args:
            forum_id: The forum to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'name', 'description', 'forum_type', 'visibility', 'is_archived',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(forum_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE comm_hub_forums SET ' + ', '.join(fields) + ' WHERE forum_id = ?',
                values)
            log_activity('update', 'comm_hub_forum', details={
                'forum_id': forum_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def get_forum_members(forum_id: int) -> List[Dict[str, Any]]:
        """Get all members of a forum.

        Args:
            forum_id: The forum to list members for.

        Returns:
            A list of member dicts for the given forum.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM comm_hub_forum_members
                WHERE forum_id = ?
            ''', (forum_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def add_forum_member(forum_id: int, user_id: str,
                         role: str = 'member') -> int:
        """Add a member to a forum.

        Args:
            forum_id: The forum to add the member to.
            user_id: The user to add.
            role: The member's role (default 'member').

        Returns:
            The ID of the new comm_hub_forum_members row.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO comm_hub_forum_members (
                    forum_id, user_id, role, joined_at
                ) VALUES (?, ?, ?, ?)
            ''', (
                forum_id, user_id, role,
                datetime.now().isoformat(),
            ))
            member_id = cursor.lastrowid
            log_activity('create', 'comm_hub_forum_member', details={
                'forum_id': forum_id, 'user_id': user_id,
                'role': role,
            })
            return member_id

    @staticmethod
    def remove_forum_member(forum_id: int, user_id: str) -> None:
        """Remove a member from a forum.

        Args:
            forum_id: The forum to remove the member from.
            user_id: The user to remove.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM comm_hub_forum_members
                WHERE forum_id = ? AND user_id = ?
            ''', (forum_id, user_id))
            log_activity('delete', 'comm_hub_forum_member', details={
                'forum_id': forum_id, 'user_id': user_id,
            })

    # ==================== THREAD MANAGEMENT ====================

    @staticmethod
    def create_thread(forum_id: int, title: str, content: str,
                      author_id: str) -> int:
        """Create a new thread in a forum.

        Args:
            forum_id: The forum this thread belongs to.
            title: Thread title.
            content: Thread body content.
            author_id: User ID of the thread author.

        Returns:
            The ID of the newly created thread.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO comm_hub_threads (
                    forum_id, title, content, author_id,
                    is_pinned, is_locked, reply_count, view_count,
                    last_reply_at, last_reply_by,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 0, 0, 0, NULL, NULL, ?, ?)
            ''', (
                forum_id, title, content, author_id,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            thread_id = cursor.lastrowid
            log_activity('create', 'comm_hub_thread', details={
                'thread_id': thread_id, 'forum_id': forum_id,
                'title': title, 'author_id': author_id,
            })
            return thread_id

    @staticmethod
    def get_threads(forum_id: int, offset: int = 0,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """Get threads for a forum with pagination.

        Threads are ordered by pinned status first, then by most recent
        reply activity, then by creation date.

        Args:
            forum_id: The forum to list threads for.
            offset: Number of rows to skip (default 0).
            limit: Maximum number of rows to return (default 50).

        Returns:
            A list of thread dicts ordered by is_pinned DESC,
            last_reply_at DESC NULLS LAST, created_at DESC.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM comm_hub_threads
                WHERE forum_id = ?
                ORDER BY is_pinned DESC,
                         last_reply_at DESC NULLS LAST,
                         created_at DESC
                LIMIT ? OFFSET ?
            ''', (forum_id, limit, offset)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_thread(thread_id: int) -> Optional[Dict[str, Any]]:
        """Get a single thread by ID.

        Args:
            thread_id: The thread's primary key.

        Returns:
            A dict of the thread row, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM comm_hub_threads WHERE thread_id = ?
            ''', (thread_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_thread(thread_id: int, **data) -> None:
        """Update allowed fields on a thread.

        Allowed fields: title, content, is_pinned, is_locked.

        Args:
            thread_id: The thread to update.
            **data: Field-value pairs to update.
        """
        allowed_fields = {
            'title', 'content', 'is_pinned', 'is_locked',
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(thread_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE comm_hub_threads SET ' + ', '.join(fields) + ' WHERE thread_id = ?',
                values)
            log_activity('update', 'comm_hub_thread', details={
                'thread_id': thread_id,
                'updated_fields': list(data.keys()),
            })

    @staticmethod
    def delete_thread(thread_id: int) -> None:
        """Delete a thread and all of its replies.

        Args:
            thread_id: The thread to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM comm_hub_replies WHERE thread_id = ?
            ''', (thread_id,))
            conn.execute('''
                DELETE FROM comm_hub_threads WHERE thread_id = ?
            ''', (thread_id,))
            log_activity('delete', 'comm_hub_thread', details={
                'thread_id': thread_id,
            })

    @staticmethod
    def increment_view_count(thread_id: int) -> None:
        """Increment the view count of a thread by one.

        Args:
            thread_id: The thread whose view count should be incremented.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE comm_hub_threads
                SET view_count = view_count + 1
                WHERE thread_id = ?
            ''', (thread_id,))

    # ==================== REPLY MANAGEMENT ====================

    @staticmethod
    def add_reply(thread_id: int, content: str, author_id: str,
                  parent_reply_id: int = None) -> int:
        """Add a reply to a thread.

        Also updates the thread's reply_count, last_reply_at, and
        last_reply_by fields.

        Args:
            thread_id: The thread this reply belongs to.
            content: Reply body content.
            author_id: User ID of the reply author.
            parent_reply_id: ID of the parent reply for nested replies
                (optional, None for top-level replies).

        Returns:
            The ID of the newly created reply.
        """
        with transaction() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute('''
                INSERT INTO comm_hub_replies (
                    thread_id, content, author_id, parent_reply_id,
                    is_solution, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?)
            ''', (
                thread_id, content, author_id, parent_reply_id,
                now, now,
            ))
            reply_id = cursor.lastrowid

            conn.execute('''
                UPDATE comm_hub_threads
                SET reply_count = reply_count + 1,
                    last_reply_at = ?,
                    last_reply_by = ?
                WHERE thread_id = ?
            ''', (now, author_id, thread_id))

            log_activity('create', 'comm_hub_reply', details={
                'reply_id': reply_id, 'thread_id': thread_id,
                'author_id': author_id,
            })
            return reply_id

    @staticmethod
    def get_replies(thread_id: int) -> List[Dict[str, Any]]:
        """Get all replies for a thread ordered chronologically.

        Args:
            thread_id: The thread to retrieve replies for.

        Returns:
            A list of reply dicts ordered by created_at ascending.
        """
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM comm_hub_replies
                WHERE thread_id = ?
                ORDER BY created_at ASC
            ''', (thread_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_reply(reply_id: int, content: str) -> None:
        """Update the content of a reply.

        Args:
            reply_id: The reply to update.
            content: The new reply content.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE comm_hub_replies
                SET content = ?, updated_at = ?
                WHERE reply_id = ?
            ''', (content, datetime.now().isoformat(), reply_id))
            log_activity('update', 'comm_hub_reply', details={
                'reply_id': reply_id,
            })

    @staticmethod
    def delete_reply(reply_id: int) -> None:
        """Delete a reply and decrement the parent thread's reply_count.

        Args:
            reply_id: The reply to delete.
        """
        with transaction() as conn:
            row = conn.execute('''
                SELECT thread_id FROM comm_hub_replies WHERE reply_id = ?
            ''', (reply_id,)).fetchone()

            conn.execute('''
                DELETE FROM comm_hub_replies WHERE reply_id = ?
            ''', (reply_id,))

            if row:
                conn.execute('''
                    UPDATE comm_hub_threads
                    SET reply_count = reply_count - 1
                    WHERE thread_id = ?
                ''', (row['thread_id'],))

            log_activity('delete', 'comm_hub_reply', details={
                'reply_id': reply_id,
            })

    @staticmethod
    def mark_solution(reply_id: int) -> None:
        """Mark a reply as the solution for its thread.

        Args:
            reply_id: The reply to mark as the solution.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE comm_hub_replies
                SET is_solution = 1
                WHERE reply_id = ?
            ''', (reply_id,))
            log_activity('update', 'comm_hub_reply', details={
                'reply_id': reply_id, 'action': 'mark_solution',
            })

    # ==================== POLL MANAGEMENT ====================

    @staticmethod
    def create_poll(forum_id: int, thread_id: int, title: str,
                    description: str, poll_type: str,
                    is_anonymous: bool, allow_comments: bool,
                    closes_at: str, created_by: str,
                    options: List[str]) -> int:
        """Create a poll with its options.

        Args:
            forum_id: The forum this poll belongs to.
            thread_id: The thread this poll is associated with.
            title: Poll title or question.
            description: Detailed description of the poll.
            poll_type: Type of poll (e.g. 'single_choice', 'multiple_choice').
            is_anonymous: Whether votes are anonymous.
            allow_comments: Whether voters can leave comments.
            closes_at: ISO format datetime when the poll closes.
            created_by: User ID of the poll creator.
            options: List of option text strings to create as poll options.

        Returns:
            The ID of the newly created poll.
        """
        with transaction() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute('''
                INSERT INTO comm_hub_polls (
                    forum_id, thread_id, title, description,
                    poll_type, is_anonymous, allow_comments,
                    closes_at, status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            ''', (
                forum_id, thread_id, title, description,
                poll_type, int(is_anonymous), int(allow_comments),
                closes_at, created_by, now, now,
            ))
            poll_id = cursor.lastrowid

            for option_text in options:
                conn.execute('''
                    INSERT INTO comm_hub_poll_options (
                        poll_id, option_text, vote_count, created_at
                    ) VALUES (?, ?, 0, ?)
                ''', (poll_id, option_text, now))

            log_activity('create', 'comm_hub_poll', details={
                'poll_id': poll_id, 'forum_id': forum_id,
                'thread_id': thread_id, 'title': title,
                'created_by': created_by,
                'option_count': len(options),
            })
            return poll_id

    @staticmethod
    def get_polls(forum_id: int = None,
                  status: str = None) -> List[Dict[str, Any]]:
        """Get polls with optional filters.

        Args:
            forum_id: Filter by forum.
            status: Filter by poll status (e.g. 'open', 'closed').

        Returns:
            A list of poll dicts.
        """
        with get_connection() as conn:
            query = 'SELECT * FROM comm_hub_polls WHERE 1=1'
            params: list = []

            if forum_id:
                query += ' AND forum_id = ?'
                params.append(forum_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_poll(poll_id: int) -> Optional[Dict[str, Any]]:
        """Get a single poll by ID, including its options.

        Args:
            poll_id: The poll's primary key.

        Returns:
            A dict of the poll row with an 'options' key containing
            a list of option dicts, or None if not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM comm_hub_polls WHERE poll_id = ?
            ''', (poll_id,)).fetchone()

            if not row:
                return None

            poll = dict(row)
            option_rows = conn.execute('''
                SELECT * FROM comm_hub_poll_options
                WHERE poll_id = ?
            ''', (poll_id,)).fetchall()
            poll['options'] = [dict(o) for o in option_rows]
            return poll

    @staticmethod
    def cast_poll_vote(poll_id: int, option_id: int, voter_id: str,
                       comment: str = None) -> int:
        """Cast a vote on a poll option.

        For single_choice polls, a voter may only vote once across all
        options for the poll.  If the voter has already voted on any
        option for this poll, a ValueError is raised.

        Args:
            poll_id: The poll being voted on.
            option_id: The specific option being voted for.
            voter_id: The user casting the vote.
            comment: Optional comment from the voter.

        Returns:
            The ID of the newly created vote record.

        Raises:
            ValueError: If the voter has already voted on this poll
                (for single_choice polls).
        """
        with transaction() as conn:
            # Get poll type
            poll_row = conn.execute('''
                SELECT poll_type FROM comm_hub_polls WHERE poll_id = ?
            ''', (poll_id,)).fetchone()

            if poll_row and poll_row['poll_type'] == 'single_choice':
                existing = conn.execute('''
                    SELECT vote_id FROM comm_hub_poll_votes
                    WHERE poll_id = ? AND voter_id = ?
                ''', (poll_id, voter_id)).fetchone()

                if existing:
                    raise ValueError(
                        f"Voter {voter_id} has already voted on poll {poll_id}"
                    )

            now = datetime.now().isoformat()
            cursor = conn.execute('''
                INSERT INTO comm_hub_poll_votes (
                    poll_id, option_id, voter_id, comment, voted_at
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                poll_id, option_id, voter_id, comment, now,
            ))
            vote_id = cursor.lastrowid

            conn.execute('''
                UPDATE comm_hub_poll_options
                SET vote_count = vote_count + 1
                WHERE option_id = ?
            ''', (option_id,))

            log_activity('create', 'comm_hub_poll_vote', details={
                'vote_id': vote_id, 'poll_id': poll_id,
                'option_id': option_id,
            })
            return vote_id

    @staticmethod
    def get_poll_results(poll_id: int) -> Dict[str, Any]:
        """Get poll information with options, vote counts, and total votes.

        Args:
            poll_id: The poll to retrieve results for.

        Returns:
            A dict containing poll info, an 'options' list with vote
            counts, and a 'total_votes' tally.

        Raises:
            ValueError: If the poll is not found.
        """
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM comm_hub_polls WHERE poll_id = ?
            ''', (poll_id,)).fetchone()

            if not row:
                raise ValueError(f"Poll {poll_id} not found")

            poll = dict(row)

            option_rows = conn.execute('''
                SELECT * FROM comm_hub_poll_options
                WHERE poll_id = ?
            ''', (poll_id,)).fetchall()

            options = [dict(o) for o in option_rows]
            total_votes = sum(o['vote_count'] for o in options)

            poll['options'] = options
            poll['total_votes'] = total_votes
            return poll

    @staticmethod
    def close_poll(poll_id: int) -> None:
        """Close a poll by setting its status to 'closed'.

        Args:
            poll_id: The poll to close.
        """
        with transaction() as conn:
            conn.execute('''
                UPDATE comm_hub_polls
                SET status = 'closed', updated_at = ?
                WHERE poll_id = ?
            ''', (datetime.now().isoformat(), poll_id))
            log_activity('update', 'comm_hub_poll', details={
                'poll_id': poll_id, 'action': 'closed',
            })

    # ==================== PINNED MESSAGES ====================

    @staticmethod
    def pin_message(message_type: str, message_id: int,
                    pinned_by: str, expires_at: str = None,
                    context: str = 'global') -> int:
        """Pin a message for visibility.

        Args:
            message_type: Type of the pinned item (e.g. 'thread', 'reply').
            message_id: ID of the item being pinned.
            pinned_by: User ID of the person pinning the message.
            expires_at: ISO format datetime when the pin expires (optional).
            context: Pinning context scope (default 'global').

        Returns:
            The ID of the newly created pin record.
        """
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO comm_hub_pinned_messages (
                    message_type, message_id, pinned_by,
                    expires_at, context, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                message_type, message_id, pinned_by,
                expires_at, context,
                datetime.now().isoformat(),
            ))
            pin_id = cursor.lastrowid
            log_activity('create', 'comm_hub_pinned_message', details={
                'pin_id': pin_id, 'message_type': message_type,
                'message_id': message_id, 'pinned_by': pinned_by,
            })
            return pin_id

    @staticmethod
    def unpin_message(pin_id: int) -> None:
        """Remove a pinned message.

        Args:
            pin_id: The pin record to delete.
        """
        with transaction() as conn:
            conn.execute('''
                DELETE FROM comm_hub_pinned_messages WHERE pin_id = ?
            ''', (pin_id,))
            log_activity('delete', 'comm_hub_pinned_message', details={
                'pin_id': pin_id,
            })

    @staticmethod
    def get_pinned_messages(context: str = 'global') -> List[Dict[str, Any]]:
        """Get active pinned messages for a given context, excluding expired.

        Args:
            context: The pinning context scope (default 'global').

        Returns:
            A list of pinned message dicts that have not expired.
        """
        with get_connection() as conn:
            now = datetime.now().isoformat()
            rows = conn.execute('''
                SELECT * FROM comm_hub_pinned_messages
                WHERE context = ?
                  AND (expires_at IS NULL OR expires_at > ?)
            ''', (context, now)).fetchall()
            return [dict(row) for row in rows]

    # ==================== SEARCH ====================

    @staticmethod
    def search_all(query: str) -> Dict[str, List[Dict[str, Any]]]:
        """Search across threads and replies.

        Performs a case-insensitive LIKE search on thread titles and
        content, and on reply content.

        Args:
            query: The search term to match against thread titles,
                thread content, and reply content.

        Returns:
            A dict with two keys:
            - 'threads': list of matching thread dicts
            - 'replies': list of matching reply dicts
        """
        with get_connection() as conn:
            like_pattern = f'%{query}%'

            thread_rows = conn.execute('''
                SELECT * FROM comm_hub_threads
                WHERE title LIKE ? OR content LIKE ?
            ''', (like_pattern, like_pattern)).fetchall()

            reply_rows = conn.execute('''
                SELECT * FROM comm_hub_replies
                WHERE content LIKE ?
            ''', (like_pattern,)).fetchall()

            return {
                'threads': [dict(row) for row in thread_rows],
                'replies': [dict(row) for row in reply_rows],
            }
