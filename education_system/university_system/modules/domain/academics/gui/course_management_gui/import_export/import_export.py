# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.constants import paths

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
_CENTRALDEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# --------------------------------------------------------------------
# Override sqlite3.connect for this GUI. Many database calls within this
# module reference 'courses.db' or str(DEFAULT_DB_PATH) directly. Without
# overriding, these calls would create separate database files in the
# working directory, leading to inconsistencies and missing tables. By
# redirecting those names to the central student_records.db located in
# university_system/data/db_files, we ensure a single database file is
# used across the entire application. Only connections specifying no
# database or targeting courses.db/student_records.db are redirected;
# all other database paths are left untouched.

_original_sqlite_connect = sqlite3.connect

def _patched_sqlite_connect(database, *args, **kwargs):
    try:
        db_name = os.path.basename(str(database)) if database else ""
        if not database or db_name in (str(DEFAULT_DB_PATH), "courses.db"):
            return _original_sqlite_connect(str(_CENTRALDEFAULT_DB_PATH), *args, **kwargs)
    except Exception:
        pass
    return _original_sqlite_connect(database, *args, **kwargs)

sqlite3.connect = _patched_sqlite_connect
import re
import csv
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import threading
import os
import logging

# Import chart generation utility
try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import seaborn as sns
    import numpy as np
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    plt = None
    Figure = None
    FigureCanvasTkAgg = None
    sns = None
    np = None

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.university_system.modules.domain.academics.services.course_management import (
        add_prerequisite, create_course, create_enhanced_course,
        display_enhanced_course_menu, find_alternative_courses,
        generate_course_analytics, generate_enrollment_report,
        initialize_enhanced_database, remove_prerequisite, search_courses,
        update_course, update_schedule, view_all_courses, view_course_details
    )
    ORIGINAL_MODULE_AVAILABLE = True
except ImportError:
    ORIGINAL_MODULE_AVAILABLE = False
    print(_("course_management.warnings.original_module_not_found"))

# Import academic system launchers
try:
    from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_import_csv(self):
    """Show import CSV dialog"""
    dialog = ImportExportDialog(self.root, self.auth, "import")
    if dialog.result:
        self.refresh_course_list()
        self.update_status(_("course_management.status.courses_imported"))


def show_export_csv(self):
    """Show export CSV dialog"""
    dialog = ImportExportDialog(self.root, self.auth, "export")
    if dialog.result:
        self.update_status(_("course_management.status.courses_exported"))


def import_csv(self):
    """Import courses from CSV file"""
    file_path = filedialog.askopenfilename(
        title="Select CSV file to import",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        imported_count = 0
        error_count = 0

        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            required_fields = ['course_code', 'course_name', 'department']
            if not all(field in reader.fieldnames for field in required_fields):
                messagebox.showerror(_("common.import_error"), f"CSV must contain these required columns: {', '.join(required_fields)}")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                for row_num, row in enumerate(reader, 1):
                    try:
                        course_code = row['course_code'].strip().upper()
                        course_name = row['course_name'].strip()
                        department = row['department'].strip()

                        if not course_code or not course_name:
                            error_count += 1
                            continue

                        # Check for duplicates
                        cursor.execute("SELECT id FROM courses WHERE code = ?", (course_code,))
                        if cursor.fetchone():
                            error_count += 1
                            continue

                        # Prepare optional fields
                        description = row.get('description', '').strip()
                        level = row.get('level', '').strip()
                        credit_hours = float(row.get('credit_hours', 3.0))
                        max_enrollment = int(row.get('max_enrollment', 30))
                        course_type = row.get('course_type', 'Core').strip()

                        import uuid
                        course_id = str(uuid.uuid4())

                        # Insert course
                        cursor.execute('''
                        INSERT INTO courses (
                            id, code, name, credits, date_added,
                            course_code, course_name, description, level, department,
                            credit_hours, max_enrollment, course_type, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                              course_code, course_name, description, level, department,
                              credit_hours, max_enrollment, course_type, timestamp, timestamp))

                        imported_count += 1

                    except (ValueError, sqlite3.Error):
                        error_count += 1
                        continue

                conn.commit()
            finally:
                conn.close()

        self.refresh_course_list()

        message = f"Import completed!\n\nSuccessfully imported: {imported_count} courses\nErrors: {error_count} courses"
        messagebox.showinfo("Import Results", message)
        self.update_status(f"Imported {imported_count} courses from CSV")

    except Exception as e:
        messagebox.showerror(_("common.import_error"), f"Failed to import CSV: {e}")


def export_csv(self):
    """Export courses to CSV file"""
    file_path = filedialog.asksaveasfilename(
        title="Save CSV file",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM courses ORDER BY course_code")
        courses = cursor.fetchall()

        # Get column names
        cursor.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in cursor.fetchall()]

        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(columns)
            writer.writerows(courses)

        conn.close()

        messagebox.showinfo(_("common.export_complete"), f"Exported {len(courses)} courses to {file_path}")
        self.update_status(f"Exported {len(courses)} courses to CSV")

    except Exception as e:
        messagebox.showerror(_("common.export_error"), f"Failed to export CSV: {e}")


def backup_database(self):
    """Create database backup - enhanced version"""
    file_path = filedialog.asksaveasfilename(
        title="Save database backup",
        defaultextension=".sql",
        filetypes=[("SQL files", "*.sql"), ("SQLite files", "*.db"), ("All files", "*.*")]
    )

    if not file_path:
        return

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")

        if file_path.endswith('.sql'):
            # SQL dump backup
            with open(file_path, 'w') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
        else:
            # Binary database copy
            backup_conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                conn.backup(backup_conn)
            finally:
                backup_conn.close()

        conn.close()

        messagebox.showinfo("Backup Complete", f"Database backup saved to {file_path}")
        self.update_status("Database backup created")

    except Exception as e:
        messagebox.showerror("Backup Error", f"Failed to create backup: {e}")


def import_courses_from_csv_wrapper(self):
    """Import courses from CSV file. Calls existing import_csv()."""
    self.import_csv()


def export_courses_to_csv_wrapper(self):
    """Export courses to CSV file. Calls existing export_csv()."""
    self.export_csv()


class ImportExportDialog:
    def __init__(self, parent, auth, operation="import"):
        self.parent = parent
        self.auth = auth
        self.operation = operation
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"{operation.capitalize()} Courses")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=f"{self.operation.capitalize()} Courses",
                 font=("Arial", 12, "bold")).pack(pady=10)

        if self.operation == "import":
            self.create_import_widgets(main_frame)
        else:
            self.create_export_widgets(main_frame)

    def create_import_widgets(self, parent):
        # File selection
        file_frame = ttk.LabelFrame(parent, text="Select CSV File", padding=10)
        file_frame.pack(fill=tk.X, pady=5)

        self.file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.RIGHT, padx=(5,0))

        # Requirements
        req_frame = ttk.LabelFrame(parent, text="CSV Requirements", padding=10)
        req_frame.pack(fill=tk.X, pady=5)

        requirements = [
            "• Required columns: course_code, course_name, department",
            "• Optional columns: description, level, credit_hours, max_enrollment, course_type",
            "• Course codes must be unique and follow format (e.g., CS101)",
            "• First row should contain column headers"
        ]

        for req in requirements:
            ttk.Label(req_frame, text=req).pack(anchor=tk.W)

        # Options
        options_frame = ttk.LabelFrame(parent, text="Import Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        self.skip_duplicates = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip duplicate course codes",
                       variable=self.skip_duplicates).pack(anchor=tk.W)

        self.validate_codes = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate course code format",
                       variable=self.validate_codes).pack(anchor=tk.W)

        # Progress display
        self.progress_text = ScrolledText(parent, height=8)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Import", command=self.import_courses).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def create_export_widgets(self, parent):
        # Filter options
        filter_frame = ttk.LabelFrame(parent, text="Export Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.dept_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.dept_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(filter_frame, text="Level:").grid(row=1, column=0, sticky=tk.W)
        self.level_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.level_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(filter_frame, text="Status:").grid(row=2, column=0, sticky=tk.W)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_var,
                                   values=["", "Active", "Inactive", "Archived", "Cancelled"])
        status_combo.grid(row=2, column=1, sticky=tk.W, padx=5)

        # File location
        file_frame = ttk.LabelFrame(parent, text="Export Location", padding=10)
        file_frame.pack(fill=tk.X, pady=5)

        self.export_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.export_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Browse", command=self.browse_export_file).pack(side=tk.RIGHT, padx=(5,0))

        # Progress display
        self.progress_text = ScrolledText(parent, height=8)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Export", command=self.export_courses).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.file_var.set(filename)

    def browse_export_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.export_file_var.set(filename)

    def import_courses(self):
        file_path = self.file_var.get()
        if not file_path:
            messagebox.showwarning("No File", "Please select a CSV file to import.")
            return

        try:
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, f"Starting import from {file_path}...\n")

            imported_count = 0
            error_count = 0

            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)

                required_fields = ['course_code', 'course_name', 'department']
                if not all(field in reader.fieldnames for field in required_fields):
                    self.progress_text.insert(tk.END, f"ERROR: CSV must contain these required columns: {', '.join(required_fields)}\n")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                try:
                    cursor = conn.cursor()
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for row_num, row in enumerate(reader, 1):
                        try:
                            course_code = row['course_code'].strip().upper()
                            course_name = row['course_name'].strip()
                            department = row['department'].strip()

                            if not course_code or not course_name:
                                self.progress_text.insert(tk.END, f"Row {row_num}: Missing required fields\n")
                                error_count += 1
                                continue

                            if self.validate_codes.get() and not re.match(r'^[A-Z]{2,4}\d{2,3}$', course_code):
                                self.progress_text.insert(tk.END, f"Row {row_num}: Invalid course code format: {course_code}\n")
                                error_count += 1
                                continue

                            if self.skip_duplicates.get():
                                cursor.execute("SELECT id FROM courses WHERE code = ?", (course_code,))
                                if cursor.fetchone():
                                    self.progress_text.insert(tk.END, f"Row {row_num}: Skipping duplicate course code {course_code}\n")
                                    error_count += 1
                                    continue

                            # Insert course
                            description = row.get('description', '').strip()
                            level = row.get('level', '').strip()
                            credit_hours = float(row.get('credit_hours', 3.0))
                            max_enrollment = int(row.get('max_enrollment', 30))
                            course_type = row.get('course_type', 'Core').strip()

                            import uuid
                            course_id = str(uuid.uuid4())

                            cursor.execute('''
                            INSERT INTO courses (
                                id, code, name, credits, date_added,
                                course_code, course_name, description, level, department,
                                credit_hours, max_enrollment, course_type, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                                  course_code, course_name, description, level, department,
                                  credit_hours, max_enrollment, course_type, timestamp, timestamp))

                            self.progress_text.insert(tk.END, f"Row {row_num}: Imported {course_code} - {course_name}\n")
                            imported_count += 1

                        except (ValueError, sqlite3.Error) as e:
                            self.progress_text.insert(tk.END, f"Row {row_num}: Error - {e}\n")
                            error_count += 1
                            continue

                    conn.commit()
                finally:
                    conn.close()

            self.progress_text.insert(tk.END, f"\nImport completed!\n")
            self.progress_text.insert(tk.END, f"Successfully imported: {imported_count} courses\n")
            self.progress_text.insert(tk.END, f"Errors: {error_count} courses\n")

            self.result = imported_count > 0

        except FileNotFoundError:
            messagebox.showerror("File Error", "File not found.")
        except Exception as e:
            messagebox.showerror(_("common.import_error"), f"Failed to import CSV: {e}")

    def export_courses(self):
        file_path = self.export_file_var.get()
        if not file_path:
            messagebox.showwarning("No File", "Please specify a location to save the CSV file.")
            return

        try:
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, f"Starting export to {file_path}...\n")

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()

                # Build query with filters
                conditions = []
                params = []

                if self.dept_var.get():
                    conditions.append("department = ?")
                    params.append(self.dept_var.get())

                if self.level_var.get():
                    conditions.append("level = ?")
                    params.append(self.level_var.get())

                if self.status_var.get():
                    conditions.append("status = ?")
                    params.append(self.status_var.get())

                query = "SELECT * FROM courses"
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY course_code"

                cursor.execute(query, params)
                courses = cursor.fetchall()

                if not courses:
                    self.progress_text.insert(tk.END, "No courses found to export.\n")
            finally:
                conn.close()
                return

            # Get column names
            cursor.execute("PRAGMA table_info(courses)")
            columns = [col[1] for col in cursor.fetchall()]

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(columns)
                writer.writerows(courses)

            conn.close()

            self.progress_text.insert(tk.END, f"Exported {len(courses)} courses to {file_path}\n")
            self.result = True

        except Exception as e:
            messagebox.showerror(_("common.export_error"), f"Failed to export CSV: {e}")
