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
from education_system.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
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
from education_system.university_system.core.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:50 %s", 'except ImportError')
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
    logger.exception("misc_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class ExportDataWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.export_data"))
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📤 Export Data", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Export options
        options_frame = ttk.LabelFrame(self.window, text="Export Options", padding=20)
        options_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.data_type_var = tk.StringVar(value="All Data")
        type_combo = ttk.Combobox(options_frame, textvariable=self.data_type_var,
                                 values=["All Data", "Students", "Attendance Records", "Modules", "Settings"],
                                 state="readonly", width=25)
        type_combo.grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(options_frame, text="Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(options_frame, textvariable=self.format_var,
                                   values=["Excel", "CSV", "JSON"], state="readonly", width=25)
        format_combo.grid(row=1, column=1, padx=(10, 0), pady=5)

        # Date range for attendance data
        ttk.Label(options_frame, text="Date Range:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(options_frame)
        date_frame.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        self.start_date_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=10).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" to ").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=10).pack(side=tk.LEFT)

        # Include options
        self.include_deleted_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Include deleted records", variable=self.include_deleted_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text=_("common.export"), command=self.export_data, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"), command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def export_data(self):
        """Export the selected data"""
        try:
            data_type = self.data_type_var.get()
            format_type = self.format_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()

            # Choose file location
            file_ext = ".xlsx" if format_type == "Excel" else f".{format_type.lower()}"
            filename = filedialog.asksaveasfilename(
                defaultextension=file_ext,
                filetypes=[(f"{format_type} files", f"*{file_ext}"), ("All files", "*.*")]
            )

            if filename:
                messagebox.showinfo("Export", f"Would export {data_type} as {format_type} to {filename}")
                self.window.destroy()

        except Exception as e:
            logger.exception("misc_windows.py:1572 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Export failed: {e}")

