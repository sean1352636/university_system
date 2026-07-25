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
    logger = configure_logging(name="attendance_tracker.gui.attendance_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.attendance_windows")
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
    logger.exception("attendance_windows.py:50 %s", 'except ImportError')
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
    logger.exception("attendance_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from education_system.systems.university.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("attendance_windows.py:75 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True


_ABSENCE_PLACEHOLDER_NOTES = {"", "batch entry", "manual gui entry", "gui edit"}
_NON_PRESENT_STATUSES = {"absent", "late", "excused"}


def _sync_to_absence_db(module_code, date_str, attendance_data, recorded_by=None):
    """Mirror non-present rows into the absence tracker's tables.

    For every row whose status is absent/late/excused, insert into
    ``attendance`` (powers "All Absences"). Additionally, for absent rows
    with no real reason, file a pending row in ``absence_requests``
    (powers "Pending Requests" + the badge).

    attendance_data tuples: (student_id, status, notes). Best-effort —
    failure here must not block attendance recording. Returns
    ``(n_absences, n_requests)``.
    """
    rows = [
        (sid, str(status).strip().lower(), (notes or "").strip())
        for (sid, status, notes) in attendance_data
    ]
    rows = [(sid, st, n) for (sid, st, n) in rows if st in _NON_PRESENT_STATUSES]
    if not rows:
        return (0, 0)
    try:
        from education_system.systems.university.domain.academics.services.attendance.absence_tracking.absence_tracker import (  # noqa: E501
            Database as _AbsenceDB,
        )
        db = _AbsenceDB()
        try:
            n_abs = 0
            n_req = 0
            for sid, status, notes in rows:
                try:
                    db.record_absence(sid, module_code, date_str, status,
                                      notes or "", recorded_by=recorded_by)
                    n_abs += 1
                except Exception:
                    logger.exception("record_absence failed sid=%s", sid)
                    continue
                if status == "absent" and notes.lower() in _ABSENCE_PLACEHOLDER_NOTES:
                    try:
                        rid = db.submit_request(
                            sid, module_code, date_str,
                            "(auto) absence recorded — reason pending")
                        n_req += 1
                        # If an exam exists on this (module, date), tag the
                        # request as a missed-exam so the exam GUI's
                        # Deferred Exam Requests tab picks it up.
                        try:
                            exam_row = db.cur.execute(
                                "SELECT id FROM exams "
                                "WHERE module_code = ? AND date = ? "
                                "LIMIT 1",
                                (module_code, date_str),
                            ).fetchone()
                            if exam_row:
                                db.cur.execute(
                                    "UPDATE absence_requests "
                                    "SET is_missed_exam = 1, exam_id = ? "
                                    "WHERE id = ?",
                                    (exam_row[0], rid),
                                )
                                db.conn.commit()
                        except Exception:
                            logger.exception(
                                "missed-exam flag update failed rid=%s", rid)
                    except Exception:
                        logger.exception("submit_request failed sid=%s", sid)
            absent_sids = {sid for (sid, st, _n) in rows if st == "absent"}
            if absent_sids:
                try:
                    from education_system.systems.university.domain.academics.services.attendance.absence_tracking.email_notifications import (  # noqa: E501
                        notify_frequent_absences,
                        maybe_create_wellbeing_referral,
                    )
                    for sid in absent_sids:
                        notify_frequent_absences(db, sid)
                        maybe_create_wellbeing_referral(db, sid)
                except Exception:
                    logger.exception("frequent-absence dispatch failed")
            return (n_abs, n_req)
        finally:
            db.close()
    except Exception:
        logger.exception("absence-db sync failed")
        return (0, 0)


class ManualAttendanceWindow:
    def __init__(self, parent, module_code, date, callback):
        self.parent = parent
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.manual_attendance')} - {module_code}")
        self.window.geometry("600x400")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()
        self.load_students()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Manual Attendance Entry", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))

        # Students frame
        students_frame = ttk.Frame(self.window)
        students_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Headers
        headers_frame = ttk.Frame(students_frame)
        headers_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(headers_frame, text="Student ID", width=15).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Name", width=25).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Status", width=15).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Notes", width=20).pack(side=tk.LEFT)

        # Scrollable frame for students
        canvas = tk.Canvas(students_frame)
        scrollbar = ttk.Scrollbar(students_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.student_widgets = []

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save Attendance",
                  command=self.save_attendance, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Mark All Present",
                  command=self.mark_all_present, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def load_students(self):
        """Load students for the module"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample students
                students = [("S001", "John", "Doe"), ("S002", "Jane", "Smith"), ("S003", "Bob", "Wilson")]
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ORDER BY s.student_id
                ''', (self.module_code,))
                students = cursor.fetchall()
                conn.close()

            for student_id, first_name, last_name in students:
                self.create_student_row(student_id, f"{first_name} {last_name}")

        except Exception as e:
            logger.exception("attendance_windows.py:171 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to load students: {e}")

    def create_student_row(self, student_id, name):
        """Create a row for student attendance entry"""
        row_frame = ttk.Frame(self.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2)

        # Student ID
        ttk.Label(row_frame, text=student_id, width=15).pack(side=tk.LEFT)

        # Name
        ttk.Label(row_frame, text=name, width=25).pack(side=tk.LEFT)

        # Status
        status_var = tk.StringVar(value="Present")
        status_combo = ttk.Combobox(row_frame, textvariable=status_var,
                                   values=["Present", "Late", "Absent", "Excused"],
                                   state="readonly", width=12)
        status_combo.pack(side=tk.LEFT, padx=(0, 5))

        # Notes
        notes_var = tk.StringVar()
        notes_entry = ttk.Entry(row_frame, textvariable=notes_var, width=18)
        notes_entry.pack(side=tk.LEFT)

        self.student_widgets.append({
            'student_id': student_id,
            'status_var': status_var,
            'notes_var': notes_var
        })

    def mark_all_present(self):
        """Mark all students as present"""
        for widget in self.student_widgets:
            widget['status_var'].set("Present")

    def save_attendance(self):
        """Save attendance records"""
        try:
            attendance_data = []
            for widget in self.student_widgets:
                attendance_data.append((
                    widget['student_id'],
                    widget['status_var'].get(),
                    widget['notes_var'].get()
                ))

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = record_attendance(self.module_code, self.date, attendance_data, "Manual GUI Entry")
                if success:
                    n_abs, n_req = _sync_to_absence_db(
                        self.module_code, self.date, attendance_data,
                        recorded_by="Manual GUI Entry")
                    msg = "Attendance recorded successfully!"
                    if n_abs:
                        msg += f"\n{n_abs} absence/late row(s) mirrored to the Absence Tracker."
                    if n_req:
                        msg += f"\n{n_req} pending request(s) created for absentees with no reason."
                    messagebox.showinfo(_("common.success"), msg)
                    self.callback()  # Refresh parent data
                    self.window.destroy()
                else:
                    messagebox.showerror(_("common.error"), "Failed to record attendance")
            else:
                messagebox.showinfo("Demo", "Attendance would be recorded here")
                self.callback()
                self.window.destroy()

        except Exception as e:
            logger.exception("attendance_windows.py:232 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save attendance: {e}")

class BatchAttendanceWindow:
    """Window for marking attendance for all students in a module at once"""
    def __init__(self, parent, module_code, date, callback):
        self.parent = parent
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.batch_attendance')} - {module_code}")
        self.window.geometry("700x500")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()
        self.load_students()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Batch Attendance Entry", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))

        # Batch action frame
        batch_frame = ttk.LabelFrame(self.window, text="Batch Actions", padding=10)
        batch_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Status selector
        status_selector_frame = ttk.Frame(batch_frame)
        status_selector_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_selector_frame, text="Mark Selected As:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_status_var = tk.StringVar(value="Present")
        status_combo = ttk.Combobox(status_selector_frame, textvariable=self.batch_status_var,
                                   values=["Present", "Late", "Absent", "Excused"],
                                   state="readonly", width=15)
        status_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(status_selector_frame, text="Apply to Selected",
                  command=self.apply_batch_status, style='Primary.TButton').pack(side=tk.LEFT)

        # Selection buttons
        selection_frame = ttk.Frame(batch_frame)
        selection_frame.pack(fill=tk.X, pady=5)

        ttk.Button(selection_frame, text="Select All",
                  command=self.select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(selection_frame, text="Deselect All",
                  command=self.deselect_all).pack(side=tk.LEFT)

        # Students frame with scrollbar
        students_frame = ttk.LabelFrame(self.window, text="Students", padding=10)
        students_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Treeview for students
        columns = ("Select", "ID", "Name", "Status")
        self.students_tree = ttk.Treeview(students_frame, columns=columns, show="headings", height=15)

        self.students_tree.heading("Select", text="✓")
        self.students_tree.heading("ID", text="Student ID")
        self.students_tree.heading("Name", text="Name")
        self.students_tree.heading("Status", text="Current Status")

        self.students_tree.column("Select", width=40)
        self.students_tree.column("ID", width=120)
        self.students_tree.column("Name", width=200)
        self.students_tree.column("Status", width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind click event for checkbox toggle
        self.students_tree.bind('<Button-1>', self.on_tree_click)

        # Track selection state
        self.selected_students = set()

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save All Attendance",
                  command=self.save_attendance, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def load_students(self):
        """Load students for the module"""
        try:
            conn = get_db_connection() if MAIN_DB_AVAILABLE else None

            if conn:
                cursor = conn.cursor()
                # Get students enrolled in the module with their current attendance status
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name,
                       COALESCE(ar.status, 'Not Marked') as current_status
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                    AND ar.module_code = sm.module_code
                    AND ar.date = ?
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''', (self.date, self.module_code))
                students = cursor.fetchall()
                conn.close()
            else:
                # Sample data
                students = [
                    ("S001", "John", "Doe", "Not Marked"),
                    ("S002", "Jane", "Smith", "Not Marked"),
                    ("S003", "Bob", "Wilson", "Not Marked")
                ]

            # Populate treeview
            for student_id, first_name, last_name, current_status in students:
                name = f"{first_name} {last_name}"
                self.students_tree.insert('', 'end', values=("☐", student_id, name, current_status),
                                        tags=(student_id,))
                # Default: select all students
                self.selected_students.add(student_id)

            # Update display
            self.update_selection_display()

        except Exception as e:
            logger.exception("attendance_windows.py:367 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to load students: {e}")
            import traceback
            traceback.print_exc()

    def on_tree_click(self, event):
        """Handle click on treeview to toggle selection"""
        region = self.students_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.students_tree.identify_row(event.y)
            column = self.students_tree.identify_column(event.x)

            # Only toggle if clicking on the checkbox column
            if column == "#1":  # First column
                student_id = self.students_tree.item(item)['values'][1]
                if student_id in self.selected_students:
                    self.selected_students.remove(student_id)
                else:
                    self.selected_students.add(student_id)
                self.update_selection_display()

    def update_selection_display(self):
        """Update checkbox display for all items"""
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item)['values']
            student_id = values[1]
            checkbox = "☑" if student_id in self.selected_students else "☐"
            self.students_tree.item(item, values=(checkbox, values[1], values[2], values[3]))

    def select_all(self):
        """Select all students"""
        for item in self.students_tree.get_children():
            student_id = self.students_tree.item(item)['values'][1]
            self.selected_students.add(student_id)
        self.update_selection_display()

    def deselect_all(self):
        """Deselect all students"""
        self.selected_students.clear()
        self.update_selection_display()

    def apply_batch_status(self):
        """Apply selected status to selected students"""
        if not self.selected_students:
            messagebox.showwarning(_("common.warning"), "No students selected")
            return

        status = self.batch_status_var.get()

        # Update display
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item)['values']
            student_id = values[1]
            if student_id in self.selected_students:
                self.students_tree.item(item, values=(values[0], values[1], values[2], status))

        messagebox.showinfo(_("common.success"), f"Status '{status}' applied to {len(self.selected_students)} selected student(s)")

    def save_attendance(self):
        """Save attendance records for all students"""
        try:
            attendance_data = []

            for item in self.students_tree.get_children():
                values = self.students_tree.item(item)['values']
                student_id = values[1]
                current_status = values[3]

                # Only save if status is not "Not Marked"
                if current_status != "Not Marked":
                    attendance_data.append((student_id, current_status, "Batch entry"))

            if not attendance_data:
                messagebox.showwarning(_("common.warning"), "No attendance records to save")
                return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = record_attendance(self.module_code, self.date, attendance_data, "Batch GUI Entry")
                if success:
                    n_abs, n_req = _sync_to_absence_db(
                        self.module_code, self.date, attendance_data,
                        recorded_by="Batch GUI Entry")
                    msg = f"Attendance recorded for {len(attendance_data)} student(s)!"
                    if n_abs:
                        msg += f"\n{n_abs} absence/late row(s) mirrored to the Absence Tracker."
                    if n_req:
                        msg += f"\n{n_req} pending request(s) created for absentees with no reason."
                    messagebox.showinfo(_("common.success"), msg)
                    self.callback()  # Refresh parent data
                    self.window.destroy()
                else:
                    messagebox.showerror(_("common.error"), "Failed to record attendance")
            else:
                messagebox.showinfo("Demo", f"Attendance would be recorded for {len(attendance_data)} students")
                self.callback()
                self.window.destroy()

        except Exception as e:
            logger.exception("attendance_windows.py:456 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save attendance: {e}")
            import traceback
            traceback.print_exc()

class EditAttendanceWindow:
    def __init__(self, parent, student_id, name, current_status, notes, module_code, date, callback):
        self.parent = parent
        self.student_id = student_id
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"{_('attendance.windows.edit_attendance')} - {student_id}")
        self.window.geometry("400x300")
        self.window.transient(parent)

        self.create_widgets(name, current_status, notes)

        # Set grab after window is fully created and visible
        self.window.after(100, self._safe_grab_set)

    def create_widgets(self, name, current_status, notes):
        # Title
        title_label = ttk.Label(self.window, text="Edit Attendance Record", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Student info
        info_frame = ttk.LabelFrame(self.window, text="Student Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(info_frame, text=f"Student ID: {self.student_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Name: {name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Module: {self.module_code}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Date: {self.date}").pack(anchor=tk.W)

        # Attendance details
        details_frame = ttk.LabelFrame(self.window, text="Attendance Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(details_frame, text="Status:").pack(anchor=tk.W)
        self.status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(details_frame, textvariable=self.status_var,
                                   values=["Present", "Late", "Absent", "Excused"],
                                   state="readonly")
        status_combo.pack(fill=tk.X, pady=(5, 10))

        ttk.Label(details_frame, text="Notes:").pack(anchor=tk.W)
        self.notes_var = tk.StringVar(value=notes or "")
        notes_entry = ttk.Entry(details_frame, textvariable=self.notes_var)
        notes_entry.pack(fill=tk.X, pady=(5, 0))

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save Changes",
                  command=self.save_changes, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text=_("common.cancel"),
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def save_changes(self):
        """Save attendance changes"""
        try:
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT OR REPLACE INTO attendance_records
                (student_id, module_code, date, status, notes, recorded_by, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.student_id, self.module_code, self.date,
                      self.status_var.get(), self.notes_var.get(),
                      "GUI Edit", datetime.datetime.now().isoformat()))

                conn.commit()
                conn.close()

                n_abs, n_req = _sync_to_absence_db(
                    self.module_code, self.date,
                    [(self.student_id, self.status_var.get(), self.notes_var.get())],
                    recorded_by="GUI Edit")
                msg = "Attendance record updated successfully!"
                if n_abs:
                    msg += "\nMirrored to Absence Tracker."
                if n_req:
                    msg += "\nPending absence request created (no reason given)."
                messagebox.showinfo(_("common.success"), msg)
            else:
                messagebox.showinfo("Demo", "Attendance record would be updated here")

            self.callback()  # Refresh parent data
            self.window.destroy()
        except Exception as e:
            logger.exception("attendance_windows.py:542 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save changes: {e}")

    def _safe_grab_set(self):
        """Safely set window grab with error handling"""
        try:
            if self.window.winfo_exists():
                self.window.grab_set()
        except Exception as e:
            logger.exception("attendance_windows.py:550 %s", 'except Exception as e')
            print(f"Warning: Could not set window grab: {e}")

class AddEditStudentWindow:
    def __init__(self, parent, student_data, callback):
        self.parent = parent
        self.student_data = student_data
        self.callback = callback
        self.is_edit = student_data is not None

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.edit_student") if self.is_edit else _("attendance.windows.add_student"))
        self.window.geometry("500x400")
        self.window.transient(parent)

        self.create_widgets()

        # Set grab after window is fully created and visible
        self.window.after(100, self._safe_grab_set)

    def create_widgets(self):
        # Title
        title = "Edit Student" if self.is_edit else "Add New Student"
        title_label = ttk.Label(self.window, text=title, font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Form frame
        form_frame = ttk.LabelFrame(self.window, text="Student Information", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Student ID
        ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(form_frame, textvariable=self.student_id_var, width=30)
        self.student_id_entry.grid(row=0, column=1, pady=5, padx=5)

        # Name
        ttk.Label(form_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var, width=30).grid(row=1, column=1, pady=5, padx=5)

        # Email
        ttk.Label(form_frame, text="Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_var, width=30).grid(row=2, column=1, pady=5, padx=5)

        # If editing, populate fields
        if self.is_edit and self.student_data:
            self.student_id_var.set(self.student_data.get('student_id', ''))
            self.name_var.set(self.student_data.get('name', ''))
            self.email_var.set(self.student_data.get('email', ''))
            self.student_id_entry.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("common.save"), command=self.save_student).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=self.window.destroy).pack(side=tk.LEFT, padx=10)

    def _safe_grab_set(self):
        """Safely set grab on window"""
        try:
            if self.window.winfo_exists():
                self.window.grab_set()
        except Exception as e:
            logger.exception("attendance_windows.py:615 %s", 'except Exception as e')
            print(f"Warning: Could not set window grab: {e}")

    def save_student(self):
        """Save student data"""
        student_id = self.student_id_var.get().strip()
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()

        if not student_id or not name:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.fill_required_fields"))
            return

        # Call callback with student data
        if self.callback:
            self.callback({
                'student_id': student_id,
                'name': name,
                'email': email,
                'is_edit': self.is_edit
            })

        self.window.destroy()


# Alias for backward compatibility
StudentAddWindow = AddEditStudentWindow
