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
    from education_system.university_system.modules.shared.utils.i18n import (
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
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
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

def show_department_management(self):
    """Show department management dialog"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        dept_window = tk.Toplevel(self.root)
        dept_window.title("Department Management")
        dept_window.geometry("800x500")
        dept_window.transient(self.root)

        main_frame = ttk.Frame(dept_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Departments", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Treeview for departments
        columns = ('ID', 'Name', 'Description', 'Email', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140)
        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load departments with proper connection handling
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT dept_id, name, description, email, is_active FROM departments")
            rows = cursor.fetchall()
            for row in rows:
                tree.insert('', 'end', values=(row[0], row[1], row[2] or '', row[3] or '', 'Yes' if row[4] else 'No'))
        finally:
            conn.close()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')

        def add_dept():
            self._show_department_form(tree)

        ttk.Button(btn_frame, text="Add Department", command=add_dept).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=dept_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load department management: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_department_management = show_department_management

def _show_department_form(self, tree):
    """Show form to add new department"""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Department")
    form_window.geometry("400x300")
    form_window.transient(self.root)
    form_window.grab_set()

    frame = ttk.Frame(form_window, padding="20")
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text="Department Name:").grid(row=0, column=0, sticky='w', pady=5)
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

    ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='w', pady=5)
    desc_var = tk.StringVar()
    ttk.Entry(frame, textvariable=desc_var, width=30).grid(row=1, column=1, pady=5)

    ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky='w', pady=5)
    email_var = tk.StringVar()
    ttk.Entry(frame, textvariable=email_var, width=30).grid(row=2, column=1, pady=5)

    def save():
        conn = None
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO departments (name, description, email, is_active, created_at)
                VALUES (?, ?, ?, 1, ?)
            """, (name_var.get(), desc_var.get(), email_var.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            dept_id = cursor.lastrowid

            tree.insert('', 'end', values=(dept_id, name_var.get(), desc_var.get(), email_var.get(), 'Yes'))
            messagebox.showinfo("Success", "Department added successfully!")
            form_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add department: {str(e)}")
        finally:
            if conn:
                conn.close()

    ttk.Button(frame, text="Save", command=save).grid(row=3, column=0, pady=20)
    ttk.Button(frame, text="Cancel", command=form_window.destroy).grid(row=3, column=1, pady=20)

# Attach method to HelpdeskGUI class
HelpdeskGUI._show_department_form = _show_department_form

def manage_departments_gui(self):
    """Manage departments"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to manage departments.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Department Management")
    dialog.geometry("900x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Department Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="➕ Create Department",
              command=lambda: self.create_department_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="✏️ Edit Department",
              command=lambda: self.edit_selected_department(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔄 Toggle Active",
              command=lambda: self.toggle_selected_department(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self.load_departments_list(tree)).pack(side='left', padx=5)

    # Departments list
    columns = ('ID', 'Name', 'Email', 'Manager', 'Description', 'Active')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        width = 60 if col == 'ID' else 150
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    # Scrollbar
    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load departments
    self.load_departments_list(tree)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_departments_gui = manage_departments_gui

def load_departments_list(self, tree):
    """Load departments into treeview"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT d.dept_id, d.name, d.email, u.username as manager,
                   d.description, d.is_active
            FROM departments d
            LEFT JOIN users u ON d.manager_id = u.id
            ORDER BY d.name
        ''')

        departments = cursor.fetchall()
        conn.close()

        for dept in departments:
            dept_id, name, email, manager, description, is_active = dept
            active_text = "✓ Yes" if is_active else "✗ No"
            manager_text = manager or 'None'

            tree.insert('', 'end', values=(
                dept_id, name, email or 'N/A', manager_text,
                (description or 'N/A')[:50], active_text
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load departments: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_departments_list = load_departments_list

def create_department_gui(self):
    """Create a new department"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Create Department")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Create New Department",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Form fields
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True)

    ttk.Label(form_frame, text="Department Name *").grid(row=0, column=0, sticky='w', pady=5)
    name_entry = ttk.Entry(form_frame, width=35)
    name_entry.grid(row=0, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='nw', pady=5)
    desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
    desc_text.grid(row=1, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Email").grid(row=2, column=0, sticky='w', pady=5)
    email_entry = ttk.Entry(form_frame, width=35)
    email_entry.grid(row=2, column=1, sticky='ew', pady=5)

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def save_department():
        name = name_entry.get().strip()

        if not name:
            messagebox.showerror("Error", "Department name is required")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO departments (name, description, email, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                name,
                desc_text.get('1.0', 'end-1c').strip(),
                email_entry.get().strip(),
                now
            ))

            conn.commit()
            dept_id = cursor.lastrowid
            conn.close()

            messagebox.showinfo("Success", f"Department #{dept_id} created successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create department: {str(e)}")

    ttk.Button(button_frame, text="Create Department", command=save_department).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_department_gui = create_department_gui

def edit_selected_department(self, tree):
    """Edit selected department"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a department to edit")
        return

    dept_id = tree.item(selection[0])['values'][0]
    self.edit_department_gui(dept_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_selected_department = edit_selected_department

def edit_department_gui(self, dept_id):
    """Edit an existing department"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM departments WHERE dept_id = ?', (dept_id,))
        dept = cursor.fetchone()
        conn.close()

        if not dept:
            messagebox.showerror("Error", "Department not found")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Department #{dept_id}")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Edit Department: {dept[1]}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        ttk.Label(form_frame, text="Department Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=35)
        name_entry.insert(0, dept[1])
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
        desc_text.insert('1.0', dept[2] or '')
        desc_text.grid(row=1, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Email").grid(row=2, column=0, sticky='w', pady=5)
        email_entry = ttk.Entry(form_frame, width=35)
        email_entry.insert(0, dept[3] or '')
        email_entry.grid(row=2, column=1, sticky='ew', pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def update_department():
            name = name_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Department name is required")
                return

            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE departments
                    SET name = ?, description = ?, email = ?
                    WHERE dept_id = ?
                ''', (
                    name,
                    desc_text.get('1.0', 'end-1c').strip(),
                    email_entry.get().strip(),
                    dept_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Department updated successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update department: {str(e)}")

        ttk.Button(button_frame, text="Update Department", command=update_department).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load department: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_department_gui = edit_department_gui

def toggle_selected_department(self, tree):
    """Toggle active status of selected department"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a department to toggle")
        return

    dept_id = tree.item(selection[0])['values'][0]
    self.toggle_department_gui(dept_id, tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_selected_department = toggle_selected_department

def toggle_department_gui(self, dept_id, tree):
    """Toggle department active status"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, is_active FROM departments WHERE dept_id = ?', (dept_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "Department not found")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('UPDATE departments SET is_active = ? WHERE dept_id = ?',
                      (new_status, dept_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"Department '{name}' has been {status_text}")

        # Refresh tree
        self.load_departments_list(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle department: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_department_gui = toggle_department_gui

def view_departments_gui(self):
    """View departments (read-only)"""
    self.manage_departments_gui()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_departments_gui = view_departments_gui

def manage_organizations_gui(self):
    """Manage organizations"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to manage organizations.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Organization Management")
    dialog.geometry("1000x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Organization Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="➕ Add Organization",
              command=lambda: self.add_organization_gui(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="✏️ Edit Organization",
              command=lambda: self.edit_selected_organization(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔄 Toggle Active",
              command=lambda: self.toggle_selected_organization(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self.load_organizations_list(tree)).pack(side='left', padx=5)

    # Organizations list
    columns = ('ID', 'Name', 'Code', 'Description', 'Parent Org', 'Active')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        width = 60 if col == 'ID' else 150
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load organizations
    self.load_organizations_list(tree)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_organizations_gui = manage_organizations_gui

def load_organizations_list(self, tree):
    """Load organizations into treeview"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        # Check if organizations table exists, create if not
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS organizations (
                org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE,
                description TEXT,
                parent_org_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_org_id) REFERENCES organizations(org_id)
            )
        ''')
        conn.commit()

        cursor.execute('''
            SELECT o.org_id, o.name, o.code, o.description, p.name as parent_name, o.is_active
            FROM organizations o
            LEFT JOIN organizations p ON o.parent_org_id = p.org_id
            ORDER BY o.name
        ''')

        organizations = cursor.fetchall()
        conn.close()

        for org in organizations:
            org_id, name, code, description, parent_name, is_active = org
            active_text = "✓ Yes" if is_active else "✗ No"

            tree.insert('', 'end', values=(
                org_id, name, code or 'N/A',
                (description or 'N/A')[:50], parent_name or 'None', active_text
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load organizations: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_organizations_list = load_organizations_list

def add_organization_gui(self, tree):
    """Add a new organization"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Organization")
    dialog.geometry("500x450")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Add New Organization",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True)

    ttk.Label(form_frame, text="Organization Name *").grid(row=0, column=0, sticky='w', pady=5)
    name_entry = ttk.Entry(form_frame, width=35)
    name_entry.grid(row=0, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Organization Code").grid(row=1, column=0, sticky='w', pady=5)
    code_entry = ttk.Entry(form_frame, width=35)
    code_entry.grid(row=1, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Description").grid(row=2, column=0, sticky='nw', pady=5)
    desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
    desc_text.grid(row=2, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Parent Organization").grid(row=3, column=0, sticky='w', pady=5)
    parent_var = tk.StringVar()
    parent_combo = ttk.Combobox(form_frame, textvariable=parent_var, state="readonly", width=33)
    parent_combo.grid(row=3, column=1, sticky='ew', pady=5)

    # Load parent organizations
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT org_id, name FROM organizations WHERE is_active = 1 ORDER BY name')
        parents = cursor.fetchall()
        conn.close()
        parent_combo['values'] = ['None'] + [f"{p[0]}: {p[1]}" for p in parents]
        parent_combo.set('None')
    except Exception:
        parent_combo['values'] = ['None']
        parent_combo.set('None')

    form_frame.columnconfigure(1, weight=1)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def save_organization():
        name = name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Organization name is required")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection

            parent_id = None
            parent_selection = parent_var.get()
            if parent_selection and parent_selection != 'None':
                parent_id = int(parent_selection.split(':')[0])

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO organizations (name, code, description, parent_org_id)
                VALUES (?, ?, ?, ?)
            ''', (
                name,
                code_entry.get().strip() or None,
                desc_text.get('1.0', 'end-1c').strip() or None,
                parent_id
            ))

            conn.commit()
            org_id = cursor.lastrowid
            conn.close()

            messagebox.showinfo("Success", f"Organization #{org_id} created successfully!")
            dialog.destroy()
            self.load_organizations_list(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create organization: {str(e)}")

    ttk.Button(button_frame, text="Create Organization", command=save_organization).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_organization_gui = add_organization_gui

def edit_selected_organization(self, tree):
    """Edit selected organization"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select an organization to edit")
        return

    org_id = tree.item(selection[0])['values'][0]
    self.edit_organization_gui(org_id, tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_selected_organization = edit_selected_organization

def edit_organization_gui(self, org_id, tree):
    """Edit existing organization"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, code, description, parent_org_id FROM organizations WHERE org_id = ?',
                      (org_id,))
        org = cursor.fetchone()
        conn.close()

        if not org:
            messagebox.showerror("Error", "Organization not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Organization #{org_id}")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Edit Organization: {org[0]}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        ttk.Label(form_frame, text="Organization Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=35)
        name_entry.insert(0, org[0])
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Organization Code").grid(row=1, column=0, sticky='w', pady=5)
        code_entry = ttk.Entry(form_frame, width=35)
        code_entry.insert(0, org[1] or '')
        code_entry.grid(row=1, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Description").grid(row=2, column=0, sticky='nw', pady=5)
        desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=35)
        desc_text.insert('1.0', org[2] or '')
        desc_text.grid(row=2, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Parent Organization").grid(row=3, column=0, sticky='w', pady=5)
        parent_var = tk.StringVar()
        parent_combo = ttk.Combobox(form_frame, textvariable=parent_var, state="readonly", width=33)
        parent_combo.grid(row=3, column=1, sticky='ew', pady=5)

        # Load parent organizations (excluding self)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT org_id, name FROM organizations WHERE is_active = 1 AND org_id != ? ORDER BY name',
                          (org_id,))
            parents = cursor.fetchall()
            conn.close()
            parent_combo['values'] = ['None'] + [f"{p[0]}: {p[1]}" for p in parents]

            if org[3]:
                for p in parents:
                    if p[0] == org[3]:
                        parent_combo.set(f"{p[0]}: {p[1]}")
                        break
            else:
                parent_combo.set('None')
        except Exception:
            parent_combo['values'] = ['None']
            parent_combo.set('None')

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def update_organization():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Organization name is required")
                return

            try:
                parent_id = None
                parent_selection = parent_var.get()
                if parent_selection and parent_selection != 'None':
                    parent_id = int(parent_selection.split(':')[0])

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE organizations
                    SET name = ?, code = ?, description = ?, parent_org_id = ?
                    WHERE org_id = ?
                ''', (
                    name,
                    code_entry.get().strip() or None,
                    desc_text.get('1.0', 'end-1c').strip() or None,
                    parent_id,
                    org_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Organization updated successfully!")
                dialog.destroy()
                self.load_organizations_list(tree)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update organization: {str(e)}")

        ttk.Button(button_frame, text="Update Organization", command=update_organization).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load organization: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_organization_gui = edit_organization_gui

def toggle_selected_organization(self, tree):
    """Toggle active status of selected organization"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select an organization to toggle")
        return

    org_id = tree.item(selection[0])['values'][0]

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, is_active FROM organizations WHERE org_id = ?', (org_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "Organization not found")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('UPDATE organizations SET is_active = ? WHERE org_id = ?',
                      (new_status, org_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"Organization '{name}' has been {status_text}")
        self.load_organizations_list(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle organization: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_selected_organization = toggle_selected_organization

def view_organizations_gui(self):
    """View organizations"""
    self.manage_organizations_gui()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_organizations_gui = view_organizations_gui

def show_template_management(self):
    """Show template management dialog"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        template_window = tk.Toplevel(self.root)
        template_window.title("Ticket Template Management")
        template_window.geometry("900x550")
        template_window.transient(self.root)

        main_frame = ttk.Frame(template_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Ticket Templates", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Treeview for templates
        columns = ('ID', 'Name', 'Category', 'Priority', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load templates with proper connection handling
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT template_id, name, category, priority, is_active FROM ticket_templates")
            rows = cursor.fetchall()
            for row in rows:
                tree.insert('', 'end', values=(row[0], row[1], row[2], row[3], 'Yes' if row[4] else 'No'))
        finally:
            conn.close()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')

        def add_template():
            self._show_template_form(tree)

        ttk.Button(btn_frame, text="Add Template", command=add_template).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=template_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load template management: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_template_management = show_template_management

def _show_template_form(self, tree):
    """Show form to add new ticket template"""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Ticket Template")
    form_window.geometry("500x450")
    form_window.transient(self.root)
    form_window.grab_set()

    frame = ttk.Frame(form_window, padding="20")
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text="Template Name:").grid(row=0, column=0, sticky='w', pady=5)
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5)

    ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky='w', pady=5)
    category_var = tk.StringVar()
    ttk.Combobox(frame, textvariable=category_var,
                values=['Technical', 'Academic', 'Administrative', 'Financial', 'Other'], width=37).grid(row=1, column=1, pady=5)

    ttk.Label(frame, text="Title Template:").grid(row=2, column=0, sticky='w', pady=5)
    title_var = tk.StringVar()
    ttk.Entry(frame, textvariable=title_var, width=40).grid(row=2, column=1, pady=5)

    ttk.Label(frame, text="Priority:").grid(row=3, column=0, sticky='w', pady=5)
    priority_var = tk.StringVar(value="medium")
    ttk.Combobox(frame, textvariable=priority_var, values=['low', 'medium', 'high'], width=37).grid(row=3, column=1, pady=5)

    ttk.Label(frame, text="Description Template:").grid(row=4, column=0, sticky='nw', pady=5)
    desc_text = scrolledtext.ScrolledText(frame, width=38, height=6)
    desc_text.grid(row=4, column=1, pady=5)

    def save():
        conn = None
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ticket_templates (name, category, title_template, description_template,
                                             priority, is_active, created_by, created_datetime)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (name_var.get(), category_var.get(), title_var.get(), desc_text.get('1.0', 'end').strip(),
                  priority_var.get(), self.current_user.get('username', 'admin'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            template_id = cursor.lastrowid

            tree.insert('', 'end', values=(template_id, name_var.get(), category_var.get(), priority_var.get(), 'Yes'))
            messagebox.showinfo("Success", "Template added successfully!")
            form_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add template: {str(e)}")
        finally:
            if conn:
                conn.close()

    ttk.Button(frame, text="Save", command=save).grid(row=5, column=0, pady=20)
    ttk.Button(frame, text="Cancel", command=form_window.destroy).grid(row=5, column=1, pady=20)

# Attach method to HelpdeskGUI class
HelpdeskGUI._show_template_form = _show_template_form

def manage_ticket_templates_gui(self):
    """Manage ticket templates"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to manage templates.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Ticket Template Management")
    dialog.geometry("900x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Ticket Template Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="➕ Create Template",
              command=lambda: self.create_ticket_template_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="✏️ Edit Template",
              command=lambda: self.edit_selected_template(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔄 Toggle Active",
              command=lambda: self.toggle_selected_template(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self.load_templates_list(tree)).pack(side='left', padx=5)

    # Templates list
    columns = ('ID', 'Name', 'Category', 'Priority', 'Impact', 'Urgency', 'Active')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        width = 80 if col == 'ID' else 150
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    # Scrollbar
    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load templates
    self.load_templates_list(tree)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_ticket_templates_gui = manage_ticket_templates_gui

def load_templates_list(self, tree):
    """Load templates into treeview"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT template_id, name, category, default_priority, default_impact,
                   default_urgency, is_active
            FROM ticket_templates
            ORDER BY category, name
        ''')

        templates = cursor.fetchall()
        conn.close()

        for template in templates:
            tid, name, category, priority, impact, urgency, is_active = template
            active_text = "✓ Yes" if is_active else "✗ No"

            tree.insert('', 'end', values=(
                tid, name, category or 'N/A', priority or 'N/A',
                impact or 'N/A', urgency or 'N/A', active_text
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_templates_list = load_templates_list

def create_ticket_template_gui(self):
    """Create a new ticket template"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Create Ticket Template")
    dialog.geometry("600x700")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Create New Ticket Template",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Form fields
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True)

    # Name
    ttk.Label(form_frame, text="Template Name *").grid(row=0, column=0, sticky='w', pady=5)
    name_entry = ttk.Entry(form_frame, width=40)
    name_entry.grid(row=0, column=1, sticky='ew', pady=5)

    # Description
    ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
    desc_entry = ttk.Entry(form_frame, width=40)
    desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

    # Category
    ttk.Label(form_frame, text="Category *").grid(row=2, column=0, sticky='w', pady=5)
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=38)
    category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                'Account Access', 'Other']
    category_combo.grid(row=2, column=1, sticky='ew', pady=5)

    # Subject Template
    ttk.Label(form_frame, text="Subject Template").grid(row=3, column=0, sticky='nw', pady=5)
    subject_entry = ttk.Entry(form_frame, width=40)
    subject_entry.grid(row=3, column=1, sticky='ew', pady=5)
    ttk.Label(form_frame, text="Use [FIELD_NAME] for placeholders", foreground='gray').grid(
        row=4, column=1, sticky='w')

    # Message Template
    ttk.Label(form_frame, text="Message Template").grid(row=5, column=0, sticky='nw', pady=5)
    message_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
    message_text.grid(row=5, column=1, sticky='ew', pady=5)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text="Default Priority").grid(row=6, column=0, sticky='w', pady=5)
    priority_var = tk.StringVar(value='medium')
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
    priority_combo['values'] = ['low', 'medium', 'high']
    priority_combo.grid(row=6, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Default Impact").grid(row=7, column=0, sticky='w', pady=5)
    impact_var = tk.StringVar(value='low')
    impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
    impact_combo['values'] = ['low', 'medium', 'high']
    impact_combo.grid(row=7, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Default Urgency").grid(row=8, column=0, sticky='w', pady=5)
    urgency_var = tk.StringVar(value='low')
    urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
    urgency_combo['values'] = ['low', 'medium', 'high']
    urgency_combo.grid(row=8, column=1, sticky='w', pady=5)

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def save_template():
        name = name_entry.get().strip()
        category = category_var.get()

        if not name or not category:
            messagebox.showerror("Error", "Name and category are required")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO ticket_templates
                (name, description, category, subject_template, message_template,
                 default_priority, default_impact, default_urgency, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                desc_entry.get().strip(),
                category,
                subject_entry.get().strip(),
                message_text.get('1.0', 'end-1c').strip(),
                priority_var.get(),
                impact_var.get(),
                urgency_var.get(),
                self.current_user.get('id', 0),
                now
            ))

            conn.commit()
            template_id = cursor.lastrowid
            conn.close()

            messagebox.showinfo("Success", f"Template #{template_id} created successfully!")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create template: {str(e)}")

    ttk.Button(button_frame, text="Create Template", command=save_template).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_template_gui = create_ticket_template_gui

def edit_selected_template(self, tree):
    """Edit selected template"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a template to edit")
        return

    template_id = tree.item(selection[0])['values'][0]
    self.edit_ticket_template_gui(template_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_selected_template = edit_selected_template

def edit_ticket_template_gui(self, template_id):
    """Edit an existing ticket template"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM ticket_templates WHERE template_id = ?', (template_id,))
        template = cursor.fetchone()
        conn.close()

        if not template:
            messagebox.showerror("Error", "Template not found")
            return

        # Create edit dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Template #{template_id}")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Edit Template: {template[1]}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        # Form fields (similar to create, but pre-filled)
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Template Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.insert(0, template[1])
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=40)
        desc_entry.insert(0, template[2] or '')
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Category
        ttk.Label(form_frame, text="Category *").grid(row=2, column=0, sticky='w', pady=5)
        category_var = tk.StringVar(value=template[3] or '')
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=38)
        category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                    'Account Access', 'Other']
        category_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Subject Template
        ttk.Label(form_frame, text="Subject Template").grid(row=3, column=0, sticky='nw', pady=5)
        subject_entry = ttk.Entry(form_frame, width=40)
        subject_entry.insert(0, template[4] or '')
        subject_entry.grid(row=3, column=1, sticky='ew', pady=5)

        # Message Template
        ttk.Label(form_frame, text="Message Template").grid(row=4, column=0, sticky='nw', pady=5)
        message_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        message_text.insert('1.0', template[5] or '')
        message_text.grid(row=4, column=1, sticky='ew', pady=5)

        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Default Priority").grid(row=5, column=0, sticky='w', pady=5)
        priority_var = tk.StringVar(value=template[6] or 'medium')
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
        priority_combo['values'] = ['low', 'medium', 'high']
        priority_combo.grid(row=5, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Default Impact").grid(row=6, column=0, sticky='w', pady=5)
        impact_var = tk.StringVar(value=template[7] or 'low')
        impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
        impact_combo['values'] = ['low', 'medium', 'high']
        impact_combo.grid(row=6, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Default Urgency").grid(row=7, column=0, sticky='w', pady=5)
        urgency_var = tk.StringVar(value=template[8] or 'low')
        urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
        urgency_combo['values'] = ['low', 'medium', 'high']
        urgency_combo.grid(row=7, column=1, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def update_template():
            name = name_entry.get().strip()
            category = category_var.get()

            if not name or not category:
                messagebox.showerror("Error", "Name and category are required")
                return

            try:
                from education_system.university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE ticket_templates
                    SET name = ?, description = ?, category = ?, subject_template = ?,
                        message_template = ?, default_priority = ?, default_impact = ?,
                        default_urgency = ?
                    WHERE template_id = ?
                ''', (
                    name,
                    desc_entry.get().strip(),
                    category,
                    subject_entry.get().strip(),
                    message_text.get('1.0', 'end-1c').strip(),
                    priority_var.get(),
                    impact_var.get(),
                    urgency_var.get(),
                    template_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Template updated successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update template: {str(e)}")

        ttk.Button(button_frame, text="Update Template", command=update_template).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_ticket_template_gui = edit_ticket_template_gui

def toggle_selected_template(self, tree):
    """Toggle active status of selected template"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a template to toggle")
        return

    template_id = tree.item(selection[0])['values'][0]
    self.toggle_ticket_template_gui(template_id, tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_selected_template = toggle_selected_template

def toggle_ticket_template_gui(self, template_id, tree):
    """Toggle template active status"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, is_active FROM ticket_templates WHERE template_id = ?',
                      (template_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "Template not found")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('UPDATE ticket_templates SET is_active = ? WHERE template_id = ?',
                      (new_status, template_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"Template '{name}' has been {status_text}")

        # Refresh tree
        self.load_templates_list(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_ticket_template_gui = toggle_ticket_template_gui

def view_ticket_templates_gui(self):
    """View ticket templates (read-only)"""
    self.manage_ticket_templates_gui()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_ticket_templates_gui = view_ticket_templates_gui

