import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from education_system.post_18.university_system.core import paths

# Import i18n for language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    from education_system.post_18.university_system.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this module when targeting the
# student_records.db database. Many functions within this GUI refer to
# str(DEFAULT_DB_PATH) without specifying a full path. Without this
# override, a new database would be created in the current working
# directory, leading to multiple database files and missing tables. The
# override redirects connections to the shared student_records.db in
# university_system/data/db_files. If a different database name/path is
# supplied, the connection falls back to the original behaviour.

_original_sqlite3_connect = sqlite3.connect  # preserve original

def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect

# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action, set_auth,
        # Display functions
        display_support_menu, display_enhanced_faqs, display_enhanced_resources,
        # Ticket management functions
        view_my_tickets_enhanced, view_all_tickets_enhanced,
        create_enhanced_ticket, display_ticket_details_enhanced,
        # Admin functions
        manage_templates_menu, manage_knowledge_base_menu, show_template_statistics,
        # Helper functions
        format_ticket_status_display, format_priority_display, format_file_size,
        truncate_text, handle_support_error, validate_ticket_permissions
    )

    # Auth handling - auth is now managed differently in the new structure
    auth = None  # Will be set via set_auth_instance()

except ImportError:
    # Backwards compatibility - if module structure changes or imports fail
    try:
        from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu, set_auth
        )
        auth = None
    except ImportError:
        # If even the fallback import fails, define minimal stubs
        auth = None
        SUPPORT_CATEGORIES = []
        TICKET_PRIORITIES = []
        TICKET_STATUSES = []
        EnhancedStudentSupport = None
        SupportConfig = None
        display_support_menu = None

    # Define fallback functions if not available
    display_enhanced_faqs = None
    display_enhanced_resources = None
    view_my_tickets_enhanced = None
    view_all_tickets_enhanced = None
    create_enhanced_ticket = None
    display_ticket_details_enhanced = None
    manage_templates_menu = None
    manage_knowledge_base_menu = None
    show_template_statistics = None

    # Define fallback enum types
    from enum import Enum
    class NotificationType(str, Enum):
        INFO = 'info'
        WARNING = 'warning'
        ERROR = 'error'

    class TicketSentiment(str, Enum):
        POSITIVE = 'positive'
        NEUTRAL = 'neutral'
        NEGATIVE = 'negative'

    class FileType(str, Enum):
        IMAGE = 'image'
        DOCUMENT = 'document'
        OTHER = 'other'

    # Define fallback helper functions
    setup_enhanced_logging = lambda: None
    audit_action = lambda *args, **kwargs: None
    set_auth = lambda x: None  # Fallback if set_auth not available
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None

class ReportsExportMixin:
    def show_export_dialog(self):
        """Show data export dialog with advanced filters"""
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("📤 Export Data")
        export_dialog.geometry("1200x800")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        # Scrollable frame
        canvas = tk.Canvas(export_dialog)
        scrollbar = ttk.Scrollbar(export_dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding="20")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        ttk.Label(scrollable_frame, text="📤 Export Data", style='Heading.TLabel').pack(pady=(0, 20))

        # Export type
        ttk.Label(scrollable_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar(value="tickets")

        export_options = [
            ("🎫 Tickets", "tickets"),
            ("💬 Responses", "responses"),
            ("📊 Metrics", "metrics")
        ]

        for text, value in export_options:
            ttk.Radiobutton(scrollable_frame, text=text, variable=export_type_var,
                           value=value).pack(anchor="w", pady=2)

        # Filters Section
        filters_frame = ttk.LabelFrame(scrollable_frame, text="Filters (Optional)", padding="10")
        filters_frame.pack(fill="x", pady=(20, 10))

        # Date Range Filters
        ttk.Label(filters_frame, text="Date From (YYYY-MM-DD):").pack(anchor="w")
        date_from_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=date_from_var, width=40).pack(fill="x", pady=(5, 10))

        ttk.Label(filters_frame, text="Date To (YYYY-MM-DD):").pack(anchor="w")
        date_to_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=date_to_var, width=40).pack(fill="x", pady=(5, 10))

        # Status Filter (for tickets)
        ttk.Label(filters_frame, text="Status (for tickets):").pack(anchor="w")
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(filters_frame, textvariable=status_var,
                                    values=['All'] + TICKET_STATUSES, state="readonly", width=37)
        status_combo.set('All')
        status_combo.pack(fill="x", pady=(5, 10))

        # Category Filter (for tickets)
        ttk.Label(filters_frame, text="Category (for tickets):").pack(anchor="w")
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(filters_frame, textvariable=category_var,
                                      values=['All'] + SUPPORT_CATEGORIES, state="readonly", width=37)
        category_combo.set('All')
        category_combo.pack(fill="x", pady=(5, 10))

        # Priority Filter (for tickets)
        ttk.Label(filters_frame, text="Priority (for tickets):").pack(anchor="w")
        priority_var = tk.StringVar()
        priority_combo = ttk.Combobox(filters_frame, textvariable=priority_var,
                                      values=['All'] + TICKET_PRIORITIES, state="readonly", width=37)
        priority_combo.set('All')
        priority_combo.pack(fill="x", pady=(5, 10))

        # Format
        ttk.Label(scrollable_frame, text="Format:").pack(anchor="w", pady=(10, 5))
        format_var = tk.StringVar(value="csv")

        format_frame = ttk.Frame(scrollable_frame)
        format_frame.pack(anchor="w")

        ttk.Radiobutton(format_frame, text="CSV", variable=format_var,
                       value="csv").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(format_frame, text="JSON", variable=format_var,
                       value="json").pack(side="left")

        # Buttons
        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        def start_export():
            export_type = export_type_var.get()
            format_type = format_var.get()

            # Build filters
            filters = {}

            date_from = date_from_var.get().strip()
            if date_from:
                filters['date_from'] = date_from

            date_to = date_to_var.get().strip()
            if date_to:
                filters['date_to'] = date_to

            status = status_var.get()
            if status and status != 'All':
                filters['status'] = status

            category = category_var.get()
            if category and category != 'All':
                filters['category'] = category

            priority = priority_var.get()
            if priority and priority != 'All':
                filters['priority'] = priority

            export_dialog.destroy()
            self.perform_export(export_type, format_type, filters)

        ttk.Button(btn_frame, text="📤 Export", command=start_export,
                  style='Primary.TButton').pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=export_dialog.destroy).pack(side="left")

        # Pack canvas and scrollbar
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def perform_export(self, export_type, format_type, filters=None):
        """Perform data export with optional filters"""
        try:
            # Get filename
            filename = filedialog.asksaveasfilename(
                title="Save Export",
                defaultextension=f".{format_type}",
                filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
            )

            if not filename:
                return

            self.update_status(f"Exporting {export_type} data...")

            # Export data with filters
            exported_data = self.support.export_data(export_type, filters or {}, format_type)

            with open(filename, 'w') as f:
                f.write(exported_data)

            filter_info = f" with {len(filters)} filter(s)" if filters else ""
            messagebox.showinfo("Export Complete", f"Data exported to {filename}{filter_info}")
            self.update_status("Export completed")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")
            self.update_status("Export failed")

    def refresh_data(self):
        """Refresh all data"""
        try:
            self.update_status("Refreshing data...")

            # Reload dashboard data
            self.load_dashboard()

            # Refresh current view
            current_tab = self.notebook.tab(self.notebook.select(), "text")

            if "Dashboard" in current_tab:
                self.show_dashboard()
            elif "My Tickets" in current_tab:
                if hasattr(self, 'refresh_my_tickets'):
                    self.refresh_my_tickets()
            elif "All Tickets" in current_tab:
                if hasattr(self, 'refresh_all_tickets'):
                    self.refresh_all_tickets()
            elif "FAQs" in current_tab:
                if hasattr(self, 'load_faqs'):
                    self.load_faqs()
            elif "Knowledge Base" in current_tab:
                if hasattr(self, 'load_knowledge_base'):
                    self.load_knowledge_base()
            elif "Notifications" in current_tab:
                if hasattr(self, 'load_notifications'):
                    self.load_notifications()

            self.update_status("Data refreshed")

        except Exception as e:
            self.update_status(f"Refresh failed: {e}")

    def show_export_data_dialog(self):
        """Show enhanced data export dialog"""
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            messagebox.showerror("Error", "Staff access required")
            return

        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("Export Data")
        export_dialog.geometry("1300x800")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        form_frame = ttk.Frame(export_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Export Data", style='Title.TLabel').pack(pady=(0, 20))

        # Export type
        ttk.Label(form_frame, text="Export Type:").pack(anchor="w")
        export_type_var = tk.StringVar(value="tickets")

        export_options = [
            ("Tickets", "tickets"),
            ("Responses", "responses"),
            ("Metrics", "metrics"),
            ("User Data", "users"),
            ("System Logs", "logs")
        ]

        for text, value in export_options:
            ttk.Radiobutton(form_frame, text=text, variable=export_type_var,
                           value=value).pack(anchor="w", pady=2)

        # Date range
        date_frame = ttk.LabelFrame(form_frame, text="Date Range (Optional)", padding="10")
        date_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(date_frame, text="From:").grid(row=0, column=0, sticky="w")
        from_date = ttk.Entry(date_frame, width=12)
        from_date.grid(row=0, column=1, padx=(5, 10))
        from_date.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

        ttk.Label(date_frame, text="To:").grid(row=0, column=2, sticky="w")
        to_date = ttk.Entry(date_frame, width=12)
        to_date.grid(row=0, column=3, padx=(5, 0))
        to_date.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Format
        format_frame = ttk.LabelFrame(form_frame, text="Format", padding="10")
        format_frame.pack(fill="x", pady=(10, 0))

        format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV", variable=format_var, value="csv").pack(side="left")
        ttk.Radiobutton(format_frame, text="JSON", variable=format_var, value="json").pack(side="left", padx=(10, 0))
        ttk.Radiobutton(format_frame, text="Excel", variable=format_var, value="xlsx").pack(side="left", padx=(10, 0))

        def start_export():
            export_type = export_type_var.get()
            format_type = format_var.get()
            date_from = from_date.get().strip() or None
            date_to = to_date.get().strip() or None

            filters = {}
            if date_from:
                filters['date_from'] = date_from
            if date_to:
                filters['date_to'] = date_to

            export_dialog.destroy()
            self.perform_enhanced_export(export_type, filters, format_type)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        ttk.Button(btn_frame, text="Export", command=start_export).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=export_dialog.destroy).pack(side="left")

    def show_user_management(self):
        """Show user management interface (admin only)"""
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'admin':
            messagebox.showerror("Error", "Admin access required")
            return

        self.clear_content()

        user_mgmt_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(user_mgmt_frame, text="User Management")

        # Configure frame to expand
        user_mgmt_frame.rowconfigure(0, weight=1)
        user_mgmt_frame.columnconfigure(0, weight=1)

        ttk.Label(user_mgmt_frame, text="User Management",
                 style='Title.TLabel').pack(pady=(0, 20))

        # User list
        users_frame = ttk.LabelFrame(user_mgmt_frame, text="System Users", padding="10")
        users_frame.pack(fill="both", expand=True)

        # Create treeview for users
        columns = ('ID', 'Username', 'Role', 'Student ID', 'Status', 'Last Login')
        user_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=15)

        for col in columns:
            user_tree.heading(col, text=col)
            user_tree.column(col, width=100)

        # Load users
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, role, student_id FROM users ORDER BY username')
            users = cursor.fetchall()
            conn.close()

            for user in users:
                user_tree.insert('', 'end', values=(
                    user[0], user[1], user[2], user[3] or 'N/A', 'Active', 'N/A'
                ))
        except Exception as e:
            ttk.Label(users_frame, text=f"Error loading users: {e}").pack()

        user_tree.pack(fill="both", expand=True, pady=(0, 10))

        # User actions
        actions_frame = ttk.Frame(users_frame)
        actions_frame.pack(fill="x")

        ttk.Button(actions_frame, text="Reset Password",
                  command=lambda: self.reset_user_password(user_tree)).pack(side="left", padx=(0, 5))
        ttk.Button(actions_frame, text="Change Role",
                  command=lambda: self.change_user_role(user_tree)).pack(side="left", padx=(0, 5))
        ttk.Button(actions_frame, text="Deactivate User",
                  command=lambda: self.deactivate_user(user_tree)).pack(side="left", padx=(0, 5))
        ttk.Button(actions_frame, text="Activate User",
                  command=lambda: self.activate_user(user_tree)).pack(side="left")

    def reset_user_password(self, user_tree):
        """Reset user password"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return

        user_data = user_tree.item(selection[0])['values']
        username = user_data[1]
        user_id, admin_username = self._get_current_user_identity()
        permissions = self.auth.current_user.get('permissions', []) if self.auth and self.auth.current_user else []

        if self.auth and self.auth.current_user:
            if 'manage_users' not in permissions and self.auth.current_user['username'] != admin_username:
                messagebox.showerror("Permission Denied", "You do not have permission to reset passwords.")
                return
        else:
            messagebox.showerror("Error", "Authentication required to reset passwords.")
            return

        if messagebox.askyesno("Confirm", f"Reset password for user '{username}'?"):
            try:
                if not hasattr(self.auth, '_generate_temp_password') or not hasattr(self.auth, '_hash_password'):
                    raise RuntimeError("Authentication system does not support password resets.")

                temp_password = self.auth._generate_temp_password()
                salt, password_hash = self.auth._hash_password(temp_password)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                conn = sqlite3.connect(self.auth.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT id FROM user_accounts WHERE username = ?',
                    (username,)
                )
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    messagebox.showerror("Error", f"User account for '{username}' not found.")
                    return

                account_id = row[0]
                cursor.execute(
                    '''
                    UPDATE user_accounts
                    SET password_hash = ?, salt = ?, updated_at = ?, password_reset_required = 1
                    WHERE id = ?
                    ''',
                    (password_hash, salt, timestamp, account_id)
                )
                conn.commit()
                conn.close()

                if hasattr(self.auth, '_log_activity'):
                    self.auth._log_activity(
                        self.auth.current_user['username'],
                        f"Password reset for user: {username}",
                        user_id=self.auth.current_user.get('id')
                    )

                messagebox.showinfo(
                    "Success",
                    f"Password reset for {username}.\nTemporary password: {temp_password}\nThe user will be prompted to change it on next login."
                )
            except Exception as e:
                messagebox.showerror("Error", f"Could not reset password: {e}")

    def change_user_role(self, user_tree):
        """Change user role"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return

        user_data = user_tree.item(selection[0])['values']
        user_id = user_data[0]
        username = user_data[1]
        current_role = user_data[2]

        role_dialog = tk.Toplevel(self.root)
        role_dialog.title(f"Change Role - {username}")
        role_dialog.geometry("800x500")
        role_dialog.transient(self.root)
        role_dialog.grab_set()

        form_frame = ttk.Frame(role_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text=f"Change role for {username}:").pack(pady=(0, 10))
        ttk.Label(form_frame, text=f"Current role: {current_role}").pack(pady=(0, 10))

        role_var = tk.StringVar(value=current_role)
        for role in ['student', 'staff', 'admin']:
            ttk.Radiobutton(form_frame, text=role.title(), variable=role_var, value=role).pack(anchor="w")

        def save_role():
            new_role = role_var.get()
            if new_role == current_role:
                role_dialog.destroy()
                return

            try:
                # Use auth system to update user role if available
                if self.auth:
                    success = self.auth.update_user(user_id, role=new_role)

                    if not success:
                        messagebox.showerror("Error", "Failed to update role via auth system")
                        return
                else:
                    # Fallback to direct DB access
                    from education_system.post_18.university_system.infrastructure.database.db import get_connection
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
                    conn.commit()
                    conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'user_role', user_id=user_id, details={
                        'username': username,
                        'old_role': current_role,
                        'new_role': new_role
                    })

                messagebox.showinfo("Success", f"Role changed to {new_role}")
                role_dialog.destroy()
                self.show_user_management()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Could not change role: {e}")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x", pady=(20, 0))

        ttk.Button(btn_frame, text="Save", command=save_role).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=role_dialog.destroy).pack(side="left")

    def deactivate_user(self, user_tree):
        """Deactivate or reactivate a user account"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return

        user_data = user_tree.item(selection[0])['values']
        user_id = user_data[0]
        username = user_data[1]
        current_status = user_data[4]  # Status column

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'admin':
            messagebox.showerror("Error", "Admin access required to deactivate users")
            return

        # Toggle status
        new_status = 'Inactive' if current_status == 'Active' else 'Active'
        action = 'deactivate' if new_status == 'Inactive' else 'reactivate'

        if messagebox.askyesno("Confirm", f"Are you sure you want to {action} user '{username}'?"):
            try:
                # Update user status in database
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if users table has an 'active' or 'status' column
                # For now, we'll use a simple flag (1 for active, 0 for inactive)
                is_active = 1 if new_status == 'Active' else 0

                # Try to update the status
                try:
                    cursor.execute(
                        'UPDATE users SET active = ?, updated_at = ? WHERE id = ?',
                        (is_active, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
                    )
                except Exception:
                    # If 'active' column doesn't exist, add it first
                    cursor.execute('ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1')
                    cursor.execute('ALTER TABLE users ADD COLUMN updated_at TEXT')
                    cursor.execute(
                        'UPDATE users SET active = ?, updated_at = ? WHERE id = ?',
                        (is_active, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
                    )

                conn.commit()
                conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'user_status', user_id=user_id, details={
                        'username': username,
                        'action': action,
                        'new_status': new_status
                    })

                messagebox.showinfo("Success", f"User '{username}' has been {action}d")
                self.show_user_management()  # Refresh the user list

            except Exception as e:
                messagebox.showerror("Error", f"Could not {action} user: {e}")

    def activate_user(self, user_tree):
        """Activate a user account"""
        selection = user_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a user")
            return

        user_data = user_tree.item(selection[0])['values']
        user_id = user_data[0]
        username = user_data[1]
        current_status = user_data[4]  # Status column

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] != 'admin':
            messagebox.showerror("Error", "Admin access required to activate users")
            return

        # Check if already active
        if current_status == 'Active':
            messagebox.showinfo("Info", f"User '{username}' is already active")
            return

        if messagebox.askyesno("Confirm", f"Are you sure you want to activate user '{username}'?"):
            try:
                # Update user status in database
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Activate the user (set active = 1)
                try:
                    cursor.execute(
                        'UPDATE users SET active = ?, updated_at = ? WHERE id = ?',
                        (1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
                    )
                except Exception:
                    # If 'active' column doesn't exist, add it first
                    cursor.execute('ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1')
                    cursor.execute('ALTER TABLE users ADD COLUMN updated_at TEXT')
                    cursor.execute(
                        'UPDATE users SET active = ?, updated_at = ? WHERE id = ?',
                        (1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
                    )

                conn.commit()
                conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'user_status', user_id=user_id, details={
                        'username': username,
                        'action': 'activate',
                        'new_status': 'Active'
                    })

                messagebox.showinfo("Success", f"User '{username}' has been activated")
                self.show_user_management()  # Refresh the user list

            except Exception as e:
                messagebox.showerror("Error", f"Could not activate user: {e}")

    def perform_enhanced_export(self, export_type, filters, format_type):
        """Perform enhanced data export"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save Export",
                defaultextension=f".{format_type}",
                filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
            )

            if not filename:
                return

            self.update_status(f"Exporting {export_type} data...")

            # Use existing export functionality
            exported_data = self.support.export_data(export_type, filters, format_type)

            with open(filename, 'w') as f:
                f.write(exported_data)

            messagebox.showinfo("Export Complete", f"Data exported to {filename}")
            self.update_status("Export completed")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {e}")
            self.update_status("Export failed")

    def show_help(self):
        """Show help dialog"""
        help_dialog = tk.Toplevel(self.root)
        help_dialog.title("📖 User Guide")
        help_dialog.geometry("1400x850")
        help_dialog.transient(self.root)

        # Help content
        help_content = """
🎓 Enhanced Student Support Portal - User Guide

📊 DASHBOARD
- View your ticket statistics and recent activity
- Access quick actions and notifications
- See system status and important announcements

🎫 TICKETS
- Create new support tickets with attachments
- Track your existing tickets and responses
- Use templates for common issues
- Receive notifications on updates

🔍 SEARCH
- Search across tickets, FAQs, resources, and knowledge base
- Use filters to narrow down results
- Get AI-powered suggestions

❓ FAQs & 📚 KNOWLEDGE BASE
- Browse frequently asked questions
- Access detailed articles and guides
- Rate content as helpful
- Search for specific topics

📋 RESOURCES
- Access support documents and files
- Browse by category
- Download helpful materials

⚙️ PREFERENCES
- Customize notification settings
- Change display preferences
- Set your timezone and language

🔔 NOTIFICATIONS
- View all your notifications
- Mark as read/unread
- Filter by type and status

For additional help, contact the support team.
        """

        text_widget = scrolledtext.ScrolledText(help_dialog, wrap=tk.WORD, state='disabled', padding=10)
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)

        text_widget.config(state='normal')
        text_widget.insert(1.0, help_content)
        text_widget.config(state='disabled')

        # Close button
        ttk.Button(help_dialog, text="❌ Close", command=help_dialog.destroy).pack(pady=10)

    def show_about(self):
        """Show about dialog"""
        about_text = """
🎓 Enhanced Student Support Portal
Version 2.0

A comprehensive support system for educational institutions.

Features:
• Advanced ticket management
• Knowledge base and FAQs
• Real-time notifications
• Reporting and analytics
• Mobile-friendly interface

© 2024 Student Support System
        """

        messagebox.showinfo("About", about_text)

    def show_reports(self):
        """Show reports interface (staff only)"""
        self.clear_content()

        reports_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(reports_frame, text="📊 Reports")

        # Configure frame to expand
        reports_frame.rowconfigure(0, weight=1)
        reports_frame.columnconfigure(0, weight=1)

        # Check permissions
        if not self.auth or not self.auth.current_user or self.auth.current_user['role'] not in ('staff', 'admin'):
            ttk.Label(reports_frame, text="❌ Staff access required",
                     style='Title.TLabel').pack(pady=20)
            return

        # Reports interface
        ttk.Label(reports_frame, text="📊 Support Reports",
                 style='Title.TLabel').pack(pady=(0, 20))

        # Report types
        report_types = [
            ("📊 Ticket Summary Report", "ticket_summary"),
            ("📈 Performance Report", "performance"),
            ("⭐ Satisfaction Report", "satisfaction"),
            ("📂 Category Analysis", "category_analysis")
        ]

        for name, report_type in report_types:
            btn_frame = ttk.Frame(reports_frame)
            btn_frame.pack(fill="x", pady=5)

            ttk.Button(btn_frame, text=name,
                      command=lambda rt=report_type: self.generate_report(rt)).pack(side="left")

            # Add description
            descriptions = {
                "ticket_summary": "Overview of tickets by status, category, and priority",
                "performance": "Staff performance metrics and resolution times",
                "satisfaction": "Customer satisfaction ratings and feedback",
                "category_analysis": "Analysis of tickets by support category"
            }

            ttk.Label(btn_frame, text=descriptions.get(report_type, ""),
                     foreground=self.colors['text_secondary']).pack(side="left", padx=(10, 0))

    def generate_report(self, report_type):
        """Generate a report"""
        # Show date range dialog
        date_dialog = tk.Toplevel(self.root)
        date_dialog.title("📅 Report Date Range")
        date_dialog.geometry("900x550")
        date_dialog.transient(self.root)
        date_dialog.grab_set()

        # Date range form
        form_frame = ttk.Frame(date_dialog, padding="20")
        form_frame.pack(fill="both", expand=True)

        ttk.Label(form_frame, text="Select Report Date Range", style='Heading.TLabel').pack(pady=(0, 20))

        # Start date
        ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").pack(anchor="w")
        start_date_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        start_entry = ttk.Entry(form_frame, textvariable=start_date_var, width=20)
        start_entry.pack(fill="x", pady=(5, 10))

        # End date
        ttk.Label(form_frame, text="End Date (YYYY-MM-DD):").pack(anchor="w")
        end_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        end_entry = ttk.Entry(form_frame, textvariable=end_date_var, width=20)
        end_entry.pack(fill="x", pady=(5, 20))

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill="x")

        def generate():
            start_date = start_date_var.get()
            end_date = end_date_var.get()
            date_dialog.destroy()
            self.run_report_generation(report_type, start_date, end_date)

        ttk.Button(btn_frame, text="📊 Generate Report", command=generate).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="❌ Cancel", command=date_dialog.destroy).pack(side="left")

    def run_report_generation(self, report_type, start_date, end_date):
        """Run report generation in background"""
        def generate_in_background():
            try:
                self.update_status(f"Generating {report_type} report...")

                date_range = {'start': start_date, 'end': end_date}
                report_data = self.support.generate_reports(report_type, date_range)

                # Show report in new window
                self.root.after(0, lambda: self.show_report_window(report_type, report_data, date_range))

            except Exception as e:
                self.root.after(0, lambda _e=e: messagebox.showerror("Report Error", f"Failed to generate report: {_e}"))
                self.root.after(0, lambda: self.update_status("Report generation failed"))

        # Run in background thread
        threading.Thread(target=generate_in_background, daemon=True).start()

    def show_report_window(self, report_type, report_data, date_range):
        """Show generated report in a new window as plain text"""
        report_window = tk.Toplevel(self.root)
        report_window.title(f"📊 {report_type.replace('_', ' ').title()} Report")
        report_window.geometry("1200x800")

        # Main frame
        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Toolbar at top
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(toolbar_frame, text=f"📄 {report_type.replace('_', ' ').title()} Report",
                 font=('Segoe UI', 14, 'bold')).pack(side="left")

        # Buttons on the right
        btn_container = ttk.Frame(toolbar_frame)
        btn_container.pack(side="right")

        ttk.Button(btn_container, text="💾 Save as TXT",
                  command=lambda: self.save_report_as_txt(report_type, report_data, date_range)).pack(side="left", padx=2)
        ttk.Button(btn_container, text="📧 Email to Admin",
                  command=lambda: self.send_report_to_admin(report_type, report_data)).pack(side="left", padx=2)
        ttk.Button(btn_container, text="❌ Close",
                  command=report_window.destroy).pack(side="left", padx=2)

        # Text display area
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True)

        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('Courier New', 10))
        text_widget.pack(fill="both", expand=True)

        # Format report as plain text
        report_text = self._format_report_as_txt(report_type, report_data, date_range)

        # Insert text
        text_widget.insert(1.0, report_text)
        text_widget.config(state='disabled')  # Make read-only

        self.update_status(f"{report_type} report generated successfully")

    def create_report_summary(self, parent, report_type, report_data, date_range):
        """Create report summary view"""
        # Title
        title_text = f"📊 {report_type.replace('_', ' ').title()} Report"
        ttk.Label(parent, text=title_text, style='Title.TLabel').pack(pady=(0, 10))

        # Date range
        date_text = f"📅 Period: {date_range['start']} to {date_range['end']}"
        ttk.Label(parent, text=date_text, font=('Segoe UI', 10)).pack(pady=(0, 20))

        # Key metrics based on report type
        if report_type == 'ticket_summary':
            metrics = [
                ("📊 Total Tickets", str(report_data.get('total_tickets', 0))),
                ("🟢 Open", str(report_data.get('status_breakdown', {}).get('Open', 0))),
                ("⏳ In Progress", str(report_data.get('status_breakdown', {}).get('In Progress', 0))),
                ("✅ Resolved", str(report_data.get('status_breakdown', {}).get('Resolved', 0))),
            ]
        elif report_type == 'performance':
            stats = report_data.get('resolution_stats', {})
            metrics = [
                ("⏱️ Avg Resolution Time", f"{stats.get('avg_hours', 0):.1f} hours"),
                ("✅ Resolved Tickets", str(stats.get('resolved_count', 0))),
                ("⚡ Fastest Resolution", f"{stats.get('min_hours', 0):.1f} hours"),
                ("🐌 Slowest Resolution", f"{stats.get('max_hours', 0):.1f} hours"),
            ]
        elif report_type == 'satisfaction':
            metrics = [
                ("⭐ Average Rating", f"{report_data.get('avg_rating', 0):.2f}/5"),
                ("📊 Response Rate", f"{report_data.get('response_rate', 0):.1f}%"),
                ("📝 Total Responses", str(report_data.get('total_responses', 0))),
            ]
        else:
            metrics = []

        # Display metrics in a grid
        if metrics:
            metrics_frame = ttk.LabelFrame(parent, text="📈 Key Metrics", padding="15")
            metrics_frame.pack(fill="x", pady=(0, 20))

            metrics_grid = ttk.Frame(metrics_frame)
            metrics_grid.pack()

            for i, (label, value) in enumerate(metrics):
                row, col = i // 2, i % 2

                metric_frame = ttk.Frame(metrics_grid)
                metric_frame.grid(row=row, column=col, padx=20, pady=10, sticky="w")

                ttk.Label(metric_frame, text=label, font=('Segoe UI', 10)).pack()
                ttk.Label(metric_frame, text=value, font=('Segoe UI', 14, 'bold'),
                         foreground=self.colors['primary']).pack()

    def create_report_data_view(self, parent, report_data):
        """Create detailed data view"""
        # Create scrollable text area for JSON data
        data_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, state='disabled')
        data_text.pack(fill="both", expand=True)

        # Format and display data
        data_text.config(state='normal')
        data_text.insert(1.0, json.dumps(report_data, indent=2, default=str))
        data_text.config(state='disabled')

    def create_report_export_options(self, parent, report_type, report_data):
        """Create report export options"""
        ttk.Label(parent, text="📤 Export Options", style='Heading.TLabel').pack(pady=(0, 20))

        # Export format selection
        format_frame = ttk.LabelFrame(parent, text="Format", padding="10")
        format_frame.pack(fill="x", pady=(0, 10))

        self.export_format_var = tk.StringVar(value="JSON")

        for fmt in ["JSON", "CSV", "TXT"]:
            ttk.Radiobutton(format_frame, text=fmt, variable=self.export_format_var,
                           value=fmt).pack(side="left", padx=10)

        # Button frame for export options
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=20)

        # Export to file button
        ttk.Button(btn_frame, text="💾 Export Report",
                  command=lambda: self.export_report_data(report_type, report_data)).pack(side="left", padx=(0, 10))

        # Send to admin button
        ttk.Button(btn_frame, text="📧 Send to Admin",
                  command=lambda: self.send_report_to_admin(report_type, report_data)).pack(side="left")

    def export_report_data(self, report_type, report_data):
        """Export report data to file"""
        format_type = self.export_format_var.get().lower()

        # File dialog
        filename = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=f".{format_type}",
            filetypes=[(f"{format_type.upper()} files", f"*.{format_type}"), ("All files", "*.*")]
        )

        if not filename:
            return

        try:
            if format_type == "json":
                with open(filename, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
            elif format_type == "csv":
                # Convert to CSV format (simplified)
                with open(filename, 'w') as f:
                    f.write("Report Type,Data\n")
                    f.write(f"{report_type},{json.dumps(report_data, default=str)}\n")
            else:  # TXT
                with open(filename, 'w') as f:
                    f.write(f"Report: {report_type}\n")
                    f.write("=" * 50 + "\n")
                    f.write(json.dumps(report_data, indent=2, default=str))

            messagebox.showinfo("Export Complete", f"Report exported to {filename}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export report: {e}")

    def send_report_to_admin(self, report_type, report_data):
        """Send report to admin via email"""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email

            # Get admin email from database
            admin_email = None
            conn = get_connection()
            cursor = conn.cursor()

            # First try to find admin user with email
            cursor.execute('''
                SELECT u.email, u.username
                FROM users u
                WHERE u.role = 'admin' AND u.email IS NOT NULL AND u.email != ''
                ORDER BY u.id ASC
                LIMIT 1
            ''')
            result = cursor.fetchone()

            if result:
                admin_email = result[0]
                admin_username = result[1]
            else:
                # Fallback: check user_accounts table
                cursor.execute('''
                    SELECT ua.email, ua.username
                    FROM user_accounts ua
                    WHERE ua.role = 'admin' AND ua.email IS NOT NULL AND ua.email != ''
                    ORDER BY ua.id ASC
                    LIMIT 1
                ''')
                result = cursor.fetchone()
                if result:
                    admin_email = result[0]
                    admin_username = result[1]

            conn.close()

            if not admin_email:
                # Show dialog to manually enter admin email
                self._show_admin_email_dialog(report_type, report_data)
                return

            # Confirm sending
            if not messagebox.askyesno("Send Report",
                                       f"Send {report_type.replace('_', ' ').title()} Report to admin ({admin_username})?\n\nEmail: {admin_email}"):
                return

            # Format report content
            report_title = f"{report_type.replace('_', ' ').title()} Report"
            report_content = self._format_report_for_email(report_type, report_data)

            # Send email using send_email function
            success = send_email(
                recipient_email=admin_email,
                subject=f"[Student Support] {report_title}",
                body=report_content
            )

            if success:
                messagebox.showinfo("Success", f"Report sent to {admin_email}")
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('send', 'report_email', details={
                        'report_type': report_type,
                        'recipient': admin_email
                    })
            else:
                messagebox.showerror("Error", "Failed to send email. Please check email configuration.")

        except ImportError as e:
            messagebox.showerror("Error", f"Email service not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report: {e}")
            import traceback
            traceback.print_exc()

    def _show_admin_email_dialog(self, report_type, report_data):
        """Show dialog to manually enter admin email"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Enter Admin Email")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="No admin email found in database.\nPlease enter admin email:",
                 font=('Segoe UI', 10)).pack(pady=20)

        email_var = tk.StringVar()
        email_entry = ttk.Entry(dialog, textvariable=email_var, width=40)
        email_entry.pack(pady=10)
        email_entry.focus()

        def send():
            email = email_var.get().strip()
            if not email or '@' not in email:
                messagebox.showerror("Error", "Please enter a valid email address")
                return

            dialog.destroy()

            try:
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email

                report_title = f"{report_type.replace('_', ' ').title()} Report"
                report_content = self._format_report_for_email(report_type, report_data)

                success = send_email(
                    recipient_email=email,
                    subject=f"[Student Support] {report_title}",
                    body=report_content
                )

                if success:
                    messagebox.showinfo("Success", f"Report sent to {email}")
                else:
                    messagebox.showerror("Error", "Failed to send email")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Send", command=send).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)

    def _format_report_for_email(self, report_type, report_data):
        """Format report data for email body using template system"""
        # Build the specific report content based on type
        content_lines = []

        if report_type == 'ticket_summary':
            content_lines.append(f"Total Tickets: {report_data.get('total_tickets', 0)}")
            status_breakdown = report_data.get('status_breakdown', {})
            content_lines.append("\nStatus Breakdown:")
            for status, count in status_breakdown.items():
                content_lines.append(f"  - {status}: {count}")

        elif report_type == 'performance':
            stats = report_data.get('resolution_stats', {})
            content_lines.append(f"Average Resolution Time: {stats.get('avg_hours', 0):.1f} hours")
            content_lines.append(f"Resolved Tickets: {stats.get('resolved_count', 0)}")
            content_lines.append(f"Fastest Resolution: {stats.get('min_hours', 0):.1f} hours")
            content_lines.append(f"Slowest Resolution: {stats.get('max_hours', 0):.1f} hours")

        elif report_type == 'satisfaction':
            content_lines.append(f"Average Rating: {report_data.get('avg_rating', 0):.2f}/5")
            content_lines.append(f"Response Rate: {report_data.get('response_rate', 0):.1f}%")
            content_lines.append(f"Total Responses: {report_data.get('total_responses', 0)}")

        else:
            content_lines.append("Report Data:")
            content_lines.append(json.dumps(report_data, indent=2, default=str))

        report_content = '\n'.join(content_lines)

        # Use template for the overall structure
        template_vars = {
            'report_type': report_type.replace('_', ' ').title(),
            'report_type_upper': report_type.replace('_', ' ').upper(),
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'generated_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'report_content': report_content
        }

        # Return just the body portion (subject is handled separately in calling code)
        _, body = render_template('student_support_report', template_vars)

        if not body:
            # Fallback if template fails
            lines = []
            lines.append(f"{'='*60}")
            lines.append(f"  {report_type.replace('_', ' ').upper()} REPORT")
            lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"{'='*60}\n")
            lines.append(report_content)
            lines.append(f"\n{'='*60}")
            lines.append("This report was generated automatically by the Student Support System.")
            body = '\n'.join(lines)

        return body

    def _format_report_as_txt(self, report_type, report_data, date_range):
        """Format report data as plain text for display"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"  {report_type.replace('_', ' ').upper()} REPORT")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  Period: {date_range.get('start', 'N/A')} to {date_range.get('end', 'N/A')}")
        lines.append("=" * 80)
        lines.append("")

        if report_type == 'ticket_summary':
            lines.append("TICKET SUMMARY")
            lines.append("-" * 80)
            lines.append(f"Total Tickets: {report_data.get('total_tickets', 0)}")
            lines.append("")

            status_breakdown = report_data.get('status_breakdown', {})
            if status_breakdown:
                lines.append("Status Breakdown:")
                for status, count in status_breakdown.items():
                    lines.append(f"  • {status}: {count}")
                lines.append("")

            category_breakdown = report_data.get('category_breakdown', {})
            if category_breakdown:
                lines.append("Category Breakdown:")
                for category, count in category_breakdown.items():
                    lines.append(f"  • {category}: {count}")
                lines.append("")

            priority_breakdown = report_data.get('priority_breakdown', {})
            if priority_breakdown:
                lines.append("Priority Breakdown:")
                for priority, count in priority_breakdown.items():
                    lines.append(f"  • {priority}: {count}")
                lines.append("")

        elif report_type == 'performance':
            lines.append("PERFORMANCE REPORT")
            lines.append("-" * 80)
            stats = report_data.get('resolution_stats', {})
            lines.append(f"Average Resolution Time: {stats.get('avg_hours', 0):.1f} hours")
            lines.append(f"Resolved Tickets: {stats.get('resolved_count', 0)}")
            lines.append(f"Fastest Resolution: {stats.get('min_hours', 0):.1f} hours")
            lines.append(f"Slowest Resolution: {stats.get('max_hours', 0):.1f} hours")
            lines.append("")

            staff_performance = report_data.get('staff_performance', {})
            if staff_performance:
                lines.append("Staff Performance:")
                for staff, data in staff_performance.items():
                    lines.append(f"  • {staff}: {data.get('resolved', 0)} resolved, "
                               f"Avg: {data.get('avg_time', 0):.1f} hours")
                lines.append("")

        elif report_type == 'satisfaction':
            lines.append("SATISFACTION REPORT")
            lines.append("-" * 80)
            lines.append(f"Average Rating: {report_data.get('avg_rating', 0):.2f}/5.00 ⭐")
            lines.append(f"Response Rate: {report_data.get('response_rate', 0):.1f}%")
            lines.append(f"Total Responses: {report_data.get('total_responses', 0)}")
            lines.append("")

            rating_distribution = report_data.get('rating_distribution', {})
            if rating_distribution:
                lines.append("Rating Distribution:")
                for rating, count in sorted(rating_distribution.items(), reverse=True):
                    stars = "⭐" * int(rating)
                    lines.append(f"  {stars} ({rating}): {count}")
                lines.append("")

        elif report_type == 'category_analysis':
            lines.append("CATEGORY ANALYSIS REPORT")
            lines.append("-" * 80)

            category_data = report_data.get('categories', {})
            for category, data in category_data.items():
                lines.append(f"\n{category.upper()}")
                lines.append(f"  Total Tickets: {data.get('total', 0)}")
                lines.append(f"  Resolved: {data.get('resolved', 0)}")
                lines.append(f"  Avg Resolution Time: {data.get('avg_time', 0):.1f} hours")
                lines.append(f"  Satisfaction Rating: {data.get('satisfaction', 0):.2f}/5.00")

        else:
            lines.append("DETAILED REPORT DATA")
            lines.append("-" * 80)
            lines.append(json.dumps(report_data, indent=2, default=str))

        lines.append("")
        lines.append("=" * 80)
        lines.append("Report generated by Student Support System")
        lines.append("For questions or concerns, contact the support team")
        lines.append("=" * 80)

        return '\n'.join(lines)

    def save_report_as_txt(self, report_type, report_data, date_range):
        """Save report as TXT file"""
        filename = filedialog.asksaveasfilename(
            title="Save Report as TXT",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        try:
            report_text = self._format_report_as_txt(report_type, report_data, date_range)

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report_text)

            messagebox.showinfo("Success", f"Report saved to:\n{filename}")

            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('export', 'report', details={
                    'report_type': report_type,
                    'format': 'txt',
                    'filename': os.path.basename(filename)
                })

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {e}")

