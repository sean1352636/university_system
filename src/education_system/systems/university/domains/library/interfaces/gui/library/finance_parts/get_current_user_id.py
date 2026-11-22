"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_current_user_id():
    """Get current user ID"""
    if ORIGINAL_LIBRARY_AVAILABLE and 'auth' in globals() and auth and auth.current_user:
        return auth.current_user.get('user_id', 'unknown')
    return 'gui_user'
