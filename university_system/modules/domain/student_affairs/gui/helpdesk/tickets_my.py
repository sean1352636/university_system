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

def create_my_tickets_tab(self):
    """Create my tickets tab"""
    tickets_frame = ttk.Frame(self.notebook)
    self.notebook.add(tickets_frame, text="My Tickets")

    # Toolbar
    toolbar = ttk.Frame(tickets_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text="Refresh", command=self.refresh_my_tickets).pack(side='left', padx=5)
    ttk.Button(toolbar, text="New Ticket", command=self.show_create_ticket, 
              style='Primary.TButton').pack(side='left', padx=5)

    # Filter frame
    filter_frame = ttk.LabelFrame(tickets_frame, text="Filters")
    filter_frame.pack(fill='x', padx=10, pady=5)

    filter_grid = ttk.Frame(filter_frame)
    filter_grid.pack(fill='x', padx=5, pady=5)

    ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, padx=5)
    self.my_tickets_status_var = tk.StringVar(value="all")
    status_combo = ttk.Combobox(filter_grid, textvariable=self.my_tickets_status_var,
                               values=["all", "open", "in progress", "resolved", "closed"],
                               state="readonly")
    status_combo.grid(row=0, column=1, padx=5)
    status_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_my_tickets())

    # Tickets list
    self.my_tickets_frame = ttk.Frame(tickets_frame)
    self.my_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.create_my_tickets_list()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_tab = create_my_tickets_tab

def create_my_tickets_list(self):
    """Create my tickets list"""
    # Clear existing widgets
    for widget in self.my_tickets_frame.winfo_children():
        widget.destroy()

    # Create treeview
    columns = ('ID', 'Subject', 'Category', 'Status', 'Priority', 'Created', 'Updated')
    self.my_tickets_tree = ttk.Treeview(self.my_tickets_frame, columns=columns, show='headings')

    # Configure columns
    column_widths = {'ID': 50, 'Subject': 200, 'Category': 120, 'Status': 100, 
                    'Priority': 80, 'Created': 120, 'Updated': 120}

    for col in columns:
        self.my_tickets_tree.heading(col, text=col)
        self.my_tickets_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='vertical', 
                               command=self.my_tickets_tree.yview)
    h_scrollbar = ttk.Scrollbar(self.my_tickets_frame, orient='horizontal', 
                               command=self.my_tickets_tree.xview)

    self.my_tickets_tree.configure(yscrollcommand=v_scrollbar.set, 
                                  xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.my_tickets_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    self.my_tickets_frame.grid_rowconfigure(0, weight=1)
    self.my_tickets_frame.grid_columnconfigure(0, weight=1)

    # Bind double-click to view ticket
    self.my_tickets_tree.bind('<Double-1>', self.on_my_ticket_double_click)

    # Context menu
    self.create_my_tickets_context_menu()

    # Load data
    self.refresh_my_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_list = create_my_tickets_list

def create_my_tickets_context_menu(self):
    """Create context menu for my tickets"""
    self.my_tickets_context_menu = tk.Menu(self.root, tearoff=0)
    self.my_tickets_context_menu.add_command(label="View Details", command=self.view_selected_ticket)
    self.my_tickets_context_menu.add_command(label="Reply", command=self.reply_to_selected_ticket)
    self.my_tickets_context_menu.add_separator()
    self.my_tickets_context_menu.add_command(label="Refresh", command=self.refresh_my_tickets)

    self.my_tickets_tree.bind('<Button-3>', self.show_my_tickets_context_menu)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_my_tickets_context_menu = create_my_tickets_context_menu

def show_my_tickets_context_menu(self, event):
    """Show context menu for my tickets"""
    try:
        self.my_tickets_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self.my_tickets_context_menu.grab_release()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_my_tickets_context_menu = show_my_tickets_context_menu

def refresh_my_tickets(self):
    """Refresh my tickets list"""
    try:
        # Clear existing items
        for item in self.my_tickets_tree.get_children():
            self.my_tickets_tree.delete(item)

        # Get tickets from database
        tickets = self.get_my_tickets()

        # Populate treeview
        for ticket in tickets:
            # Safely get values with defaults for None
            subject = ticket.get('subject') or 'No Subject'
            category = ticket.get('category') or 'General'
            status = ticket.get('status') or 'open'
            priority = ticket.get('priority') or 'medium'
            created_at = ticket.get('created_at') or ''
            updated_at = ticket.get('updated_at') or ''

            # Format dates
            created = created_at[:16] if created_at else ''
            updated = updated_at[:16] if updated_at else ''

            self.my_tickets_tree.insert('', 'end', values=(
                ticket.get('ticket_id', 'N/A'),
                subject[:50] if subject else 'No Subject',
                category,
                status.title() if status else 'Open',
                priority.title() if priority else 'Medium',
                created,
                updated
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_my_tickets = refresh_my_tickets

def get_my_tickets(self):
    """Get user's tickets from database"""
    try:
        # Check if user is logged in
        if self.current_user is None:
            return []

        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        status_filter = self.my_tickets_status_var.get()
        where_clause = "WHERE user_id = ?"
        params = [self.current_user.get('id', 0)]

        if status_filter != "all":
            where_clause += " AND status = ?"
            params.append(status_filter)

        # Use COALESCE to handle both old (title) and new (subject) column names
        cursor.execute(f'''
        SELECT ticket_id,
               COALESCE(subject, title, 'No Subject') as subject,
               COALESCE(category, 'General') as category,
               COALESCE(status, 'open') as status,
               COALESCE(priority, 'medium') as priority,
               COALESCE(created_at, created_datetime) as created_at,
               COALESCE(updated_at, last_updated_datetime) as updated_at
        FROM support_tickets
        {where_clause}
        ORDER BY COALESCE(created_at, created_datetime) DESC
        ''', params)

        tickets = cursor.fetchall()
        conn.close()

        return [dict(ticket) for ticket in tickets]

    except Exception as e:
        messagebox.showerror("Error", f"Database error: {str(e)}")
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_my_tickets = get_my_tickets

def on_my_ticket_double_click(self, event):
    """Handle double-click on my ticket"""
    self.view_selected_ticket()

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_my_ticket_double_click = on_my_ticket_double_click

def view_selected_ticket(self):
    """View selected ticket details"""
    selection = self.my_tickets_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a ticket")
        return

    item = self.my_tickets_tree.item(selection[0])
    ticket_id = item['values'][0]

    self.show_ticket_details(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_selected_ticket = view_selected_ticket

def reply_to_selected_ticket(self):
    """Reply to selected ticket"""
    selection = self.my_tickets_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a ticket")
        return

    item = self.my_tickets_tree.item(selection[0])
    ticket_id = item['values'][0]

    self.show_reply_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.reply_to_selected_ticket = reply_to_selected_ticket

def show_my_tickets(self):
    """Switch to my tickets tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'My Tickets':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_my_tickets = show_my_tickets

