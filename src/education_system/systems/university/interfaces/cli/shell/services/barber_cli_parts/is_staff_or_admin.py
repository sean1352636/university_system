"""Extracted function implementation."""

from .. import barber_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def is_staff_or_admin():
    """Check if current user is staff or admin"""
    try:
        user = get_current_user()
        if user and user.get('role') in ['admin', 'staff', 'Admin', 'Staff']:
            return True
    except Exception as e:
        logger.error(f"Error checking user role: {e}")
    return False
