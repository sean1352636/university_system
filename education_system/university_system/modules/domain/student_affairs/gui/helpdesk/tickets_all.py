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

def create_all_tickets_tab(self):
    """Create all tickets tab (admin only)"""
    if not self.has_permission('view_all_tickets'):
        return

    all_tickets_frame = ttk.Frame(self.notebook)
    self.notebook.add(all_tickets_frame, text="All Tickets")

    # Toolbar
    toolbar = ttk.Frame(all_tickets_frame)
    toolbar.pack(fill='x', padx=10, pady=5)

    ttk.Button(toolbar, text="Refresh", command=self.refresh_all_tickets).pack(side='left', padx=5)
    ttk.Button(toolbar, text="Bulk Actions", command=self.show_bulk_actions).pack(side='left', padx=5)

    # Filters
    filter_frame = ttk.LabelFrame(all_tickets_frame, text="Filters")
    filter_frame.pack(fill='x', padx=10, pady=5)

    filter_grid = ttk.Frame(filter_frame)
    filter_grid.pack(fill='x', padx=5, pady=5)

    # Status filter
    ttk.Label(filter_grid, text="Status:").grid(row=0, column=0, padx=5)
    self.all_tickets_status_var = tk.StringVar(value="all")
    status_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_status_var,
                               values=["all", "open", "in progress", "waiting for customer", "resolved", "closed"],
                               state="readonly")
    status_combo.grid(row=0, column=1, padx=5)

    # Priority filter
    ttk.Label(filter_grid, text="Priority:").grid(row=0, column=2, padx=5)
    self.all_tickets_priority_var = tk.StringVar(value="all")
    priority_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_priority_var,
                                 values=["all", "low", "medium", "high"],
                                 state="readonly")
    priority_combo.grid(row=0, column=3, padx=5)

    # Assignment filter
    ttk.Label(filter_grid, text="Assignment:").grid(row=0, column=4, padx=5)
    self.all_tickets_assignment_var = tk.StringVar(value="all")
    assignment_combo = ttk.Combobox(filter_grid, textvariable=self.all_tickets_assignment_var,
                                   values=["all", "assigned", "unassigned"],
                                   state="readonly")
    assignment_combo.grid(row=0, column=5, padx=5)

    # Bind filter changes
    for combo in [status_combo, priority_combo, assignment_combo]:
        combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_all_tickets())

    # Apply filters button
    ttk.Button(filter_grid, text="Apply Filters",
              command=self.refresh_all_tickets).grid(row=0, column=6, padx=10)

    # Tickets list
    self.all_tickets_frame = ttk.Frame(all_tickets_frame)
    self.all_tickets_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.create_all_tickets_list()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_tab = create_all_tickets_tab

def create_all_tickets_list(self):
    """Create all tickets list"""
    # Clear existing widgets
    for widget in self.all_tickets_frame.winfo_children():
        widget.destroy()

    # Create treeview with checkboxes for selection
    columns = ('Select', 'ID', 'Subject', 'Submitter', 'Assignee', 'Category', 'Status', 'Priority', 'Created', 'Updated')
    self.all_tickets_tree = ttk.Treeview(self.all_tickets_frame, columns=columns, show='headings')

    # Configure columns
    column_widths = {'Select': 50, 'ID': 50, 'Subject': 200, 'Submitter': 100, 'Assignee': 100,
                    'Category': 120, 'Status': 100, 'Priority': 80, 'Created': 120, 'Updated': 120}

    for col in columns:
        self.all_tickets_tree.heading(col, text=col)
        self.all_tickets_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='vertical',
                               command=self.all_tickets_tree.yview)
    h_scrollbar = ttk.Scrollbar(self.all_tickets_frame, orient='horizontal',
                               command=self.all_tickets_tree.xview)

    self.all_tickets_tree.configure(yscrollcommand=v_scrollbar.set,
                                   xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.all_tickets_tree.grid(row=0, column=0, sticky='nsew')
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    self.all_tickets_frame.grid_rowconfigure(0, weight=1)
    self.all_tickets_frame.grid_columnconfigure(0, weight=1)

    # Bind events
    self.all_tickets_tree.bind('<Double-1>', self.on_all_ticket_double_click)
    self.all_tickets_tree.bind('<Button-1>', self.on_all_ticket_click)

    # Context menu
    self.create_all_tickets_context_menu()

    # Track selected items
    self.selected_tickets = set()

    # Load data
    self.refresh_all_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_list = create_all_tickets_list

def create_all_tickets_context_menu(self):
    """Create context menu for all tickets"""
    self.all_tickets_context_menu = tk.Menu(self.root, tearoff=0)
    self.all_tickets_context_menu.add_command(label="View Details", command=self.view_selected_all_ticket)
    self.all_tickets_context_menu.add_command(label="Assign", command=self.assign_selected_ticket)
    self.all_tickets_context_menu.add_command(label="Change Status", command=self.change_status_selected_ticket)
    self.all_tickets_context_menu.add_separator()
    self.all_tickets_context_menu.add_command(label="Select All", command=self.select_all_tickets)
    self.all_tickets_context_menu.add_command(label="Deselect All", command=self.deselect_all_tickets)
    self.all_tickets_context_menu.add_separator()
    self.all_tickets_context_menu.add_command(label="Refresh", command=self.refresh_all_tickets)

    self.all_tickets_tree.bind('<Button-3>', self.show_all_tickets_context_menu)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_all_tickets_context_menu = create_all_tickets_context_menu

def show_all_tickets_context_menu(self, event):
    """Show context menu for all tickets"""
    try:
        self.all_tickets_context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        self.all_tickets_context_menu.grab_release()

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_all_tickets_context_menu = show_all_tickets_context_menu

def on_all_ticket_click(self, event):
    """Handle click on all tickets tree"""
    region = self.all_tickets_tree.identify("region", event.x, event.y)
    if region == "cell":
        column = self.all_tickets_tree.identify_column(event.x)
        if column == '#1':  # Select column
            item = self.all_tickets_tree.identify_row(event.y)
            if item:
                self.toggle_ticket_selection(item)

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_all_ticket_click = on_all_ticket_click

def toggle_ticket_selection(self, item):
    """Toggle ticket selection"""
    values = list(self.all_tickets_tree.item(item, 'values'))
    ticket_id = values[1]

    if values[0] == '☐':  # Not selected
        values[0] = '☑'
        self.selected_tickets.add(ticket_id)
    else:  # Selected
        values[0] = '☐'
        self.selected_tickets.discard(ticket_id)

    self.all_tickets_tree.item(item, values=values)

# Attach method to HelpdeskGUI class
HelpdeskGUI.toggle_ticket_selection = toggle_ticket_selection

def select_all_tickets(self):
    """Select all visible tickets"""
    for item in self.all_tickets_tree.get_children():
        values = list(self.all_tickets_tree.item(item, 'values'))
        if values[0] == '☐':
            values[0] = '☑'
            self.selected_tickets.add(values[1])
            self.all_tickets_tree.item(item, values=values)

# Attach method to HelpdeskGUI class
HelpdeskGUI.select_all_tickets = select_all_tickets

def deselect_all_tickets(self):
    """Deselect all tickets"""
    for item in self.all_tickets_tree.get_children():
        values = list(self.all_tickets_tree.item(item, 'values'))
        if values[0] == '☑':
            values[0] = '☐'
            self.all_tickets_tree.item(item, values=values)
    self.selected_tickets.clear()

# Attach method to HelpdeskGUI class
HelpdeskGUI.deselect_all_tickets = deselect_all_tickets

def refresh_all_tickets(self):
    """Refresh all tickets list"""
    try:
        # Clear existing items and selections
        for item in self.all_tickets_tree.get_children():
            self.all_tickets_tree.delete(item)
        self.selected_tickets.clear()

        # Get tickets from database
        tickets = self.get_all_tickets()

        # Populate treeview
        for ticket in tickets:
            # Safely get values with defaults for None
            subject = ticket.get('subject') or 'No Subject'
            submitter = ticket.get('submitter') or 'Unknown'
            assignee = ticket.get('assignee') or 'Unassigned'
            category = ticket.get('category') or 'General'
            status = ticket.get('status') or 'open'
            priority = ticket.get('priority') or 'medium'
            created_at = ticket.get('created_at') or ''
            updated_at = ticket.get('updated_at') or ''

            # Format dates
            created = created_at[:16] if created_at else ''
            updated = updated_at[:16] if updated_at else ''

            self.all_tickets_tree.insert('', 'end', values=(
                '☐',  # Checkbox
                ticket.get('ticket_id', 'N/A'),
                subject[:40] if subject else 'No Subject',
                submitter[:15] if submitter else 'Unknown',
                assignee[:15] if assignee else 'Unassigned',
                category,
                status.title() if status else 'Open',
                priority.title() if priority else 'Medium',
                created,
                updated
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_all_tickets = refresh_all_tickets

def get_all_tickets(self):
    """Get all tickets from database with filters"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build where clause based on filters
        where_conditions = []
        params = []

        status_filter = self.all_tickets_status_var.get()
        if status_filter != "all":
            where_conditions.append("t.status = ?")
            params.append(status_filter)

        priority_filter = self.all_tickets_priority_var.get()
        if priority_filter != "all":
            where_conditions.append("t.priority = ?")
            params.append(priority_filter)

        assignment_filter = self.all_tickets_assignment_var.get()
        if assignment_filter == "assigned":
            where_conditions.append("t.assigned_to IS NOT NULL")
        elif assignment_filter == "unassigned":
            where_conditions.append("t.assigned_to IS NULL")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        # Use COALESCE for column compatibility between old and new schema
        cursor.execute('''
        SELECT t.ticket_id,
               COALESCE(t.subject, t.title, 'No Subject') as subject,
               COALESCE(t.category, 'General') as category,
               COALESCE(t.status, 'open') as status,
               COALESCE(t.priority, 'medium') as priority,
               COALESCE(t.created_at, t.created_datetime) as created_at,
               COALESCE(t.updated_at, t.last_updated_datetime) as updated_at,
               u1.username as submitter,
               u2.username as assignee
        FROM support_tickets t
        LEFT JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE ''' + where_clause + '''
        ORDER BY COALESCE(t.updated_at, t.last_updated_datetime) DESC
        ''', params)

        tickets = cursor.fetchall()
        conn.close()

        return [dict(ticket) for ticket in tickets]

    except Exception as e:
        messagebox.showerror("Error", f"Database error: {str(e)}")
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_all_tickets = get_all_tickets

def on_all_ticket_double_click(self, event):
    """Handle double-click on all tickets"""
    region = self.all_tickets_tree.identify("region", event.x, event.y)
    if region == "cell":
        column = self.all_tickets_tree.identify_column(event.x)
        if column != '#1':  # Not the select column
            self.view_selected_all_ticket()

# Attach method to HelpdeskGUI class
HelpdeskGUI.on_all_ticket_double_click = on_all_ticket_double_click

def view_selected_all_ticket(self):
    """View selected ticket from all tickets"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a ticket")
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_ticket_details(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_selected_all_ticket = view_selected_all_ticket

def assign_selected_ticket(self):
    """Assign selected ticket"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a ticket")
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_assign_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_selected_ticket = assign_selected_ticket

def change_status_selected_ticket(self):
    """Change status of selected ticket"""
    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a ticket")
        return

    item = self.all_tickets_tree.item(selection[0])
    ticket_id = item['values'][1]

    self.show_status_dialog(ticket_id)

# Attach method to HelpdeskGUI class
HelpdeskGUI.change_status_selected_ticket = change_status_selected_ticket

def show_bulk_actions(self):
    """Show bulk actions dialog"""
    if not self.selected_tickets:
        messagebox.showwarning("Warning", "Please select some tickets first")
        return

    bulk_window = tk.Toplevel(self.root)
    bulk_window.title("Bulk Actions")
    bulk_window.geometry("400x300")
    bulk_window.transient(self.root)
    bulk_window.grab_set()

    # Title
    ttk.Label(bulk_window, text=f"Bulk Actions ({len(self.selected_tickets)} tickets selected)",
             style='Heading.TLabel').pack(pady=10)

    # Actions frame
    actions_frame = ttk.LabelFrame(bulk_window, text="Available Actions")
    actions_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Bulk assign
    assign_frame = ttk.Frame(actions_frame)
    assign_frame.pack(fill='x', padx=5, pady=5)

    ttk.Label(assign_frame, text="Assign to:").pack(side='left')

    staff_list = self.get_available_staff()
    assign_var = tk.StringVar()
    assign_combo = ttk.Combobox(assign_frame, textvariable=assign_var, state="readonly")
    assign_combo['values'] = ["Unassigned"] + [f"{s['username']} ({s['role']})" for s in staff_list]
    assign_combo.pack(side='left', padx=5)

    ttk.Button(assign_frame, text="Assign",
              command=lambda: self.bulk_assign_tickets(assign_var.get(), staff_list, bulk_window)).pack(side='left', padx=5)

    # Bulk status change
    status_frame = ttk.Frame(actions_frame)
    status_frame.pack(fill='x', padx=5, pady=5)

    ttk.Label(status_frame, text="Change status to:").pack(side='left')

    status_var = tk.StringVar()
    status_combo = ttk.Combobox(status_frame, textvariable=status_var, state="readonly")
    status_combo['values'] = ["open", "in progress", "waiting for customer", "resolved", "closed"]
    status_combo.pack(side='left', padx=5)

    ttk.Button(status_frame, text="Change Status",
              command=lambda: self.bulk_change_status(status_var.get(), bulk_window)).pack(side='left', padx=5)

    # Close button
    ttk.Button(bulk_window, text="Close", command=bulk_window.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_bulk_actions = show_bulk_actions

def bulk_assign_tickets(self, assign_text, staff_list, window):
    """Bulk assign tickets"""
    if not assign_text:
        messagebox.showerror("Error", "Please select an assignee")
        return

    assignee_id = None
    if assign_text != "Unassigned":
        # Extract username from combo text
        username = assign_text.split(' (')[0]
        for staff in staff_list:
            if staff['username'] == username:
                assignee_id = staff['id']
                break

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for ticket_id in self.selected_tickets:
            cursor.execute('''
            UPDATE support_tickets
            SET assigned_to = ?, updated_at = ?, last_activity_at = ?
            WHERE ticket_id = ?
            ''', (assignee_id, now, now, ticket_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"{len(self.selected_tickets)} tickets assigned successfully!")
        window.destroy()
        self.refresh_all_tickets()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to assign tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_assign_tickets = bulk_assign_tickets

def bulk_change_status(self, new_status, window):
    """Bulk change ticket status"""
    if not new_status:
        messagebox.showerror("Error", "Please select a status")
        return

    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        resolved_at = now if new_status in ['resolved', 'closed'] else None

        for ticket_id in self.selected_tickets:
            cursor.execute('''
            UPDATE support_tickets
            SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
            WHERE ticket_id = ?
            ''', (new_status, resolved_at, now, now, ticket_id))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"{len(self.selected_tickets)} tickets updated successfully!")
        window.destroy()
        self.refresh_all_tickets()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to update tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_change_status = bulk_change_status

def bulk_status_change_gui(self):
    """Bulk change status of multiple selected tickets"""
    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to change ticket status.")
        return

    # Get selected tickets from all tickets view
    if not hasattr(self, 'all_tickets_tree'):
        messagebox.showerror("Error", "Please navigate to All Tickets tab first")
        return

    selection = self.all_tickets_tree.selection()
    if not selection:
        messagebox.showerror("Error", "Please select one or more tickets")
        return

    ticket_ids = [self.all_tickets_tree.item(item)['values'][0] for item in selection]

    # Create bulk status change dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Bulk Status Change")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Update {len(ticket_ids)} Tickets",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    ttk.Label(main_frame, text=f"Ticket IDs: {', '.join(map(str, ticket_ids))}").pack(pady=(0, 10))

    # Status selection
    status_frame = ttk.LabelFrame(main_frame, text="Select New Status", padding="10")
    status_frame.pack(fill='x', pady=(0, 10))

    status_var = tk.StringVar(value='open')
    statuses = ['open', 'in progress', 'waiting for customer', 'resolved', 'closed']

    for status in statuses:
        ttk.Radiobutton(status_frame, text=status.title(),
                       variable=status_var, value=status).pack(anchor='w')

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def perform_bulk_update():
        new_status = status_var.get()

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resolved_at = now if new_status in ['resolved', 'closed'] else None

            for ticket_id in ticket_ids:
                cursor.execute('''
                    UPDATE support_tickets
                    SET status = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
                    WHERE ticket_id = ?
                ''', (new_status, resolved_at, now, now, ticket_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"{len(ticket_ids)} tickets updated to {new_status.upper()}")
            dialog.destroy()
            self.refresh_all_tickets()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update tickets: {str(e)}")

    ttk.Button(button_frame, text="Update All", command=perform_bulk_update).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.bulk_status_change_gui = bulk_status_change_gui

def show_all_tickets(self):
    """Switch to all tickets tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'All Tickets':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_all_tickets = show_all_tickets

def view_all_tickets_enhanced_gui(self):
    """Enhanced view of all tickets with advanced filtering"""
    if not self.auth.has_permission('view_all_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to view all tickets.")
        return

    window = tk.Toplevel(self.root)
    window.title("All Tickets - Enhanced View")
    window.geometry("1200x700")

    main_frame = ttk.Frame(window, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Filter frame
    filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding="10")
    filter_frame.pack(fill=tk.X, pady=5)

    ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)

    filter_var = tk.StringVar(value="all")
    filters = [
        ("All tickets", "all"),
        ("Unassigned", "unassigned"),
        ("My assigned", "my_assigned"),
        ("Overdue", "overdue"),
        ("High priority", "high_priority"),
        ("Escalated", "escalated")
    ]

    for label, value in filters:
        ttk.Radiobutton(filter_frame, text=label, variable=filter_var, value=value).pack(side=tk.LEFT, padx=5)

    # Tickets treeview
    columns = ('id', 'subject', 'category', 'status', 'priority', 'submitter', 'assignee', 'created', 'due')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)

    tree.heading('id', text='ID')
    tree.heading('subject', text='Subject')
    tree.heading('category', text='Category')
    tree.heading('status', text='Status')
    tree.heading('priority', text='Priority')
    tree.heading('submitter', text='Submitter')
    tree.heading('assignee', text='Assignee')
    tree.heading('created', text='Created')
    tree.heading('due', text='Due Date')

    tree.column('id', width=50)
    tree.column('subject', width=250)
    tree.column('category', width=120)
    tree.column('status', width=100)
    tree.column('priority', width=80)
    tree.column('submitter', width=100)
    tree.column('assignee', width=100)
    tree.column('created', width=130)
    tree.column('due', width=130)

    scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=10)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

    def load_tickets():
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_conditions = []
            params = []

            filter_val = filter_var.get()
            if filter_val == "unassigned":
                where_conditions.append("t.assigned_to IS NULL")
            elif filter_val == "my_assigned":
                if self.auth and self.auth.current_user:
                    where_conditions.append("t.assigned_to = ?")
                    params.append(self.auth.current_user.get('id', 0))
            elif filter_val == "overdue":
                where_conditions.append("t.due_date IS NOT NULL AND t.due_date < ? AND COALESCE(t.status, 'open') NOT IN ('resolved', 'closed')")
                params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            elif filter_val == "high_priority":
                where_conditions.append("COALESCE(t.priority, 'medium') = 'high'")
            elif filter_val == "escalated":
                where_conditions.append("COALESCE(t.escalation_level, 0) > 0")

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            cursor.execute('''
                SELECT t.ticket_id,
                       COALESCE(t.subject, t.title, 'No Subject') as subject,
                       COALESCE(t.category, 'General') as category,
                       COALESCE(t.status, 'open') as status,
                       COALESCE(t.priority, 'medium') as priority,
                       u1.username as submitter,
                       u2.username as assignee,
                       COALESCE(t.created_at, t.created_datetime) as created_at,
                       t.due_date
                FROM support_tickets t
                LEFT JOIN users u1 ON t.user_id = u1.id
                LEFT JOIN users u2 ON t.assigned_to = u2.id
                WHERE ''' + where_clause + '''
                ORDER BY COALESCE(t.created_at, t.created_datetime) DESC
            ''', params)

            tickets = cursor.fetchall()
            conn.close()

            for ticket in tickets:
                # Safely get values with defaults
                subject = ticket['subject'] or 'No Subject'
                category = ticket['category'] or 'General'
                status = ticket['status'] or 'open'
                priority = ticket['priority'] or 'medium'
                submitter = ticket['submitter'] or 'Unknown'
                created_at = ticket['created_at'] or ''

                tree.insert('', tk.END, values=(
                    ticket['ticket_id'],
                    subject[:40] if subject else 'No Subject',
                    category,
                    status.upper() if status else 'OPEN',
                    priority.upper() if priority else 'MEDIUM',
                    submitter,
                    ticket['assignee'] or 'Unassigned',
                    created_at,
                    ticket['due_date'] or 'N/A'
                ))

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load tickets: {e}")

    ttk.Button(filter_frame, text="Apply Filter", command=load_tickets).pack(side=tk.LEFT, padx=5)
    ttk.Button(main_frame, text="View Details", command=lambda: self.view_ticket_from_tree(tree)).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=window.destroy).pack(pady=5)

    tree.bind('<Double-1>', lambda e: self.view_ticket_from_tree(tree))

    # Initial load
    load_tickets()

# Attach method to HelpdeskGUI class
HelpdeskGUI.view_all_tickets_enhanced_gui = view_all_tickets_enhanced_gui

