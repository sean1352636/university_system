import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.university_system.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import activity logger for audit trail
try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.helpdesk import (
        backup_database, bulk_assign_tickets, check_data_integrity,
        create_kb_article, display_helpdesk_menu, escalate_ticket,
        escalate_ticket_manual, export_tickets_csv, export_users_csv,
        init_default_data, init_helpdesk_db, search_kb_articles,
        setup_enhanced_helpdesk_permissions
    )
except ImportError:
    # If helpdesk.py is not available, we'll define minimal stubs
    print("Warning: helpdesk.py not found. Running in standalone mode.")

    def init_helpdesk_db():
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Create support_tickets table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                assigned_to INTEGER,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'medium',
                impact TEXT DEFAULT 'low',
                urgency TEXT DEFAULT 'low',
                source TEXT DEFAULT 'web',
                resolution TEXT,
                satisfaction_rating INTEGER,
                satisfaction_feedback TEXT,
                estimated_hours REAL,
                actual_hours REAL,
                due_date TEXT,
                resolved_at TEXT,
                first_response_at TEXT,
                last_activity_at TEXT,
                escalation_level INTEGER DEFAULT 0,
                tags TEXT,
                department TEXT,
                organization_id INTEGER,
                parent_ticket_id INTEGER,
                knowledge_base_articles TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id),
                FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
            )
            ''')

            # Add subject column if it doesn't exist (migration)
            try:
                # Check if subject column exists using PRAGMA
                cursor.execute("PRAGMA table_info(support_tickets)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'subject' not in columns:
                    cursor.execute("ALTER TABLE support_tickets ADD COLUMN subject TEXT DEFAULT 'No Subject'")
                    conn.commit()
            except Exception as e:
                print(f"Warning: Could not add subject column: {e}")

            # Create ticket_replies table with enhanced fields
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_replies (
                reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                message TEXT NOT NULL,
                is_internal BOOLEAN DEFAULT 0,
                reply_type TEXT DEFAULT 'comment',
                time_spent REAL DEFAULT 0,
                created_at TEXT,
                edited_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create ticket_attachments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                reply_id INTEGER,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                file_hash TEXT,
                uploaded_by INTEGER,
                upload_path TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (reply_id) REFERENCES ticket_replies (reply_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_assignments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                assigned_from INTEGER,
                assigned_to INTEGER,
                assignment_reason TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (assigned_from) REFERENCES users (id),
                FOREIGN KEY (assigned_to) REFERENCES users (id)
            )
            ''')

            # Create ticket_templates table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                subject_template TEXT,
                message_template TEXT,
                default_priority TEXT,
                default_impact TEXT,
                default_urgency TEXT,
                form_fields TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create sla_policies table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sla_policies (
                sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                priority TEXT,
                impact TEXT,
                urgency TEXT,
                first_response_hours INTEGER,
                resolution_hours INTEGER,
                escalation_hours INTEGER,
                business_hours_only BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create ticket_workflows table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_workflows (
                workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                trigger_type TEXT NOT NULL,
                trigger_conditions TEXT,
                actions TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_by INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_time_tracking table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_time_tracking (
                time_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_minutes INTEGER,
                description TEXT,
                billable BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create ticket_escalations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_escalations (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                escalation_level INTEGER,
                escalated_to INTEGER,
                escalated_by INTEGER,
                escalation_reason TEXT,
                resolved BOOLEAN DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (escalated_to) REFERENCES users (id),
                FOREIGN KEY (escalated_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_links table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                linked_ticket_id INTEGER,
                link_type TEXT,
                created_by INTEGER,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
            ''')

            # Create ticket_audit_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                user_id INTEGER,
                action TEXT NOT NULL,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            # Create knowledge_base table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_base (
                article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                author_id INTEGER,
                status TEXT DEFAULT 'draft',
                views INTEGER DEFAULT 0,
                helpful_votes INTEGER DEFAULT 0,
                unhelpful_votes INTEGER DEFAULT 0,
                search_keywords TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (author_id) REFERENCES users (id)
            )
            ''')

            # Create departments table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                manager_id INTEGER,
                email TEXT,
                sla_policy_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (manager_id) REFERENCES users (id),
                FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
            )
            ''')

            # Create organizations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT,
                contact_email TEXT,
                phone TEXT,
                address TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            )
            ''')

            # Create saved_searches table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                search_criteria TEXT,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            conn.commit()
            conn.close()
            print("Enhanced helpdesk database initialized successfully!")

            # Initialize default data
            init_default_data()

        except sqlite3.Error as e:
            print(f"An error occurred while initializing the helpdesk database: {e}")

    def setup_enhanced_helpdesk_permissions():
        """
        Setup enhanced helpdesk permissions

        Creates and configures helpdesk-specific permissions in the
        authentication system. This includes permissions for:
        - Creating and managing tickets
        - Knowledge base management
        - SLA and workflow configuration
        - Analytics and reporting
        - Department and organization management

        Permissions are automatically assigned to appropriate roles
        (Student, Staff, Admin) based on typical helpdesk workflows.

        Note: This is a wrapper that calls the actual implementation
        from the services layer. It's provided here for backwards
        compatibility and convenience.
        """
        try:
            # Try to import and call the actual implementation
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk import (
                setup_enhanced_helpdesk_permissions as service_setup_permissions
            )
            service_setup_permissions()
        except ImportError:
            # If service layer is not available, do basic setup
            print("Warning: Helpdesk service layer not available. Setting up basic permissions...")
            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if permissions table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permissions'")
                if not cursor.fetchone():
                    print("Permissions table not found. Authentication system must be initialized first.")
                    conn.close()
                    return

                # Add basic helpdesk permissions
                basic_permissions = [
                    ('create_ticket', 'Can create support tickets'),
                    ('view_own_tickets', 'Can view own support tickets'),
                    ('view_all_tickets', 'Can view all support tickets'),
                    ('manage_tickets', 'Can manage ticket status and priority')
                ]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for perm_name, perm_desc in basic_permissions:
                    cursor.execute(
                        "SELECT COUNT(*) FROM permissions WHERE permission_name = ?",
                        (perm_name,)
                    )
                    if cursor.fetchone()[0] == 0:
                        cursor.execute(
                            "INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)",
                            (perm_name, perm_desc, timestamp)
                        )

                conn.commit()
                conn.close()
                print("Basic helpdesk permissions setup completed")

            except Exception as e:
                print(f"Error setting up basic helpdesk permissions: {e}")
        except Exception as e:
            print(f"Error setting up enhanced helpdesk permissions: {e}")

from education_system.university_system.modules.domain.student_affairs.gui.helpdesk.base import HelpdeskGUI

def create_user_management_tab(self, parent):
    """Create user management tab"""
    user_frame = ttk.Frame(parent)
    parent.add(user_frame, text="Users")

    # Toolbar
    toolbar = ttk.Frame(user_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text="Refresh", command=lambda: self._refresh_user_list(users_tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="Add User", command=self._show_add_user_dialog).pack(side='left', padx=5)

    # Search frame
    search_frame = ttk.Frame(user_frame)
    search_frame.pack(fill='x', padx=10, pady=5)

    ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
    self.user_search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=self.user_search_var, width=30)
    search_entry.pack(side='left', padx=5)
    ttk.Button(search_frame, text="Search", command=lambda: self._search_users(users_tree)).pack(side='left', padx=5)

    # Users list
    list_frame = ttk.Frame(user_frame)
    list_frame.pack(fill='both', expand=True, padx=10, pady=5)

    columns = ('ID', 'Username', 'Email', 'Role', 'Status', 'Created')
    users_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

    column_widths = {'ID': 50, 'Username': 120, 'Email': 200, 'Role': 100, 'Status': 80, 'Created': 120}
    for col in columns:
        users_tree.heading(col, text=col)
        users_tree.column(col, width=column_widths.get(col, 100))

    v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=users_tree.yview)
    users_tree.configure(yscrollcommand=v_scrollbar.set)

    users_tree.pack(side='left', fill='both', expand=True)
    v_scrollbar.pack(side='right', fill='y')

    # Action buttons
    action_frame = ttk.Frame(user_frame)
    action_frame.pack(fill='x', padx=10, pady=5)

    ttk.Button(action_frame, text="Edit User", command=lambda: self._edit_selected_user(users_tree)).pack(side='left', padx=5)
    ttk.Button(action_frame, text="Deactivate", command=lambda: self._deactivate_user(users_tree)).pack(side='left', padx=5)
    ttk.Button(action_frame, text="Reset Password", command=lambda: self._reset_user_password(users_tree)).pack(side='left', padx=5)

    # Double-click to edit
    users_tree.bind('<Double-1>', lambda e: self._edit_selected_user(users_tree))

    # Store reference and load data
    self.users_tree = users_tree
    self._refresh_user_list(users_tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_user_management_tab = create_user_management_tab

def _refresh_user_list(self, tree):
    """Refresh the user list"""
    for item in tree.get_children():
        tree.delete(item)

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check which columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        # Build query based on available columns
        if 'is_active' in columns:
            status_expr = "CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END"
        else:
            status_expr = "'Active'"

        created_col = 'created_at' if 'created_at' in columns else 'NULL'

        cursor.execute('''
            SELECT id, username, email, role,
                   ''' + status_expr + ''' as status,
                   ''' + created_col + ''' as created_at
            FROM users
            ORDER BY username
        ''')

        users = cursor.fetchall()
        conn.close()

        for user in users:
            created = user['created_at'] or ''
            tree.insert('', 'end', values=(
                user['id'],
                user['username'] or 'N/A',
                user['email'] or 'N/A',
                user['role'] or 'user',
                user['status'] or 'Active',
                created[:16] if created else ''
            ))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load users: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._refresh_user_list = _refresh_user_list

def _search_users(self, tree):
    """Search users by username or email"""
    search_text = self.user_search_var.get().strip().lower()
    if not search_text:
        self._refresh_user_list(tree)
        return

    for item in tree.get_children():
        tree.delete(item)

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check which columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'is_active' in columns:
            status_expr = "CASE WHEN is_active = 1 THEN 'Active' ELSE 'Inactive' END"
        else:
            status_expr = "'Active'"

        created_col = 'created_at' if 'created_at' in columns else 'NULL'

        cursor.execute('''
            SELECT id, username, email, role,
                   ''' + status_expr + ''' as status,
                   ''' + created_col + ''' as created_at
            FROM users
            WHERE LOWER(username) LIKE ? OR LOWER(COALESCE(email, '')) LIKE ?
            ORDER BY username
        ''', (f'%{search_text}%', f'%{search_text}%'))

        users = cursor.fetchall()
        conn.close()

        for user in users:
            created = user['created_at'] or ''
            tree.insert('', 'end', values=(
                user['id'],
                user['username'] or 'N/A',
                user['email'] or 'N/A',
                user['role'] or 'user',
                user['status'] or 'Active',
                created[:16] if created else ''
            ))
    except Exception as e:
        messagebox.showerror("Error", f"Search failed: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._search_users = _search_users

def _show_add_user_dialog(self):
    """Show dialog to add a new user"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Add New User")
    dialog.geometry("400x350")
    dialog.transient(self.root)
    dialog.grab_set()

    form_frame = ttk.Frame(dialog, padding="20")
    form_frame.pack(fill='both', expand=True)

    ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky='w', pady=5)
    username_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=username_var, width=30).grid(row=0, column=1, pady=5)

    ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
    email_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=email_var, width=30).grid(row=1, column=1, pady=5)

    ttk.Label(form_frame, text="Password:").grid(row=2, column=0, sticky='w', pady=5)
    password_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=password_var, show='*', width=30).grid(row=2, column=1, pady=5)

    ttk.Label(form_frame, text="Role:").grid(row=3, column=0, sticky='w', pady=5)
    role_var = tk.StringVar(value='student')
    ttk.Combobox(form_frame, textvariable=role_var,
                values=['student', 'instructor', 'staff', 'admin'],
                state='readonly', width=27).grid(row=3, column=1, pady=5)

    def save_user():
        if not username_var.get() or not email_var.get() or not password_var.get():
            messagebox.showerror("Error", "All fields are required")
            return
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            import hashlib
            conn = get_connection()
            cursor = conn.cursor()

            # Check which columns exist
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]

            # Simple password hash (in real system, use proper hashing)
            password_hash = hashlib.sha256(password_var.get().encode()).hexdigest()

            # Build insert based on available columns
            if 'is_active' in columns and 'created_at' in columns:
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, datetime('now'))
                ''', (username_var.get(), email_var.get(), password_hash, role_var.get()))
            elif 'is_active' in columns:
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, role, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (username_var.get(), email_var.get(), password_hash, role_var.get()))
            else:
                cursor.execute('''
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                ''', (username_var.get(), email_var.get(), password_hash, role_var.get()))

            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "User created successfully")
            dialog.destroy()
            self._refresh_user_list(self.users_tree)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create user: {e}")

    btn_frame = ttk.Frame(form_frame)
    btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
    ttk.Button(btn_frame, text="Save", command=save_user).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI._show_add_user_dialog = _show_add_user_dialog

def _edit_selected_user(self, tree):
    """Edit selected user"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a user")
        return

    item = tree.item(selection[0])
    user_id = item['values'][0]
    self.show_edit_user(user_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI._edit_selected_user = _edit_selected_user

def _deactivate_user(self, tree):
    """Deactivate selected user"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a user")
        return

    item = tree.item(selection[0])
    user_id = item['values'][0]
    username = item['values'][1]

    if not messagebox.askyesno("Confirm", f"Deactivate user '{username}'?"):
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Check if is_active column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'is_active' in columns:
            cursor.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"User '{username}' has been deactivated")
            self._refresh_user_list(tree)
        else:
            conn.close()
            messagebox.showinfo("Info", "User deactivation not supported - is_active column not available")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to deactivate user: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._deactivate_user = _deactivate_user

def _reset_user_password(self, tree):
    """Reset password for selected user"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a user")
        return

    item = tree.item(selection[0])
    user_id = item['values'][0]
    username = item['values'][1]

    if not messagebox.askyesno("Confirm", f"Reset password for user '{username}'?"):
        return

    # Show password entry dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Reset Password")
    dialog.geometry("300x150")
    dialog.transient(self.root)
    dialog.grab_set()

    ttk.Label(dialog, text="New Password:").pack(pady=10)
    password_var = tk.StringVar()
    ttk.Entry(dialog, textvariable=password_var, show='*', width=25).pack(pady=5)

    def do_reset():
        if not password_var.get():
            messagebox.showerror("Error", "Password cannot be empty")
            return
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            import hashlib
            conn = get_connection()
            cursor = conn.cursor()
            password_hash = hashlib.sha256(password_var.get().encode()).hexdigest()
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Password reset for '{username}'")
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset password: {e}")

    ttk.Button(dialog, text="Reset Password", command=do_reset).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI._reset_user_password = _reset_user_password

def show_user_management(self):
    """Switch to user management"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Administration':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_user_management = show_user_management

def show_add_user(self):
    """Show add user dialog"""
    self.show_register()  # Reuse the registration dialog

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_add_user = show_add_user

def show_edit_user(self):
    """Show edit user dialog"""
    selection = self.users_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a user to edit")
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Get selected user ID
        item = self.users_tree.item(selection[0])
        user_id = item['values'][0]

        # Fetch user data
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = dict(cursor.fetchone())
        conn.close()

        # Create edit window
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit User - {user.get('username', 'Unknown')}")
        edit_window.geometry("500x450")
        edit_window.transient(self.root)
        edit_window.grab_set()

        main_frame = ttk.Frame(edit_window, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Edit User Details", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        # Form frame
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='x', pady=10)

        # Username (read-only)
        ttk.Label(form_frame, text="Username:").grid(row=0, column=0, sticky='w', pady=5)
        username_var = tk.StringVar(value=user.get('username', ''))
        ttk.Entry(form_frame, textvariable=username_var, state='disabled', width=30).grid(row=0, column=1, pady=5, padx=5)

        # Email
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky='w', pady=5)
        email_var = tk.StringVar(value=user.get('email', ''))
        ttk.Entry(form_frame, textvariable=email_var, width=30).grid(row=1, column=1, pady=5, padx=5)

        # First Name
        ttk.Label(form_frame, text="First Name:").grid(row=2, column=0, sticky='w', pady=5)
        first_name_var = tk.StringVar(value=user.get('first_name', ''))
        ttk.Entry(form_frame, textvariable=first_name_var, width=30).grid(row=2, column=1, pady=5, padx=5)

        # Last Name
        ttk.Label(form_frame, text="Last Name:").grid(row=3, column=0, sticky='w', pady=5)
        last_name_var = tk.StringVar(value=user.get('last_name', ''))
        ttk.Entry(form_frame, textvariable=last_name_var, width=30).grid(row=3, column=1, pady=5, padx=5)

        # Role
        ttk.Label(form_frame, text="Role:").grid(row=4, column=0, sticky='w', pady=5)
        role_var = tk.StringVar(value=user.get('role', 'student'))
        role_combo = ttk.Combobox(form_frame, textvariable=role_var,
                                  values=['student', 'instructor', 'staff', 'admin'], state='readonly', width=27)
        role_combo.grid(row=4, column=1, pady=5, padx=5)

        def save_user():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE users
                    SET email = ?, first_name = ?, last_name = ?, role = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    email_var.get().strip(),
                    first_name_var.get().strip(),
                    last_name_var.get().strip(),
                    role_var.get(),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    user_id
                ))

                conn.commit()
                conn.close()

                # Log activity
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('update', 'user', user_id=user_id,
                                details={'updated_by': self.current_user.get('username')})

                messagebox.showinfo("Success", "User updated successfully!")
                edit_window.destroy()
                self.refresh_users()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update user: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=20)

        ttk.Button(btn_frame, text="Save Changes", command=save_user).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=edit_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load user data: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_edit_user = show_edit_user

