"""
Centralized context and auth management for all system modules.

This module provides a single source for authentication setup and
shared context management across different domains.
"""

from __future__ import annotations

import logging
from typing import Optional

from university_system.infrastructure.auth.user_authentication import UserAuth

# Global auth instance
_auth_instance: Optional[UserAuth] = None

# Dummy auth for fallback
class _DummyAuth(UserAuth):
    """Fallback auth when no real auth is configured."""
    current_user = {"username": "admin", "permissions": ["*"]}

    def check_permission(self, permission: str) -> bool:  # type: ignore[override]
        return True


def get_auth() -> UserAuth:
    """Get the current auth instance, creating dummy if needed."""
    global _auth_instance
    if _auth_instance is None:
        logging.warning("No auth instance configured, using dummy auth")
        _auth_instance = _DummyAuth()
    return _auth_instance


def set_auth(auth_instance: UserAuth) -> None:
    """Set the global auth instance for all modules."""
    global _auth_instance
    _auth_instance = auth_instance

    # Also set in the auth module if the helper exists
    try:
        from university_system.infrastructure.auth.user_authentication import set_auth_instance
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
    'get_current_user',
    'check_permission',
    'require_permission',
]
