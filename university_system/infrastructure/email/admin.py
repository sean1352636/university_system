"""Administration and dashboard integration helpers."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from university_system.infrastructure.email import state
from university_system.core.sql_safety import (
    validate_column_definition,
    safe_alter_table_add_column,
    SQLIdentifierError,
)

# Configure logger for this module
logger = logging.getLogger(__name__)
from university_system.infrastructure.email.announcements import (
    _send_announcement_notifications,
    create_announcement_safe,
    deactivate_announcement,
    display_announcements_menu,
    get_announcement_by_id,
    mark_announcement_viewed,
)
from university_system.infrastructure.email.chat_rooms import (
    create_chat_room_form,
    display_all_rooms_admin,
    display_chat_rooms_menu,
    display_my_chat_rooms,
    display_public_rooms,
    display_room_invitations,
    enter_chat_room,
    initialize_chat_tables,
    manage_chat_room,
)
from university_system.infrastructure.email.config import (
    config,
    configure_email_settings,
    ensure_email_config_for_database_mode,
    load_config,
    save_config,
)
from university_system.infrastructure.email.email_db_utilities import execute_db_operation, initialize_email_db, ensure_parent_dir, ensure_db_directory
from university_system.infrastructure.email.email_service import (
    display_stored_emails_menu,
    ensure_scheduler_running,
    get_stored_emails,
    queue_email,
    schedule_send,
    send_bulk,
    send_email,
    send_email_as_user,
    send_template_email,
    start_email_workers,
    wait_for_email_queue,
)
from university_system.core.logs import (
    LOG_MANAGEMENT_AVAILABLE,
    display_communication_analytics_menu,
    display_communication_logs_menu,
    handle_exception,
    log_event,
    log_manager,
)
from university_system.infrastructure.email.reports import (
    generate_report_form,
    get_recent_communication_activity,
    get_system_health_info,
    get_user_communication_stats,
)
from university_system.infrastructure.email.state import auth_proxy as auth
from university_system.infrastructure.email.templates import template_management_menu, save_default_templates, render_template

@handle_exception
def search_users(auth, search_term):
    """Search for users by username, first name, or last name using auth users table"""
    if not auth or not auth.current_user:
        log_event('error', "Must be logged in to search for users")
        return []
    
    def _search_users(cursor):
        search_pattern = f"%{search_term}%"
        
        # Use the auth users table structure
        cursor.execute('''
        SELECT id, username, first_name, last_name, email, role
        FROM users
        WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
        ORDER BY username
        LIMIT 50
        ''', (search_pattern, search_pattern, search_pattern))
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'email': row[4],
                'role': row[5],
                'full_name': f"{row[2]} {row[3]}"
            })
        
        return users
    
    try:
        return execute_db_operation(_search_users)
    except Exception as e:
        log_event('error', f"Error searching users: {e}")
        return []



@handle_exception
def list_all_users(auth, page=1, limit=10, role_filter=None):
    """List all users with pagination using auth users table"""
    if not auth or not auth.current_user:
        log_event('error', "Must be logged in to list users")
        return {'users': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}
    
    def _list_users(cursor):
        # Build query with optional role filter
        where_clause = ""
        params = []
        
        if role_filter:
            where_clause = "WHERE u.role = ?"
            params.append(role_filter)
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM users u ' + where_clause, params)
        total_count = cursor.fetchone()[0]

        # Calculate offset
        offset = (page - 1) * limit
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1

        # Get users for current page
        cursor.execute('''
        SELECT u.id, u.username, u.first_name, u.last_name, u.email, u.role
        FROM users u ''' + where_clause + '''
        ORDER BY u.first_name, u.last_name, u.username
        LIMIT ? OFFSET ?
        ''', params + [limit, offset])
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'email': row[4],
                'role': row[5],
                'full_name': f"{row[2]} {row[3]}".strip()
            })
        
        return {
            'users': users,
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'total_pages': total_pages
        }
    
    try:
        return execute_db_operation(_list_users)
    except Exception as e:
        log_event('error', f"Error listing users: {e}")
        return {'users': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}



@handle_exception
def integrate_communication_dashboard_with_main():
    """Integrate the communication dashboard with the main system"""
    try:
        # Initialize database tables
        dashboard = CommunicationDashboard()
        
        # Load email configuration
        load_config()
        save_default_templates()
        
        # Initialize email database
        initialize_email_db()
        
        # Start email workers if configuration is complete and not in database-only mode
        if not config.get('database_only_mode', True):
            if config['sender_email'] and config['smtp_server']:
                start_email_workers()
        
        # Ensure the scheduler is running for scheduled emails
        if not config.get('database_only_mode', True):
            ensure_scheduler_running()
        
        # Log the integration
        log_event('info', "Communication Dashboard integrated successfully!")
        return True
    except Exception as e:
        log_event('error', f"Error integrating Communication Dashboard: {e}")
        return False



class CommunicationDashboard:
    """Main class for managing the university communication system with enhanced logging"""
    
    def __init__(self, db_path=None, auth=None):
        """Initialize using the same database path as auth system with logging integration"""
        try:
            # Use auth database path if available, with proper fallback
            from university_system.core.paths import DEFAULT_DB_PATH
            if auth and hasattr(auth, 'db_path') and auth.db_path:
                self.db_path = auth.db_path
            else:
                self.db_path = db_path or str(DEFAULT_DB_PATH)
            
            self.auth = auth
            
            # Ensure the directory exists
            ensure_parent_dir(self.db_path)
            
            # Initialize email system
            load_config()
            save_default_templates()
            
            # Initialize databases using the unified connection
            email_success = initialize_email_db()
            chat_success = initialize_chat_tables()
            main_success = self._init_db()
            
            success = email_success and chat_success and main_success
                        
            # Start email workers if configuration is complete and not in database-only mode
            if not config.get('database_only_mode', True):
                if config['sender_email'] and config['smtp_server']:
                    start_email_workers()
                
            if not success:
                log_event('warning', "Some database tables could not be initialized.")
            else:
                log_event('info', "Communication dashboard with enhanced logging initialized successfully")
                
        except Exception as e:
            log_event('error', f"Error initializing Communication Dashboard: {e}")
            raise

    def get_communication_logs(self, days=7, limit=100, user_filter=None, action_filter=None):
        """Get communication-related logs from the enhanced logging system"""
        if not LOG_MANAGEMENT_AVAILABLE or not log_manager:
            return []
        
        try:
            # Get logs from the last N days for communication activities
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            filters = {
                'date_from': start_date,
                'date_to': end_date,
                'module': 'email_manager'
            }
            
            # Add optional filters
            if user_filter:
                filters['username'] = user_filter
            if action_filter:
                filters['action'] = action_filter
            
            return log_manager.db.search_logs(filters, limit=limit)
        except Exception as e:
            log_event('error', f"Error retrieving communication logs: {e}")
            return []
    
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
        
    def _log_communication_action(self, user_id, action_type, action_details, cursor=None):
        """Enhanced communication action logging using both systems.

        Args:
            user_id: The user performing the action
            action_type: Type of action being logged
            action_details: Details about the action
            cursor: Optional cursor to reuse existing database connection.
                    If provided, uses the cursor directly to avoid nested transactions.
                    If None, opens a new database connection.
        """

        def _log_action(cur):
            performed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute('''
            INSERT INTO communication_log (user_id, action_type, action_details, performed_at)
            VALUES (?, ?, ?, ?)
            ''', (user_id, action_type, action_details, performed_at))
            return True

        try:
            # Log to communication system
            # If cursor is provided, use it directly to avoid nested transactions/deadlock
            if cursor is not None:
                result = _log_action(cursor)
            else:
                result = execute_db_operation(_log_action)

            # Also log to enhanced logging system if available
            # Note: This is deferred to avoid nested transactions
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    # Get user info for enhanced logging
                    def _get_user_info(cur):
                        cur.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
                        return cur.fetchone()

                    # Reuse cursor if provided, otherwise open new connection
                    if cursor is not None:
                        user_info = _get_user_info(cursor)
                    else:
                        user_info = execute_db_operation(_get_user_info)

                    if user_info:
                        username, role = user_info

                        activity_data = {
                            'timestamp': datetime.now().isoformat(),
                            'user_id': user_id,
                            'username': username,
                            'role': role,
                            'action': action_type,
                            'module': 'communication_dashboard',
                            'details': action_details,
                            'status': 'success'
                        }

                        log_manager.db.insert_log(activity_data)

                except Exception as e:
                    # Don't fail the main operation for enhanced logging issues
                    logger.warning(f"Enhanced communication logging failed: {e}")

            return result

        except Exception as e:
            log_event('warning', f"Communication log failed: {e}")
            return False

    @handle_exception
    def _send_email_notification(self, recipient_email, subject, message):
        """Send an email notification using the integrated email system"""
        return queue_email(recipient_email, subject, message)

    @handle_exception
    def get_integrated_system_health_info():
        """Get comprehensive system health information for both systems"""
        health_info = {
            'email_system': 'operational',
            'message_system': 'operational',
            'chat_system': 'operational',
            'database_status': 'operational',
            'enhanced_logging': 'not_available',
            'queue_size': 0,
            'log_entries_today': 0,
            'active_users': 0,
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # Check basic communication system health
            base_health = get_system_health_info()
            health_info.update(base_health)
            
            # Check enhanced logging system if available
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                health_info['enhanced_logging'] = 'operational'
                
                try:
                    # Get today's log count
                    today = datetime.now().strftime('%Y-%m-%d')
                    filters = {
                        'date_from': today,
                        'date_to': today,
                        'module': 'email_manager'
                    }
                    
                    today_logs = log_manager.db.search_logs(filters, limit=10000)
                    health_info['log_entries_today'] = len(today_logs)
                    
                    # Get active users count (users who performed actions today)
                    unique_users = set()
                    for log in today_logs:
                        if log.get('user_id'):
                            unique_users.add(log['user_id'])
                    health_info['active_users'] = len(unique_users)
                    
                except Exception as e:
                    health_info['enhanced_logging'] = 'degraded'
                    log_event('warning', f"Enhanced logging health check failed: {e}")
            
        except Exception as e:
            log_event('error', f"Error checking integrated system health: {e}")
            health_info['database_status'] = 'error'
        
        return health_info

    def display_system_health():
        """Display comprehensive system health information"""
        health = get_integrated_system_health_info()
        
        logger.info("\nIntegrated System Health Report:")
        logger.info("=" * 40)
        logger.info(f"Email System: {health['email_system'].upper()}")
        logger.info(f"Message System: {health['message_system'].upper()}")
        logger.info(f"Chat System: {health['chat_system'].upper()}")
        logger.info(f"Database: {health['database_status'].upper()}")
        logger.info(f"Enhanced Logging: {health['enhanced_logging'].upper()}")
        
        logger.info(f"\nSystem Metrics:")
        logger.info(f"Email Queue Size: {health['queue_size']}")
        logger.info(f"Log Entries Today: {health['log_entries_today']}")
        logger.info(f"Active Users Today: {health['active_users']}")
        logger.info(f"Last Check: {health['last_check']}")
        
        # Show any issues
        issues = []
        if health['email_system'] != 'operational':
            issues.append("Email system issues detected")
        if health['database_status'] != 'operational':
            issues.append("Database connectivity issues")
        if health['enhanced_logging'] == 'degraded':
            issues.append("Enhanced logging experiencing issues")
        
        if issues:
            logger.info(f"\nIssues Detected:")
            for issue in issues:
                logger.info(f"  - {issue}")
        else:
            logger.info(f"\nAll systems operational.")
        
        input("\nPress Enter to continue...")

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
            # Validate recipient exists
            cursor.execute('SELECT id, email, username FROM users WHERE id = ?', (recipient_id,))
            recipient_data = cursor.fetchone()
            if not recipient_data:
                log_event('error', f"Recipient with ID {recipient_id} not found")
                return False
            
            recipient_email = recipient_data[1]
            recipient_username = recipient_data[2]
            
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
                cursor.execute('''
                SELECT np.email_notifications, np.message_notifications 
                FROM notification_preferences np
                WHERE np.user_id = ?
                ''', (recipient_id,))

                prefs = cursor.fetchone()
                if prefs:
                    email_notifications = prefs[0] if prefs[0] is not None else 1
                    message_notifications = prefs[1] if prefs[1] is not None else 1
                    should_notify = bool(email_notifications and message_notifications and recipient_email)
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

    def get_communication_analytics(self, days=30):
        """Get analytics for communication activities"""
        if not LOG_MANAGEMENT_AVAILABLE or not log_manager:
            return None
        
        try:
            # Use log manager's analytics if available
            return log_manager.analytics.generate_activity_summary(days)
        except Exception as e:
            log_event('error', f"Error getting communication analytics: {e}")
            return None

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
            SELECT m.id, m.sender_id, s.username as sender_username, m.recipient_id,
                   r.username as recipient_username, m.subject, m.content,
                   m.is_read, m.sent_at, m.assignment_id, m.reply_to
            FROM messages m
            JOIN users s ON m.sender_id = s.id
            JOIN users r ON m.recipient_id = r.id
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
    
    @handle_exception
    def send_email_to_role(self, role, subject, body):
        """Send email to all users with a specific role"""
        if not self.auth or not self.auth.current_user:
            logger.info("You must be logged in to send emails.")
            return False
        
        def _send_to_role(cursor):
            # Get all users with the specified role
            cursor.execute('''
            SELECT id, email, first_name, last_name, username
            FROM users
            WHERE role = ?
            ORDER BY first_name, last_name
            ''', (role,))
            
            users = cursor.fetchall()
            
            if not users:
                logger.info(f"No users found with role '{role}'.")
                return False
            
            logger.info(f"Found {len(users)} users with role '{role}':")
            for user in users[:5]:  # Show first 5
                logger.info(f"  - {user[2]} {user[3]} ({user[1]})")
            
            if len(users) > 5:
                logger.info(f"  ... and {len(users) - 5} more")
            
            confirm = input(f"\nSend email to all {len(users)} {role}s? (y/n): ")
            if confirm.lower() != 'y':
                logger.info("Email cancelled.")
                return False
            
            # Send emails
            success_count = 0
            failure_count = 0
            
            for user in users:
                try:
                    success = queue_email(user[1], subject, body)
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    log_event('error', f"Error processing email for {user[1]}: {e}")
                    failure_count += 1
            
            if config.get('database_only_mode', True):
                logger.error(f"\nEmails stored in database: {success_count} successful, {failure_count} failed")
            else:
                logger.error(f"\nEmails queued: {success_count} successful, {failure_count} failed")
            
            # Log the bulk send
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                f"Bulk to {role}s",
                subject,
                current_time,
                'stored' if config.get('database_only_mode', True) else 'bulk_queued',
                f"Bulk Email to {role}s from {self.auth.current_user['username']}"
            ))
            
            return True
        
        try:
            return execute_db_operation(_send_to_role)
        except Exception as e:
            log_event('error', f"Error sending bulk email to {role}: {e}")
            return False

    @handle_exception
    def compose_email_with_user_selection(self):
        """Enhanced email composition with user selection interface"""
        if not self.auth or not self.auth.current_user:
            logger.info("You must be logged in to send emails.")
            return False
        
        logger.info("\nCompose New Email")
        logger.info("=================")
        
        # Get recipients using the selection interface
        recipients = self.display_user_selection_menu()
        
        if not recipients:
            logger.info("Email composition cancelled.")
            return False
        
        logger.info(f"\nComposing email for {len(recipients)} recipient(s):")
        for recipient in recipients:
            logger.info(f"  - {recipient['full_name']} ({recipient['email']})")
        
        # Get email details
        subject = input("\nEmail Subject: ").strip()
        if not subject:
            logger.info("Subject cannot be empty.")
            return False
        
        logger.info("\nEmail Body (type 'END' on a new line to finish):")
        body_lines = []
        while True:
            line = input()
            if line == 'END':
                break
            body_lines.append(line)
        
        body = "\n".join(body_lines)
        if not body:
            logger.info("Email body cannot be empty.")
            return False
        
        # Ask for email options
        logger.info("\nEmail Options:")
        send_immediately = input("Send immediately? (y/n, default: y): ").strip().lower()
        send_immediately = send_immediately != 'n'
        
        cc_emails = input("CC emails (comma-separated, optional): ").strip()
        cc_list = [email.strip() for email in cc_emails.split(',') if email.strip()] if cc_emails else None
        
        bcc_emails = input("BCC emails (comma-separated, optional): ").strip()
        bcc_list = [email.strip() for email in bcc_emails.split(',') if email.strip()] if bcc_emails else None
        
        # Confirm sending
        logger.info(f"\nEmail Summary:")
        logger.info(f"Subject: {subject}")
        logger.info(f"Recipients: {len(recipients)}")
        logger.info(f"CC: {len(cc_list) if cc_list else 0}")
        logger.info(f"BCC: {len(bcc_list) if bcc_list else 0}")
        logger.info(f"Mode: {'Database Storage' if config.get('database_only_mode', True) else 'SMTP Sending'}")
        logger.info(f"Send immediately: {'Yes' if send_immediately else 'No'}")
        
        if not send_immediately:
            # Get scheduling details
            logger.info("\nSchedule Email:")
            try:
                year = int(input("Year (YYYY): "))
                month = int(input("Month (MM): "))
                day = int(input("Day (DD): "))
                hour = int(input("Hour (0-23): "))
                minute = int(input("Minute (0-59): "))
                
                scheduled_date = datetime(year, month, day, hour, minute)
                
                if scheduled_date <= datetime.now():
                    logger.info("Scheduled date must be in the future.")
                    return False
                    
                logger.info(f"Scheduled for: {scheduled_date}")
            except ValueError:
                logger.info("Invalid date/time format.")
                return False
        
        confirm = input("\nSend this email? (y/n): ").strip().lower()
        if confirm != 'y':
            logger.info("Email cancelled.")
            return False
        
        # Send the emails
        success_count = 0
        failure_count = 0
        
        if send_immediately:
            # Send immediately
            for recipient in recipients:
                try:
                    success = queue_email(
                        recipient['email'], 
                        subject, 
                        body, 
                        cc=cc_list, 
                        bcc=bcc_list
                    )
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception as e:
                    log_event('error', f"Error processing email for {recipient['email']}: {e}")
                    failure_count += 1
            
            if config.get('database_only_mode', True):
                logger.error(f"\nEmails stored in database: {success_count} successful, {failure_count} failed")
            else:
                logger.error(f"\nEmails queued: {success_count} successful, {failure_count} failed")
                
                if success_count > 0:
                    wait_choice = input("Wait for all emails to be sent? (y/n): ")
                    if wait_choice.lower() == 'y':
                        wait_for_email_queue()
                        logger.info("All emails have been sent.")
        else:
            # Schedule emails
            recipient_emails = [r['email'] for r in recipients]
            
            # Create a simple template for scheduled sending
            template_name = f"scheduled_email_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create temporary template
            create_template(template_name, subject, body)
            
            # Schedule the emails
            result = schedule_send(scheduled_date, recipient_emails, template_name)
            
            logger.error(f"\nEmails scheduled: {result['success']} successful, {result['failure']} failed")
            logger.info(f"Scheduled for: {scheduled_date}")
        
        # Log the activity
        try:
            def _log_activity(cursor):
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Log each email sent
                for recipient in recipients:
                    cursor.execute('''
                    INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (
                        recipient['email'],
                        subject,
                        current_time,
                        'stored' if config.get('database_only_mode', True) else ('queued' if send_immediately else 'scheduled'),
                        f"Manual Email from {self.auth.current_user['username']}"
                    ))
                return True
            
            execute_db_operation(_log_activity)
        except Exception as e:
            log_event('error', f"Error logging email activity: {e}")
        
        return True
    
    @handle_exception
    def display_user_selection_menu(self):
        """Display user selection menu for email composition"""
        selected_recipients = []
        page = 1
        limit = 15
        role_filter = None
        search_term = None
        
        while True:
            logger.info("\n" + "="*80)
            logger.info("SELECT EMAIL RECIPIENTS")
            logger.info("="*80)
            
            # Show current selections
            if selected_recipients:
                logger.info(f"Selected Recipients ({len(selected_recipients)}):")
                for i, recipient in enumerate(selected_recipients, 1):
                    logger.info(f"  {i}. {recipient['full_name']} ({recipient['username']}) - {recipient['email']}")
                logger.info("-" * 80)
            
            # Get users to display
            if search_term:
                users_data = search_users(self.auth, search_term)
                users_result = {
                    'users': users_data[:limit],
                    'total_count': len(users_data),
                    'page': 1,
                    'limit': limit,
                    'total_pages': (len(users_data) + limit - 1) // limit
                }
            else:
                users_result = list_all_users(self.auth, page, limit, role_filter)
            
            if users_result['total_count'] == 0:
                logger.info("No users found.")
            else:
                # Display filter info
                filter_info = []
                if role_filter:
                    filter_info.append(f"Role: {role_filter}")
                if search_term:
                    filter_info.append(f"Search: {search_term}")
                
                if filter_info:
                    logger.info(f"Filters: {', '.join(filter_info)}")
                
                logger.info(f"\nUsers (Page {users_result['page']} of {users_result['total_pages']}):")
                logger.info(f"{'#':<3}{'Name':<25}{'Username':<15}{'Email':<30}{'Role':<10}{'Selected'}")
                logger.info("-" * 80)
                
                for i, user in enumerate(users_result['users'], 1):
                    # Check if user is already selected
                    is_selected = any(r['id'] == user['id'] for r in selected_recipients)
                    selected_mark = "✓" if is_selected else ""
                    
                    # Truncate long names/emails for display
                    name = user['full_name'][:24] if len(user['full_name']) > 24 else user['full_name']
                    username = user['username'][:14] if len(user['username']) > 14 else user['username']
                    email = user['email'][:29] if len(user['email']) > 29 else user['email']
                    
                    logger.info(f"{i:<3}{name:<25}{username:<15}{email:<30}{user['role']:<10}{selected_mark}")
            
            # Menu options
            logger.info("\nOptions:")
            logger.info("1. Select user by number")
            logger.info("2. Remove selected recipient")
            logger.info("3. Next page") if users_result['page'] < users_result['total_pages'] else None
            logger.info("4. Previous page") if users_result['page'] > 1 else None
            logger.info("5. Filter by role")
            logger.info("6. Search users")
            logger.info("7. Clear filters")
            logger.info("8. Select all on page")
            logger.info("9. Clear all selected")
            logger.info("10. Continue to compose email") if selected_recipients else None
            logger.info("0. Cancel")
            
            choice = input("\nEnter your choice: ").strip()
            
            if choice == '1':
                # Select user by number
                try:
                    user_num = int(input("Enter user number to select/deselect: "))
                    if 1 <= user_num <= len(users_result['users']):
                        selected_user = users_result['users'][user_num - 1]
                        
                        # Check if already selected
                        if any(r['id'] == selected_user['id'] for r in selected_recipients):
                            # Remove from selection
                            selected_recipients = [r for r in selected_recipients if r['id'] != selected_user['id']]
                            logger.info(f"Removed {selected_user['full_name']} from selection.")
                        else:
                            # Add to selection
                            selected_recipients.append(selected_user)
                            logger.info(f"Added {selected_user['full_name']} to selection.")
                    else:
                        logger.info("Invalid user number.")
                except ValueError:
                    logger.info("Please enter a valid number.")
            
            elif choice == '2':
                # Remove selected recipient
                if not selected_recipients:
                    logger.info("No recipients selected.")
                    continue
                
                logger.info("\nSelected Recipients:")
                for i, recipient in enumerate(selected_recipients, 1):
                    logger.info(f"{i}. {recipient['full_name']} ({recipient['email']})")
                
                try:
                    remove_num = int(input("Enter number to remove: "))
                    if 1 <= remove_num <= len(selected_recipients):
                        removed = selected_recipients.pop(remove_num - 1)
                        logger.info(f"Removed {removed['full_name']} from selection.")
                    else:
                        logger.info("Invalid number.")
                except ValueError:
                    logger.info("Please enter a valid number.")
            
            elif choice == '3' and users_result['page'] < users_result['total_pages']:
                # Next page
                page += 1
            
            elif choice == '4' and users_result['page'] > 1:
                # Previous page
                page -= 1
            
            elif choice == '5':
                # Filter by role
                logger.info("\nFilter by role:")
                logger.info("1. Students")
                logger.info("2. Staff")
                logger.info("3. Instructors") 
                logger.info("4. Admins")
                logger.info("5. Parents")
                logger.info("6. Clear role filter")
                
                role_choice = input("Enter choice: ").strip()
                
                if role_choice == '1':
                    role_filter = 'student'
                    page = 1
                elif role_choice == '2':
                    role_filter = 'staff'
                    page = 1
                elif role_choice == '3':
                    role_filter = 'instructor'
                    page = 1
                elif role_choice == '4':
                    role_filter = 'admin'
                    page = 1
                elif role_choice == '5':
                    role_filter = 'parent'
                    page = 1
                elif role_choice == '6':
                    role_filter = None
                    page = 1
                else:
                    logger.info("Invalid choice.")
            
            elif choice == '6':
                # Search users
                search_term = input("Enter search term (name, username, or email): ").strip()
                if not search_term:
                    search_term = None
                page = 1
            
            elif choice == '7':
                # Clear filters
                role_filter = None
                search_term = None
                page = 1
                logger.info("Filters cleared.")
            
            elif choice == '8':
                # Select all on page
                for user in users_result['users']:
                    if not any(r['id'] == user['id'] for r in selected_recipients):
                        selected_recipients.append(user)
                logger.info(f"Added {len(users_result['users'])} users to selection.")
            
            elif choice == '9':
                # Clear all selected
                if selected_recipients:
                    confirm = input(f"Clear all {len(selected_recipients)} selected recipients? (y/n): ")
                    if confirm.lower() == 'y':
                        selected_recipients = []
                        logger.info("All selections cleared.")
                else:
                    logger.info("No recipients selected.")
            
            elif choice == '10' and selected_recipients:
                # Continue to compose email
                return selected_recipients
            
            elif choice == '0':
                # Cancel
                if selected_recipients:
                    confirm = input("Cancel email composition? This will lose your recipient selection. (y/n): ")
                    if confirm.lower() == 'y':
                        return None
                else:
                    return None
            
            else:
                logger.info("Invalid choice.")
    
    @handle_exception
    def create_announcement(self, title, content, target_audience, is_urgent=0, start_date=None, end_date=None):
        """Create a new announcement"""
        # Check authentication and permissions
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to create announcements")
            return False
        
        # Only staff, admin, and instructors can create announcements
        allowed_roles = ['admin', 'staff', 'instructor']
        if self.auth.current_user['role'] not in allowed_roles:
            log_event('error', "Permission denied to create announcements")
            return False
        
        # Validate inputs
        if not title or not content or not target_audience:
            log_event('error', "Title, content, and target audience are required")
            return False
        
        # Set dates
        now = datetime.now()
        current_date = now.strftime('%Y-%m-%d %H:%M:%S')
        start_date = start_date if start_date else current_date
        
        # Validate date formats
        try:
            datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
            if end_date:
                datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            log_event('error', "Invalid date format. Use YYYY-MM-DD HH:MM:SS")
            return False
        
        def _create_announcement_op(cursor):
            creator_id = self.auth.current_user['id']
            
            cursor.execute('''
            INSERT INTO announcements (creator_id, title, content, target_audience, is_urgent, start_date, end_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (creator_id, title, content, target_audience, is_urgent, start_date, end_date, current_date, current_date))
            
            announcement_id = cursor.lastrowid
            
            # Log the action for auditing (pass cursor to avoid nested transactions)
            self._log_communication_action(creator_id, "create_announcement", f"Announcement created: {title}", cursor=cursor)
            
            # Send email notifications to target audience
            if target_audience == 'all':
                cursor.execute('''
                SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
                FROM users u
                LEFT JOIN notification_preferences np ON u.id = np.user_id
                ''')
            elif target_audience == 'students':
                cursor.execute('''
                SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
                FROM users u
                LEFT JOIN notification_preferences np ON u.id = np.user_id
                WHERE u.role = 'student'
                ''')
            elif target_audience == 'staff':
                cursor.execute('''
                SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
                FROM users u
                LEFT JOIN notification_preferences np ON u.id = np.user_id
                WHERE u.role IN ('staff', 'admin')
                ''')
            elif target_audience == 'instructors':
                cursor.execute('''
                SELECT u.id, u.email, np.email_notifications, np.announcement_notifications 
                FROM users u
                LEFT JOIN notification_preferences np ON u.id = np.user_id
                WHERE u.role = 'instructor'
                ''')
            else:
                # Specific course or department — not supported
                log_event(
                    'warning',
                    f"Target audience '{target_audience}' not implemented; skipping notifications."
                )
                return announcement_id

            recipients = cursor.fetchall()
            
            # Use bulk sending for announcements
            recipient_emails = []
            template_vars_list = []
            
            for recipient in recipients:
                recipient_id = recipient[0]
                recipient_email = recipient[1]
                email_notifications = recipient[2] if recipient[2] is not None else 1
                announcement_notifications = recipient[3] if recipient[3] is not None else 1
                
                if email_notifications and announcement_notifications:
                    recipient_emails.append(recipient_email)
                    template_vars = {
                        'announcement_title': title,
                        'announcement_body': content,
                        'title': '',  # These would need to be populated in a real implementation
                        'first_name': '',
                        'last_name': ''
                    }
                    template_vars_list.append(template_vars)
            
            if recipient_emails:
                send_bulk(recipient_emails, 'general_announcement', template_vars_list)
            
            return announcement_id
        
        try:
            result = execute_db_operation(_create_announcement_op)
            if result:
                log_event('info', "Announcement created successfully!")
            return result
        except Exception as e:
            log_event('error', f"Error creating announcement: {e}")
            return False
    
    @handle_exception
    def get_announcements(self, page=1, limit=10):
        """Get active announcements relevant to the current user"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to view announcements")
            return {'announcements': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}

        user_id = self.auth.current_user['id']
        user_role = self.auth.current_user['role']
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        offset = (page - 1) * limit

        def _get_announcements(cursor):
            # Set role-based audience filters
            role_map = {
                'student': ['all', 'students'],
                'instructor': ['all', 'instructors'],
                'staff': ['all', 'staff'],
                'admin': ['all', 'staff']
            }

            audiences = role_map.get(user_role, ['all'])  # fallback to 'all' if unknown role
            role_placeholders = ','.join('?' for _ in audiences)

            # Fetch announcements
            query = f'''
                SELECT a.id, a.creator_id, u.username AS creator_username, a.title, a.content,
                       a.target_audience, a.is_urgent, a.start_date, a.end_date, a.created_at,
                       EXISTS (
                           SELECT 1 FROM announcement_viewers av 
                           WHERE av.announcement_id = a.id AND av.viewer_id = ?
                       ) as is_viewed
                FROM announcements a
                JOIN users u ON a.creator_id = u.id
                WHERE a.is_active = 1
                  AND a.start_date <= ?
                  AND (a.end_date IS NULL OR a.end_date >= ?)
                  AND a.target_audience IN ({role_placeholders})
                ORDER BY a.is_urgent DESC, a.created_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(query, (user_id, current_date, current_date, *audiences, limit, offset))

            announcements = []
            for row in cursor.fetchall():
                announcements.append({
                    'id': row[0],
                    'creator_id': row[1],
                    'creator': row[2],
                    'title': row[3],
                    'content': row[4],
                    'target_audience': row[5],
                    'is_urgent': bool(row[6]),
                    'start_date': row[7],
                    'end_date': row[8],
                    'created_at': row[9],
                    'is_viewed': bool(row[10])
                })

            # Count total relevant announcements
            count_query = f'''
                SELECT COUNT(*) FROM announcements a
                WHERE a.is_active = 1
                  AND a.start_date <= ?
                  AND (a.end_date IS NULL OR a.end_date >= ?)
                  AND a.target_audience IN ({role_placeholders})
            '''
            cursor.execute(count_query, (current_date, current_date, *audiences))
            total_count = cursor.fetchone()[0]

            return {
                'announcements': announcements,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            }

        try:
            return execute_db_operation(_get_announcements)
        except Exception as e:
            log_event('error', f"Error getting announcements: {e}")
            return {'announcements': [], 'total_count': 0, 'page': page, 'limit': limit, 'total_pages': 0}
    
    @handle_exception
    def create_chat_room(self, name, description=None, room_type='public'):
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
        
        def _create_room(cursor):
            creator_id = self.auth.current_user['id']
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if room name already exists
            cursor.execute('SELECT id FROM chat_rooms WHERE name = ? AND is_active = 1', (name.strip(),))
            if cursor.fetchone():
                log_event('error', f"Chat room '{name}' already exists")
                return False
            
            # Create the chat room
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
    def send_chat_message(self, room_id, content):
        """Send a message to a chat room"""
        if not self.auth or not self.auth.current_user:
            log_event('error', "Must be logged in to send chat messages")
            return False
        
        if not content or not content.strip():
            log_event('error', "Message content is required")
            return False
        
        def _send_message(cursor):
            user_id = self.auth.current_user['id']
            sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Check if user is a member of the room
            cursor.execute('''
            SELECT 1 FROM chat_room_members 
            WHERE room_id = ? AND user_id = ?
            ''', (room_id, user_id))
            
            if not cursor.fetchone():
                log_event('error', f"User not a member of room {room_id}")
                return False
            
            # Check if room is active
            cursor.execute('''
            SELECT is_active FROM chat_rooms WHERE id = ?
            ''', (room_id,))
            
            room_data = cursor.fetchone()
            if not room_data or not room_data[0]:
                log_event('error', f"Room {room_id} not found or inactive")
                return False
            
            # Send the message
            cursor.execute('''
            INSERT INTO chat_messages (room_id, sender_id, content, sent_at)
            VALUES (?, ?, ?, ?)
            ''', (room_id, user_id, content.strip(), sent_at))
            
            message_id = cursor.lastrowid
            
            return message_id
        
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
                       (SELECT COUNT(*) FROM chat_messages WHERE room_id = r.id) as message_count
                FROM chat_rooms r
                JOIN chat_room_members m ON r.id = m.room_id
                JOIN users u ON r.created_by = u.id
                WHERE m.user_id = ? AND r.is_active = 1
                ORDER BY r.name
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
            
            # Format room data
            room_list = []
            for room in rooms:
                room_list.append({
                    'id': room[0],
                    'name': room[1],
                    'description': room[2],
                    'room_type': room[3],
                    'created_at': room[4],
                    'creator': room[5],
                    'is_admin': bool(room[6]),
                    'member_count': room[7],
                    'message_count': room[8]
                })
            
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
            SELECT m.id, m.content, m.sent_at, u.username, u.first_name, u.last_name
            FROM chat_messages m
            JOIN users u ON m.sender_id = u.id
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
            for message in reversed(messages):
                full_name = f"{message[4]} {message[5]}".strip()
                message_list.append({
                    'id': message[0],
                    'content': message[1],
                    'sent_at': message[2],
                    'sender': message[3],
                    'sender_name': full_name if full_name else message[3]
                })
            
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
            
            # Get room members
            cursor.execute('''
            SELECT m.user_id, u.username, u.first_name, u.last_name, u.email,
                   m.joined_at, m.is_admin
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
                    'is_admin': bool(member[6])
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
                
    def get_notification_preferences(self):
        """Get notification preferences for the current user"""
        if not self.auth or not self.auth.current_user:
            return None
        
        def _get_prefs(cursor):
            cursor.execute('''
            SELECT email_notifications, message_notifications, announcement_notifications,
                   chat_notifications, daily_digest
            FROM notification_preferences
            WHERE user_id = ?
            ''', (self.auth.current_user['id'],))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    'email_notifications': bool(result[0]),
                    'message_notifications': bool(result[1]),
                    'announcement_notifications': bool(result[2]),
                    'chat_notifications': bool(result[3]),
                    'daily_digest': bool(result[4])
                }
            else:
                # Create default preferences
                default_prefs = {
                    'email_notifications': True,
                    'message_notifications': True,
                    'announcement_notifications': True,
                    'chat_notifications': True,
                    'daily_digest': False
                }
                
                cursor.execute('''
                INSERT INTO notification_preferences 
                (user_id, email_notifications, message_notifications, announcement_notifications,
                 chat_notifications, daily_digest)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    self.auth.current_user['id'],
                    default_prefs['email_notifications'],
                    default_prefs['message_notifications'],
                    default_prefs['announcement_notifications'],
                    default_prefs['chat_notifications'],
                    default_prefs['daily_digest']
                ))
                
                return default_prefs
        
        try:
            return execute_db_operation(_get_prefs)
        except Exception as e:
            log_event('error', f"Error getting notification preferences: {e}")
            return None

    def update_notification_preferences(self, preferences):
        """Update notification preferences for the current user"""
        if not self.auth or not self.auth.current_user:
            return False
        
        def _update_prefs(cursor):
            cursor.execute('''
            INSERT OR REPLACE INTO notification_preferences 
            (user_id, email_notifications, message_notifications, announcement_notifications,
             chat_notifications, daily_digest)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.auth.current_user['id'],
                preferences['email_notifications'],
                preferences['message_notifications'],
                preferences['announcement_notifications'],
                preferences['chat_notifications'],
                preferences['daily_digest']
            ))
            
            # Log the action (pass cursor to avoid nested transactions)
            self._log_communication_action(
                self.auth.current_user['id'],
                "update_preferences",
                "Updated notification preferences",
                cursor=cursor
            )
            return True

        try:
            return execute_db_operation(_update_prefs)
        except Exception as e:
            log_event('error', f"Error updating notification preferences: {e}")
            return False



@handle_exception
def display_messages_menu(dashboard):
    """Enhanced messages menu with FIXED reply functionality"""
    while True:
        logger.info("\nMessages:")
        logger.info("=========")
        logger.info("1. View Inbox")
        logger.info("2. View Sent Messages")
        logger.info("3. Compose New Email (Select Recipients)")
        logger.info("4. Send Email to Role")
        logger.info("5. View Archived Messages")
        logger.info("6. Back to Communication Dashboard")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            # View inbox
            inbox = dashboard.get_inbox()
            
            if inbox and inbox['total_count'] > 0:
                logger.info(f"\nInbox ({inbox['unread_count']} unread):")
                logger.info("=" * 60)
                
                for i, message in enumerate(inbox['messages'], 1):
                    if message.get('is_archived'):
                        status = "ARCHIVED"
                    elif not message.get('is_read'):
                        status = "NEW"
                    else:
                        status = "OPENED"
                    logger.info(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")
                
                logger.info(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")
                
                # Handle message reading with FIXED reply
                while True:
                    logger.info("\nOptions:")
                    logger.info("1. Read a message")
                    logger.info("2. Next page")
                    logger.info("3. Previous page")
                    logger.info("4. Back to Messages Menu")
                    
                    action = input("Enter choice: ")
                    
                    if action == '1':
                        msg_num = input("Enter message number to read: ")
                        try:
                            msg_index = int(msg_num) - 1
                            if 0 <= msg_index < len(inbox['messages']):
                                message_id = inbox['messages'][msg_index]['id']
                                message = dashboard.read_message(message_id)
                                
                                if message:
                                    logger.info("\n" + "=" * 60)
                                    logger.info(f"From: {message['sender']}")
                                    logger.info(f"To: {message['recipient']}")
                                    logger.info(f"Subject: {message['subject']}")
                                    logger.info(f"Date: {message['sent_at']}")
                                    logger.info("-" * 60)
                                    logger.info(message['content'])
                                    logger.info("=" * 60)
                                    # Mark local cache as read so status updates immediately
                                    inbox['messages'][msg_index]['is_read'] = True
                                    
                                    
                                    # Message actions - with archive support
                                    logger.info("\nOptions:")
                                    logger.info("1. Reply")
                                    logger.info("2. Archive")
                                    logger.info("3. Delete")
                                    logger.info("4. Mark as Unread")
                                    logger.info("5. Back")

                                    msg_action = input("Enter choice: ")

                                    if msg_action == '1':
                                        # Reply functionality
                                        logger.info(f"\nReplying to message from {message['sender']}")

                                        subject = f"Re: {message['subject']}"
                                        if subject.startswith("Re: Re:"):  # Avoid multiple Re: prefixes
                                            subject = message['subject']
                                            if not subject.startswith("Re: "):
                                                subject = f"Re: {subject}"

                                        logger.info(f"Reply subject: {subject}")
                                        content = input("Enter your reply: ")

                                        if content:
                                            logger.info(f"Sending reply to {message['sender']}...")

                                            # Send the reply
                                            reply_result = dashboard.send_message(
                                                message['sender_id'],
                                                subject,
                                                content
                                            )

                                            if reply_result:
                                                logger.info(f"✓ Reply sent successfully!")
                                                logger.info(f"The reply has been sent to {message['sender']} and should appear in their inbox.")
                                            else:
                                                logger.error("✗ Failed to send reply. Please check the logs for details.")
                                        else:
                                            logger.info("Reply cancelled - no content entered.")

                                    elif msg_action == '2':
                                        # Archive message
                                        if dashboard.update_message_status(message_id, 'archive'):
                                            logger.info("✅ Message archived successfully!")
                                            input("Press Enter to continue...")
                                            break  # Go back to inbox
                                        else:
                                            logger.error("❌ Failed to archive message.")

                                    elif msg_action == '3':
                                        # Delete message
                                        confirm = input(f"Are you sure you want to delete this message? (y/n): ")
                                        if confirm.lower() == 'y':
                                            if dashboard.update_message_status(message_id, 'delete'):
                                                logger.info("✅ Message deleted successfully!")
                                                input("Press Enter to continue...")
                                                break  # Go back to inbox
                                            else:
                                                logger.error("❌ Failed to delete message.")
                                        else:
                                            logger.info("Delete cancelled.")

                                    elif msg_action == '4':
                                        # Mark as unread
                                        if dashboard.update_message_status(message_id, 'mark_unread'):
                                            logger.info("✅ Message marked as unread!")
                                        else:
                                            logger.error("❌ Failed to mark message as unread.")

                                    elif msg_action == '5':
                                        # Back
                                        break
                                            
                                    elif msg_action == '3':
                                        # Enhanced Delete message
                                        logger.info(f"\nDelete Options for message: {message['subject']}")
                                        logger.info("=" * 50)
                                        
                                        # Get current message status
                                        msg_status = dashboard.get_message_status_info(message_id)
                                        
                                        if msg_status:
                                            logger.info(f"Current deletion status: {msg_status['deletion_status'].replace('_', ' ').title()}")
                                            
                                            if msg_status['deletion_status'] == 'not_deleted':
                                                logger.info("→ This will mark the message as deleted for you.")
                                                logger.info("→ The message will be permanently removed if the other party also deletes it.")
                                            elif msg_status['deletion_status'] == 'sender_deleted' and user_id == recipient_id:
                                                logger.info("→ The sender has already deleted this message.")
                                                logger.info("→ Deleting will PERMANENTLY remove it from the database.")
                                            elif msg_status['deletion_status'] == 'recipient_deleted' and user_id == sender_id:
                                                logger.info("→ The recipient has already deleted this message.")
                                                logger.info("→ Deleting will PERMANENTLY remove it from the database.")
                                            
                                            logger.info("\nDelete Options:")
                                            logger.info("1. Standard Delete (mark as deleted)")
                                            if dashboard.auth.current_user['role'] == 'admin':
                                                logger.info("2. Force Delete (permanently remove immediately - ADMIN ONLY)")
                                            logger.info("3. Cancel")
                                            
                                            delete_choice = input("\nEnter choice: ")
                                            
                                            if delete_choice == '1':
                                                # Check if this will result in permanent deletion
                                                will_be_permanent = False
                                                if user_id == sender_id and msg_status['is_deleted_by_recipient']:
                                                    will_be_permanent = True
                                                elif user_id == recipient_id and msg_status['is_deleted_by_sender']:
                                                    will_be_permanent = True
                                                
                                                if will_be_permanent:
                                                    confirm = input("⚠️  This will PERMANENTLY delete the message from the database. Continue? (y/n): ")
                                                else:
                                                    confirm = input("Mark this message as deleted? (y/n): ")
                                                
                                                if confirm.lower() == 'y':
                                                    if dashboard.update_message_status(message_id, 'delete'):
                                                        if will_be_permanent:
                                                            logger.info("✅ Message permanently deleted from database!")
                                                        else:
                                                            logger.info("✅ Message marked as deleted successfully!")
                                                            logger.info("ℹ️  Message will be permanently removed if the other party also deletes it.")
                                                    else:
                                                        logger.error("❌ Failed to delete message.")
                                                else:
                                                    logger.info("Delete cancelled.")
                                                    
                                            elif delete_choice == '2' and dashboard.auth.current_user['role'] == 'admin':
                                                # Admin force delete
                                                confirm = input("⚠️  ADMIN FORCE DELETE: This will immediately and permanently remove the message. Continue? (y/n): ")
                                                if confirm.lower() == 'y':
                                                    if dashboard.force_delete_message(message_id):
                                                        logger.info("✅ Message force deleted by administrator!")
                                                    else:
                                                        logger.error("❌ Failed to force delete message.")
                                                else:
                                                    logger.info("Force delete cancelled.")
                                                    
                                            else:
                                                logger.info("Delete cancelled.")
                                        else:
                                            logger.info("❌ Could not retrieve message status information.")

                            else:
                                logger.info("Invalid message number.")
                        except ValueError:
                            logger.info("Please enter a number.")
                            
                    elif action == '2':
                        if inbox['page'] < inbox['total_pages']:
                            inbox = dashboard.get_inbox(page=inbox['page'] + 1)
                            
                            logger.info(f"\nInbox ({inbox['unread_count']} unread):")
                            logger.info("=" * 60)
                            
                            for i, message in enumerate(inbox['messages'], 1):
                                if message.get('is_archived'):
                                    status = "ARCHIVED"
                                elif not message.get('is_read'):
                                    status = "NEW"
                                else:
                                    status = "OPENED"
                                logger.info(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")
                            
                            logger.info(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")
                        else:
                            logger.info("You are already on the last page.")
                            
                    elif action == '3':
                        if inbox['page'] > 1:
                            inbox = dashboard.get_inbox(page=inbox['page'] - 1)
                            
                            logger.info(f"\nInbox ({inbox['unread_count']} unread):")
                            logger.info("=" * 60)
                            
                            for i, message in enumerate(inbox['messages'], 1):
                                if message.get('is_archived'):
                                    status = "ARCHIVED"
                                elif not message.get('is_read'):
                                    status = "NEW"
                                else:
                                    status = "OPENED"
                                logger.info(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")
                            
                            logger.info(f"\nShowing {len(inbox['messages'])} of {inbox['total_count']} messages (Page {inbox['page']} of {inbox['total_pages']})")
                        else:
                            logger.info("You are already on the first page.")
                            
                    elif action == '4':
                        break
                    else:
                        logger.info("Invalid choice.")
            else:
                logger.info("Your inbox is empty.")
                input("Press Enter to continue...")
                
        elif choice == '2':
            # View sent messages
            sent = dashboard.get_sent_messages()
            if sent and sent['messages']:
                logger.info("\nSent Messages:")
                logger.info("=" * 60)
                
                for i, message in enumerate(sent['messages'], 1):
                    sender = message.get('sender') or (dashboard.auth.current_user['username'] if dashboard.auth and dashboard.auth.current_user else 'Unknown')
                    logger.info(f"{i}. From: {sender} -> To: {message['recipient']} (Sent: {message['sent_at']})")
                    logger.info(f"   Subject: {message['subject']}")
                    logger.info(f"   Message: {message['content']}")
                
                logger.info(f"\nShowing {len(sent['messages'])} of {sent['total_count']} messages")
            else:
                logger.info("No sent messages.")
            input("Press Enter to continue...")
                
        elif choice == '3':
            dashboard.compose_email_with_user_selection()
            input("Press Enter to continue...")
            
        elif choice == '4':
            # Send email to role
            logger.info("\nSend Email to Role:")
            logger.info("1. All Students")
            logger.info("2. All Staff")
            logger.info("3. All Instructors")
            logger.info("4. All Admins")
            logger.info("5. All Parents")
            logger.info("6. Cancel")
            
            role_choice = input("Select role (1-6): ")
            
            roles = {
                '1': 'student',
                '2': 'staff', 
                '3': 'instructor',
                '4': 'admin',
                '5': 'parent'
            }
            
            if role_choice in roles:
                role = roles[role_choice]
                
                subject = input("Email Subject: ")
                if not subject:
                    logger.info("Subject cannot be empty.")
                    continue
                
                logger.info("\nEmail Body (type 'END' on a new line to finish):")
                body_lines = []
                while True:
                    line = input()
                    if line == 'END':
                        break
                    body_lines.append(line)
                
                body = "\n".join(body_lines)
                if not body:
                    logger.info("Email body cannot be empty.")
                    continue
                
                dashboard.send_email_to_role(role, subject, body)
            elif role_choice == '6':
                continue
            else:
                logger.info("Invalid choice.")
            
        elif choice == '5':
            # View archived messages - Updated to use dedicated function
            page = 1
            limit = 10

            while True:
                archived = dashboard.get_archived_messages(page=page, limit=limit)

                if not archived or archived['total_count'] == 0:
                    logger.info("\nYou have no archived messages.")
                    input("Press Enter to continue...")
                    break

                logger.info(f"\nArchived Messages ({archived['total_count']} messages):")
                logger.info("=" * 70)

                for i, message in enumerate(archived['messages'], 1):
                    status = "READ" if message['is_read'] else "NEW"
                    logger.info(f"{i}. [{status}] From: {message['sender']} - Subject: {message['subject']} - {message['sent_at']}")

                logger.info(f"\nShowing {len(archived['messages'])} of {archived['total_count']} archived messages (Page {archived['page']} of {archived['total_pages']})")

                logger.info("\nOptions:")
                logger.info("1. Read a message")
                logger.info("2. Next page") if page < archived['total_pages'] else logger.info("2. (No more pages)")
                logger.info("3. Previous page") if page > 1 else logger.info("3. (First page)")
                logger.info("4. Unarchive a message")
                logger.info("5. Delete a message")
                logger.info("6. Back to Messages Menu")
                
                action = input("Enter choice: ")
                
                if action == '1':
                    # Read a message
                    if not archived['messages']:
                        logger.info("No messages to read on this page.")
                        continue

                    try:
                        msg_num = int(input("Enter message number to read: "))
                        if 1 <= msg_num <= len(archived['messages']):
                            message_id = archived['messages'][msg_num - 1]['id']
                            message = dashboard.read_message(message_id)
                            
                            if message:
                                logger.info("\n" + "=" * 60)
                                logger.info(f"From: {message['sender']}")
                                logger.info(f"To: {message['recipient']}")
                                logger.info(f"Subject: {message['subject']}")
                                logger.info(f"Date: {message['sent_at']}")
                                logger.info(f"Status: ARCHIVED")
                                logger.info("-" * 60)
                                logger.info(message['content'])
                                logger.info("=" * 60)
                                
                                # Message actions for archived messages
                                logger.info("\nMessage Actions:")
                                logger.info("1. Reply")
                                logger.info("2. Unarchive")
                                logger.info("3. Delete")
                                logger.info("4. Back to Archived Messages")
                                
                                msg_action = input("Enter choice: ")
                                
                                if msg_action == '1':
                                    # Reply to archived message
                                    logger.info(f"\nReplying to message from {message['sender']}")
                                    subject = f"Re: {message['subject']}"
                                    if subject.startswith("Re: Re:"):
                                        subject = message['subject']
                                        if not subject.startswith("Re: "):
                                            subject = f"Re: {subject}"
                                    
                                    logger.info(f"Reply subject: {subject}")
                                    content = input("Enter your reply: ")
                                    
                                    if content:
                                        reply_result = dashboard.send_message(
                                            message['sender_id'], 
                                            subject, 
                                            content
                                        )
                                        
                                        if reply_result:
                                            logger.info(f"✓ Reply sent successfully!")
                                        else:
                                            logger.error("✗ Failed to send reply.")
                                    else:
                                        logger.info("Reply cancelled - no content entered.")
                                        
                                elif msg_action == '2':
                                    # Unarchive message
                                    if dashboard.update_message_status(message_id, 'unarchive'):
                                        logger.info("✅ Message unarchived successfully!")
                                        # Refresh the archived messages list
                                        archived_messages = [msg for msg in dashboard.get_inbox(include_archived=True)['messages'] if msg['is_archived']]
                                        total_archived = len(archived_messages)
                                        if total_archived == 0:
                                            logger.info("No more archived messages.")
                                            input("Press Enter to continue...")
                                            break
                                    else:
                                        logger.error("❌ Failed to unarchive message.")
                                        
                                elif msg_action == '3':
                                    # Delete archived message
                                    confirm = input("Are you sure you want to delete this archived message? (y/n): ")
                                    if confirm.lower() == 'y':
                                        if dashboard.update_message_status(message_id, 'delete'):
                                            logger.info("✅ Message deleted successfully!")
                                            # Refresh the archived messages list
                                            archived_messages = [msg for msg in dashboard.get_inbox(include_archived=True)['messages'] if msg['is_archived']]
                                            total_archived = len(archived_messages)
                                            if total_archived == 0:
                                                logger.info("No more archived messages.")
                                                input("Press Enter to continue...")
                                                break
                                        else:
                                            logger.error("❌ Failed to delete message.")
                                    else:
                                        logger.info("Delete cancelled.")
                                
                                # Continue showing archived messages after action
                                
                            else:
                                logger.info("❌ Could not read message.")
                        else:
                            logger.info("Invalid message number.")
                    except ValueError:
                        logger.info("Please enter a valid number.")
                
                elif action == '2' and page < total_pages:
                    # Next page
                    page += 1
                
                elif action == '3' and page > 1:
                    # Previous page
                    page -= 1
                
                elif action == '4':
                    # Unarchive a message
                    if not current_page_messages:
                        logger.info("No messages to unarchive on this page.")
                        continue
                        
                    try:
                        msg_num = int(input("Enter message number to unarchive: "))
                        if 1 <= msg_num <= len(current_page_messages):
                            message_id = current_page_messages[msg_num - 1]['id']
                            message_subject = current_page_messages[msg_num - 1]['subject']
                            
                            confirm = input(f"Unarchive message '{message_subject}'? (y/n): ")
                            if confirm.lower() == 'y':
                                if dashboard.update_message_status(message_id, 'unarchive'):
                                    logger.info("✅ Message unarchived successfully!")
                                    
                                    # Refresh the archived messages list
                                    inbox = dashboard.get_inbox(include_archived=True)
                                    archived_messages = [msg for msg in inbox['messages'] if msg['is_archived']]
                                    total_archived = len(archived_messages)
                                    
                                    if total_archived == 0:
                                        logger.info("No more archived messages.")
                                        input("Press Enter to continue...")
                                        break
                                    
                                    # Adjust page if current page is now empty
                                    total_pages = (total_archived + limit - 1) // limit
                                    if page > total_pages and total_pages > 0:
                                        page = total_pages
                                    
                                    # Refresh current page messages
                                    start_idx = (page - 1) * limit
                                    end_idx = start_idx + limit
                                    current_page_messages = archived_messages[start_idx:end_idx]
                                    
                                else:
                                    logger.error("❌ Failed to unarchive message.")
                            else:
                                logger.info("Unarchive cancelled.")
                        else:
                            logger.info("Invalid message number.")
                    except ValueError:
                        logger.info("Please enter a valid number.")
                
                elif action == '5':
                    # Delete a message
                    if not current_page_messages:
                        logger.info("No messages to delete on this page.")
                        continue
                        
                    try:
                        msg_num = int(input("Enter message number to delete: "))
                        if 1 <= msg_num <= len(current_page_messages):
                            message_id = current_page_messages[msg_num - 1]['id']
                            message_subject = current_page_messages[msg_num - 1]['subject']
                            
                            # Get message status for enhanced delete feedback
                            msg_status = dashboard.get_message_status_info(message_id) if hasattr(dashboard, 'get_message_status_info') else None
                            
                            if msg_status:
                                logger.info(f"\nDelete message: {message_subject}")
                                logger.info("=" * 50)
                                logger.info(f"Current deletion status: {msg_status['deletion_status'].replace('_', ' ').title()}")
                                
                                user_id = dashboard.auth.current_user['id']
                                will_be_permanent = False
                                
                                if user_id == msg_status['sender_id'] and msg_status['is_deleted_by_recipient']:
                                    will_be_permanent = True
                                elif user_id == msg_status['recipient_id'] and msg_status['is_deleted_by_sender']:
                                    will_be_permanent = True
                                
                                if will_be_permanent:
                                    confirm = input("⚠️  This will PERMANENTLY delete the message from the database. Continue? (y/n): ")
                                else:
                                    confirm = input("Mark this message as deleted? (y/n): ")
                            else:
                                # Fallback if get_message_status_info is not available
                                confirm = input(f"Delete message '{message_subject}'? (y/n): ")
                            
                            if confirm.lower() == 'y':
                                if dashboard.update_message_status(message_id, 'delete'):
                                    if msg_status and will_be_permanent:
                                        logger.info("✅ Message permanently deleted from database!")
                                    else:
                                        logger.info("✅ Message deleted successfully!")
                                    
                                    # Refresh the archived messages list
                                    inbox = dashboard.get_inbox(include_archived=True)
                                    archived_messages = [msg for msg in inbox['messages'] if msg['is_archived']]
                                    total_archived = len(archived_messages)
                                    
                                    if total_archived == 0:
                                        logger.info("No more archived messages.")
                                        input("Press Enter to continue...")
                                        break
                                    
                                    # Adjust page if current page is now empty
                                    total_pages = (total_archived + limit - 1) // limit
                                    if page > total_pages and total_pages > 0:
                                        page = total_pages
                                    
                                    # Refresh current page messages
                                    start_idx = (page - 1) * limit
                                    end_idx = start_idx + limit
                                    current_page_messages = archived_messages[start_idx:end_idx]
                                    
                                else:
                                    logger.error("❌ Failed to delete message.")
                            else:
                                logger.info("Delete cancelled.")
                        else:
                            logger.info("Invalid message number.")
                    except ValueError:
                        logger.info("Please enter a valid number.")
            
        elif choice == '6':
            break
            
        else:
            logger.info("Invalid choice. Please try again.")



@handle_exception  
def display_preferences_menu(dashboard):
    """Enhanced notification preferences menu"""
    try:
        # Get current preferences
        preferences = dashboard.get_notification_preferences()
        
        if not preferences:
            # Create default preferences if they don't exist
            preferences = {
                'email_notifications': True,
                'message_notifications': True,
                'announcement_notifications': True,
                'chat_notifications': True,
                'daily_digest': False
            }
            dashboard.update_notification_preferences(preferences)
        
        while True:
            logger.info("\nNotification Preferences:")
            logger.info("========================")
            logger.info(f"1. Email Notifications: {'Enabled' if preferences['email_notifications'] else 'Disabled'}")
            logger.info(f"2. Message Notifications: {'Enabled' if preferences['message_notifications'] else 'Disabled'}")
            logger.info(f"3. Announcement Notifications: {'Enabled' if preferences['announcement_notifications'] else 'Disabled'}")
            logger.info(f"4. Chat Notifications: {'Enabled' if preferences['chat_notifications'] else 'Disabled'}")
            logger.info(f"5. Daily Digest: {'Enabled' if preferences['daily_digest'] else 'Disabled'}")
            logger.info("6. Save Changes")
            logger.info("7. Reset to Defaults")
            logger.info("8. Back to Communication Dashboard")
            
            choice = input("Enter your choice (1-8): ")
            
            if choice == '1':
                preferences['email_notifications'] = not preferences['email_notifications']
                logger.info(f"Email Notifications {'Enabled' if preferences['email_notifications'] else 'Disabled'}")
            elif choice == '2':
                preferences['message_notifications'] = not preferences['message_notifications']
                logger.info(f"Message Notifications {'Enabled' if preferences['message_notifications'] else 'Disabled'}")
            elif choice == '3':
                preferences['announcement_notifications'] = not preferences['announcement_notifications']
                logger.info(f"Announcement Notifications {'Enabled' if preferences['announcement_notifications'] else 'Disabled'}")
            elif choice == '4':
                preferences['chat_notifications'] = not preferences['chat_notifications']
                logger.info(f"Chat Notifications {'Enabled' if preferences['chat_notifications'] else 'Disabled'}")
            elif choice == '5':
                preferences['daily_digest'] = not preferences['daily_digest']
                logger.info(f"Daily Digest {'Enabled' if preferences['daily_digest'] else 'Disabled'}")
            elif choice == '6':
                # Save changes
                if dashboard.update_notification_preferences(preferences):
                    logger.info("Preferences saved successfully!")
                else:
                    logger.error("Failed to save preferences.")
                input("Press Enter to continue...")
            elif choice == '7':
                # Reset to defaults
                confirm = input("Reset all preferences to defaults? (y/n): ")
                if confirm.lower() == 'y':
                    preferences = {
                        'email_notifications': True,
                        'message_notifications': True,
                        'announcement_notifications': True,
                        'chat_notifications': True,
                        'daily_digest': False
                    }
                    logger.info("Preferences reset to defaults.")
            elif choice == '8':
                break
            else:
                logger.info("Invalid choice. Please try again.")
    except Exception as e:
        log_event('error', f"Error displaying preferences menu: {e}")
        logger.error("An error occurred while managing preferences.")
        input("Press Enter to continue...")



def display_admin_message_management_menu(dashboard):
    """Admin-only message management menu"""
    if not dashboard.auth or dashboard.auth.current_user['role'] != 'admin':
        logger.info("Access denied. Administrator privileges required.")
        return
    
    while True:
        logger.info("\nAdmin Message Management:")
        logger.info("========================")
        logger.info("1. View All Messages")
        logger.info("2. Search Messages")
        logger.info("3. Cleanup Deleted Messages")
        logger.info("4. Force Delete Message")
        logger.info("5. Message Statistics")
        logger.info("6. Back to Communication Dashboard")
        
        choice = input("Enter your choice (1-6): ")
        
        if choice == '1':
            # View all messages
            def _get_all_messages(cursor):
                cursor.execute('''
                SELECT m.id, s.username as sender, r.username as recipient, 
                       m.subject, m.sent_at, m.is_read, m.is_deleted_by_sender, 
                       m.is_deleted_by_recipient
                FROM messages m
                JOIN users s ON m.sender_id = s.id
                JOIN users r ON m.recipient_id = r.id
                ORDER BY m.sent_at DESC
                LIMIT 20
                ''')
                return cursor.fetchall()
            
            try:
                messages = execute_db_operation(_get_all_messages)
                
                if messages:
                    logger.info(f"\nAll Messages (Last 20):")
                    logger.info("=" * 100)
                    logger.info(f"{'ID':<5}{'Sender':<15}{'Recipient':<15}{'Subject':<25}{'Date':<20}{'Status':<15}")
                    logger.info("-" * 100)
                    
                    for msg in messages:
                        msg_id, sender, recipient, subject, sent_at, is_read, del_sender, del_recipient = msg
                        
                        # Determine status
                        if del_sender and del_recipient:
                            status = "BOTH_DELETED"
                        elif del_sender:
                            status = "SENDER_DEL"
                        elif del_recipient:
                            status = "RECIPIENT_DEL"
                        elif is_read:
                            status = "READ"
                        else:
                            status = "UNREAD"
                        
                        # Truncate long subjects
                        subj_display = subject[:22] + "..." if len(subject) > 22 else subject
                        
                        logger.info(f"{msg_id:<5}{sender:<15}{recipient:<15}{subj_display:<25}{sent_at:<20}{status:<15}")
                else:
                    logger.info("No messages found.")
            except Exception as e:
                logger.error(f"Error retrieving messages: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            # Search messages
            search_term = input("Enter search term (username or subject): ")
            if search_term:
                def _search_messages(cursor):
                    cursor.execute('''
                    SELECT m.id, s.username as sender, r.username as recipient, 
                           m.subject, m.sent_at, m.is_read, m.is_deleted_by_sender, 
                           m.is_deleted_by_recipient
                    FROM messages m
                    JOIN users s ON m.sender_id = s.id
                    JOIN users r ON m.recipient_id = r.id
                    WHERE s.username LIKE ? OR r.username LIKE ? OR m.subject LIKE ?
                    ORDER BY m.sent_at DESC
                    LIMIT 50
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                    return cursor.fetchall()
                
                try:
                    results = execute_db_operation(_search_messages)
                    logger.info(f"\nSearch Results for '{search_term}': {len(results)} found")
                    # Display similar to option 1
                except Exception as e:
                    logger.error(f"Error searching messages: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            # Cleanup deleted messages
            confirm = input("Clean up messages deleted by both parties? (y/n): ")
            if confirm.lower() == 'y':
                cleaned = dashboard.cleanup_deleted_messages()
                logger.info(f"✅ Cleaned up {cleaned} deleted messages.")
            else:
                logger.info("Cleanup cancelled.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            # Force delete message
            try:
                msg_id = int(input("Enter message ID to force delete: "))
                
                # Show message details first
                msg_status = dashboard.get_message_status_info(msg_id)
                if msg_status:
                    logger.info(f"\nMessage Details:")
                    logger.info(f"ID: {msg_status['id']}")
                    logger.info(f"Subject: {msg_status['subject']}")
                    logger.info(f"Sent: {msg_status['sent_at']}")
                    logger.info(f"Status: {msg_status['deletion_status']}")
                    
                    confirm = input(f"\nForce delete message {msg_id}? (y/n): ")
                    if confirm.lower() == 'y':
                        if dashboard.force_delete_message(msg_id):
                            logger.info("✅ Message force deleted successfully!")
                        else:
                            logger.error("❌ Failed to force delete message.")
                    else:
                        logger.info("Force delete cancelled.")
                else:
                    logger.info(f"Message {msg_id} not found.")
            except ValueError:
                logger.info("Invalid message ID.")
            
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            # Message statistics
            def _get_message_stats(cursor):
                cursor.execute('SELECT COUNT(*) FROM messages')
                total_messages = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_read = 0')
                unread_messages = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_deleted_by_sender = 1 AND is_deleted_by_recipient = 1')
                both_deleted = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM messages WHERE is_deleted_by_sender = 1 OR is_deleted_by_recipient = 1')
                partially_deleted = cursor.fetchone()[0]
                
                return total_messages, unread_messages, both_deleted, partially_deleted
            
            try:
                total, unread, both_del, partial_del = execute_db_operation(_get_message_stats)
                
                logger.info(f"\nMessage Statistics:")
                logger.info("=" * 30)
                logger.info(f"Total Messages: {total}")
                logger.info(f"Unread Messages: {unread}")
                logger.info(f"Messages deleted by both parties: {both_del}")
                logger.info(f"Messages deleted by one party: {partial_del - both_del}")
                logger.info(f"Active Messages: {total - both_del}")
            except Exception as e:
                logger.error(f"Error getting statistics: {e}")
            
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            break
        else:
            logger.info("Invalid choice. Please try again.")



def display_communication_dashboard(auth=None):
    """Display the integrated communication dashboard menu with enhanced logging"""
    
    # Use the same database path as the auth system
    if auth and hasattr(auth, 'db_path'):
        dashboard = CommunicationDashboard(db_path=auth.db_path, auth=auth)
    else:
        dashboard = CommunicationDashboard(auth=auth)
        
    # Email initialization
    load_config()
    save_default_templates()
    initialize_email_db()
    initialize_chat_tables()
    
    # Start email workers if configuration is complete and not in database-only mode
    if config['sender_email'] and not config.get('database_only_mode', True):
        if config['smtp_server']:
            start_email_workers()
    
    while True:
        if not auth or not auth.current_user:
            logger.info("You must be logged in to access the communication dashboard.")
            break
        
        mode_indicator = " [DB Mode]" if config.get('database_only_mode', True) else " [SMTP Mode]"
        is_admin = auth.current_user.get('role') == 'admin'
        
        # Check for notifications
        pending_invitations = dashboard.get_pending_invitations()
        notification_text = ""
        if pending_invitations:
            notification_text = f" (Chat invitations: {len(pending_invitations)})"
        
        logger.info(f"\nCommunication Dashboard{mode_indicator}{notification_text}:")
        logger.info("========================")
        logger.info("1. Messages")
        logger.info("2. Announcements")
        logger.info("3. Chat Rooms")
        logger.info("4. Notification Preferences")
        logger.info("5. Configure Email Settings")
        logger.info("6. Test Email Configuration")
        logger.info("7. Manage Email Templates")
        logger.info("8. Send Batch Announcement")
        logger.info("9. Schedule Emails")
        logger.info("10. View Email Queue Status")
        logger.info("11. Generate Email Reports")
        logger.info("12. View Stored Emails")
        
        # Enhanced logging options
        if LOG_MANAGEMENT_AVAILABLE:
            logger.info("13. View Communication Activity Logs")
            if is_admin:
                logger.info("14. Communication Analytics")
                logger.info("15. Admin Message Management")
                logger.info("16. Return to Main Menu")
                max_choice = 16
            else:
                logger.info("14. Return to Main Menu")
                max_choice = 14
        else:
            if is_admin:
                logger.info("13. Admin Message Management")
                logger.info("14. Return to Main Menu")
                max_choice = 14
            else:
                logger.info("13. Return to Main Menu")
                max_choice = 13
        
        choice = input(f"Enter your choice (1-{max_choice}): ")
        
        if choice == '1':
            display_messages_menu(dashboard)
        elif choice == '2':
            display_announcements_menu(dashboard)
        elif choice == '3':
            display_chat_rooms_menu(dashboard)
        elif choice == '4':
            display_preferences_menu(dashboard)
        elif choice == '5':
            configure_email_settings()
        elif choice == '6':
            if config.get('database_only_mode', True):
                logger.info("Test emails are stored in database when in Database Only mode.")
                recipient = input("Enter test recipient email: ")
                if recipient:
                    subject, body = render_template("test_email_database_mode", {
                        "sender_email": config['sender_email'],
                        "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "signature": config['email_signature']
                    })

                    if send_email(recipient, subject, body):
                        logger.info("Test email stored in database successfully!")
                    else:
                        logger.error("Failed to store test email.")
            else:
                recipient = input("Enter test recipient email (leave empty to send to yourself): ")
                test_email_configuration(recipient if recipient else None)
            input("\nPress Enter to continue...")
        elif choice == '7':
            template_management_menu()
        elif choice == '8':
            send_batch_email_form()
        elif choice == '9':
            schedule_email_form()
        elif choice == '10':
            if config.get('database_only_mode', True):
                # Show stored emails info instead of queue
                emails_data = get_stored_emails(limit=1)
                logger.info(f"\nStored emails in database: {emails_data['total_count']}")
                
                if emails_data['total_count'] > 0:
                    logger.info("Recent stored emails:")
                    recent_emails = get_stored_emails(limit=5)
                    for email in recent_emails['emails']:
                        logger.info(f"  - To: {email['recipient_email']}, Subject: {email['subject'][:50]}...")
            else:
                queue_size = email_queue.qsize()
                logger.info(f"\nCurrent email queue size: {queue_size}")
                if queue_size > 0:
                    wait = input("Wait for all emails to be sent? (y/n): ")
                    if wait.lower() == 'y':
                        wait_for_email_queue()
                
                # Show scheduled emails
                def _get_scheduled_emails(cursor):
                    cursor.execute('''
                    SELECT id, template_name, recipient_email, scheduled_date, status
                    FROM scheduled_emails
                    WHERE status = 'pending'
                    ORDER BY scheduled_date
                    ''')
                    
                    return cursor.fetchall()
                
                try:
                    scheduled = execute_db_operation(_get_scheduled_emails)
                    
                    if scheduled:
                        logger.info("\nPending Scheduled Emails:")
                        logger.info(f"{'ID':<5}{'Template':<25}{'Recipient':<30}{'Scheduled Date':<20}{'Status'}")
                        logger.info("-" * 80)
                        
                        for email in scheduled:
                            logger.info(f"{email[0]:<5}{email[1]:<25}{email[2]:<30}{email[3]:<20}{email[4]}")
                    else:
                        logger.info("\nNo pending scheduled emails.")
                except Exception as e:
                    log_event('error', f"Error getting scheduled emails: {e}")
                    logger.error("\nError retrieving scheduled emails.")
            
            input("\nPress Enter to continue...")
        elif choice == '11':
            generate_report_form()
        elif choice == '12':
            display_stored_emails_menu(auth)
        elif choice == '13' and LOG_MANAGEMENT_AVAILABLE:
            display_communication_logs_menu(dashboard)
        elif choice == '14' and LOG_MANAGEMENT_AVAILABLE and is_admin:
            display_communication_analytics_menu(dashboard)
        elif (choice == '13' and not LOG_MANAGEMENT_AVAILABLE and not is_admin) or \
             (choice == '14' and LOG_MANAGEMENT_AVAILABLE and not is_admin) or \
             (choice == '14' and not LOG_MANAGEMENT_AVAILABLE and is_admin) or \
             (choice == '15' and is_admin) or \
             (choice == '16' and is_admin):
            # Handle admin message management
            if choice in ['13', '14', '15'] and is_admin:
                display_admin_message_management_menu(dashboard)
            else:
                # Return to main menu
                if worker_threads and not config.get('database_only_mode', True):
                    if email_queue.qsize() > 0:
                        wait = input(f"There are {email_queue.qsize()} emails in the queue. Wait for them to be sent? (y/n): ")
                        if wait.lower() == 'y':
                            wait_for_email_queue()
                    stop_email_workers()
                logger.info("Returning to main menu...")
                break
        else:
            logger.info("Invalid choice. Please try again.")



def set_auth(auth_obj):
    """Set the authentication object for the email module and link to user_authentication"""
    # Use state.set_auth which properly links to user_authentication
    state.set_auth(auth_obj)
    if auth_obj:
        log_event('info', "Email system: Authentication set successfully and linked to user_authentication")
        return True
    return False



def set_communication_auth(auth_obj):
    """Set the authentication object for the communication dashboard module - alias for backward compatibility"""
    return set_auth(auth_obj)



def initialize_integrated_system(auth=None):
    """Initialize both communication and enhanced logging systems"""
    global log_manager
    
    try:
        # Initialize communication system first
        comm_result = initialize_communication_system()
        
        # Initialize enhanced logging if available
        log_result = True
        if LOG_MANAGEMENT_AVAILABLE:
            try:
                log_manager = get_log_manager()
                log_event('info', "Enhanced logging system integrated with communication dashboard")
                log_result = True
            except Exception as e:
                log_event('warning', f"Enhanced logging integration failed: {e}")
                log_result = False
        else:
            log_event('info', "Communication system initialized without enhanced logging")
        
        # Set authentication for both systems
        if auth:
            set_auth(auth)
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                # Both systems will use the same auth and database
                log_event('info', f"Authentication set for integrated system - User: {auth.current_user.get('username', 'Unknown')}")
        
        return comm_result and log_result
        
    except Exception as e:
        log_event('error', f"Error initializing integrated system: {e}")
        return False



def cleanup_integrated_system():
    """Clean up resources for both systems before shutting down"""
    try:
        # Clean up communication system
        cleanup_result = cleanup_communication_system()
        
        # Clean up enhanced logging system if available
        if LOG_MANAGEMENT_AVAILABLE and log_manager:
            try:
                # Stop any scheduled tasks
                if hasattr(log_manager, 'monitor') and log_manager.monitor.running:
                    log_manager.monitor.stop_monitoring()
                
                log_event('info', "Enhanced logging system cleaned up")
            except Exception as e:
                log_event('warning', f"Error cleaning up enhanced logging: {e}")
        
        log_event('info', "Integrated communication and logging system shutdown complete")
        return cleanup_result
        
    except Exception as e:
        log_event('error', f"Error during integrated system cleanup: {e}")
        return False



@handle_exception
def initialize_communication_system():
    """Initialize the entire communication system including chat rooms"""
    # Ensure database directory exists
    ensure_db_directory()
    
    # Load configuration (which includes database_only_mode setting)
    load_config()
    
    # Ensure proper email configuration for database-only mode
    if config.get('database_only_mode', True):
        if not config['sender_email']:
            config['sender_email'] = "noreply@university.edu"
            config['sender_name'] = "University System"
            save_config()
            log_event('info', "Configured default sender email for database-only mode")
    
    # Initialize databases
    initialize_email_db()
    initialize_chat_tables()
    
    # Only start SMTP workers if not in database-only mode
    if not config.get('database_only_mode', True):
        # Start email workers if configuration is complete
        if config['sender_email'] and config['smtp_server']:
            start_email_workers()
    
    log_event('info', f"Communication system with chat rooms initialized in {'Database Only' if config.get('database_only_mode', True) else 'SMTP'} mode")
    return True



@handle_exception
def cleanup_communication_system():
    """Clean up resources before shutting down"""
    # Stop email workers
    if worker_threads:
        if email_queue.qsize() > 0:
            log_event('warning', f"Warning: {email_queue.qsize()} emails still in queue and will not be sent.")
        stop_email_workers()
    
    log_event('info', "Communication system resources cleaned up.")
    return True



@handle_exception
def test_email_system():
    """Test the email system with database storage"""
    logger.info("Testing Email System - Database Storage Mode")
    logger.info("=" * 50)
    
    # Initialize system
    if initialize_communication_system():
        logger.info("✓ Communication system initialized")
    else:
        logger.error("✗ Failed to initialize communication system")
        return False
    
    # Test sending an email
    test_email = "test@example.com"
    test_subject = "Test Email"
    test_body = "This is a test email stored in the database."
    
    logger.info(f"\nTesting email to {test_email}...")
    if send_email(test_email, test_subject, test_body):
        logger.info("✓ Email stored successfully")
        
        # Log metrics
        log_email_metrics('sent')
        logger.info("✓ Metrics logged")
        
    else:
        logger.error("✗ Failed to store email")
        return False
    
    # Test template email
    logger.info("\nTesting template email...")
    template_vars = {
        'student_id': 'TEST123',
        'title': 'Mr',
        'first_name': 'John',
        'last_name': 'Doe',
        'email_address': test_email,
        'course': 'Computer Science',
        'modules_list': '- CS101: Introduction to Programming\n- CS102: Data Structures'
    }
    
    if send_template_email('user_management/registration_confirmation', test_email, template_vars):
        logger.info("✓ Template email stored successfully")
    else:
        logger.error("✗ Failed to store template email")
    
    logger.info("\n" + "=" * 50)
    logger.info("Email system test completed!")
    
    return True



def test_communication_dashboard_methods(auth=None):
    """Test if all required methods exist in CommunicationDashboard"""
    logger.info("Testing CommunicationDashboard methods...")
    
    # Create dashboard instance
    try:
        dashboard = CommunicationDashboard(auth=auth)
        logger.info("✅ CommunicationDashboard created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create CommunicationDashboard: {e}")
        return False
    
    # List of required methods
    required_methods = [
        'send_message',
        'send_message_with_debug',
        'get_inbox',
        'get_sent_messages', 
        'read_message',
        'update_message_status',
        'send_email_to_role',
        'compose_email_with_user_selection',
        'display_user_selection_menu',
        'get_notification_preferences',
        'update_notification_preferences',
        'create_announcement',
        'get_announcements'
    ]
    
    # Test each method
    missing_methods = []
    for method_name in required_methods:
        if hasattr(dashboard, method_name):
            method = getattr(dashboard, method_name)
            if callable(method):
                logger.info(f"✅ {method_name} - Found")
            else:
                logger.info(f"❌ {method_name} - Not callable")
                missing_methods.append(method_name)
        else:
            logger.info(f"❌ {method_name} - Missing")
            missing_methods.append(method_name)
    
    if missing_methods:
        logger.info(f"\n❌ Missing methods: {', '.join(missing_methods)}")
        logger.info("Please add these methods to your CommunicationDashboard class.")
        return False
    else:
        logger.info("\n✅ All required methods are present!")
        return True



@handle_exception
def send_system_notification(dashboard, user_id, title, message, notification_type='info'):
    """Send a system notification to a user"""
    if not dashboard.auth or not dashboard.auth.current_user:
        return False
    
    # For now, we'll implement this as a system message
    system_subject, system_message = render_template("system_notification", {
        "title": title,
        "notification_type": notification_type.upper(),
        "message": message
    })

    # Send as a message from system (admin) user
    def _send_notification(cursor):
        # Get or create system user
        cursor.execute('''
        SELECT id FROM users WHERE role = 'admin' AND username = 'system'
        ''')
        
        system_user = cursor.fetchone()
        if not system_user:
            # Create system user if it doesn't exist
            cursor.execute('''
            INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('system', 'System', 'User', 'system@university.edu', 'admin', 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            system_user_id = cursor.lastrowid
        else:
            system_user_id = system_user[0]
        
        # Send the message
        sent_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, subject, content, sent_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (system_user_id, user_id, system_subject, system_message, sent_at))
        
        return True
    
    try:
        return execute_db_operation(_send_notification)
    except Exception as e:
        log_event('error', f"Error sending system notification: {e}")
        return False
