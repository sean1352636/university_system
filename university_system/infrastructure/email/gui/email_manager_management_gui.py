"""
Email Manager Management GUI Wrapper

This module provides a simple wrapper around the main EmailManagerGUI for
convenience when opening it from other GUI components. It handles permission
checks and opens the email manager in a Toplevel window.

Note: This is a thin wrapper. For direct use, import EmailManagerGUI directly from:
university_system.modules.interfaces.gui.email_manager_gui
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading
import logging
from datetime import datetime, timedelta

# Import email manager GUI from canonical location
try:
    from university_system.infrastructure.email.gui.email_manager_gui import EmailManagerGUI
    EMAIL_MANAGER_GUI_AVAILABLE = True
except ImportError as e:
    print(f"Email Manager GUI module not available: {e}")
    EmailManagerGUI = None
    EMAIL_MANAGER_GUI_AVAILABLE = False

from university_system.infrastructure.auth.user_authentication import UserAuth

class EmailManagerManagementGUI:
    """
    Email Manager GUI wrapper for convenience.

    This class provides a simple interface to launch the EmailManagerGUI
    in a Toplevel window with appropriate permission checks.
    """

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

        # Initialize theme manager for dark mode support
        try:
            from university_system.modules.shared.gui.theme_config import get_theme_manager
            self.theme_manager = get_theme_manager()
            self.theme_manager.register_observer(self.on_theme_changed)
        except Exception as e:
            print(f"Warning: Could not initialize theme manager: {e}")
            self.theme_manager = None

    def on_theme_changed(self):
        """Handle theme changes"""
        if self.theme_manager:
            pass

    def show_email_manager(self):
        """Open the Communication/Email Manager GUI in a child window."""
        try:
            if not self.auth or not getattr(self.auth, 'current_user', None):
                messagebox.showerror("Communication", "You must be logged in.")
                return

            user_perms = self.auth.current_user.get('permissions', []) or []
            if not any(p in user_perms for p in ['send_emails', 'view_messages']):
                messagebox.showerror("Communication", "You don't have permission to access communication features.")
                return

            if not EMAIL_MANAGER_GUI_AVAILABLE:
                messagebox.showerror("Communication", "Email GUI not available")
                return

            top = tk.Toplevel(self.root)
            top.title("Communication & Email")
            top.geometry("1200x800")

            # Apply theme to window
            if self.theme_manager:
                self.theme_manager.apply_theme_to_window(top)

            try:
                top.transient(self.root)
                top.grab_set()
            except Exception:
                pass

            # Ensure 'Exit' or Ctrl+Q in the email GUI doesn't terminate the whole app
            try:
                top.quit = top.destroy
            except Exception:
                pass

            try:
                EmailManagerGUI(top, auth=self.auth)
                print("✅ Email/Communication GUI opened")
            except Exception as e:
                try:
                    top.destroy()
                except Exception:
                    pass
                messagebox.showerror("Communication", f"Failed to open Email GUI:\n{e}")

        except Exception as e:
            messagebox.showerror("Communication", f"Unexpected error:\n{e}")

    def compose_email(self, email_address):
        """Compose email to student"""
        messagebox.showinfo("Email", f"Email composition feature for {email_address}")