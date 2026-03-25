import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from pathlib import Path
import uuid
import qrcode
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import path constants
from education_system.university_system.modules.shared.constants.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

# Import modular tab functions
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import dashboard_tab
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import attendance_tab
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import students_tab
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import reports_tab
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import analytics_tab
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import settings_admin_tabs
from education_system.university_system.modules.domain.academics.gui.attendance_tracker import misc_tab

# Import window classes
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.attendance_windows import (
    ManualAttendanceWindow, BatchAttendanceWindow, EditAttendanceWindow, StudentAddWindow
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.qr_windows import QRAttendanceWindow, QRGeneratorWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.face_recognition_windows import (
    FaceRecognitionAttendanceWindow, FaceRecognitionWindow
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.admin_windows import APIManagementWindow, AuditLogsViewer, SystemDiagnosticsWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.backup_database_windows import (
    BackupRecoveryWindow, BackupSettingsDialog, DatabaseMaintenanceWindow
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.alerts_predictive_windows import (
    AlertsWindow, CreateAlertDialog, AlertDetailsWindow,
    PredictiveAnalyticsWindow, SinglePredictionDialog
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.notifications_windows import (
    ParentNotificationWindow, ParentContactDialog, NotificationSettingsWindow
)
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.misc_windows import (
    GeofencingWindow, LMSIntegrationWindow, CalendarSyncWindow,
    GamificationWindow, CustomReportWindow, ImportDataWindow,
    ExportDataWindow, ReportWindow, AttendancePoliciesWindow, HelpWindow
)


class AttendanceGUI:
    def setup_menu(self):
            """Create menu bar"""
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)

            # File menu
            file_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("attendance.menu.file"), menu=file_menu)
            file_menu.add_command(label=_("attendance.menu.import_data"), command=self.import_data)
            file_menu.add_command(label=_("attendance.menu.export_data"), command=self.export_data)
            file_menu.add_separator()
            file_menu.add_command(label=_("attendance.menu.backup_database"), command=self.backup_database)
            file_menu.add_command(label=_("attendance.menu.restore_database"), command=self.restore_database)
            file_menu.add_separator()
            file_menu.add_command(label=_("common.exit"), command=self.root.quit)

            # Advanced menu
            advanced_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("attendance.menu.advanced"), menu=advanced_menu)
            advanced_menu.add_command(label=_("attendance.menu.api_management"), command=self.open_api_management)
            advanced_menu.add_command(label=_("attendance.menu.lms_integration"), command=self.open_lms_integration)
            advanced_menu.add_command(label=_("attendance.menu.calendar_sync"), command=self.open_calendar_sync)
            advanced_menu.add_separator()
            advanced_menu.add_command(label=_("attendance.menu.audit_logs"), command=self.view_audit_logs)
            advanced_menu.add_command(label=_("attendance.menu.system_diagnostics"), command=self.run_diagnostics)
            advanced_menu.add_command(label=_("attendance.menu.database_maintenance"), command=self.database_maintenance)

            # Tools menu
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("attendance.menu.tools"), menu=tools_menu)
            tools_menu.add_command(label=_("attendance.menu.qr_code_generator"), command=self.open_qr_generator)
            tools_menu.add_command(label=_("attendance.menu.face_recognition_setup"), command=self.open_face_recognition)
            tools_menu.add_command(label=_("attendance.menu.geofencing_setup"), command=self.open_geofencing)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("attendance.menu.parent_notification_system"), command=self.open_parent_notifications)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("attendance.menu.run_original_cli"), command=self.run_original_cli)
            tools_menu.add_separator()
            tools_menu.add_command(label=_("attendance.menu.biometrics_management"), command=self.open_biometrics_management)
            tools_menu.add_command(label=_("attendance.menu.attendance_alerts"), command=self.open_attendance_alerts)
            tools_menu.add_command(label=_("attendance.menu.predictive_analytics"), command=self.open_predictive_analytics)
            tools_menu.add_command(label=_("attendance.menu.backup_recovery"), command=self.open_backup_recovery)

            # Help menu
            help_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_("attendance.menu.help"), menu=help_menu)
            help_menu.add_command(label=_("attendance.menu.user_manual"), command=self.show_help)
            help_menu.add_command(label=_("attendance.menu.about"), command=self.show_about)

            self.create_main_menu_button()
    def refresh_data(self):
            """Refresh all data in the application"""
            self.update_status(_("attendance.messages.refreshing_data"))

            # Update dashboard stats
            self.update_dashboard_stats()

            # Update charts
            self.update_dashboard_charts()

            # Refresh module combo
            self.refresh_modules()

            # Refresh students data
            self.refresh_students_data()

            # Refresh recent activity
            self.refresh_recent_activity()

            self.update_status(_("attendance.messages.data_refreshed"), "success")
    def setup_styles(self):
            """Configure custom styles"""
            # Configure notebook tabs
            self.style.configure('Custom.TNotebook.Tab', padding=[20, 10])
            self.style.map('Custom.TNotebook.Tab',
                          background=[('selected', self.colors['secondary']),
                                    ('!selected', self.colors['light'])],
                          foreground=[('selected', 'white'),
                                    ('!selected', self.colors['dark'])])

            # Configure buttons
            self.style.configure('Primary.TButton',
                               background=self.colors['secondary'],
                               foreground='white',
                               padding=(10, 5))

            self.style.configure('Success.TButton',
                               background=self.colors['success'],
                               foreground='white',
                               padding=(10, 5))

            self.style.configure('Warning.TButton',
                               background=self.colors['warning'],
                               foreground='white',
                               padding=(10, 5))

            self.style.configure('Danger.TButton',
                               background=self.colors['danger'],
                               foreground='white',
                               padding=(10, 5))
    def return_to_main_menu(self):
            """Return to the main menu"""
            try:
                # Check if this is a child window (Toplevel) or standalone (Tk)
                if isinstance(self.root, tk.Toplevel):
                    # Just close the child window
                    self.root.destroy()
                else:
                    # Running standalone, need to create main GUI
                    self.root.destroy()
                    from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                    app = UnifiedManagementGUI(self.auth)
                    app.run()
            except Exception as e:
                print(f"Error returning to main menu: {e}")
                import traceback
                traceback.print_exc()
    def create_main_menu_button(self):
            """Place a dedicated top-right navigation button"""
            try:
                if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                    return
            except Exception:
                pass

            self.main_menu_button = ttk.Button(
                self.root,
                text=_("common.return_to_main_menu"),
                command=self.return_to_main_menu,
            )
            self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    def create_widgets(self):
            """Create main GUI widgets"""
            # Main container
            main_frame = ttk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Title
            title_frame = ttk.Frame(main_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            title_label = ttk.Label(title_frame,
                                   text=_("attendance.title"),
                                   font=('Arial', 20, 'bold'))
            title_label.pack(side=tk.LEFT)

            # Status label
            self.status_label = ttk.Label(title_frame, text=_("common.ready"), foreground=self.colors['success'])
            self.status_label.pack(side=tk.RIGHT)

            # Main notebook
            self.notebook = ttk.Notebook(main_frame, style='Custom.TNotebook')
            self.notebook.pack(fill=tk.BOTH, expand=True)

            # Create tabs
            self.create_dashboard_tab()
            self.create_attendance_tab()
            self.create_students_tab()
            self.create_reports_tab()
            self.create_analytics_tab()
            self.create_settings_tab()
            self.create_admin_tab()
    def run_original_cli(self):
            """Run original CLI in a separate thread"""
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                messagebox.showerror(_("common.error"), _("attendance.messages.original_cli_not_available"))
                return

            def run_cli():
                try:
                    display_attendance_menu()
                except Exception as e:
                    print(f"CLI error: {e}")

            threading.Thread(target=run_cli, daemon=True).start()
            messagebox.showinfo(_("attendance.messages.cli_started"), _("attendance.messages.cli_started_message"))
    def update_status(self, message, status_type="info"):
            """Update status label"""
            color_map = {
                "info": self.colors['dark'],
                "success": self.colors['success'],
                "warning": self.colors['warning'],
                "error": self.colors['danger']
            }

            self.status_label.config(text=message, foreground=color_map.get(status_type, self.colors['dark']))

            # Auto-clear status after 5 seconds
            self.root.after(5000, lambda: self.status_label.config(text=_("common.ready"), foreground=self.colors['success']))
    def __init__(self, root, auth_manager=None):
            self.root = root
            self.auth = auth_manager
            self.root.title(_("attendance.title"))
            self.root.geometry("1400x900")
            self.root.minsize(1200, 800)

            # Initialize original systems if available
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                try:
                    init_enhanced_attendance_db()
                    create_missing_tables()
                    self.qr_system = QRAttendanceSystem()
                    self.geo_system = GeofencingSystem() if GEOFENCING_SUPPORT else None
                    self.face_system = FaceRecognitionSystem() if FACE_RECOGNITION_SUPPORT else None
                    self.notification_system = EnhancedNotificationSystem()
                    self.analytics = AttendancePredictiveAnalytics()
                    self.backup_system = BackupRecoverySystem()
                except Exception as e:
                    print(f"Warning: Could not initialize some systems: {e}")
                    self.qr_system = None
                    self.geo_system = None
                    self.face_system = None
                    self.notification_system = None
                    self.analytics = None
                    self.backup_system = None

            # Style configuration
            self.style = ttk.Style()
            self.style.theme_use('clam')

            # Configure colors
            self.colors = {
                'primary': '#2C3E50',
                'secondary': '#3498DB',
                'success': '#27AE60',
                'warning': '#F39C12',
                'danger': '#E74C3C',
                'light': '#ECF0F1',
                'dark': '#34495E'
            }

            self.setup_styles()
            self.create_widgets()
            self.setup_menu()

            # Initialize data
            self.refresh_data()


# Bind methods from modular files to AttendanceGUI class

# Dashboard tab methods
AttendanceGUI.create_dashboard_tab = dashboard_tab.create_dashboard_tab
AttendanceGUI.create_dashboard_charts = dashboard_tab.create_dashboard_charts
AttendanceGUI.update_dashboard_charts = dashboard_tab.update_dashboard_charts
AttendanceGUI.update_dashboard_stats = dashboard_tab.update_dashboard_stats
AttendanceGUI.refresh_recent_activity = dashboard_tab.refresh_recent_activity
AttendanceGUI.create_sample_charts = dashboard_tab.create_sample_charts

# Attendance tab methods
AttendanceGUI.create_attendance_tab = attendance_tab.create_attendance_tab
AttendanceGUI.refresh_attendance_data = attendance_tab.refresh_attendance_data
AttendanceGUI.manual_attendance = attendance_tab.manual_attendance
AttendanceGUI.batch_attendance = attendance_tab.batch_attendance
AttendanceGUI.qr_attendance = attendance_tab.qr_attendance
AttendanceGUI.geo_attendance = attendance_tab.geo_attendance
AttendanceGUI.face_attendance = attendance_tab.face_attendance
AttendanceGUI.refresh_modules = attendance_tab.refresh_modules
AttendanceGUI.on_module_selected = attendance_tab.on_module_selected
AttendanceGUI.load_module_students = attendance_tab.load_module_students
AttendanceGUI.edit_attendance_record = attendance_tab.edit_attendance_record

# Students tab methods
AttendanceGUI.create_students_tab = students_tab.create_students_tab
AttendanceGUI.refresh_students_data = students_tab.refresh_students_data
AttendanceGUI.filter_students = students_tab.filter_students
AttendanceGUI.add_student = students_tab.add_student
AttendanceGUI.edit_student = students_tab.edit_student
AttendanceGUI.delete_student = students_tab.delete_student
AttendanceGUI.show_student_management_redirect = students_tab.show_student_management_redirect

# Reports tab methods
AttendanceGUI.create_reports_tab = reports_tab.create_reports_tab
AttendanceGUI.generate_student_report = reports_tab.generate_student_report
AttendanceGUI.generate_module_report = reports_tab.generate_module_report
AttendanceGUI.generate_executive_report = reports_tab.generate_executive_report
AttendanceGUI.generate_at_risk_report = reports_tab.generate_at_risk_report
AttendanceGUI.generate_trends_report = reports_tab.generate_trends_report
AttendanceGUI.generate_custom_report = reports_tab.generate_custom_report
AttendanceGUI.generate_quick_report = reports_tab.generate_quick_report
AttendanceGUI._send_attendance_alert_emails = reports_tab._send_attendance_alert_emails
AttendanceGUI._send_email_via_gui = reports_tab._send_email_via_gui
AttendanceGUI._show_attendance_email_fallback = reports_tab._show_attendance_email_fallback

# Analytics tab methods
AttendanceGUI.create_analytics_tab = analytics_tab.create_analytics_tab
AttendanceGUI.train_prediction_model = analytics_tab.train_prediction_model
AttendanceGUI.on_model_trained = analytics_tab.on_model_trained
AttendanceGUI.predict_student_risk = analytics_tab.predict_student_risk
AttendanceGUI.batch_risk_analysis = analytics_tab.batch_risk_analysis
AttendanceGUI.open_gamification = analytics_tab.open_gamification

# Settings and admin tab methods
AttendanceGUI.create_settings_tab = settings_admin_tabs.create_settings_tab
AttendanceGUI.create_admin_tab = settings_admin_tabs.create_admin_tab
AttendanceGUI.create_general_settings = settings_admin_tabs.create_general_settings
AttendanceGUI.create_notifications_settings = settings_admin_tabs.create_notifications_settings
AttendanceGUI.create_features_settings = settings_admin_tabs.create_features_settings
AttendanceGUI.create_thresholds_settings = settings_admin_tabs.create_thresholds_settings
AttendanceGUI.save_thresholds = settings_admin_tabs.save_thresholds
AttendanceGUI.save_notification_settings = settings_admin_tabs.save_notification_settings
AttendanceGUI.save_feature_settings = settings_admin_tabs.save_feature_settings
AttendanceGUI.load_system_info = settings_admin_tabs.load_system_info
AttendanceGUI.refresh_audit_logs = settings_admin_tabs.refresh_audit_logs
AttendanceGUI.export_audit_logs = settings_admin_tabs.export_audit_logs
AttendanceGUI.backup_database = settings_admin_tabs.backup_database
AttendanceGUI.restore_database = settings_admin_tabs.restore_database
AttendanceGUI.cleanup_old_data = settings_admin_tabs.cleanup_old_data
AttendanceGUI.import_data = settings_admin_tabs.import_data
AttendanceGUI.export_data = settings_admin_tabs.export_data
AttendanceGUI.open_qr_generator = settings_admin_tabs.open_qr_generator
AttendanceGUI.open_face_recognition = settings_admin_tabs.open_face_recognition
AttendanceGUI.open_geofencing = settings_admin_tabs.open_geofencing
AttendanceGUI.open_biometrics_management = settings_admin_tabs.open_biometrics_management
AttendanceGUI.open_attendance_alerts = settings_admin_tabs.open_attendance_alerts
AttendanceGUI.open_predictive_analytics = settings_admin_tabs.open_predictive_analytics
AttendanceGUI.open_backup_recovery = settings_admin_tabs.open_backup_recovery
AttendanceGUI.open_api_management = settings_admin_tabs.open_api_management
AttendanceGUI.open_parent_notifications = settings_admin_tabs.open_parent_notifications
AttendanceGUI.open_lms_integration = settings_admin_tabs.open_lms_integration
AttendanceGUI.open_calendar_sync = settings_admin_tabs.open_calendar_sync
AttendanceGUI.view_audit_logs = settings_admin_tabs.view_audit_logs
AttendanceGUI.run_diagnostics = settings_admin_tabs.run_diagnostics
AttendanceGUI.database_maintenance = settings_admin_tabs.database_maintenance
AttendanceGUI.update_notification_settings = settings_admin_tabs.update_notification_settings
AttendanceGUI.manage_attendance_policies = settings_admin_tabs.manage_attendance_policies

# Misc tab methods
AttendanceGUI.show_help = misc_tab.show_help
AttendanceGUI.show_about = misc_tab.show_about


# Main application runner functions
def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = AttendanceGUI(root)

    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

    root.mainloop()


def main():
    """Main entry point with CLI compatibility"""
    import sys

    if len(sys.argv) > 1:
        # Command line arguments provided
        arg = sys.argv[1].lower()

        if arg in ['--gui', '-g']:
            print("Starting GUI application...")
            run_gui()
        elif arg in ['--cli', '-c']:
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                print("Starting CLI application...")
                display_attendance_menu()
            else:
                print("CLI not available. Original functions not found.")
                print("Starting GUI instead...")
                run_gui()
        elif arg in ['--help', '-h']:
            print("Enhanced Attendance Tracking System")
            print("Usage:")
            print("  python attendance_gui.py [--gui|-g]    Start GUI (default)")
            print("  python attendance_gui.py [--cli|-c]    Start CLI")
            print("  python attendance_gui.py [--help|-h]   Show this help")
        else:
            print(f"Unknown argument: {arg}")
            print("Use --help for usage information")
    else:
        # No arguments - check if running in interactive environment
        try:
            # Try to detect if we're in a GUI environment
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            root.destroy()

            # GUI available, start GUI
            print("Starting GUI application...")
            run_gui()

        except (ImportError, tk.TclError):
            # No GUI available, start CLI
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                print("GUI not available. Starting CLI...")
                display_attendance_menu()
            else:
                print("Neither GUI nor CLI is available.")
                print("Please install tkinter for GUI or ensure attendance_tracker.py is available for CLI.")


# Backwards compatibility functions
def start_gui():
    """Start the GUI application - backwards compatibility"""
    run_gui()


def start_cli():
    """Start the CLI application - backwards compatibility"""
    if ORIGINAL_FUNCTIONS_AVAILABLE:
        display_attendance_menu()
    else:
        print("CLI not available. Starting GUI instead...")
        run_gui()


# Auto-detection and startup
if __name__ == "__main__":
    main()
else:
    # Module imported - provide both options
    print("Enhanced Attendance GUI System loaded.")
    print("Use start_gui() for GUI or start_cli() for CLI")
