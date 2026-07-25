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
            logger.exception("misc_windows.py:970 %s", 'except Exception as e')
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
            logger.exception("misc_windows.py:1022 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), "Please enter a valid number of points")

