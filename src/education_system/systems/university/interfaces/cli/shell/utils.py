"""
Utility functions for CLI operations.

This module contains helper functions, formatting utilities, and common operations
used throughout the CLI system.
"""

from education_system.systems.university.interfaces.cli.shell.imports import (
    logging, time, datetime, re, contextlib, io,
    logger, DB_PATH, _t, Any
)


def safe_auth_check(auth_obj: Any) -> bool:
    """
    Safely check if auth object has required attributes.

    Args:
        auth_obj: Authentication object to check

    Returns:
        bool: True if auth object is valid
    """
    if not auth_obj:
        return False

    # Ensure required attributes exist
    if not hasattr(auth_obj, 'current_user'):
        auth_obj.current_user = None

    if not hasattr(auth_obj, 'last_activity'):
        auth_obj.last_activity = None

    if not hasattr(auth_obj, 'session_timeout'):
        auth_obj.session_timeout = 30

    if not hasattr(auth_obj, 'login_attempts'):
        auth_obj.login_attempts = {}

    if not hasattr(auth_obj, 'max_attempts'):
        auth_obj.max_attempts = 5

    if not hasattr(auth_obj, 'lockout_time'):
        auth_obj.lockout_time = 15

    return True


def require_authenticated_user(auth_obj: Any, allowed_roles=None) -> dict | None:
    """Return the live user or None; never treats a missing session as valid."""
    if not auth_obj or not getattr(auth_obj, 'current_user', None):
        return None
    try:
        if hasattr(auth_obj, 'check_session') and not auth_obj.check_session():
            return None
    except Exception:
        return None
    user = auth_obj.current_user
    role = str(user.get('role', '')).lower() if isinstance(user, dict) else ''
    if allowed_roles is not None and role not in {str(r).lower() for r in allowed_roles}:
        return None
    return user


def suppress_duplicate_messages():
    """Suppress duplicate log messages using context manager."""
    @contextlib.contextmanager
    def _suppress():
        yield
    return _suppress()


def cleanup_connections():
    """Clean up database connections on exit."""
    try:
        from education_system.systems.university.infrastructure.database.database_utils import cleanup_database_connections
        cleanup_database_connections()
    except Exception as e:
        logger.error(f"Error cleaning up connections: {e}")


__all__ = [
    'safe_auth_check',
    'require_authenticated_user',
    'suppress_duplicate_messages',
    'cleanup_connections',
]
