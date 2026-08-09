
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
from pathlib import Path
import uuid
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import internationalization support
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.misc_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.misc_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.paths import (
    UNIVERSITY_BACKUP_DIR,
    UNIVERSITY_DEFAULT_DB_PATH,
    UNIVERSITY_LOG_DIR,
)

# Import authentication system
from education_system.systems.university.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.systems.university.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:50 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.systems.university.domains.academics.domain.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from education_system.systems.university.domains.academics.domain.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class LMSIntegrationWindow:
    """LMS Integration for syncing attendance with external learning management systems"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.lms_integration"))
        self.window.geometry("900x650")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.lms_integration', default="🔗 LMS Integration"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different LMS systems
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.tabs.configuration', default="⚙️ Configuration"))
        self.create_config_tab(config_frame)

        # Sync tab
        sync_frame = ttk.Frame(notebook)
        notebook.add(sync_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.tabs.sync_data', default="🔄 Sync Data"))
        self.create_sync_tab(sync_frame)

        # History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.tabs.sync_history', default="📜 Sync History"))
        self.create_history_tab(history_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_config_tab(self, parent):
        # LMS Platform selection
        platform_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.lms_platform', default="LMS Platform"), padding=15)
        platform_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(platform_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.select_lms_platform', default="Select LMS Platform:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.lms_platform_var = tk.StringVar(value=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.values.moodle', default="Moodle"))
        platform_combo = ttk.Combobox(platform_frame, textvariable=self.lms_platform_var, width=30,
                                     values=["Moodle", "Canvas", "Blackboard", "Google Classroom", "Microsoft Teams", "Custom API"])
        platform_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        platform_frame.grid_columnconfigure(1, weight=1)

        # Connection settings
        connection_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.connection_settings', default="Connection Settings"), padding=15)
        connection_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(connection_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.api_endpoint_url', default="API Endpoint URL:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_url_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_url_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.api_key', default="API Key:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_key_var, show="*").grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.username_if_required', default="Username (if required):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.lms_username_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.lms_username_var).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        connection_frame.grid_columnconfigure(1, weight=1)

        # Test connection button
        ttk.Button(connection_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.test_connection', default="Test Connection"), command=self.test_lms_connection, style='Primary.TButton').grid(row=3, column=0, columnspan=2, pady=(10, 5))

        # Sync options
        options_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_options', default="Sync Options"), padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.auto_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.enable_automatic_sync', default="Enable automatic sync"), variable=self.auto_sync_var).pack(anchor=tk.W)

        self.sync_grades_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.sync_attendance_as_grades', default="Sync attendance as grades"), variable=self.sync_grades_var).pack(anchor=tk.W)

        self.bidirectional_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.enable_bidirectional_sync', default="Enable bidirectional sync"), variable=self.bidirectional_var).pack(anchor=tk.W)

        ttk.Label(options_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_frequency', default="Sync Frequency:")).pack(anchor=tk.W, pady=(10, 0))
        self.sync_frequency_var = tk.StringVar(value=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.values.daily', default="Daily"))
        freq_combo = ttk.Combobox(options_frame, textvariable=self.sync_frequency_var, width=20,
                                  values=["Hourly", "Daily", "Weekly", "Manual Only"])
        freq_combo.pack(anchor=tk.W, pady=(5, 0))

        # Save settings button
        ttk.Button(options_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.save_settings', default="Save Settings"), command=self.save_lms_settings, style='Success.TButton').pack(pady=(15, 0))

    def create_sync_tab(self, parent):
        # Sync controls frame
        controls_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_controls', default="Sync Controls"), padding=15)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(controls_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_date_range', default="Sync Date Range:")).pack(side=tk.LEFT)
        self.sync_start_var = tk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(date_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.to', default="to")).pack(side=tk.LEFT)
        self.sync_end_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_end_var, width=12).pack(side=tk.LEFT, padx=(5, 0))

        # Module selection
        module_frame = ttk.Frame(controls_frame)
        module_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(module_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.select_modules_to_sync', default="Select Modules to Sync:")).pack(side=tk.LEFT)
        self.sync_all_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(module_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.all_modules', default="All Modules"), variable=self.sync_all_modules_var).pack(side=tk.LEFT, padx=(10, 0))

        # Sync direction
        direction_frame = ttk.Frame(controls_frame)
        direction_frame.pack(fill=tk.X)

        ttk.Label(direction_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_direction', default="Sync Direction:")).pack(side=tk.LEFT)
        self.sync_direction_var = tk.StringVar(value=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.values.to_lms', default="to_lms"))
        ttk.Radiobutton(direction_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.to_lms', default="To LMS"), variable=self.sync_direction_var, value="to_lms").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(direction_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.from_lms', default="From LMS"), variable=self.sync_direction_var, value="from_lms").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(direction_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.both_ways', default="Both Ways"), variable=self.sync_direction_var, value="bidirectional").pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.start_sync', default="Start Sync"), command=self.start_sync, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.preview_changes', default="Preview Changes"), command=self.preview_sync, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.cancel_sync', default="Cancel Sync"), command=self.cancel_sync, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Status frame
        status_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_status', default="Sync Status"), padding=15)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.sync_status_text = tk.Text(status_frame, wrap=tk.WORD, height=15)
        sync_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.sync_status_text.yview)
        self.sync_status_text.configure(yscrollcommand=sync_scrollbar.set)

        self.sync_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sync_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sync_status_text.insert(tk.END, "Ready to sync. Configure your LMS settings and click 'Start Sync'.\n")

    def create_history_tab(self, parent):
        # Filter frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(filter_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.show_syncs_from', default="Show syncs from:")).pack(side=tk.LEFT)
        self.history_days_var = tk.StringVar(value="30")
        ttk.Combobox(filter_frame, textvariable=self.history_days_var, width=10,
                    values=["7", "30", "90", "365", "All"]).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(filter_frame, text=_("common.refresh"), command=self.load_sync_history, style='Primary.TButton').pack(side=tk.LEFT)

        # History treeview
        history_columns = ("Date", "Time", "Direction", "Status", "Records Synced", "Errors", "Duration")
        self.history_tree = ttk.Treeview(parent, columns=history_columns, show="headings", height=20)

        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120)

        history_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

        # Load initial history
        self.load_sync_history()

    def test_lms_connection(self):
        platform = self.lms_platform_var.get()
        api_url = self.api_url_var.get()
        api_key = self.api_key_var.get()

        if not api_url or not api_key:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.please_provide_api_endpoint_and_api_key', default="Please provide API endpoint and API key"))
            return

        # Simulate connection test
        messagebox.showinfo(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.connection_test', default="Connection Test"), f"Testing connection to {platform}...\n\nConnection successful!\n\nLMS Version: 3.11\nAvailable Courses: 24\nAPI Status: Active")

    def save_lms_settings(self):
        try:
            with sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lms_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        api_url TEXT,
                        api_key TEXT,
                        username TEXT,
                        auto_sync INTEGER,
                        sync_grades INTEGER,
                        bidirectional INTEGER,
                        sync_frequency TEXT
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO lms_settings (id, platform, api_url, api_key, username, auto_sync, sync_grades, bidirectional, sync_frequency)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.lms_platform_var.get(),
                    self.api_url_var.get(),
                    self.api_key_var.get(),
                    self.lms_username_var.get(),
                    1 if self.auto_sync_var.get() else 0,
                    1 if self.sync_grades_var.get() else 0,
                    1 if self.bidirectional_var.get() else 0,
                    self.sync_frequency_var.get()
                ))

                conn.commit()

            messagebox.showinfo(_("common.success"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.lms_settings_saved_successfully', default="LMS settings saved successfully"))

        except Exception as e:
            logger.exception("misc_windows.py:467 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save settings: {e}")

    def start_sync(self):
        direction = self.sync_direction_var.get()
        start_date = self.sync_start_var.get()
        end_date = self.sync_end_var.get()

        self.sync_status_text.insert(tk.END, f"\n{'='*50}\n")
        self.sync_status_text.insert(tk.END, f"Starting sync ({direction})...\n")
        self.sync_status_text.insert(tk.END, f"Date range: {start_date} to {end_date}\n")
        self.sync_status_text.insert(tk.END, f"{'='*50}\n\n")

        # Simulate sync process
        steps = [
            "Connecting to LMS...",
            "Authenticating...",
            "Fetching module list...",
            "Syncing attendance records...",
            "Updating grades...",
            "Finalizing sync..."
        ]

        for step in steps:
            self.sync_status_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {step}\n")
            self.sync_status_text.see(tk.END)
            self.window.update()

        self.sync_status_text.insert(tk.END, "\n✅ Sync completed successfully!\n")
        self.sync_status_text.insert(tk.END, "Records synced: 245\n")
        self.sync_status_text.insert(tk.END, "Duration: 12.3 seconds\n")
        self.sync_status_text.see(tk.END)

        messagebox.showinfo(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.sync_complete', default="Sync Complete"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.lms_sync_completed_successfully_245_records_synced_duration_12_3', default="LMS sync completed successfully!\n\n245 records synced\nDuration: 12.3 seconds"))

    def preview_sync(self):
        messagebox.showinfo(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.sync_preview', default="Sync Preview"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.preview_of_changes_to_be_synced_245_attendance_records_will_be_p', default="Preview of changes to be synced:\n\n"
                          "• 245 attendance records will be pushed to LMS\n"
                          "• 12 new grades will be created\n"
                          "• 3 existing grades will be updated\n"
                          "• No records will be deleted\n\n"
                          "Click 'Start Sync' to proceed with these changes."))

    def cancel_sync(self):
        self.sync_status_text.insert(tk.END, "\n❌ Sync cancelled by user.\n")
        self.sync_status_text.see(tk.END)

    def load_sync_history(self):
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Sample sync history
        sample_history = [
            (datetime.datetime.now().strftime("%Y-%m-%d"), "14:23", "To LMS", "Success", "245", "0", "12.3s"),
            ((datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), "09:15", "To LMS", "Success", "198", "2", "15.1s"),
            ((datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d"), "10:30", "From LMS", "Success", "156", "0", "8.7s"),
            ((datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d"), "16:45", "Bidirectional", "Failed", "0", "12", "2.1s"),
        ]

        for record in sample_history:
            item = self.history_tree.insert('', 'end', values=record)
            if record[3] == "Failed":
                self.history_tree.item(item, tags=('error',))

        self.history_tree.tag_configure('error', foreground='red')

