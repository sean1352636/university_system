import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import tkinter.font as tkFont
from datetime import datetime, timedelta
import json
import os
import threading
import webbrowser
from typing import Dict, List, Optional, Any
from university_system.infrastructure.database.db import sqlite3
from pathlib import Path
import logging
from university_system.modules.shared.constants import paths

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

# Import email service for notifications
try:
    from university_system.infrastructure.email.email_service import send_email
    from university_system.infrastructure.email.templates import load_template, render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    send_email = lambda *args, **kwargs: False
    load_template = lambda *args, **kwargs: None
    render_template = lambda *args, **kwargs: (None, None)

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this module when targeting the
# student_records.db database. Many functions within this GUI refer to
# str(DEFAULT_DB_PATH) without specifying a full path. Without this
# override, a new database would be created in the current working
# directory, leading to multiple database files and missing tables. The
# override redirects connections to the shared student_records.db in
# university_system/data/db_files. If a different database name/path is
# supplied, the connection falls back to the original behaviour.

_original_sqlite3_connect = sqlite3.connect  # preserve original

def _patched_sqlite_connect(database, *args, **kwargs):
    """Redirect connections targeting student_records.db to the central path."""
    try:
        # Determine basename; accept Path or str
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name == str(DEFAULT_DB_PATH):
            return _original_sqlite3_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite3_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect

# Import all functionality from student_support module (it's a single monolithic file)
try:
    # Import everything from the single student_support module
    from university_system.modules.domain.student_affairs.services.student_support import (
        # Core constants and enums
        SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
        NotificationType, TicketSentiment, FileType,
        # Main classes
        EnhancedStudentSupport, SupportConfig,
        # Utility functions
        setup_enhanced_logging, audit_action, set_auth,
        # Display functions
        display_support_menu, display_enhanced_faqs, display_enhanced_resources,
        # Ticket management functions
        view_my_tickets_enhanced, view_all_tickets_enhanced,
        create_enhanced_ticket, display_ticket_details_enhanced,
        # Admin functions
        manage_templates_menu, manage_knowledge_base_menu, show_template_statistics,
        # Helper functions
        format_ticket_status_display, format_priority_display, format_file_size,
        truncate_text, handle_support_error, validate_ticket_permissions
    )

    # Auth handling - auth is now managed differently in the new structure
    auth = None  # Will be set via set_auth_instance()

except ImportError:
    # Backwards compatibility - if module structure changes or imports fail
    try:
        from university_system.modules.domain.student_affairs.services.student_support import (
            SUPPORT_CATEGORIES, TICKET_PRIORITIES, TICKET_STATUSES,
            EnhancedStudentSupport, SupportConfig, display_support_menu, set_auth
        )
        auth = None
    except ImportError:
        # If even the fallback import fails, define minimal stubs
        auth = None
        SUPPORT_CATEGORIES = []
        TICKET_PRIORITIES = []
        TICKET_STATUSES = []
        EnhancedStudentSupport = None
        SupportConfig = None
        display_support_menu = None

    # Define fallback functions if not available
    display_enhanced_faqs = None
    display_enhanced_resources = None
    view_my_tickets_enhanced = None
    view_all_tickets_enhanced = None
    create_enhanced_ticket = None
    display_ticket_details_enhanced = None
    manage_templates_menu = None
    manage_knowledge_base_menu = None
    show_template_statistics = None

    # Define fallback enum types
    from enum import Enum
    class NotificationType(str, Enum):
        INFO = 'info'
        WARNING = 'warning'
        ERROR = 'error'

    class TicketSentiment(str, Enum):
        POSITIVE = 'positive'
        NEUTRAL = 'neutral'
        NEGATIVE = 'negative'

    class FileType(str, Enum):
        IMAGE = 'image'
        DOCUMENT = 'document'
        OTHER = 'other'

    # Define fallback helper functions
    setup_enhanced_logging = lambda: None
    audit_action = lambda *args, **kwargs: None
    set_auth = lambda x: None  # Fallback if set_auth not available
    validate_ticket_permissions = lambda *args, **kwargs: True
    format_ticket_status_display = lambda x: str(x)
    format_priority_display = lambda x: str(x)
    format_file_size = lambda x: f"{x} bytes"
    truncate_text = lambda x, length=100: x[:length] if len(x) > length else x
    handle_support_error = lambda *args, **kwargs: None

class DashboardMixin:
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def open_helpdesk_gui(self):
        """Open the IT Helpdesk GUI in a new window"""
        try:
            from university_system.modules.domain.student_affairs.gui.helpdesk import HelpdeskGUI

            # Create a new Toplevel window for Helpdesk
            helpdesk_window = tk.Toplevel(self.root)
            helpdesk_window.title("IT Helpdesk System")
            helpdesk_window.geometry("1200x800")
            helpdesk_window.transient(self.root)

            # Initialize the Helpdesk GUI in the new window
            HelpdeskGUI(helpdesk_window, self.auth)

            self.update_status("Opened IT Helpdesk")
        except ImportError as e:
            messagebox.showerror("Error", f"Could not load Helpdesk GUI: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open Helpdesk: {e}")
            import traceback
            traceback.print_exc()

    def load_dashboard(self):
        """Load dashboard data"""
        if not self.support:
            return

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return

        try:
            # Get user ID (try 'id' first, fallback to 'user_id', then default to None)
            user_id = self.auth.current_user.get('id') or self.auth.current_user.get('user_id')
            user_role = self.auth.current_user.get('role', 'student')

            self.dashboard_data = self.support.get_dashboard_data(
                user_role,
                user_id
            )
            self.update_status("Dashboard loaded")
        except Exception as e:
            self.update_status(f"Error loading dashboard: {e}")
            self.dashboard_data = {}
            print(f"Dashboard error: {e}")
            import traceback
            traceback.print_exc()

    def show_dashboard(self):
        """Display dashboard"""
        self.clear_content()

        dashboard_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(dashboard_frame, text=_t("student_support.dashboard.tab_title"))

        # Configure frame to expand
        dashboard_frame.rowconfigure(0, weight=1)
        dashboard_frame.columnconfigure(0, weight=1)

        # Configure frame to expand
        dashboard_frame.rowconfigure(0, weight=1)
        dashboard_frame.columnconfigure(0, weight=1)

        # Create scrollable area
        canvas = tk.Canvas(dashboard_frame, bg=self.colors['background'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dashboard_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        scroll_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def on_canvas_configure(event):
            # Make the scrollable frame fill the canvas width
            canvas.itemconfigure(scroll_window, width=event.width)
            # If content is smaller than canvas, expand scrollable_frame to fill canvas height
            canvas_height = event.height
            content_height = scrollable_frame.winfo_reqheight()
            if content_height < canvas_height:
                canvas.itemconfigure(scroll_window, height=canvas_height)

        canvas.bind("<Configure>", on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Dashboard content - authentication already checked in __init__
        # Robust check: ensure auth and current_user are valid
        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            return
        if not isinstance(self.auth.current_user, dict) or not self.auth.current_user.get('username'):
            return
        
        # Load fresh data
        self.load_dashboard()
        
        # Title
        title_frame = ttk.Frame(scrollable_frame, padding="10")
        title_frame.pack(fill="x")

        ttk.Label(title_frame, text=_t("student_support.dashboard.title"),
                 style='Title.TLabel').pack(side="left")

        # Welcome message
        welcome_text = _t("student_support.dashboard.welcome", username=self.auth.current_user['username'])
        ttk.Label(title_frame, text=welcome_text,
                 font=('Segoe UI', 12)).pack(side="right")
        
        # Create dashboard widgets based on role
        if self.auth.current_user['role'] == 'student':
            self.create_student_dashboard(scrollable_frame)
        else:
            self.create_staff_dashboard(scrollable_frame)
        
        # Common widgets
        self.create_notifications_widget(scrollable_frame)
        self.create_quick_actions_widget(scrollable_frame)

    def create_student_dashboard(self, parent):
        """Create student-specific dashboard widgets"""
        # Ticket statistics
        stats_frame = ttk.LabelFrame(parent, text="📊 Your Tickets", padding="10")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        stats = self.dashboard_data.get('ticket_stats', {})
        
        stats_text = f"Open: {stats.get('Open', 0)} | "
        stats_text += f"In Progress: {stats.get('In Progress', 0)} | "
        stats_text += f"Resolved: {stats.get('Resolved', 0)}"
        
        ttk.Label(stats_frame, text=stats_text, font=('Segoe UI', 11)).pack()
        
        # Recent tickets
        recent_frame = ttk.LabelFrame(parent, text="📋 Recent Tickets", padding="10")
        recent_frame.pack(fill="x", padx=10, pady=5)
        
        recent_tickets = self.dashboard_data.get('recent_tickets', []) or []
        if recent_tickets:
            for ticket in recent_tickets[:3]:
                if ticket is None or not isinstance(ticket, dict):
                    continue
                ticket_frame = ttk.Frame(recent_frame)
                ticket_frame.pack(fill="x", pady=2)

                ticket_status = ticket.get('status', 'Unknown')
                ticket_id = ticket.get('ticket_id', 'N/A')
                ticket_title = ticket.get('title', 'Untitled')[:50]

                status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket_status, '❓')
                ticket_text = f"{status_emoji} #{ticket_id} - {ticket_title}..."

                ttk.Label(ticket_frame, text=ticket_text).pack(side="left")
                ttk.Button(ticket_frame, text="View",
                          command=lambda t=ticket_id: self.view_ticket_details(t)).pack(side="right")
        else:
            ttk.Label(recent_frame, text="No recent tickets").pack()
        
        # Featured resources
        resources_frame = ttk.LabelFrame(parent, text="⭐ Featured Resources", padding="10")
        resources_frame.pack(fill="x", padx=10, pady=5)
        
        featured_resources = self.dashboard_data.get('featured_resources', []) or []
        if featured_resources:
            for resource in featured_resources[:3]:
                if resource is None or not isinstance(resource, dict):
                    continue
                resource_frame = ttk.Frame(resources_frame)
                resource_frame.pack(fill="x", pady=2)

                resource_title = resource.get('title', 'Untitled Resource')
                ttk.Label(resource_frame, text=f"📄 {resource_title}").pack(side="left")
                ttk.Button(resource_frame, text="View",
                          command=lambda r=resource: self.open_resource(r)).pack(side="right")
        else:
            ttk.Label(resources_frame, text="No featured resources available").pack()

    def create_staff_dashboard(self, parent):
        """Create staff-specific dashboard widgets"""
        # Performance metrics
        metrics_frame = ttk.LabelFrame(parent, text="📈 Performance Metrics", padding="10")
        metrics_frame.pack(fill="x", padx=10, pady=5)
        
        metrics = self.dashboard_data.get('performance_metrics', {})
        
        metrics_text = f"Monthly Tickets: {metrics.get('total_tickets_month', 0)} | "
        metrics_text += f"Avg Resolution: {metrics.get('avg_resolution_time', 0)} days | "
        metrics_text += f"Resolution Rate: {metrics.get('resolution_rate', 0)}%"
        
        ttk.Label(metrics_frame, text=metrics_text, font=('Segoe UI', 11)).pack()
        
        # Assigned tickets
        assigned_frame = ttk.LabelFrame(parent, text="👨‍💼 Assigned Tickets", padding="10")
        assigned_frame.pack(fill="x", padx=10, pady=5)
        
        assigned_stats = self.dashboard_data.get('assigned_stats', {})
        assigned_text = f"Open: {assigned_stats.get('Open', 0)} | "
        assigned_text += f"In Progress: {assigned_stats.get('In Progress', 0)}"
        
        ttk.Label(assigned_frame, text=assigned_text, font=('Segoe UI', 11)).pack()
        
        # High priority tickets
        priority_frame = ttk.LabelFrame(parent, text="🚨 Priority Tickets", padding="10")
        priority_frame.pack(fill="x", padx=10, pady=5)

        priority_tickets = self.dashboard_data.get('priority_tickets', []) or []
        if priority_tickets:
            for ticket in priority_tickets[:5]:
                # Skip None or invalid ticket entries
                if ticket is None or not isinstance(ticket, dict):
                    continue

                ticket_frame = ttk.Frame(priority_frame)
                ticket_frame.pack(fill="x", pady=2)

                ticket_priority = ticket.get('priority', 'Normal')
                ticket_id = ticket.get('ticket_id', 'N/A')
                ticket_title = ticket.get('title', 'Untitled')[:40]

                priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡'}.get(ticket_priority, '⚪')
                ticket_text = f"{priority_emoji} #{ticket_id} - {ticket_title}..."

                ttk.Label(ticket_frame, text=ticket_text).pack(side="left")
                ttk.Button(ticket_frame, text="Assign to Me",
                          command=lambda t=ticket_id: self.assign_ticket_to_me(t)).pack(side="right")
        else:
            ttk.Label(priority_frame, text="No high priority tickets").pack()

    def create_notifications_widget(self, parent):
        """Create notifications widget"""
        notifications_frame = ttk.LabelFrame(parent, text="🔔 Recent Notifications", padding="10")
        notifications_frame.pack(fill="x", padx=10, pady=5)

        notifications = self.dashboard_data.get('notifications', []) or []
        if notifications:
            for notif in notifications[:3]:
                # Skip None or invalid notification entries
                if notif is None or not isinstance(notif, dict):
                    continue

                notif_frame = ttk.Frame(notifications_frame)
                notif_frame.pack(fill="x", pady=2)

                is_read = notif.get('is_read', False)
                notif_title = notif.get('title', 'Notification')
                notif_created = notif.get('created', '')

                status_icon = "📫" if is_read else "📬"
                notif_text = f"{status_icon} {notif_title}"

                ttk.Label(notif_frame, text=notif_text).pack(side="left")
                ttk.Label(notif_frame, text=notif_created,
                         font=('Segoe UI', 9), foreground=self.colors['text_secondary']).pack(side="right")
        else:
            ttk.Label(notifications_frame, text="No recent notifications").pack()

    def create_quick_actions_widget(self, parent):
        """Create quick actions widget"""
        actions_frame = ttk.LabelFrame(parent, text="⚡ Quick Actions", padding="10")
        actions_frame.pack(fill="x", padx=10, pady=5)
        
        # Create grid of action buttons
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill="x")
        
        if self.auth.current_user['role'] == 'student':
            actions = [
                ("🎫 Create Ticket", self.show_create_ticket),
                ("📋 My Tickets", self.show_my_tickets),
                ("🔍 Search", self.show_search),
                ("❓ Browse FAQs", self.show_faqs)
            ]
        else:
            actions = [
                ("🎫 View All Tickets", self.show_all_tickets),
                ("📊 Generate Report", self.show_reports),
                ("🔧 Manage Templates", self.show_manage_templates),
                ("📦 Bulk Operations", self.show_bulk_operations)
            ]
        
        for i, (text, command) in enumerate(actions):
            row, col = i // 2, i % 2
            ttk.Button(actions_grid, text=text, command=command).grid(
                row=row, column=col, padx=5, pady=5, sticky="ew")
        
        actions_grid.columnconfigure(0, weight=1)
        actions_grid.columnconfigure(1, weight=1)

    def show_notifications(self):
        """Show notifications interface"""
        self.clear_content()
        
        notifications_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(notifications_frame, text="🔔 Notifications")

        # Configure frame to expand
        notifications_frame.rowconfigure(0, weight=1)
        notifications_frame.columnconfigure(0, weight=1)
        
        # Header
        header_frame = ttk.Frame(notifications_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        ttk.Label(header_frame, text="🔔 Notifications", 
                 style='Title.TLabel').pack(side="left")
        
        # Mark all as read button
        ttk.Button(header_frame, text="📫 Mark All Read", 
                  command=self.mark_all_notifications_read).pack(side="right")
        
        # Filter options
        filter_frame = ttk.Frame(notifications_frame)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        
        self.notification_filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.notification_filter_var,
                                   values=["All", "Unread", "Read"], state="readonly")
        filter_combo.pack(side="left", padx=(10, 0))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.load_notifications())
        
        # Notifications display
        self.notifications_display_frame = ttk.Frame(notifications_frame)
        self.notifications_display_frame.pack(fill="both", expand=True)
        
        # Load notifications
        self.load_notifications()

    def load_notifications(self):
        """Load and display notifications"""
        # Clear display
        for widget in self.notifications_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Get notifications (using dashboard data for now)
            notifications = self.dashboard_data.get('notifications', [])
            
            # Apply filter
            filter_value = self.notification_filter_var.get()
            if filter_value == "Unread":
                notifications = [n for n in notifications if not n.get('is_read', False)]
            elif filter_value == "Read":
                notifications = [n for n in notifications if n.get('is_read', False)]
            
            if not notifications:
                ttk.Label(self.notifications_display_frame, text="📭 No notifications").pack(pady=20)
                return
            
            # Create scrollable notifications list
            canvas, scrollbar, scrollable_frame = self._create_scrollable_frame(self.notifications_display_frame)
            
            # Add notifications
            for notification in notifications:
                self.create_notification_item(scrollable_frame, notification)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            ttk.Label(self.notifications_display_frame, text=f"❌ Error loading notifications: {e}").pack(pady=20)

    def create_notification_item(self, parent, notification):
        """Create a notification item"""
        # Frame with background color based on read status
        bg_color = "#f8fafc" if notification.get('is_read') else "#dbeafe"
        
        notif_frame = tk.Frame(parent, bg=bg_color, relief="solid", bd=1)
        notif_frame.pack(fill="x", padx=5, pady=2)
        
        content_frame = ttk.Frame(notif_frame)
        content_frame.pack(fill="x", padx=10, pady=8)
        
        # Status icon and title
        header_frame = ttk.Frame(content_frame)
        header_frame.pack(fill="x")
        
        status_icon = "📫" if notification.get('is_read') else "📬"
        title_text = f"{status_icon} {notification['title']}"
        
        ttk.Label(header_frame, text=title_text, font=('Segoe UI', 10, 'bold')).pack(side="left")
        
        # Timestamp
        ttk.Label(header_frame, text=notification['created'], font=('Segoe UI', 9),
                 foreground=self.colors['text_secondary']).pack(side="right")
        
        # Message
        if notification.get('message'):
            ttk.Label(content_frame, text=notification['message'], wraplength=700).pack(anchor="w", pady=(5, 0))
        
        # Actions
        action_frame = ttk.Frame(content_frame)
        action_frame.pack(anchor="w", pady=(5, 0))

        if not notification.get('is_read'):
            ttk.Button(action_frame, text="✓ Mark as Read",
                      command=lambda: self.mark_notification_read(notification)).pack(side="left", padx=(0, 5))

        # Add "View Email" button for email notifications
        notification_type = notification.get('type') or notification.get('notification_type', '')
        if notification_type and 'email' in str(notification_type).lower():
            ttk.Button(action_frame, text="📧 View Email",
                      command=lambda: self.view_notification_email(notification)).pack(side="left", padx=(0, 5))

    def mark_notification_read(self, notification):
        """Mark a notification as read"""
        notification_id = notification.get('notification_id') or notification.get('id')
        user_id, _ = self._get_current_user_identity()

        if not notification_id:
            messagebox.showerror("Error", "Notification identifier missing.")
            return

        if not user_id:
            messagebox.showerror("Error", "You must be signed in to update notifications.")
            return

        try:
            success = False
            if self.support and hasattr(self.support, 'mark_notification_read'):
                success = self.support.mark_notification_read(notification_id, user_id=user_id)
            else:
                def update_notification(conn):
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        UPDATE notifications
                        SET is_read = 1, read_datetime = ?
                        WHERE notification_id = ? AND user_id = ?
                        ''',
                        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notification_id, user_id)
                    )
                    return cursor.rowcount
                success = self._safe_db_call(update_notification) > 0

            if not success:
                messagebox.showwarning("Notification", "Notification was already marked as read or no longer exists.")
                return

            notification['is_read'] = True
            self.load_dashboard()
            self.load_notifications()
            self.update_status("Notification marked as read")
        except Exception as e:
            messagebox.showerror("Error", f"Could not mark notification as read: {e}")

    def view_notification_email(self, notification):
        """View the email notification that was sent"""
        # Create a new window to display the email content
        email_window = tk.Toplevel(self.root)
        email_window.title(f"📧 Email Notification - {notification.get('title', 'Notification')}")
        email_window.geometry("900x700")
        email_window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(email_window, padding="15")
        main_frame.pack(fill="both", expand=True)

        # Email header
        header_frame = ttk.LabelFrame(main_frame, text="Email Details", padding="10")
        header_frame.pack(fill="x", pady=(0, 10))

        # Get user email
        user_id, _ = self._get_current_user_identity()
        user_email = self._get_user_email(user_id)

        ttk.Label(header_frame, text=f"To: {user_email or 'Your Email'}",
                 font=('Segoe UI', 10)).pack(anchor="w", pady=2)
        ttk.Label(header_frame, text=f"Subject: {notification.get('title', 'N/A')}",
                 font=('Segoe UI', 10)).pack(anchor="w", pady=2)
        ttk.Label(header_frame, text=f"Date: {notification.get('created', 'N/A')}",
                 font=('Segoe UI', 10)).pack(anchor="w", pady=2)

        # Email body
        body_frame = ttk.LabelFrame(main_frame, text="Email Content", padding="10")
        body_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Create scrolled text widget for email body
        email_text = scrolledtext.ScrolledText(body_frame, wrap=tk.WORD, font=('Segoe UI', 10))
        email_text.pack(fill="both", expand=True)

        # Format email content
        email_content = self._format_notification_as_email(notification)
        email_text.insert(1.0, email_content)
        email_text.config(state='disabled')  # Make read-only

        # Action buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="📋 Copy to Clipboard",
                  command=lambda: self._copy_to_clipboard(email_content)).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="💾 Save as TXT",
                  command=lambda: self._save_email_as_txt(notification, email_content)).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="❌ Close",
                  command=email_window.destroy).pack(side="left")

    def _get_user_email(self, user_id):
        """Get user email from database"""
        try:
            from university_system.infrastructure.database.db import get_connection

            conn = get_connection()
            cursor = conn.cursor()

            # Try students table first
            cursor.execute("SELECT email_address FROM students WHERE student_id = ?", (user_id,))
            result = cursor.fetchone()

            if result and result[0]:
                conn.close()
                return result[0]

            # Fallback to users table
            cursor.execute("SELECT email FROM users WHERE username = ? OR id = ?", (user_id, user_id))
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                return result[0]

            return None

        except Exception as e:
            logging.error(f"Error getting user email: {e}")
            return None

    def _format_notification_as_email(self, notification):
        """Format notification as email body"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  EMAIL NOTIFICATION: {notification.get('title', 'Notification')}")
        lines.append("=" * 70)
        lines.append("")

        # Email message
        lines.append(notification.get('message', 'No message content available.'))
        lines.append("")

        # Additional details if available
        related_ticket_id = notification.get('related_ticket_id')
        if related_ticket_id:
            lines.append("-" * 70)
            lines.append(f"Related Ticket: #{related_ticket_id}")
            lines.append("")

        # Footer
        lines.append("=" * 70)
        lines.append("This is an automated notification from the Student Support System.")
        lines.append("Please do not reply to this notification.")
        lines.append("")
        lines.append("If you have questions, please log into the support portal")
        lines.append("or contact the support team directly.")
        lines.append("=" * 70)

        return '\n'.join(lines)

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            messagebox.showinfo("Copied", "Email content copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")

    def _save_email_as_txt(self, notification, email_content):
        """Save email notification as TXT file"""
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            title="Save Email as TXT",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"email_notification_{notification.get('notification_id', 'unknown')}.txt"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(email_content)

            messagebox.showinfo("Success", f"Email saved to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save email: {e}")

    def mark_all_notifications_read(self):
        """Mark all notifications as read"""
        user_id, _ = self._get_current_user_identity()
        if not user_id:
            messagebox.showerror("Error", "You must be signed in to update notifications.")
            return

        try:
            def bulk_update(conn):
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    '''
                    UPDATE notifications
                    SET is_read = 1,
                        read_datetime = COALESCE(read_datetime, ?)
                    WHERE user_id = ? AND is_read = 0
                    ''',
                    (timestamp, user_id)
                )
                return cursor.rowcount

            updated = 0
            if self.support and hasattr(self.support, 'get_user_notifications'):
                notifications = self.support.get_user_notifications(user_id=user_id, unread_only=True)
                for notif in notifications:
                    if self.support.mark_notification_read(notif['notification_id'], user_id=user_id):
                        updated += 1
            else:
                updated = self._safe_db_call(bulk_update)

            self.load_dashboard()
            self.load_notifications()
            self.update_status("All notifications marked as read")
            messagebox.showinfo("Success", f"Marked {updated} notification(s) as read.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not mark notifications as read: {e}")

    def show_preferences(self):
        """Show user preferences interface"""
        self.clear_content()
        
        prefs_frame = ttk.Frame(self.notebook, padding="3")
        self.notebook.add(prefs_frame, text="⚙️ Preferences")

        # Configure frame to expand
        prefs_frame.rowconfigure(0, weight=1)
        prefs_frame.columnconfigure(0, weight=1)
        
        ttk.Label(prefs_frame, text="⚙️ User Preferences", 
                 style='Title.TLabel').pack(pady=(0, 20))
        
        # Get current preferences
        try:
            if self.support:
                current_prefs = self.support.get_user_preferences()
            else:
                current_prefs = {}
        except Exception:
            current_prefs = {}
        
        # Preferences form
        form_frame = ttk.LabelFrame(prefs_frame, text="Notification Settings", padding="15")
        form_frame.pack(fill="x", pady=(0, 10))
        
        # Notification preferences
        self.email_notifications_var = tk.BooleanVar(value=current_prefs.get('email_notifications', True))
        ttk.Checkbutton(form_frame, text="📧 Email Notifications", 
                       variable=self.email_notifications_var).pack(anchor="w", pady=2)
        
        self.in_app_notifications_var = tk.BooleanVar(value=current_prefs.get('in_app_notifications', True))
        ttk.Checkbutton(form_frame, text="🔔 In-App Notifications", 
                       variable=self.in_app_notifications_var).pack(anchor="w", pady=2)
        
        self.push_notifications_var = tk.BooleanVar(value=current_prefs.get('push_notifications', True))
        ttk.Checkbutton(form_frame, text="📱 Push Notifications", 
                       variable=self.push_notifications_var).pack(anchor="w", pady=2)
        
        # Digest frequency
        digest_frame = ttk.Frame(form_frame)
        digest_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Label(digest_frame, text="📅 Digest Frequency:").pack(side="left")
        self.digest_frequency_var = tk.StringVar(value=current_prefs.get('digest_frequency', 'daily'))
        digest_combo = ttk.Combobox(digest_frame, textvariable=self.digest_frequency_var,
                                   values=['immediate', 'daily', 'weekly'], state="readonly")
        digest_combo.pack(side="left", padx=(10, 0))
        
        # Display preferences
        display_frame = ttk.LabelFrame(prefs_frame, text="Display Settings", padding="15")
        display_frame.pack(fill="x", pady=(0, 10))
        
        # Theme
        theme_frame = ttk.Frame(display_frame)
        theme_frame.pack(fill="x", pady=2)
        
        ttk.Label(theme_frame, text="🎨 Theme:").pack(side="left")
        self.theme_var = tk.StringVar(value=current_prefs.get('theme', 'light'))
        theme_combo = ttk.Combobox(theme_frame, textvariable=self.theme_var,
                                  values=['light', 'dark'], state="readonly")
        theme_combo.pack(side="left", padx=(10, 0))
        
        # Language
        language_frame = ttk.Frame(display_frame)
        language_frame.pack(fill="x", pady=2)
        
        ttk.Label(language_frame, text="🌐 Language:").pack(side="left")
        self.language_var = tk.StringVar(value=current_prefs.get('language', 'en'))
        language_combo = ttk.Combobox(language_frame, textvariable=self.language_var,
                                     values=['en', 'es', 'fr', 'de'], state="readonly")
        language_combo.pack(side="left", padx=(10, 0))
        
        # Timezone
        timezone_frame = ttk.Frame(display_frame)
        timezone_frame.pack(fill="x", pady=2)
        
        ttk.Label(timezone_frame, text="🕐 Timezone:").pack(side="left")
        self.timezone_var = tk.StringVar(value=current_prefs.get('timezone', 'UTC'))
        timezone_entry = ttk.Entry(timezone_frame, textvariable=self.timezone_var, width=20)
        timezone_entry.pack(side="left", padx=(10, 0))
        
        # Save button
        ttk.Button(prefs_frame, text="💾 Save Preferences", 
                  command=self.save_preferences, style='Primary.TButton').pack(pady=20)

    def save_preferences(self):
        """Save user preferences"""
        try:
            preferences = {
                'email_notifications': self.email_notifications_var.get(),
                'in_app_notifications': self.in_app_notifications_var.get(),
                'push_notifications': self.push_notifications_var.get(),
                'digest_frequency': self.digest_frequency_var.get(),
                'theme': self.theme_var.get(),
                'language': self.language_var.get(),
                'timezone': self.timezone_var.get()
            }
            
            if self.support:
                self.support.update_user_preferences(preferences)
                messagebox.showinfo("Success", "Preferences saved successfully!")
                self.update_status("Preferences saved")
            else:
                messagebox.showerror("Error", "Support system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preferences: {e}")

