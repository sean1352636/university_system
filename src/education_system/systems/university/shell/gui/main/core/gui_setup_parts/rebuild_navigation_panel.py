"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def rebuild_navigation_panel(self):
    """Rebuild the navigation panel based on current user role"""
    if hasattr(self, 'nav_parent') and self.nav_parent:
        try:
            # Force GUI update before starting rebuild
            self.root.update_idletasks()

            self.create_navigation_panel(self.nav_parent)

            # Force another GUI update after rebuild completes
            self.root.update_idletasks()

            logger.debug(f"Navigation panel rebuilt for role: {self.auth.current_user.get('role') if self.auth and self.auth.current_user else 'Not logged in'}")
        except Exception as e:
            logger.error(f"Failed to rebuild navigation panel: {e}")
