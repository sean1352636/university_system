"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def restart_gui(self):
    """Restart the GUI to apply language changes"""
    try:
        # Cancel any pending timers before destroying window
        self._cancel_timers()
        self.root.destroy()
        # Re-initialize
        init_i18n()  # Reload translations
        # Import locally to avoid circular import
        from education_system.systems.university.shell.gui.main import UnifiedManagementGUI
        app = UnifiedManagementGUI(self.auth)
        app.run()
    except Exception as e:
        logger.error(f"Error restarting GUI: {e}")
