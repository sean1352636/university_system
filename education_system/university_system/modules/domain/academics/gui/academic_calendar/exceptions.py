import logging
from datetime import datetime
from typing import Any, Dict, Optional, List

gui_logger = logging.getLogger(__name__)

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


