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

def create_new_ticket_tab(self):
    """Create new ticket tab"""
    ticket_frame = ttk.Frame(self.notebook)
    self.notebook.add(ticket_frame, text="Create Ticket")

    # Create scrollable frame
    canvas = tk.Canvas(ticket_frame)
    scrollbar = ttk.Scrollbar(ticket_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    ttk.Label(scrollable_frame, text="Create New Support Ticket", 
             style='Title.TLabel').pack(pady=10)

    # Template selection
    template_frame = ttk.LabelFrame(scrollable_frame, text="Use Template (Optional)")
    template_frame.pack(fill='x', padx=10, pady=5)

    self.template_var = tk.StringVar(value="custom")
    ttk.Radiobutton(template_frame, text="Custom Ticket", variable=self.template_var, 
                   value="custom").pack(anchor='w', padx=5, pady=2)

    # Load available templates
    templates = self.get_ticket_templates()
    for template in templates:
        ttk.Radiobutton(template_frame, text=f"{template['name']} ({template['category']})", 
                       variable=self.template_var, value=str(template['template_id']),
                       command=lambda t=template: self.load_template(t)).pack(anchor='w', padx=5, pady=2)

    # Ticket form
    form_frame = ttk.LabelFrame(scrollable_frame, text="Ticket Details")
    form_frame.pack(fill='x', padx=10, pady=5)

    # Subject
    ttk.Label(form_frame, text="Subject:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    self.subject_entry = ttk.Entry(form_frame, width=60)
    self.subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)

    # Category
    ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    self.category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=self.category_var,
                                 values=["Technical Support", "Academic Inquiry", 
                                        "Financial Services", "Account Access", "Other"],
                                 state="readonly")
    category_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text="Priority:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    self.priority_var = tk.StringVar(value="medium")
    priority_combo = ttk.Combobox(form_frame, textvariable=self.priority_var,
                                 values=["low", "medium", "high"], state="readonly")
    priority_combo.grid(row=2, column=1, sticky='ew', padx=5, pady=5)

    ttk.Label(form_frame, text="Impact:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
    self.impact_var = tk.StringVar(value="low")
    impact_combo = ttk.Combobox(form_frame, textvariable=self.impact_var,
                               values=["low", "medium", "high"], state="readonly")
    impact_combo.grid(row=3, column=1, sticky='ew', padx=5, pady=5)

    ttk.Label(form_frame, text="Urgency:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
    self.urgency_var = tk.StringVar(value="low")
    urgency_combo = ttk.Combobox(form_frame, textvariable=self.urgency_var,
                                values=["low", "medium", "high"], state="readonly")
    urgency_combo.grid(row=4, column=1, sticky='ew', padx=5, pady=5)

    # Configure grid weights
    form_frame.grid_columnconfigure(1, weight=1)

    # Message
    message_frame = ttk.LabelFrame(scrollable_frame, text="Message")
    message_frame.pack(fill='both', expand=True, padx=10, pady=5)

    self.message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    self.message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.pack(fill='x', padx=10, pady=10)

    ttk.Button(button_frame, text="Create Ticket", command=self.create_ticket, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Clear Form", command=self.clear_ticket_form).pack(side='right', padx=5)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_new_ticket_tab = create_new_ticket_tab

def get_ticket_templates(self):
    """Get available ticket templates"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT template_id, name, category, subject_template, message_template,
               default_priority, default_impact, default_urgency
        FROM ticket_templates
        WHERE is_active = 1
        ORDER BY category, name
        ''')

        templates = cursor.fetchall()
        conn.close()

        return [dict(template) for template in templates]

    except Exception as e:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_ticket_templates = get_ticket_templates

def load_template(self, template):
    """Load selected template into form"""
    try:
        self.subject_entry.delete(0, 'end')
        self.subject_entry.insert(0, template.get('subject_template', ''))

        self.category_var.set(template.get('category', ''))
        self.priority_var.set(template.get('default_priority', 'medium'))
        self.impact_var.set(template.get('default_impact', 'low'))
        self.urgency_var.set(template.get('default_urgency', 'low'))

        self.message_text.delete('1.0', 'end')
        self.message_text.insert('1.0', template.get('message_template', ''))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_template = load_template

def clear_ticket_form(self):
    """Clear the ticket creation form"""
    self.subject_entry.delete(0, 'end')
    self.category_var.set('')
    self.priority_var.set('medium')
    self.impact_var.set('low')
    self.urgency_var.set('low')
    self.message_text.delete('1.0', 'end')
    self.template_var.set('custom')

# Attach method to HelpdeskGUI class
HelpdeskGUI.clear_ticket_form = clear_ticket_form

def create_ticket(self):
    """Create new support ticket"""
    try:
        # Validate form
        subject = self.subject_entry.get().strip()
        category = self.category_var.get()
        message = self.message_text.get('1.0', 'end-1c').strip()

        if not subject:
            messagebox.showerror("Error", "Subject is required")
            return

        if not category:
            messagebox.showerror("Error", "Category is required")
            return

        if not message:
            messagebox.showerror("Error", "Message is required")
            return

        # Create ticket
        ticket_data = {
            'subject': subject,
            'message': message,
            'category': category,
            'priority': self.priority_var.get(),
            'impact': self.impact_var.get(),
            'urgency': self.urgency_var.get()
        }

        if self.create_support_ticket(ticket_data):
            messagebox.showinfo("Success", "Ticket created successfully!")
            self.clear_ticket_form()
            self.refresh_my_tickets()
            # Switch to My Tickets tab
            self.notebook.select(1)
        else:
            messagebox.showerror("Error", "Failed to create ticket")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to create ticket: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket = create_ticket

def create_support_ticket(self, ticket_data):
    """Create support ticket in database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Use both original schema column names and new schema column names for compatibility
        cursor.execute('''
        INSERT INTO support_tickets
        (user_id, title, description, subject, message, category, status, priority,
         impact, urgency, source, created_at, updated_at, last_activity_at,
         created_datetime, last_updated_datetime)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.current_user.get('id', 0),
            ticket_data['subject'],  # title (original schema)
            ticket_data['message'],  # description (original schema)
            ticket_data['subject'],  # subject (new schema)
            ticket_data['message'],  # message (new schema)
            ticket_data['category'],
            'open',
            ticket_data['priority'],
            ticket_data['impact'],
            ticket_data['urgency'],
            'web',
            now, now, now,  # created_at, updated_at, last_activity_at
            now, now  # created_datetime, last_updated_datetime (original schema)
        ))

        # Get the created ticket ID
        ticket_id = cursor.lastrowid

        conn.commit()
        conn.close()

        # Auto-send email notifications
        self.auto_send_ticket_notifications(ticket_id, "created")

        return True

    except Exception as e:
        messagebox.showerror("Error", f"Database error: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_support_ticket = create_support_ticket

def show_create_ticket(self):
    """Switch to create ticket tab"""
    # Find the create ticket tab and select it
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Create Ticket':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_create_ticket = show_create_ticket

def create_ticket_enhanced(self):
    """Enhanced ticket creation with templates and validation"""
    if not self.current_user:
        messagebox.showerror("Error", "You must be logged in to create a support ticket.")
        return

    if not self.has_permission('create_ticket'):
        messagebox.showerror("Permission Denied", "You don't have permission to create support tickets.")
        return

    # Create enhanced ticket creation dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Create Enhanced Ticket")
    dialog.geometry("700x600")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main container
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    # Title
    ttk.Label(main_frame, text="Create New Support Ticket",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

    # Template selection
    template_frame = ttk.LabelFrame(main_frame, text="Template Selection", padding="10")
    template_frame.pack(fill='x', pady=(0, 10))

    ttk.Label(template_frame, text="Select a template to auto-fill form:").pack(anchor='w')

    template_var = tk.StringVar(value='custom')
    template_combo = ttk.Combobox(template_frame, textvariable=template_var, state="readonly", width=50)
    template_combo.pack(fill='x', pady=5)

    # Load templates
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT template_id, name, description FROM ticket_templates
            WHERE is_active = 1 ORDER BY category, name
        ''')
        templates = cursor.fetchall()
        conn.close()

        template_list = ['Custom (No Template)']
        template_map = {0: None}

        for idx, (tid, name, desc) in enumerate(templates, 1):
            template_list.append(f"{name} - {desc}")
            template_map[idx] = tid

        template_combo['values'] = template_list
    except Exception as e:
        print(f"Error loading templates: {e}")
        template_combo['values'] = ['Custom (No Template)']
        template_map = {0: None}

    # Form fields
    form_frame = ttk.LabelFrame(main_frame, text="Ticket Information", padding="10")
    form_frame.pack(fill='both', expand=True, pady=(0, 10))

    # Subject
    ttk.Label(form_frame, text="Subject *").grid(row=0, column=0, sticky='w', pady=2)
    subject_entry = ttk.Entry(form_frame, width=60)
    subject_entry.grid(row=0, column=1, columnspan=2, sticky='ew', pady=2)

    # Category with subcategory
    ttk.Label(form_frame, text="Category *").grid(row=1, column=0, sticky='w', pady=2)
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(form_frame, textvariable=category_var, state="readonly", width=28)
    category_combo['values'] = ['Technical Support', 'Academic Inquiry', 'Financial Services',
                                'Account Access', 'Other']
    category_combo.grid(row=1, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text="Subcategory").grid(row=1, column=2, sticky='w', pady=2, padx=(10,0))
    subcategory_var = tk.StringVar()
    subcategory_combo = ttk.Combobox(form_frame, textvariable=subcategory_var, state="readonly", width=25)
    subcategory_combo.grid(row=1, column=3, sticky='w', pady=2)

    # Priority, Impact, Urgency
    ttk.Label(form_frame, text="Priority *").grid(row=2, column=0, sticky='w', pady=2)
    priority_var = tk.StringVar(value='medium')
    priority_combo = ttk.Combobox(form_frame, textvariable=priority_var, state="readonly", width=15)
    priority_combo['values'] = ['low', 'medium', 'high']
    priority_combo.grid(row=2, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text="Impact *").grid(row=3, column=0, sticky='w', pady=2)
    impact_var = tk.StringVar(value='low')
    impact_combo = ttk.Combobox(form_frame, textvariable=impact_var, state="readonly", width=15)
    impact_combo['values'] = ['low', 'medium', 'high']
    impact_combo.grid(row=3, column=1, sticky='w', pady=2)

    ttk.Label(form_frame, text="Urgency *").grid(row=4, column=0, sticky='w', pady=2)
    urgency_var = tk.StringVar(value='low')
    urgency_combo = ttk.Combobox(form_frame, textvariable=urgency_var, state="readonly", width=15)
    urgency_combo['values'] = ['low', 'medium', 'high']
    urgency_combo.grid(row=4, column=1, sticky='w', pady=2)

    # Message
    ttk.Label(form_frame, text="Description *").grid(row=5, column=0, sticky='nw', pady=2)
    message_text = scrolledtext.ScrolledText(form_frame, height=10, width=60)
    message_text.grid(row=5, column=1, columnspan=3, sticky='ew', pady=2)

    # Configure grid weights
    form_frame.columnconfigure(1, weight=1)

    # Update subcategory when category changes
    def update_subcategories(event=None):
        cat = category_var.get()
        subcategories_map = {
            "Technical Support": ["Login Issues", "Performance Problems", "Software Bugs", "Hardware Problems"],
            "Academic Inquiry": ["Course Information", "Grading Questions", "Academic Records", "Transcript Requests"],
            "Financial Services": ["Payment Plans", "Refunds", "Financial Aid", "Billing Inquiries"],
            "Account Access": ["Password Reset", "Account Locked", "Permission Issues", "Profile Updates"],
            "Other": ["General Inquiry", "Feedback", "Complaint", "Suggestion"]
        }
        subcategory_combo['values'] = subcategories_map.get(cat, [])
        if subcategory_combo['values']:
            subcategory_combo.current(0)

    category_combo.bind('<<ComboboxSelected>>', update_subcategories)

    # Load template when selected
    def load_template(event=None):
        idx = template_combo.current()
        if idx > 0 and idx in template_map:
            template_id = template_map[idx]
            self.create_ticket_from_template_gui(template_id, subject_entry, category_var,
                                                 priority_var, impact_var, urgency_var, message_text)

    template_combo.bind('<<ComboboxSelected>>', load_template)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(0, 5))

    def submit_ticket():
        subject = subject_entry.get().strip()
        category = category_var.get()
        subcategory = subcategory_var.get()
        message = message_text.get('1.0', 'end-1c').strip()
        priority = priority_var.get()
        impact = impact_var.get()
        urgency = urgency_var.get()

        if not subject or not category or not message:
            messagebox.showerror("Error", "Subject, category, and description are required")
            return

        # Create ticket using enhanced method
        ticket_id = self.create_ticket_with_details(subject, message, category, priority,
                                                   impact, urgency, subcategory)
        if ticket_id:
            messagebox.showinfo("Success", f"Ticket #{ticket_id} created successfully!")
            dialog.destroy()
            self.refresh_my_tickets()
        else:
            messagebox.showerror("Error", "Failed to create ticket")

    ttk.Button(button_frame, text="Create Ticket", command=submit_ticket).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_enhanced = create_ticket_enhanced

def create_ticket_from_template_gui(self, template_id, subject_entry, category_var,
                                    priority_var, impact_var, urgency_var, message_text):
    """Load template data into form fields"""
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

        # Unpack template data (adjust indices based on schema)
        # Assuming: template_id, name, description, category, subject_template, message_template,
        #           default_priority, default_impact, default_urgency, form_fields
        _, name, desc, category, subj_tpl, msg_tpl, pri, imp, urg, form_fields = template[:10]

        # Fill in form fields
        if subj_tpl:
            subject_entry.delete(0, 'end')
            subject_entry.insert(0, subj_tpl)

        if category:
            category_var.set(category)

        if pri:
            priority_var.set(pri)
        if imp:
            impact_var.set(imp)
        if urg:
            urgency_var.set(urg)

        if msg_tpl:
            message_text.delete('1.0', 'end')
            message_text.insert('1.0', msg_tpl)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load template: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_from_template_gui = create_ticket_from_template_gui

def create_custom_ticket_gui(self):
    """Create ticket with custom form fields (wrapper for create_ticket_enhanced)"""
    # This is essentially the same as create_ticket_enhanced but can be extended
    # with dynamic custom fields from database
    self.create_ticket_enhanced()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_custom_ticket_gui = create_custom_ticket_gui

def create_ticket_with_details(self, subject, message, category, priority, impact, urgency, subcategory=None):
    """Programmatic ticket creation with full details"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Determine SLA and department assignment
        cursor.execute('''
            SELECT sla_id, first_response_hours, resolution_hours
            FROM sla_policies
            WHERE priority = ? AND impact = ? AND urgency = ? AND is_active = 1
            ORDER BY sla_id LIMIT 1
        ''', (priority, impact, urgency))

        sla_result = cursor.fetchone()
        due_date = None
        if sla_result:
            resolution_hours = sla_result[2]
            due_date = (datetime.now() + timedelta(hours=resolution_hours)).strftime('%Y-%m-%d %H:%M:%S')

        # Auto-assign to department based on category
        assigned_to = None
        department = None

        category_dept_map = {
            "Technical Support": "IT Support",
            "Academic Inquiry": "Academic Affairs",
            "Financial Services": "Financial Services",
            "Account Access": "IT Support"
        }

        if category in category_dept_map:
            department = category_dept_map[category]

            # Find available staff in the department
            cursor.execute('''
                SELECT u.id FROM users u
                WHERE u.role IN ('staff', 'admin')
                ORDER BY u.last_login_at DESC LIMIT 1
            ''')

            dept_staff = cursor.fetchone()
            if dept_staff:
                assigned_to = dept_staff[0]

        # Get current time
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert ticket into database
        cursor.execute('''
            INSERT INTO support_tickets
            (user_id, assigned_to, subject, message, category, subcategory, status, priority,
             impact, urgency, source, due_date, department, created_at, updated_at, last_activity_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (self.current_user.get('id', 0), assigned_to, subject, message, category, subcategory,
              'open', priority, impact, urgency, 'web', due_date, department, now, now, now))

        conn.commit()
        ticket_id = cursor.lastrowid
        conn.close()

        # Send notifications
        self.auto_send_ticket_notifications(ticket_id, "created")

        return ticket_id

    except Exception as e:
        messagebox.showerror("Error", f"Failed to create ticket: {str(e)}")
        return None

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_ticket_with_details = create_ticket_with_details

