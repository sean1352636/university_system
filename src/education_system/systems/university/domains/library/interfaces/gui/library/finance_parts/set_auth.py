"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def set_auth(auth_object):
    """Set global auth object for backwards compatibility"""
    global auth
    auth = auth_object
    # Also set it in the global auth instance if available
    if SHARED_AUTH_AVAILABLE:
        set_auth_instance(auth_object)
