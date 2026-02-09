import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class UserManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def load_users(self):
        """Load users into management interface"""
        if hasattr(self.gui, 'users_tree') and self.gui.users_tree is not None:
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id as user_id, username, role, email, created_at,
                       COALESCE(is_active, 1) as is_active
                FROM users
                ORDER BY username
                ''')
                users = cursor.fetchall()
                conn.close()

                # Clear existing items
                for item in self.gui.users_tree.get_children():
                    self.gui.users_tree.delete(item)

                # Insert new items
                for user in users:
                    user_id, username, role, email, created_at, is_active = user
                    active_text = "Yes" if is_active else "No"
                    self.gui.users_tree.insert('', 'end', values=(
                        user_id, username, role, email, created_at, active_text
                    ))
            except Exception as e:
                print(f"Error loading users: {e}")

    def add_user(self):
        """Add new user"""
        # Placeholder - would integrate with main_gui implementation
        messagebox.showinfo("Feature", "User management should be done from the main menu.")

    def edit_user(self):
        """Edit selected user"""
        # Placeholder - would integrate with main_gui implementation
        messagebox.showinfo("Feature", "User management should be done from the main menu.")

    def reset_user_password(self):
        """Reset user password"""
        if not hasattr(self.gui, 'users_tree'):
            messagebox.showerror("Error", "User list not available")
            return
        selection = self.gui.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to reset password")
            return
        # Placeholder - refer to main menu for full user management
        messagebox.showinfo("Feature", "Password reset should be done from the main menu for full functionality.")

    def deactivate_user(self):
        """Deactivate selected user"""
        if not hasattr(self.gui, 'users_tree'):
            messagebox.showerror("Error", "User list not available")
            return
        selection = self.gui.users_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a user to deactivate")
            return
        # Placeholder - refer to main menu for full user management
        messagebox.showinfo("Feature", "User deactivation should be done from the main menu.")

    def ensure_login(self, required_role=None):
        """
        Ensure user is logged in with optional role check

        Args:
            required_role: Required role (e.g., 'admin', 'staff') or None for any logged-in user

        Returns:
            bool: True if user is logged in (and has required role), False otherwise

        Raises:
            PermissionError: If role check fails
        """
        try:
            # Check if authenticated
            if not self.gui.check_authentication():
                messagebox.showerror("Authentication Required",
                                   "You must be logged in to perform this action.")
                return False

            # Check role if required
            if required_role:
                user_role = self.gui.current_user.get('role', '').lower()
                required_role_lower = required_role.lower()

                # Admin has access to everything
                if user_role == 'admin':
                    return True

                # Check specific role
                if user_role != required_role_lower:
                    messagebox.showerror("Permission Denied",
                                       f"This action requires '{required_role}' role.\n"
                                       f"Your role: '{user_role}'")
                    raise PermissionError(f"User role '{user_role}' does not have access "
                                        f"(required: '{required_role}')")

            # Log the access
            self.gui.log_event('access', 'system', details={
                'action': 'ensure_login',
                'required_role': required_role,
                'user_role': self.gui.current_user.get('role', 'unknown')
            })

            return True

        except PermissionError:
            raise
        except Exception as e:
            messagebox.showerror("Error", f"Authentication check failed: {e}")
            return False
