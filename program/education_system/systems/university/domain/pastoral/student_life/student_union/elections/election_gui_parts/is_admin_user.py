"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _is_admin_user(user):
    role = (user or {}).get('role', '').lower()
    return role in ('admin', 'superadmin', 'staff', 'instructor')
