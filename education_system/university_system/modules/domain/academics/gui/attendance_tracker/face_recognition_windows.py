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

class FaceRecognitionAttendanceWindow:
    """Window for face recognition-based attendance with live camera feed"""
    def __init__(self, parent, face_system, module_code, date, callback):
        self.parent = parent
        self.face_system = face_system
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.camera = None
        self.is_running = False
        self.recognized_students = set()

        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.face_recognition_attendance')} - {module_code}")
        self.window.geometry("1000x700")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(title_frame, text="👤 Face Recognition Attendance System",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        info_label = ttk.Label(title_frame, text=f"Module: {self.module_code} | Date: {self.date}",
                              font=('Arial', 10))
        info_label.pack(side=tk.RIGHT)

        # Main content frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Left panel - Camera feed
        left_panel = ttk.LabelFrame(main_frame, text="Camera Feed", padding=15)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Camera display
        self.camera_label = ttk.Label(left_panel, text="📹\n\nInitializing camera...",
                                     font=('Arial', 12), anchor='center')
        self.camera_label.pack(fill=tk.BOTH, expand=True)

        # Camera controls
        camera_controls = ttk.Frame(left_panel)
        camera_controls.pack(fill=tk.X, pady=(10, 0))

        self.start_btn = ttk.Button(camera_controls, text="Start Camera",
                                    command=self.start_camera, style='Success.TButton')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(camera_controls, text="Stop Camera",
                                   command=self.stop_camera, style='Danger.TButton', state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(camera_controls, text="Capture Photo",
                  command=self.manual_capture, style='Primary.TButton').pack(side=tk.LEFT)

        # Right panel - Recognized students
        right_panel = ttk.LabelFrame(main_frame, text="Recognized Students", padding=15)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Status info
        status_frame = ttk.Frame(right_panel)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="Ready", foreground='green',
                                     font=('Arial', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Recognized students tree
        columns = ("Time", "Student ID", "Name", "Confidence")
        self.students_tree = ttk.Treeview(right_panel, columns=columns, show="headings", height=15)

        self.students_tree.heading("Time", text="Time")
        self.students_tree.heading("Student ID", text="Student ID")
        self.students_tree.heading("Name", text="Name")
        self.students_tree.heading("Confidence", text="Confidence")

        self.students_tree.column("Time", width=80)
        self.students_tree.column("Student ID", width=100)
        self.students_tree.column("Name", width=150)
        self.students_tree.column("Confidence", width=80)

        scrollbar = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Statistics
        stats_frame = ttk.Frame(right_panel)
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(stats_frame, text="Total Recognized:").pack(side=tk.LEFT)
        self.count_label = ttk.Label(stats_frame, text="0", font=('Arial', 12, 'bold'))
        self.count_label.pack(side=tk.LEFT, padx=(5, 0))

        # Bottom buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Button(buttons_frame, text="Save & Close",
                  command=self.save_and_close, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Enroll New Face",
                  command=self.enroll_new_face, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.close"),
                  command=self.on_closing, style='Danger.TButton').pack(side=tk.RIGHT)

    def start_camera(self):
        """Start camera capture"""
        try:
            import cv2
            import os
            import sys

            # Suppress OpenCV errors temporarily
            old_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')

            try:
                # Try to open camera
                self.camera = cv2.VideoCapture(0)
            finally:
                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr

            if not self.camera.isOpened():
                messagebox.showerror("Camera Not Available",
                    "Could not access camera.\n\n"
                    "This system does not have a webcam or the camera is not accessible.\n\n"
                    "Options:\n"
                    "1. Connect a USB webcam and try again\n"
                    "2. Use file-based face recognition (upload photos)\n"
                    "3. Use alternative attendance methods (QR code, manual entry)")
                return

            self.is_running = True
            self.start_btn.configure(state='disabled')
            self.stop_btn.configure(state='normal')
            self.status_label.configure(text="Camera Active", foreground='green')

            # Start video feed
            self.update_camera_feed()

        except ImportError:
            messagebox.showerror(_("common.error"), "OpenCV (cv2) not installed.\n\n"
                                         "Install with: pip install opencv-python")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to start camera: {e}")
            import traceback
            traceback.print_exc()

    def stop_camera(self):
        """Stop camera capture"""
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None

        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.status_label.configure(text="Camera Stopped", foreground='red')
        self.camera_label.configure(image='', text="📹\n\nCamera stopped")

    def update_camera_feed(self):
        """Update camera feed with face detection"""
        if not self.is_running or not self.camera:
            return

        try:
            import cv2
            import face_recognition
            from PIL import Image, ImageTk

            # Capture frame
            ret, frame = self.camera.read()

            if not ret:
                self.status_label.configure(text="Camera Error", foreground='red')
                return

            # Resize for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            # Draw rectangles around faces
            for (top, right, bottom, left) in face_locations:
                # Scale back up
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Draw rectangle
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)

            # Try to recognize faces
            for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
                # Scale back
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Compare with known faces
                matches = []
                student_id = None
                confidence = 0

                for known_id, known_encoding in self.face_system.known_encodings.items():
                    # Calculate face distance (lower = better match)
                    face_distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                    confidence_score = max(0, (1 - face_distance) * 100)

                    if face_distance < 0.6:  # Threshold for match
                        student_id = known_id
                        confidence = confidence_score
                        break

                # Draw label
                if student_id:
                    label = f"{student_id} ({confidence:.1f}%)"
                    cv2.putText(frame, label, (left + 6, bottom - 6),
                              cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

                    # Add to recognized list if not already there
                    if student_id not in self.recognized_students and confidence > 70:
                        self.add_recognized_student(student_id, confidence)
                else:
                    cv2.putText(frame, "Unknown", (left + 6, bottom - 6),
                              cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

            # Convert frame to PhotoImage
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Resize to fit display
            display_width = 640
            display_height = 480
            img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(image=img)
            self.camera_label.configure(image=photo, text='')
            self.camera_label.image = photo  # Keep reference

            # Update status
            face_count = len(face_locations)
            if face_count > 0:
                self.status_label.configure(text=f"Detecting {face_count} face(s)", foreground='blue')
            else:
                self.status_label.configure(text="No faces detected", foreground='orange')

            # Schedule next update
            self.window.after(33, self.update_camera_feed)  # ~30 FPS

        except Exception as e:
            print(f"Error in camera feed: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.configure(text="Processing Error", foreground='red')
            self.window.after(100, self.update_camera_feed)

    def add_recognized_student(self, student_id, confidence):
        """Add recognized student to the list"""
        try:
            # Get student name from database
            conn = get_db_connection() if MAIN_DB_AVAILABLE else None
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?",
                             (student_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    name = f"{result[0]} {result[1]}"
                else:
                    name = "Unknown"
            else:
                name = "Unknown"

            # Add to recognized set
            self.recognized_students.add(student_id)

            # Add to tree
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            self.students_tree.insert('', 0, values=(
                time_str,
                student_id,
                name,
                f"{confidence:.1f}%"
            ))

            # Update count
            self.count_label.configure(text=str(len(self.recognized_students)))

            # Visual feedback
            self.window.bell()

        except Exception as e:
            print(f"Error adding recognized student: {e}")
            import traceback
            traceback.print_exc()

    def manual_capture(self):
        """Manually capture current frame for recognition"""
        if not self.camera or not self.is_running:
            messagebox.showwarning(_("common.warning"), "Camera is not running")
            return

        try:
            import cv2
            import tempfile

            # Capture frame
            ret, frame = self.camera.read()
            if not ret:
                messagebox.showerror(_("common.error"), "Failed to capture frame")
                return

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, frame)
            temp_file.close()

            # Use face recognition system
            success, message, student_id = self.face_system.recognize_face_attendance(
                temp_file.name, self.module_code, self.date
            )

            if success:
                messagebox.showinfo(_("common.success"), f"Recognized: {student_id}\n{message}")
                if student_id not in self.recognized_students:
                    self.add_recognized_student(student_id, 95.0)
            else:
                messagebox.showwarning("Recognition Failed", message)

            # Clean up temp file
            import os
            os.unlink(temp_file.name)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Capture failed: {e}")
            import traceback
            traceback.print_exc()

    def enroll_new_face(self):
        """Enroll a new student's face"""
        # Pause camera
        was_running = self.is_running
        if was_running:
            self.stop_camera()

        try:
            # Ask for student ID
            student_id = simpledialog.askstring("Enroll Face", "Enter Student ID:")
            if not student_id:
                return

            # Ask to take photo or select file
            response = messagebox.askyesno("Photo Source",
                                          "Take photo with camera?\n\n"
                                          "Yes = Use camera\n"
                                          "No = Select file")

            if response:
                # Take photo with camera
                import cv2
                import tempfile

                temp_camera = cv2.VideoCapture(0)
                if not temp_camera.isOpened():
                    messagebox.showerror(_("common.error"), "Could not access camera")
                    return

                # Simple countdown window
                countdown_window = tk.Toplevel(self.window)
                countdown_window.title("Get Ready")
                countdown_window.geometry("300x200")
                countdown_label = ttk.Label(countdown_window, text="Get ready...",
                                           font=('Arial', 24, 'bold'))
                countdown_label.pack(expand=True)

                for i in range(3, 0, -1):
                    countdown_label.configure(text=str(i))
                    countdown_window.update()
                    self.window.after(1000)

                countdown_label.configure(text="Smile! 📸")
                countdown_window.update()

                # Capture photo
                ret, frame = temp_camera.read()
                temp_camera.release()
                countdown_window.destroy()

                if not ret:
                    messagebox.showerror(_("common.error"), "Failed to capture photo")
                    return

                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                cv2.imwrite(temp_file.name, frame)
                photo_path = temp_file.name
                temp_file.close()

            else:
                # Select from file
                photo_path = filedialog.askopenfilename(
                    title="Select Student Photo",
                    filetypes=[("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")]
                )
                if not photo_path:
                    return

            # Enroll face
            success, message = self.face_system.enroll_student_face(student_id, photo_path)

            if success:
                messagebox.showinfo(_("common.success"), f"Face enrolled successfully for {student_id}")
                # Reload known faces
                self.face_system.load_known_faces()
            else:
                messagebox.showerror("Enrollment Failed", message)

            # Clean up temp file if created
            if response:
                import os
                os.unlink(photo_path)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Enrollment failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Resume camera if it was running
            if was_running:
                self.start_camera()

    def save_and_close(self):
        """Save all recognized attendance and close"""
        if not self.recognized_students:
            messagebox.showinfo("Info", "No students recognized yet")
            self.on_closing()
            return

        try:
            # All recognized students are already saved by the face_system
            # Just show summary
            count = len(self.recognized_students)
            messagebox.showinfo(_("common.success"),
                              f"Attendance recorded for {count} student(s)!\n\n"
                              f"Students recognized:\n" +
                              "\n".join([f"• {sid}" for sid in sorted(self.recognized_students)]))

            self.callback()  # Refresh parent window
            self.on_closing()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Error saving attendance: {e}")
            import traceback
            traceback.print_exc()

    def on_closing(self):
        """Clean up and close window"""
        self.stop_camera()
        self.window.destroy()

class FaceRecognitionWindow:
    def __init__(self, parent, face_system):
        self.parent = parent
        self.face_system = face_system

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.face_recognition_setup"))
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👤 Face Recognition Setup", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Enrollment section
        enroll_frame = ttk.LabelFrame(self.window, text="Enroll Student Face", padding=10)
        enroll_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(enroll_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(enroll_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(enroll_frame, text="Photo Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.photo_path_var = tk.StringVar()
        photo_frame = ttk.Frame(enroll_frame)
        photo_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Entry(photo_frame, textvariable=self.photo_path_var, width=25).pack(side=tk.LEFT)
        ttk.Button(photo_frame, text=_("common.browse"), command=self.browse_photo).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Button(enroll_frame, text="Enroll Face", command=self.enroll_face, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=10)

        # Recognition section
        recognize_frame = ttk.LabelFrame(self.window, text="Recognize Face", padding=10)
        recognize_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(recognize_frame, text="Image Path:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.recognize_path_var = tk.StringVar()
        recognize_photo_frame = ttk.Frame(recognize_frame)
        recognize_photo_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Entry(recognize_photo_frame, textvariable=self.recognize_path_var, width=25).pack(side=tk.LEFT)
        ttk.Button(recognize_photo_frame, text=_("common.browse"), command=self.browse_recognize_photo).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Button(recognize_frame, text="Recognize Face", command=self.recognize_face, style='Primary.TButton').grid(row=1, column=0, columnspan=2, pady=10)

        # Enrolled students
        enrolled_frame = ttk.LabelFrame(self.window, text="Enrolled Students", padding=10)
        enrolled_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Enrolled students list
        enrolled_columns = ("Student ID", "Name", "Enrollment Date")
        self.enrolled_tree = ttk.Treeview(enrolled_frame, columns=enrolled_columns, show="headings", height=6)

        for col in enrolled_columns:
            self.enrolled_tree.heading(col, text=col)
            self.enrolled_tree.column(col, width=150)

        enrolled_scrollbar = ttk.Scrollbar(enrolled_frame, orient=tk.VERTICAL, command=self.enrolled_tree.yview)
        self.enrolled_tree.configure(yscrollcommand=enrolled_scrollbar.set)

        self.enrolled_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        enrolled_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load enrolled students
        self.load_enrolled_students()

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def browse_photo(self):
        """Browse for photo file"""
        filename = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.photo_path_var.set(filename)

    def browse_recognize_photo(self):
        """Browse for recognition photo"""
        filename = filedialog.askopenfilename(
            title="Select Photo for Recognition",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.recognize_path_var.set(filename)

    def enroll_face(self):
        """Enroll student face"""
        student_id = self.student_id_var.get()
        photo_path = self.photo_path_var.get()

        if not student_id or not photo_path:
            messagebox.showwarning(_("common.warning"), "Please enter student ID and select a photo")
            return

        try:
            success, message = self.face_system.enroll_student_face(student_id, photo_path)

            if success:
                messagebox.showinfo(_("common.success"), message)
                self.load_enrolled_students()
                self.student_id_var.set("")
                self.photo_path_var.set("")
            else:
                messagebox.showerror(_("common.error"), message)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Enrollment failed: {e}")

    def recognize_face(self):
        """Recognize face in photo"""
        image_path = self.recognize_path_var.get()

        if not image_path:
            messagebox.showwarning(_("common.warning"), "Please select an image for recognition")
            return

        try:
            success, message, student_id = self.face_system.recognize_face_attendance(
                image_path, "CS101", datetime.date.today().isoformat()
            )

            if success:
                messagebox.showinfo("Recognition Success", f"{message}\nStudent ID: {student_id}")
            else:
                messagebox.showwarning("Recognition Failed", message)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Recognition failed: {e}")

    def load_enrolled_students(self):
        """Load enrolled students list"""
        # Clear existing items
        for item in self.enrolled_tree.get_children():
            self.enrolled_tree.delete(item)

        # Load enrolled students from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name as full_name,
                        s.enrollment_date
                    FROM students s
                    WHERE s.status = 'active' OR s.status IS NULL
                    ORDER BY s.last_name, s.first_name
                ''')
                students = cursor.fetchall()

                for data in students:
                    self.enrolled_tree.insert('', 'end', values=data)

                if not students:
                    # Show message if no students found
                    self.enrolled_tree.insert('', 'end', values=("--", "No students enrolled", "--"))
        except Exception as e:
            self.enrolled_tree.insert('', 'end', values=("--", f"Error: {e}", "--"))

class BiometricsManagementWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.biometrics_management"))
        self.window.geometry("600x500")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👤 Biometrics Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different biometric types
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Face enrollment tab
        face_frame = ttk.Frame(notebook)
        notebook.add(face_frame, text="Face Enrollment")

        # Student ID
        ttk.Label(face_frame, text="Student ID:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.student_id_var = tk.StringVar()
        ttk.Entry(face_frame, textvariable=self.student_id_var, width=30).pack(padx=10, pady=5)

        # Photo selection
        ttk.Label(face_frame, text="Student Photo:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        photo_frame = ttk.Frame(face_frame)
        photo_frame.pack(fill=tk.X, padx=10, pady=5)

        self.photo_path_var = tk.StringVar()
        ttk.Entry(photo_frame, textvariable=self.photo_path_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(photo_frame, text=_("common.browse"), command=self.browse_photo).pack(side=tk.RIGHT, padx=(5, 0))

        # Enroll button
        ttk.Button(face_frame, text="Enroll Face", command=self.enroll_face, style='Success.TButton').pack(pady=20)

        # Enrolled students list
        ttk.Label(face_frame, text="Enrolled Students:").pack(anchor=tk.W, padx=10)

        list_frame = ttk.Frame(face_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("Student ID", "Name", "Enrollment Date", "Status")
        self.enrolled_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)

        for col in columns:
            self.enrolled_tree.heading(col, text=col)
            self.enrolled_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.enrolled_tree.yview)
        self.enrolled_tree.configure(yscrollcommand=scrollbar.set)

        self.enrolled_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load enrolled students
        self.load_enrolled_students()

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def browse_photo(self):
        filename = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.photo_path_var.set(filename)

    def enroll_face(self):
        student_id = self.student_id_var.get()
        photo_path = self.photo_path_var.get()

        if not student_id or not photo_path:
            messagebox.showwarning(_("common.warning"), "Please enter student ID and select a photo")
            return

        try:
            if FACE_RECOGNITION_SUPPORT:
                face_system = FaceRecognitionSystem()
                success, message = face_system.enroll_student_face(student_id, photo_path)

                if success:
                    messagebox.showinfo(_("common.success"), message)
                    self.load_enrolled_students()
                    self.student_id_var.set("")
                    self.photo_path_var.set("")
                else:
                    messagebox.showerror(_("common.error"), message)
            else:
                messagebox.showinfo("Demo", "Face would be enrolled here (face recognition not available)")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Enrollment failed: {e}")

    def load_enrolled_students(self):
        # Clear existing items
        for item in self.enrolled_tree.get_children():
            self.enrolled_tree.delete(item)

        # Sample data or real data from database
        # Load real enrollment data from database
        try:

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get student enrollment data
                cursor.execute("""
                    SELECT student_id, first_name || ' ' || last_name, enrollment_date, status
                    FROM students
                    WHERE status = 'Active' OR status = 'Enrolled'
                    ORDER BY enrollment_date DESC
                """)
                enrollment_data = cursor.fetchall()

                if enrollment_data:
                    for data in enrollment_data:
                        self.enrolled_tree.insert('', 'end', values=data)
                else:
                    # Check if students table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
                    if cursor.fetchone():
                        self.enrolled_tree.insert('', 'end', values=('N/A', 'No enrolled students found', '', 'Please enroll students first'))
                    else:
                        self.enrolled_tree.insert('', 'end', values=('ERROR', 'Students table not found', '', 'Database needs initialization'))

        except Exception as e:
            self.enrolled_tree.insert('', 'end', values=('ERROR', f'Database error: {str(e)}', '', 'Unable to load enrollment data'))

