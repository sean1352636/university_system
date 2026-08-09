"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _deferred_navigation_rebuild(self):
    """Rebuild navigation panel after GUI has rendered (non-blocking)"""
    try:
        self.rebuild_navigation_panel()

        # Update status to "Logged in" after navigation is ready
        if self.auth.current_user:
            self.status_var.set(_t("gui.logged_in"))
    except Exception as e:
        logger.error(f"Error rebuilding navigation panel: {e}")
        if self.auth.current_user:
            self.status_var.set(_t("gui.logged_in"))
