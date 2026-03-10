import logging
from functools import wraps
from typing import Any, Callable, Optional, Dict
from tkinter import messagebox
from .exceptions import CalendarError, ValidationError, DatabaseError, AuthenticationError, PermissionError, ExportError, SyncError
from education_system.university_system.modules.shared.utils.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

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
            # Validate calendar event form data
            if not data.get('title'):
                raise ValidationError("Title is required")
            if not data.get('start_date'):
                raise ValidationError("Start date is required")
            return True
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
                    safe_show_error(_("common.error"), e.user_message)
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
                    safe_show_error(_("academic_calendar.errors.unexpected_error"), custom_error.user_message)
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
            # Track user actions for analytics (non-critical)
            # This might fail but shouldn't interrupt the main flow
            analytics_service = get_analytics_service()
            analytics_service.log_action(action)
            return True
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
                _("academic_calendar.errors.database_locked"),
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
                _("academic_calendar.errors.database_error"),
                operation="unknown",
                context=context
            )

    # Permission errors
    elif 'permission' in error_str or 'access denied' in error_str or error_type == 'PermissionError':
        return PermissionError(
            _("academic_calendar.errors.permission_denied"),
            context=context
        )

    # File/IO errors
    elif 'file' in error_str or error_type in ('IOError', 'OSError', 'FileNotFoundError'):
        if 'not found' in error_str or error_type == 'FileNotFoundError':
            return ExportError(
                _("academic_calendar.errors.file_not_found"),
                context=context
            )
        else:
            return ExportError(
                _("academic_calendar.errors.file_operation_error"),
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
            _("academic_calendar.errors.unexpected_error_with_details", error=str(error)),
            error_type=error_type,
            context=context
        )


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
            except Exception as e:
                gui_logger.debug(f"Failed to release grab: {e}")

        # Show error without grab to avoid conflicts
        messagebox.showerror(title, message)
    except Exception as e:
        # Fallback to logger if messagebox fails
        gui_logger.error("%s: %s", title, message)
        gui_logger.error("Failed to show error dialog: %s", e)


def safe_show_info(title, message, parent=None):
    """Safely show info message without grab conflicts"""
    try:
        if parent and hasattr(parent, 'grab_release'):
            try:
                parent.grab_release()
            except Exception as e:
                gui_logger.debug(f"Failed to release grab: {e}")
        messagebox.showinfo(title, message)
    except Exception as e:
        gui_logger.info("%s: %s", title, message)
        gui_logger.warning("Failed to show info dialog: %s", e)


def safe_show_warning(title, message, parent=None):
    """Safely show warning message without grab conflicts"""
    try:
        if parent and hasattr(parent, 'grab_release'):
            try:
                parent.grab_release()
            except Exception as e:
                gui_logger.debug(f"Failed to release grab: {e}")
        messagebox.showwarning(title, message)
    except Exception as e:
        gui_logger.warning("%s: %s", title, message)
        gui_logger.warning("Failed to show warning dialog: %s", e)


