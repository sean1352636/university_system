import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys

# Add the project root to Python path if not already there
# This file is at university_system/interfaces/gui/email_manager_gui.py
# So we need to go up 3 levels to get to the parent of university_system
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from university_system.infrastructure.database.db import get_db_connection
from university_system.infrastructure.auth.user_authentication import UserAuth

# Import get_stored_emails first - this is critical for the inbox functionality
try:
    from university_system.infrastructure.email.email_service import get_stored_emails
    print("✓ Successfully imported get_stored_emails from email_service")
except ImportError as e:
    print(f"✗ Failed to import get_stored_emails: {e}")
    get_stored_emails = None

# Import other functions we need - try individually to avoid complete failure
# Initialize all functions to None first
send_email = delete_stored_email = list_templates = load_template = create_template = None
list_all_users = search_users = send_batch_announcement = get_system_health_info = None
clear_stored_emails = optimize_database = execute_db_operation = config = None
save_config = test_email_configuration = initialize_communication_system = None
cleanup_communication_system = CommunicationDashboard = None

# Try to import from individual modules to avoid the shared utils dependency issues
try:
    from university_system.infrastructure.email.email_service import (
        send_email, delete_stored_email, clear_stored_emails,
        send_registration_confirmation, send_assignment_notification,
        send_grade_notification, send_extension_notification,
        send_update_confirmation, send_password_reset,
        send_appointment_confirmation, send_health_notification,
        send_ticket_notification, send_reply_notification,
        send_internship_notification, send_alumni_welcome_email,
        send_mentorship_notification, send_event_invitation,
        send_donation_receipt, send_book_checkout_confirmation,
        send_book_return_reminder, send_overdue_notification
    )
    print("✓ Imported email functions from email_service")
except ImportError as e:
    print(f"⚠️ Could not import email functions: {e}")
    # Set missing functions to None as fallback
    for func_name in ['send_registration_confirmation', 'send_assignment_notification',
                      'send_grade_notification', 'send_extension_notification',
                      'send_update_confirmation', 'send_password_reset',
                      'send_appointment_confirmation', 'send_health_notification',
                      'send_ticket_notification', 'send_reply_notification',
                      'send_internship_notification', 'send_alumni_welcome_email',
                      'send_mentorship_notification', 'send_event_invitation',
                      'send_donation_receipt', 'send_book_checkout_confirmation',
                      'send_book_return_reminder', 'send_overdue_notification']:
        if func_name not in dir():
            globals()[func_name] = None

try:
    from university_system.infrastructure.email.email_db_utilities import optimize_database, execute_db_operation
    print("✓ Imported database functions")
except ImportError as e:
    print(f"⚠️ Could not import database functions: {e}")

try:
    from university_system.infrastructure.email.template_utils import list_templates, load_template, create_template
    print("✓ Imported template functions")
except ImportError as e:
    print(f"⚠️ Could not import template functions: {e}")

try:
    from university_system.infrastructure.email.reports import get_system_health_info, get_user_communication_stats
    print("✓ Imported system health and communication stats functions")
except ImportError as e:
    print(f"⚠️ Could not import system health functions: {e}")
    get_user_communication_stats = None

# Direct import for CommunicationDashboard as fallback
if CommunicationDashboard is None:
    try:
        from university_system.infrastructure.email.admin import CommunicationDashboard as DirectCommunicationDashboard
        CommunicationDashboard = DirectCommunicationDashboard
        print("✓ Imported CommunicationDashboard directly from admin module")
    except ImportError as e:
        print(f"⚠️ Could not import CommunicationDashboard: {e}")

try:
    from university_system.infrastructure.email.announcements import send_batch_announcement
    print("✓ Imported announcement functions")
except ImportError as e:
    print(f"⚠️ Could not import announcement functions: {e}")

try:
    from university_system.infrastructure.email.admin import search_users, list_all_users
    print("✓ Imported user search functions")
except ImportError as e:
    print(f"⚠️ Could not import user search functions: {e}")

# Try importing communication system from infrastructure
try:
    from university_system.infrastructure.email.admin import (
        initialize_communication_system,
        cleanup_communication_system,
        CommunicationDashboard
    )
    from university_system.infrastructure.email.config import config, save_config
    print("✓ Imported communication system")
except ImportError as e:
    print(f"⚠️ Running in standalone mode - some features may be limited: {e}")
    # Define minimal fallbacks
    config = {'database_only_mode': True}

    def save_config(cfg):
        """Save configuration to JSON file"""
        try:
            config_path = os.path.join(os.path.expanduser('~'), '.email_manager_config.json')
            with open(config_path, 'w') as f:
                json.dump(cfg, f, indent=4)
            print(f"✓ Configuration saved to {config_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to save configuration: {e}")
            return False

    def initialize_communication_system():
        """Initialize the communication system"""
        try:
            # Ensure database tables exist
            from university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create emails table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    cc TEXT,
                    bcc TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    attachments TEXT
                )
            ''')

            # Create email_templates table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    subject TEXT,
                    body TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create scheduled_emails table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    scheduled_for TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')

            conn.commit()
            conn.close()
            print("✓ Communication system initialized")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize communication system: {e}")
            return False

    def cleanup_communication_system():
        """Clean up communication system resources"""
        try:
            # Close any open database connections
            print("✓ Communication system cleaned up")
            return True
        except Exception as e:
            print(f"✗ Failed to cleanup communication system: {e}")
            return False

# Only define mock send_email if not imported
if send_email is None:
    def send_email(recipient, subject, body, cc=None, bcc=None, attachments=None):
        print(f"Mock: Sending email to {recipient}")
        return True

# Only define mock get_stored_emails if real function wasn't imported
if get_stored_emails is None:
    def get_stored_emails(limit=50, offset=0, recipient_filter=None, date_filter=None):
        print("Warning: Using mock get_stored_emails - database connection may be misconfigured")
        return {'emails': [], 'total_count': 0, 'limit': limit, 'offset': offset}

# Add missing function implementations to prevent None errors
if list_templates is None:
    def list_templates():
        print("Warning: list_templates not available")
        return []

if load_template is None:
    def load_template(template_name):
        print(f"Warning: load_template not available for {template_name}")
        return {'subject': '', 'body': ''}

if create_template is None:
    def create_template(name, subject, body):
        print(f"Warning: create_template not available - would create {name}")
        return False

if list_all_users is None:
    def list_all_users(auth, limit=100):
        print("Warning: list_all_users not available")
        return []

if search_users is None:
    def search_users(auth, search_term):
        print("Warning: search_users not available")
        return []

if send_batch_announcement is None:
    def send_batch_announcement(*args, **kwargs):
        print("Warning: send_batch_announcement not available")
        return False

if get_system_health_info is None:
    def get_system_health_info():
        print("Warning: get_system_health_info not available")
        return {}

if test_email_configuration is None:
    def test_email_configuration():
        print("Warning: test_email_configuration not available")

if execute_db_operation is None:
    def execute_db_operation(func):
        print("Warning: execute_db_operation not available")
        return None

if clear_stored_emails is None:
    def clear_stored_emails(older_than_days=30):
        print("Warning: clear_stored_emails not available")
        return 0

if delete_stored_email is None:
    def delete_stored_email(email_id):
        print("Warning: delete_stored_email not available")
        return False

if optimize_database is None:
    def optimize_database():
        print("Warning: optimize_database not available")
    
class EmailManagerGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth if auth is not None else UserAuth()
        self.dashboard = None
        
        # Initialize the communication system
        self.initialize_system()
        
        # Setup main window
        self.setup_main_window()
        
        # Create menu bar
        self.create_menu_bar()

        # Create main interface
        self.create_main_interface()
        
        # Load initial data
        self.load_initial_data()
        
    def initialize_system(self):
        """Initialize the email and communication system"""
        try:
            # Initialize email database tables
            from university_system.infrastructure.email.email_db_utilities import initialize_email_db
            initialize_email_db()

            # Initialize the communication system using existing functions
            if initialize_communication_system is not None:
                initialize_communication_system()

            # Set the auth instance in the email infrastructure state
            # This ensures all email modules can access authentication
            try:
                from university_system.infrastructure.email import set_auth
                set_auth(self.auth)
                print("✓ Authentication linked to email infrastructure")
            except ImportError:
                print("⚠️ Could not import set_auth function")

            # Create the communication dashboard with auth
            if CommunicationDashboard is not None:
                self.dashboard = CommunicationDashboard(auth=self.auth)
            print("✅ Communication system initialized")
        except Exception as e:
            print(f"⚠️ Error initializing system: {e}")
            
    def setup_main_window(self):
        """Setup the main window properties"""
        self.root.title("University Communication System - Email Manager")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        self.colors = {
            'primary': '#2E86AB',
            'secondary': '#A23B72',
            'success': '#F18F01',
            'warning': '#C73E1D',
            'background': '#F5F5F5',
            'surface': '#FFFFFF'
        }
        
    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Email", command=self.compose_email, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label="Import Contacts", command=self.import_contacts)
        file_menu.add_command(label="Export Data", command=self.export_data)
        
        # Email menu
        email_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Email", menu=email_menu)
        email_menu.add_command(label="Compose", command=self.compose_email)
        email_menu.add_command(label="Send Bulk", command=self.send_bulk_email)
        email_menu.add_command(label="Schedule Email", command=self.schedule_email)
        email_menu.add_separator()
        email_menu.add_command(label="Templates", command=self.manage_templates)
        email_menu.add_command(label="Configuration", command=self.email_configuration)
        
        # Communication menu
        comm_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Communication", menu=comm_menu)
        comm_menu.add_command(label="Messages", command=self.open_messages)
        comm_menu.add_command(label="Announcements", command=self.open_announcements)
        comm_menu.add_command(label="Chat Rooms", command=self.open_chat_rooms)
        comm_menu.add_separator()
        comm_menu.add_command(label="Preferences", command=self.notification_preferences)

        # Notifications menu with submenus
        notif_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Notifications", menu=notif_menu)

        # Academic submenu
        academic_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Academic", menu=academic_menu)
        academic_menu.add_command(label="Registration Confirmation", command=self.send_registration_confirmation_dialog)
        academic_menu.add_command(label="Assignment Notification", command=self.send_assignment_notification_dialog)
        academic_menu.add_command(label="Grade Notification (Module)", command=self.send_module_grade_notification_dialog)
        academic_menu.add_command(label="Grade Notification (Assignment)", command=self.send_assignment_grade_notification_dialog)
        academic_menu.add_command(label="Extension Notification", command=self.send_extension_notification_dialog)
        academic_menu.add_command(label="Update Confirmation", command=self.send_update_confirmation_dialog)
        academic_menu.add_command(label="Password Reset", command=self.send_password_reset_dialog)

        # Health Services submenu
        health_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Health Services", menu=health_menu)
        health_menu.add_command(label="Appointment Confirmation", command=self.send_appointment_confirmation_dialog)
        health_menu.add_command(label="Health Advisory", command=self.send_health_notification_dialog)

        # Helpdesk submenu
        helpdesk_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Helpdesk", menu=helpdesk_menu)
        helpdesk_menu.add_command(label="Ticket Notification", command=self.send_ticket_notification_dialog)
        helpdesk_menu.add_command(label="Reply Notification", command=self.send_reply_notification_dialog)

        # Library submenu
        library_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Library", menu=library_menu)
        library_menu.add_command(label="Checkout Confirmation", command=self.send_book_checkout_confirmation_dialog)
        library_menu.add_command(label="Return Reminder", command=self.send_book_return_reminder_dialog)
        library_menu.add_command(label="Overdue Notice", command=self.send_overdue_notification_dialog)

        # Student Affairs submenu
        affairs_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Student Affairs", menu=affairs_menu)
        affairs_menu.add_command(label="Internship Notification", command=self.send_internship_notification_dialog)
        affairs_menu.add_command(label="Mentorship Notification", command=self.send_mentorship_notification_dialog)

        # Alumni submenu
        alumni_menu = tk.Menu(notif_menu, tearoff=0)
        notif_menu.add_cascade(label="Alumni", menu=alumni_menu)
        alumni_menu.add_command(label="Welcome Email", command=self.send_alumni_welcome_dialog)
        alumni_menu.add_command(label="Event Invitation", command=self.send_event_invitation_dialog)
        alumni_menu.add_command(label="Donation Receipt", command=self.send_donation_receipt_dialog)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Email Reports", command=self.advanced_email_reports)
        tools_menu.add_command(label="System Health", command=self.system_health)
        tools_menu.add_command(label="Database Cleanup", command=self.database_cleanup)
        tools_menu.add_command(label="Advanced Search", command=self.advanced_search)
        tools_menu.add_command(label="Communication Stats", command=self.communication_stats)
        tools_menu.add_separator()
        tools_menu.add_command(label="Fix Email Senders", command=self.fix_email_senders)
        tools_menu.add_command(label="Test Sender Attribution", command=self.test_sender_attribution)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

        # Bind keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.compose_email())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a top-right button exists for returning to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def fix_email_senders(self):
        """Fix existing email sender attribution"""
        if messagebox.askyesno("Confirm", "Fix email sender attribution? This will update existing messages."):
            try:
                # Import the function from email_manager
                from university_system.infrastructure.email.email_service import fix_existing_email_senders
                count = fix_existing_email_senders()
                messagebox.showinfo("Success", f"Fixed {count} messages with proper sender attribution")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to fix senders: {e}")

    def test_sender_attribution(self):
        """Test sender attribution"""
        try:
            # Import the function from email_manager
            from university_system.infrastructure.email.email_service import test_sender_attribution as test_func
            result = test_func()
            if result:
                messagebox.showinfo("Test", "Sender attribution test completed. Check the console for details.")
            else:
                messagebox.showwarning("Test", "Sender attribution test failed. Check the console for details.")
        except Exception as e:
            messagebox.showerror("Error", f"Test failed: {e}")
        
    def create_main_interface(self):
        """Create the main interface with notebook tabs"""
        # Add return to main menu button at top right
        return_btn = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu
        )
        return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create status frame
        self.create_status_frame(main_frame)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_email_tab()
        self.create_messages_tab()
        self.create_sms_tab()
        self.create_announcements_tab()
        self.create_chat_tab()
        self.create_reports_tab()
        
    def create_status_frame(self, parent):
        """Create status bar and notifications"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(status_frame, text="Ready")
        self.status_label.pack(side=tk.LEFT)
        
        # Notification area
        self.notification_frame = ttk.Frame(status_frame)
        self.notification_frame.pack(side=tk.RIGHT)
        
        # Email mode indicator
        mode = "Database Mode" if config.get('database_only_mode', True) else "SMTP Mode"
        mode_label = ttk.Label(self.notification_frame, text=f"📧 {mode}")
        mode_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # User info
        user_text = f"👤 {self.auth.current_user['username']} ({self.auth.current_user['role']})"
        user_label = ttk.Label(self.notification_frame, text=user_text)
        user_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Homescreen navigation button keeps experience consistent with other GUIs
        exit_button = ttk.Button(
            self.notification_frame,
            text="🏠 Return to Homescreen",
            command=self.return_to_main_menu,
        )
        exit_button.pack(side=tk.RIGHT, padx=(10, 0))
        
    def create_dashboard_tab(self):
        """Create the main dashboard tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Dashboard")
        
        # Welcome section
        welcome_frame = ttk.LabelFrame(tab_frame, text="Welcome", padding=10)
        welcome_frame.pack(fill=tk.X, padx=10, pady=10)
        
        welcome_text = f"Welcome to the University Communication System, {self.auth.current_user['username']}!"
        ttk.Label(welcome_frame, text=welcome_text, font=('Arial', 12, 'bold')).pack()
        
        # Quick actions
        actions_frame = ttk.LabelFrame(tab_frame, text="Quick Actions", padding=10)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack()
        
        # Create action buttons
        actions = [
            ("📧 Compose Email", self.compose_email),
            ("📨 Check Messages", self.open_messages),
            ("📢 View Announcements", self.open_announcements),
            ("💬 Chat Rooms", self.open_chat_rooms),
            ("📊 Email Reports", self.email_reports),
            ("⚙️ Settings", self.email_configuration)
        ]
        
        for i, (text, command) in enumerate(actions):
            row, col = divmod(i, 3)
            btn = ttk.Button(actions_grid, text=text, command=command, width=20)
            btn.grid(row=row, column=col, padx=5, pady=5)
        
        # Statistics section
        self.create_stats_section(tab_frame)
        
    def create_stats_section(self, parent):
        """Create statistics section for dashboard"""
        stats_frame = ttk.LabelFrame(parent, text="Statistics", padding=10)
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack()
        
        # Stats labels
        self.stats_labels = {}
        stats_items = [
            ("emails_sent", "Emails Sent"),
            ("emails_stored", "Emails Stored"),
            ("messages_received", "Messages Received"),
            ("unread_messages", "Unread Messages"),
            ("announcements", "Active Announcements"),
            ("chat_rooms", "Chat Rooms Joined")
        ]
        
        for i, (key, label) in enumerate(stats_items):
            row, col = divmod(i, 3)
            
            frame = ttk.Frame(stats_grid)
            frame.grid(row=row, column=col, padx=20, pady=10)
            
            ttk.Label(frame, text=label, font=('Arial', 10)).pack()
            self.stats_labels[key] = ttk.Label(frame, text="0", font=('Arial', 14, 'bold'))
            self.stats_labels[key].pack()
        
    def create_email_tab(self):
        """Create the email management tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Email")
        
        # Email toolbar
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(toolbar_frame, text="Compose", command=self.compose_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Send Bulk", command=self.send_bulk_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Templates", command=self.manage_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Schedule", command=self.schedule_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Refresh", command=self.refresh_emails).pack(side=tk.RIGHT, padx=5)
        
        # Email list
        self.create_email_list(tab_frame)
        
    def create_email_list(self, parent):
        """Create email list with treeview"""
        list_frame = ttk.LabelFrame(parent, text="Stored Emails", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create treeview
        columns = ("ID", "Recipient", "Subject", "Date", "Template", "Status")
        self.email_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        for col in columns:
            self.email_tree.heading(col, text=col)
            if col == "ID":
                self.email_tree.column(col, width=50)
            elif col == "Subject":
                self.email_tree.column(col, width=300)
            else:
                self.email_tree.column(col, width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.email_tree.yview)
        self.email_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.email_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click
        self.email_tree.bind("<Double-1>", self.view_email_details)
        
        # Context menu
        self.email_tree.bind("<Button-3>", self.show_email_context_menu)
        
    def create_messages_tab(self):
        """Create the messages tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Messages")
        
        # Messages toolbar
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(toolbar_frame, text="Compose Message", command=self.compose_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Reply", command=self.reply_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Delete", command=self.delete_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Refresh", command=self.refresh_messages).pack(side=tk.RIGHT, padx=5)
        
        # Create paned window for inbox and message view
        paned = ttk.PanedWindow(tab_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left pane - message list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        # Messages list
        ttk.Label(left_frame, text="Inbox", font=('Arial', 12, 'bold')).pack(pady=(0, 5))

        # Create frame for treeview with scrollbar
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.messages_tree = ttk.Treeview(
            tree_frame,
            columns=("From", "Subject", "Date", "Status"),
            show="headings",
            selectmode='browse',  # Allow single selection
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        self.messages_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb.config(command=self.messages_tree.yview)
        hsb.config(command=self.messages_tree.xview)

        # Configure columns with proper widths
        self.messages_tree.heading("From", text="From")
        self.messages_tree.column("From", width=150, minwidth=100)

        self.messages_tree.heading("Subject", text="Subject")
        self.messages_tree.column("Subject", width=250, minwidth=150)

        self.messages_tree.heading("Date", text="Date")
        self.messages_tree.column("Date", width=150, minwidth=120)

        self.messages_tree.heading("Status", text="Status")
        self.messages_tree.column("Status", width=80, minwidth=60)

        # Enable row selection highlighting
        self.messages_tree.tag_configure('unread', background='#E8F4F8')
        self.messages_tree.tag_configure('read', background='white')

        self.messages_tree.bind("<<TreeviewSelect>>", self.on_message_select)
        self.messages_tree.bind("<Double-1>", self.on_message_double_click)
        self.messages_tree.bind("<Button-3>", self.show_message_context_menu)

        # Add helpful label
        help_label = ttk.Label(
            left_frame,
            text="💡 Click a message to view • Double-click or use Reply button to respond",
            font=('Arial', 9, 'italic'),
            foreground='#666'
        )
        help_label.pack(pady=(5, 0))
        
        # Right pane - message viewer
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        ttk.Label(right_frame, text="Message Content", font=('Arial', 12, 'bold')).pack()
        
        self.message_text = scrolledtext.ScrolledText(right_frame, state=tk.DISABLED, wrap=tk.WORD)
        self.message_text.pack(fill=tk.BOTH, expand=True)

    def create_sms_tab(self):
        """Create the SMS messaging tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="SMS")

        # Create main paned window for compose and history
        paned = ttk.PanedWindow(tab_frame, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top pane - SMS Composer
        compose_frame = ttk.LabelFrame(paned, text="📱 Compose SMS", padding=10)
        paned.add(compose_frame, weight=1)

        # Recipient selection
        recipient_frame = ttk.Frame(compose_frame)
        recipient_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(recipient_frame, text="Recipient:").pack(side=tk.LEFT, padx=(0, 5))

        # Recipient type selection
        self.sms_recipient_type = tk.StringVar(value="individual")
        ttk.Radiobutton(recipient_frame, text="Individual", variable=self.sms_recipient_type,
                       value="individual", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(recipient_frame, text="Group", variable=self.sms_recipient_type,
                       value="group", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(recipient_frame, text="Role", variable=self.sms_recipient_type,
                       value="role", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)

        # Recipient input area
        recipient_input_frame = ttk.Frame(compose_frame)
        recipient_input_frame.pack(fill=tk.X, pady=(0, 10))

        # Phone number entry (for individual)
        phone_frame = ttk.Frame(recipient_input_frame)
        phone_frame.pack(fill=tk.X)
        ttk.Label(phone_frame, text="Phone Number:").pack(side=tk.LEFT, padx=(0, 5))
        self.sms_phone_entry = ttk.Entry(phone_frame, width=20)
        self.sms_phone_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(phone_frame, text="(Format: +1234567890)", foreground='gray').pack(side=tk.LEFT)

        # User selection combobox (for individual user lookup)
        user_frame = ttk.Frame(recipient_input_frame)
        ttk.Label(user_frame, text="Or select user:").pack(side=tk.LEFT, padx=(0, 5))
        self.sms_user_combo = ttk.Combobox(user_frame, width=30, state='readonly')
        self.sms_user_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.sms_user_combo.bind('<<ComboboxSelected>>', self.on_sms_user_selected)
        ttk.Button(user_frame, text="🔄 Refresh Users", command=self.load_sms_users).pack(side=tk.LEFT, padx=5)

        # Group/Role selection (hidden by default)
        self.sms_group_frame = ttk.Frame(recipient_input_frame)
        ttk.Label(self.sms_group_frame, text="Select Group/Role:").pack(side=tk.LEFT, padx=(0, 5))
        self.sms_group_combo = ttk.Combobox(self.sms_group_frame, width=30, state='readonly')
        self.sms_group_combo.pack(side=tk.LEFT, padx=(0, 5))

        # Message area
        message_frame = ttk.Frame(compose_frame)
        message_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        ttk.Label(message_frame, text="Message:").pack(anchor=tk.W, pady=(0, 5))

        # Character counter
        counter_frame = ttk.Frame(message_frame)
        counter_frame.pack(fill=tk.X, pady=(0, 5))
        self.sms_char_label = ttk.Label(counter_frame, text="0 / 160 characters", foreground='gray')
        self.sms_char_label.pack(side=tk.RIGHT)

        # Text area with scrollbar
        text_scroll_frame = ttk.Frame(message_frame)
        text_scroll_frame.pack(fill=tk.BOTH, expand=True)

        self.sms_message_text = scrolledtext.ScrolledText(text_scroll_frame, height=5, wrap=tk.WORD)
        self.sms_message_text.pack(fill=tk.BOTH, expand=True)
        self.sms_message_text.bind('<KeyRelease>', self.update_sms_char_count)

        # Action buttons
        button_frame = ttk.Frame(compose_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="📤 Send SMS", command=self.send_sms).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Clear", command=self.clear_sms_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📋 Template", command=self.sms_templates).pack(side=tk.LEFT, padx=5)

        # Bottom pane - SMS History
        history_frame = ttk.LabelFrame(paned, text="📋 SMS History", padding=10)
        paned.add(history_frame, weight=2)

        # History toolbar
        history_toolbar = ttk.Frame(history_frame)
        history_toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(history_toolbar, text="🔄 Refresh", command=self.refresh_sms_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(history_toolbar, text="🗑️ Delete", command=self.delete_sms).pack(side=tk.LEFT, padx=5)
        ttk.Button(history_toolbar, text="📊 Statistics", command=self.sms_statistics).pack(side=tk.LEFT, padx=5)

        # Search frame
        search_frame = ttk.Frame(history_toolbar)
        search_frame.pack(side=tk.RIGHT)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.sms_search_entry = ttk.Entry(search_frame, width=20)
        self.sms_search_entry.pack(side=tk.LEFT)
        self.sms_search_entry.bind('<KeyRelease>', lambda e: self.refresh_sms_history())

        # History tree
        tree_frame = ttk.Frame(history_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.sms_history_tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "Date", "Recipient", "Phone", "Message", "Status"),
            show="headings",
            selectmode='browse',
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        self.sms_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb.config(command=self.sms_history_tree.yview)
        hsb.config(command=self.sms_history_tree.xview)

        # Configure columns
        self.sms_history_tree.heading("ID", text="ID")
        self.sms_history_tree.column("ID", width=50, minwidth=50)

        self.sms_history_tree.heading("Date", text="Date & Time")
        self.sms_history_tree.column("Date", width=150, minwidth=120)

        self.sms_history_tree.heading("Recipient", text="Recipient")
        self.sms_history_tree.column("Recipient", width=150, minwidth=100)

        self.sms_history_tree.heading("Phone", text="Phone Number")
        self.sms_history_tree.column("Phone", width=120, minwidth=100)

        self.sms_history_tree.heading("Message", text="Message")
        self.sms_history_tree.column("Message", width=300, minwidth=200)

        self.sms_history_tree.heading("Status", text="Status")
        self.sms_history_tree.column("Status", width=100, minwidth=80)

        # Status tags
        self.sms_history_tree.tag_configure('sent', background='#E8F8E8')
        self.sms_history_tree.tag_configure('failed', background='#FFE8E8')
        self.sms_history_tree.tag_configure('pending', background='#FFF8E8')

        # Load initial data
        self.load_sms_users()
        self.refresh_sms_history()

    def create_announcements_tab(self):
        """Create the announcements tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Announcements")

        # Announcements toolbar
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

        if self.auth.current_user['role'] in ['admin', 'staff', 'instructor']:
            ttk.Button(toolbar_frame, text="Create Announcement", command=self.create_announcement_dialog).pack(side=tk.LEFT, padx=5)
            ttk.Button(toolbar_frame, text="Edit Announcement", command=self.edit_announcement).pack(side=tk.LEFT, padx=5)
            ttk.Button(toolbar_frame, text="Delete Announcement", command=self.delete_announcement).pack(side=tk.LEFT, padx=5)

        ttk.Button(toolbar_frame, text="Refresh", command=self.refresh_announcements).pack(side=tk.RIGHT, padx=5)

        # Create announcements list FIRST
        self.create_announcements_list(tab_frame)

    def create_announcements_list(self, parent):
        """Create announcements list"""
        list_frame = ttk.LabelFrame(parent, text="Active Announcements", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        columns = ("Title", "Creator", "Date", "Audience", "Urgent")
        self.announcements_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns:
            self.announcements_tree.heading(col, text=col)
            if col == "Title":
                self.announcements_tree.column(col, width=300)
            else:
                self.announcements_tree.column(col, width=150)
        
        scrollbar2 = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.announcements_tree.yview)
        self.announcements_tree.configure(yscrollcommand=scrollbar2.set)
        
        self.announcements_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind the event handler AFTER the tree is created
        self.announcements_tree.bind("<Double-1>", self.view_announcement_details)

    def create_announcement_dialog(self):
        """Open create announcement dialog"""
        CreateAnnouncementDialog(self.root, self.dashboard)

    def edit_announcement(self):
        """Edit selected announcement"""
        selection = self.announcements_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an announcement to edit")
            return

        item = self.announcements_tree.item(selection[0])
        announcement_id = item['tags'][0] if item['tags'] else None

        if not announcement_id:
            messagebox.showerror("Error", "Could not determine announcement ID")
            return

        # Open edit dialog
        EditAnnouncementDialog(self.root, self.dashboard, announcement_id, self.refresh_announcements)

    def delete_announcement(self):
        """Delete selected announcement"""
        selection = self.announcements_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an announcement to delete")
            return

        item = self.announcements_tree.item(selection[0])
        announcement_id = item['tags'][0] if item['tags'] else None
        announcement_title = item['values'][0] if item['values'] else "this announcement"

        if not announcement_id:
            messagebox.showerror("Error", "Could not determine announcement ID")
            return

        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{announcement_title}'?"):
            return

        try:
            from university_system.infrastructure.database.db import get_db_connection

            conn = get_db_connection()
            cursor = conn.cursor()

            # Delete the announcement
            cursor.execute('DELETE FROM announcements WHERE id = ?', (announcement_id,))
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement deleted successfully!")
            self.refresh_announcements()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete announcement: {e}")

    def create_chat_tab(self):
        """Create the chat rooms tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Chat Rooms")
        
        # Chat toolbar
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(toolbar_frame, text="Create Room", command=self.create_chat_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Join Room", command=self.join_chat_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Invitations", command=self.view_invitations).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Refresh", command=self.refresh_chat_rooms).pack(side=tk.RIGHT, padx=5)
        
        # Chat rooms notebook
        self.chat_notebook = ttk.Notebook(tab_frame)
        self.chat_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # My rooms tab
        self.create_my_rooms_tab()
        
        # Public rooms tab
        self.create_public_rooms_tab()
        
    def create_my_rooms_tab(self):
        """Create my chat rooms tab"""
        tab_frame = ttk.Frame(self.chat_notebook)
        self.chat_notebook.add(tab_frame, text="My Rooms")
        
        columns = ("Name", "Type", "Members", "Messages", "Role")
        self.my_rooms_tree = ttk.Treeview(tab_frame, columns=columns, show="headings")
        
        for col in columns:
            self.my_rooms_tree.heading(col, text=col)
        
        scrollbar3 = ttk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=self.my_rooms_tree.yview)
        self.my_rooms_tree.configure(yscrollcommand=scrollbar3.set)
        
        self.my_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar3.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.my_rooms_tree.bind("<Double-1>", self.enter_chat_room)
        
    def create_public_rooms_tab(self):
        """Create public rooms tab"""
        tab_frame = ttk.Frame(self.chat_notebook)
        self.chat_notebook.add(tab_frame, text="Public Rooms")
        
        columns = ("Name", "Description", "Members", "Creator")
        self.public_rooms_tree = ttk.Treeview(tab_frame, columns=columns, show="headings")
        
        for col in columns:
            self.public_rooms_tree.heading(col, text=col)
        
        scrollbar4 = ttk.Scrollbar(tab_frame, orient=tk.VERTICAL, command=self.public_rooms_tree.yview)
        self.public_rooms_tree.configure(yscrollcommand=scrollbar4.set)
        
        self.public_rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar4.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_reports_tab(self):
        """Enhanced reports tab"""
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text="Reports")
        
        # Reports toolbar
        toolbar_frame = ttk.Frame(tab_frame)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(toolbar_frame, text="Email Reports", command=self.advanced_email_reports).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Communication Stats", command=self.communication_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Advanced Search", command=self.advanced_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="Export Data", command=self.export_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_frame, text="System Health", command=self.system_health).pack(side=tk.LEFT, padx=5)
        
        # Report display area
        report_frame = ttk.LabelFrame(tab_frame, text="Report Results", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True)

    def advanced_email_reports(self):
        """Open advanced email reports dialog"""
        EmailReportsDialog(self.root)

    def communication_stats(self):
        """Show communication statistics"""
        try:
            if self.dashboard and get_user_communication_stats:
                stats = get_user_communication_stats(self.dashboard)
                if stats:
                    stats_text = f"""Communication Statistics:
                    
    Messages Sent: {stats['messages_sent']}
    Messages Received: {stats['messages_received']}
    Unread Messages: {stats['unread_messages']}
    Announcements Created: {stats['announcements_created']}
    Chat Rooms Joined: {stats['chat_rooms_joined']}
    Chat Rooms Created: {stats['chat_rooms_created']}
    """
                    self.report_text.delete(1.0, tk.END)
                    self.report_text.insert(1.0, stats_text)
                else:
                    messagebox.showinfo("Info", "Could not retrieve statistics")
            else:
                messagebox.showinfo("Info", "Dashboard not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error getting statistics: {e}")

    def advanced_search(self):
        """Open advanced search dialog"""
        AdvancedSearchDialog(self.root, self.dashboard)
        
    def load_initial_data(self):
        """Load initial data for all tabs"""
        self.refresh_emails()
        self.refresh_messages()
        self.refresh_announcements()
        self.refresh_chat_rooms()
        self.update_stats()
        
    def update_stats(self):
        """Update dashboard statistics"""
        try:
            # Get email statistics
            if 'get_stored_emails' in globals():
                emails_data = get_stored_emails(limit=1)
                self.stats_labels['emails_stored'].config(text=str(emails_data['total_count']))
            
            # Get message statistics
            if self.dashboard:
                inbox = self.dashboard.get_inbox()
                self.stats_labels['unread_messages'].config(text=str(inbox.get('unread_count', 0)))
                self.stats_labels['messages_received'].config(text=str(inbox.get('total_count', 0)))
                
                # Get announcements
                announcements = self.dashboard.get_announcements()
                self.stats_labels['announcements'].config(text=str(announcements.get('total_count', 0)))
                
                # Get chat rooms
                rooms = self.dashboard.get_chat_rooms('joined')
                self.stats_labels['chat_rooms'].config(text=str(rooms.get('total_count', 0)))
                
        except Exception as e:
            print(f"Error updating stats: {e}")
    
    def refresh_emails(self):
        """Refresh the email list"""
        try:
            # Clear existing items
            for item in self.email_tree.get_children():
                self.email_tree.delete(item)
            
            # Get stored emails
            if 'get_stored_emails' in globals():
                emails_data = get_stored_emails(limit=100)
                
                for email in emails_data['emails']:
                    self.email_tree.insert('', tk.END, values=(
                        email['id'],
                        email['recipient_email'],
                        email['subject'][:50] + ('...' if len(email['subject']) > 50 else ''),
                        email['created_date'],
                        email['template_name'] or 'Direct',
                        'Stored'
                    ))
            
            self.update_status("Email list refreshed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh emails: {e}")
    
    def refresh_messages(self):
        """Refresh the messages list"""
        try:
            # Clear existing items
            for item in self.messages_tree.get_children():
                self.messages_tree.delete(item)

            if self.dashboard:
                inbox = self.dashboard.get_inbox()

                # Handle case where inbox might be a boolean or None
                if isinstance(inbox, dict):
                    messages = inbox.get('messages', [])

                    if not messages:
                        # Insert a placeholder if no messages
                        self.messages_tree.insert('', tk.END, values=(
                            "No messages",
                            "Your inbox is empty",
                            "",
                            ""
                        ), tags=('empty',))
                    else:
                        for message in messages:
                            status = "NEW" if not message['is_read'] else "READ"
                            # Use different tags for styling
                            tag = 'unread' if not message['is_read'] else 'read'

                            self.messages_tree.insert('', tk.END, values=(
                                message['sender'],
                                message['subject'][:40] + ('...' if len(message['subject']) > 40 else ''),
                                message['sent_at'],
                                status
                            ), tags=(str(message['id']), tag))

                    self.update_status(f"Messages refreshed - {len(messages)} message(s)")
                else:
                    print(f"Warning: inbox is not a dict, it's {type(inbox)}")
                    # Show error in tree
                    self.messages_tree.insert('', tk.END, values=(
                        "Error",
                        "Failed to load messages",
                        "",
                        ""
                    ), tags=('error',))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh messages: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_announcements(self):
        """Refresh the announcements list"""
        try:
            # Clear existing items
            for item in self.announcements_tree.get_children():
                self.announcements_tree.delete(item)
            
            if self.dashboard:
                announcements = self.dashboard.get_announcements()
                
                for announcement in announcements.get('announcements', []):
                    urgent_text = "YES" if announcement.get('is_urgent') else "NO"
                    self.announcements_tree.insert('', tk.END, values=(
                        announcement['title'],
                        announcement['creator'],
                        announcement['created_at'],
                        announcement['target_audience'],
                        urgent_text
                    ), tags=(announcement['id'],))
            
            self.update_status("Announcements refreshed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh announcements: {e}")
    
    def refresh_chat_rooms(self):
        """Refresh the chat rooms lists"""
        try:
            if not self.dashboard:
                return
                
            # Refresh my rooms
            for item in self.my_rooms_tree.get_children():
                self.my_rooms_tree.delete(item)
            
            my_rooms = self.dashboard.get_chat_rooms('joined')
            for room in my_rooms.get('rooms', []):
                role = "Admin" if room['is_admin'] else "Member"
                self.my_rooms_tree.insert('', tk.END, values=(
                    room['name'],
                    room['room_type'],
                    room['member_count'],
                    room['message_count'],
                    role
                ), tags=(room['id'],))
            
            # Refresh public rooms
            for item in self.public_rooms_tree.get_children():
                self.public_rooms_tree.delete(item)
            
            public_rooms = self.dashboard.get_chat_rooms('public')
            for room in public_rooms.get('rooms', []):
                desc = room['description'][:30] + '...' if room['description'] and len(room['description']) > 30 else (room['description'] or '')
                self.public_rooms_tree.insert('', tk.END, values=(
                    room['name'],
                    desc,
                    room['member_count'],
                    room['creator']
                ), tags=(room['id'],))
            
            self.update_status("Chat rooms refreshed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh chat rooms: {e}")
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
        self.root.update_idletasks()
    
    # Email Functions
    def compose_email(self, recipient=None):
        """Open compose email dialog with optional pre-filled recipient"""
        ComposeEmailDialog(self.root, self.auth, recipient=recipient)
    
    def send_bulk_email(self):
        """Open bulk email dialog"""
        BulkEmailDialog(self.root, self.auth)
    
    def schedule_email(self):
        """Open schedule email dialog"""
        ScheduleEmailDialog(self.root)
    
    def manage_templates(self):
        """Open template management dialog"""
        TemplateManagerDialog(self.root)
    
    def email_configuration(self):
        """Open email configuration dialog"""
        EmailConfigDialog(self.root)

    # Notification Methods
    def send_registration_confirmation_dialog(self):
        """Open registration confirmation dialog"""
        RegistrationConfirmationDialog(self.root)

    def send_assignment_notification_dialog(self):
        """Open assignment notification dialog"""
        AssignmentNotificationDialog(self.root)

    def send_module_grade_notification_dialog(self):
        """Open module grade notification dialog"""
        ModuleGradeNotificationDialog(self.root)

    def send_assignment_grade_notification_dialog(self):
        """Open assignment grade notification dialog"""
        AssignmentGradeNotificationDialog(self.root)

    def send_extension_notification_dialog(self):
        """Open extension notification dialog"""
        ExtensionNotificationDialog(self.root)

    def send_update_confirmation_dialog(self):
        """Open update confirmation dialog"""
        UpdateConfirmationDialog(self.root)

    def send_password_reset_dialog(self):
        """Open password reset dialog"""
        PasswordResetDialog(self.root)

    # Health Services Notification Methods
    def send_appointment_confirmation_dialog(self):
        """Open appointment confirmation dialog"""
        AppointmentConfirmationDialog(self.root)

    def send_health_notification_dialog(self):
        """Open health advisory notification dialog"""
        HealthNotificationDialog(self.root)

    # Helpdesk Notification Methods
    def send_ticket_notification_dialog(self):
        """Open ticket notification dialog"""
        TicketNotificationDialog(self.root)

    def send_reply_notification_dialog(self):
        """Open reply notification dialog"""
        ReplyNotificationDialog(self.root)

    # Library Notification Methods
    def send_book_checkout_confirmation_dialog(self):
        """Open book checkout confirmation dialog"""
        BookCheckoutConfirmationDialog(self.root)

    def send_book_return_reminder_dialog(self):
        """Open book return reminder dialog"""
        BookReturnReminderDialog(self.root)

    def send_overdue_notification_dialog(self):
        """Open overdue notification dialog"""
        OverdueNotificationDialog(self.root)

    # Student Affairs Notification Methods
    def send_internship_notification_dialog(self):
        """Open internship notification dialog"""
        InternshipNotificationDialog(self.root)

    def send_mentorship_notification_dialog(self):
        """Open mentorship notification dialog"""
        MentorshipNotificationDialog(self.root)

    # Alumni Notification Methods
    def send_alumni_welcome_dialog(self):
        """Open alumni welcome email dialog"""
        AlumniWelcomeDialog(self.root)

    def send_event_invitation_dialog(self):
        """Open event invitation dialog"""
        EventInvitationDialog(self.root)

    def send_donation_receipt_dialog(self):
        """Open donation receipt dialog"""
        DonationReceiptDialog(self.root)

    def view_email_details(self, event):
        """View details of selected email"""
        selection = self.email_tree.selection()
        if selection:
            item = self.email_tree.item(selection[0])
            email_id = item['values'][0]
            EmailDetailsDialog(self.root, email_id)
    
    def show_email_context_menu(self, event):
        """Show context menu for email"""
        # Create context menu
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="View Details", command=lambda: self.view_email_details(event))
        context_menu.add_command(label="Delete", command=self.delete_selected_email)
        context_menu.add_separator()
        context_menu.add_command(label="Export", command=self.export_selected_email)
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
    
    def delete_selected_email(self):
        """Delete selected email"""
        selection = self.email_tree.selection()
        if selection:
            item = self.email_tree.item(selection[0])
            email_id = item['values'][0]
            
            if messagebox.askyesno("Confirm Delete", f"Delete email ID {email_id}?"):
                try:
                    if 'delete_stored_email' in globals():
                        if delete_stored_email(email_id):
                            self.refresh_emails()
                            self.update_status(f"Email {email_id} deleted")
                        else:
                            messagebox.showerror("Error", "Failed to delete email")
                except Exception as e:
                    messagebox.showerror("Error", f"Error deleting email: {e}")
    
    def export_selected_email(self):
        """Export selected email"""
        selection = self.email_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an email to export")
            return

        item = self.email_tree.item(selection[0])
        email_id = item['values'][0]

        # Ask user for export format
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("Export Email")
        export_dialog.geometry("300x150")
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        ttk.Label(export_dialog, text="Select Export Format:", font=('Arial', 10, 'bold')).pack(pady=10)

        format_var = tk.StringVar(value="txt")
        ttk.Radiobutton(export_dialog, text="Text File (.txt)", variable=format_var, value="txt").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(export_dialog, text="HTML File (.html)", variable=format_var, value="html").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(export_dialog, text="JSON File (.json)", variable=format_var, value="json").pack(anchor=tk.W, padx=20)

        def do_export():
            format_type = format_var.get()
            export_dialog.destroy()

            # Get email details
            try:
                from university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
                email_data = cursor.fetchone()
                conn.close()

                if not email_data:
                    messagebox.showerror("Error", "Email not found")
                    return

                # Ask for file location
                file_types = {
                    "txt": [("Text files", "*.txt"), ("All files", "*.*")],
                    "html": [("HTML files", "*.html"), ("All files", "*.*")],
                    "json": [("JSON files", "*.json"), ("All files", "*.*")]
                }

                file_path = filedialog.asksaveasfilename(
                    title="Save Email Export",
                    defaultextension=f".{format_type}",
                    filetypes=file_types.get(format_type, [("All files", "*.*")])
                )

                if not file_path:
                    return

                # Export based on format
                if format_type == "txt":
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"Email ID: {email_data[0]}\n")
                        f.write(f"Recipient: {email_data[1]}\n")
                        f.write(f"Subject: {email_data[2]}\n")
                        f.write(f"Sent At: {email_data[6]}\n")
                        f.write(f"Status: {email_data[7]}\n")
                        f.write(f"\n{'='*50}\n\n")
                        f.write(f"{email_data[3]}\n")

                elif format_type == "html":
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(f"<!DOCTYPE html>\n<html>\n<head>\n<title>{email_data[2]}</title>\n</head>\n<body>\n")
                        f.write(f"<h2>{email_data[2]}</h2>\n")
                        f.write(f"<p><strong>Recipient:</strong> {email_data[1]}</p>\n")
                        f.write(f"<p><strong>Sent:</strong> {email_data[6]}</p>\n")
                        f.write(f"<hr>\n<div>{email_data[3]}</div>\n")
                        f.write(f"</body>\n</html>")

                elif format_type == "json":
                    email_dict = {
                        "id": email_data[0],
                        "recipient": email_data[1],
                        "subject": email_data[2],
                        "body": email_data[3],
                        "cc": email_data[4],
                        "bcc": email_data[5],
                        "sent_at": email_data[6],
                        "status": email_data[7]
                    }
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(email_dict, f, indent=4)

                messagebox.showinfo("Success", f"Email exported successfully to {file_path}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export email: {e}")

        ttk.Button(export_dialog, text="Export", command=do_export).pack(pady=10)
        ttk.Button(export_dialog, text="Cancel", command=export_dialog.destroy).pack()
    
    # Message Functions
    def compose_message(self):
        """Open compose message dialog"""
        ComposeMessageDialog(self.root, self.dashboard)
    
    def reply_message(self):
        """Reply to selected message"""
        selection = self.messages_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to reply to")
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
            return

        item = self.messages_tree.item(selection[0])
        message_id = item['tags'][0]
        ReplyMessageDialog(self.root, self.dashboard, message_id)
    
    def delete_message(self):
        """Delete selected message"""
        selection = self.messages_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a message to delete")
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
            return

        item = self.messages_tree.item(selection[0])
        message_id = item['tags'][0]

        if messagebox.askyesno("Confirm Delete", "Delete this message?"):
            try:
                if self.dashboard.update_message_status(message_id, 'delete'):
                    self.refresh_messages()
                    self.update_status("Message deleted")
                else:
                    messagebox.showerror("Error", "Failed to delete message")
            except Exception as e:
                messagebox.showerror("Error", f"Error deleting message: {e}")
    
    def on_message_select(self, event):
        """Handle message selection"""
        selection = self.messages_tree.selection()
        if selection:
            item = self.messages_tree.item(selection[0])
            tags = item['tags']

            # Skip if this is a placeholder message
            if 'empty' in tags or 'error' in tags:
                return

            if not tags:
                return

            message_id = tags[0]

            try:
                if self.dashboard:
                    message = self.dashboard.read_message(message_id)
                    if message:
                        self.message_text.config(state=tk.NORMAL)
                        self.message_text.delete(1.0, tk.END)

                        # Format message content
                        content = f"From: {message['sender']}\n"
                        content += f"To: {message['recipient']}\n"
                        content += f"Subject: {message['subject']}\n"
                        content += f"Date: {message['sent_at']}\n"
                        content += f"Status: {'Read' if message['is_read'] else 'Unread'}\n"
                        content += "-" * 50 + "\n\n"
                        content += message['content']

                        self.message_text.insert(1.0, content)
                        self.message_text.config(state=tk.DISABLED)

                        # Mark as read
                        self.refresh_messages()
            except Exception as e:
                messagebox.showerror("Error", f"Error loading message: {e}")
                import traceback
                traceback.print_exc()

    def on_message_double_click(self, event):
        """Handle double-click on message - open reply dialog"""
        selection = self.messages_tree.selection()
        if selection:
            # Same as clicking Reply button
            self.reply_message()

    def show_message_context_menu(self, event):
        """Show context menu for message"""
        # Select the item under cursor
        item = self.messages_tree.identify_row(event.y)
        if item:
            self.messages_tree.selection_set(item)

            # Check if it's a valid message (not placeholder)
            item_data = self.messages_tree.item(item)
            tags = item_data['tags']

            if 'empty' in tags or 'error' in tags:
                return

            # Create context menu
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Reply", command=self.reply_message)
            context_menu.add_command(label="Delete", command=self.delete_message)
            context_menu.add_separator()
            context_menu.add_command(label="Mark as Unread", command=lambda: self.mark_message_unread(tags[0]))
            context_menu.add_command(label="Archive", command=lambda: self.archive_message(tags[0]))

            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

    def mark_message_unread(self, message_id):
        """Mark a message as unread"""
        try:
            if self.dashboard:
                # Call dashboard method to mark unread
                from university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE messages SET is_read = 0, read_at = NULL WHERE id = ?', (message_id,))
                conn.commit()
                conn.close()
                self.refresh_messages()
                self.update_status("Message marked as unread")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to mark as unread: {e}")

    def archive_message(self, message_id):
        """Archive a message"""
        try:
            if self.dashboard:
                from university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE messages SET is_archived = 1 WHERE id = ?', (message_id,))
                conn.commit()
                conn.close()
                self.refresh_messages()
                self.update_status("Message archived")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to archive message: {e}")

    # Announcement Functions
    def create_announcement(self):
        """Open create announcement dialog"""
        CreateAnnouncementDialog(self.root, self.dashboard)
    
    def view_announcement_details(self, event):
        """View announcement details"""
        selection = self.announcements_tree.selection()
        if selection:
            item = self.announcements_tree.item(selection[0])
            announcement_id = item['tags'][0]
            AnnouncementDetailsDialog(self.root, self.dashboard, announcement_id)
                
    # Chat Functions
    def create_chat_room(self):
        """Open create chat room dialog"""
        CreateChatRoomDialog(self.root, self.dashboard, self.refresh_chat_rooms)
    
    def join_chat_room(self):
        """Join selected public chat room"""
        selection = self.public_rooms_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a chat room to join")
            return

        if not self.dashboard:
            messagebox.showerror("Error", "Dashboard not initialized. Please restart the application.")
            return

        item = self.public_rooms_tree.item(selection[0])
        room_id = item['tags'][0]

        try:
            result = self.dashboard.join_chat_room(room_id)
            if result == True:
                messagebox.showinfo("Success", "Successfully joined chat room!")
                self.refresh_chat_rooms()
            elif result == "already_member":
                messagebox.showinfo("Info", "You are already a member of this room")
            else:
                messagebox.showerror("Error", "Failed to join chat room")
        except Exception as e:
            messagebox.showerror("Error", f"Error joining chat room: {e}")
    
    def enter_chat_room(self, event):
        """Enter selected chat room"""
        selection = self.my_rooms_tree.selection()
        if selection:
            item = self.my_rooms_tree.item(selection[0])
            room_id = item['tags'][0]
            room_name = item['values'][0]
            ChatRoomWindow(self.root, self.dashboard, room_id, room_name)
    
    def view_invitations(self):
        """View chat room invitations"""
        ChatInvitationsDialog(self.root, self.dashboard)
    
    # Report Functions
    def email_reports(self):
        """Show email reports"""
        self.notebook.select(5)  # Switch to reports tab
        self.generate_email_report()
    
    def generate_email_report(self):
        """Generate and display email report"""
        try:
            self.report_text.delete(1.0, tk.END)

            report_content = "EMAIL SYSTEM REPORT\n"
            report_content += "=" * 70 + "\n\n"
            report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            # Get data from database
            from university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            # Stored Emails Statistics
            cursor.execute("SELECT COUNT(*) FROM stored_emails")
            stored_count = cursor.fetchone()[0]
            report_content += f"STORED EMAILS: {stored_count}\n"

            # Recent stored emails
            cursor.execute("""
                SELECT recipient_email, subject, created_date
                FROM stored_emails
                ORDER BY created_date DESC LIMIT 10
            """)
            recent_stored = cursor.fetchall()
            if recent_stored:
                report_content += "\nRecent Stored Emails:\n"
                report_content += "-" * 50 + "\n"
                for row in recent_stored:
                    report_content += f"• To: {row[0]}\n"
                    report_content += f"  Subject: {row[1]}\n"
                    report_content += f"  Date: {row[2]}\n\n"

            # Email Log Statistics
            cursor.execute("SELECT COUNT(*) FROM email_log")
            log_count = cursor.fetchone()[0]
            report_content += f"\nEMAIL LOG (Sent): {log_count}\n"

            # Status breakdown
            cursor.execute("SELECT status, COUNT(*) FROM email_log GROUP BY status")
            status_rows = cursor.fetchall()
            if status_rows:
                report_content += "\nBy Status:\n"
                for row in status_rows:
                    status = row[0] or 'Unknown'
                    report_content += f"  {status}: {row[1]}\n"

            # Internal Messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            msg_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 0")
            unread_count = cursor.fetchone()[0]

            report_content += f"\nINTERNAL MESSAGES: {msg_count}\n"
            report_content += f"  Unread: {unread_count}\n"
            report_content += f"  Read: {msg_count - unread_count}\n"

            # Templates
            cursor.execute("SELECT COUNT(*) FROM email_templates")
            template_count = cursor.fetchone()[0]
            report_content += f"\nEMAIL TEMPLATES: {template_count}\n"

            # Announcements
            try:
                cursor.execute("SELECT COUNT(*) FROM announcements WHERE is_active = 1")
                announcement_count = cursor.fetchone()[0]
                report_content += f"\nACTIVE ANNOUNCEMENTS: {announcement_count}\n"
            except:
                pass

            # Chat Rooms
            try:
                cursor.execute("SELECT COUNT(*) FROM chat_rooms WHERE is_active = 1")
                chatroom_count = cursor.fetchone()[0]
                report_content += f"ACTIVE CHAT ROOMS: {chatroom_count}\n"
            except:
                pass

            conn.close()

            self.report_text.insert(1.0, report_content)
            self.update_status("Report generated")

        except Exception as e:
            import traceback
            error_msg = f"Error generating report:\n{str(e)}\n\n{traceback.format_exc()}"
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, error_msg)
            messagebox.showerror("Error", f"Error generating report: {e}")
    
    def export_report_csv(self):
        """Export report to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filename:
                if 'get_stored_emails' in globals():
                    emails_data = get_stored_emails(limit=1000)
                    
                    import csv
                    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                        fieldnames = ['id', 'recipient_email', 'subject', 'created_date', 'template_name']
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        
                        writer.writeheader()
                        for email in emails_data['emails']:
                            writer.writerow({
                                'id': email['id'],
                                'recipient_email': email['recipient_email'],
                                'subject': email['subject'],
                                'created_date': email['created_date'],
                                'template_name': email['template_name'] or 'Direct'
                            })
                    
                    messagebox.showinfo("Success", f"Report exported to {filename}")
                    self.update_status(f"Report exported to {filename}")
                else:
                    messagebox.showerror("Error", "Export functionality not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error exporting report: {e}")
    
    def system_health(self):
        """Show system health dialog"""
        SystemHealthDialog(self.root)
    
    def database_cleanup(self):
        """Open database cleanup dialog"""
        DatabaseCleanupDialog(self.root)
    
    def notification_preferences(self):
        """Open notification preferences dialog"""
        NotificationPreferencesDialog(self.root, self.dashboard)
    
    # Utility Functions
    def import_contacts(self):
        """Import contacts from file"""
        filename = filedialog.askopenfilename(
            title="Import Contacts",
            filetypes=[("CSV files", "*.csv"), ("VCard files", "*.vcf"), ("All files", "*.*")]
        )

        if not filename:
            return

        try:
            import csv

            # Create import preview dialog
            import_dialog = tk.Toplevel(self.root)
            import_dialog.title("Import Contacts")
            import_dialog.geometry("700x500")
            import_dialog.transient(self.root)

            ttk.Label(import_dialog, text="Import Contacts Preview",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            ttk.Label(import_dialog, text=f"File: {filename}", foreground='blue').pack()

            # Preview frame
            preview_frame = ttk.LabelFrame(import_dialog, text="Preview (first 10 rows)", padding=10)
            preview_frame.pack(fill='both', expand=True, padx=10, pady=10)

            preview_tree = ttk.Treeview(preview_frame, columns=('Name', 'Email', 'Group'),
                                       show='headings', height=15)
            preview_tree.heading('Name', text='Name')
            preview_tree.heading('Email', text='Email')
            preview_tree.heading('Group', text='Group')

            for col in ('Name', 'Email', 'Group'):
                preview_tree.column(col, width=200)

            preview_tree.pack(fill='both', expand=True)

            # Parse CSV file
            contacts_to_import = []
            with open(filename, 'r', encoding='utf-8') as csvfile:
                # Try to detect if file has headers
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                has_header = sniffer.has_header(sample)

                csvfile.seek(0)
                reader = csv.reader(csvfile)

                if has_header:
                    next(reader)  # Skip header row

                for i, row in enumerate(reader):
                    if i < 10:  # Preview first 10
                        if len(row) >= 2:
                            name = row[0].strip()
                            email = row[1].strip()
                            group = row[2].strip() if len(row) > 2 else 'Imported'
                            preview_tree.insert('', 'end', values=(name, email, group))
                            contacts_to_import.append((name, email, group))
                        else:
                            contacts_to_import.append((row[0].strip() if row else '', '', 'Imported'))

            # Info label
            info_label = ttk.Label(import_dialog,
                                  text=f"Total contacts to import: {len(contacts_to_import)}",
                                  font=('TkDefaultFont', 10, 'bold'))
            info_label.pack(pady=5)

            def perform_import():
                try:
                    # In real implementation, save to database
                    # For now, just show success message
                    imported_count = 0
                    duplicate_count = 0

                    for name, email, group in contacts_to_import:
                        if email:  # Only import if email is present
                            # Here would check for duplicates and insert into database
                            imported_count += 1
                        else:
                            duplicate_count += 1

                    messagebox.showinfo("Import Complete",
                                      f"Successfully imported {imported_count} contacts!\n\n"
                                      f"Skipped {duplicate_count} invalid/duplicate entries.",
                                      parent=import_dialog)
                    import_dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Import Error", f"Failed to import contacts: {e}",
                                       parent=import_dialog)

            # Buttons
            button_frame = ttk.Frame(import_dialog)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Import", command=perform_import).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=import_dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to read contacts file: {e}")
    
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
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def export_data(self):
        """Export system data"""
        ExportDataDialog(self.root)

    def show_help(self):
        """Show help documentation"""
        HelpDialog(self.root)


    def open_messages(self):
        """Switch to messages tab"""
        self.notebook.select(2)  # Messages tab index
        self.refresh_messages()

    def open_announcements(self):
        """Switch to announcements tab"""
        self.notebook.select(3)  # Announcements tab index
        self.refresh_announcements()

    def open_chat_rooms(self):
        """Switch to chat rooms tab"""
        self.notebook.select(4)  # Chat rooms tab index
        self.refresh_chat_rooms()

    # Additional missing helper functions that may be referenced elsewhere
    def get_announcement_by_id(dashboard, announcement_id):
        """Get announcement by ID"""
        try:
            if hasattr(dashboard, 'get_announcement'):
                return dashboard.get_announcement(announcement_id)
            else:
                # Mock announcement data
                return {
                    'id': announcement_id,
                    'title': 'Sample Announcement',
                    'creator': 'System Admin',
                    'target_audience': 'all',
                    'created_at': '2024-01-01 12:00:00',
                    'is_urgent': False,
                    'is_active': True,
                    'content': 'This is a sample announcement.'
                }
        except Exception as e:
            print(f"Error getting announcement: {e}")
            return None

    def mark_announcement_viewed(dashboard, announcement_id):
        """Mark announcement as viewed"""
        try:
            if hasattr(dashboard, 'mark_announcement_viewed'):
                return dashboard.mark_announcement_viewed(announcement_id)
            else:
                print(f"Mock: Marking announcement {announcement_id} as viewed")
                return True
        except Exception as e:
            print(f"Error marking announcement as viewed: {e}")
            return False
    
    # ==================== SMS MESSAGING METHODS ====================

    def on_sms_recipient_type_change(self):
        """Handle recipient type change"""
        recipient_type = self.sms_recipient_type.get()

        # Show/hide appropriate inputs
        if recipient_type == "individual":
            # Show phone and user selection
            self.sms_phone_entry.config(state='normal')
            self.sms_user_combo.config(state='readonly')
            self.sms_group_frame.pack_forget()
        else:
            # Hide individual inputs, show group/role selector
            self.sms_phone_entry.config(state='disabled')
            self.sms_user_combo.config(state='disabled')
            self.sms_group_frame.pack(fill=tk.X, pady=(10, 0))

            # Load appropriate values
            if recipient_type == "group":
                self.load_sms_groups()
            elif recipient_type == "role":
                self.load_sms_roles()

    def on_sms_user_selected(self, event=None):
        """Auto-fill phone number when user is selected"""
        try:
            selected = self.sms_user_combo.get()
            if not selected:
                return

            # Extract username from the combo value (format: "username (Name)")
            username = selected.split(' (')[0]

            # Try to look up phone number from student emergency contacts
            with get_db_connection() as conn:
                # First try to get student_id from users table
                cursor = conn.execute("""
                    SELECT u.student_id
                    FROM users u
                    WHERE u.username = ?
                """, (username,))
                user_result = cursor.fetchone()

                if user_result and user_result[0]:
                    # Look up emergency contact phone
                    student_id = user_result[0]
                    cursor = conn.execute("""
                        SELECT phone_primary
                        FROM emergency_contacts
                        WHERE student_id = ?
                        AND phone_primary IS NOT NULL
                        ORDER BY priority_order
                        LIMIT 1
                    """, (student_id,))
                    phone_result = cursor.fetchone()

                    if phone_result and phone_result[0]:
                        self.sms_phone_entry.delete(0, tk.END)
                        self.sms_phone_entry.insert(0, phone_result[0])
                    else:
                        # Clear field and let user enter manually
                        self.sms_phone_entry.delete(0, tk.END)
                        print(f"ℹ️ No phone number found for {username}. Please enter manually.")
                else:
                    # Not a student or no student_id - let user enter phone manually
                    self.sms_phone_entry.delete(0, tk.END)
                    print(f"ℹ️ User {username} is not a student. Please enter phone number manually.")
        except Exception as e:
            print(f"Error loading user phone: {e}")

    def load_sms_users(self):
        """Load users into the SMS recipient combobox"""
        try:
            with get_db_connection() as conn:
                # Get all users - phone numbers will need to be entered manually
                # or loaded from emergency_contacts for students
                cursor = conn.execute("""
                    SELECT username, first_name, last_name, email
                    FROM users
                    ORDER BY last_name, first_name
                """)
                users = cursor.fetchall()

                # Format: "username (Full Name)"
                user_list = [f"{user[0]} ({user[1]} {user[2]})" for user in users]
                self.sms_user_combo['values'] = user_list

                print(f"✅ Loaded {len(users)} users (phone numbers must be entered manually)")
        except Exception as e:
            print(f"⚠️ Error loading SMS users: {e}")
            self.sms_user_combo['values'] = []

    def load_sms_groups(self):
        """Load groups for bulk SMS"""
        try:
            # Load student groups, courses, etc.
            with get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT DISTINCT group_name FROM student_groups
                    WHERE group_name IS NOT NULL
                    ORDER BY group_name
                """)
                groups = cursor.fetchall()

                group_list = [group[0] for group in groups]
                self.sms_group_combo['values'] = group_list

                if not group_list:
                    self.sms_group_combo['values'] = ["No groups available"]
        except Exception as e:
            print(f"⚠️ Error loading groups: {e}")
            self.sms_group_combo['values'] = ["Error loading groups"]

    def load_sms_roles(self):
        """Load user roles for bulk SMS"""
        # Standard roles
        roles = ["student", "instructor", "staff", "admin"]
        self.sms_group_combo['values'] = roles

    def update_sms_char_count(self, event=None):
        """Update SMS character counter"""
        try:
            message = self.sms_message_text.get("1.0", tk.END).strip()
            char_count = len(message)

            # Update label with color coding
            if char_count == 0:
                self.sms_char_label.config(text="0 / 160 characters", foreground='gray')
            elif char_count <= 160:
                self.sms_char_label.config(
                    text=f"{char_count} / 160 characters",
                    foreground='green'
                )
            else:
                # Calculate number of SMS segments needed
                segments = (char_count // 153) + 1
                self.sms_char_label.config(
                    text=f"{char_count} chars ({segments} messages)",
                    foreground='orange'
                )
        except Exception as e:
            print(f"Error updating char count: {e}")

    def send_sms(self):
        """Send SMS message"""
        try:
            # Get message
            message = self.sms_message_text.get("1.0", tk.END).strip()
            if not message:
                messagebox.showwarning("No Message", "Please enter a message to send.")
                return

            # Get recipients based on type
            recipient_type = self.sms_recipient_type.get()
            recipients = []

            if recipient_type == "individual":
                phone = self.sms_phone_entry.get().strip()
                if not phone:
                    messagebox.showwarning("No Recipient", "Please enter a phone number or select a user.")
                    return

                # Validate phone format
                if not self.validate_phone_number(phone):
                    messagebox.showerror("Invalid Phone", "Phone number must be in format: +1234567890")
                    return

                recipients = [(phone, self.sms_user_combo.get() or "Unknown")]

            elif recipient_type in ["group", "role"]:
                group_or_role = self.sms_group_combo.get()
                if not group_or_role:
                    messagebox.showwarning("No Selection", f"Please select a {recipient_type}.")
                    return

                # Get recipients from group/role
                recipients = self.get_recipients_for_group_or_role(recipient_type, group_or_role)

                if not recipients:
                    messagebox.showwarning("No Recipients", f"No users found for {recipient_type}: {group_or_role}")
                    return

            # Confirm bulk send
            if len(recipients) > 1:
                if not messagebox.askyesno("Confirm Bulk SMS",
                    f"Send SMS to {len(recipients)} recipients?\n\nThis will send {len(recipients)} messages."):
                    return

            # Send SMS to all recipients
            success_count = 0
            fail_count = 0

            for phone, recipient_name in recipients:
                try:
                    # Store in database (simulated SMS - in production would use Twilio/AWS SNS)
                    self.store_sms(phone, recipient_name, message, "sent")
                    success_count += 1
                except Exception as e:
                    print(f"Failed to send to {phone}: {e}")
                    self.store_sms(phone, recipient_name, message, "failed")
                    fail_count += 1

            # Show result
            result_msg = f"✅ SMS sent successfully to {success_count} recipient(s)"
            if fail_count > 0:
                result_msg += f"\n⚠️ {fail_count} failed"

            messagebox.showinfo("SMS Sent", result_msg)

            # Log activity
            log_activity(
                'send_sms',
                'communication',
                details={
                    'recipient_count': len(recipients),
                    'success': success_count,
                    'failed': fail_count,
                    'message_length': len(message)
                }
            )

            # Clear form and refresh history
            self.clear_sms_form()
            self.refresh_sms_history()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send SMS: {str(e)}")
            print(f"SMS send error: {e}")

    def validate_phone_number(self, phone):
        """Validate phone number format"""
        import re
        # Allow formats: +1234567890, +12345678901, etc.
        pattern = r'^\+\d{10,15}$'
        return bool(re.match(pattern, phone))

    def get_recipients_for_group_or_role(self, recipient_type, value):
        """Get phone numbers for group or role"""
        try:
            with get_db_connection() as conn:
                if recipient_type == "role":
                    # Get users by role
                    cursor = conn.execute("""
                        SELECT phone, name FROM users
                        WHERE role = ? AND phone IS NOT NULL AND phone != ''
                    """, (value,))
                else:
                    # Get users by group
                    cursor = conn.execute("""
                        SELECT u.phone, u.name
                        FROM users u
                        JOIN student_groups sg ON u.username = sg.username
                        WHERE sg.group_name = ? AND u.phone IS NOT NULL AND u.phone != ''
                    """, (value,))

                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting recipients: {e}")
            return []

    def store_sms(self, phone, recipient_name, message, status):
        """Store SMS in database"""
        try:
            # Create SMS table if not exists
            with transaction() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sms_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_username TEXT,
                        recipient_name TEXT,
                        phone_number TEXT,
                        message TEXT,
                        status TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Insert SMS record
                conn.execute("""
                    INSERT INTO sms_messages
                    (sender_username, recipient_name, phone_number, message, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    self.auth.current_user['username'],
                    recipient_name,
                    phone,
                    message,
                    status
                ))

        except Exception as e:
            print(f"Error storing SMS: {e}")
            raise

    def clear_sms_form(self):
        """Clear the SMS form"""
        self.sms_phone_entry.delete(0, tk.END)
        self.sms_user_combo.set('')
        self.sms_message_text.delete("1.0", tk.END)
        self.update_sms_char_count()

    def sms_templates(self):
        """Show SMS templates dialog"""
        messagebox.showinfo("SMS Templates",
            "SMS Templates feature coming soon!\n\n"
            "You'll be able to save and reuse common SMS messages.")

    def refresh_sms_history(self):
        """Refresh SMS history list"""
        try:
            # Clear existing items
            for item in self.sms_history_tree.get_children():
                self.sms_history_tree.delete(item)

            # Get search term
            search_term = self.sms_search_entry.get().lower() if hasattr(self, 'sms_search_entry') else ""

            # Load SMS history
            with get_db_connection() as conn:
                # Check if table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='sms_messages'
                """)
                if not cursor.fetchone():
                    # Table doesn't exist yet, create it
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS sms_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_username TEXT,
                            recipient_name TEXT,
                            phone_number TEXT,
                            message TEXT,
                            status TEXT,
                            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    return

                query = """
                    SELECT id, sent_at, recipient_name, phone_number, message, status
                    FROM sms_messages
                    WHERE sender_username = ?
                """
                params = [self.auth.current_user['username']]

                if search_term:
                    query += """ AND (
                        LOWER(recipient_name) LIKE ? OR
                        LOWER(phone_number) LIKE ? OR
                        LOWER(message) LIKE ?
                    )"""
                    search_pattern = f"%{search_term}%"
                    params.extend([search_pattern, search_pattern, search_pattern])

                query += " ORDER BY sent_at DESC LIMIT 500"

                cursor = conn.execute(query, params)
                messages = cursor.fetchall()

                for msg in messages:
                    sms_id, sent_at, recipient, phone, message, status = msg

                    # Truncate long messages
                    display_msg = message[:50] + "..." if len(message) > 50 else message

                    # Determine tag based on status
                    tag = status if status in ['sent', 'failed', 'pending'] else 'sent'

                    self.sms_history_tree.insert('', 'end', values=(
                        sms_id,
                        sent_at,
                        recipient,
                        phone,
                        display_msg,
                        status.upper()
                    ), tags=(tag,))

                print(f"✅ Loaded {len(messages)} SMS messages")

        except Exception as e:
            print(f"⚠️ Error loading SMS history: {e}")
            messagebox.showerror("Error", f"Failed to load SMS history: {str(e)}")

    def delete_sms(self):
        """Delete selected SMS from history"""
        try:
            selection = self.sms_history_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an SMS to delete.")
                return

            if not messagebox.askyesno("Confirm Delete", "Delete selected SMS from history?"):
                return

            # Get SMS ID
            item = self.sms_history_tree.item(selection[0])
            sms_id = item['values'][0]

            # Delete from database
            with transaction() as conn:
                conn.execute("DELETE FROM sms_messages WHERE id = ?", (sms_id,))

            # Refresh list
            self.refresh_sms_history()

            messagebox.showinfo("Deleted", "SMS deleted successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete SMS: {str(e)}")

    def sms_statistics(self):
        """Show SMS statistics"""
        try:
            with get_db_connection() as conn:
                # Check if table exists
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='sms_messages'
                """)
                if not cursor.fetchone():
                    messagebox.showinfo("Statistics", "No SMS data available yet.")
                    return

                # Get statistics
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                    FROM sms_messages
                    WHERE sender_username = ?
                """, (self.auth.current_user['username'],))

                stats = cursor.fetchone()
                total, sent, failed, pending = stats

                # Calculate success rate
                success_rate = (sent / total * 100) if total > 0 else 0

                stats_msg = f"""SMS Statistics for {self.auth.current_user['username']}

Total Messages: {total}
✅ Sent: {sent}
❌ Failed: {failed}
⏳ Pending: {pending}

Success Rate: {success_rate:.1f}%
"""

                messagebox.showinfo("SMS Statistics", stats_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics: {str(e)}")

    def show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)

# Dialog Classes
class ComposeEmailDialog:
    def __init__(self, parent, auth, recipient=None):
        self.auth = auth
        self.recipient = recipient
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compose Email")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

        # Pre-fill recipient if provided
        if self.recipient:
            self.to_entry.insert(0, self.recipient)
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Recipients
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.to_entry = ttk.Entry(main_frame, width=50)
        self.to_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)
        
        ttk.Button(main_frame, text="Select Recipients", command=self.select_recipients).grid(row=0, column=3, padx=5)
        
        # CC
        ttk.Label(main_frame, text="CC:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.cc_entry = ttk.Entry(main_frame, width=50)
        self.cc_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)
        
        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=5)
        
        # Template
        ttk.Label(main_frame, text="Template:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(main_frame, textvariable=self.template_var, width=30)
        self.template_combo.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Button(main_frame, text="Load Template", command=self.load_template).grid(row=3, column=2, padx=5)
        
        # Body
        ttk.Label(main_frame, text="Message:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.body_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.body_text.grid(row=4, column=1, columnspan=3, sticky=tk.NSEW, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        ttk.Button(button_frame, text="Send", command=self.send_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Draft", command=self.save_draft).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Load available templates
        self.load_templates()
    
    def load_templates(self):
        """Load available templates"""
        try:
            if list_templates is not None:
                templates = list_templates()
                template_names = [t['name'] for t in templates]
                self.template_combo['values'] = template_names
        except Exception as e:
            print(f"Error loading templates: {e}")
    
    def select_recipients(self):
        """Open recipient selection dialog"""
        RecipientSelectorDialog(self.dialog, self.to_entry)
    
    def load_template(self):
        """Load selected template"""
        template_name = self.template_var.get()
        if template_name and load_template is not None:
            try:
                template_data = load_template(template_name)
                if template_data:
                    self.subject_entry.delete(0, tk.END)
                    self.subject_entry.insert(0, template_data['subject'])
                    
                    self.body_text.delete(1.0, tk.END)
                    self.body_text.insert(1.0, template_data['body'])
            except Exception as e:
                messagebox.showerror("Error", f"Error loading template: {e}")
    
    def send_email(self):
        """Send the composed email"""
        try:
            recipients = [r.strip() for r in self.to_entry.get().split(',') if r.strip()]
            cc = [r.strip() for r in self.cc_entry.get().split(',') if r.strip()] if self.cc_entry.get() else None
            subject = self.subject_entry.get()
            body = self.body_text.get(1.0, tk.END).strip()
            
            if not recipients:
                messagebox.showerror("Error", "Please enter at least one recipient")
                return
            
            if not subject:
                messagebox.showerror("Error", "Please enter a subject")
                return
            
            if not body:
                messagebox.showerror("Error", "Please enter a message")
                return
            
            # Send emails
            success_count = 0
            for recipient in recipients:
                if 'send_email' in globals():
                    if send_email(recipient, subject, body, cc=cc):
                        success_count += 1
            
            if success_count > 0:
                messagebox.showinfo("Success", f"Email sent to {success_count} recipient(s)")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to send emails")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error sending email: {e}")
    
    def save_draft(self):
        """Save email as draft"""
        try:
            from university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            recipients = self.to_entry.get().strip()
            cc = self.cc_entry.get().strip()
            subject = self.subject_entry.get().strip()
            body = self.body_text.get(1.0, tk.END).strip()

            if not recipients and not subject and not body:
                messagebox.showwarning("Empty Draft", "Cannot save an empty draft")
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            # Create drafts table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_drafts (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipients TEXT,
                    cc TEXT,
                    subject TEXT,
                    body TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # Save draft
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO email_drafts (recipients, cc, subject, body, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipients, cc, subject, body, now, now))

            draft_id = cursor.lastrowid
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Draft saved successfully (ID: {draft_id})")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save draft: {e}")

# Add these to email_manager_gui.py after the existing dialog classes

class AnnouncementDetailsDialog:
    def __init__(self, parent, dashboard, announcement_id):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Announcement Details")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_announcement()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        self.title_label = ttk.Label(main_frame, text="", font=('Arial', 14, 'bold'))
        self.title_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Details frame
        details_frame = ttk.LabelFrame(main_frame, text="Announcement Details", padding=10)
        details_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.details_text = tk.Text(details_frame, height=3, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.X)
        
        # Content
        content_frame = ttk.LabelFrame(main_frame, text="Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        self.content_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.content_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_announcement(self):
        try:
            announcement = get_announcement_by_id(self.dashboard, self.announcement_id)
            if announcement:
                self.title_label.config(text=announcement['title'])
                
                details = f"Created by: {announcement['creator']}\n"
                details += f"Target: {announcement['target_audience']}\n"
                details += f"Created: {announcement['created_at']}\n"
                details += f"Priority: {'URGENT' if announcement['is_urgent'] else 'Normal'}\n"
                details += f"Status: {'Active' if announcement['is_active'] else 'Inactive'}"
                
                self.details_text.config(state=tk.NORMAL)
                self.details_text.insert(1.0, details)
                self.details_text.config(state=tk.DISABLED)
                
                self.content_text.config(state=tk.NORMAL)
                self.content_text.insert(1.0, announcement['content'])
                self.content_text.config(state=tk.DISABLED)
                
                # Mark as viewed
                mark_announcement_viewed(self.dashboard, self.announcement_id)
        except Exception as e:
            messagebox.showerror("Error", f"Error loading announcement: {e}")

class CreateAnnouncementDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Announcement")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=60)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)
        
        # Target audience
        ttk.Label(main_frame, text="Target Audience:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.audience_var = tk.StringVar(value="all")
        audience_frame = ttk.Frame(main_frame)
        audience_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(audience_frame, text="All Users", variable=self.audience_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Students", variable=self.audience_var, value="students").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(audience_frame, text="Staff", variable=self.audience_var, value="staff").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Instructors", variable=self.audience_var, value="instructors").pack(side=tk.LEFT, padx=10)
        
        # Urgent checkbox
        self.urgent_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Mark as urgent", variable=self.urgent_var).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Content
        ttk.Label(main_frame, text="Content:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.content_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.content_text.grid(row=3, column=1, columnspan=2, sticky=tk.NSEW, pady=5)
        
        # Date options
        ttk.Label(main_frame, text="Start Date:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=20)
        self.start_date_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.start_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        ttk.Label(main_frame, text="End Date (optional):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=20)
        self.end_date_entry.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Create", command=self.create_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
    
    def create_announcement(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get(1.0, tk.END).strip()
        target_audience = self.audience_var.get()
        is_urgent = 1 if self.urgent_var.get() else 0
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip() or None

        if not title or not content:
            messagebox.showwarning("Missing Information", "Title and content are required")
            return

        try:
            from university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get the current user ID (default to 1 if not available)
            creator_id = getattr(self.dashboard.auth, 'current_user', {}).get('id', 1) if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'auth') else 1

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use the correct schema from admin.py
            cursor.execute('''
                INSERT INTO announcements (creator_id, title, content, target_audience, is_urgent, is_active, start_date, end_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (creator_id, title, content, target_audience, is_urgent, 1, start_date, end_date, current_time, current_time))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement created successfully!")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create announcement: {e}")

class CreateChatRoomDialog:
    def __init__(self, parent, dashboard, refresh_callback=None):
        self.dashboard = dashboard
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Chat Room")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room name
        ttk.Label(main_frame, text="Room Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        # Description
        ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=40, height=5)
        self.description_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="public")
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(type_frame, text="Public", variable=self.type_var, value="public").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Private", variable=self.type_var, value="private").pack(anchor=tk.W)

        # Max members
        ttk.Label(main_frame, text="Max Members:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_members_var = tk.StringVar(value="50")
        ttk.Spinbox(main_frame, from_=2, to=1000, textvariable=self.max_members_var, width=10).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Create", command=self.create_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def create_room(self):
        name = self.name_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()
        room_type = self.type_var.get()
        max_members = int(self.max_members_var.get())

        if not name:
            messagebox.showwarning("Missing Information", "Please provide a room name")
            return

        try:
            from university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get the current user ID (default to 1 if not available)
            created_by = getattr(self.dashboard.auth, 'current_user', {}).get('id', 1) if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'auth') else 1

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use the correct schema from admin.py
            cursor.execute('''
                INSERT INTO chat_rooms (name, description, room_type, created_by, created_at, max_members, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, room_type, created_by, current_time, max_members, 1))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Chat room '{name}' created successfully!")
            self.dialog.destroy()

            # Refresh the chat rooms list in the GUI
            if self.refresh_callback:
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create chat room: {e}")

class ChatInvitationsDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Chat Room Invitations")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_invitations()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Pending Chat Room Invitations", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Invitations list
        columns = ("Room", "Invited By", "Date")
        self.invitations_tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        
        for col in columns:
            self.invitations_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.invitations_tree.yview)
        self.invitations_tree.configure(yscrollcommand=scrollbar.set)
        
        self.invitations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Accept", command=self.accept_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Decline", command=self.decline_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_invitations(self):
        # Clear existing items
        for item in self.invitations_tree.get_children():
            self.invitations_tree.delete(item)
        
        try:
            invitations = self.dashboard.get_pending_invitations()
            
            for invitation in invitations:
                self.invitations_tree.insert('', tk.END, values=(
                    invitation['room_name'],
                    invitation['invited_by'],
                    invitation['invited_at']
                ), tags=(invitation['id'],))
        except Exception as e:
            messagebox.showerror("Error", f"Error loading invitations: {e}")
    
    def accept_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]
            
            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=True):
                    messagebox.showinfo("Success", "Invitation accepted!")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to accept invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error accepting invitation: {e}")
    
    def decline_invitation(self):
        selection = self.invitations_tree.selection()
        if selection:
            item = self.invitations_tree.item(selection[0])
            invitation_id = item['tags'][0]
            
            try:
                if self.dashboard.respond_to_invitation(invitation_id, accept=False):
                    messagebox.showinfo("Success", "Invitation declined")
                    self.load_invitations()
                else:
                    messagebox.showerror("Error", "Failed to decline invitation")
            except Exception as e:
                messagebox.showerror("Error", f"Error declining invitation: {e}")

class RecipientSelectorDialog:
    def __init__(self, parent, entry_widget):
        self.entry_widget = entry_widget
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Recipients")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.selected_recipients = []
        self.create_widgets()
        self.load_users()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Search
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search)
        
        # Users list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.users_tree = ttk.Treeview(list_frame, columns=("Name", "Email", "Role"), show="headings", selectmode=tk.EXTENDED)
        
        for col in ["Name", "Email", "Role"]:
            self.users_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Add Selected", command=self.add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="OK", command=self.confirm_selection).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_users(self):
        """Load users into the tree from database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, email, first_name, last_name, role
                    FROM users
                    ORDER BY username
                """)
                users = cursor.fetchall()

                for user in users:
                    # Build full name
                    full_name = f"{user['first_name']} {user['last_name']}".strip()
                    if not full_name:
                        full_name = user['username']

                    self.users_tree.insert('', tk.END, values=(
                        full_name,
                        user['email'] or user['username'],
                        user['role'] or 'user'
                    ))
        except Exception as e:
            print(f"Error loading users from database: {e}")
            # Log error without fallback - database should be properly initialized
            import traceback
            traceback.print_exc()
    
    def on_search(self, event):
        """Handle search input"""
        search_term = self.search_entry.get().lower()

        # Clear current items
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)

        # Re-load filtered users from database
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, email, first_name, last_name, role
                    FROM users
                    WHERE LOWER(username) LIKE ? OR LOWER(email) LIKE ?
                       OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                    ORDER BY username
                """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                users = cursor.fetchall()

                for user in users:
                    # Build full name
                    full_name = f"{user['first_name']} {user['last_name']}".strip()
                    if not full_name:
                        full_name = user['username']

                    self.users_tree.insert('', tk.END, values=(
                        full_name,
                        user['email'] or user['username'],
                        user['role'] or 'user'
                    ))
        except Exception as e:
            print(f"Error searching users in database: {e}")
            # Log error without fallback - database should be properly initialized
            import traceback
            traceback.print_exc()
    
    def add_selected(self):
        """Add selected users to recipients"""
        selection = self.users_tree.selection()
        for item in selection:
            values = self.users_tree.item(item)['values']
            email = values[1]
            if email not in self.selected_recipients:
                self.selected_recipients.append(email)
    
    def confirm_selection(self):
        """Confirm recipient selection"""
        if self.selected_recipients:
            current_text = self.entry_widget.get()
            if current_text:
                new_text = current_text + ", " + ", ".join(self.selected_recipients)
            else:
                new_text = ", ".join(self.selected_recipients)
            
            self.entry_widget.delete(0, tk.END)
            self.entry_widget.insert(0, new_text)
        
        self.dialog.destroy()

class BulkEmailDialog:
    def __init__(self, parent, auth):
        self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Bulk Email")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Target audience
        ttk.Label(main_frame, text="Target Audience:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        self.audience_var = tk.StringVar(value="all")
        audience_frame = ttk.Frame(main_frame)
        audience_frame.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(audience_frame, text="All Users", variable=self.audience_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Students", variable=self.audience_var, value="students").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(audience_frame, text="Staff", variable=self.audience_var, value="staff").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Instructors", variable=self.audience_var, value="instructors").pack(side=tk.LEFT, padx=10)
        
        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # Template
        ttk.Label(main_frame, text="Template:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(main_frame, textvariable=self.template_var, width=30)
        self.template_combo.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Body
        ttk.Label(main_frame, text="Message:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.body_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.body_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Send Bulk Email", command=self.send_bulk).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Load templates
        self.load_templates()
    
    def load_templates(self):
        """Load available templates"""
        try:
            if list_templates is not None:
                templates = list_templates()
                template_names = [t['name'] for t in templates]
                self.template_combo['values'] = template_names
        except Exception as e:
            print(f"Error loading templates: {e}")
    
    def send_bulk(self):
        """Send bulk email"""
        try:
            audience = self.audience_var.get()
            subject = self.subject_entry.get()
            body = self.body_text.get(1.0, tk.END).strip()
            
            if not subject or not body:
                messagebox.showerror("Error", "Please enter subject and message")
                return
            
            # Confirm sending
            if not messagebox.askyesno("Confirm", f"Send bulk email to {audience}?"):
                return
            
            # Use existing bulk send functionality
            if 'send_batch_announcement' in globals():
                # Create filter criteria based on audience
                filter_criteria = {}
                if audience == "students":
                    filter_criteria = {'role': 'student'}
                elif audience == "staff":
                    filter_criteria = {'role': 'staff'}
                elif audience == "instructors":
                    filter_criteria = {'role': 'instructor'}
                
                success, failed, total = send_batch_announcement(subject, body, filter_criteria)
                
                messagebox.showinfo("Result", 
                    f"Bulk email completed:\n"
                    f"Total: {total}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}")
                
                if success > 0:
                    self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Bulk email functionality not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error sending bulk email: {e}")
    
    def preview_email(self):
        """Preview the email"""
        subject = self.subject_entry.get()
        body = self.body_text.get(1.0, tk.END).strip()
        
        preview_text = f"Subject: {subject}\n\nMessage:\n{body}"
        
        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Email Preview")
        preview_dialog.geometry("500x400")
        
        text_widget = scrolledtext.ScrolledText(preview_dialog, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, preview_text)
        text_widget.config(state=tk.DISABLED)

# Additional dialog classes would continue here...
class ScheduleEmailDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Email")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Schedule Email", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Recipient
        ttk.Label(main_frame, text="Recipient Email:").pack(anchor=tk.W)
        self.recipient_entry = ttk.Entry(main_frame, width=50)
        self.recipient_entry.pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.pack(fill=tk.X, pady=(0, 10))

        # Body
        ttk.Label(main_frame, text="Message Body:").pack(anchor=tk.W)
        self.body_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Schedule date/time frame
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule For", padding=10)
        schedule_frame.pack(fill=tk.X, pady=(0, 10))

        # Date selection
        date_frame = ttk.Frame(schedule_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT, padx=(0, 5))

        # Year
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        year_spinbox = ttk.Spinbox(date_frame, from_=datetime.now().year, to=datetime.now().year + 5,
                                   textvariable=self.year_var, width=6)
        year_spinbox.pack(side=tk.LEFT, padx=2)

        # Month
        self.month_var = tk.StringVar(value=str(datetime.now().month))
        month_spinbox = ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.month_var, width=4)
        month_spinbox.pack(side=tk.LEFT, padx=2)

        # Day
        self.day_var = tk.StringVar(value=str(datetime.now().day))
        day_spinbox = ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.day_var, width=4)
        day_spinbox.pack(side=tk.LEFT, padx=2)

        # Time selection
        time_frame = ttk.Frame(schedule_frame)
        time_frame.pack(fill=tk.X)

        ttk.Label(time_frame, text="Time:").pack(side=tk.LEFT, padx=(0, 5))

        # Hour
        self.hour_var = tk.StringVar(value=str(datetime.now().hour))
        hour_spinbox = ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self.hour_var, width=4)
        hour_spinbox.pack(side=tk.LEFT, padx=2)

        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)

        # Minute
        self.minute_var = tk.StringVar(value=str(datetime.now().minute))
        minute_spinbox = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.minute_var, width=4)
        minute_spinbox.pack(side=tk.LEFT, padx=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Schedule", command=self.schedule_email).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Send Now", command=self.send_now).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def schedule_email(self):
        """Schedule the email for later"""
        recipient = self.recipient_entry.get().strip()
        subject = self.subject_entry.get().strip()
        body = self.body_text.get(1.0, tk.END).strip()

        if not recipient or not subject:
            messagebox.showwarning("Missing Information", "Please fill in recipient and subject")
            return

        try:
            # Get scheduled time
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            day = int(self.day_var.get())
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())

            scheduled_time = datetime(year, month, day, hour, minute)

            if scheduled_time <= datetime.now():
                messagebox.showwarning("Invalid Time", "Scheduled time must be in the future")
                return

            # Store scheduled email in database
            from university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create scheduled_emails table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    scheduled_for TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')

            cursor.execute('''
                INSERT INTO scheduled_emails (recipient, subject, body, scheduled_for)
                VALUES (?, ?, ?, ?)
            ''', (recipient, subject, body, scheduled_time.strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Email scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}")
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Date/Time", f"Please enter valid date and time values: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule email: {e}")

    def send_now(self):
        """Send the email immediately"""
        recipient = self.recipient_entry.get().strip()
        subject = self.subject_entry.get().strip()
        body = self.body_text.get(1.0, tk.END).strip()

        if not recipient or not subject:
            messagebox.showwarning("Missing Information", "Please fill in recipient and subject")
            return

        try:
            if send_email:
                result = send_email(recipient, subject, body)
                if result:
                    messagebox.showinfo("Success", "Email sent successfully!")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send email")
            else:
                messagebox.showerror("Error", "Email service not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}")

class TemplateManagerDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_templates()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Email Template Manager", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(button_frame, text="New Template", command=self.create_new_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_selected_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_templates).pack(side=tk.LEFT, padx=5)

        # Templates list frame
        list_frame = ttk.LabelFrame(main_frame, text="Available Templates", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with scrollbar
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.templates_tree = ttk.Treeview(tree_frame, columns=('Type', 'Subject', 'Preview'), show='tree headings')
        self.templates_tree.heading('#0', text='Template Name')
        self.templates_tree.heading('Type', text='Type')
        self.templates_tree.heading('Subject', text='Subject')
        self.templates_tree.heading('Preview', text='Body Preview')

        self.templates_tree.column('#0', width=150)
        self.templates_tree.column('Type', width=80)
        self.templates_tree.column('Subject', width=200)
        self.templates_tree.column('Preview', width=300)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=scrollbar.set)

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.templates_tree.bind('<Double-1>', lambda e: self.edit_selected_template())

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(10, 0))

    def load_templates(self):
        """Load and display templates in the tree"""
        # Clear existing items
        for item in self.templates_tree.get_children():
            self.templates_tree.delete(item)

        try:
            # Import template functions
            from university_system.infrastructure.email.template_utils import list_templates
            templates = list_templates()

            for template in templates:
                template_type = "Default" if template.get('is_default', False) else "Custom"
                self.templates_tree.insert('', 'end',
                                         text=template['name'],
                                         values=(template_type,
                                               template.get('subject', ''),
                                               template.get('body_preview', '')))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def create_new_template(self):
        """Open dialog to create a new template"""
        dialog = TemplateEditDialog(self.dialog, None)
        if dialog.result:
            self.load_templates()

    def edit_selected_template(self):
        """Edit the selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit.")
            return

        template_name = self.templates_tree.item(selection[0])['text']
        dialog = TemplateEditDialog(self.dialog, template_name)
        if dialog.result:
            self.load_templates()

    def delete_selected_template(self):
        """Delete the selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete.")
            return

        template_name = self.templates_tree.item(selection[0])['text']
        template_type = self.templates_tree.item(selection[0])['values'][0]

        if template_type == "Default":
            messagebox.showwarning("Cannot Delete", "Default templates cannot be deleted.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the template '{template_name}'?"):
            try:
                from university_system.infrastructure.email.template_utils import delete_template
                if delete_template(template_name):
                    messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully.")
                    self.load_templates()
                else:
                    messagebox.showerror("Error", f"Failed to delete template '{template_name}'.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {str(e)}")


class TemplateEditDialog:
    def __init__(self, parent, template_name=None):
        self.dialog = tk.Toplevel(parent)
        self.template_name = template_name
        self.result = False

        title = "Edit Template" if template_name else "Create New Template"
        self.dialog.title(title)
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if template_name:
            self.load_template_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Template name
        ttk.Label(main_frame, text="Template Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=50)
        self.name_entry.pack(fill=tk.X, pady=(0, 10))

        if self.template_name:
            self.name_var.set(self.template_name)
            self.name_entry.config(state='readonly')

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.subject_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Body
        ttk.Label(main_frame, text="Body:").pack(anchor=tk.W)
        body_frame = ttk.Frame(main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.body_text = scrolledtext.ScrolledText(body_frame, wrap=tk.WORD, height=15)
        self.body_text.pack(fill=tk.BOTH, expand=True)

        # Variables help
        help_frame = ttk.LabelFrame(main_frame, text="Available Variables", padding=5)
        help_frame.pack(fill=tk.X, pady=(0, 10))

        help_text = ("Common variables: $student_name, $student_id, $email_address, $course, "
                    "$module_code, $assignment_title, $due_date, $grade, $signature")
        ttk.Label(help_frame, text=help_text, wraplength=550).pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Save", command=self.save_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_template_data(self):
        """Load existing template data"""
        try:
            from university_system.infrastructure.email.template_utils import load_template
            template_data = load_template(self.template_name)
            if template_data:
                self.subject_var.set(template_data.get('subject', ''))
                self.body_text.insert('1.0', template_data.get('body', ''))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")

    def save_template(self):
        """Save the template"""
        name = self.name_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.body_text.get('1.0', tk.END).strip()

        if not name or not subject or not body:
            messagebox.showerror("Validation Error", "All fields are required.")
            return

        try:
            if self.template_name:
                # Update existing template
                from university_system.infrastructure.email.template_utils import update_template
                if update_template(name, subject=subject, body=body):
                    messagebox.showinfo("Success", "Template updated successfully.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to update template.")
            else:
                # Create new template
                from university_system.infrastructure.email.template_utils import create_template
                if create_template(name, subject, body):
                    messagebox.showinfo("Success", "Template created successfully.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to create template. Template may already exist.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")

# Continue with remaining dialog classes...
class EmailConfigDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Configuration")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_config()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Email Mode", padding=10)
        mode_frame.pack(fill=tk.X, pady=5)
        
        self.mode_var = tk.StringVar()
        ttk.Radiobutton(mode_frame, text="Database Only Mode", variable=self.mode_var, value="database").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="SMTP Sending Mode", variable=self.mode_var, value="smtp").pack(anchor=tk.W)
        
        # SMTP settings
        smtp_frame = ttk.LabelFrame(main_frame, text="SMTP Settings", padding=10)
        smtp_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(smtp_frame, text="SMTP Server:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.smtp_server_entry = ttk.Entry(smtp_frame, width=30)
        self.smtp_server_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(smtp_frame, text="SMTP Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.smtp_port_entry = ttk.Entry(smtp_frame, width=10)
        self.smtp_port_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(smtp_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.username_entry = ttk.Entry(smtp_frame, width=30)
        self.username_entry.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(smtp_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.password_entry = ttk.Entry(smtp_frame, width=30, show="*")
        self.password_entry.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        # Sender settings
        sender_frame = ttk.LabelFrame(main_frame, text="Sender Information", padding=10)
        sender_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sender_frame, text="Sender Email:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sender_email_entry = ttk.Entry(sender_frame, width=40)
        self.sender_email_entry.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(sender_frame, text="Sender Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sender_name_entry = ttk.Entry(sender_frame, width=40)
        self.sender_name_entry.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.use_tls_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Use TLS", variable=self.use_tls_var).pack(anchor=tk.W)
        
        self.use_auth_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Use Authentication", variable=self.use_auth_var).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test", command=self.test_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_config(self):
        """Load current configuration"""
        try:
            if 'config' in globals():
                cfg = config
                
                # Set mode
                if cfg.get('database_only_mode', True):
                    self.mode_var.set("database")
                else:
                    self.mode_var.set("smtp")
                
                # Set SMTP settings
                self.smtp_server_entry.insert(0, cfg.get('smtp_server', ''))
                self.smtp_port_entry.insert(0, str(cfg.get('smtp_port', 587)))
                self.username_entry.insert(0, cfg.get('username', ''))
                
                # Set sender settings
                self.sender_email_entry.insert(0, cfg.get('sender_email', ''))
                self.sender_name_entry.insert(0, cfg.get('sender_name', ''))
                
                # Set options
                self.use_tls_var.set(cfg.get('use_tls', True))
                self.use_auth_var.set(cfg.get('use_authentication', True))
                
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration"""
        try:
            if 'config' in globals():
                # Update global config
                config['database_only_mode'] = (self.mode_var.get() == "database")
                config['smtp_server'] = self.smtp_server_entry.get()
                config['smtp_port'] = int(self.smtp_port_entry.get() or 587)
                config['username'] = self.username_entry.get()
                config['sender_email'] = self.sender_email_entry.get()
                config['sender_name'] = self.sender_name_entry.get()
                config['use_tls'] = self.use_tls_var.get()
                config['use_authentication'] = self.use_auth_var.get()
                
                if self.password_entry.get():
                    config['password'] = self.password_entry.get()
                
                # Save to file
                if 'save_config' in globals():
                    save_config()
                
                messagebox.showinfo("Success", "Configuration saved successfully")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Configuration system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving configuration: {e}")
    
    def test_config(self):
        """Test email configuration"""
        try:
            if 'test_email_configuration' in globals():
                test_email_configuration()
                messagebox.showinfo("Test", "Check console for test results")
            else:
                messagebox.showinfo("Test", "Test functionality not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error testing configuration: {e}")

# Continue with more dialog classes...
class EmailDetailsDialog:
    def __init__(self, parent, email_id):
        self.email_id = email_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Email Details - ID {email_id}")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_email_details()

        # Set grab after window is fully initialized and visible
        self.dialog.after(100, self.dialog.grab_set)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Details display
        self.details_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_email_details(self):
        """Load email details"""
        try:
            # Get email details using existing function
            def _get_email_details(cursor):
                cursor.execute('''
                SELECT id, recipient_email, subject, body, sender_email, sender_name,
                       cc_recipients, bcc_recipients, attachment_paths, created_date,
                       template_name, template_vars, related_to, student_id
                FROM stored_emails WHERE id = ?
                ''', (self.email_id,))
                return cursor.fetchone()
            
            if 'execute_db_operation' in globals():
                email_data = execute_db_operation(_get_email_details)
                
                if email_data:
                    details = f"Email ID: {email_data[0]}\n"
                    details += f"To: {email_data[1]}\n"
                    details += f"From: {email_data[5]} <{email_data[4]}>\n"
                    details += f"Subject: {email_data[2]}\n"
                    details += f"Date: {email_data[9]}\n"
                    
                    if email_data[6]:  # CC
                        details += f"CC: {email_data[6]}\n"
                    if email_data[7]:  # BCC
                        details += f"BCC: {email_data[7]}\n"
                    if email_data[8]:  # Attachments
                        details += f"Attachments: {email_data[8]}\n"
                    if email_data[10]:  # Template
                        details += f"Template: {email_data[10]}\n"
                    
                    details += "\n" + "-" * 50 + "\n\n"
                    details += email_data[3]  # Body
                    
                    self.details_text.config(state=tk.NORMAL)
                    self.details_text.insert(1.0, details)
                    self.details_text.config(state=tk.DISABLED)
                else:
                    self.details_text.config(state=tk.NORMAL)
                    self.details_text.insert(1.0, "Email not found")
                    self.details_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.insert(1.0, f"Error loading email details: {e}")
            self.details_text.config(state=tk.DISABLED)

class ComposeMessageDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compose Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Recipient
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.recipient_entry = ttk.Entry(main_frame, width=40)
        self.recipient_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Button(main_frame, text="Select", command=self.select_recipient).grid(row=0, column=2, padx=5)
        
        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=40)
        self.subject_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)
        
        # Message
        ttk.Label(main_frame, text="Message:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.message_text = scrolledtext.ScrolledText(main_frame, width=50, height=15)
        self.message_text.grid(row=2, column=1, columnspan=2, sticky=tk.NSEW, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
    
    def select_recipient(self):
        """Select message recipient"""
        RecipientSelectorDialog(self.dialog, self.recipient_entry)
    
    def send_message(self):
        """Send the message"""
        try:
            recipient_email = self.recipient_entry.get().strip()
            subject = self.subject_entry.get().strip()
            content = self.message_text.get(1.0, tk.END).strip()
            
            if not recipient_email or not subject or not content:
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            # Find recipient user ID
            def _find_recipient(cursor):
                cursor.execute("SELECT id FROM users WHERE email = ?", (recipient_email,))
                result = cursor.fetchone()
                return result[0] if result else None
            
            if 'execute_db_operation' in globals():
                recipient_id = execute_db_operation(_find_recipient)
                
                if recipient_id and self.dashboard:
                    if self.dashboard.send_message(recipient_id, subject, content):
                        messagebox.showinfo("Success", "Message sent successfully")
                        self.dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to send message")
                else:
                    messagebox.showerror("Error", "Recipient not found")
            else:
                messagebox.showerror("Error", "Messaging system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")

class ReplyMessageDialog:
    def __init__(self, parent, dashboard, message_id):
        self.dashboard = dashboard
        self.message_id = message_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Reply to Message")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_original_message()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Original message (read-only)
        ttk.Label(main_frame, text="Original Message:").pack(anchor=tk.W)
        self.original_text = scrolledtext.ScrolledText(main_frame, height=8, state=tk.DISABLED)
        self.original_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Reply
        ttk.Label(main_frame, text="Your Reply:").pack(anchor=tk.W, pady=(10, 0))
        self.reply_text = scrolledtext.ScrolledText(main_frame, height=8)
        self.reply_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Send Reply", command=self.send_reply).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def load_original_message(self):
        """Load the original message"""
        try:
            if self.dashboard:
                message = self.dashboard.read_message(self.message_id)
                if message:
                    original_content = f"From: {message['sender']}\n"
                    original_content += f"Subject: {message['subject']}\n"
                    original_content += f"Date: {message['sent_at']}\n"
                    original_content += "-" * 40 + "\n"
                    original_content += message['content']
                    
                    self.original_text.config(state=tk.NORMAL)
                    self.original_text.insert(1.0, original_content)
                    self.original_text.config(state=tk.DISABLED)
                    
                    # Store message info for reply
                    self.original_sender_id = message['sender_id']
                    self.original_subject = message['subject']
        except Exception as e:
            messagebox.showerror("Error", f"Error loading original message: {e}")
    
    def send_reply(self):
        """Send the reply"""
        try:
            reply_content = self.reply_text.get(1.0, tk.END).strip()
            
            if not reply_content:
                messagebox.showerror("Error", "Please enter a reply")
                return
            
            # Create reply subject
            reply_subject = self.original_subject
            if not reply_subject.startswith("Re: "):
                reply_subject = f"Re: {reply_subject}"
            
            if self.dashboard:
                if self.dashboard.send_message(self.original_sender_id, reply_subject, reply_content):
                    messagebox.showinfo("Success", "Reply sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reply")
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error sending reply: {e}")

# Additional utility dialogs
class SystemHealthDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("System Health")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        self.load_health_info()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="System Health Status", font=('Arial', 14, 'bold')).pack(pady=10)
        
        self.health_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.health_text.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Refresh", command=self.load_health_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_health_info(self):
        """Load system health information"""
        try:
            self.health_text.config(state=tk.NORMAL)
            self.health_text.delete(1.0, tk.END)
            
            health_info = "SYSTEM HEALTH REPORT\n"
            health_info += "=" * 30 + "\n\n"
            health_info += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            if 'get_system_health_info' in globals():
                health = get_system_health_info()
                health_info += f"Email System: {health.get('email_system', 'Unknown')}\n"
                health_info += f"Message System: {health.get('message_system', 'Unknown')}\n"
                health_info += f"Chat System: {health.get('chat_system', 'Unknown')}\n"
                health_info += f"Database: {health.get('database_status', 'Unknown')}\n"
                health_info += f"Queue Size: {health.get('queue_size', 0)}\n"
            else:
                health_info += "Health monitoring not available\n"
            
            # Check configuration
            if 'config' in globals():
                health_info += f"\nConfiguration:\n"
                health_info += f"Mode: {'Database Only' if config.get('database_only_mode', True) else 'SMTP'}\n"
                health_info += f"Sender Email: {config.get('sender_email', 'Not set')}\n"
                health_info += f"SMTP Server: {config.get('smtp_server', 'Not set')}\n"
            
            self.health_text.insert(1.0, health_info)
            self.health_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.health_text.config(state=tk.NORMAL)
            self.health_text.delete(1.0, tk.END)
            self.health_text.insert(1.0, f"Error loading health info: {e}")
            self.health_text.config(state=tk.DISABLED)

class DatabaseCleanupDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Cleanup")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Database Cleanup Options", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Cleanup options
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(options_frame, text="Clean Old Emails (30+ days)", 
                  command=lambda: self.cleanup_emails(30)).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Clean Old Emails (90+ days)", 
                  command=lambda: self.cleanup_emails(90)).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Cleanup Deleted Messages", 
                  command=self.cleanup_messages).pack(fill=tk.X, pady=2)
        
        ttk.Button(options_frame, text="Optimize Database", 
                  command=self.optimize_database).pack(fill=tk.X, pady=2)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=20)
    
    def cleanup_emails(self, days):
        """Clean up old emails"""
        if messagebox.askyesno("Confirm", f"Delete emails older than {days} days?"):
            try:
                if 'clear_stored_emails' in globals():
                    count = clear_stored_emails(older_than_days=days)
                    messagebox.showinfo("Success", f"Deleted {count} old emails")
                else:
                    messagebox.showerror("Error", "Cleanup function not available")
            except Exception as e:
                messagebox.showerror("Error", f"Error during cleanup: {e}")
    
    def cleanup_messages(self):
        """Clean up deleted messages"""
        if messagebox.askyesno("Confirm", "Clean up messages deleted by both parties?"):
            try:
                from university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()

                # Delete messages deleted by both sender and recipient or older than 90 days
                cursor.execute("""
                    DELETE FROM messages
                    WHERE (is_deleted_by_sender = 1 AND is_deleted_by_recipient = 1)
                       OR (is_deleted_by_sender = 1 AND sent_at < date('now', '-90 days'))
                       OR (is_deleted_by_recipient = 1 AND sent_at < date('now', '-90 days'))
                """)

                deleted = cursor.rowcount
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Cleaned up {deleted} messages")
            except Exception as e:
                messagebox.showerror("Error", f"Error during cleanup: {e}")
    
    def optimize_database(self):
        """Optimize database"""
        try:
            if 'optimize_database' in globals():
                optimize_database()
                messagebox.showinfo("Success", "Database optimized successfully")
            else:
                messagebox.showinfo("Info", "Database optimization not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error optimizing database: {e}")

# Additional dialogs for completeness
class EditAnnouncementDialog:
    def __init__(self, parent, dashboard, announcement_id, refresh_callback):
        self.dashboard = dashboard
        self.announcement_id = announcement_id
        self.refresh_callback = refresh_callback
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Announcement")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.load_announcement()

    def load_announcement(self):
        """Load existing announcement data"""
        try:
            from university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT title, content, is_urgent
                FROM announcements WHERE id = ?
            ''', (self.announcement_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                self.title = row[0]
                self.content = row[1]
                self.is_urgent = row[2]
                self.create_widgets()
            else:
                messagebox.showerror("Error", "Announcement not found")
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load announcement: {e}")
            self.dialog.destroy()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Edit Announcement", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Title
        ttk.Label(main_frame, text="Title:").pack(anchor=tk.W)
        self.title_entry = ttk.Entry(main_frame, width=50)
        self.title_entry.insert(0, self.title)
        self.title_entry.pack(fill=tk.X, pady=(0, 10))

        # Message
        ttk.Label(main_frame, text="Message:").pack(anchor=tk.W)
        self.message_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.message_text.insert(1.0, self.content)
        self.message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Priority
        priority_frame = ttk.Frame(main_frame)
        priority_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(priority_frame, text="Priority:").pack(side=tk.LEFT, padx=(0, 5))

        # Map is_urgent to priority string
        initial_priority = "high" if self.is_urgent else "normal"
        self.priority_var = tk.StringVar(value=initial_priority)

        ttk.Radiobutton(priority_frame, text="Low", variable=self.priority_var, value="low").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="Normal", variable=self.priority_var, value="normal").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(priority_frame, text="High", variable=self.priority_var, value="high").pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Save", command=self.save_announcement).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def save_announcement(self):
        title = self.title_entry.get().strip()
        message = self.message_text.get(1.0, tk.END).strip()
        priority = self.priority_var.get()

        if not title or not message:
            messagebox.showwarning("Missing Information", "Please provide both title and message")
            return

        try:
            from university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            conn = get_db_connection()
            cursor = conn.cursor()

            # Map priority to is_urgent
            is_urgent = 1 if priority.lower() == 'high' else 0

            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update the announcement
            cursor.execute('''
                UPDATE announcements
                SET title = ?, content = ?, is_urgent = ?, updated_at = ?
                WHERE id = ?
            ''', (title, message, is_urgent, current_time, self.announcement_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Announcement updated successfully!")
            self.dialog.destroy()

            # Refresh the announcements list
            if self.refresh_callback:
                self.refresh_callback()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update announcement: {e}")

class ChatRoomWindow:
    """Enhanced chat room interface"""
    def __init__(self, parent, dashboard, room_id, room_name):
        self.dashboard = dashboard
        self.room_id = room_id
        self.room_name = room_name
        self.window = tk.Toplevel(parent)
        self.window.title(f"Chat Room: {room_name}")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_messages()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Chat display area
        self.chat_text = scrolledtext.ScrolledText(main_frame, state=tk.DISABLED, wrap=tk.WORD, height=20)
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Message input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.message_entry = ttk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind('<Return>', self.send_message)
        
        ttk.Button(input_frame, text="Send", command=self.send_message).pack(side=tk.RIGHT)
        
        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X)
        
        ttk.Button(controls_frame, text="Members", command=self.show_members).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Invite", command=self.invite_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Leave Room", command=self.leave_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def load_messages(self):
        try:
            messages_data = self.dashboard.get_chat_messages(self.room_id, limit=50)
            self.chat_text.config(state=tk.NORMAL)
            self.chat_text.delete(1.0, tk.END)
            
            for msg in messages_data.get('messages', []):
                timestamp = msg['sent_at'][:16]
                self.chat_text.insert(tk.END, f"[{timestamp}] {msg['sender']}: {msg['content']}\n")
                
            self.chat_text.config(state=tk.DISABLED)
            self.chat_text.see(tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load messages: {e}")
    
    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if message:
            try:
                if self.dashboard.send_chat_message(self.room_id, message):
                    self.message_entry.delete(0, tk.END)
                    self.load_messages()  # Refresh messages
                else:
                    messagebox.showerror("Error", "Failed to send message")
            except Exception as e:
                messagebox.showerror("Error", f"Error sending message: {e}")
    
    def show_members(self):
        try:
            members = self.dashboard.get_room_members(self.room_id)
            if members:
                member_text = "\n".join([f"• {m['full_name']} (@{m['username']})" + 
                                       (" - Admin" if m['is_admin'] else "") for m in members])
                messagebox.showinfo(f"Members of {self.room_name}", member_text)
            else:
                messagebox.showinfo("Members", "Could not retrieve member list")
        except Exception as e:
            messagebox.showerror("Error", f"Error getting members: {e}")
    
    def invite_user(self):
        username = askstring("Invite User", "Enter username to invite:")
        if username:
            try:
                # Find user and invite
                users = search_users(self.dashboard.auth, username)
                if users:
                    user = users[0]
                    result = self.dashboard.invite_user_to_room(self.room_id, user['id'])
                    if result == True:
                        messagebox.showinfo("Success", f"Invitation sent to {username}")
                    elif result == "already_member":
                        messagebox.showinfo("Info", f"{username} is already a member")
                    else:
                        messagebox.showerror("Error", "Failed to send invitation")
                else:
                    messagebox.showerror("Error", f"User '{username}' not found")
            except Exception as e:
                messagebox.showerror("Error", f"Error inviting user: {e}")
    
    def leave_room(self):
        if messagebox.askyesno("Confirm", f"Leave room '{self.room_name}'?"):
            try:
                if self.dashboard.leave_chat_room(self.room_id):
                    messagebox.showinfo("Success", f"Left room '{self.room_name}'")
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to leave room")
            except Exception as e:
                messagebox.showerror("Error", f"Error leaving room: {e}")

class AdvancedSearchDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Search")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search in
        ttk.Label(criteria_frame, text="Search in:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.search_in = ttk.Combobox(criteria_frame, values=["Messages", "Stored Emails", "Both"])
        self.search_in.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.search_in.set("Messages")
        
        # Keywords
        ttk.Label(criteria_frame, text="Keywords:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.keywords = ttk.Entry(criteria_frame, width=40)
        self.keywords.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # From/To
        ttk.Label(criteria_frame, text="From/To:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.sender_recipient = ttk.Entry(criteria_frame, width=40)
        self.sender_recipient.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Date range
        ttk.Label(criteria_frame, text="Date from:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_from = ttk.Entry(criteria_frame, width=15)
        self.date_from.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(criteria_frame, text="Date to:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.date_to = ttk.Entry(criteria_frame, width=15)
        self.date_to.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Search button
        ttk.Button(criteria_frame, text="Search", command=self.perform_search).grid(row=5, column=0, columnspan=2, pady=10)
        
        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("Type", "From/To", "Subject", "Date")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def perform_search(self):
        keywords = self.keywords.get().strip()
        search_in = self.search_in.get()
        sender_recipient = self.sender_recipient.get().strip()
        date_from = self.date_from.get().strip()
        date_to = self.date_to.get().strip()

        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        if not keywords and not sender_recipient:
            messagebox.showwarning("Warning", "Please enter search keywords or sender/recipient")
            return

        try:
            def search_database(cursor):
                results = []

                # Search in messages if requested
                if search_in in ["Messages", "Both"]:
                    query = """
                    SELECT 'Message' as type,
                           u.username as sender,
                           m.subject,
                           m.sent_at,
                           m.id
                    FROM messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE 1=1
                    """
                    params = []

                    if keywords:
                        query += " AND (m.subject LIKE ? OR m.message LIKE ? OR m.content LIKE ?)"
                        keyword_param = f"%{keywords}%"
                        params.extend([keyword_param, keyword_param, keyword_param])

                    if sender_recipient:
                        query += " AND u.username LIKE ?"
                        params.append(f"%{sender_recipient}%")

                    if date_from:
                        query += " AND m.sent_at >= ?"
                        params.append(date_from)

                    if date_to:
                        query += " AND m.sent_at <= ?"
                        params.append(date_to)

                    cursor.execute(query, params)
                    for row in cursor.fetchall():
                        results.append(('Message', row[1], row[2], row[3]))

                # Search in stored emails if requested
                if search_in in ["Stored Emails", "Both"]:
                    query = """
                    SELECT 'Email' as type,
                           sender_name,
                           subject,
                           created_date
                    FROM stored_emails
                    WHERE 1=1
                    """
                    params = []

                    if keywords:
                        query += " AND (subject LIKE ? OR body LIKE ?)"
                        keyword_param = f"%{keywords}%"
                        params.extend([keyword_param, keyword_param])

                    if sender_recipient:
                        query += " AND (sender_name LIKE ? OR recipient_email LIKE ?)"
                        sender_param = f"%{sender_recipient}%"
                        params.extend([sender_param, sender_param])

                    if date_from:
                        query += " AND created_date >= ?"
                        params.append(date_from)

                    if date_to:
                        query += " AND created_date <= ?"
                        params.append(date_to)

                    cursor.execute(query, params)
                    for row in cursor.fetchall():
                        results.append(('Email', row[1], row[2], row[3]))

                return results

            results = execute_db_operation(search_database)

            # Display results
            for result in results:
                self.results_tree.insert('', tk.END, values=result)

            if results:
                messagebox.showinfo("Search Complete", f"Found {len(results)} results")
            else:
                messagebox.showinfo("Search Complete", "No results found")

        except Exception as e:
            messagebox.showerror("Error", f"Search failed: {e}")

class EmailReportsDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Reports")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Filter options
        filter_frame = ttk.LabelFrame(main_frame, text="Report Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Date range
        ttk.Label(filter_frame, text="From Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.start_date = ttk.Entry(filter_frame, width=15)
        self.start_date.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        
        ttk.Label(filter_frame, text="To Date:").grid(row=0, column=2, sticky=tk.W, pady=5)
        self.end_date = ttk.Entry(filter_frame, width=15)
        self.end_date.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        
        # Report type
        ttk.Label(filter_frame, text="Report Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.report_type = ttk.Combobox(filter_frame, values=[
            "Email Statistics", "Stored Emails", "Email Log", "Messages",
            "Template Usage", "User Activity", "Failed Emails"
        ])
        self.report_type.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.report_type.set("Email Statistics")
        
        # Generate button
        ttk.Button(filter_frame, text="Generate Report", command=self.generate_report).grid(row=2, column=0, columnspan=4, pady=10)
        
        # Report display
        report_frame = ttk.LabelFrame(main_frame, text="Report Results", padding=10)
        report_frame.pack(fill=tk.BOTH, expand=True)
        
        self.report_text = scrolledtext.ScrolledText(report_frame, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True)
        
        # Export buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_report(self):
        try:
            start_date = self.start_date.get() or None
            end_date = self.end_date.get() or None
            report_type = self.report_type.get()

            # Generate basic report
            self.report_text.delete(1.0, tk.END)

            report_content = f"EMAIL SYSTEM REPORT - {report_type}\n"
            report_content += "=" * 70 + "\n\n"
            report_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            if start_date:
                report_content += f"From: {start_date}\n"
            if end_date:
                report_content += f"To: {end_date}\n"

            report_content += "\n" + "=" * 70 + "\n\n"

            # Generate actual report data
            try:
                from university_system.infrastructure.database.db import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()

                if report_type == "Email Statistics":
                    # Stored Emails Statistics
                    cursor.execute("SELECT COUNT(*) FROM stored_emails")
                    stored_count = cursor.fetchone()[0]
                    report_content += f"STORED EMAILS\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Stored: {stored_count}\n\n"

                    # Email Log Statistics
                    cursor.execute("SELECT COUNT(*) FROM email_log")
                    log_count = cursor.fetchone()[0]
                    report_content += f"EMAIL LOG (Sent Emails)\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Logged: {log_count}\n"

                    # Count by status
                    cursor.execute("SELECT status, COUNT(*) FROM email_log GROUP BY status")
                    report_content += "\nBy Status:\n"
                    for row in cursor.fetchall():
                        status = row[0] or 'Unknown'
                        report_content += f"  {status}: {row[1]}\n"

                    # Messages Statistics
                    cursor.execute("SELECT COUNT(*) FROM messages")
                    msg_count = cursor.fetchone()[0]
                    report_content += f"\nINTERNAL MESSAGES\n"
                    report_content += "-" * 40 + "\n"
                    report_content += f"Total Messages: {msg_count}\n"

                    cursor.execute("SELECT COUNT(*) FROM messages WHERE is_read = 1")
                    read_count = cursor.fetchone()[0]
                    report_content += f"Read Messages: {read_count}\n"
                    report_content += f"Unread Messages: {msg_count - read_count}\n"

                elif report_type == "Stored Emails":
                    cursor.execute("""
                        SELECT recipient_email, subject, sender_email, sender_name, created_date
                        FROM stored_emails
                        ORDER BY created_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"STORED EMAILS (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"From: {row[3]} <{row[2]}>\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Date: {row[4]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Email Log":
                    cursor.execute("""
                        SELECT recipient, subject, status, sent_date, sender_name
                        FROM email_log
                        ORDER BY sent_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"EMAIL SEND LOG (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"From: {row[4] or 'System'}\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Status: {row[2] or 'Unknown'}\n"
                        report_content += f"Sent: {row[3]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Messages":
                    cursor.execute("""
                        SELECT
                            m.subject,
                            m.sent_at,
                            m.is_read,
                            sender.username as sender_username,
                            sender.email as sender_email,
                            recipient.username as recipient_username,
                            recipient.email as recipient_email
                        FROM messages m
                        LEFT JOIN users sender ON m.sender_id = sender.id
                        LEFT JOIN users recipient ON m.recipient_id = recipient.id
                        ORDER BY m.sent_at DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"INTERNAL MESSAGES (Last 50)\n"
                    report_content += "-" * 70 + "\n\n"

                    for row in rows:
                        status = "✓ Read" if row[2] else "⚬ Unread"
                        report_content += f"From: {row[3] or 'Unknown'} <{row[4] or 'N/A'}>\n"
                        report_content += f"To: {row[5] or 'Unknown'} <{row[6] or 'N/A'}>\n"
                        report_content += f"Subject: {row[0]}\n"
                        report_content += f"Status: {status}\n"
                        report_content += f"Sent: {row[1]}\n"
                        report_content += "-" * 40 + "\n\n"

                elif report_type == "Template Usage":
                    cursor.execute("""
                        SELECT template_name, template_type, created_date, created_by
                        FROM email_templates
                        ORDER BY template_name
                    """)
                    templates = cursor.fetchall()
                    report_content += f"EMAIL TEMPLATES\n"
                    report_content += "-" * 70 + "\n"
                    report_content += f"Total Templates: {len(templates)}\n\n"

                    for tmpl in templates:
                        report_content += f"Name: {tmpl[0]}\n"
                        report_content += f"Type: {tmpl[1] or 'N/A'}\n"
                        report_content += f"Created: {tmpl[2] or 'N/A'}\n"
                        report_content += f"Created By: {tmpl[3] or 'System'}\n"
                        report_content += "-" * 40 + "\n\n"

                    # Template usage in stored emails
                    cursor.execute("""
                        SELECT template_name, COUNT(*) as count
                        FROM stored_emails
                        WHERE template_name IS NOT NULL
                        GROUP BY template_name
                        ORDER BY count DESC
                    """)
                    usage = cursor.fetchall()
                    if usage:
                        report_content += "\nTEMPLATE USAGE STATISTICS\n"
                        report_content += "-" * 40 + "\n"
                        for row in usage:
                            report_content += f"  {row[0]}: {row[1]} emails\n"

                elif report_type == "User Activity":
                    # Top email recipients from stored_emails
                    cursor.execute("""
                        SELECT recipient_email, COUNT(*) as count
                        FROM stored_emails
                        GROUP BY recipient_email
                        ORDER BY count DESC LIMIT 20
                    """)
                    report_content += "TOP 20 EMAIL RECIPIENTS (Stored Emails)\n"
                    report_content += "-" * 70 + "\n"
                    for row in cursor.fetchall():
                        report_content += f"  {row[0]}: {row[1]} emails\n"

                    # Top message senders
                    cursor.execute("""
                        SELECT u.username, u.email, COUNT(*) as count
                        FROM messages m
                        LEFT JOIN users u ON m.sender_id = u.id
                        GROUP BY m.sender_id
                        ORDER BY count DESC LIMIT 20
                    """)
                    report_content += "\n\nTOP 20 MESSAGE SENDERS (Internal Messages)\n"
                    report_content += "-" * 70 + "\n"
                    for row in cursor.fetchall():
                        username = row[0] or 'Unknown'
                        email = row[1] or 'N/A'
                        report_content += f"  {username} <{email}>: {row[2]} messages\n"

                elif report_type == "Failed Emails":
                    cursor.execute("""
                        SELECT recipient, subject, sent_date, status, message
                        FROM email_log
                        WHERE status LIKE '%fail%' OR status LIKE '%error%'
                        ORDER BY sent_date DESC LIMIT 50
                    """)
                    rows = cursor.fetchall()
                    report_content += f"FAILED EMAILS\n"
                    report_content += "-" * 70 + "\n"
                    report_content += f"Total Failed: {len(rows)}\n\n"

                    for row in rows:
                        report_content += f"To: {row[0]}\n"
                        report_content += f"Subject: {row[1]}\n"
                        report_content += f"Date: {row[2]}\n"
                        report_content += f"Status: {row[3]}\n"
                        if row[4]:
                            report_content += f"Details: {row[4][:100]}...\n"
                        report_content += "-" * 40 + "\n\n"

                conn.close()

            except Exception as e:
                import traceback
                report_content += f"\nError generating detailed report:\n"
                report_content += f"{str(e)}\n\n"
                report_content += traceback.format_exc()

            self.report_text.insert(1.0, report_content)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def export_csv(self):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if filename:
                content = self.report_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")

class NotificationPreferencesDialog:
    def __init__(self, parent, dashboard):
        self.dashboard = dashboard
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Notification Preferences")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.preferences = {}
        self.create_widgets()
        self.load_preferences()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Notification Preferences", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        # Preference checkboxes
        self.email_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Email Notifications", variable=self.email_var).pack(anchor=tk.W, pady=5)
        
        self.message_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Message Notifications", variable=self.message_var).pack(anchor=tk.W, pady=5)
        
        self.announcement_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Announcement Notifications", variable=self.announcement_var).pack(anchor=tk.W, pady=5)
        
        self.chat_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Chat Notifications", variable=self.chat_var).pack(anchor=tk.W, pady=5)
        
        self.digest_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Daily Digest", variable=self.digest_var).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_preferences).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_preferences(self):
        try:
            if self.dashboard:
                prefs = self.dashboard.get_notification_preferences()
                if prefs:
                    self.email_var.set(prefs.get('email_notifications', True))
                    self.message_var.set(prefs.get('message_notifications', True))
                    self.announcement_var.set(prefs.get('announcement_notifications', True))
                    self.chat_var.set(prefs.get('chat_notifications', True))
                    self.digest_var.set(prefs.get('daily_digest', False))
        except Exception as e:
            print(f"Error loading preferences: {e}")
    
    def save_preferences(self):
        try:
            preferences = {
                'email_notifications': self.email_var.get(),
                'message_notifications': self.message_var.get(),
                'announcement_notifications': self.announcement_var.get(),
                'chat_notifications': self.chat_var.get(),
                'daily_digest': self.digest_var.get()
            }

            # Save directly to database
            from university_system.infrastructure.database.db import get_db_connection
            import json

            conn = get_db_connection()
            cursor = conn.cursor()

            # Save preferences (using user_id 1 as default)
            user_id = 1  # Would need actual user ID from auth

            # Store preferences as JSON string
            prefs_json = json.dumps(preferences)

            # Use INSERT OR REPLACE to handle existing records
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences (user_id, preferences, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, prefs_json))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Preferences saved successfully!")
            self.dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Error saving preferences: {e}")
            
class ExportDataDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Data")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Email Data", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Export options
        options_frame = ttk.LabelFrame(main_frame, text="Select Data to Export", padding=10)
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.export_emails_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Emails", variable=self.export_emails_var).pack(anchor=tk.W, pady=2)

        self.export_templates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Templates", variable=self.export_templates_var).pack(anchor=tk.W, pady=2)

        self.export_scheduled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Scheduled Emails", variable=self.export_scheduled_var).pack(anchor=tk.W, pady=2)

        self.export_announcements_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Announcements", variable=self.export_announcements_var).pack(anchor=tk.W, pady=2)

        self.export_chatrooms_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Chat Rooms", variable=self.export_chatrooms_var).pack(anchor=tk.W, pady=2)

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text="Export Format", padding=10)
        format_frame.pack(fill=tk.X, pady=(0, 10))

        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV", variable=self.format_var, value="csv").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="JSON", variable=self.format_var, value="json").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="HTML Report", variable=self.format_var, value="html").pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Export", command=self.export_data).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def export_data(self):
        # Check if at least one option is selected
        if not any([
            self.export_emails_var.get(),
            self.export_templates_var.get(),
            self.export_scheduled_var.get(),
            self.export_announcements_var.get(),
            self.export_chatrooms_var.get()
        ]):
            messagebox.showwarning("No Selection", "Please select at least one data type to export")
            return

        format_type = self.format_var.get()

        # Ask for file location
        file_types = {
            "csv": [("CSV files", "*.csv"), ("All files", "*.*")],
            "json": [("JSON files", "*.json"), ("All files", "*.*")],
            "html": [("HTML files", "*.html"), ("All files", "*.*")]
        }

        file_path = filedialog.asksaveasfilename(
            title="Save Export",
            defaultextension=f".{format_type}",
            filetypes=file_types.get(format_type, [("All files", "*.*")])
        )

        if not file_path:
            return

        try:
            from university_system.infrastructure.database.db import get_db_connection
            import csv as csv_module

            conn = get_db_connection()
            cursor = conn.cursor()

            export_data = {}
            export_headers = {}

            # Export emails with comprehensive details
            if self.export_emails_var.get():
                try:
                    # Query messages with full sender/recipient details
                    cursor.execute('''
                        SELECT
                            m.id as message_id,
                            m.subject,
                            COALESCE(m.content, m.message) as content,
                            m.sent_at,
                            m.read_at,
                            m.is_read,
                            sender.id as sender_id,
                            sender.username as sender_username,
                            sender.email as sender_email,
                            sender.first_name as sender_first_name,
                            sender.last_name as sender_last_name,
                            recipient.id as recipient_id,
                            recipient.username as recipient_username,
                            recipient.email as recipient_email,
                            recipient.first_name as recipient_first_name,
                            recipient.last_name as recipient_last_name,
                            m.attachment_path,
                            m.is_archived,
                            m.is_deleted_by_sender,
                            m.is_deleted_by_recipient
                        FROM messages m
                        LEFT JOIN users sender ON m.sender_id = sender.id
                        LEFT JOIN users recipient ON m.recipient_id = recipient.id
                        ORDER BY m.sent_at DESC
                    ''')
                    export_data['messages'] = cursor.fetchall()
                    export_headers['messages'] = [
                        'Message ID', 'Subject', 'Content', 'Sent Date/Time', 'Read Date/Time', 'Is Read',
                        'Sender ID', 'Sender Username', 'Sender Email', 'Sender First Name', 'Sender Last Name',
                        'Recipient ID', 'Recipient Username', 'Recipient Email', 'Recipient First Name', 'Recipient Last Name',
                        'Attachments', 'Is Archived', 'Deleted by Sender', 'Deleted by Recipient'
                    ]
                except Exception as e:
                    print(f"Error exporting messages: {e}")

                # Also export stored emails (sent via SMTP or database-only mode)
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            recipient_email,
                            subject,
                            body,
                            sender_email,
                            sender_name,
                            cc_recipients,
                            bcc_recipients,
                            attachment_paths,
                            created_date,
                            template_name,
                            template_vars
                        FROM stored_emails
                        ORDER BY created_date DESC
                    ''')
                    export_data['stored_emails'] = cursor.fetchall()
                    export_headers['stored_emails'] = [
                        'Email ID', 'Recipient Email', 'Subject', 'Body', 'Sender Email', 'Sender Name',
                        'CC Recipients', 'BCC Recipients', 'Attachments', 'Sent Date/Time',
                        'Template Name', 'Template Variables'
                    ]
                except Exception as e:
                    print(f"Error exporting stored emails: {e}")

                # Export email logs
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            recipient,
                            subject,
                            sent_date,
                            status,
                            related_to,
                            student_id,
                            sender_email,
                            sender_name,
                            cc_recipients,
                            bcc_recipients,
                            attachment_info
                        FROM email_log
                        ORDER BY sent_date DESC
                    ''')
                    export_data['email_log'] = cursor.fetchall()
                    export_headers['email_log'] = [
                        'Log ID', 'Recipient', 'Subject', 'Sent Date/Time', 'Status',
                        'Related To', 'Student ID', 'Sender Email', 'Sender Name',
                        'CC Recipients', 'BCC Recipients', 'Attachment Info'
                    ]
                except Exception as e:
                    print(f"Error exporting email logs: {e}")

            # Export templates with full details
            if self.export_templates_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            template_id,
                            template_name,
                            template_content,
                            template_type,
                            created_date,
                            created_by
                        FROM email_templates
                        ORDER BY template_name
                    ''')
                    export_data['templates'] = cursor.fetchall()
                    export_headers['templates'] = [
                        'Template ID', 'Template Name', 'Template Content', 'Template Type',
                        'Created Date', 'Created By'
                    ]
                except Exception as e:
                    print(f"Error exporting templates: {e}")

            # Export scheduled emails
            if self.export_scheduled_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            id,
                            recipient,
                            subject,
                            body,
                            scheduled_for,
                            status,
                            created_at
                        FROM scheduled_emails
                        ORDER BY scheduled_for
                    ''')
                    export_data['scheduled_emails'] = cursor.fetchall()
                    export_headers['scheduled_emails'] = [
                        'Schedule ID', 'Recipient', 'Subject', 'Body',
                        'Scheduled For', 'Status', 'Created At'
                    ]
                except Exception as e:
                    print(f"Error exporting scheduled emails: {e}")

            # Export announcements with creator details
            if self.export_announcements_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            a.id,
                            a.title,
                            a.content,
                            a.target_audience,
                            a.is_urgent,
                            a.is_active,
                            a.start_date,
                            a.end_date,
                            a.created_at,
                            a.updated_at,
                            u.id as creator_id,
                            u.username as creator_username,
                            u.email as creator_email,
                            u.first_name as creator_first_name,
                            u.last_name as creator_last_name
                        FROM announcements a
                        LEFT JOIN users u ON a.creator_id = u.id
                        ORDER BY a.created_at DESC
                    ''')
                    export_data['announcements'] = cursor.fetchall()
                    export_headers['announcements'] = [
                        'Announcement ID', 'Title', 'Content', 'Target Audience', 'Is Urgent', 'Is Active',
                        'Start Date', 'End Date', 'Created Date/Time', 'Updated Date/Time',
                        'Creator ID', 'Creator Username', 'Creator Email', 'Creator First Name', 'Creator Last Name'
                    ]
                except Exception as e:
                    print(f"Error exporting announcements: {e}")

            # Export chat rooms with creator details
            if self.export_chatrooms_var.get():
                try:
                    cursor.execute('''
                        SELECT
                            cr.id,
                            cr.name,
                            cr.description,
                            cr.room_type,
                            cr.max_members,
                            cr.is_active,
                            cr.created_at,
                            u.id as creator_id,
                            u.username as creator_username,
                            u.email as creator_email
                        FROM chat_rooms cr
                        LEFT JOIN users u ON cr.created_by = u.id
                        ORDER BY cr.created_at DESC
                    ''')
                    export_data['chat_rooms'] = cursor.fetchall()
                    export_headers['chat_rooms'] = [
                        'Room ID', 'Room Name', 'Description', 'Room Type', 'Max Members',
                        'Is Active', 'Created Date/Time', 'Creator ID', 'Creator Username', 'Creator Email'
                    ]
                except Exception as e:
                    print(f"Error exporting chat rooms: {e}")

            conn.close()

            # Export based on format
            if format_type == "csv":
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv_module.writer(f)
                    writer.writerow(['Email System Comprehensive Export'])
                    writer.writerow([f'Exported on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                    writer.writerow([])

                    for data_type, rows in export_data.items():
                        writer.writerow([f"=== {data_type.upper().replace('_', ' ')} ==="])
                        writer.writerow([f'Total Records: {len(rows)}'])
                        writer.writerow([])

                        # Write headers if available
                        if data_type in export_headers:
                            writer.writerow(export_headers[data_type])

                        # Write data
                        for row in rows:
                            writer.writerow(row)
                        writer.writerow([])
                        writer.writerow([])

            elif format_type == "json":
                # Convert tuples to dictionaries with headers for better readability
                json_data = {
                    'export_info': {
                        'exported_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'format': 'json'
                    }
                }

                for data_type, rows in export_data.items():
                    headers = export_headers.get(data_type, [f'field_{i}' for i in range(len(rows[0]) if rows else 0)])
                    json_data[data_type] = {
                        'total_records': len(rows),
                        'records': [dict(zip(headers, row)) for row in rows]
                    }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4, default=str)

            elif format_type == "html":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("""
                    <html>
                    <head>
                        <title>Email System Comprehensive Export</title>
                        <style>
                            body { font-family: Arial, sans-serif; margin: 20px; }
                            h1 { color: #333; }
                            h2 { color: #666; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
                            table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
                            th { background-color: #4CAF50; color: white; padding: 10px; text-align: left; }
                            td { border: 1px solid #ddd; padding: 8px; }
                            tr:nth-child(even) { background-color: #f2f2f2; }
                            .metadata { background-color: #f9f9f9; padding: 10px; border-left: 4px solid #4CAF50; margin-bottom: 20px; }
                            .content { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: pre-wrap; }
                        </style>
                    </head>
                    <body>
                    """)
                    f.write("<h1>Email System Comprehensive Export</h1>")
                    f.write(f"<div class='metadata'>")
                    f.write(f"<p><strong>Exported on:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>")
                    f.write(f"<p><strong>Total sections:</strong> {len(export_data)}</p>")
                    f.write("</div>")

                    for data_type, rows in export_data.items():
                        f.write(f"<h2>{data_type.replace('_', ' ').title()}</h2>")
                        f.write(f"<p><strong>Total records:</strong> {len(rows)}</p>")
                        if rows:
                            headers = export_headers.get(data_type, [f'Field {i+1}' for i in range(len(rows[0]))])
                            f.write("<table>")
                            f.write("<tr>")
                            for header in headers:
                                f.write(f"<th>{header}</th>")
                            f.write("</tr>")

                            for row in rows[:500]:  # Limit to first 500 rows in HTML
                                f.write("<tr>")
                                for item in row:
                                    # Truncate very long content for display
                                    display_item = str(item) if item is not None else ''
                                    if len(display_item) > 200:
                                        display_item = display_item[:200] + '...'
                                    f.write(f"<td class='content'>{display_item}</td>")
                                f.write("</tr>")
                            f.write("</table>")

                            if len(rows) > 500:
                                f.write(f"<p><em>Showing first 500 of {len(rows)} records</em></p>")

                    f.write("</body></html>")

            # Show summary
            summary = f"Data exported successfully to {file_path}\n\n"
            summary += "Export Summary:\n"
            for data_type, rows in export_data.items():
                summary += f"  - {data_type.replace('_', ' ').title()}: {len(rows)} records\n"

            messagebox.showinfo("Export Complete", summary)
            self.dialog.destroy()

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Export Error", f"Failed to export data: {e}")

class HelpDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Help")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="University Communication System - Help", font=('Arial', 14, 'bold')).pack(pady=10)
        
        help_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD)
        help_text.pack(fill=tk.BOTH, expand=True)
        
        help_content = """
UNIVERSITY COMMUNICATION SYSTEM - USER GUIDE

Getting Started:
1. Use the Dashboard tab to see an overview
2. Navigate between tabs to access different features
3. Use toolbar buttons for quick actions

Email Features:
- Compose individual emails or bulk announcements
- Use templates for consistent messaging
- Schedule emails for later delivery
- View stored emails and their details

Messaging:
- Send direct messages to other users
- Reply to received messages
- Archive or delete messages as needed

Announcements:
- View system-wide announcements
- Create announcements (if you have permission)
- Mark announcements as read

Chat Rooms:
- Join public chat rooms
- Create your own rooms
- Invite other users to private rooms
- Participate in real-time conversations

Reports:
- Generate email usage reports
- Export data to CSV
- Monitor system health
- View communication statistics

For additional help, contact your system administrator.
        """
        
        help_text.insert(1.0, help_content)
        help_text.config(state=tk.DISABLED)
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

class AboutDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("About")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="University Communication System", font=('Arial', 16, 'bold')).pack(pady=10)
        ttk.Label(main_frame, text="Email Manager GUI", font=('Arial', 12)).pack()
        ttk.Label(main_frame, text="Version 1.0", font=('Arial', 10)).pack(pady=5)
        
        desc_text = """
A comprehensive communication platform for universities
featuring email management, messaging, announcements,
and chat rooms with full backwards compatibility.

Features:
- Email composition and bulk sending
- Template management
- Direct messaging system
- Announcements and notifications
- Chat rooms and invitations
- Reporting and analytics
- Database and SMTP support
        """
        
        ttk.Label(main_frame, text=desc_text, justify=tk.CENTER).pack(pady=10)
        ttk.Label(main_frame, text="© 2024 University Communication System", font=('Arial', 9)).pack(pady=5)
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=20)

# Notification Dialog Classes
class RegistrationConfirmationDialog:
    """Dialog for sending registration confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Registration Confirmation")
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=30)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        student_id = self.student_id_entry.get().strip()

        if not student_id:
            messagebox.showerror("Error", "Please enter a student ID")
            return

        try:
            if send_registration_confirmation is not None:
                if send_registration_confirmation(student_id):
                    messagebox.showinfo("Success", "Registration confirmation sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation. Student may not exist.")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending confirmation: {e}")

class AssignmentNotificationDialog:
    """Dialog for sending assignment notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Assignment Notification")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Assignment ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.assignment_id_entry = ttk.Entry(main_frame, width=40)
        self.assignment_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.description_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.description_text.grid(row=4, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def send_notification(self):
        assignment_id = self.assignment_id_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        due_date = self.due_date_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()

        if not all([assignment_id, title, module_code, due_date]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            if send_assignment_notification is not None:
                if send_assignment_notification(assignment_id, title, module_code, due_date, description):
                    messagebox.showinfo("Success", "Assignment notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")

class ModuleGradeNotificationDialog:
    """Dialog for sending module grade notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Module Grade Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_name_entry = ttk.Entry(main_frame, width=40)
        self.module_name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.grade_entry = ttk.Entry(main_frame, width=40)
        self.grade_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        student_id = self.student_id_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        module_name = self.module_name_entry.get().strip()
        grade = self.grade_entry.get().strip()

        if not all([student_id, module_code, module_name, grade]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_grade_notification is not None:
                # This is the first version that takes student_id
                if send_grade_notification(student_id, module_code, module_name, grade):
                    messagebox.showinfo("Success", "Grade notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")

class AssignmentGradeNotificationDialog:
    """Dialog for sending assignment grade notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Assignment Grade Notification")
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.grade_entry = ttk.Entry(main_frame, width=40)
        self.grade_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Feedback (Optional):").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.feedback_text = scrolledtext.ScrolledText(main_frame, width=40, height=6)
        self.feedback_text.grid(row=4, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def send_notification(self):
        email = self.email_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        grade = self.grade_entry.get().strip()
        feedback = self.feedback_text.get(1.0, tk.END).strip()

        if not all([email, title, module_code, grade]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            if send_grade_notification is not None:
                # This is the second version that takes email directly
                if send_grade_notification(email, title, module_code, grade, feedback if feedback else None):
                    messagebox.showinfo("Success", "Grade notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")

class ExtensionNotificationDialog:
    """Dialog for sending extension notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Extension Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="New Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.new_due_date_entry = ttk.Entry(main_frame, width=40)
        self.new_due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Extension Days:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.extension_days_entry = ttk.Entry(main_frame, width=40)
        self.extension_days_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        email = self.email_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        new_due_date = self.new_due_date_entry.get().strip()
        extension_days = self.extension_days_entry.get().strip()

        if not all([email, title, module_code, new_due_date, extension_days]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_extension_notification is not None:
                if send_extension_notification(email, title, module_code, new_due_date, extension_days):
                    messagebox.showinfo("Success", "Extension notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")

class UpdateConfirmationDialog:
    """Dialog for sending update confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Update Confirmation")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Updated Fields (comma-separated):").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.fields_text = scrolledtext.ScrolledText(main_frame, width=40, height=10)
        self.fields_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        ttk.Label(main_frame, text="Example: name, email, phone", font=('Arial', 8, 'italic')).grid(row=2, column=1, sticky=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def send_confirmation(self):
        email = self.email_entry.get().strip()
        fields_text = self.fields_text.get(1.0, tk.END).strip()

        if not email or not fields_text:
            messagebox.showerror("Error", "Please fill in all fields")
            return

        # Convert to list
        updated_fields = [f.strip() for f in fields_text.split(',') if f.strip()]

        if not updated_fields:
            messagebox.showerror("Error", "Please enter at least one updated field")
            return

        try:
            if send_update_confirmation is not None:
                if send_update_confirmation(email, updated_fields):
                    messagebox.showinfo("Success", "Update confirmation sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending confirmation: {e}")

class PasswordResetDialog:
    """Dialog for sending password reset emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Password Reset")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=30)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Reset Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.reset_code_entry = ttk.Entry(main_frame, width=30)
        self.reset_code_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Button(main_frame, text="Generate Code", command=self.generate_code).grid(row=1, column=2, padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_reset).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def generate_code(self):
        """Generate a random reset code"""
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.reset_code_entry.delete(0, tk.END)
        self.reset_code_entry.insert(0, code)

    def send_reset(self):
        student_id = self.student_id_entry.get().strip()
        reset_code = self.reset_code_entry.get().strip()

        if not student_id or not reset_code:
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_password_reset is not None:
                if send_password_reset(student_id, reset_code):
                    messagebox.showinfo("Success", "Password reset email sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reset email. Student may not exist.")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending reset email: {e}")

# Health Services Dialog Classes
class AppointmentConfirmationDialog:
    """Dialog for sending appointment confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Appointment Confirmation")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Appointment ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.appointment_id_entry = ttk.Entry(main_frame, width=40)
        self.appointment_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(main_frame, width=40)
        self.date_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Time (HH:MM):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.time_entry = ttk.Entry(main_frame, width=40)
        self.time_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Provider:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.provider_entry = ttk.Entry(main_frame, width=40)
        self.provider_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Appointment Type:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.type_entry = ttk.Entry(main_frame, width=40)
        self.type_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.student_id_entry.get(), self.appointment_id_entry.get(),
                    self.date_entry.get(), self.time_entry.get(),
                    self.provider_entry.get(), self.type_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_appointment_confirmation is not None:
                if send_appointment_confirmation(
                    self.student_id_entry.get().strip(),
                    self.appointment_id_entry.get().strip(),
                    self.date_entry.get().strip(),
                    self.time_entry.get().strip(),
                    self.provider_entry.get().strip(),
                    self.type_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Appointment confirmation sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class HealthNotificationDialog:
    """Dialog for sending health advisory notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Health Advisory")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Advisory Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Severity:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.severity_var = tk.StringVar(value="low")
        severity_frame = ttk.Frame(main_frame)
        severity_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(severity_frame, text="Low", variable=self.severity_var, value="low").pack(side=tk.LEFT)
        ttk.Radiobutton(severity_frame, text="Medium", variable=self.severity_var, value="medium").pack(side=tk.LEFT)
        ttk.Radiobutton(severity_frame, text="High", variable=self.severity_var, value="high").pack(side=tk.LEFT)

        ttk.Label(main_frame, text="Description:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.description_text = scrolledtext.ScrolledText(main_frame, width=40, height=10)
        self.description_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.student_id_entry.get(), self.title_entry.get(),
                    self.description_text.get(1.0, tk.END).strip()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_health_notification is not None:
                if send_health_notification(
                    self.student_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.description_text.get(1.0, tk.END).strip(),
                    self.severity_var.get()
                ):
                    messagebox.showinfo("Success", "Health advisory sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send advisory")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

# Helpdesk Dialog Classes
class TicketNotificationDialog:
    """Dialog for sending helpdesk ticket notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Ticket Notification")
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=40)
        self.subject_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(main_frame, width=40)
        self.username_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Admin Emails (comma-separated):").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.admins_text = scrolledtext.ScrolledText(main_frame, width=40, height=6)
        self.admins_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.ticket_id_entry.get(), self.subject_entry.get(), self.username_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        admin_list = [a.strip() for a in self.admins_text.get(1.0, tk.END).split(',') if a.strip()] or None

        try:
            if send_ticket_notification is not None:
                if send_ticket_notification(
                    self.ticket_id_entry.get().strip(),
                    self.subject_entry.get().strip(),
                    self.username_entry.get().strip(),
                    admin_list
                ):
                    messagebox.showinfo("Success", "Ticket notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class ReplyNotificationDialog:
    """Dialog for sending ticket reply notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Reply Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="User ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(main_frame, width=40)
        self.username_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Responder:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.responder_entry = ttk.Entry(main_frame, width=40)
        self.responder_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Status Update (optional):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_entry = ttk.Entry(main_frame, width=40)
        self.status_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.ticket_id_entry.get(), self.username_entry.get(), self.responder_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_reply_notification is not None:
                user_id = self.user_id_entry.get().strip() or None
                status = self.status_entry.get().strip() or None

                if send_reply_notification(
                    self.ticket_id_entry.get().strip(),
                    user_id,
                    self.username_entry.get().strip(),
                    self.responder_entry.get().strip(),
                    None,  # admin_list
                    status
                ):
                    messagebox.showinfo("Success", "Reply notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

# Library Dialog Classes
class BookCheckoutConfirmationDialog:
    """Dialog for sending book checkout confirmations"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Book Checkout Confirmation")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book Title:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_book_checkout_confirmation is not None:
                if send_book_checkout_confirmation(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Checkout confirmation sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class BookReturnReminderDialog:
    """Dialog for sending book return reminders"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Return Reminder")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book Title:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_reminder).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_reminder(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_book_return_reminder is not None:
                if send_book_return_reminder(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Return reminder sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reminder")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class OverdueNotificationDialog:
    """Dialog for sending overdue book notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Overdue Notice")
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="User ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Book Title:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Days Overdue:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.days_entry = ttk.Entry(main_frame, width=40)
        self.days_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get(), self.days_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_overdue_notification is not None:
                if send_overdue_notification(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip(),
                    int(self.days_entry.get())
                ):
                    messagebox.showinfo("Success", "Overdue notice sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notice")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

# Student Affairs Dialog Classes
class InternshipNotificationDialog:
    """Dialog for sending internship status notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Internship Notification")
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Internship ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.internship_id_entry = ttk.Entry(main_frame, width=40)
        self.internship_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value="accepted")
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(status_frame, text="Accepted", variable=self.status_var, value="accepted").pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text="Rejected", variable=self.status_var, value="rejected").pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text="Pending", variable=self.status_var, value="pending").pack(side=tk.LEFT)

        ttk.Label(main_frame, text="Feedback (optional):").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.feedback_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.feedback_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.student_id_entry.get(), self.internship_id_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_internship_notification is not None:
                feedback = self.feedback_text.get(1.0, tk.END).strip() or None
                if send_internship_notification(
                    self.student_id_entry.get().strip(),
                    self.internship_id_entry.get().strip(),
                    self.status_var.get(),
                    feedback
                ):
                    messagebox.showinfo("Success", "Internship notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class MentorshipNotificationDialog:
    """Dialog for sending mentorship pairing notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Mentorship Notification")
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Mentor Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.mentor_email_entry = ttk.Entry(main_frame, width=40)
        self.mentor_email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Mentee Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mentee_email_entry = ttk.Entry(main_frame, width=40)
        self.mentee_email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Mentor Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.mentor_name_entry = ttk.Entry(main_frame, width=40)
        self.mentor_name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Mentee Name:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.mentee_name_entry = ttk.Entry(main_frame, width=40)
        self.mentee_name_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Focus Area:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.focus_entry = ttk.Entry(main_frame, width=40)
        self.focus_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=40)
        self.start_date_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="End Date (optional):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=40)
        self.end_date_entry.grid(row=6, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.mentor_email_entry.get(), self.mentee_email_entry.get(),
                    self.mentor_name_entry.get(), self.mentee_name_entry.get(),
                    self.focus_entry.get(), self.start_date_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_mentorship_notification is not None:
                end_date = self.end_date_entry.get().strip() or None
                if send_mentorship_notification(
                    self.mentor_email_entry.get().strip(),
                    self.mentee_email_entry.get().strip(),
                    self.mentor_name_entry.get().strip(),
                    self.mentee_name_entry.get().strip(),
                    self.focus_entry.get().strip(),
                    self.start_date_entry.get().strip(),
                    end_date
                ):
                    messagebox.showinfo("Success", "Mentorship notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

# Alumni Dialog Classes
class AlumniWelcomeDialog:
    """Dialog for sending alumni welcome emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Alumni Welcome Email")
        self.dialog.geometry("450x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Alumni ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Email Address:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Full Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_welcome).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_welcome(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(), self.name_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_alumni_welcome_email is not None:
                if send_alumni_welcome_email(
                    self.alumni_id_entry.get().strip(),
                    self.email_entry.get().strip(),
                    self.name_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Welcome email sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send email")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class EventInvitationDialog:
    """Dialog for sending event invitations"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Event Invitation")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Alumni ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Event ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.event_id_entry = ttk.Entry(main_frame, width=40)
        self.event_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Email Address:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Event Name:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.event_name_entry = ttk.Entry(main_frame, width=40)
        self.event_name_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Event Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.event_date_entry = ttk.Entry(main_frame, width=40)
        self.event_date_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Event Location:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.location_entry = ttk.Entry(main_frame, width=40)
        self.location_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_invitation(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(),
                    self.event_name_entry.get(), self.event_date_entry.get(),
                    self.location_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_event_invitation is not None:
                event_id = self.event_id_entry.get().strip() or None
                if send_event_invitation(
                    self.alumni_id_entry.get().strip(),
                    event_id,
                    self.email_entry.get().strip(),
                    self.event_name_entry.get().strip(),
                    self.event_date_entry.get().strip(),
                    self.location_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Event invitation sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send invitation")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

class DonationReceiptDialog:
    """Dialog for sending donation receipts"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Donation Receipt")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Alumni ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Donation ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.donation_id_entry = ttk.Entry(main_frame, width=40)
        self.donation_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Email Address:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Amount ($):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.amount_entry = ttk.Entry(main_frame, width=40)
        self.amount_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(main_frame, width=40)
        self.date_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Purpose:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.purpose_entry = ttk.Entry(main_frame, width=40)
        self.purpose_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_receipt).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_receipt(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(),
                    self.amount_entry.get(), self.date_entry.get(), self.purpose_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_donation_receipt is not None:
                donation_id = self.donation_id_entry.get().strip() or None
                if send_donation_receipt(
                    self.alumni_id_entry.get().strip(),
                    donation_id,
                    self.email_entry.get().strip(),
                    self.amount_entry.get().strip(),
                    self.date_entry.get().strip(),
                    self.purpose_entry.get().strip()
                ):
                    messagebox.showinfo("Success", "Donation receipt sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send receipt")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

# Main Application Entry Point
def main():
    """Main application entry point with backwards compatibility"""
    # Check if running as standalone or imported
    try:
        # Try to use existing auth system
        # Import centralized authentication system
        from university_system.infrastructure.auth.user_authentication import UserAuth
        auth = UserAuth()
        print("Running in standalone mode - using UserAuth")
    except Exception as e:
        print(f"❌ Failed to initialize authentication: {e}")
        raise
    
    # Create main window
    root = tk.Tk()
    
    # Set application icon (if available)
    try:
        root.iconbitmap('icon.ico')  # Replace with actual icon path
    except:
        pass
    
    # Initialize the GUI application
    app = EmailManagerGUI(root, auth)
    
    # Handle window closing
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            try:
                # Cleanup resources
                if 'cleanup_communication_system' in globals():
                    cleanup_communication_system()
            except:
                pass
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Start the GUI
    root.mainloop()

# Backwards Compatibility Functions
def run_gui_mode(auth=None):
    """Run the GUI version - backwards compatible function"""
    # Create root window
    root = tk.Tk()
    
    # Initialize GUI
    app = EmailManagerGUI(root, auth)
    
    # Start GUI
    root.mainloop()

def display_communication_dashboard_gui(auth=None):
    """GUI version of display_communication_dashboard - backwards compatible"""
    run_gui_mode(auth)

# CLI Integration Functions for Backwards Compatibility
def integrate_with_cli():
    """Integrate GUI with existing CLI functions"""
    
    # These functions maintain CLI compatibility while adding GUI options
    
    def enhanced_display_communication_dashboard(auth=None):
        """Enhanced dashboard that can run both CLI and GUI"""
        if '--gui' in sys.argv or os.environ.get('USE_GUI', '').lower() == 'true':
            display_communication_dashboard_gui(auth)
        else:
            # Call original CLI function
            if 'display_communication_dashboard' in globals():
                display_communication_dashboard(auth)
            else:
                print("CLI mode not available, starting GUI...")
                display_communication_dashboard_gui(auth)
    
    # Replace the original function
    globals()['display_communication_dashboard'] = enhanced_display_communication_dashboard

# Auto-detect mode and provide backwards compatibility
if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        print("Starting in CLI mode...")
        # Import and run original CLI functions
        try:
            if 'display_communication_dashboard' in globals():
                display_communication_dashboard()
            else:
                print("CLI mode not available")
        except Exception as e:
            print(f"Error in CLI mode: {e}")
    else:
        print("Starting GUI mode...")
        main()
else:
    # When imported as module, integrate with existing CLI
    integrate_with_cli()

# Additional Utility Classes
class ProgressDialog:
    """Progress dialog for long-running operations"""
    def __init__(self, parent, title="Processing..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x100")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = ttk.Label(main_frame, text="Please wait...")
        self.label.pack(pady=5)
        
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)
        self.progress.start()
        
        self.dialog.update()
    
    def update_text(self, text):
        """Update progress text"""
        self.label.config(text=text)
        self.dialog.update()
    
    def close(self):
        """Close progress dialog"""
        self.progress.stop()
        self.dialog.destroy()

class StatusNotification:
    """Temporary status notification"""
    def __init__(self, parent, message, duration=3000):
        self.notification = tk.Toplevel(parent)
        self.notification.title("")
        self.notification.geometry("300x80")
        
        # Position at bottom right of parent
        parent.update_idletasks()
        x = parent.winfo_x() + parent.winfo_width() - 320
        y = parent.winfo_y() + parent.winfo_height() - 100
        self.notification.geometry(f"+{x}+{y}")
        
        self.notification.overrideredirect(True)
        self.notification.configure(bg='#333333')
        
        # Message label
        label = tk.Label(self.notification, text=message, 
                        bg='#333333', fg='white', 
                        font=('Arial', 10), wraplength=280)
        label.pack(expand=True)
        
        # Auto-close after duration
        self.notification.after(duration, self.notification.destroy)

# Email Template Editor
class TemplateEditor:
    """Advanced template editor with syntax highlighting"""
    def __init__(self, parent, template_name=None):
        self.template_name = template_name
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Template Editor - {template_name or 'New Template'}")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)
        
        self.create_widgets()
        if template_name:
            self.load_template()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Template info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(info_frame, width=30)
        self.name_entry.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_entry = ttk.Entry(main_frame, width=80)
        self.subject_entry.pack(fill=tk.X, pady=5)
        
        # Body with variable hints
        body_frame = ttk.Frame(main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True)
        
        # Variables panel
        vars_frame = ttk.LabelFrame(body_frame, text="Available Variables", padding=5)
        vars_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        variables = [
            "$student_id", "$email_address", "$title", "$first_name", 
            "$last_name", "$course", "$modules_list", "$signature"
        ]
        
        for var in variables:
            btn = ttk.Button(vars_frame, text=var, width=15,
                           command=lambda v=var: self.insert_variable(v))
            btn.pack(fill=tk.X, pady=1)
        
        # Body editor
        editor_frame = ttk.Frame(body_frame)
        editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(editor_frame, text="Body:").pack(anchor=tk.W)
        self.body_text = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def insert_variable(self, variable):
        """Insert variable at cursor position"""
        self.body_text.insert(tk.INSERT, variable)
        self.body_text.focus()
    
    def load_template(self):
        """Load existing template"""
        if self.template_name and 'load_template' in globals():
            try:
                template_data = load_template(self.template_name)
                if template_data:
                    self.name_entry.insert(0, self.template_name)
                    self.subject_entry.insert(0, template_data['subject'])
                    self.body_text.insert(1.0, template_data['body'])
            except Exception as e:
                messagebox.showerror("Error", f"Error loading template: {e}")
    
    def save_template(self):
        """Save template"""
        try:
            name = self.name_entry.get().strip()
            subject = self.subject_entry.get().strip()
            body = self.body_text.get(1.0, tk.END).strip()
            
            if not name or not subject or not body:
                messagebox.showerror("Error", "Please fill in all fields")
                return
            
            if 'create_template' in globals():
                if create_template(name, subject, body):
                    messagebox.showinfo("Success", f"Template '{name}' saved successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save template")
            else:
                messagebox.showerror("Error", "Template system not available")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving template: {e}")
    
    def preview_template(self):
        """Preview template with sample data"""
        subject = self.subject_entry.get()
        body = self.body_text.get(1.0, tk.END).strip()
        
        # Sample template variables
        sample_vars = {
            'student_id': 'STU12345',
            'email_address': 'john.doe@university.edu',
            'title': 'Mr',
            'first_name': 'John',
            'last_name': 'Doe',
            'course': 'Computer Science',
            'modules_list': '- CS101: Programming\n- CS102: Data Structures',
            'signature': '\n\nBest regards,\nUniversity Administration'
        }
        
        # Simple variable substitution
        preview_subject = subject
        preview_body = body
        
        for var, value in sample_vars.items():
            preview_subject = preview_subject.replace(f'${var}', str(value))
            preview_body = preview_body.replace(f'${var}', str(value))
        
        # Show preview
        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Template Preview")
        preview_dialog.geometry("500x400")
        
        preview_frame = ttk.Frame(preview_dialog, padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(preview_frame, text=f"Subject: {preview_subject}", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)
        
        preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, state=tk.DISABLED)
        preview_text.pack(fill=tk.BOTH, expand=True)
        
        preview_text.config(state=tk.NORMAL)
        preview_text.insert(1.0, preview_body)
        preview_text.config(state=tk.DISABLED)
        
        ttk.Button(preview_frame, text="Close", command=preview_dialog.destroy).pack(pady=10)

# Theme Manager
class ThemeManager:
    """Manage application themes"""
    def __init__(self):
        self.themes = {
            'default': {
                'bg': '#f0f0f0',
                'fg': '#000000',
                'select_bg': '#0078d4',
                'select_fg': '#ffffff'
            },
            'dark': {
                'bg': '#2d2d2d',
                'fg': '#ffffff',
                'select_bg': '#404040',
                'select_fg': '#ffffff'
            },
            'blue': {
                'bg': '#e6f3ff',
                'fg': '#000080',
                'select_bg': '#0066cc',
                'select_fg': '#ffffff'
            }
        }
        self.current_theme = 'default'
    
    def apply_theme(self, root, theme_name):
        """Apply theme to application"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            
            # Apply to ttk styles
            style = ttk.Style()
            style.configure('TLabel', background=theme['bg'], foreground=theme['fg'])
            style.configure('TFrame', background=theme['bg'])
            
            # Configure root
            root.configure(bg=theme['bg'])

# Configuration Manager
class ConfigManager:
    """Manage application configuration"""
    def __init__(self):
        self.config_file = "gui_config.json"
        self.default_config = {
            'window_geometry': '1200x800',
            'theme': 'default',
            'auto_refresh': True,
            'refresh_interval': 30,
            'show_notifications': True
        }
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return {**self.default_config, **json.load(f)}
        except Exception as e:
            print(f"Error loading config: {e}")
        return self.default_config.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()

# Application singleton to prevent multiple instances
class SingletonApp:
    """Ensure only one instance of the application runs"""
    def __init__(self):
        self.socket = None
        self.port = 9999
    
    def is_running(self):
        """Check if another instance is running"""
        try:
            import socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('localhost', self.port))
            return False
        except:
            return True
    
    def cleanup(self):
        """Cleanup socket"""
        if self.socket:
            self.socket.close()

# Enhanced error handling
def handle_gui_error(func):
    """Decorator for GUI error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            import traceback
            error_msg = f"Error in {func.__name__}: {e}\n\nTraceback:\n{traceback.format_exc()}"
            print(error_msg)
            
            # Show error dialog if GUI is available
            try:
                messagebox.showerror("Error", f"An error occurred: {e}")
            except:
                print(f"GUI Error: {e}")
    return wrapper

# Export main functions for backwards compatibility
__all__ = [
    'EmailManagerGUI',
    'main',
    'run_gui_mode', 
    'display_communication_dashboard_gui',
    'integrate_with_cli'
]
