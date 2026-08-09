"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def show_main_interface(self):
    """Show main interface when authenticated"""
    # Update status variables immediately
    if self.auth.current_user:
        user = self.auth.current_user
        self.current_user_var.set(f"{user['username']} ({user['role']})")
        self.status_var.set(_t("gui.loading_menu"))  # Show loading message
    else:
        self.current_user_var.set(_t("gui.not_logged_in"))
        self.status_var.set(_t("gui.not_logged_in"))

    self.update_login_logout_button()

    # Show role-based dashboard immediately on login
    self.show_integrated_dashboard()

    # Defer navigation panel rebuild to allow GUI to respond
    # This prevents the freeze during login
    self.root.after(50, self._deferred_navigation_rebuild)
