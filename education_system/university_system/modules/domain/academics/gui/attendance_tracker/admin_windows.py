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
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.admin_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.admin_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

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
    logger.exception("admin_windows.py:51 %s", 'except ImportError')
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
    logger.exception("admin_windows.py:65 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("admin_windows.py:76 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True


class ApiManagementWindow:
    def __init__(self, parent):
        self.parent = parent
        self.api_server = None
        self.api_thread = None

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.api_management"))
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        title_label = ttk.Label(self.window, text="🔌 API Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Server controls
        server_frame = ttk.LabelFrame(self.window, text="API Server Controls", padding=10)
        server_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Server settings
        settings_grid = ttk.Frame(server_frame)
        settings_grid.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_grid, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(settings_grid, textvariable=self.host_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(settings_grid, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0), pady=5)
        self.port_var = tk.StringVar(value="5000")
        ttk.Entry(settings_grid, textvariable=self.port_var, width=10).grid(row=0, column=3, padx=(10, 0), pady=5)

        # Server control buttons
        button_frame = ttk.Frame(server_frame)
        button_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(button_frame, text="▶ Start Server", command=self.start_server, style='Success.TButton')
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(button_frame, text="⏹ Stop Server", command=self.stop_server, state='disabled', style='Danger.TButton')
        self.stop_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(button_frame, text="● Server Stopped", foreground='red')
        self.status_label.pack(side=tk.LEFT, padx=(20, 0))

        # API Documentation
        doc_frame = ttk.LabelFrame(self.window, text="API Endpoints", padding=10)
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Create treeview for endpoints
        columns = ('Method', 'Endpoint', 'Description')
        self.endpoints_tree = ttk.Treeview(doc_frame, columns=columns, show='headings', height=8)

        self.endpoints_tree.heading('Method', text='Method')
        self.endpoints_tree.heading('Endpoint', text='Endpoint')
        self.endpoints_tree.heading('Description', text='Description')

        self.endpoints_tree.column('Method', width=80, anchor='center')
        self.endpoints_tree.column('Endpoint', width=250)
        self.endpoints_tree.column('Description', width=300)

        # Add endpoints
        endpoints = [
            ("POST", "/api/attendance/record", "Record attendance for a student"),
            ("GET", "/api/attendance/student/<id>", "Get student attendance statistics"),
            ("POST", "/api/qr/generate", "Generate QR code for session"),
            ("POST", "/api/qr/checkin", "Process QR code check-in"),
            ("GET", "/api/predictions/<student_id>/<module>", "Get risk prediction"),
        ]

        for method, endpoint, description in endpoints:
            self.endpoints_tree.insert('', 'end', values=(method, endpoint, description))

        scrollbar = ttk.Scrollbar(doc_frame, orient='vertical', command=self.endpoints_tree.yview)
        self.endpoints_tree.configure(yscrollcommand=scrollbar.set)

        self.endpoints_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Example usage
        example_frame = ttk.LabelFrame(self.window, text="Example Usage", padding=10)
        example_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        example_text = scrolledtext.ScrolledText(example_frame, height=6, width=70, wrap=tk.WORD)
        example_text.pack(fill=tk.X)

        example_text.insert(tk.END, "curl -X POST http://localhost:5000/api/attendance/record \\\n")
        example_text.insert(tk.END, "  -H 'Content-Type: application/json' \\\n")
        example_text.insert(tk.END, "  -d '{\n")
        example_text.insert(tk.END, "    \"student_id\": \"S001\",\n")
        example_text.insert(tk.END, "    \"module_code\": \"CS101\",\n")
        example_text.insert(tk.END, "    \"date\": \"2025-01-01\",\n")
        example_text.insert(tk.END, "    \"status\": \"Present\"\n")
        example_text.insert(tk.END, "  }'")

        example_text.config(state='disabled')

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.close_window).pack(pady=10)

    def start_server(self):
        """Start the API server in a background thread"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                messagebox.showerror(_("common.error"), "API system not available. Original attendance_tracker module not found.")
                return

            from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import AttendanceAPI

            host = self.host_var.get()
            port = int(self.port_var.get())

            self.api_server = AttendanceAPI()

            # Start server in background thread
            def run_server():
                try:
                    self.api_server.run_api(host=host, port=port, debug=False)
                except Exception as e:
                    logger.exception("admin_windows.py:203 %s", 'except Exception as e')
                    print(f"API server error: {e}")

            self.api_thread = threading.Thread(target=run_server, daemon=True)
            self.api_thread.start()

            # Update UI
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.status_label.config(text=f"● Server Running on {host}:{port}", foreground='green')

            messagebox.showinfo("Server Started", f"API server started at http://{host}:{port}")

        except ValueError:
            logger.exception("admin_windows.py:216 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), "Invalid port number")
        except Exception as e:
            logger.exception("admin_windows.py:218 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to start server: {e}")

    def stop_server(self):
        """Stop the API server"""
        try:
            # Note: Flask doesn't have a clean shutdown method when run directly
            # In production, you'd use a WSGI server like gunicorn
            messagebox.showinfo("Stop Server", "API server will stop when the application closes.\n\nFor production use, consider using a proper WSGI server.")

            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.status_label.config(text="● Server Stopped", foreground='red')

        except Exception as e:
            logger.exception("admin_windows.py:232 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Error stopping server: {e}")

    def close_window(self):
        """Close the window"""
        if self.stop_button['state'] == 'normal':
            response = messagebox.askyesno("Confirm Close", "API server is running. Close anyway?")
            if not response:
                return

        self.window.destroy()

class AuditLogsWindow:
    """Rich audit log viewer with filtering and export support."""

    LOG_FILES = (
        "audit_system.log",
        "app.log",
        "app.log",
        "attendance.log",
        "app.log",
    )

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.system_audit_logs"))
        self.window.geometry("980x640")
        self.window.transient(parent)
        self.window.grab_set()

        self.all_logs = []
        self.filtered_logs = []
        self.errors = []

        self.create_widgets()
        self.refresh_logs()

    # ------------------------------------------------------------------ UI ---
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)
        ttk.Label(title_frame, text="📋 System Audit Logs", font=('Arial', 16, 'bold')).pack(side='left')

        # Filters
        filters_frame = ttk.LabelFrame(self.window, text="Filters", padding=15)
        filters_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.date_range_var = tk.StringVar(value="Last 7 Days")
        ttk.Label(filters_frame, text="Date Range:").grid(row=0, column=0, sticky='w')
        self.date_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.date_range_var,
            values=["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time", "Custom Range"],
            width=18,
            state='readonly'
        )
        self.date_combo.grid(row=0, column=1, padx=(5, 20))

        self.level_var = tk.StringVar(value="All Levels")
        ttk.Label(filters_frame, text="Level:").grid(row=0, column=2, sticky='w')
        self.level_combo = ttk.Combobox(filters_frame, textvariable=self.level_var, width=16, state='readonly')
        self.level_combo.grid(row=0, column=3, padx=(5, 20))

        self.source_var = tk.StringVar(value="All Sources")
        ttk.Label(filters_frame, text="Source:").grid(row=0, column=4, sticky='w')
        self.source_combo = ttk.Combobox(filters_frame, textvariable=self.source_var, width=18, state='readonly')
        self.source_combo.grid(row=0, column=5, padx=(5, 0))

        ttk.Label(filters_frame, text="Search:").grid(row=1, column=0, sticky='w', pady=(12, 0))
        self.search_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self.search_var, width=38).grid(
            row=1, column=1, columnspan=3, sticky='ew', padx=(5, 20), pady=(12, 0)
        )

        button_frame = ttk.Frame(filters_frame)
        button_frame.grid(row=1, column=4, columnspan=2, sticky='e', pady=(12, 0))

        ttk.Button(button_frame, text="Apply Filters", command=self.apply_filters).pack(side='left')
        ttk.Button(button_frame, text="Reset", command=self.reset_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("common.refresh"), command=self.refresh_logs).pack(side='left')

        # Logs table
        table_frame = ttk.LabelFrame(self.window, text="Log Entries", padding=15)
        table_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        columns = ('Timestamp', 'Level', 'Category', 'User', 'Action', 'Source', 'Details')
        self.logs_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=18)
        for col in columns:
            width = 140 if col == 'Details' else 120
            self.logs_tree.heading(col, text=col)
            self.logs_tree.column(col, width=width, anchor='w')

        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.logs_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.logs_tree.xview)
        self.logs_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.logs_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        action_bar = ttk.Frame(self.window)
        action_bar.pack(fill='x', padx=15, pady=(0, 10))

        ttk.Button(action_bar, text="View Details", command=self.view_log_details).pack(side='left')
        ttk.Button(action_bar, text="Export...", command=self.export_logs).pack(side='left', padx=5)
        ttk.Button(action_bar, text="Archive / Clear", command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(action_bar, text=_("common.close"), command=self.window.destroy).pack(side='right')

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var, foreground="#555555").pack(anchor='w', padx=15, pady=(0, 10))

        self.logs_tree.bind('<Double-1>', self.view_log_details)

    # ------------------------------------------------------------ data load ---
    def refresh_logs(self):
        self._set_status("Loading audit logs...")
        self.errors.clear()
        self.all_logs = self._load_logs()
        self._update_filter_options()
        self.apply_filters()
        if self.errors:
            self._set_status(f"Loaded {len(self.all_logs)} entries with warnings: {'; '.join(self.errors)}")
        else:
            self._set_status(f"Loaded {len(self.all_logs)} audit log entries.")

    def _load_logs(self):
        logs = []
        logs.extend(self._load_db_logs())
        logs.extend(self._load_file_logs())
        return logs

    def _load_db_logs(self):
        logs = []
        if not MAIN_DB_AVAILABLE:
            return logs

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            candidates = self._find_audit_tables(cursor)

            for table_name in candidates:
                try:
                    safe_table = validate_table_name(table_name, conn=conn)
                    cursor.execute("PRAGMA table_info([" + safe_table + "])")
                    columns = [row[1] for row in cursor.fetchall()]
                    if not columns:
                        continue

                    cursor.execute("SELECT * FROM [" + safe_table + "] ORDER BY ROWID DESC LIMIT 500")
                    for row in cursor.fetchall():
                        log_entry = self._build_log_record(table_name, columns, row)
                        if log_entry:
                            logs.append(log_entry)
                except Exception as exc:
                    logger.exception("admin_windows.py:390 %s", 'except Exception as exc')
                    self.errors.append(f"{table_name}: {exc}")

            conn.close()
        except Exception as exc:
            logger.exception("admin_windows.py:394 %s", 'except Exception as exc')
            self.errors.append(f"Database error: {exc}")
        return logs

    def _find_audit_tables(self, cursor):
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            return [
                name for name in tables
                if any(keyword in name.lower() for keyword in ("audit", "log", "activity"))
            ]
        except Exception as exc:
            logger.exception("admin_windows.py:406 %s", 'except Exception as exc')
            self.errors.append(f"Unable to list tables: {exc}")
            return []

    def _build_log_record(self, table_name, columns, row):
        data = dict(zip(columns, row))

        timestamp_value = self._first_available(data, ("timestamp", "created_at", "created_on",
                                                       "logged_at", "event_time", "datetime"))
        timestamp_obj, timestamp_str = self._parse_timestamp(timestamp_value)

        level = self._first_available(data, ("level", "severity", "status", "log_level")) or "INFO"
        category = self._first_available(data, ("category", "module", "event_type",
                                                "table_affected", "function")) or table_name
        user = self._first_available(data, ("user", "username", "user_id", "actor", "initiated_by")) or "system"
        action = self._first_available(data, ("action", "event", "operation", "activity", "title")) or "activity"
        source = self._first_available(data, ("source", "system", "service", "module")) or table_name

        detail_value = self._first_available(
            data,
            ("details", "description", "message", "notes", "change_summary", "new_values")
        )
        if isinstance(detail_value, (dict, list)):
            details = json.dumps(detail_value, default=str)
        else:
            details = str(detail_value or "")

        if not timestamp_str:
            # Skip rows that are clearly not log entries
            return None

        return {
            "timestamp": timestamp_obj,
            "timestamp_str": timestamp_str,
            "level": str(level),
            "category": str(category),
            "user": str(user),
            "action": str(action),
            "source": str(source),
            "details": details,
        }

    def _first_available(self, data, keys):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        return None

    @staticmethod
    def _parse_timestamp(value):
        if value is None:
            return None, ""

        if isinstance(value, datetime.datetime):
            return value, value.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(value, (int, float)):
            try:
                dt = datetime.datetime.fromtimestamp(value)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                logger.exception("admin_windows.py:466 %s", 'except Exception')
        value_str = str(value).strip()
        if not value_str:
            return None, ""

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%d/%m/%Y %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(value_str.replace("Z", ""), fmt)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.exception("admin_windows.py:478 %s", 'except ValueError')
                continue

        try:
            dt = datetime.datetime.fromisoformat(value_str.replace("Z", "+00:00"))
            return dt, dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            logger.exception("admin_windows.py:484 %s", 'except Exception')
            return None, value_str

    def _load_file_logs(self):
        logs = []
        log_dir = Path(LOG_DIR)
        for filename in self.LOG_FILES:
            file_path = log_dir / filename
            if not file_path.exists():
                continue
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in deque(handle, maxlen=400):
                        record = self._parse_log_line(line, filename)
                        if record:
                            logs.append(record)
            except Exception as exc:
                logger.exception("admin_windows.py:500 %s", 'except Exception as exc')
                self.errors.append(f"{filename}: {exc}")
        return logs

    def _parse_log_line(self, line, filename):
        line = line.strip()
        if not line:
            return None

        patterns = [
            r'^\[(?P<timestamp>[^\]]+)\]\s+(?P<level>[A-Z]+)\s*-\s*(?P<message>.+)',
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2} [\d:]+)\s+\[(?P<level>[A-Z]+)\]\s+(?P<message>.+)',
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:]+(?:\.\d+)?Z?)\s+(?P<message>.+)',
        ]

        timestamp_obj, timestamp_str, level, message = None, "", "INFO", line
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                timestamp_obj, timestamp_str = self._parse_timestamp(match.group('timestamp'))
                level = match.groupdict().get('level', level) or level
                message = match.groupdict().get('message', message)
                break

        # Attempt to split category/action details
        category = "Log File"
        action = message
        details = ""
        if " - " in message:
            parts = message.split(" - ", 1)
            category = parts[0].strip() or category
            action = parts[0].strip()
            details = parts[1].strip()

        return {
            "timestamp": timestamp_obj,
            "timestamp_str": timestamp_str or message[:19],
            "level": level,
            "category": category,
            "user": "system",
            "action": action,
            "source": filename,
            "details": details or message,
        }

    # -------------------------------------------------------------- filters ---
    def _update_filter_options(self):
        levels = sorted({log['level'] for log in self.all_logs if log['level']})
        sources = sorted({log['source'] for log in self.all_logs if log['source']})
        self.level_combo['values'] = ["All Levels"] + levels
        self.source_combo['values'] = ["All Sources"] + sources

        if self.level_var.get() not in self.level_combo['values']:
            self.level_var.set("All Levels")
        if self.source_var.get() not in self.source_combo['values']:
            self.source_var.set("All Sources")

    def apply_filters(self):
        level_filter = self.level_var.get()
        source_filter = self.source_var.get()
        search_text = self.search_var.get().strip().lower()

        now = datetime.datetime.now()
        range_map = {
            "Last 24 Hours": now - datetime.timedelta(days=1),
            "Last 7 Days": now - datetime.timedelta(days=7),
            "Last 30 Days": now - datetime.timedelta(days=30)
        }
        threshold = range_map.get(self.date_range_var.get())

        if self.date_range_var.get() == "Custom Range":
            custom = simpledialog.askstring(
                "Custom Date Range",
                "Enter custom range as YYYY-MM-DD,YYYY-MM-DD",
                parent=self.window
            )
            if custom:
                try:
                    start_str, end_str = [part.strip() for part in custom.split(",")]
                    start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.datetime.strptime(end_str, "%Y-%m-%d") + datetime.timedelta(days=1)
                    threshold = start_dt
                    range_end = end_dt
                except Exception:
                    logger.exception("admin_windows.py:583 %s", 'except Exception')
                    messagebox.showerror("Invalid Range", "Could not parse the supplied date range.")
                    threshold = None
                    range_end = None
            else:
                threshold = None
                range_end = None
        else:
            range_end = None

        filtered = []
        for log in self.all_logs:
            timestamp_ok = True
            if threshold:
                if log['timestamp']:
                    if self.date_range_var.get() == "Custom Range" and range_end:
                        timestamp_ok = threshold <= log['timestamp'] <= range_end
                    else:
                        timestamp_ok = log['timestamp'] >= threshold
                else:
                    timestamp_ok = False
            if not timestamp_ok:
                continue

            if level_filter != "All Levels" and log['level'] != level_filter:
                continue

            if source_filter != "All Sources" and log['source'] != source_filter:
                continue

            if search_text and not self._matches_search(log, search_text):
                continue

            filtered.append(log)

        filtered.sort(key=lambda entry: entry['timestamp'] or datetime.datetime.min, reverse=True)
        self.filtered_logs = filtered
        self._populate_treeview()

    def _matches_search(self, log, text):
        haystack = " ".join([
            log.get('timestamp_str', ''),
            log.get('level', ''),
            log.get('category', ''),
            log.get('user', ''),
            log.get('action', ''),
            log.get('source', ''),
            log.get('details', ''),
        ]).lower()
        return text in haystack

    def reset_filters(self):
        self.date_range_var.set("Last 7 Days")
        self.level_var.set("All Levels")
        self.source_var.set("All Sources")
        self.search_var.set("")
        self.apply_filters()

    def _populate_treeview(self):
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        for log in self.filtered_logs:
            values = (
                log['timestamp_str'],
                log['level'],
                log['category'],
                log['user'],
                log['action'],
                log['source'],
                log['details'],
            )
            self.logs_tree.insert('', 'end', values=values)

    # -------------------------------------------------------------- actions ---
    def export_logs(self):
        if not self.filtered_logs:
            messagebox.showinfo("No Data", "There are no log entries to export.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(["Timestamp", "Level", "Category", "User", "Action", "Source", "Details"])
                for log in self.filtered_logs:
                    writer.writerow([
                        log['timestamp_str'],
                        log['level'],
                        log['category'],
                        log['user'],
                        log['action'],
                        log['source'],
                        log['details'],
                    ])
            messagebox.showinfo("Export Complete", f"Exported {len(self.filtered_logs)} log entries to {filename}")
        except Exception as exc:
            logger.exception("admin_windows.py:686 %s", 'except Exception as exc')
            messagebox.showerror("Export Failed", f"Unable to export logs:\n{exc}")

    def view_log_details(self, event=None):
        selection = self.logs_tree.selection()
        if not selection:
            return

        item = self.logs_tree.item(selection[0])
        values = item['values']

        details_window = tk.Toplevel(self.window)
        details_window.title("Log Entry Details")
        details_window.geometry("640x520")
        details_window.transient(self.window)

        details_frame = ttk.LabelFrame(details_window, text="Log Details", padding=15)
        details_frame.pack(fill='both', expand=True, padx=15, pady=15)

        details_text = scrolledtext.ScrolledText(details_frame, wrap='word', height=22)
        details_text.pack(fill='both', expand=True)

        detail_report = f"""
LOG ENTRY DETAILS
=================

Timestamp : {values[0]}
Level     : {values[1]}
Category  : {values[2]}
User      : {values[3]}
Action    : {values[4]}
Source    : {values[5]}

Details
-------
{values[6]}
"""
        details_text.insert('1.0', detail_report.strip())
        details_text.config(state='disabled')

        ttk.Button(details_window, text=_("common.close"), command=details_window.destroy).pack(pady=(0, 10))

    def clear_logs(self):
        messagebox.showinfo(
            "Archive Logs",
            "Automated log archival is not yet connected to the database.\n"
            "Consider exporting the entries you need before removing old data."
        )

    def _set_status(self, message):
        self.status_var.set(message)

class DiagnosticsWindow:
    """Run lightweight diagnostics for the attendance stack."""

    def __init__(self, parent, controller=None):
        self.parent = parent
        self.controller = controller

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.system_diagnostics"))
        self.window.geometry("920x620")
        self.window.transient(parent)
        self.window.grab_set()

        self.summary_labels = {}
        self.services_tree = None
        self.table_tree = None
        self.log_text = None

        self.metrics = self._collect_metrics()
        self.create_widgets()

    # ------------------------------------------------------------ UI setup ---
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)
        ttk.Label(title_frame, text="🔧 Attendance System Diagnostics",
                 font=('Arial', 16, 'bold')).pack(side='left')

        ttk.Button(title_frame, text="Re-run Checks", command=self.refresh_metrics).pack(side='right')

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="System Summary")
        self._build_summary_tab(summary_frame)

        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="Database & Data")
        self._build_data_tab(data_frame)

        services_frame = ttk.Frame(notebook)
        notebook.add(services_frame, text="Services & Integrations")
        self._build_services_tab(services_frame)

        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Recent Activity")
        self._build_logs_tab(logs_frame)

        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=(0, 10))

    def _build_summary_tab(self, parent):
        overview = ttk.LabelFrame(parent, text="Health Overview", padding=15)
        overview.pack(fill='x', padx=10, pady=10)

        summary_items = [
            ("Database", "db_status"),
            ("Database Path", "db_path"),
            ("Last Check", "generated_at"),
            ("Issues Detected", "issues"),
        ]

        for idx, (label, key) in enumerate(summary_items):
            frame = ttk.LabelFrame(overview, text=label, padding=10)
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky='ew')
            value = ttk.Label(frame, text="", font=('Arial', 11, 'bold'))
            value.pack()
            self.summary_labels[key] = value
            overview.grid_columnconfigure(idx, weight=1)

        stats_frame = ttk.LabelFrame(parent, text="Attendance Data Snapshot", padding=15)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        stats_columns = ('Metric', 'Value')
        stats_tree = ttk.Treeview(stats_frame, columns=stats_columns, show='headings', height=8)
        for col in stats_columns:
            stats_tree.heading(col, text=col)
            stats_tree.column(col, width=220 if col == 'Metric' else 160)
        stats_tree.pack(fill='both', expand=True)

        self.summary_labels['stats_tree'] = stats_tree
        self._populate_summary()

    def _build_data_tab(self, parent):
        status_frame = ttk.LabelFrame(parent, text="Table Overview", padding=15)
        status_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Table', 'Exists', 'Row Count', 'Notes')
        self.table_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=12)
        for idx, col in enumerate(columns):
            width = 160 if idx == 0 else 110
            if col == 'Notes':
                width = 260
            self.table_tree.heading(col, text=col)
            self.table_tree.column(col, width=width, anchor='w')
        self.table_tree.pack(fill='both', expand=True)

        actions = ttk.Frame(parent)
        actions.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(actions, text="Run Integrity Check", command=self._run_integrity_check).pack(side='left')
        ttk.Button(actions, text="Open Maintenance Tools",
                   command=lambda: DatabaseMaintenanceWindow(self.parent)).pack(side='left', padx=5)

        self._populate_data_tab()

    def _build_services_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Integration Status", padding=15)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Service', 'Status', 'Notes')
        self.services_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for idx, col in enumerate(columns):
            width = 200 if idx == 0 else 160
            if col == 'Notes':
                width = 340
            self.services_tree.heading(col, text=col)
            self.services_tree.column(col, width=width, anchor='w')
        self.services_tree.pack(fill='both', expand=True)

        self._populate_services_tab()

    def _build_logs_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Recent Log Activity", padding=15)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(frame, wrap='word', height=18)
        self.log_text.pack(fill='both', expand=True)
        self._populate_logs_tab()

    # --------------------------------------------------------- data helpers ---
    def _collect_metrics(self):
        metrics = {
            "generated_at": datetime.datetime.now(),
            "db_status": "Unavailable",
            "db_path": "Unknown",
            "issues": "None detected",
            "counts": {
                "Students": "n/a",
                "Modules": "n/a",
                "Attendance Records": "n/a",
                "Audit Entries": "n/a",
            },
            "tables": [],
            "recent_logs": [],
            "services": [],
            "errors": [],
        }

        # Database inspection
        if MAIN_DB_AVAILABLE:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                metrics["db_status"] = "Connected"

                cursor.execute("PRAGMA database_list;")
                rows = cursor.fetchall()
                if rows:
                    db_path = rows[0][2]
                    metrics["db_path"] = db_path or "memory"

                tables = self._list_tables(cursor)
                metrics["tables"] = tables

                # Counts for common tables
                count_targets = {
                    "students": "Students",
                    "modules": "Modules",
                    "attendance": "Attendance Records",
                    "attendance_records": "Attendance Records",
                    "attendance_logs": "Audit Entries",
                    "audit_log": "Audit Entries",
                    "audit_logs": "Audit Entries",
                }

                for table_name, metric_label in count_targets.items():
                    if any(t['name'] == table_name for t in tables if t['exists']):
                        try:
                            safe_table = validate_table_name(table_name, conn=conn)
                            cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                            count = cursor.fetchone()[0]
                            metrics["counts"][metric_label] = f"{count:,}"
                        except Exception:
                            logger.exception("admin_windows.py:920 %s", 'except Exception')
                            continue

                recent_activity = self._load_recent_activity(cursor, tables)
                metrics["recent_logs"] = recent_activity

                conn.close()
            except Exception as exc:
                logger.exception("admin_windows.py:927 %s", 'except Exception as exc')
                metrics["db_status"] = "Connection failed"
                metrics["issues"] = str(exc)
                metrics["errors"].append(str(exc))
        else:
            metrics["db_status"] = "Connection helper unavailable"
            metrics["issues"] = "Database access helper is not available in this environment."

        # Services status
        metrics["services"] = self._evaluate_services()
        return metrics

    def _list_tables(self, cursor):
        tables = []
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cursor.fetchall()}
        except Exception:
            logger.exception("admin_windows.py:944 %s", 'except Exception')
            existing = set()

        required = [
            "students",
            "modules",
            "attendance",
            "attendance_records",
            "attendance_logs",
            "audit_log",
            "audit_logs",
        ]

        for name in sorted(existing.union(required)):
            exists = name in existing
            row_count = "—"
            if exists:
                try:
                    safe_name = validate_identifier(name, "table")
                    cursor.execute("SELECT COUNT(*) FROM [" + safe_name + "]")
                    row_count = f"{cursor.fetchone()[0]:,}"
                except Exception:
                    logger.exception("admin_windows.py:965 %s", 'except Exception')
                    row_count = "?"
            tables.append({
                "name": name,
                "exists": exists,
                "rows": row_count,
                "notes": "Required" if name in required else "",
            })

        return tables

    def _load_recent_activity(self, cursor, tables):
        table_candidates = [
            "attendance_logs",
            "attendance_log",
            "audit_logs",
            "audit_log",
            "attendance_records",
        ]
        existing_tables = {tbl['name'] for tbl in tables if tbl['exists']}

        for table in table_candidates:
            if table not in existing_tables:
                continue
            try:
                safe_table = validate_identifier(table, "table")
                cursor.execute("PRAGMA table_info([" + safe_table + "])")
                columns = [row[1] for row in cursor.fetchall()]
                if not columns:
                    continue

                cursor.execute("SELECT * FROM [" + safe_table + "] ORDER BY ROWID DESC LIMIT 5")
                rows = cursor.fetchall()
                recent = []
                for row in rows:
                    record = dict(zip(columns, row))
                    timestamp_val = record.get('timestamp') or record.get('created_at') or record.get('datetime')
                    ts_obj, ts_str = AuditLogsWindow._parse_timestamp(timestamp_val)
                    recent.append({
                        "table": table,
                        "timestamp": ts_str or "—",
                        "summary": record.get('action') or record.get('event') or "Update",
                        "details": record.get('details') or record.get('description') or "",
                    })
                if recent:
                    return recent
            except Exception:
                logger.exception("admin_windows.py:1011 %s", 'except Exception')
                continue
        return []

    def _evaluate_services(self):
        services = []

        services.append(self._service_row(
            "QR Attendance",
            True,
            "QR code generator available" if 'qrcode' in globals() else "QR library not imported"
        ))

        services.append(self._service_row(
            "Geofencing",
            GEOFENCING_SUPPORT,
            "Geofencing support enabled" if GEOFENCING_SUPPORT else "Feature flagged off"
        ))

        services.append(self._service_row(
            "Face Recognition",
            FACE_RECOGNITION_SUPPORT,
            "Face recognition helpers available" if FACE_RECOGNITION_SUPPORT else "Feature flagged off"
        ))

        services.append(self._service_row(
            "Predictive Analytics",
            ORIGINAL_FUNCTIONS_AVAILABLE,
            "Analytics module imported" if ORIGINAL_FUNCTIONS_AVAILABLE else "Analytics module missing"
        ))

        services.append(self._service_row(
            "Notification System",
            ORIGINAL_FUNCTIONS_AVAILABLE,
            "Notification helpers available" if ORIGINAL_FUNCTIONS_AVAILABLE else "Notification helpers missing"
        ))

        return services

    def _service_row(self, name, available, notes):
        return {
            "name": name,
            "status": "🟢 Available" if available else "🔴 Unavailable",
            "notes": notes,
        }

    # ---------------------------------------------------------- populators ---
    def _populate_summary(self):
        metrics = self.metrics
        self.summary_labels['db_status'].config(text=metrics['db_status'])
        self.summary_labels['db_path'].config(text=metrics['db_path'])
        self.summary_labels['generated_at'].config(
            text=metrics['generated_at'].strftime("%Y-%m-%d %H:%M:%S")
        )
        self.summary_labels['issues'].config(text=metrics.get('issues', 'None'))

        stats_tree = self.summary_labels['stats_tree']
        for item in stats_tree.get_children():
            stats_tree.delete(item)
        for key, value in metrics['counts'].items():
            stats_tree.insert('', 'end', values=(key, value))

    def _populate_data_tab(self):
        if not self.table_tree:
            return
        for item in self.table_tree.get_children():
            self.table_tree.delete(item)

        for table in self.metrics['tables']:
            exists = "Yes" if table['exists'] else "No"
            notes = table['notes'] or ("Detected" if table['exists'] else "")
            self.table_tree.insert('', 'end', values=(table['name'], exists, table['rows'], notes))

    def _populate_services_tab(self):
        if not self.services_tree:
            return
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)
        for service in self.metrics['services']:
            self.services_tree.insert('', 'end', values=(service['name'], service['status'], service['notes']))

    def _populate_logs_tab(self):
        if not self.log_text:
            return
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)

        recent = self.metrics['recent_logs']
        if not recent:
            self.log_text.insert('1.0', "No recent activity records were discovered.\n")
        else:
            lines = [
                f"[{entry['timestamp']}] {entry['table']} - {entry['summary']}\n{entry['details']}"
                for entry in recent
            ]
            self.log_text.insert('1.0', "\n\n".join(lines))

        # Append tail of log file for manual inspection
        from education_system.university_system.core.paths import LOG_DIR
        activity_log = LOG_DIR / "app.log"
        if activity_log.exists():
            self.log_text.insert(tk.END, "\n\n--- activity.log (latest entries) ---\n")
            try:
                with activity_log.open('r', encoding='utf-8', errors='ignore') as handle:
                    for line in deque(handle, maxlen=15):
                        self.log_text.insert(tk.END, line)
            except Exception as exc:
                logger.exception("admin_windows.py:1117 %s", 'except Exception as exc')
                self.log_text.insert(tk.END, f"[Unable to read activity.log: {exc}]\n")

        self.log_text.config(state='disabled')

    # ------------------------------------------------------------- actions ---
    def refresh_metrics(self):
        self.metrics = self._collect_metrics()
        self._populate_summary()
        self._populate_data_tab()
        self._populate_services_tab()
        self._populate_logs_tab()
        messagebox.showinfo("Diagnostics", "System diagnostics have been refreshed.")

    def _run_integrity_check(self):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available in this environment.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            message = result[0] if result else "No response"
            messagebox.showinfo("Integrity Check", f"Database integrity check returned: {message}")
        except Exception as exc:
            logger.exception("admin_windows.py:1143 %s", 'except Exception as exc')
            messagebox.showerror("Integrity Check Failed", str(exc))



# Aliases for backward compatibility
APIManagementWindow = ApiManagementWindow
AuditLogsViewer = AuditLogsWindow
SystemDiagnosticsWindow = DiagnosticsWindow
