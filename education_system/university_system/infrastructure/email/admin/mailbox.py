"""Mailbox retrieval mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    execute_db_operation,
    handle_exception,
    log_event,
    logger,
)


class _MailboxMixin:
    """Mixin providing inbox, sent, and archived message retrieval."""

    @handle_exception
    def get_inbox(self, include_archived=False, page=1, limit=10):
        """Get the current user's inbox messages - FIXED VERSION"""
        # Check authentication
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view inbox")
            return {'messages': [], 'unread_count': 0, 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_inbox(cursor):
            # Debug: First check if user has any messages at all
            cursor.execute('''
            SELECT COUNT(*) FROM messages WHERE recipient_id = ?
            ''', (user_id,))
            total_messages_for_user = cursor.fetchone()[0]

            logger.debug("User %s has %d total messages", user_id, total_messages_for_user)

            # Debug: Check messages with simplified filters (no deleted/archived columns)
            cursor.execute('''
            SELECT COUNT(*) FROM messages
            WHERE recipient_id = ?
            ''', (user_id,))
            non_deleted_count = cursor.fetchone()[0]

            logger.debug("Found %d non-deleted messages for user", non_deleted_count)

            # Query for inbox messages - excluding archived messages unless requested
            def _archived_filter(alias: str) -> str:
                return "" if include_archived else f" AND ({alias}.is_archived IS NULL OR {alias}.is_archived = 0)"

            def _active_filter(alias: str) -> str:
                return f" AND ({alias}.is_deleted_by_recipient IS NULL OR {alias}.is_deleted_by_recipient = 0)"

            archived_condition = _archived_filter("m") + _active_filter("m")

            cursor.execute(f'''
            SELECT m.id, m.sender_id, u.username as sender_username, m.subject, m.content,
                   COALESCE(m.is_read, 0) as is_read,
                   COALESCE(m.is_archived, 0) as is_archived,
                   COALESCE(m.is_deleted_by_recipient, 0) as is_deleted,
                   m.sent_at, m.assignment_id, m.reply_to
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ? {archived_condition}
            ORDER BY m.sent_at DESC
            LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))

            messages = []
            rows = cursor.fetchall()
            logger.debug("Inbox query returned %d messages", len(rows))

            for row in rows:
                messages.append({
                    'id': row[0],
                    'sender_id': row[1],
                    'sender': row[2],
                    'subject': row[3],
                    'content': row[4],  # This is actually 'message' column
                    'is_read': bool(row[5]),
                    'is_archived': bool(row[6]),  # Now available
                    'is_deleted': bool(row[7]),
                    'sent_at': row[8],
                    'read_at': None,  # Not in current schema
                    'assignment_id': row[9],
                    'reply_to': row[10]
                })

            # Get count of unread messages - excluding archived unless requested
            unread_archived_condition = _archived_filter("m") + _active_filter("m")

            cursor.execute(f'''
            SELECT COUNT(*) FROM messages m
            WHERE m.recipient_id = ?
              AND (m.is_read IS NULL OR m.is_read = 0)
              {unread_archived_condition}
            ''', (user_id,))

            unread_count = cursor.fetchone()[0]

            # Get total count of messages - excluding archived unless requested
            cursor.execute(f'''
            SELECT COUNT(*) FROM messages m
            WHERE m.recipient_id = ?
              {archived_condition}
            ''', (user_id,))

            total_count = cursor.fetchone()[0]

            logger.debug("Inbox stats - total: %d, unread: %d", total_count, unread_count)

            return {
                'messages': messages,
                'unread_count': unread_count,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_inbox)
        except Exception as e:
            log_event('error', f"Error getting inbox: {e}")
            return {'messages': [], 'unread_count': 0, 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def get_sent_messages(self, page=1, limit=10):
        """Get the current user's sent messages"""
        # Check authentication
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view sent messages")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_sent(cursor):
            # Query for sent messages - simplified for actual schema
            cursor.execute('''
            SELECT m.id, m.recipient_id, u.username as recipient_username, m.subject, m.content,
                   m.is_read, m.sent_at, m.assignment_id, m.reply_to
            FROM messages m
            JOIN users u ON m.recipient_id = u.id
            WHERE m.sender_id = ?
            ORDER BY m.sent_at DESC
            LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))

            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'recipient_id': row[1],
                    'recipient': row[2],
                    'subject': row[3],
                    'content': row[4],  # This is actually 'message' column
                    'is_read': bool(row[5]),
                    'sent_at': row[6],
                    'read_at': None,  # Default since column doesn't exist
                    'assignment_id': row[7],
                    'reply_to': row[8],
                    'sender': self.auth.current_user['username'] if self.auth and self.auth.current_user else 'Unknown'
                })

            # Get total count of sent messages - simplified for actual schema
            cursor.execute('''
            SELECT COUNT(*) FROM messages
            WHERE sender_id = ?
            ''', (user_id,))

            total_count = cursor.fetchone()[0]

            return {
                'messages': messages,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_sent)
        except Exception as e:
            log_event('error', f"Error getting sent messages: {e}")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def get_archived_messages(self, page=1, limit=10):
        """Get the current user's archived messages"""
        # Check authentication
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view archived messages")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        offset = (page - 1) * limit

        def _get_archived(cursor):
            # Query for archived messages only
            cursor.execute('''
            SELECT m.id, m.sender_id, u.username as sender_username, m.subject, m.content,
                   COALESCE(m.is_read, 0) as is_read,
                   COALESCE(m.is_archived, 0) as is_archived,
                   m.sent_at, m.assignment_id, m.reply_to
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ? AND m.is_archived = 1
            ORDER BY m.sent_at DESC
            LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))

            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'sender_id': row[1],
                    'sender': row[2],
                    'subject': row[3],
                    'content': row[4],  # This is actually 'message' column
                    'is_read': bool(row[5]),
                    'is_archived': bool(row[6]),
                    'sent_at': row[7],
                    'read_at': None,  # Not in current schema
                    'assignment_id': row[8],
                    'reply_to': row[9]
                })

            # Get total count of archived messages
            cursor.execute('''
            SELECT COUNT(*) FROM messages
            WHERE recipient_id = ? AND is_archived = 1
            ''', (user_id,))

            total_count = cursor.fetchone()[0]

            return {
                'messages': messages,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_archived)
        except Exception as e:
            log_event('error', f"Error getting archived messages: {e}")
            return {'messages': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

    @handle_exception
    def get_message_status_info(self, message_id):
        """Get detailed status information about a message - SIMPLIFIED"""
        def _get_status(cursor):
            cursor.execute('''
            SELECT id, sender_id, recipient_id, subject, is_read, sent_at
            FROM messages WHERE id = ?
            ''', (message_id,))

            row = cursor.fetchone()

            if not row:
                return None

            return {
                'id': row[0],
                'sender_id': row[1],
                'recipient_id': row[2],
                'subject': row[3],
                'is_read': bool(row[4]),
                'is_archived': False,  # Not supported in current schema
                'is_deleted_by_sender': False,  # Not supported in current schema
                'is_deleted_by_recipient': False,  # Not supported in current schema
                'sent_at': row[5],
                'deletion_status': 'not_deleted'  # Simplified
            }

        try:
            return execute_db_operation(_get_status)
        except Exception as e:
            log_event('error', f"Error getting message status: {e}")
            return None

    @handle_exception
    def debug_check_messages(self, user_id=None):
        """Debug method to check messages for a user"""
        if not user_id and self.auth and self.auth.current_user:
            user_id = self.auth.current_user['id']

        if not user_id:
            logger.debug("No user ID provided for debugging")
            return

        def _check_messages(cursor):
            logger.debug("Checking messages for user ID %s", user_id)

            # Check sent messages
            cursor.execute('''
            SELECT m.id, m.recipient_id, u.username, m.subject, m.sent_at
            FROM messages m
            JOIN users u ON m.recipient_id = u.id
            WHERE m.sender_id = ?
            ORDER BY m.sent_at DESC
            LIMIT 10
            ''', (user_id,))

            sent_messages = cursor.fetchall()
            logger.info(f"Recent sent messages ({len(sent_messages)}):")
            for msg in sent_messages:
                logger.info(f"  - ID {msg[0]} to {msg[2]} ({msg[1]}): {msg[3]} at {msg[4]}")

            # Check received messages
            cursor.execute('''
            SELECT m.id, m.sender_id, u.username, m.subject, m.sent_at, m.is_read
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ?
            ORDER BY m.sent_at DESC
            LIMIT 10
            ''', (user_id,))

            received_messages = cursor.fetchall()
            logger.info(f"Recent received messages ({len(received_messages)}):")
            for msg in received_messages:
                status = "READ" if msg[5] else "UNREAD"
                logger.info(f"  - ID {msg[0]} from {msg[2]} ({msg[1]}): {msg[3]} at {msg[4]} [{status}]")

            return True

        try:
            execute_db_operation(_check_messages)
        except Exception as e:
            logger.error(f"Error checking messages: {e}")
