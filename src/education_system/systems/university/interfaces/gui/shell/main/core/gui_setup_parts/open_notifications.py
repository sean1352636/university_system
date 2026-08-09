"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _open_notifications(self):
    """Open the Notifications Hub and immediately refresh the badge
    (the user is about to read them, so the count will drop)."""
    try:
        self.show_notifications_hub_gui()
    except Exception:
        logger.exception("Failed to open Notifications Hub from header bell")
    try:
        self._refresh_notification_badge()
    except Exception:
        pass
