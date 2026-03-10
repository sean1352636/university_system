"""
Notifications GUI Interface

DEPRECATED: The standalone Notifications Hub GUI has been integrated into the Email Manager.

For notifications functionality, please use:
    from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI

    # Then call email_gui.show_notifications_tab()

This module provides backward compatibility by redirecting to the Email Manager.
"""

import warnings

# Backward compatibility wrapper
class NotificationsGUI:
    """
    Backward compatibility wrapper for NotificationsGUI.

    This class is deprecated. Notifications are now integrated into the Email Manager GUI.
    Use EmailManagerGUI with the notifications tab instead.
    """

    def __init__(self, parent=None):
        warnings.warn(
            "NotificationsGUI is deprecated. Notifications are now integrated into the Email Manager. "
            "Use EmailManagerGUI with show_notifications_tab() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # Import here to avoid circular dependency
        from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
        import tkinter as tk
        from education_system.university_system.infrastructure.shared_context import get_auth

        # Create window
        if parent:
            self.window = tk.Toplevel(parent)
        else:
            self.window = tk.Tk()

        self.window.title("Communication Center - Notifications")
        self.window.geometry("1200x800")

        # Create email manager GUI
        auth = get_auth()
        self.email_gui = EmailManagerGUI(self.window, auth=auth)

        # Switch to notifications tab after a brief delay
        self.window.after(100, self._show_notifications)

    def _show_notifications(self):
        """Switch to notifications tab"""
        if hasattr(self.email_gui, 'show_notifications_tab'):
            self.email_gui.show_notifications_tab()

    def run(self):
        """Run the GUI application"""
        self.window.mainloop()


__all__ = ['NotificationsGUI']
