# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure import paths

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
    from education_system.systems.university.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.systems.university.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.systems.university.domain.academics.services.course_management import (
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
    from education_system.systems.university.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.systems.university.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_prerequisites_window(self):
    """Show prerequisites management window"""
    PrerequisitesWindow(self.root, self.auth)


def show_remove_prerequisite(self):
    """Show remove prerequisite dialog"""
    dialog = RemovePrerequisiteDialog(self.root, self.auth)
    if dialog.result:
        self.update_status(_("course_management.status.prerequisite_removed"))


def add_prerequisite_gui(self):
    """
    Add a prerequisite to a course with circular dependency checking.
    Opens a dialog to select course and prerequisite.
    """
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Course Prerequisite")
    dialog.geometry("500x300")
    dialog.transient(self.root)

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Add Prerequisite to Course",
             font=('Arial', 12, 'bold')).pack(pady=(0, 10))

    # Course selection
    course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
    course_frame.pack(fill=tk.X, pady=5)

    ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=40)
    course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

    # Prerequisite selection
    prereq_frame = ttk.LabelFrame(main_frame, text="Select Prerequisite", padding="10")
    prereq_frame.pack(fill=tk.X, pady=5)

    ttk.Label(prereq_frame, text="Prerequisite:").grid(row=0, column=0, sticky=tk.W, pady=5)
    prereq_var = tk.StringVar()
    prereq_combo = ttk.Combobox(prereq_frame, textvariable=prereq_var, state='readonly', width=40)
    prereq_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

    # Required checkbox
    required_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(prereq_frame, text="Required (vs. Recommended)",
                   variable=required_var).grid(row=1, column=1, sticky=tk.W, pady=5)

    # Load courses
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, course_code, course_name FROM courses "
            "WHERE course_code IS NOT NULL "
            "AND course_name IS NOT NULL "
            "AND LOWER(COALESCE(status, 'active')) = 'active' "
            "ORDER BY course_code"
        )
        courses = cursor.fetchall()
        conn.close()

        course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
        course_combo['values'] = course_list
        prereq_combo['values'] = course_list

    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
        dialog.destroy()
        return

    def save_prerequisite():
        if not course_var.get() or not prereq_var.get():
            messagebox.showwarning("Incomplete", "Please select both course and prerequisite")
            return

        try:
            # Extract IDs from selection
            course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
            prereq_id = int(prereq_var.get().split("ID: ")[1].rstrip(")"))

            if course_id == prereq_id:
                messagebox.showerror(_("common.error"), "A course cannot be its own prerequisite")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()

                # Check for circular dependency
                if self.check_circular_prerequisite_db(cursor, course_id, prereq_id):
                    messagebox.showerror("Circular Dependency",
                                       "Adding this prerequisite would create a circular dependency!")
            finally:
                conn.close()
                return

            # Check if already exists
            cursor.execute("""
                SELECT id FROM course_prerequisites
                WHERE course_id = ? AND prerequisite_course_id = ?
            """, (course_id, prereq_id))

            if cursor.fetchone():
                messagebox.showwarning("Duplicate", "This prerequisite already exists")
                conn.close()
                return

            # Add prerequisite
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
                VALUES (?, ?, ?, ?)
            """, (course_id, prereq_id, 1 if required_var.get() else 0, timestamp))

            conn.commit()
            conn.close()

            messagebox.showinfo(_("common.success"), "Prerequisite added successfully!")
            self.update_status("Prerequisite added successfully")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to add prerequisite: {e}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    ttk.Button(button_frame, text="Save", command=save_prerequisite).pack(side=tk.RIGHT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)


def view_prerequisites_gui(self):
    """
    View prerequisites for a selected course or all courses.
    Opens a dialog with prerequisite information.
    """
    dialog = tk.Toplevel(self.root)
    dialog.title("View Course Prerequisites")
    dialog.geometry("700x500")
    dialog.transient(self.root)

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Course Prerequisites",
             font=('Arial', 12, 'bold')).pack(pady=(0, 10))

    # Course selection
    select_frame = ttk.Frame(main_frame)
    select_frame.pack(fill=tk.X, pady=5)

    ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
    course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    # Add "All Courses" option
    all_option = "-- All Courses --"

    # Text display
    text_frame = ttk.Frame(main_frame)
    text_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    scrollbar = ttk.Scrollbar(text_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                         font=('Courier', 10))
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=text_widget.yview)

    def load_courses():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, course_code, course_name FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()
            conn.close()

            course_list = [all_option] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
            course_combo['values'] = course_list
            course_combo.current(0)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def show_prerequisites(*args):
        text_widget.delete('1.0', tk.END)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            selected = course_var.get()

            if selected == all_option or not selected:
                # Show all prerequisites
                cursor.execute("""
                    SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                    FROM course_prerequisites cp
                    JOIN courses c1 ON cp.course_id = c1.id
                    JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                    ORDER BY c1.course_code, c2.course_code
                """)

                prereqs = cursor.fetchall()
                if prereqs:
                    text_widget.insert(tk.END, "ALL COURSE PREREQUISITES\n")
                    text_widget.insert(tk.END, "=" * 70 + "\n\n")

                    current_course = None
                    for course_code, course_name, prereq_code, prereq_name, is_req in prereqs:
                        if current_course != course_code:
                            current_course = course_code
                            text_widget.insert(tk.END, f"\n{course_code} - {course_name}:\n")
                            text_widget.insert(tk.END, "-" * 70 + "\n")

                        req_status = "Required" if is_req else "Recommended"
                        text_widget.insert(tk.END, f"  → {prereq_code} - {prereq_name} ({req_status})\n")
                else:
                    text_widget.insert(tk.END, "No prerequisites found in the system.\n")
            else:
                # Show prerequisites for specific course
                course_id = int(selected.split("ID: ")[1].rstrip(")"))

                cursor.execute("""
                    SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                    FROM course_prerequisites cp
                    JOIN courses c1 ON cp.course_id = c1.id
                    JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                    WHERE cp.course_id = ?
                    ORDER BY c2.course_code
                """, (course_id,))

                prereqs = cursor.fetchall()
                if prereqs:
                    course_code, course_name = prereqs[0][0], prereqs[0][1]
                    text_widget.insert(tk.END, f"PREREQUISITES FOR: {course_code} - {course_name}\n")
                    text_widget.insert(tk.END, "=" * 70 + "\n\n")

                    for _, _, prereq_code, prereq_name, is_req in prereqs:
                        req_status = "Required" if is_req else "Recommended"
                        text_widget.insert(tk.END, f"{prereq_code} - {prereq_name} ({req_status})\n")
                else:
                    text_widget.insert(tk.END, "No prerequisites found for this course.\n")

            conn.close()

        except Exception as e:
            text_widget.insert(tk.END, f"Error loading prerequisites: {e}\n")

    course_combo.bind('<<ComboboxSelected>>', show_prerequisites)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    ttk.Button(button_frame, text="Refresh", command=show_prerequisites).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # Initial load
    load_courses()
    show_prerequisites()


def remove_prerequisite_gui(self):
    """
    Remove a prerequisite from a course.
    Opens a dialog to select and remove prerequisites.
    """
    dialog = tk.Toplevel(self.root)
    dialog.title("Remove Course Prerequisite")
    dialog.geometry("600x400")
    dialog.transient(self.root)

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Remove Course Prerequisite",
             font=('Arial', 12, 'bold')).pack(pady=(0, 10))

    # Course selection
    select_frame = ttk.Frame(main_frame)
    select_frame.pack(fill=tk.X, pady=5)

    ttk.Label(select_frame, text="Select Course:").pack(side=tk.LEFT, padx=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=40)
    course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    # Prerequisites list
    list_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding="10")
    list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    prereq_listbox = tk.Listbox(list_frame, height=10)
    prereq_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=prereq_listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    prereq_listbox.config(yscrollcommand=scrollbar.set)

    # Store prerequisite IDs
    prereq_data = {}

    def load_courses():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, course_code, course_name FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()
            conn.close()

            course_list = [f"{code} - {name} (ID: {id})" for id, code, name in courses]
            course_combo['values'] = course_list

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def load_prerequisites(*args):
        prereq_listbox.delete(0, tk.END)
        prereq_data.clear()

        if not course_var.get():
            return

        try:
            course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cp.id, c.course_code, c.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c ON cp.prerequisite_course_id = c.id
                WHERE cp.course_id = ?
                ORDER BY c.course_code
            """, (course_id,))

            prereqs = cursor.fetchall()
            conn.close()

            for prereq_id, code, name, is_req in prereqs:
                req_status = "Required" if is_req else "Recommended"
                display_text = f"{code} - {name} ({req_status})"
                prereq_listbox.insert(tk.END, display_text)
                prereq_data[display_text] = prereq_id

            if not prereqs:
                prereq_listbox.insert(tk.END, "No prerequisites found")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load prerequisites: {e}")

    def remove_selected():
        selection = prereq_listbox.curselection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a prerequisite to remove")
            return

        selected_text = prereq_listbox.get(selection[0])
        if selected_text == "No prerequisites found":
            return

        prereq_id = prereq_data.get(selected_text)
        if not prereq_id:
            return

        if messagebox.askyesno(_("common.confirm"), f"Remove prerequisite:\n{selected_text}?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq_id,))
                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Prerequisite removed successfully!")
                self.update_status("Prerequisite removed")
                load_prerequisites()

            except sqlite3.Error as e:
                messagebox.showerror(_("common.error"), f"Failed to remove prerequisite: {e}")

    course_combo.bind('<<ComboboxSelected>>', load_prerequisites)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    ttk.Button(button_frame, text="Remove Selected", command=remove_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # Initial load
    load_courses()


def check_circular_prerequisite_db(self, cursor, course_id, prereq_id):
    """
    Check if adding a prerequisite would create a circular dependency.
    Uses recursive helper function to traverse prerequisite tree.
    """
    visited = set()

    def has_prerequisite(cid, target_id):
        """Nested helper function to recursively check prerequisites"""
        if cid in visited:
            return False
        visited.add(cid)

        cursor.execute("""
            SELECT prerequisite_course_id FROM course_prerequisites
            WHERE course_id = ?
        """, (cid,))
        prereqs = cursor.fetchall()

        for (pid,) in prereqs:
            if pid == target_id:
                return True
            if has_prerequisite(pid, target_id):
                return True
        return False

    return has_prerequisite(prereq_id, course_id)


class PrerequisitesWindow:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth

        self.window = tk.Toplevel(parent)
        self.window.title("Manage Prerequisites")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        # Prerequisites management interface
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        ttk.Button(controls_frame, text="Add Prerequisite", command=self.add_prerequisite).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Remove Prerequisite", command=self.remove_prerequisite).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Refresh", command=self.load_data).pack(side=tk.LEFT, padx=5)

        # Prerequisites display
        self.prereq_text = ScrolledText(main_frame, wrap=tk.WORD, height=30)
        self.prereq_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def load_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Check if prerequisites table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='course_prerequisites'")
            if not cursor.fetchone():
                prereq_text = "PREREQUISITES MANAGEMENT\n"
                prereq_text += "=" * 50 + "\n\n"
                prereq_text += "No prerequisites table found. Create some prerequisites first.\n"
            else:
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                ORDER BY c1.course_code, c2.course_code
                """)

                prereqs = cursor.fetchall()

                prereq_text = "PREREQUISITES MANAGEMENT\n"
                prereq_text += "=" * 50 + "\n\n"

                if prereqs:
                    current_course = None
                    for prereq in prereqs:
                        if current_course != prereq[0]:
                            current_course = prereq[0]
                            prereq_text += f"\n{prereq[0]} - {prereq[1]}:\n"

                        req_type = "Required" if prereq[4] else "Recommended"
                        prereq_text += f"  → {prereq[2]} - {prereq[3]} ({req_type})\n"
                else:
                    prereq_text += "No prerequisites found in the system.\n"

            conn.close()

            self.prereq_text.delete(1.0, tk.END)
            self.prereq_text.insert(1.0, prereq_text)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load prerequisites: {e}")

    def add_prerequisite(self):
        dialog = AddPrerequisiteDialog(self.window, self.auth)
        if dialog.result:
            self.load_data()

    def remove_prerequisite(self):
        """Show remove prerequisite dialog"""
        dialog = RemovePrerequisiteDialog(self.window, self.auth)
        if dialog.result:
            self.load_data()


class AddPrerequisiteDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Prerequisite")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_courses()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Add Course Prerequisite", font=("Arial", 12, "bold")).pack(pady=10)

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding=10)
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").pack(anchor=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50)
        self.course_combo.pack(fill=tk.X, pady=2)

        # Prerequisite selection
        prereq_frame = ttk.LabelFrame(main_frame, text="Select Prerequisite", padding=10)
        prereq_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prereq_frame, text="Prerequisite Course:").pack(anchor=tk.W)
        self.prereq_combo = ttk.Combobox(prereq_frame, width=50)
        self.prereq_combo.pack(fill=tk.X, pady=2)

        # Requirement type
        self.is_required = tk.BooleanVar(value=True)
        ttk.Checkbutton(prereq_frame, text="Required (uncheck for recommended)",
                       variable=self.is_required).pack(anchor=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Prerequisite", command=self.add_prerequisite).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, course_code, course_name FROM courses "
                "WHERE course_code IS NOT NULL "
                "AND course_name IS NOT NULL "
                "AND LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY course_code"
            )
            courses = cursor.fetchall()

            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            self.prereq_combo['values'] = course_options

            # Store course IDs for mapping
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def add_prerequisite(self):
        try:
            course_text = self.course_combo.get()
            prereq_text = self.prereq_combo.get()

            if not course_text or not prereq_text:
                messagebox.showwarning(_("common.selection_required"), "Please select both course and prerequisite.")
                return

            if course_text == prereq_text:
                messagebox.showerror("Invalid Selection", "A course cannot be a prerequisite for itself.")
                return

            course_id = self.course_id_map.get(course_text)
            prereq_id = self.course_id_map.get(prereq_text)

            if not course_id or not prereq_id:
                messagebox.showerror(_("common.error"), "Invalid course selection.")
                return

            # Create prerequisites table if it doesn't exist
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_prerequisites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    prerequisite_course_id INTEGER NOT NULL,
                    is_required BOOLEAN DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    FOREIGN KEY (prerequisite_course_id) REFERENCES courses (id),
                    UNIQUE(course_id, prerequisite_course_id)
                )
                ''')

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO course_prerequisites (course_id, prerequisite_course_id, is_required, created_at)
                VALUES (?, ?, ?, ?)
                ''', (course_id, prereq_id, self.is_required.get(), timestamp))

                conn.commit()
            finally:
                conn.close()

            self.result = True
            self.dialog.destroy()

        except sqlite3.IntegrityError:
            messagebox.showerror(_("common.duplicate_error"), "This prerequisite already exists.")
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to add prerequisite: {e}")




class RemovePrerequisiteDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Remove Prerequisite")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_prerequisites()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text="Remove Course Prerequisite", font=("Arial", 12, "bold")).pack(pady=10)

        # Prerequisites list
        prereq_frame = ttk.LabelFrame(main_frame, text="Current Prerequisites", padding=10)
        prereq_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create treeview for prerequisites
        columns = ("Course", "Prerequisite", "Type")
        self.prereq_tree = ttk.Treeview(prereq_frame, columns=columns, show="headings", height=10)

        self.prereq_tree.heading("Course", text="Course")
        self.prereq_tree.heading("Prerequisite", text="Prerequisite Course")
        self.prereq_tree.heading("Type", text="Type")

        self.prereq_tree.column("Course", width=150)
        self.prereq_tree.column("Prerequisite", width=150)
        self.prereq_tree.column("Type", width=100)

        # Scrollbar
        scrollbar = ttk.Scrollbar(prereq_frame, orient=tk.VERTICAL, command=self.prereq_tree.yview)
        self.prereq_tree.configure(yscrollcommand=scrollbar.set)

        self.prereq_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Remove Selected", command=self.remove_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_prerequisites(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Get all prerequisites
            cursor.execute('''
            SELECT
                cp.id,
                c1.course_code || ' - ' || c1.course_name as course,
                c2.course_code || ' - ' || c2.course_name as prerequisite,
                CASE WHEN cp.is_required = 1 THEN 'Required' ELSE 'Recommended' END as type
            FROM course_prerequisites cp
            JOIN courses c1 ON cp.course_id = c1.id
            JOIN courses c2 ON cp.prerequisite_course_id = c2.id
            ORDER BY c1.course_code, c2.course_code
            ''')

            prerequisites = cursor.fetchall()
            conn.close()

            # Clear existing items
            for item in self.prereq_tree.get_children():
                self.prereq_tree.delete(item)

            # Add prerequisites to tree
            for prereq in prerequisites:
                self.prereq_tree.insert('', tk.END, values=(prereq[1], prereq[2], prereq[3]), tags=(prereq[0],))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load prerequisites: {e}")

    def remove_selected(self):
        selected = self.prereq_tree.selection()
        if not selected:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a prerequisite to remove.")
            return

        # Confirm removal
        if not messagebox.askyesno("Confirm Removal", "Are you sure you want to remove this prerequisite?"):
            return

        try:
            prereq_id = self.prereq_tree.item(selected[0])['tags'][0]

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute('DELETE FROM course_prerequisites WHERE id = ?', (prereq_id,))

            conn.commit()
            conn.close()

            # Remove from tree
            self.prereq_tree.delete(selected[0])

            self.result = True
            messagebox.showinfo(_("common.success"), "Prerequisite removed successfully")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to remove prerequisite: {e}")
