"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _notification_user_id(self):
    """Resolve the current user's notification key. Notifications may be
    keyed by username or numeric id depending on the seeding path, so the
    caller tries both. Returns a list of candidate id strings (possibly
    empty when nobody is logged in)."""
    cu = getattr(self.auth, 'current_user', None) if getattr(self, 'auth', None) else None
    if not cu:
        return []
    candidates = []
    for key in ('username', 'id', 'user_id'):
        val = cu.get(key)
        if val is not None and str(val) not in candidates:
            candidates.append(str(val))
    return candidates
