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
    from education_system.university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_bulk_update(self):
    """Show bulk update dialog"""
    dialog = BulkUpdateDialog(self.root, self.auth)
    if dialog.result:
        self.refresh_course_list()
        self.update_status("Bulk update completed")


def bulk_update_courses_wrapper(self):
    """Bulk update multiple courses. Calls existing show_bulk_update()."""
    self.show_bulk_update()


class BulkUpdateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Update Courses")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Bulk Update Courses", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Select Courses to Update", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        self.selection_method = tk.StringVar(value="department")
        
        ttk.Radiobutton(criteria_frame, text="By Department", variable=self.selection_method, 
                       value="department").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Level", variable=self.selection_method, 
                       value="level").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Status", variable=self.selection_method, 
                       value="status").pack(anchor=tk.W)
        
        ttk.Label(criteria_frame, text="Value:").pack(anchor=tk.W, pady=(10,0))
        self.criteria_value_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.criteria_value_var, width=30).pack(anchor=tk.W)
        
        # Update field
        update_frame = ttk.LabelFrame(main_frame, text="Field to Update", padding=10)
        update_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(update_frame, text="Field:").pack(anchor=tk.W)
        self.update_field = tk.StringVar(value="status")
        field_combo = ttk.Combobox(update_frame, textvariable=self.update_field,
                                  values=["status", "max_enrollment", "course_fee", "course_type"])
        field_combo.pack(anchor=tk.W, pady=2)
        
        ttk.Label(update_frame, text="New Value:").pack(anchor=tk.W, pady=(10,0))
        self.new_value_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.new_value_var, width=30).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Preview", command=self.preview_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.perform_update).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    _ALLOWED_SELECTION_COLUMNS = frozenset({'department', 'level', 'status'})
    _ALLOWED_UPDATE_COLUMNS = frozenset({'status', 'max_enrollment', 'course_fee', 'course_type'})

    def preview_update(self):
        selection_method = self.selection_method.get()
        criteria_value = self.criteria_value_var.get().strip()

        if not criteria_value:
            messagebox.showwarning(_("common.input_required"), "Please enter a value for the selection criteria.")
            return

        if selection_method not in self._ALLOWED_SELECTION_COLUMNS:
            messagebox.showerror("Error", f"Invalid selection method: {selection_method}")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            query = f"SELECT course_code, course_name FROM courses WHERE {selection_method} = ?"
            cursor.execute(query, (criteria_value,))
            courses = cursor.fetchall()
            conn.close()

            if courses:
                preview_text = f"Courses that will be updated ({len(courses)}):\n\n"
                for code, name in courses:
                    preview_text += f"• {code} - {name}\n"

                messagebox.showinfo("Update Preview", preview_text)
            else:
                messagebox.showinfo("No Matches", "No courses match the specified criteria.")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Preview failed: {e}")

    def perform_update(self):
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()
            update_field = self.update_field.get()
            new_value = self.new_value_var.get().strip()

            if not criteria_value or not new_value:
                messagebox.showwarning(_("common.input_required"), "Please fill in all fields.")
                return

            if selection_method not in self._ALLOWED_SELECTION_COLUMNS:
                messagebox.showerror("Error", f"Invalid selection method: {selection_method}")
                return
            if update_field not in self._ALLOWED_UPDATE_COLUMNS:
                messagebox.showerror("Error", f"Invalid update field: {update_field}")
                return

            if not messagebox.askyesno("Confirm Update",
                f"Update all courses where {selection_method} = '{criteria_value}'?\n\nField: {update_field}\nNew Value: {new_value}"):
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            update_query = f"UPDATE courses SET {update_field} = ? WHERE {selection_method} = ?"
            cursor.execute(update_query, (new_value, criteria_value))

            updated_count = cursor.rowcount
            conn.commit()
            conn.close()

            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} courses.")
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Update failed: {e}")


class BulkUpdateDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Bulk Update Courses")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Bulk Update Courses", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Select Courses to Update", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        self.selection_method = tk.StringVar(value="department")
        
        ttk.Radiobutton(criteria_frame, text="By Department", variable=self.selection_method, 
                       value="department").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Level", variable=self.selection_method, 
                       value="level").pack(anchor=tk.W)
        ttk.Radiobutton(criteria_frame, text="By Status", variable=self.selection_method, 
                       value="status").pack(anchor=tk.W)
        
        ttk.Label(criteria_frame, text="Value:").pack(anchor=tk.W, pady=(10,0))
        self.criteria_value_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.criteria_value_var, width=30).pack(anchor=tk.W)
        
        # Update field
        update_frame = ttk.LabelFrame(main_frame, text="Field to Update", padding=10)
        update_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(update_frame, text="Field:").pack(anchor=tk.W)
        self.update_field = tk.StringVar(value="status")
        field_combo = ttk.Combobox(update_frame, textvariable=self.update_field,
                                  values=["status", "max_enrollment", "course_fee", "course_type"])
        field_combo.pack(anchor=tk.W, pady=2)
        
        ttk.Label(update_frame, text="New Value:").pack(anchor=tk.W, pady=(10,0))
        self.new_value_var = tk.StringVar()
        ttk.Entry(update_frame, textvariable=self.new_value_var, width=30).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Preview", command=self.preview_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.perform_update).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    _ALLOWED_SELECTION_COLUMNS = frozenset({'department', 'level', 'status'})
    _ALLOWED_UPDATE_COLUMNS = frozenset({'status', 'max_enrollment', 'course_fee', 'course_type'})

    def preview_update(self):
        # Show preview of courses that will be affected
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()

            if not criteria_value:
                messagebox.showwarning(_("common.input_required"), "Please enter a value for the selection criteria.")
                return

            if selection_method not in self._ALLOWED_SELECTION_COLUMNS:
                messagebox.showerror("Error", f"Invalid selection method: {selection_method}")
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            query = f"SELECT course_code, course_name FROM courses WHERE {selection_method} = ?"
            cursor.execute(query, (criteria_value,))
            courses = cursor.fetchall()
            conn.close()

            if courses:
                preview_text = f"Courses that will be updated ({len(courses)}):\n\n"
                for code, name in courses:
                    preview_text += f"• {code} - {name}\n"

                messagebox.showinfo("Update Preview", preview_text)
            else:
                messagebox.showinfo("No Matches", "No courses match the specified criteria.")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Preview failed: {e}")

    def perform_update(self):
        try:
            selection_method = self.selection_method.get()
            criteria_value = self.criteria_value_var.get().strip()
            update_field = self.update_field.get()
            new_value = self.new_value_var.get().strip()

            if not criteria_value or not new_value:
                messagebox.showwarning(_("common.input_required"), "Please fill in all fields.")
                return

            if selection_method not in self._ALLOWED_SELECTION_COLUMNS:
                messagebox.showerror("Error", f"Invalid selection method: {selection_method}")
                return
            if update_field not in self._ALLOWED_UPDATE_COLUMNS:
                messagebox.showerror("Error", f"Invalid update field: {update_field}")
                return

            # Confirm update
            if not messagebox.askyesno("Confirm Update", f"Update all courses where {selection_method} = '{criteria_value}'?\n\nField: {update_field}\nNew Value: {new_value}"):
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            update_query = f"UPDATE courses SET {update_field} = ? WHERE {selection_method} = ?"
            cursor.execute(update_query, (new_value, criteria_value))

            # After performing the update, resynchronise any legacy alias
            # columns for all courses.  This ensures that if the caller
            # updated a canonical field (course_code, course_name or
            # credit_hours) the corresponding alias columns (code, name,
            # credits) remain in sync.  Performing the update for all
            # rows is inexpensive given the expected table size.
            try:
                cursor.execute(
                    "UPDATE courses SET code = course_code, name = course_name, credits = credit_hours, date_added = COALESCE(date_added, created_at)"
                )
            except Exception:
                pass
            
            updated_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Update Complete", f"Successfully updated {updated_count} courses.")
            self.result = True
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Update failed: {e}")
