import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
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
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import (
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
from education_system.post_18.university_system.core.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.post_18.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:50 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
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
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class ImportDataWindow:
    def __init__(self, parent, filename, callback):
        self.parent = parent
        self.filename = filename
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.import_data"))
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📥 Import Data", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # File info
        info_frame = ttk.LabelFrame(self.window, text="File Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(info_frame, text=f"File: {os.path.basename(self.filename)}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Path: {self.filename}").pack(anchor=tk.W)

        # Import options
        options_frame = ttk.LabelFrame(self.window, text="Import Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W)
        self.data_type_var = tk.StringVar(value="Students")
        type_combo = ttk.Combobox(options_frame, textvariable=self.data_type_var,
                                 values=["Students", "Attendance Records", "Modules"], state="readonly")
        type_combo.grid(row=0, column=1, padx=(10, 0))

        self.overwrite_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Overwrite existing data", variable=self.overwrite_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

        # Preview
        preview_frame = ttk.LabelFrame(self.window, text="Data Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load preview
        self.load_preview()

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text=_("common.import"), command=self.import_data, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"), command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def load_preview(self):
        """Load and display file preview"""
        import pandas as pd
        try:
            if self.filename.endswith('.csv'):
                df = pd.read_csv(self.filename, nrows=10)
            elif self.filename.endswith('.xlsx'):
                df = pd.read_excel(self.filename, nrows=10)
            else:
                self.preview_text.insert(tk.END, "File format not supported for preview")
                return

            preview_text = f"Columns: {', '.join(df.columns)}\n\n"
            preview_text += f"First 10 rows:\n{df.to_string(index=False)}"

            self.preview_text.insert(tk.END, preview_text)

        except Exception as e:
            logger.exception("misc_windows.py:1480 %s", 'except Exception as e')
            self.preview_text.insert(tk.END, f"Error loading preview: {e}")

    def import_data(self):
        """Import the data"""
        try:
            data_type = self.data_type_var.get()
            overwrite = self.overwrite_var.get()

            messagebox.showinfo("Import", f"Would import {data_type} data from {self.filename}\nOverwrite: {overwrite}")

            self.callback()  # Refresh parent data
            self.window.destroy()

        except Exception as e:
            logger.exception("misc_windows.py:1494 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Import failed: {e}")

