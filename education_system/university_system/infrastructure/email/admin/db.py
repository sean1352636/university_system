"""Database initialization mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.university_system.infrastructure.email.admin._imports import (
    execute_db_operation,
    handle_exception,
    log_event,
    safe_alter_table_add_column,
    SQLIdentifierError,
)


class _DbMixin:
    """Mixin providing database table initialization."""

    @handle_exception
    def _init_db(self):
        """Initialize database tables required for the communication system"""

        def _create_tables(cursor):
            # Messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                attachment_path TEXT,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_deleted_by_sender INTEGER DEFAULT 0,
                is_deleted_by_recipient INTEGER DEFAULT 0,
                sent_at TEXT NOT NULL,
                read_at TEXT,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
            ''')

            # Group Messages table (for course-wide or department-wide messages)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                group_type TEXT NOT NULL,
                group_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                attachment_path TEXT,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users (id)
            )
            ''')

            # Group Message Recipients table (tracks who has read which group messages)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_message_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0,
                read_at TEXT,
                FOREIGN KEY (message_id) REFERENCES group_messages (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
            ''')

            # Announcements table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                is_urgent INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                start_date TEXT NOT NULL,
                end_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (creator_id) REFERENCES users (id)
            )
            ''')

            # Announcement Viewers table (tracks who has viewed announcements)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcement_viewers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id INTEGER NOT NULL,
                viewer_id INTEGER NOT NULL,
                viewed_at TEXT NOT NULL,
                FOREIGN KEY (announcement_id) REFERENCES announcements (id),
                FOREIGN KEY (viewer_id) REFERENCES users (id)
            )
            ''')

            # Chat Rooms table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                room_type TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                max_members INTEGER DEFAULT 50,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Migrate existing chat_rooms table to add missing columns
            cursor.execute("PRAGMA table_info(chat_rooms)")
            chat_room_columns = {row[1] for row in cursor.fetchall()}

            chat_room_column_definitions = [
                ('max_members', 'INTEGER DEFAULT 50'),
                ('is_active', 'INTEGER DEFAULT 1'),
                ('description', 'TEXT')
            ]

            # Use centralized SQL safety validation for column definitions
            for column_name, definition in chat_room_column_definitions:
                if column_name not in chat_room_columns:
                    try:
                        safe_alter_table_add_column("chat_rooms", column_name, definition, cursor.connection)
                        log_event('info', f"Added missing column {column_name} to chat_rooms")
                    except SQLIdentifierError as e:
                        log_event('warning', f"Invalid column definition for {column_name}: {e}")
                        continue
                    except Exception as e:
                        log_event('warning', f"Could not add column {column_name} to chat_rooms: {e}")

            # Chat Room Members table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_room_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Chat Messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                FOREIGN KEY (sender_id) REFERENCES users (id)
            )
            ''')

            # Notification Preferences table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notification_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email_notifications INTEGER DEFAULT 1,
                message_notifications INTEGER DEFAULT 1,
                announcement_notifications INTEGER DEFAULT 1,
                chat_notifications INTEGER DEFAULT 1,
                daily_digest INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Migrate existing notification_preferences table if columns are missing
            try:
                # First check if this is the new schema from notifications service
                cursor.execute("PRAGMA table_info(notification_preferences)")
                columns = {row[1] for row in cursor.fetchall()}

                # If it has preference_id, it's the new schema - skip migration
                if 'preference_id' in columns:
                    log_event('info', 'notification_preferences already migrated to new schema - skipping')
                else:
                    # Check if columns exist by trying to select them
                    try:
                        cursor.execute('SELECT email_notifications FROM notification_preferences LIMIT 1')
                    except Exception:
                        # Columns don't exist, need to migrate
                        try:
                            # Get existing data
                            cursor.execute('SELECT id, user_id FROM notification_preferences')
                            existing_data = cursor.fetchall()

                            # Drop and recreate table
                            cursor.execute('DROP TABLE IF EXISTS notification_preferences_old')
                            cursor.execute('ALTER TABLE notification_preferences RENAME TO notification_preferences_old')

                            # Create new table with correct schema
                            cursor.execute('''
                            CREATE TABLE notification_preferences (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER NOT NULL,
                                email_notifications INTEGER DEFAULT 1,
                                message_notifications INTEGER DEFAULT 1,
                                announcement_notifications INTEGER DEFAULT 1,
                                chat_notifications INTEGER DEFAULT 1,
                                daily_digest INTEGER DEFAULT 0,
                                FOREIGN KEY (user_id) REFERENCES users (id)
                            )
                            ''')

                            # Migrate existing data with default values
                            for row in existing_data:
                                cursor.execute('''
                                INSERT INTO notification_preferences (user_id, email_notifications, message_notifications,
                                                                     announcement_notifications, chat_notifications, daily_digest)
                                VALUES (?, 1, 1, 1, 1, 0)
                                ''', (row[1],))

                            # Drop old table
                            cursor.execute('DROP TABLE notification_preferences_old')
                        except Exception as e:
                            log_event('warning', f"Could not migrate notification_preferences table: {e}")
            except Exception as e:
                log_event('warning', f"Could not check notification_preferences schema: {e}")

            # Communication Log table (for audit purposes)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS communication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_details TEXT,
                performed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            return True

        try:
            result = execute_db_operation(_create_tables)
            if result:
                log_event('info', "Communication system database tables initialized successfully!")
            return result
        except Exception as e:
            log_event('error', f"Error initializing communication database: {e}")
            return False
