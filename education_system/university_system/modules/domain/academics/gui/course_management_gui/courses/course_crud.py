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


def show_create_course(self):
    """Show create course dialog"""
    dialog = CourseCreateDialog(self.root, self.auth)
    if dialog.result:
        self.refresh_course_list()
        self.update_status(_("course_management.status.course_created").format(course=dialog.result))


def edit_selected_course(self):
    """Edit the selected course"""
    selection = self.course_tree.selection()
    if not selection:
        messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_edit"))
        return

    item = self.course_tree.item(selection[0])
    course_id = item['values'][0]

    dialog = CourseEditDialog(self.root, self.auth, course_id)
    if dialog.result:
        self.refresh_course_list()
        self.update_status(_("course_management.status.course_updated"))


def delete_selected_course(self):
    """Delete the selected course"""
    selection = self.course_tree.selection()
    if not selection:
        messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_delete"))
        return

    item = self.course_tree.item(selection[0])
    course_id = item['values'][0]
    course_code = item['values'][1]
    course_name = item['values'][2]

    # Enhanced delete confirmation with impact analysis
    if self.confirm_course_deletion(course_id, course_code, course_name):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Handle student reassignment before deleting course
                self.reassign_students_from_deleted_course(cursor, course_code)

                # Delete related records first
                cursor.execute("DELETE FROM course_prerequisites WHERE course_id = ? OR prerequisite_course_id = ?", (course_id, course_id))
                cursor.execute("DELETE FROM course_schedule WHERE course_id = ?", (course_id,))
                cursor.execute("DELETE FROM course_waitlist WHERE course_id = ?", (course_id,))
                cursor.execute("DELETE FROM course_history WHERE course_id = ?", (course_id,))

                # Delete the course
                cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))

                conn.commit()

            self.refresh_course_list()
            self.update_status(_("course_management.status.course_deleted").format(course=course_code))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.delete_course_failed").format(error=e))


def reassign_students_from_deleted_course(self, cursor, course_code):
    """Reassign students from a course that's being deleted to other available courses and modules"""
    try:
        # First, delete all modules and assignments for this course
        self.delete_modules_for_course(cursor, course_code)

        # Get students enrolled in the course being deleted
        cursor.execute('''
            SELECT student_id, first_name, last_name
            FROM students
            WHERE course = ?
        ''', (course_code,))
        affected_students = cursor.fetchall()

        if not affected_students:
            return

        # Get available alternative courses (excluding the one being deleted)
        cursor.execute('''
            SELECT course_code FROM courses
            WHERE (status = 'Active' OR status = 'active') AND course_code != ?
            AND course_code IS NOT NULL AND course_code != ''
            AND max_enrollment > current_enrollment
        ''')
        alternative_courses = [row[0] for row in cursor.fetchall()]

        if not alternative_courses:
            # If no alternatives, create a default holding course
            alternative_courses = ['GENERAL']

        import random
        reassignment_count = 0

        # Reassign each student to a random alternative course
        for student_id, first_name, last_name in affected_students:
            new_course = random.choice(alternative_courses)

            # Update student's course
            cursor.execute('''
                UPDATE students
                SET course = ?
                WHERE student_id = ?
            ''', (new_course, student_id))

            # Remove student from modules of the deleted course
            cursor.execute('''
                DELETE FROM student_modules
                WHERE student_id = ? AND module_code IN (
                    SELECT module_code FROM modules WHERE department = ?
                )
            ''', (student_id, course_code))

            # Assign student to modules of the new course
            self.assign_student_to_course_modules(cursor, student_id, new_course)

            # Update course enrollment counts
            cursor.execute('''
                UPDATE courses
                SET current_enrollment = current_enrollment + 1
                WHERE course_code = ?
            ''', (new_course,))

            reassignment_count += 1

        # Decrease enrollment count for the deleted course
        cursor.execute('''
            UPDATE courses
            SET current_enrollment = current_enrollment - ?
            WHERE course_code = ?
        ''', (reassignment_count, course_code))

        print(_("course_management.success.students_reassigned", count=reassignment_count, code=course_code))

    except Exception as e:
        print(_("course_management.errors.student_reassignment", error=str(e)))


def delete_modules_for_course(self, cursor, course_code):
    """Delete all modules and their assignments for a specific course"""
    try:
        # Get all modules for this course
        cursor.execute('SELECT module_code FROM modules WHERE department = ?', (course_code,))
        modules = [row[0] for row in cursor.fetchall()]

        for module_code in modules:
            # Delete assignments and related data for each module
            self.delete_assignments_for_module(cursor, module_code)

        # Delete all modules for this course
        cursor.execute('DELETE FROM modules WHERE department = ?', (course_code,))
        print(_("course_management.success.modules_deleted", count=len(modules), code=course_code))

    except Exception as e:
        print(_("course_management.errors.module_delete", code=course_code, error=str(e)))


def delete_assignments_for_module(self, cursor, module_code):
    """Delete all assignments and related data for a specific module"""
    try:
        # Get all assignment IDs for this module
        cursor.execute('SELECT id FROM assignments WHERE module_code = ?', (module_code,))
        assignment_ids = [row[0] for row in cursor.fetchall()]

        if assignment_ids:
            # Delete assignment submissions first
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))

            # Delete peer reviews for these assignments
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM peer_reviews WHERE assignment_id = ?', (assignment_id,))

            # Delete extension requests for these assignments
            for assignment_id in assignment_ids:
                cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))

            # Delete the assignments themselves
            cursor.execute('DELETE FROM assignments WHERE module_code = ?', (module_code,))

        # Also delete any assessments for this module
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'")
        if cursor.fetchone():
            cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))

    except Exception as e:
        print(_("course_management.errors.assignment_delete", code=module_code, error=str(e)))


def assign_student_to_course_modules(self, cursor, student_id, course_code):
    """Assign a student to random modules from their new course"""
    try:
        import random
        from datetime import datetime

        # Get available modules for the new course
        cursor.execute('''
            SELECT module_code, module_name FROM modules
            WHERE department = ? AND is_active = 1
        ''', (course_code,))
        available_modules = cursor.fetchall()

        if available_modules:
            # Randomly select 3-5 modules for the student
            num_modules = min(random.randint(3, 5), len(available_modules))
            selected_modules = random.sample(available_modules, num_modules)

            current_date = datetime.now().strftime('%Y-%m-%d')

            for module_code, module_name in selected_modules:
                cursor.execute('''
                    INSERT OR IGNORE INTO student_modules (student_id, module_code, enrollment_date, status)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, module_code, current_date, 'Enrolled'))

            print(_("course_management.success.student_assigned_modules", id=student_id, count=len(selected_modules), code=course_code))

    except Exception as e:
        print(_("course_management.errors.student_assign_modules", id=student_id, error=str(e)))


def confirm_course_deletion(self, course_id, course_code, course_name):
    """Show enhanced deletion confirmation dialog"""
    try:
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Get impact analysis
            cursor.execute("SELECT current_enrollment FROM courses WHERE id = ?", (course_id,))
            enrolled = cursor.fetchone()
            enrolled_count = enrolled[0] if enrolled and enrolled[0] else 0

            cursor.execute("SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?", (course_id,))
            prereq_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM course_schedule WHERE course_id = ?", (course_id,))
            schedule_count = cursor.fetchone()[0]

        # Create confirmation dialog
        message = f"Delete Course: {course_code} - {course_name}\n\n"
        message += "IMPACT ANALYSIS:\n"
        message += f"• Students enrolled: {enrolled_count}\n"
        message += f"• Courses using as prerequisite: {prereq_count}\n"
        message += f"• Schedule entries: {schedule_count}\n\n"

        if enrolled_count > 0 or prereq_count > 0:
            message += _("course_management.messages.deletion_warning") + "\n"
            message += _("course_management.messages.consider_inactive") + "\n\n"

        message += _("course_management.messages.action_cannot_be_undone")

        return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), message)

    except sqlite3.Error:
        return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), _("course_management.messages.delete_course_confirm").format(code=course_code, name=course_name))


class CourseCreateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create New Course")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Basic Information
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, pady=5)

        ttk.Label(basic_frame, text="Course Code:").grid(row=0, column=0, sticky=tk.W)
        self.code_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.code_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(basic_frame, text="(e.g. CS, DS, ENG)", font=('Arial', 8)).grid(row=0, column=2, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Course Name:").grid(row=1, column=0, sticky=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW)
        self.desc_text = tk.Text(basic_frame, width=40, height=3)
        self.desc_text.grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Department:").grid(row=3, column=0, sticky=tk.W)
        self.dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(basic_frame, textvariable=self.dept_var, width=25,
                                  values=["Computer Science", "Data Science", "Engineering",
                                          "Mathematics", "Business", "Arts", "Science", "Other"])
        dept_combo.grid(row=3, column=1, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Level:").grid(row=4, column=0, sticky=tk.W)
        self.level_var = tk.StringVar(value="Undergraduate")
        level_combo = ttk.Combobox(basic_frame, textvariable=self.level_var, state='readonly',
                                  values=["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"])
        level_combo.grid(row=4, column=1, sticky=tk.W, padx=5)

        # Academic Details
        academic_frame = ttk.LabelFrame(main_frame, text="Academic Details", padding=10)
        academic_frame.pack(fill=tk.X, pady=5)

        ttk.Label(academic_frame, text="Credit Hours:").grid(row=0, column=0, sticky=tk.W)
        self.credits_var = tk.StringVar(value="3.0")
        ttk.Entry(academic_frame, textvariable=self.credits_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(academic_frame, text="Max Enrollment:").grid(row=1, column=0, sticky=tk.W)
        self.max_enroll_var = tk.StringVar(value="30")
        ttk.Entry(academic_frame, textvariable=self.max_enroll_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(academic_frame, text="Course Type:").grid(row=2, column=0, sticky=tk.W)
        self.type_var = tk.StringVar(value="Degree Program")
        type_combo = ttk.Combobox(academic_frame, textvariable=self.type_var, state='readonly',
                                 values=["Degree Program", "Certificate", "Diploma", "Short Course"])
        type_combo.grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(academic_frame, text="Course Fee:").grid(row=3, column=0, sticky=tk.W)
        self.fee_var = tk.StringVar(value="0.0")
        ttk.Entry(academic_frame, textvariable=self.fee_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Additional Options
        options_frame = ttk.LabelFrame(main_frame, text="Additional Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        self.lab_required = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Lab Required", variable=self.lab_required).grid(row=0, column=0, sticky=tk.W)

        self.online_available = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Online Available", variable=self.online_available).grid(row=0, column=1, sticky=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Create Course", command=self.create_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def create_course(self):
        try:
            # Validate inputs
            course_code = self.code_var.get().strip().upper()
            course_name = self.name_var.get().strip()

            if not course_code or not course_name:
                messagebox.showerror(_("common.validation_error"), "Course code and name are required.")
                return

            # Validate course code format — 2-4 uppercase letters, optionally followed by digits
            if not re.match(r'^[A-Z]{2,4}\d{0,4}$', course_code):
                messagebox.showerror(_("common.validation_error"),
                                     "Invalid course code format. Use 2-4 letters optionally followed by digits (e.g. CS, ENG, BUS101).")
                return

            description = self.desc_text.get(1.0, tk.END).strip()
            department = self.dept_var.get().strip()
            level = self.level_var.get().strip()

            try:
                credit_hours = float(self.credits_var.get())
                max_enrollment = int(self.max_enroll_var.get())
                course_fee = float(self.fee_var.get())
            except ValueError:
                messagebox.showerror(_("common.validation_error"), "Please enter valid numbers for credits, enrollment, and fee.")
                return

            course_type = self.type_var.get()
            lab_required = self.lab_required.get()
            online_available = self.online_available.get()

            import uuid
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
                cursor = conn.cursor()

                # Check for duplicate code
                cursor.execute(
                    "SELECT COALESCE(course_code, code) FROM courses WHERE UPPER(COALESCE(course_code, code)) = ?",
                    (course_code,)
                )
                if cursor.fetchone():
                    messagebox.showerror(_("common.duplicate_error"), f"Course code '{course_code}' already exists.")
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                course_id = str(uuid.uuid4())

                cursor.execute('''
                INSERT INTO courses (
                    id, code, name, credits, date_added,
                    course_code, course_name, description, level, department,
                    credit_hours, max_enrollment, course_type, course_fee,
                    lab_required, online_available, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (course_id, course_code, course_name, int(credit_hours), timestamp,
                      course_code, course_name, description, level, department,
                      credit_hours, max_enrollment, course_type, course_fee,
                      lab_required, online_available, timestamp, timestamp))

                conn.commit()

                messagebox.showinfo(_("common.success"), f"Course '{course_code} - {course_name}' created successfully.")
                self.result = f"{course_code} - {course_name}"
                self.dialog.destroy()

            finally:
                if conn:
                    conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to create course: {e}")


class CourseEditDialog:
    def __init__(self, parent, auth, course_id):
        self.parent = parent
        self.auth = auth
        self.course_id = course_id
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Course")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.load_course_data()
        self.create_widgets()
        self.dialog.focus_set()

    def load_course_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM courses WHERE id = ?", (self.course_id,))
            self.course_data = cursor.fetchone()
            conn.close()

            if not self.course_data:
                messagebox.showerror(_("common.error"), "Course not found.")
                self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load course: {e}")
            self.dialog.destroy()

    def create_widgets(self):
        # Similar to create dialog but pre-populate with existing data
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Basic Information
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Information", padding=10)
        basic_frame.pack(fill=tk.X, pady=5)

        ttk.Label(basic_frame, text="Course Code:").grid(row=0, column=0, sticky=tk.W)
        self.code_var = tk.StringVar(value=self.course_data[1])
        ttk.Entry(basic_frame, textvariable=self.code_var, width=15).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Course Name:").grid(row=1, column=0, sticky=tk.W)
        self.name_var = tk.StringVar(value=self.course_data[2])
        ttk.Entry(basic_frame, textvariable=self.name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW)
        self.desc_text = tk.Text(basic_frame, width=40, height=3)
        self.desc_text.grid(row=2, column=1, sticky=tk.W, padx=5)
        if len(self.course_data) > 3 and self.course_data[3]:
            self.desc_text.insert(1.0, self.course_data[3])

        # Add other fields similar to create dialog...
        # (For brevity, showing key fields)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Update Course", command=self.update_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def update_course(self):
        try:
            # Get updated values
            course_code = self.code_var.get().strip().upper()
            course_name = self.name_var.get().strip()
            description = self.desc_text.get(1.0, tk.END).strip()

            if not course_code or not course_name:
                messagebox.showerror(_("common.validation_error"), "Course code and name are required.")
                return

            # Update database
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                UPDATE courses
                SET course_code = ?, course_name = ?, description = ?
                WHERE id = ?
                ''', (course_code, course_name, description, self.course_id))

                conn.commit()
            finally:
                conn.close()

            self.result = True
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to update course: {e}")
