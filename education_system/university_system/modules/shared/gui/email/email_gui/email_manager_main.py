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
import logging

# Configure logging
logger = logging.getLogger(__name__)

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

# Add the project root to Python path if not already there
# This file is at university_system/interfaces/gui/email_manager_gui.py
# So we need to go up 3 levels to get to the parent of university_system
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from education_system.university_system.infrastructure.database.db import get_db_connection
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core import paths

# Import get_stored_emails first - this is critical for the inbox functionality
try:
    from education_system.university_system.infrastructure.email.email_service import get_stored_emails
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
    from education_system.university_system.infrastructure.email.email_service import (
        send_email, delete_stored_email, clear_stored_emails,
        send_registration_confirmation, send_assignment_notification,
        send_grade_notification, send_extension_notification,
        send_update_confirmation, send_password_reset,
        send_appointment_confirmation, send_health_notification,
        send_ticket_notification, send_reply_notification,
        send_internship_notification, send_alumni_welcome_email,
        send_mentorship_notification, send_event_invitation,
        send_donation_receipt, send_book_checkout_confirmation,
        send_book_return_reminder, send_overdue_notification,
        send_sla_alert, send_satisfaction_survey, send_bulk_satisfaction_surveys,
        send_application_confirmation, send_schedule_change_notification,
        send_permit_confirmation, send_permit_update_confirmation
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
                      'send_book_return_reminder', 'send_overdue_notification',
                      'send_sla_alert', 'send_satisfaction_survey', 'send_bulk_satisfaction_surveys',
                      'send_application_confirmation', 'send_schedule_change_notification',
                      'send_permit_confirmation', 'send_permit_update_confirmation']:
        if func_name not in dir():
            globals()[func_name] = None

try:
    from education_system.university_system.infrastructure.email.email_db_utilities import optimize_database, execute_db_operation
    print("✓ Imported database functions")
except ImportError as e:
    print(f"⚠️ Could not import database functions: {e}")

try:
    from education_system.university_system.infrastructure.email.template_utils import list_templates, load_template, create_template
    print("✓ Imported template functions")
except ImportError as e:
    print(f"⚠️ Could not import template functions: {e}")

try:
    from education_system.university_system.infrastructure.email.reports import get_system_health_info, get_user_communication_stats
    print("✓ Imported system health and communication stats functions")
except ImportError as e:
    print(f"⚠️ Could not import system health functions: {e}")
    get_user_communication_stats = None

# Direct import for CommunicationDashboard as fallback
if CommunicationDashboard is None:
    try:
        from education_system.university_system.infrastructure.email.admin import CommunicationDashboard as DirectCommunicationDashboard
        CommunicationDashboard = DirectCommunicationDashboard
        print("✓ Imported CommunicationDashboard directly from admin module")
    except ImportError as e:
        print(f"⚠️ Could not import CommunicationDashboard: {e}")

try:
    from education_system.university_system.infrastructure.email.announcements import send_batch_announcement
    print("✓ Imported announcement functions")
except ImportError as e:
    print(f"⚠️ Could not import announcement functions: {e}")

try:
    from education_system.university_system.infrastructure.email.admin import search_users, list_all_users
    print("✓ Imported user search functions")
except ImportError as e:
    print(f"⚠️ Could not import user search functions: {e}")

# Try importing communication system from infrastructure
try:
    from education_system.university_system.infrastructure.email.admin import (
        initialize_communication_system,
        cleanup_communication_system,
        CommunicationDashboard
    )
    from education_system.university_system.infrastructure.email.config import config, save_config
    print("✓ Imported communication system")
except ImportError as e:
    print(f"⚠️ Running in standalone mode - some features may be limited: {e}")
    # Define minimal fallbacks
    config = {'database_only_mode': True}

    def save_config(cfg):
        """Save configuration to JSON file"""
        try:
            paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config_path = str(paths.CONFIG_DIR / 'email_manager_config.json')
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
            from education_system.university_system.infrastructure.database.db import get_db_connection
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

# Import dialog classes used by EmailManagerGUI
from education_system.university_system.modules.shared.gui.email.email_gui.utility_dialogs import HelpDialog, AboutDialog

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
            from education_system.university_system.infrastructure.email.email_db_utilities import initialize_email_db
            initialize_email_db()

            # Initialize the communication system using existing functions
            if initialize_communication_system is not None:
                initialize_communication_system()

            # Set the auth instance in the email infrastructure state
            # This ensures all email modules can access authentication
            try:
                from education_system.university_system.infrastructure.email import set_auth
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
        self.root.title(_t("email.window_title", default="University Communication System - Email Manager"))

        # Center on screen. withdraw → set geometry → (caller deiconifies) avoids
        # a single-frame flash at the WM-default position before the move.
        w, h = 1400, 900
        try:
            self.root.withdraw()
            x = max(0, (self.root.winfo_screenwidth() - w) // 2)
            y = max(0, (self.root.winfo_screenheight() - h) // 2)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.root.deiconify()
        except tk.TclError:
            self.root.geometry(f"{w}x{h}")
        self.root.minsize(1200, 800)

        # Configure style
        style = ttk.Style()

        # Configure Treeview selection highlighting
        style.map('Treeview',
                  background=[('selected', '#0078D7')],
                  foreground=[('selected', 'white')])

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
        menubar.add_cascade(label=_t("email.menu.file", default="File"), menu=file_menu)
        file_menu.add_command(label=_t("email.menu.new_email", default="New Email"), command=self.compose_email, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label=_t("email.menu.import_contacts", default="Import Contacts"), command=self.import_contacts)
        file_menu.add_command(label=_t("email.menu.export_data", default="Export Data"), command=self.export_data)

        # Email menu
        email_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("email.menu.email", default="Email"), menu=email_menu)
        email_menu.add_command(label=_t("email.menu.compose", default="Compose"), command=self.compose_email)
        email_menu.add_command(label=_t("email.menu.send_bulk", default="Send Bulk"), command=self.send_bulk_email)
        email_menu.add_command(label=_t("email.menu.schedule_email", default="Schedule Email"), command=self.schedule_email)
        email_menu.add_separator()
        email_menu.add_command(label=_t("email.menu.templates", default="Templates"), command=self.manage_templates)
        email_menu.add_command(label=_t("email.menu.configuration", default="Configuration"), command=self.email_configuration)

        # Communication menu
        comm_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("email.menu.communication", default="Communication"), menu=comm_menu)
        comm_menu.add_command(label=_t("email.menu.messages", default="Messages"), command=self.open_messages)
        comm_menu.add_command(label=_t("email.menu.announcements", default="Announcements"), command=self.open_announcements)
        comm_menu.add_command(label=_t("email.menu.chat_rooms", default="Chat Rooms"), command=self.open_chat_rooms)
        comm_menu.add_separator()
        comm_menu.add_command(label=_t("email.menu.notifications_hub", default="Notifications Hub"), command=self.show_notifications_hub)
        comm_menu.add_command(label=_t("email.menu.preferences", default="Preferences"), command=self.notification_preferences)

        # NOTE: Notifications menu removed - emails now send automatically
        # All notification emails are triggered automatically by the respective modules:
        # - Academic: Registration, assignments, grades, extensions, schedule changes
        # - Health: Appointments, health advisories
        # - Helpdesk: Tickets, replies, SLA alerts, satisfaction surveys
        # - Library: Checkouts, return reminders, overdue notices
        # - Student Affairs: Internships, mentorships
        # - Alumni: Welcome emails, event invitations, donation receipts
        # - Parking: Permit confirmations and updates
        # Use the Email Scheduler for batch operations (Queue & Workers button)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("email.menu.tools", default="Tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("email.menu.email_reports", default="Email Reports"), command=self.advanced_email_reports)
        tools_menu.add_command(label=_t("email.menu.system_health", default="System Health"), command=self.system_health)
        tools_menu.add_command(label=_t("email.menu.database_cleanup", default="Database Cleanup"), command=self.database_cleanup)
        tools_menu.add_command(label=_t("email.menu.advanced_search", default="Advanced Search"), command=self.advanced_search)
        tools_menu.add_command(label=_t("email.menu.communication_stats", default="Communication Stats"), command=self.communication_stats)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("email.menu.fix_email_senders", default="Fix Email Senders"), command=self.fix_email_senders)
        tools_menu.add_command(label=_t("email.menu.test_sender_attribution", default="Test Sender Attribution"), command=self.test_sender_attribution)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("email.menu.help", default="Help"), menu=help_menu)
        help_menu.add_command(label=_t("email.menu.user_guide", default="User Guide"), command=self.show_help)
        help_menu.add_command(label=_t("email.menu.about", default="About"), command=self.show_about)

        # Bind keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.compose_email())
        self.root.bind('<Control-q>', lambda e: self.root.quit())

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Ensure a top-right button exists for returning to the main menu"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception as e:
            logger.debug(f"Failed to check main menu button existence: {e}")

        self.main_menu_button = ttk.Button(
            self.root,
            text=_t("common.return_to_main_menu", default="Return to Main Menu"),
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

    def create_main_interface(self):
        """Create the main interface with notebook tabs"""
        # Add return to main menu button at top right
        return_btn = ttk.Button(
            self.root,
            text=_t("email.buttons.return_to_main_menu", default="Return to Main Menu"),
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
        self.create_messages_tab()  # Now includes notifications as a sub-tab
        self.create_sms_tab()
        self.create_announcements_tab()
        self.create_chat_tab()
        self.create_reports_tab()

    def create_status_frame(self, parent):
        """Create status bar and notifications"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # Status label
        self.status_label = ttk.Label(status_frame, text=_t("email.status.ready", default="Ready"))
        self.status_label.pack(side=tk.LEFT)

        # Notification area
        self.notification_frame = ttk.Frame(status_frame)
        self.notification_frame.pack(side=tk.RIGHT)

        # Email mode indicator
        mode = _t("email.status.database_mode", default="Database Mode") if config.get('database_only_mode', True) else _t("email.status.smtp_mode", default="SMTP Mode")
        mode_label = ttk.Label(self.notification_frame, text=f"{mode}")
        mode_label.pack(side=tk.RIGHT, padx=(10, 0))

        # User info
        user_text = f"👤 {self.auth.current_user['username']} ({self.auth.current_user['role']})"
        user_label = ttk.Label(self.notification_frame, text=user_text)
        user_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Homescreen navigation button keeps experience consistent with other GUIs
        exit_button = ttk.Button(
            self.notification_frame,
            text=_t("email.buttons.return_to_homescreen", default="Return to Homescreen"),
            command=self.return_to_main_menu,
        )
        exit_button.pack(side=tk.RIGHT, padx=(10, 0))

    def load_initial_data(self):
        """Load initial data for all tabs"""
        self.refresh_emails()
        self.refresh_messages()
        self.refresh_announcements()
        self.refresh_chat_rooms()
        self.update_stats()

    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
        self.root.update_idletasks()

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_help(self):
        """Show help documentation"""
        HelpDialog(self.root)

    def show_about(self):
        """Show about dialog"""
        AboutDialog(self.root)

    def fix_email_senders(self):
        """Fix existing email sender attribution"""
        if messagebox.askyesno(_t("common.confirm", default="Confirm"), _t("email.dialogs.fix_senders_confirm", default="Fix email sender attribution? This will update existing messages.")):
            try:
                # Import the function from email_manager
                from education_system.university_system.infrastructure.email.email_service import fix_existing_email_senders
                count = fix_existing_email_senders()
                messagebox.showinfo(_t("common.success", default="Success"), _t("email.dialogs.fix_senders_success", default="Fixed {count} messages with proper sender attribution").format(count=count))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("email.dialogs.fix_senders_failed", default="Failed to fix senders: {error}").format(error=e))

    def test_sender_attribution(self):
        """Test sender attribution"""
        try:
            # Import the function from email_manager
            from education_system.university_system.infrastructure.email.email_service import test_sender_attribution as test_func
            result = test_func()
            if result:
                messagebox.showinfo(_t("common.info", default="Test"), _t("email.dialogs.sender_test_complete", default="Sender attribution test completed. Check the console for details."))
            else:
                messagebox.showwarning(_t("common.warning", default="Test"), _t("email.dialogs.sender_test_failed", default="Sender attribution test failed. Check the console for details."))
        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), _t("email.dialogs.test_failed", default="Test failed: {error}").format(error=e))

    def show_notifications_hub(self):
        """Focus the unified Messages tab (notifications now live there)."""
        try:
            self.open_messages()
            if getattr(self, "_unified_inbox_panel", None):
                self._unified_inbox_panel._type_var.set("Notification")
                self._unified_inbox_panel._refresh_feed()
        except Exception as e:
            logger.error(f"Error focusing Messages tab: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to open Notifications: {e}")


# Import tab modules to bind their methods to EmailManagerGUI
# These modules define helper methods and bind them to the EmailManagerGUI class
try:
    from education_system.university_system.modules.shared.gui.email.email_gui import email_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import messages_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import dashboard_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import sms_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import announcements_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import chat_tab
    from education_system.university_system.modules.shared.gui.email.email_gui import reports_tab
except ImportError as e:
    # Some tab modules may not exist yet
    logger.debug(f"Could not import all tab modules: {e}")

def main():
    """Main application entry point with backwards compatibility"""
    # Check if running as standalone or imported
    try:
        # Try to use centralized auth system first
        auth = get_auth()
        if auth is None:
            from education_system.university_system.infrastructure.auth import UserAuth
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
    except Exception as e:
        logger.debug(f"Failed to set application icon: {e}")

    # Initialize the GUI application
    app = EmailManagerGUI(root, auth)

    # Handle window closing
    def on_closing():
        if messagebox.askokcancel(_t("email.dialogs.quit_title", default="Quit"), _t("email.dialogs.confirm_quit", default="Do you want to quit?")):
            try:
                # Cleanup resources
                if 'cleanup_communication_system' in globals():
                    cleanup_communication_system()
            except Exception as e:
                logger.debug(f"Failed to cleanup communication system: {e}")
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start the GUI
    root.mainloop()
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
