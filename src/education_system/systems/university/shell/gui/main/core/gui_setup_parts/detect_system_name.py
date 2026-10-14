"""Extracted function implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _detect_system_name(self):
    """Best-effort: pull the human-readable system name from auth or
    from ``modules.services``'s package metadata. Returns ``""`` if
    we can't figure it out — status bar tolerates an empty
    right-region gracefully."""
    try:
        if getattr(self, 'auth', None) and getattr(self.auth, 'current_user', None):
            sys_key = self.auth.current_user.get('system') or self.auth.current_user.get('subsystem')
            if sys_key:
                return str(sys_key).title()
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    return "University"  # the dominant subsystem this GUI is built for
