# Auto-generated module (split from student_crud_gui.py)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _safe_set_combobox, _safe_entry_insert
from education_system.systems.university.infrastructure.email.sign_off import office_name

def view_student_attendance(self, student_id, email, first_name, last_name):
    """Display student attendance table and send email if below 90%"""
    try:
        attendance_window = tk.Toplevel(self.root)
        _install_clean_close(attendance_window)
        attendance_window.title(f"Attendance - {first_name} {last_name} ({student_id})")
        attendance_window.geometry("900x600")
        attendance_window.transient(self.root)

        main_frame = ttk.Frame(attendance_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Attendance for {first_name} {last_name}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview for attendance
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Date", "Module", "Session Type", "Status", "Reason")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
        tree.column("Date", width=120)
        tree.column("Module", width=120)
        tree.column("Session Type", width=120)
        tree.column("Status", width=100)
        tree.column("Reason", width=200)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Fetch attendance from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            attendance_window.destroy()
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, module_code, status, notes
            FROM attendance_records
            WHERE student_id = ?
            ORDER BY date DESC
        """, (student_id,))

        attendance_records = cursor.fetchall()
        conn.close()

        present_count = 0
        total_count = len(attendance_records)

        for record in attendance_records:
            # Convert Row object to tuple
            record_tuple = tuple(record)
            date, module, status, reason = record_tuple
            # Default session type to 'Lecture' since it's not in the database
            tree.insert('', tk.END, values=(date, module, 'Lecture', status, reason or ''))
            if status and status.lower() == 'present':
                present_count += 1

        # Calculate attendance percentage
        attendance_percentage = (present_count / total_count * 100) if total_count > 0 else 0

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.attendance_summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(summary_frame, text=f"Total Sessions: {total_count}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Present: {present_count}").grid(row=0, column=1, padx=10)

        # Attendance percentage label with color coding
        percentage_label = ttk.Label(summary_frame,
                                    text=f"Attendance: {attendance_percentage:.1f}%",
                                    font=('TkDefaultFont', 10, 'bold'))
        percentage_label.grid(row=0, column=2, padx=10)

        # Send email if attendance below 90%
        if attendance_percentage < 90 and email:
            # Send email alert
            email_sent = False
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email
                from education_system.systems.university.infrastructure.email.template_utils import render_template

                # Build attendance summary
                attendance_summary = (
                    f"- Total Sessions: {total_count}\n"
                    f"- Sessions Attended: {present_count}\n"
                    f"- Sessions Missed: {total_count - present_count}"
                )

                # Resolved through render_template rather than a hand-built
                # path: this used to open
                # ``templates/email/academics/low_attendance_alert.json``,
                # which does not exist — the template lives two directories
                # deeper, under ``academics/student_support/low_attendance/``.
                # Every alert died on FileNotFoundError inside the except
                # below, so the window only ever showed "Email notification
                # failed". render_template also handles the $placeholder
                # substitution this block was doing by hand.
                subject, message = render_template(
                    'academics/student_support/low_attendance/low_attendance_alert',
                    {
                        'student_name': f"{first_name} {last_name}",
                        'module_name': 'All Modules',
                        'attendance_percentage': f"{attendance_percentage:.1f}",
                        'attendance_summary': attendance_summary,
                        'signature': office_name('Administration'),
                    },
                )

                if subject and message:
                    email_sent = send_email(email, subject, message)
                else:
                    print("Failed to send attendance alert email: template could not be rendered")

            except Exception as e:
                print(f"Failed to send attendance alert email: {e}")

            # Show status label based on whether email was sent
            if email_sent:
                ttk.Label(summary_frame,
                         text=_t('gui.learners.students.student_crud_gui.attendance.labels.low_attendance_alert_sent', default="⚠ Low Attendance Alert Sent"),
                         foreground='red').grid(row=1, column=0, columnspan=3, pady=5)
            else:
                ttk.Label(summary_frame,
                         text=_t('gui.learners.students.student_crud_gui.attendance.labels.low_attendance_email_notification_failed', default="⚠ Low Attendance - Email notification failed"),
                         foreground='orange').grid(row=1, column=0, columnspan=3, pady=5)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"), command=attendance_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_attendance", error=str(e)))
        if 'attendance_window' in locals():
            attendance_window.destroy()

