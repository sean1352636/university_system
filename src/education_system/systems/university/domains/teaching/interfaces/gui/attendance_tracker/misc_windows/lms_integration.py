
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
    from education_system.systems.university.domains.teaching.domain.attendance.attendance_tracker import (
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
    from education_system.systems.university.domains.teaching.domain.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

from education_system.systems.university.domains.teaching.domain.attendance import lms_sync
from education_system.platform.delivery.gui.tk_threads import start_thread, ui

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class LMSIntegrationWindow:
    """LMS Integration for syncing attendance with external learning management systems"""
    def __init__(self, parent, run_by=""):
        self.parent = parent
        self.run_by = run_by or ""
        self._cancel = threading.Event()
        self._sync_running = False

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.lms_integration"))
        self.window.geometry("900x650")
        self.window.transient(parent)

        self.create_widgets()
        self.load_lms_settings()

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
                                     values=list(lms_sync.PLATFORMS), state="readonly")
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
        # The token is kept in var/secrets, never shown back; blank keeps it.
        self.token_status_var = tk.StringVar()
        ttk.Label(connection_frame, textvariable=self.token_status_var, foreground="gray").grid(row=1, column=2, sticky=tk.W, padx=(8, 0))

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
        ttk.Checkbutton(module_frame, text=_t('gui.academics.attendance_tracker.misc_windows.lms_integration.buttons.all_modules', default="All Modules"), variable=self.sync_all_modules_var, command=self._toggle_module_combo).pack(side=tk.LEFT, padx=(10, 0))
        # Used when "All Modules" is off: modules that have attendance recorded.
        self.sync_module_var = tk.StringVar()
        self.sync_module_combo = ttk.Combobox(module_frame, textvariable=self.sync_module_var, width=18, state="disabled")
        self.sync_module_combo.pack(side=tk.LEFT, padx=(10, 0))
        try:
            self.sync_module_combo["values"] = lms_sync.module_codes()
        except Exception:
            logger.exception("Could not list attendance modules for LMS sync")

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

        self.sync_status_text.insert(tk.END, "Ready to sync. Configure your LMS settings and click 'Start Sync'.\n"
                                     "Canvas and Custom API receive a live push; other platforms, or an LMS that\n"
                                     "is not configured or reachable, get the LMS-importable CSV export.\n")

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

    def _toggle_module_combo(self):
        self.sync_module_combo.configure(state="disabled" if self.sync_all_modules_var.get() else "readonly")

    def _selected_module(self):
        if self.sync_all_modules_var.get():
            return None
        return self.sync_module_var.get().strip() or None

    def _token(self):
        """The token typed in the window, else the stored one."""
        return self.api_key_var.get().strip() or lms_sync.read_token()

    def _date_range(self):
        start, end = self.sync_start_var.get().strip(), self.sync_end_var.get().strip()
        for value in (start, end):
            if value:
                datetime.date.fromisoformat(value)
        return start or None, end or None

    def load_lms_settings(self):
        try:
            settings = lms_sync.load_settings()
        except Exception:
            logger.exception("Could not load LMS settings")
            settings = {}
        if settings:
            self.lms_platform_var.set(settings.get("platform") or "Moodle")
            self.api_url_var.set(settings.get("api_url") or "")
            self.lms_username_var.set(settings.get("username") or "")
            self.auto_sync_var.set(bool(settings.get("auto_sync")))
            self.sync_grades_var.set(bool(settings.get("sync_grades")))
            self.bidirectional_var.set(bool(settings.get("bidirectional")))
            self.sync_frequency_var.set(settings.get("sync_frequency") or "Manual Only")
        self.token_status_var.set("Token stored (leave blank to keep)" if lms_sync.read_token() else "No token stored")

    def test_lms_connection(self):
        platform = self.lms_platform_var.get()
        api_url = self.api_url_var.get()
        api_key = self._token()

        if not (api_url or platform in lms_sync.DEFAULT_URLS) or not api_key:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.please_provide_api_endpoint_and_api_key', default="Please provide API endpoint and API key"), parent=self.window)
            return

        username = self.lms_username_var.get().strip()

        def worker():
            try:
                lines = lms_sync.test_connection(platform, api_url, api_key, username)
            except lms_sync.LMSError as exc:
                ui(self.window, messagebox.showerror, _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.connection_test', default="Connection Test"),
                   f"Connection to {platform} failed.\n\n{exc}", parent=self.window)
                return
            except Exception as exc:
                logger.exception("LMS connection test failed")
                ui(self.window, messagebox.showerror, _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.connection_test', default="Connection Test"),
                   f"Connection to {platform} failed.\n\n{exc}", parent=self.window)
                return
            body = "\n".join(f"{label}: {value if value not in (None, '') else 'not reported'}" for label, value in lines)
            ui(self.window, messagebox.showinfo, _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.connection_test', default="Connection Test"),
               f"Connected to {platform}.\n\n{body}", parent=self.window)

        start_thread(self.window, worker)

    def save_lms_settings(self):
        try:
            # The token goes to var/secrets; a plaintext one left in the
            # old api_key column is moved there by this save.
            lms_sync.save_settings({
                "platform": self.lms_platform_var.get(),
                "api_url": self.api_url_var.get(),
                "username": self.lms_username_var.get(),
                "auto_sync": self.auto_sync_var.get(),
                "sync_grades": self.sync_grades_var.get(),
                "bidirectional": self.bidirectional_var.get(),
                "sync_frequency": self.sync_frequency_var.get(),
            }, self.api_key_var.get())
            self.api_key_var.set("")
            self.token_status_var.set("Token stored (leave blank to keep)" if lms_sync.read_token() else "No token stored")

            messagebox.showinfo(_("common.success"), _t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.lms_settings_saved_successfully', default="LMS settings saved successfully"), parent=self.window)

        except Exception as e:
            logger.exception("misc_windows.py:467 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save settings: {e}", parent=self.window)

    def _status(self, line):
        """Append a timestamped line to the status box (main thread only)."""
        self.sync_status_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {line}\n")
        self.sync_status_text.see(tk.END)

    def start_sync(self):
        if self._sync_running:
            messagebox.showinfo(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.labels.sync_status', default="Sync Status"), "A sync is already running.", parent=self.window)
            return
        try:
            start_date, end_date = self._date_range()
        except ValueError:
            messagebox.showwarning(_("common.warning"), "Dates must be YYYY-MM-DD.", parent=self.window)
            return
        direction = self.sync_direction_var.get()
        module = self._selected_module()
        if not self.sync_all_modules_var.get() and not module:
            messagebox.showwarning(_("common.warning"), "Choose a module, or tick All Modules.", parent=self.window)
            return

        options = dict(platform=self.lms_platform_var.get(), api_url=self.api_url_var.get(),
                       token=self._token(), username=self.lms_username_var.get().strip(),
                       direction=direction, sync_grades=self.sync_grades_var.get(),
                       date_from=start_date, date_to=end_date, module_code=module,
                       run_by=self.run_by)

        self.sync_status_text.insert(tk.END, f"\n{'='*50}\n")
        self.sync_status_text.insert(tk.END, f"Starting sync ({direction})...\n")
        self.sync_status_text.insert(tk.END, f"Date range: {start_date or 'start'} to {end_date or 'today'}"
                                     f"{' - module ' + module if module else ''}\n")
        self.sync_status_text.insert(tk.END, f"{'='*50}\n\n")
        self.sync_status_text.see(tk.END)

        self._cancel.clear()
        self._sync_running = True

        def worker():
            try:
                result = lms_sync.run_sync(**options,
                                           log=lambda line: ui(self.window, self._status, line),
                                           cancelled=self._cancel.is_set)
            except Exception as exc:
                logger.exception("LMS sync failed")
                result = {"status": "Failed", "records": 0, "errors": 1,
                          "duration": 0, "mode": "", "export_path": None, "detail": str(exc)}
            ui(self.window, self._sync_finished, result)

        start_thread(self.window, worker)

    def _sync_finished(self, result):
        self._sync_running = False
        status = result.get("status")
        ok = status in ("Success", "Exported")
        self.sync_status_text.insert(tk.END, f"\n{'✅' if ok else '⚠️'} Sync {status.lower()}.\n")
        self.sync_status_text.insert(tk.END, f"Records {'exported' if result.get('mode') == 'csv' else 'synced'}: {result.get('records', 0)}\n")
        if result.get("errors"):
            self.sync_status_text.insert(tk.END, f"Errors: {result['errors']}\n")
        self.sync_status_text.insert(tk.END, f"Duration: {result.get('duration', 0)} seconds\n")
        self.sync_status_text.see(tk.END)
        self.load_sync_history()

        summary = (f"Status: {status}\n"
                   f"Records {'exported' if result.get('mode') == 'csv' else 'synced'}: {result.get('records', 0)}\n"
                   f"Errors: {result.get('errors', 0)}\n"
                   f"Duration: {result.get('duration', 0)} seconds")
        if result.get("export_path"):
            summary += f"\n\nCSV written to:\n{result['export_path']}"
        show = messagebox.showinfo if ok or status == "Nothing to sync" else messagebox.showwarning
        show(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.sync_complete', default="Sync Complete"), summary, parent=self.window)

    def preview_sync(self):
        try:
            start_date, end_date = self._date_range()
            records = lms_sync.collect_records(start_date, end_date, self._selected_module())
        except ValueError:
            messagebox.showwarning(_("common.warning"), "Dates must be YYYY-MM-DD.", parent=self.window)
            return
        except Exception as e:
            logger.exception("LMS preview failed")
            messagebox.showerror(_("common.error"), f"Could not read attendance: {e}", parent=self.window)
            return

        platform = self.lms_platform_var.get()
        grades = lms_sync.attendance_grades(records)
        top = tk.Toplevel(self.window)
        top.title(_t('gui.academics.attendance_tracker.misc_windows.lms_integration.dialogs.sync_preview', default="Sync Preview"))
        top.geometry("820x480")
        top.transient(self.window)

        if platform in lms_sync.PUSH_PLATFORMS and self._token() and self.api_url_var.get().strip():
            target = f"pushed to {platform}"
        else:
            target = "written to the LMS-importable CSV"
        summary = (f"{len(records)} attendance record(s) will be {target}; "
                   f"{len(grades)} student/module attendance grade(s). Nothing is deleted.")
        ttk.Label(top, text=summary, wraplength=780).pack(anchor=tk.W, padx=10, pady=(10, 5))

        columns = ("Student", "Name", "Module", "Date", "Status")
        tree = ttk.Treeview(top, columns=columns, show="headings")
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=140)
        scroll = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        ttk.Button(top, text=_("common.close"), command=top.destroy).pack(side=tk.BOTTOM, pady=8)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

        if not records:
            tree.insert('', 'end', values=("No records yet", "", "", "", ""))
        for rec in records:
            tree.insert('', 'end', values=(rec["student_id"], rec["name"], rec["module_code"],
                                           rec["session_date"], rec["status"]))

    def cancel_sync(self):
        if not self._sync_running:
            self.sync_status_text.insert(tk.END, "\nNo sync is running.\n")
            self.sync_status_text.see(tk.END)
            return
        # Stops between modules; a request already sent cannot be recalled.
        self._cancel.set()
        self.sync_status_text.insert(tk.END, "\n❌ Sync cancelled by user (stops after the current module).\n")
        self.sync_status_text.see(tk.END)

    def load_sync_history(self):
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        days = self.history_days_var.get().strip()
        try:
            runs = lms_sync.sync_history(None if days == "All" else int(days or 30))
        except Exception:
            logger.exception("Could not read the LMS sync log")
            runs = []

        directions = {"to_lms": "To LMS", "from_lms": "From LMS", "bidirectional": "Bidirectional"}
        for run in runs:
            when = str(run["started_at"] or "")
            date, _sep, clock = when.partition("T")
            status = run["status"] + (" (CSV)" if run["mode"] == "csv" else "")
            item = self.history_tree.insert('', 'end', values=(
                date, clock[:5], directions.get(run["direction"], run["direction"] or ""),
                status, run["records"], run["errors"],
                f"{run['duration']}s" if run["duration"] is not None else ""))
            if run["status"] in ("Failed", "Partial"):
                self.history_tree.item(item, tags=('error',))

        if not runs:
            self.history_tree.insert('', 'end', values=("No records yet", "", "", "", "", "", ""))

        self.history_tree.tag_configure('error', foreground='red')
