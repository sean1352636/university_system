from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.utils.logging.gui.helpers import (
    _t, I18N_AVAILABLE, STUDENT_SYSTEM_AVAILABLE,
    init_i18n, get_current_language, show_gui_language_selector,
    get_log_manager, initialize_database,
)
from education_system.university_system.utils.logging.gui.fallbacks import FallbackLogManager

# Mixin imports – tabs
from education_system.university_system.utils.logging.gui.tabs.dashboard import DashboardMixin
from education_system.university_system.utils.logging.gui.tabs.search import SearchMixin
from education_system.university_system.utils.logging.gui.tabs.analytics import AnalyticsMixin
from education_system.university_system.utils.logging.gui.tabs.alerts import AlertsMixin
from education_system.university_system.utils.logging.gui.tabs.config import ConfigMixin
from education_system.university_system.utils.logging.gui.tabs.maintenance import MaintenanceMixin

# Mixin imports – features
from education_system.university_system.utils.logging.gui.features.security_analysis import SecurityAnalysisMixin
from education_system.university_system.utils.logging.gui.features.realtime_monitor import RealtimeMonitorMixin
from education_system.university_system.utils.logging.gui.features.performance_testing import PerformanceTestingMixin
from education_system.university_system.utils.logging.gui.features.student_integration import StudentIntegrationMixin
from education_system.university_system.utils.logging.gui.features.export_import import ExportImportMixin
from education_system.university_system.utils.logging.gui.features.api_management import ApiManagementMixin
from education_system.university_system.utils.logging.gui.features.email_reporting import EmailReportingMixin

# Initialize logger
logger = logging.getLogger(__name__)


class LogManagementGUI(
    DashboardMixin,
    SearchMixin,
    AnalyticsMixin,
    AlertsMixin,
    ConfigMixin,
    MaintenanceMixin,
    SecurityAnalysisMixin,
    RealtimeMonitorMixin,
    PerformanceTestingMixin,
    StudentIntegrationMixin,
    ExportImportMixin,
    ApiManagementMixin,
    EmailReportingMixin,
):
    """Main GUI application for log management"""

    def __init__(self, root, auth=None, embedded: bool = False):
        self.root = root
        self.auth = auth
        self.log_manager = None
        self.embedded = embedded

        # Initialize database tables
        initialize_database()

        try:
            self.log_manager = get_log_manager()
            if not hasattr(self.log_manager, 'available'):
                self.log_manager.available = True
        except Exception as e:
            print(f"Error initializing log manager: {e}")
            self.log_manager = FallbackLogManager()

        self.setup_gui()

    def setup_gui(self):
        """Setup the main GUI"""
        if not self.embedded:
            self.root.title(_t("log_management.window_title"))
            self.root.geometry("1300x850")
            self.root.minsize(1100, 720)
            ttk.Button(
                self.root,
                text="🏠 " + _t("log_management.return_to_main"),
                command=self.return_to_main_menu
            ).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        style = ttk.Style()
        style.theme_use('clam')

        if not self.embedded:
            self.setup_menu()

        # Main frame + notebook live fine in both modes
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.setup_dashboard_tab()
        self.setup_search_tab()
        self.setup_analytics_tab()
        self.setup_alerts_tab()
        self.setup_config_tab()
        self.setup_maintenance_tab()

        self.setup_status_bar()

        if not self.embedded:
            self.update_dashboard()

    def setup_menu(self):
        """Setup the main menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.file"), menu=file_menu)
        file_menu.add_command(label=_t("log_management.menu.export_logs"), command=self.export_logs_dialog)
        file_menu.add_command(label=_t("log_management.menu.import_logs"), command=self.import_logs_dialog)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("log_management.menu.refresh_dashboard"), command=self.update_dashboard)
        view_menu.add_command(label=_t("log_management.menu.realtime_monitor"), command=self.open_realtime_monitor)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.tools"), menu=tools_menu)
        tools_menu.add_command(label=_t("log_management.menu.generate_chart"), command=self.generate_chart_dialog)
        tools_menu.add_command(label=_t("log_management.menu.integrity_check"), command=self.run_integrity_check)
        tools_menu.add_command(label=_t("log_management.menu.db_optimization"), command=self.optimize_database)
        tools_menu.add_separator()
        tools_menu.add_command(label=_t("log_management.menu.send_email_report"), command=self.email_report_dialog)
        tools_menu.add_command(label=_t("log_management.menu.test_email"), command=self.send_test_email)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("log_management.menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("log_management.menu.api_docs"), command=self.show_api_docs)
        help_menu.add_command(label=_t("log_management.menu.about"), command=self.show_about)
        self.setup_integration_menu()

    def setup_integration_menu(self):
        """Add integration menu items if student system is available"""
        if self.embedded:
            return
        if STUDENT_SYSTEM_AVAILABLE:
            tools_menu = self.root.nametowidget(self.root['menu']).children['!menu2']
            tools_menu.add_separator()
            tools_menu.add_command(label=_t("log_management.student_logs.title"), command=self.view_student_logs)

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text=_t("log_management.status_bar.ready"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Add connection status
        db_status = self._check_database_connection()
        self.connection_label = ttk.Label(self.status_bar, text=_t("log_management.status_bar.database", status=db_status))
        self.connection_label.pack(side=tk.RIGHT, padx=5)

        # Language change button
        if I18N_AVAILABLE:
            lang_button = ttk.Button(
                self.status_bar,
                text="🌐 " + _t("log_management.language.button"),
                command=self._on_language_change
            )
            lang_button.pack(side=tk.RIGHT, padx=5)

        # Consistent navigation back to the main menu
        exit_button = ttk.Button(
            self.status_bar,
            text="🏠 " + _t("log_management.return_to_main"),
            command=self.return_to_main_menu
        )
        exit_button.pack(side=tk.RIGHT, padx=5)

    def _on_language_change(self):
        """Handle language change request"""
        current_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()

        if new_lang != current_lang:
            messagebox.showinfo(
                _t("log_management.language.changed_title"),
                _t("log_management.language.changed_message")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh the UI after language change"""
        # Re-initialize i18n with new language
        init_i18n(get_current_language())

        # Update window title
        if not self.embedded:
            self.root.title(_t("log_management.window_title"))

        # Rebuild the UI by destroying and recreating all widgets
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if hasattr(self, 'status_bar'):
            self.status_bar.destroy()

        # Recreate notebook and tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.setup_dashboard_tab()
        self.setup_search_tab()
        self.setup_analytics_tab()
        self.setup_alerts_tab()
        self.setup_config_tab()
        self.setup_maintenance_tab()

        self.setup_status_bar()

        if not self.embedded:
            self.update_dashboard()

    def _check_database_connection(self):
        """Check if database connection is working"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            conn.close()

            # Check if required tables exist
            required_tables = {'logs', 'alerts', 'saved_searches', 'students'}
            existing_tables = {table[0] for table in tables}

            if required_tables.issubset(existing_tables):
                return _t("log_management.status_bar.connected")
            else:
                return _t("log_management.status_bar.missing_tables")
        except Exception:
            return _t("log_management.status_bar.disconnected")

    def update_status(self, message):
        """Update status bar message (safe if status bar not yet built)"""
        if not hasattr(self, "status_label"):
            # build it on first use to avoid AttributeError
            self.setup_status_bar()
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def refresh_connection_status(self):
        """Refresh database connection status in status bar"""
        if hasattr(self, "connection_label"):
            db_status = self._check_database_connection()
            self.connection_label.config(text=_t("log_management.status_bar.database", status=db_status))

    def show_api_docs(self):
        """Show API documentation"""
        docs_window = tk.Toplevel(self.root)
        docs_window.title(_t("log_management.dialogs.api_docs"))
        docs_window.geometry("800x600")

        ttk.Label(docs_window, text=_t("log_management.dialogs.api_docs"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        docs_text = scrolledtext.ScrolledText(docs_window, wrap=tk.WORD, font=("Courier", 10))
        docs_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        api_docs = """
Log Management API Endpoints
============================

Authentication:
POST /api/auth/login - Get authentication token
  Body: {"username": "user", "password": "pass"}
  Returns: {"token": "jwt_token", "expires_in": 86400}

Log Operations:
POST /api/logs/search - Search logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"date_from": "2024-01-01", "user_id": "admin", "limit": 100}

GET /api/logs/recent?hours=24&limit=50 - Get recent logs
  Headers: Authorization: Bearer <token>

GET /api/logs/user/{user_id}?days=7&limit=100 - Get logs for specific user
  Headers: Authorization: Bearer <token>

Analytics:
GET /api/analytics/summary?days=7 - Get activity summary
  Headers: Authorization: Bearer <token>

GET /api/analytics/user/{user_id}?days=30 - Get user analytics
  Headers: Authorization: Bearer <token>

POST /api/analytics/chart - Generate activity chart
  Headers: Authorization: Bearer <token>
  Body: {"days": 7, "type": "daily"}

Alerts:
GET /api/alerts?hours=24 - Get recent alerts
  Headers: Authorization: Bearer <token>

POST /api/alerts/check - Trigger alert checks
  Headers: Authorization: Bearer <token>

Export:
POST /api/export/logs - Export logs with filters
  Headers: Authorization: Bearer <token>
  Body: {"filters": {...}, "format": "json|csv|excel"}

System:
GET /api/system/status - Get system status
  Headers: Authorization: Bearer <token>

GET /api/config - Get configuration
  Headers: Authorization: Bearer <token>

PUT /api/config - Update configuration
  Headers: Authorization: Bearer <token>
  Body: {"retention_days": 90, "enable_alerts": true}

Webhooks:
POST /api/webhooks/log - Receive external log entries
  Headers: X-Webhook-Key: <webhook_secret>
  Body: {log_entry_data}

Health:
GET /api/health - Health check (no auth required)
  Returns: {"status": "healthy", "timestamp": "..."}

Error Responses:
All endpoints return appropriate HTTP status codes:
- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error

Response format:
{
  "success": true/false,
  "data": {...},
  "error": "error message if applicable"
}
"""

        docs_text.insert("1.0", api_docs)
        docs_text.config(state=tk.DISABLED)

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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def show_about(self):
        """Show about dialog"""
        about_text = """Enhanced Log Management System
Version 1.0.0

A comprehensive logging and audit system with:
• Real-time monitoring
• Advanced search and filtering
• Analytics and reporting
• Security alerts
• API integration
• Database management tools

Built with Python and tkinter
Compatible with the original CLI interface

For support and documentation, visit:
https://github.com/yourproject/log-management"""

        messagebox.showinfo("About", about_text)


# GUI Launcher Functions (maintains backwards compatibility)
def launch_log_management_gui(auth=None):
    """Launch the GUI version of log management"""
    root = tk.Tk()
    app = LogManagementGUI(root, auth)
    root.mainloop()

def display_log_management_menu_gui(auth):
    """GUI version of the original menu function"""
    launch_log_management_gui(auth)

if __name__ == "__main__":
    # Test the GUI
    try:
        # Try to import the original module for full functionality
        from education_system.university_system.infrastructure.logging.log_management import (
            log_manager, LogSecurity, generate_api_key, generate_chart,
            get_alerts, get_log_manager, login, optimize_database, save_search,
            search_logs, show_api_docs, show_system_resources,
            test_insert_performance, test_query_performance, vacuum_database
        )
        print("Full log management system loaded")
    except ImportError:
        print("Running in standalone GUI mode")

    # Add tkinter import for the dialog
    import tkinter.simpledialog
    tk.simpledialog = tkinter.simpledialog

    # Launch GUI
    launch_log_management_gui()
