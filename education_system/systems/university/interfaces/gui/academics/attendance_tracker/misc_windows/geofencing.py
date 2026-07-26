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
from education_system.systems.university.infrastructure.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

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
    from education_system.systems.university.domain.academics.services.attendance.attendance_tracker import (
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
    from education_system.systems.university.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class GeofencingWindow:
    def __init__(self, parent, geo_system):
        self.parent = parent
        self.geo_system = geo_system

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.geofencing_setup"))
        self.window.geometry("500x400")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📍 Geofencing Setup", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Create geofenced session
        session_frame = ttk.LabelFrame(self.window, text="Create Geofenced Session", padding=10)
        session_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(session_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        self.module_var.trace('w', lambda *args: self.on_module_change())
        ttk.Entry(session_frame, textvariable=self.module_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(session_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(session_frame, textvariable=self.date_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)

        ttk.Label(session_frame, text="Location Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.location_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)

        ttk.Label(session_frame, text="Latitude:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.latitude_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.latitude_var, width=30).grid(row=3, column=1, padx=(10, 0), pady=5)

        ttk.Label(session_frame, text="Longitude:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.longitude_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.longitude_var, width=30).grid(row=4, column=1, padx=(10, 0), pady=5)

        ttk.Label(session_frame, text="Radius (meters):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.radius_var = tk.StringVar(value="50")
        ttk.Entry(session_frame, textvariable=self.radius_var, width=30).grid(row=5, column=1, padx=(10, 0), pady=5)

        ttk.Button(session_frame, text="Create Geofenced Session", command=self.create_session, style='Success.TButton').grid(row=6, column=0, columnspan=2, pady=10)

        # Test location
        test_frame = ttk.LabelFrame(self.window, text="Test Location Check", padding=10)
        test_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(test_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.test_student_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_student_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(test_frame, text="Test Latitude:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.test_lat_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_lat_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)

        ttk.Label(test_frame, text="Test Longitude:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.test_lon_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_lon_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)

        ttk.Button(test_frame, text="Test Location", command=self.test_location, style='Primary.TButton').grid(row=3, column=0, columnspan=2, pady=10)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def on_module_change(self):
        """Auto-fill location when module code changes"""
        module_code = self.module_var.get().strip()
        if not module_code:
            return

        try:
            # Get current day of week
            current_day = datetime.datetime.now().strftime('%A')

            # Query timetable for module location
            try:
                from education_system.systems.university.infrastructure.database.db import get_db_connection as get_conn
                conn = get_conn()
            except ImportError:
                logger.exception("misc_windows.py:164 %s", 'except ImportError')
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))

            cursor = conn.cursor()

            # Try to find the room for this module
            cursor.execute('''
                SELECT r.building, r.room_number, ms.day_of_week, ms.start_time, ms.end_time
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                WHERE ms.module_code = ?
                ORDER BY
                    CASE
                        WHEN ms.day_of_week = ? THEN 1
                        ELSE 2
                    END,
                    ms.start_time
                LIMIT 1
            ''', (module_code, current_day))

            result = cursor.fetchone()
            conn.close()

            if result:
                building, room_number, day, start_time, end_time = result
                if building and room_number:
                    location_str = f"{building} - Room {room_number}"
                    self.location_var.set(location_str)
                    # For geofencing, we would need GPS coordinates
                    # In a real system, you'd have a rooms table with GPS coords
                    # For now, leave latitude/longitude empty for manual entry
        except Exception as e:
            logger.exception("misc_windows.py:195 %s", 'except Exception as e')
            print(f"Could not auto-fill location: {e}")

    def create_session(self):
        """Create geofenced session"""
        try:
            module_code = self.module_var.get()
            date = self.date_var.get()
            location_name = self.location_var.get()
            latitude = float(self.latitude_var.get())
            longitude = float(self.longitude_var.get())
            radius = int(self.radius_var.get())

            session_id = self.geo_system.create_geofenced_session(
                module_code, date, location_name, latitude, longitude, radius
            )

            if session_id:
                messagebox.showinfo(_("common.success"), f"Geofenced session created!\nSession ID: {session_id}")
            else:
                messagebox.showerror(_("common.error"), "Failed to create geofenced session")

        except ValueError:
            logger.exception("misc_windows.py:217 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), "Please enter valid latitude, longitude, and radius values")
        except Exception as e:
            logger.exception("misc_windows.py:219 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Session creation failed: {e}")

    def test_location(self):
        """Test location check"""
        try:
            student_id = self.test_student_var.get()
            latitude = float(self.test_lat_var.get())
            longitude = float(self.test_lon_var.get())

            success, message = self.geo_system.check_location_attendance(student_id, latitude, longitude)

            if success:
                messagebox.showinfo("Location Test", f"✅ {message}")
            else:
                messagebox.showwarning("Location Test", f"❌ {message}")

        except ValueError:
            logger.exception("misc_windows.py:236 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), "Please enter valid student ID, latitude, and longitude")
        except Exception as e:
            logger.exception("misc_windows.py:238 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Location test failed: {e}")

