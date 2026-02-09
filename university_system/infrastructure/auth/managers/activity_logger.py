"""
Activity Logging Module for Authentication

Comprehensive activity logging system with multiple fallback mechanisms
to ensure audit trail integrity even in adverse conditions.

Features:
- Primary database logging with retry logic
- File-based fallback logging
- In-memory emergency buffer
- Shared connection logging support
- Comprehensive error handling
- Multiple logging strategies

Fallback Hierarchy:
1. Primary database logging
2. Database retry with reduced timeout
3. File-based backup logging
4. Alternate location file logging
5. Emergency in-memory buffer
6. Python logging system (last resort)

Part of the authentication module refactoring to separate logging
concerns from core authentication logic.
"""

import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from university_system.modules.shared.constants import paths

__all__ = [
    'log_activity',
    'log_activity_with_connection',
    'get_emergency_log_buffer',
    'clear_emergency_log_buffer',
    'get_shared_connection_fallback_buffer',
    'clear_shared_connection_fallback_buffer',
]

logger = logging.getLogger(__name__)

# Emergency log buffers (module-level for persistence)
_emergency_log_buffer: List[Dict[str, Any]] = []
_shared_connection_fallback_buffer: List[Dict[str, Any]] = []


def log_activity(
    db_path: str,
    username: str,
    action: str,
    details: Optional[str] = None,
    user_id: Optional[int] = None
) -> bool:
    """
    Log user activity for audit purposes with comprehensive error handling.

    Primary logging function that attempts database logging with multiple
    fallback strategies to ensure audit trail integrity.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database
    username : str
        Username performing the action
    action : str
        Description of the action performed
    details : str, optional
        Additional details about the action
    user_id : int, optional
        User ID if available

    Returns
    -------
    bool
        True if logging succeeded (any method), False if all methods failed

    Examples
    --------
    >>> log_activity('/path/to/db.db', 'admin', 'User login', 'Successful login', 1)
    True

    Notes
    -----
    This function tries multiple strategies in order:
    1. Primary database logging
    2. Retry with reduced timeout
    3. File-based backup
    4. Alternate location file
    5. Emergency memory buffer
    """
    # Input validation and sanitization
    if not username or not action:
        logging.warning("Activity logging skipped: username and action are required")
        return False

    # Sanitize inputs to prevent injection attacks
    username = str(username)[:255]  # Limit length
    action = str(action)[:500]      # Limit length
    details = str(details)[:1000] if details else None  # Limit length

    # Validate user_id exists to avoid foreign key constraint violations
    if user_id is not None:
        try:
            with sqlite3.connect(db_path, timeout=2.0) as check_conn:
                check_conn.execute("PRAGMA busy_timeout = 2000")
                cursor = check_conn.cursor()
                cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                if cursor.fetchone() is None:
                    logging.debug(f"User ID {user_id} not found, setting to None to avoid FK violation")
                    user_id = None
        except sqlite3.Error as e:
            logging.debug(f"Database error validating user_id {user_id}, setting to None: {e}")
            user_id = None

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ip_address = _get_client_ip()

    # Track logging attempts for monitoring
    log_entry = {
        'user_id': user_id,
        'username': username,
        'action': action,
        'details': details,
        'timestamp': timestamp,
        'ip_address': ip_address
    }

    # Primary database logging attempt
    try:
        return _attempt_database_logging(db_path, log_entry)

    except sqlite3.OperationalError as e:
        return _handle_operational_error(db_path, e, log_entry)

    except sqlite3.IntegrityError as e:
        return _handle_integrity_error(db_path, e, log_entry)

    except sqlite3.DatabaseError as e:
        return _handle_database_error(e, log_entry)

    except sqlite3.Error as e:
        return _handle_sqlite_error(e, log_entry)

    except OSError as e:
        return _handle_os_error(e, log_entry)

    except MemoryError as e:
        return _handle_memory_error(e, log_entry)

    except Exception as e:
        return _handle_unexpected_error(db_path, e, log_entry)


def log_activity_with_connection(
    conn: sqlite3.Connection,
    username: str,
    action: str,
    details: Optional[str] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Log activity using an existing database connection with comprehensive error handling.

    Used when logging should be part of a larger transaction. Does not commit
    the connection - that responsibility lies with the caller.

    Parameters
    ----------
    conn : sqlite3.Connection
        Existing database connection to use
    username : str
        Username performing the action
    action : str
        Description of the action performed
    details : str, optional
        Additional details about the action
    user_id : int, optional
        User ID if available

    Returns
    -------
    dict
        Result dictionary with keys:
        - 'success': bool - Whether logging succeeded
        - 'error': str or None - Error type if failed
        - 'fallback': str or None - Fallback method used
        - 'method': str - Method used ('shared_connection' if successful)

    Notes
    -----
    This function does NOT commit the connection. The caller must handle
    transaction management.
    """
    # Input validation and sanitization
    if not conn:
        logging.error("Cannot log activity: database connection is None")
        return {'success': False, 'error': 'no_connection', 'fallback': None}

    if not username or not action:
        logging.warning("Activity logging skipped: username and action are required")
        return {'success': False, 'error': 'invalid_input', 'fallback': None}

    # Sanitize inputs to prevent issues
    try:
        username = str(username)[:255] if username else 'unknown'
        action = str(action)[:500] if action else 'unknown_action'
        details = str(details)[:1000] if details else None
        user_id = int(user_id) if user_id is not None else None
    except (ValueError, TypeError) as sanitize_error:
        logging.warning(f"Input sanitization warning: {sanitize_error}")
        username = 'sanitization_failed'
        action = 'sanitization_failed'
        details = f"Original error: {sanitize_error}"
        user_id = None

    # Prepare log entry
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ip_address = _get_client_ip()

    log_entry = {
        'user_id': user_id,
        'username': username,
        'action': action,
        'details': details,
        'timestamp': timestamp,
        'ip_address': ip_address
    }

    # Attempt database logging with the shared connection
    try:
        return _attempt_shared_connection_logging(conn, log_entry)

    except sqlite3.IntegrityError as e:
        return _handle_shared_connection_integrity_error(e, log_entry)

    except sqlite3.OperationalError as e:
        return _handle_shared_connection_operational_error(e, log_entry)

    except sqlite3.DatabaseError as e:
        return _handle_shared_connection_database_error(e, log_entry)

    except sqlite3.Error as e:
        return _handle_shared_connection_sqlite_error(e, log_entry)

    except AttributeError as e:
        return _handle_shared_connection_attribute_error(e, log_entry)

    except ValueError as e:
        return _handle_shared_connection_value_error(e, log_entry)

    except MemoryError as e:
        return _handle_shared_connection_memory_error(e, log_entry)

    except Exception as e:
        return _handle_shared_connection_unexpected_error(e, log_entry)


# ============================================================================
# Helper Functions - Primary Database Logging
# ============================================================================

def _attempt_database_logging(db_path: str, log_entry: Dict[str, Any]) -> bool:
    """Attempt to log to the primary database"""
    log_conn = None

    try:
        # Establish connection with optimized settings for logging
        log_conn = sqlite3.connect(db_path, timeout=5.0)
        log_conn.execute("PRAGMA busy_timeout = 5000")      # 5 second timeout
        log_conn.execute("PRAGMA journal_mode = WAL")       # WAL mode for better concurrency
        log_conn.execute("PRAGMA synchronous = NORMAL")     # Balance safety and speed

        cursor = log_conn.cursor()

        # Verify table exists before attempting insert
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
        if not cursor.fetchone():
            logging.error("Activity log table does not exist - cannot log activity")
            return _fallback_to_file_logging(log_entry, "Table does not exist")

        # Insert the log entry
        cursor.execute('''
            INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            log_entry['user_id'],
            log_entry['username'],
            log_entry['action'],
            log_entry['details'],
            log_entry['timestamp'],
            log_entry['ip_address']
        ))

        log_conn.commit()
        logging.debug(f"Activity logged successfully for user: {log_entry['username']}")
        return True

    finally:
        # Ensure connection is properly closed
        if log_conn:
            try:
                log_conn.close()
            except sqlite3.Error as close_error:
                logging.warning(f"Error closing log database connection: {close_error}")
            except Exception as close_error:
                logging.error(f"Unexpected error closing log connection: {type(close_error).__name__}: {close_error}")


def _retry_database_logging(db_path: str, log_entry: Dict[str, Any], reason: str) -> bool:
    """Retry database logging with reduced timeout and fallback"""
    logging.info(f"Retrying activity logging due to: {reason}")

    try:
        time.sleep(0.1)  # Brief pause before retry

        log_conn = sqlite3.connect(db_path, timeout=1.0)
        log_conn.execute("PRAGMA busy_timeout = 1000")  # Reduced timeout for retry
        cursor = log_conn.cursor()

        cursor.execute('''
            INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            log_entry['user_id'],
            log_entry['username'],
            log_entry['action'],
            log_entry['details'],
            log_entry['timestamp'],
            log_entry['ip_address']
        ))

        log_conn.commit()
        log_conn.close()

        logging.debug(f"Activity logging retry successful for {log_entry['username']}")
        return True

    except sqlite3.Error as retry_error:
        logging.warning(f"Activity logging retry failed: {retry_error}")
        return _fallback_to_file_logging(log_entry, f"retry_failed: {retry_error}")

    except Exception as retry_error:
        logging.error(f"Unexpected error during activity logging retry: {type(retry_error).__name__}: {retry_error}")
        return _fallback_to_file_logging(log_entry, f"retry_unexpected: {retry_error}")


# ============================================================================
# Helper Functions - Shared Connection Logging
# ============================================================================

def _attempt_shared_connection_logging(conn: sqlite3.Connection, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to log using the shared database connection"""
    try:
        # Verify connection is still valid
        if not _validate_shared_connection(conn):
            return {'success': False, 'error': 'invalid_connection', 'fallback': 'file_logged'}

        cursor = conn.cursor()

        # Verify activity_log table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log'")
        if not cursor.fetchone():
            logging.error("Activity log table does not exist in shared connection")
            return _fallback_shared_connection_logging(log_entry, "table_missing")

        # Check table schema compatibility
        cursor.execute("PRAGMA table_info(activity_log)")
        columns = [column[1] for column in cursor.fetchall()]
        required_columns = ['user_id', 'username', 'action', 'details', 'timestamp', 'ip_address']

        missing_columns = [col for col in required_columns if col not in columns]
        if missing_columns:
            logging.error(f"Activity log table missing required columns: {missing_columns}")
            return _fallback_shared_connection_logging(log_entry, f"missing_columns: {missing_columns}")

        # Perform the insert (don't commit - let caller handle transaction)
        cursor.execute('''
            INSERT INTO activity_log (user_id, username, action, details, timestamp, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            log_entry['user_id'],
            log_entry['username'],
            log_entry['action'],
            log_entry['details'],
            log_entry['timestamp'],
            log_entry['ip_address']
        ))

        logging.debug(f"Activity logged via shared connection for user: {log_entry['username']}")
        return {'success': True, 'error': None, 'fallback': None, 'method': 'shared_connection'}

    except sqlite3.Error as db_error:
        # Re-raise for specific handling by calling methods
        raise db_error
    except Exception as unexpected_error:
        # Re-raise for specific handling by calling methods
        raise unexpected_error


def _validate_shared_connection(conn: sqlite3.Connection) -> bool:
    """Validate that the shared connection is still usable"""
    try:
        # Test with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True

    except sqlite3.ProgrammingError as e:
        if "cannot operate on a closed database" in str(e).lower():
            logging.warning("Shared database connection is closed")
            return False
        else:
            logging.error(f"Programming error with shared connection: {e}")
            return False

    except sqlite3.Error as e:
        logging.warning(f"Shared database connection validation failed: {e}")
        return False

    except Exception as e:
        logging.error(f"Unexpected error validating shared connection: {type(e).__name__}: {e}")
        return False


# ============================================================================
# Error Handlers - Primary Logging
# ============================================================================

def _handle_operational_error(db_path: str, error: sqlite3.OperationalError, log_entry: Dict[str, Any]) -> bool:
    """Handle SQLite operational errors with specific strategies"""
    error_msg = str(error).lower()

    if "database is locked" in error_msg:
        logging.warning(f"Database locked during activity logging for {log_entry['username']}")
        return _retry_database_logging(db_path, log_entry, "database_locked")

    elif "disk i/o error" in error_msg:
        logging.error(f"Disk I/O error during activity logging: {error}")
        return _fallback_to_file_logging(log_entry, f"Disk I/O error: {error}")

    elif "permission denied" in error_msg:
        logging.error(f"Permission denied for activity logging: {error}")
        return _fallback_to_file_logging(log_entry, f"Permission denied: {error}")

    elif "no such table" in error_msg:
        logging.error(f"Activity log table missing: {error}")
        return _fallback_to_file_logging(log_entry, f"Table missing: {error}")

    elif "database disk image is malformed" in error_msg:
        logging.critical(f"Database corruption detected during activity logging: {error}")
        return _fallback_to_file_logging(log_entry, f"Database corruption: {error}")

    else:
        logging.error(f"Operational error during activity logging: {error}")
        return _retry_database_logging(db_path, log_entry, "operational_error")


def _handle_integrity_error(db_path: str, error: sqlite3.IntegrityError, log_entry: Dict[str, Any]) -> bool:
    """Handle database integrity constraint violations"""
    error_msg = str(error).lower()

    if "foreign key constraint failed" in error_msg:
        logging.warning(f"Foreign key constraint violation in activity log for user_id {log_entry['user_id']}: {error}")
        # Log without user_id to avoid constraint issues
        log_entry_copy = log_entry.copy()
        log_entry_copy['user_id'] = None
        return _attempt_database_logging(db_path, log_entry_copy)

    elif "unique constraint failed" in error_msg:
        logging.debug(f"Duplicate activity log entry detected for {log_entry['username']}")
        # This might be acceptable for some logging scenarios
        return True

    else:
        logging.error(f"Integrity constraint violation in activity logging: {error}")
        return _fallback_to_file_logging(log_entry, f"Integrity error: {error}")


def _handle_database_error(error: sqlite3.DatabaseError, log_entry: Dict[str, Any]) -> bool:
    """Handle general database errors"""
    logging.error(f"Database error during activity logging: {error}")
    return _fallback_to_file_logging(log_entry, f"Database error: {error}")


def _handle_sqlite_error(error: sqlite3.Error, log_entry: Dict[str, Any]) -> bool:
    """Handle general SQLite errors"""
    logging.error(f"SQLite error during activity logging: {error}")
    return _fallback_to_file_logging(log_entry, f"SQLite error: {error}")


def _handle_os_error(error: OSError, log_entry: Dict[str, Any]) -> bool:
    """Handle operating system errors"""
    error_msg = str(error).lower()

    if "disk full" in error_msg or "no space left" in error_msg:
        logging.critical(f"Disk space exhausted during activity logging: {error}")
        return _emergency_memory_logging(log_entry, f"Disk full: {error}")

    elif "permission denied" in error_msg:
        logging.error(f"File permission error during activity logging: {error}")
        return _fallback_to_alternate_location(log_entry, f"Permission error: {error}")

    else:
        logging.error(f"OS error during activity logging: {error}")
        return _fallback_to_file_logging(log_entry, f"OS error: {error}")


def _handle_memory_error(error: MemoryError, log_entry: Dict[str, Any]) -> bool:
    """Handle memory exhaustion errors"""
    logging.critical(f"Memory error during activity logging: {error}")
    # Try to log essential information only
    minimal_entry = {
        'username': log_entry['username'][:50],  # Truncate to essential data
        'action': log_entry['action'][:100],
        'timestamp': log_entry['timestamp']
    }
    return _emergency_memory_logging(minimal_entry, f"Memory error: {error}")


def _handle_unexpected_error(db_path: str, error: Exception, log_entry: Dict[str, Any]) -> bool:
    """Handle unexpected errors with comprehensive fallback"""
    error_type = type(error).__name__
    error_msg = str(error)

    logging.error(f"Unexpected error during activity logging: {error_type}: {error_msg}")

    # Try to determine if this is a recoverable error
    if any(keyword in error_msg.lower() for keyword in ['timeout', 'temporary', 'retry']):
        return _retry_database_logging(db_path, log_entry, f"unexpected_recoverable: {error_type}")
    else:
        return _fallback_to_file_logging(log_entry, f"unexpected_error: {error_type}: {error_msg}")


# ============================================================================
# Error Handlers - Shared Connection
# ============================================================================

def _handle_shared_connection_integrity_error(error: sqlite3.IntegrityError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle integrity constraint violations in shared connection"""
    error_msg = str(error).lower()

    if "foreign key constraint failed" in error_msg:
        logging.warning(f"Foreign key constraint in shared logging for user_id {log_entry['user_id']}: {error}")
        return _fallback_shared_connection_logging(log_entry, f"foreign_key: {error}")

    elif "unique constraint failed" in error_msg:
        logging.debug(f"Duplicate activity log entry for {log_entry['username']} in shared connection")
        return {'success': True, 'error': 'duplicate_entry', 'fallback': None, 'method': 'shared_connection'}

    else:
        logging.error(f"Integrity constraint violation in shared logging: {error}")
        return _fallback_shared_connection_logging(log_entry, f"integrity_error: {error}")


def _handle_shared_connection_operational_error(error: sqlite3.OperationalError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle operational errors in shared connection logging"""
    error_msg = str(error).lower()

    if "database is locked" in error_msg:
        logging.warning(f"Database locked during shared connection logging for {log_entry['username']}: {error}")
        return _fallback_shared_connection_logging(log_entry, f"shared_db_locked: {error}")

    elif "no such table" in error_msg:
        logging.error(f"Activity log table missing in shared connection: {error}")
        return _fallback_shared_connection_logging(log_entry, f"table_missing: {error}")

    else:
        logging.error(f"Operational error in shared connection logging: {error}")
        return _fallback_shared_connection_logging(log_entry, f"operational_error: {error}")


def _handle_shared_connection_database_error(error: sqlite3.DatabaseError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle general database errors in shared connection"""
    logging.error(f"Database error in shared connection logging: {error}")
    return _fallback_shared_connection_logging(log_entry, f"database_error: {error}")


def _handle_shared_connection_sqlite_error(error: sqlite3.Error, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle general SQLite errors in shared connection"""
    logging.error(f"SQLite error in shared connection logging: {error}")
    return _fallback_shared_connection_logging(log_entry, f"sqlite_error: {error}")


def _handle_shared_connection_attribute_error(error: AttributeError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle attribute errors (like connection object issues)"""
    logging.error(f"Attribute error in shared connection logging: {error}")
    return _fallback_shared_connection_logging(log_entry, f"attribute_error: {error}")


def _handle_shared_connection_value_error(error: ValueError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle value errors (like data type issues)"""
    logging.warning(f"Value error in shared connection logging: {error}")
    return _fallback_shared_connection_logging(log_entry, f"value_error: {error}")


def _handle_shared_connection_memory_error(error: MemoryError, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle memory errors in shared connection logging"""
    logging.critical(f"Memory error in shared connection logging: {error}")

    # Create minimal log entry to reduce memory usage
    minimal_entry = {
        'user_id': None,
        'username': log_entry['username'][:50] if log_entry.get('username') else 'unknown',
        'action': log_entry['action'][:50] if log_entry.get('action') else 'unknown',
        'details': None,
        'timestamp': log_entry.get('timestamp', ''),
        'ip_address': '127.0.0.1'
    }

    return _fallback_shared_connection_logging(minimal_entry, f"memory_error: {error}")


def _handle_shared_connection_unexpected_error(error: Exception, log_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Handle unexpected errors in shared connection logging"""
    error_type = type(error).__name__
    error_msg = str(error)

    logging.error(f"Unexpected error in shared connection logging: {error_type}: {error_msg}")
    return _fallback_shared_connection_logging(log_entry, f"unexpected_error: {error_type}: {error_msg}")


# ============================================================================
# Fallback Mechanisms
# ============================================================================

def _fallback_to_file_logging(log_entry: Dict[str, Any], reason: str) -> bool:
    """Fallback to file-based logging with comprehensive error handling"""
    backup_file = 'activity_backup.log'

    try:
        # Ensure backup directory exists
        backup_path = Path(backup_file)
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Format log entry for file output
        log_line = _format_log_entry_for_file(log_entry, reason)

        # Attempt to write to backup file with proper encoding
        with open(backup_file, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
            f.flush()  # Ensure data is written immediately

        logging.info(f"Activity logged to backup file for {log_entry['username']} (reason: {reason})")
        return True

    except PermissionError as perm_error:
        logging.error(f"Permission denied writing to backup log: {perm_error}")
        return _fallback_to_alternate_location(log_entry, f"backup_permission: {perm_error}")

    except OSError as os_error:
        logging.error(f"OS error writing to backup log: {os_error}")
        return _emergency_memory_logging(log_entry, f"backup_os_error: {os_error}")

    except UnicodeEncodeError as encoding_error:
        logging.warning(f"Encoding error in backup logging: {encoding_error}")
        # Try with ASCII encoding as fallback
        try:
            safe_log_line = _format_log_entry_for_file(log_entry, reason, safe_encoding=True)
            with open(backup_file, 'a', encoding='ascii', errors='replace') as f:
                f.write(safe_log_line + '\n')
                f.flush()
            logging.info(f"Activity logged to backup file with safe encoding for {log_entry['username']}")
            return True
        except Exception as safe_error:
            logging.error(f"Safe encoding backup also failed: {safe_error}")
            return _emergency_memory_logging(log_entry, f"encoding_fallback_failed: {safe_error}")

    except Exception as file_error:
        logging.error(f"Unexpected error in file backup logging: {type(file_error).__name__}: {file_error}")
        return _emergency_memory_logging(log_entry, f"file_backup_unexpected: {file_error}")


def _fallback_to_alternate_location(log_entry: Dict[str, Any], reason: str) -> bool:
    """Try alternative logging locations when primary backup fails"""
    alternate_locations = [
        str(paths.TEMP_DIR / 'activity_backup.log'),
        str(paths.LOG_DIR / 'activity_backup.log'),
        f'{os.path.expanduser("~")}/activity_backup.log'
    ]

    for alt_location in alternate_locations:
        try:
            alt_path = Path(alt_location)
            alt_path.parent.mkdir(parents=True, exist_ok=True)

            log_line = _format_log_entry_for_file(log_entry, reason)

            with open(alt_location, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
                f.flush()

            logging.info(f"Activity logged to alternate location {alt_location} for {log_entry['username']}")
            return True

        except Exception as alt_error:
            logging.debug(f"Alternate location {alt_location} failed: {alt_error}")
            continue

    # If all alternate locations fail
    logging.error(f"All alternate logging locations failed for {log_entry['username']}")
    return _emergency_memory_logging(log_entry, f"all_alternates_failed: {reason}")


def _emergency_memory_logging(log_entry: Dict[str, Any], reason: str) -> bool:
    """Emergency in-memory logging when all file operations fail"""
    global _emergency_log_buffer

    try:
        emergency_entry = {
            'timestamp': log_entry.get('timestamp'),
            'username': log_entry.get('username'),
            'action': log_entry.get('action'),
            'reason': reason
        }

        # Limit buffer size to prevent memory issues
        if len(_emergency_log_buffer) >= 1000:
            _emergency_log_buffer.pop(0)  # Remove oldest entry

        _emergency_log_buffer.append(emergency_entry)

        logging.warning(f"Activity logged to emergency memory buffer for {log_entry['username']} (reason: {reason})")
        return True

    except Exception as emergency_error:
        # Absolute last resort - log to Python's logging system only
        logging.critical(f"Emergency memory logging failed for {log_entry['username']}: {emergency_error}")
        logging.critical(f"Lost activity log: {log_entry['username']} performed {log_entry['action']} at {log_entry['timestamp']}")
        return False


def _fallback_shared_connection_logging(log_entry: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Fallback logging when shared connection fails"""
    global _shared_connection_fallback_buffer

    fallback_methods = [
        ('file_logging', lambda: _fallback_to_file_logging(log_entry, reason)),
        ('memory_buffer', lambda: _attempt_fallback_memory_logging(log_entry, reason))
    ]

    for method_name, method_func in fallback_methods:
        try:
            if method_func():
                return {
                    'success': False,
                    'error': 'shared_connection_failed',
                    'fallback': method_name,
                    'reason': reason
                }
        except Exception as fallback_error:
            logging.debug(f"Fallback method {method_name} failed: {fallback_error}")
            continue

    # If all fallbacks fail
    logging.error(f"All fallback methods failed for shared connection logging: {reason}")
    return {
        'success': False,
        'error': 'all_fallbacks_failed',
        'fallback': None,
        'reason': reason
    }


def _attempt_fallback_memory_logging(log_entry: Dict[str, Any], reason: str) -> bool:
    """Attempt to log to memory buffer as fallback"""
    global _shared_connection_fallback_buffer

    try:
        # Limit buffer size
        if len(_shared_connection_fallback_buffer) >= 500:
            _shared_connection_fallback_buffer.pop(0)

        buffer_entry = {
            'timestamp': log_entry.get('timestamp'),
            'username': log_entry.get('username'),
            'action': log_entry.get('action'),
            'reason': reason
        }

        _shared_connection_fallback_buffer.append(buffer_entry)
        logging.info(f"Shared connection fallback logged to memory for {log_entry['username']}")
        return True

    except Exception as memory_error:
        logging.debug(f"Memory fallback logging failed: {memory_error}")
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def _format_log_entry_for_file(log_entry: Dict[str, Any], reason: str, safe_encoding: bool = False) -> str:
    """Format log entry for file output with optional safe encoding"""
    if safe_encoding:
        # Use safe ASCII characters only
        username = ''.join(c if ord(c) < 128 else '?' for c in log_entry.get('username', ''))
        action = ''.join(c if ord(c) < 128 else '?' for c in log_entry.get('action', ''))
        details = ''.join(c if ord(c) < 128 else '?' for c in log_entry.get('details', '')) if log_entry.get('details') else 'None'
    else:
        username = log_entry.get('username', 'unknown')
        action = log_entry.get('action', 'unknown')
        details = log_entry.get('details') or 'None'

    return f"{log_entry.get('timestamp')} - {username}: {action} - {details} - IP: {log_entry.get('ip_address', 'unknown')} - Reason: {reason}"


def _get_client_ip() -> str:
    """Get client IP address with fallback for different environments"""
    # In a real web application, you would extract this from the request
    # For now, return localhost but make it extensible
    try:
        # This could be extended to get real IP from web frameworks
        # like Flask (request.remote_addr) or Django (request.META['REMOTE_ADDR'])
        return "127.0.0.1"
    except Exception:
        return "unknown"


# ============================================================================
# Public Buffer Access Functions
# ============================================================================

def get_emergency_log_buffer() -> List[Dict[str, Any]]:
    """
    Retrieve emergency log buffer for manual processing.

    Returns
    -------
    list of dict
        List of log entries that were buffered in memory
    """
    return _emergency_log_buffer.copy()


def clear_emergency_log_buffer() -> None:
    """Clear the emergency log buffer after processing"""
    global _emergency_log_buffer
    _emergency_log_buffer.clear()
    logging.info("Emergency log buffer cleared")


def get_shared_connection_fallback_buffer() -> List[Dict[str, Any]]:
    """
    Retrieve the shared connection fallback buffer for manual processing.

    Returns
    -------
    list of dict
        List of log entries that failed with shared connections
    """
    return _shared_connection_fallback_buffer.copy()


def clear_shared_connection_fallback_buffer() -> None:
    """Clear the shared connection fallback buffer after processing"""
    global _shared_connection_fallback_buffer
    _shared_connection_fallback_buffer.clear()
    logging.info("Shared connection fallback buffer cleared")
