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
    logger = configure_logging(name="attendance_tracker.gui.notifications_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.notifications_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.post_18.university_system.core.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR


# Columns this module needs on parent_notifications. The table may have
# been created earlier by the parent-portal code with a different schema
# (parent_id / notification_content / created_date / read_status), so we
# additively migrate it on first use. ALTER TABLE … ADD COLUMN is
# idempotent here via the duplicate-column catch.
_PARENT_NOTIF_COLS = [
    ("sent_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ("parent_name", "TEXT"),
    ("method", "TEXT"),
    ("status", "TEXT"),
    ("subject", "TEXT"),
]


def _ensure_parent_notifications_columns(conn):
    """Add the columns this GUI relies on if missing. Safe to call
    repeatedly; ignores duplicate-column errors."""
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS parent_notifications ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT)"
        )
        existing = {row[1] for row in cur.execute(
            "PRAGMA table_info(parent_notifications)").fetchall()}
        for col, decl in _PARENT_NOTIF_COLS:
            if col in existing:
                continue
            try:
                cur.execute(
                    f"ALTER TABLE parent_notifications ADD COLUMN {col} {decl}"
                )
            except sqlite3.OperationalError as e:
                # Race or pre-existing column under a different cast —
                # safe to ignore.
                if "duplicate column" not in str(e).lower():
                    logger.debug(
                        "ALTER parent_notifications ADD %s skipped: %s",
                        col, e)
        conn.commit()
    except Exception:
        logger.exception("parent_notifications schema migration failed")

# Import authentication system
from education_system.post_18.university_system.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.post_18.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("notifications_windows.py:50 %s", 'except ImportError')
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
    logger.exception("notifications_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.post_18.university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("notifications_windows.py:75 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True


class ParentNotificationWindow:
    """Parent Notification System for sending alerts about student attendance"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.parent_notification_system"))
        self.window.geometry("1000x700")
        self.window.transient(parent)

        self.create_widgets()
        self.load_parent_contacts()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👨‍👩‍👧 Parent Notification System", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different functions
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Parent Contacts tab
        contacts_frame = ttk.Frame(notebook)
        notebook.add(contacts_frame, text="📋 Parent Contacts")
        self.create_contacts_tab(contacts_frame)

        # Send Notifications tab
        notifications_frame = ttk.Frame(notebook)
        notebook.add(notifications_frame, text="📧 Send Notifications")
        self.create_notifications_tab(notifications_frame)

        # Notification History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="📜 Notification History")
        self.create_history_tab(history_frame)

        # Settings tab
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="⚙️ Settings")
        self.create_notification_settings_tab(settings_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_contacts_tab(self, parent):
        # Search frame
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.contact_search_var = tk.StringVar()
        self.contact_search_var.trace('w', lambda *args: self.filter_contacts())
        ttk.Entry(search_frame, textvariable=self.contact_search_var, width=30).pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(search_frame, text="Add Parent Contact", command=self.add_parent_contact, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Edit Selected", command=self.edit_parent_contact, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Delete Selected", command=self.delete_parent_contact, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Contacts treeview
        contacts_columns = ("Student ID", "Student Name", "Parent Name", "Relationship", "Email", "Phone", "Preferred Contact")
        self.contacts_tree = ttk.Treeview(parent, columns=contacts_columns, show="headings", height=20)

        for col in contacts_columns:
            self.contacts_tree.heading(col, text=col)
            if col == "Email":
                self.contacts_tree.column(col, width=200)
            else:
                self.contacts_tree.column(col, width=120)

        contacts_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.contacts_tree.yview)
        self.contacts_tree.configure(yscrollcommand=contacts_scrollbar.set)

        self.contacts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        contacts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

    def create_notifications_tab(self, parent):
        # Notification type frame
        type_frame = ttk.LabelFrame(parent, text="Notification Type", padding=15)
        type_frame.pack(fill=tk.X, padx=10, pady=10)

        self.notification_type_var = tk.StringVar(value="absence")
        ttk.Radiobutton(type_frame, text="Absence Alert", variable=self.notification_type_var, value="absence").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Low Attendance Warning", variable=self.notification_type_var, value="low_attendance").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Perfect Attendance Praise", variable=self.notification_type_var, value="perfect").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Custom Message", variable=self.notification_type_var, value="custom").pack(anchor=tk.W)


        # Quick action buttons
        quick_actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding=15)
        quick_actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(quick_actions_frame, text="🔍 Check Low Attendance (<90%)",
                  command=self.check_low_attendance_now, style='Warning.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_actions_frame, text="📊 View Attendance Report",
                  command=self.view_attendance_report, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        # Recipients frame
        recipients_frame = ttk.LabelFrame(parent, text="Recipients", padding=15)
        recipients_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(recipients_frame, text="Select Students:").pack(anchor=tk.W, pady=(0, 5))

        recipients_controls = ttk.Frame(recipients_frame)
        recipients_controls.pack(fill=tk.X, pady=(0, 5))

        self.recipient_mode_var = tk.StringVar(value="individual")
        ttk.Radiobutton(recipients_controls, text="Individual Student", variable=self.recipient_mode_var, value="individual",
                       command=self.update_recipient_mode).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(recipients_controls, text="All At-Risk Students", variable=self.recipient_mode_var, value="at_risk",
                       command=self.update_recipient_mode).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(recipients_controls, text="Module Students", variable=self.recipient_mode_var, value="module",
                       command=self.update_recipient_mode).pack(side=tk.LEFT)

        self.recipient_input_frame = ttk.Frame(recipients_frame)
        self.recipient_input_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(self.recipient_input_frame, text="Student ID:").pack(side=tk.LEFT)
        self.student_id_notify_var = tk.StringVar()
        ttk.Entry(self.recipient_input_frame, textvariable=self.student_id_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))

        # Message frame
        message_frame = ttk.LabelFrame(parent, text="Message", padding=15)
        message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        ttk.Label(message_frame, text="Subject:").pack(anchor=tk.W)
        self.message_subject_var = tk.StringVar(value="Student Attendance Alert")
        ttk.Entry(message_frame, textvariable=self.message_subject_var).pack(fill=tk.X, pady=(5, 10))

        ttk.Label(message_frame, text="Message Body:").pack(anchor=tk.W)
        self.message_body_text = tk.Text(message_frame, wrap=tk.WORD, height=8)
        self.message_body_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        self.message_body_text.insert(tk.END, "Dear Parent/Guardian,\n\nThis is to inform you about your child's attendance.\n\nBest regards,\nAttendance Office")

        # Send controls
        send_controls = ttk.Frame(message_frame)
        send_controls.pack(fill=tk.X)

        self.send_email_var = tk.BooleanVar(value=True)
        self.send_sms_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(send_controls, text="Send Email", variable=self.send_email_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(send_controls, text="Send SMS", variable=self.send_sms_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(send_controls, text="Send Notifications", command=self.send_notifications, style='Success.TButton').pack(side=tk.RIGHT)

    def create_history_tab(self, parent):
        # Filter frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(filter_frame, text="Date Range:").pack(side=tk.LEFT)
        self.history_start_var = tk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(filter_frame, textvariable=self.history_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(filter_frame, text="to").pack(side=tk.LEFT)
        self.history_end_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(filter_frame, textvariable=self.history_end_var, width=12).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(filter_frame, text="Load History", command=self.load_notification_history, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Export to CSV", command=self.export_notification_history, style='Success.TButton').pack(side=tk.LEFT)

        # History treeview
        history_columns = ("Date", "Time", "Student", "Parent", "Type", "Method", "Status", "Subject")
        self.history_tree = ttk.Treeview(parent, columns=history_columns, show="headings", height=22)

        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120 if col != "Subject" else 200)

        history_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

        # Bind double-click to view details
        self.history_tree.bind('<Double-1>', self.view_notification_details)

        # Load initial history
        self.load_notification_history()

    def create_notification_settings_tab(self, parent):
        # Auto-notification settings
        auto_frame = ttk.LabelFrame(parent, text="Automatic Notifications", padding=15)
        auto_frame.pack(fill=tk.X, padx=10, pady=10)

        self.auto_absence_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto_frame, text="Auto-notify parents on absence", variable=self.auto_absence_var).pack(anchor=tk.W)

        self.auto_low_attendance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(auto_frame, text="Auto-notify when attendance falls below threshold", variable=self.auto_low_attendance_var).pack(anchor=tk.W)

        ttk.Label(auto_frame, text="Low attendance threshold (%):").pack(anchor=tk.W, pady=(10, 0))
        self.low_attendance_threshold_var = tk.StringVar(value="75")
        ttk.Entry(auto_frame, textvariable=self.low_attendance_threshold_var, width=10).pack(anchor=tk.W, pady=(5, 10))

        # Template settings
        template_frame = ttk.LabelFrame(parent, text="Message Templates", padding=15)
        template_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        ttk.Label(template_frame, text="Absence Template:").pack(anchor=tk.W)
        self.absence_template_text = tk.Text(template_frame, wrap=tk.WORD, height=4)
        self.absence_template_text.pack(fill=tk.X, pady=(5, 10))
        self.absence_template_text.insert(tk.END, "Dear {parent_name},\n\nYour child {student_name} was absent from {module_name} on {date}.\n\nPlease contact us if you have any questions.")

        ttk.Label(template_frame, text="Low Attendance Template:").pack(anchor=tk.W)
        self.low_attendance_template_text = tk.Text(template_frame, wrap=tk.WORD, height=4)
        self.low_attendance_template_text.pack(fill=tk.X, pady=(5, 10))
        self.low_attendance_template_text.insert(tk.END, "Dear {parent_name},\n\nWe would like to inform you that {student_name}'s attendance rate is currently {attendance_rate}%.\n\nWe encourage regular attendance for academic success.")

        # Save button
        ttk.Button(template_frame, text="Save Settings", command=self.save_notification_settings, style='Success.TButton').pack(pady=(10, 0))

    def load_parent_contacts(self):
        # Clear existing items
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get parent contacts from database
                cursor.execute("""
                    SELECT
                        pc.student_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        pc.parent_name,
                        pc.relationship,
                        pc.email,
                        pc.phone,
                        pc.preferred_contact
                    FROM parent_contacts pc
                    JOIN students s ON pc.student_id = s.student_id
                    ORDER BY s.last_name, s.first_name
                """)
                contacts = cursor.fetchall()

                if contacts:
                    for contact in contacts:
                        self.contacts_tree.insert('', 'end', values=contact)
                else:
                    # Show message if no contacts found
                    self.contacts_tree.insert('', 'end', values=("N/A", "No parent contacts found", "Add contacts to enable parent notifications", "", "", "", ""))
        except sqlite3.OperationalError:
            # Table doesn't exist, create it
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS parent_contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            parent_name TEXT NOT NULL,
                            relationship TEXT,
                            email TEXT,
                            phone TEXT,
                            preferred_contact TEXT DEFAULT 'email',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
                    """)
                    conn.commit()
                self.contacts_tree.insert('', 'end', values=("INFO", "Parent contacts table created", "Add your first parent contact", "", "", "", ""))
            except Exception as e:
                logger.exception("notifications_windows.py:345 %s", 'except Exception as e')
                self.contacts_tree.insert('', 'end', values=("ERROR", f"Database error: {e}", "", "", "", "", ""))
        except Exception as e:
            logger.exception("notifications_windows.py:347 %s", 'except Exception as e')
            self.contacts_tree.insert('', 'end', values=("ERROR", f"Error loading contacts: {e}", "", "", "", "", ""))

    def filter_contacts(self):
        search_term = self.contact_search_var.get().lower()
        # Re-load and filter contacts
        self.load_parent_contacts()

        if search_term:
            # Remove items that don't match search
            for item in self.contacts_tree.get_children():
                values = self.contacts_tree.item(item)['values']
                match = any(search_term in str(val).lower() for val in values)
                if not match:
                    self.contacts_tree.delete(item)

    def add_parent_contact(self):
        ParentContactDialog(self.window, "add", None, self.load_parent_contacts)

    def edit_parent_contact(self):
        selected = self.contacts_tree.selection()
        if not selected:
            messagebox.showwarning(_("common.warning"), "Please select a parent contact to edit")
            return

        contact_data = self.contacts_tree.item(selected[0])['values']
        ParentContactDialog(self.window, "edit", contact_data, self.load_parent_contacts)

    def delete_parent_contact(self):
        selected = self.contacts_tree.selection()
        if not selected:
            messagebox.showwarning(_("common.warning"), "Please select a parent contact to delete")
            return

        contact_data = self.contacts_tree.item(selected[0])['values']
        student_id = contact_data[0]
        parent_name = contact_data[2]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete parent contact for {parent_name} ({student_id})?"):
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM parent_contacts WHERE student_id = ? AND parent_name = ?", (student_id, parent_name))
                    conn.commit()
                messagebox.showinfo(_("common.success"), "Parent contact deleted successfully")
                self.load_parent_contacts()
            except Exception as e:
                logger.exception("notifications_windows.py:393 %s", 'except Exception as e')
                messagebox.showerror(_("common.error"), f"Failed to delete parent contact: {e}")

    def update_recipient_mode(self):
        # Clear and rebuild recipient input frame
        for widget in self.recipient_input_frame.winfo_children():
            widget.destroy()

        mode = self.recipient_mode_var.get()

        if mode == "individual":
            ttk.Label(self.recipient_input_frame, text="Student ID:").pack(side=tk.LEFT)
            self.student_id_notify_var = tk.StringVar()
            ttk.Entry(self.recipient_input_frame, textvariable=self.student_id_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))
        elif mode == "module":
            ttk.Label(self.recipient_input_frame, text="Module Code:").pack(side=tk.LEFT)
            self.module_notify_var = tk.StringVar()
            ttk.Entry(self.recipient_input_frame, textvariable=self.module_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))
        else:  # at_risk
            ttk.Label(
                self.recipient_input_frame,
                text="Notifies students at high/medium risk in the latest "
                     "Risk Feed (falls back to attendance < 75% if the "
                     "feed is empty).").pack(side=tk.LEFT)

    def send_notifications(self):
        notification_type = self.notification_type_var.get()
        recipient_mode = self.recipient_mode_var.get()
        subject = self.message_subject_var.get()
        body = self.message_body_text.get("1.0", tk.END).strip()

        if not subject or not body:
            messagebox.showwarning(_("common.warning"), "Please provide both subject and message body")
            return

        send_email = self.send_email_var.get()
        send_sms = self.send_sms_var.get()

        if not send_email and not send_sms:
            messagebox.showwarning(_("common.warning"), "Please select at least one notification method (Email or SMS)")
            return

        try:
            # Determine recipients
            recipients = []

            if recipient_mode == "individual":
                student_id = self.student_id_notify_var.get() if hasattr(self, 'student_id_notify_var') else ""
                if not student_id:
                    messagebox.showwarning(_("common.warning"), "Please enter a student ID")
                    return
                recipients = [student_id]
            elif recipient_mode == "module":
                module_code = self.module_notify_var.get() if hasattr(self, 'module_notify_var') else ""
                if not module_code:
                    messagebox.showwarning(_("common.warning"), "Please enter a module code")
                    return
                # Get all students in module
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT student_id FROM enrollments WHERE module_code = ?", (module_code,))
                    recipients = [row[0] for row in cursor.fetchall()]
            else:  # at_risk
                # Prefer the persisted Risk Feed (student_risk_assessment)
                # so this stays in sync with whatever the absence-tracker's
                # blended model is currently flagging. Fall back to the
                # raw-attendance heuristic when the feed is empty.
                recipients = []
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    try:
                        cursor.execute("""
                            SELECT r.student_id
                            FROM student_risk_assessment r
                            WHERE r.id = (SELECT MAX(id)
                                          FROM student_risk_assessment
                                          WHERE student_id = r.student_id)
                              AND LOWER(COALESCE(r.risk_level, ''))
                                  IN ('high', 'medium')
                        """)
                        recipients = [row[0] for row in cursor.fetchall()]
                    except sqlite3.Error:
                        recipients = []
                    if not recipients:
                        cursor.execute("""
                            SELECT s.student_id
                            FROM students s
                            LEFT JOIN (
                                SELECT student_id,
                                       SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as rate
                                FROM attendance
                                GROUP BY student_id
                            ) a ON s.student_id = a.student_id
                            WHERE a.rate < 75 OR a.rate IS NULL
                        """)
                        recipients = [row[0] for row in cursor.fetchall()]

            if not recipients:
                messagebox.showinfo("No Recipients", "No recipients found matching the criteria")
                return

            # Send notifications
            sent_count = 0
            failed_count = 0

            for student_id in recipients:
                try:
                    # Get parent contact info
                    with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT parent_name, email, phone, preferred_contact
                            FROM parent_contacts
                            WHERE student_id = ?
                        """, (student_id,))
                        parent_info = cursor.fetchone()

                    if not parent_info:
                        failed_count += 1
                        continue

                    parent_name, email, phone, preferred = parent_info

                    # Send notification based on preferences
                    if send_email and email and (preferred == 'email' or preferred == 'both'):
                        # Log notification (actual sending would use email service)
                        self.log_notification(student_id, parent_name, "Email", subject, "Sent")
                        sent_count += 1

                    if send_sms and phone and (preferred == 'sms' or preferred == 'both'):
                        # Log notification (actual sending would use SMS service)
                        self.log_notification(student_id, parent_name, "SMS", subject, "Sent")
                        sent_count += 1

                except Exception as e:
                    logger.exception("notifications_windows.py:505 %s", 'except Exception as e')
                    failed_count += 1
                    print(f"Failed to send notification to student {student_id}: {e}")

            messagebox.showinfo("Notifications Sent",
                              f"Successfully sent {sent_count} notifications\n"
                              f"Failed: {failed_count}\n"
                              f"Recipients: {len(recipients)}")

            # Refresh history
            self.load_notification_history()

        except Exception as e:
            logger.exception("notifications_windows.py:517 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to send notifications: {e}")

    def log_notification(self, student_id, parent_name, method, subject, status):
        """Log notification to database"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                _ensure_parent_notifications_columns(conn)
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO parent_notifications (student_id, parent_name, notification_type, method, subject, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, parent_name, self.notification_type_var.get(), method, subject, status))

                conn.commit()
        except Exception as e:
            logger.exception("notifications_windows.py:546 %s", 'except Exception as e')
            print(f"Error logging notification: {e}")

    def check_low_attendance_now(self):
        """Check for students with low attendance and send notifications"""
        if not ATTENDANCE_NOTIFICATIONS_AVAILABLE:
            messagebox.showerror(_("common.error"), "Attendance notification service not available")
            return

        # Ask for confirmation
        if not messagebox.askyesno(_("common.confirm"),
                                   "This will check all students' attendance and send notifications "
                                   "to those below 90%.\n\n"
                                   "Send notifications to both students and parents?"):
            return

        try:
            # Show progress
            progress_window = tk.Toplevel(self.window)
            progress_window.title("Checking Attendance")
            progress_window.geometry("400x150")
            progress_window.transient(self.window)

            ttk.Label(progress_window, text="Checking student attendance...",
                     font=('Arial', 12)).pack(pady=20)
            progress_label = ttk.Label(progress_window, text="Please wait...")
            progress_label.pack(pady=10)

            progress_window.update()

            # Run notification check
            service = AttendanceNotificationService(attendance_threshold=90.0)
            results = service.check_and_notify_low_attendance(
                module_code=None,
                send_to_students=True,
                send_to_parents=True
            )

            progress_window.destroy()

            # Show results
            messagebox.showinfo("Notifications Sent",
                              f"Attendance Check Complete!\n\n"
                              f"Students Checked: {results['students_checked']}\n"
                              f"Students Notified: {results['students_notified']}\n"
                              f"Parents Notified: {results['parents_notified']}\n"
                              f"Total Emails Sent: {results['emails_sent']}\n"
                              f"Errors: {results['errors']}")

            # Refresh notification history
            self.load_notification_history()

        except Exception as e:
            logger.exception("notifications_windows.py:598 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to check attendance:\n{e}")
            import traceback
            traceback.print_exc()

    def view_attendance_report(self):
        """Display attendance statistics and at-risk students"""
        if not ATTENDANCE_NOTIFICATIONS_AVAILABLE:
            messagebox.showerror(_("common.error"), "Attendance notification service not available")
            return

        try:
            service = AttendanceNotificationService(attendance_threshold=90.0)
            low_attendance_students = service.get_low_attendance_students()

            # Create report window
            report_window = tk.Toplevel(self.window)
            report_window.title("Attendance Report - At-Risk Students")
            report_window.geometry("900x600")
            report_window.transient(self.window)

            # Title
            ttk.Label(report_window, text="Students with Attendance Below 90%",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Report treeview
            columns = ("Student ID", "Name", "Module", "Total Sessions",
                       "Attended", "Attendance %")
            tree = ttk.Treeview(report_window, columns=columns, show="headings")

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            # Populate data
            for student in low_attendance_students:
                tree.insert('', 'end', values=(
                    student['student_id'],
                    f"{student['first_name']} {student['last_name']}",
                    f"{student['module_code']} - {student['module_name']}",
                    student['total_sessions'],
                    student['attended_sessions'],
                    f"{student['attendance_percentage']:.1f}%"
                ))

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))

            # Summary
            summary_frame = ttk.Frame(report_window)
            summary_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(summary_frame,
                     text=f"Total At-Risk Students: {len(low_attendance_students)}",
                     font=('Arial', 12, 'bold')).pack()

            # Close button
            ttk.Button(report_window, text=_("common.close"),
                      command=report_window.destroy).pack(pady=10)

        except Exception as e:
            logger.exception("notifications_windows.py:661 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to generate report:\n{e}")
            import traceback
            traceback.print_exc()

    def load_notification_history(self):
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            start_date = self.history_start_var.get()
            end_date = self.history_end_var.get()

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                _ensure_parent_notifications_columns(conn)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        DATE(sent_at) as date,
                        strftime('%I:%M %p', sent_at) as time,
                        student_id,
                        parent_name,
                        notification_type,
                        method,
                        status,
                        subject
                    FROM parent_notifications
                    WHERE DATE(sent_at) BETWEEN ? AND ?
                    ORDER BY sent_at DESC
                    LIMIT 500
                """, (start_date, end_date))

                history = cursor.fetchall()

                if history:
                    for record in history:
                        self.history_tree.insert('', 'end', values=record)
                else:
                    self.history_tree.insert('', 'end', values=("N/A", "", "No notification history found", "", "", "", "", ""))
        except sqlite3.OperationalError:
            logger.exception("notifications_windows.py:700 %s", 'except sqlite3.OperationalError')
            self.history_tree.insert('', 'end', values=("INFO", "", "No notifications sent yet", "", "", "", "", "Send your first notification"))
        except Exception as e:
            logger.exception("notifications_windows.py:702 %s", 'except Exception as e')
            self.history_tree.insert('', 'end', values=("ERROR", "", f"Error loading history: {e}", "", "", "", "", ""))

    def export_notification_history(self):
        import pandas as pd
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"notification_history_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            start_date = self.history_start_var.get()
            end_date = self.history_end_var.get()

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                df = pd.read_sql_query("""
                    SELECT * FROM parent_notifications
                    WHERE DATE(sent_at) BETWEEN ? AND ?
                    ORDER BY sent_at DESC
                """, conn, params=(start_date, end_date))

            df.to_csv(filename, index=False)
            messagebox.showinfo(_("common.success"), f"Notification history exported to:\n{filename}")

        except Exception as e:
            logger.exception("notifications_windows.py:729 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to export history: {e}")

    def view_notification_details(self, event):
        selected = self.history_tree.selection()
        if not selected:
            return

        notification_data = self.history_tree.item(selected[0])['values']

        details = f"""NOTIFICATION DETAILS
{'='*50}

Date: {notification_data[0]}
Time: {notification_data[1]}
Student ID: {notification_data[2]}
Parent: {notification_data[3]}
Type: {notification_data[4]}
Method: {notification_data[5]}
Status: {notification_data[6]}
Subject: {notification_data[7]}
"""

        messagebox.showinfo("Notification Details", details)

    def save_notification_settings(self):
        try:
            # Save settings to database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS parent_notification_settings (
                        id INTEGER PRIMARY KEY,
                        auto_absence INTEGER,
                        auto_low_attendance INTEGER,
                        low_attendance_threshold INTEGER,
                        absence_template TEXT,
                        low_attendance_template TEXT
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO parent_notification_settings (id, auto_absence, auto_low_attendance, low_attendance_threshold, absence_template, low_attendance_template)
                    VALUES (1, ?, ?, ?, ?, ?)
                """, (
                    1 if self.auto_absence_var.get() else 0,
                    1 if self.auto_low_attendance_var.get() else 0,
                    int(self.low_attendance_threshold_var.get()),
                    self.absence_template_text.get("1.0", tk.END).strip(),
                    self.low_attendance_template_text.get("1.0", tk.END).strip()
                ))

                conn.commit()

            messagebox.showinfo(_("common.success"), "Notification settings saved successfully")

        except Exception as e:
            logger.exception("notifications_windows.py:786 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save settings: {e}")

class ParentContactDialog:
    """Dialog for adding/editing parent contacts"""
    def __init__(self, parent, mode, contact_data, callback):
        self.parent = parent
        self.mode = mode  # 'add' or 'edit'
        self.contact_data = contact_data
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.add_parent_contact") if mode == 'add' else _("attendance.windows.edit_parent_contact"))
        self.window.geometry("500x450")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

        if mode == 'edit' and contact_data:
            self.populate_fields()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window,
                               text=f"{'Add New' if self.mode == 'add' else 'Edit'} Parent Contact",
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(self.window, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Student ID
        ttk.Label(form_frame, text="Student ID:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, pady=5, sticky=tk.EW)

        # Parent Name
        ttk.Label(form_frame, text="Parent/Guardian Name:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.parent_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.parent_name_var, width=30).grid(row=1, column=1, pady=5, sticky=tk.EW)

        # Relationship
        ttk.Label(form_frame, text="Relationship:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.relationship_var = tk.StringVar(value="Parent")
        relationship_combo = ttk.Combobox(form_frame, textvariable=self.relationship_var, width=28,
                                         values=["Mother", "Father", "Parent", "Guardian", "Grandparent", "Other"])
        relationship_combo.grid(row=2, column=1, pady=5, sticky=tk.EW)

        # Email
        ttk.Label(form_frame, text="Email:*").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_var, width=30).grid(row=3, column=1, pady=5, sticky=tk.EW)

        # Phone
        ttk.Label(form_frame, text="Phone:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.phone_var, width=30).grid(row=4, column=1, pady=5, sticky=tk.EW)

        # Preferred Contact Method
        ttk.Label(form_frame, text="Preferred Contact:*").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.preferred_var = tk.StringVar(value="email")
        preferred_combo = ttk.Combobox(form_frame, textvariable=self.preferred_var, width=28,
                                      values=["email", "sms", "both"])
        preferred_combo.grid(row=5, column=1, pady=5, sticky=tk.EW)

        form_frame.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("common.save"), command=self.save, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.window.destroy, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

    def populate_fields(self):
        if self.contact_data:
            self.student_id_var.set(self.contact_data[0])
            self.parent_name_var.set(self.contact_data[2])
            self.relationship_var.set(self.contact_data[3])
            self.email_var.set(self.contact_data[4])
            self.phone_var.set(self.contact_data[5])
            self.preferred_var.set(self.contact_data[6])

    def save(self):
        # Validate required fields
        if not self.student_id_var.get() or not self.parent_name_var.get() or not self.email_var.get():
            messagebox.showwarning(_("common.warning"), "Please fill in all required fields (marked with *)")
            return

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                if self.mode == 'add':
                    cursor.execute("""
                        INSERT INTO parent_contacts (student_id, parent_name, relationship, email, phone, preferred_contact)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        self.student_id_var.get(),
                        self.parent_name_var.get(),
                        self.relationship_var.get(),
                        self.email_var.get(),
                        self.phone_var.get(),
                        self.preferred_var.get()
                    ))
                else:  # edit
                    # Update existing contact
                    cursor.execute("""
                        UPDATE parent_contacts
                        SET parent_name = ?, relationship = ?, email = ?, phone = ?, preferred_contact = ?
                        WHERE student_id = ? AND parent_name = ?
                    """, (
                        self.parent_name_var.get(),
                        self.relationship_var.get(),
                        self.email_var.get(),
                        self.phone_var.get(),
                        self.preferred_var.get(),
                        self.student_id_var.get(),
                        self.contact_data[2] if self.contact_data else self.parent_name_var.get()
                    ))

                conn.commit()

            messagebox.showinfo(_("common.success"), f"Parent contact {'added' if self.mode == 'add' else 'updated'} successfully")
            self.callback()  # Refresh parent list
            self.window.destroy()

        except Exception as e:
            logger.exception("notifications_windows.py:915 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save parent contact: {e}")

class NotificationSettingsWindow:
    """Configure notification settings for attendance system"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.notification_settings"))
        self.window.geometry("800x700")
        self.window.transient(parent)
        self.window.grab_set()

        # Load current settings
        self.settings = self.load_settings()
        self.create_widgets()

    def load_settings(self):
        """Load current notification settings from database"""
        settings = {
            'email_enabled': True,
            'sms_enabled': False,
            'push_enabled': True,
            'low_attendance_threshold': 75,
            'notify_parents': True,
            'notify_instructors': True,
            'notify_students': True,
            'daily_summary': True,
            'weekly_report': True,
            'monthly_report': False,
            'alert_on_absence': True,
            'alert_on_late': False,
            'alert_threshold_absences': 3,
            'email_frequency': 'immediate',
            'quiet_hours_enabled': False,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }

        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to load settings from database
                cursor.execute("SELECT setting_key, setting_value FROM notification_settings")
                rows = cursor.fetchall()

                for key, value in rows:
                    if key in settings:
                        # Convert string values to appropriate types
                        if isinstance(settings[key], bool):
                            settings[key] = value.lower() == 'true'
                        elif isinstance(settings[key], int):
                            settings[key] = int(value)
                        else:
                            settings[key] = value

                conn.close()
        except Exception as e:
            logger.exception("notifications_windows.py:976 %s", 'except Exception as e')
            print(f"Error loading notification settings: {e}")

        return settings

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text="🔔 Notification Settings",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        # Create notebook for different settings categories
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # General tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        self.create_general_settings_tab(general_frame)

        # Recipients tab
        recipients_frame = ttk.Frame(notebook)
        notebook.add(recipients_frame, text="Recipients")
        self.create_recipients_tab(recipients_frame)

        # Alerts tab
        alerts_frame = ttk.Frame(notebook)
        notebook.add(alerts_frame, text="Alerts")
        self.create_alerts_tab(alerts_frame)

        # Schedule tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Schedule")
        self.create_schedule_tab(schedule_frame)

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Settings",
                  command=self.save_settings, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="🔄 Reset to Defaults",
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📧 Test Notification",
                  command=self.test_notification).pack(side=tk.LEFT)

        ttk.Button(button_frame, text=_("common.close"),
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def create_general_settings_tab(self, parent):
        """General notification settings"""
        frame = ttk.LabelFrame(parent, text="Notification Channels", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.email_enabled_var = tk.BooleanVar(value=self.settings['email_enabled'])
        self.sms_enabled_var = tk.BooleanVar(value=self.settings['sms_enabled'])
        self.push_enabled_var = tk.BooleanVar(value=self.settings['push_enabled'])

        ttk.Checkbutton(frame, text="📧 Email Notifications",
                       variable=self.email_enabled_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="📱 SMS Notifications",
                       variable=self.sms_enabled_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="🔔 Push Notifications",
                       variable=self.push_enabled_var).pack(anchor=tk.W, pady=5)

        # Frequency settings
        freq_frame = ttk.LabelFrame(parent, text="Notification Frequency", padding=15)
        freq_frame.pack(fill=tk.X, padx=10, pady=10)

        self.email_frequency_var = tk.StringVar(value=self.settings['email_frequency'])

        ttk.Label(freq_frame, text="Email Frequency:").pack(anchor=tk.W, pady=(0, 5))

        freq_options = ['immediate', 'hourly', 'daily', 'weekly']
        for option in freq_options:
            ttk.Radiobutton(freq_frame, text=option.capitalize(),
                           variable=self.email_frequency_var,
                           value=option).pack(anchor=tk.W, padx=20)

    def create_recipients_tab(self, parent):
        """Configure who receives notifications"""
        frame = ttk.LabelFrame(parent, text="Notification Recipients", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.notify_students_var = tk.BooleanVar(value=self.settings['notify_students'])
        self.notify_parents_var = tk.BooleanVar(value=self.settings['notify_parents'])
        self.notify_instructors_var = tk.BooleanVar(value=self.settings['notify_instructors'])

        ttk.Checkbutton(frame, text="👨‍🎓 Notify Students",
                       variable=self.notify_students_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="👨‍👩‍👧 Notify Parents/Guardians",
                       variable=self.notify_parents_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="👨‍🏫 Notify Instructors",
                       variable=self.notify_instructors_var).pack(anchor=tk.W, pady=5)

        # Report settings
        report_frame = ttk.LabelFrame(parent, text="Automated Reports", padding=15)
        report_frame.pack(fill=tk.X, padx=10, pady=10)

        self.daily_summary_var = tk.BooleanVar(value=self.settings['daily_summary'])
        self.weekly_report_var = tk.BooleanVar(value=self.settings['weekly_report'])
        self.monthly_report_var = tk.BooleanVar(value=self.settings['monthly_report'])

        ttk.Checkbutton(report_frame, text="📊 Daily Summary",
                       variable=self.daily_summary_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(report_frame, text="📈 Weekly Report",
                       variable=self.weekly_report_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(report_frame, text="📉 Monthly Report",
                       variable=self.monthly_report_var).pack(anchor=tk.W, pady=5)

    def create_alerts_tab(self, parent):
        """Configure alert triggers"""
        frame = ttk.LabelFrame(parent, text="Alert Triggers", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.alert_on_absence_var = tk.BooleanVar(value=self.settings['alert_on_absence'])
        self.alert_on_late_var = tk.BooleanVar(value=self.settings['alert_on_late'])

        ttk.Checkbutton(frame, text="⚠️ Alert on Absence",
                       variable=self.alert_on_absence_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="⏰ Alert on Late Arrival",
                       variable=self.alert_on_late_var).pack(anchor=tk.W, pady=5)

        # Threshold settings
        threshold_frame = ttk.LabelFrame(parent, text="Alert Thresholds", padding=15)
        threshold_frame.pack(fill=tk.X, padx=10, pady=10)

        # Low attendance threshold
        ttk.Label(threshold_frame, text="Low Attendance Alert Threshold (%):").pack(anchor=tk.W, pady=(0, 5))
        self.low_attendance_threshold_var = tk.IntVar(value=self.settings['low_attendance_threshold'])
        threshold_scale = ttk.Scale(threshold_frame, from_=0, to=100,
                                   variable=self.low_attendance_threshold_var,
                                   orient=tk.HORIZONTAL)
        threshold_scale.pack(fill=tk.X, pady=(0, 5))

        self.threshold_label = ttk.Label(threshold_frame,
                                        text=f"{self.settings['low_attendance_threshold']}%")
        self.threshold_label.pack(anchor=tk.W)

        threshold_scale.configure(command=lambda v: self.threshold_label.config(
            text=f"{int(float(v))}%"))

        # Consecutive absences
        ttk.Label(threshold_frame, text="Alert after N consecutive absences:").pack(anchor=tk.W, pady=(10, 5))
        self.alert_threshold_absences_var = tk.IntVar(value=self.settings['alert_threshold_absences'])
        ttk.Spinbox(threshold_frame, from_=1, to=10,
                   textvariable=self.alert_threshold_absences_var,
                   width=10).pack(anchor=tk.W)

    def create_schedule_tab(self, parent):
        """Configure notification schedule"""
        frame = ttk.LabelFrame(parent, text="Quiet Hours", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.quiet_hours_enabled_var = tk.BooleanVar(value=self.settings['quiet_hours_enabled'])

        ttk.Checkbutton(frame, text="🌙 Enable Quiet Hours (No notifications during this time)",
                       variable=self.quiet_hours_enabled_var).pack(anchor=tk.W, pady=5)

        # Time settings
        time_frame = ttk.Frame(frame)
        time_frame.pack(fill=tk.X, pady=10)

        ttk.Label(time_frame, text="Start Time:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.quiet_hours_start_var = tk.StringVar(value=self.settings['quiet_hours_start'])
        ttk.Entry(time_frame, textvariable=self.quiet_hours_start_var,
                 width=10).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(time_frame, text="(HH:MM format)").grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        ttk.Label(time_frame, text="End Time:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.quiet_hours_end_var = tk.StringVar(value=self.settings['quiet_hours_end'])
        ttk.Entry(time_frame, textvariable=self.quiet_hours_end_var,
                 width=10).grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        ttk.Label(time_frame, text="(HH:MM format)").grid(row=1, column=2, sticky=tk.W, padx=(5, 0), pady=(5, 0))

    def save_settings(self):
        """Save notification settings to database"""
        try:
            # Update settings dictionary
            self.settings['email_enabled'] = self.email_enabled_var.get()
            self.settings['sms_enabled'] = self.sms_enabled_var.get()
            self.settings['push_enabled'] = self.push_enabled_var.get()
            self.settings['low_attendance_threshold'] = self.low_attendance_threshold_var.get()
            self.settings['notify_parents'] = self.notify_parents_var.get()
            self.settings['notify_instructors'] = self.notify_instructors_var.get()
            self.settings['notify_students'] = self.notify_students_var.get()
            self.settings['daily_summary'] = self.daily_summary_var.get()
            self.settings['weekly_report'] = self.weekly_report_var.get()
            self.settings['monthly_report'] = self.monthly_report_var.get()
            self.settings['alert_on_absence'] = self.alert_on_absence_var.get()
            self.settings['alert_on_late'] = self.alert_on_late_var.get()
            self.settings['alert_threshold_absences'] = self.alert_threshold_absences_var.get()
            self.settings['email_frequency'] = self.email_frequency_var.get()
            self.settings['quiet_hours_enabled'] = self.quiet_hours_enabled_var.get()
            self.settings['quiet_hours_start'] = self.quiet_hours_start_var.get()
            self.settings['quiet_hours_end'] = self.quiet_hours_end_var.get()

            # Save to database
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS notification_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Save each setting
                for key, value in self.settings.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO notification_settings (setting_key, setting_value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))

                conn.commit()
                conn.close()

            messagebox.showinfo(_("common.success"), "Notification settings saved successfully!")

            # Log activity
            try:
                from education_system.post_18.university_system.core.activity_logger import log_activity
                log_activity('update', 'notification_settings',
                           details={'settings_count': len(self.settings)})
            except Exception:
                logger.exception("notifications_windows.py:1215 %s", 'except Exception')
        except Exception as e:
            logger.exception("notifications_windows.py:1218 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save settings:\n{e}")
            import traceback
            traceback.print_exc()

    def reset_to_defaults(self):
        """Reset settings to default values"""
        if messagebox.askyesno("Confirm Reset",
                              "Are you sure you want to reset all notification settings to defaults?"):
            # Reset all variables to defaults
            self.email_enabled_var.set(True)
            self.sms_enabled_var.set(False)
            self.push_enabled_var.set(True)
            self.low_attendance_threshold_var.set(75)
            self.notify_parents_var.set(True)
            self.notify_instructors_var.set(True)
            self.notify_students_var.set(True)
            self.daily_summary_var.set(True)
            self.weekly_report_var.set(True)
            self.monthly_report_var.set(False)
            self.alert_on_absence_var.set(True)
            self.alert_on_late_var.set(False)
            self.alert_threshold_absences_var.set(3)
            self.email_frequency_var.set('immediate')
            self.quiet_hours_enabled_var.set(False)
            self.quiet_hours_start_var.set('22:00')
            self.quiet_hours_end_var.set('08:00')

            messagebox.showinfo(_("common.success"), "Settings reset to defaults!")

    def test_notification(self):
        """Send a test notification"""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email
            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

            # Get test email
            test_email = simpledialog.askstring("Test Email",
                                              "Enter email address for test notification:",
                                              parent=self.window)

            if not test_email:
                return

            # Render email from template
            subject, body = render_template('attendance/test_notification', {
                'test_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'email_enabled': 'Enabled' if self.settings['email_enabled'] else 'Disabled',
                'sms_enabled': 'Enabled' if self.settings['sms_enabled'] else 'Disabled',
                'push_enabled': 'Enabled' if self.settings['push_enabled'] else 'Disabled',
                'alert_threshold': str(self.settings['low_attendance_threshold'])
            })

            if not subject or not body:
                # Fallback if template not found
                subject = "Test Notification - Attendance System"
                body = f"""This is a test notification from the Attendance Tracking System.

Test sent at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your notification settings are configured and working correctly!

Current Settings:
- Email: {'Enabled' if self.settings['email_enabled'] else 'Disabled'}
- SMS: {'Enabled' if self.settings['sms_enabled'] else 'Disabled'}
- Push: {'Enabled' if self.settings['push_enabled'] else 'Disabled'}
- Alert Threshold: {self.settings['low_attendance_threshold']}%

This is an automated test message from the University Attendance System.
"""

            success = send_email(test_email, subject, body)

            if success:
                messagebox.showinfo(_("common.success"), f"Test notification sent to {test_email}!")
            else:
                messagebox.showwarning("Failed",
                                     "Failed to send test notification. Please check email configuration.")

        except Exception as e:
            logger.exception("notifications_windows.py:1297 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to send test notification:\n{e}")

