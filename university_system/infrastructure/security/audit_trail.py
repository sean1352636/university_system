"""
Comprehensive Audit Trail for the University System.

Provides decorator-based automatic logging of data access and modifications
with configurable detail levels and compliance-focused features.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import logging
import sqlite3
import threading
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Types of auditable actions."""
    ACCESS = 'access'
    CREATE = 'create'
    READ = 'read'
    UPDATE = 'update'
    DELETE = 'delete'
    EXPORT = 'export'
    IMPORT = 'import'
    LOGIN = 'login'
    LOGOUT = 'logout'
    PERMISSION_CHANGE = 'permission_change'
    CONFIG_CHANGE = 'config_change'


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: datetime
    action: str
    resource_type: str
    resource_id: Optional[str]
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    function_name: Optional[str] = None
    module_name: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    data_hash: Optional[str] = None  # For integrity verification

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'details': self.details,
            'function_name': self.function_name,
            'module_name': self.module_name,
            'success': self.success,
            'error_message': self.error_message,
            'data_hash': self.data_hash,
        }


class AuditLogger:
    """
    Thread-safe audit logger with database persistence.

    Provides comprehensive audit logging for compliance and security.
    """

    _instance: Optional['AuditLogger'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.db_path = db_path or DEFAULT_DB_PATH
        self._user_context = threading.local()
        self._init_db()
        self._initialized = True

        logger.info("AuditLogger initialized")

    # Use a dedicated table name to avoid conflicts with existing audit_log
    TABLE_NAME = 'audit_trail'

    def _init_db(self) -> None:
        """Initialize audit trail tables."""
        # TABLE_NAME is a class constant, not user input, but use bracket quoting for consistency
        with get_connection(self.db_path) as conn:
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS [{self.TABLE_NAME}] (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    user_id INTEGER,
                    username TEXT,
                    ip_address TEXT,
                    details TEXT,
                    function_name TEXT,
                    module_name TEXT,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    data_hash TEXT
                )
            ''')
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp
                ON [{self.TABLE_NAME}](timestamp DESC)
            ''')
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_audit_trail_user
                ON [{self.TABLE_NAME}](user_id, timestamp DESC)
            ''')
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_audit_trail_resource
                ON [{self.TABLE_NAME}](resource_type, resource_id)
            ''')
            conn.execute(f'''
                CREATE INDEX IF NOT EXISTS idx_audit_trail_action
                ON [{self.TABLE_NAME}](action, timestamp DESC)
            ''')
            conn.commit()

    def set_user_context(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """Set current user context for audit logging."""
        self._user_context.user_id = user_id
        self._user_context.username = username
        self._user_context.ip_address = ip_address

    def clear_user_context(self) -> None:
        """Clear current user context."""
        self._user_context.user_id = None
        self._user_context.username = None
        self._user_context.ip_address = None

    def get_user_context(self) -> Dict[str, Any]:
        """Get current user context."""
        return {
            'user_id': getattr(self._user_context, 'user_id', None),
            'username': getattr(self._user_context, 'username', None),
            'ip_address': getattr(self._user_context, 'ip_address', None),
        }

    @contextmanager
    def user_context(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Context manager for setting user context."""
        old_context = self.get_user_context()
        self.set_user_context(user_id, username, ip_address)
        try:
            yield
        finally:
            self.set_user_context(**old_context)

    def _compute_data_hash(self, data: Any) -> str:
        """Compute hash for data integrity verification."""
        if data is None:
            return ""
        try:
            json_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.sha256(json_str.encode()).hexdigest()[:16]
        except Exception:
            return ""

    def log(
        self,
        action: Union[AuditAction, str],
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        function_name: Optional[str] = None,
        module_name: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        data_for_hash: Any = None,
    ) -> int:
        """
        Log an audit entry.

        Args:
            action: The action performed
            resource_type: Type of resource accessed/modified
            resource_id: Identifier of the resource
            user_id: User who performed the action (uses context if not provided)
            username: Username (uses context if not provided)
            ip_address: IP address (uses context if not provided)
            details: Additional details to log
            function_name: Name of the function
            module_name: Name of the module
            success: Whether the action succeeded
            error_message: Error message if failed
            data_for_hash: Data to hash for integrity

        Returns:
            The audit log entry ID
        """
        context = self.get_user_context()

        action_str = action.value if isinstance(action, AuditAction) else action

        entry = AuditEntry(
            timestamp=datetime.now(),
            action=action_str,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            user_id=user_id or context.get('user_id'),
            username=username or context.get('username'),
            ip_address=ip_address or context.get('ip_address'),
            details=details or {},
            function_name=function_name,
            module_name=module_name,
            success=success,
            error_message=error_message,
            data_hash=self._compute_data_hash(data_for_hash) if data_for_hash else None,
        )

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(f'''
                INSERT INTO [{self.TABLE_NAME}]
                (timestamp, action, resource_type, resource_id, user_id, username,
                 ip_address, details, function_name, module_name, success,
                 error_message, data_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.timestamp.isoformat(),
                entry.action,
                entry.resource_type,
                entry.resource_id,
                entry.user_id,
                entry.username,
                entry.ip_address,
                json.dumps(entry.details),
                entry.function_name,
                entry.module_name,
                1 if entry.success else 0,
                entry.error_message,
                entry.data_hash,
            ))
            conn.commit()

            return cursor.lastrowid

    def query(
        self,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[int] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEntry]:
        """
        Query audit log entries.

        Args:
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            user_id: Filter by user ID
            since: Filter entries after this time
            until: Filter entries before this time
            success_only: Filter by success status
            limit: Maximum entries to return
            offset: Offset for pagination

        Returns:
            List of AuditEntry objects
        """
        conditions = []
        params = []

        if action:
            conditions.append("action = ?")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if resource_id:
            conditions.append("resource_id = ?")
            params.append(resource_id)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())
        if until:
            conditions.append("timestamp <= ?")
            params.append(until.isoformat())
        if success_only is not None:
            conditions.append("success = ?")
            params.append(1 if success_only else 0)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f'''
            SELECT timestamp, action, resource_type, resource_id, user_id,
                   username, ip_address, details, function_name, module_name,
                   success, error_message, data_hash
            FROM [{self.TABLE_NAME}]
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        '''
        params.extend([limit, offset])

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, params)

            entries = []
            for row in cursor.fetchall():
                entries.append(AuditEntry(
                    timestamp=datetime.fromisoformat(row[0]),
                    action=row[1],
                    resource_type=row[2],
                    resource_id=row[3],
                    user_id=row[4],
                    username=row[5],
                    ip_address=row[6],
                    details=json.loads(row[7]) if row[7] else {},
                    function_name=row[8],
                    module_name=row[9],
                    success=bool(row[10]),
                    error_message=row[11],
                    data_hash=row[12],
                ))

            return entries

    def get_user_activity(
        self,
        user_id: int,
        days: int = 30,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Get recent activity for a specific user."""
        since = datetime.now() - timedelta(days=days)
        return self.query(user_id=user_id, since=since, limit=limit)

    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Get history of changes to a specific resource."""
        return self.query(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )

    def get_failed_operations(
        self,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Get failed operations for security analysis."""
        if since is None:
            since = datetime.now() - timedelta(days=7)
        return self.query(success_only=False, since=since, limit=limit)


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Type variable for decorator
F = TypeVar('F', bound=Callable[..., Any])


def audit_data_access(
    resource_type: str,
    action: Union[AuditAction, str] = AuditAction.ACCESS,
    resource_id_param: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to automatically log data access.

    Args:
        resource_type: Type of resource being accessed
        action: The action being performed
        resource_id_param: Name of parameter containing resource ID
        log_args: Include function arguments in log
        log_result: Include function result in log

    Example:
        >>> @audit_data_access('student_records')
        ... def get_student_transcript(student_id: str) -> Transcript:
        ...     ...
        >>>
        >>> @audit_data_access('course', action=AuditAction.UPDATE, resource_id_param='course_id')
        ... def update_course(course_id: str, data: dict):
        ...     ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            audit = get_audit_logger()
            action_str = action.value if isinstance(action, AuditAction) else action

            # Try to get resource ID from parameters
            resource_id = None
            if resource_id_param:
                # Check kwargs first
                if resource_id_param in kwargs:
                    resource_id = kwargs[resource_id_param]
                else:
                    # Try to get from positional args
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    if resource_id_param in params:
                        idx = params.index(resource_id_param)
                        if idx < len(args):
                            resource_id = args[idx]

            # Build details
            details = {'function': func.__name__}
            if log_args:
                # Sanitize args (don't log sensitive data)
                safe_kwargs = {
                    k: str(v)[:100] if not any(s in k.lower() for s in ['password', 'secret', 'token', 'key']) else '***'
                    for k, v in kwargs.items()
                }
                details['args'] = safe_kwargs

            module_name = func.__module__ if hasattr(func, '__module__') else None

            # Execute function
            success = True
            error_message = None
            result = None

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                success = False
                error_message = str(e)[:500]
                raise

            finally:
                # Log result if requested
                if log_result and result is not None:
                    details['result_type'] = type(result).__name__
                    if isinstance(result, (list, tuple)):
                        details['result_count'] = len(result)

                audit.log(
                    action=action_str,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id else None,
                    details=details,
                    function_name=func.__name__,
                    module_name=module_name,
                    success=success,
                    error_message=error_message,
                )

        return wrapper  # type: ignore
    return decorator


def log_activity(
    action: Union[AuditAction, str],
    resource: str,
    user_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Convenience function to log an activity.

    Args:
        action: Action type
        resource: Resource being accessed
        user_id: Optional user ID
        details: Optional additional details

    Returns:
        Audit log entry ID
    """
    audit = get_audit_logger()
    return audit.log(
        action=action,
        resource_type=resource,
        user_id=user_id,
        details=details,
    )


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get current user from shared context.

    Returns user info dict or None.
    """
    try:
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except (ImportError, Exception):
        pass
    return None


__all__ = [
    'AuditLogger',
    'AuditEntry',
    'AuditAction',
    'audit_data_access',
    'log_activity',
    'get_audit_logger',
    'get_current_user',
]
