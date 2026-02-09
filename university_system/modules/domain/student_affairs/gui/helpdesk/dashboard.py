import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import json
import os
import threading
from functools import partial
import webbrowser
from university_system.infrastructure.email.template_utils import render_template

# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
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
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import all the original functions from helpdesk.py
# This ensures backwards compatibility
try:
    from university_system.modules.domain.student_affairs.services.helpdesk import (
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
            from university_system.modules.domain.student_affairs.services.helpdesk import (
                setup_enhanced_helpdesk_permissions as service_setup_permissions
            )
            service_setup_permissions()
        except ImportError:
            # If service layer is not available, do basic setup
            print("Warning: Helpdesk service layer not available. Setting up basic permissions...")
            try:
                from university_system.infrastructure.database.db import get_connection
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

def show_main_dashboard(self):
    """Show the main dashboard"""
    self.clear_main_container()

    # Header
    header_frame = ttk.Frame(self.main_container)
    header_frame.pack(fill='x', pady=(0, 20))

    welcome_text = _t("helpdesk.welcome", default="Welcome to Helpdesk System, {username}!").format(
        username=self.current_user['username'] if self.current_user else _t("common.user", default="User")
    )
    welcome_label = ttk.Label(header_frame, text=welcome_text, style='Title.TLabel')
    welcome_label.pack(side='left')

    # Navigation buttons
    ttk.Button(header_frame, text=_t("common.return_to_main_menu", default="Return to Main Menu"), command=self.return_to_main_menu).pack(side='right')
    ttk.Button(header_frame, text=_t("helpdesk.student_support_portal", default="Student Support Portal"), command=self.open_student_support_gui).pack(side='right', padx=(0, 10))

    # Create notebook for tabs
    self.notebook = ttk.Notebook(self.main_container)
    self.notebook.pack(fill='both', expand=True)

    # Dashboard tab
    self.create_dashboard_tab()

    # My Tickets tab
    self.create_my_tickets_tab()

    # Create Ticket tab
    self.create_new_ticket_tab()

    # Knowledge Base tab
    self.create_knowledge_base_tab()

    # Admin tabs (if admin)
    if self.has_permission('view_all_tickets'):
        self.create_all_tickets_tab()
        self.create_analytics_tab()

    if self.has_permission('manage_tickets'):
        self.create_admin_tab()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_main_dashboard = show_main_dashboard

def create_dashboard_tab(self):
    """Create dashboard tab"""
    dashboard_frame = ttk.Frame(self.notebook)
    self.notebook.add(dashboard_frame, text=_t("helpdesk.tabs.dashboard", default="Dashboard"))

    # Quick stats
    stats_frame = ttk.LabelFrame(dashboard_frame, text=_t("helpdesk.quick_statistics", default="Quick Statistics"))
    stats_frame.pack(fill='x', padx=10, pady=10)

    # Create stats grid
    stats_grid = ttk.Frame(stats_frame)
    stats_grid.pack(fill='x', padx=10, pady=10)

    # Load and display stats
    self.load_dashboard_stats(stats_grid)

    # Quick actions
    actions_frame = ttk.LabelFrame(dashboard_frame, text=_t("helpdesk.quick_actions", default="Quick Actions"))
    actions_frame.pack(fill='x', padx=10, pady=10)

    actions_grid = ttk.Frame(actions_frame)
    actions_grid.pack(fill='x', padx=10, pady=10)

    # Action buttons
    ttk.Button(actions_grid, text=_t("helpdesk.create_new_ticket", default="Create New Ticket"),
              command=self.show_create_ticket, style='Primary.TButton').grid(row=0, column=0, padx=5, pady=5)
    ttk.Button(actions_grid, text=_t("helpdesk.view_my_tickets", default="View My Tickets"),
              command=self.show_my_tickets).grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(actions_grid, text=_t("helpdesk.search_knowledge_base", default="Search Knowledge Base"),
              command=self.show_knowledge_base).grid(row=0, column=2, padx=5, pady=5)

    # Recent activity
    recent_frame = ttk.LabelFrame(dashboard_frame, text=_t("helpdesk.recent_activity", default="Recent Activity"))
    recent_frame.pack(fill='both', expand=True, padx=10, pady=10)

    self.load_recent_activity(recent_frame)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_dashboard_tab = create_dashboard_tab

def load_dashboard_stats(self, parent):
    """Load dashboard statistics"""
    try:
        # Get statistics from database
        stats = self.get_user_stats()

        # Display stats
        row = 0
        for label, value in stats.items():
            ttk.Label(parent, text=f"{label}:", style='Heading.TLabel').grid(row=row, column=0, sticky='w', padx=5)
            ttk.Label(parent, text=str(value)).grid(row=row, column=1, sticky='w', padx=20)
            row += 1

    except Exception as e:
        ttk.Label(parent, text=f"Error loading stats: {str(e)}", style='Error.TLabel').pack()

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_dashboard_stats = load_dashboard_stats

def get_user_stats(self):
    """Get user statistics"""
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        stats = {}

        if self.current_user:
            # User's ticket stats
            cursor.execute('''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
                COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved
            FROM support_tickets 
            WHERE user_id = ?
            ''', (self.current_user.get('id', 0),))

            result = cursor.fetchone()
            if result:
                stats[_t("helpdesk.stats.my_total_tickets", default="My Total Tickets")] = result[0]
                stats[_t("helpdesk.stats.my_open_tickets", default="My Open Tickets")] = result[1]
                stats[_t("helpdesk.stats.my_resolved_tickets", default="My Resolved Tickets")] = result[2]

        # System-wide stats (if admin)
        if self.has_permission('view_all_tickets'):
            cursor.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open,
                COUNT(CASE WHEN assigned_to IS NULL THEN 1 END) as unassigned
            FROM support_tickets
            ''')

            result = cursor.fetchone()
            if result:
                stats[_t("helpdesk.stats.total_system_tickets", default="Total System Tickets")] = result[0]
                stats[_t("helpdesk.stats.system_open_tickets", default="System Open Tickets")] = result[1]
                stats[_t("helpdesk.stats.unassigned_tickets", default="Unassigned Tickets")] = result[2]

        conn.close()
        return stats

    except Exception as e:
        return {"Error": str(e)}

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_user_stats = get_user_stats

def load_recent_activity(self, parent):
    """Load recent activity"""
    try:
        # Create treeview for recent activity
        columns = ('Date', 'Type', 'Description')
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=6)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # Pack widgets
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load recent activity data
        recent_data = self.get_recent_activity()
        for item in recent_data:
            tree.insert('', 'end', values=item)

    except Exception as e:
        ttk.Label(parent, text=f"Error loading activity: {str(e)}", style='Error.TLabel').pack()

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_recent_activity = load_recent_activity

def get_recent_activity(self):
    """Get recent activity data"""
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        if self.current_user:
            cursor.execute('''
            SELECT created_at, 'Ticket Created' as type, subject as description
            FROM support_tickets 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            ''', (self.current_user.get('id', 0),))

            results = cursor.fetchall()
            conn.close()

            return [(r[0][:16], r[1], r[2][:50]) for r in results]

        return []

    except Exception as e:
        return [("Error", "System", str(e))]

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_recent_activity = get_recent_activity

