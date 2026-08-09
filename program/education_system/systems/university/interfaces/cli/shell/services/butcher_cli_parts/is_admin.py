"""Extracted function implementation."""

from .. import butcher_cli_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def is_admin() -> bool:
    """Check if current user is admin"""
    user = get_current_user()
    return user and user.get('role') in ['admin', 'staff']
