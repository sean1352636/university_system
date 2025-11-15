import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import threading
import logging
from datetime import datetime, timedelta

# Import student union modules
try:
    from university_system.modules.domain.student_affairs.gui.student_union_gui import StudentUnionGUI
    STUDENT_UNION_GUI_AVAILABLE = True
except ImportError as e:
    print(f"Student Union GUI module not available: {e}")
    StudentUnionGUI = None
    STUDENT_UNION_GUI_AVAILABLE = False
    STUDENT_UNION_GUI_IMPORT_ERROR = str(e)

# Import CLI fallback
try:
    from university_system.modules.domain.student_affairs.student_union import display_student_union_menu
except ImportError:
    def display_student_union_menu():
        print("Student Union CLI menu not available")

# Import shared constants
try:
    from university_system.modules.shared.constants.paths import PROJECT_ROOT, DEFAULT_DB_PATH
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "data", "db_files", "student_records.db")

from university_system.infrastructure.auth.user_authentication import UserAuth

class StudentUnionManagementGUI:
    """Student Union management GUI wrapper"""

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

    def show_student_union_portal(self):
        """Wrapper method to maintain compatibility with navigation buttons"""
        self.open_student_union_portal_gui()

    def open_student_union_portal_gui(self):
        """Open the Student Union GUI in a child window with proper integration"""
        try:
            if not getattr(self.auth, "current_user", None):
                messagebox.showerror("Student Union", "You must be logged in to access the Student Union Portal.")
                return

            if not STUDENT_UNION_GUI_AVAILABLE:
                msg = "Student Union GUI not available."
                if 'STUDENT_UNION_GUI_IMPORT_ERROR' in globals():
                    msg += f"\n{STUDENT_UNION_GUI_IMPORT_ERROR}"
                messagebox.showerror("Student Union", msg)
                return

            # Create a new window for the Student Union GUI
            union_window = tk.Toplevel(self.root)
            union_window.title("Student Union Portal - Management System")
            union_window.geometry("1400x900")
            union_window.minsize(1200, 800)

            # Apply theme to window
            if self.theme_manager:
                self.theme_manager.apply_theme_to_window(union_window)

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

            print("Student Union GUI opened successfully as child window")

        except Exception as e:
            messagebox.showerror("Student Union", f"Failed to open Student Union GUI:\n{e}")
            print(f"Student Union GUI error: {e}")

            # Fallback to CLI menu if GUI fails
            try:
                display_student_union_menu()
            except ImportError:
                messagebox.showerror("Error", "Neither GUI nor CLI Student Union system is available.")