"""
Authentication and authorization helpers for the Student Support module.

This module provides functions for managing authentication state and checking
permissions for support operations.
"""

import logging

# Import auth instance management from user_authentication
try:
    from education_system.post_18.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None

# Global auth instance
auth = None

# Logger
logger = logging.getLogger(__name__)


def set_auth(auth_instance):
    """
    Set the authentication instance for the student support module.

    Registers the authentication instance both locally in this module and
    globally (if available) so that support operations can access user
    context for authorization and audit logging.

    Parameters
    ----------
    auth_instance : UserAuth
        The authentication instance to register. This instance manages
        user sessions and provides current user context.

    Examples
    --------
    >>> from education_system.post_18.university_system.infrastructure.auth import UserAuth
    >>> auth = UserAuth()
    >>> auth.login("admin", "password")
    >>> set_auth(auth)
    >>> # Now support operations can access user context

    Notes
    -----
    This should be called during application initialization after the user
    has logged in. Support operations require authentication for:
    - Creating and managing support tickets
    - Assigning staff to tickets
    - Audit trail logging

    See Also
    --------
    set_auth_instance : Global auth instance setter.
    get_current_user : Get the current logged-in user.
    """
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
    logger.info("Auth instance set for student support module")


def get_auth_instance():
    """
    Get the current authentication instance.

    Returns
    -------
    UserAuth or None
        The current auth instance, or None if not set.
    """
    return auth


def get_current_user_safe():
    """
    Safely get the current user without raising exceptions.

    Returns
    -------
    dict or None
        Current user data, or None if not authenticated.
    """
    if auth and hasattr(auth, 'current_user'):
        return auth.current_user
    return None


def require_auth():
    """
    Check if user is authenticated.

    Raises
    ------
    PermissionError
        If user is not authenticated.
    """
    if not auth or not auth.current_user:
        raise PermissionError("You must be logged in to perform this action")


def require_role(allowed_roles):
    """
    Check if user has one of the allowed roles.

    Parameters
    ----------
    allowed_roles : list
        List of allowed role names.

    Raises
    ------
    PermissionError
        If user doesn't have an allowed role.
    """
    require_auth()
    current_role = auth.current_user.get('role')
    if current_role not in allowed_roles:
        raise PermissionError(f"This action requires one of these roles: {', '.join(allowed_roles)}")


def check_ticket_ownership(ticket_student_id):
    """
    Check if current user owns a ticket.

    Parameters
    ----------
    ticket_student_id : str
        The student_id associated with the ticket.

    Returns
    -------
    bool
        True if user owns the ticket or has staff permissions.
    """
    if not auth or not auth.current_user:
        return False

    # Staff and admin can access all tickets
    role = auth.current_user.get('role', '')
    if role in ['admin', 'staff', 'instructor']:
        return True

    # Students can only access their own tickets
    if role == 'student':
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            if result:
                return result[0] == ticket_student_id
        except Exception as e:
            logger.error(f"Error checking ticket ownership: {e}")
            return False

    return False


def has_staff_permissions():
    """
    Check if current user has staff-level permissions.

    Returns
    -------
    bool
        True if user is admin, staff, or instructor.
    """
    if not auth or not auth.current_user:
        return False
    return auth.current_user.get('role', '') in ['admin', 'staff', 'instructor']
