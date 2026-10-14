"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _get_current_user_id(auth):
    """Extract the current user identifier from the auth manager."""
    try:
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user.get('id') or auth.current_user.get('user_id') or 'unknown'
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return 'unknown'
