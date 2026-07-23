"""
Audit logging utilities.
"""

import datetime
import json
import logging
import time
import re
import os
import hashlib
import mimetypes
import base64
import secrets
import traceback
from typing import Optional, List, Dict, Any
from functools import wraps

from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.post_18.university_system.infrastructure.email.email_manager import send_email
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.post_18.university_system.infrastructure.logging.log_config import get_log_file

from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import auth as _auth_mod
from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.auth import get_current_user_safe, require_auth, has_staff_permissions

logger = logging.getLogger(__name__)

def _log_audit(audit_data: Dict[str, Any]):
    """Log audit trail information"""
    conn = None
    try:
        conn = sqlite3.connect(SUPPORT_DB, timeout=10)
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO audit_trail (
            user_id, action, resource_type, resource_id, old_values,
            new_values, success, error_message, duration, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            audit_data.get('user', 'system'),
            audit_data.get('action'),
            audit_data.get('function', 'unknown'),
            audit_data.get('resource_id'),
            json.dumps(audit_data.get('old_values', {})),
            json.dumps(audit_data.get('new_values', {})),
            audit_data.get('success', True),
            audit_data.get('error'),
            audit_data.get('duration', 0),
            audit_data.get('timestamp')
        ))

        conn.commit()

    except Exception as e:
        logger.error(f"Failed to log audit trail: {e}")
    finally:
        if conn:
            conn.close()

def audit_action(action_type: str):
    """
    Decorator that creates an audit trail for support operations.

    Wraps a function to automatically log audit information before and
    after execution, including success/failure status, duration, and
    user attribution. Supports compliance requirements by maintaining
    a complete record of all support system actions.

    Parameters
    ----------
    action_type : str
        A descriptive name for the action being audited (e.g., 'create_ticket',
        'assign_staff', 'close_ticket'). This is stored in the audit log.

    Returns
    -------
    Callable
        Decorated function with audit logging.

    Examples
    --------
    >>> @audit_action('create_ticket')
    ... def create_support_ticket(self, subject, description):
    ...     # Implementation
    ...     return ticket_id
    ...
    >>> # When called, automatically logs:
    >>> # - Action type: 'create_ticket'
    >>> # - Function: 'create_support_ticket'
    >>> # - User: current authenticated user
    >>> # - Duration: execution time
    >>> # - Success/failure status

    Notes
    -----
    Audit data includes:
    - action: The action_type parameter
    - function: The decorated function's name
    - user: Current user's username or 'system'
    - success: Boolean indicating completion status
    - duration: Execution time in seconds
    - timestamp: ISO format timestamp
    - error: Exception message (if failed)

    The decorator attempts to store audit data via the object's _log_audit
    method if available. All actions are also logged via the module logger.

    See Also
    --------
    log_activity : General activity logging utility.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Log successful action
                audit_data = {
                    'action': action_type,
                    'function': func.__name__,
                    'user': _auth_mod.auth.current_user['username'] if _auth_mod.auth and _auth_mod.auth.current_user else 'system',
                    'success': True,
                    'duration': duration,
                    'timestamp': datetime.datetime.now().isoformat()
                }

                # Store in audit table
                if args and hasattr(args[0], '_log_audit'):
                    args[0]._log_audit(audit_data)
                else:
                    # Use module-level _log_audit if no object method exists
                    _log_audit(audit_data)

                logger.info(f"Action {action_type} completed successfully in {duration:.2f}s")
                return result

            except Exception as e:
                duration = time.time() - start_time

                # Log failed action
                audit_data = {
                    'action': action_type,
                    'function': func.__name__,
                    'user': _auth_mod.auth.current_user['username'] if _auth_mod.auth and _auth_mod.auth.current_user else 'system',
                    'success': False,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': datetime.datetime.now().isoformat()
                }

                if args and hasattr(args[0], '_log_audit'):
                    args[0]._log_audit(audit_data)
                else:
                    # Use module-level _log_audit if no object method exists
                    _log_audit(audit_data)

                logger.error(f"Action {action_type} failed after {duration:.2f}s: {e}")
                raise

        return wrapper
    return decorator
