"""Database initialization mixin for CommunicationDashboard."""

from __future__ import annotations

from education_system.post_18.university_system.infrastructure.email.admin._imports import (
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
                ('description', 'TEXT'),
                ('archived_at', 'TEXT'),
                ('archived_by', 'INTEGER'),
                ('category', 'TEXT'),
                ('icon', 'TEXT'),
                ('colour', 'TEXT'),
                ('linked_course_code', 'TEXT'),
                ('linked_assignment_group_id', 'INTEGER'),
                ('announcement_mode', 'INTEGER DEFAULT 0'),
                ('oh_starts_at', 'TEXT'),
                ('oh_ends_at', 'TEXT'),
                ('retention_days', 'INTEGER'),
                ('slow_mode_seconds', 'INTEGER DEFAULT 0'),
                ('is_encrypted', 'INTEGER DEFAULT 0'),
                ('linked_entity_type', 'TEXT'),
                ('linked_entity_id', 'TEXT'),
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

            # Migrate chat_room_members with moderation/favourite columns
            cursor.execute("PRAGMA table_info(chat_room_members)")
            crm_columns = {row[1] for row in cursor.fetchall()}
            crm_column_definitions = [
                ('is_banned', 'INTEGER DEFAULT 0'),
                ('muted_until', 'TEXT'),
                ('is_favourite', 'INTEGER DEFAULT 0'),
            ]
            for column_name, definition in crm_column_definitions:
                if column_name not in crm_columns:
                    try:
                        safe_alter_table_add_column("chat_room_members", column_name, definition, cursor.connection)
                        log_event('info', f"Added missing column {column_name} to chat_room_members")
                    except SQLIdentifierError as e:
                        log_event('warning', f"Invalid column definition for {column_name}: {e}")
                    except Exception as e:
                        log_event('warning', f"Could not add column {column_name} to chat_room_members: {e}")

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

            # Migrate chat_messages with new columns (edit/delete/reply/pin/attach)
            cursor.execute("PRAGMA table_info(chat_messages)")
            chat_message_columns = {row[1] for row in cursor.fetchall()}
            chat_message_column_definitions = [
                ('edited_at', 'TEXT'),
                ('is_deleted', 'INTEGER DEFAULT 0'),
                ('reply_to_id', 'INTEGER'),
                ('pinned_at', 'TEXT'),
                ('pinned_by', 'INTEGER'),
                ('attachment_path', 'TEXT'),
                ('attachment_name', 'TEXT'),
                ('attachment_mime', 'TEXT'),
                ('attachment_size', 'INTEGER'),
                ('flagged_at', 'TEXT'),
                ('is_encrypted', 'INTEGER DEFAULT 0'),
            ]
            for column_name, definition in chat_message_column_definitions:
                if column_name not in chat_message_columns:
                    try:
                        safe_alter_table_add_column("chat_messages", column_name, definition, cursor.connection)
                        log_event('info', f"Added missing column {column_name} to chat_messages")
                    except SQLIdentifierError as e:
                        log_event('warning', f"Invalid column definition for {column_name}: {e}")
                    except Exception as e:
                        log_event('warning', f"Could not add column {column_name} to chat_messages: {e}")

            # Reactions
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_message_reactions (
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (message_id, user_id, emoji),
                FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Polls (one row per poll-message)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_polls (
                message_id INTEGER PRIMARY KEY,
                question TEXT NOT NULL,
                multi_choice INTEGER DEFAULT 0,
                closes_at TEXT,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_poll_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (message_id) REFERENCES chat_polls (message_id) ON DELETE CASCADE
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_poll_votes (
                option_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                voted_at TEXT NOT NULL,
                PRIMARY KEY (option_id, user_id),
                FOREIGN KEY (option_id) REFERENCES chat_poll_options (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Shared notes (one document per room)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_room_notes (
                room_id INTEGER PRIMARY KEY,
                content TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                updated_by INTEGER,
                version INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE
            )
            ''')
            # Migrate notes table if version column is missing
            cursor.execute("PRAGMA table_info(chat_room_notes)")
            if 'version' not in {row[1] for row in cursor.fetchall()}:
                try:
                    safe_alter_table_add_column(
                        "chat_room_notes", "version",
                        "INTEGER NOT NULL DEFAULT 1",
                        cursor.connection,
                    )
                except Exception:
                    pass

            # Profanity / safeguarding wordlist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_filter_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                severity TEXT NOT NULL DEFAULT 'flag',
                created_at TEXT NOT NULL
            )
            ''')

            # Safeguarding flags emitted when a filter word matches
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS safeguarding_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                matched_word TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'flag',
                created_at TEXT NOT NULL,
                FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Reports (a user reporting a message or another user)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reporter_id INTEGER NOT NULL,
                target_message_id INTEGER,
                target_user_id INTEGER,
                room_id INTEGER,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                resolved_by INTEGER,
                resolved_at TEXT,
                resolution_note TEXT,
                FOREIGN KEY (reporter_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Migrate chat_reports with safeguarding link
            cursor.execute("PRAGMA table_info(chat_reports)")
            report_columns = {row[1] for row in cursor.fetchall()}
            if 'safeguarding_submission_id' not in report_columns:
                try:
                    safe_alter_table_add_column(
                        "chat_reports", "safeguarding_submission_id", "INTEGER",
                        cursor.connection,
                    )
                except Exception:
                    pass

            # At-rest encryption keys (deterrent — DB-local; not E2E)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_room_keys (
                room_id INTEGER PRIMARY KEY,
                key_b64 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE
            )
            ''')

            # Migrate users with a service_account flag (additive; safe).
            try:
                cursor.execute("PRAGMA table_info(users)")
                user_cols = {row[1] for row in cursor.fetchall()}
                if user_cols and 'service_account' not in user_cols:
                    safe_alter_table_add_column(
                        "users", "service_account",
                        "INTEGER DEFAULT 0", cursor.connection,
                    )
            except Exception as e:
                log_event('warning', f"Could not add service_account to users: {e}")

            # Persistent ban list (survives kicks / rejoins)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_room_bans (
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                banned_at TEXT NOT NULL,
                banned_by INTEGER,
                reason TEXT,
                PRIMARY KEY (room_id, user_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Idempotent system-generated posts (e.g. auto-posted assignment due dates)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_system_posts (
                room_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                message_id INTEGER,
                posted_at TEXT NOT NULL,
                PRIMARY KEY (room_id, kind, key),
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE
            )
            ''')

            # DM block list
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS dm_blocks (
                user_id INTEGER NOT NULL,
                blocked_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, blocked_user_id),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (blocked_user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Office-hours queue ("raise hand")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_room_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Chat read receipts / unread tracking
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_message_reads (
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                last_read_message_id INTEGER NOT NULL DEFAULT 0,
                last_read_at TEXT NOT NULL,
                PRIMARY KEY (user_id, room_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Chat typing indicator (ephemeral)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_typing (
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                PRIMARY KEY (user_id, room_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Chat presence (heartbeat per user per room)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_presence (
                user_id INTEGER NOT NULL,
                room_id INTEGER NOT NULL,
                last_seen_at TEXT NOT NULL,
                PRIMARY KEY (user_id, room_id),
                FOREIGN KEY (room_id) REFERENCES chat_rooms (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

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

            # Indexes for hot chat-side paths. The base tables only had their
            # PRIMARY KEYs; per-room queries fell back to full scans once a
            # busy room had thousands of messages. All `IF NOT EXISTS` so the
            # migration is safe to re-run.
            chat_indexes = [
                ('idx_chat_messages_room_id',        'chat_messages',        '(room_id, id DESC)'),
                ('idx_chat_messages_room_sent',      'chat_messages',        '(room_id, sent_at DESC)'),
                ('idx_chat_messages_sender',         'chat_messages',        '(sender_id)'),
                ('idx_chat_messages_reply_to',       'chat_messages',        '(reply_to_id)'),
                ('idx_chat_room_members_user',       'chat_room_members',    '(user_id)'),
                ('idx_chat_room_members_room',       'chat_room_members',    '(room_id, user_id)'),
                ('idx_chat_message_reads_room',      'chat_message_reads',   '(room_id, user_id)'),
                ('idx_chat_message_reactions_msg',   'chat_message_reactions', '(message_id)'),
                ('idx_chat_typing_room',             'chat_typing',          '(room_id, started_at DESC)'),
                ('idx_chat_presence_room',           'chat_presence',        '(room_id, last_seen_at DESC)'),
                ('idx_chat_room_queue_room',         'chat_room_queue',      '(room_id, status, joined_at)'),
                ('idx_chat_room_bans_user',          'chat_room_bans',       '(user_id)'),
                ('idx_safeguarding_flags_room',      'safeguarding_flags',   '(room_id, created_at DESC)'),
                ('idx_safeguarding_flags_msg',       'safeguarding_flags',   '(message_id)'),
                ('idx_chat_polls_msg',               'chat_polls',           '(message_id)'),
                ('idx_chat_poll_options_msg',        'chat_poll_options',    '(message_id, sort_order)'),
                ('idx_chat_poll_votes_user',         'chat_poll_votes',      '(user_id)'),
                ('idx_chat_reports_status',          'chat_reports',         '(status, created_at DESC)'),
                ('idx_chat_reports_room',            'chat_reports',         '(room_id, status)'),
                ('idx_chat_room_invitations_user',   'chat_room_invitations', '(user_id, status)'),
                ('idx_chat_room_invitations_room',   'chat_room_invitations', '(room_id, status)'),
                ('idx_communication_log_action',     'communication_log',    '(action_type, performed_at DESC)'),
                ('idx_communication_log_user',       'communication_log',    '(user_id, performed_at DESC)'),
            ]
            for index_name, table, cols in chat_indexes:
                try:
                    cursor.execute(
                        f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} {cols}'
                    )
                except Exception as e:
                    log_event('debug', f"Could not create {index_name}: {e}")

            return True

        try:
            result = execute_db_operation(_create_tables)
            if result:
                log_event('info', "Communication system database tables initialized successfully!")
            return result
        except Exception as e:
            log_event('error', f"Error initializing communication database: {e}")
            return False
