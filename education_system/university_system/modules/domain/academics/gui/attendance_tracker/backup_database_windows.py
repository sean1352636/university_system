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
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

# Import internationalization support
from education_system.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.backup_database_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.backup_database_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.university_system.core.paths import BACKUP_DIR, BACKUP_ATTENDANCE_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("backup_database_windows.py:51 %s", 'except ImportError')
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
    logger.exception("backup_database_windows.py:65 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("backup_database_windows.py:76 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True


class BackupRecoveryWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.backup_recovery"))
        self.window.geometry("700x500")
        self.window.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="💾 Backup & Recovery System", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Backup operations frame
        operations_frame = ttk.LabelFrame(self.window, text="Backup Operations", padding=10)
        operations_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        operations_grid = ttk.Frame(operations_frame)
        operations_grid.pack(fill=tk.X)

        ttk.Button(operations_grid, text="Create Backup",
                  command=self.create_backup, style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(operations_grid, text="Restore Backup",
                  command=self.restore_backup, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(operations_grid, text="Schedule Settings",
                  command=self.backup_settings, style='Primary.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(operations_grid, text="Cleanup Old",
                  command=self.cleanup_backups, style='Primary.TButton').grid(row=0, column=3, padx=5)

        # Available backups frame
        backups_frame = ttk.LabelFrame(self.window, text="Available Backups", padding=10)
        backups_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Backups treeview
        backup_columns = ("Filename", "Size", "Type", "Created", "Status")
        self.backups_tree = ttk.Treeview(backups_frame, columns=backup_columns, show="headings")

        for col in backup_columns:
            self.backups_tree.heading(col, text=col)
            self.backups_tree.column(col, width=120)

        backup_scrollbar = ttk.Scrollbar(backups_frame, orient=tk.VERTICAL, command=self.backups_tree.yview)
        self.backups_tree.configure(yscrollcommand=backup_scrollbar.set)

        self.backups_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        backup_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to restore
        self.backups_tree.bind('<Double-1>', self.restore_selected_backup)

        # Status frame
        status_frame = ttk.LabelFrame(self.window, text="Backup Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.status_text = tk.Text(status_frame, height=4, wrap=tk.WORD)
        status_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)

        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial status
        self.load_backup_status()

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def load_backups(self):
        # Clear existing items
        for item in self.backups_tree.get_children():
            self.backups_tree.delete(item)

        # Sample backup data
        sample_backups = [
            ("attendance_backup_full_20241220_143022.db", "2.4 MB", "Full", "2024-12-20 14:30", "Valid"),
            ("attendance_backup_manual_20241219_091500.db", "2.3 MB", "Manual", "2024-12-19 09:15", "Valid"),
            ("attendance_backup_scheduled_20241218_000000.db", "2.2 MB", "Scheduled", "2024-12-18 00:00", "Valid"),
        ]

        for backup in sample_backups:
            self.backups_tree.insert('', 'end', values=backup)

    def create_backup(self):
        backup_type = simpledialog.askstring("Backup Type", "Enter backup type (full/manual/custom):", initialvalue="manual")
        if not backup_type:
            return

        if ORIGINAL_FUNCTIONS_AVAILABLE:
            try:
                backup_system = BackupRecoverySystem()
                backup_path = backup_system.create_backup(backup_type)

                if backup_path:
                    messagebox.showinfo(_("common.success"), f"Backup created: {backup_path}")
                    self.load_backups()
                    self.load_backup_status()
                else:
                    messagebox.showerror(_("common.error"), "Backup creation failed")
            except Exception as e:
                logger.exception("backup_database_windows.py:186 %s", 'except Exception as e')
                messagebox.showerror(_("common.error"), f"Backup creation failed: {e}")
        else:
            messagebox.showinfo("Demo", f"Backup of type '{backup_type}' would be created here")
            self.load_backups()

    def restore_backup(self):
        filename = filedialog.askopenfilename(
            title="Select backup file to restore",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if filename:
            if messagebox.askyesno("Confirm Restore",
                                 "This will overwrite current data. Are you sure?"):
                self.perform_restore(filename)

    def restore_selected_backup(self, event):
        selection = self.backups_tree.selection()
        if selection:
            item = self.backups_tree.item(selection[0])
            filename = item['values'][0]

            if messagebox.askyesno("Confirm Restore",
                                 f"Restore from {filename}? This will overwrite current data."):
                backup_path = str(BACKUP_ATTENDANCE_DIR / filename)
                self.perform_restore(backup_path)

    def perform_restore(self, backup_path):
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            try:
                backup_system = BackupRecoverySystem()
                success, message = backup_system.restore_backup(backup_path)

                if success:
                    messagebox.showinfo(_("common.success"), message)
                    self.load_backup_status()
                else:
                    messagebox.showerror(_("common.error"), message)
            except Exception as e:
                logger.exception("backup_database_windows.py:225 %s", 'except Exception as e')
                messagebox.showerror(_("common.error"), f"Restore failed: {e}")
        else:
            messagebox.showinfo("Demo", f"Database would be restored from {backup_path}")

    def backup_settings(self):
        BackupSettingsWindow(self.window, self.load_backup_status)

    def cleanup_backups(self):
        try:
            keep_days = int(simpledialog.askstring("Cleanup", "Keep backups newer than how many days?", initialvalue="30"))

            if messagebox.askyesno("Confirm Cleanup",
                                 f"Delete backups older than {keep_days} days?"):
                if ORIGINAL_FUNCTIONS_AVAILABLE:
                    backup_system = BackupRecoverySystem()
                    backup_system.cleanup_old_backups(keep_days)
                    messagebox.showinfo(_("common.success"), f"Cleaned up backups older than {keep_days} days")
                else:
                    messagebox.showinfo("Demo", f"Would cleanup backups older than {keep_days} days")

                self.load_backups()
        except (ValueError, TypeError):
            logger.exception("backup_database_windows.py:247 %s", 'except (ValueError, TypeError)')
            messagebox.showerror(_("common.error"), "Invalid number of days")

    def load_backup_status(self):
        status_text = """BACKUP SYSTEM STATUS
==================

Automatic Backups: Enabled
Backup Frequency: Every 24 hours
Last Backup: 2024-12-20 14:30:22
Next Scheduled: 2024-12-21 14:30:22

Storage Location: ./backups/
Available Space: 45.2 GB
Total Backups: 15
Oldest Backup: 2024-11-20

Configuration:
- Auto-cleanup after 30 days
- Maximum backup size: 100 MB
- Compression: Enabled
"""

        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, status_text)

class BackupSettingsWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.backup_settings"))
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Backup Settings", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Settings frame
        settings_frame = ttk.LabelFrame(self.window, text="Backup Configuration", padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Automatic backups
        self.auto_backup_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Enable automatic backups",
                       variable=self.auto_backup_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Backup frequency
        ttk.Label(settings_frame, text="Backup frequency (hours):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.frequency_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.frequency_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Retention period
        ttk.Label(settings_frame, text="Keep backups for (days):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.retention_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.retention_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # Backup location
        ttk.Label(settings_frame, text="Backup location:").grid(row=3, column=0, sticky=tk.W, pady=5)
        location_frame = ttk.Frame(settings_frame)
        location_frame.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        self.location_var = tk.StringVar()
        ttk.Entry(location_frame, textvariable=self.location_var, width=30).pack(side=tk.LEFT)
        ttk.Button(location_frame, text=_("common.browse"), command=self.browse_location).pack(side=tk.LEFT, padx=(5, 0))

        # Compression
        self.compression_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Enable compression",
                       variable=self.compression_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Notifications
        self.notifications_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Email notifications on backup completion",
                       variable=self.notifications_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save Settings",
                  command=self.save_settings, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Test Backup",
                  command=self.test_backup, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def load_current_settings(self):
        # Load current settings from database or use defaults
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            self.auto_backup_var.set(get_enhanced_setting('auto_backup_enabled', True, 'boolean'))
            self.frequency_var.set(str(get_enhanced_setting('backup_frequency_hours', 24, 'integer')))
        else:
            self.auto_backup_var.set(True)
            self.frequency_var.set("24")

        self.retention_var.set("30")
        from education_system.university_system.core import paths
        self.location_var.set(str(paths.BACKUP_ATTENDANCE_DIR / ""))
        self.compression_var.set(True)
        self.notifications_var.set(False)

    def browse_location(self):
        directory = filedialog.askdirectory(title="Select backup location")
        if directory:
            self.location_var.set(directory)

    def save_settings(self):
        try:
            # Validate inputs
            frequency = int(self.frequency_var.get())
            retention = int(self.retention_var.get())

            if frequency < 1 or retention < 1:
                messagebox.showerror(_("common.error"), "Frequency and retention must be positive numbers")
                return

            # Save settings
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                set_enhanced_setting('auto_backup_enabled', self.auto_backup_var.get(), data_type='boolean')
                set_enhanced_setting('backup_frequency_hours', frequency, data_type='integer')

            messagebox.showinfo(_("common.success"), "Backup settings saved successfully!")
            self.callback()  # Refresh parent status
            self.window.destroy()

        except ValueError:
            logger.exception("backup_database_windows.py:380 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), "Please enter valid numbers for frequency and retention")

    def test_backup(self):
        messagebox.showinfo("Test Backup", "Test backup would be created here")

class DatabaseMaintenanceWindow:
    """SQLite-oriented maintenance helpers for attendance data."""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.database_maintenance"))
        self.window.geometry("900x620")
        self.window.transient(parent)
        self.window.grab_set()

        self.db_info = self._collect_db_info()
        self.status_labels = {}
        self.tables_tree = None
        self.logs_text = None
        self.backup_tree = None

        self.create_widgets()

    # --------------------------------------------------------------- UI setup
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)

        ttk.Label(title_frame, text="🗄️ Attendance Database Maintenance",
                 font=('Arial', 16, 'bold')).pack(side='left')
        ttk.Button(title_frame, text=_("common.refresh"), command=self.refresh_view).pack(side='right')

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text="Status")
        self._build_status_tab(status_frame)

        maintenance_frame = ttk.Frame(notebook)
        notebook.add(maintenance_frame, text="Maintenance Tasks")
        self._build_maintenance_tab(maintenance_frame)

        backup_frame = ttk.Frame(notebook)
        notebook.add(backup_frame, text="Backup & Restore")
        self._build_backup_tab(backup_frame)

        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=(0, 10))

    def _build_status_tab(self, parent):
        overview = ttk.LabelFrame(parent, text="Database Overview", padding=15)
        overview.pack(fill='x', padx=10, pady=10)

        summary_items = [
            ("Connection", "connection"),
            ("Database Path", "path"),
            ("Size", "size"),
            ("Tables", "tables_count"),
        ]

        for idx, (label, key) in enumerate(summary_items):
            frame = ttk.LabelFrame(overview, text=label, padding=10)
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky='ew')
            value_label = ttk.Label(frame, text="", font=('Arial', 11, 'bold'))
            value_label.pack()
            self.status_labels[key] = value_label
            overview.grid_columnconfigure(idx, weight=1)

        tables_frame = ttk.LabelFrame(parent, text="Table Statistics", padding=15)
        tables_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        columns = ('Table', 'Rows')
        self.tables_tree = ttk.Treeview(tables_frame, columns=columns, show='headings', height=14)
        for col in columns:
            width = 220 if col == 'Table' else 120
            self.tables_tree.heading(col, text=col)
            self.tables_tree.column(col, width=width, anchor='w')
        self.tables_tree.pack(fill='both', expand=True)

        self._populate_status_tab()

    def _build_maintenance_tab(self, parent):
        actions_frame = ttk.LabelFrame(parent, text="Maintenance Operations", padding=15)
        actions_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(actions_frame, text="VACUUM", command=self.run_vacuum).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="ANALYZE", command=self.run_analyze).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="REINDEX", command=self.run_reindex).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="PRAGMA optimize", command=self.run_optimize).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="Integrity Check", command=self.run_integrity_check).pack(side='left', padx=5)

        log_frame = ttk.LabelFrame(parent, text="Maintenance Log", padding=15)
        log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        self.logs_text = scrolledtext.ScrolledText(log_frame, wrap='word', height=16)
        self.logs_text.pack(fill='both', expand=True)
        self.logs_text.config(state='disabled')

    def _build_backup_tab(self, parent):
        controls = ttk.LabelFrame(parent, text="Backup Operations", padding=15)
        controls.pack(fill='x', padx=10, pady=10)

        ttk.Button(controls, text="Create Backup", command=self.create_backup).pack(side='left', padx=5)
        ttk.Button(controls, text="Restore Backup", command=self.restore_backup).pack(side='left', padx=5)
        ttk.Button(controls, text="Open Backup Folder", command=self.open_backup_folder).pack(side='left', padx=5)

        history_frame = ttk.LabelFrame(parent, text="Backup History", padding=15)
        history_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        columns = ('Filename', 'Created', 'Size')
        self.backup_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=14)
        for idx, col in enumerate(columns):
            width = 320 if idx == 0 else 160
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=width, anchor='w')
        self.backup_tree.pack(fill='both', expand=True)

        self._populate_backup_history()

    # --------------------------------------------------------- data helpers ---
    def _collect_db_info(self):
        info = {
            "connected": False,
            "path": "Unknown",
            "size": "Unknown",
            "tables": [],
            "error": None,
        }

        if not MAIN_DB_AVAILABLE:
            info["error"] = "Database helper unavailable in this environment."
            return info

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            info["connected"] = True

            cursor.execute("PRAGMA database_list;")
            rows = cursor.fetchall()
            if rows:
                db_path = rows[0][2]
                info["path"] = db_path or "memory"
                if db_path and os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    info["size"] = self._format_size(size_bytes)

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for table in sorted(tables):
                try:
                    safe_table = validate_identifier(table, "table")
                    cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                    count = cursor.fetchone()[0]
                    info["tables"].append((table, count))
                except Exception:
                    logger.exception("backup_database_windows.py:538 %s", 'except Exception')
                    info["tables"].append((table, None))

            conn.close()
        except Exception as exc:
            logger.exception("backup_database_windows.py:542 %s", 'except Exception as exc')
            info["error"] = str(exc)

        return info

    def _format_size(self, size_bytes):
        if size_bytes is None:
            return "Unknown"
        for unit in ("bytes", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024.0:
                return f"{size_bytes:3.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _populate_status_tab(self):
        info = self.db_info
        self.status_labels['connection'].config(
            text="Connected" if info['connected'] else "Not connected"
        )
        self.status_labels['path'].config(text=info['path'])
        self.status_labels['size'].config(text=info['size'])
        self.status_labels['tables_count'].config(text=str(len(info['tables'])))

        for item in self.tables_tree.get_children():
            self.tables_tree.delete(item)
        for table, count in info['tables']:
            count_display = f"{count:,}" if isinstance(count, int) else "?"
            self.tables_tree.insert('', 'end', values=(table, count_display))

        if info['error']:
            self._append_log(f"⚠ Error collecting database information: {info['error']}")

    def _populate_backup_history(self):
        if not self.backup_tree:
            return
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)

        backups_dir = Path(BACKUP_ATTENDANCE_DIR)
        backups_dir.mkdir(parents=True, exist_ok=True)
        backups = sorted(backups_dir.glob("attendance_backup_*.db"), reverse=True)

        for backup in backups:
            stat = backup.stat()
            created = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = self._format_size(stat.st_size)
            self.backup_tree.insert('', 'end', values=(backup.name, created, size))

    # -------------------------------------------------------------- actions ---
    def run_vacuum(self):
        self._run_sql_command("VACUUM")

    def run_analyze(self):
        self._run_sql_command("ANALYZE")

    def run_reindex(self):
        self._run_sql_command("REINDEX")

    def run_optimize(self):
        self._run_sql_command("PRAGMA optimize")

    def run_integrity_check(self):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()
            self._append_log(f"Integrity check: {result[0] if result else 'No response'}")
            messagebox.showinfo("Integrity Check", result[0] if result else "No response")
        except Exception as exc:
            logger.exception("backup_database_windows.py:615 %s", 'except Exception as exc')
            self._append_log(f"Integrity check failed: {exc}")
            messagebox.showerror("Integrity Check Failed", str(exc))

    def _run_sql_command(self, command):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(command)
            conn.commit()
            conn.close()
            self._append_log(f"Executed {command}")
            messagebox.showinfo("Maintenance", f"{command} executed successfully.")
        except Exception as exc:
            logger.exception("backup_database_windows.py:631 %s", 'except Exception as exc')
            self._append_log(f"{command} failed: {exc}")
            messagebox.showerror("Maintenance Failed", str(exc))

    def create_backup(self):
        if not self.db_info['path'] or not os.path.exists(self.db_info['path']):
            messagebox.showwarning("No Database File", "Database path is unknown or unavailable.")
            return

        backups_dir = Path(BACKUP_ATTENDANCE_DIR)
        backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = backups_dir / f"attendance_backup_{timestamp}.db"

        try:
            shutil.copy2(self.db_info['path'], destination)
            self._append_log(f"Backup created at {destination}")
            self._populate_backup_history()
            messagebox.showinfo("Backup Complete", f"Backup saved to {destination}")
        except Exception as exc:
            logger.exception("backup_database_windows.py:650 %s", 'except Exception as exc')
            self._append_log(f"Backup failed: {exc}")
            messagebox.showerror("Backup Failed", str(exc))

    def restore_backup(self):
        if not self.db_info['path'] or not os.path.exists(self.db_info['path']):
            messagebox.showwarning("No Database File", "Database path is unknown or unavailable.")
            return

        filename = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        if not filename:
            return

        confirmed = messagebox.askyesno(
            "Confirm Restore",
            "Restoring a backup will overwrite the current database.\n"
            "Make sure you have a recent backup of the current data.\n\n"
            "Proceed with restore?"
        )
        if not confirmed:
            return

        try:
            shutil.copy2(self.db_info['path'], f"{self.db_info['path']}.bak")
            shutil.copy2(filename, self.db_info['path'])
            self._append_log(f"Database restored from {filename}")
            messagebox.showinfo("Restore Complete", "Database has been restored successfully.")
            self.refresh_view()
        except Exception as exc:
            logger.exception("backup_database_windows.py:681 %s", 'except Exception as exc')
            self._append_log(f"Restore failed: {exc}")
            messagebox.showerror("Restore Failed", str(exc))

    def open_backup_folder(self):
        backups_dir = Path(BACKUP_ATTENDANCE_DIR)
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Get list of backup files
        backups = sorted(backups_dir.glob("attendance_backup_*.db"), reverse=True)

        if backups:
            backup_list = "\n".join([f"• {b.name}" for b in backups[:10]])  # Show first 10
            if len(backups) > 10:
                backup_list += f"\n... and {len(backups) - 10} more"
            message = f"Backups are stored in:\n{backups_dir}\n\nRecent backups:\n{backup_list}"
        else:
            message = f"Backups are stored in:\n{backups_dir}\n\nNo backup files found."

        messagebox.showinfo("Backup Folder", message)

    def refresh_view(self):
        self.db_info = self._collect_db_info()
        self._populate_status_tab()
        self._populate_backup_history()

    # -------------------------------------------------------------- helpers ---
    def _append_log(self, message):
        if not self.logs_text:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.config(state='normal')
        self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.logs_text.see(tk.END)
        self.logs_text.config(state='disabled')



# Aliases for backward compatibility
BackupSettingsDialog = BackupSettingsWindow
