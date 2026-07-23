"""Message sending, reading, and status management mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
    datetime,
    execute_db_operation,
    handle_exception,
    log_event,
    logger,
    queue_email,
    render_template,
    send_email_as_user,
)


class _MessagingMixin:
    """Mixin providing message CRUD operations."""

    def send_message_with_email_notification(dashboard, recipient_id, subject, content, send_email_copy=False):
        """Enhanced message sending that can also send email copy with proper sender"""

        # Send the regular message first
        message_id = dashboard.send_message(recipient_id, subject, content)

        if message_id and send_email_copy:
            # Get recipient email
            def _get_recipient_email(cursor):
                cursor.execute("SELECT email FROM users WHERE id = ?", (recipient_id,))
                result = cursor.fetchone()
                return result[0] if result else None

            try:
                recipient_email = execute_db_operation(_get_recipient_email)
                if recipient_email:
                    # Send email copy with current user as sender
                    email_subject, email_body = render_template("new_message_notification", {
                        "subject": subject,
                        "sender_name": dashboard.auth.current_user['username'],
                        "content": content
                    })

                    # Use the current authenticated user as sender context
                    send_email_as_user(recipient_email, email_subject, email_body, dashboard.auth.current_user['id'])

            except Exception as e:
                log_event('error', f"Error sending email copy: {e}")

        return message_id

    @handle_exception
    def send_message_with_debug(self, recipient_id, subject, content, attachment_path=None):
        """Send a message with detailed debugging information"""
        logger.debug("Attempting to send message to user ID %s", recipient_id)
        logger.debug("Subject: %s", subject)
        logger.debug("Current user: %s (ID: %s)", self.auth.current_user['username'], self.auth.current_user['id'])

        result = self.send_message(recipient_id, subject, content, attachment_path)

        if result:
            logger.debug("Message sent successfully with ID: %s", result)
        else:
            logger.error("Failed to send message")

        return result

    @handle_exception
    def send_message(self, recipient_id, subject, content, attachment_path=None):
        """Send a message to another user with enhanced logging"""
        # Check authentication and permissions
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to send messages")
            return False

        # Validate inputs
        if not recipient_id or not subject or not content:
            log_event('error', "Recipient, subject, and content are required")
            return False

        def _send_message_op(cursor):
            # DM block check: refuse if the recipient has blocked the sender.
            sender_id = self.auth.current_user['id']
            cursor.execute(
                'SELECT 1 FROM dm_blocks WHERE user_id = ? AND blocked_user_id = ?',
                (recipient_id, sender_id),
            )
            if cursor.fetchone():
                log_event('error', f"DM blocked: recipient {recipient_id} has blocked sender")
                return False

            # Validate recipient exists (check legacy users table, fall back to shared auth)
            cursor.execute('SELECT id, email, username FROM users WHERE id = ?', (recipient_id,))
            recipient_data = cursor.fetchone()
            if recipient_data:
                recipient_email = recipient_data[1]
                recipient_username = recipient_data[2]
            else:
                # Recipient may only exist in shared auth DB
                recipient_email = None
                recipient_username = f"User {recipient_id}"

            # Create the message
            sender_id = self.auth.current_user['id']
            sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, subject, content, sent_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (sender_id, recipient_id, subject, content, sent_at))

            message_id = cursor.lastrowid

            # Enhanced logging
            log_event('info', f"Message sent from {self.auth.current_user['username']} to {recipient_username}: {subject[:50]}...")
            should_notify = False
            notification_subject = "New Message Notification"
            notification_body = (
                f"You have received a new message from {self.auth.current_user['username']}.\n\n"
                f"Subject: {subject}\n\nLog in to view the message."
            )

            try:
                # Email opt-in lives on user_preferences.email_notifications.
                # Per-message-type toggles live inside preferences_json (managed by the
                # email GUI's Notification Preferences dialog) and aren't reliably
                # populated for every user, so we treat the top-level email flag as
                # the source of truth. Default to 'send' when no row exists.
                cursor.execute('''
                SELECT email_notifications
                FROM user_preferences
                WHERE user_id = ?
                ''', (str(recipient_id),))

                prefs = cursor.fetchone()
                email_notifications = prefs[0] if prefs and prefs[0] is not None else 1
                should_notify = bool(email_notifications and recipient_email)
            except Exception as notif_error:
                log_event('warning', f"Error checking notification preferences: {notif_error}")

            try:
                cursor.connection.commit()
            except Exception as commit_error:
                log_event('warning', f"Failed to commit message send transaction: {commit_error}")

            return {
                'message_id': message_id,
                'sender_id': sender_id,
                'recipient_username': recipient_username,
                'recipient_email': recipient_email,
                'should_notify': should_notify,
                'notification_subject': notification_subject,
                'notification_body': notification_body,
            }

        try:
            result = execute_db_operation(_send_message_op)
            if not result:
                log_event('error', "Failed to send message")
                return False

            message_id = result['message_id']
            log_event('info', f"Message sent successfully! ID: {message_id}")

            # Log the action for auditing outside of the DB write context
            try:
                self._log_communication_action(
                    result['sender_id'],
                    "send_message",
                    f"Message sent to user ID {recipient_id}"
                )
            except Exception as log_error:
                log_event('warning', f"Failed to log communication action: {log_error}")

            # Send email notification only after the message transaction completes
            if result['should_notify']:
                try:
                    queue_email(
                        result['recipient_email'],
                        result['notification_subject'],
                        result['notification_body']
                    )
                    log_event('info', f"Email notification sent to {result['recipient_username']}")
                except Exception as email_error:
                    log_event('warning', f"Failed to send email notification: {email_error}")

            return message_id
        except Exception as e:
            log_event('error', f"Error sending message: {e}")
            return False

    @handle_exception
    def read_message(self, message_id):
        """Mark a message as read and return its details - FIXED VERSION"""
        # Check authentication
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to read messages")
            return None

        user_id = self.auth.current_user['id']

        def _read_message_operation(cursor):
            """Single transaction for reading message and logging"""
            # Get the message and check if user is authorized to read it - FIXED for actual schema
            cursor.execute('''
            SELECT m.id, m.sender_id, COALESCE(s.username, 'User ' || m.sender_id) as sender_username,
                   m.recipient_id,
                   COALESCE(r.username, 'User ' || m.recipient_id) as recipient_username,
                   m.subject, m.content,
                   m.is_read, m.sent_at, m.assignment_id, m.reply_to
            FROM messages m
            LEFT JOIN users s ON m.sender_id = s.id
            LEFT JOIN users r ON m.recipient_id = r.id
            WHERE m.id = ? AND (m.sender_id = ? OR m.recipient_id = ?)
            ''', (message_id, user_id, user_id))

            row = cursor.fetchone()

            if not row:
                log_event('error', "Message not found or permission denied")
                return None

            message = {
                'id': row[0],
                'sender_id': row[1],
                'sender': row[2],
                'recipient_id': row[3],
                'recipient': row[4],
                'subject': row[5],
                'content': row[6],  # This is actually 'message' column
                'attachment_path': None,  # Not in current schema
                'is_read': bool(row[7]),
                'sent_at': row[8],
                'read_at': None,  # Not in current schema
                'assignment_id': row[9],
                'reply_to': row[10]
            }

            # If user is the recipient and message is not read, mark it as read
            if user_id == row[3] and not row[7]:
                cursor.execute('''
                UPDATE messages SET is_read = 1 WHERE id = ?
                ''', (message_id,))

                message['is_read'] = True

                # Log the action (simplified - just to event log)
                log_event('info', f"Message {message_id} marked as read by user {user_id}")

            if cursor.connection:
                cursor.connection.commit()

            return message

        # Execute everything in a single transaction
        try:
            return execute_db_operation(_read_message_operation)
        except Exception as e:
            log_event('error', f"Error reading message {message_id}: {e}")
            return None

    @handle_exception
    def update_message_status(self, message_id, action):
        """Update a message's status - SIMPLIFIED for existing schema"""
        # Check authentication
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to update message status")
            return False

        user_id = self.auth.current_user['id']

        def _update_status(cursor):
            # Check if the message exists and user is authorized
            cursor.execute('''
            SELECT sender_id, recipient_id
            FROM messages WHERE id = ?
            ''', (message_id,))

            row = cursor.fetchone()

            if not row:
                log_event('error', "Message not found")
                return False

            sender_id, recipient_id = row

            if user_id not in (sender_id, recipient_id):
                log_event('error', "Permission denied to update message")
                return False

            # Perform the requested action
            if action == 'delete':
                if user_id == recipient_id:
                    cursor.execute('''
                    UPDATE messages SET is_deleted_by_recipient = 1 WHERE id = ?
                    ''', (message_id,))
                    action_desc = "marked as deleted by recipient"
                elif user_id == sender_id:
                    cursor.execute('''
                    UPDATE messages SET is_deleted_by_sender = 1 WHERE id = ?
                    ''', (message_id,))
                    action_desc = "marked as deleted by sender"
                else:
                    log_event('error', "User not permitted to delete this message")
                    return False
            elif action == 'mark_read' and user_id == recipient_id:
                cursor.execute('''
                UPDATE messages SET is_read = 1 WHERE id = ?
                ''', (message_id,))
                action_desc = "marked as read"
            elif action == 'mark_unread' and user_id == recipient_id:
                cursor.execute('''
                UPDATE messages SET is_read = 0 WHERE id = ?
                ''', (message_id,))
                action_desc = "marked as unread"
            elif action == 'archive' and user_id == recipient_id:
                cursor.execute('''
                UPDATE messages SET is_archived = 1 WHERE id = ?
                ''', (message_id,))
                action_desc = "archived"
            elif action == 'unarchive' and user_id == recipient_id:
                cursor.execute('''
                UPDATE messages SET is_archived = 0 WHERE id = ?
                ''', (message_id,))
                action_desc = "unarchived"
            else:
                log_event('error', f"Invalid action: {action} or user not authorized")
                return False

            # Log the action for auditing
            if cursor.connection:
                cursor.connection.commit()

            self._log_communication_action(user_id, f"{action}_message", f"Message ID {message_id} {action_desc}", cursor=cursor)

            return True

        try:
            result = execute_db_operation(_update_status)
            if result:
                log_event('info', f"Message successfully {action}")
            return result
        except Exception as e:
            log_event('error', f"Error updating message status: {e}")
            return False

    @handle_exception
    def force_delete_message(self, message_id):
        """Force delete a message immediately from database (admin function)"""
        # Check authentication and admin permissions
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to force delete messages")
            return False

        # Only allow admins to force delete
        if self.auth.current_user['role'] != 'admin':
            log_event('error', "Only administrators can force delete messages")
            return False

        user_id = self.auth.current_user['id']

        def _force_delete(cursor):
            # Check if message exists
            cursor.execute('SELECT sender_id, recipient_id FROM messages WHERE id = ?', (message_id,))
            row = cursor.fetchone()

            if not row:
                log_event('error', f"Message {message_id} not found")
                return False

            sender_id, recipient_id = row

            # Remove reply references so the original delete does not trip FK constraints
            cursor.execute('UPDATE messages SET reply_to = NULL WHERE reply_to = ?', (message_id,))

            # Delete the message
            cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))
            # Commit immediately so downstream logging does not deadlock on the DB lock
            if cursor.connection:
                cursor.connection.commit()

            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                user_id,
                "force_delete_message",
                f"Admin force deleted message ID {message_id} (sender: {sender_id}, recipient: {recipient_id})",
                cursor=cursor
            )

            return True

        try:
            result = execute_db_operation(_force_delete)
            if result:
                log_event('info', f"Message {message_id} force deleted by admin")
            return result
        except Exception as e:
            log_event('error', f"Error force deleting message: {e}")
            return False

    @handle_exception
    def cleanup_deleted_messages(self):
        """Clean up messages marked as deleted by both parties (maintenance function)"""
        # Check authentication and admin permissions
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to clean up messages")
            return False

        # Only allow admins to run cleanup
        if self.auth.current_user['role'] != 'admin':
            log_event('error', "Only administrators can run message cleanup")
            return False

        def _cleanup_messages(cursor):
            # Find messages deleted by both parties
            cursor.execute('''
            SELECT id, sender_id, recipient_id
            FROM messages
            WHERE is_deleted_by_sender = 1 AND is_deleted_by_recipient = 1
            ''')

            messages_to_delete = cursor.fetchall()

            if not messages_to_delete:
                return 0

            # Delete them permanently
            message_ids = [msg[0] for msg in messages_to_delete]
            placeholders = ','.join(['?' for _ in message_ids])

            cursor.execute('DELETE FROM messages WHERE id IN (' + placeholders + ')', message_ids)

            deleted_count = cursor.rowcount
            if cursor.connection:
                cursor.connection.commit()

            # Log the cleanup (pass cursor to avoid nested transactions)
            self._log_communication_action(
                self.auth.current_user['id'],
                "cleanup_deleted_messages",
                f"Cleaned up {deleted_count} messages deleted by both parties",
                cursor=cursor
            )

            return deleted_count

        try:
            result = execute_db_operation(_cleanup_messages)
            if result:
                log_event('info', f"Cleaned up {result} deleted messages")
            return result
        except Exception as e:
            log_event('error', f"Error cleaning up deleted messages: {e}")
            return 0
