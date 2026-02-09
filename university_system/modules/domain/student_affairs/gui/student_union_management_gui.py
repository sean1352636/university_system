import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import threading
import logging
from datetime import datetime, timedelta

# Import student union modules (from student_union_gui package)
try:
    from university_system.modules.domain.student_affairs.gui.student_union_gui import StudentUnionGUI
    STUDENT_UNION_GUI_AVAILABLE = True
except ImportError as e:
    print(get_text("student_affairs.union_management.gui_not_available", error=str(e)))
    StudentUnionGUI = None
    STUDENT_UNION_GUI_AVAILABLE = False
    STUDENT_UNION_GUI_IMPORT_ERROR = str(e)

# Import CLI fallback
try:
    from university_system.modules.domain.student_affairs.student_union import display_student_union_menu
except ImportError:
    def display_student_union_menu():
        print(get_text("student_affairs.union_management.cli_not_available"))

# Import shared constants
try:
    from university_system.modules.shared.constants.paths import PROJECT_ROOT, DEFAULT_DB_PATH
except ImportError:
    # Fallback: import from paths module
    from university_system.modules.shared.constants import paths
    PROJECT_ROOT = paths.PROJECT_ROOT
    DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

from university_system.infrastructure.auth import UserAuth
from university_system.modules.shared.utils.i18n import get_text, _

class StudentUnionManagementGUI:
    """Student Union management GUI wrapper"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def show_student_union_portal(self):
        """Wrapper method to maintain compatibility with navigation buttons"""
        self.open_student_union_portal_gui()

    def open_student_union_portal_gui(self):
        """Open the Student Union GUI in a child window with proper integration"""
        try:
            if not getattr(self.auth, "current_user", None):
                messagebox.showerror(get_text("student_affairs.union_management.title"), get_text("student_affairs.union_management.login_required"))
                return

            if not STUDENT_UNION_GUI_AVAILABLE:
                msg = get_text("student_affairs.union_management.gui_unavailable")
                if 'STUDENT_UNION_GUI_IMPORT_ERROR' in globals():
                    msg += f"\n{STUDENT_UNION_GUI_IMPORT_ERROR}"
                messagebox.showerror(get_text("student_affairs.union_management.title"), msg)
                return

            # Create a new window for the Student Union GUI
            union_window = tk.Toplevel(self.root)
            union_window.title(get_text("student_affairs.union_management.window_title"))
            union_window.geometry("1400x900")
            union_window.minsize(1200, 800)

            # Configure window background
            union_window.configure(bg='#f0f0f0')

            # Center the window
            union_window.update_idletasks()
            x = (union_window.winfo_screenwidth() - union_window.winfo_width()) // 2
            y = (union_window.winfo_screenheight() - union_window.winfo_height()) // 2
            union_window.geometry(f"+{x}+{y}")

            try:
                union_window.transient(self.root)
            except Exception:
                pass  # Continue if transient fails

            # Initialize the Student Union GUI in the new window
            union_gui = StudentUnionGUI(parent=union_window)

            # Check if initialization was successful
            if not union_gui.initialized:
                # Initialization incomplete - need to set auth manually

                # Set up the correct database path - use main student_records.db
                union_gui.db_path = str(DEFAULT_DB_PATH)

                # Pass authentication context
                union_gui.auth_manager = self.auth

                # Set current user from auth
                if self.auth.current_user:
                    union_gui.current_user = {
                        'id': self.auth.current_user.get('id'),
                        'username': self.auth.current_user.get('username'),
                        'email': self.auth.current_user.get('email', ''),
                        'role': self.auth.current_user.get('role', 'student')
                    }

                # Now setup GUI with auth in place
                union_gui.setup_gui()
                union_gui.setup_database()

                # Mark as successfully initialized
                union_gui.initialized = True

                # Show the main dashboard
                union_gui.show_main_dashboard()
            else:
                # Already initialized successfully - just show dashboard
                union_gui.show_main_dashboard()

            print(get_text("student_affairs.union_management.opened_success"))

        except Exception as e:
            messagebox.showerror(get_text("student_affairs.union_management.title"), get_text("student_affairs.union_management.open_failed", error=str(e)))
            print(get_text("student_affairs.union_management.error", error=str(e)))

            # Fallback to CLI menu if GUI fails
            try:
                display_student_union_menu()
            except ImportError:
                messagebox.showerror(get_text("common.error"), get_text("student_affairs.union_management.neither_available"))