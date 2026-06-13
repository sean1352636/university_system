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
            logger.exception("misc_windows.py:1646 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save report:\n{e}")

    def copy_to_clipboard(self):
        """Copy report content to clipboard"""
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.report_content)
            messagebox.showinfo(_("common.success"), "Report copied to clipboard!")
        except Exception as e:
            logger.exception("misc_windows.py:1655 %s", 'except Exception as e')
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
                    logger.exception("misc_windows.py:1700 %s", 'except Exception as e')
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
            logger.exception("misc_windows.py:1718 %s", 'except Exception as e')
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
            logger.exception("misc_windows.py:1760 %s", 'except Exception as e')
            print(f"Error getting admin emails: {e}")
            import traceback
            traceback.print_exc()

        return admin_emails

    def send_report_email(self, recipient_email):
        """Send report via email service"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            from education_system.university_system.core.activity_logger import log_activity

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
            logger.exception("misc_windows.py:1814 %s", 'except Exception as e')
            print(f"Error sending email to {recipient_email}: {e}")
            import traceback
            traceback.print_exc()
            return False

