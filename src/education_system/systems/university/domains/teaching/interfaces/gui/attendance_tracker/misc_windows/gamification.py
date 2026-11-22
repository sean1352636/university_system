
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
        title_label = ttk.Label(self.window, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.gamification_portal', default="🎮 Gamification Portal"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different views
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Leaderboard tab
        leaderboard_frame = ttk.Frame(notebook)
        notebook.add(leaderboard_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.tabs.leaderboard', default="🏆 Leaderboard"))

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
        notebook.add(details_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.tabs.student_details', default="👤 Student Details"))

        # Student lookup
        lookup_frame = ttk.Frame(details_frame)
        lookup_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(lookup_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.student_id', default="Student ID:")).pack(side=tk.LEFT)
        self.lookup_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self.lookup_var, width=15).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(lookup_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.buttons.lookup', default="Lookup"), command=self.lookup_student, style='Primary.TButton').pack(side=tk.LEFT)

        # Student details display
        self.details_text = tk.Text(details_frame, wrap=tk.WORD, height=20)
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)

        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))

        # Awards tab
        awards_frame = ttk.Frame(notebook)
        notebook.add(awards_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.tabs.award_points', default="🎯 Award Points"))

        # Award form
        award_form = ttk.LabelFrame(awards_frame, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.award_points_to_student', default="Award Points to Student"), padding=20)
        award_form.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(award_form, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.award_student_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_student_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(award_form, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.points', default="Points:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.award_points_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_points_var, width=20).grid(row=1, column=1, padx=(10, 0), pady=5)

        ttk.Label(award_form, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.labels.reason', default="Reason:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.award_reason_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_reason_var, width=40).grid(row=2, column=1, padx=(10, 0), pady=5)

        ttk.Button(award_form, text=_t('gui.academics.attendance_tracker.misc_windows.gamification.buttons.award_points', default="Award Points"), command=self.award_points, style='Success.TButton').grid(row=3, column=0, columnspan=2, pady=10)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def load_leaderboard(self):
        """Load leaderboard data"""
        # Clear existing items
        for item in self.leaderboard_tree.get_children():
            self.leaderboard_tree.delete(item)

        # Load real leaderboard data from database
        try:

            with sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get gamification/points data
                cursor.execute("""
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY COALESCE(g.points, 0) DESC) as rank,
                        s.student_id,
                        s.first_name || ' ' || s.last_name as name,
                        COALESCE(g.points, 0) as points,
                        COALESCE(g.level, 1) as level,
                        COALESCE(g.streak_days, 0) as streak,
                        COALESCE(g.badges, '') as badges
                    FROM students s
                    JOIN attendance_gamification g ON s.student_id = g.student_id
                    WHERE s.status = 'Active'
                    ORDER BY points DESC
                    LIMIT 10
                """)
                leaderboard_data = cursor.fetchall()

                # Nobody has earned points yet: basic attendance-based points
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
            messagebox.showwarning(_("common.warning"), _t('gui.academics.attendance_tracker.misc_windows.gamification.dialogs.please_enter_a_student_id', default="Please enter a student ID"))
            return

        with sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH)) as conn:
            row = conn.execute(
                "SELECT points, level, streak_days, best_streak, total_rewards, badges, "
                "achievements, last_attendance_date FROM attendance_gamification "
                "WHERE student_id = ?", (student_id,)).fetchone()
        if row:
            points, level, streak, best, rewards, badges, achievements, last_seen = row
            badge_list = json.loads(badges or '[]')
            recent = json.loads(achievements or '[]')[-5:]
            achieved = "\n".join(
                f"• {a.get('badge', '')} ({a.get('date', '')}) - {a.get('description', '')}"
                for a in reversed(recent)) or "None yet"
            details = f"""🎮 GAMIFICATION PROFILE: {student_id}
{'='*50}

Student ID: {student_id}
Current Points: {points:,}
Level: {level}
Current Streak: {streak} days
Best Streak: {best} days
Total Rewards: {rewards:,}

🏆 BADGES: {', '.join(badge_list) or 'None yet'}

🎯 RECENT ACHIEVEMENTS:
{achieved}

📈 Points to next level: {level * 1000 - points}

Last Attendance: {last_seen or 'N/A'}"""
        else:
            details = f"No gamification record for {student_id} yet."

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, details)

    def award_points(self):
        """Award points to student"""
        try:
            student_id = self.award_student_var.get()
            points = int(self.award_points_var.get())
            reason = self.award_reason_var.get()

            if not all([student_id, points, reason]):
                messagebox.showwarning(_("common.warning"), _t('gui.academics.attendance_tracker.misc_windows.gamification.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
                return

            with sqlite3.connect(str(UNIVERSITY_DEFAULT_DB_PATH)) as conn:
                if not conn.execute("SELECT 1 FROM students WHERE student_id = ?", (student_id,)).fetchone():
                    messagebox.showerror(_("common.error"), f"Student {student_id} not found")
                    return
                row = conn.execute("SELECT points, achievements FROM attendance_gamification "
                                   "WHERE student_id = ?", (student_id,)).fetchone()
                if not row:
                    conn.execute("INSERT INTO attendance_gamification (student_id) VALUES (?)", (student_id,))
                    row = (0, '[]')
                total = (row[0] or 0) + points
                achievements = json.loads(row[1] or '[]')
                achievements.append({'badge': 'award', 'date': datetime.date.today().isoformat(),
                                     'description': f"{points} points: {reason}"})
                # Same level rule as the attendance points in domain/attendance/gamification.py
                conn.execute(
                    "UPDATE attendance_gamification SET points = ?, level = ?, achievements = ?, "
                    "total_rewards = COALESCE(total_rewards, 0) + ?, updated_at = ? WHERE student_id = ?",
                    (total, total // 1000 + 1, json.dumps(achievements), points,
                     datetime.datetime.now().isoformat(), student_id))

            messagebox.showinfo(_("common.success"), f"Awarded {points} points to {student_id} for: {reason}")
            self.load_leaderboard()

            # Clear form
            self.award_student_var.set("")
            self.award_points_var.set("")
            self.award_reason_var.set("")

        except ValueError:
            logger.exception("misc_windows.py:1022 %s", 'except ValueError')
            messagebox.showerror(_("common.error"), _t('gui.academics.attendance_tracker.misc_windows.gamification.dialogs.please_enter_a_valid_number_of_points', default="Please enter a valid number of points"))

