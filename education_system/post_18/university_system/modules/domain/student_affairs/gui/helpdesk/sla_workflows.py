import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
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
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk import (
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
                description TEXT NOT NULL,
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
                file_path TEXT,
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
                priority TEXT,
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
            from education_system.post_18.university_system.modules.domain.student_affairs.services.helpdesk import (
                setup_enhanced_helpdesk_permissions as service_setup_permissions
            )
            service_setup_permissions()
        except ImportError:
            # If service layer is not available, do basic setup
            print("Warning: Helpdesk service layer not available. Setting up basic permissions...")
            try:
                from education_system.post_18.university_system.infrastructure.database.db import get_connection
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

from education_system.post_18.university_system.modules.domain.student_affairs.gui.helpdesk.base import HelpdeskGUI

def show_sla_management(self):
    """Show SLA management dialog"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        sla_window = tk.Toplevel(self.root)
        sla_window.title("SLA Policy Management")
        sla_window.geometry("800x500")
        sla_window.transient(self.root)

        main_frame = ttk.Frame(sla_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="SLA Policies", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Treeview for SLA policies
        columns = ('ID', 'Name', 'Priority', 'Response Hours', 'Resolution Hours', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load SLA policies with proper connection handling
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT sla_id, name, priority, first_response_hours, resolution_hours, is_active FROM sla_policies")
            rows = cursor.fetchall()
            for row in rows:
                tree.insert('', 'end', values=(row[0], row[1], row[2], row[3], row[4], 'Yes' if row[5] else 'No'))
        finally:
            conn.close()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')

        def add_sla():
            self._show_sla_form(tree)

        ttk.Button(btn_frame, text="Add SLA Policy", command=add_sla).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=sla_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load SLA management: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_sla_management = show_sla_management

def _show_sla_form(self, tree):
    """Show form to add new SLA policy"""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add SLA Policy")
    form_window.geometry("400x350")
    form_window.transient(self.root)
    form_window.grab_set()

    frame = ttk.Frame(form_window, padding="20")
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='w', pady=5)
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

    ttk.Label(frame, text="Priority:").grid(row=1, column=0, sticky='w', pady=5)
    priority_var = tk.StringVar(value="medium")
    ttk.Combobox(frame, textvariable=priority_var, values=['low', 'medium', 'high', 'critical'], width=27).grid(row=1, column=1, pady=5)

    ttk.Label(frame, text="Response Hours:").grid(row=2, column=0, sticky='w', pady=5)
    response_var = tk.StringVar(value="4")
    ttk.Entry(frame, textvariable=response_var, width=30).grid(row=2, column=1, pady=5)

    ttk.Label(frame, text="Resolution Hours:").grid(row=3, column=0, sticky='w', pady=5)
    resolution_var = tk.StringVar(value="24")
    ttk.Entry(frame, textvariable=resolution_var, width=30).grid(row=3, column=1, pady=5)

    def save():
        conn = None
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sla_policies (name, priority, first_response_hours, resolution_hours, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (name_var.get(), priority_var.get(), int(response_var.get()), int(resolution_var.get()),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            sla_id = cursor.lastrowid

            tree.insert('', 'end', values=(sla_id, name_var.get(), priority_var.get(),
                                           response_var.get(), resolution_var.get(), 'Yes'))
            messagebox.showinfo("Success", "SLA Policy added successfully!")
            form_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add SLA: {str(e)}")
        finally:
            if conn:
                conn.close()

    ttk.Button(frame, text="Save", command=save).grid(row=4, column=0, pady=20)
    ttk.Button(frame, text="Cancel", command=form_window.destroy).grid(row=4, column=1, pady=20)

# Attach method to HelpdeskGUI class
HelpdeskGUI._show_sla_form = _show_sla_form

def manage_sla_policies_gui(self):
    """Manage SLA policies"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to manage SLA policies.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("SLA Policy Management")
    dialog.geometry("1100x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="SLA Policy Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="➕ Create SLA Policy",
              command=lambda: self.create_sla_policy_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="✏️ Edit SLA Policy",
              command=lambda: self.edit_selected_sla(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔄 Toggle Active",
              command=lambda: self.toggle_selected_sla(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="📊 SLA Report",
              command=lambda: self.generate_sla_compliance_report_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="⚠️ Check Overdue",
              command=lambda: self.check_overdue_tickets_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self.load_sla_policies_list(tree)).pack(side='left', padx=5)

    # SLA policies list
    columns = ('ID', 'Name', 'P/I/U', 'Response (h)', 'Resolution (h)',
              'Escalation (h)', 'Business Hours', 'Active')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        width = 60 if col == 'ID' else 120
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    # Scrollbar
    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load SLA policies
    self.load_sla_policies_list(tree)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_sla_policies_gui = manage_sla_policies_gui

def load_sla_policies_list(self, tree):
    """Load SLA policies into treeview"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT sla_id, name, priority, impact, urgency, first_response_hours,
                   resolution_hours, escalation_hours, business_hours_only, is_active
            FROM sla_policies
            ORDER BY priority, impact, urgency
        ''')

        policies = cursor.fetchall()
        conn.close()

        for policy in policies:
            sla_id, name, priority, impact, urgency, response_h, resolution_h, escalation_h, business_only, is_active = policy
            p_i_u = f"{priority}/{impact}/{urgency}"
            business_text = "Yes" if business_only else "No"
            active_text = "✓ Yes" if is_active else "✗ No"

            tree.insert('', 'end', values=(
                sla_id, name, p_i_u, response_h, resolution_h,
                escalation_h, business_text, active_text
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load SLA policies: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_sla_policies_list = load_sla_policies_list

def create_sla_policy_gui(self):
    """Create a new SLA policy"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Create SLA Policy")
    dialog.geometry("500x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Create New SLA Policy",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Form fields
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True)

    # Name
    ttk.Label(form_frame, text="Policy Name *").grid(row=0, column=0, sticky='w', pady=5)
    name_entry = ttk.Entry(form_frame, width=35)
    name_entry.grid(row=0, column=1, sticky='ew', pady=5)

    # Description
    ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
    desc_entry = ttk.Entry(form_frame, width=35)
    desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text="Priority *").grid(row=2, column=0, sticky='w', pady=5)
    priority_var = tk.StringVar(value='medium')
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
    priority_combo['values'] = ['low', 'medium', 'high']
    priority_combo.grid(row=2, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Impact *").grid(row=3, column=0, sticky='w', pady=5)
    impact_var = tk.StringVar(value='low')
    impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
    impact_combo['values'] = ['low', 'medium', 'high']
    impact_combo.grid(row=3, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Urgency *").grid(row=4, column=0, sticky='w', pady=5)
    urgency_var = tk.StringVar(value='low')
    urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
    urgency_combo['values'] = ['low', 'medium', 'high']
    urgency_combo.grid(row=4, column=1, sticky='w', pady=5)

    # Time targets
    ttk.Label(form_frame, text="First Response (hours) *").grid(row=5, column=0, sticky='w', pady=5)
    response_entry = ttk.Entry(form_frame, width=15)
    response_entry.insert(0, '4')
    response_entry.grid(row=5, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Resolution (hours) *").grid(row=6, column=0, sticky='w', pady=5)
    resolution_entry = ttk.Entry(form_frame, width=15)
    resolution_entry.insert(0, '24')
    resolution_entry.grid(row=6, column=1, sticky='w', pady=5)

    ttk.Label(form_frame, text="Escalation (hours) *").grid(row=7, column=0, sticky='w', pady=5)
    escalation_entry = ttk.Entry(form_frame, width=15)
    escalation_entry.insert(0, '8')
    escalation_entry.grid(row=7, column=1, sticky='w', pady=5)

    # Business hours only
    business_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(form_frame, text="Business hours only",
                   variable=business_var).grid(row=8, column=1, sticky='w', pady=5)

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def save_sla():
        name = name_entry.get().strip()

        if not name:
            messagebox.showerror("Error", "Policy name is required")
            return

        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection

            first_response = int(response_entry.get())
            resolution = int(resolution_entry.get())
            escalation = int(escalation_entry.get())

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO sla_policies
                (name, description, priority, impact, urgency, first_response_hours,
                 resolution_hours, escalation_hours, business_hours_only, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                desc_entry.get().strip(),
                priority_var.get(),
                impact_var.get(),
                urgency_var.get(),
                first_response,
                resolution,
                escalation,
                business_var.get(),
                now
            ))

            conn.commit()
            sla_id = cursor.lastrowid
            conn.close()

            messagebox.showinfo("Success", f"SLA Policy #{sla_id} created successfully!")
            dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Time values must be numbers")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create SLA policy: {str(e)}")

    ttk.Button(button_frame, text="Create SLA Policy", command=save_sla).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_sla_policy_gui = create_sla_policy_gui

def edit_selected_sla(self, tree):
    """Edit selected SLA policy"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select an SLA policy to edit")
        return

    sla_id = tree.item(selection[0])['values'][0]
    self.edit_sla_policy_gui(sla_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_selected_sla = edit_selected_sla

def edit_sla_policy_gui(self, sla_id):
    """Edit existing SLA policy"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, description, priority, impact, urgency,
                   first_response_hours, resolution_hours, escalation_hours,
                   business_hours_only, is_active
            FROM sla_policies WHERE sla_id = ?
        ''', (sla_id,))
        sla = cursor.fetchone()
        conn.close()

        if not sla:
            messagebox.showerror("Error", "SLA policy not found")
            return

        (name, description, priority, impact, urgency, response_h,
         resolution_h, escalation_h, business_only, is_active) = sla

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit SLA Policy #{sla_id}")
        dialog.geometry("500x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Edit SLA Policy: {name}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Policy Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=35)
        name_entry.insert(0, name or '')
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=35)
        desc_entry.insert(0, description or '')
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Priority, Impact, Urgency
        ttk.Label(form_frame, text="Priority *").grid(row=2, column=0, sticky='w', pady=5)
        priority_var = tk.StringVar(value=priority or 'medium')
        priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
        priority_combo['values'] = ['low', 'medium', 'high']
        priority_combo.grid(row=2, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Impact *").grid(row=3, column=0, sticky='w', pady=5)
        impact_var = tk.StringVar(value=impact or 'low')
        impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
        impact_combo['values'] = ['low', 'medium', 'high']
        impact_combo.grid(row=3, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Urgency *").grid(row=4, column=0, sticky='w', pady=5)
        urgency_var = tk.StringVar(value=urgency or 'low')
        urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
        urgency_combo['values'] = ['low', 'medium', 'high']
        urgency_combo.grid(row=4, column=1, sticky='w', pady=5)

        # Time targets
        ttk.Label(form_frame, text="First Response (hours) *").grid(row=5, column=0, sticky='w', pady=5)
        response_entry = ttk.Entry(form_frame, width=15)
        response_entry.insert(0, str(response_h or 4))
        response_entry.grid(row=5, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Resolution (hours) *").grid(row=6, column=0, sticky='w', pady=5)
        resolution_entry = ttk.Entry(form_frame, width=15)
        resolution_entry.insert(0, str(resolution_h or 24))
        resolution_entry.grid(row=6, column=1, sticky='w', pady=5)

        ttk.Label(form_frame, text="Escalation (hours) *").grid(row=7, column=0, sticky='w', pady=5)
        escalation_entry = ttk.Entry(form_frame, width=15)
        escalation_entry.insert(0, str(escalation_h or 8))
        escalation_entry.grid(row=7, column=1, sticky='w', pady=5)

        # Business hours only
        business_var = tk.BooleanVar(value=bool(business_only))
        ttk.Checkbutton(form_frame, text="Business hours only",
                       variable=business_var).grid(row=8, column=1, sticky='w', pady=5)

        # Active status
        active_var = tk.BooleanVar(value=bool(is_active))
        ttk.Checkbutton(form_frame, text="Policy Active",
                       variable=active_var).grid(row=9, column=1, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def update_sla():
            new_name = name_entry.get().strip()

            if not new_name:
                messagebox.showerror("Error", "Policy name is required")
                return

            try:
                first_response = int(response_entry.get())
                resolution = int(resolution_entry.get())
                escalation = int(escalation_entry.get())

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE sla_policies
                    SET name = ?, description = ?, priority = ?, impact = ?, urgency = ?,
                        first_response_hours = ?, resolution_hours = ?, escalation_hours = ?,
                        business_hours_only = ?, is_active = ?
                    WHERE sla_id = ?
                ''', (
                    new_name,
                    desc_entry.get().strip() or None,
                    priority_var.get(),
                    impact_var.get(),
                    urgency_var.get(),
                    first_response,
                    resolution,
                    escalation,
                    1 if business_var.get() else 0,
                    1 if active_var.get() else 0,
                    sla_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"SLA Policy #{sla_id} updated successfully!")
                dialog.destroy()

            except ValueError:
                messagebox.showerror("Error", "Time values must be numbers")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update SLA policy: {str(e)}")

        ttk.Button(button_frame, text="Update SLA Policy", command=update_sla).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load SLA policy: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_sla_policy_gui = edit_sla_policy_gui

def toggle_selected_sla(self, tree):
    """Toggle active status of selected SLA policy"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select an SLA policy to toggle")
        return

    sla_id = tree.item(selection[0])['values'][0]
    self.toggle_sla_policy_gui(sla_id, tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_selected_sla = toggle_selected_sla

def toggle_sla_policy_gui(self, sla_id, tree):
    """Toggle SLA policy active status"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, is_active FROM sla_policies WHERE sla_id = ?', (sla_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "SLA policy not found")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('UPDATE sla_policies SET is_active = ? WHERE sla_id = ?',
                      (new_status, sla_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"SLA Policy '{name}' has been {status_text}")

        # Refresh tree
        self.load_sla_policies_list(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle SLA policy: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_sla_policy_gui = toggle_sla_policy_gui

def check_overdue_tickets_gui(self):
    """Check for overdue tickets based on SLA"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now()

        cursor.execute('''
            SELECT ticket_id, subject, due_date, JULIANDAY(?) - JULIANDAY(due_date) as days_overdue
            FROM support_tickets
            WHERE status NOT IN ('resolved', 'closed')
              AND due_date IS NOT NULL
              AND due_date < ?
            ORDER BY days_overdue DESC
        ''', (now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))

        overdue = cursor.fetchall()
        conn.close()

        if not overdue:
            messagebox.showinfo("SLA Check", "No overdue tickets found!")
            return

        # Create results window
        result_window = tk.Toplevel(self.root)
        result_window.title("Overdue Tickets")
        result_window.geometry("800x400")

        main_frame = ttk.Frame(result_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"⚠️ {len(overdue)} Overdue Tickets Found",
                 font=('TkDefaultFont', 12, 'bold'), foreground='red').pack(pady=(0, 10))

        columns = ('Ticket ID', 'Subject', 'Due Date', 'Days Overdue')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        tree.pack(fill='both', expand=True)

        for ticket_id, subject, due_date, days_overdue in overdue:
            tree.insert('', 'end', values=(
                ticket_id, subject[:50], due_date, f"{days_overdue:.1f}"
            ))

        ttk.Button(main_frame, text="Close", command=result_window.destroy).pack(pady=10)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to check overdue tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.check_overdue_tickets_gui = check_overdue_tickets_gui

def generate_sla_compliance_report_gui(self):
    """Generate SLA compliance report"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Get SLA compliance metrics
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN resolved_at <= due_date THEN 1 END) as within_sla,
                COUNT(CASE WHEN resolved_at > due_date THEN 1 END) as breached,
                COUNT(CASE WHEN resolved_at IS NULL AND due_date < datetime('now') THEN 1 END) as at_risk
            FROM support_tickets
            WHERE due_date IS NOT NULL
        ''')

        metrics = cursor.fetchone()
        conn.close()

        if not metrics or metrics[0] == 0:
            messagebox.showinfo("SLA Report", "No SLA data available")
            return

        total, within_sla, breached, at_risk = metrics
        compliance_rate = (within_sla / total * 100) if total > 0 else 0

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title("SLA Compliance Report")
        report_window.geometry("600x400")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="📊 SLA Compliance Report",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

        # Metrics display
        metrics_frame = ttk.LabelFrame(main_frame, text="Compliance Metrics", padding="20")
        metrics_frame.pack(fill='both', expand=True)

        metrics_text = f"""
Total Tickets with SLA: {total}
Within SLA: {within_sla} ({compliance_rate:.1f}%)
Breached SLA: {breached}
At Risk (Overdue): {at_risk}

Overall Compliance Rate: {compliance_rate:.1f}%
"""

        ttk.Label(metrics_frame, text=metrics_text, font=('TkDefaultFont', 11),
                 justify='left').pack(anchor='w')

        # Color-coded status
        if compliance_rate >= 95:
            status_color = 'green'
            status_text = "✓ Excellent"
        elif compliance_rate >= 80:
            status_color = 'orange'
            status_text = "⚠ Needs Improvement"
        else:
            status_color = 'red'
            status_text = "✗ Critical"

        ttk.Label(metrics_frame, text=f"Status: {status_text}",
                 font=('TkDefaultFont', 12, 'bold'),
                 foreground=status_color).pack(pady=(10, 0))

        ttk.Button(main_frame, text="Close", command=report_window.destroy).pack(pady=20)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate SLA report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_sla_compliance_report_gui = generate_sla_compliance_report_gui

def view_sla_policies_gui(self):
    """View SLA policies (read-only)"""
    self.manage_sla_policies_gui()

# END OF SLA POLICY MANAGEMENT FUNCTIONS
# ============================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_sla_policies_gui = view_sla_policies_gui

def show_workflow_management(self):
    """Show workflow management dialog"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        workflow_window = tk.Toplevel(self.root)
        workflow_window.title("Workflow Management")
        workflow_window.geometry("900x500")
        workflow_window.transient(self.root)

        main_frame = ttk.Frame(workflow_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Ticket Workflows", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Treeview for workflows
        columns = ('ID', 'Name', 'Trigger Type', 'Description', 'Active')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=160)
        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load workflows with proper connection handling
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT workflow_id, name, trigger_type, description, is_active FROM ticket_workflows")
            rows = cursor.fetchall()
            for row in rows:
                tree.insert('', 'end', values=(row[0], row[1], row[2], row[3] or '', 'Yes' if row[4] else 'No'))
        finally:
            conn.close()

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')

        def add_workflow():
            self._show_workflow_form(tree)

        ttk.Button(btn_frame, text="Add Workflow", command=add_workflow).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=workflow_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load workflow management: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_workflow_management = show_workflow_management

def _show_workflow_form(self, tree):
    """Show form to add new workflow"""
    form_window = tk.Toplevel(self.root)
    form_window.title("Add Workflow")
    form_window.geometry("450x350")
    form_window.transient(self.root)
    form_window.grab_set()

    frame = ttk.Frame(form_window, padding="20")
    frame.pack(fill='both', expand=True)

    ttk.Label(frame, text="Workflow Name:").grid(row=0, column=0, sticky='w', pady=5)
    name_var = tk.StringVar()
    ttk.Entry(frame, textvariable=name_var, width=30).grid(row=0, column=1, pady=5)

    ttk.Label(frame, text="Trigger Type:").grid(row=1, column=0, sticky='w', pady=5)
    trigger_var = tk.StringVar()
    ttk.Combobox(frame, textvariable=trigger_var,
                values=['on_create', 'on_update', 'on_close', 'on_escalate', 'scheduled'], width=27).grid(row=1, column=1, pady=5)

    ttk.Label(frame, text="Description:").grid(row=2, column=0, sticky='w', pady=5)
    desc_var = tk.StringVar()
    ttk.Entry(frame, textvariable=desc_var, width=30).grid(row=2, column=1, pady=5)

    def save():
        conn = None
        try:
            from education_system.post_18.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("PRAGMA busy_timeout = 5000")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ticket_workflows (name, trigger_type, description, is_active, created_by, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (name_var.get(), trigger_var.get(), desc_var.get(),
                  self.current_user.get('id', 0), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            workflow_id = cursor.lastrowid

            tree.insert('', 'end', values=(workflow_id, name_var.get(), trigger_var.get(), desc_var.get(), 'Yes'))
            messagebox.showinfo("Success", "Workflow added successfully!")
            form_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add workflow: {str(e)}")
        finally:
            if conn:
                conn.close()

    ttk.Button(frame, text="Save", command=save).grid(row=3, column=0, pady=20)
    ttk.Button(frame, text="Cancel", command=form_window.destroy).grid(row=3, column=1, pady=20)

# Attach method to HelpdeskGUI class
HelpdeskGUI._show_workflow_form = _show_workflow_form

def manage_workflows_gui(self):
    """Manage automated workflows"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to manage workflows.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("Workflow Management")
    dialog.geometry("1000x600")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Automated Workflow Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="➕ Create Workflow",
              command=lambda: self.create_workflow_gui()).pack(side='left', padx=5)
    ttk.Button(toolbar, text="✏️ Edit Workflow",
              command=lambda: self.edit_selected_workflow(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔄 Toggle Active",
              command=lambda: self.toggle_selected_workflow(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self.load_workflows_list(tree)).pack(side='left', padx=5)

    # Workflows list
    columns = ('ID', 'Name', 'Trigger Type', 'Description', 'Active')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        width = 60 if col == 'ID' else 200
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    # Scrollbar
    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load workflows
    self.load_workflows_list(tree)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.manage_workflows_gui = manage_workflows_gui

def load_workflows_list(self, tree):
    """Load workflows into treeview"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT workflow_id, name, trigger_type, description, is_active
            FROM ticket_workflows
            ORDER BY trigger_type, name
        ''')

        workflows = cursor.fetchall()
        conn.close()

        for workflow in workflows:
            wf_id, name, trigger_type, description, is_active = workflow
            active_text = "✓ Yes" if is_active else "✗ No"

            tree.insert('', 'end', values=(
                wf_id, name, trigger_type or 'N/A',
                (description or 'N/A')[:50], active_text
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load workflows: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_workflows_list = load_workflows_list

def create_workflow_gui(self):
    """Create a new automated workflow"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Create Workflow")
    dialog.geometry("600x700")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Create New Automated Workflow",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Form fields
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True)

    # Name
    ttk.Label(form_frame, text="Workflow Name *").grid(row=0, column=0, sticky='w', pady=5)
    name_entry = ttk.Entry(form_frame, width=40)
    name_entry.grid(row=0, column=1, sticky='ew', pady=5)

    # Description
    ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
    desc_entry = ttk.Entry(form_frame, width=40)
    desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

    # Trigger Type
    ttk.Label(form_frame, text="Trigger Type *").grid(row=2, column=0, sticky='w', pady=5)
    trigger_var = tk.StringVar()
    trigger_combo = ttk.Combobox(form_frame, textvariable=trigger_var, state="readonly", width=38)
    trigger_combo['values'] = ['ticket_created', 'ticket_updated', 'status_changed',
                               'priority_changed', 'assigned', 'overdue']
    trigger_combo.grid(row=2, column=1, sticky='ew', pady=5)

    # Conditions (JSON)
    ttk.Label(form_frame, text="Conditions (JSON)").grid(row=3, column=0, sticky='nw', pady=5)
    conditions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
    conditions_text.insert('1.0', '{\n  "priority": "high",\n  "category": "Technical Support"\n}')
    conditions_text.grid(row=3, column=1, sticky='ew', pady=5)

    # Actions (JSON)
    ttk.Label(form_frame, text="Actions (JSON) *").grid(row=4, column=0, sticky='nw', pady=5)
    actions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
    actions_text.insert('1.0', '{\n  "assign_to_department": "IT Support",\n  "set_priority": "high"\n}')
    actions_text.grid(row=4, column=1, sticky='ew', pady=5)

    ttk.Label(form_frame, text="Actions: assign_to_department, set_priority, change_status",
             foreground='gray', font=('TkDefaultFont', 8)).grid(row=5, column=1, sticky='w')

    form_frame.columnconfigure(1, weight=1)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def save_workflow():
        name = name_entry.get().strip()
        trigger_type = trigger_var.get()

        if not name or not trigger_type:
            messagebox.showerror("Error", "Name and trigger type are required")
            return

        try:
            import json
            from education_system.post_18.university_system.infrastructure.database.db import get_connection

            # Validate JSON
            conditions_json = conditions_text.get('1.0', 'end-1c').strip()
            actions_json = actions_text.get('1.0', 'end-1c').strip()

            if conditions_json:
                json.loads(conditions_json)
            if actions_json:
                json.loads(actions_json)

            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO ticket_workflows
                (name, description, trigger_type, trigger_conditions, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                name,
                desc_entry.get().strip(),
                trigger_type,
                conditions_json if conditions_json else None,
                actions_json if actions_json else None,
                now
            ))

            conn.commit()
            workflow_id = cursor.lastrowid
            conn.close()

            messagebox.showinfo("Success", f"Workflow #{workflow_id} created successfully!")
            dialog.destroy()

        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create workflow: {str(e)}")

    ttk.Button(button_frame, text="Create Workflow", command=save_workflow).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_workflow_gui = create_workflow_gui

def edit_selected_workflow(self, tree):
    """Edit selected workflow"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a workflow to edit")
        return

    workflow_id = tree.item(selection[0])['values'][0]
    self.edit_workflow_gui(workflow_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_selected_workflow = edit_selected_workflow

def edit_workflow_gui(self, workflow_id):
    """Edit existing workflow"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        import json

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, description, trigger_type, trigger_conditions, actions, is_active
            FROM ticket_workflows WHERE workflow_id = ?
        ''', (workflow_id,))
        workflow = cursor.fetchone()
        conn.close()

        if not workflow:
            messagebox.showerror("Error", "Workflow not found")
            return

        name, description, trigger_type, trigger_conditions, actions, is_active = workflow

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Workflow #{workflow_id}")
        dialog.geometry("600x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Edit Workflow: {name}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Name
        ttk.Label(form_frame, text="Workflow Name *").grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(form_frame, width=40)
        name_entry.insert(0, name or '')
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Description
        ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='w', pady=5)
        desc_entry = ttk.Entry(form_frame, width=40)
        desc_entry.insert(0, description or '')
        desc_entry.grid(row=1, column=1, sticky='ew', pady=5)

        # Trigger Type
        ttk.Label(form_frame, text="Trigger Type *").grid(row=2, column=0, sticky='w', pady=5)
        trigger_var = tk.StringVar(value=trigger_type or '')
        trigger_combo = ttk.Combobox(form_frame, textvariable=trigger_var, state="readonly", width=38)
        trigger_combo['values'] = ['ticket_created', 'ticket_updated', 'status_changed',
                                   'priority_changed', 'assigned', 'overdue']
        trigger_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Conditions (JSON)
        ttk.Label(form_frame, text="Conditions (JSON)").grid(row=3, column=0, sticky='nw', pady=5)
        conditions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        if trigger_conditions:
            try:
                formatted = json.dumps(json.loads(trigger_conditions), indent=2)
                conditions_text.insert('1.0', formatted)
            except (json.JSONDecodeError, TypeError):
                conditions_text.insert('1.0', trigger_conditions or '')
        conditions_text.grid(row=3, column=1, sticky='ew', pady=5)

        # Actions (JSON)
        ttk.Label(form_frame, text="Actions (JSON) *").grid(row=4, column=0, sticky='nw', pady=5)
        actions_text = scrolledtext.ScrolledText(form_frame, height=8, width=40)
        if actions:
            try:
                formatted = json.dumps(json.loads(actions), indent=2)
                actions_text.insert('1.0', formatted)
            except (json.JSONDecodeError, TypeError):
                actions_text.insert('1.0', actions or '')
        actions_text.grid(row=4, column=1, sticky='ew', pady=5)

        ttk.Label(form_frame, text="Actions: assign_to_department, set_priority, change_status",
                 foreground='gray', font=('TkDefaultFont', 8)).grid(row=5, column=1, sticky='w')

        # Active status
        active_var = tk.BooleanVar(value=bool(is_active))
        ttk.Checkbutton(form_frame, text="Workflow Active",
                       variable=active_var).grid(row=6, column=1, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def update_workflow():
            new_name = name_entry.get().strip()
            new_trigger = trigger_var.get()

            if not new_name or not new_trigger:
                messagebox.showerror("Error", "Name and trigger type are required")
                return

            try:
                conditions_json = conditions_text.get('1.0', 'end-1c').strip()
                actions_json = actions_text.get('1.0', 'end-1c').strip()

                if conditions_json:
                    json.loads(conditions_json)
                if actions_json:
                    json.loads(actions_json)

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE ticket_workflows
                    SET name = ?, description = ?, trigger_type = ?,
                        trigger_conditions = ?, actions = ?, is_active = ?
                    WHERE workflow_id = ?
                ''', (
                    new_name,
                    desc_entry.get().strip() or None,
                    new_trigger,
                    conditions_json if conditions_json else None,
                    actions_json if actions_json else None,
                    1 if active_var.get() else 0,
                    workflow_id
                ))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Workflow #{workflow_id} updated successfully!")
                dialog.destroy()

            except json.JSONDecodeError as e:
                messagebox.showerror("Error", f"Invalid JSON: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update workflow: {str(e)}")

        ttk.Button(button_frame, text="Update Workflow", command=update_workflow).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load workflow: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.edit_workflow_gui = edit_workflow_gui

def toggle_selected_workflow(self, tree):
    """Toggle active status of selected workflow"""
    selection = tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select a workflow to toggle")
        return

    workflow_id = tree.item(selection[0])['values'][0]
    self.toggle_workflow_gui(workflow_id, tree)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_selected_workflow = toggle_selected_workflow

def toggle_workflow_gui(self, workflow_id, tree):
    """Toggle workflow active status"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, is_active FROM ticket_workflows WHERE workflow_id = ?',
                      (workflow_id,))
        result = cursor.fetchone()

        if not result:
            messagebox.showerror("Error", "Workflow not found")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('UPDATE ticket_workflows SET is_active = ? WHERE workflow_id = ?',
                      (new_status, workflow_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Success", f"Workflow '{name}' has been {status_text}")

        # Refresh tree
        self.load_workflows_list(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to toggle workflow: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_workflow_gui = toggle_workflow_gui

def run_ticket_workflows_gui(self, ticket_id, trigger_type):
    """Run automated workflows based on triggers"""
    try:
        import json
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Get active workflows for this trigger
        cursor.execute('''
            SELECT workflow_id, name, trigger_conditions, actions
            FROM ticket_workflows
            WHERE trigger_type = ? AND is_active = 1
        ''', (trigger_type,))

        workflows = cursor.fetchall()
        executed_count = 0

        for workflow in workflows:
            workflow_id, name, conditions_json, actions_json = workflow

            try:
                conditions = json.loads(conditions_json) if conditions_json else {}
                actions = json.loads(actions_json) if actions_json else {}

                # Check conditions and execute
                if self.check_workflow_conditions_gui(ticket_id, conditions):
                    self.execute_workflow_actions_gui(ticket_id, actions)
                    executed_count += 1

            except json.JSONDecodeError:
                pass

        conn.close()

    except Exception as e:
        print(f"Error running workflows: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.run_ticket_workflows_gui = run_ticket_workflows_gui

def check_workflow_conditions_gui(self, ticket_id, conditions):
    """Check if workflow conditions are met"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        if not ticket:
            conn.close()
            return False

        # Convert to dict
        columns = [desc[0] for desc in cursor.description]
        ticket_dict = dict(zip(columns, ticket))
        conn.close()

        # Check each condition
        for field, expected_value in conditions.items():
            if field in ticket_dict:
                if ticket_dict[field] != expected_value:
                    return False

        return True

    except Exception:
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.check_workflow_conditions_gui = check_workflow_conditions_gui

def execute_workflow_actions_gui(self, ticket_id, actions):
    """Execute workflow actions"""
    try:
        from education_system.post_18.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for action, value in actions.items():
            if action == 'set_priority':
                cursor.execute('''
                    UPDATE support_tickets SET priority = ?, updated_at = ? WHERE ticket_id = ?
                ''', (value, now, ticket_id))
            elif action == 'change_status':
                cursor.execute('''
                    UPDATE support_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?
                ''', (value, now, ticket_id))

        conn.commit()
        conn.close()

    except Exception:
        pass

# Attach method to HelpdeskGUI class
HelpdeskGUI.execute_workflow_actions_gui = execute_workflow_actions_gui

def view_workflows_gui(self):
    """View workflows (read-only)"""
    self.manage_workflows_gui()

# END OF WORKFLOW AUTOMATION FUNCTIONS
# ============================================================================

# ============================================================================
# SLA POLICY MANAGEMENT FUNCTIONS (7 FUNCTIONS)
# ============================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_workflows_gui = view_workflows_gui

