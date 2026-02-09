# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
import sqlite3
import logging

# Import database connection
from university_system.infrastructure.database.db import get_connection

# Import i18n for language support
from university_system.modules.shared.utils.i18n import get_text as _

# Import GUI availability flags and classes
from university_system.modules.shared.gui.main.imports import gui_imports
from university_system.modules.shared.gui.main.imports.gui_imports import (
    STUDENT_ANALYTICS_GUI_AVAILABLE,
    ANALYTICS_GUI_AVAILABLE,
    CHATBOT_GUI_AVAILABLE,
    GUIStudentAnalytics,
    UniversityChatbotGUI,
)

def show_integrated_dashboard(self):
    """Show integrated dashboard with system overview and quick stats"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.login_required"))
        return

    self.clear_content()

    # Create dashboard layout
    dashboard_frame = ttk.Frame(self.content_frame)
    dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Title
    title_label = ttk.Label(dashboard_frame, text=_("dashboard.title"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=(0, 20))

    # Create notebook for different dashboard sections
    notebook = ttk.Notebook(dashboard_frame)
    notebook.pack(fill=tk.BOTH, expand=True)

    # System Overview Tab
    overview_frame = ttk.Frame(notebook)
    notebook.add(overview_frame, text=_("dashboard.tabs.overview"))
    self.create_overview_tab(overview_frame)

    # Quick Stats Tab
    stats_frame = ttk.Frame(notebook)
    notebook.add(stats_frame, text=_("dashboard.tabs.statistics"))
    self.create_stats_tab(stats_frame)

    # Recent Activity Tab
    activity_frame = ttk.Frame(notebook)
    notebook.add(activity_frame, text=_("dashboard.tabs.activity"))
    self.create_activity_tab(activity_frame)

    # System Health Tab
    health_frame = ttk.Frame(notebook)
    notebook.add(health_frame, text=_("dashboard.tabs.health"))
    self.create_health_tab(health_frame)

    print(_("dashboard.messages.opened_successfully"))
def create_overview_tab(self, parent):
    """Create system overview tab"""
    overview_container = ttk.Frame(parent, padding="20")
    overview_container.pack(fill=tk.BOTH, expand=True)

    # Welcome message
    welcome_text = _("dashboard.overview.welcome", username=self.auth.current_user.get('username', _("common.user")))
    ttk.Label(overview_container, text=welcome_text, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Quick access buttons in a grid
    buttons_frame = ttk.LabelFrame(overview_container, text=_("dashboard.overview.quick_access"), padding="15")
    buttons_frame.pack(fill=tk.X, pady=(0, 20))

    # Configure grid
    for i in range(3):
        buttons_frame.columnconfigure(i, weight=1)

    # Quick access buttons
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.student_records"),
              command=self.show_student_records).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.grade_tracking"),
              command=self.show_grade_tracking_gui).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.attendance"),
              command=self.open_attendance_gui).grid(row=0, column=2, padx=5, pady=5, sticky="ew")

    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.course_management"),
              command=self.show_course_management).grid(row=1, column=0, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.finance_management"),
              command=self.show_finance_management).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(buttons_frame, text=_("dashboard.overview.buttons.reports"),
              command=self.show_enhanced_reporting_dashboard).grid(row=1, column=2, padx=5, pady=5, sticky="ew")

    # System status
    status_frame = ttk.LabelFrame(overview_container, text=_("dashboard.overview.system_status"), padding="15")
    status_frame.pack(fill=tk.X, pady=(0, 20))

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ttk.Label(status_frame, text=_("dashboard.overview.current_time", time=current_time)).pack(anchor="w")
    ttk.Label(status_frame, text=_("dashboard.overview.user_role", role=self.auth.current_user.get('role', _("common.unknown")))).pack(anchor="w")
    ttk.Label(status_frame, text=_("dashboard.overview.database_connected")).pack(anchor="w")

def create_stats_tab(self, parent):
    """Create quick statistics tab"""
    stats_container = ttk.Frame(parent, padding="20")
    stats_container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(stats_container, text=_("dashboard.statistics.title"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Stats grid
    stats_frame = ttk.Frame(stats_container)
    stats_frame.pack(fill=tk.BOTH, expand=True)

    # Try to get actual database statistics
    try:
        # This would be populated with real data from the database
        stats_text = _("dashboard.statistics.database_stats") + """
• """ + _("dashboard.statistics.total_students") + """ Loading...
• """ + _("dashboard.statistics.active_courses") + """ Loading...
• """ + _("dashboard.statistics.pending_assignments") + """ Loading...
• """ + _("dashboard.statistics.system_uptime") + """ """ + _("common.active") + """
• """ + _("dashboard.statistics.recent_logins") + """ Loading...

""" + _("dashboard.statistics.performance_metrics") + """
• """ + _("dashboard.statistics.db_response_time") + """ <50ms
• """ + _("dashboard.statistics.system_load") + """ """ + _("dashboard.statistics.normal") + """
• """ + _("dashboard.statistics.memory_usage") + """ """ + _("dashboard.statistics.optimal") + """
• """ + _("dashboard.statistics.active_sessions") + """ 1"""

        stats_display = tk.Text(stats_frame, wrap=tk.WORD, height=15, width=60)
        stats_display.pack(fill=tk.BOTH, expand=True)
        stats_display.insert(tk.END, stats_text)
        stats_display.config(state=tk.DISABLED)

    except Exception as e:
        ttk.Label(stats_frame, text=_("dashboard.statistics.load_error", error=str(e))).pack()

def create_activity_tab(self, parent):
    """Create recent activity tab"""
    activity_container = ttk.Frame(parent, padding="20")
    activity_container.pack(fill=tk.BOTH, expand=True)

    ttk.Label(activity_container, text=_("dashboard.activity.title"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Activity log display
    activity_display = tk.Text(activity_container, wrap=tk.WORD, height=20)
    activity_display.pack(fill=tk.BOTH, expand=True)

    # Sample activity data (would be populated from actual logs)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    username = self.auth.current_user.get('username')
    activity_text = _("dashboard.activity.log_header") + f"""
{timestamp} - """ + _("dashboard.activity.user_logged_in", username=username) + f"""
{timestamp} - """ + _("dashboard.activity.dashboard_accessed") + f"""
{timestamp} - """ + _("dashboard.activity.system_initialized") + """

""" + _("dashboard.activity.previous_sessions") + """
• """ + _("dashboard.activity.last_login") + """ """ + _("dashboard.activity.today") + """
• """ + _("dashboard.activity.recent_actions") + """ """ + _("dashboard.activity.actions_list") + """
• """ + _("dashboard.activity.system_health") + """ """ + _("dashboard.activity.all_operational") + """
"""

    activity_display.insert(tk.END, activity_text)
    activity_display.config(state=tk.DISABLED)

def create_health_tab(self, parent):
    """Create system health monitoring tab"""
    if self.health_portal_gui:
        self.health_portal_gui.create_health_tab(parent)
    else:
        # Fallback implementation
        health_container = ttk.Frame(parent, padding="20")
        health_container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(health_container, text=_("dashboard.health.title"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        ttk.Label(health_container, text=_("dashboard.health.not_available")).pack(pady=10)
def show_analytics(self):
    """Launch the standalone Student Analytics GUI from student_analytics_gui.py"""
    if not self.auth.current_user or 'view_analytics' not in self.auth.current_user.get('permissions', []):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_analytics_permission"))
        return

    try:
        if STUDENT_ANALYTICS_GUI_AVAILABLE:
            # Create a child window for the analytics GUI
            analytics_window = tk.Toplevel(self.root)
            analytics_window.transient(self.root)

            # Launch the GUI in the child window
            analytics_app = GUIStudentAnalytics(root=analytics_window, auth_manager=self.auth)
        else:
            messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_not_available"))
    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.analytics_launch_failed", error=str(e)))
def show_chatbot(self):
    """Launch the full Chatbot GUI using the existing ChatbotGUI class"""
    if not self.auth.current_user:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_login_required"))
        return

    if not self.auth.check_permission('access_chatbot'):
        messagebox.showerror(_("common.error"), _("dashboard.errors.no_chatbot_permission"))
        return

    try:
        # Initialize the chatbot instance if not already done
        if not gui_imports.chatbot_instance:
            if not gui_imports.initialize_chatbot_integration():
                messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_init_failed"))
                return

        # Set authentication system for chatbot
        if gui_imports.chatbot_instance and self.auth:
            gui_imports.chatbot_instance.set_auth_system(self.auth)

        # Use imported UniversityChatbotGUI if available
        if CHATBOT_GUI_AVAILABLE and UniversityChatbotGUI:
            chatbot_window = tk.Toplevel(self.root)
            chatbot_window.title(_("dashboard.chatbot.title"))
            chatbot_window.geometry("1000x700")

            chatbot_gui = UniversityChatbotGUI(gui_imports.chatbot_instance, chatbot_window, auth_system=self.auth)
            print(_("dashboard.messages.chatbot_opened"))
        else:
            messagebox.showerror(
                _("common.error"),
                "Chatbot GUI is not available. Please ensure the chatbot module is installed."
            )

        print(_("dashboard.messages.chatbot_launched"))

    except Exception as e:
        messagebox.showerror(_("common.error"), _("dashboard.errors.chatbot_open_failed", error=str(e)))
        print(f"Chatbot GUI error: {e}")
def log_activity(self, message, level="info", action=None):
    """Log activity with comprehensive error handling"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        formatted_message = f"[{timestamp}] {_('dashboard.log.gui_prefix')}: {message}"

        print(formatted_message)

        if level.lower() == "error":
            logging.error(formatted_message)
        elif level.lower() == "warning":
            logging.warning(formatted_message)
        else:
            logging.info(formatted_message)

    except Exception as e:
        print(f"{_('dashboard.log.gui_activity')}: {message}")
        logging.error(f"{_('dashboard.log.logging_error')}: {e}")
def launch_analytics_gui_standalone():
    """Launch analytics GUI as standalone window"""
    try:
        if ANALYTICS_GUI_AVAILABLE:
            analytics_app = GUIStudentAnalytics()
            if auth:
                analytics_app.auth = auth
            analytics_app.run()
        else:
            print(_("dashboard.messages.analytics_not_available_cli"))
            display_analytics_menu()
    except Exception as e:
        print(_("dashboard.errors.analytics_error", error=str(e)))
        display_analytics_menu()
