from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime


class MessagingMixin:
    """Mixin providing notification preferences, messaging, and notification API."""

    def manage_notifications(self):
        """Manage notification preferences"""
        if not self._check_permission('view_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            user_id = self.auth.current_user['id']

            print("\nNotification Preferences")
            print("=" * 50)

            cursor.execute('''
            SELECT notification_type, email_enabled, sms_enabled, in_app_enabled, advance_notice_days
            FROM notification_preferences
            WHERE user_id = ?
            ''', (user_id,))

            preferences = cursor.fetchall()

            if preferences:
                print("Current preferences:")
                for pref in preferences:
                    ntype, email, sms, app, days = pref
                    print(f"- {ntype}: Email: {'Y' if email else 'N'}, "
                          f"SMS: {'Y' if sms else 'N'}, App: {'Y' if app else 'N'}, "
                          f"Advance notice: {days} days")
            else:
                print("No preferences set (using defaults)")

            print("\nNotification Types:")
            print("1. Assignment due reminders")
            print("2. Grade released notifications")
            print("3. New assignment announcements")
            print("4. Extension request updates")
            print("5. Peer review assignments")

            ntype = input("\nSelect type to configure: ").strip()
            types = {
                '1': 'due_reminder',
                '2': 'grade_released',
                '3': 'new_assignment',
                '4': 'extension_update',
                '5': 'peer_review'
            }

            if ntype in types:
                self._configure_notification_type(cursor, user_id, types[ntype])

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error managing notifications: {e}")

    def _configure_notification_type(self, cursor, user_id, notification_type):
        """Configure specific notification type"""
        print(f"\nConfiguring {notification_type} notifications:")

        email = input("Enable email notifications? (y/n): ").lower() == 'y'
        sms = input("Enable SMS notifications? (y/n): ").lower() == 'y'
        app = input("Enable in-app notifications? (y/n): ").lower() == 'y'

        days = 1
        if notification_type == 'due_reminder':
            while True:
                try:
                    days = int(input("Days in advance for reminders (1-7): "))
                    if 1 <= days <= 7:
                        break
                    else:
                        print("Please enter 1-7 days.")
                except ValueError:
                    print("Please enter a valid number.")

        cursor.execute('''
        INSERT OR REPLACE INTO notification_preferences
        (user_id, notification_type, email_enabled, sms_enabled, in_app_enabled, advance_notice_days)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, notification_type, email, sms, app, days))

        print("Preferences saved!")

    def send_message(self):
        """Send message to students or instructors"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\nSend Message")
            print("=" * 30)

            print("1. Send to all students in a module")
            print("2. Send to specific student")
            print("3. Send to all instructors")

            choice = input("Choose option: ").strip()

            if choice == '1':
                self._send_module_message(cursor)
            elif choice == '2':
                self._send_individual_message(cursor)
            elif choice == '3':
                self._send_instructor_broadcast(cursor)
            else:
                print("Invalid choice.")

            conn.close()

        except Exception as e:
            print(f"Error sending message: {e}")

    def view_messages(self):
        """View received messages"""
        if not self._check_permission('view_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            user_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT m.id, u.username, m.subject, m.sent_at, m.is_read
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.recipient_id = ?
            ORDER BY m.sent_at DESC
            LIMIT 20
            ''', (user_id,))

            messages = cursor.fetchall()

            if not messages:
                print("No messages found.")
                conn.close()
                return

            print("\nYour Messages:")
            print("=" * 80)
            for i, (mid, sender, subject, sent_at, is_read) in enumerate(messages, 1):
                status = " " if is_read else "*"
                print(f"{i:2d}. {status} From: {sender:<15} Subject: {subject:<30} {sent_at}")

            choice = input("\nSelect message number to read (or Enter to return): ").strip()
            if choice:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(messages):
                        self._read_message(cursor, messages[index][0])
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")

            conn.close()

        except Exception as e:
            print(f"Error viewing messages: {e}")

    def _read_message(self, cursor, message_id):
        """Read a specific message"""
        cursor.execute('''
        SELECT m.*, u.username, a.title
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        LEFT JOIN assignments a ON m.assignment_id = a.id
        WHERE m.id = ?
        ''', (message_id,))

        message = cursor.fetchone()
        if not message:
            print("Message not found.")
            return

        print(f"\nMessage Details:")
        print("=" * 50)
        print(f"From: {message[7]}")
        print(f"Subject: {message[3]}")
        print(f"Sent: {message[6]}")
        if message[8]:
            print(f"Related Assignment: {message[8]}")
        print(f"\nMessage:")
        print("-" * 50)
        print(message[4])
        print("-" * 50)

        cursor.execute('UPDATE messages SET is_read = 1 WHERE id = ?', (message_id,))
        cursor.connection.commit()

        reply = input("\nReply to this message? (y/n): ").lower()
        if reply == 'y':
            self._send_reply(cursor, message)

    def _send_reply(self, cursor, original_message):
        """Send reply to a message"""
        subject = f"Re: {original_message[3]}"
        message_text = input("Your reply: ").strip()

        if message_text:
            cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, subject, message, assignment_id, sent_at, reply_to)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'],
                original_message[1],
                subject,
                message_text,
                original_message[5],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                original_message[0]
            ))

            cursor.connection.commit()
            print("Reply sent!")

    def _send_module_message(self, cursor):
        """Send message to all students in a module"""
        cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
        modules = cursor.fetchall()

        if not modules:
            print("No modules found.")
            return

        print("Available modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        choice = input("Select module number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(modules):
                module_code = modules[index][0]

                subject = input("Message subject: ").strip()
                message = input("Message text: ").strip()

                if not subject or not message:
                    print("Subject and message cannot be empty.")
                    return

                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))

                student_users = cursor.fetchall()

                for (user_id,) in student_users:
                    cursor.execute('''
                    INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (self.auth.current_user['id'], user_id, subject, message,
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                cursor.connection.commit()
                print(f"Message sent to {len(student_users)} students in {module_code}.")

        except (ValueError, IndexError):
            print("Invalid selection.")

    def _send_individual_message(self, cursor):
        """Send message to a specific student"""
        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return

        cursor.execute('SELECT u.id, s.first_name, s.last_name FROM users u JOIN students s ON u.student_id = s.student_id WHERE s.student_id = ?', (student_id,))
        result = cursor.fetchone()

        if not result:
            print("Student not found.")
            return

        user_id, fname, lname = result
        print(f"Sending message to: {fname} {lname} ({student_id})")

        subject = input("Subject: ").strip()
        message = input("Message: ").strip()

        if not subject or not message:
            print("Subject and message cannot be empty.")
            return

        cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (self.auth.current_user['id'], user_id, subject, message,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        cursor.connection.commit()
        print("Message sent successfully!")

    def _send_instructor_broadcast(self, cursor):
        """Send message to all instructors"""
        subject = input("Subject: ").strip()
        message = input("Message: ").strip()

        if not subject or not message:
            print("Subject and message cannot be empty.")
            return

        cursor.execute("SELECT id FROM users WHERE role IN ('instructor', 'admin')")
        instructors = cursor.fetchall()

        for (user_id,) in instructors:
            cursor.execute('''
            INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (self.auth.current_user['id'], user_id, subject, message,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        cursor.connection.commit()
        print(f"Broadcast sent to {len(instructors)} instructors.")

    # API methods

    def get_user_notifications(self, user_id=None, unread_only=False):
        """Get notifications for a user"""
        try:
            if not user_id:
                user_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if unread_only:
                cursor.execute('''
                    SELECT * FROM notifications
                    WHERE user_id = ? AND is_read = 0
                    ORDER BY created_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))

            notifications = cursor.fetchall()
            conn.close()
            return notifications

        except Exception as e:
            print(f"Error retrieving notifications: {e}")
            return []

    def mark_notification_read(self, notification_id):
        """Mark a notification as read"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE notifications
                SET is_read = 1, read_at = ?
                WHERE id = ?
            ''', (timestamp, notification_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return False

    def delete_notification(self, notification_id):
        """Delete a notification"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM notifications WHERE id = ?', (notification_id,))

            conn.commit()
            self._log_action('delete', 'notifications', notification_id)
            conn.close()
            return True

        except Exception as e:
            print(f"Error deleting notification: {e}")
            return False

    def get_user_messages(self, user_id=None, unread_only=False):
        """Get messages for a user"""
        try:
            if not user_id:
                user_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if unread_only:
                cursor.execute('''
                    SELECT * FROM messages
                    WHERE recipient_id = ? AND is_read = 0
                    ORDER BY sent_at DESC
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT * FROM messages
                    WHERE recipient_id = ? OR sender_id = ?
                    ORDER BY sent_at DESC
                ''', (user_id, user_id))

            messages = cursor.fetchall()
            conn.close()
            return messages

        except Exception as e:
            print(f"Error retrieving messages: {e}")
            return []

    def reply_to_message(self, original_message_id, reply_text):
        """Reply to a message"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT sender_id FROM messages WHERE id = ?', (original_message_id,))
            result = cursor.fetchone()

            if not result:
                print("Original message not found")
                return False

            recipient_id = result[0]
            sender_id = self._get_student_id()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO messages (sender_id, recipient_id, subject, message, sent_at, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (sender_id, recipient_id, f"Re: Message #{original_message_id}", reply_text, timestamp))

            conn.commit()
            self._log_action('create', 'messages', cursor.lastrowid)
            conn.close()

            print("Reply sent successfully!")
            return True

        except Exception as e:
            print(f"Error replying to message: {e}")
            return False

    def configure_notification_preferences(self, user_id, preferences):
        """Configure notification preferences for a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    user_id INTEGER PRIMARY KEY,
                    email_notifications INTEGER DEFAULT 1,
                    assignment_notifications INTEGER DEFAULT 1,
                    grade_notifications INTEGER DEFAULT 1,
                    message_notifications INTEGER DEFAULT 1,
                    extension_notifications INTEGER DEFAULT 1,
                    peer_review_notifications INTEGER DEFAULT 1
                )
            ''')

            cursor.execute('''
                INSERT OR REPLACE INTO notification_preferences (
                    user_id, email_notifications, assignment_notifications,
                    grade_notifications, message_notifications, extension_notifications,
                    peer_review_notifications
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id,
                  preferences.get('email', 1),
                  preferences.get('assignments', 1),
                  preferences.get('grades', 1),
                  preferences.get('messages', 1),
                  preferences.get('extensions', 1),
                  preferences.get('peer_review', 1)))

            conn.commit()
            self._log_action('update', 'notification_preferences', user_id, preferences)
            conn.close()

            print("Notification preferences updated successfully!")
            return True

        except Exception as e:
            print(f"Error configuring notification preferences: {e}")
            return False
