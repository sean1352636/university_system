"""
Global Authentication Context

Provides thread-safe global access to the current authentication
instance and user information. This allows any module in the
application to access the current user context without explicit
parameter passing.

Features:
- Thread-safe global auth instance management
- Current user information retrieval
- Centralized auth context for the entire application

Part of the authentication module refactoring to separate global
state management from core authentication logic.
"""

import threading
from typing import Optional, Dict, Any

__all__ = [
    'get_current_user',
    'set_auth_instance',
    'get_auth_instance',
    'clear_auth_instance',
    'is_user_logged_in',
    'get_current_user_id',
    'get_current_username',
    'get_current_user_role',
    'get_global_auth',
    'set_global_auth',
    'reset_global_auth',
]

# Global variable to store the current auth instance with thread-safe access
_current_auth_instance = None
_auth_instance_lock = threading.Lock()


def get_current_user() -> Optional[Dict[str, Any]]:
    """
    Get the current logged-in user information from the global auth instance.

    Retrieves the currently authenticated user's information from the
    globally registered authentication instance. This is the primary
    way to access user context throughout the application.

    Returns
    -------
    dict or None
        User information dictionary containing user details if a user
        is logged in, including keys such as:
        - 'user_id': str - Unique identifier for the user
        - 'username': str - User's login name
        - 'role': str - User's role (admin, staff, student, instructor)
        - 'email': str - User's email address
        Returns None if no user is logged in or auth instance not set.

    Examples
    --------
    >>> user = get_current_user()
    >>> if user:
    ...     print(f"Logged in as: {user['username']}")
    ... else:
    ...     print("No user logged in")
    Logged in as: admin

    See Also
    --------
    set_auth_instance : Set the global auth instance.
    get_auth_instance : Retrieve the global auth instance.

    Notes
    -----
    This function is thread-safe and can be called from any thread.
    The returned dictionary should be treated as read-only to avoid
    concurrency issues.
    """
    with _auth_instance_lock:
        if _current_auth_instance and hasattr(_current_auth_instance, 'current_user'):
            return _current_auth_instance.current_user
        return None


def set_auth_instance(auth_instance) -> None:
    """
    Set the global authentication instance for the application.

    Registers an authentication instance globally so that other modules
    can access the current user context without passing the auth object
    explicitly. This should be called during application initialization.

    Thread-safe: Uses a lock to prevent race conditions when setting
    the global auth instance from multiple threads.

    Parameters
    ----------
    auth_instance : UserAuth
        The authentication instance to register globally. This instance
        manages user sessions and authentication state.

    Examples
    --------
    >>> from education_system.university_system.infrastructure.auth import (
    ...     UserAuth, set_auth_instance
    ... )
    >>> auth = UserAuth()
    >>> set_auth_instance(auth)
    >>> # Now other modules can use get_current_user()

    Notes
    -----
    Only one auth instance can be active at a time. Calling this function
    again will replace the previous instance. Typically called once at
    application startup in the main entry point.

    See Also
    --------
    get_current_user : Get the current logged-in user.
    get_auth_instance : Retrieve the global auth instance.
    """
    global _current_auth_instance
    with _auth_instance_lock:
        _current_auth_instance = auth_instance


def get_auth_instance():
    """
    Retrieve the global authentication instance.

    Provides thread-safe access to the globally registered authentication
    instance. This allows any module to access authentication functionality
    without explicit dependency injection.

    Returns
    -------
    UserAuth or None
        The global authentication instance if set, None otherwise

    Examples
    --------
    >>> auth = get_auth_instance()
    >>> if auth and auth.is_logged_in():
    ...     print("User is logged in")
    ... else:
    ...     print("No active session")

    Notes
    -----
    This function is thread-safe and can be called from any thread.
    Returns None if set_auth_instance() has not been called yet.

    See Also
    --------
    set_auth_instance : Set the global auth instance.
    get_current_user : Get the current logged-in user.
    """
    with _auth_instance_lock:
        return _current_auth_instance


def clear_auth_instance() -> None:
    """
    Clear the global authentication instance.

    Removes the global authentication instance, typically called during
    application shutdown or when switching authentication contexts.

    Thread-safe: Uses a lock to prevent race conditions.

    Examples
    --------
    >>> clear_auth_instance()
    >>> assert get_auth_instance() is None

    Notes
    -----
    This will effectively log out any active user from the global
    context perspective. Use with caution.
    """
    global _current_auth_instance
    with _auth_instance_lock:
        _current_auth_instance = None


def is_user_logged_in() -> bool:
    """
    Check if a user is currently logged in to the global auth instance.

    Convenience function that combines auth instance check and login
    status check.

    Returns
    -------
    bool
        True if a user is logged in, False otherwise

    Examples
    --------
    >>> if is_user_logged_in():
    ...     user = get_current_user()
    ...     print(f"Welcome back, {user['username']}!")
    ... else:
    ...     print("Please log in")

    See Also
    --------
    get_current_user : Get the current user information.
    get_auth_instance : Get the auth instance.
    """
    with _auth_instance_lock:
        if _current_auth_instance and hasattr(_current_auth_instance, 'is_logged_in'):
            return _current_auth_instance.is_logged_in()
        return False


def get_current_user_id() -> Optional[int]:
    """
    Get the current user's ID.

    Convenience function to extract just the user ID from the
    current user information.

    Returns
    -------
    int or None
        User ID if logged in, None otherwise

    Examples
    --------
    >>> user_id = get_current_user_id()
    >>> if user_id:
    ...     print(f"User ID: {user_id}")

    See Also
    --------
    get_current_user : Get full user information.
    """
    user = get_current_user()
    return user.get('id') if user else None


def get_current_username() -> Optional[str]:
    """
    Get the current user's username.

    Convenience function to extract just the username from the
    current user information.

    Returns
    -------
    str or None
        Username if logged in, None otherwise

    Examples
    --------
    >>> username = get_current_username()
    >>> if username:
    ...     print(f"Logged in as: {username}")

    See Also
    --------
    get_current_user : Get full user information.
    """
    user = get_current_user()
    return user.get('username') if user else None


def get_current_user_role() -> Optional[str]:
    """
    Get the current user's role.

    Convenience function to extract just the role from the
    current user information.

    Returns
    -------
    str or None
        User role if logged in, None otherwise

    Examples
    --------
    >>> role = get_current_user_role()
    >>> if role == 'admin':
    ...     print("You have admin privileges")

    See Also
    --------
    get_current_user : Get full user information.
    """
    user = get_current_user()
    return user.get('role') if user else None


# Alias variable for backward compatibility
_global_auth_instance = _current_auth_instance


def get_global_auth():
    """
    Get the global centralized auth instance.

    This is a convenience function that creates an auth instance
    if one doesn't exist. Useful for modules that need auth access
    without explicit initialization.

    Returns
    -------
    UserAuth or None
        The global auth instance, creating it if needed, or None if
        UserAuth cannot be imported (circular import protection)

    Examples
    --------
    >>> auth = get_global_auth()
    >>> if auth:
    ...     auth.login(username, password)

    See Also
    --------
    get_auth_instance : Get existing auth instance without creating
    set_global_auth : Set the global auth instance
    reset_global_auth : Clear the global auth instance

    Notes
    -----
    This ensures all modules use the same auth instance for consistent
    session management across the application. If called before any
    auth instance is set, it will attempt to create a new UserAuth
    instance automatically.
    """
    global _current_auth_instance, _global_auth_instance

    with _auth_instance_lock:
        if _current_auth_instance is None:
            # Try to create a new auth instance
            try:
                from education_system.university_system.infrastructure.auth.core import UserAuth
                _current_auth_instance = UserAuth()
                _global_auth_instance = _current_auth_instance
            except ImportError:
                # Avoid circular import issues
                pass

        _global_auth_instance = _current_auth_instance
        return _current_auth_instance


def set_global_auth(auth_instance):
    """
    Set the global auth instance.

    This is an alias for set_auth_instance() provided for backward
    compatibility with code that uses the 'global' naming convention.

    Parameters
    ----------
    auth_instance : UserAuth
        The authentication instance to register globally

    Examples
    --------
    >>> from education_system.university_system.infrastructure.auth import UserAuth
    >>> auth = UserAuth()
    >>> set_global_auth(auth)

    See Also
    --------
    set_auth_instance : The primary function for setting auth instance
    get_global_auth : Get the global auth instance
    """
    set_auth_instance(auth_instance)


def reset_global_auth():
    """
    Reset/clear the global auth instance.

    Removes the current global auth instance. The next call to
    get_global_auth() will create a new instance.

    Examples
    --------
    >>> reset_global_auth()
    >>> # Next get_global_auth() call will create new instance

    See Also
    --------
    clear_auth_instance : The primary function for clearing auth
    get_global_auth : Get the global auth instance
    set_global_auth : Set the global auth instance

    Notes
    -----
    This is useful for testing or when you need to completely
    reset the authentication state.
    """
    clear_auth_instance()
