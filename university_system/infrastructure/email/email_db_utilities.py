"""Database utilities for the email infrastructure package."""

from __future__ import annotations

import contextlib
import os
import random
from university_system.infrastructure.database.db import sqlite3
import threading
import time

from university_system.modules.shared.utils.logs import handle_exception, log_event, logger
from university_system.modules.shared.constants import paths

try:
    from university_system.infrastructure.auth.user_authentication import (  # type: ignore
        get_connection as auth_get_connection,
    )

    USE_AUTH_DB = True
    logger.info("Using authentication database connection")
except ImportError:  # pragma: no cover - optional dependency
    USE_AUTH_DB = False
    auth_get_connection = None
    logger.warning("Authentication module not found, using standalone DB")

# Core path configuration shared with the email system
MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = paths.PROJECT_ROOT
DB_PATH = os.fspath(paths.DEFAULT_DB_PATH)

_DB_READY = False

def _ensure_db_ready():
    """Ensure email DB schema exists before any send/save logic runs."""
    global _DB_READY
    try:
        if not _DB_READY:
            logger.info("Initializing email database...")
            initialize_email_db()
            logger.info("Database initialized, running inbox sync...")
            _sync_inbox_messages()  # Auto-fix missing inbox messages on startup
            _DB_READY = True
            logger.info("Email system initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize email system: {e}")
        # Do not hide init errors; re-raise so caller can log properly.
        raise


def _sync_inbox_messages():
    """
    Silently check for and fix missing inbox messages on startup.
    This ensures emails in 'stored_emails' are delivered to user inboxes in 'messages' table.
    """
    logger.info("Email sync: Starting automatic inbox sync check...")

    try:
        def _fix_missing_messages(cursor):
            import re
            from datetime import datetime

            # Find stored emails missing from inboxes
            cursor.execute('''
            SELECT se.id, se.recipient_email, se.subject, se.body,
                   se.sender_email, se.sender_name, se.created_date,
                   se.attachment_paths
            FROM stored_emails se
            LEFT JOIN users u ON se.recipient_email = u.email
            LEFT JOIN messages m ON (m.recipient_id = u.id AND m.subject = se.subject AND m.sent_at = se.created_date)
            WHERE u.id IS NOT NULL AND m.id IS NULL
            ORDER BY se.created_date DESC
            ''')

            missing_messages = cursor.fetchall()
            fixed_count = 0

            if not missing_messages:
                logger.info("Email sync: No missing inbox messages found (system is healthy)")
                return 0  # Nothing to fix, return silently

            logger.info(f"Email sync: Found {len(missing_messages)} stored emails missing from inboxes, syncing...")

            for email_data in missing_messages:
                se_id, recipient_email, subject, body, sender_email, sender_name, created_date, attachments = email_data

                try:
                    # Get recipient ID
                    cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                    recipient_result = cursor.fetchone()

                    if not recipient_result:
                        logger.debug(f"Email sync: Skipping - no user found for {recipient_email}")
                        continue

                    recipient_id = recipient_result[0]

                    # Get or create sender ID
                    sender_id = _get_or_create_sender_id(cursor, sender_email, sender_name, created_date)

                    # Create the inbox message
                    cursor.execute('''
                    INSERT INTO messages (
                        sender_id, recipient_id, subject, message, content,
                        attachment_path, is_read, sent_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    ''', (sender_id, recipient_id, subject, body, body, attachments, created_date))

                    fixed_count += 1
                    logger.debug(f"Email sync: Added '{subject[:40]}...' to inbox for {recipient_email}")

                except Exception as e:
                    logger.warning(f"Email sync: Failed to sync message for {recipient_email}: {e}")

            if fixed_count > 0:
                logger.info(f"Email sync: ✅ Successfully synced {fixed_count} messages to user inboxes")

            return fixed_count

        result = execute_db_operation(_fix_missing_messages)
        logger.info(f"Email sync: Completed - {result} messages synced")
        return result

    except Exception as e:
        # Don't crash startup if sync fails, just log it
        logger.warning(f"Email sync: Failed to sync inbox messages on startup: {e}")
        import traceback
        logger.debug(f"Email sync error traceback: {traceback.format_exc()}")
        return 0


def _get_or_create_sender_id(cursor, sender_email, sender_name, current_time):
    """
    Get the appropriate sender ID for an email.
    Helper function for _sync_inbox_messages to avoid circular imports.
    """
    import re

    # Method 1: Look for a real user with the sender email
    cursor.execute("SELECT id FROM users WHERE email = ?", (sender_email,))
    real_user = cursor.fetchone()

    if real_user:
        return real_user[0]

    # Method 2: Create or get a system user
    # Generate system username from sender name
    clean_name = re.sub(r'[^\w]', '', sender_name.lower())

    generic_names = ['system', 'university', 'noreply', 'admin']
    if clean_name in generic_names or len(clean_name) < 3:
        email_local = sender_email.split('@')[0]
        clean_name = re.sub(r'[^\w]', '', email_local.lower())

    if len(clean_name) > 20:
        clean_name = clean_name[:20]

    system_username = f"system_{clean_name}"

    cursor.execute("SELECT id FROM users WHERE username = ? AND role = 'admin'", (system_username,))
    system_user = cursor.fetchone()

    if system_user:
        return system_user[0]

    # Create new system user
    name_parts = sender_name.split(' ', 1)
    first_name = name_parts[0] if name_parts else sender_name
    last_name = name_parts[1] if len(name_parts) > 1 else ''

    cursor.execute('''
    INSERT INTO users (username, first_name, last_name, email, role, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (system_username, first_name, last_name, sender_email, 'admin', current_time, current_time))

    return cursor.lastrowid


def ensure_db_directory():
    """Ensure the database directory exists"""
    import os
    db_dir = os.fspath(paths.DB_DIR)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        log_event('info', f"Created database directory: {db_dir}")
    return db_dir



def ensure_parent_dir(file_path):
    """Ensure the parent directory of a file path exists"""
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

def get_unified_connection():
    """Get a unified database connection"""
    try:
        # Try to use auth database connection first
        if USE_AUTH_DB:
            try:
                return auth_get_connection()
            except Exception as e:
                log_event('warning', f"Auth DB connection failed, using direct connection: {e}")
        
        # Fallback to direct SQLite connection
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
        
    except Exception as e:
        log_event('error', f"Failed to get database connection: {e}")
        raise



class SimpleDBManager:
    """Ultra-simple database manager that uses auth DB when available"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        ensure_parent_dir(self.db_path)
        self._lock = threading.RLock()
    
    @contextlib.contextmanager
    def get_connection(self, timeout=30.0):
        """Get a database connection with auth integration"""
        conn = None
        try:
            if not self._lock.acquire(timeout=timeout):
                raise sqlite3.OperationalError("Could not acquire database lock")

            # Use unified connection
            conn = get_unified_connection()

            # Safe PRAGMA settings
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 30000")

            cursor = conn.cursor()
            yield cursor

            # CRITICAL: Commit transaction before closing
            conn.commit()

        except Exception:
            # Rollback on error
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
            try:
                self._lock.release()
            except:
                pass



_db_manager = None

_db_manager_lock = threading.Lock()



def get_db_manager():
    """Get or create the global database manager"""
    global _db_manager
    with _db_manager_lock:
        if _db_manager is None:
            _db_manager = SimpleDBManager()
        return _db_manager



def execute_db_operation(operation_func, *args, max_retries=3, **kwargs):
    """Execute a database operation with retry logic"""
    db_manager = get_db_manager()
    
    for attempt in range(max_retries):
        try:
            with db_manager.get_connection() as cursor:
                return operation_func(cursor, *args, **kwargs)
                
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Database locked, retrying in {delay:.2f}s (attempt {attempt + 1})")
                time.sleep(delay)
                continue
            else:
                logger.error(f"Database operation failed: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            raise
    
    raise sqlite3.OperationalError("Database operation failed after all retries")



def safe_db_operation(operation_func, *args, **kwargs):
    """Simplified safe database operation"""
    return execute_db_operation(operation_func, *args, **kwargs)



@handle_exception
def initialize_email_db():
    """Simplified email database initialization"""
    
    def _init_tables(cursor):
        # Stored emails table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS stored_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            cc_recipients TEXT,
            bcc_recipients TEXT,
            attachment_paths TEXT,
            created_date TEXT NOT NULL,
            template_name TEXT,
            template_vars TEXT,
            related_to TEXT,
            student_id TEXT
        )
        ''')
        
        # Email log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT,
            subject TEXT,
            message TEXT,
            sent_date TEXT,
            status TEXT,
            related_to TEXT,
            student_id TEXT,
            sender_email TEXT,
            sender_name TEXT,
            cc_recipients TEXT,
            bcc_recipients TEXT,
            attachment_info TEXT,
            template_name TEXT,
            template_vars TEXT
        )
        ''')
        
        # Messages table - align schema with communication admin expectations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            message TEXT,
            content TEXT,
            attachment_path TEXT,
            assignment_id INTEGER,
            is_read INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            is_deleted_by_sender INTEGER DEFAULT 0,
            is_deleted_by_recipient INTEGER DEFAULT 0,
            sent_at TEXT NOT NULL,
            read_at TEXT,
            reply_to INTEGER,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reply_to) REFERENCES messages (id)
        )
        ''')

        # Backfill missing columns for legacy databases without recreating the table
        cursor.execute("PRAGMA table_info(messages)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        column_definitions = [
            ('message', 'TEXT'),
            ('content', 'TEXT'),
            ('attachment_path', 'TEXT'),
            ('assignment_id', 'INTEGER'),
            ('is_archived', 'INTEGER DEFAULT 0'),
            ('is_deleted_by_sender', 'INTEGER DEFAULT 0'),
            ('is_deleted_by_recipient', 'INTEGER DEFAULT 0'),
            ('read_at', 'TEXT')
        ]

        for column_name, definition in column_definitions:
            if column_name not in existing_columns:
                cursor.execute(f'ALTER TABLE messages ADD COLUMN {column_name} {definition}')
                existing_columns.add(column_name)

        # Keep legacy data consistent between message/content columns
        if 'message' in existing_columns and 'content' in existing_columns:
            cursor.execute("UPDATE messages SET content = message WHERE content IS NULL AND message IS NOT NULL")
            cursor.execute("UPDATE messages SET message = content WHERE message IS NULL AND content IS NOT NULL")

        # Ensure default flags are set for existing rows
        if 'is_archived' in existing_columns:
            cursor.execute("UPDATE messages SET is_archived = 0 WHERE is_archived IS NULL")
        if 'is_deleted_by_sender' in existing_columns:
            cursor.execute("UPDATE messages SET is_deleted_by_sender = 0 WHERE is_deleted_by_sender IS NULL")
        if 'is_deleted_by_recipient' in existing_columns:
            cursor.execute("UPDATE messages SET is_deleted_by_recipient = 0 WHERE is_deleted_by_recipient IS NULL")

        # Email metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            opened_count INTEGER DEFAULT 0,
            clicked_count INTEGER DEFAULT 0
        )
        ''')
        
        # Scheduled emails table - handle both legacy and new schemas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_emails'")
        scheduled_exists = cursor.fetchone()

        if scheduled_exists:
            # Check if this is a legacy table
            cursor.execute("PRAGMA table_info(scheduled_emails)")
            scheduled_columns = {row[1] for row in cursor.fetchall()}

            # Legacy schema has: recipient, subject, body, scheduled_for
            # New schema has: template_name, recipient_email, template_vars, scheduled_date
            is_legacy = 'scheduled_for' in scheduled_columns and 'scheduled_date' not in scheduled_columns

            if is_legacy:
                log_event('info', "Migrating legacy scheduled_emails table to new schema")

                # Rename old table
                cursor.execute("ALTER TABLE scheduled_emails RENAME TO scheduled_emails_old")

                # Create new table with correct schema
                cursor.execute('''
                CREATE TABLE scheduled_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT,
                    recipient_email TEXT NOT NULL,
                    template_vars TEXT,
                    scheduled_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                ''')

                # Migrate data from old table
                try:
                    cursor.execute('''
                    INSERT INTO scheduled_emails (id, recipient_email, template_vars, scheduled_date, status, created_at)
                    SELECT
                        id,
                        recipient,
                        json_object('subject', subject, 'body', body),
                        scheduled_for,
                        COALESCE(status, 'pending'),
                        COALESCE(created_at, datetime('now'))
                    FROM scheduled_emails_old
                    ''')
                    log_event('info', f"Migrated {cursor.rowcount} records from legacy scheduled_emails")
                except Exception as e:
                    log_event('warning', f"Error migrating scheduled_emails data: {e}")

                # Drop old table
                cursor.execute("DROP TABLE scheduled_emails_old")
            else:
                # Not legacy, just add missing columns
                scheduled_column_definitions = [
                    ('template_name', 'TEXT'),
                    ('recipient_email', 'TEXT NOT NULL DEFAULT ""'),
                    ('template_vars', 'TEXT'),
                    ('scheduled_date', 'TEXT NOT NULL DEFAULT "2024-01-01 00:00:00"'),
                    ('status', 'TEXT DEFAULT "pending"'),
                    ('created_at', 'TEXT NOT NULL DEFAULT (datetime("now"))')
                ]

                for column_name, definition in scheduled_column_definitions:
                    if column_name not in scheduled_columns:
                        try:
                            cursor.execute(f'ALTER TABLE scheduled_emails ADD COLUMN {column_name} {definition}')
                            log_event('info', f"Added missing column {column_name} to scheduled_emails")
                        except Exception as e:
                            log_event('warning', f"Could not add column {column_name} to scheduled_emails: {e}")
        else:
            # Table doesn't exist, create it fresh
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT,
                recipient_email TEXT NOT NULL,
                template_vars TEXT,
                scheduled_date TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            ''')

        # Create indexes with error handling
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recipient_id ON messages(recipient_id)')
        except Exception as e:
            log_event('warning', f"Could not create idx_recipient_id: {e}")

        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender_id ON messages(sender_id)')
        except Exception as e:
            log_event('warning', f"Could not create idx_sender_id: {e}")

        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_metrics_date ON email_metrics(date)')
        except Exception as e:
            log_event('warning', f"Could not create idx_email_metrics_date: {e}")

        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_scheduled_emails_date ON scheduled_emails(scheduled_date)')
        except Exception as e:
            log_event('warning', f"Could not create idx_scheduled_emails_date: {e}")

        return True
    
    result = execute_db_operation(_init_tables)
    
    if result:
        log_event('info', "Email database initialized successfully")
    else:
        log_event('error', "Failed to initialize email database")
    
    return result



@handle_exception
def migrate_email_log_table():
    """Migrate existing email_log table to add missing columns"""
    def _migrate_table(cursor):
        try:
            # Get current table schema
            cursor.execute("PRAGMA table_info(email_log)")
            columns = cursor.fetchall()
            existing_columns = [column[1] for column in columns]
            
            # List of columns that should exist
            required_columns = [
                ('sender_email', 'TEXT'),
                ('sender_name', 'TEXT'),
                ('cc_recipients', 'TEXT'),
                ('bcc_recipients', 'TEXT'),
                ('attachment_info', 'TEXT'),
                ('template_name', 'TEXT'),
                ('template_vars', 'TEXT')
            ]
            
            # Add missing columns
            for column_name, column_type in required_columns:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f'ALTER TABLE email_log ADD COLUMN {column_name} {column_type}')
                        log_event('info', f"Added column {column_name} to email_log table")
                    except Exception as e:
                        log_event('warning', f"Could not add column {column_name}: {e}")
            
            log_event('info', "Email log table migration completed")
            return True
            
        except Exception as e:
            log_event('error', f"Error during email_log table migration: {e}")
            return False
    
    return execute_db_operation(_migrate_table)



def schedule_database_maintenance():
    """Schedule regular database maintenance"""
    import schedule
    schedule.every().day.at("02:00").do(optimize_database)



def optimize_database():
    """Run database optimization and maintenance"""
    def _optimize_db(cursor):
        # Run SQLite optimization
        cursor.execute("PRAGMA optimize")
        cursor.execute("PRAGMA wal_checkpoint(FULL)")
        
        # Analyze tables for better query planning
        cursor.execute("ANALYZE")
        return True
    
    try:
        result = execute_db_operation(_optimize_db)
        if result:
            log_event('info', "Database optimization completed")
        return result
    except Exception as e:
        log_event('error', f"Database optimization failed: {e}")
        return False
