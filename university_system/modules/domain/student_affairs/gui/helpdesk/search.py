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

def show_search_tickets(self):
    """Show advanced search dialog"""
    search_window = tk.Toplevel(self.root)
    search_window.title("Advanced Ticket Search")
    search_window.geometry("600x500")
    search_window.transient(self.root)
    search_window.grab_set()

    # Search form
    form_frame = ttk.LabelFrame(search_window, text="Search Criteria")
    form_frame.pack(fill='x', padx=10, pady=10)

    # Text search
    ttk.Label(form_frame, text="Search Text:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    search_text_entry = ttk.Entry(form_frame, width=40)
    search_text_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)

    # Status filter
    ttk.Label(form_frame, text="Status:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    status_var = tk.StringVar(value="all")
    status_combo = ttk.Combobox(form_frame, textvariable=status_var,
                               values=["all", "open", "in progress", "resolved", "closed"],
                               state="readonly")
    status_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)

    # Priority filter
    ttk.Label(form_frame, text="Priority:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    priority_var = tk.StringVar(value="all")
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var,
                                 values=["all", "low", "medium", "high"],
                                 state="readonly")
    priority_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)

    # Date range
    ttk.Label(form_frame, text="Date From:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
    date_from_entry = ttk.Entry(form_frame, width=15)
    date_from_entry.grid(row=3, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(form_frame, text="Date To:").grid(row=3, column=2, sticky='w', padx=5, pady=5)
    date_to_entry = ttk.Entry(form_frame, width=15)
    date_to_entry.grid(row=3, column=3, sticky='w', padx=5, pady=5)

    form_frame.grid_columnconfigure(1, weight=1)

    # Results frame
    results_frame = ttk.LabelFrame(search_window, text="Search Results")
    results_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Results treeview
    columns = ('ID', 'Subject', 'Status', 'Priority', 'Created')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings')

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=100)

    # Scrollbar for results
    results_scroll = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
    results_tree.configure(yscrollcommand=results_scroll.set)

    results_tree.pack(side='left', fill='both', expand=True)
    results_scroll.pack(side='right', fill='y')

    # Search function
    def perform_search():
        # Clear existing results
        for item in results_tree.get_children():
            results_tree.delete(item)

        # Get search criteria
        criteria = {
            'text': search_text_entry.get().strip(),
            'status': status_var.get() if status_var.get() != 'all' else None,
            'priority': priority_var.get() if priority_var.get() != 'all' else None,
            'date_from': date_from_entry.get().strip(),
            'date_to': date_to_entry.get().strip()
        }

        # Perform search
        results = self.search_tickets(criteria)

        # Display results
        for ticket in results:
            results_tree.insert('', 'end', values=(
                ticket.get('ticket_id', ''),
                ticket.get('subject', '')[:40],
                ticket.get('status', '').title(),
                ticket.get('priority', '').title(),
                ticket.get('created_at', '')[:16]
            ))

    # Buttons
    button_frame = ttk.Frame(search_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(button_frame, text="Search", command=perform_search, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Clear", 
              command=lambda: self.clear_search_form(search_text_entry, status_var, priority_var, 
                                                    date_from_entry, date_to_entry, results_tree)).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Close", command=search_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_search_tickets = show_search_tickets

def search_tickets(self, criteria):
    """Search tickets based on criteria"""
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        where_conditions = []
        params = []

        # Check permissions
        if not self.has_permission('view_all_tickets'):
            where_conditions.append("t.user_id = ?")
            params.append(self.current_user.get('id', 0))

        # Text search
        if criteria.get('text'):
            where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
            text_param = f"%{criteria['text']}%"
            params.extend([text_param, text_param])

        # Status filter
        if criteria.get('status'):
            where_conditions.append("t.status = ?")
            params.append(criteria['status'])

        # Priority filter
        if criteria.get('priority'):
            where_conditions.append("t.priority = ?")
            params.append(criteria['priority'])

        # Date filters
        if criteria.get('date_from'):
            where_conditions.append("DATE(t.created_at) >= ?")
            params.append(criteria['date_from'])

        if criteria.get('date_to'):
            where_conditions.append("DATE(t.created_at) <= ?")
            params.append(criteria['date_to'])

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        cursor.execute(f'''
        SELECT t.ticket_id, t.subject, t.status, t.priority, t.created_at
        FROM support_tickets t
        WHERE {where_clause}
        ORDER BY t.created_at DESC
        LIMIT 100
        ''', params)

        results = cursor.fetchall()
        conn.close()

        return [dict(result) for result in results]

    except Exception as e:
        messagebox.showerror("Error", f"Search failed: {str(e)}")
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.search_tickets = search_tickets

def clear_search_form(self, text_entry, status_var, priority_var, date_from, date_to, results_tree):
    """Clear search form"""
    text_entry.delete(0, 'end')
    status_var.set('all')
    priority_var.set('all')
    date_from.delete(0, 'end')
    date_to.delete(0, 'end')

    for item in results_tree.get_children():
        results_tree.delete(item)

# Attach method to HelpdeskGUI class
HelpdeskGUI.clear_search_form = clear_search_form

def show_saved_searches(self):
    """Show and execute saved searches"""
    search_window = tk.Toplevel(self.root)
    search_window.title("Saved Searches")
    search_window.geometry("600x400")
    search_window.transient(self.root)
    search_window.grab_set()

    ttk.Label(search_window, text="Saved Searches", style='Heading.TLabel').pack(pady=10)

    # Create treeview for saved searches
    columns = ('Name', 'Created')
    searches_tree = ttk.Treeview(search_window, columns=columns, show='headings', height=10)

    for col in columns:
        searches_tree.heading(col, text=col)
        searches_tree.column(col, width=200)

    searches_tree.pack(fill='both', expand=True, padx=10, pady=10)

    # Load saved searches
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT search_id, name, search_criteria, created_at
        FROM saved_searches 
        WHERE user_id = ? 
        ORDER BY created_at DESC
        ''', (self.current_user.get('id', 0),))

        searches = cursor.fetchall()

        for search in searches:
            searches_tree.insert('', 'end', values=(search[1], search[3][:16]))

        conn.close()

        def execute_selected_search():
            selection = searches_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a search")
                return

            item = searches_tree.item(selection[0])
            search_name = item['values'][0]

            # Find the search data
            for search in searches:
                if search[1] == search_name:
                    try:
                        criteria = json.loads(search[2])
                        results = self.execute_search_criteria(criteria)
                        search_window.destroy()
                        self.display_search_results_window(results, f"Results for '{search_name}'")
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid search data")
                    break

        button_frame = ttk.Frame(search_window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Execute Search", command=execute_selected_search,
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=search_window.destroy).pack(side='left', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load saved searches: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_saved_searches = show_saved_searches

def execute_search_criteria(self, criteria):
    """Execute search with given criteria - backend function"""
    try:
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        where_conditions = []
        params = []

        # Check permissions
        if not self.has_permission('view_all_tickets'):
            where_conditions.append("t.user_id = ?")
            params.append(self.current_user['id'])

        # Text search
        if 'text' in criteria:
            where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
            text_param = f"%{criteria['text']}%"
            params.extend([text_param, text_param])

        # Status filter
        if 'status' in criteria:
            where_conditions.append("t.status = ?")
            params.append(criteria['status'])

        # Priority filter
        if 'priority' in criteria:
            where_conditions.append("t.priority = ?")
            params.append(criteria['priority'])

        # Category filter
        if 'category' in criteria:
            where_conditions.append("t.category = ?")
            params.append(criteria['category'])

        # Date range
        if 'start_date' in criteria:
            where_conditions.append("DATE(t.created_at) >= ?")
            params.append(criteria['start_date'])

        if 'end_date' in criteria:
            where_conditions.append("DATE(t.created_at) <= ?")
            params.append(criteria['end_date'])

        # Build final query
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f'''
        SELECT t.*, u1.username as submitter, u2.username as assignee
        FROM support_tickets t
        JOIN users u1 ON t.user_id = u1.id
        LEFT JOIN users u2 ON t.assigned_to = u2.id
        WHERE {where_clause}
        ORDER BY t.updated_at DESC
        '''

        cursor.execute(query, params)
        results = cursor.fetchall()

        conn.close()
        return [dict(result) for result in results]

    except Exception as e:
        messagebox.showerror("Error", f"Search failed: {str(e)}")
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.execute_search_criteria = execute_search_criteria

def display_search_results_window(self, results, title="Search Results"):
    """Display search results in a new window"""
    results_window = tk.Toplevel(self.root)
    results_window.title(title)
    results_window.geometry("1000x600")
    results_window.transient(self.root)

    ttk.Label(results_window, text=title, style='Heading.TLabel').pack(pady=10)

    if not results:
        ttk.Label(results_window, text="No tickets found matching your search criteria.").pack(pady=20)
        ttk.Button(results_window, text="Close", command=results_window.destroy).pack(pady=10)
        return

    # Create treeview for results
    columns = ('ID', 'Subject', 'From', 'Assigned', 'Status', 'Priority', 'Updated')
    results_tree = ttk.Treeview(results_window, columns=columns, show='headings')

    column_widths = {'ID': 50, 'Subject': 200, 'From': 100, 'Assigned': 100, 
                    'Status': 100, 'Priority': 80, 'Updated': 120}

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=column_widths.get(col, 100))

    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(results_window, orient='vertical', command=results_tree.yview)
    h_scrollbar = ttk.Scrollbar(results_window, orient='horizontal', command=results_tree.xview)

    results_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    results_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
    v_scrollbar.pack(side='right', fill='y')

    # Populate results
    for ticket in results:
        # Safely get values with defaults
        subject = ticket.get('subject') or 'No Subject'
        submitter = ticket.get('submitter') or 'Unknown'
        assignee = ticket.get('assignee') or 'Unassigned'
        status = ticket.get('status') or 'open'
        priority = ticket.get('priority') or 'medium'
        updated_at = ticket.get('updated_at') or ''

        results_tree.insert('', 'end', values=(
            ticket.get('ticket_id', 'N/A'),
            subject[:30] if subject else 'No Subject',
            submitter[:15] if submitter else 'Unknown',
            assignee[:15] if assignee else 'Unassigned',
            status.title() if status else 'Open',
            priority.title() if priority else 'Medium',
            updated_at[:16] if updated_at else ''
        ))

    # Double-click to view ticket
    def on_double_click(event):
        selection = results_tree.selection()
        if selection:
            item = results_tree.item(selection[0])
            ticket_id = item['values'][0]
            self.show_ticket_details(ticket_id)

    results_tree.bind('<Double-1>', on_double_click)

    # Close button
    ttk.Button(results_window, text="Close", command=results_window.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_search_results_window = display_search_results_window

def advanced_search_tickets_gui(self):
    """Advanced ticket search with multiple filters"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Advanced Ticket Search")
    dialog.geometry("700x700")

    # Main frame with scrollbar
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Search criteria storage
    criteria = {}

    # Text search
    ttk.Label(main_frame, text="Search Text (Subject/Message):").grid(row=0, column=0, sticky=tk.W, pady=5)
    text_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=text_var, width=50).grid(row=0, column=1, pady=5, padx=5)

    # Status filter
    ttk.Label(main_frame, text="Status Filter:").grid(row=1, column=0, sticky=tk.W, pady=5)
    status_var = tk.StringVar(value="all")
    status_combo = ttk.Combobox(main_frame, textvariable=status_var, width=47,
                                values=["all", "open", "in progress", "resolved", "closed"])
    status_combo.grid(row=1, column=1, pady=5, padx=5)

    # Priority filter
    ttk.Label(main_frame, text="Priority Filter:").grid(row=2, column=0, sticky=tk.W, pady=5)
    priority_var = tk.StringVar(value="all")
    priority_combo = ttk.Combobox(main_frame, textvariable=priority_var, width=47,
                                  values=["all", "low", "medium", "high"])
    priority_combo.grid(row=2, column=1, pady=5, padx=5)

    # Category filter
    ttk.Label(main_frame, text="Category Filter:").grid(row=3, column=0, sticky=tk.W, pady=5)
    category_var = tk.StringVar(value="all")
    categories = ["all", "Technical Support", "Academic Inquiry", "Financial Services",
                  "Account Access", "Other"]
    category_combo = ttk.Combobox(main_frame, textvariable=category_var, width=47, values=categories)
    category_combo.grid(row=3, column=1, pady=5, padx=5)

    # Date range
    ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, pady=5)
    start_date_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=start_date_var, width=50).grid(row=4, column=1, pady=5, padx=5)

    ttk.Label(main_frame, text="End Date (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, pady=5)
    end_date_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=end_date_var, width=50).grid(row=5, column=1, pady=5, padx=5)

    # Assigned user filter (admin only)
    assigned_label = ttk.Label(main_frame, text="Assigned To (Username):")
    assigned_var = tk.StringVar()
    assigned_entry = ttk.Entry(main_frame, textvariable=assigned_var, width=50)

    if self.auth.has_permission('view_all_tickets'):
        assigned_label.grid(row=6, column=0, sticky=tk.W, pady=5)
        assigned_entry.grid(row=6, column=1, pady=5, padx=5)

    # Save search name
    ttk.Label(main_frame, text="Save Search As:").grid(row=7, column=0, sticky=tk.W, pady=5)
    save_name_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=save_name_var, width=50).grid(row=7, column=1, pady=5, padx=5)

    # Results display
    results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding="10")
    results_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

    # Results treeview
    columns = ('id', 'subject', 'from', 'assigned', 'status', 'priority', 'updated')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

    results_tree.heading('id', text='ID')
    results_tree.heading('subject', text='Subject')
    results_tree.heading('from', text='From')
    results_tree.heading('assigned', text='Assigned')
    results_tree.heading('status', text='Status')
    results_tree.heading('priority', text='Priority')
    results_tree.heading('updated', text='Updated')

    results_tree.column('id', width=40)
    results_tree.column('subject', width=200)
    results_tree.column('from', width=100)
    results_tree.column('assigned', width=100)
    results_tree.column('status', width=80)
    results_tree.column('priority', width=60)
    results_tree.column('updated', width=120)

    scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=scrollbar.set)

    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def execute_search():
        """Execute the search with current criteria"""
        # Build criteria dictionary
        search_criteria = {}

        if text_var.get().strip():
            search_criteria['text'] = text_var.get().strip()

        if status_var.get() != "all":
            search_criteria['status'] = status_var.get()

        if priority_var.get() != "all":
            search_criteria['priority'] = priority_var.get()

        if category_var.get() != "all":
            search_criteria['category'] = category_var.get()

        if start_date_var.get().strip():
            search_criteria['start_date'] = start_date_var.get().strip()

        if end_date_var.get().strip():
            search_criteria['end_date'] = end_date_var.get().strip()

        if assigned_var.get().strip() and self.auth.has_permission('view_all_tickets'):
            search_criteria['assigned_user'] = assigned_var.get().strip()

        # Save search if name provided
        if save_name_var.get().strip():
            self.save_search_criteria_gui(save_name_var.get().strip(), search_criteria)

        # Execute search
        results = self.execute_search_gui(search_criteria)

        # Display results
        self.display_search_results_gui(results, results_tree)

    # Button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=9, column=0, columnspan=2, pady=10)

    ttk.Button(btn_frame, text="Search", command=execute_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Load Saved Search",
              command=lambda: self.load_saved_searches_gui(results_tree)).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Clear", command=lambda: [
        text_var.set(''), status_var.set('all'), priority_var.set('all'),
        category_var.set('all'), start_date_var.set(''), end_date_var.set(''),
        assigned_var.set(''), save_name_var.set(''),
        results_tree.delete(*results_tree.get_children())
    ]).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.advanced_search_tickets_gui = advanced_search_tickets_gui

def save_search_criteria_gui(self, name, criteria):
    """Save search criteria for later use"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_id = self.auth.current_user['id']

        cursor.execute('''
            INSERT INTO saved_searches (user_id, name, search_criteria, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, json.dumps(criteria), now))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Search '{name}' saved successfully!")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to save search: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.save_search_criteria_gui = save_search_criteria_gui

def load_saved_searches_gui(self, results_tree):
    """Load and execute saved searches"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        user_id = self.auth.current_user['id']

        cursor.execute('''
            SELECT search_id, name, search_criteria
            FROM saved_searches
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))

        searches = cursor.fetchall()
        conn.close()

        if not searches:
            messagebox.showinfo("No Saved Searches", "No saved searches found.")
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Saved Search")
        dialog.geometry("400x300")

        ttk.Label(dialog, text="Select a saved search:", padding="10").pack()

        # Listbox with saved searches
        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        search_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        search_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=search_listbox.yview)

        for search_id, name, criteria_json in searches:
            search_listbox.insert(tk.END, name)

        def execute_selected():
            selection = search_listbox.curselection()
            if selection:
                idx = selection[0]
                search_id, name, criteria_json = searches[idx]

                try:
                    criteria = json.loads(criteria_json)
                    results = self.execute_search_gui(criteria)
                    self.display_search_results_gui(results, results_tree)
                    dialog.destroy()
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "Corrupted search data")

        ttk.Button(dialog, text="Execute", command=execute_selected).pack(pady=5)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load searches: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_saved_searches_gui = load_saved_searches_gui

def execute_search_gui(self, criteria):
    """Execute search with given criteria"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query
        where_conditions = []
        params = []

        # Check permissions
        if not self.auth.has_permission('view_all_tickets'):
            where_conditions.append("t.user_id = ?")
            params.append(self.auth.current_user['id'])

        # Text search
        if 'text' in criteria:
            where_conditions.append("(t.subject LIKE ? OR t.message LIKE ?)")
            text_param = f"%{criteria['text']}%"
            params.extend([text_param, text_param])

        # Status filter
        if 'status' in criteria:
            where_conditions.append("t.status = ?")
            params.append(criteria['status'])

        # Priority filter
        if 'priority' in criteria:
            where_conditions.append("t.priority = ?")
            params.append(criteria['priority'])

        # Category filter
        if 'category' in criteria:
            where_conditions.append("t.category = ?")
            params.append(criteria['category'])

        # Date range
        if 'start_date' in criteria:
            where_conditions.append("DATE(t.created_at) >= ?")
            params.append(criteria['start_date'])

        if 'end_date' in criteria:
            where_conditions.append("DATE(t.created_at) <= ?")
            params.append(criteria['end_date'])

        # Assigned user
        if 'assigned_user' in criteria:
            where_conditions.append("u2.username = ?")
            params.append(criteria['assigned_user'])

        # Build final query
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f'''
            SELECT t.*, u1.username as submitter, u2.username as assignee
            FROM support_tickets t
            JOIN users u1 ON t.user_id = u1.id
            LEFT JOIN users u2 ON t.assigned_to = u2.id
            WHERE {where_clause}
            ORDER BY t.updated_at DESC
        '''

        cursor.execute(query, params)
        results = cursor.fetchall()

        conn.close()
        return results

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Search failed: {e}")
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.execute_search_gui = execute_search_gui

def display_search_results_gui(self, results, tree_widget):
    """Display search results in the treeview"""
    # Clear existing results
    for item in tree_widget.get_children():
        tree_widget.delete(item)

    if not results:
        messagebox.showinfo("No Results", "No tickets found matching your search criteria.")
        return

    # Populate results
    for ticket in results:
        # Safely get values with defaults
        subject = ticket.get('subject') or 'No Subject'
        submitter = ticket.get('submitter') or 'Unknown'
        assignee = ticket.get('assignee') or 'Unassigned'
        status = ticket.get('status') or 'open'
        priority = ticket.get('priority') or 'medium'
        updated_at = ticket.get('updated_at') or ''

        tree_widget.insert('', tk.END, values=(
            ticket.get('ticket_id', 'N/A'),
            subject[:40] if subject else 'No Subject',
            submitter[:20] if submitter else 'Unknown',
            assignee[:20] if assignee else 'Unassigned',
            status.upper() if status else 'OPEN',
            priority.upper() if priority else 'MEDIUM',
            updated_at
        ))

    messagebox.showinfo("Search Complete", f"Found {len(results)} ticket(s) matching your criteria.")

# Attach method to HelpdeskGUI class
HelpdeskGUI.display_search_results_gui = display_search_results_gui

def rebuild_search_indexes_gui(self):
    """Rebuild full-text search indexes"""
    if not self.auth.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to rebuild search indexes.")
        return

    if not messagebox.askyesno("Confirm", "Rebuild search indexes? This may take a moment."):
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Update search keywords for knowledge base articles
        cursor.execute('''
            UPDATE knowledge_base
            SET search_keywords = LOWER(title || ' ' || content || ' ' || COALESCE(tags, ''))
        ''')

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", "Search indexes rebuilt successfully!")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to rebuild indexes: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.rebuild_search_indexes_gui = rebuild_search_indexes_gui

