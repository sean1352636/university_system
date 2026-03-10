"""
Centralized context and auth management for all system modules.

This module provides a single source for authentication setup and
shared context management across different domains.

Thread Safety:
    All access to the global auth instance is protected by a threading.Lock
    to prevent race conditions in multi-threaded environments.

Security:
    Authentication MUST be explicitly initialized before use. There is no
    fallback or dummy authentication to prevent accidental privilege escalation.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth

# Thread-safe global auth instance
_auth_instance: Optional[UserAuth] = None
_auth_lock = threading.Lock()
_auth_initialized = False

logger = logging.getLogger(__name__)


class AuthenticationNotInitializedError(RuntimeError):
    """Raised when authentication system is accessed before initialization."""
    pass


def get_auth() -> UserAuth:
    """
    Get the current auth instance.

    Thread-safe: Uses double-checked locking pattern for efficiency.

    Raises:
        AuthenticationNotInitializedError: If initialize_auth() has not been called.

    Security Note:
        This function will NOT create a fallback/dummy auth instance.
        Authentication must be explicitly initialized to prevent security bypasses.
    """
    global _auth_instance
    # Fast path - no lock needed if already initialized
    if _auth_instance is not None:
        return _auth_instance

    # Slow path - acquire lock and check again
    with _auth_lock:
        if _auth_instance is None:
            logger.error(
                "SECURITY: Authentication system accessed before initialization! "
                "Call initialize_auth() or set_auth() before using get_auth()"
            )
            raise AuthenticationNotInitializedError(
                "Authentication system not initialized! "
                "Call initialize_auth() or set_auth() before using get_auth(). "
                "This is a security requirement - no fallback authentication is allowed."
            )
        return _auth_instance


def initialize_auth(db_path: Optional[str] = None) -> UserAuth:
    """
    Initialize the authentication system with a real auth instance.

    This MUST be called before any authentication operations.

    Args:
        db_path: Optional database path. If None, uses default from paths module.

    Returns:
        The initialized UserAuth instance.

    Thread-safe: Acquires lock before modifying global state.
    """
    global _auth_instance, _auth_initialized
    with _auth_lock:
        if _auth_instance is None:
            if db_path is None:
                from education_system.university_system.core import paths
                db_path = paths.DEFAULT_DB_PATH
            _auth_instance = UserAuth(db_path)
            _auth_initialized = True
            logger.info("Authentication system initialized successfully")
        return _auth_instance


def is_auth_initialized() -> bool:
    """
    Check if the authentication system has been initialized.

    Returns:
        True if auth is initialized, False otherwise.
    """
    return _auth_instance is not None


def set_auth(auth_instance: UserAuth) -> None:
    """
    Set the global auth instance for all modules.

    This is an alternative to initialize_auth() when you already have
    an auth instance (e.g., from dependency injection or testing).

    Args:
        auth_instance: A properly configured UserAuth instance.

    Thread-safe: Acquires lock before modifying global state.

    Raises:
        ValueError: If auth_instance is None.
    """
    global _auth_instance, _auth_initialized
    if auth_instance is None:
        raise ValueError(
            "Cannot set auth to None. Use a valid UserAuth instance. "
            "This prevents accidental authentication bypass."
        )
    with _auth_lock:
        _auth_instance = auth_instance
        _auth_initialized = True
        logger.info("Authentication instance set successfully")

    # Also set in the auth module if the helper exists
    try:
        from education_system.university_system.infrastructure.auth import set_auth_instance
        set_auth_instance(auth_instance)
    except ImportError:
        pass


def get_current_user():
    """Get the current authenticated user."""
    auth = get_auth()
    if hasattr(auth, 'current_user'):
        return auth.current_user
    return None


def check_permission(permission: str) -> bool:
    """Check if current user has a permission."""
    auth = get_auth()
    return auth.check_permission(permission)


def require_permission(permission: str):
    """Decorator to require a permission for a function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not check_permission(permission):
                raise PermissionError(f"Permission denied: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    'get_auth',
    'set_auth',
    'initialize_auth',
    'is_auth_initialized',
    'get_current_user',
    'check_permission',
    'require_permission',
    'AuthenticationNotInitializedError',
]
