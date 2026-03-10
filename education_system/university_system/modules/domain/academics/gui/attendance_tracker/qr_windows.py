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


class QRAttendanceWindow:
    def __init__(self, parent, qr_system, module_code, date, callback):
        self.parent = parent
        self.qr_system = qr_system
        self.module_code = module_code
        self.date = date
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.qr_code_attendance')} - {module_code}")
        self.window.geometry("600x500")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="QR Code Attendance System", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))
        
        # QR Generation frame
        gen_frame = ttk.LabelFrame(self.window, text="Generate QR Code", padding=10)
        gen_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Time inputs
        time_frame = ttk.Frame(gen_frame)
        time_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(time_frame, text="Start Time:").grid(row=0, column=0, sticky=tk.W)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(time_frame, textvariable=self.start_time_var, width=10).grid(row=0, column=1, padx=(5, 20))
        
        ttk.Label(time_frame, text="End Time:").grid(row=0, column=2, sticky=tk.W)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(time_frame, textvariable=self.end_time_var, width=10).grid(row=0, column=3, padx=(5, 0))
        
        ttk.Label(gen_frame, text="Location (optional):").pack(anchor=tk.W)
        self.location_var = tk.StringVar()
        ttk.Entry(gen_frame, textvariable=self.location_var, width=40).pack(fill=tk.X, pady=(5, 10))

        # Auto-fill location from timetable
        self.auto_fill_location()

        ttk.Button(gen_frame, text="Generate QR Code",
                  command=self.generate_qr, style='Primary.TButton').pack()
        
        # QR Display frame
        qr_frame = ttk.LabelFrame(self.window, text="QR Code", padding=10)
        qr_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.qr_label = ttk.Label(qr_frame, text="No QR code generated yet")
        self.qr_label.pack(expand=True)
        
        # Check-in frame
        checkin_frame = ttk.LabelFrame(self.window, text="Manual Check-in", padding=10)
        checkin_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        checkin_controls = ttk.Frame(checkin_frame)
        checkin_controls.pack(fill=tk.X)
        
        ttk.Label(checkin_controls, text="Student ID:").pack(side=tk.LEFT)
        self.student_id_var = tk.StringVar()
        ttk.Entry(checkin_controls, textvariable=self.student_id_var, width=15).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(checkin_controls, text="Check In",
                  command=self.manual_checkin, style='Success.TButton').pack(side=tk.LEFT)
        
        # Close button
        ttk.Button(self.window, text=_("common.close"),
                  command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def auto_fill_location(self):
        """Auto-fill location from timetable based on module code and current day/time"""
        try:
            # Get current day of week
            current_day = datetime.datetime.now().strftime('%A')
            current_time = datetime.datetime.now().strftime('%H:%M')

            # Query timetable for module location
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
            else:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))

            cursor = conn.cursor()

            # Try to find the room for this module on current day
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
            ''', (self.module_code, current_day))

            result = cursor.fetchone()
            conn.close()

            if result:
                building, room_number, day, start_time, end_time = result
                if building and room_number:
                    location_str = f"{building} - Room {room_number}"
                    if day == current_day:
                        location_str += f" ({day} {start_time}-{end_time})"
                    self.location_var.set(location_str)
                    # Also update time fields if it matches current day
                    if day == current_day and start_time and end_time:
                        self.start_time_var.set(start_time)
                        self.end_time_var.set(end_time)
        except Exception as e:
            print(f"Could not auto-fill location: {e}")

    def generate_qr(self):
        """Generate QR code for the session"""
        try:
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            location = self.location_var.get()
            
            session_id, qr_filename = self.qr_system.generate_session_qr(
                self.module_code, self.date, start_time, end_time, location
            )
            
            if session_id and qr_filename:
                # Load and display QR code
                try:
                    qr_image = Image.open(qr_filename)
                    qr_image = qr_image.resize((200, 200), Image.Resampling.LANCZOS)
                    qr_photo = ImageTk.PhotoImage(qr_image)
                    
                    self.qr_label.config(image=qr_photo, text="")
                    self.qr_label.image = qr_photo  # Keep a reference
                    
                    messagebox.showinfo(_("common.success"), f"QR code generated!\nSession ID: {session_id}")
                    
                except Exception as e:
                    self.qr_label.config(text=f"QR code generated but cannot display: {e}")
            else:
                messagebox.showerror(_("common.error"), "Failed to generate QR code")
                
        except Exception as e:
            messagebox.showerror(_("common.error"), f"QR generation failed: {e}")
    
    def manual_checkin(self):
        """Manual check-in for testing"""
        student_id = self.student_id_var.get()
        if not student_id:
            messagebox.showwarning(_("common.warning"), "Please enter a student ID")
            return
        
        # Simulate QR check-in
        messagebox.showinfo("Check-in", f"Student {student_id} checked in successfully!")
        self.callback()

class QRGeneratorWindow:
    def __init__(self, parent, qr_system):
        self.parent = parent
        self.qr_system = qr_system
        
        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.qr_code_generator"))
        self.window.geometry("500x600")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📱 QR Code Generator", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Session details
        details_frame = ttk.LabelFrame(self.window, text="Session Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(details_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        self.module_var.trace('w', lambda *args: self.on_module_change())
        ttk.Entry(details_frame, textvariable=self.module_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(details_frame, textvariable=self.date_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(details_frame, textvariable=self.start_time_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(details_frame, textvariable=self.end_time_var, width=30).grid(row=3, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Location:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.location_var, width=30).grid(row=4, column=1, padx=(10, 0), pady=5)
        
        # Generate button
        ttk.Button(details_frame, text="Generate QR Code", command=self.generate_qr, style='Primary.TButton').grid(row=5, column=0, columnspan=2, pady=10)
        
        # QR display
        qr_frame = ttk.LabelFrame(self.window, text="Generated QR Code", padding=10)
        qr_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.qr_label = ttk.Label(qr_frame, text="No QR code generated yet")
        self.qr_label.pack(expand=True)
        
        # Session info
        self.session_info = tk.Text(qr_frame, height=4, wrap=tk.WORD)
        self.session_info.pack(fill=tk.X, pady=(10, 0))
        
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
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
            else:
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
                    if day == current_day:
                        location_str += f" ({day} {start_time}-{end_time})"
                    self.location_var.set(location_str)
                    # Also update time fields if it matches current day
                    if day == current_day and start_time and end_time:
                        self.start_time_var.set(start_time)
                        self.end_time_var.set(end_time)
        except Exception as e:
            print(f"Could not auto-fill location: {e}")

    def generate_qr(self):
        """Generate QR code"""
        try:
            module_code = self.module_var.get()
            date = self.date_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            location = self.location_var.get()

            if not all([module_code, date, start_time, end_time]):
                messagebox.showwarning(_("common.warning"), "Please fill in all required fields")
                return
            
            session_id, qr_filename = self.qr_system.generate_session_qr(
                module_code, date, start_time, end_time, location
            )
            
            if session_id and qr_filename:
                # Load and display QR code
                try:
                    qr_image = Image.open(qr_filename)
                    qr_image = qr_image.resize((250, 250), Image.Resampling.LANCZOS)
                    qr_photo = ImageTk.PhotoImage(qr_image)
                    
                    self.qr_label.config(image=qr_photo, text="")
                    self.qr_label.image = qr_photo
                    
                    # Display session info
                    info_text = f"Session ID: {session_id}\n"
                    info_text += f"Module: {module_code}\n"
                    info_text += f"Date: {date}\n"
                    info_text += f"Time: {start_time} - {end_time}\n"
                    if location:
                        info_text += f"Location: {location}\n"
                    
                    self.session_info.delete(1.0, tk.END)
                    self.session_info.insert(tk.END, info_text)
                    
                    messagebox.showinfo(_("common.success"), f"QR code generated successfully!\nSaved as: {qr_filename}")
                    
                except Exception as e:
                    messagebox.showerror(_("common.error"), f"QR code generated but cannot display: {e}")
            else:
                messagebox.showerror(_("common.error"), "Failed to generate QR code")
                
        except Exception as e:
            messagebox.showerror(_("common.error"), f"QR generation failed: {e}")

