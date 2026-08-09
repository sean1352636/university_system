"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def update_status(self):
    """Update the status display and rebuild navigation for role-based UI"""
    if self.auth.current_user:
        user = self.auth.current_user
        self.current_user_var.set(f"{user['username']} ({user['role']})")
        self.status_var.set(_t("gui.logged_in"))
    else:
        self.current_user_var.set(_t("gui.not_logged_in"))
        self.status_var.set(_t("gui.not_logged_in"))

    # Rebuild navigation panel to show role-specific buttons
    self.rebuild_navigation_panel()
    self.update_login_logout_button()
