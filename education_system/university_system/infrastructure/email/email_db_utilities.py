"""Database utilities for the email infrastructure package.

This module provides database utilities for the email system, using the
centralized connection pool from infrastructure.database.db for consistency
and better resource management across the application.
"""

from __future__ import annotations

import contextlib
import os
import random
import re
import threading
import time

from education_system.university_system.infrastructure.database import db as _db_module
from education_system.university_system.infrastructure.database.db import (
    sqlite3,
    get_connection,
    get_connection_pool,
    transaction,
    DatabaseManager,
)
from education_system.university_system.infrastructure.database.constants import (
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY,
)
from education_system.university_system.core.logs import handle_exception, log_event, logger
from education_system.university_system.core import paths
from education_system.university_system.core.sql_safety import (
    validate_column_definition,
    safe_alter_table_add_column,
    SQLIdentifierError,
)

# Core path configuration shared with the email system
MAIN_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = paths.PROJECT_ROOT
DB_PATH = os.fspath(paths.DEFAULT_DB_PATH)

_DB_READY = False

# =============================================================================
# SCHEMA MIGRATION VERSIONING SYSTEM
# =============================================================================
# Provides proper version tracking for database schema migrations with:
# - Version tracking table
# - Applied migration timestamps
# - Rollback capability (for failed migrations)
# - Migration history logging
# =============================================================================

CURRENT_SCHEMA_VERSION = 2  # Increment this when adding new migrations


def _get_db_path() -> str:
    """Resolve the active database path dynamically for test monkeypatches."""
    return os.fspath(_db_module.DEFAULT_DB_PATH)


def _ensure_migrations_table(cursor) -> None:
    """Ensure the schema_migrations table exists with all required columns.
    Older deployments may have a leaner version (id/migration_name/applied_at
    only); add missing columns in place via ALTER TABLE."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schema_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version INTEGER NOT NULL UNIQUE,
        migration_name TEXT NOT NULL,
        applied_at TEXT NOT NULL,
        status TEXT DEFAULT 'success',
        error_message TEXT,
        rollback_sql TEXT
    )
    ''')
    existing = {row[1] for row in cursor.execute("PRAGMA table_info(schema_migrations)").fetchall()}
    for col, ddl in (
        ("version", "INTEGER"),
        ("status", "TEXT DEFAULT 'success'"),
        ("error_message", "TEXT"),
        ("rollback_sql", "TEXT"),
    ):
        if col not in existing:
            try:
                cursor.execute(f"ALTER TABLE schema_migrations ADD COLUMN {col} {ddl}")
            except Exception as e:
                logger.warning(f"Could not add schema_migrations.{col}: {e}")


def get_schema_version(cursor) -> int:
    """
    Get the current schema version from the database.

    Args:
        cursor: Database cursor

    Returns:
        int: Current schema version, or 0 if no migrations have been applied
    """
    try:
        _ensure_migrations_table(cursor)
        cursor.execute("""
            SELECT version FROM schema_migrations
            WHERE status = 'success'
            ORDER BY version DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Could not determine schema version: {e}")
        return 0


def apply_migration(cursor, version: int, migration_name: str,
                   migration_func, rollback_sql: str = None) -> bool:
    """
    Apply a single migration with proper tracking.

    Args:
        cursor: Database cursor
        version: Migration version number
        migration_name: Human-readable migration name
        migration_func: Callable that takes cursor and applies the migration
        rollback_sql: Optional SQL to rollback this migration (for simple cases)

    Returns:
        bool: True if migration was applied successfully, False otherwise
    """
    from datetime import datetime as dt

    _ensure_migrations_table(cursor)

    # Check if already applied
    cursor.execute("""
        SELECT id FROM schema_migrations
        WHERE version = ? AND status = 'success'
    """, (version,))
    if cursor.fetchone():
        logger.debug(f"Migration v{version} ({migration_name}) already applied, skipping")
        return True

    logger.info(f"Applying migration v{version}: {migration_name}")
    applied_at = dt.now().isoformat()

    try:
        # Apply the migration
        migration_func(cursor)

        # Record successful migration
        cursor.execute("""
            INSERT INTO schema_migrations
            (version, migration_name, applied_at, status, rollback_sql)
            VALUES (?, ?, ?, 'success', ?)
        """, (version, migration_name, applied_at, rollback_sql))

        logger.info(f"Migration v{version} ({migration_name}) applied successfully")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Migration v{version} ({migration_name}) failed: {error_msg}")

        # Record failed migration
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO schema_migrations
                (version, migration_name, applied_at, status, error_message)
                VALUES (?, ?, ?, 'failed', ?)
            """, (version, migration_name, applied_at, error_msg))
        except Exception as record_error:
            logger.warning(f"Could not record migration failure: {record_error}")

        return False


def get_migration_history(cursor) -> list:
    """
    Get the full migration history.

    Args:
        cursor: Database cursor

    Returns:
        list: List of migration records as dictionaries
    """
    try:
        _ensure_migrations_table(cursor)
        cursor.execute("""
            SELECT version, migration_name, applied_at, status, error_message
            FROM schema_migrations
            ORDER BY version ASC
        """)

        columns = ['version', 'migration_name', 'applied_at', 'status', 'error_message']
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.warning(f"Could not retrieve migration history: {e}")
        return []


def run_pending_migrations(cursor) -> dict:
    """
    Run all pending migrations up to CURRENT_SCHEMA_VERSION.

    Args:
        cursor: Database cursor

    Returns:
        dict: Results with 'applied', 'skipped', 'failed' counts
    """
    results = {'applied': 0, 'skipped': 0, 'failed': 0}
    current_version = get_schema_version(cursor)

    logger.info(f"Current schema version: {current_version}, target: {CURRENT_SCHEMA_VERSION}")

    # Define migrations (add new ones here as needed)
    migrations = {
        1: {
            'name': 'initial_email_schema',
            'func': _migration_v1_initial_schema,
            'rollback': None  # Cannot rollback initial schema
        },
        2: {
            'name': 'add_email_tracking_columns',
            'func': _migration_v2_add_tracking_columns,
            'rollback': None  # Column drops not safe to automate
        },
    }

    for version in range(current_version + 1, CURRENT_SCHEMA_VERSION + 1):
        if version not in migrations:
            logger.warning(f"No migration defined for version {version}")
            results['skipped'] += 1
            continue

        migration = migrations[version]
        success = apply_migration(
            cursor,
            version,
            migration['name'],
            migration['func'],
            migration.get('rollback')
        )

        if success:
            results['applied'] += 1
        else:
            results['failed'] += 1
            # Stop on failure to maintain consistency
            logger.error(f"Stopping migrations due to failure at v{version}")
            break

    return results


# =============================================================================
# MIGRATION DEFINITIONS
# =============================================================================

def _migration_v1_initial_schema(cursor):
    """Migration v1: Ensure base email tables exist."""
    # This migration just ensures the migration system is tracked
    # The actual tables are created by initialize_email_db()
    logger.info("Migration v1: Base schema marker applied")


def _migration_v2_add_tracking_columns(cursor):
    """Migration v2: Add email tracking and analytics columns."""
    # Add tracking columns to email_log if they don't exist
    cursor.execute("PRAGMA table_info(email_log)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ('opened_at', 'TEXT'),
        ('clicked_at', 'TEXT'),
        ('delivery_status', 'TEXT'),
        ('bounce_reason', 'TEXT'),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                safe_alter_table_add_column("email_log", col_name, col_type, cursor.connection)
                logger.info(f"Added column {col_name} to email_log")
            except SQLIdentifierError as e:
                logger.warning(f"Invalid column definition for {col_name}: {e}")
            except Exception as e:
                logger.warning(f"Could not add column {col_name}: {e}")


# =============================================================================
# ORIGINAL FUNCTIONS (updated to use migration system)
# =============================================================================

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
    if not file_path:
        return
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def get_unified_connection():
    """Get a unified database connection using the central connection pool.

    This function now delegates to the centralized database layer in
    infrastructure.database.db, ensuring consistent connection management
    across the entire application.

    Returns:
        sqlite3.Connection: A configured database connection.

    Raises:
        DatabaseConnectionError: If unable to connect to database.
    """
    return get_connection(db_path=_get_db_path(), row_factory=True)


def execute_db_operation(operation_func, *args, max_retries=None, **kwargs):
    """Execute a database operation with retry logic.

    Uses the centralized DatabaseManager from infrastructure.database.db
    for consistent connection handling and automatic retry on database locks.

    Args:
        operation_func: Function to execute, receives cursor as first argument.
        *args: Additional positional arguments passed to operation_func.
        max_retries: Maximum retry attempts (defaults to MAX_RETRY_ATTEMPTS).
        **kwargs: Additional keyword arguments passed to operation_func.

    Returns:
        The return value of operation_func.

    Raises:
        sqlite3.OperationalError: If operation fails after all retries.
    """
    if max_retries is None:
        max_retries = MAX_RETRY_ATTEMPTS

    for attempt in range(max_retries):
        try:
            # Use centralized DatabaseManager with automatic retry and transaction handling
            with DatabaseManager(_get_db_path()) as db:
                return operation_func(db.cursor, *args, **kwargs)

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                delay = (2 ** attempt) * RETRY_DELAY + random.uniform(0, 1)
                logger.info(f"Database locked, retrying in {delay:.2f}s (attempt {attempt + 1})")
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
    """Simplified safe database operation.

    Alias for execute_db_operation for backward compatibility.
    """
    return execute_db_operation(operation_func, *args, **kwargs)


# =============================================================================
# Backward Compatibility - Deprecated
# =============================================================================
# The following classes and functions are deprecated but maintained for
# backward compatibility. New code should use the centralized database
# utilities from infrastructure.database.db directly.

class SimpleDBManager:
    """Database manager using centralized connection pool.

    .. deprecated::
        Use DatabaseManager from infrastructure.database.db instead.
        This class is maintained for backward compatibility only.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or _get_db_path()
        ensure_parent_dir(self.db_path)
        self._lock = threading.RLock()
        import warnings
        warnings.warn(
            "SimpleDBManager is deprecated. Use DatabaseManager from "
            "infrastructure.database.db instead.",
            DeprecationWarning,
            stacklevel=2
        )

    @contextlib.contextmanager
    def get_connection(self, timeout=30.0):
        """Get a database connection using centralized pool."""
        conn = None
        try:
            if not self._lock.acquire(timeout=timeout):
                raise sqlite3.OperationalError("Could not acquire database lock")

            # Use centralized connection
            conn = get_connection(db_path=self.db_path, row_factory=True, timeout=timeout)
            cursor = conn.cursor()
            yield cursor
            conn.commit()

        except Exception as original_error:
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.warning(f"Failed to rollback connection during error handling: {rollback_error}")
            raise original_error
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    logger.warning(f"Failed to close database connection: {close_error}")
            try:
                self._lock.release()
            except RuntimeError as lock_error:
                logger.debug(f"Lock release failed (may have been released already): {lock_error}")


_db_manager = None
_db_manager_lock = threading.Lock()


def get_db_manager():
    """Get or create the global database manager.

    .. deprecated::
        Use DatabaseManager from infrastructure.database.db instead.
    """
    global _db_manager
    with _db_manager_lock:
        if _db_manager is None:
            # Suppress deprecation warning for internal use
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                _db_manager = SimpleDBManager()
        return _db_manager



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
            ('read_at', 'TEXT'),
            ('reply_to', 'INTEGER')
        ]

        # Use centralized SQL safety validation for column definitions
        for column_name, definition in column_definitions:
            if column_name not in existing_columns:
                try:
                    safe_alter_table_add_column("messages", column_name, definition, cursor.connection)
                    existing_columns.add(column_name)
                except SQLIdentifierError as e:
                    logger.warning(f"Invalid column definition for '{column_name}': {e}")
                    continue

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
                            safe_alter_table_add_column("scheduled_emails", column_name, definition, cursor.connection)
                            log_event('info', f"Added missing column {column_name} to scheduled_emails")
                        except SQLIdentifierError as e:
                            log_event('warning', f"Invalid column definition for {column_name}: {e}")
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

        # Run schema migrations after base tables are created
        migration_results = run_pending_migrations(cursor)
        if migration_results['failed'] > 0:
            log_event('warning', f"Some migrations failed: {migration_results}")
        elif migration_results['applied'] > 0:
            log_event('info', f"Applied {migration_results['applied']} new migration(s)")

        return True

    result = execute_db_operation(_init_tables)

    # Heal older deployments where email_log was created with a leaner
    # column set (sent_at instead of sent_date, missing tracking columns).
    try:
        migrate_email_log_table()
    except Exception as e:
        log_event('warning', f"email_log migration during init skipped: {e}")

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

            # List of columns that should exist. `sent_date` and `message`
            # are present in the canonical schema but missing on older
            # deployments that only have `sent_at`/`body`.
            required_columns = [
                ('sent_date', 'TEXT'),
                ('message', 'TEXT'),
                ('related_to', 'TEXT'),
                ('student_id', 'TEXT'),
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
                        safe_alter_table_add_column("email_log", column_name, column_type, cursor.connection)
                        log_event('info', f"Added column {column_name} to email_log table")
                    except SQLIdentifierError as e:
                        log_event('warning', f"Invalid column definition for {column_name}: {e}")
                    except Exception as e:
                        log_event('warning', f"Could not add column {column_name}: {e}")

            # Rebuild the table if any legacy NOT NULL constraints survive on
            # columns the canonical writers don't populate (body/sent_at were
            # superseded by message/sent_date). SQLite can't relax a NOT NULL
            # in place, so copy → drop → rename.
            cursor.execute("PRAGMA table_info(email_log)")
            cols = cursor.fetchall()
            problem_nn = {row[1] for row in cols
                          if row[1] in ('body', 'sent_at') and row[3]}
            if problem_nn:
                col_names = [row[1] for row in cols]
                col_list = ", ".join(col_names)
                cursor.execute("ALTER TABLE email_log RENAME TO email_log_old")
                cursor.execute(f'''
                    CREATE TABLE email_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipient TEXT,
                        subject TEXT,
                        body TEXT,
                        sent_at TEXT,
                        status TEXT,
                        error_message TEXT,
                        opened_at TEXT,
                        clicked_at TEXT,
                        delivery_status TEXT,
                        bounce_reason TEXT,
                        sent_date TEXT,
                        message TEXT,
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
                shared = [c for c in col_names if c in (
                    'id','recipient','subject','body','sent_at','status','error_message',
                    'opened_at','clicked_at','delivery_status','bounce_reason','sent_date',
                    'message','related_to','student_id','sender_email','sender_name',
                    'cc_recipients','bcc_recipients','attachment_info','template_name','template_vars')]
                shared_list = ", ".join(shared)
                cursor.execute(
                    f"INSERT INTO email_log ({shared_list}) SELECT {shared_list} FROM email_log_old"
                )
                cursor.execute("DROP TABLE email_log_old")
                log_event('info',
                    f"Rebuilt email_log to drop legacy NOT NULL on {sorted(problem_nn)}")

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
