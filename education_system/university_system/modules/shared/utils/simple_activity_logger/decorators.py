import time
import functools
import traceback
import logging

import psutil

from .models import LogLevel, SecurityLevel

_logger = logging.getLogger(__name__)


# Enhanced Decorators with full feature support
def enhanced_log_activity(action=None, module=None, description=None,
                         log_level=LogLevel.INFO, security_level=SecurityLevel.LOW,
                         metadata=None, measure_performance=True):
    """
    Enhanced decorator with performance measurement and rich metadata
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Import here to avoid circular imports with module_api
            from .module_api import logger

            start_time = time.time()

            # Get current user information (simplified - no auth imports)
            user_id = 'system'
            username = 'system'
            role = 'system'

            # Try to extract user info from function arguments if available
            if args and hasattr(args[0], '__dict__'):
                obj = args[0]
                if hasattr(obj, 'current_user'):
                    user = obj.current_user
                    user_id = getattr(user, 'id', 'system')
                    username = getattr(user, 'username', 'system')
                    role = getattr(user, 'role', 'system')

            # Determine the action, module, and details
            action_name = action or func.__name__
            module_name = module or func.__module__ or 'general'
            details = description or f"Executed {func.__name__}"

            # Prepare metadata
            func_metadata = metadata.copy() if metadata else {}
            func_metadata['function_name'] = func.__name__
            func_metadata['function_module'] = func.__module__

            if measure_performance:
                func_metadata['function_args_count'] = len(args) + len(kwargs)

            try:
                # Execute the original function
                result = func(*args, **kwargs)

                # Measure performance
                end_time = time.time()
                processing_time = end_time - start_time

                if measure_performance:
                    func_metadata['execution_time'] = processing_time
                    try:
                        func_metadata['memory_usage'] = psutil.Process().memory_info().rss
                    except (ImportError, OSError, AttributeError) as e:
                        _logger.debug(f"Failed to get memory usage: {e}")

                # Log successful execution
                logger.log_activity(
                    user_id, username, role, action_name, module_name,
                    details, "success", log_level, security_level, func_metadata,
                    processing_time=processing_time
                )

                return result

            except Exception as e:
                # Measure performance even for errors
                end_time = time.time()
                processing_time = end_time - start_time

                if measure_performance:
                    func_metadata['execution_time'] = processing_time
                    func_metadata['error_type'] = type(e).__name__

                # Log the error with stack trace
                error_details = f"Error in {func.__name__}: {str(e)}"
                func_metadata['stack_trace'] = traceback.format_exc()

                logger.log_activity(
                    user_id, username, role, f"{action_name}_error", module_name,
                    error_details, "failure", LogLevel.ERROR, SecurityLevel.MEDIUM,
                    func_metadata, processing_time=processing_time
                )
                raise

        return wrapper
    return decorator


# Specialized decorators for different operations
def log_create(module, description=None, **kwargs):
    """Enhanced decorator for create operations"""
    return enhanced_log_activity(
        action="create", module=module, description=description,
        security_level=SecurityLevel.MEDIUM, **kwargs
    )

def log_read(module, description=None, **kwargs):
    """Enhanced decorator for read operations"""
    return enhanced_log_activity(
        action="read", module=module, description=description,
        log_level=LogLevel.DEBUG, **kwargs
    )

def log_update(module, description=None, **kwargs):
    """Enhanced decorator for update operations"""
    return enhanced_log_activity(
        action="update", module=module, description=description,
        security_level=SecurityLevel.MEDIUM, **kwargs
    )

def log_delete(module, description=None, **kwargs):
    """Enhanced decorator for delete operations"""
    return enhanced_log_activity(
        action="delete", module=module, description=description,
        log_level=LogLevel.WARNING, security_level=SecurityLevel.HIGH, **kwargs
    )

def log_search(module, description=None, **kwargs):
    """Enhanced decorator for search operations"""
    return enhanced_log_activity(
        action="search", module=module, description=description, **kwargs
    )

def log_export(module, description=None, **kwargs):
    """Enhanced decorator for export operations"""
    return enhanced_log_activity(
        action="export", module=module, description=description,
        security_level=SecurityLevel.HIGH, **kwargs
    )

def log_admin_action(module, description=None, **kwargs):
    """Enhanced decorator for administrative operations"""
    return enhanced_log_activity(
        action="admin", module=module, description=description,
        log_level=LogLevel.WARNING, security_level=SecurityLevel.CRITICAL, **kwargs
    )

def log_menu_navigation(description=None, **kwargs):
    """Enhanced decorator for menu navigation operations"""
    return enhanced_log_activity(
        action="menu_navigation", module="navigation", description=description,
        log_level=LogLevel.DEBUG, **kwargs
    )
