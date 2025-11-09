import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter.font as tkFont
from tkinter import scrolledtext
from datetime import datetime, timedelta
import threading
import queue
import json
import os
from typing import Dict, Any, Optional, List, Tuple, Callable
import logging
import platform
import re
import uuid
import hashlib
import secrets
from functools import wraps
from urllib.parse import urlparse

# Import the original calendar functionality
from university_system.modules.domain.academics.services.academic_calendar import (
    AcademicCalendarManager, CalendarConfig, CalendarError, ValidationError,
    DatabaseError, PermissionError, display_academic_calendar_menu,
    handle_add_event, handle_update_event, handle_delete_event,
    handle_view_calendar, handle_export_calendar, auth, set_auth
)

# Import central auth system
try:
    from university_system.infrastructure.auth.user_authentication import _current_auth_instance
    CENTRAL_AUTH_AVAILABLE = True
except ImportError:
    _current_auth_instance = None
    CENTRAL_AUTH_AVAILABLE = False

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Configure logging for GUI
gui_logger = logging.getLogger('calendar_gui')

# ============================================================================
# CUSTOM ERROR CLASSES WITH DETAILED ERROR TRACKING
# ============================================================================

class CalendarError(Exception):
    """
    Base error class for Academic Calendar operations with detailed tracking

    Provides:
    - Unique error codes
    - User-friendly messages
    - Automatic logging
    - Context tracking
    - JSON serialization
    """

    def __init__(self, message: str, error_type: str = "CALENDAR_ERROR",
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize calendar error

        Args:
            message: Error message
            error_type: Type of error (used for error code generation)
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.context = context or {}
        self.timestamp = datetime.now()
        self.error_code = self._generate_error_code()
        self.user_message = self._generate_user_message()
        self._log_error()

    def _generate_error_code(self) -> str:
        """
        Generate unique error code

        Format: ERR-{TYPE}-{TIMESTAMP}
        Example: ERR-CALENDAR-20250109143022

        Returns:
            str: Unique error code
        """
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        return f"ERR-{self.error_type}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """
        Generate user-friendly error message

        Returns:
            str: User-friendly message with error code
        """
        return f"{self.message}\n\nError Code: {self.error_code}\nTime: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    def _log_error(self) -> None:
        """Log error with full context"""
        gui_logger.error(
            f"{self.error_code} - {self.message}",
            extra={
                'error_type': self.error_type,
                'context': self.context,
                'timestamp': self.timestamp.isoformat()
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to dictionary for serialization

        Returns:
            Dict: Error information as dictionary
        """
        return {
            'error_code': self.error_code,
            'error_type': self.error_type,
            'message': self.message,
            'user_message': self.user_message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }

    def add_context(self, key: str, value: Any) -> 'CalendarError':
        """
        Add additional context to error

        Args:
            key: Context key
            value: Context value

        Returns:
            CalendarError: Self for method chaining
        """
        self.context[key] = value
        return self


class ValidationError(CalendarError):
    """
    Validation error for input validation failures

    Handles:
    - Required field validation
    - Format validation
    - Range validation
    """

    def __init__(self, message: str, field: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize validation error

        Args:
            message: Error message
            field: Field name that failed validation
            context: Additional context
        """
        if context is None:
            context = {}
        if field:
            context['field'] = field
        super().__init__(message, "VALIDATION", context)

    def _generate_error_code(self) -> str:
        """Generate validation-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        field = self.context.get('field', 'UNKNOWN')
        return f"ERR-VAL-{field.upper()}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly validation message"""
        field = self.context.get('field', 'field')
        return f"Validation Error: {self.message}\n\nField: {field}\nError Code: {self.error_code}"

    @classmethod
    def required_field(cls, field: str) -> 'ValidationError':
        """
        Create error for missing required field

        Args:
            field: Name of required field

        Returns:
            ValidationError: Configured error instance
        """
        return cls(
            f"Required field '{field}' is missing or empty",
            field=field,
            context={'validation_type': 'required'}
        )

    @classmethod
    def invalid_format(cls, field: str, expected_format: str,
                      actual_value: Any = None) -> 'ValidationError':
        """
        Create error for invalid format

        Args:
            field: Field name
            expected_format: Expected format description
            actual_value: Actual value provided

        Returns:
            ValidationError: Configured error instance
        """
        context = {
            'validation_type': 'format',
            'expected_format': expected_format
        }
        if actual_value is not None:
            context['actual_value'] = str(actual_value)

        return cls(
            f"Field '{field}' has invalid format. Expected: {expected_format}",
            field=field,
            context=context
        )

    @classmethod
    def out_of_range(cls, field: str, min_value: Any = None,
                     max_value: Any = None, actual_value: Any = None) -> 'ValidationError':
        """
        Create error for out of range value

        Args:
            field: Field name
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            actual_value: Actual value provided

        Returns:
            ValidationError: Configured error instance
        """
        context = {'validation_type': 'range'}

        range_msg = []
        if min_value is not None:
            context['min_value'] = str(min_value)
            range_msg.append(f"min: {min_value}")
        if max_value is not None:
            context['max_value'] = str(max_value)
            range_msg.append(f"max: {max_value}")
        if actual_value is not None:
            context['actual_value'] = str(actual_value)

        range_str = ", ".join(range_msg)
        return cls(
            f"Field '{field}' is out of range. Valid range: {range_str}",
            field=field,
            context=context
        )


class DatabaseError(CalendarError):
    """
    Database error for database operation failures

    Handles:
    - Connection failures
    - Constraint violations
    - Record not found errors
    """

    def __init__(self, message: str, operation: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize database error

        Args:
            message: Error message
            operation: Database operation that failed
            context: Additional context
        """
        if context is None:
            context = {}
        if operation:
            context['operation'] = operation
        super().__init__(message, "DATABASE", context)

    def _generate_error_code(self) -> str:
        """Generate database-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        operation = self.context.get('operation', 'UNKNOWN')
        return f"ERR-DB-{operation.upper()}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly database message"""
        operation = self.context.get('operation', 'operation')
        return f"Database Error: Failed to {operation}\n\n{self.message}\n\nError Code: {self.error_code}"

    @classmethod
    def connection_failed(cls, reason: Optional[str] = None) -> 'DatabaseError':
        """
        Create error for database connection failure

        Args:
            reason: Reason for connection failure

        Returns:
            DatabaseError: Configured error instance
        """
        message = "Failed to connect to database"
        if reason:
            message += f": {reason}"

        return cls(
            message,
            operation="connect",
            context={'error_type': 'connection'}
        )

    @classmethod
    def constraint_violation(cls, constraint: str, table: Optional[str] = None) -> 'DatabaseError':
        """
        Create error for constraint violation

        Args:
            constraint: Constraint that was violated
            table: Table name

        Returns:
            DatabaseError: Configured error instance
        """
        context = {
            'error_type': 'constraint',
            'constraint': constraint
        }
        if table:
            context['table'] = table

        message = f"Database constraint violation: {constraint}"
        if table:
            message += f" on table '{table}'"

        return cls(message, operation="insert/update", context=context)

    @classmethod
    def record_not_found(cls, record_type: str, identifier: Any) -> 'DatabaseError':
        """
        Create error for record not found

        Args:
            record_type: Type of record (e.g., 'event', 'user')
            identifier: Record identifier

        Returns:
            DatabaseError: Configured error instance
        """
        return cls(
            f"{record_type.capitalize()} not found: {identifier}",
            operation="select",
            context={
                'error_type': 'not_found',
                'record_type': record_type,
                'identifier': str(identifier)
            }
        )


class AuthenticationError(CalendarError):
    """
    Authentication error for login/session failures

    Handles:
    - Invalid credentials
    - Session expiration
    - Account lockout
    """

    def __init__(self, message: str, username: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize authentication error

        Args:
            message: Error message
            username: Username attempting authentication
            context: Additional context
        """
        if context is None:
            context = {}
        if username:
            context['username'] = username
        super().__init__(message, "AUTH", context)

    def _generate_error_code(self) -> str:
        """Generate authentication-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        return f"ERR-AUTH-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly authentication message"""
        # Don't expose username in user message for security
        return f"Authentication Error: {self.message}\n\nError Code: {self.error_code}\n\nPlease contact support if the issue persists."

    @classmethod
    def invalid_credentials(cls, username: Optional[str] = None) -> 'AuthenticationError':
        """
        Create error for invalid credentials

        Args:
            username: Username that failed authentication

        Returns:
            AuthenticationError: Configured error instance
        """
        return cls(
            "Invalid username or password",
            username=username,
            context={'error_type': 'invalid_credentials'}
        )

    @classmethod
    def session_expired(cls, username: Optional[str] = None) -> 'AuthenticationError':
        """
        Create error for expired session

        Args:
            username: Username with expired session

        Returns:
            AuthenticationError: Configured error instance
        """
        return cls(
            "Your session has expired. Please log in again.",
            username=username,
            context={'error_type': 'session_expired'}
        )

    @classmethod
    def account_locked(cls, username: str, reason: Optional[str] = None) -> 'AuthenticationError':
        """
        Create error for locked account

        Args:
            username: Locked username
            reason: Reason for lockout

        Returns:
            AuthenticationError: Configured error instance
        """
        message = f"Account is locked"
        if reason:
            message += f": {reason}"

        context = {'error_type': 'account_locked'}
        if reason:
            context['reason'] = reason

        return cls(message, username=username, context=context)


class PermissionError(CalendarError):
    """
    Permission error for authorization failures

    Handles:
    - Insufficient role/permissions
    - Resource access denied
    """

    def __init__(self, message: str, required_permission: Optional[str] = None,
                 user_role: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize permission error

        Args:
            message: Error message
            required_permission: Permission that was required
            user_role: User's actual role
            context: Additional context
        """
        if context is None:
            context = {}
        if required_permission:
            context['required_permission'] = required_permission
        if user_role:
            context['user_role'] = user_role
        super().__init__(message, "PERMISSION", context)

    def _generate_error_code(self) -> str:
        """Generate permission-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        permission = self.context.get('required_permission', 'UNKNOWN')
        return f"ERR-PERM-{permission.upper()}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly permission message"""
        return f"Access Denied: {self.message}\n\nError Code: {self.error_code}\n\nContact your administrator for access."

    @classmethod
    def insufficient_role(cls, required_role: str, user_role: Optional[str] = None) -> 'PermissionError':
        """
        Create error for insufficient role

        Args:
            required_role: Role required for operation
            user_role: User's actual role

        Returns:
            PermissionError: Configured error instance
        """
        message = f"Insufficient permissions. Required role: {required_role}"
        if user_role:
            message += f". Your role: {user_role}"

        return cls(
            message,
            required_permission=required_role,
            user_role=user_role,
            context={'error_type': 'insufficient_role'}
        )

    @classmethod
    def resource_access_denied(cls, resource: str, action: str,
                              required_permission: Optional[str] = None) -> 'PermissionError':
        """
        Create error for resource access denial

        Args:
            resource: Resource being accessed
            action: Action being attempted
            required_permission: Permission required

        Returns:
            PermissionError: Configured error instance
        """
        message = f"You do not have permission to {action} {resource}"

        context = {
            'error_type': 'resource_access_denied',
            'resource': resource,
            'action': action
        }

        return cls(
            message,
            required_permission=required_permission,
            context=context
        )


class ExportError(CalendarError):
    """
    Export error for data export failures

    Handles:
    - File write failures
    - Data too large
    - Unsupported formats
    """

    def __init__(self, message: str, export_format: Optional[str] = None,
                 file_path: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize export error

        Args:
            message: Error message
            export_format: Export format (e.g., 'CSV', 'PDF')
            file_path: Target file path
            context: Additional context
        """
        if context is None:
            context = {}
        if export_format:
            context['export_format'] = export_format
        if file_path:
            context['file_path'] = file_path
        super().__init__(message, "EXPORT", context)

    def _generate_error_code(self) -> str:
        """Generate export-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        format_type = self.context.get('export_format', 'UNKNOWN')
        return f"ERR-EXPORT-{format_type.upper()}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly export message"""
        format_type = self.context.get('export_format', 'file')
        return f"Export Failed: Unable to export {format_type}\n\n{self.message}\n\nError Code: {self.error_code}"

    @classmethod
    def file_write_failed(cls, file_path: str, reason: Optional[str] = None) -> 'ExportError':
        """
        Create error for file write failure

        Args:
            file_path: Path where write failed
            reason: Reason for failure

        Returns:
            ExportError: Configured error instance
        """
        message = f"Failed to write file: {file_path}"
        if reason:
            message += f". Reason: {reason}"

        context = {'error_type': 'file_write_failed'}
        if reason:
            context['reason'] = reason

        return cls(message, file_path=file_path, context=context)

    @classmethod
    def data_too_large(cls, export_format: str, size: int, max_size: int) -> 'ExportError':
        """
        Create error for data too large to export

        Args:
            export_format: Format being exported to
            size: Actual data size
            max_size: Maximum allowed size

        Returns:
            ExportError: Configured error instance
        """
        return cls(
            f"Data size ({size} bytes) exceeds maximum allowed size ({max_size} bytes) for {export_format} export",
            export_format=export_format,
            context={
                'error_type': 'data_too_large',
                'size': size,
                'max_size': max_size
            }
        )

    @classmethod
    def unsupported_format(cls, requested_format: str,
                          supported_formats: Optional[List[str]] = None) -> 'ExportError':
        """
        Create error for unsupported export format

        Args:
            requested_format: Format that was requested
            supported_formats: List of supported formats

        Returns:
            ExportError: Configured error instance
        """
        message = f"Unsupported export format: {requested_format}"
        context = {'error_type': 'unsupported_format'}

        if supported_formats:
            message += f". Supported formats: {', '.join(supported_formats)}"
            context['supported_formats'] = supported_formats

        return cls(
            message,
            export_format=requested_format,
            context=context
        )


class SyncError(CalendarError):
    """
    Synchronization error for data sync failures

    Handles:
    - Connection failures
    - Data conflicts
    - Partial sync failures
    """

    def __init__(self, message: str, sync_source: Optional[str] = None,
                 sync_target: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        """
        Initialize sync error

        Args:
            message: Error message
            sync_source: Source of sync operation
            sync_target: Target of sync operation
            context: Additional context
        """
        if context is None:
            context = {}
        if sync_source:
            context['sync_source'] = sync_source
        if sync_target:
            context['sync_target'] = sync_target
        super().__init__(message, "SYNC", context)

    def _generate_error_code(self) -> str:
        """Generate sync-specific error code"""
        timestamp_str = self.timestamp.strftime("%Y%m%d%H%M%S")
        source = self.context.get('sync_source', 'UNKNOWN')
        return f"ERR-SYNC-{source.upper()}-{timestamp_str}"

    def _generate_user_message(self) -> str:
        """Generate user-friendly sync message"""
        source = self.context.get('sync_source', 'source')
        target = self.context.get('sync_target', 'target')
        return f"Synchronization Failed: {source} → {target}\n\n{self.message}\n\nError Code: {self.error_code}"

    @classmethod
    def connection_failed(cls, sync_source: str, reason: Optional[str] = None) -> 'SyncError':
        """
        Create error for sync connection failure

        Args:
            sync_source: Source that failed to connect
            reason: Reason for failure

        Returns:
            SyncError: Configured error instance
        """
        message = f"Failed to connect to {sync_source}"
        if reason:
            message += f": {reason}"

        context = {'error_type': 'connection_failed'}
        if reason:
            context['reason'] = reason

        return cls(message, sync_source=sync_source, context=context)

    @classmethod
    def data_conflict(cls, sync_source: str, sync_target: str,
                     conflicting_records: Optional[List[str]] = None) -> 'SyncError':
        """
        Create error for data conflict during sync

        Args:
            sync_source: Sync source
            sync_target: Sync target
            conflicting_records: List of conflicting record IDs

        Returns:
            SyncError: Configured error instance
        """
        message = f"Data conflict detected between {sync_source} and {sync_target}"
        context = {'error_type': 'data_conflict'}

        if conflicting_records:
            message += f". Conflicting records: {len(conflicting_records)}"
            context['conflicting_records'] = conflicting_records
            context['conflict_count'] = len(conflicting_records)

        return cls(
            message,
            sync_source=sync_source,
            sync_target=sync_target,
            context=context
        )

    @classmethod
    def partial_sync(cls, sync_source: str, sync_target: str,
                    successful: int, failed: int,
                    failed_records: Optional[List[str]] = None) -> 'SyncError':
        """
        Create error for partial sync completion

        Args:
            sync_source: Sync source
            sync_target: Sync target
            successful: Number of successful syncs
            failed: Number of failed syncs
            failed_records: List of failed record IDs

        Returns:
            SyncError: Configured error instance
        """
        message = f"Partial sync completed: {successful} succeeded, {failed} failed"

        context = {
            'error_type': 'partial_sync',
            'successful_count': successful,
            'failed_count': failed
        }

        if failed_records:
            context['failed_records'] = failed_records

        return cls(
            message,
            sync_source=sync_source,
            sync_target=sync_target,
            context=context
        )

# ============================================================================
# END OF CUSTOM ERROR CLASSES
# ============================================================================

# ============================================================================
# ERROR HANDLING UTILITIES
# ============================================================================

def handle_exception(error_class: type = CalendarError,
                    default_return: Any = None,
                    show_dialog: bool = True) -> Callable:
    """
    Decorator for automatic exception handling and conversion

    Automatically catches exceptions, converts them to custom error types,
    logs them, and optionally displays error dialogs to users.

    Args:
        error_class: Error class to convert exceptions to
        default_return: Default return value on error
        show_dialog: Whether to show error dialog to user

    Returns:
        Callable: Decorated function

    Example:
        @handle_exception(ValidationError, default_return=False)
        def validate_form(data):
            # validation logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (CalendarError, ValidationError, DatabaseError,
                   AuthenticationError, PermissionError, ExportError, SyncError) as e:
                # Already a custom error, just log and handle
                gui_logger.error(f"Error in {func.__name__}: {e.user_message}")
                if show_dialog:
                    safe_show_error("Error", e.user_message)
                return default_return
            except Exception as e:
                # Convert to custom error
                custom_error = error_class(
                    str(e),
                    context={
                        'function': func.__name__,
                        'original_error': type(e).__name__
                    }
                )
                gui_logger.error(f"Unexpected error in {func.__name__}: {custom_error.user_message}")
                if show_dialog:
                    safe_show_error("Unexpected Error", custom_error.user_message)
                return default_return
        return wrapper
    return decorator


def log_and_suppress(error_message: str = "An error occurred",
                    logger: Optional[logging.Logger] = None) -> Callable:
    """
    Decorator to log and suppress errors without propagating them

    Useful for non-critical operations where failures should not interrupt
    the main flow (e.g., analytics, optional features).

    Args:
        error_message: Custom error message to log
        logger: Logger to use (defaults to gui_logger)

    Returns:
        Callable: Decorated function

    Example:
        @log_and_suppress("Failed to track analytics")
        def track_user_action(action):
            # analytics tracking that shouldn't fail the main flow
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log = logger or gui_logger
                log.warning(
                    f"{error_message} in {func.__name__}: {str(e)}",
                    extra={'function': func.__name__, 'error': str(e)}
                )
                return None
        return wrapper
    return decorator


def convert_to_user_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> CalendarError:
    """
    Convert any exception to a user-friendly CalendarError

    Analyzes the exception type and message to create appropriate
    user-friendly error messages with helpful context.

    Args:
        error: Original exception
        context: Additional context information

    Returns:
        CalendarError: User-friendly error instance

    Example:
        try:
            conn.execute(query)
        except Exception as e:
            user_error = convert_to_user_error(e, {'query': 'SELECT...'})
            raise user_error
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Database errors
    if 'database' in error_str or 'sqlite' in error_str or error_type in ('DatabaseError', 'OperationalError'):
        if 'locked' in error_str:
            return DatabaseError(
                "Database is temporarily locked. Please try again.",
                operation="database_access",
                context=context
            )
        elif 'constraint' in error_str or 'unique' in error_str:
            return DatabaseError.constraint_violation(
                "UNIQUE" if 'unique' in error_str else "CONSTRAINT",
                table=context.get('table') if context else None
            )
        else:
            return DatabaseError(
                "A database error occurred. Please contact support.",
                operation="unknown",
                context=context
            )

    # Permission errors
    elif 'permission' in error_str or 'access denied' in error_str or error_type == 'PermissionError':
        return PermissionError(
            "You do not have permission to perform this action.",
            context=context
        )

    # File/IO errors
    elif 'file' in error_str or error_type in ('IOError', 'OSError', 'FileNotFoundError'):
        if 'not found' in error_str or error_type == 'FileNotFoundError':
            return ExportError(
                "File not found. Please check the file path.",
                context=context
            )
        else:
            return ExportError(
                "A file operation error occurred.",
                context=context
            )

    # Network/connection errors
    elif 'connection' in error_str or 'network' in error_str or error_type in ('ConnectionError', 'TimeoutError'):
        return SyncError.connection_failed(
            context.get('sync_source', 'remote server') if context else 'remote server',
            reason=str(error)
        )

    # Validation errors
    elif 'invalid' in error_str or 'validation' in error_str or error_type == 'ValueError':
        return ValidationError(
            str(error),
            field=context.get('field') if context else None,
            context=context
        )

    # Generic error
    else:
        return CalendarError(
            f"An unexpected error occurred: {str(error)}",
            error_type=error_type,
            context=context
        )

# ============================================================================
# VALIDATION UTILITIES
# ============================================================================

def validate_date(date_string: str, format: str = "%Y-%m-%d") -> Tuple[bool, Optional[datetime]]:
    """
    Validate date string and convert to datetime

    Args:
        date_string: Date string to validate
        format: Expected date format (default: YYYY-MM-DD)

    Returns:
        Tuple[bool, Optional[datetime]]: (is_valid, datetime_object or None)

    Example:
        is_valid, date_obj = validate_date("2025-11-09")
        if is_valid:
            print(f"Valid date: {date_obj}")
    """
    try:
        date_obj = datetime.strptime(date_string.strip(), format)
        return True, date_obj
    except (ValueError, AttributeError, TypeError):
        return False, None


def validate_datetime(datetime_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> Tuple[bool, Optional[datetime]]:
    """
    Validate datetime string and convert to datetime object

    Args:
        datetime_string: Datetime string to validate
        format: Expected datetime format (default: YYYY-MM-DD HH:MM:SS)

    Returns:
        Tuple[bool, Optional[datetime]]: (is_valid, datetime_object or None)

    Example:
        is_valid, dt_obj = validate_datetime("2025-11-09 14:30:00")
        if is_valid:
            print(f"Valid datetime: {dt_obj}")
    """
    try:
        dt_obj = datetime.strptime(datetime_string.strip(), format)
        return True, dt_obj
    except (ValueError, AttributeError, TypeError):
        return False, None


def validate_email(email: str) -> bool:
    """
    Validate email address format

    Uses RFC 5322 compliant regex pattern for email validation.

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid email format, False otherwise

    Example:
        if validate_email("user@example.com"):
            print("Valid email")
    """
    if not email or not isinstance(email, str):
        return False

    # RFC 5322 compliant email regex (simplified)
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    return bool(email_pattern.match(email.strip()))


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID string format

    Supports UUID versions 1, 3, 4, and 5.

    Args:
        uuid_string: UUID string to validate

    Returns:
        bool: True if valid UUID format, False otherwise

    Example:
        if validate_uuid("550e8400-e29b-41d4-a716-446655440000"):
            print("Valid UUID")
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    try:
        uuid_obj = uuid.UUID(uuid_string.strip())
        return str(uuid_obj) == uuid_string.strip().lower()
    except (ValueError, AttributeError):
        return False

# ============================================================================
# SANITIZATION UTILITIES
# ============================================================================

def sanitize_string(input_string: str, max_length: int = 1000,
                   allow_special_chars: bool = True) -> str:
    """
    Sanitize input string to prevent SQL injection and XSS

    Removes potentially dangerous characters and limits length.

    Args:
        input_string: String to sanitize
        max_length: Maximum allowed length
        allow_special_chars: Whether to allow special characters

    Returns:
        str: Sanitized string

    Example:
        safe_input = sanitize_string(user_input, max_length=100)
    """
    if not input_string or not isinstance(input_string, str):
        return ""

    # Limit length
    sanitized = input_string[:max_length]

    # Remove null bytes (common SQL injection technique)
    sanitized = sanitized.replace('\x00', '')

    if not allow_special_chars:
        # Keep only alphanumeric, spaces, and basic punctuation
        sanitized = re.sub(r'[^a-zA-Z0-9\s\.,!?\-_@]', '', sanitized)
    else:
        # Remove potentially dangerous characters for SQL/XSS
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                 # JavaScript protocol
            r'on\w+\s*=',                  # Event handlers
            r'--',                         # SQL comments
            r'/\*.*?\*/',                  # SQL block comments
        ]
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)

    return sanitized.strip()


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent path traversal attacks

    Removes path separators and limits to valid filename characters.

    Args:
        filename: Filename to sanitize
        max_length: Maximum filename length (default: 255)

    Returns:
        str: Sanitized filename

    Example:
        safe_filename = sanitize_filename("../../etc/passwd")
        # Returns: "etc_passwd"
    """
    if not filename or not isinstance(filename, str):
        return "unnamed_file"

    # Remove path separators and parent directory references
    sanitized = filename.replace('/', '_').replace('\\', '_')
    sanitized = sanitized.replace('..', '')
    sanitized = sanitized.replace('~', '')

    # Keep only safe filename characters
    # Allow: alphanumeric, spaces, dots, dashes, underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\s\.\-_]', '', sanitized)

    # Remove leading/trailing dots and spaces (problematic on Windows)
    sanitized = sanitized.strip('. ')

    # Ensure not empty after sanitization
    if not sanitized:
        sanitized = "unnamed_file"

    # Limit length
    if len(sanitized) > max_length:
        # Preserve extension if present
        name_parts = sanitized.rsplit('.', 1)
        if len(name_parts) == 2:
            name, ext = name_parts
            max_name_length = max_length - len(ext) - 1
            sanitized = f"{name[:max_name_length]}.{ext}"
        else:
            sanitized = sanitized[:max_length]

    return sanitized


def validate_file_path(file_path: str, allowed_directories: Optional[List[str]] = None,
                      allowed_extensions: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate file path for security

    Checks for path traversal, validates against allowed directories,
    and checks file extensions.

    Args:
        file_path: File path to validate
        allowed_directories: List of allowed directory paths (optional)
        allowed_extensions: List of allowed file extensions (optional)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message or None)

    Example:
        is_valid, error = validate_file_path(
            user_path,
            allowed_directories=['/home/user/uploads'],
            allowed_extensions=['.txt', '.pdf']
        )
        if not is_valid:
            print(f"Invalid path: {error}")
    """
    if not file_path or not isinstance(file_path, str):
        return False, "File path is empty or invalid"

    # Check for path traversal attempts
    normalized_path = os.path.normpath(file_path)
    if '..' in normalized_path or normalized_path.startswith('/..'):
        return False, "Path traversal detected"

    # Convert to absolute path
    try:
        abs_path = os.path.abspath(normalized_path)
    except (ValueError, OSError):
        return False, "Invalid file path"

    # Check against allowed directories
    if allowed_directories:
        allowed = False
        for allowed_dir in allowed_directories:
            allowed_abs = os.path.abspath(allowed_dir)
            if abs_path.startswith(allowed_abs):
                allowed = True
                break

        if not allowed:
            return False, f"File path not in allowed directories"

    # Check file extension
    if allowed_extensions:
        _, ext = os.path.splitext(abs_path)
        if ext.lower() not in [e.lower() for e in allowed_extensions]:
            return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"

    return True, None


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None,
                require_tld: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format and security

    Checks URL structure, scheme, and optionally validates TLD.

    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
        require_tld: Whether to require a valid TLD (default: True)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message or None)

    Example:
        is_valid, error = validate_url("https://example.com/path")
        if is_valid:
            print("Valid URL")
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or invalid"

    # Default allowed schemes
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if not parsed.scheme:
        return False, "URL must include a scheme (e.g., https://)"

    if parsed.scheme.lower() not in [s.lower() for s in allowed_schemes]:
        return False, f"URL scheme '{parsed.scheme}' not allowed. Allowed: {', '.join(allowed_schemes)}"

    # Check netloc (domain)
    if not parsed.netloc:
        return False, "URL must include a domain"

    # Check for valid TLD
    if require_tld:
        domain_parts = parsed.netloc.split('.')
        if len(domain_parts) < 2:
            return False, "URL must include a valid top-level domain"

        tld = domain_parts[-1]
        if not tld or len(tld) < 2:
            return False, "Invalid top-level domain"

    # Check for suspicious patterns
    suspicious_patterns = [
        r'@',  # Credentials in URL
        r'javascript:',  # JavaScript protocol
        r'data:',  # Data protocol (can be used for XSS)
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return False, f"URL contains suspicious pattern: {pattern}"

    return True, None

# ============================================================================
# SECURITY UTILITIES
# ============================================================================

def hash_password(password: str, salt: Optional[bytes] = None,
                 iterations: int = 100000) -> Tuple[str, str]:
    """
    Hash password securely using PBKDF2-SHA256

    Uses PBKDF2 with SHA256 for secure password hashing.

    Args:
        password: Password to hash
        salt: Salt bytes (auto-generated if not provided)
        iterations: Number of PBKDF2 iterations (default: 100,000)

    Returns:
        Tuple[str, str]: (hashed_password_hex, salt_hex)

    Example:
        password_hash, salt = hash_password("user_password")
        # Store both password_hash and salt in database
    """
    if not password:
        raise ValidationError.required_field("password")

    # Generate salt if not provided
    if salt is None:
        salt = secrets.token_bytes(32)  # 256-bit salt

    # Hash password using PBKDF2-SHA256
    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations
    )

    return password_hash.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt: str,
                   iterations: int = 100000) -> bool:
    """
    Verify hashed password

    Compares provided password against stored hash using constant-time comparison.

    Args:
        password: Password to verify
        password_hash: Stored password hash (hex)
        salt: Stored salt (hex)
        iterations: Number of PBKDF2 iterations (must match hash_password)

    Returns:
        bool: True if password matches, False otherwise

    Example:
        if verify_password(user_input, stored_hash, stored_salt):
            print("Password correct")
    """
    if not password or not password_hash or not salt:
        return False

    try:
        # Convert hex strings back to bytes
        salt_bytes = bytes.fromhex(salt)
        stored_hash_bytes = bytes.fromhex(password_hash)

        # Hash the provided password with the same salt
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt_bytes,
            iterations
        )

        # Constant-time comparison to prevent timing attacks
        return secrets.compare_digest(computed_hash, stored_hash_bytes)

    except (ValueError, AttributeError):
        return False


def generate_token(length: int = 32, url_safe: bool = True) -> str:
    """
    Generate secure random token

    Creates cryptographically secure random tokens for sessions,
    API keys, CSRF tokens, etc.

    Args:
        length: Token length in bytes (default: 32 = 256 bits)
        url_safe: Whether to generate URL-safe token (default: True)

    Returns:
        str: Secure random token

    Example:
        session_token = generate_token(32)
        api_key = generate_token(64)
    """
    if length < 16:
        raise ValidationError(
            "Token length must be at least 16 bytes for security",
            field="length"
        )

    if url_safe:
        # URL-safe base64 encoded token
        return secrets.token_urlsafe(length)
    else:
        # Hexadecimal token
        return secrets.token_hex(length)

# ============================================================================
# END OF UTILITIES
# ============================================================================

# ============================================================================
# DATABASE MANAGEMENT SYSTEM
# ============================================================================

class ConnectionPool:
    """
    Database connection pool for efficient connection management

    Provides connection pooling to reduce connection overhead and
    improve performance for database operations.
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        """
        Initialize connection pool

        Args:
            db_path: Path to database file
            pool_size: Number of connections to maintain
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection = None

    def __enter__(self):
        """Context manager entry - get connection"""
        import sqlite3
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        return self._connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection"""
        if self._connection:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
            self._connection.close()
        return False


class DatabaseManager:
    """
    Comprehensive database abstraction layer

    Provides:
    - Connection pooling
    - Transaction management
    - Query execution with error handling
    - Database backup functionality
    - Thread-safe operations
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_path: Path to database file (defaults to centralized path)
        """
        if db_path is None:
            from university_system.modules.shared.constants import paths
            db_path = paths.DEFAULT_DB_PATH

        self.db_path = db_path
        self._connection = None
        self._connection_pool = ConnectionPool(db_path)
        gui_logger.info(f"DatabaseManager initialized with path: {db_path}")

    def _connect(self):
        """
        Establish database connection

        Returns:
            sqlite3.Connection: Database connection

        Raises:
            DatabaseError: If connection fails
        """
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except Exception as e:
            raise DatabaseError.connection_failed(str(e))

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results

        Args:
            query: SQL SELECT query
            params: Query parameters (optional)

        Returns:
            List[Dict]: Query results as list of dictionaries

        Raises:
            DatabaseError: If query execution fails

        Example:
            results = db.execute_query(
                "SELECT * FROM events WHERE date = ?",
                (date_str,)
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.execute(query, params or ())
                rows = cursor.fetchall()
                # Convert Row objects to dictionaries
                return [dict(row) for row in rows]
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'SELECT'})

    def execute_update(self, query: str, params: Optional[Tuple] = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE query

        Args:
            query: SQL modification query
            params: Query parameters (optional)

        Returns:
            int: Number of affected rows

        Raises:
            DatabaseError: If query execution fails

        Example:
            rows_affected = db.execute_update(
                "UPDATE events SET title = ? WHERE id = ?",
                (new_title, event_id)
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.execute(query, params or ())
                return cursor.rowcount
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'UPDATE'})

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute query with multiple parameter sets (batch operation)

        Args:
            query: SQL query
            params_list: List of parameter tuples

        Returns:
            int: Number of affected rows

        Raises:
            DatabaseError: If batch execution fails

        Example:
            db.execute_many(
                "INSERT INTO events (title, date) VALUES (?, ?)",
                [("Event 1", "2025-11-09"), ("Event 2", "2025-11-10")]
            )
        """
        try:
            with self._connection_pool as conn:
                cursor = conn.executemany(query, params_list)
                return cursor.rowcount
        except Exception as e:
            raise convert_to_user_error(e, {'query': query, 'operation': 'BATCH'})

    def transaction(self):
        """
        Create transaction context manager

        Returns:
            ConnectionPool: Context manager for transaction

        Example:
            with db.transaction() as conn:
                conn.execute("INSERT INTO events ...")
                conn.execute("INSERT INTO attendees ...")
                # Auto-commits if no exception
        """
        return self._connection_pool

    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create database backup

        Args:
            backup_path: Path for backup file (auto-generated if not provided)

        Returns:
            str: Path to backup file

        Raises:
            ExportError: If backup fails

        Example:
            backup_file = db.backup_database()
            print(f"Backup created: {backup_file}")
        """
        try:
            import shutil
            from pathlib import Path

            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = Path(self.db_path).parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = str(backup_dir / f"calendar_backup_{timestamp}.db")

            # Create backup using shutil
            shutil.copy2(self.db_path, backup_path)

            gui_logger.info(f"Database backup created: {backup_path}")
            return backup_path

        except Exception as e:
            raise ExportError.file_write_failed(
                backup_path or "unknown",
                reason=str(e)
            )

    def close(self):
        """
        Close database connections and cleanup resources

        Should be called when database manager is no longer needed.
        """
        if self._connection:
            self._connection.close()
            self._connection = None
        gui_logger.info("DatabaseManager closed")

# ============================================================================
# AUTHENTICATION SYSTEM
# ============================================================================

class AuthenticationManager:
    """
    Comprehensive authentication and authorization system

    Features:
    - User authentication with password verification
    - Role-based access control (RBAC)
    - Session management
    - Permission checking
    - User creation and management
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize authentication manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.current_user = None
        self.current_session = None
        self.permissions = {}
        self._load_permissions()
        gui_logger.info("AuthenticationManager initialized")

    def authenticate_user(self, username: str, password: str) -> bool:
        """
        Authenticate user with username and password

        Args:
            username: Username
            password: Password (will be hashed for comparison)

        Returns:
            bool: True if authentication successful

        Raises:
            AuthenticationError: If authentication fails

        Example:
            if auth.authenticate_user("admin", "password123"):
                print("Login successful")
        """
        try:
            # Query user from database
            users = self.db.execute_query(
                "SELECT id, username, password_hash, password_salt, role, active FROM users WHERE username = ?",
                (username,)
            )

            if not users:
                raise AuthenticationError.invalid_credentials(username)

            user = users[0]

            # Check if account is active
            if not user['active']:
                raise AuthenticationError.account_locked(
                    username,
                    reason="Account is inactive"
                )

            # Verify password
            if not verify_password(password, user['password_hash'], user['password_salt']):
                raise AuthenticationError.invalid_credentials(username)

            # Create session
            self._create_session(user)

            gui_logger.info(f"User authenticated successfully: {username}")
            return True

        except AuthenticationError:
            raise
        except Exception as e:
            raise convert_to_user_error(e, {'username': username})

    def check_permission(self, permission: str) -> bool:
        """
        Check if current user has specified permission

        Args:
            permission: Permission name to check

        Returns:
            bool: True if user has permission

        Example:
            if auth.check_permission('create_event'):
                # Allow event creation
                pass
        """
        if not self.current_user:
            return False

        user_role = self.current_user.get('role', '')
        role_permissions = self.permissions.get(user_role, [])

        return permission in role_permissions or 'admin' in role_permissions

    def _load_permissions(self):
        """
        Load role-based permissions from configuration

        Defines permission sets for each role.
        """
        self.permissions = {
            'admin': ['admin', 'create_event', 'edit_event', 'delete_event',
                     'view_event', 'manage_users', 'view_reports'],
            'instructor': ['create_event', 'edit_event', 'view_event', 'view_reports'],
            'staff': ['create_event', 'view_event'],
            'student': ['view_event'],
        }

    def _create_session(self, user: Dict[str, Any]):
        """
        Create user session after successful authentication

        Args:
            user: User data dictionary
        """
        self.current_user = user
        self.current_session = {
            'user_id': user['id'],
            'username': user['username'],
            'role': user['role'],
            'session_token': generate_token(32),
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(hours=24)
        }

        # Store session in database
        try:
            self.db.execute_update(
                """INSERT INTO user_sessions
                   (user_id, session_token, created_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    self.current_session['user_id'],
                    self.current_session['session_token'],
                    self.current_session['created_at'].isoformat(),
                    self.current_session['expires_at'].isoformat()
                )
            )
        except Exception as e:
            gui_logger.warning(f"Failed to store session in database: {e}")

    def _is_session_valid(self) -> bool:
        """
        Check if current session is valid

        Returns:
            bool: True if session is valid and not expired
        """
        if not self.current_session:
            return False

        if datetime.now() > self.current_session['expires_at']:
            return False

        return True

    def require_permission(self, permission: str) -> Callable:
        """
        Decorator to require specific permission for function execution

        Args:
            permission: Required permission name

        Returns:
            Callable: Decorated function

        Example:
            @auth.require_permission('create_event')
            def create_event(event_data):
                # Only users with 'create_event' permission can execute
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.check_permission(permission):
                    raise PermissionError.resource_access_denied(
                        resource=func.__name__,
                        action='execute',
                        required_permission=permission
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def logout(self):
        """
        Logout current user and clear session

        Invalidates current session and clears user data.
        """
        if self.current_session:
            # Invalidate session in database
            try:
                self.db.execute_update(
                    "DELETE FROM user_sessions WHERE session_token = ?",
                    (self.current_session['session_token'],)
                )
            except Exception as e:
                gui_logger.warning(f"Failed to invalidate session in database: {e}")

        self.current_user = None
        self.current_session = None
        gui_logger.info("User logged out")

    def create_user(self, username: str, password: str, role: str = 'student',
                   email: Optional[str] = None) -> int:
        """
        Create new user account

        Args:
            username: Username
            password: Password (will be hashed)
            role: User role (default: 'student')
            email: Email address (optional)

        Returns:
            int: New user ID

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If user creation fails

        Example:
            user_id = auth.create_user(
                "john_doe",
                "secure_password",
                role="instructor",
                email="john@university.edu"
            )
        """
        # Validate inputs
        if not username or len(username) < 3:
            raise ValidationError.invalid_format(
                'username',
                'at least 3 characters',
                username
            )

        if not password or len(password) < 8:
            raise ValidationError.invalid_format(
                'password',
                'at least 8 characters'
            )

        if email and not validate_email(email):
            raise ValidationError.invalid_format(
                'email',
                'valid email address',
                email
            )

        # Try to use central auth system first
        if CENTRAL_AUTH_AVAILABLE and _current_auth_instance:
            try:
                user_id = _current_auth_instance.create_user(
                    username=username,
                    password=password,
                    email=email,
                    role=role,
                    first_name='',
                    last_name=''
                )

                if user_id:
                    gui_logger.info(f"User created via central auth: {username} (ID: {user_id}, Role: {role})")
                    # Log activity
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_activity('create', 'user', user_id=user_id, details={'username': username, 'role': role, 'email': email})
                    return user_id
            except Exception as e:
                gui_logger.warning(f"Failed to create user via central auth, falling back to local: {e}")

        # Fallback to local user creation
        # Hash password
        password_hash, password_salt = hash_password(password)

        # Create user
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO users
                       (username, password_hash, password_salt, role, email, active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (
                        username,
                        password_hash,
                        password_salt,
                        role,
                        email,
                        datetime.now().isoformat()
                    )
                )
                user_id = cursor.lastrowid

            gui_logger.info(f"User created (fallback): {username} (ID: {user_id}, Role: {role})")
            # Log activity even in fallback mode
            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('create', 'user', user_id=user_id, details={'username': username, 'role': role, 'email': email, 'method': 'fallback'})
            return user_id

        except Exception as e:
            raise convert_to_user_error(e, {'username': username, 'table': 'users'})

# ============================================================================
# RECURRING EVENTS SYSTEM
# ============================================================================

class RecurringEventManager:
    """
    Manages recurring events with flexible recurrence patterns

    Supports:
    - Daily, weekly, monthly, yearly recurrence
    - Custom recurrence intervals
    - End date or occurrence count limits
    - Exception dates (skip specific occurrences)
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize recurring event manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("RecurringEventManager initialized")

    def create_recurring_event(self, event_data: Dict[str, Any],
                               recurrence_pattern: str,
                               interval: int = 1,
                               end_date: Optional[datetime] = None,
                               occurrences: Optional[int] = None) -> List[int]:
        """
        Create recurring event with specified pattern

        Args:
            event_data: Base event data (title, description, etc.)
            recurrence_pattern: 'daily', 'weekly', 'monthly', 'yearly'
            interval: Recurrence interval (e.g., every 2 weeks)
            end_date: Optional end date for recurrence
            occurrences: Optional number of occurrences to create

        Returns:
            List[int]: List of created event IDs

        Raises:
            ValidationError: If parameters are invalid

        Example:
            event_ids = recurring_mgr.create_recurring_event(
                {
                    'title': 'Weekly Team Meeting',
                    'description': 'Team sync',
                    'start_time': '10:00',
                    'duration': 60
                },
                recurrence_pattern='weekly',
                interval=1,
                occurrences=10
            )
        """
        # Validate recurrence pattern
        valid_patterns = ['daily', 'weekly', 'monthly', 'yearly']
        if recurrence_pattern not in valid_patterns:
            raise ValidationError.invalid_format(
                'recurrence_pattern',
                f"One of: {', '.join(valid_patterns)}",
                recurrence_pattern
            )

        # Validate that either end_date or occurrences is specified
        if end_date is None and occurrences is None:
            raise ValidationError(
                "Either end_date or occurrences must be specified",
                field="recurrence"
            )

        # Generate recurring occurrences
        event_dates = self._generate_recurring_occurrences(
            start_date=event_data.get('date'),
            pattern=recurrence_pattern,
            interval=interval,
            end_date=end_date,
            occurrences=occurrences
        )

        # Create events for each occurrence
        event_ids = []
        try:
            with self.db.transaction() as conn:
                for event_date in event_dates:
                    # Create event with specific date
                    event_copy = event_data.copy()
                    event_copy['date'] = event_date.strftime('%Y-%m-%d')

                    cursor = conn.execute(
                        """INSERT INTO calendar_events
                           (title, description, date, start_time, end_time, location,
                            event_type, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            event_copy.get('title'),
                            event_copy.get('description'),
                            event_copy['date'],
                            event_copy.get('start_time'),
                            event_copy.get('end_time'),
                            event_copy.get('location'),
                            event_copy.get('event_type', 'recurring'),
                            datetime.now().isoformat()
                        )
                    )
                    event_ids.append(cursor.lastrowid)

            gui_logger.info(
                f"Created {len(event_ids)} recurring events: {recurrence_pattern}, "
                f"interval: {interval}"
            )
            return event_ids

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'create_recurring_events'})

    def _generate_recurring_occurrences(self, start_date: str, pattern: str,
                                       interval: int, end_date: Optional[datetime],
                                       occurrences: Optional[int]) -> List[datetime]:
        """
        Generate list of dates for recurring event

        Args:
            start_date: Start date string (YYYY-MM-DD)
            pattern: Recurrence pattern
            interval: Recurrence interval
            end_date: Optional end date
            occurrences: Optional number of occurrences

        Returns:
            List[datetime]: List of occurrence dates
        """
        # Parse start date
        is_valid, current_date = validate_date(start_date)
        if not is_valid:
            raise ValidationError.invalid_format('start_date', 'YYYY-MM-DD', start_date)

        occurrence_dates = []
        count = 0

        # Determine delta based on pattern
        delta_map = {
            'daily': lambda i: timedelta(days=i),
            'weekly': lambda i: timedelta(weeks=i),
            'monthly': lambda i: timedelta(days=30 * i),  # Approximate
            'yearly': lambda i: timedelta(days=365 * i)  # Approximate
        }

        delta_func = delta_map[pattern]

        # Generate occurrences
        while True:
            # Check if we've reached the limit
            if occurrences and count >= occurrences:
                break
            if end_date and current_date > end_date:
                break

            occurrence_dates.append(current_date)
            count += 1

            # Move to next occurrence
            current_date = current_date + delta_func(interval)

        return occurrence_dates

# ============================================================================
# EVENT DEPENDENCIES AND WORKFLOWS
# ============================================================================

class EventDependencyManager:
    """
    Manages event dependencies and workflows

    Features:
    - Event dependencies (prerequisite events)
    - Circular dependency detection
    - Automatic deadline calculation
    - Workflow creation
    - Dependency-based date updates
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize event dependency manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self._create_dependency_tables()
        gui_logger.info("EventDependencyManager initialized")

    def _create_dependency_tables(self):
        """Create tables for event dependencies if they don't exist"""
        try:
            with self.db.transaction() as conn:
                # Event dependencies table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        depends_on_event_id INTEGER NOT NULL,
                        dependency_type TEXT DEFAULT 'finish_to_start',
                        lag_days INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE,
                        FOREIGN KEY (depends_on_event_id) REFERENCES calendar_events(id) ON DELETE CASCADE,
                        UNIQUE(event_id, depends_on_event_id)
                    )
                """)

                # Event workflows table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_workflows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_name TEXT NOT NULL,
                        description TEXT,
                        created_at TEXT NOT NULL
                    )
                """)

                # Workflow events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_id INTEGER NOT NULL,
                        event_id INTEGER NOT NULL,
                        sequence_order INTEGER NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES event_workflows(id) ON DELETE CASCADE,
                        FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
                    )
                """)

        except Exception as e:
            gui_logger.error(f"Failed to create dependency tables: {e}")

    def add_event_dependency(self, event_id: int, depends_on_event_id: int,
                            dependency_type: str = 'finish_to_start',
                            lag_days: int = 0) -> int:
        """
        Add dependency between two events

        Args:
            event_id: ID of dependent event
            depends_on_event_id: ID of prerequisite event
            dependency_type: Type of dependency ('finish_to_start', 'start_to_start')
            lag_days: Number of days lag between events

        Returns:
            int: Dependency ID

        Raises:
            ValidationError: If circular dependency detected

        Example:
            # Exam depends on lecture finishing
            dep_mgr.add_event_dependency(
                event_id=exam_id,
                depends_on_event_id=lecture_id,
                dependency_type='finish_to_start',
                lag_days=1
            )
        """
        # Check for circular dependencies
        if self._creates_circular_dependency(event_id, depends_on_event_id):
            raise ValidationError(
                f"Circular dependency detected: Event {event_id} cannot depend on {depends_on_event_id}",
                field="dependency"
            )

        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO event_dependencies
                       (event_id, depends_on_event_id, dependency_type, lag_days, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        event_id,
                        depends_on_event_id,
                        dependency_type,
                        lag_days,
                        datetime.now().isoformat()
                    )
                )
                dependency_id = cursor.lastrowid

            # Update dependent event dates if needed
            self._update_dependent_event_dates(event_id)

            gui_logger.info(
                f"Event dependency added: {event_id} depends on {depends_on_event_id}"
            )
            return dependency_id

        except Exception as e:
            raise convert_to_user_error(e, {'table': 'event_dependencies'})

    def _creates_circular_dependency(self, event_id: int, depends_on_event_id: int) -> bool:
        """
        Check if adding dependency would create circular reference

        Args:
            event_id: ID of dependent event
            depends_on_event_id: ID of prerequisite event

        Returns:
            bool: True if circular dependency would be created
        """
        # BFS to detect cycles
        visited = set()
        queue = [depends_on_event_id]

        while queue:
            current_id = queue.pop(0)

            if current_id == event_id:
                return True

            if current_id in visited:
                continue

            visited.add(current_id)

            # Get dependencies of current event
            try:
                dependencies = self.db.execute_query(
                    "SELECT depends_on_event_id FROM event_dependencies WHERE event_id = ?",
                    (current_id,)
                )
                queue.extend([dep['depends_on_event_id'] for dep in dependencies])
            except Exception:
                pass

        return False

    def _update_dependent_event_dates(self, event_id: int):
        """
        Update dates of dependent events based on dependencies

        Args:
            event_id: ID of event that was updated
        """
        try:
            # Get all events that depend on this event
            dependents = self.db.execute_query(
                """SELECT ed.event_id, ed.dependency_type, ed.lag_days,
                          e.date as dependent_date,
                          pe.date as prerequisite_date
                   FROM event_dependencies ed
                   JOIN calendar_events e ON ed.event_id = e.id
                   JOIN calendar_events pe ON ed.depends_on_event_id = pe.id
                   WHERE ed.depends_on_event_id = ?""",
                (event_id,)
            )

            for dep in dependents:
                # Calculate new date based on dependency type
                prereq_date = datetime.strptime(dep['prerequisite_date'], '%Y-%m-%d')
                new_date = prereq_date + timedelta(days=dep['lag_days'])

                if dep['dependency_type'] == 'finish_to_start':
                    new_date += timedelta(days=1)  # Start day after finish

                # Update dependent event date
                self.db.execute_update(
                    "UPDATE calendar_events SET date = ? WHERE id = ?",
                    (new_date.strftime('%Y-%m-%d'), dep['event_id'])
                )

        except Exception as e:
            gui_logger.warning(f"Failed to update dependent event dates: {e}")

    def create_workflow(self, workflow_name: str, description: str,
                       event_ids: List[int]) -> int:
        """
        Create event workflow with ordered events

        Args:
            workflow_name: Name of workflow
            description: Workflow description
            event_ids: List of event IDs in sequence order

        Returns:
            int: Workflow ID

        Example:
            workflow_id = dep_mgr.create_workflow(
                "Course Semester Flow",
                "Complete semester timeline",
                [orientation_id, lecture1_id, midterm_id, lecture2_id, final_id]
            )
        """
        try:
            with self.db.transaction() as conn:
                # Create workflow
                cursor = conn.execute(
                    """INSERT INTO event_workflows
                       (workflow_name, description, created_at)
                       VALUES (?, ?, ?)""",
                    (workflow_name, description, datetime.now().isoformat())
                )
                workflow_id = cursor.lastrowid

                # Add events to workflow
                for sequence_order, event_id in enumerate(event_ids):
                    conn.execute(
                        """INSERT INTO workflow_events
                           (workflow_id, event_id, sequence_order)
                           VALUES (?, ?, ?)""",
                        (workflow_id, event_id, sequence_order)
                    )

            gui_logger.info(f"Workflow created: {workflow_name} with {len(event_ids)} events")
            return workflow_id

        except Exception as e:
            raise convert_to_user_error(e, {'table': 'event_workflows'})

    def calculate_automatic_deadlines(self, workflow_id: int, start_date: datetime,
                                     event_durations: Dict[int, int]):
        """
        Calculate and set automatic deadlines for workflow events

        Args:
            workflow_id: Workflow ID
            start_date: Start date for workflow
            event_durations: Dict mapping event_id to duration in days

        Example:
            dep_mgr.calculate_automatic_deadlines(
                workflow_id=1,
                start_date=datetime(2025, 9, 1),
                event_durations={
                    orientation_id: 1,
                    lecture1_id: 14,
                    midterm_id: 1,
                    lecture2_id: 14,
                    final_id: 1
                }
            )
        """
        try:
            # Get workflow events in order
            events = self.db.execute_query(
                """SELECT event_id
                   FROM workflow_events
                   WHERE workflow_id = ?
                   ORDER BY sequence_order""",
                (workflow_id,)
            )

            current_date = start_date

            with self.db.transaction() as conn:
                for event in events:
                    event_id = event['event_id']
                    duration = event_durations.get(event_id, 1)

                    # Update event date
                    conn.execute(
                        "UPDATE calendar_events SET date = ? WHERE id = ?",
                        (current_date.strftime('%Y-%m-%d'), event_id)
                    )

                    # Move to next event start date
                    current_date += timedelta(days=duration)

            gui_logger.info(f"Automatic deadlines calculated for workflow {workflow_id}")

        except Exception as e:
            gui_logger.error(f"Failed to calculate automatic deadlines: {e}")

# ============================================================================
# ADVANCED REPORTING ENGINE
# ============================================================================

class ReportingEngine:
    """
    Advanced reporting and analytics engine

    Features:
    - Attendance tracking and reporting
    - Resource utilization analysis
    - Academic year summaries
    - Custom report generation
    - Export to multiple formats
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize reporting engine

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("ReportingEngine initialized")

    def generate_attendance_report(self, start_date: str, end_date: str,
                                  event_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate attendance report for date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            event_type: Optional event type filter

        Returns:
            Dict: Attendance statistics and details

        Example:
            report = reporting.generate_attendance_report(
                "2025-09-01",
                "2025-12-31",
                event_type="lecture"
            )
        """
        try:
            query = """
                SELECT
                    e.id,
                    e.title,
                    e.date,
                    e.event_type,
                    COUNT(DISTINCT a.student_id) as attendee_count,
                    e.capacity,
                    CASE
                        WHEN e.capacity > 0
                        THEN ROUND(COUNT(DISTINCT a.student_id) * 100.0 / e.capacity, 2)
                        ELSE 0
                    END as attendance_percentage
                FROM calendar_events e
                LEFT JOIN event_attendance a ON e.id = a.event_id
                WHERE e.date BETWEEN ? AND ?
            """

            params = [start_date, end_date]

            if event_type:
                query += " AND e.event_type = ?"
                params.append(event_type)

            query += " GROUP BY e.id ORDER BY e.date"

            events = self.db.execute_query(query, tuple(params))

            # Calculate summary statistics
            total_events = len(events)
            total_attendees = sum(e['attendee_count'] for e in events)
            avg_attendance = (
                sum(e['attendance_percentage'] for e in events) / total_events
                if total_events > 0 else 0
            )

            return {
                'period': {'start': start_date, 'end': end_date},
                'event_type': event_type or 'all',
                'summary': {
                    'total_events': total_events,
                    'total_attendees': total_attendees,
                    'average_attendance_percentage': round(avg_attendance, 2)
                },
                'events': events
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_attendance_report'})

    def generate_utilization_report(self, resource_type: str = 'room') -> Dict[str, Any]:
        """
        Generate resource utilization report

        Args:
            resource_type: Type of resource ('room', 'equipment', etc.)

        Returns:
            Dict: Utilization statistics

        Example:
            report = reporting.generate_utilization_report(resource_type='room')
        """
        try:
            query = """
                SELECT
                    location as resource_name,
                    COUNT(*) as total_bookings,
                    COUNT(DISTINCT date) as days_used,
                    SUM(CASE
                        WHEN date >= date('now')
                        THEN 1 ELSE 0
                    END) as upcoming_bookings
                FROM calendar_events
                WHERE location IS NOT NULL AND location != ''
                GROUP BY location
                ORDER BY total_bookings DESC
            """

            resources = self.db.execute_query(query)

            # Calculate overall utilization
            total_bookings = sum(r['total_bookings'] for r in resources)
            total_resources = len(resources)

            return {
                'resource_type': resource_type,
                'summary': {
                    'total_resources': total_resources,
                    'total_bookings': total_bookings,
                    'average_bookings_per_resource': (
                        round(total_bookings / total_resources, 2)
                        if total_resources > 0 else 0
                    )
                },
                'resources': resources
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_utilization_report'})

    def generate_academic_year_summary(self, academic_year: str) -> Dict[str, Any]:
        """
        Generate comprehensive academic year summary

        Args:
            academic_year: Academic year (e.g., "2025-2026")

        Returns:
            Dict: Academic year statistics and breakdown

        Example:
            report = reporting.generate_academic_year_summary("2025-2026")
        """
        try:
            # Parse academic year
            start_year = int(academic_year.split('-')[0])
            start_date = f"{start_year}-09-01"
            end_date = f"{start_year + 1}-08-31"

            # Get event breakdown by type
            event_breakdown = self.db.execute_query("""
                SELECT
                    event_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT date) as unique_dates
                FROM calendar_events
                WHERE date BETWEEN ? AND ?
                GROUP BY event_type
            """, (start_date, end_date))

            # Get monthly distribution
            monthly_distribution = self.db.execute_query("""
                SELECT
                    strftime('%Y-%m', date) as month,
                    COUNT(*) as event_count
                FROM calendar_events
                WHERE date BETWEEN ? AND ?
                GROUP BY month
                ORDER BY month
            """, (start_date, end_date))

            total_events = sum(e['count'] for e in event_breakdown)

            return {
                'academic_year': academic_year,
                'period': {'start': start_date, 'end': end_date},
                'summary': {
                    'total_events': total_events,
                    'event_types': len(event_breakdown)
                },
                'event_breakdown': event_breakdown,
                'monthly_distribution': monthly_distribution
            }

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'generate_academic_year_summary'})

# ============================================================================
# NOTIFICATION SYSTEM
# ============================================================================

class NotificationManager:
    """
    Multi-channel notification system

    Features:
    - SMS notifications
    - Email notifications (integration ready)
    - Event reminders
    - Scheduled notifications
    - Notification templates
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize notification manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("NotificationManager initialized")

    def send_sms_notification(self, phone_number: str, message: str) -> bool:
        """
        Send SMS notification

        Args:
            phone_number: Recipient phone number
            message: SMS message content

        Returns:
            bool: True if SMS sent successfully

        Raises:
            ValidationError: If phone number invalid
            SyncError: If SMS service unavailable

        Example:
            notif.send_sms_notification(
                "+1234567890",
                "Reminder: Team meeting tomorrow at 10 AM"
            )
        """
        # Validate phone number
        if not self._validate_phone_number(phone_number):
            raise ValidationError.invalid_format(
                'phone_number',
                'valid phone number format',
                phone_number
            )

        # Sanitize message
        safe_message = sanitize_string(message, max_length=160)

        try:
            # TODO: Integrate with actual SMS service (Twilio, AWS SNS, etc.)
            # For now, log the SMS
            gui_logger.info(f"SMS to {phone_number}: {safe_message}")

            # Store notification record
            self.db.execute_update(
                """INSERT INTO notifications
                   (recipient, channel, message, sent_at, status)
                   VALUES (?, 'sms', ?, ?, 'sent')""",
                (phone_number, safe_message, datetime.now().isoformat())
            )

            return True

        except Exception as e:
            raise SyncError.connection_failed(
                'SMS service',
                reason=str(e)
            )

    def _validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate phone number format

        Args:
            phone_number: Phone number to validate

        Returns:
            bool: True if valid phone number
        """
        # Simple validation - accepts formats: +1234567890, 123-456-7890, etc.
        phone_pattern = re.compile(r'^\+?[1-9]\d{1,14}$|^[\d\-\(\)\s]{10,}$')
        return bool(phone_pattern.match(phone_number.replace(' ', '').replace('-', '')))

    def send_event_reminder_sms(self, event_id: int, hours_before: int = 24):
        """
        Send SMS reminder for upcoming event

        Args:
            event_id: Event ID
            hours_before: Hours before event to send reminder

        Example:
            notif.send_event_reminder_sms(event_id=123, hours_before=24)
        """
        try:
            # Get event details
            events = self.db.execute_query(
                """SELECT e.*, GROUP_CONCAT(a.phone_number) as attendee_phones
                   FROM calendar_events e
                   LEFT JOIN event_attendees ea ON e.id = ea.event_id
                   LEFT JOIN attendees a ON ea.attendee_id = a.id
                   WHERE e.id = ?
                   GROUP BY e.id""",
                (event_id,)
            )

            if not events:
                raise DatabaseError.record_not_found('event', event_id)

            event = events[0]

            # Create reminder message
            message = f"Reminder: {event['title']} on {event['date']}"
            if event.get('start_time'):
                message += f" at {event['start_time']}"
            if event.get('location'):
                message += f" ({event['location']})"

            # Send to attendees
            if event.get('attendee_phones'):
                phones = event['attendee_phones'].split(',')
                for phone in phones:
                    if phone:
                        self.send_sms_notification(phone.strip(), message)

            gui_logger.info(f"Event reminder sent for event {event_id}")

        except Exception as e:
            gui_logger.error(f"Failed to send event reminder: {e}")

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_calendar_database(db_path: Optional[str] = None) -> DatabaseManager:
    """
    Initialize calendar database with comprehensive schema

    Creates all required tables for calendar management system including:
    - Events, attendees, attendance tracking
    - Recurring events, dependencies, workflows
    - Users, sessions, permissions
    - Notifications, reports

    Args:
        db_path: Path to database file (uses default if not provided)

    Returns:
        DatabaseManager: Initialized database manager

    Example:
        db = init_calendar_database()
        # Database ready for use
    """
    db = DatabaseManager(db_path)

    try:
        with db.transaction() as conn:
            # Calendar events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    date TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    event_type TEXT DEFAULT 'general',
                    capacity INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'scheduled',
                    created_by INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)

            # Attendees table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attendees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone_number TEXT,
                    student_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Event attendance table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    attended BOOLEAN DEFAULT 0,
                    attendance_time TEXT,
                    FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE,
                    UNIQUE(event_id, student_id)
                )
            """)

            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'student',
                    email TEXT,
                    active BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)

            # User sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Notifications table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_date ON calendar_events(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON calendar_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token)")

        gui_logger.info("Calendar database initialized successfully")
        return db

    except Exception as e:
        gui_logger.error(f"Failed to initialize database: {e}")
        raise convert_to_user_error(e, {'operation': 'database_initialization'})

# ============================================================================
# END OF MANAGEMENT SYSTEMS
# ============================================================================

def safe_grab_set(dialog, parent=None):
    """
    Safely set grab on dialog, handling grab conflicts
    
    Args:
        dialog: The dialog window to grab
        parent: Parent window (optional)
    """
    try:
        # Small delay to ensure parent dialog operations complete
        dialog.after_idle(lambda: _attempt_grab(dialog))
    except Exception as e:
        gui_logger.warning(f"Failed to set grab on dialog: {e}")

def _attempt_grab(dialog):
    """Attempt to grab dialog with error handling"""
    try:
        dialog.grab_set()
    except Exception as e:
        gui_logger.warning(f"Grab failed: {e}")
        # Continue without grab - dialog will still be functional

def safe_show_error(title, message, parent=None):
    """
    Safely show error message without grab conflicts
    
    Args:
        title: Error dialog title
        message: Error message
        parent: Parent window (optional)
    """
    try:
        # Release any existing grabs before showing error
        if parent and hasattr(parent, 'grab_release'):
            try:
                parent.grab_release()
            except:
                pass
        
        # Show error without grab to avoid conflicts
        messagebox.showerror(title, message)
    except Exception as e:
        # Fallback to print if messagebox fails
        print(f"ERROR - {title}: {message}")
        gui_logger.error(f"Failed to show error dialog: {e}")

def safe_show_info(title, message, parent=None):
    """Safely show info message without grab conflicts"""
    try:
        if parent and hasattr(parent, 'grab_release'):
            try:
                parent.grab_release()
            except:
                pass
        messagebox.showinfo(title, message)
    except Exception as e:
        print(f"INFO - {title}: {message}")
        gui_logger.warning(f"Failed to show info dialog: {e}")

def safe_show_warning(title, message, parent=None):
    """Safely show warning message without grab conflicts"""
    try:
        if parent and hasattr(parent, 'grab_release'):
            try:
                parent.grab_release()
            except:
                pass
        messagebox.showwarning(title, message)
    except Exception as e:
        print(f"WARNING - {title}: {message}")
        gui_logger.warning(f"Failed to show warning dialog: {e}")

class CalendarGUI:
    """Modern GUI for Academic Calendar Management with backward compatibility"""
    
    def __init__(self, auth_manager=None, parent_window=None):
        self.auth_manager = auth_manager
        self.calendar_manager = None
        self.parent_window = parent_window
        self.style = None
        
        # GUI components
        self.main_frame = None
        self.sidebar = None
        self.content_area = None
        self.status_bar = None
        
        # Data storage
        self.current_events = []
        self.current_view = "calendar"
        
        # Threading for long operations
        self.task_queue = queue.Queue()
        
        # Initialize GUI
        self._setup_gui()
        self._setup_calendar_manager()

    def init_calendar_database():
        """Initialize the academic calendar database tables"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            print("🗓️ Initializing academic calendar database...")
            
            # Create academic_years table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS academic_years (
                id TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                date_added TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0
            )
            ''')
            
            # Create semesters table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                academic_year_id TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                date_added TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                FOREIGN KEY (academic_year_id) REFERENCES academic_years (id)
            )
            ''')
            
            # Create event_categories table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                color TEXT DEFAULT '#2196F3',
                icon TEXT DEFAULT '📅',
                created_at TEXT NOT NULL,
                is_system BOOLEAN DEFAULT 0
            )
            ''')
            
            # Create events table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                event_type TEXT DEFAULT 'Academic',
                category_id INTEGER,
                date TEXT,
                date_start TEXT,
                date_end TEXT,
                all_day BOOLEAN DEFAULT 1,
                location TEXT,
                academic_year_id TEXT,
                semester_id INTEGER,
                created_by TEXT,
                date_added TEXT NOT NULL,
                last_modified TEXT,
                is_recurring BOOLEAN DEFAULT 0,
                recurrence_rule TEXT,
                status TEXT DEFAULT 'active',
                priority INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES event_categories (id),
                FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                FOREIGN KEY (semester_id) REFERENCES semesters (id)
            )
            ''')
            
            # Create event_notifications table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                user_id TEXT,
                notification_type TEXT NOT NULL,
                send_at TEXT NOT NULL,
                sent BOOLEAN DEFAULT 0,
                sent_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events (id)
            )
            ''')
            
            # Create calendar_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_type TEXT NOT NULL,
                resource_id TEXT,
                granted_by TEXT,
                granted_at TEXT NOT NULL,
                expires_at TEXT
            )
            ''')
            
            # Create calendar_audit_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS calendar_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                old_values TEXT,
                new_values TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT
            )
            ''')
            
            # Insert default event categories
            default_categories = [
                ('Academic', 'Academic events and deadlines', '#2196F3', '📚', 1),
                ('Holiday', 'Holidays and breaks', '#4CAF50', '🎉', 1),
                ('Administrative', 'Administrative events', '#FF9800', '📋', 1),
                ('Social', 'Social events and activities', '#E91E63', '🎊', 1),
                ('Sports', 'Sports and athletic events', '#9C27B0', '⚽', 1),
                ('Trip', 'Educational trips and excursions', '#00BCD4', '🎒', 1),
                ('Deadline', 'Important deadlines', '#F44336', '⏰', 1),
                ('Meeting', 'Meetings and conferences', '#795548', '🤝', 1)
            ]
            
            for name, desc, color, icon, is_system in default_categories:
                cursor.execute('''
                INSERT OR IGNORE INTO event_categories 
                (name, description, color, icon, created_at, is_system)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, desc, color, icon, datetime.now().isoformat(), is_system))
            
            conn.commit()
            conn.close()
            
            print("✅ Academic calendar database initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize calendar database: {e}")
            logging.error(f"Calendar database initialization failed: {e}")
            return False

    def _setup_gui(self):
        """Initialize the main GUI"""
        if self.parent_window:
            self.root = self.parent_window
        else:
            self.root = tk.Tk()
            self.root.title("Academic Calendar Management System")
            self.root.geometry("1400x900")
            self.root.minsize(1000, 600)
            
        # Set icon (if available)
        try:
            self.root.iconname("📅")
        except:
            pass
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors and fonts
        self._configure_styles()
        
        # Create main layout
        self._create_layout()
        
        # Setup menu bar
        self._create_menu_bar()
        
        # Setup keyboard shortcuts
        self._setup_shortcuts()
        
        # Start task processor
        self._start_task_processor()
        
    def _configure_styles(self):
        """Configure custom styles for the GUI"""
        # Colors
        bg_color = '#f0f0f0'
        accent_color = '#2E86C1'
        success_color = '#27AE60'
        warning_color = '#F39C12'
        error_color = '#E74C3C'
        
        # Configure styles
        self.style.configure('Sidebar.TFrame', background='#34495E')
        self.style.configure('SidebarButton.TButton', 
                           background='#34495E', 
                           foreground='white',
                           borderwidth=0,
                           focuscolor='none')
        self.style.map('SidebarButton.TButton',
                      background=[('active', '#5D6D7E')])
        
        self.style.configure('Header.TLabel', 
                           font=('Arial', 16, 'bold'),
                           background=bg_color)
        
        self.style.configure('Success.TLabel', foreground=success_color)
        self.style.configure('Warning.TLabel', foreground=warning_color)
        self.style.configure('Error.TLabel', foreground=error_color)
        
    def _create_layout(self):
        """Create the main layout structure"""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.sidebar = ttk.Frame(self.main_frame, style='Sidebar.TFrame', width=250)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        
        # Content area
        self.content_area = ttk.Frame(self.main_frame)
        self.content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create sidebar content
        self._create_sidebar()
        
        # Create status bar
        self._create_status_bar()
        
        # Show initial view
        self._show_dashboard()
        
    def _create_sidebar(self):
        """Create the sidebar navigation with scrollable content"""
        # Logo/Title
        title_frame = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        title_label = ttk.Label(title_frame, text="📅 Calendar", 
                               font=('Arial', 18, 'bold'),
                               background='#34495E', foreground='white')
        title_label.pack()
        
        # Create scrollable frame for navigation
        # Main container for scrollable area
        scroll_container = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        scroll_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas for scrolling
        canvas = tk.Canvas(scroll_container, bg='#34495E', highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Sidebar.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Navigation buttons in scrollable frame
        nav_frame = ttk.Frame(scrollable_frame, style='Sidebar.TFrame')
        nav_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Updated button definitions with new features
        nav_buttons = [
            ("📊 Dashboard", self._show_dashboard),
            ("📅 View Calendar", self._show_calendar_view),
            ("➕ Add Event", self._show_add_event),
            ("📝 Manage Events", self._show_manage_events),
            ("🔄 Recurring Events", self._show_create_recurring_event),
            ("🔍 Advanced Search", self._show_advanced_search),
            ("📚 Academic Years", self._show_academic_years),
            ("📖 Semesters", self._show_semesters),
            ("🏢 Resources", self._show_resource_management),
            ("📚 Courses", self._show_course_management),
            ("🏷️ Categories & Tags", self._show_event_categories),
            ("📊 Reports", self._show_reports),
            ("📈 Visualizations", self._show_data_visualization),
            ("🎯 Milestones", self._show_project_milestones),
            ("🔔 Notifications", self._show_notification_settings),
            ("🌐 Timezone", self._show_timezone_settings),
            ("📤 Export", self._show_export),
            ("🛠️ System", self._show_system_backup),
            ("📋 Audit Logs", self._show_audit_logs),
            ("⚙️ Settings", self._show_settings),
        ]
        
        # Add buttons if user has permissions
        if self.auth_manager and self.auth_manager.current_user:
            for text, command in nav_buttons:
                if self._has_permission_for_button(text):
                    btn = ttk.Button(nav_frame, text=text, 
                                   command=command,
                                   style='SidebarButton.TButton')
                    btn.pack(fill=tk.X, pady=2)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
        
        # Bind mouse wheel events
        canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows
        canvas.bind("<Button-4>", _on_mousewheel_linux)  # Linux
        canvas.bind("<Button-5>", _on_mousewheel_linux)  # Linux
        
        # User info at bottom (fixed position)
        user_frame = ttk.Frame(self.sidebar, style='Sidebar.TFrame')
        user_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        if self.auth_manager and self.auth_manager.current_user:
            user_text = f"👤 {self.auth_manager.current_user['username']}\n({self.auth_manager.current_user['role']})"
            user_label = ttk.Label(user_frame, text=user_text,
                                 background='#34495E', foreground='white',
                                 font=('Arial', 9))
            user_label.pack()
        
        # Backward compatibility button (fixed position)
        compat_btn = ttk.Button(user_frame, text="💻 CLI Mode",
                              command=self._launch_cli_mode,
                              style='SidebarButton.TButton')
        compat_btn.pack(fill=tk.X, pady=(10, 0))
        
    def _create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.status_bar, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        # Progress bar for long operations
        self.progress_bar = ttk.Progressbar(self.status_bar, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2)
        
    def _create_menu_bar(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Calendar...", command=self._show_export)
        file_menu.add_command(label="Import Calendar...", command=self._import_calendar)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database...", command=self._backup_database)
        file_menu.add_command(label="Restore Database...", command=self._restore_database)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Events menu (new)
        events_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Events", menu=events_menu)
        events_menu.add_command(label="Add Event", command=self._show_add_event)
        events_menu.add_command(label="Recurring Event", command=self._show_create_recurring_event)
        events_menu.add_command(label="Advanced Search", command=self._show_advanced_search)
        events_menu.add_separator()
        events_menu.add_command(label="Categories & Tags", command=self._show_event_categories)
        
        # Resources menu (new)
        resources_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Resources", menu=resources_menu)
        resources_menu.add_command(label="Manage Resources", command=self._show_resource_management)
        resources_menu.add_command(label="Manage Courses", command=self._show_course_management)
        resources_menu.add_command(label="Project Milestones", command=self._show_project_milestones)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Dashboard", command=self._show_dashboard)
        view_menu.add_command(label="Calendar", command=self._show_calendar_view)
        view_menu.add_command(label="Events List", command=self._show_manage_events)
        view_menu.add_separator()
        view_menu.add_command(label="Data Visualization", command=self._show_data_visualization)
        view_menu.add_command(label="Reports", command=self._show_reports)
        view_menu.add_separator()
        view_menu.add_command(label="Refresh", command=self._refresh_current_view)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Calendar Sync...", command=self._calendar_sync)
        tools_menu.add_command(label="Import Holidays...", command=self._import_holidays)
        tools_menu.add_command(label="Bulk Operations...", command=self._bulk_operations)
        tools_menu.add_separator()
        tools_menu.add_command(label="System Maintenance", command=self._show_system_backup)
        tools_menu.add_command(label="Audit Logs", command=self._show_audit_logs)
        tools_menu.add_separator()
        tools_menu.add_command(label="CLI Mode", command=self._launch_cli_mode)
        
        # Settings menu (new)
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Notification Settings", command=self._show_notification_settings)
        settings_menu.add_command(label="Timezone Settings", command=self._show_timezone_settings)
        settings_menu.add_command(label="General Settings", command=self._show_settings)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self._show_help)
        help_menu.add_command(label="About", command=self._show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Place a reusable main-menu button in the top-right corner"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-n>', lambda e: self._show_add_event())
        self.root.bind('<Control-e>', lambda e: self._show_export())
        self.root.bind('<Control-r>', lambda e: self._refresh_current_view())
        self.root.bind('<F5>', lambda e: self._refresh_current_view())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        
    def _setup_calendar_manager(self):
        """Setup the calendar manager"""
        try:
            config = CalendarConfig()
            self.calendar_manager = AcademicCalendarManager(
                config=config, 
                auth_manager=self.auth_manager
            )
            self._update_status("Calendar system initialized successfully")
        except Exception as e:
            self._show_error(f"Failed to initialize calendar system: {e}")
            gui_logger.error(f"Calendar initialization failed: {e}")
    
    def _has_permission_for_button(self, button_text: str) -> bool:
        """Check if user has permission for a specific button"""
        if not self.auth_manager or not self.auth_manager.current_user:
            return False
            
        permission_map = {
            "➕ Add Event": "manage_schedules",
            "📝 Manage Events": "manage_schedules",
            "🔄 Recurring Events": "manage_schedules",
            "📚 Academic Years": "manage_schedules",
            "📖 Semesters": "manage_schedules",
            "🏢 Resources": "manage_schedules",
            "📚 Courses": "manage_schedules",
            "🏷️ Categories & Tags": "manage_schedules",
            "🎯 Milestones": "manage_schedules",
            "🔔 Notifications": "view_own_timetable",
            "🌐 Timezone": "view_own_timetable",
            "📊 Reports": "view_reports",
            "📈 Visualizations": "export_data",
            "📤 Export": "export_data",
            "🛠️ System": "system_config",
            "📋 Audit Logs": "system_config",
            "⚙️ Settings": "system_config",
        }
        
        required_permission = permission_map.get(button_text)
        if not required_permission:
            return True  # No specific permission required
            
        return self.auth_manager.check_permission(required_permission)

    def _show_resource_management(self):
        """Show resource management dialog"""
        ResourceManagementDialog(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_course_management(self):
        """Show course management dialog"""
        CourseManagementDialog(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_notification_settings(self):
        """Show notification settings dialog"""
        NotificationSettingsDialog(self.root, self.calendar_manager, self.auth_manager, self._refresh_current_view)

    def _show_event_categories(self):
        """Show event categories dialog"""
        EventCategoriesDialog(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_advanced_search(self):
        """Show advanced search dialog"""
        AdvancedSearchDialog(self.root, self.calendar_manager)

    def _show_create_recurring_event(self):
        """Show create recurring event dialog"""
        RecurringEventDialog(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_system_backup(self):
        """Show system backup and maintenance options"""
        SystemMaintenanceDialog(self.root, self.calendar_manager, self.auth_manager)

    def _show_audit_logs(self):
        """Show audit logs dialog"""
        AuditLogsDialog(self.root, self.calendar_manager)

    def _show_project_milestones(self):
        """Show project milestones dialog"""
        ProjectMilestonesDialog(self.root, self.calendar_manager, self._refresh_current_view)

    def _show_data_visualization(self):
        """Show data visualization dialog"""
        DataVisualizationDialog(self.root, self.calendar_manager)

    def _show_timezone_settings(self):
        """Show timezone settings dialog"""
        TimezoneSettingsDialog(self.root, self.calendar_manager, self.auth_manager)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-n>', lambda e: self._show_add_event())
        self.root.bind('<Control-e>', lambda e: self._show_export())
        self.root.bind('<Control-r>', lambda e: self._refresh_current_view())
        self.root.bind('<F5>', lambda e: self._refresh_current_view())
        self.root.bind('<Control-f>', lambda e: self._show_advanced_search())
        # Fix: Use proper key binding syntax for Shift combinations
        self.root.bind('<Control-Shift-R>', lambda e: self._show_create_recurring_event())
        self.root.bind('<Control-Shift-N>', lambda e: self._show_notification_settings())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

    def _start_task_processor(self):
        """Start background task processor"""
        def process_tasks():
            try:
                while True:
                    task = self.task_queue.get(timeout=0.1)
                    if task is None:
                        break
                    try:
                        task()
                    except Exception as e:
                        gui_logger.error(f"Task failed: {e}")
                        self.root.after(0, lambda: self._show_error(f"Operation failed: {e}"))
                    finally:
                        self.task_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                gui_logger.error(f"Task processor error: {e}")
            
            # Schedule next check
            self.root.after(100, process_tasks)
        
        self.root.after(100, process_tasks)
    
    def _clear_content_area(self):
        """Clear the content area"""
        for widget in self.content_area.winfo_children():
            widget.destroy()
    
    def _update_status(self, message: str, status_type: str = "info"):
        """Update status bar message"""
        self.status_label.config(text=message)
        if status_type == "error":
            self.status_label.config(foreground='red')
        elif status_type == "success":
            self.status_label.config(foreground='green')
        elif status_type == "warning":
            self.status_label.config(foreground='orange')
        else:
            self.status_label.config(foreground='black')
    
    def _show_progress(self, show: bool = True):
        """Show/hide progress bar"""
        if show:
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
    
    def _show_error(self, message: str):
        """Show error message"""
        messagebox.showerror("Error", message)
        self._update_status(f"Error: {message}", "error")
    
    def _show_success(self, message: str):
        """Show success message"""
        messagebox.showinfo("Success", message)
        self._update_status(message, "success")
    
    def _show_warning(self, message: str):
        """Show warning message"""
        messagebox.showwarning("Warning", message)
        self._update_status(f"Warning: {message}", "warning")
    
    # Main view methods
    def _show_dashboard(self):
        """Show dashboard view"""
        self._clear_content_area()
        self.current_view = "dashboard"
        
        # Dashboard header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(header_frame, text="📊 Dashboard", style='Header.TLabel').pack(side=tk.LEFT)
        
        refresh_btn = ttk.Button(header_frame, text="🔄 Refresh", 
                               command=self._refresh_dashboard)
        refresh_btn.pack(side=tk.RIGHT)
        
        # Dashboard content
        dashboard_frame = ttk.Frame(self.content_area)
        dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self._create_dashboard_content(dashboard_frame)
    
    def _create_dashboard_content(self, parent):
        """Create dashboard content"""
        try:
            # Stats cards row
            stats_frame = ttk.Frame(parent)
            stats_frame.pack(fill=tk.X, pady=(0, 20))
            
            # Get system stats
            if self.calendar_manager:
                stats = self.calendar_manager.get_system_stats()
                
                # Total events card
                self._create_stat_card(stats_frame, "📅 Total Events", 
                                     sum(stats.get('events_by_type', {}).values()),
                                     "All events in system")
                
                # Current academic year card
                self._create_stat_card(stats_frame, "📚 Academic Year",
                                     stats.get('current_academic_year', 'None'),
                                     "Current active year")
                
                # Current semester card
                self._create_stat_card(stats_frame, "📖 Semester",
                                     stats.get('current_semester', 'None'),
                                     "Current active semester")
                
                # Upcoming events card
                self._create_stat_card(stats_frame, "⏰ Upcoming",
                                     stats.get('upcoming_events', 0),
                                     "Events in next 30 days")
            
            # Recent events section
            recent_frame = ttk.LabelFrame(parent, text="Recent Events", padding=10)
            recent_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            self._create_recent_events_list(recent_frame)
            
            # Quick actions section
            actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding=10)
            actions_frame.pack(fill=tk.X)
            
            self._create_quick_actions(actions_frame)
            
        except Exception as e:
            gui_logger.error(f"Dashboard creation failed: {e}")
            ttk.Label(parent, text=f"Error loading dashboard: {e}").pack()
    
    def _create_stat_card(self, parent, title, value, description):
        """Create a statistics card"""
        card_frame = ttk.Frame(parent)
        card_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Card content
        card_content = ttk.LabelFrame(card_frame, text=title, padding=10)
        card_content.pack(fill=tk.BOTH, expand=True)
        
        # Value
        value_label = ttk.Label(card_content, text=str(value), 
                               font=('Arial', 18, 'bold'))
        value_label.pack()
        
        # Description
        desc_label = ttk.Label(card_content, text=description,
                              font=('Arial', 9))
        desc_label.pack()
    
    def _create_recent_events_list(self, parent):
        """Create recent events list"""
        try:
            # Get recent events
            if self.calendar_manager:
                current_date = datetime.now().strftime("%Y-%m-%d")
                future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                
                events = self.calendar_manager.get_events_by_date_range(
                    current_date, future_date
                )[:10]  # Limit to 10 events
                
                if events:
                    # Treeview for events
                    tree = ttk.Treeview(parent, columns=('Date', 'Type', 'Description'), 
                                       show='tree headings', height=8)
                    tree.pack(fill=tk.BOTH, expand=True)
                    
                    # Configure columns
                    tree.heading('#0', text='Event Name')
                    tree.heading('Date', text='Date')
                    tree.heading('Type', text='Type')
                    tree.heading('Description', text='Description')
                    
                    tree.column('#0', width=200)
                    tree.column('Date', width=100)
                    tree.column('Type', width=100)
                    tree.column('Description', width=300)
                    
                    # Add events
                    for event in events:
                        event_date = event['date'] or event['date_start']
                        description = (event['description'] or '')[:50]
                        if len(event['description'] or '') > 50:
                            description += "..."
                        
                        tree.insert('', 'end', text=event['name'],
                                   values=(event_date, event['event_type'], description))
                    
                    # Scrollbar
                    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                else:
                    ttk.Label(parent, text="No upcoming events found").pack()
            else:
                ttk.Label(parent, text="Calendar manager not available").pack()
                
        except Exception as e:
            gui_logger.error(f"Recent events list creation failed: {e}")
            ttk.Label(parent, text=f"Error loading events: {e}").pack()
    
    def _create_quick_actions(self, parent):
        """Create quick action buttons"""
        actions = [
            ("➕ Add Event", self._show_add_event),
            ("📅 View Calendar", self._show_calendar_view),
            ("📤 Export", self._show_export),
            ("🔧 Settings", self._show_settings)
        ]
        
        for text, command in actions:
            if self._has_permission_for_button(text):
                btn = ttk.Button(parent, text=text, command=command)
                btn.pack(side=tk.LEFT, padx=5)
    
    def _show_calendar_view(self):
        """Show calendar view"""
        self._clear_content_area()
        self.current_view = "calendar"
        
        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(header_frame, text="📅 Calendar View", style='Header.TLabel').pack(side=tk.LEFT)
        
        # Filters
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        
        ttk.Label(filter_frame, text="Academic Year:").pack(side=tk.LEFT, padx=(0, 5))
        self.year_var = tk.StringVar()
        year_combo = ttk.Combobox(filter_frame, textvariable=self.year_var, width=15)
        year_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(filter_frame, text="Semester:").pack(side=tk.LEFT, padx=(0, 5))
        self.semester_var = tk.StringVar()
        semester_combo = ttk.Combobox(filter_frame, textvariable=self.semester_var, width=15)
        semester_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        view_btn = ttk.Button(filter_frame, text="View", command=self._load_calendar_data)
        view_btn.pack(side=tk.LEFT)
        
        # Content area
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create treeview for calendar data
        self._create_calendar_treeview(content_frame)
        
        # Load initial data
        self._load_calendar_data()
    
    def _create_calendar_treeview(self, parent):
        """Create treeview for calendar display"""
        # Treeview
        self.calendar_tree = ttk.Treeview(parent, 
                                        columns=('Date', 'End Date', 'Type', 'Description'),
                                        show='tree headings')
        self.calendar_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.calendar_tree.heading('#0', text='Event Name')
        self.calendar_tree.heading('Date', text='Start Date')
        self.calendar_tree.heading('End Date', text='End Date')
        self.calendar_tree.heading('Type', text='Type')
        self.calendar_tree.heading('Description', text='Description')
        
        self.calendar_tree.column('#0', width=250)
        self.calendar_tree.column('Date', width=120)
        self.calendar_tree.column('End Date', width=120)
        self.calendar_tree.column('Type', width=120)
        self.calendar_tree.column('Description', width=300)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.calendar_tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.calendar_tree.xview)
        
        self.calendar_tree.configure(yscrollcommand=v_scrollbar.set, 
                                   xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Context menu
        self._create_calendar_context_menu()
    
    def _create_calendar_context_menu(self):
        """Create context menu for calendar items"""
        self.calendar_context_menu = tk.Menu(self.root, tearoff=0)
        self.calendar_context_menu.add_command(label="Edit Event", command=self._edit_selected_event)
        self.calendar_context_menu.add_command(label="Delete Event", command=self._delete_selected_event)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label="View Details", command=self._view_event_details)
        self.calendar_context_menu.add_separator()
        self.calendar_context_menu.add_command(label="📧 Send Email Reminder", command=self._send_email_reminder)
        
        def show_context_menu(event):
            try:
                self.calendar_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.calendar_context_menu.grab_release()
        
        self.calendar_tree.bind("<Button-3>", show_context_menu)  # Right click
    
    def _load_calendar_data(self):
        """Load calendar data into treeview"""
        try:
            if not self.calendar_manager:
                return
            
            # Clear existing data
            for item in self.calendar_tree.get_children():
                self.calendar_tree.delete(item)
            
            # Get filter values
            academic_year = self.year_var.get() if hasattr(self, 'year_var') else None
            semester = self.semester_var.get() if hasattr(self, 'semester_var') else None
            
            academic_year = academic_year if academic_year and academic_year != '' else None
            semester = semester if semester and semester != '' else None
            
            # Get calendar data
            success, data = self.calendar_manager.view_calendar(academic_year, semester)
            
            if success and data:
                # Group by semester
                semester_groups = {}
                for item in data:
                    semester_name = item.get('semester_name', 'Unknown')
                    if semester_name not in semester_groups:
                        semester_groups[semester_name] = []
                    if item.get('event_name'):  # Only add items with events
                        semester_groups[semester_name].append(item)
                
                # Add to treeview
                for semester_name, events in semester_groups.items():
                    if events:  # Only show semesters with events
                        # Add semester header
                        semester_node = self.calendar_tree.insert('', 'end', 
                                                                text=f"📖 {semester_name}",
                                                                values=('', '', 'Semester', ''),
                                                                open=True)
                        
                        # Add events
                        for event in events:
                            event_date = event.get('date') or event.get('date_start', '')
                            end_date = event.get('date_end', '')
                            event_type = event.get('event_type', '')
                            description = event.get('description', '')[:100]
                            
                            # Add event type icon
                            type_icons = {
                                'Academic': '📚',
                                'Holiday': '🎉',
                                'Administrative': '📋',
                                'Trip': '🎒',
                                'Deadline': '⏰',
                                'Social': '🎊',
                                'Sports': '⚽'
                            }
                            icon = type_icons.get(event_type, '📅')
                            
                            self.calendar_tree.insert(semester_node, 'end',
                                                    text=f"{icon} {event['event_name']}",
                                                    values=(event_date, end_date, event_type, description))
                
                self._update_status(f"Loaded {len(data)} calendar items", "success")
            else:
                self._update_status("No calendar data found", "warning")
                
        except Exception as e:
            gui_logger.error(f"Failed to load calendar data: {e}")
            self._show_error(f"Failed to load calendar: {e}")
    
    def _show_add_event(self):
        """Show add event dialog"""
        AddEventDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _show_manage_events(self):
        """Show event management view"""
        self._clear_content_area()
        self.current_view = "manage_events"
        
        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(header_frame, text="📝 Manage Events", style='Header.TLabel').pack(side=tk.LEFT)
        
        # Action buttons
        action_frame = ttk.Frame(header_frame)
        action_frame.pack(side=tk.RIGHT)
        
        ttk.Button(action_frame, text="➕ Add Event", 
                  command=self._show_add_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🔄 Refresh", 
                  command=self._refresh_manage_events).pack(side=tk.LEFT, padx=5)
        
        # Search frame
        search_frame = ttk.Frame(self.content_area)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind('<KeyRelease>', lambda e: self._search_events())
        
        ttk.Button(search_frame, text="🔍 Search", 
                  command=self._search_events).pack(side=tk.LEFT, padx=5)
        
        # Events list
        events_frame = ttk.Frame(self.content_area)
        events_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self._create_events_treeview(events_frame)
        self._load_events_data()
    
    def _create_events_treeview(self, parent):
        """Create treeview for events management"""
        # Treeview
        self.events_tree = ttk.Treeview(parent,
                                      columns=('ID', 'Date', 'End Date', 'Type', 'Description', 'full_data'),
                                      show='tree headings')
        self.events_tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        self.events_tree.heading('#0', text='Event Name')
        self.events_tree.heading('ID', text='ID')
        self.events_tree.heading('Date', text='Start Date')
        self.events_tree.heading('End Date', text='End Date')
        self.events_tree.heading('Type', text='Type')
        self.events_tree.heading('Description', text='Description')
        self.events_tree.heading('full_data', text='')  # Hidden column

        self.events_tree.column('#0', width=200)
        self.events_tree.column('ID', width=80)
        self.events_tree.column('Date', width=100)
        self.events_tree.column('End Date', width=100)
        self.events_tree.column('Type', width=120)
        self.events_tree.column('Description', width=300)
        self.events_tree.column('full_data', width=0, minwidth=0, stretch=False)  # Hide this column
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.events_tree.yview)
        h_scrollbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.events_tree.xview)
        
        self.events_tree.configure(yscrollcommand=v_scrollbar.set, 
                                 xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Context menu
        self._create_events_context_menu()
        
        # Double-click to edit
        self.events_tree.bind('<Double-1>', lambda e: self._edit_selected_event())
    
    def _create_events_context_menu(self):
        """Create context menu for events management"""
        self.events_context_menu = tk.Menu(self.root, tearoff=0)
        self.events_context_menu.add_command(label="✏️ Edit Event", command=self._edit_selected_event)
        self.events_context_menu.add_command(label="🗑️ Delete Event", command=self._delete_selected_event)
        self.events_context_menu.add_separator()
        self.events_context_menu.add_command(label="📋 Copy ID", command=self._copy_event_id)
        self.events_context_menu.add_command(label="📄 View Details", command=self._view_event_details)
        self.events_context_menu.add_separator()
        self.events_context_menu.add_command(label="📧 Send Email Reminder", command=self._send_email_reminder)
        
        def show_context_menu(event):
            try:
                self.events_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.events_context_menu.grab_release()
        
        self.events_tree.bind("<Button-3>", show_context_menu)
    
    def _load_events_data(self):
        """Load events data into treeview"""
        try:
            if not self.calendar_manager:
                return

            # Clear existing data
            for item in self.events_tree.get_children():
                self.events_tree.delete(item)

            # Get all events (recent first)
            current_date = datetime.now().strftime("%Y-%m-%d")
            past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            future_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

            events = self.calendar_manager.get_events_by_date_range(past_date, future_date)

            # Load and integrate trip data
            trip_events = self._get_trip_events(past_date, future_date)
            events.extend(trip_events)

            # Load and integrate assignment due dates
            assignment_events = self._get_assignment_events(past_date, future_date)
            events.extend(assignment_events)

            # Load and integrate finance payment due dates
            finance_events = self._get_finance_events(past_date, future_date)
            events.extend(finance_events)

            # Load and integrate library return due dates
            library_events = self._get_library_events(past_date, future_date)
            events.extend(library_events)
            
            # Sort by date (most recent first)
            events.sort(key=lambda x: x.get('date') or x.get('date_start') or '', reverse=True)
            
            # Add to treeview
            for event in events:
                event_date = event.get('date') or event.get('date_start', '')
                end_date = event.get('date_end', '')
                event_type = event.get('event_type', '')
                description = (event.get('description', '') or '')[:100]
                event_id = event['id'][:8] + "..." if len(event['id']) > 8 else event['id']
                
                # Add event type icon
                type_icons = {
                    'Academic': '📚',
                    'Holiday': '🎉',
                    'Administrative': '📋',
                    'Trip': '🎒',
                    'Deadline': '⏰',
                    'Social': '🎊',
                    'Sports': '⚽',
                    'Finance': '💰',
                    'Payment': '💳',
                    'Library': '📖'
                }
                icon = type_icons.get(event_type, '📅')
                
                item_id = self.events_tree.insert('', 'end',
                                                 text=f"{icon} {event['name']}",
                                                 values=(event_id, event_date, end_date, 
                                                        event_type, description))
                
                # Store full event data as JSON
                import json
                self.events_tree.set(item_id, 'full_data', json.dumps(dict(event) if hasattr(event, 'keys') else event))
            
            self._update_status(f"Loaded {len(events)} events", "success")

        except Exception as e:
            gui_logger.error(f"Failed to load events: {e}")
            self._show_error(f"Failed to load events: {e}")

    def _get_trip_events(self, start_date, end_date):
        """Get trip events from trip management system"""
        trip_events = []
        try:
            from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT trip_name, start_date, end_date, description, id
                    FROM trips
                    WHERE (start_date BETWEEN ? AND ?) OR (end_date BETWEEN ? AND ?)
                    OR (start_date <= ? AND end_date >= ?)
                    ORDER BY start_date
                ''', (start_date, end_date, start_date, end_date, start_date, end_date))

                for trip in cursor.fetchall():
                    trip_events.append({
                        'id': f'trip_{trip[4]}',
                        'name': f"🎒 {trip[0]}",
                        'date': trip[1],
                        'date_start': trip[1],
                        'date_end': trip[2],
                        'event_type': 'Trip',
                        'description': f"Trip: {trip[3] or 'No description'}",
                        'source': 'trip_management'
                    })
        except Exception as e:
            gui_logger.warning(f"Failed to load trip events: {e}")

        return trip_events

    def _get_assignment_events(self, start_date, end_date):
        """Get assignment due dates from assignment system"""
        assignment_events = []
        try:
            from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, due_date, module_code, description, id
                    FROM assignments
                    WHERE due_date BETWEEN ? AND ? AND is_active = 1
                    ORDER BY due_date
                ''', (start_date, end_date))

                for assignment in cursor.fetchall():
                    assignment_events.append({
                        'id': f'assignment_{assignment[4]}',
                        'name': f"📝 {assignment[0]}",
                        'date': assignment[1],
                        'date_start': assignment[1],
                        'date_end': assignment[1],
                        'event_type': 'Deadline',
                        'description': f"Assignment due ({assignment[2]}): {assignment[3] or 'No description'}",
                        'source': 'assignments'
                    })
        except Exception as e:
            gui_logger.warning(f"Failed to load assignment events: {e}")

        return assignment_events

    def _get_finance_events(self, start_date, end_date):
        """Get finance payment due dates from finance system"""
        finance_events = []
        try:
            from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get payment due dates for student fees
                cursor.execute('''
                    SELECT ft.fee_name, f.due_date, f.amount, s.first_name, s.last_name, f.student_fee_id
                    FROM student_fees f
                    JOIN students s ON f.student_id = s.student_id
                    LEFT JOIN fee_types ft ON f.fee_type_id = ft.fee_type_id
                    WHERE f.due_date BETWEEN ? AND ? AND f.status != 'paid'
                    ORDER BY f.due_date
                ''', (start_date, end_date))

                for fee in cursor.fetchall():
                    fee_name = fee[0] if fee[0] else 'Fee'
                    finance_events.append({
                        'id': f'fee_{fee[5]}',
                        'name': f"💳 {fee_name} Due",
                        'date': fee[1],
                        'date_start': fee[1],
                        'date_end': fee[1],
                        'event_type': 'Payment',
                        'description': f"Payment due: {fee_name} - ${fee[2]:.2f} ({fee[3]} {fee[4]})",
                        'source': 'finance'
                    })

                # Get scholarship deadlines (using correct schema)
                try:
                    cursor.execute('''
                        SELECT sch.scholarship_name, sch.deadline, sch.amount, sch.scholarship_id
                        FROM scholarships sch
                        WHERE sch.deadline BETWEEN ? AND ? AND sch.is_active = 1
                        ORDER BY sch.deadline
                    ''', (start_date, end_date))

                    for scholarship in cursor.fetchall():
                        finance_events.append({
                            'id': f'scholarship_{scholarship[3]}',
                            'name': f"💰 {scholarship[0]} Deadline",
                            'date': scholarship[1],
                            'date_start': scholarship[1],
                            'date_end': scholarship[1],
                            'event_type': 'Finance',
                            'description': f"Scholarship deadline: {scholarship[0]} - ${scholarship[2]:.2f}",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load scholarship events: {e}")

                # Get financial aid application deadlines
                try:
                    cursor.execute('''
                        SELECT fat.aid_name, fat.application_deadline, fat.max_amount, fat.aid_type_id
                        FROM financial_aid_types fat
                        WHERE fat.application_deadline BETWEEN ? AND ?
                          AND fat.is_active = 1
                        ORDER BY fat.application_deadline
                    ''', (start_date, end_date))

                    for aid_type in cursor.fetchall():
                        finance_events.append({
                            'id': f'aid_deadline_{aid_type[3]}',
                            'name': f"📝 {aid_type[0]} Deadline",
                            'date': aid_type[1],
                            'date_start': aid_type[1],
                            'date_end': aid_type[1],
                            'event_type': 'Finance',
                            'description': f"Financial aid application deadline: {aid_type[0]} - Max ${aid_type[2]:.2f}",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load financial aid deadlines: {e}")

                # Get student financial aid approval/disbursement dates
                try:
                    cursor.execute('''
                        SELECT sfa.aid_id, fat.aid_name, sfa.approval_date, sfa.awarded_amount,
                               s.first_name, s.last_name, sfa.status
                        FROM student_financial_aid sfa
                        JOIN students s ON sfa.student_id = s.student_id
                        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        WHERE sfa.approval_date BETWEEN ? AND ?
                          AND sfa.status IN ('approved', 'disbursed', 'completed')
                        ORDER BY sfa.approval_date
                    ''', (start_date, end_date))

                    for aid in cursor.fetchall():
                        finance_events.append({
                            'id': f'aid_approval_{aid[0]}',
                            'name': f"✅ {aid[1]} Approved",
                            'date': aid[2],
                            'date_start': aid[2],
                            'date_end': aid[2],
                            'event_type': 'Finance',
                            'description': f"{aid[1]} approved for {aid[4]} {aid[5]} - ${aid[3]:.2f} (Status: {aid[6]})",
                            'source': 'finance'
                        })
                except Exception as e:
                    gui_logger.debug(f"Could not load student financial aid: {e}")

        except Exception as e:
            gui_logger.warning(f"Failed to load finance events: {e}")

        return finance_events

    def _get_library_events(self, start_date, end_date):
        """Get library book return due dates from library system"""
        library_events = []
        try:
            from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get book return due dates
                cursor.execute('''
                    SELECT bl.book_id, bl.user_id, bl.due_date,
                           b.title, b.author,
                           s.first_name, s.last_name, bl.loan_id
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    JOIN students s ON bl.user_id = s.student_id
                    WHERE bl.due_date BETWEEN ? AND ? AND bl.status = 'active'
                    ORDER BY bl.due_date
                ''', (start_date, end_date))

                for loan in cursor.fetchall():
                    book_id, user_id, due_date, title, author, first_name, last_name, loan_id = loan
                    library_events.append({
                        'id': f'library_{loan_id}',
                        'name': f"📖 {title} Return Due",
                        'date': due_date,
                        'date_start': due_date,
                        'date_end': due_date,
                        'event_type': 'Library',
                        'description': f"Book return due: {title} by {author} (borrowed by {first_name} {last_name})",
                        'source': 'library'
                    })

        except Exception as e:
            gui_logger.warning(f"Failed to load library events: {e}")

        return library_events

    def _search_events(self):
        """Search events based on search term"""
        search_term = self.search_var.get().lower()
        
        # Show/hide items based on search
        for item in self.events_tree.get_children():
            event_name = self.events_tree.item(item, 'text').lower()
            values = [str(v).lower() for v in self.events_tree.item(item, 'values')]
            
            if (search_term in event_name or 
                any(search_term in v for v in values)):
                # Show item
                self.events_tree.item(item, tags=())
            else:
                # Hide item (by moving it out of view)
                self.events_tree.item(item, tags=('hidden',))
        
        # Configure hidden tag
        self.events_tree.tag_configure('hidden', foreground='gray')
    
    def _show_academic_years(self):
        """Show academic years management"""
        self._clear_content_area()
        self.current_view = "academic_years"
        
        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(header_frame, text="📚 Academic Years", style='Header.TLabel').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="➕ Add Year", 
                  command=self._add_academic_year).pack(side=tk.RIGHT, padx=5)
        
        # Academic years list
        years_frame = ttk.LabelFrame(self.content_area, text="Academic Years", padding=10)
        years_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self._create_academic_years_list(years_frame)
    
    def _create_academic_years_list(self, parent):
        """Create academic years list"""
        try:
            if not self.calendar_manager:
                return
            
            # Get academic years
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM academic_years ORDER BY start_date DESC"
            )
            
            if years:
                # Treeview
                years_tree = ttk.Treeview(parent, columns=('Start', 'End', 'Added'), show='tree headings')
                years_tree.pack(fill=tk.BOTH, expand=True)
                
                years_tree.heading('#0', text='Academic Year')
                years_tree.heading('Start', text='Start Date')
                years_tree.heading('End', text='End Date')
                years_tree.heading('Added', text='Date Added')
                
                years_tree.column('#0', width=150)
                years_tree.column('Start', width=120)
                years_tree.column('End', width=120)
                years_tree.column('Added', width=150)
                
                # Add years
                for year in years:
                    added_date = year['date_added'][:10] if year['date_added'] else ''
                    years_tree.insert('', 'end', text=year['id'],
                                    values=(year['start_date'], year['end_date'], added_date))
                
                # Scrollbar
                scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=years_tree.yview)
                years_tree.configure(yscrollcommand=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(parent, text="No academic years found. Add one to get started.").pack()
                
        except Exception as e:
            gui_logger.error(f"Failed to load academic years: {e}")
            ttk.Label(parent, text=f"Error loading academic years: {e}").pack()
    
    def _show_semesters(self):
        """Show semesters management"""
        self._clear_content_area()
        self.current_view = "semesters"
        
        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(header_frame, text="📖 Semesters", style='Header.TLabel').pack(side=tk.LEFT)
        
        ttk.Button(header_frame, text="➕ Add Semester", 
                  command=self._add_semester).pack(side=tk.RIGHT, padx=5)
        
        # Semesters list
        semesters_frame = ttk.LabelFrame(self.content_area, text="Semesters", padding=10)
        semesters_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self._create_semesters_list(semesters_frame)
    
    def _create_semesters_list(self, parent):
        """Create semesters list"""
        try:
            if not self.calendar_manager:
                return
            
            # Get semesters
            semesters = self.calendar_manager.db_manager.execute_query("""
                SELECT s.*, ay.id as year_id FROM semesters s
                JOIN academic_years ay ON s.academic_year_id = ay.id
                ORDER BY ay.start_date DESC, s.start_date
            """)
            
            if semesters:
                # Treeview
                sem_tree = ttk.Treeview(parent, 
                                      columns=('Year', 'Start', 'End', 'Added'), 
                                      show='tree headings')
                sem_tree.pack(fill=tk.BOTH, expand=True)
                
                sem_tree.heading('#0', text='Semester Name')
                sem_tree.heading('Year', text='Academic Year')
                sem_tree.heading('Start', text='Start Date')
                sem_tree.heading('End', text='End Date')
                sem_tree.heading('Added', text='Date Added')
                
                sem_tree.column('#0', width=150)
                sem_tree.column('Year', width=120)
                sem_tree.column('Start', width=120)
                sem_tree.column('End', width=120)
                sem_tree.column('Added', width=150)
                
                # Add semesters
                for semester in semesters:
                    added_date = semester['date_added'][:10] if semester['date_added'] else ''
                    sem_tree.insert('', 'end', text=semester['name'],
                                  values=(semester['year_id'], semester['start_date'], 
                                         semester['end_date'], added_date))
                
                # Scrollbar
                scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=sem_tree.yview)
                sem_tree.configure(yscrollcommand=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(parent, text="No semesters found. Add academic years first.").pack()
                
        except Exception as e:
            gui_logger.error(f"Failed to load semesters: {e}")
            ttk.Label(parent, text=f"Error loading semesters: {e}").pack()
    
    def _show_recurring_events(self):
        """Show recurring events management"""
        RecurringEventsDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _show_reports(self):
        """Show reports view"""
        ReportsDialog(self.root, self.calendar_manager)
    
    def return_to_main_menu(self):
        """Return to main menu"""
        try:
            # Determine which window to close
            window_to_close = self.parent_window if self.parent_window else self.root

            # Check if it's a child window (Toplevel) or standalone (Tk)
            if isinstance(window_to_close, tk.Toplevel):
                # Just close the child window
                window_to_close.destroy()
            else:
                # Running standalone, need to create main GUI if auth available
                if self.auth_manager:
                    window_to_close.destroy()
                    from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                    app = UnifiedManagementGUI(self.auth_manager)
                    app.run()
                else:
                    from tkinter import messagebox
                    messagebox.showinfo("Info", "No main menu available - running standalone")
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def _show_export(self):
        """Show export dialog"""
        ExportDialog(self.root, self.calendar_manager)

    def _show_settings(self):
        """Show settings dialog"""
        SettingsDialog(self.root, self.calendar_manager, self.auth_manager)
    
    # Dialog and action methods
    def _add_academic_year(self):
        """Add academic year dialog"""
        AddAcademicYearDialog(self.root, self.calendar_manager, 
                            lambda: self._refresh_current_view())
    
    def _add_semester(self):
        """Add semester dialog"""
        AddSemesterDialog(self.root, self.calendar_manager, 
                        lambda: self._refresh_current_view())
    
    def _edit_selected_event(self):
        """Edit selected event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []
        
        if selection:
            item = selection[0]
            # Get event data from the item
            if hasattr(self, 'events_tree') and self.events_tree.exists(item):
                event_data_json = self.events_tree.set(item, 'full_data')
                if event_data_json:
                    try:
                        import json
                        event_data = json.loads(event_data_json)
                        EditEventDialog(self.root, self.calendar_manager, event_data,
                                      self._refresh_current_view)
                        return
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, treat as string (fallback)
                        pass
            
            # Fallback: get event by name
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')
            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])
            
            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    EditEventDialog(self.root, self.calendar_manager, dict(events[0]), 
                                  self._refresh_current_view)
                else:
                    self._show_error("Event not found")
            except Exception as e:
                self._show_error(f"Failed to load event: {e}")
        else:
            self._show_warning("Please select an event to edit")
    
    def _delete_selected_event(self):
        """Delete selected event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []
        
        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')
            
            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])
            
            if messagebox.askyesno("Confirm Delete", 
                                 f"Are you sure you want to delete '{event_name}'?"):
                try:
                    # Get event ID
                    events = self.calendar_manager.db_manager.execute_query(
                        "SELECT id FROM events WHERE name = ? LIMIT 1", (event_name,)
                    )
                    if events:
                        result = self.calendar_manager.delete_event(events[0]['id'])
                        if result['success']:
                            self._show_success(result['message'])
                            self._refresh_current_view()
                        else:
                            self._show_error(result['message'])
                    else:
                        self._show_error("Event not found")
                except Exception as e:
                    self._show_error(f"Failed to delete event: {e}")
        else:
            self._show_warning("Please select an event to delete")
    
    def _view_event_details(self):
        """View event details"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []
        
        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text') if hasattr(self, 'events_tree') else \
                        self.calendar_tree.item(item, 'text')
            
            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])
            
            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    EventDetailsDialog(self.root, dict(events[0]))
                else:
                    self._show_error("Event not found")
            except Exception as e:
                self._show_error(f"Failed to load event details: {e}")
        else:
            self._show_warning("Please select an event to view")
    
    def _copy_event_id(self):
        """Copy event ID to clipboard"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        
        if selection:
            item = selection[0]
            event_name = self.events_tree.item(item, 'text')
            
            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])
            
            try:
                events = self.calendar_manager.db_manager.execute_query(
                    "SELECT id FROM events WHERE name = ? LIMIT 1", (event_name,)
                )
                if events:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(events[0]['id'])
                    self._update_status("Event ID copied to clipboard", "success")
                else:
                    self._show_error("Event not found")
            except Exception as e:
                self._show_error(f"Failed to copy ID: {e}")

    def _send_email_reminder(self):
        """Send email reminder for selected calendar event"""
        selection = self.events_tree.selection() if hasattr(self, 'events_tree') else []
        if not selection:
            selection = self.calendar_tree.selection() if hasattr(self, 'calendar_tree') else []

        if not selection:
            safe_show_warning("No Selection", "Please select an event to send reminder for.", self.root)
            return

        try:
            item = selection[0]
            # Get event details
            if hasattr(self, 'events_tree') and self.events_tree.exists(item):
                event_name = self.events_tree.item(item, 'text')
                values = self.events_tree.item(item, 'values')
                event_date = values[1] if len(values) > 1 else 'Unknown'
                event_type = values[3] if len(values) > 3 else 'Event'
                description = values[4] if len(values) > 4 else ''
            else:
                event_name = self.calendar_tree.item(item, 'text')
                values = self.calendar_tree.item(item, 'values')
                event_date = values[0] if len(values) > 0 else 'Unknown'
                event_type = values[2] if len(values) > 2 else 'Event'
                description = values[3] if len(values) > 3 else ''

            # Remove icon from name
            if ' ' in event_name:
                event_name = ' '.join(event_name.split(' ')[1:])

            # Launch email GUI with pre-filled reminder
            self._launch_email_reminder_dialog(event_name, event_date, event_type, description)

        except Exception as e:
            self._show_error(f"Failed to prepare email reminder: {e}")

    def _launch_email_reminder_dialog(self, event_name, event_date, event_type, description):
        """Launch email dialog for calendar reminder"""
        try:
            # Try to import and use the email manager GUI
            from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI

            # Create email dialog
            email_dialog = tk.Toplevel(self.root)
            email_dialog.title("Send Calendar Reminder")
            email_dialog.geometry("600x500")
            email_dialog.transient(self.root)

            # Create email manager instance
            email_manager = EmailManagerGUI(parent=email_dialog)

            # Pre-fill email with calendar event details using template system
            from university_system.infrastructure.email.template_utils import render_template

            try:
                subject, message = render_template("calendar_reminder", {
                    "event_name": event_name,
                    "event_date": event_date,
                    "event_time": event_time,
                    "event_type": event_type,
                    "location": location,
                    "description": description if description else 'No additional details provided.',
                    "first_name": first_name
                })

            except Exception as e:
                # Error handling for template rendering
                subject = None
                message = None

            # Set the email content if the email manager supports it
            if subject and message and hasattr(email_manager, 'set_email_content'):
                email_manager.set_email_content(subject, message)

        except ImportError:
            # Fallback to simple dialog if email GUI not available
            self._show_simple_email_dialog(event_name, event_date, event_type, description)
        except Exception as e:
            self._show_error(f"Failed to launch email dialog: {e}")

    def _show_simple_email_dialog(self, event_name, event_date, event_type, description):
        """Show simple email dialog as fallback"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calendar Reminder Details")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Calendar Event Reminder",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(details_frame, text=f"Event: {event_name}").pack(anchor='w')
        ttk.Label(details_frame, text=f"Date: {event_date}").pack(anchor='w')
        ttk.Label(details_frame, text=f"Type: {event_type}").pack(anchor='w')

        if description:
            ttk.Label(details_frame, text=f"Description: {description}").pack(anchor='w')

        # Email template
        template_frame = ttk.LabelFrame(main_frame, text="Email Template", padding=10)
        template_frame.pack(fill=tk.BOTH, expand=True)

        email_text = scrolledtext.ScrolledText(template_frame, wrap=tk.WORD, height=10)
        email_text.pack(fill=tk.BOTH, expand=True)

        email_content = f"""Subject: Reminder: {event_name} - {event_date}

Dear Students/Staff,

This is a reminder about an upcoming {event_type.lower()}:

Event: {event_name}
Date: {event_date}
Type: {event_type}

{description if description else 'No additional details provided.'}

Please mark your calendar and prepare accordingly.

Best regards,
Academic Calendar System"""

        email_text.insert(tk.END, email_content)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Copy to Clipboard",
                  command=lambda: self._copy_to_clipboard(email_content)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._update_status("Email template copied to clipboard", "success")
        except Exception as e:
            self._show_error(f"Failed to copy to clipboard: {e}")

    # Refresh methods
    def _refresh_current_view(self):
        """Refresh the current view"""
        if self.current_view == "dashboard":
            self._show_dashboard()
        elif self.current_view == "calendar":
            self._load_calendar_data()
        elif self.current_view == "manage_events":
            self._load_events_data()
        elif self.current_view == "academic_years":
            self._show_academic_years()
        elif self.current_view == "semesters":
            self._show_semesters()
    
    def _refresh_dashboard(self):
        """Refresh dashboard"""
        self._show_dashboard()
    
    def _refresh_manage_events(self):
        """Refresh events management"""
        self._load_events_data()
    
    # Utility methods
    def _import_calendar(self):
        """Import calendar from file"""
        ImportCalendarDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _backup_database(self):
        """Backup database"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                self._show_success(result['message'])
            else:
                self._show_error(result['message'])
        except Exception as e:
            self._show_error(f"Backup failed: {e}")
    
    def _restore_database(self):
        """Restore database from backup"""
        backup_file = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if backup_file:
            if messagebox.askyesno("Confirm Restore", 
                                 "This will replace the current database. Continue?"):
                try:
                    result = self.calendar_manager.restore_backup(backup_file)
                    if result['success']:
                        self._show_success(result['message'])
                        self._refresh_current_view()
                    else:
                        self._show_error(result['message'])
                except Exception as e:
                    self._show_error(f"Restore failed: {e}")
    
    def _calendar_sync(self):
        """Calendar sync dialog"""
        CalendarSyncDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _import_holidays(self):
        """Import holidays dialog"""
        ImportHolidaysDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _bulk_operations(self):
        """Bulk operations dialog"""
        BulkOperationsDialog(self.root, self.calendar_manager, self._refresh_current_view)
    
    def _launch_cli_mode(self):
        """Launch CLI mode for backward compatibility"""
        try:
            # Hide GUI temporarily
            self.root.withdraw()
            
            # Set global auth for CLI mode
            set_auth(self.auth_manager)
            
            # Launch CLI in a new thread
            def run_cli():
                try:
                    display_academic_calendar_menu()
                except Exception as e:
                    gui_logger.error(f"CLI mode error: {e}")
                finally:
                    # Show GUI again
                    self.root.after(0, self.root.deiconify)
            
            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()
            
        except Exception as e:
            self._show_error(f"Failed to launch CLI mode: {e}")
            self.root.deiconify()  # Make sure GUI is visible
    
    def _show_help(self):
        """Show help dialog"""
        HelpDialog(self.root)
    
    def _show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)
    
    def run(self):
        """Run the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.quit()
        except Exception as e:
            gui_logger.error(f"GUI runtime error: {e}")
            messagebox.showerror("Runtime Error", f"An error occurred: {e}")


class SystemMaintenanceDialog:
    """Dialog for system maintenance and backup operations"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("System Maintenance")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="System Maintenance", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Backup section
        backup_frame = ttk.LabelFrame(main_frame, text="Database Backup", padding=10)
        backup_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(backup_frame, text="Create Backup", 
                  command=self._create_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_frame, text="Restore from Backup", 
                  command=self._restore_backup).pack(side=tk.LEFT, padx=5)
        
        # Maintenance section
        maintenance_frame = ttk.LabelFrame(main_frame, text="Database Maintenance", padding=10)
        maintenance_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(maintenance_frame, text="Verify Database Integrity", 
                  command=self._verify_database).pack(side=tk.LEFT, padx=5)
        ttk.Button(maintenance_frame, text="Cleanup Old Data", 
                  command=self._cleanup_data).pack(side=tk.LEFT, padx=5)
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="System Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(config_frame, text="Export Configuration", 
                  command=self._export_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_frame, text="Import Configuration", 
                  command=self._import_config).pack(side=tk.LEFT, padx=5)
        
        # Status area
        status_frame = ttk.LabelFrame(main_frame, text="System Status", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, width=70)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Get system status
        self._update_status()
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()
    
    def _create_backup(self):
        """Create database backup"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                self._log_message(f"SUCCESS: {result['message']}")
            else:
                self._log_message(f"ERROR: {result['message']}")
        except Exception as e:
            self._log_message(f"ERROR: Backup failed: {e}")
    
    def _restore_backup(self):
        """Restore from backup"""
        backup_file = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if backup_file:
            if messagebox.askyesno("Confirm Restore", 
                                 "This will replace the current database. Continue?"):
                try:
                    result = self.calendar_manager.restore_backup(backup_file)
                    if result['success']:
                        self._log_message(f"SUCCESS: {result['message']}")
                    else:
                        self._log_message(f"ERROR: {result['message']}")
                except Exception as e:
                    self._log_message(f"ERROR: Restore failed: {e}")
    
    def _verify_database(self):
        """Verify database integrity"""
        try:
            success = self.calendar_manager.verify_calendar_database_integrity()
            if success:
                self._log_message("SUCCESS: Database integrity verified")
            else:
                self._log_message("WARNING: Database integrity issues found (check logs)")
        except Exception as e:
            self._log_message(f"ERROR: Verification failed: {e}")
    
    def _cleanup_data(self):
        """Cleanup old data"""
        if messagebox.askyesno("Confirm Cleanup", 
                             "This will remove old events and data. Continue?"):
            try:
                result = self.calendar_manager.cleanup_old_data()
                if result['success']:
                    self._log_message(f"SUCCESS: Cleaned {result['cleaned_events']} events, "
                                    f"{result['cleaned_notifications']} notifications, "
                                    f"{result['cleaned_audit_logs']} audit logs")
                else:
                    self._log_message(f"ERROR: {result['error']}")
            except Exception as e:
                self._log_message(f"ERROR: Cleanup failed: {e}")
    
    def _export_config(self):
        """Export system configuration"""
        try:
            config_data = self.calendar_manager.export_system_configuration()
            
            filename = filedialog.asksaveasfilename(
                title="Save Configuration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                with open(filename, 'w') as f:
                    json.dump(config_data, f, indent=2)
                self._log_message(f"SUCCESS: Configuration exported to {filename}")
        except Exception as e:
            self._log_message(f"ERROR: Export failed: {e}")
    
    def _import_config(self):
        """Import system configuration"""
        config_file = filedialog.askopenfilename(
            title="Select Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if config_file:
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                
                result = self.calendar_manager.import_system_configuration(config_data)
                if result['success']:
                    imported = result['imported']
                    self._log_message(f"SUCCESS: Imported {imported['academic_years']} academic years, "
                                    f"{imported['semesters']} semesters, "
                                    f"{imported['event_categories']} categories")
                else:
                    self._log_message(f"ERROR: {result['error']}")
            except Exception as e:
                self._log_message(f"ERROR: Import failed: {e}")
    
    def _update_status(self):
        """Update system status display"""
        try:
            stats = self.calendar_manager.get_system_stats()
            
            status = "SYSTEM STATUS\n" + "="*50 + "\n\n"
            status += f"Current Academic Year: {stats.get('current_academic_year', 'None')}\n"
            status += f"Current Semester: {stats.get('current_semester', 'None')}\n"
            status += f"Total Academic Years: {stats.get('total_academic_years', 0)}\n"
            status += f"Total Semesters: {stats.get('total_semesters', 0)}\n"
            status += f"Upcoming Events: {stats.get('upcoming_events', 0)}\n\n"
            
            status += "Events by Type:\n"
            for event_type, count in stats.get('events_by_type', {}).items():
                status += f"  {event_type}: {count}\n"
            
            status += f"\nDatabase File: {self.calendar_manager.config.db_file}\n"
            
            # Check database file size
            try:
                db_size = os.path.getsize(self.calendar_manager.config.db_file)
                status += f"Database Size: {db_size:,} bytes\n"
            except:
                status += "Database Size: Unknown\n"
            
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, status)
            
        except Exception as e:
            self._log_message(f"ERROR: Failed to get system status: {e}")
    
    def _log_message(self, message):
        """Log a message to the status area"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_text.insert(tk.END, f"\n[{timestamp}] {message}")
        self.status_text.see(tk.END)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AuditLogsDialog:
    """Dialog for viewing audit logs"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Audit Logs")
        self.dialog.geometry("1000x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_audit_logs()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Audit Logs", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Filter section
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Filter controls
        filter_controls = ttk.Frame(filter_frame)
        filter_controls.pack(fill=tk.X)
        
        ttk.Label(filter_controls, text="Table:").pack(side=tk.LEFT)
        self.table_var = tk.StringVar()
        table_combo = ttk.Combobox(filter_controls, textvariable=self.table_var, width=15,
                                  values=["", "events", "academic_years", "semesters", "courses"])
        table_combo.pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(filter_controls, text="User:").pack(side=tk.LEFT)
        self.user_var = tk.StringVar()
        ttk.Entry(filter_controls, textvariable=self.user_var, width=15).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Button(filter_controls, text="Filter", 
                  command=self._load_audit_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_controls, text="Clear", 
                  command=self._clear_filters).pack(side=tk.LEFT, padx=5)
        
        # Audit logs tree
        self.audit_tree = ttk.Treeview(main_frame, 
                                     columns=('Timestamp', 'User', 'Action', 'Table', 'Record'),
                                     show='tree headings')
        self.audit_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.audit_tree.heading('#0', text='ID')
        self.audit_tree.heading('Timestamp', text='Timestamp')
        self.audit_tree.heading('User', text='User')
        self.audit_tree.heading('Action', text='Action')
        self.audit_tree.heading('Table', text='Table')
        self.audit_tree.heading('Record', text='Record ID')
        
        self.audit_tree.column('#0', width=50)
        self.audit_tree.column('Timestamp', width=150)
        self.audit_tree.column('User', width=100)
        self.audit_tree.column('Action', width=80)
        self.audit_tree.column('Table', width=120)
        self.audit_tree.column('Record', width=200)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.audit_tree.xview)
        
        self.audit_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Double-click to view details
        self.audit_tree.bind('<Double-1>', self._view_audit_details)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_audit_logs(self):
        """Load audit logs"""
        try:
            # Clear existing items
            for item in self.audit_tree.get_children():
                self.audit_tree.delete(item)
            
            # Get filters
            table_filter = self.table_var.get().strip() or None
            user_filter = self.user_var.get().strip() or None
            
            # Get audit logs
            success, logs = self.calendar_manager.audit_manager.get_audit_trail(
                table_name=table_filter, user_id=user_filter, limit=200
            )
            
            if success:
                # Filter logs to show only current session if login_time is available
                filtered_logs = logs
                if hasattr(self.auth_manager, 'login_time') and self.auth_manager.login_time:
                    from datetime import datetime
                    login_time_str = self.auth_manager.login_time
                    if isinstance(login_time_str, str):
                        filtered_logs = [log for log in logs
                                       if log.get('timestamp', '') >= login_time_str]

                for log in filtered_logs:
                    log_id = str(log.get('id', ''))
                    timestamp = log.get('timestamp', '')[:19]  # Remove microseconds
                    user_id = log.get('user_id', 'System')[:15]  # Truncate long user IDs
                    action = log.get('action', '')
                    table_name = log.get('table_name', '')
                    record_id = log.get('record_id', '')[:30]  # Truncate long IDs

                    self.audit_tree.insert('', 'end',
                                         text=log_id,
                                         values=(timestamp, user_id, action, table_name, record_id),
                                         tags=(log.get('action', '').lower(),))
                
                # Configure action colors
                self.audit_tree.tag_configure('create', foreground='green')
                self.audit_tree.tag_configure('update', foreground='blue')
                self.audit_tree.tag_configure('delete', foreground='red')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit logs: {e}")
    
    def _clear_filters(self):
        """Clear all filters"""
        self.table_var.set("")
        self.user_var.set("")
        self._load_audit_logs()
    
    def _view_audit_details(self, event):
        """View detailed audit information"""
        selection = self.audit_tree.selection()
        if selection:
            item = selection[0]
            log_id = self.audit_tree.item(item, 'text')
            
            # Get full log details
            try:
                logs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM audit_log WHERE id = ?", (log_id,)
                )
                
                if logs:
                    log_data = dict(logs[0])
                    AuditDetailsDialog(self.dialog, log_data)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to get audit details: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AuditDetailsDialog:
    """Dialog for viewing detailed audit information"""
    
    def __init__(self, parent, log_data):
        self.log_data = log_data
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Audit Log Details")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Audit Log Details", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Basic info
        info_frame = ttk.LabelFrame(main_frame, text="Basic Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        basic_info = [
            ("ID:", self.log_data.get('id', 'N/A')),
            ("Timestamp:", self.log_data.get('timestamp', 'N/A')),
            ("User ID:", self.log_data.get('user_id', 'N/A')),
            ("Action:", self.log_data.get('action', 'N/A')),
            ("Table:", self.log_data.get('table_name', 'N/A')),
            ("Record ID:", self.log_data.get('record_id', 'N/A')),
            ("IP Address:", self.log_data.get('ip_address', 'N/A'))
        ]
        
        for i, (label, value) in enumerate(basic_info):
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(row_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=str(value)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Old values
        if self.log_data.get('old_values'):
            old_frame = ttk.LabelFrame(main_frame, text="Old Values", padding=10)
            old_frame.pack(fill=tk.X, pady=(0, 15))
            
            old_text = scrolledtext.ScrolledText(old_frame, height=6, wrap=tk.WORD)
            old_text.pack(fill=tk.X)
            
            try:
                old_values = json.loads(self.log_data['old_values'])
                old_text.insert(1.0, json.dumps(old_values, indent=2))
            except:
                old_text.insert(1.0, self.log_data['old_values'])
            
            old_text.config(state=tk.DISABLED)
        
        # New values
        if self.log_data.get('new_values'):
            new_frame = ttk.LabelFrame(main_frame, text="New Values", padding=10)
            new_frame.pack(fill=tk.X, pady=(0, 15))
            
            new_text = scrolledtext.ScrolledText(new_frame, height=6, wrap=tk.WORD)
            new_text.pack(fill=tk.X)
            
            try:
                new_values = json.loads(self.log_data['new_values'])
                new_text.insert(1.0, json.dumps(new_values, indent=2))
            except:
                new_text.insert(1.0, self.log_data['new_values'])
            
            new_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class ProjectMilestonesDialog:
    """Dialog for managing project milestones"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Project Milestones")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_milestones()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Project Milestones", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(action_frame, text="Add Milestone", 
                  command=self._add_milestone).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Update Progress", 
                  command=self._update_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", 
                  command=self._load_milestones).pack(side=tk.RIGHT, padx=5)
        
        # Milestones tree
        self.milestones_tree = ttk.Treeview(main_frame, 
                                          columns=('Project', 'Due Date', 'Progress', 'Status'),
                                          show='tree headings')
        self.milestones_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.milestones_tree.heading('#0', text='Milestone Name')
        self.milestones_tree.heading('Project', text='Project')
        self.milestones_tree.heading('Due Date', text='Due Date')
        self.milestones_tree.heading('Progress', text='Progress %')
        self.milestones_tree.heading('Status', text='Status')
        
        self.milestones_tree.column('#0', width=200)
        self.milestones_tree.column('Project', width=150)
        self.milestones_tree.column('Due Date', width=100)
        self.milestones_tree.column('Progress', width=100)
        self.milestones_tree.column('Status', width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.milestones_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.milestones_tree.xview)
        
        self.milestones_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_milestones(self):
        """Load milestones into tree"""
        try:
            # Clear existing items
            for item in self.milestones_tree.get_children():
                self.milestones_tree.delete(item)
            
            # Get milestones from database
            milestones = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM project_milestones ORDER BY due_date"
            )
            
            for milestone in milestones:
                # Convert sqlite3.Row to dict if necessary
                if hasattr(milestone, '__getitem__') and not hasattr(milestone, 'get'):
                    milestone = dict(milestone)

                progress = f"{milestone.get('completion_percentage', 0):.1f}%"

                # Color code by status
                status = milestone.get('status', 'pending')
                tag = status.lower()

                self.milestones_tree.insert('', 'end',
                                          text=milestone['milestone_name'],
                                          values=(milestone['project_name'],
                                                milestone['due_date'],
                                                progress,
                                                status.title()),
                                          tags=(tag,))
            
            # Configure status colors
            self.milestones_tree.tag_configure('completed', foreground='green')
            self.milestones_tree.tag_configure('in_progress', foreground='blue')
            self.milestones_tree.tag_configure('overdue', foreground='red')
            self.milestones_tree.tag_configure('pending', foreground='orange')
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load milestones: {e}")
    
    def _add_milestone(self):
        """Add new milestone"""
        AddMilestoneDialog(self.dialog, self.calendar_manager, self._load_milestones)
    
    def _update_progress(self):
        """Update milestone progress"""
        selection = self.milestones_tree.selection()
        if selection:
            milestone_name = self.milestones_tree.item(selection[0], 'text')
            UpdateMilestoneDialog(self.dialog, self.calendar_manager, milestone_name, self._load_milestones)
        else:
            messagebox.showwarning("Selection Required", "Please select a milestone to update")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class DataVisualizationDialog:
    """Dialog for data visualization options"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Data Visualization")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Data Visualization", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Available visualizations
        viz_frame = ttk.LabelFrame(main_frame, text="Available Visualizations", padding=10)
        viz_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        visualizations = [
            ("Calendar Heatmap", "Show event density over time", self._create_heatmap),
            ("Event Distribution Chart", "Show event types distribution", self._create_distribution),
            ("Timeline Visualization", "Show academic year timeline", self._create_timeline),
            ("Conflict Visualization", "Show scheduling conflicts", self._create_conflicts),
            ("Resource Utilization", "Show resource usage patterns", self._create_utilization),
            ("Attendance Trends", "Show attendance patterns", self._create_attendance)
        ]
        
        for viz_name, description, command in visualizations:
            viz_item_frame = ttk.Frame(viz_frame)
            viz_item_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(viz_item_frame, text=viz_name, width=25,
                      command=command).pack(side=tk.LEFT)
            ttk.Label(viz_item_frame, text=description).pack(side=tk.LEFT, padx=(10, 0))
        
        # Note about requirements
        note_frame = ttk.LabelFrame(main_frame, text="Requirements", padding=10)
        note_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(note_frame, text="Some visualizations require additional libraries (matplotlib, plotly).\n"
                                 "If libraries are missing, you'll be notified when attempting to create visualizations.",
                 wraplength=600).pack()
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()
    
    def _create_heatmap(self):
        """Create calendar heatmap"""
        year = simpledialog.askinteger("Calendar Heatmap", "Enter year:", 
                                     initialvalue=datetime.now().year)
        if year:
            try:
                success, message = self.calendar_manager.visualizations.create_calendar_heatmap(year)
                if success:
                    messagebox.showinfo("Success", "Calendar heatmap created successfully")
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create heatmap: {e}")
    
    def _create_distribution(self):
        """Create event distribution chart"""
        timeframe = simpledialog.askstring("Event Distribution", 
                                         "Enter timeframe (month/semester/year):", 
                                         initialvalue="month")
        if timeframe:
            try:
                success, message = self.calendar_manager.visualizations.create_event_distribution_chart(timeframe)
                if success:
                    messagebox.showinfo("Success", "Distribution chart created successfully")
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create chart: {e}")
    
    def _create_timeline(self):
        """Create timeline visualization"""
        academic_year = simpledialog.askstring("Timeline Visualization", 
                                              "Enter academic year ID:")
        if academic_year:
            try:
                success, message = self.calendar_manager.enhanced_visualizations.create_timeline_visualization(academic_year)
                if success:
                    messagebox.showinfo("Success", "Timeline visualization created successfully")
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create timeline: {e}")
    
    def _create_conflicts(self):
        """Create conflict visualization"""
        start_date = simpledialog.askstring("Conflict Visualization", 
                                           "Enter start date (YYYY-MM-DD):")
        if start_date:
            end_date = simpledialog.askstring("Conflict Visualization", 
                                            "Enter end date (YYYY-MM-DD):")
            if end_date:
                try:
                    success, message = self.calendar_manager.enhanced_visualizations.create_conflict_visualization(
                        (start_date, end_date)
                    )
                    if success:
                        messagebox.showinfo("Success", "Conflict visualization created successfully")
                    else:
                        messagebox.showerror("Error", message)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create visualization: {e}")
    
    def _create_utilization(self):
        """Create resource utilization chart"""
        try:
            report = self.calendar_manager.advanced_reporting.generate_utilization_report()
            if report['success']:
                # Simple text-based display since we may not have plotting libraries
                utilization_text = "RESOURCE UTILIZATION REPORT\n" + "="*50 + "\n\n"
                for resource in report['resources']:
                    utilization_text += f"{resource['resource_name']}: {resource['utilization_percentage']:.1f}%\n"
                    utilization_text += f"  Bookings: {resource['total_bookings']}, Hours: {resource['total_hours']:.1f}\n\n"
                
                ReportViewDialog(self.dialog, "Resource Utilization", utilization_text)
            else:
                messagebox.showerror("Error", f"Failed to generate report: {report['error']}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create utilization report: {e}")
    
    def _create_attendance(self):
        """Create attendance trends visualization"""
        try:
            report = self.calendar_manager.advanced_reporting.generate_attendance_report()
            if report['success']:
                # Simple text-based display
                attendance_text = "ATTENDANCE TRENDS REPORT\n" + "="*50 + "\n\n"
                attendance_text += f"Total Events: {report['total_events']}\n"
                attendance_text += f"Average Attendance: {report['average_attendance']}\n\n"
                
                attendance_text += "Course Statistics:\n"
                for course, stats in report['course_statistics'].items():
                    avg_attendance = stats['total_attendance'] / stats['events'] if stats['events'] > 0 else 0
                    attendance_text += f"  {course}: {avg_attendance:.1f} avg attendance over {stats['events']} events\n"
                
                ReportViewDialog(self.dialog, "Attendance Trends", attendance_text)
            else:
                messagebox.showerror("Error", f"Failed to generate report: {report['error']}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create attendance report: {e}")

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class TimezoneSettingsDialog:
    """Dialog for timezone settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Timezone Settings")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_current_settings()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Timezone Settings", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Current timezone
        current_frame = ttk.LabelFrame(main_frame, text="Current Settings", padding=10)
        current_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.current_tz_label = ttk.Label(current_frame, text="Current Timezone: Loading...")
        self.current_tz_label.pack(anchor=tk.W)
        
        # Timezone selection
        selection_frame = ttk.LabelFrame(main_frame, text="Change Timezone", padding=10)
        selection_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(selection_frame, text="Select Timezone:").pack(anchor=tk.W)
        self.timezone_var = tk.StringVar()
        
        # Common timezones
        common_timezones = [
            "UTC",
            "US/Eastern",
            "US/Central", 
            "US/Mountain",
            "US/Pacific",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Asia/Tokyo",
            "Asia/Shanghai",
            "Australia/Sydney"
        ]
        
        timezone_combo = ttk.Combobox(selection_frame, textvariable=self.timezone_var, 
                                    width=40, values=common_timezones)
        timezone_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Auto DST
        self.auto_dst_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(selection_frame, text="Automatically adjust for Daylight Saving Time",
                       variable=self.auto_dst_var).pack(anchor=tk.W, pady=(0, 15))
        
        # Timezone info
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding=10)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        info_text = ("Timezone settings affect how event times are displayed and stored.\n\n"
                    "Note: Some timezone features require the 'pytz' library.\n"
                    "Install with: pip install pytz")
        
        ttk.Label(info_frame, text=info_text, wraplength=450).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Apply", command=self._apply_timezone).pack(side=tk.RIGHT)
    
    def _load_current_settings(self):
        """Load current timezone settings"""
        try:
            if self.auth_manager.current_user:
                user_id = self.auth_manager.current_user['id']
                
                # Get current timezone preference
                prefs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM user_timezone_preferences WHERE user_id = ?", (user_id,)
                )
                
                if prefs:
                    pref = prefs[0]
                    current_tz = pref['timezone_name']
                    self.current_tz_label.config(text=f"Current Timezone: {current_tz}")
                    self.timezone_var.set(current_tz)
                    self.auto_dst_var.set(pref.get('auto_dst', True))
                else:
                    self.current_tz_label.config(text="Current Timezone: UTC (default)")
                    self.timezone_var.set("UTC")
        except Exception as e:
            self.current_tz_label.config(text=f"Error loading settings: {e}")
    
    def _apply_timezone(self):
        """Apply timezone settings"""
        try:
            if not self.auth_manager.current_user:
                messagebox.showerror("Error", "No user logged in")
                return
            
            user_id = self.auth_manager.current_user['id']
            timezone_name = self.timezone_var.get().strip()
            auto_dst = self.auto_dst_var.get()
            
            if not timezone_name:
                messagebox.showerror("Error", "Please select a timezone")
                return
            
            success, message = self.calendar_manager.timezone_manager.set_user_timezone(
                user_id, timezone_name, auto_dst
            )
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply timezone settings: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


# Small helper dialogs that are referenced but missing

class AddMilestoneDialog:
    """Simple dialog for adding milestones"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        # Create and show simple input dialog
        project_name = simpledialog.askstring("Add Milestone", "Project Name:")
        if not project_name:
            return
            
        milestone_name = simpledialog.askstring("Add Milestone", "Milestone Name:")
        if not milestone_name:
            return
            
        due_date = simpledialog.askstring("Add Milestone", "Due Date (YYYY-MM-DD):")
        if not due_date:
            return
        
        description = simpledialog.askstring("Add Milestone", "Description (optional):") or ""
        
        try:
            success, message = calendar_manager.academic_deadlines.create_project_milestone(
                project_name, milestone_name, due_date, description=description
            )
            
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add milestone: {e}")


class UpdateMilestoneDialog:
    """Simple dialog for updating milestone progress"""
    
    def __init__(self, parent, calendar_manager, milestone_name, callback=None):
        try:
            # Get milestone ID by name
            milestones = calendar_manager.db_manager.execute_query(
                "SELECT id FROM project_milestones WHERE milestone_name = ?", (milestone_name,)
            )
            
            if not milestones:
                messagebox.showerror("Error", "Milestone not found")
                return
            
            milestone_id = milestones[0]['id']
            
            # Ask for progress
            progress = simpledialog.askfloat("Update Progress", 
                                           "Enter completion percentage (0-100):",
                                           minvalue=0, maxvalue=100)
            if progress is not None:
                success, message = calendar_manager.academic_deadlines.update_milestone_progress(
                    milestone_id, progress
                )
                
                if success:
                    messagebox.showinfo("Success", message)
                    if callback:
                        callback()
                else:
                    messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update milestone: {e}")


# Additional small helper dialogs for categories and tags

class AddCategoryDialog:
    """Simple dialog for adding categories"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        name = simpledialog.askstring("Add Category", "Category Name:")
        if not name:
            return
            
        color = simpledialog.askstring("Add Category", "Color Code (optional, e.g., #FF0000):") or None
        description = simpledialog.askstring("Add Category", "Description (optional):") or None
        
        try:
            success, message = calendar_manager.categories.create_category(name, color, description)
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add category: {e}")


class AddTagDialog:
    """Simple dialog for adding tags"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        name = simpledialog.askstring("Add Tag", "Tag Name:")
        if not name:
            return
            
        color = simpledialog.askstring("Add Tag", "Color Code (optional, e.g., #FF0000):") or None
        
        try:
            success, message = calendar_manager.categories.create_tag(name, color)
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add tag: {e}")


class AssignTagDialog:
    """Simple dialog for assigning tags to events"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        event_id = simpledialog.askstring("Assign Tag", "Event ID:")
        if not event_id:
            return
            
        tags = simpledialog.askstring("Assign Tag", "Tag Names (comma-separated):")
        if not tags:
            return
        
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        try:
            success, message = calendar_manager.categories.assign_tags_to_event(event_id, tag_list)
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign tags: {e}")


class AddCourseDialog:
    """Simple dialog for adding courses"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        code = simpledialog.askstring("Add Course", "Course Code:")
        if not code:
            return
            
        name = simpledialog.askstring("Add Course", "Course Name:")
        if not name:
            return
        
        credits = simpledialog.askinteger("Add Course", "Credits:", initialvalue=3) or 3
        department = simpledialog.askstring("Add Course", "Department (optional):") or None
        
        course_data = {
            'code': code,
            'name': name,
            'credits': credits,
            'department': department
        }
        
        try:
            success, message = calendar_manager.courses.create_course(course_data)
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add course: {e}")


class LinkCourseEventDialog:
    """Simple dialog for linking courses to events"""
    
    def __init__(self, parent, calendar_manager, course_name, callback=None):
        event_id = simpledialog.askstring("Link Course to Event", "Event ID:")
        if not event_id:
            return
        
        try:
            # Get course ID by name
            courses = calendar_manager.db_manager.execute_query(
                "SELECT id FROM courses WHERE name = ?", (course_name,)
            )
            
            if not courses:
                messagebox.showerror("Error", "Course not found")
                return
            
            course_id = courses[0]['id']
            
            success, message = calendar_manager.courses.link_event_to_course(event_id, course_id)
            if success:
                messagebox.showinfo("Success", message)
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to link course to event: {e}")

class ResourceManagementDialog:
    """Dialog for managing resources (rooms, equipment, etc.)"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Resource Management")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_resources()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Resource Management", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(action_frame, text="Add Resource", 
                  command=self._add_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Book Resource", 
                  command=self._book_resource).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", 
                  command=self._load_resources).pack(side=tk.RIGHT, padx=5)
        
        # Resources tree
        self.resources_tree = ttk.Treeview(main_frame, 
                                         columns=('Type', 'Capacity', 'Location', 'Status'),
                                         show='tree headings')
        self.resources_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.resources_tree.heading('#0', text='Resource Name')
        self.resources_tree.heading('Type', text='Type')
        self.resources_tree.heading('Capacity', text='Capacity')
        self.resources_tree.heading('Location', text='Location')
        self.resources_tree.heading('Status', text='Status')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.resources_tree.yview)
        self.resources_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_resources(self):
        """Load resources into tree"""
        try:
            # Clear existing items
            for item in self.resources_tree.get_children():
                self.resources_tree.delete(item)
            
            # Get resources from database
            resources = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM resources ORDER BY type, name"
            )
            
            for resource in resources:
                self.resources_tree.insert('', 'end',
                                         text=resource['name'],
                                         values=(resource['type'], 
                                               resource['capacity'] or 'N/A',
                                               resource['location'] or 'N/A',
                                               resource['status']))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load resources: {e}")
    
    def _add_resource(self):
        """Show add resource dialog"""
        AddResourceDialog(self.dialog, self.calendar_manager, self._load_resources)
    
    def _book_resource(self):
        """Show resource booking dialog"""
        selection = self.resources_tree.selection()
        if selection:
            resource_name = self.resources_tree.item(selection[0], 'text')
            BookResourceDialog(self.dialog, self.calendar_manager, resource_name, self._load_resources)
        else:
            messagebox.showwarning("Selection Required", "Please select a resource to book")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddResourceDialog:
    """Dialog for adding new resources"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Resource")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Add New Resource", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Resource name
        ttk.Label(main_frame, text="Resource Name *").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Resource type
        ttk.Label(main_frame, text="Resource Type *").pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=37,
                                values=["Classroom", "Laboratory", "Auditorium", "Equipment", "Vehicle", "Other"])
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Capacity
        ttk.Label(main_frame, text="Capacity").pack(anchor=tk.W)
        self.capacity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Location
        ttk.Label(main_frame, text="Location").pack(anchor=tk.W)
        self.location_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.location_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Add Resource", command=self._add_resource).pack(side=tk.RIGHT)
    
    def _add_resource(self):
        """Add the resource"""
        try:
            name = self.name_var.get().strip()
            resource_type = self.type_var.get().strip()
            
            if not name or not resource_type:
                messagebox.showerror("Error", "Name and type are required")
                return
            
            resource_data = {
                'name': name,
                'type': resource_type,
                'capacity': int(self.capacity_var.get()) if self.capacity_var.get().strip() else None,
                'location': self.location_var.get().strip() or None
            }
            
            success, message = self.calendar_manager.resources.create_resource(resource_data)
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
                
        except ValueError:
            messagebox.showerror("Error", "Capacity must be a number")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add resource: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class BookResourceDialog:
    """Dialog for booking resources"""
    
    def __init__(self, parent, calendar_manager, resource_name=None, callback=None):
        self.calendar_manager = calendar_manager
        self.resource_name = resource_name
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Book Resource")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Book Resource", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Resource selection
        ttk.Label(main_frame, text="Resource *").pack(anchor=tk.W)
        self.resource_var = tk.StringVar(value=self.resource_name or "")
        resource_combo = ttk.Combobox(main_frame, textvariable=self.resource_var, width=42)
        resource_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Load resources
        try:
            resources = self.calendar_manager.db_manager.execute_query(
                "SELECT name FROM resources WHERE status = 'available' ORDER BY name"
            )
            resource_names = [r['name'] for r in resources]
            resource_combo['values'] = resource_names
        except:
            pass
        
        # Event selection
        ttk.Label(main_frame, text="Event (optional)").pack(anchor=tk.W)
        self.event_var = tk.StringVar()
        event_combo = ttk.Combobox(main_frame, textvariable=self.event_var, width=42)
        event_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Load recent events
        try:
            events = self.calendar_manager.db_manager.execute_query(
                "SELECT id, name FROM events ORDER BY date_added DESC LIMIT 20"
            )
            event_list = [f"{e['name']} ({e['id'][:8]})" for e in events]
            event_combo['values'] = event_list
        except:
            pass
        
        # Start time
        ttk.Label(main_frame, text="Start Time (YYYY-MM-DD HH:MM:SS) *").pack(anchor=tk.W)
        self.start_time_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_time_var, width=45).pack(fill=tk.X, pady=(5, 15))
        
        # End time
        ttk.Label(main_frame, text="End Time (YYYY-MM-DD HH:MM:SS) *").pack(anchor=tk.W)
        self.end_time_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_time_var, width=45).pack(fill=tk.X, pady=(5, 15))
        
        # Notes
        ttk.Label(main_frame, text="Notes").pack(anchor=tk.W)
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=3, width=45)
        self.notes_text.pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Book Resource", command=self._book_resource).pack(side=tk.RIGHT)
    
    def _book_resource(self):
        """Book the resource"""
        try:
            resource_name = self.resource_var.get().strip()
            start_time = self.start_time_var.get().strip()
            end_time = self.end_time_var.get().strip()
            
            if not all([resource_name, start_time, end_time]):
                messagebox.showerror("Error", "Resource, start time, and end time are required")
                return
            
            # Get resource ID
            resource_rows = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM resources WHERE name = ?", (resource_name,)
            )
            if not resource_rows:
                messagebox.showerror("Error", "Selected resource not found")
                return
            
            resource_id = resource_rows[0]['id']
            
            # Get event ID if selected
            event_id = None
            event_selection = self.event_var.get().strip()
            if event_selection:
                # Extract ID from "Name (ID)" format
                if '(' in event_selection and ')' in event_selection:
                    event_id_part = event_selection.split('(')[1].split(')')[0]
                    # Find full event ID
                    event_rows = self.calendar_manager.db_manager.execute_query(
                        "SELECT id FROM events WHERE id LIKE ?", (f"{event_id_part}%",)
                    )
                    if event_rows:
                        event_id = event_rows[0]['id']
            
            booking_data = {
                'resource_id': resource_id,
                'event_id': event_id,
                'start_time': start_time,
                'end_time': end_time,
                'notes': self.notes_text.get(1.0, tk.END).strip()
            }
            
            success, message = self.calendar_manager.resources.book_resource(booking_data)
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to book resource: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class CourseManagementDialog:
    """Dialog for managing courses"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Management")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_courses()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Course Management", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(action_frame, text="Add Course", 
                  command=self._add_course).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Link to Event", 
                  command=self._link_to_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", 
                  command=self._load_courses).pack(side=tk.RIGHT, padx=5)
        
        # Courses tree
        self.courses_tree = ttk.Treeview(main_frame, 
                                       columns=('Code', 'Credits', 'Department', 'Status'),
                                       show='tree headings')
        self.courses_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Configure columns
        self.courses_tree.heading('#0', text='Course Name')
        self.courses_tree.heading('Code', text='Code')
        self.courses_tree.heading('Credits', text='Credits')
        self.courses_tree.heading('Department', text='Department')
        self.courses_tree.heading('Status', text='Status')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.courses_tree.yview)
        h_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.courses_tree.xview)
        
        self.courses_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_courses(self):
        """Load courses into tree"""
        try:
            # Clear existing items
            for item in self.courses_tree.get_children():
                self.courses_tree.delete(item)
            
            # Get courses from database
            courses = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM courses ORDER BY department, code"
            )
            
            for course in courses:
                self.courses_tree.insert('', 'end',
                                       text=course['name'],
                                       values=(course['code'], 
                                             course['credits'] or 'N/A',
                                             course['department'] or 'N/A',
                                             course['status']))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load courses: {e}")
    
    def _add_course(self):
        """Show add course dialog"""
        AddCourseDialog(self.dialog, self.calendar_manager, self._load_courses)
    
    def _link_to_event(self):
        """Show link course to event dialog"""
        selection = self.courses_tree.selection()
        if selection:
            course_name = self.courses_tree.item(selection[0], 'text')
            LinkCourseEventDialog(self.dialog, self.calendar_manager, course_name, self._load_courses)
        else:
            messagebox.showwarning("Selection Required", "Please select a course to link")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class NotificationSettingsDialog:
    """Dialog for managing notification settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Notification Settings")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_preferences()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Notification Settings", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Notification types
        types_frame = ttk.LabelFrame(main_frame, text="Notification Types", padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.notification_vars = {}
        notification_types = [
            ("event_reminder", "Event Reminders"),
            ("deadline_warning", "Deadline Warnings"), 
            ("schedule_change", "Schedule Changes"),
            ("trip_update", "Trip Updates")
        ]
        
        for i, (type_key, type_label) in enumerate(notification_types):
            frame = ttk.Frame(types_frame)
            frame.pack(fill=tk.X, pady=2)
            
            var = tk.BooleanVar()
            self.notification_vars[type_key] = var
            
            ttk.Checkbutton(frame, text=type_label, variable=var).pack(side=tk.LEFT)
            
            # Advance time
            ttk.Label(frame, text="Minutes before:").pack(side=tk.RIGHT, padx=(10, 5))
            advance_var = tk.StringVar(value="60")
            self.notification_vars[f"{type_key}_advance"] = advance_var
            ttk.Entry(frame, textvariable=advance_var, width=8).pack(side=tk.RIGHT)
        
        # Delivery methods
        method_frame = ttk.LabelFrame(main_frame, text="Delivery Methods", padding=10)
        method_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.method_var = tk.StringVar(value="email")
        ttk.Radiobutton(method_frame, text="Email", variable=self.method_var, value="email").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text="SMS", variable=self.method_var, value="sms").pack(anchor=tk.W)
        ttk.Radiobutton(method_frame, text="Both", variable=self.method_var, value="both").pack(anchor=tk.W)
        
        # Contact info
        contact_frame = ttk.LabelFrame(main_frame, text="Contact Information", padding=10)
        contact_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(contact_frame, text="Email:").pack(anchor=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(contact_frame, textvariable=self.email_var, width=50).pack(fill=tk.X, pady=(5, 10))
        
        ttk.Label(contact_frame, text="Phone:").pack(anchor=tk.W)
        self.phone_var = tk.StringVar()
        ttk.Entry(contact_frame, textvariable=self.phone_var, width=50).pack(fill=tk.X, pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Save Settings", command=self._save_preferences).pack(side=tk.RIGHT)
    
    def _load_preferences(self):
        """Load current notification preferences"""
        try:
            if self.auth_manager.current_user:
                user_id = self.auth_manager.current_user['id']
                
                # Load notification preferences
                prefs = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM notification_preferences WHERE user_id = ?", (user_id,)
                )
                
                for pref in prefs:
                    type_key = pref['notification_type']
                    if type_key in self.notification_vars:
                        self.notification_vars[type_key].set(pref['enabled'])
                        self.notification_vars[f"{type_key}_advance"].set(str(pref['advance_time']))
                
                # Load contact info from user data
                self.email_var.set(self.auth_manager.current_user.get('email', ''))
                self.phone_var.set(self.auth_manager.current_user.get('phone', ''))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preferences: {e}")
    
    def _save_preferences(self):
        """Save notification preferences"""
        try:
            if not self.auth_manager.current_user:
                messagebox.showerror("Error", "No user logged in")
                return
            
            user_id = self.auth_manager.current_user['id']
            method = self.method_var.get()
            
            # Save each notification type
            for type_key, enabled_var in self.notification_vars.items():
                if not type_key.endswith('_advance') and isinstance(enabled_var, tk.BooleanVar):
                    advance_time = int(self.notification_vars.get(f"{type_key}_advance", tk.StringVar(value="60")).get())
                    
                    success, message = self.calendar_manager.notifications.set_notification_preference(
                        user_id, type_key, enabled_var.get(), advance_time, method
                    )
                    
                    if not success:
                        messagebox.showerror("Error", f"Failed to save {type_key}: {message}")
                        return
            
            messagebox.showinfo("Success", "Notification preferences saved successfully")
            if self.callback:
                self.callback()
            self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Invalid advance time values")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preferences: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class EventCategoriesDialog:
    """Dialog for managing event categories"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Categories")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_categories()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Event Categories & Tags", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Notebook for categories and tags
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Categories tab
        categories_frame = ttk.Frame(notebook, padding=10)
        notebook.add(categories_frame, text="Categories")
        
        # Action buttons for categories
        cat_action_frame = ttk.Frame(categories_frame)
        cat_action_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(cat_action_frame, text="Add Category", 
                  command=self._add_category).pack(side=tk.LEFT, padx=5)
        ttk.Button(cat_action_frame, text="Refresh", 
                  command=self._load_categories).pack(side=tk.RIGHT, padx=5)
        
        # Categories tree
        self.categories_tree = ttk.Treeview(categories_frame, 
                                          columns=('Color', 'Description'),
                                          show='tree headings')
        self.categories_tree.pack(fill=tk.BOTH, expand=True)
        
        self.categories_tree.heading('#0', text='Category Name')
        self.categories_tree.heading('Color', text='Color')
        self.categories_tree.heading('Description', text='Description')
        
        # Tags tab
        tags_frame = ttk.Frame(notebook, padding=10)
        notebook.add(tags_frame, text="Tags")
        
        # Action buttons for tags
        tag_action_frame = ttk.Frame(tags_frame)
        tag_action_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(tag_action_frame, text="Add Tag", 
                  command=self._add_tag).pack(side=tk.LEFT, padx=5)
        ttk.Button(tag_action_frame, text="Assign to Event", 
                  command=self._assign_tag).pack(side=tk.LEFT, padx=5)
        
        # Tags listbox
        self.tags_listbox = tk.Listbox(tags_frame)
        self.tags_listbox.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _load_categories(self):
        """Load categories into tree"""
        try:
            # Clear existing items
            for item in self.categories_tree.get_children():
                self.categories_tree.delete(item)
            
            # Get categories from database
            categories = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM event_categories ORDER BY name"
            )
            
            for category in categories:
                self.categories_tree.insert('', 'end',
                                          text=category['name'],
                                          values=(category['color_code'] or 'N/A',
                                                category['description'] or ''))
            
            # Load tags
            self.tags_listbox.delete(0, tk.END)
            tags = self.calendar_manager.db_manager.execute_query(
                "SELECT name FROM event_tags ORDER BY name"
            )
            for tag in tags:
                self.tags_listbox.insert(tk.END, tag['name'])
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load categories: {e}")
    
    def _add_category(self):
        """Add new category"""
        AddCategoryDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _add_tag(self):
        """Add new tag"""
        AddTagDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _assign_tag(self):
        """Assign tag to event"""
        AssignTagDialog(self.dialog, self.calendar_manager, self._load_categories)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AdvancedSearchDialog:
    """Dialog for advanced search functionality"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Search")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Advanced Search", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Text search
        ttk.Label(criteria_frame, text="Search Text:").pack(anchor=tk.W)
        self.text_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.text_var, width=60).pack(fill=tk.X, pady=(5, 15))
        
        # Date range
        date_frame = ttk.Frame(criteria_frame)
        date_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(date_frame, text="Start Date:").pack(side=tk.LEFT)
        self.start_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=15).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(date_frame, text="End Date:").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=15).pack(side=tk.LEFT, padx=(5, 0))
        
        # Event type
        ttk.Label(criteria_frame, text="Event Type:").pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(criteria_frame, textvariable=self.type_var, width=57,
                                values=["", "Academic", "Holiday", "Administrative", "Social", "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Tags
        ttk.Label(criteria_frame, text="Tags (comma-separated):").pack(anchor=tk.W)
        self.tags_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.tags_var, width=60).pack(fill=tk.X, pady=(5, 0))
        
        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # Results tree
        self.results_tree = ttk.Treeview(results_frame, 
                                       columns=('Date', 'Type', 'Description'),
                                       show='tree headings')
        self.results_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.results_tree.heading('#0', text='Event Name')
        self.results_tree.heading('Date', text='Date')
        self.results_tree.heading('Type', text='Type')
        self.results_tree.heading('Description', text='Description')
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(button_frame, text="Search", command=self._perform_search).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Clear", command=self._clear_search).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def _perform_search(self):
        """Perform the search"""
        try:
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Build search criteria
            criteria = {}
            
            text = self.text_var.get().strip()
            if text:
                criteria['text'] = text
            
            start_date = self.start_date_var.get().strip()
            if start_date:
                criteria['start_date'] = start_date
            
            end_date = self.end_date_var.get().strip()
            if end_date:
                criteria['end_date'] = end_date
            
            event_type = self.type_var.get().strip()
            if event_type:
                criteria['event_type'] = event_type
            
            tags = self.tags_var.get().strip()
            if tags:
                criteria['tags'] = [tag.strip() for tag in tags.split(',') if tag.strip()]
            
            # Perform search
            success, results = self.calendar_manager.search.advanced_search(criteria)
            
            if success:
                for event in results:
                    event_date = event.get('date') or event.get('date_start', '')
                    description = (event.get('description', '') or '')[:50]
                    if len(event.get('description', '') or '') > 50:
                        description += "..."
                    
                    self.results_tree.insert('', 'end',
                                           text=event['name'],
                                           values=(event_date, event['event_type'], description))
                
                messagebox.showinfo("Search Complete", f"Found {len(results)} events")
            else:
                messagebox.showerror("Search Error", f"Search failed: {results}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")
    
    def _clear_search(self):
        """Clear search criteria and results"""
        self.text_var.set("")
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.type_var.set("")
        self.tags_var.set("")
        
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class RecurringEventDialog:
    """Dialog for creating recurring events"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Recurring Event")
        self.dialog.geometry("550x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Create Recurring Event", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(details_frame, text="Event Name *").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        ttk.Label(details_frame, text="Start Date (YYYY-MM-DD) *").pack(anchor=tk.W)
        self.date_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.date_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        ttk.Label(details_frame, text="Description").pack(anchor=tk.W)
        self.description_text = scrolledtext.ScrolledText(details_frame, height=3, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 15))
        
        ttk.Label(details_frame, text="Event Type").pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(details_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social", "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Recurrence pattern
        pattern_frame = ttk.LabelFrame(main_frame, text="Recurrence Pattern", padding=10)
        pattern_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Frequency
        freq_frame = ttk.Frame(pattern_frame)
        freq_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(freq_frame, text="Frequency:").pack(side=tk.LEFT)
        self.frequency_var = tk.StringVar(value="weekly")
        freq_combo = ttk.Combobox(freq_frame, textvariable=self.frequency_var, width=15,
                                values=["daily", "weekly", "monthly", "yearly"])
        freq_combo.pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(freq_frame, text="Every:").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="1")
        ttk.Entry(freq_frame, textvariable=self.interval_var, width=5).pack(side=tk.LEFT, padx=(5, 0))
        
        # End condition
        end_frame = ttk.LabelFrame(pattern_frame, text="End Condition", padding=5)
        end_frame.pack(fill=tk.X)
        
        self.end_type_var = tk.StringVar(value="date")
        ttk.Radiobutton(end_frame, text="End by date:", variable=self.end_type_var, 
                       value="date", command=self._toggle_end_fields).pack(anchor=tk.W)
        
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(end_frame, textvariable=self.end_date_var, width=20)
        self.end_date_entry.pack(anchor=tk.W, padx=(20, 0), pady=(5, 10))
        
        ttk.Radiobutton(end_frame, text="End after occurrences:", variable=self.end_type_var, 
                       value="count", command=self._toggle_end_fields).pack(anchor=tk.W)
        
        self.count_var = tk.StringVar(value="10")
        self.count_entry = ttk.Entry(end_frame, textvariable=self.count_var, width=10)
        self.count_entry.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Create Recurring Event", command=self._create_recurring_event).pack(side=tk.RIGHT)
        
        # Initialize field states
        self._toggle_end_fields()
    
    def _toggle_end_fields(self):
        """Toggle end condition fields based on selection"""
        if self.end_type_var.get() == "date":
            self.end_date_entry.config(state="normal")
            self.count_entry.config(state="disabled")
        else:
            self.end_date_entry.config(state="disabled")
            self.count_entry.config(state="normal")
    
    def _create_recurring_event(self):
        """Create the recurring event"""
        try:
            # Validate required fields
            name = self.name_var.get().strip()
            date = self.date_var.get().strip()
            
            if not name or not date:
                messagebox.showerror("Error", "Event name and start date are required")
                return
            
            # Build base event data
            base_event = {
                'name': name,
                'date': date,
                'description': self.description_text.get(1.0, tk.END).strip(),
                'event_type': self.type_var.get()
            }
            
            # Build recurrence pattern
            pattern = {
                'frequency': self.frequency_var.get(),
                'interval': int(self.interval_var.get()) if self.interval_var.get().strip() else 1
            }
            
            if self.end_type_var.get() == "date":
                end_date = self.end_date_var.get().strip()
                if end_date:
                    pattern['end_date'] = end_date
            else:
                count = self.count_var.get().strip()
                if count:
                    pattern['occurrence_count'] = min(int(count), 100)  # Limit for safety
            
            # Create recurring event
            success, message = self.calendar_manager.recurring_events.create_recurring_event(base_event, pattern)
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
        
        except ValueError as e:
            messagebox.showerror("Error", "Invalid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create recurring event: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")



# Dialog Classes
class AddEventDialog:
    """Dialog for adding new events"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Event")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Add New Event", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Event name
        ttk.Label(main_frame, text="Event Name *").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        # Event type
        ttk.Label(main_frame, text="Event Type").pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social", 
                                       "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Date type selection
        date_type_frame = ttk.LabelFrame(main_frame, text="Date Configuration", padding=10)
        date_type_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.date_type = tk.StringVar(value="single")
        ttk.Radiobutton(date_type_frame, text="Single Date", variable=self.date_type, 
                       value="single", command=self._toggle_date_fields).pack(anchor=tk.W)
        ttk.Radiobutton(date_type_frame, text="Date Range", variable=self.date_type, 
                       value="range", command=self._toggle_date_fields).pack(anchor=tk.W)
        
        # Single date
        self.single_date_frame = ttk.Frame(date_type_frame)
        self.single_date_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.single_date_frame, text="Date (YYYY-MM-DD)").pack(anchor=tk.W)
        self.single_date_var = tk.StringVar()
        ttk.Entry(self.single_date_frame, textvariable=self.single_date_var, width=47).pack(fill=tk.X)
        
        # Date range
        self.date_range_frame = ttk.Frame(date_type_frame)
        
        ttk.Label(self.date_range_frame, text="Start Date (YYYY-MM-DD)").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(self.date_range_frame, textvariable=self.start_date_var, width=47).pack(fill=tk.X)
        
        ttk.Label(self.date_range_frame, text="End Date (YYYY-MM-DD)").pack(anchor=tk.W, pady=(10, 0))
        self.end_date_var = tk.StringVar()
        ttk.Entry(self.date_range_frame, textvariable=self.end_date_var, width=47).pack(fill=tk.X)
        
        # Description
        ttk.Label(main_frame, text="Description").pack(anchor=tk.W)
        self.description_text = scrolledtext.ScrolledText(main_frame, height=5, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Add Event", command=self._add_event).pack(side=tk.RIGHT)
        
        # Initialize date fields
        self._toggle_date_fields()
    
    def _toggle_date_fields(self):
        """Toggle date fields based on selection"""
        if self.date_type.get() == "single":
            self.single_date_frame.pack(fill=tk.X, pady=5)
            self.date_range_frame.pack_forget()
        else:
            self.single_date_frame.pack_forget()
            self.date_range_frame.pack(fill=tk.X, pady=5)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _add_event(self):
        """Add the event"""
        try:
            name = self.name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Event name is required")
                return
            
            event_type = self.type_var.get()
            description = self.description_text.get(1.0, tk.END).strip()
            
            if self.date_type.get() == "single":
                date = self.single_date_var.get().strip()
                if not date:
                    messagebox.showerror("Error", "Date is required")
                    return
                
                result = self.calendar_manager.add_event(
                    name=name,
                    date=date,
                    description=description,
                    event_type=event_type
                )
            else:
                start_date = self.start_date_var.get().strip()
                end_date = self.end_date_var.get().strip()
                
                if not start_date or not end_date:
                    messagebox.showerror("Error", "Both start and end dates are required")
                    return
                
                result = self.calendar_manager.add_event(
                    name=name,
                    date_start=start_date,
                    date_end=end_date,
                    description=description,
                    event_type=event_type
                )
            
            if result['success']:
                messagebox.showinfo("Success", result['message'])
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", result['message'])
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add event: {e}")


class EditEventDialog:
    """Dialog for editing existing events"""
    
    def __init__(self, parent, calendar_manager, event_data, callback=None):
        self.calendar_manager = calendar_manager
        self.event_data = event_data
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Event")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_event_data()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Edit Event", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Event ID (read-only)
        ttk.Label(main_frame, text="Event ID").pack(anchor=tk.W)
        id_frame = ttk.Frame(main_frame)
        id_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.id_var = tk.StringVar()
        id_entry = ttk.Entry(id_frame, textvariable=self.id_var, state="readonly")
        id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(id_frame, text="Copy", width=8,
                  command=lambda: self._copy_to_clipboard(self.id_var.get())).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Event name
        ttk.Label(main_frame, text="Event Name *").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        # Event type
        ttk.Label(main_frame, text="Event Type").pack(anchor=tk.W)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, width=47,
                                values=["Academic", "Holiday", "Administrative", "Social", 
                                       "Sports", "Trip", "Deadline"])
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Dates (simplified - show current structure)
        date_frame = ttk.LabelFrame(main_frame, text="Dates", padding=10)
        date_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Single date
        ttk.Label(date_frame, text="Date (YYYY-MM-DD)").pack(anchor=tk.W)
        self.date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_var, width=47).pack(fill=tk.X, pady=(5, 10))
        
        # Start date
        ttk.Label(date_frame, text="Start Date (YYYY-MM-DD)").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=47).pack(fill=tk.X, pady=(5, 10))
        
        # End date
        ttk.Label(date_frame, text="End Date (YYYY-MM-DD)").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=47).pack(fill=tk.X, pady=(5, 10))
        
        # Description
        ttk.Label(main_frame, text="Description").pack(anchor=tk.W)
        self.description_text = scrolledtext.ScrolledText(main_frame, height=5, width=50)
        self.description_text.pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Save Changes", command=self._save_event).pack(side=tk.RIGHT)
    
    def _load_event_data(self):
        """Load event data into form"""
        self.id_var.set(self.event_data.get('id', ''))
        self.name_var.set(self.event_data.get('name', ''))
        self.type_var.set(self.event_data.get('event_type', 'Academic'))
        self.date_var.set(self.event_data.get('date', ''))
        self.start_date_var.set(self.event_data.get('date_start', ''))
        self.end_date_var.set(self.event_data.get('date_end', ''))
        
        description = self.event_data.get('description', '')
        if description:
            self.description_text.insert(1.0, description)
    
    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(text)
        messagebox.showinfo("Copied", "Event ID copied to clipboard")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _save_event(self):
        """Save event changes"""
        try:
            updates = {}
            
            # Check what changed
            if self.name_var.get() != self.event_data.get('name', ''):
                updates['name'] = self.name_var.get().strip()
            
            if self.type_var.get() != self.event_data.get('event_type', ''):
                updates['event_type'] = self.type_var.get()
            
            if self.date_var.get() != self.event_data.get('date', ''):
                updates['date'] = self.date_var.get().strip() or None
            
            if self.start_date_var.get() != self.event_data.get('date_start', ''):
                updates['date_start'] = self.start_date_var.get().strip() or None
            
            if self.end_date_var.get() != self.event_data.get('date_end', ''):
                updates['date_end'] = self.end_date_var.get().strip() or None
            
            new_description = self.description_text.get(1.0, tk.END).strip()
            if new_description != self.event_data.get('description', ''):
                updates['description'] = new_description
            
            if not updates:
                messagebox.showinfo("No Changes", "No changes were made to the event")
                return
            
            result = self.calendar_manager.update_event(self.event_data['id'], updates)
            
            if result['success']:
                messagebox.showinfo("Success", result['message'])
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", result['message'])
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update event: {e}")


class EventDetailsDialog:
    """Dialog for viewing event details"""
    
    def __init__(self, parent, event_data):
        self.event_data = event_data
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Details")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Event Details", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Details frame
        details_frame = ttk.Frame(main_frame)
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Event details
        details = [
            ("Event ID:", self.event_data.get('id', 'N/A')),
            ("Name:", self.event_data.get('name', 'N/A')),
            ("Type:", self.event_data.get('event_type', 'N/A')),
            ("Date:", self.event_data.get('date', 'N/A')),
            ("Start Date:", self.event_data.get('date_start', 'N/A')),
            ("End Date:", self.event_data.get('date_end', 'N/A')),
            ("Created:", self.event_data.get('date_added', 'N/A')),
            ("Modified:", self.event_data.get('last_modified', 'N/A')),
            ("Created By:", self.event_data.get('created_by', 'N/A'))
        ]
        
        for i, (label, value) in enumerate(details):
            if value and value != 'N/A':
                label_widget = ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold'))
                label_widget.grid(row=i, column=0, sticky=tk.W, padx=(0, 10), pady=2)
                
                value_widget = ttk.Label(details_frame, text=str(value))
                value_widget.grid(row=i, column=1, sticky=tk.W, pady=2)
        
        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Description", padding=10)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        description = self.event_data.get('description', 'No description available')
        desc_text = scrolledtext.ScrolledText(desc_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
        desc_text.pack(fill=tk.BOTH, expand=True)
        desc_text.config(state=tk.NORMAL)
        desc_text.insert(1.0, description)
        desc_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(20, 0))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddAcademicYearDialog:
    """Dialog for adding academic years"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Academic Year")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Add Academic Year", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Academic year
        ttk.Label(main_frame, text="Academic Year (e.g., 2024-2025) *").pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.year_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Start date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD) *").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # End date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD) *").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Add", command=self._add_year).pack(side=tk.RIGHT)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _add_year(self):
        """Add academic year"""
        try:
            year = self.year_var.get().strip()
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()
            
            if not all([year, start_date, end_date]):
                messagebox.showerror("Error", "All fields are required")
                return
            
            success, message = self.calendar_manager.add_academic_year(year, start_date, end_date)
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add academic year: {e}")


class AddSemesterDialog:
    """Dialog for adding semesters"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Semester")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._load_academic_years()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Add Semester", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Academic year
        ttk.Label(main_frame, text="Academic Year *").pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        self.year_combo = ttk.Combobox(main_frame, textvariable=self.year_var, width=37)
        self.year_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Semester name
        ttk.Label(main_frame, text="Semester Name *").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        name_combo = ttk.Combobox(main_frame, textvariable=self.name_var, width=37,
                                values=["Fall", "Spring", "Summer", "Winter"])
        name_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Start date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD) *").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # End date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD) *").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Add", command=self._add_semester).pack(side=tk.RIGHT)
    
    def _load_academic_years(self):
        """Load academic years into combo box"""
        try:
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM academic_years ORDER BY start_date DESC"
            )
            year_list = [year['id'] for year in years]
            self.year_combo['values'] = year_list
            
            if year_list:
                self.year_var.set(year_list[0])
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load academic years: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _add_semester(self):
        """Add semester"""
        try:
            academic_year = self.year_var.get().strip()
            name = self.name_var.get().strip()
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()
            
            if not all([academic_year, name, start_date, end_date]):
                messagebox.showerror("Error", "All fields are required")
                return
            
            success, message = self.calendar_manager.add_semester(academic_year, name, start_date, end_date)
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add semester: {e}")


class ExportDialog:
    """Dialog for exporting calendar data"""
    
    def __init__(self, parent, calendar_manager):
        self.calendar_manager = calendar_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Calendar")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Export Calendar", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Export format
        format_frame = ttk.LabelFrame(main_frame, text="Export Format", padding=10)
        format_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.format_var = tk.StringVar(value="csv")
        formats = [
            ("CSV", "csv"),
            ("Excel", "xlsx"),
            ("PDF", "pdf"),
            ("JSON", "json"),
            ("iCal", "ics"),
            ("Text", "txt")
        ]
        
        for i, (label, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=label, variable=self.format_var, 
                           value=value).grid(row=i//2, column=i%2, sticky=tk.W, padx=10, pady=2)
        
        # Academic year filter
        filter_frame = ttk.LabelFrame(main_frame, text="Filter Options", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(filter_frame, text="Academic Year (optional):").pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        year_combo = ttk.Combobox(filter_frame, textvariable=self.year_var, width=40)
        year_combo.pack(fill=tk.X, pady=(5, 0))
        
        # Load academic years
        try:
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM academic_years ORDER BY start_date DESC"
            )
            year_list = ["All Years"] + [year['id'] for year in years]
            year_combo['values'] = year_list
            self.year_var.set("All Years")
        except:
            pass
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Output File", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_var, width=35)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(file_frame, text="Browse...", 
                  command=self._browse_file).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Export", command=self._export_calendar).pack(side=tk.RIGHT)
    
    def _browse_file(self):
        """Browse for output file"""
        format_ext = self.format_var.get()
        filetypes = {
            'csv': [("CSV files", "*.csv"), ("All files", "*.*")],
            'xlsx': [("Excel files", "*.xlsx"), ("All files", "*.*")],
            'pdf': [("PDF files", "*.pdf"), ("All files", "*.*")],
            'json': [("JSON files", "*.json"), ("All files", "*.*")],
            'ics': [("iCal files", "*.ics"), ("All files", "*.*")],
            'txt': [("Text files", "*.txt"), ("All files", "*.*")]
        }
        
        filename = filedialog.asksaveasfilename(
            title="Save Export As",
            defaultextension=f".{format_ext}",
            filetypes=filetypes.get(format_ext, [("All files", "*.*")])
        )
        
        if filename:
            self.file_var.set(filename)
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def _export_calendar(self):
        """Export calendar"""
        try:
            format_type = self.format_var.get()
            file_path = self.file_var.get().strip()
            academic_year = self.year_var.get()
            
            if not file_path:
                messagebox.showerror("Error", "Please select an output file")
                return
            
            academic_year = academic_year if academic_year != "All Years" else None
            
            result = self.calendar_manager.export_calendar(file_path, format_type, academic_year)
            
            if result['success']:
                messagebox.showinfo("Success", result['message'])
                if messagebox.askyesno("Open File", "Would you like to open the exported file?"):
                    try:
                        self.calendar_manager.safe_open_file(result['file_path'])
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not open file: {e}")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", result['message'])
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")


# Additional utility dialogs
class RecurringEventsDialog:
    """Dialog for managing recurring events"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Recurring Events")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🔄 Recurring Events", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Note about dateutil requirement
        note_frame = ttk.LabelFrame(main_frame, text="Note", padding=10)
        note_frame.pack(fill=tk.X, pady=(0, 15))
        
        note_text = ("Recurring events require the 'python-dateutil' library. "
                    "If not installed, this feature will not be available.")
        ttk.Label(note_frame, text=note_text, wraplength=500).pack()
        
        # Simple placeholder for now
        ttk.Label(main_frame, text="This feature is available in CLI mode.", 
                 font=('Arial', 10, 'italic')).pack(pady=20)
        
        ttk.Button(main_frame, text="Launch CLI Mode", 
                  command=self._launch_cli).pack(pady=10)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def _launch_cli(self):
        """Launch CLI mode for recurring events"""
        self.dialog.destroy()
        # This would trigger the CLI mode launch
        messagebox.showinfo("CLI Mode", "Use the 'CLI Mode' button in the main interface to access recurring events.")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class ReportsDialog:
    """Dialog for generating reports"""
    
    def __init__(self, parent, calendar_manager):
        self.calendar_manager = calendar_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Reports")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📊 Reports", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Report types
        reports_frame = ttk.LabelFrame(main_frame, text="Available Reports", padding=10)
        reports_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        reports = [
            ("📅 Events Summary", "Get a summary of all events"),
            ("📚 Academic Year Report", "Detailed academic year breakdown"),
            ("📊 Statistics Report", "Calendar usage statistics"),
            ("📈 Upcoming Events", "Events in the next 30 days")
        ]
        
        for report_name, description in reports:
            report_frame = ttk.Frame(reports_frame)
            report_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(report_frame, text=report_name, width=25,
                      command=lambda r=report_name: self._generate_report(r)).pack(side=tk.LEFT)
            ttk.Label(report_frame, text=description).pack(side=tk.LEFT, padx=(10, 0))
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(20, 0))
    
    def _generate_report(self, report_type):
        """Generate selected report"""
        try:
            if "Events Summary" in report_type:
                self._show_events_summary()
            elif "Academic Year" in report_type:
                self._show_academic_year_report()
            elif "Statistics" in report_type:
                self._show_statistics_report()
            elif "Upcoming Events" in report_type:
                self._show_upcoming_events()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def _show_events_summary(self):
        """Show events summary"""
        try:
            # Get basic statistics
            events = self.calendar_manager.db_manager.execute_query(
                "SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type"
            )
            
            summary = "EVENTS SUMMARY\n" + "="*50 + "\n\n"
            
            total_events = 0
            for event in events:
                summary += f"{event['event_type']}: {event['count']} events\n"
                total_events += event['count']
            
            summary += f"\nTotal Events: {total_events}"
            
            ReportViewDialog(self.dialog, "Events Summary", summary)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate events summary: {e}")
    
    def _show_academic_year_report(self):
        """Show academic year report"""
        try:
            if not self.calendar_manager:
                messagebox.showerror("Error", "Calendar manager is not available.")
                return

            # Fetch available academic years
            year_rows = self.calendar_manager.db_manager.execute_query(
                "SELECT id, start_date, end_date FROM academic_years ORDER BY start_date DESC"
            )

            if not year_rows:
                messagebox.showinfo(
                    "Academic Year Report",
                    "No academic years found. Please add an academic year before generating a report."
                )
                return

            year_lookup = {row['id']: dict(row) for row in year_rows}

            # Determine which academic year to report on
            if len(year_lookup) == 1:
                selected_year_id = next(iter(year_lookup))
            else:
                default_year_id = None
                current_year = None
                try:
                    current_year = self.calendar_manager.get_current_academic_year()
                except Exception as err:
                    gui_logger.warning(f"Unable to determine current academic year: {err}")

                if current_year and current_year.get('id') in year_lookup:
                    default_year_id = current_year['id']

                options_text = "\n".join(f" • {row['id']} ({row['start_date']} → {row['end_date']})"
                                         for row in year_rows)
                prompt = ("Enter the academic year identifier to report on:\n\n"
                          f"{options_text}\n\n"
                          "Leave blank to cancel.")

                selected_year_id = simpledialog.askstring(
                    "Select Academic Year",
                    prompt,
                    parent=self.dialog,
                    initialvalue=default_year_id or year_rows[0]['id']
                )

                if not selected_year_id:
                    return  # User cancelled

                selected_year_id = selected_year_id.strip()
                if selected_year_id not in year_lookup:
                    messagebox.showerror(
                        "Invalid Selection",
                        f"The academic year '{selected_year_id}' is not in the available list."
                    )
                    return

            # Generate the detailed summary from the calendar manager
            summary = self.calendar_manager.generate_academic_year_summary(selected_year_id)
            if not summary or not summary.get('success'):
                message = summary.get('error') if isinstance(summary, dict) else "Unknown error."
                messagebox.showerror("Error", f"Failed to generate report: {message}")
                return

            year_info = summary['academic_year']
            semesters = summary.get('semesters', [])
            events = summary.get('events', [])
            event_stats = summary.get('event_statistics', {})
            monthly_dist = summary.get('monthly_distribution', {})

            start_date = year_info.get('start_date', 'N/A')
            end_date = year_info.get('end_date', 'N/A')
            try:
                duration_days = (datetime.strptime(end_date, "%Y-%m-%d") -
                                 datetime.strptime(start_date, "%Y-%m-%d")).days + 1
            except Exception:
                duration_days = "N/A"

            report_lines = [
                f"ACADEMIC YEAR REPORT: {selected_year_id}",
                "=" * 60,
                "",
                f"Date Range       : {start_date} → {end_date}",
                f"Duration         : {duration_days} days" if isinstance(duration_days, int)
                                   else f"Duration         : {duration_days}",
                f"Total Semesters  : {len(semesters)}",
                f"Total Events     : {summary.get('total_events', 0)}",
                ""
            ]

            # Semesters overview
            report_lines.append("Semesters")
            report_lines.append("-" * 60)
            if semesters:
                for idx, semester in enumerate(semesters, start=1):
                    report_lines.append(
                        f"{idx}. {semester.get('name', 'Unnamed')} "
                        f"({semester.get('start_date', '?')} → {semester.get('end_date', '?')})"
                    )
            else:
                report_lines.append("No semesters recorded for this academic year.")
            report_lines.append("")

            # Event statistics by type
            report_lines.append("Events by Type")
            report_lines.append("-" * 60)
            if event_stats:
                for event_type, count in sorted(event_stats.items(), key=lambda item: (-item[1], item[0])):
                    report_lines.append(f"{event_type}: {count} event(s)")
            else:
                report_lines.append("No events recorded for this academic year.")
            report_lines.append("")

            # Monthly distribution
            report_lines.append("Monthly Distribution")
            report_lines.append("-" * 60)
            if monthly_dist:
                for month, count in sorted(monthly_dist.items()):
                    try:
                        month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
                    except Exception:
                        month_label = month
                    report_lines.append(f"{month_label}: {count} event(s)")
            else:
                report_lines.append("No monthly activity recorded.")
            report_lines.append("")

            # Highlight of key events (first 10 chronologically)
            report_lines.append("Key Events")
            report_lines.append("-" * 60)
            if events:
                def event_sort_key(evt: Dict[str, Any]) -> Tuple[Optional[datetime], str]:
                    date_str = evt.get('date') or evt.get('date_start')
                    try:
                        sort_date = datetime.strptime(date_str, "%Y-%m-%d")
                    except Exception:
                        sort_date = None
                    return (sort_date, evt.get('name', ''))

                sorted_events = sorted(events, key=event_sort_key)
                for event in sorted_events[:10]:
                    event_date = event.get('date') or event.get('date_start') or "N/A"
                    event_type = event.get('event_type', 'Unknown')
                    event_name = event.get('name', 'Untitled Event')
                    semester_name = event.get('semester_name') or 'Unassigned'
                    report_lines.append(f"{event_date} • {event_name} [{event_type}] — Semester: {semester_name}")
                    description = event.get('description')
                    if description:
                        trimmed = description.strip()
                        if len(trimmed) > 120:
                            trimmed = trimmed[:117] + "..."
                        report_lines.append(f"    {trimmed}")
                if len(sorted_events) > 10:
                    report_lines.append(f"...and {len(sorted_events) - 10} additional event(s).")
            else:
                report_lines.append("No events recorded for this academic year.")
            report_lines.append("")

            report_lines.append(f"Report generated at: {summary.get('generated_at', datetime.now().isoformat())}")

            report_content = "\n".join(report_lines)
            ReportViewDialog(self.dialog, f"Academic Year Report ({selected_year_id})", report_content)

        except PermissionError as perm_err:
            messagebox.showerror("Permission Denied", str(perm_err))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to generate academic year report: {exc}")
    
    def _show_statistics_report(self):
        """Show statistics report"""
        try:
            stats = self.calendar_manager.get_system_stats()
            
            report = "CALENDAR STATISTICS\n" + "="*50 + "\n\n"
            
            report += f"Current Academic Year: {stats.get('current_academic_year', 'None')}\n"
            report += f"Current Semester: {stats.get('current_semester', 'None')}\n"
            report += f"Total Academic Years: {stats.get('total_academic_years', 0)}\n"
            report += f"Total Semesters: {stats.get('total_semesters', 0)}\n"
            report += f"Upcoming Events (30 days): {stats.get('upcoming_events', 0)}\n\n"
            
            report += "Events by Type:\n"
            for event_type, count in stats.get('events_by_type', {}).items():
                report += f"  {event_type}: {count}\n"
            
            ReportViewDialog(self.dialog, "Statistics Report", report)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate statistics: {e}")
    
    def _show_upcoming_events(self):
        """Show upcoming events"""
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            
            events = self.calendar_manager.get_events_by_date_range(current_date, future_date)
            
            report = "UPCOMING EVENTS (Next 30 Days)\n" + "="*50 + "\n\n"
            
            if events:
                for event in events:
                    event_date = event.get('date') or event.get('date_start')
                    report += f"{event_date}: {event['name']} ({event['event_type']})\n"
                    if event.get('description'):
                        report += f"   {event['description'][:100]}...\n"
                    report += "\n"
            else:
                report += "No upcoming events found."
            
            ReportViewDialog(self.dialog, "Upcoming Events", report)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get upcoming events: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class ReportViewDialog:
    """Dialog for viewing generated reports"""
    
    def __init__(self, parent, title, content):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets(content)
        self._center_dialog()
    
    def _create_widgets(self, content):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Content
        text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Consolas', 10))
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        text_widget.insert(1.0, content)
        text_widget.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Save As...", 
                  command=lambda: self._save_report(content)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Copy", 
                  command=lambda: self._copy_report(content)).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)
    
    def _save_report(self, content):
        """Save report to file"""
        filename = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report saved to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save report: {e}")
    
    def _copy_report(self, content):
        """Copy report to clipboard"""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(content)
        messagebox.showinfo("Copied", "Report copied to clipboard")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class SettingsDialog:
    """Dialog for application settings"""
    
    def __init__(self, parent, calendar_manager, auth_manager):
        self.calendar_manager = calendar_manager
        self.auth_manager = auth_manager
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Settings")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🔧 Settings", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Notebook for different setting categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # General settings
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="General")
        
        ttk.Label(general_frame, text="Default Event Type:").pack(anchor=tk.W)
        self.default_type_var = tk.StringVar(value="Academic")
        type_combo = ttk.Combobox(general_frame, textvariable=self.default_type_var,
                                values=["Academic", "Holiday", "Administrative", "Social", "Sports", "Trip"])
        type_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Database settings
        db_frame = ttk.Frame(notebook, padding=10)
        notebook.add(db_frame, text="Database")
        
        ttk.Label(db_frame, text="Database File:").pack(anchor=tk.W)
        self.db_file_var = tk.StringVar(value=self.calendar_manager.config.db_file)
        ttk.Entry(db_frame, textvariable=self.db_file_var, state="readonly").pack(fill=tk.X, pady=(5, 15))
        
        ttk.Button(db_frame, text="Create Backup", 
                  command=self._create_backup).pack(anchor=tk.W, pady=5)
        ttk.Button(db_frame, text="Verify Database", 
                  command=self._verify_database).pack(anchor=tk.W, pady=5)
        
        # User info
        user_frame = ttk.Frame(notebook, padding=10)
        notebook.add(user_frame, text="User Info")
        
        if self.auth_manager and self.auth_manager.current_user:
            user_info = [
                ("Username:", self.auth_manager.current_user.get('username', 'N/A')),
                ("Role:", self.auth_manager.current_user.get('role', 'N/A')),
                ("User ID:", self.auth_manager.current_user.get('id', 'N/A'))
            ]
            
            for label, value in user_info:
                info_frame = ttk.Frame(user_frame)
                info_frame.pack(fill=tk.X, pady=5)
                ttk.Label(info_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
                ttk.Label(info_frame, text=str(value)).pack(side=tk.LEFT, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Apply", command=self._apply_settings).pack(side=tk.RIGHT)
    
    def _create_backup(self):
        """Create database backup"""
        try:
            result = self.calendar_manager.create_backup()
            if result['success']:
                messagebox.showinfo("Success", result['message'])
            else:
                messagebox.showerror("Error", result['message'])
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {e}")
    
    def _verify_database(self):
        """Verify database integrity"""
        try:
            success = self.calendar_manager.verify_calendar_database_integrity()
            if success:
                messagebox.showinfo("Success", "Database verification completed successfully")
            else:
                messagebox.showwarning("Warning", "Database verification found issues (check logs)")
        except Exception as e:
            messagebox.showerror("Error", f"Verification failed: {e}")
    
    def _apply_settings(self):
        """Apply settings"""
        messagebox.showinfo("Settings", "Settings applied successfully")
        self.dialog.destroy()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


# Additional utility dialogs
class ImportCalendarDialog:
    """Dialog for importing calendar data"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Import Calendar")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Import Calendar", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Import options
        options_frame = ttk.LabelFrame(main_frame, text="Import Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.import_type = tk.StringVar(value="file")
        ttk.Radiobutton(options_frame, text="Import from file", 
                       variable=self.import_type, value="file").pack(anchor=tk.W)
        ttk.Radiobutton(options_frame, text="Import from URL (iCal)", 
                       variable=self.import_type, value="url").pack(anchor=tk.W)
        
        # File/URL input
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(input_frame, text="File/URL:").pack(anchor=tk.W)
        
        file_frame = ttk.Frame(input_frame)
        file_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse...", 
                  command=self._browse_file).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Import", command=self._import_calendar).pack(side=tk.RIGHT)
    
    def _browse_file(self):
        """Browse for import file"""
        filename = filedialog.askopenfilename(
            title="Select Calendar File",
            filetypes=[
                ("iCal files", "*.ics"),
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            self.file_var.set(filename)
    
    def _import_calendar(self):
        """Import calendar"""
        try:
            source = self.file_var.get().strip()
            if not source:
                messagebox.showerror("Error", "Please select a file or enter a URL")
                return

            if self.import_type.get() == "url":
                # Import from URL (iCal sync)
                result = self.calendar_manager.calendar_sync(source)
                message = f"Imported {result['synced']} events from URL"
                messagebox.showinfo("Success", message)
            else:
                # Import from file
                if not os.path.exists(source):
                    messagebox.showerror("Error", "Selected file does not exist")
                    return

                imported_count = 0
                error_count = 0

                # Determine file type and import accordingly
                file_ext = os.path.splitext(source)[1].lower()

                if file_ext == '.ics':
                    # Import iCal file
                    try:
                        import ics
                        with open(source, 'r', encoding='utf-8') as f:
                            calendar_data = ics.Calendar(f.read())

                        for event in calendar_data.events:
                            try:
                                # Convert ics event to our format
                                self.calendar_manager.create_event(
                                    title=str(event.name) if event.name else "Imported Event",
                                    start_datetime=event.begin.datetime if event.begin else datetime.now(),
                                    end_datetime=event.end.datetime if event.end else datetime.now() + timedelta(hours=1),
                                    description=str(event.description) if event.description else "",
                                    location=str(event.location) if event.location else ""
                                )
                                imported_count += 1
                            except Exception:
                                error_count += 1
                    except ImportError:
                        messagebox.showerror("Error", "ICS library not available. Install with: pip install ics")
                        return

                elif file_ext == '.json':
                    # Import JSON file
                    try:
                        with open(source, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        events = data if isinstance(data, list) else data.get('events', [])

                        for event_data in events:
                            try:
                                start_dt = datetime.fromisoformat(event_data.get('start_datetime', datetime.now().isoformat()))
                                end_dt = datetime.fromisoformat(event_data.get('end_datetime', (start_dt + timedelta(hours=1)).isoformat()))

                                self.calendar_manager.create_event(
                                    title=event_data.get('title', 'Imported Event'),
                                    start_datetime=start_dt,
                                    end_datetime=end_dt,
                                    description=event_data.get('description', ''),
                                    location=event_data.get('location', ''),
                                    category=event_data.get('category', 'imported')
                                )
                                imported_count += 1
                            except Exception:
                                error_count += 1
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid JSON file format")
                        return

                elif file_ext == '.csv':
                    # Import CSV file
                    try:
                        import csv
                        with open(source, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)

                            for row in reader:
                                try:
                                    start_dt = datetime.strptime(row.get('start_datetime', ''), '%Y-%m-%d %H:%M:%S')
                                    end_dt = datetime.strptime(row.get('end_datetime', ''), '%Y-%m-%d %H:%M:%S') if row.get('end_datetime') else start_dt + timedelta(hours=1)

                                    self.calendar_manager.create_event(
                                        title=row.get('title', 'Imported Event'),
                                        start_datetime=start_dt,
                                        end_datetime=end_dt,
                                        description=row.get('description', ''),
                                        location=row.get('location', ''),
                                        category=row.get('category', 'imported')
                                    )
                                    imported_count += 1
                                except Exception:
                                    error_count += 1
                    except Exception:
                        messagebox.showerror("Error", "Error reading CSV file")
                        return
                else:
                    messagebox.showerror("Error", "Unsupported file format. Please use .ics, .json, or .csv files")
                    return

                # Show import results
                if imported_count > 0:
                    message = f"Successfully imported {imported_count} events"
                    if error_count > 0:
                        message += f" ({error_count} errors)"
                    messagebox.showinfo("Import Complete", message)
                else:
                    messagebox.showwarning("Import Warning", "No events were imported")

            if self.callback:
                self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class CalendarSyncDialog:
    """Dialog for calendar synchronization"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Calendar Sync")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🔄 Calendar Sync", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # URL input
        ttk.Label(main_frame, text="iCal URL:").pack(anchor=tk.W)
        self.url_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.url_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        # Local calendar selection
        ttk.Label(main_frame, text="Local Calendar (optional):").pack(anchor=tk.W)
        self.local_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.local_var, width=50).pack(fill=tk.X, pady=(5, 15))
        
        # Sync options
        options_frame = ttk.LabelFrame(main_frame, text="Sync Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.skip_holidays = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip holidays/breaks", 
                       variable=self.skip_holidays).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Sync", command=self._sync_calendar).pack(side=tk.RIGHT)
    
    def _sync_calendar(self):
        """Perform calendar sync"""
        try:
            url = self.url_var.get().strip()
            if not url:
                messagebox.showerror("Error", "Please enter an iCal URL")
                return
            
            local_calendar = self.local_var.get().strip() or None
            
            # Show progress
            progress_dialog = tk.Toplevel(self.dialog)
            progress_dialog.title("Syncing...")
            progress_dialog.geometry("300x100")
            progress_dialog.transient(self.dialog)
            progress_dialog.grab_set()
            
            ttk.Label(progress_dialog, text="Syncing calendar...").pack(pady=20)
            progress = ttk.Progressbar(progress_dialog, mode='indeterminate')
            progress.pack(pady=10)
            progress.start()
            
            def sync_worker():
                try:
                    result = self.calendar_manager.calendar_sync(url, local_calendar)
                    
                    progress_dialog.after(0, progress_dialog.destroy)
                    
                    message = (f"Sync completed!\n"
                              f"Synced: {result['synced']} events\n"
                              f"Skipped: {result['skipped_holidays']} holidays\n"
                              f"Conflicts: {len(result['conflicts'])} conflicts found")
                    
                    self.dialog.after(0, lambda: messagebox.showinfo("Sync Complete", message))
                    
                    if self.callback:
                        self.dialog.after(0, self.callback)
                    
                    self.dialog.after(0, self.dialog.destroy)
                    
                except Exception as e:
                    progress_dialog.after(0, progress_dialog.destroy)
                    self.dialog.after(0, lambda: messagebox.showerror("Sync Error", f"Sync failed: {e}"))
            
            sync_thread = threading.Thread(target=sync_worker, daemon=True)
            sync_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Sync setup failed: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class ImportHolidaysDialog:
    """Dialog for importing holidays"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Import Holidays")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🎉 Import Holidays", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Country selection
        ttk.Label(main_frame, text="Country Code:").pack(anchor=tk.W)
        self.country_var = tk.StringVar(value="US")
        country_combo = ttk.Combobox(main_frame, textvariable=self.country_var, width=40,
                                   values=["US", "UK", "CA", "AU", "DE", "FR", "JP", "IN"])
        country_combo.pack(fill=tk.X, pady=(5, 15))
        
        # Year selection
        ttk.Label(main_frame, text="Year:").pack(anchor=tk.W)
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Entry(main_frame, textvariable=self.year_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Region/State (optional)
        ttk.Label(main_frame, text="Region/State (optional):").pack(anchor=tk.W)
        self.region_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.region_var, width=40).pack(fill=tk.X, pady=(5, 15))
        
        # Note
        note_frame = ttk.LabelFrame(main_frame, text="Note", padding=5)
        note_frame.pack(fill=tk.X, pady=(10, 15))
        
        note_text = "Requires 'holidays' library. Install with: pip install holidays"
        ttk.Label(note_frame, text=note_text, font=('Arial', 9)).pack()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Import", command=self._import_holidays).pack(side=tk.RIGHT)
    
    def _import_holidays(self):
        """Import holidays"""
        try:
            country = self.country_var.get().strip().upper()
            year_str = self.year_var.get().strip()
            region = self.region_var.get().strip() or None
            
            if not country or not year_str:
                messagebox.showerror("Error", "Country and year are required")
                return
            
            year = int(year_str)
            
            success, message = self.calendar_manager.holidays.import_national_holidays(
                country, year, region
            )
            
            if success:
                messagebox.showinfo("Success", message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", message)
                
        except ValueError:
            messagebox.showerror("Error", "Invalid year format")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class BulkOperationsDialog:
    """Dialog for bulk operations"""
    
    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Operations")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="⚡ Bulk Operations", 
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        
        # Operations
        ops_frame = ttk.LabelFrame(main_frame, text="Available Operations", padding=10)
        ops_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        operations = [
            ("📝 Bulk Create Events", "Create multiple events at once"),
            ("✏️ Bulk Update Events", "Update multiple events"),
            ("📋 Create Event Template", "Create reusable templates"),
            ("🧹 Cleanup Old Data", "Clean up old calendar data")
        ]
        
        for op_name, description in operations:
            op_frame = ttk.Frame(ops_frame)
            op_frame.pack(fill=tk.X, pady=5)
            
            ttk.Button(op_frame, text=op_name, width=25,
                      command=lambda o=op_name: self._perform_operation(o)).pack(side=tk.LEFT)
            ttk.Label(op_frame, text=description).pack(side=tk.LEFT, padx=(10, 0))
        
        # Note
        note_frame = ttk.LabelFrame(main_frame, text="Note", padding=5)
        note_frame.pack(fill=tk.X, pady=(10, 0))
        
        note_text = "Advanced bulk operations are available in CLI mode for more detailed control."
        ttk.Label(note_frame, text=note_text, wraplength=450).pack()
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(15, 0))
    
    def _perform_operation(self, operation):
        """Perform selected bulk operation"""
        if "Bulk Create" in operation:
            messagebox.showinfo("Info", "Use the 'Add Event' button to create events individually, or CLI mode for bulk operations.")
        elif "Bulk Update" in operation:
            messagebox.showinfo("Info", "Use the event management view to edit events individually, or CLI mode for bulk updates.")
        elif "Template" in operation:
            messagebox.showinfo("Info", "Event templates are available in CLI mode.")
        elif "Cleanup" in operation:
            self._cleanup_old_data()
    
    def _cleanup_old_data(self):
        """Clean up old data"""
        if messagebox.askyesno("Confirm Cleanup", "This will remove old events and data. Continue?"):
            try:
                result = self.calendar_manager.cleanup_old_data()
                if result['success']:
                    message = (f"Cleanup completed!\n"
                              f"Cleaned events: {result['cleaned_events']}\n"
                              f"Cleaned notifications: {result['cleaned_notifications']}\n"
                              f"Cleaned audit logs: {result['cleaned_audit_logs']}")
                    messagebox.showinfo("Cleanup Complete", message)
                    if self.callback:
                        self.callback()
                else:
                    messagebox.showerror("Error", result['error'])
            except Exception as e:
                messagebox.showerror("Error", f"Cleanup failed: {e}")
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class HelpDialog:
    """Help dialog with user guide"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("User Guide")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create help dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📚 User Guide", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Help content
        help_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=25)
        help_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        help_content = """
ACADEMIC CALENDAR MANAGEMENT SYSTEM - USER GUIDE

OVERVIEW
========
This application provides a comprehensive interface for managing academic calendars,
events, and schedules. It includes both a modern GUI and backward-compatible CLI mode.

MAIN FEATURES
=============

📊 Dashboard
- View system statistics and recent events
- Quick access to common operations
- System status information

📅 Calendar View
- Browse events by academic year and semester
- Filter and search capabilities
- Visual calendar display

➕ Add Events
- Create single-date or date-range events
- Multiple event types (Academic, Holiday, Administrative, etc.)
- Rich text descriptions

📝 Manage Events
- Edit existing events
- Delete events
- View detailed event information
- Search and filter events

📚 Academic Years & Semesters
- Create and manage academic years
- Add semesters to academic years
- Hierarchical organization

📤 Export
- Multiple export formats (CSV, Excel, PDF, JSON, iCal, Text)
- Filter by academic year
- Customizable output

🔄 Import & Sync
- Import from iCal URLs
- Import holiday calendars
- Synchronize with external calendars

📊 Reports
- Generate various reports
- Export reports to files
- Statistical analysis

KEYBOARD SHORTCUTS
==================
Ctrl+N     - Add new event
Ctrl+E     - Export calendar
Ctrl+R     - Refresh current view
F5         - Refresh current view
Ctrl+Q     - Quit application

BACKWARD COMPATIBILITY
======================
The application includes full backward compatibility with the original CLI interface.
Click "CLI Mode" in the sidebar or use the Tools menu to access all original functions.

CLI MODE FEATURES
=================
- All original command-line functions
- Advanced bulk operations
- Recurring events management
- Detailed reporting and analytics
- Trip management integration
- Project milestone tracking
- Advanced search capabilities

PERMISSIONS
===========
Different users have different permissions based on their role:
- Students: View calendars and own events
- Teachers: Manage course-related events
- Administrators: Full system access

GETTING HELP
============
- Use this help dialog for quick reference
- Access CLI mode for advanced features
- Check the About dialog for version information
- Contact system administrator for technical support

TIPS & TRICKS
=============
- Use right-click context menus for quick actions
- Double-click events to edit them
- Use the search function to quickly find events
- Export calendars regularly as backups
- Use CLI mode for advanced operations

TROUBLESHOOTING
===============
- If features are missing, check your user permissions
- Use "Verify Database" in Settings if you encounter errors
- Create backups before major operations
- Some advanced features require additional Python libraries
- Check the status bar for operation feedback
        """
        
        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack()
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AboutDialog:
    """About dialog with application information"""
    
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("About")
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        
        self._create_widgets()
        self._center_dialog()
    
    def _create_widgets(self):
        """Create about dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=30)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Application icon/title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(pady=(0, 20))
        
        ttk.Label(title_frame, text="📅", font=('Arial', 48)).pack()
        ttk.Label(title_frame, text="Academic Calendar Management System", 
                 font=('Arial', 14, 'bold')).pack(pady=(10, 0))
        
        # Version info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(pady=(0, 20))
        
        info_text = [
            ("Version:", "2.0 (GUI + CLI)"),
            ("Release:", "2024"),
            ("License:", "Educational Use"),
            ("Interface:", "Modern GUI with CLI Compatibility"),
            ("Platform:", f"{platform.system()} {platform.release()}")
        ]
        
        for label, value in info_text:
            row_frame = ttk.Frame(info_frame)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=label, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=value).pack(side=tk.LEFT, padx=(10, 0))
        
        # Features
        features_frame = ttk.LabelFrame(main_frame, text="Key Features", padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 20))
        
        features = [
            "📅 Comprehensive calendar management",
            "📊 Advanced reporting and analytics", 
            "🔄 Import/export multiple formats",
            "🎒 Trip management integration",
            "💻 Backward-compatible CLI mode",
            "🔐 Role-based access control",
            "📱 Modern, intuitive interface"
        ]
        
        for feature in features:
            ttk.Label(features_frame, text=feature).pack(anchor=tk.W, pady=1)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(10, 0))
    
    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


# Main application launcher
def launch_calendar_gui(auth_manager=None):
    """
    Launch the Calendar GUI application
    
    Args:
        auth_manager: Authentication manager instance (optional)
    
    Returns:
        CalendarGUI instance
    """
    try:
        # Ensure calendar permissions exist
        from university_system.modules.domain.academics.services.academic_calendar import ensure_calendar_permissions
        ensure_calendar_permissions()
        
        # Create and run GUI
        gui = CalendarGUI(auth_manager)
        return gui
        
    except ImportError as e:
        # Handle missing dependencies gracefully
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        error_msg = (f"Failed to import required modules: {e}\n\n"
                    "Please ensure all dependencies are installed:\n"
                    "- tkinter (usually included with Python)\n" 
                    "- The academic_calendar module\n"
                    "- All calendar system dependencies")
        
        messagebox.showerror("Import Error", error_msg)
        root.destroy()
        return None
        
    except Exception as e:
        # Handle other initialization errors
        root = tk.Tk()
        root.withdraw()
        
        error_msg = (f"Failed to initialize calendar GUI: {e}\n\n"
                    "This may be due to:\n"
                    "- Missing database permissions\n"
                    "- Corrupted configuration\n"
                    "- System compatibility issues\n\n"
                    "Try running in CLI mode or contact support.")
        
        messagebox.showerror("Initialization Error", error_msg)
        root.destroy()
        return None


def run_gui_calendar(auth_manager=None):
    """
    Convenience function to launch and run the calendar GUI
    
    Args:
        auth_manager: Authentication manager instance (optional)
    """
    gui = launch_calendar_gui(auth_manager)
    if gui:
        gui.run()


# Backward compatibility function
def display_academic_calendar_gui(auth_manager=None):
    """
    Backward compatibility function for GUI launch
    Maintains same signature as CLI function
    """
    return run_gui_calendar(auth_manager)


# Integration function for main system
def integrate_with_main_system():
    """
    Integration function to be called from main system
    Provides seamless integration with existing authentication
    """
    try:
        # Import the main authentication system
        from university_system.infrastructure.auth.user_authentication import _current_auth_instance
        
        if _current_auth_instance and _current_auth_instance.current_user:
            # User is authenticated, launch GUI
            return run_gui_calendar(_current_auth_instance)
        else:
            # No authentication, show error
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Authentication Required", 
                               "Please log in to access the calendar system.")
            root.destroy()
            return None
            
    except ImportError:
        # Fallback to basic GUI without authentication
        messagebox.showwarning("Authentication Unavailable", 
                             "Running in limited mode without authentication.")
        return run_gui_calendar()


if __name__ == "__main__":
    """
    Main entry point for standalone GUI execution
    """
    print("Academic Calendar GUI - Starting...")
    
    # Try to set up authentication
    auth_manager = None
    try:
        from university_system.modules.domain.academics.services.academic_calendar import auth
        auth_manager = auth
    except:
        print("Running without authentication")
    
    # Launch GUI
    gui = launch_calendar_gui(auth_manager)
    if gui:
        print("GUI launched successfully")
        gui.run()
    else:
        print("Failed to launch GUI")


# Export main classes for external use
__all__ = [
    'CalendarGUI',
    'launch_calendar_gui', 
    'run_gui_calendar',
    'display_academic_calendar_gui',
    'integrate_with_main_system',
    # Main dialog classes
    'AddEventDialog',
    'EditEventDialog', 
    'EventDetailsDialog',
    'AddAcademicYearDialog',
    'AddSemesterDialog',
    'ExportDialog',
    'ReportsDialog',
    'SettingsDialog',
    'ImportCalendarDialog',
    'CalendarSyncDialog',
    'ImportHolidaysDialog',
    'BulkOperationsDialog',
    'HelpDialog',
    'AboutDialog',
    # New dialog classes added
    'ResourceManagementDialog',
    'AddResourceDialog',
    'BookResourceDialog',
    'CourseManagementDialog',
    'NotificationSettingsDialog',
    'EventCategoriesDialog',
    'AdvancedSearchDialog',
    'RecurringEventDialog',
    'SystemMaintenanceDialog',
    'AuditLogsDialog',
    'AuditDetailsDialog',
    'ProjectMilestonesDialog',
    'DataVisualizationDialog',
    'TimezoneSettingsDialog',
    # Helper dialog classes
    'AddMilestoneDialog',
    'UpdateMilestoneDialog',
    'AddCategoryDialog',
    'AddTagDialog',
    'AssignTagDialog',
    'AddCourseDialog',
    'LinkCourseEventDialog',
    'ReportViewDialog'  # This was already in the original file
]
