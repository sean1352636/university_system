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

def create_analytics_tab(self):
    """Create analytics tab"""
    analytics_frame = ttk.Frame(self.notebook)
    self.notebook.add(analytics_frame, text="Analytics")

    # Create scrollable frame
    canvas = tk.Canvas(analytics_frame)
    scrollbar = ttk.Scrollbar(analytics_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    ttk.Label(scrollable_frame, text="Analytics Dashboard", 
         style='Title.TLabel').pack(pady=10)

    # Time period selector
    period_frame = ttk.Frame(scrollable_frame)
    period_frame.pack(fill='x', padx=10, pady=5)

    ttk.Label(period_frame, text="Time Period:").pack(side='left')
    self.analytics_period_var = tk.StringVar(value="30d")
    period_combo = ttk.Combobox(period_frame, textvariable=self.analytics_period_var,
                           values=["7d", "30d", "90d", "1y"], state="readonly", width=10)
    period_combo.pack(side='left', padx=5)
    period_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_analytics())

    ttk.Button(period_frame, text="Refresh", command=self.refresh_analytics).pack(side='left', padx=5)

    # Analytics content frame
    self.analytics_content_frame = ttk.Frame(scrollable_frame)
    self.analytics_content_frame.pack(fill='both', expand=True, padx=10, pady=10)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Load initial analytics
    self.refresh_analytics()

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_analytics_tab = create_analytics_tab

def refresh_analytics(self):
    """Refresh analytics data"""
    try:
        # Clear existing content
        for widget in self.analytics_content_frame.winfo_children():
            widget.destroy()
        
        # Get analytics data
        period = self.analytics_period_var.get()
        analytics_data = self.get_analytics_data(period)
        
        # Overall statistics
        stats_frame = ttk.LabelFrame(self.analytics_content_frame, text=f"Overview ({period})")
        stats_frame.pack(fill='x', pady=5)
        
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill='x', padx=10, pady=10)
        
        # Display key metrics
        metrics = [
            ("Total Tickets", analytics_data.get('total_tickets', 0)),
            ("Open Tickets", analytics_data.get('open_tickets', 0)),
            ("Resolved Tickets", analytics_data.get('resolved_tickets', 0)),
            ("Resolution Rate", f"{analytics_data.get('resolution_rate', 0):.1f}%"),
            ("Avg Resolution Time", f"{analytics_data.get('avg_resolution_hours', 0):.1f}h"),
            ("Customer Satisfaction", f"{analytics_data.get('avg_satisfaction', 0):.1f}/5.0")
        ]
        
        for i, (label, value) in enumerate(metrics):
            row = i // 3
            col = (i % 3) * 2
            
            ttk.Label(stats_grid, text=f"{label}:", style='Heading.TLabel').grid(
                row=row, column=col, sticky='w', padx=5, pady=2)
            ttk.Label(stats_grid, text=str(value)).grid(
                row=row, column=col+1, sticky='w', padx=20, pady=2)
        
        # Category breakdown
        if analytics_data.get('categories'):
            category_frame = ttk.LabelFrame(self.analytics_content_frame, text="Tickets by Category")
            category_frame.pack(fill='x', pady=5)
            
            category_tree = ttk.Treeview(category_frame, columns=('Category', 'Count', 'Percentage'), 
                                       show='headings', height=6)
            category_tree.heading('Category', text='Category')
            category_tree.heading('Count', text='Count')
            category_tree.heading('Percentage', text='Percentage')
            
            for category, count in analytics_data['categories'].items():
                percentage = (count / analytics_data.get('total_tickets', 1)) * 100
                category_tree.insert('', 'end', values=(category, count, f"{percentage:.1f}%"))
            
            category_tree.pack(fill='x', padx=5, pady=5)
        
        # Staff performance
        if analytics_data.get('staff_performance'):
            staff_frame = ttk.LabelFrame(self.analytics_content_frame, text="Staff Performance")
            staff_frame.pack(fill='x', pady=5)
            
            staff_tree = ttk.Treeview(staff_frame, columns=('Staff', 'Assigned', 'Resolved', 'Rate'), 
                                    show='headings', height=6)
            staff_tree.heading('Staff', text='Staff')
            staff_tree.heading('Assigned', text='Assigned')
            staff_tree.heading('Resolved', text='Resolved')
            staff_tree.heading('Rate', text='Resolution Rate')
            
            for staff_data in analytics_data['staff_performance']:
                rate = (staff_data['resolved'] / staff_data['assigned'] * 100) if staff_data['assigned'] > 0 else 0
                staff_tree.insert('', 'end', values=(
                    staff_data['username'], 
                    staff_data['assigned'], 
                    staff_data['resolved'], 
                    f"{rate:.1f}%"
                ))
            
            staff_tree.pack(fill='x', padx=5, pady=5)
        
    except Exception as e:
        ttk.Label(self.analytics_content_frame, text=f"Error loading analytics: {str(e)}", 
                 style='Error.TLabel').pack()

# Attach method to HelpdeskGUI class
HelpdeskGUI.refresh_analytics = refresh_analytics

def get_analytics_data(self, period):
    """Get analytics data for specified period"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculate date range
        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        analytics_data = {}
        
        # Overall statistics
        cursor.execute('''
        SELECT 
            COUNT(*) as total_tickets,
            COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
            COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
            AVG(CASE WHEN resolved_at IS NOT NULL 
                THEN (julianday(resolved_at) - julianday(created_at)) * 24 
                ELSE NULL END) as avg_resolution_hours,
            AVG(satisfaction_rating) as avg_satisfaction
        FROM support_tickets
        WHERE created_at >= ?
        ''', (start_date,))
        
        result = cursor.fetchone()
        if result:
            total = result[0]
            analytics_data.update({
                'total_tickets': total,
                'open_tickets': result[1],
                'resolved_tickets': result[2],
                'resolution_rate': (result[2] / total * 100) if total > 0 else 0,
                'avg_resolution_hours': result[3] or 0,
                'avg_satisfaction': result[4] or 0
            })
        
        # Category breakdown
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM support_tickets
        WHERE created_at >= ?
        GROUP BY category
        ORDER BY count DESC
        ''', (start_date,))
        
        analytics_data['categories'] = dict(cursor.fetchall())
        
        # Staff performance
        cursor.execute('''
        SELECT 
            u.username,
            COUNT(t.ticket_id) as assigned,
            COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
        FROM users u
        LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
        WHERE u.role IN ('staff', 'admin')
        GROUP BY u.id, u.username
        HAVING assigned > 0
        ORDER BY resolved DESC
        ''', (start_date,))
        
        staff_data = []
        for row in cursor.fetchall():
            staff_data.append({
                'username': row[0],
                'assigned': row[1],
                'resolved': row[2]
            })
        
        analytics_data['staff_performance'] = staff_data
        
        conn.close()
        return analytics_data
        
    except Exception as e:
        return {'error': str(e)}

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_analytics_data = get_analytics_data

def show_analytics_dashboard(self):
    """Show analytics dashboard in a new window"""
    analytics_window = tk.Toplevel(self.root)
    analytics_window.title("Analytics Dashboard")
    analytics_window.geometry("1000x700")
    analytics_window.transient(self.root)
    
    # Create scrollable frame
    canvas = tk.Canvas(analytics_window)
    scrollbar = ttk.Scrollbar(analytics_window, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    ttk.Label(scrollable_frame, text="Analytics Dashboard", style='Title.TLabel').pack(pady=10)
    
    # Time period selector
    period_frame = ttk.Frame(scrollable_frame)
    period_frame.pack(fill='x', padx=10, pady=5)
    
    ttk.Label(period_frame, text="Time Period:").pack(side='left')
    period_var = tk.StringVar(value="30d")
    period_combo = ttk.Combobox(period_frame, textvariable=period_var,
                               values=["7d", "30d", "90d", "1y"], state="readonly", width=10)
    period_combo.pack(side='left', padx=5)
    
    def refresh_analytics():
        self.load_analytics_data(scrollable_frame, period_var.get())
    
    ttk.Button(period_frame, text="Refresh", command=refresh_analytics).pack(side='left', padx=5)
    
    # Initial load
    self.load_analytics_data(scrollable_frame, "30d")
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_analytics_dashboard = show_analytics_dashboard

def load_analytics_data(self, parent, period):
    """Load analytics data for the dashboard"""
    # Clear existing analytics content (but keep header and controls)
    for widget in parent.winfo_children()[2:]:  # Skip title and period frame
        widget.destroy()
    
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Calculate date range
        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Overall statistics
        stats_frame = ttk.LabelFrame(parent, text=f"Overview ({period.upper()})")
        stats_frame.pack(fill='x', padx=10, pady=5)
        
        cursor.execute('''
        SELECT 
            COUNT(*) as total_tickets,
            COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
            COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
            AVG(CASE WHEN resolved_at IS NOT NULL 
                THEN (julianday(resolved_at) - julianday(created_at)) * 24 
                ELSE NULL END) as avg_resolution_hours,
            AVG(satisfaction_rating) as avg_satisfaction
        FROM support_tickets
        WHERE created_at >= ?
        ''', (start_date,))
        
        result = cursor.fetchone()
        if result:
            total = result[0]
            resolution_rate = (result[2] / total * 100) if total > 0 else 0
            
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.pack(fill='x', padx=10, pady=10)
            
            metrics = [
                ("Total Tickets", total),
                ("Open Tickets", result[1]),
                ("Resolved Tickets", result[2]),
                ("Resolution Rate", f"{resolution_rate:.1f}%"),
                ("Avg Resolution Time", f"{result[3] or 0:.1f}h"),
                ("Customer Satisfaction", f"{result[4] or 0:.1f}/5.0")
            ]
            
            for i, (label, value) in enumerate(metrics):
                row = i // 3
                col = (i % 3) * 2
                
                ttk.Label(stats_grid, text=f"{label}:", style='Heading.TLabel').grid(
                    row=row, column=col, sticky='w', padx=5, pady=2)
                ttk.Label(stats_grid, text=str(value)).grid(
                    row=row, column=col+1, sticky='w', padx=20, pady=2)
        
        conn.close()
        
    except Exception as e:
        ttk.Label(parent, text=f"Error loading analytics: {str(e)}", 
                 style='Error.TLabel').pack(pady=20)

# Attach method to HelpdeskGUI class
HelpdeskGUI.load_analytics_data = load_analytics_data

def show_analytics(self):
    """Switch to analytics tab"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Analytics':
            self.notebook.select(i)
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_analytics = show_analytics

def show_reports(self):
    """Switch to reports section"""
    for i in range(self.notebook.index('end')):
        if self.notebook.tab(i, 'text') == 'Administration':
            self.notebook.select(i)
            # Then select the Reports sub-tab
            break

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_reports = show_reports

def create_reports_tab(self, parent):
    """Create reports tab"""
    reports_frame = ttk.Frame(parent)
    parent.add(reports_frame, text="Reports")
    
    # Report generation options
    options_frame = ttk.LabelFrame(reports_frame, text="Report Generation")
    options_frame.pack(fill='x', padx=10, pady=10)
    
    # Report types
    report_grid = ttk.Frame(options_frame)
    report_grid.pack(fill='x', padx=10, pady=10)
    
    # Configure grid weights for better spacing
    for i in range(3):
        report_grid.grid_columnconfigure(i, weight=1)
    
    ttk.Button(report_grid, text="Executive Summary", 
              command=lambda: self.generate_report('executive')).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
    ttk.Button(report_grid, text="Staff Performance", 
              command=lambda: self.generate_report('staff')).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    ttk.Button(report_grid, text="SLA Compliance", 
              command=lambda: self.generate_report('sla')).grid(row=0, column=2, padx=5, pady=5, sticky='ew')
    
    ttk.Button(report_grid, text="Customer Satisfaction", 
              command=lambda: self.generate_report('satisfaction')).grid(row=1, column=0, padx=5, pady=5, sticky='ew')
    ttk.Button(report_grid, text="Trend Analysis", 
              command=lambda: self.generate_report('trends')).grid(row=1, column=1, padx=5, pady=5, sticky='ew')
    ttk.Button(report_grid, text="Custom Report", 
              command=lambda: self.generate_report('custom')).grid(row=1, column=2, padx=5, pady=5, sticky='ew')
    
    # Export options
    export_frame = ttk.LabelFrame(reports_frame, text="Data Export")
    export_frame.pack(fill='x', padx=10, pady=10)
    
    export_grid = ttk.Frame(export_frame)
    export_grid.pack(fill='x', padx=10, pady=10)
    
    # Configure grid weights for export section
    for i in range(3):
        export_grid.grid_columnconfigure(i, weight=1)
    
    ttk.Button(export_grid, text="Export Tickets (CSV)", 
              command=self.export_tickets_csv).grid(row=0, column=0, padx=5, pady=5, sticky='ew')
    ttk.Button(export_grid, text="Export Users (CSV)", 
              command=self.export_users_csv).grid(row=0, column=1, padx=5, pady=5, sticky='ew')
    ttk.Button(export_grid, text="Export Analytics (JSON)", 
              command=self.export_analytics_json).grid(row=0, column=2, padx=5, pady=5, sticky='ew')

# Attach method to HelpdeskGUI class
HelpdeskGUI.create_reports_tab = create_reports_tab

def generate_report(self, report_type):
    """Generate specified report type and show in window"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        reports = {
            'executive': 'Executive Summary Report',
            'staff': 'Staff Performance Report',
            'sla': 'SLA Compliance Report',
            'satisfaction': 'Customer Satisfaction Report',
            'trends': 'Trend Analysis Report',
            'custom': 'Custom Report'
        }

        report_name = reports.get(report_type, 'Unknown Report')

        # Generate report content
        report_content = self._generate_report_content(report_type)

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(report_name)
        report_window.geometry("900x700")
        report_window.transient(self.root)

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text=report_name, font=('TkDefaultFont', 16, 'bold')).pack(pady=(0, 10))

        # Report content area
        report_text = scrolledtext.ScrolledText(main_frame, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True, pady=(0, 10))
        report_text.insert('1.0', report_content)
        report_text.config(state='disabled')

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(10, 0))

        def export_to_txt():
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Report",
                initialfile=f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(report_content)
                    messagebox.showinfo("Success", f"Report exported to:\n{filename}")
                except Exception as e:
                    messagebox.showerror("Error", f"Export failed: {str(e)}")

        def send_to_admin():
            self._send_report_to_admin(report_name, report_content)

        ttk.Button(btn_frame, text="Export to TXT", command=export_to_txt).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Send to Admin via Email", command=send_to_admin).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Report generation failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_report = generate_report

def _generate_report_content(self, report_type):
    """Generate actual report content from database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now()
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append(f"HELPDESK REPORT - {report_type.upper()}")
        report_lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Generated by: {self.current_user.get('username', 'Unknown')}")
        report_lines.append("=" * 70)
        report_lines.append("")

        if report_type == 'executive':
            # Executive Summary
            cursor.execute("SELECT COUNT(*) FROM support_tickets")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
            open_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'closed'")
            closed_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'resolved'")
            resolved_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE priority = 'high'")
            high_priority = cursor.fetchone()[0]

            report_lines.append("EXECUTIVE SUMMARY")
            report_lines.append("-" * 40)
            report_lines.append(f"Total Tickets:        {total}")
            report_lines.append(f"Open Tickets:         {open_count}")
            report_lines.append(f"Resolved Tickets:     {resolved_count}")
            report_lines.append(f"Closed Tickets:       {closed_count}")
            report_lines.append(f"High Priority:        {high_priority}")
            report_lines.append("")
            report_lines.append("TICKETS BY CATEGORY")
            report_lines.append("-" * 40)

            cursor.execute("SELECT category, COUNT(*) as cnt FROM support_tickets GROUP BY category ORDER BY cnt DESC")
            for row in cursor.fetchall():
                report_lines.append(f"  {row[0] or 'Uncategorized'}: {row[1]}")

        elif report_type == 'staff':
            # Staff Performance
            report_lines.append("STAFF PERFORMANCE REPORT")
            report_lines.append("-" * 40)

            cursor.execute("""
                SELECT u.username, COUNT(t.ticket_id) as assigned,
                       SUM(CASE WHEN t.status IN ('closed', 'resolved') THEN 1 ELSE 0 END) as resolved
                FROM users u
                LEFT JOIN support_tickets t ON u.id = t.assigned_to
                WHERE u.role IN ('admin', 'staff', 'instructor')
                GROUP BY u.id
                ORDER BY assigned DESC
            """)
            staff_data = cursor.fetchall()

            if staff_data:
                report_lines.append(f"{'Staff Member':<25} {'Assigned':<12} {'Resolved':<12}")
                report_lines.append("-" * 50)
                for row in staff_data:
                    report_lines.append(f"{row[0]:<25} {row[1]:<12} {row[2] or 0:<12}")
            else:
                report_lines.append("No staff assignment data available.")

        elif report_type == 'sla':
            # SLA Compliance
            report_lines.append("SLA COMPLIANCE REPORT")
            report_lines.append("-" * 40)

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE first_response_at IS NOT NULL")
            responded = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status != 'closed'")
            pending = cursor.fetchone()[0]

            report_lines.append(f"Tickets with First Response: {responded}")
            report_lines.append(f"Pending Tickets: {pending}")

        elif report_type == 'satisfaction':
            # Customer Satisfaction
            report_lines.append("CUSTOMER SATISFACTION REPORT")
            report_lines.append("-" * 40)

            cursor.execute("SELECT AVG(satisfaction_rating) FROM support_tickets WHERE satisfaction_rating IS NOT NULL")
            avg_rating = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE satisfaction_rating IS NOT NULL")
            rated_count = cursor.fetchone()[0]

            cursor.execute("SELECT satisfaction_rating, COUNT(*) FROM support_tickets WHERE satisfaction_rating IS NOT NULL GROUP BY satisfaction_rating ORDER BY satisfaction_rating DESC")
            ratings = cursor.fetchall()

            report_lines.append(f"Average Rating: {avg_rating:.2f if avg_rating else 'N/A'}")
            report_lines.append(f"Total Rated Tickets: {rated_count}")
            report_lines.append("")
            report_lines.append("Rating Distribution:")
            for row in ratings:
                report_lines.append(f"  {row[0]} stars: {row[1]} tickets")

        elif report_type == 'trends':
            # Trend Analysis
            report_lines.append("TREND ANALYSIS REPORT")
            report_lines.append("-" * 40)

            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM support_tickets
                WHERE created_at IS NOT NULL
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            """)
            daily_data = cursor.fetchall()

            report_lines.append("Tickets Created (Last 30 Days):")
            for row in daily_data:
                report_lines.append(f"  {row[0]}: {row[1]} tickets")

        else:
            # Custom/Other
            report_lines.append("CUSTOM REPORT")
            report_lines.append("-" * 40)
            report_lines.append("Select specific metrics from the dashboard for custom reporting.")

        conn.close()
        report_lines.append("")
        report_lines.append("=" * 70)
        report_lines.append("END OF REPORT")
        report_lines.append("=" * 70)

        return "\n".join(report_lines)

    except Exception as e:
        return f"Error generating report: {str(e)}"

# Attach method to HelpdeskGUI class
HelpdeskGUI._generate_report_content = _generate_report_content

def _send_report_to_admin(self, report_name, report_content):
    """Send report to admin via email"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        # Find admin users
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL")
        admin_emails = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()

        if not admin_emails:
            messagebox.showwarning("Warning", "No admin email addresses found in the system.")
            return

        # Try to send email
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Use template for email
            template_vars = {
                'report_name': report_name,
                'report_date': datetime.now().strftime('%Y-%m-%d'),
                'report_content': report_content,
                'generated_by': self.current_user.get('username', 'Unknown'),
                'generated_datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            subject, body = render_template('helpdesk_report_admin', template_vars)

            if not subject or not body:
                # Fallback if template fails
                subject = f"Helpdesk Report: {report_name} - {datetime.now().strftime('%Y-%m-%d')}"
                body = f"""
Dear Administrator,

Please find below the requested helpdesk report.

{report_content}

This report was generated by {self.current_user.get('username', 'Unknown')} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Best regards,
University Helpdesk System
"""

            for admin_email in admin_emails:
                send_email(admin_email, subject, body)

            messagebox.showinfo("Success", f"Report sent to {len(admin_emails)} admin(s):\n" + "\n".join(admin_emails))

        except ImportError:
            messagebox.showerror("Error", "Email service not available. Please configure SMTP settings.")
        except Exception as email_err:
            messagebox.showerror("Error", f"Failed to send email: {str(email_err)}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to send report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_report_to_admin = _send_report_to_admin

def generate_enhanced_ticket_report_gui(self):
    """Show report generation dialog"""
    if not self.current_user:
        messagebox.showerror("Error", "You must be logged in to generate reports.")
        return

    if not self.has_permission('view_all_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to generate reports.")
        return

    # Create report selection dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Generate Reports")
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Enhanced Ticket Report Generator",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

    # Report type selection
    report_frame = ttk.LabelFrame(main_frame, text="Select Report Type", padding="10")
    report_frame.pack(fill='both', expand=True, pady=(0, 10))

    report_type = tk.StringVar(value='executive')

    reports = [
        ('executive', 'Executive Summary Report', 'High-level metrics and KPIs'),
        ('staff', 'Staff Performance Report', 'Individual staff metrics and workload'),
        ('sla', 'SLA Compliance Report', 'SLA adherence and breaches'),
        ('satisfaction', 'Customer Satisfaction Report', 'Satisfaction ratings and feedback'),
        ('trend', 'Trend Analysis Report', 'Historical trends and patterns'),
        ('department', 'Department Performance Report', 'Department-level metrics'),
        ('custom', 'Custom Date Range Report', 'Custom period analysis')
    ]

    for value, label, desc in reports:
        frame = ttk.Frame(report_frame)
        frame.pack(fill='x', pady=2)
        ttk.Radiobutton(frame, text=label, variable=report_type, value=value).pack(side='left')
        ttk.Label(frame, text=f"  ({desc})", foreground='gray').pack(side='left')

    # Period selection
    period_frame = ttk.LabelFrame(main_frame, text="Time Period", padding="10")
    period_frame.pack(fill='x', pady=(0, 10))

    period_var = tk.StringVar(value='30d')
    periods = [('7d', '7 Days'), ('30d', '30 Days'), ('90d', '90 Days'), ('1y', '1 Year')]

    period_buttons = ttk.Frame(period_frame)
    period_buttons.pack(fill='x')
    for value, label in periods:
        ttk.Radiobutton(period_buttons, text=label, variable=period_var,
                       value=value).pack(side='left', padx=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def generate_report():
        rtype = report_type.get()
        period = period_var.get()

        if rtype == 'executive':
            self.generate_executive_summary_gui(period)
        elif rtype == 'staff':
            self.generate_staff_performance_report_gui(period)
        elif rtype == 'department':
            self.generate_department_report_gui(period)
        elif rtype == 'satisfaction':
            self.generate_satisfaction_report_gui(period)
        elif rtype == 'trend':
            self.generate_trend_analysis_report_gui(period)
        elif rtype == 'custom':
            self.generate_custom_date_report_gui()
        else:
            messagebox.showinfo("Info", f"Report type '{rtype}' will be generated")

        dialog.destroy()

    ttk.Button(button_frame, text="Generate Report", command=generate_report).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_enhanced_ticket_report_gui = generate_enhanced_ticket_report_gui

def generate_executive_summary_gui(self, period='30d'):
    """Generate and display executive summary report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Calculate date range
        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Get key metrics
        cursor.execute('''
            SELECT
                COUNT(*) as total_tickets,
                COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved_tickets,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                AVG(CASE WHEN resolved_at IS NOT NULL
                    THEN (julianday(resolved_at) - julianday(created_at)) * 24
                    ELSE NULL END) as avg_resolution_hours,
                AVG(satisfaction_rating) as avg_satisfaction
            FROM support_tickets
            WHERE created_at >= ?
        ''', (start_date,))

        metrics = cursor.fetchone()

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Executive Summary - {period.upper()}")
        report_window.geometry("800x600")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text=f"📊 Executive Summary Report ({period.upper()})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Scrollable content
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Report content
        report_text = ""

        if metrics[0] > 0:
            resolution_rate = (metrics[1] / metrics[0] * 100)

            # Key Metrics Section
            metrics_frame = ttk.LabelFrame(scrollable_frame, text="📊 Key Metrics", padding="10")
            metrics_frame.pack(fill='x', pady=5)

            metrics_text = f"""Total Tickets: {metrics[0]}
Resolution Rate: {resolution_rate:.1f}%
Open Tickets: {metrics[2]}
High Priority: {metrics[3]}"""

            if metrics[4]:
                metrics_text += f"\nAvg Resolution Time: {metrics[4]:.1f} hours"
            if metrics[5]:
                metrics_text += f"\nCustomer Satisfaction: {metrics[5]:.1f}/5.0"

            ttk.Label(metrics_frame, text=metrics_text, justify='left',
                     font=('TkDefaultFont', 10)).pack(anchor='w')

            report_text += metrics_text + "\n\n"

            # Top Categories
            cursor.execute('''
                SELECT category, COUNT(*) as count
                FROM support_tickets
                WHERE created_at >= ?
                GROUP BY category
                ORDER BY count DESC
                LIMIT 5
            ''', (start_date,))

            categories = cursor.fetchall()

            cat_frame = ttk.LabelFrame(scrollable_frame, text="📋 Top Categories", padding="10")
            cat_frame.pack(fill='x', pady=5)

            cat_text = ""
            for cat, count in categories:
                percentage = (count / metrics[0] * 100)
                cat_text += f"{cat}: {count} ({percentage:.1f}%)\n"

            ttk.Label(cat_frame, text=cat_text, justify='left').pack(anchor='w')
            report_text += "Top Categories:\n" + cat_text + "\n"

            # Staff Workload
            cursor.execute('''
                SELECT u.username,
                       COUNT(t.ticket_id) as assigned,
                       COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved
                FROM users u
                LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
                WHERE u.role IN ('staff', 'admin')
                GROUP BY u.id, u.username
                HAVING assigned > 0
                ORDER BY assigned DESC
                LIMIT 5
            ''', (start_date,))

            staff_stats = cursor.fetchall()

            staff_frame = ttk.LabelFrame(scrollable_frame, text="👥 Staff Workload", padding="10")
            staff_frame.pack(fill='x', pady=5)

            staff_text = ""
            for username, assigned, resolved in staff_stats:
                staff_resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
                staff_text += f"{username}: {assigned} assigned, {resolved} resolved ({staff_resolution_rate:.1f}%)\n"

            ttk.Label(staff_frame, text=staff_text, justify='left').pack(anchor='w')
            report_text += "Staff Workload:\n" + staff_text

        conn.close()

        # Export button
        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill='x', pady=(10, 0))

        def export_report():
            self.save_report_to_file_gui("executive_summary", period, report_text)

        ttk.Button(export_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
        ttk.Button(export_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_executive_summary_gui = generate_executive_summary_gui

def generate_staff_performance_report_gui(self, period='30d'):
    """Generate staff performance report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Get staff performance data
        cursor.execute('''
            SELECT
                u.username,
                u.role,
                COUNT(t.ticket_id) as total_assigned,
                COUNT(CASE WHEN t.status IN ('resolved', 'closed') THEN 1 END) as resolved,
                AVG(CASE WHEN t.resolved_at IS NOT NULL
                    THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24
                    ELSE NULL END) as avg_resolution_hours,
                AVG(t.satisfaction_rating) as avg_satisfaction
            FROM users u
            LEFT JOIN support_tickets t ON u.id = t.assigned_to AND t.created_at >= ?
            WHERE u.role IN ('staff', 'admin')
            GROUP BY u.id, u.username, u.role
            HAVING total_assigned > 0
            ORDER BY total_assigned DESC
        ''', (start_date,))

        staff_data = cursor.fetchall()
        conn.close()

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Staff Performance Report - {period.upper()}")
        report_window.geometry("900x600")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"👥 Staff Performance Report ({period.upper()})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview
        columns = ('Username', 'Role', 'Assigned', 'Resolved', 'Resolution %', 'Avg Hours', 'Satisfaction')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Populate data
        report_text = "Staff Performance Report\n" + "="*50 + "\n\n"
        for username, role, assigned, resolved, avg_hours, avg_sat in staff_data:
            resolution_rate = (resolved / assigned * 100) if assigned > 0 else 0
            avg_hours_str = f"{avg_hours:.1f}" if avg_hours else "N/A"
            avg_sat_str = f"{avg_sat:.1f}" if avg_sat else "N/A"

            tree.insert('', 'end', values=(
                username, role, assigned, resolved,
                f"{resolution_rate:.1f}%", avg_hours_str, avg_sat_str
            ))

            report_text += f"{username} ({role}): {assigned} assigned, {resolved} resolved ({resolution_rate:.1f}%), "
            report_text += f"Avg: {avg_hours_str}h, Satisfaction: {avg_sat_str}\n"

        # Export button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def export_report():
            self.save_report_to_file_gui("staff_performance", period, report_text)

        ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_staff_performance_report_gui = generate_staff_performance_report_gui

def generate_department_report_gui(self, period='30d'):
    """Generate department performance report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Get department performance data
        cursor.execute('''
            SELECT
                COALESCE(department, 'Unassigned') as dept,
                COUNT(*) as total_tickets,
                COUNT(CASE WHEN status IN ('resolved', 'closed') THEN 1 END) as resolved,
                AVG(CASE WHEN resolved_at IS NOT NULL
                    THEN (julianday(resolved_at) - julianday(created_at)) * 24
                    ELSE NULL END) as avg_resolution_hours
            FROM support_tickets
            WHERE created_at >= ?
            GROUP BY department
            ORDER BY total_tickets DESC
        ''', (start_date,))

        dept_data = cursor.fetchall()
        conn.close()

        # Create report window with chart
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Department Performance - {period.upper()}")
        report_window.geometry("800x600")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"🏢 Department Performance Report ({period.upper()})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview
        columns = ('Department', 'Total Tickets', 'Resolved', 'Resolution %', 'Avg Resolution Hours')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        tree.pack(fill='both', expand=True, pady=(0, 10))

        report_text = "Department Performance Report\n" + "="*50 + "\n\n"
        for dept, total, resolved, avg_hours in dept_data:
            resolution_rate = (resolved / total * 100) if total > 0 else 0
            avg_hours_str = f"{avg_hours:.1f}" if avg_hours else "N/A"

            tree.insert('', 'end', values=(
                dept, total, resolved, f"{resolution_rate:.1f}%", avg_hours_str
            ))

            report_text += f"{dept}: {total} tickets, {resolved} resolved ({resolution_rate:.1f}%), Avg: {avg_hours_str}h\n"

        # Export button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def export_report():
            self.save_report_to_file_gui("department_performance", period, report_text)

        ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_department_report_gui = generate_department_report_gui

def generate_satisfaction_report_gui(self, period='30d'):
    """Generate customer satisfaction report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Get satisfaction data
        cursor.execute('''
            SELECT
                satisfaction_rating,
                COUNT(*) as count,
                satisfaction_feedback
            FROM support_tickets
            WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
            GROUP BY satisfaction_rating
            ORDER BY satisfaction_rating DESC
        ''', (start_date,))

        satisfaction_data = cursor.fetchall()

        # Get average
        cursor.execute('''
            SELECT AVG(satisfaction_rating) as avg_rating,
                   COUNT(*) as total_rated
            FROM support_tickets
            WHERE created_at >= ? AND satisfaction_rating IS NOT NULL
        ''', (start_date,))

        avg_data = cursor.fetchone()
        conn.close()

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Customer Satisfaction Report - {period.upper()}")
        report_window.geometry("700x500")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"⭐ Customer Satisfaction Report ({period.upper()})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Average satisfaction
        if avg_data and avg_data[0]:
            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
            summary_frame.pack(fill='x', pady=(0, 10))

            summary_text = f"Average Rating: {avg_data[0]:.2f}/5.0\nTotal Rated Tickets: {avg_data[1]}"
            ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 11, 'bold')).pack()

        # Rating distribution
        dist_frame = ttk.LabelFrame(main_frame, text="Rating Distribution", padding="10")
        dist_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Rating', 'Count', 'Percentage')
        tree = ttk.Treeview(dist_frame, columns=columns, show='headings', height=5)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        tree.pack(fill='both', expand=True)

        report_text = f"Customer Satisfaction Report\n{'='*50}\n\n"
        if avg_data and avg_data[0]:
            report_text += f"Average Rating: {avg_data[0]:.2f}/5.0\nTotal Rated: {avg_data[1]}\n\n"

        total_ratings = sum(count for _, count, _ in satisfaction_data)
        for rating, count, _ in satisfaction_data:
            percentage = (count / total_ratings * 100) if total_ratings > 0 else 0
            tree.insert('', 'end', values=(
                f"{'⭐' * rating} ({rating})", count, f"{percentage:.1f}%"
            ))
            report_text += f"{rating} stars: {count} ({percentage:.1f}%)\n"

        # Export button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def export_report():
            self.save_report_to_file_gui("satisfaction", period, report_text)

        ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_satisfaction_report_gui = generate_satisfaction_report_gui

def generate_trend_analysis_report_gui(self, period='30d'):
    """Generate trend analysis report"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        days_map = {'7d': 7, '30d': 30, '90d': 90, '1y': 365}
        days = days_map.get(period, 30)
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Get daily ticket counts
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM support_tickets
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (start_date,))

        daily_data = cursor.fetchall()

        # Get status trends
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM support_tickets
            WHERE created_at >= ?
            GROUP BY status
            ORDER BY count DESC
        ''', (start_date,))

        status_data = cursor.fetchall()
        conn.close()

        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title(f"Trend Analysis - {period.upper()}")
        report_window.geometry("800x600")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"📈 Trend Analysis Report ({period.upper()})",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Daily trends
        daily_frame = ttk.LabelFrame(main_frame, text="Daily Ticket Volume", padding="10")
        daily_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Date', 'Tickets Created')
        tree = ttk.Treeview(daily_frame, columns=columns, show='headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)

        tree.pack(fill='both', expand=True)

        report_text = f"Trend Analysis Report\n{'='*50}\n\nDaily Trends:\n"
        for date, count in daily_data:
            tree.insert('', 'end', values=(date, count))
            report_text += f"{date}: {count} tickets\n"

        # Status distribution
        status_frame = ttk.LabelFrame(main_frame, text="Status Distribution", padding="10")
        status_frame.pack(fill='x', pady=(0, 10))

        status_text = "\n\nStatus Distribution:\n"
        for status, count in status_data:
            status_text += f"{status}: {count} tickets\n"

        ttk.Label(status_frame, text=status_text, justify='left').pack(anchor='w')
        report_text += status_text

        # Export button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        def export_report():
            self.save_report_to_file_gui("trend_analysis", period, report_text)

        ttk.Button(button_frame, text="Export to File", command=export_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_trend_analysis_report_gui = generate_trend_analysis_report_gui

def generate_custom_date_report_gui(self):
    """Generate report for custom date range"""
    # Create dialog for date selection
    dialog = tk.Toplevel(self.root)
    dialog.title("Custom Date Range Report")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Select Date Range",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Date inputs
    date_frame = ttk.LabelFrame(main_frame, text="Date Range", padding="10")
    date_frame.pack(fill='x', pady=(0, 10))

    ttk.Label(date_frame, text="Start Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='w', pady=5)
    start_entry = ttk.Entry(date_frame, width=20)
    start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    start_entry.grid(row=0, column=1, pady=5)

    ttk.Label(date_frame, text="End Date (YYYY-MM-DD):").grid(row=1, column=0, sticky='w', pady=5)
    end_entry = ttk.Entry(date_frame, width=20)
    end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
    end_entry.grid(row=1, column=1, pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(10, 0))

    def generate():
        start_date = start_entry.get()
        end_date = end_entry.get()

        try:
            # Validate dates
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')

            dialog.destroy()
            messagebox.showinfo("Info", f"Generating report from {start_date} to {end_date}")
            # Here you would call the actual report generation with the custom dates

        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")

    ttk.Button(button_frame, text="Generate", command=generate).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.generate_custom_date_report_gui = generate_custom_date_report_gui

def save_report_to_file_gui(self, report_type, period, report_content):
    """Save report to file"""
    try:
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{report_type}_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        if not filename:
            return

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Helpdesk Report: {report_type}\n")
            f.write(f"Period: {period}\n")
            f.write(f"Generated by: {self.current_user.get('username', 'Unknown')}\n")
            f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n" + "="*50 + "\n\n")
            f.write(report_content)

        messagebox.showinfo("Success", f"Report saved to {filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to save report: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.save_report_to_file_gui = save_report_to_file_gui

