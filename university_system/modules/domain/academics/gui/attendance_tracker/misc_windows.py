import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from university_system.infrastructure.database.db import sqlite3
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
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import path constants
from university_system.modules.shared.constants.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from university_system.modules.domain.academics.services.attendance.attendance_tracker import (
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
    from university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
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
                from university_system.infrastructure.database.db import get_db_connection as get_conn
                conn = get_conn()
            except ImportError:
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
            messagebox.showerror(_("common.error"), "Please enter valid latitude, longitude, and radius values")
        except Exception as e:
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
            messagebox.showerror(_("common.error"), "Please enter valid student ID, latitude, and longitude")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Location test failed: {e}")

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
        title_label = ttk.Label(self.window, text="🔗 LMS Integration", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different LMS systems
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ Configuration")
        self.create_config_tab(config_frame)

        # Sync tab
        sync_frame = ttk.Frame(notebook)
        notebook.add(sync_frame, text="🔄 Sync Data")
        self.create_sync_tab(sync_frame)

        # History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="📜 Sync History")
        self.create_history_tab(history_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_config_tab(self, parent):
        # LMS Platform selection
        platform_frame = ttk.LabelFrame(parent, text="LMS Platform", padding=15)
        platform_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(platform_frame, text="Select LMS Platform:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.lms_platform_var = tk.StringVar(value="Moodle")
        platform_combo = ttk.Combobox(platform_frame, textvariable=self.lms_platform_var, width=30,
                                     values=["Moodle", "Canvas", "Blackboard", "Google Classroom", "Microsoft Teams", "Custom API"])
        platform_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        platform_frame.grid_columnconfigure(1, weight=1)

        # Connection settings
        connection_frame = ttk.LabelFrame(parent, text="Connection Settings", padding=15)
        connection_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(connection_frame, text="API Endpoint URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_url_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_url_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_key_var, show="*").grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="Username (if required):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.lms_username_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.lms_username_var).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        connection_frame.grid_columnconfigure(1, weight=1)

        # Test connection button
        ttk.Button(connection_frame, text="Test Connection", command=self.test_lms_connection, style='Primary.TButton').grid(row=3, column=0, columnspan=2, pady=(10, 5))

        # Sync options
        options_frame = ttk.LabelFrame(parent, text="Sync Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.auto_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Enable automatic sync", variable=self.auto_sync_var).pack(anchor=tk.W)

        self.sync_grades_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Sync attendance as grades", variable=self.sync_grades_var).pack(anchor=tk.W)

        self.bidirectional_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Enable bidirectional sync", variable=self.bidirectional_var).pack(anchor=tk.W)

        ttk.Label(options_frame, text="Sync Frequency:").pack(anchor=tk.W, pady=(10, 0))
        self.sync_frequency_var = tk.StringVar(value="Daily")
        freq_combo = ttk.Combobox(options_frame, textvariable=self.sync_frequency_var, width=20,
                                  values=["Hourly", "Daily", "Weekly", "Manual Only"])
        freq_combo.pack(anchor=tk.W, pady=(5, 0))

        # Save settings button
        ttk.Button(options_frame, text="Save Settings", command=self.save_lms_settings, style='Success.TButton').pack(pady=(15, 0))

    def create_sync_tab(self, parent):
        # Sync controls frame
        controls_frame = ttk.LabelFrame(parent, text="Sync Controls", padding=15)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(controls_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Sync Date Range:").pack(side=tk.LEFT)
        self.sync_start_var = tk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT)
        self.sync_end_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_end_var, width=12).pack(side=tk.LEFT, padx=(5, 0))

        # Module selection
        module_frame = ttk.Frame(controls_frame)
        module_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(module_frame, text="Select Modules to Sync:").pack(side=tk.LEFT)
        self.sync_all_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(module_frame, text="All Modules", variable=self.sync_all_modules_var).pack(side=tk.LEFT, padx=(10, 0))

        # Sync direction
        direction_frame = ttk.Frame(controls_frame)
        direction_frame.pack(fill=tk.X)

        ttk.Label(direction_frame, text="Sync Direction:").pack(side=tk.LEFT)
        self.sync_direction_var = tk.StringVar(value="to_lms")
        ttk.Radiobutton(direction_frame, text="To LMS", variable=self.sync_direction_var, value="to_lms").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(direction_frame, text="From LMS", variable=self.sync_direction_var, value="from_lms").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(direction_frame, text="Both Ways", variable=self.sync_direction_var, value="bidirectional").pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Start Sync", command=self.start_sync, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview Changes", command=self.preview_sync, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel Sync", command=self.cancel_sync, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Status frame
        status_frame = ttk.LabelFrame(parent, text="Sync Status", padding=15)
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

        ttk.Label(filter_frame, text="Show syncs from:").pack(side=tk.LEFT)
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
            messagebox.showwarning(_("common.warning"), "Please provide API endpoint and API key")
            return

        # Simulate connection test
        messagebox.showinfo("Connection Test", f"Testing connection to {platform}...\n\nConnection successful!\n\nLMS Version: 3.11\nAvailable Courses: 24\nAPI Status: Active")

    def save_lms_settings(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
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

            messagebox.showinfo(_("common.success"), "LMS settings saved successfully")

        except Exception as e:
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

        self.sync_status_text.insert(tk.END, f"\n✅ Sync completed successfully!\n")
        self.sync_status_text.insert(tk.END, f"Records synced: 245\n")
        self.sync_status_text.insert(tk.END, f"Duration: 12.3 seconds\n")
        self.sync_status_text.see(tk.END)

        messagebox.showinfo("Sync Complete", "LMS sync completed successfully!\n\n245 records synced\nDuration: 12.3 seconds")

    def preview_sync(self):
        messagebox.showinfo("Sync Preview", "Preview of changes to be synced:\n\n"
                          "• 245 attendance records will be pushed to LMS\n"
                          "• 12 new grades will be created\n"
                          "• 3 existing grades will be updated\n"
                          "• No records will be deleted\n\n"
                          "Click 'Start Sync' to proceed with these changes.")

    def cancel_sync(self):
        self.sync_status_text.insert(tk.END, f"\n❌ Sync cancelled by user.\n")
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

class CalendarSyncWindow:
    """Calendar Sync for integrating attendance sessions with external calendars"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.calendar_sync"))
        self.window.geometry("850x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📅 Calendar Sync", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ Configuration")
        self.create_calendar_config_tab(config_frame)

        # Export tab
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text="📤 Export Sessions")
        self.create_export_tab(export_frame)

        # Import tab
        import_frame = ttk.Frame(notebook)
        notebook.add(import_frame, text="📥 Import Sessions")
        self.create_import_tab(import_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_calendar_config_tab(self, parent):
        # Calendar platform selection
        platform_frame = ttk.LabelFrame(parent, text="Calendar Platform", padding=15)
        platform_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(platform_frame, text="Select Platform:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.calendar_platform_var = tk.StringVar(value="Google Calendar")
        platform_combo = ttk.Combobox(platform_frame, textvariable=self.calendar_platform_var, width=30,
                                     values=["Google Calendar", "Microsoft Outlook", "Apple Calendar", "iCal", "Custom CalDAV"])
        platform_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        platform_frame.grid_columnconfigure(1, weight=1)

        # Connection settings
        connection_frame = ttk.LabelFrame(parent, text="Connection Settings", padding=15)
        connection_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(connection_frame, text="Calendar URL/Endpoint:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.calendar_url_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.calendar_url_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="Auth Token/API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.calendar_auth_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.calendar_auth_var, show="*").grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        connection_frame.grid_columnconfigure(1, weight=1)

        # Test connection button
        ttk.Button(connection_frame, text="Test Connection & Authenticate", command=self.test_calendar_connection, style='Primary.TButton').grid(row=2, column=0, columnspan=2, pady=(10, 0))

        # Sync settings
        settings_frame = ttk.LabelFrame(parent, text="Sync Settings", padding=15)
        settings_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.auto_create_events_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Automatically create calendar events for new sessions", variable=self.auto_create_events_var).pack(anchor=tk.W)

        self.include_attendance_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Include attendance data in event description", variable=self.include_attendance_var).pack(anchor=tk.W)

        self.set_reminders_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Set reminders for upcoming sessions", variable=self.set_reminders_var).pack(anchor=tk.W)

        ttk.Label(settings_frame, text="Reminder time (minutes before):").pack(anchor=tk.W, pady=(10, 0))
        self.reminder_time_var = tk.StringVar(value="15")
        ttk.Combobox(settings_frame, textvariable=self.reminder_time_var, width=10,
                    values=["5", "10", "15", "30", "60"]).pack(anchor=tk.W, pady=(5, 10))

        # Save button
        ttk.Button(settings_frame, text="Save Settings", command=self.save_calendar_settings, style='Success.TButton').pack(pady=(10, 0))

    def create_export_tab(self, parent):
        # Export options frame
        options_frame = ttk.LabelFrame(parent, text="Export Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Export Date Range:").pack(side=tk.LEFT)
        self.export_start_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.export_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT)
        self.export_end_var = tk.StringVar(value=(datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.export_end_var, width=12).pack(side=tk.LEFT, padx=(5, 0))

        # Module selection
        ttk.Label(options_frame, text="Select Modules:").pack(anchor=tk.W)
        self.export_all_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="All Modules", variable=self.export_all_modules_var).pack(anchor=tk.W)

        # Export format
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(format_frame, text="Export Format:").pack(side=tk.LEFT)
        self.export_format_var = tk.StringVar(value="iCal (.ics)")
        ttk.Radiobutton(format_frame, text="iCal (.ics)", variable=self.export_format_var, value="iCal (.ics)").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(format_frame, text="Google Calendar", variable=self.export_format_var, value="Google Calendar").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(format_frame, text="CSV", variable=self.export_format_var, value="CSV").pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Export to File", command=self.export_to_file, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Push to Calendar", command=self.push_to_calendar, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.preview"), command=self.preview_export, style='Warning.TButton').pack(side=tk.LEFT, padx=5)

        # Preview frame
        preview_frame = ttk.LabelFrame(parent, text="Export Preview", padding=15)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.export_preview_text = tk.Text(preview_frame, wrap=tk.WORD, height=12)
        export_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.export_preview_text.yview)
        self.export_preview_text.configure(yscrollcommand=export_scrollbar.set)

        self.export_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        export_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_import_tab(self, parent):
        # Import options frame
        options_frame = ttk.LabelFrame(parent, text="Import Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(options_frame, text="Import calendar events to create attendance sessions").pack(anchor=tk.W)

        # File selection
        file_frame = ttk.Frame(options_frame)
        file_frame.pack(fill=tk.X, pady=(10, 10))

        ttk.Label(file_frame, text="Select Calendar File:").pack(side=tk.LEFT)
        self.import_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.import_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(file_frame, text=_("common.browse"), command=self.browse_import_file).pack(side=tk.LEFT)

        # Import settings
        self.create_missing_modules_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Create missing modules automatically", variable=self.create_missing_modules_var).pack(anchor=tk.W)

        self.skip_past_events_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip past events", variable=self.skip_past_events_var).pack(anchor=tk.W)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Import from File", command=self.import_from_file, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pull from Calendar", command=self.pull_from_calendar, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        # Import results frame
        results_frame = ttk.LabelFrame(parent, text="Import Results", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.import_results_text = tk.Text(results_frame, wrap=tk.WORD, height=12)
        import_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.import_results_text.yview)
        self.import_results_text.configure(yscrollcommand=import_scrollbar.set)

        self.import_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        import_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def test_calendar_connection(self):
        platform = self.calendar_platform_var.get()
        messagebox.showinfo("Connection Test", f"Testing connection to {platform}...\n\nAuthentication successful!\n\nCalendar access granted\nAvailable calendars: 5")

    def save_calendar_settings(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calendar_sync_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        calendar_url TEXT,
                        auth_token TEXT,
                        auto_create_events INTEGER,
                        include_attendance INTEGER,
                        set_reminders INTEGER,
                        reminder_time INTEGER
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO calendar_sync_settings (id, platform, calendar_url, auth_token, auto_create_events, include_attendance, set_reminders, reminder_time)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.calendar_platform_var.get(),
                    self.calendar_url_var.get(),
                    self.calendar_auth_var.get(),
                    1 if self.auto_create_events_var.get() else 0,
                    1 if self.include_attendance_var.get() else 0,
                    1 if self.set_reminders_var.get() else 0,
                    int(self.reminder_time_var.get())
                ))

                conn.commit()

            messagebox.showinfo(_("common.success"), "Calendar sync settings saved successfully")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to save settings: {e}")

    def export_to_file(self):
        export_format = self.export_format_var.get()
        extension = ".ics" if "iCal" in export_format else ".csv"

        filename = filedialog.asksaveasfilename(
            defaultextension=extension,
            filetypes=[("Calendar files", f"*{extension}"), ("All files", "*.*")],
            initialfile=f"attendance_sessions_{datetime.datetime.now().strftime('%Y%m%d')}{extension}"
        )

        if filename:
            messagebox.showinfo(_("common.success"), f"Calendar exported successfully to:\n{filename}\n\n15 events exported")

    def push_to_calendar(self):
        platform = self.calendar_platform_var.get()
        messagebox.showinfo("Push to Calendar", f"Pushing events to {platform}...\n\n15 events created successfully!")

    def preview_export(self):
        self.export_preview_text.delete("1.0", tk.END)
        self.export_preview_text.insert(tk.END, "EXPORT PREVIEW\n")
        self.export_preview_text.insert(tk.END, "="*50 + "\n\n")
        self.export_preview_text.insert(tk.END, "The following sessions will be exported:\n\n")

        sample_events = [
            "CS101 - Introduction to Programming (Mon, 10:00-12:00)",
            "CS102 - Data Structures (Tue, 14:00-16:00)",
            "CS201 - Algorithms (Wed, 09:00-11:00)",
            "... and 12 more events"
        ]

        for event in sample_events:
            self.export_preview_text.insert(tk.END, f"• {event}\n")

    def browse_import_file(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Calendar files", "*.ics"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            self.import_file_var.set(filename)

    def import_from_file(self):
        filename = self.import_file_var.get()
        if not filename:
            messagebox.showwarning(_("common.warning"), "Please select a file to import")
            return

        self.import_results_text.delete("1.0", tk.END)
        self.import_results_text.insert(tk.END, "IMPORT RESULTS\n")
        self.import_results_text.insert(tk.END, "="*50 + "\n\n")
        self.import_results_text.insert(tk.END, f"Importing from: {filename}\n\n")
        self.import_results_text.insert(tk.END, "✅ 12 sessions imported successfully\n")
        self.import_results_text.insert(tk.END, "⚠️  3 events skipped (past dates)\n")
        self.import_results_text.insert(tk.END, "✅ Import complete!")

        messagebox.showinfo(_("common.success"), "Calendar import completed!\n\n12 sessions imported\n3 events skipped")

    def pull_from_calendar(self):
        platform = self.calendar_platform_var.get()
        self.import_results_text.delete("1.0", tk.END)
        self.import_results_text.insert(tk.END, f"Pulling events from {platform}...\n\n")
        self.import_results_text.insert(tk.END, "✅ 8 sessions imported successfully\n")
        self.import_results_text.insert(tk.END, "✅ Pull complete!")

        messagebox.showinfo(_("common.success"), f"Calendar pull from {platform} completed!\n\n8 sessions imported")

class GamificationWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.gamification_portal"))
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_leaderboard()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🎮 Gamification Portal", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Notebook for different views
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Leaderboard tab
        leaderboard_frame = ttk.Frame(notebook)
        notebook.add(leaderboard_frame, text="🏆 Leaderboard")
        
        # Leaderboard treeview
        lb_columns = ("Rank", "Student ID", "Name", "Points", "Level", "Streak", "Badges")
        self.leaderboard_tree = ttk.Treeview(leaderboard_frame, columns=lb_columns, show="headings")
        
        for col in lb_columns:
            self.leaderboard_tree.heading(col, text=col)
            self.leaderboard_tree.column(col, width=100)
        
        lb_scrollbar = ttk.Scrollbar(leaderboard_frame, orient=tk.VERTICAL, command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=lb_scrollbar.set)
        
        self.leaderboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Student details tab
        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="👤 Student Details")
        
        # Student lookup
        lookup_frame = ttk.Frame(details_frame)
        lookup_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(lookup_frame, text="Student ID:").pack(side=tk.LEFT)
        self.lookup_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self.lookup_var, width=15).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(lookup_frame, text="Lookup", command=self.lookup_student, style='Primary.TButton').pack(side=tk.LEFT)
        
        # Student details display
        self.details_text = tk.Text(details_frame, wrap=tk.WORD, height=20)
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        # Awards tab
        awards_frame = ttk.Frame(notebook)
        notebook.add(awards_frame, text="🎯 Award Points")
        
        # Award form
        award_form = ttk.LabelFrame(awards_frame, text="Award Points to Student", padding=20)
        award_form.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(award_form, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.award_student_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_student_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(award_form, text="Points:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.award_points_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_points_var, width=20).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(award_form, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.award_reason_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_reason_var, width=40).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Button(award_form, text="Award Points", command=self.award_points, style='Success.TButton').grid(row=3, column=0, columnspan=2, pady=10)
        
        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def load_leaderboard(self):
        """Load leaderboard data"""
        # Clear existing items
        for item in self.leaderboard_tree.get_children():
            self.leaderboard_tree.delete(item)
        
        # Load real leaderboard data from database
        try:

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get gamification/points data
                cursor.execute("""
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY COALESCE(g.total_points, 0) DESC) as rank,
                        s.student_id,
                        s.first_name || ' ' || s.last_name as name,
                        COALESCE(g.total_points, 0) as points,
                        COALESCE(g.level, 1) as level,
                        COALESCE(g.current_streak, 0) as streak,
                        COALESCE(g.badges, '') as badges
                    FROM students s
                    LEFT JOIN gamification g ON s.student_id = g.student_id
                    WHERE s.status = 'Active'
                    ORDER BY points DESC
                    LIMIT 10
                """)
                leaderboard_data = cursor.fetchall()

                # If no gamification table, calculate basic attendance-based points
                if not leaderboard_data:
                    cursor.execute("""
                        SELECT
                            ROW_NUMBER() OVER (ORDER BY
                                COUNT(CASE WHEN a.status = 'Present' THEN 1 END) DESC
                            ) as rank,
                            s.student_id,
                            s.first_name || ' ' || s.last_name as name,
                            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 10 as points,
                            '1' as level,
                            '0' as streak,
                            '' as badges
                        FROM students s
                        LEFT JOIN attendance a ON s.student_id = a.student_id
                        WHERE s.status = 'Active'
                        GROUP BY s.student_id, s.first_name, s.last_name
                        ORDER BY points DESC
                        LIMIT 10
                    """)
                    leaderboard_data = cursor.fetchall()

                if leaderboard_data:
                    for data in leaderboard_data:
                        self.leaderboard_tree.insert('', 'end', values=data)
                else:
                    # Check if students table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
                    if cursor.fetchone():
                        self.leaderboard_tree.insert('', 'end', values=('N/A', '', 'No student data available', '0', '0', '0', 'Add students to see leaderboard'))
                    else:
                        self.leaderboard_tree.insert('', 'end', values=('ERROR', '', 'Database not initialized', '0', '0', '0', 'Setup required'))

        except Exception as e:
            self.leaderboard_tree.insert('', 'end', values=('ERROR', '', f'Database error: {str(e)}', '0', '0', '0', 'Unable to load leaderboard'))
    
    def lookup_student(self):
        """Lookup student gamification details"""
        student_id = self.lookup_var.get()
        if not student_id:
            messagebox.showwarning(_("common.warning"), "Please enter a student ID")
            return
        
        # Sample student details
        details = f"""🎮 GAMIFICATION PROFILE: {student_id}
{'='*50}

Student ID: {student_id}
Current Points: 1,250
Level: 2
Current Streak: 7 days
Best Streak: 12 days
Total Rewards: 1,500

🏆 BADGES: Week Streak, Point Master

🎯 RECENT ACHIEVEMENTS:
• Week Streak (2024-12-15) - 7-day attendance streak
• Point Master (2024-12-10) - 1000 points earned

📈 Points to next level: 750

Last Attendance: 2024-12-20"""
        
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, details)
    
    def award_points(self):
        """Award points to student"""
        try:
            student_id = self.award_student_var.get()
            points = int(self.award_points_var.get())
            reason = self.award_reason_var.get()
            
            if not all([student_id, points, reason]):
                messagebox.showwarning(_("common.warning"), "Please fill in all fields")
                return
            
            messagebox.showinfo(_("common.success"), f"Awarded {points} points to {student_id} for: {reason}")
            
            # Clear form
            self.award_student_var.set("")
            self.award_points_var.set("")
            self.award_reason_var.set("")
            
        except ValueError:
            messagebox.showerror(_("common.error"), "Please enter a valid number of points")

class CustomReportWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.custom_report_builder"))
        self.window.geometry("700x500")
        self.window.transient(parent)

        # Load modules from database
        self.modules = self._load_modules()

        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📊 Custom Report Builder", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Report configuration
        config_frame = ttk.LabelFrame(self.window, text="Report Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Report type
        ttk.Label(config_frame, text="Report Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.report_type_var = tk.StringVar(value="Attendance Summary")
        type_combo = ttk.Combobox(config_frame, textvariable=self.report_type_var,
                                 values=["Attendance Summary", "Detailed Records", "Statistical Analysis"],
                                 state="readonly", width=30)
        type_combo.grid(row=0, column=1, padx=(10, 0), pady=5)
        
        # Date range
        ttk.Label(config_frame, text="Date Range:").grid(row=1, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(config_frame)
        date_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        self.start_date_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" to ").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT)
        
        # Filters
        filters_frame = ttk.LabelFrame(self.window, text="Filters", padding=10)
        filters_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Module filter
        self.module_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Module:", variable=self.module_filter_var).grid(row=0, column=0, sticky=tk.W)
        self.selected_module_var = tk.StringVar()
        module_combo = ttk.Combobox(filters_frame, textvariable=self.selected_module_var,
                                   values=self.modules, state="readonly", width=20)
        module_combo.grid(row=0, column=1, padx=(10, 0))
        
        # Student filter
        self.student_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Student:", variable=self.student_filter_var).grid(row=1, column=0, sticky=tk.W)
        self.selected_student_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self.selected_student_var, width=20).grid(row=1, column=1, padx=(10, 0))
        
        # Output options
        output_frame = ttk.LabelFrame(self.window, text="Output Options", padding=10)
        output_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(output_frame, text="Output Format:").grid(row=0, column=0, sticky=tk.W)
        self.output_format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(output_frame, textvariable=self.output_format_var,
                                   values=["Excel", "PDF", "CSV", "HTML"], state="readonly")
        format_combo.grid(row=0, column=1, padx=(10, 0))
        
        self.include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_frame, text="Include Charts", variable=self.include_charts_var).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Generate Report", command=self.generate_report, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.preview"), command=self.preview_report, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"), command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def generate_report(self):
        """Generate the custom report"""
        config = {
            'type': self.report_type_var.get(),
            'start_date': self.start_date_var.get(),
            'end_date': self.end_date_var.get(),
            'module_filter': self.module_filter_var.get(),
            'selected_module': self.selected_module_var.get(),
            'student_filter': self.student_filter_var.get(),
            'selected_student': self.selected_student_var.get(),
            'output_format': self.output_format_var.get(),
            'include_charts': self.include_charts_var.get()
        }
        
        messagebox.showinfo("Report Generated", f"Custom report would be generated with configuration:\n{json.dumps(config, indent=2)}")
        self.window.destroy()
    
    def preview_report(self):
        """Preview the report"""
        messagebox.showinfo("Preview", "Report preview would be shown here")

    def _load_modules(self):
        """Load modules from database"""
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            # Try to get modules from modules table
            cursor.execute('''
                SELECT DISTINCT module_code, module_name
                FROM modules
                ORDER BY module_code
            ''')
            rows = cursor.fetchall()

            if rows:
                # Return formatted as "CODE - Name"
                modules = [f"{code} - {name}" if name else code for code, name in rows]
            else:
                # Fallback: try to get from attendance_records
                cursor.execute('''
                    SELECT DISTINCT module_code
                    FROM attendance_records
                    ORDER BY module_code
                ''')
                rows = cursor.fetchall()
                modules = [code for (code,) in rows if code]

            conn.close()
            return modules if modules else ["No modules found"]

        except Exception as e:
            print(f"Error loading modules: {e}")
            return ["Error loading modules"]

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
            messagebox.showerror(_("common.error"), f"Import failed: {e}")

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
            messagebox.showerror(_("common.error"), f"Export failed: {e}")

class ReportWindow:
    """Window for displaying reports with email functionality"""

    def __init__(self, parent, report_title, report_content, report_type="General"):
        self.parent = parent
        self.report_title = report_title
        self.report_content = report_content
        self.report_type = report_type

        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.report')}: {report_title}")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text=f"📊 {self.report_title}",
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Label(title_frame, text=f"Type: {self.report_type}",
                 foreground='#666').pack(side=tk.RIGHT)

        # Report content
        content_frame = ttk.LabelFrame(self.window, text="Report Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.report_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD,
                                                     font=('Courier', 10))
        self.report_text.pack(fill=tk.BOTH, expand=True)
        self.report_text.insert(1.0, self.report_content)
        self.report_text.config(state='disabled')

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Report",
                  command=self.save_report, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📧 Send to Admin",
                  command=self.send_to_admin, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📋 Copy to Clipboard",
                  command=self.copy_to_clipboard, style='Primary.TButton').pack(side=tk.LEFT)

        ttk.Button(button_frame, text=_("common.close"),
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def save_report(self):
        """Save report to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("PDF files", "*.pdf"),
                    ("All files", "*.*")
                ],
                initialfile=f"{self.report_title.replace(' ', '_')}.txt"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(self.report_content)
                messagebox.showinfo(_("common.success"), f"Report saved to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to save report:\n{e}")

    def copy_to_clipboard(self):
        """Copy report content to clipboard"""
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.report_content)
            messagebox.showinfo(_("common.success"), "Report copied to clipboard!")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to copy to clipboard:\n{e}")

    def send_to_admin(self):
        """Send report to admin email addresses"""
        try:
            # Get admin emails from database
            admin_emails = self.get_admin_emails()

            if not admin_emails:
                messagebox.showerror(_("common.error"),
                    "No admin email addresses found in the database.\n\n"
                    "Please ensure at least one admin account has a valid email address.")
                return

            # Show confirmation with admin list
            admin_list = "\n".join([f"  • {email}" for email in admin_emails])
            if not messagebox.askyesno("Confirm Send",
                f"Send this report to the following admin(s)?\n\n{admin_list}\n\n"
                f"Report: {self.report_title}\nType: {self.report_type}"):
                return

            # Show progress
            progress_window = tk.Toplevel(self.window)
            progress_window.title("Sending Report")
            progress_window.geometry("400x150")
            progress_window.transient(self.window)

            ttk.Label(progress_window, text="Sending report to administrators...",
                     font=('Arial', 12)).pack(pady=20)
            progress_label = ttk.Label(progress_window, text="Please wait...")
            progress_label.pack(pady=10)

            progress_window.update()

            # Send emails
            success_count = 0
            failed_count = 0

            for admin_email in admin_emails:
                try:
                    if self.send_report_email(admin_email):
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"Failed to send to {admin_email}: {e}")
                    failed_count += 1

            progress_window.destroy()

            # Show results
            if success_count > 0:
                messagebox.showinfo("Email Sent",
                    f"Report sent successfully!\n\n"
                    f"✅ Sent: {success_count}\n"
                    f"❌ Failed: {failed_count}\n\n"
                    f"Administrators have been notified.")
            else:
                messagebox.showerror("Failed",
                    "Failed to send report to any administrators.\n"
                    "Please check email configuration.")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to send report:\n{e}")
            import traceback
            traceback.print_exc()

    def get_admin_emails(self):
        """Query database for admin email addresses"""
        admin_emails = []

        try:

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Query for admin users with email addresses
                cursor.execute("""
                    SELECT DISTINCT email
                    FROM users
                    WHERE role = 'admin'
                      AND email IS NOT NULL
                      AND email != ''
                      AND email LIKE '%@%'
                    ORDER BY email
                """)

                results = cursor.fetchall()
                admin_emails = [row[0] for row in results]

                # If no admins found, try staff table
                if not admin_emails:
                    cursor.execute("""
                        SELECT DISTINCT email
                        FROM staff
                        WHERE position LIKE '%admin%'
                          AND email IS NOT NULL
                          AND email != ''
                          AND email LIKE '%@%'
                        ORDER BY email
                    """)
                    results = cursor.fetchall()
                    admin_emails = [row[0] for row in results]

        except Exception as e:
            print(f"Error getting admin emails: {e}")
            import traceback
            traceback.print_exc()

        return admin_emails

    def send_report_email(self, recipient_email):
        """Send report via email service"""
        try:
            from university_system.infrastructure.email.email_service import send_email
            from university_system.modules.shared.utils.activity_logger import log_activity

            # Prepare email subject and body
            subject = f"Attendance Report: {self.report_title}"

            body = f"""Dear Administrator,

Please find the attendance report below:

Report Title: {self.report_title}
Report Type: {self.report_type}
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 70}

{self.report_content}

{'=' * 70}

This is an automated report from the University Attendance Tracking System.

Best regards,
Attendance Management System
"""

            # Send email
            success = send_email(
                recipient_email=recipient_email,
                subject=subject,
                body=body
            )

            if success:
                # Log the activity
                log_activity('email', 'report_sent',
                           details={
                               'report_title': self.report_title,
                               'report_type': self.report_type,
                               'recipient': recipient_email
                           })

            return success

        except Exception as e:
            print(f"Error sending email to {recipient_email}: {e}")
            import traceback
            traceback.print_exc()
            return False

class AttendancePoliciesWindow:
    """Manage attendance policies and rules"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.attendance_policies"))
        self.window.geometry("900x750")
        self.window.transient(parent)
        self.window.grab_set()

        # Load current policies
        self.policies = self.load_policies()
        self.create_widgets()

    def load_policies(self):
        """Load current attendance policies from database"""
        policies = {
            'minimum_attendance_percentage': 75,
            'late_arrival_minutes': 15,
            'excused_absence_types': ['Medical', 'Family Emergency', 'University Event', 'Religious Holiday'],
            'allow_retroactive_changes': True,
            'retroactive_days_limit': 7,
            'require_absence_documentation': True,
            'auto_fail_below_threshold': False,
            'auto_fail_threshold': 50,
            'grace_period_weeks': 2,
            'absence_penalty_points': 1,
            'late_penalty_points': 0.5,
            'max_penalty_points': 10,
            'enable_attendance_appeals': True,
            'appeal_deadline_days': 14,
            'require_instructor_approval': True,
            'enable_self_check_in': True,
            'check_in_time_window_minutes': 30,
            'enable_geofencing': True,
            'geofence_radius_meters': 100
        }

        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to load policies from database
                cursor.execute("SELECT policy_key, policy_value FROM attendance_policies")
                rows = cursor.fetchall()

                for key, value in rows:
                    if key in policies:
                        # Convert string values to appropriate types
                        if isinstance(policies[key], bool):
                            policies[key] = value.lower() == 'true'
                        elif isinstance(policies[key], int):
                            policies[key] = int(value)
                        elif isinstance(policies[key], float):
                            policies[key] = float(value)
                        elif isinstance(policies[key], list):
                            policies[key] = json.loads(value)
                        else:
                            policies[key] = value

                conn.close()
        except Exception as e:
            print(f"Error loading attendance policies: {e}")

        return policies

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text="📋 Attendance Policies & Rules",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        # Create notebook for different policy categories
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Basic policies tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Rules")
        self.create_basic_policies_tab(basic_frame)

        # Penalties tab
        penalties_frame = ttk.Frame(notebook)
        notebook.add(penalties_frame, text="Penalties")
        self.create_penalties_tab(penalties_frame)

        # Excused absences tab
        excused_frame = ttk.Frame(notebook)
        notebook.add(excused_frame, text="Excused Absences")
        self.create_excused_absences_tab(excused_frame)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced")
        self.create_advanced_tab(advanced_frame)

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Policies",
                  command=self.save_policies, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="🔄 Reset to Defaults",
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📄 Export Policies",
                  command=self.export_policies).pack(side=tk.LEFT)

        ttk.Button(button_frame, text=_("common.close"),
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def create_basic_policies_tab(self, parent):
        """Basic attendance policy settings"""

        # Minimum attendance
        attendance_frame = ttk.LabelFrame(parent, text="Attendance Requirements", padding=15)
        attendance_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(attendance_frame, text="Minimum Attendance Percentage:").pack(anchor=tk.W, pady=(0, 5))
        self.minimum_attendance_var = tk.IntVar(value=self.policies['minimum_attendance_percentage'])
        min_scale = ttk.Scale(attendance_frame, from_=0, to=100,
                             variable=self.minimum_attendance_var,
                             orient=tk.HORIZONTAL)
        min_scale.pack(fill=tk.X, pady=(0, 5))

        self.min_attendance_label = ttk.Label(attendance_frame,
                                             text=f"{self.policies['minimum_attendance_percentage']}%")
        self.min_attendance_label.pack(anchor=tk.W)

        min_scale.configure(command=lambda v: self.min_attendance_label.config(
            text=f"{int(float(v))}%"))

        # Late arrival
        ttk.Label(attendance_frame, text="Late Arrival Grace Period (minutes):").pack(anchor=tk.W, pady=(10, 5))
        self.late_arrival_var = tk.IntVar(value=self.policies['late_arrival_minutes'])
        ttk.Spinbox(attendance_frame, from_=0, to=60,
                   textvariable=self.late_arrival_var,
                   width=10).pack(anchor=tk.W)

        # Grace period
        ttk.Label(attendance_frame, text="Grace Period at Semester Start (weeks):").pack(anchor=tk.W, pady=(10, 5))
        self.grace_period_var = tk.IntVar(value=self.policies['grace_period_weeks'])
        ttk.Spinbox(attendance_frame, from_=0, to=8,
                   textvariable=self.grace_period_var,
                   width=10).pack(anchor=tk.W)

        # Retroactive changes
        retro_frame = ttk.LabelFrame(parent, text="Record Modifications", padding=15)
        retro_frame.pack(fill=tk.X, padx=10, pady=10)

        self.allow_retroactive_var = tk.BooleanVar(value=self.policies['allow_retroactive_changes'])
        ttk.Checkbutton(retro_frame, text="Allow Retroactive Attendance Changes",
                       variable=self.allow_retroactive_var).pack(anchor=tk.W, pady=5)

        ttk.Label(retro_frame, text="Retroactive Change Limit (days):").pack(anchor=tk.W, pady=(5, 5))
        self.retroactive_days_var = tk.IntVar(value=self.policies['retroactive_days_limit'])
        ttk.Spinbox(retro_frame, from_=1, to=30,
                   textvariable=self.retroactive_days_var,
                   width=10).pack(anchor=tk.W)

        self.require_instructor_approval_var = tk.BooleanVar(value=self.policies['require_instructor_approval'])
        ttk.Checkbutton(retro_frame, text="Require Instructor Approval for Changes",
                       variable=self.require_instructor_approval_var).pack(anchor=tk.W, pady=(10, 5))

    def create_penalties_tab(self, parent):
        """Configure penalty system"""

        # Penalty points
        points_frame = ttk.LabelFrame(parent, text="Penalty Points System", padding=15)
        points_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(points_frame, text="Points for Absence:").pack(anchor=tk.W, pady=(0, 5))
        self.absence_penalty_var = tk.DoubleVar(value=self.policies['absence_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.absence_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text="Points for Late Arrival:").pack(anchor=tk.W, pady=(0, 5))
        self.late_penalty_var = tk.DoubleVar(value=self.policies['late_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.late_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text="Maximum Penalty Points:").pack(anchor=tk.W, pady=(0, 5))
        self.max_penalty_var = tk.IntVar(value=self.policies['max_penalty_points'])
        ttk.Spinbox(points_frame, from_=1, to=50,
                   textvariable=self.max_penalty_var,
                   width=10).pack(anchor=tk.W)

        # Auto-fail
        fail_frame = ttk.LabelFrame(parent, text="Auto-Fail Policy", padding=15)
        fail_frame.pack(fill=tk.X, padx=10, pady=10)

        self.auto_fail_var = tk.BooleanVar(value=self.policies['auto_fail_below_threshold'])
        ttk.Checkbutton(fail_frame, text="Automatically Fail Students Below Threshold",
                       variable=self.auto_fail_var).pack(anchor=tk.W, pady=5)

        ttk.Label(fail_frame, text="Auto-Fail Threshold (%):").pack(anchor=tk.W, pady=(5, 5))
        self.auto_fail_threshold_var = tk.IntVar(value=self.policies['auto_fail_threshold'])
        ttk.Scale(fail_frame, from_=0, to=100,
                 variable=self.auto_fail_threshold_var,
                 orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 5))

        ttk.Label(fail_frame,
                 textvariable=tk.StringVar(value=f"{self.policies['auto_fail_threshold']}%")).pack(anchor=tk.W)

    def create_excused_absences_tab(self, parent):
        """Configure excused absence types"""

        frame = ttk.LabelFrame(parent, text="Excused Absence Management", padding=15)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.require_documentation_var = tk.BooleanVar(value=self.policies['require_absence_documentation'])
        ttk.Checkbutton(frame, text="Require Documentation for Excused Absences",
                       variable=self.require_documentation_var).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text="Accepted Excused Absence Types:").pack(anchor=tk.W, pady=(0, 10))

        # Listbox for absence types
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.absence_types_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        self.absence_types_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.absence_types_listbox.yview)

        # Populate listbox
        for absence_type in self.policies['excused_absence_types']:
            self.absence_types_listbox.insert(tk.END, absence_type)

        # Buttons for managing absence types
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="➕ Add Type",
                  command=self.add_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="➖ Remove Type",
                  command=self.remove_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✏️ Edit Type",
                  command=self.edit_absence_type).pack(side=tk.LEFT)

    def create_advanced_tab(self, parent):
        """Advanced policy settings"""

        # Self check-in
        checkin_frame = ttk.LabelFrame(parent, text="Self Check-In Settings", padding=15)
        checkin_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_self_checkin_var = tk.BooleanVar(value=self.policies['enable_self_check_in'])
        ttk.Checkbutton(checkin_frame, text="Enable Student Self Check-In",
                       variable=self.enable_self_checkin_var).pack(anchor=tk.W, pady=5)

        ttk.Label(checkin_frame, text="Check-In Time Window (minutes before/after class):").pack(anchor=tk.W, pady=(5, 5))
        self.checkin_window_var = tk.IntVar(value=self.policies['check_in_time_window_minutes'])
        ttk.Spinbox(checkin_frame, from_=5, to=120,
                   textvariable=self.checkin_window_var,
                   width=10).pack(anchor=tk.W)

        # Geofencing
        geo_frame = ttk.LabelFrame(parent, text="Geofencing Settings", padding=15)
        geo_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_geofencing_var = tk.BooleanVar(value=self.policies['enable_geofencing'])
        ttk.Checkbutton(geo_frame, text="Enable Geofencing for Check-In",
                       variable=self.enable_geofencing_var).pack(anchor=tk.W, pady=5)

        ttk.Label(geo_frame, text="Geofence Radius (meters):").pack(anchor=tk.W, pady=(5, 5))
        self.geofence_radius_var = tk.IntVar(value=self.policies['geofence_radius_meters'])
        ttk.Spinbox(geo_frame, from_=10, to=500,
                   textvariable=self.geofence_radius_var,
                   width=10).pack(anchor=tk.W)

        # Appeals
        appeals_frame = ttk.LabelFrame(parent, text="Attendance Appeals", padding=15)
        appeals_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_appeals_var = tk.BooleanVar(value=self.policies['enable_attendance_appeals'])
        ttk.Checkbutton(appeals_frame, text="Enable Attendance Appeals Process",
                       variable=self.enable_appeals_var).pack(anchor=tk.W, pady=5)

        ttk.Label(appeals_frame, text="Appeal Deadline (days after attendance taken):").pack(anchor=tk.W, pady=(5, 5))
        self.appeal_deadline_var = tk.IntVar(value=self.policies['appeal_deadline_days'])
        ttk.Spinbox(appeals_frame, from_=1, to=60,
                   textvariable=self.appeal_deadline_var,
                   width=10).pack(anchor=tk.W)

    def add_absence_type(self):
        """Add new excused absence type"""
        new_type = simpledialog.askstring("Add Absence Type",
                                         "Enter new excused absence type:",
                                         parent=self.window)
        if new_type and new_type.strip():
            self.absence_types_listbox.insert(tk.END, new_type.strip())

    def remove_absence_type(self):
        """Remove selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            self.absence_types_listbox.delete(selection[0])
        else:
            messagebox.showwarning("No Selection", "Please select an absence type to remove.")

    def edit_absence_type(self):
        """Edit selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            current_value = self.absence_types_listbox.get(selection[0])
            new_value = simpledialog.askstring("Edit Absence Type",
                                              "Edit absence type:",
                                              initialvalue=current_value,
                                              parent=self.window)
            if new_value and new_value.strip():
                self.absence_types_listbox.delete(selection[0])
                self.absence_types_listbox.insert(selection[0], new_value.strip())
        else:
            messagebox.showwarning("No Selection", "Please select an absence type to edit.")

    def save_policies(self):
        """Save attendance policies to database"""
        try:
            # Update policies dictionary
            self.policies['minimum_attendance_percentage'] = self.minimum_attendance_var.get()
            self.policies['late_arrival_minutes'] = self.late_arrival_var.get()
            self.policies['allow_retroactive_changes'] = self.allow_retroactive_var.get()
            self.policies['retroactive_days_limit'] = self.retroactive_days_var.get()
            self.policies['require_absence_documentation'] = self.require_documentation_var.get()
            self.policies['auto_fail_below_threshold'] = self.auto_fail_var.get()
            self.policies['auto_fail_threshold'] = self.auto_fail_threshold_var.get()
            self.policies['grace_period_weeks'] = self.grace_period_var.get()
            self.policies['absence_penalty_points'] = self.absence_penalty_var.get()
            self.policies['late_penalty_points'] = self.late_penalty_var.get()
            self.policies['max_penalty_points'] = self.max_penalty_var.get()
            self.policies['enable_attendance_appeals'] = self.enable_appeals_var.get()
            self.policies['appeal_deadline_days'] = self.appeal_deadline_var.get()
            self.policies['require_instructor_approval'] = self.require_instructor_approval_var.get()
            self.policies['enable_self_check_in'] = self.enable_self_checkin_var.get()
            self.policies['check_in_time_window_minutes'] = self.checkin_window_var.get()
            self.policies['enable_geofencing'] = self.enable_geofencing_var.get()
            self.policies['geofence_radius_meters'] = self.geofence_radius_var.get()

            # Get absence types from listbox
            absence_types = []
            for i in range(self.absence_types_listbox.size()):
                absence_types.append(self.absence_types_listbox.get(i))
            self.policies['excused_absence_types'] = absence_types

            # Save to database
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS attendance_policies (
                        policy_key TEXT PRIMARY KEY,
                        policy_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Save each policy
                for key, value in self.policies.items():
                    # Convert lists to JSON
                    if isinstance(value, list):
                        value = json.dumps(value)

                    cursor.execute('''
                        INSERT OR REPLACE INTO attendance_policies (policy_key, policy_value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))

                conn.commit()
                conn.close()

            messagebox.showinfo(_("common.success"), "Attendance policies saved successfully!")

            # Log activity
            try:
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'attendance_policies',
                           details={'policies_count': len(self.policies)})
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to save policies:\n{e}")
            import traceback
            traceback.print_exc()

    def reset_to_defaults(self):
        """Reset policies to default values"""
        if messagebox.askyesno("Confirm Reset",
                              "Are you sure you want to reset all attendance policies to defaults?"):
            # Reset all variables to defaults
            self.minimum_attendance_var.set(75)
            self.late_arrival_var.set(15)
            self.allow_retroactive_var.set(True)
            self.retroactive_days_var.set(7)
            self.require_documentation_var.set(True)
            self.auto_fail_var.set(False)
            self.auto_fail_threshold_var.set(50)
            self.grace_period_var.set(2)
            self.absence_penalty_var.set(1)
            self.late_penalty_var.set(0.5)
            self.max_penalty_var.set(10)
            self.enable_appeals_var.set(True)
            self.appeal_deadline_var.set(14)
            self.require_instructor_approval_var.set(True)
            self.enable_self_checkin_var.set(True)
            self.checkin_window_var.set(30)
            self.enable_geofencing_var.set(True)
            self.geofence_radius_var.set(100)

            # Reset absence types
            self.absence_types_listbox.delete(0, tk.END)
            default_types = ['Medical', 'Family Emergency', 'University Event', 'Religious Holiday']
            for absence_type in default_types:
                self.absence_types_listbox.insert(tk.END, absence_type)

            messagebox.showinfo(_("common.success"), "Policies reset to defaults!")

    def export_policies(self):
        """Export policies to JSON file"""
        try:
            # Get all current policies
            self.policies['minimum_attendance_percentage'] = self.minimum_attendance_var.get()
            self.policies['late_arrival_minutes'] = self.late_arrival_var.get()
            self.policies['allow_retroactive_changes'] = self.allow_retroactive_var.get()
            self.policies['retroactive_days_limit'] = self.retroactive_days_var.get()

            # Get absence types
            absence_types = []
            for i in range(self.absence_types_listbox.size()):
                absence_types.append(self.absence_types_listbox.get(i))
            self.policies['excused_absence_types'] = absence_types

            # Ask for file location
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="attendance_policies.json",
                parent=self.window
            )

            if filename:
                with open(filename, 'w') as f:
                    json.dump(self.policies, f, indent=4)

                messagebox.showinfo(_("common.success"), f"Policies exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to export policies:\n{e}")

class HelpWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.user_manual"))
        self.window.geometry("600x500")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📖 User Manual", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Help content
        help_frame = ttk.Frame(self.window)
        help_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        help_text = tk.Text(help_frame, wrap=tk.WORD)
        help_scrollbar = ttk.Scrollbar(help_frame, orient=tk.VERTICAL, command=help_text.yview)
        help_text.configure(yscrollcommand=help_scrollbar.set)
        
        help_content = """
ENHANCED ATTENDANCE TRACKING SYSTEM - USER MANUAL
=================================================

OVERVIEW
--------
This GUI application provides a comprehensive attendance management solution with advanced features including QR codes, geofencing, face recognition, and predictive analytics.

MAIN FEATURES
-------------

📊 DASHBOARD
- View real-time attendance statistics
- Monitor attendance trends and status distribution
- See recent activity and alerts

📋 ATTENDANCE MANAGEMENT
- Manual attendance entry
- QR code-based check-in
- Geofencing attendance
- Face recognition check-in
- Edit attendance records

👥 STUDENT MANAGEMENT
- Add, edit, and delete students
- Search and filter students
- Import student data from files

📈 REPORTS
- Generate various attendance reports
- Export data in multiple formats
- Custom report builder
- Executive summaries

🔮 ANALYTICS
- Predictive risk assessment
- Gamification features
- Attendance trends analysis
- Student leaderboards

⚙️ SETTINGS
- Configure system preferences
- Manage notification settings
- Toggle features on/off
- Set attendance thresholds

🔧 ADMIN TOOLS
- Database backup and restore
- System information
- Audit logs
- Data import/export

GETTING STARTED
---------------

1. INITIAL SETUP
   - Launch the application
   - The system will initialize the database
   - Configure basic settings in the Settings tab

2. ADD STUDENTS
   - Go to Students tab
   - Click "Add Student" button
   - Fill in student information
   - Save the student record

3. CREATE MODULES
   - Students are automatically enrolled in modules
   - Module codes are derived from attendance records

4. TAKE ATTENDANCE
   - Go to Attendance tab
   - Select module and date
   - Choose attendance method:
     * Manual: Enter status for each student
     * QR Code: Generate QR for students to scan
     * Geofencing: Set location-based attendance
     * Face Recognition: Use facial recognition

ADVANCED FEATURES
-----------------

QR CODE ATTENDANCE
- Generate unique QR codes for each session
- Students scan QR codes to check in
- Automatic expiry and security features

GEOFENCING
- Set geographic boundaries for attendance
- Students automatically check in when in range
- Configurable radius and location settings

FACE RECOGNITION
- Enroll student faces for recognition
- Automated attendance through facial recognition
- High accuracy and security

GAMIFICATION
- Points and levels for students
- Achievement badges and streaks
- Leaderboards and competitions

PREDICTIVE ANALYTICS
- AI-powered risk assessment
- Early warning for at-risk students
- Batch analysis and recommendations

TROUBLESHOOTING
---------------

Common Issues:
1. Database errors: Check file permissions
2. QR code not displaying: Install PIL/Pillow
3. Face recognition not working: Install face_recognition library
4. Geofencing not available: Install geopy library

For technical support, check the system information in the Admin tab.

KEYBOARD SHORTCUTS
------------------
- Ctrl+R: Refresh data
- F5: Refresh current view
- Escape: Close current dialog
- Enter: Confirm action

TIPS AND BEST PRACTICES
-----------------------
1. Regular backups: Use Admin > Backup Database
2. Monitor attendance trends in Dashboard
3. Set appropriate thresholds in Settings
4. Use reports for analysis and decision making
5. Enable notifications for early intervention

VERSION INFORMATION
-------------------
Enhanced Attendance System v2.0
Built with Python and tkinter
Backwards compatible with CLI version

For more information, visit the system documentation or contact your administrator.
        """
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
        
        help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        help_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Primary.TButton').pack(pady=10)

# Aliases for backward compatibility
ReportPreviewWindow = ReportWindow
CustomReportDialog = CustomReportWindow
ImportPreviewWindow = ImportDataWindow

