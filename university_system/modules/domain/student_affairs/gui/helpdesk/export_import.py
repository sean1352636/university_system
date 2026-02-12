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
from university_system.core.sql_safety import validate_identifier

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

# Import secure file upload handler
try:
    from university_system.infrastructure.security.file_upload import (
        validate_upload,
        secure_filename,
    )
    SECURE_UPLOAD_AVAILABLE = True
except ImportError:
    SECURE_UPLOAD_AVAILABLE = False
    validate_upload = None
    def secure_filename(x):
        return x

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

def export_tickets_csv(self):
    """Export tickets to CSV"""
    try:
        import csv
        from university_system.infrastructure.database.db import get_connection

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Tickets Export",
            initialfilename=f"tickets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if filename:
            conn = get_connection()
            cursor = conn.cursor()

            # Get column names
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [row[1] for row in cursor.fetchall()]

            # Get all tickets
            cursor.execute("SELECT * FROM support_tickets ORDER BY ticket_id DESC")
            tickets = cursor.fetchall()
            conn.close()

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)  # Header
                writer.writerows(tickets)

            messagebox.showinfo("Success", f"Exported {len(tickets)} tickets to:\n{filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Export failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.export_tickets_csv = export_tickets_csv

def export_users_csv(self):
    """Export users to CSV"""
    try:
        import csv
        from university_system.infrastructure.database.db import get_connection

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Users Export",
            initialfilename=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if filename:
            conn = get_connection()
            cursor = conn.cursor()

            # Get column names (excluding password hash for security)
            cursor.execute("PRAGMA table_info(users)")
            all_columns = [row[1] for row in cursor.fetchall()]
            # Exclude sensitive columns
            columns = [c for c in all_columns if c not in ('password', 'password_hash', 'salt', 'totp_secret')]

            # Get all users (excluding sensitive data)
            safe_columns = [validate_identifier(c, "column") for c in columns]
            cursor.execute("SELECT " + ', '.join(safe_columns) + " FROM users ORDER BY id")
            users = cursor.fetchall()
            conn.close()

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)  # Header
                writer.writerows(users)

            messagebox.showinfo("Success", f"Exported {len(users)} users to:\n{filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Export failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.export_users_csv = export_users_csv

def export_analytics_json(self):
    """Export analytics to JSON"""
    try:
        from university_system.infrastructure.database.db import get_connection

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Analytics Export",
            initialfilename=f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if filename:
            conn = get_connection()
            cursor = conn.cursor()

            analytics = {
                'generated_at': datetime.now().isoformat(),
                'generated_by': self.current_user.get('username', 'Unknown'),
                'summary': {},
                'by_status': {},
                'by_priority': {},
                'by_category': {},
                'recent_activity': []
            }

            # Total counts
            cursor.execute("SELECT COUNT(*) FROM support_tickets")
            analytics['summary']['total_tickets'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users")
            analytics['summary']['total_users'] = cursor.fetchone()[0]

            # By status
            cursor.execute("SELECT status, COUNT(*) FROM support_tickets GROUP BY status")
            for row in cursor.fetchall():
                analytics['by_status'][row[0] or 'unknown'] = row[1]

            # By priority
            cursor.execute("SELECT priority, COUNT(*) FROM support_tickets GROUP BY priority")
            for row in cursor.fetchall():
                analytics['by_priority'][row[0] or 'unknown'] = row[1]

            # By category
            cursor.execute("SELECT category, COUNT(*) FROM support_tickets GROUP BY category")
            for row in cursor.fetchall():
                analytics['by_category'][row[0] or 'unknown'] = row[1]

            # Recent activity (last 50 tickets)
            cursor.execute("""
                SELECT ticket_id, subject, status, priority, created_at
                FROM support_tickets
                ORDER BY created_at DESC
                LIMIT 50
            """)
            for row in cursor.fetchall():
                analytics['recent_activity'].append({
                    'ticket_id': row[0],
                    'subject': row[1],
                    'status': row[2],
                    'priority': row[3],
                    'created_at': row[4]
                })

            conn.close()

            # Write to JSON
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(analytics, f, indent=2, default=str)

            messagebox.showinfo("Success", f"Analytics exported to:\n{filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Export failed: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.export_analytics_json = export_analytics_json

def export_ticket_list_gui(self):
    """Export filtered ticket list to CSV"""
    try:
        import csv
        from tkinter import filedialog

        # Get tickets to export (from current view)
        if hasattr(self, 'all_tickets_tree'):
            items = self.all_tickets_tree.get_children()
            if not items:
                messagebox.showinfo("Info", "No tickets to export")
                return

            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"tickets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['ID', 'Subject', 'Status', 'Priority', 'Category', 'Created', 'Assigned To'])

                for item in items:
                    values = self.all_tickets_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Success", f"Exported {len(items)} tickets to {filename}")

        else:
            messagebox.showerror("Error", "No ticket list available to export")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.export_ticket_list_gui = export_ticket_list_gui

def export_analytics_data_gui(self):
    """Export analytics data to CSV"""
    try:
        import csv
        from tkinter import filedialog
        from university_system.infrastructure.database.db import get_connection

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ticket_id, user_id, subject, category, status, priority,
                   created_at, resolved_at, satisfaction_rating
            FROM support_tickets
            ORDER BY created_at DESC
        ''')

        tickets = cursor.fetchall()
        conn.close()

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Ticket ID', 'User ID', 'Subject', 'Category', 'Status',
                           'Priority', 'Created At', 'Resolved At', 'Satisfaction'])

            for ticket in tickets:
                writer.writerow(ticket)

        messagebox.showinfo("Success", f"Exported {len(tickets)} tickets to {filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export analytics data: {str(e)}")

# END OF ANALYTICS & REPORTING FUNCTIONS
# ============================================================================

# ============================================================================
# IMPORT/EXPORT & SYSTEM MANAGEMENT FUNCTIONS (7 FUNCTIONS)
# ============================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.export_analytics_data_gui = export_analytics_data_gui

def import_tickets_csv_gui(self):
    """Import tickets from CSV file"""
    try:
        import csv
        from tkinter import filedialog
        from university_system.infrastructure.database.db import get_connection

        filename = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not filename:
            return

        imported = 0
        errors = []

        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            conn = get_connection()
            cursor = conn.cursor()

            for row in reader:
                try:
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                        INSERT INTO support_tickets
                        (user_id, subject, message, category, status, priority, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        self.current_user.get('id', 0),
                        row.get('subject', ''),
                        row.get('message', ''),
                        row.get('category', 'Other'),
                        row.get('status', 'open'),
                        row.get('priority', 'medium'),
                        now, now
                    ))

                    imported += 1

                except Exception as e:
                    errors.append(f"Row {reader.line_num}: {str(e)}")

            conn.commit()
            conn.close()

        if errors:
            error_msg = "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors)-5} more errors"
            messagebox.showwarning("Import Complete with Errors",
                                  f"Imported {imported} tickets\nErrors: {len(errors)}\n\n{error_msg}")
        else:
            messagebox.showinfo("Success", f"Successfully imported {imported} tickets")

        self.refresh_all_tickets()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to import tickets: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.import_tickets_csv_gui = import_tickets_csv_gui

def data_import_export_gui(self):
    """Show import/export options dialog"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Data Import/Export")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="Data Import/Export",
             font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 20))

    # Export options
    export_frame = ttk.LabelFrame(main_frame, text="Export", padding="10")
    export_frame.pack(fill='x', pady=(0, 10))

    ttk.Button(export_frame, text="Export Tickets to CSV",
              command=lambda: [dialog.destroy(), self.export_ticket_list_gui()]).pack(fill='x', pady=2)
    ttk.Button(export_frame, text="Export Analytics Data",
              command=lambda: [dialog.destroy(), self.export_analytics_data_gui()]).pack(fill='x', pady=2)

    # Import options
    import_frame = ttk.LabelFrame(main_frame, text="Import", padding="10")
    import_frame.pack(fill='x', pady=(0, 10))

    ttk.Button(import_frame, text="Import Tickets from CSV",
              command=lambda: [dialog.destroy(), self.import_tickets_csv_gui()]).pack(fill='x', pady=2)

    # Close button
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))

# Attach method to HelpdeskGUI class
HelpdeskGUI.data_import_export_gui = data_import_export_gui

def handle_file_attachments_gui(self, ticket_id, reply_id=None):
    """Handle file attachment uploads and management"""
    dialog = tk.Toplevel(self.root)
    dialog.title(f"File Attachments - Ticket #{ticket_id}")
    dialog.geometry("700x500")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text="File Attachments",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Toolbar
    toolbar = ttk.Frame(main_frame)
    toolbar.pack(fill='x', pady=(0, 10))

    ttk.Button(toolbar, text="📎 Add File",
              command=lambda: self._select_and_upload_file(ticket_id, reply_id, tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="📥 Download",
              command=lambda: self._download_selected_attachment(tree)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🗑️ Delete",
              command=lambda: self._delete_selected_attachment(tree, ticket_id)).pack(side='left', padx=5)
    ttk.Button(toolbar, text="🔃 Refresh",
              command=lambda: self._load_attachments_list(tree, ticket_id)).pack(side='left', padx=5)

    # Attachments list
    columns = ('ID', 'Filename', 'Size', 'Type', 'Uploaded By', 'Uploaded At')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

    for col in columns:
        tree.heading(col, text=col)
        width = 60 if col == 'ID' else 120
        tree.column(col, width=width)

    tree.pack(fill='both', expand=True, side='left')

    scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
    scrollbar.pack(side='right', fill='y')
    tree.configure(yscrollcommand=scrollbar.set)

    # Load existing attachments
    self._load_attachments_list(tree, ticket_id)

    # Close button
    ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

# Attach method to HelpdeskGUI class
HelpdeskGUI.handle_file_attachments_gui = handle_file_attachments_gui

def _load_attachments_list(self, tree, ticket_id):
    """Load attachments for a ticket"""
    try:
        from university_system.infrastructure.database.db import get_connection

        for item in tree.get_children():
            tree.delete(item)

        conn = get_connection()
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                reply_id INTEGER,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                uploaded_by TEXT,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                FOREIGN KEY (ticket_id) REFERENCES support_tickets(ticket_id)
            )
        ''')
        conn.commit()

        cursor.execute('''
            SELECT attachment_id, original_filename, file_size, mime_type,
                   uploaded_by, uploaded_at
            FROM ticket_attachments
            WHERE ticket_id = ?
            ORDER BY uploaded_at DESC
        ''', (ticket_id,))

        attachments = cursor.fetchall()
        conn.close()

        for att in attachments:
            att_id, filename, size, mime_type, uploaded_by, uploaded_at = att
            size_str = self._format_file_size(size) if size else 'N/A'

            tree.insert('', 'end', values=(
                att_id, filename, size_str, mime_type or 'N/A',
                uploaded_by or 'N/A', uploaded_at or 'N/A'
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load attachments: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._load_attachments_list = _load_attachments_list

def _format_file_size(self, size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

# Attach method to HelpdeskGUI class
HelpdeskGUI._format_file_size = _format_file_size

def _select_and_upload_file(self, ticket_id, reply_id, tree):
    """Select and upload a file attachment"""
    import os
    import shutil
    import uuid
    from tkinter import filedialog

    file_path = filedialog.askopenfilename(
        title="Select File to Attach",
        filetypes=[
            ("All files", "*.*"),
            ("Documents", "*.pdf *.doc *.docx *.txt"),
            ("Images", "*.png *.jpg *.jpeg *.gif"),
            ("Spreadsheets", "*.xls *.xlsx *.csv")
        ]
    )

    if not file_path:
        return

    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10 MB
    file_size = os.path.getsize(file_path)
    if file_size > max_size:
        messagebox.showerror("Error", "File size exceeds maximum limit of 10MB")
        return

    try:
        from university_system.infrastructure.database.db import get_connection
        from university_system.modules.shared.constants import paths
        import mimetypes

        original_filename = os.path.basename(file_path)

        # Security: Validate file using secure upload handler
        if SECURE_UPLOAD_AVAILABLE and validate_upload:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            validation = validate_upload(original_filename, file_content, category='documents')
            if not validation['valid']:
                messagebox.showerror(
                    "Security Error",
                    f"File validation failed: {validation['error']}"
                )
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity(
                        'security_blocked',
                        'file_upload',
                        ticket_id=ticket_id,
                        filename=original_filename,
                        reason=validation['error']
                    )
                return

            # Use sanitized filename from validation
            safe_filename = validation.get('sanitized_filename', secure_filename(original_filename))
        else:
            # Fallback: basic filename sanitization
            safe_filename = secure_filename(original_filename)

        # Create attachments directory
        attachments_dir = paths.DATA_DIR / 'attachments' / 'tickets' / str(ticket_id)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions on directory
        os.chmod(attachments_dir, 0o700)

        # Generate unique filename
        unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
        dest_path = attachments_dir / unique_filename

        # Copy file
        shutil.copy2(file_path, dest_path)
        # Set restrictive permissions on file
        os.chmod(dest_path, 0o600)

        # Get mime type
        mime_type, _ = mimetypes.guess_type(file_path)

        # Save to database
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        uploaded_by = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'

        cursor.execute('''
            INSERT INTO ticket_attachments
            (ticket_id, reply_id, filename, original_filename, file_size, mime_type, uploaded_by, uploaded_at, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            reply_id,
            unique_filename,
            original_filename,
            file_size,
            mime_type,
            uploaded_by,
            now,
            str(dest_path)
        ))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"File '{original_filename}' uploaded successfully!")
        self._load_attachments_list(tree, ticket_id)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to upload file: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._select_and_upload_file = _select_and_upload_file

def _download_selected_attachment(self, tree):
    """Download selected attachment"""
    import os
    import shutil
    from tkinter import filedialog

    selection = tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select an attachment to download")
        return

    attachment_id = tree.item(selection[0])['values'][0]
    original_filename = tree.item(selection[0])['values'][1]

    try:
        from university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM ticket_attachments WHERE attachment_id = ?',
                      (attachment_id,))
        result = cursor.fetchone()
        conn.close()

        if not result or not result[0]:
            messagebox.showerror("Error", "File not found in database")
            return

        source_path = result[0]

        if not os.path.exists(source_path):
            messagebox.showerror("Error", "File no longer exists on disk")
            return

        # Ask user where to save
        save_path = filedialog.asksaveasfilename(
            title="Save Attachment As",
            initialfile=original_filename,
            defaultextension=os.path.splitext(original_filename)[1]
        )

        if save_path:
            shutil.copy2(source_path, save_path)
            messagebox.showinfo("Success", f"File saved to:\n{save_path}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to download file: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._download_selected_attachment = _download_selected_attachment

def _delete_selected_attachment(self, tree, ticket_id):
    """Delete selected attachment"""
    import os

    selection = tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select an attachment to delete")
        return

    attachment_id = tree.item(selection[0])['values'][0]
    filename = tree.item(selection[0])['values'][1]

    if not messagebox.askyesno("Confirm Delete",
                               f"Are you sure you want to delete '{filename}'?"):
        return

    try:
        from university_system.infrastructure.database.db import get_connection

        conn = get_connection()
        cursor = conn.cursor()

        # Get file path before deleting
        cursor.execute('SELECT file_path FROM ticket_attachments WHERE attachment_id = ?',
                      (attachment_id,))
        result = cursor.fetchone()

        # Delete from database
        cursor.execute('DELETE FROM ticket_attachments WHERE attachment_id = ?',
                      (attachment_id,))
        conn.commit()
        conn.close()

        # Delete file from disk if it exists
        if result and result[0] and os.path.exists(result[0]):
            os.remove(result[0])

        messagebox.showinfo("Success", "Attachment deleted successfully!")
        self._load_attachments_list(tree, ticket_id)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete attachment: {str(e)}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._delete_selected_attachment = _delete_selected_attachment

def add_attachment_gui(self, ticket_id, reply_id, file_path):
    """Add attachment to ticket or reply programmatically"""
    import os
    import shutil
    import uuid

    if not file_path or not os.path.exists(file_path):
        messagebox.showerror("Error", "Invalid file path")
        return False

    try:
        from university_system.infrastructure.database.db import get_connection
        from university_system.modules.shared.constants import paths
        import mimetypes

        # Create attachments directory
        attachments_dir = paths.DATA_DIR / 'attachments' / 'tickets' / str(ticket_id)
        attachments_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        original_filename = os.path.basename(file_path)
        unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
        dest_path = attachments_dir / unique_filename

        # Copy file
        shutil.copy2(file_path, dest_path)

        # Get file info
        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        # Save to database
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        uploaded_by = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'

        cursor.execute('''
            INSERT INTO ticket_attachments
            (ticket_id, reply_id, filename, original_filename, file_size, mime_type, uploaded_by, uploaded_at, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            reply_id,
            unique_filename,
            original_filename,
            file_size,
            mime_type,
            uploaded_by,
            now,
            str(dest_path)
        ))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        messagebox.showerror("Error", f"Failed to add attachment: {str(e)}")
        return False

# ========================================================================
# TIME TRACKING & TICKET LINKING
# ========================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_attachment_gui = add_attachment_gui

def send_ticket_notification_email(self, ticket_id, notification_type, admin_list, user_id=None):
    """Send ticket notification emails"""
    try:
        # Get ticket details
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT subject, status, category, priority, user_id, created_at, resolution
            FROM support_tickets WHERE ticket_id = ?
        ''', (ticket_id,))

        ticket_result = cursor.fetchone()
        if not ticket_result:
            conn.close()
            return False

        subject, status, category, priority, ticket_user_id, created_at, resolution = ticket_result
        conn.close()

        # Use user_id from ticket if not provided
        if not user_id:
            user_id = ticket_user_id

        # Generate email content based on notification type
        if notification_type == "created":
            self._send_ticket_created_emails(ticket_id, subject, category, priority, admin_list, user_id)
        elif notification_type == "resolved":
            self._send_ticket_resolved_emails(ticket_id, subject, resolution, admin_list, user_id)
        elif notification_type == "updated":
            self._send_ticket_updated_emails(ticket_id, subject, status, admin_list, user_id)

        return True

    except Exception as e:
        print(f"Failed to send ticket notification: {e}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.send_ticket_notification_email = send_ticket_notification_email

def _send_ticket_created_emails(self, ticket_id, subject, category, priority, admin_list, user_id):
    """Send emails when ticket is created"""
    # Send ticket notification using centralized email service
    try:
        from university_system.infrastructure.email.email_service import send_ticket_notification

        # Use the actual user_id from the ticket (can be username or student_id)
        if not user_id:
            print(f"Warning: Ticket {ticket_id} has no user_id")
            return

        # Send ticket notification (handles both admin and user emails)
        # admin_list is already a list of tuples from database: [('admin',), ('admin2',)]
        send_ticket_notification(ticket_id, subject, user_id, admin_list if admin_list else None)
    except Exception as e:
        print(f"Failed to send ticket notification: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_ticket_created_emails = _send_ticket_created_emails

def _send_ticket_resolved_emails(self, ticket_id, subject, resolution, admin_list, user_id):
    """Send emails when ticket is resolved"""
    try:
        from university_system.infrastructure.email.email_service import send_template_email
        from university_system.infrastructure.database.db import get_connection

        # Look up user's email from user_id using dual-table pattern
        if user_id:
            conn = get_connection()
            cursor = conn.cursor()

            user_email = None
            # Try students table first
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                user_email = result[0]
            else:
                # Fall back to users table
                cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (user_id, user_id))
                result = cursor.fetchone()
                if result and result[0]:
                    user_email = result[0]

            conn.close()

            if user_email:
                template_vars = {
                    "ticket_id": ticket_id,
                    "subject": subject,
                    "resolution": resolution or 'Issue has been resolved.',
                    "resolution_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                send_template_email('helpdesk_ticket_resolved', user_email, template_vars)
    except Exception as e:
        print(f"Failed to send ticket resolved notification: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_ticket_resolved_emails = _send_ticket_resolved_emails

def _send_ticket_updated_emails(self, ticket_id, subject, status, admin_list, user_id):
    """Send emails when ticket is updated"""
    try:
        from university_system.infrastructure.email.email_service import send_template_email
        from university_system.infrastructure.database.db import get_connection

        # Look up user's email from user_id using dual-table pattern
        if user_id:
            conn = get_connection()
            cursor = conn.cursor()

            user_email = None
            # Try students table first
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                user_email = result[0]
            else:
                # Fall back to users table
                cursor.execute('SELECT email FROM users WHERE username = ? OR id = ?', (user_id, user_id))
                result = cursor.fetchone()
                if result and result[0]:
                    user_email = result[0]

            conn.close()

            if user_email:
                template_vars = {
                    "ticket_id": ticket_id,
                    "subject": subject,
                    "status": status,
                    "updated_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                send_template_email('helpdesk_ticket_updated', user_email, template_vars)
    except Exception as e:
        print(f"Failed to send ticket update notification: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_ticket_updated_emails = _send_ticket_updated_emails

def _send_ticket_updated_emails_fallback(self, ticket_id, subject, status, user_email):
    """Fallback email sending when template fails"""
    try:
        user_subject = f"Support Ticket Updated - #{ticket_id}"
        user_message = f"""Your support ticket has been updated:

================================================
TICKET UPDATE
================================================

Ticket ID: #{ticket_id}
Subject: {subject}
New Status: {status}
Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please log into the helpdesk system to view the latest updates.

================================================

Best regards,
University Support Team
"""
        self._send_email_via_gui(user_email, user_subject, user_message)
    except Exception as e:
        print(f"Failed to send fallback email: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_ticket_updated_emails_fallback = _send_ticket_updated_emails_fallback

def _send_email_via_gui(self, to_email, subject, message):
    """Send email via email GUI"""
    try:
        from university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
        email_gui = EmailManagerGUI(self.root, auth=self.auth if hasattr(self, 'auth') else None)

        # If email GUI has send_email method, use it
        if hasattr(email_gui, 'send_email'):
            email_gui.send_email(to_email=to_email, subject=subject, message=message)
            return True
        return False
    except ImportError:
        return False
    except Exception as e:
        print(f"Error sending email via GUI: {e}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI._send_email_via_gui = _send_email_via_gui

def auto_send_ticket_notifications(self, ticket_id, notification_type):
    """Automatically send ticket notifications"""
    try:
        from university_system.infrastructure.database.db import get_connection

        # Get list of admin users from database
        admin_list = []
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username FROM users
                WHERE role = 'admin' AND (email IS NOT NULL AND email != '')
            ''')
            admin_list = cursor.fetchall()  # Returns list of tuples: [('admin',), ('admin2',)]
            conn.close()
        except Exception as e:
            print(f"Error fetching admin list: {e}")

        # Get user_id from ticket
        user_id = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            result = cursor.fetchone()
            if result:
                user_id = result[0]
            conn.close()
        except Exception as e:
            print(f"Error fetching ticket user_id: {e}")

        self.send_ticket_notification_email(ticket_id, notification_type, admin_list, user_id)
    except Exception as e:
        print(f"Failed to auto-send ticket notifications: {e}")

# ========================================================================
# SEARCH & FILTERING FUNCTIONS
# ========================================================================

# Attach method to HelpdeskGUI class
HelpdeskGUI.auto_send_ticket_notifications = auto_send_ticket_notifications

def run_gui_helpdesk(auth_system=None):
    """Run the GUI helpdesk system"""
    root = tk.Tk()
    app = HelpdeskGUI(root, auth=auth_system)
    
    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit the helpdesk system?"):
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    root.mainloop()

def display_helpdesk_menu_gui(auth):
    """GUI version of the original display_helpdesk_menu function"""
    run_gui_helpdesk(auth)

