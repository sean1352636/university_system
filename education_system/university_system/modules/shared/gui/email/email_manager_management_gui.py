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

# Import email manager GUI from modular package
try:
    from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
    EMAIL_MANAGER_GUI_AVAILABLE = True
except ImportError as e:
    print(f"Email Manager GUI module not available: {e}")
    EmailManagerGUI = None
    EMAIL_MANAGER_GUI_AVAILABLE = False

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.utils.i18n import get_text, _

class EmailManagerManagementGUI:
    """
    Email Manager GUI wrapper for convenience.

    This class provides a simple interface to launch the EmailManagerGUI
    in a Toplevel window with appropriate permission checks.
    """

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def show_email_manager(self):
        """Open the Communication/Email Manager GUI in a child window."""
        try:
            if not self.auth or not getattr(self.auth, 'current_user', None):
                messagebox.showerror(get_text("gui.email_manager.title"), get_text("gui.email_manager.login_required"))
                return

            user_perms = self.auth.current_user.get('permissions', []) or []
            if not any(p in user_perms for p in ['send_emails', 'view_messages']):
                messagebox.showerror(get_text("gui.email_manager.title"), get_text("gui.email_manager.no_permission"))
                return

            if not EMAIL_MANAGER_GUI_AVAILABLE:
                messagebox.showerror(get_text("gui.email_manager.title"), get_text("gui.email_manager.gui_unavailable"))
                return

            top = tk.Toplevel(self.root)
            top.title(get_text("gui.email_manager.window_title"))
            top.geometry("1400x900+%d+%d" % ((top.winfo_screenwidth() - 1400) // 2, (top.winfo_screenheight() - 900) // 2))
            top.minsize(1200, 800)

            # Configure window background
            top.configure(bg='#f0f0f0')

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
                print(get_text("gui.email_manager.opened_success"))
            except Exception as e:
                try:
                    top.destroy()
                except Exception:
                    pass
                messagebox.showerror(get_text("gui.email_manager.title"), get_text("gui.email_manager.open_failed", error=str(e)))

        except Exception as e:
            messagebox.showerror(get_text("gui.email_manager.title"), get_text("gui.email_manager.unexpected_error", error=str(e)))

    def compose_email(self, email_address):
        """Compose email to student"""
        messagebox.showinfo(get_text("gui.email_manager.email_title"), get_text("gui.email_manager.compose_feature", email=email_address))