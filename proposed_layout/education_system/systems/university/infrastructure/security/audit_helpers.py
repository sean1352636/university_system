"""
Audit Logging Helper Functions

Provides utility functions for safely logging security events to the
immutable audit log. These helpers handle exceptions gracefully to ensure
that audit logging failures never break application functionality.

Usage:
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        get_gui_context,
        get_api_context,
    )

    # Safe logging that never raises exceptions
    safe_log_security_event(
        action=AuditAction.LOGIN_SUCCESS,
        user_id='admin',
        resource_type='session',
        details={'username': 'admin'}
    )

    # Get context from GUI auth
    user_id, session_id = get_gui_context()

    # Get context from API request
    ip_address, user_agent = get_api_context(request)
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def safe_log_security_event(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """
    Safely log a security event to the immutable audit log.

    This wrapper function catches all exceptions to ensure that audit logging
    failures never break application functionality. The actual logging is
    still attempted, but failures are logged and suppressed.

    This is the recommended way to add audit logging to existing code paths
    where you don't want logging failures to affect user operations.

    Args:
        action: The audit action (use AuditAction constants)
        user_id: Identifier of the user performing the action
        resource_type: Type of resource being accessed (e.g., 'session', 'student', 'grade')
        resource_id: Identifier of the specific resource
        details: Additional details as a dictionary
        ip_address: Client IP address
        user_agent: Client user agent string
        session_id: Session identifier

    Returns:
        True if logging succeeded, False if it failed

    Example:
        >>> from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
        >>> safe_log_security_event(
        ...     action=AuditAction.LOGIN_SUCCESS,
        ...     user_id='admin',
        ...     resource_type='session',
        ...     details={'username': 'admin', 'role': 'admin'}
        ... )
        True
    """
    try:
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            log_security_event,
        )

        log_security_event(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
        )
        return True

    except ImportError as e:
        logger.warning(f"Immutable audit log not available: {e}")
        return False
    except Exception as e:
        # Log the failure but don't raise - audit logging should never break app
        logger.error(f"Failed to log security event ({action}): {e}")
        return False


def get_gui_context() -> Tuple[Optional[str], Optional[str]]:
    """
    Extract user context from the GUI authentication system.

    Retrieves the current user ID and session information from the
    global authentication context used by the GUI.

    Returns:
        Tuple of (user_id, session_id). Either or both may be None
        if no user is logged in or context is unavailable.

    Example:
        >>> user_id, session_id = get_gui_context()
        >>> if user_id:
        ...     safe_log_security_event(
        ...         action=AuditAction.DATA_VIEW,
        ...         user_id=user_id,
        ...         session_id=session_id,
        ...         resource_type='student_records'
        ...     )
    """
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth

        auth = get_auth()
        if auth and auth.is_logged_in():
            current_user = auth.get_current_user()
            if current_user:
                user_id = str(current_user.get('id', ''))
                session_id = current_user.get('session_id')
                return user_id, session_id
        return None, None

    except ImportError:
        logger.debug("Shared context not available for GUI context")
        return None, None
    except Exception as e:
        logger.debug(f"Could not get GUI context: {e}")
        return None, None


def get_api_context(request: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract context information from an API request.

    Retrieves the client IP address and user agent from a Flask or
    similar HTTP request object.

    Args:
        request: Flask request object (or similar with remote_addr and headers)

    Returns:
        Tuple of (ip_address, user_agent). Either or both may be None
        if the information is not available.

    Example:
        >>> from flask import request
        >>> ip_address, user_agent = get_api_context(request)
        >>> safe_log_security_event(
        ...     action=AuditAction.LOGIN_SUCCESS,
        ...     user_id=user_id,
        ...     ip_address=ip_address,
        ...     user_agent=user_agent
        ... )
    """
    try:
        ip_address = None
        user_agent = None

        # Try to get IP address
        if hasattr(request, 'remote_addr'):
            ip_address = request.remote_addr

        # Check for forwarded headers (reverse proxy)
        if hasattr(request, 'headers'):
            # X-Forwarded-For header (first IP is the client)
            forwarded_for = request.headers.get('X-Forwarded-For')
            if forwarded_for:
                ip_address = forwarded_for.split(',')[0].strip()

            # X-Real-IP header (nginx)
            real_ip = request.headers.get('X-Real-IP')
            if real_ip and not forwarded_for:
                ip_address = real_ip

            # User agent
            user_agent = request.headers.get('User-Agent')

        return ip_address, user_agent

    except Exception as e:
        logger.debug(f"Could not get API context: {e}")
        return None, None


def get_current_user_id() -> Optional[str]:
    """
    Get the current user ID from available context.

    Tries to get the user ID from:
    1. GUI authentication context
    2. Flask g object (for API requests)

    Returns:
        User ID string or None if not available
    """
    try:
        # Try GUI context first
        user_id, _ = get_gui_context()
        if user_id:
            return user_id

        # Try Flask g object
        try:
            from flask import g
            if hasattr(g, 'current_user') and g.current_user:
                return str(g.current_user.get('id', ''))
        except (ImportError, RuntimeError):
            pass

        return None

    except Exception:
        return None


def mask_sensitive_data(data: Dict[str, Any], fields_to_mask: tuple = ('password', 'token', 'secret', 'key')) -> Dict[str, Any]:
    """
    Mask sensitive fields in a dictionary for safe logging.

    Args:
        data: Dictionary containing data to log
        fields_to_mask: Tuple of field names to mask (case-insensitive partial match)

    Returns:
        New dictionary with sensitive fields masked as '***'

    Example:
        >>> data = {'username': 'admin', 'password': 'secret123'}
        >>> mask_sensitive_data(data)
        {'username': 'admin', 'password': '***'}
    """
    if not data:
        return data

    masked = {}
    for key, value in data.items():
        key_lower = key.lower()
        should_mask = any(field in key_lower for field in fields_to_mask)
        masked[key] = '***' if should_mask else value

    return masked


__all__ = [
    'safe_log_security_event',
    'get_gui_context',
    'get_api_context',
    'get_current_user_id',
    'mask_sensitive_data',
]
