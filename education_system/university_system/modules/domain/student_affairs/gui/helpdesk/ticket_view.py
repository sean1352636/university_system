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

def show_ticket_details(self, ticket_id):
    """Show detailed ticket view"""
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Ticket #{ticket_id} Details")
    details_window.geometry("800x600")
    details_window.transient(self.root)

    # Create notebook for different sections
    notebook = ttk.Notebook(details_window)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)

    # Load ticket data
    ticket_data = self.get_ticket_details(ticket_id)
    if not ticket_data:
        messagebox.showerror("Error", "Ticket not found")
        details_window.destroy()
        return

    # Details tab
    details_frame = ttk.Frame(notebook)
    notebook.add(details_frame, text="Details")

    # Create scrollable frame for details
    canvas = tk.Canvas(details_frame)
    scrollbar = ttk.Scrollbar(details_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Ticket information
    info_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Information")
    info_frame.pack(fill='x', padx=10, pady=5)

    # Display ticket fields
    fields = [
        ("Ticket ID:", ticket_data.get('ticket_id')),
        ("Subject:", ticket_data.get('subject')),
        ("Category:", ticket_data.get('category')),
        ("Status:", ticket_data.get('status', '').title()),
        ("Priority:", ticket_data.get('priority', '').title()),
        ("Impact:", ticket_data.get('impact', '').title()),
        ("Urgency:", ticket_data.get('urgency', '').title()),
        ("Created:", ticket_data.get('created_at')),
        ("Updated:", ticket_data.get('updated_at')),
        ("Assigned To:", ticket_data.get('assignee') or 'Unassigned'),
        ("Department:", ticket_data.get('department') or 'None')
    ]

    for i, (label, value) in enumerate(fields):
        ttk.Label(info_frame, text=label, style='Heading.TLabel').grid(row=i, column=0, sticky='w', padx=5, pady=2)
        ttk.Label(info_frame, text=str(value) if value else 'N/A').grid(row=i, column=1, sticky='w', padx=20, pady=2)

    # Message frame
    message_frame = ttk.LabelFrame(scrollable_frame, text="Original Message")
    message_frame.pack(fill='x', padx=10, pady=5)

    message_text = scrolledtext.ScrolledText(message_frame, height=5, wrap='word', state='disabled')
    message_text.pack(fill='x', padx=5, pady=5)
    message_text.config(state='normal')
    message_text.insert('1.0', ticket_data.get('message', ''))
    message_text.config(state='disabled')

    # Resolution frame (if resolved)
    if ticket_data.get('resolution'):
        resolution_frame = ttk.LabelFrame(scrollable_frame, text="Resolution")
        resolution_frame.pack(fill='x', padx=10, pady=5)

        resolution_text = scrolledtext.ScrolledText(resolution_frame, height=3, wrap='word', state='disabled')
        resolution_text.pack(fill='x', padx=5, pady=5)
        resolution_text.config(state='normal')
        resolution_text.insert('1.0', ticket_data.get('resolution', ''))
        resolution_text.config(state='disabled')

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Replies tab
    replies_frame = ttk.Frame(notebook)
    notebook.add(replies_frame, text="Conversation")

    self.create_replies_view(replies_frame, ticket_id)

    # Actions tab (if user has permissions)
    if self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets'):
        actions_frame = ttk.Frame(notebook)
        notebook.add(actions_frame, text="Actions")

        self.create_ticket_actions_view(actions_frame, ticket_id, ticket_data)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_ticket_details = show_ticket_details

def get_ticket_details(self, ticket_id):
    """Get detailed ticket information"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT t.*, u1.username as submitter, u2.username as assignee
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE t.ticket_id = ?
        ''', (ticket_id,))

        ticket = cursor.fetchone()
        conn.close()

        return dict(ticket) if ticket else None

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load ticket: {str(e)}")
        return None

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_details = get_ticket_details

def create_replies_view(self, parent, ticket_id):
    """Create replies/conversation view"""
    # Toolbar
    toolbar = ttk.Frame(parent)
    toolbar.pack(fill='x', padx=5, pady=5)

    ttk.Button(toolbar, text="Add Reply", command=lambda: self.show_reply_dialog(ticket_id)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="Refresh", command=lambda: self.refresh_replies_view(parent, ticket_id)).pack(side='left', padx=5)

    # Replies list
    self.replies_frame = ttk.Frame(parent)
    self.replies_frame.pack(fill='both', expand=True, padx=5, pady=5)

    self.load_ticket_replies(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_replies_view = create_replies_view

def load_ticket_replies(self, ticket_id):
    """Load ticket replies"""
    try:
        # Clear existing widgets
        for widget in self.replies_frame.winfo_children():
            widget.destroy()

        # Create scrollable frame
        canvas = tk.Canvas(self.replies_frame)
        scrollbar = ttk.Scrollbar(self.replies_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Get replies from database
        replies = self.get_ticket_replies(ticket_id)

        for i, reply in enumerate(replies):
            reply_frame = ttk.LabelFrame(scrollable_frame, 
                                       text=f"{reply['username']} - {reply['created_at']}")
            reply_frame.pack(fill='x', padx=5, pady=5)

            # Reply content
            reply_text = scrolledtext.ScrolledText(reply_frame, height=4, wrap='word', state='disabled')
            reply_text.pack(fill='x', padx=5, pady=5)
            reply_text.config(state='normal')
            reply_text.insert('1.0', reply['message'])
            reply_text.config(state='disabled')

            # Internal note indicator
            if reply.get('is_internal') and self.has_permission('manage_tickets'):
                internal_label = ttk.Label(reply_frame, text="(Internal Note)", style='Warning.TLabel')
                internal_label.pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except Exception as e:
        ttk.Label(self.replies_frame, text=f"Error loading replies: {str(e)}", 
                 style='Error.TLabel').pack()

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_ticket_replies = load_ticket_replies

def get_ticket_replies(self, ticket_id):
    """Get ticket replies from database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT r.*, u.username
        FROM ticket_replies r
        JOIN users u ON r.user_id = u.id
        WHERE r.ticket_id = ?
        ORDER BY r.created_at ASC
        ''', (ticket_id,))

        replies = cursor.fetchall()
        conn.close()

        return [dict(reply) for reply in replies]

    except Exception as e:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_replies = get_ticket_replies

def refresh_replies_view(self, parent, ticket_id):
    """Refresh replies view"""
    self.load_ticket_replies(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_replies_view = refresh_replies_view

def create_ticket_actions_view(self, parent, ticket_id, ticket_data):
    """Create ticket actions view"""
    actions_frame = ttk.LabelFrame(parent, text="Available Actions")
    actions_frame.pack(fill='x', padx=10, pady=10)

    # Reply action
    if self.has_permission('reply_to_own_ticket') or self.has_permission('manage_tickets'):
        ttk.Button(actions_frame, text="Add Reply", 
                  command=lambda: self.show_reply_dialog(ticket_id)).pack(pady=5)

    # Admin actions
    if self.has_permission('manage_tickets'):
        ttk.Button(actions_frame, text="Change Status", 
                  command=lambda: self.show_status_dialog(ticket_id)).pack(pady=5)
        ttk.Button(actions_frame, text="Assign Ticket", 
                  command=lambda: self.show_assign_dialog(ticket_id)).pack(pady=5)
        ttk.Button(actions_frame, text="Add Internal Note", 
                  command=lambda: self.show_internal_note_dialog(ticket_id)).pack(pady=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_actions_view = create_ticket_actions_view

def view_ticket_detail_enhanced_gui(self, ticket_id):
    """View complete ticket details with all information"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.*, u1.username as submitter, u2.username as assignee
            FROM support_tickets t
            JOIN users u1 ON t.user_id = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE t.ticket_id = ?
        ''', (ticket_id,))

        ticket = cursor.fetchone()
        conn.close()

        if not ticket:
            messagebox.showerror("Not Found", "Ticket not found.")
            return

        # Create detail window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"Ticket #{ticket_id} - {ticket['subject']}")
        detail_window.geometry("1000x700")

        # Main scrollable frame
        main_canvas = tk.Canvas(detail_window)
        scrollbar = ttk.Scrollbar(detail_window, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        # Ticket header
        header_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Information", padding="10")
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(header_frame, text=f"Ticket ID: #{ticket['ticket_id']}", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Subject: {ticket['subject']}", font=('Arial', 11)).pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Status: {ticket['status'].upper()}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Priority: {ticket['priority'].upper()} | Impact: {ticket['impact'].upper()} | Urgency: {ticket['urgency'].upper()}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Category: {ticket['category']}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Submitted by: {ticket['submitter']}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Assigned to: {ticket['assignee'] or 'Unassigned'}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Created: {ticket['created_at']}").pack(anchor=tk.W)
        ttk.Label(header_frame, text=f"Updated: {ticket['updated_at']}").pack(anchor=tk.W)

        if ticket['due_date']:
            ttk.Label(header_frame, text=f"Due Date: {ticket['due_date']}").pack(anchor=tk.W)

        # Message
        msg_frame = ttk.LabelFrame(scrollable_frame, text="Message", padding="10")
        msg_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        msg_text = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, height=5)
        msg_text.pack(fill=tk.BOTH, expand=True)
        msg_text.insert('1.0', ticket['message'])
        msg_text.config(state=tk.DISABLED)

        # Replies
        self.display_ticket_replies_gui(ticket_id, scrollable_frame)

        # Time tracking
        self.display_time_tracking_gui(ticket_id, scrollable_frame)

        # Escalation history
        self.display_escalation_history_gui(ticket_id, scrollable_frame)

        # Linked tickets
        self.display_linked_tickets_gui(ticket_id, scrollable_frame)

        # Audit trail (admin only)
        if self.auth.has_permission('view_all_tickets'):
            self.display_audit_trail_gui(ticket_id, scrollable_frame)

        # Action buttons
        action_frame = ttk.Frame(scrollable_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        if self.auth.has_permission('reply_to_any_ticket') or ticket['user_id'] == self.auth.current_user['id']:
            ttk.Button(action_frame, text="Reply", command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, False)).pack(side=tk.LEFT, padx=5)

        if self.auth.has_permission('manage_tickets'):
            ttk.Button(action_frame, text="Internal Note", command=lambda: self.reply_to_ticket_enhanced_gui(ticket_id, True)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Add Time Entry", command=lambda: self.add_time_entry_gui(ticket_id)).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text="Link Ticket", command=lambda: self.link_tickets_gui(ticket_id)).pack(side=tk.LEFT, padx=5)

        ttk.Button(action_frame, text="Close", command=detail_window.destroy).pack(side=tk.RIGHT, padx=5)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load ticket details: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_ticket_detail_enhanced_gui = view_ticket_detail_enhanced_gui

def view_ticket_from_tree(self, tree):
    """View ticket details from treeview selection"""
    selection = tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a ticket to view.")
        return

    item = tree.item(selection[0])
    ticket_id = item['values'][0]
    self.view_ticket_detail_enhanced_gui(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_ticket_from_tree = view_ticket_from_tree

def display_ticket_replies_gui(self, ticket_id, parent_frame):
    """Display ticket reply history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, u.username, u.role
            FROM ticket_replies r
            JOIN users u ON r.user_id = u.id
            WHERE r.ticket_id = ?
            ORDER BY r.created_at ASC
        ''', (ticket_id,))

        replies = cursor.fetchall()
        conn.close()

        if not replies:
            return

        replies_frame = ttk.LabelFrame(parent_frame, text="Conversation History", padding="10")
        replies_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for reply in replies:
            reply_type = "Internal Note" if reply[4] else "Reply"
            is_internal = reply[4]

            # Only show internal notes to admins
            if is_internal and not self.auth.has_permission('manage_tickets'):
                continue

            reply_item_frame = ttk.Frame(replies_frame)
            reply_item_frame.pack(fill=tk.X, pady=5)

            icon = "🔒" if is_internal else "💬"
            header_text = f"{icon} {reply_type} from {reply[-2]} ({reply[-1]}) at {reply[6]}"

            ttk.Label(reply_item_frame, text=header_text, font=('Arial', 9, 'bold')).pack(anchor=tk.W)

            msg_text = tk.Text(reply_item_frame, wrap=tk.WORD, height=3, relief=tk.FLAT, bg='#f0f0f0')
            msg_text.pack(fill=tk.X, pady=2)
            msg_text.insert('1.0', reply[3])
            msg_text.config(state=tk.DISABLED)

            ttk.Separator(replies_frame, orient='horizontal').pack(fill=tk.X, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading replies: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_ticket_replies_gui = display_ticket_replies_gui

def display_time_tracking_gui(self, ticket_id, parent_frame):
    """Display time tracking information"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tt.*, u.username
            FROM ticket_time_tracking tt
            JOIN users u ON tt.user_id = u.id
            WHERE tt.ticket_id = ?
            ORDER BY tt.created_at
        ''', (ticket_id,))

        time_entries = cursor.fetchall()
        conn.close()

        if not time_entries:
            return

        time_frame = ttk.LabelFrame(parent_frame, text="Time Tracking", padding="10")
        time_frame.pack(fill=tk.X, padx=10, pady=5)

        total_time = 0
        billable_time = 0

        for entry in time_entries:
            duration = entry[5] / 60  # minutes to hours
            total_time += duration
            if entry[7]:  # billable
                billable_time += duration

            billable_text = " (Billable)" if entry[7] else ""
            entry_text = f"⏱️  {entry[-1]}: {duration:.2f} hours{billable_text}"

            if entry[6]:  # description
                entry_text += f"\n   Description: {entry[6]}"

            ttk.Label(time_frame, text=entry_text).pack(anchor=tk.W, pady=2)

        ttk.Separator(time_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        ttk.Label(time_frame, text=f"Total Time: {total_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        ttk.Label(time_frame, text=f"Billable Time: {billable_time:.2f} hours", font=('Arial', 9, 'bold')).pack(anchor=tk.W)

    except sqlite3.Error as e:
        print(f"Error loading time tracking: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_time_tracking_gui = display_time_tracking_gui

def display_escalation_history_gui(self, ticket_id, parent_frame):
    """Display escalation history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT e.*, u1.username as escalated_to_user, u2.username as escalated_by_user
            FROM ticket_escalations e
            LEFT JOIN users u1 ON e.escalated_to = u1.id
            LEFT JOIN users u2 ON e.escalated_by = u2.id
            WHERE e.ticket_id = ?
            ORDER BY e.created_at
        ''', (ticket_id,))

        escalations = cursor.fetchall()
        conn.close()

        if not escalations:
            return

        esc_frame = ttk.LabelFrame(parent_frame, text="Escalation History", padding="10")
        esc_frame.pack(fill=tk.X, padx=10, pady=5)

        for esc in escalations:
            status = "Resolved" if esc[6] else "Open"
            escalated_by = esc[-1] or "System"

            esc_text = f"🔺 Level {esc[2]} - Escalated to {esc[-2]} by {escalated_by}\n"
            esc_text += f"   Reason: {esc[4]}\n"
            esc_text += f"   Date: {esc[7]} - Status: {status}"

            ttk.Label(esc_frame, text=esc_text).pack(anchor=tk.W, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading escalation history: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_escalation_history_gui = display_escalation_history_gui

def display_audit_trail_gui(self, ticket_id, parent_frame):
    """Display audit trail for admins"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT al.*, u.username
            FROM ticket_audit_log al
            JOIN users u ON al.user_id = u.id
            WHERE al.ticket_id = ?
            ORDER BY al.created_at DESC
            LIMIT 10
        ''', (ticket_id,))

        audit_entries = cursor.fetchall()
        conn.close()

        if not audit_entries:
            return

        audit_frame = ttk.LabelFrame(parent_frame, text="Recent Activity (Audit Trail)", padding="10")
        audit_frame.pack(fill=tk.X, padx=10, pady=5)

        for entry in audit_entries:
            audit_text = f"📋 {entry[3]} by {entry[-1]} at {entry[8]}"

            if entry[4]:  # old_values
                try:
                    old_vals = json.loads(entry[4])
                    if old_vals:
                        audit_text += f"\n   Previous: {old_vals}"
                except json.JSONDecodeError:
                    pass

            if entry[5]:  # new_values
                try:
                    new_vals = json.loads(entry[5])
                    if new_vals:
                        audit_text += f"\n   New: {new_vals}"
                except json.JSONDecodeError:
                    pass

            ttk.Label(audit_frame, text=audit_text).pack(anchor=tk.W, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading audit trail: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_audit_trail_gui = display_audit_trail_gui

def display_linked_tickets_gui(self, ticket_id, parent_frame):
    """Display linked tickets"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT tl.*, t.subject, t.status
            FROM ticket_links tl
            JOIN support_tickets t ON tl.linked_ticket_id = t.ticket_id
            WHERE tl.ticket_id = ?
            ORDER BY tl.created_at
        ''', (ticket_id,))

        links = cursor.fetchall()
        conn.close()

        if not links:
            return

        links_frame = ttk.LabelFrame(parent_frame, text="Linked Tickets", padding="10")
        links_frame.pack(fill=tk.X, padx=10, pady=5)

        for link in links:
            link_text = f"🔗 {link[3]} #{link[2]}: {link[-2]} ({link[-1]})"
            ttk.Label(links_frame, text=link_text).pack(anchor=tk.W, pady=2)

    except sqlite3.Error as e:
        print(f"Error loading linked tickets: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_linked_tickets_gui = display_linked_tickets_gui

