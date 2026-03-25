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

def show_reply_dialog(self, ticket_id):
    """Show reply dialog"""
    reply_window = tk.Toplevel(self.root)
    reply_window.title(f"Reply to Ticket #{ticket_id}")
    reply_window.geometry("600x400")
    reply_window.transient(self.root)
    reply_window.grab_set()

    # Title
    ttk.Label(reply_window, text=f"Reply to Ticket #{ticket_id}", 
             style='Heading.TLabel').pack(pady=10)

    # Message frame
    message_frame = ttk.LabelFrame(reply_window, text="Your Reply")
    message_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Message text area
    message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Time tracking (if admin)
    time_frame = ttk.Frame(reply_window)
    if self.has_permission('manage_tickets'):
        time_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(time_frame, text="Time spent (hours):").pack(side='left')
        time_entry = ttk.Entry(time_frame, width=10)
        time_entry.pack(side='left', padx=5)

    # Buttons
    button_frame = ttk.Frame(reply_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def send_reply():
        message = message_text.get('1.0', 'end-1c').strip()
        if not message:
            messagebox.showerror("Error", "Please enter a reply message")
            return

        time_spent = 0
        if self.has_permission('manage_tickets') and time_entry.get():
            try:
                time_spent = float(time_entry.get())
            except ValueError:
                pass

        if self.add_ticket_reply(ticket_id, message, time_spent):
            messagebox.showinfo("Success", "Reply added successfully!")
            reply_window.destroy()
            # Refresh the ticket view if it's open
            self.refresh_my_tickets()
        else:
            messagebox.showerror("Error", "Failed to add reply")

    ttk.Button(button_frame, text="Send Reply", command=send_reply, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=reply_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_reply_dialog = show_reply_dialog

def add_ticket_reply(self, ticket_id, message, time_spent=0, is_internal=False):
    """Add reply to ticket"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO ticket_replies 
        (ticket_id, user_id, message, is_internal, time_spent, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, self.current_user.get('id', 0), message, is_internal, time_spent, now))

        # Update ticket timestamp
        cursor.execute('''
        UPDATE support_tickets
        SET updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (now, now, ticket_id))

        conn.commit()
        conn.close()

        # Send reply notification email automatically
        if not is_internal:  # Only send for public replies
            try:
                from education_system.university_system.infrastructure.email.email_service import send_reply_notification
                username = self.current_user.get('username', 'Support Agent')
                send_reply_notification(ticket_id, self.current_user.get('id'), username, None, None, None)
            except Exception as e:
                import logging
                logging.warning(f"Failed to send reply notification: {e}")

        return True

    except Exception as e:
        messagebox.showerror("Error", f"Failed to add reply: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_ticket_reply = add_ticket_reply

def show_status_dialog(self, ticket_id):
    """Show status change dialog"""
    status_window = tk.Toplevel(self.root)
    status_window.title(f"Change Status - Ticket #{ticket_id}")
    status_window.geometry("400x300")
    status_window.transient(self.root)
    status_window.grab_set()

    # Title
    ttk.Label(status_window, text=f"Change Status for Ticket #{ticket_id}", 
             style='Heading.TLabel').pack(pady=10)

    # Status selection
    status_frame = ttk.LabelFrame(status_window, text="New Status")
    status_frame.pack(fill='x', padx=10, pady=10)

    status_var = tk.StringVar()
    statuses = ["open", "in progress", "waiting for customer", "resolved", "closed"]

    for status in statuses:
        ttk.Radiobutton(status_frame, text=status.title(), variable=status_var, 
                       value=status).pack(anchor='w', padx=5, pady=2)

    # Resolution field (for resolved/closed)
    resolution_frame = ttk.LabelFrame(status_window, text="Resolution (if resolved/closed)")
    resolution_frame.pack(fill='both', expand=True, padx=10, pady=10)

    resolution_text = scrolledtext.ScrolledText(resolution_frame, height=5, wrap='word')
    resolution_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(status_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def update_status():
        new_status = status_var.get()
        if not new_status:
            messagebox.showerror("Error", "Please select a status")
            return

        resolution = resolution_text.get('1.0', 'end-1c').strip()

        if self.update_ticket_status(ticket_id, new_status, resolution):
            messagebox.showinfo("Success", "Status updated successfully!")
            status_window.destroy()
            self.refresh_my_tickets()
        else:
            messagebox.showerror("Error", "Failed to update status")

    ttk.Button(button_frame, text="Update Status", command=update_status, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=status_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_status_dialog = show_status_dialog

def update_ticket_status(self, ticket_id, new_status, resolution=None):
    """Update ticket status"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        resolved_at = now if new_status in ['resolved', 'closed'] else None

        cursor.execute('''
        UPDATE support_tickets
        SET status = ?, resolution = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (new_status, resolution, resolved_at, now, now, ticket_id))

        conn.commit()
        conn.close()

        # Auto-send email notifications for status changes
        if new_status in ['resolved', 'closed']:
            self.auto_send_ticket_notifications(ticket_id, "resolved")

            # Send satisfaction survey when ticket is resolved/closed
            try:
                from education_system.university_system.infrastructure.email.email_service import send_satisfaction_survey
                send_satisfaction_survey(ticket_id)
            except Exception as e:
                import logging
                logging.warning(f"Failed to send satisfaction survey for ticket {ticket_id}: {e}")
        else:
            self.auto_send_ticket_notifications(ticket_id, "updated")

        return True

    except Exception as e:
        messagebox.showerror("Error", f"Failed to update status: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.update_ticket_status = update_ticket_status

def show_assign_dialog(self, ticket_id):
    """Show ticket assignment dialog"""
    assign_window = tk.Toplevel(self.root)
    assign_window.title(f"Assign Ticket #{ticket_id}")
    assign_window.geometry("400x300")
    assign_window.transient(self.root)
    assign_window.grab_set()

    # Title
    ttk.Label(assign_window, text=f"Assign Ticket #{ticket_id}", 
             style='Heading.TLabel').pack(pady=10)

    # Staff selection
    staff_frame = ttk.LabelFrame(assign_window, text="Assign To")
    staff_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Get available staff
    staff_list = self.get_available_staff()

    staff_var = tk.StringVar()

    # Add "Unassigned" option
    ttk.Radiobutton(staff_frame, text="Unassigned", variable=staff_var, 
                   value="").pack(anchor='w', padx=5, pady=2)

    for staff in staff_list:
        display_text = f"{staff['username']} ({staff['role']} - {staff.get('department', 'No Dept')})"
        ttk.Radiobutton(staff_frame, text=display_text, variable=staff_var, 
                       value=str(staff['id'])).pack(anchor='w', padx=5, pady=2)

    # Buttons
    button_frame = ttk.Frame(assign_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def assign_ticket():
        assignee_id = staff_var.get()
        assignee_id = int(assignee_id) if assignee_id else None

        if self.assign_ticket_to_user(ticket_id, assignee_id):
            messagebox.showinfo("Success", "Ticket assigned successfully!")
            assign_window.destroy()
            self.refresh_my_tickets()
        else:
            messagebox.showerror("Error", "Failed to assign ticket")

    ttk.Button(button_frame, text="Assign", command=assign_ticket, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=assign_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_assign_dialog = show_assign_dialog

def get_available_staff(self):
    """Get list of available staff members"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, username, role, department
        FROM users
        WHERE role IN ('staff', 'admin')
        ORDER BY department, username
        ''')

        staff = cursor.fetchall()
        conn.close()

        return [dict(s) for s in staff]

    except Exception as e:
        return []

# Attach method to HelpdeskGUI class
HelpdeskGUI.get_available_staff = get_available_staff

def assign_ticket_to_user(self, ticket_id, assignee_id):
    """Assign ticket to user"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE support_tickets
        SET assigned_to = ?, updated_at = ?, last_activity_at = ?
        WHERE ticket_id = ?
        ''', (assignee_id, now, now, ticket_id))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        messagebox.showerror("Error", f"Failed to assign ticket: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_ticket_to_user = assign_ticket_to_user

def show_internal_note_dialog(self, ticket_id):
    """Show internal note dialog"""
    note_window = tk.Toplevel(self.root)
    note_window.title(f"Add Internal Note - Ticket #{ticket_id}")
    note_window.geometry("600x400")
    note_window.transient(self.root)
    note_window.grab_set()

    # Title
    ttk.Label(note_window, text=f"Add Internal Note to Ticket #{ticket_id}", 
             style='Heading.TLabel').pack(pady=10)

    # Message frame
    message_frame = ttk.LabelFrame(note_window, text="Internal Note (Only visible to staff)")
    message_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Message text area
    message_text = scrolledtext.ScrolledText(message_frame, height=10, wrap='word')
    message_text.pack(fill='both', expand=True, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(note_window)
    button_frame.pack(fill='x', padx=10, pady=10)

    def add_note():
        message = message_text.get('1.0', 'end-1c').strip()
        if not message:
            messagebox.showerror("Error", "Please enter a note")
            return

        if self.add_ticket_reply(ticket_id, message, 0, is_internal=True):
            messagebox.showinfo("Success", "Internal note added successfully!")
            note_window.destroy()
        else:
            messagebox.showerror("Error", "Failed to add internal note")

    ttk.Button(button_frame, text="Add Note", command=add_note, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=note_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.show_internal_note_dialog = show_internal_note_dialog

def escalate_ticket_manual(self, ticket_id):
    """Manually escalate a ticket"""
    escalate_window = tk.Toplevel(self.root)
    escalate_window.title(_t("helpdesk.escalate_ticket_title", default="Escalate Ticket #{ticket_id}").format(ticket_id=ticket_id))
    escalate_window.geometry("400x200")
    escalate_window.transient(self.root)
    escalate_window.grab_set()

    ttk.Label(escalate_window, text=_t("helpdesk.escalate_ticket_title", default="Escalate Ticket #{ticket_id}").format(ticket_id=ticket_id), style='Heading.TLabel').pack(pady=10)

    ttk.Label(escalate_window, text="Escalation Reason:").pack(pady=5)
    reason_entry = ttk.Entry(escalate_window, width=40)
    reason_entry.pack(pady=5)
    reason_entry.insert(0, "Manual escalation")

    button_frame = ttk.Frame(escalate_window)
    button_frame.pack(pady=20)

    def perform_escalation():
        reason = reason_entry.get().strip()
        if self.escalate_ticket(ticket_id, reason):
            messagebox.showinfo("Success", f"Ticket #{ticket_id} escalated successfully")
            escalate_window.destroy()
            self.refresh_my_tickets()
        else:
            messagebox.showerror("Error", "Failed to escalate ticket")

    ttk.Button(button_frame, text="Escalate", command=perform_escalation, 
              style='Primary.TButton').pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=escalate_window.destroy).pack(side='right')

# Attach method to HelpdeskGUI class
HelpdeskGUI.escalate_ticket_manual = escalate_ticket_manual

def escalate_ticket(self, ticket_id, reason='manual'):
    """Backend function to escalate a ticket"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Get current ticket info
        cursor.execute('''
        SELECT assigned_to, department, escalation_level 
        FROM support_tickets 
        WHERE ticket_id = ?
        ''', (ticket_id,))

        ticket_info = cursor.fetchone()
        if not ticket_info:
            return False

        current_assigned, department, current_level = ticket_info
        new_level = current_level + 1

        # Find manager to escalate to
        escalate_to = None

        if department:
            cursor.execute('''
            SELECT manager_id FROM departments WHERE name = ?
            ''', (department,))
            dept_manager = cursor.fetchone()
            if dept_manager and dept_manager[0]:
                escalate_to = dept_manager[0]

        if not escalate_to:
            # Escalate to any admin
            cursor.execute('''
            SELECT id FROM users WHERE role = 'admin' LIMIT 1
            ''')
            admin = cursor.fetchone()
            if admin:
                escalate_to = admin[0]

        if escalate_to:
            # Update ticket
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE support_tickets 
            SET assigned_to = ?, escalation_level = ?, updated_at = ?
            WHERE ticket_id = ?
            ''', (escalate_to, new_level, now, ticket_id))

            # Record escalation
            cursor.execute('''
            INSERT INTO ticket_escalations 
            (ticket_id, escalation_level, escalated_to, escalation_reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (ticket_id, new_level, escalate_to, reason, now))

            conn.commit()
            conn.close()
            return True

        conn.close()
        return False

    except Exception as e:
        messagebox.showerror("Error", f"Failed to escalate ticket: {str(e)}")
        return False

# Attach method to HelpdeskGUI class
HelpdeskGUI.escalate_ticket = escalate_ticket

def assign_ticket_enhanced(self, ticket_id):
    """Enhanced ticket assignment with load balancing and skill-based routing"""
    if not self.current_user:
        messagebox.showerror("Error", "You must be logged in to assign tickets.")
        return

    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to assign tickets.")
        return

    # Create assignment dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Enhanced Ticket Assignment")
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Assign Ticket #{ticket_id}",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Assignment options
    option_frame = ttk.LabelFrame(main_frame, text="Assignment Options", padding="10")
    option_frame.pack(fill='x', pady=(0, 10))

    assign_option = tk.StringVar(value='user')
    ttk.Radiobutton(option_frame, text="Assign to specific user",
                   variable=assign_option, value='user').pack(anchor='w')
    ttk.Radiobutton(option_frame, text="Assign to department (auto-balance)",
                   variable=assign_option, value='department').pack(anchor='w')
    ttk.Radiobutton(option_frame, text="Unassign ticket",
                   variable=assign_option, value='unassign').pack(anchor='w')

    # User selection frame
    user_frame = ttk.LabelFrame(main_frame, text="Select User", padding="10")
    user_frame.pack(fill='both', expand=True, pady=(0, 10))

    # Staff list
    columns = ('ID', 'Username', 'Role', 'Department', 'Active Tickets')
    staff_tree = ttk.Treeview(user_frame, columns=columns, show='headings', height=10)

    for col in columns:
        staff_tree.heading(col, text=col)
        staff_tree.column(col, width=100)

    staff_tree.pack(fill='both', expand=True, side='left')

    scrollbar = ttk.Scrollbar(user_frame, orient='vertical', command=staff_tree.yview)
    scrollbar.pack(side='right', fill='y')
    staff_tree.configure(yscrollcommand=scrollbar.set)

    # Load staff members with workload
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.id, u.username, u.role, COALESCE(u.department, 'No Department'),
                   COUNT(st.ticket_id) as active_tickets
            FROM users u
            LEFT JOIN support_tickets st ON u.id = st.assigned_to AND st.status NOT IN ('closed', 'resolved')
            WHERE u.role IN ('staff', 'admin')
            GROUP BY u.id, u.username, u.role, u.department
            ORDER BY active_tickets ASC, u.username
        ''')

        staff_members = cursor.fetchall()
        conn.close()

        for staff in staff_members:
            staff_tree.insert('', 'end', values=staff)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load staff: {str(e)}")
        return

    # Department selection (hidden by default)
    dept_frame = ttk.LabelFrame(main_frame, text="Select Department", padding="10")

    dept_var = tk.StringVar()
    dept_combo = ttk.Combobox(dept_frame, textvariable=dept_var, state="readonly", width=40)
    dept_combo.pack(fill='x')

    # Load departments
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM departments WHERE is_active = 1 ORDER BY name')
        departments = [row[0] for row in cursor.fetchall()]
        conn.close()
        dept_combo['values'] = departments
    except Exception:
        dept_combo['values'] = ['IT Support', 'Academic Affairs', 'Financial Services']

    # Show/hide frames based on selection
    def update_frames(*args):
        if assign_option.get() == 'user':
            user_frame.pack(fill='both', expand=True, pady=(0, 10))
            dept_frame.pack_forget()
        elif assign_option.get() == 'department':
            user_frame.pack_forget()
            dept_frame.pack(fill='x', pady=(0, 10))
        else:
            user_frame.pack_forget()
            dept_frame.pack_forget()

    assign_option.trace('w', update_frames)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def perform_assignment():
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            new_assigned = None
            new_department = None

            if assign_option.get() == 'user':
                selection = staff_tree.selection()
                if not selection:
                    messagebox.showerror("Error", "Please select a user")
                    return

                values = staff_tree.item(selection[0])['values']
                new_assigned = values[0]
                new_department = values[3] if values[3] != 'No Department' else None

            elif assign_option.get() == 'department':
                new_department = dept_var.get()
                if not new_department:
                    messagebox.showerror("Error", "Please select a department")
                    return

                # Auto-assign to least loaded staff in department
                cursor.execute('''
                    SELECT u.id, COUNT(st.ticket_id) as workload
                    FROM users u
                    LEFT JOIN support_tickets st ON u.id = st.assigned_to AND st.status NOT IN ('closed', 'resolved')
                    WHERE u.role IN ('staff', 'admin') AND u.department = ?
                    GROUP BY u.id
                    ORDER BY workload ASC LIMIT 1
                ''', (new_department,))

                result = cursor.fetchone()
                if result:
                    new_assigned = result[0]

            # Update ticket
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, department = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
            ''', (new_assigned, new_department, now, now, ticket_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Ticket #{ticket_id} assigned successfully!")
            dialog.destroy()
            self.refresh_all_tickets()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign ticket: {str(e)}")

    ttk.Button(button_frame, text="Assign", command=perform_assignment).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.assign_ticket_enhanced = assign_ticket_enhanced

def change_ticket_status_enhanced(self, ticket_id):
    """Enhanced status change with resolution tracking and workflow validation"""
    if not self.current_user:
        messagebox.showerror("Error", "You must be logged in to update ticket status.")
        return

    if not self.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to update ticket status.")
        return

    # Create status change dialog
    dialog = tk.Toplevel(self.root)
    dialog.title("Change Ticket Status")
    dialog.geometry("500x450")
    dialog.transient(self.root)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill='both', expand=True)

    ttk.Label(main_frame, text=f"Change Status for Ticket #{ticket_id}",
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(0, 10))

    # Get current status
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT status, resolution FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            messagebox.showerror("Error", f"Ticket #{ticket_id} not found")
            dialog.destroy()
            return

        current_status, current_resolution = result

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load ticket: {str(e)}")
        dialog.destroy()
        return

    # Current status display
    status_frame = ttk.LabelFrame(main_frame, text="Current Status", padding="10")
    status_frame.pack(fill='x', pady=(0, 10))
    ttk.Label(status_frame, text=current_status.upper(),
             font=('TkDefaultFont', 10, 'bold')).pack()

    # New status selection
    new_status_frame = ttk.LabelFrame(main_frame, text="New Status", padding="10")
    new_status_frame.pack(fill='x', pady=(0, 10))

    status_var = tk.StringVar(value=current_status)
    statuses = ['open', 'in progress', 'waiting for customer', 'resolved', 'closed', 'cancelled']

    for status in statuses:
        ttk.Radiobutton(new_status_frame, text=status.title(),
                       variable=status_var, value=status).pack(anchor='w')

    # Resolution frame (shown for resolved/closed)
    resolution_frame = ttk.LabelFrame(main_frame, text="Resolution Details", padding="10")
    resolution_frame.pack(fill='both', expand=True, pady=(0, 10))

    ttk.Label(resolution_frame, text="Required for Resolved/Closed tickets:").pack(anchor='w')
    resolution_text = scrolledtext.ScrolledText(resolution_frame, height=8, width=50)
    resolution_text.pack(fill='both', expand=True)

    if current_resolution:
        resolution_text.insert('1.0', current_resolution)

    # Show/hide resolution based on status
    def update_resolution_visibility(*args):
        if status_var.get() in ['resolved', 'closed']:
            resolution_frame.pack(fill='both', expand=True, pady=(0, 10))
        else:
            resolution_frame.pack_forget()

    status_var.trace('w', update_resolution_visibility)
    update_resolution_visibility()

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')

    def update_status():
        new_status = status_var.get()
        resolution = resolution_text.get('1.0', 'end-1c').strip()

        if new_status == current_status:
            messagebox.showinfo("Info", "Status is already set to " + new_status.upper())
            return

        if new_status in ['resolved', 'closed'] and not resolution:
            messagebox.showerror("Error", "Resolution details are required for resolved/closed tickets")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            resolved_at = now if new_status in ['resolved', 'closed'] else None

            cursor.execute('''
                UPDATE support_tickets
                SET status = ?, resolution = ?, resolved_at = ?, updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
            ''', (new_status, resolution, resolved_at, now, now, ticket_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Ticket status updated to: {new_status.upper()}")
            dialog.destroy()
            self.refresh_all_tickets()
            self.auto_send_ticket_notifications(ticket_id, "updated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")

    ttk.Button(button_frame, text="Update Status", command=update_status).pack(side='right', padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.change_ticket_status_enhanced = change_ticket_status_enhanced

def execute_ticket_action_gui(self, ticket_id, action):
    """Execute various ticket actions through unified interface"""
    if action == 'reply':
        self.reply_to_ticket_enhanced_gui(ticket_id)
    elif action == 'assign':
        self.assign_ticket_enhanced(ticket_id)
    elif action == 'change_status':
        self.change_ticket_status_enhanced(ticket_id)
    elif action == 'escalate':
        self.escalate_ticket_manual(ticket_id)
    elif action == 'view':
        self.view_ticket_detail_enhanced_gui(ticket_id)
    elif action == 'close':
        self.change_ticket_status_enhanced(ticket_id)
    elif action == 'internal_note':
        self.reply_to_ticket_enhanced_gui(ticket_id, is_internal=True)
    elif action == 'time_entry':
        self.add_time_entry_gui(ticket_id)
    elif action == 'link':
        self.link_tickets_gui(ticket_id)
    else:
        messagebox.showinfo("Info", f"Action '{action}' not yet implemented")

# Attach method to HelpdeskGUI class
HelpdeskGUI.execute_ticket_action_gui = execute_ticket_action_gui

def reply_to_ticket_enhanced_gui(self, ticket_id, is_internal=False):
    """Enhanced reply functionality with attachments"""
    # Permission check
    is_admin = self.auth.has_permission('reply_to_any_ticket')

    if not is_admin and not self.auth.has_permission('reply_to_own_ticket'):
        messagebox.showerror("Permission Denied", "You don't have permission to reply to tickets.")
        return

    # Check ownership for non-admins
    if not is_admin:
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            result = cursor.fetchone()
            conn.close()

            if not result or result[0] != self.auth.current_user['id']:
                messagebox.showerror("Permission Denied", "You don't have permission to reply to this ticket.")
                return
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to check permissions: {e}")
            return

    # Create reply dialog
    reply_type = "Internal Note" if is_internal else "Reply"
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Add {reply_type} to Ticket #{ticket_id}")
    dialog.geometry("600x500")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Message
    ttk.Label(main_frame, text=f"{reply_type} Message:").pack(anchor=tk.W, pady=5)
    message_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=15)
    message_text.pack(fill=tk.BOTH, expand=True, pady=5)

    # Time spent (admin only)
    time_frame = ttk.Frame(main_frame)
    if self.auth.has_permission('manage_tickets'):
        time_frame.pack(fill=tk.X, pady=5)
        ttk.Label(time_frame, text="Time spent (hours):").pack(side=tk.LEFT, padx=5)
        time_var = tk.StringVar(value="0")
        ttk.Entry(time_frame, textvariable=time_var, width=10).pack(side=tk.LEFT, padx=5)

    def save_reply():
        message = message_text.get('1.0', tk.END).strip()

        if not message:
            messagebox.showerror("Validation Error", "Reply message cannot be empty.")
            return

        time_spent = 0
        if self.auth.has_permission('manage_tickets'):
            try:
                time_spent = float(time_var.get())
            except ValueError:
                time_spent = 0

        try:
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_id = self.auth.current_user['id']

            cursor.execute('''
                INSERT INTO ticket_replies
                (ticket_id, user_id, message, is_internal, time_spent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticket_id, user_id, message, is_internal, time_spent, now))

            # Update ticket timestamps
            cursor.execute('''
                UPDATE support_tickets
                SET updated_at = ?, last_activity_at = ?
                WHERE ticket_id = ?
            ''', (now, now, ticket_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"{reply_type} added successfully!")
            dialog.destroy()
            self.load_tickets()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add {reply_type.lower()}: {e}")

    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill=tk.X, pady=10)

    ttk.Button(btn_frame, text="Save", command=save_reply).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.reply_to_ticket_enhanced_gui = reply_to_ticket_enhanced_gui

def add_time_entry_gui(self, ticket_id):
    """Add time tracking entry"""
    if not self.auth.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to add time entries.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title(f"Add Time Entry - Ticket #{ticket_id}")
    dialog.geometry("400x300")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Duration
    ttk.Label(main_frame, text="Duration (hours):").grid(row=0, column=0, sticky=tk.W, pady=5)
    duration_var = tk.StringVar(value="1.0")
    ttk.Entry(main_frame, textvariable=duration_var, width=20).grid(row=0, column=1, pady=5, padx=5)

    # Description
    ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
    description_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, width=30, height=5)
    description_text.grid(row=1, column=1, pady=5, padx=5)

    # Billable
    billable_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(main_frame, text="Billable", variable=billable_var).grid(row=2, column=1, sticky=tk.W, pady=5)

    def save_time_entry():
        try:
            duration = float(duration_var.get())
            if duration <= 0:
                messagebox.showerror("Validation Error", "Duration must be greater than 0.")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid number for duration.")
            return

        description = description_text.get('1.0', tk.END).strip()
        billable = billable_var.get()

        try:
            conn = get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            start_time = (datetime.now() - timedelta(hours=duration)).strftime('%Y-%m-%d %H:%M:%S')
            duration_minutes = int(duration * 60)
            user_id = self.auth.current_user['id']

            cursor.execute('''
                INSERT INTO ticket_time_tracking
                (ticket_id, user_id, start_time, end_time, duration_minutes, description, billable, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (ticket_id, user_id, start_time, now, duration_minutes, description, billable, now))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Time entry added: {duration} hours")
            dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add time entry: {e}")

    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

    ttk.Button(btn_frame, text="Save", command=save_time_entry).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.add_time_entry_gui = add_time_entry_gui

def link_tickets_gui(self, ticket_id):
    """Link tickets together"""
    if not self.auth.has_permission('manage_tickets'):
        messagebox.showerror("Permission Denied", "You don't have permission to link tickets.")
        return

    dialog = tk.Toplevel(self.root)
    dialog.title(f"Link Ticket #{ticket_id}")
    dialog.geometry("400x250")

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Linked ticket ID
    ttk.Label(main_frame, text="Ticket ID to link:").grid(row=0, column=0, sticky=tk.W, pady=5)
    linked_id_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=linked_id_var, width=20).grid(row=0, column=1, pady=5, padx=5)

    # Link type
    ttk.Label(main_frame, text="Link type:").grid(row=1, column=0, sticky=tk.W, pady=5)
    link_type_var = tk.StringVar(value="related_to")
    link_types = [
        ("Related to", "related_to"),
        ("Duplicate of", "duplicate_of"),
        ("Blocks", "blocks"),
        ("Blocked by", "blocked_by"),
        ("Parent of", "parent_of"),
        ("Child of", "child_of")
    ]

    link_frame = ttk.Frame(main_frame)
    link_frame.grid(row=1, column=1, pady=5, padx=5, sticky=tk.W)

    for i, (label, value) in enumerate(link_types):
        ttk.Radiobutton(link_frame, text=label, variable=link_type_var, value=value).grid(row=i, column=0, sticky=tk.W)

    def save_link():
        try:
            linked_ticket_id = int(linked_id_var.get())

            if linked_ticket_id == ticket_id:
                messagebox.showerror("Validation Error", "Cannot link ticket to itself.")
                return

            # Check if target ticket exists
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT ticket_id, subject FROM support_tickets WHERE ticket_id = ?', (linked_ticket_id,))
            target_ticket = cursor.fetchone()

            if not target_ticket:
                messagebox.showerror("Not Found", "Target ticket not found.")
                conn.close()
                return

            link_type = link_type_var.get()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO ticket_links (ticket_id, linked_ticket_id, link_type, created_at)
                VALUES (?, ?, ?, ?)
            ''', (ticket_id, linked_ticket_id, link_type, now))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Ticket linked successfully as '{link_type}'")
            dialog.destroy()

        except ValueError:
            messagebox.showerror("Validation Error", "Please enter a valid ticket ID.")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to link tickets: {e}")

    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=2, column=0, columnspan=2, pady=10)

    ttk.Button(btn_frame, text="Link", command=save_link).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

# Attach method to HelpdeskGUI class
HelpdeskGUI.link_tickets_gui = link_tickets_gui

def log_ticket_action_gui(self, ticket_id, action, old_values=None, new_values=None):
    """Log ticket action to audit trail"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
        import json

        conn = get_connection()
        cursor = conn.cursor()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO ticket_audit_log
            (ticket_id, user_id, action, old_values, new_values, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            self.current_user.get('id', 0),
            action,
            json.dumps(old_values or {}),
            json.dumps(new_values or {}),
            now
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Failed to log action: {e}")

# Attach method to HelpdeskGUI class
HelpdeskGUI.log_ticket_action_gui = log_ticket_action_gui

