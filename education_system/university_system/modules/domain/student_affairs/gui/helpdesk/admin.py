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

from .base import HelpdeskGUI

def create_admin_tab(self):
    """Create admin tab"""
    admin_frame = ttk.Frame(self.notebook)
    self.notebook.add(admin_frame, text="Administration")

    # Create notebook for admin sections
    admin_notebook = ttk.Notebook(admin_frame)
    admin_notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # System Management tab
    self.create_system_management_tab(admin_notebook)

    # User Management tab
    self.create_user_management_tab(admin_notebook)

    # Reports tab
    self.create_reports_tab(admin_notebook)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_admin_tab = create_admin_tab

def create_system_management_tab(self, parent):
    """Create system management tab"""
    sys_frame = ttk.Frame(parent)
    parent.add(sys_frame, text="System")

    # System management options
    options_frame = ttk.LabelFrame(sys_frame, text="System Management")
    options_frame.pack(fill='x', padx=10, pady=10)

    # SLA Management
    sla_frame = ttk.Frame(options_frame)
    sla_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(sla_frame, text="SLA Policies:", style='Heading.TLabel').pack(side='left')
    ttk.Button(sla_frame, text="Manage SLAs", command=self.show_sla_management).pack(side='right')

    # Template Management
    template_frame = ttk.Frame(options_frame)
    template_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(template_frame, text="Ticket Templates:", style='Heading.TLabel').pack(side='left')
    ttk.Button(template_frame, text="Manage Templates", command=self.show_template_management).pack(side='right')

    # Department Management
    dept_frame = ttk.Frame(options_frame)
    dept_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(dept_frame, text="Departments:", style='Heading.TLabel').pack(side='left')
    ttk.Button(dept_frame, text="Manage Departments", command=self.show_department_management).pack(side='right')

    # Workflow Management
    workflow_frame = ttk.Frame(options_frame)
    workflow_frame.pack(fill='x', padx=5, pady=5)
    ttk.Label(workflow_frame, text="Workflows:", style='Heading.TLabel').pack(side='left')
    ttk.Button(workflow_frame, text="Manage Workflows", command=self.show_workflow_management).pack(side='right')

    # System Maintenance
    maintenance_frame = ttk.LabelFrame(sys_frame, text="System Maintenance")
    maintenance_frame.pack(fill='x', padx=10, pady=10)

    maint_grid = ttk.Frame(maintenance_frame)
    maint_grid.pack(fill='x', padx=5, pady=5)

    ttk.Button(maint_grid, text="Database Cleanup", command=self.show_database_cleanup).grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(maint_grid, text="Backup Database", command=self.backup_database).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(maint_grid, text="Check Integrity", command=self.check_data_integrity).grid(row=1, column=0, padx=5, pady=5)
    ttk.Button(maint_grid, text="Export Data", command=self.show_export_dialog).grid(row=1, column=1, padx=5, pady=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_system_management_tab = create_system_management_tab

def show_system_management(self):
    """Switch to system management"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Administration':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_system_management = show_system_management

def show_settings(self):
    """Show system settings dialog"""
    settings_window = tk.Toplevel(self.root)
    settings_window.title("System Settings")
    settings_window.geometry("700x550")
    settings_window.transient(self.root)
    settings_window.grab_set()

    # Settings notebook
    settings_notebook = ttk.Notebook(settings_window)
    settings_notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # === General Settings ===
    general_frame = ttk.Frame(settings_notebook, padding="10")
    settings_notebook.add(general_frame, text="General")

    # System Name
    ttk.Label(general_frame, text="System Name:").grid(row=0, column=0, sticky='w', pady=5)
    self.setting_system_name = tk.StringVar(value="University Helpdesk")
    ttk.Entry(general_frame, textvariable=self.setting_system_name, width=40).grid(row=0, column=1, pady=5, padx=5)

    # Default Ticket Priority
    ttk.Label(general_frame, text="Default Priority:").grid(row=1, column=0, sticky='w', pady=5)
    self.setting_default_priority = tk.StringVar(value="medium")
    ttk.Combobox(general_frame, textvariable=self.setting_default_priority,
            values=['low', 'medium', 'high'], state='readonly', width=37).grid(row=1, column=1, pady=5, padx=5)

    # Auto-assign tickets
    ttk.Label(general_frame, text="Auto-assign Tickets:").grid(row=2, column=0, sticky='w', pady=5)
    self.setting_auto_assign = tk.BooleanVar(value=False)
    ttk.Checkbutton(general_frame, variable=self.setting_auto_assign).grid(row=2, column=1, sticky='w', pady=5, padx=5)

    # Tickets per page
    ttk.Label(general_frame, text="Tickets Per Page:").grid(row=3, column=0, sticky='w', pady=5)
    self.setting_tickets_per_page = tk.StringVar(value="25")
    ttk.Combobox(general_frame, textvariable=self.setting_tickets_per_page,
            values=['10', '25', '50', '100'], state='readonly', width=37).grid(row=3, column=1, pady=5, padx=5)

    # Session timeout
    ttk.Label(general_frame, text="Session Timeout (min):").grid(row=4, column=0, sticky='w', pady=5)
    self.setting_session_timeout = tk.StringVar(value="30")
    ttk.Entry(general_frame, textvariable=self.setting_session_timeout, width=40).grid(row=4, column=1, pady=5, padx=5)

    # === Email Settings ===
    email_frame = ttk.Frame(settings_notebook, padding="10")
    settings_notebook.add(email_frame, text="Email")

    ttk.Label(email_frame, text="SMTP Server:").grid(row=0, column=0, sticky='w', pady=5)
    self.setting_smtp_server = tk.StringVar(value="smtp.gmail.com")
    ttk.Entry(email_frame, textvariable=self.setting_smtp_server, width=40).grid(row=0, column=1, pady=5, padx=5)

    ttk.Label(email_frame, text="SMTP Port:").grid(row=1, column=0, sticky='w', pady=5)
    self.setting_smtp_port = tk.StringVar(value="587")
    ttk.Entry(email_frame, textvariable=self.setting_smtp_port, width=40).grid(row=1, column=1, pady=5, padx=5)

    ttk.Label(email_frame, text="SMTP Username:").grid(row=2, column=0, sticky='w', pady=5)
    self.setting_smtp_user = tk.StringVar(value="")
    ttk.Entry(email_frame, textvariable=self.setting_smtp_user, width=40).grid(row=2, column=1, pady=5, padx=5)

    ttk.Label(email_frame, text="SMTP Password:").grid(row=3, column=0, sticky='w', pady=5)
    self.setting_smtp_password = tk.StringVar(value="")
    ttk.Entry(email_frame, textvariable=self.setting_smtp_password, show="*", width=40).grid(row=3, column=1, pady=5, padx=5)

    ttk.Label(email_frame, text="From Email:").grid(row=4, column=0, sticky='w', pady=5)
    self.setting_from_email = tk.StringVar(value="helpdesk@university.edu")
    ttk.Entry(email_frame, textvariable=self.setting_from_email, width=40).grid(row=4, column=1, pady=5, padx=5)

    ttk.Label(email_frame, text="Enable Email Notifications:").grid(row=5, column=0, sticky='w', pady=5)
    self.setting_email_enabled = tk.BooleanVar(value=True)
    ttk.Checkbutton(email_frame, variable=self.setting_email_enabled).grid(row=5, column=1, sticky='w', pady=5, padx=5)

    # === Security Settings ===
    security_frame = ttk.Frame(settings_notebook, padding="10")
    settings_notebook.add(security_frame, text="Security")

    ttk.Label(security_frame, text="Require Strong Passwords:").grid(row=0, column=0, sticky='w', pady=5)
    self.setting_strong_passwords = tk.BooleanVar(value=True)
    ttk.Checkbutton(security_frame, variable=self.setting_strong_passwords).grid(row=0, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(security_frame, text="Enable Two-Factor Auth:").grid(row=1, column=0, sticky='w', pady=5)
    self.setting_2fa_enabled = tk.BooleanVar(value=False)
    ttk.Checkbutton(security_frame, variable=self.setting_2fa_enabled).grid(row=1, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(security_frame, text="Max Login Attempts:").grid(row=2, column=0, sticky='w', pady=5)
    self.setting_max_login_attempts = tk.StringVar(value="5")
    ttk.Entry(security_frame, textvariable=self.setting_max_login_attempts, width=40).grid(row=2, column=1, pady=5, padx=5)

    ttk.Label(security_frame, text="Lockout Duration (min):").grid(row=3, column=0, sticky='w', pady=5)
    self.setting_lockout_duration = tk.StringVar(value="15")
    ttk.Entry(security_frame, textvariable=self.setting_lockout_duration, width=40).grid(row=3, column=1, pady=5, padx=5)

    ttk.Label(security_frame, text="Password Expiry (days):").grid(row=4, column=0, sticky='w', pady=5)
    self.setting_password_expiry = tk.StringVar(value="90")
    ttk.Entry(security_frame, textvariable=self.setting_password_expiry, width=40).grid(row=4, column=1, pady=5, padx=5)

    # === Notification Settings ===
    notif_frame = ttk.Frame(settings_notebook, padding="10")
    settings_notebook.add(notif_frame, text="Notifications")

    ttk.Label(notif_frame, text="Notify on New Ticket:").grid(row=0, column=0, sticky='w', pady=5)
    self.setting_notify_new = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, variable=self.setting_notify_new).grid(row=0, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(notif_frame, text="Notify on Assignment:").grid(row=1, column=0, sticky='w', pady=5)
    self.setting_notify_assign = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, variable=self.setting_notify_assign).grid(row=1, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(notif_frame, text="Notify on Status Change:").grid(row=2, column=0, sticky='w', pady=5)
    self.setting_notify_status = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, variable=self.setting_notify_status).grid(row=2, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(notif_frame, text="Notify on Reply:").grid(row=3, column=0, sticky='w', pady=5)
    self.setting_notify_reply = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, variable=self.setting_notify_reply).grid(row=3, column=1, sticky='w', pady=5, padx=5)

    ttk.Label(notif_frame, text="Send Satisfaction Surveys:").grid(row=4, column=0, sticky='w', pady=5)
    self.setting_send_surveys = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, variable=self.setting_send_surveys).grid(row=4, column=1, sticky='w', pady=5, padx=5)

    # Buttons
    btn_frame = ttk.Frame(settings_window)
    btn_frame.pack(fill='x', padx=10, pady=10)

    def save_settings():
        self._save_system_settings()
        messagebox.showinfo("Success", "Settings saved successfully!")
        settings_window.destroy()

    ttk.Button(btn_frame, text="Save Settings", command=save_settings).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel", command=settings_window.destroy).pack(side='right', padx=5)

    # Load existing settings
    self._load_system_settings()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_settings = show_settings

def _load_system_settings(self):
    """Load system settings from database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Check if settings table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='helpdesk_system_settings'")
        if not cursor.fetchone():
            # Create settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS helpdesk_system_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TEXT
            )
            ''')
            conn.commit()
        else:
            # Load settings
            cursor.execute("SELECT setting_key, setting_value FROM helpdesk_system_settings")
            for key, value in cursor.fetchall():
                if hasattr(self, f'setting_{key}'):
                    var = getattr(self, f'setting_{key}')
                    if isinstance(var, tk.BooleanVar):
                        var.set(value.lower() == 'true')
                    else:
                        var.set(value)

        conn.close()
    except Exception as e:
        print(f"Warning: Could not load settings: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._load_system_settings = _load_system_settings

def _save_system_settings(self):
    """Save system settings to database"""
    conn = None
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.execute("PRAGMA busy_timeout = 5000")
        cursor = conn.cursor()

        # Ensure table exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS helpdesk_system_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            updated_at TEXT
        )
        ''')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get all setting variables
        settings = {
            'system_name': self.setting_system_name.get(),
            'default_priority': self.setting_default_priority.get(),
            'auto_assign': str(self.setting_auto_assign.get()),
            'tickets_per_page': self.setting_tickets_per_page.get(),
            'session_timeout': self.setting_session_timeout.get(),
            'smtp_server': self.setting_smtp_server.get(),
            'smtp_port': self.setting_smtp_port.get(),
            'smtp_user': self.setting_smtp_user.get(),
            'from_email': self.setting_from_email.get(),
            'email_enabled': str(self.setting_email_enabled.get()),
            'strong_passwords': str(self.setting_strong_passwords.get()),
            '2fa_enabled': str(self.setting_2fa_enabled.get()),
            'max_login_attempts': self.setting_max_login_attempts.get(),
            'lockout_duration': self.setting_lockout_duration.get(),
            'password_expiry': self.setting_password_expiry.get(),
            'notify_new': str(self.setting_notify_new.get()),
            'notify_assign': str(self.setting_notify_assign.get()),
            'notify_status': str(self.setting_notify_status.get()),
            'notify_reply': str(self.setting_notify_reply.get()),
            'send_surveys': str(self.setting_send_surveys.get()),
        }

        # Save each setting
        for key, value in settings.items():
            cursor.execute('''
            INSERT OR REPLACE INTO helpdesk_system_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, ?)
            ''', (key, value, now))

        conn.commit()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('update', 'system_settings', details={'updated_by': self.current_user.get('username')})

    except Exception as e:
        messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
    finally:
        if conn:
            conn.close()

# Admin management functions

# Attach method to HelpdeskGUI class
HelpdeskGUI._save_system_settings = _save_system_settings

def show_database_cleanup(self):
    """Show database cleanup dialog"""
    cleanup_window = tk.Toplevel(self.root)
    cleanup_window.title("Database Cleanup")
    cleanup_window.geometry("500x400")
    cleanup_window.transient(self.root)

    main_frame = ttk.Frame(cleanup_window, padding="20")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Database Cleanup Options", font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

    def cleanup_old_tickets():
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            cursor.execute("DELETE FROM support_tickets WHERE status = 'closed' AND updated_at < ?", (cutoff,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Deleted {deleted} old closed tickets (older than 1 year)")
        except Exception as e:
            messagebox.showerror("Error", f"Cleanup failed: {str(e)}")

    def cleanup_orphan_replies():
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM ticket_replies
                WHERE ticket_id NOT IN (SELECT ticket_id FROM support_tickets)
            """)
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Deleted {deleted} orphan replies")
        except Exception as e:
            messagebox.showerror("Error", f"Cleanup failed: {str(e)}")

    def vacuum_database():
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            conn.execute("VACUUM")
            conn.close()
            messagebox.showinfo("Success", "Database vacuumed successfully - freed up disk space")
        except Exception as e:
            messagebox.showerror("Error", f"Vacuum failed: {str(e)}")

    ttk.Button(main_frame, text="Delete Old Closed Tickets (>1 year)", command=cleanup_old_tickets).pack(fill='x', pady=5)
    ttk.Button(main_frame, text="Remove Orphan Replies", command=cleanup_orphan_replies).pack(fill='x', pady=5)
    ttk.Button(main_frame, text="Vacuum Database (Free Space)", command=vacuum_database).pack(fill='x', pady=5)

    ttk.Label(main_frame, text="\nWarning: These operations cannot be undone.",
             foreground='red').pack(pady=20)

    ttk.Button(main_frame, text="Close", command=cleanup_window.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_database_cleanup = show_database_cleanup

def backup_database(self):
    """Backup database to file"""
    try:
        import shutil
        from education_system.university_system.modules.shared.constants import paths

        # Get source database path
        db_path = paths.DEFAULT_DB_PATH

        # Ask for backup location
        backup_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")],
            title="Save Database Backup",
            initialfile=f"helpdesk_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )

        if backup_path:
            shutil.copy2(db_path, backup_path)
            messagebox.showinfo("Success", f"Database backed up to:\n{backup_path}")

            if ACTIVITY_LOGGER_AVAILABLE:
                log_activity('backup', 'database', details={'backup_path': backup_path})

    except Exception as e:
        messagebox.showerror("Error", f"Backup failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.backup_database = backup_database

def check_data_integrity(self):
    """Check data integrity of helpdesk tables"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        issues = []

        # Check for orphan tickets (user_id doesn't exist)
        cursor.execute("""
            SELECT COUNT(*) FROM support_tickets t
            WHERE t.user_id IS NOT NULL AND t.user_id != 0
            AND t.user_id NOT IN (SELECT id FROM users)
        """)
        orphan_tickets = cursor.fetchone()[0]
        if orphan_tickets > 0:
            issues.append(f"- {orphan_tickets} tickets with non-existent user IDs")

        # Check for orphan replies
        cursor.execute("""
            SELECT COUNT(*) FROM ticket_replies r
            WHERE r.ticket_id NOT IN (SELECT ticket_id FROM support_tickets)
        """)
        orphan_replies = cursor.fetchone()[0]
        if orphan_replies > 0:
            issues.append(f"- {orphan_replies} orphan replies")

        # Check for tickets without required fields
        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE category IS NULL OR category = ''")
        no_category = cursor.fetchone()[0]
        if no_category > 0:
            issues.append(f"- {no_category} tickets without category")

        # Run SQLite integrity check
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]

        conn.close()

        if issues:
            result_msg = "Data integrity issues found:\n\n" + "\n".join(issues)
            if integrity_result != 'ok':
                result_msg += f"\n\nSQLite integrity: {integrity_result}"
            messagebox.showwarning("Integrity Issues", result_msg)
        else:
            messagebox.showinfo("Success", f"Data integrity check completed - no issues found\nSQLite integrity: {integrity_result}")

    except Exception as e:
        messagebox.showerror("Error", f"Integrity check failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.check_data_integrity = check_data_integrity

def show_export_dialog(self):
    """Show data export dialog"""
    export_window = tk.Toplevel(self.root)
    export_window.title("Export Data")
    export_window.geometry("400x300")
    export_window.transient(self.root)
    export_window.grab_set()

    ttk.Label(export_window, text="Data Export Options", style='Heading.TLabel').pack(pady=10)

    # Export options
    options_frame = ttk.LabelFrame(export_window, text="Export Options")
    options_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(options_frame, text="Export All Tickets (CSV)", 
          command=self.export_tickets_csv).pack(fill='x', padx=5, pady=5)
    ttk.Button(options_frame, text="Export Users (CSV)", 
          command=self.export_users_csv).pack(fill='x', padx=5, pady=5)
    ttk.Button(options_frame, text="Export Analytics (JSON)", 
          command=self.export_analytics_json).pack(fill='x', padx=5, pady=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_export_dialog = show_export_dialog

def show_import_dialog(self):
    """Show data import dialog"""
    messagebox.showinfo("Info", "Data import functionality would integrate with the original system")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_import_dialog = show_import_dialog

def show_about(self):
    """Show about dialog"""
    about_window = tk.Toplevel(self.root)
    about_window.title("About Enhanced Helpdesk System")
    about_window.geometry("400x300")
    about_window.transient(self.root)
    about_window.grab_set()
    
    # Center the about dialog
    about_window.update_idletasks()
    x = (about_window.winfo_screenwidth() // 2) - (400 // 2)
    y = (about_window.winfo_screenheight() // 2) - (300 // 2)
    about_window.geometry(f'400x300+{x}+{y}')
    
    # About content
    content_frame = ttk.Frame(about_window)
    content_frame.pack(fill='both', expand=True, padx=20, pady=20)
    
    ttk.Label(content_frame, text="Enhanced Helpdesk System", 
             style='Title.TLabel').pack(pady=10)
    
    ttk.Label(content_frame, text="Version 2.0 GUI Edition").pack(pady=5)
    
    info_text = """
A comprehensive helpdesk and ticket management system
with both GUI and CLI interfaces.

Features:
• Complete ticket lifecycle management
• Knowledge base integration
• Advanced analytics and reporting
• User and role management
• SLA tracking and workflows
• Bulk operations and automation

Built with Python and Tkinter
Backwards compatible with CLI version

© 2024 Enhanced Helpdesk System
    """
    
    ttk.Label(content_frame, text=info_text, justify='center').pack(pady=10)

    ttk.Button(content_frame, text="Close", command=about_window.destroy).pack(pady=10)

# ============================================================================
# ENHANCED TICKET MANAGEMENT FUNCTIONS (8 NEW FUNCTIONS)
# ============================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_about = show_about

def show_user_guide(self):
    """Show user guide"""
    guide_window = tk.Toplevel(self.root)
    guide_window.title("User Guide")
    guide_window.geometry("800x600")
    guide_window.transient(self.root)
    
    # User guide content
    guide_text = scrolledtext.ScrolledText(guide_window, wrap='word', state='disabled')
    guide_text.pack(fill='both', expand=True, padx=10, pady=10)
    
    guide_content = """
HELPDESK SYSTEM USER GUIDE

GETTING STARTED
===============
The Enhanced Helpdesk System provides a comprehensive solution for managing support tickets, 
knowledge base articles, and system administration.

MAIN FEATURES
=============

1. DASHBOARD
   - Quick overview of your tickets and system statistics
   - Recent activity display
   - Quick action buttons

2. TICKET MANAGEMENT
   - Create new support tickets using templates or custom forms
   - View and manage your tickets
   - Reply to tickets and track conversations
   - Admin functions for managing all tickets

3. KNOWLEDGE BASE
   - Browse and search articles
   - Rate articles for helpfulness
   - Create new articles (staff/admin only)

4. ANALYTICS (Admin)
   - View system-wide statistics
   - Generate various reports
   - Track performance metrics

5. ADMINISTRATION (Admin)
   - User management
   - System configuration
   - Data import/export
   - Maintenance functions

CREATING TICKETS
================
1. Click "Create Ticket" tab or use the dashboard button
2. Choose a template or create a custom ticket
3. Fill in the required information
4. Submit the ticket

MANAGING TICKETS
================
- View your tickets in the "My Tickets" tab
- Double-click any ticket to view details
- Use the conversation tab to see all replies
- Reply to tickets using the actions panel

ADMIN FUNCTIONS
===============
Administrators have access to additional features:
- View and manage all tickets
- Bulk operations on multiple tickets
- System analytics and reporting
- User and system management

For more detailed information, please contact your system administrator.
    """

    guide_text.config(state='normal')
    guide_text.insert('1.0', guide_content)
    guide_text.config(state='disabled')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_user_guide = show_user_guide

def system_management_menu_gui(self):
    """Show system management menu"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to access system management.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title("System Management")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="System Management",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

    # Management options
    options_frame = ttk.Frame(main_frame)
    options_frame.pack(fill='both', expand=True)

    ttk.Button(options_frame, text="📊 Generate Reports",
              command=lambda: [dialog.destroy(), self.generate_enhanced_ticket_report_gui()]).pack(fill='x', pady=5)
    ttk.Button(options_frame, text="💾 Data Import/Export",
              command=lambda: [dialog.destroy(), self.data_import_export_gui()]).pack(fill='x', pady=5)
    ttk.Button(options_frame, text="🔧 System Maintenance",
              command=lambda: [dialog.destroy(), self.system_maintenance_gui()]).pack(fill='x', pady=5)
    ttk.Button(options_frame, text="📋 Audit Logs",
              command=lambda: [dialog.destroy(), self.view_audit_logs_gui()]).pack(fill='x', pady=5)

    # Close button
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(20, 0))

# Attach method to HelpdeskGUI class
HelpdeskGUI.system_management_menu_gui = system_management_menu_gui

def system_maintenance_gui(self):
    """System maintenance functions"""
    dialog = tk.Toplevel(self.root)
    dialog.title("System Maintenance")
    dialog.geometry("500x350")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="System Maintenance",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

    info_frame = ttk.Frame(main_frame)
    info_frame.pack(fill='both', expand=True)

    def check_integrity():
        try:
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk import check_data_integrity
            check_data_integrity(self.auth if hasattr(self, 'auth') else None)
            messagebox.showinfo("Success", "Data integrity check completed")
        except Exception as e:
            messagebox.showerror("Error", f"Integrity check failed: {str(e)}")

    def backup_db():
        try:
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk import backup_database
            backup_database(self.auth if hasattr(self, 'auth') else None)
            messagebox.showinfo("Success", "Database backup completed")
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {str(e)}")

    ttk.Button(info_frame, text="🔍 Check Data Integrity",
              command=check_integrity).pack(fill='x', pady=5)
    ttk.Button(info_frame, text="💾 Backup Database",
              command=backup_db).pack(fill='x', pady=5)
    ttk.Button(info_frame, text="🧹 Database Cleanup",
              command=lambda: messagebox.showinfo("Info", "Database cleanup functionality")).pack(fill='x', pady=5)

    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(20, 0))

# Attach method to HelpdeskGUI class
HelpdeskGUI.system_maintenance_gui = system_maintenance_gui

def view_audit_logs_gui(self):
    """View ticket audit logs"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        log_window = tk.Toplevel(self.root)
        log_window.title("Audit Logs")
        log_window.geometry("1000x600")

        main_frame = ttk.Frame(log_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="📋 Ticket Audit Logs",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview
        columns = ('Log ID', 'Ticket ID', 'User', 'Action', 'Timestamp', 'Details')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Load audit logs
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT al.log_id, al.ticket_id, u.username, al.action, al.created_at,
                   al.new_values
            FROM ticket_audit_log al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 1000
        ''')

        logs = cursor.fetchall()
        conn.close()

        for log in logs:
            log_id, ticket_id, username, action, timestamp, details = log
            tree.insert('', 'end', values=(
                log_id, ticket_id, username or 'System', action, timestamp,
                details[:50] if details else ''
            ))

        ttk.Button(main_frame, text="Close", command=log_window.destroy).pack()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load audit logs: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_audit_logs_gui = view_audit_logs_gui

