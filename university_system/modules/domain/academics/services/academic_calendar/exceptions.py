import json
import traceback
import logging
from datetime import datetime
from typing import Dict, List, Any
from university_system.utils.logging.log_config import configure_logging

logger = configure_logging(name=__name__)
exception_logger = logging.getLogger(__name__ + '.exceptions')


class CalendarError(Exception):
    """Base exception for calendar operations with enhanced functionality"""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None,
                 original_exception: Exception = None, user_message: str = None):
        """
        Initialize the calendar error

        Args:
            message: Technical error message for developers
            error_code: Unique error code for programmatic handling
            context: Additional context information
            original_exception: The original exception that caused this error
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.context = context or {}
        self.original_exception = original_exception
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.now()
        self.stack_trace = traceback.format_exc() if original_exception else None

        # Log the error
        self._log_error()

    def _generate_error_code(self) -> str:
        """Generate a default error code based on exception type"""
        return f"{self.__class__.__name__.upper()}_001"

    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message"""
        return "An error occurred in the calendar system. Please try again or contact support."

    def _log_error(self):
        """Log the error with appropriate level"""
        log_data = {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
            'user_message': self.user_message
        }

        if self.original_exception:
            log_data['original_exception'] = str(self.original_exception)
            log_data['stack_trace'] = self.stack_trace

        exception_logger.error(f"Calendar Error: {json.dumps(log_data, indent=2)}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'user_message': self.user_message,
            'context': self.context,
            'timestamp': self.timestamp.isoformat()
        }

    def add_context(self, key: str, value: Any) -> 'CalendarError':
        """Add context information to the error"""
        self.context[key] = value
        return self

    def __str__(self) -> str:
        """String representation of the error"""
        return f"{self.__class__.__name__}({self.error_code}): {self.message}"

    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (f"{self.__class__.__name__}("
                f"message='{self.message}', "
                f"error_code='{self.error_code}', "
                f"context={self.context})")


class ValidationError(CalendarError):
    """Raised when input validation fails"""

    def __init__(self, message: str, field_name: str = None, field_value: Any = None,
                 validation_rules: List[str] = None, **kwargs):
        """
        Initialize validation error

        Args:
            message: Error message
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            validation_rules: List of validation rules that were violated
        """
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rules = validation_rules or []

        # Add validation-specific context
        context = kwargs.get('context', {})
        if field_name:
            context['field_name'] = field_name
        if field_value is not None:
            context['field_value'] = str(field_value)
        if validation_rules:
            context['validation_rules'] = validation_rules

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate validation-specific error code"""
        if self.field_name:
            return f"VALIDATION_ERROR_{self.field_name.upper()}"
        return "VALIDATION_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly validation message"""
        if self.field_name:
            return f"The value provided for '{self.field_name}' is not valid. Please check your input and try again."
        return "The information provided is not valid. Please check your input and try again."

    @classmethod
    def required_field(cls, field_name: str) -> 'ValidationError':
        """Create a required field validation error"""
        return cls(
            message=f"Required field '{field_name}' is missing or empty",
            field_name=field_name,
            validation_rules=["required"],
            user_message=f"The field '{field_name}' is required."
        )

    @classmethod
    def invalid_format(cls, field_name: str, field_value: Any, expected_format: str) -> 'ValidationError':
        """Create an invalid format validation error"""
        return cls(
            message=f"Field '{field_name}' has invalid format. Expected: {expected_format}",
            field_name=field_name,
            field_value=field_value,
            validation_rules=["format"],
            user_message=f"The format for '{field_name}' is incorrect. Expected format: {expected_format}"
        )

    @classmethod
    def out_of_range(cls, field_name: str, field_value: Any, min_val: Any = None, max_val: Any = None) -> 'ValidationError':
        """Create an out of range validation error"""
        range_msg = ""
        if min_val is not None and max_val is not None:
            range_msg = f"between {min_val} and {max_val}"
        elif min_val is not None:
            range_msg = f"at least {min_val}"
        elif max_val is not None:
            range_msg = f"at most {max_val}"

        return cls(
            message=f"Field '{field_name}' value {field_value} is out of range. Expected {range_msg}",
            field_name=field_name,
            field_value=field_value,
            validation_rules=["range"],
            user_message=f"The value for '{field_name}' must be {range_msg}."
        )


class DatabaseError(CalendarError):
    """Raised when database operations fail"""

    def __init__(self, message: str, operation: str = None, table: str = None,
                 query: str = None, error_code: str = None, **kwargs):
        """
        Initialize database error

        Args:
            message: Error message
            operation: Database operation that failed (SELECT, INSERT, UPDATE, DELETE)
            table: Table name where error occurred
            query: SQL query that failed
            error_code: Database-specific error code
        """
        self.operation = operation
        self.table = table
        self.query = query
        self.db_error_code = error_code

        # Add database-specific context
        context = kwargs.get('context', {})
        if operation:
            context['operation'] = operation
        if table:
            context['table'] = table
        if query:
            context['query'] = query[:200] + "..." if len(query) > 200 else query  # Truncate long queries
        if error_code:
            context['db_error_code'] = error_code

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate database-specific error code"""
        if self.operation and self.table:
            return f"DB_ERROR_{self.operation}_{self.table.upper()}"
        elif self.operation:
            return f"DB_ERROR_{self.operation}"
        return "DB_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly database error message"""
        if self.operation:
            operation_messages = {
                'SELECT': 'retrieve data from',
                'INSERT': 'save data to',
                'UPDATE': 'update data in',
                'DELETE': 'remove data from'
            }
            op_msg = operation_messages.get(self.operation, 'access')
            return f"Unable to {op_msg} the database. Please try again or contact support."
        return "A database error occurred. Please try again or contact support."

    @classmethod
    def connection_failed(cls, details: str = None) -> 'DatabaseError':
        """Create a database connection error"""
        return cls(
            message=f"Database connection failed: {details or 'Unknown reason'}",
            operation="CONNECT",
            user_message="Unable to connect to the database. Please try again later."
        )

    @classmethod
    def constraint_violation(cls, constraint: str, table: str = None) -> 'DatabaseError':
        """Create a constraint violation error"""
        return cls(
            message=f"Database constraint violation: {constraint}",
            operation="CONSTRAINT",
            table=table,
            user_message="The operation violates database rules. Please check your data and try again."
        )

    @classmethod
    def record_not_found(cls, table: str, identifier: str = None) -> 'DatabaseError':
        """Create a record not found error"""
        return cls(
            message=f"Record not found in table {table}" + (f" with identifier {identifier}" if identifier else ""),
            operation="SELECT",
            table=table,
            user_message="The requested record was not found."
        )


class AuthenticationError(CalendarError):
    """Raised when authentication fails"""

    def __init__(self, message: str, username: str = None, auth_method: str = None,
                 reason: str = None, **kwargs):
        """
        Initialize authentication error

        Args:
            message: Error message
            username: Username that failed authentication
            auth_method: Authentication method used
            reason: Reason for authentication failure
        """
        self.username = username
        self.auth_method = auth_method
        self.reason = reason

        # Add auth-specific context (but don't expose sensitive info)
        context = kwargs.get('context', {})
        if username:
            context['username'] = username
        if auth_method:
            context['auth_method'] = auth_method
        if reason:
            context['reason'] = reason

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate authentication-specific error code"""
        if self.reason:
            return f"AUTH_ERROR_{self.reason.upper()}"
        return "AUTH_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly authentication error message"""
        reason_messages = {
            'invalid_credentials': 'Invalid username or password.',
            'account_locked': 'Your account has been locked. Please contact support.',
            'account_disabled': 'Your account has been disabled. Please contact support.',
            'session_expired': 'Your session has expired. Please log in again.',
            'insufficient_permissions': 'You do not have permission to perform this action.'
        }

        return reason_messages.get(self.reason, 'Authentication failed. Please check your credentials and try again.')

    @classmethod
    def invalid_credentials(cls, username: str = None) -> 'AuthenticationError':
        """Create invalid credentials error"""
        return cls(
            message="Invalid username or password provided",
            username=username,
            reason="invalid_credentials"
        )

    @classmethod
    def session_expired(cls, username: str = None) -> 'AuthenticationError':
        """Create session expired error"""
        return cls(
            message="User session has expired",
            username=username,
            reason="session_expired"
        )

    @classmethod
    def account_locked(cls, username: str) -> 'AuthenticationError':
        """Create account locked error"""
        return cls(
            message=f"Account {username} is locked",
            username=username,
            reason="account_locked"
        )


class PermissionError(CalendarError):
    """Raised when user lacks required permissions"""

    def __init__(self, message: str, required_permission: str = None, user_role: str = None,
                 resource: str = None, action: str = None, **kwargs):
        """
        Initialize permission error

        Args:
            message: Error message
            required_permission: Permission that was required
            user_role: Current user's role
            resource: Resource being accessed
            action: Action being attempted
        """
        self.required_permission = required_permission
        self.user_role = user_role
        self.resource = resource
        self.action = action

        # Add permission-specific context
        context = kwargs.get('context', {})
        if required_permission:
            context['required_permission'] = required_permission
        if user_role:
            context['user_role'] = user_role
        if resource:
            context['resource'] = resource
        if action:
            context['action'] = action

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate permission-specific error code"""
        if self.required_permission:
            return f"PERMISSION_ERROR_{self.required_permission.upper()}"
        return "PERMISSION_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly permission error message"""
        if self.action and self.resource:
            return f"You do not have permission to {self.action} {self.resource}."
        elif self.required_permission:
            return f"You need '{self.required_permission}' permission to perform this action."
        return "You do not have sufficient permissions to perform this action."

    @classmethod
    def insufficient_role(cls, required_role: str, current_role: str, action: str = None) -> 'PermissionError':
        """Create insufficient role error"""
        return cls(
            message=f"Role '{current_role}' insufficient. Required: '{required_role}'",
            user_role=current_role,
            action=action,
            user_message=f"You need '{required_role}' role to perform this action."
        )

    @classmethod
    def resource_access_denied(cls, resource: str, action: str, required_permission: str = None) -> 'PermissionError':
        """Create resource access denied error"""
        return cls(
            message=f"Access denied to {action} {resource}",
            required_permission=required_permission,
            resource=resource,
            action=action
        )


class ExportError(CalendarError):
    """Raised when export operations fail"""

    def __init__(self, message: str, export_format: str = None, file_path: str = None,
                 data_size: int = None, **kwargs):
        """
        Initialize export error

        Args:
            message: Error message
            export_format: Format being exported (CSV, PDF, etc.)
            file_path: Path where export was attempted
            data_size: Size of data being exported
        """
        self.export_format = export_format
        self.file_path = file_path
        self.data_size = data_size

        # Add export-specific context
        context = kwargs.get('context', {})
        if export_format:
            context['export_format'] = export_format
        if file_path:
            context['file_path'] = file_path
        if data_size:
            context['data_size'] = data_size

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate export-specific error code"""
        if self.export_format:
            return f"EXPORT_ERROR_{self.export_format.upper()}"
        return "EXPORT_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly export error message"""
        if self.export_format:
            return f"Failed to export data in {self.export_format} format. Please try again or use a different format."
        return "Export operation failed. Please try again or contact support."

    @classmethod
    def file_write_failed(cls, file_path: str, export_format: str = None) -> 'ExportError':
        """Create file write failed error"""
        return cls(
            message=f"Failed to write export file: {file_path}",
            export_format=export_format,
            file_path=file_path,
            user_message="Unable to save the export file. Please check file permissions and try again."
        )

    @classmethod
    def data_too_large(cls, data_size: int, max_size: int, export_format: str = None) -> 'ExportError':
        """Create data too large error"""
        return cls(
            message=f"Export data size {data_size} exceeds maximum {max_size}",
            export_format=export_format,
            data_size=data_size,
            user_message=f"The data is too large to export. Please filter your data or export in smaller chunks."
        )

    @classmethod
    def unsupported_format(cls, export_format: str) -> 'ExportError':
        """Create unsupported format error"""
        return cls(
            message=f"Unsupported export format: {export_format}",
            export_format=export_format,
            user_message=f"The format '{export_format}' is not supported. Please choose a different format."
        )


class SyncError(CalendarError):
    """Raised when calendar sync fails"""

    def __init__(self, message: str, sync_source: str = None, sync_destination: str = None,
                 sync_type: str = None, items_processed: int = None, **kwargs):
        """
        Initialize sync error

        Args:
            message: Error message
            sync_source: Source of the sync operation
            sync_destination: Destination of the sync operation
            sync_type: Type of sync (import, export, bidirectional)
            items_processed: Number of items processed before error
        """
        self.sync_source = sync_source
        self.sync_destination = sync_destination
        self.sync_type = sync_type
        self.items_processed = items_processed

        # Add sync-specific context
        context = kwargs.get('context', {})
        if sync_source:
            context['sync_source'] = sync_source
        if sync_destination:
            context['sync_destination'] = sync_destination
        if sync_type:
            context['sync_type'] = sync_type
        if items_processed is not None:
            context['items_processed'] = items_processed

        kwargs['context'] = context
        super().__init__(message, **kwargs)

    def _generate_error_code(self) -> str:
        """Generate sync-specific error code"""
        if self.sync_type:
            return f"SYNC_ERROR_{self.sync_type.upper()}"
        return "SYNC_ERROR_GENERAL"

    def _generate_user_message(self) -> str:
        """Generate user-friendly sync error message"""
        if self.sync_source and self.sync_destination:
            return f"Failed to sync calendar data from {self.sync_source} to {self.sync_destination}."
        return "Calendar synchronization failed. Please try again or contact support."

    @classmethod
    def connection_failed(cls, sync_source: str) -> 'SyncError':
        """Create sync connection failed error"""
        return cls(
            message=f"Failed to connect to sync source: {sync_source}",
            sync_source=sync_source,
            sync_type="import",
            user_message=f"Unable to connect to {sync_source}. Please check your connection and try again."
        )

    @classmethod
    def data_conflict(cls, conflicting_items: List[str], sync_source: str = None) -> 'SyncError':
        """Create data conflict error"""
        return cls(
            message=f"Data conflicts detected during sync: {', '.join(conflicting_items)}",
            sync_source=sync_source,
            sync_type="bidirectional",
            user_message="Conflicting data detected during sync. Please resolve conflicts manually."
        )

    @classmethod
    def partial_sync(cls, items_processed: int, total_items: int, sync_source: str = None) -> 'SyncError':
        """Create partial sync error"""
        return cls(
            message=f"Partial sync completed: {items_processed}/{total_items} items processed",
            sync_source=sync_source,
            items_processed=items_processed,
            user_message=f"Sync completed partially. {items_processed} of {total_items} items were processed."
        )


# Exception handler utility functions
class CalendarExceptionHandler:
    """Utility class for handling calendar exceptions"""

    @staticmethod
    def handle_exception(func):
        """Decorator to handle exceptions in calendar functions"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CalendarError:
                # Re-raise calendar errors as-is
                raise
            except Exception as e:
                # Wrap other exceptions in CalendarError
                raise CalendarError(
                    message=f"Unexpected error in {func.__name__}: {str(e)}",
                    original_exception=e,
                    context={'function': func.__name__, 'args': str(args)[:100], 'kwargs': str(kwargs)[:100]}
                )
        return wrapper

    @staticmethod
    def log_and_suppress(exception: CalendarError, default_return=None):
        """Log an exception and return a default value instead of raising"""
        exception_logger.warning(f"Suppressed exception: {exception}")
        return default_return

    @staticmethod
    def convert_to_user_error(exception: CalendarError) -> Dict[str, Any]:
        """Convert exception to user-friendly error response"""
        return {
            'error': True,
            'message': exception.user_message,
            'error_code': exception.error_code,
            'timestamp': exception.timestamp.isoformat()
        }
