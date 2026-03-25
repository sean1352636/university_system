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


def show_manage_status(self):
    """Show manage course status dialog"""
    dialog = ManageCourseStatusDialog(self.root, self.auth)
    if dialog.result:
        self.refresh_course_list()
        self.update_status(_("course_management.status.course_status_updated"))


def show_course_history(self):
    """Show course history dialog"""
    CourseHistoryDialog(self.root, self.auth)


def manage_course_status_gui(self):
    """
    Manage course status (Active, Inactive, Archived, Cancelled).
    Opens a dialog to change course status.
    """
    dialog = tk.Toplevel(self.root)
    dialog.title("Manage Course Status")
    dialog.geometry("600x400")
    dialog.transient(self.root)

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Manage Course Status",
             font=('Arial', 12, 'bold')).pack(pady=(0, 10))

    # Course selection
    select_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
    select_frame.pack(fill=tk.X, pady=5)

    ttk.Label(select_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(select_frame, textvariable=course_var, state='readonly', width=45)
    course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

    # Current status display
    current_status_var = tk.StringVar(value="No course selected")
    ttk.Label(select_frame, text="Current Status:").grid(row=1, column=0, sticky=tk.W, pady=5)
    ttk.Label(select_frame, textvariable=current_status_var,
             font=('Arial', 10, 'bold')).grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

    # New status selection
    status_frame = ttk.LabelFrame(main_frame, text="Select New Status", padding="10")
    status_frame.pack(fill=tk.X, pady=5)

    ttk.Label(status_frame, text="New Status:").grid(row=0, column=0, sticky=tk.W, pady=5)
    status_var = tk.StringVar()
    status_combo = ttk.Combobox(status_frame, textvariable=status_var,
                               values=["Active", "Inactive", "Archived", "Cancelled"],
                               state='readonly', width=25)
    status_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

    def load_courses():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, course_code, course_name, status
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                ORDER BY course_code
            """)
            courses = cursor.fetchall()
            conn.close()

            course_list = [f"{code} - {name} (ID: {id})" for id, code, name, status in courses]
            course_combo['values'] = course_list

            # Store course data for status display
            course_combo.course_data = {
                f"{code} - {name} (ID: {id})": status
                for id, code, name, status in courses
            }

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
            dialog.destroy()

    def on_course_select(*args):
        selected = course_var.get()
        if selected and hasattr(course_combo, 'course_data'):
            current_status = course_combo.course_data.get(selected, "Unknown")
            current_status_var.set(current_status)
            status_var.set(current_status)

    course_combo.bind('<<ComboboxSelected>>', on_course_select)

    def update_status():
        if not course_var.get():
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course")
            return

        if not status_var.get():
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a new status")
            return

        current = current_status_var.get()
        new = status_var.get()

        if current == new:
            messagebox.showinfo("No Change", "Status is already set to " + new)
            return

        if messagebox.askyesno("Confirm Status Change",
                              f"Change course status from {current} to {new}?"):
            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE courses SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (new, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), course_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), f"Course status updated to {new}")
                self.update_status(f"Course status changed to {new}")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to update status: {e}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    ttk.Button(button_frame, text="Update Status", command=update_status).pack(side=tk.RIGHT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    load_courses()


def view_course_history_gui(self):
    """
    View historical changes to courses (audit trail).
    Opens a dialog with course history information.
    """
    dialog = tk.Toplevel(self.root)
    dialog.title("View Course History")
    dialog.geometry("900x600")
    dialog.transient(self.root)

    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Course Change History",
             font=('Arial', 12, 'bold')).pack(pady=(0, 10))

    # Filter frame
    filter_frame = ttk.Frame(main_frame)
    filter_frame.pack(fill=tk.X, pady=5)

    ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
    course_var = tk.StringVar()
    course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
    course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

    # Treeview for history
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    columns = ('Course', 'Field', 'Old Value', 'New Value', 'Changed By', 'Date')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=130)

    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def load_courses():
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            conn.close()

            course_list = ["-- All Courses --"] + [f"{code} - {name} (ID: {id})" for id, code, name in courses]
            course_combo['values'] = course_list
            course_combo.current(0)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def load_history(*args):
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Check if course_history table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='course_history'
            """)
            if not cursor.fetchone():
                tree.insert('', tk.END, values=(
                    "History table not found", "", "", "", "", ""
                ))
                conn.close()
                return

            selected = course_var.get()

            if selected == "-- All Courses --" or not selected:
                cursor.execute("""
                    SELECT c.course_code, h.field_name, h.old_value,
                           h.new_value, h.changed_by, h.changed_at
                    FROM course_history h
                    JOIN courses c ON h.course_id = c.id
                    ORDER BY h.changed_at DESC
                    LIMIT 100
                """)
            else:
                course_id = int(selected.split("ID: ")[1].rstrip(")"))
                cursor.execute("""
                    SELECT c.course_code, h.field_name, h.old_value,
                           h.new_value, h.changed_by, h.changed_at
                    FROM course_history h
                    JOIN courses c ON h.course_id = c.id
                    WHERE h.course_id = ?
                    ORDER BY h.changed_at DESC
                """, (course_id,))

            history = cursor.fetchall()
            conn.close()

            for entry in history:
                code, field, old_val, new_val, changed_by, changed_at = entry
                old_display = (old_val[:25] + "...") if old_val and len(old_val) > 25 else (old_val or "")
                new_display = (new_val[:25] + "...") if new_val and len(new_val) > 25 else (new_val or "")
                date_display = changed_at.split()[0] if changed_at else ""

                tree.insert('', tk.END, values=(
                    code, field, old_display, new_display,
                    changed_by or "System", date_display
                ))

            if not history:
                tree.insert('', tk.END, values=(
                    "No history records found", "", "", "", "", ""
                ))

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load history: {e}")

    course_combo.bind('<<ComboboxSelected>>', load_history)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    ttk.Button(button_frame, text="Refresh", command=load_history).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # Initial load
    load_courses()
    load_history()


class ManageCourseStatusDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Course Status")
        self.dialog.geometry("1200x800")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course list with status
        columns = ("ID", "Code", "Name", "Current Status", "Enrollment")
        self.course_tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        
        for col in columns:
            self.course_tree.heading(col, text=col)
            if col == "ID":
                self.course_tree.column(col, width=50)
            elif col == "Code":
                self.course_tree.column(col, width=80)
            elif col == "Name":
                self.course_tree.column(col, width=250)
            elif col == "Current Status":
                self.course_tree.column(col, width=120)
            elif col == "Enrollment":
                self.course_tree.column(col, width=100)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        
        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status change controls
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(controls_frame, text="New Status:").pack(side=tk.LEFT)
        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(controls_frame, textvariable=self.status_var,
                                   values=["Active", "Inactive", "Archived", "Cancelled"])
        status_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(controls_frame, text="Reason:").pack(side=tk.LEFT, padx=(20,5))
        self.reason_var = tk.StringVar()
        ttk.Entry(controls_frame, textvariable=self.reason_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Update Status", command=self.update_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_courses).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.load_courses()
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT id, COALESCE(course_code, code) as course_code,
                   COALESCE(course_name, name) as course_name, status,
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment
            FROM courses
            WHERE COALESCE(course_code, code) IS NOT NULL
            AND COALESCE(course_name, name) IS NOT NULL
            ORDER BY course_code
            """)
            courses = cursor.fetchall()
            
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)
            
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
    
    def update_status(self):
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course.")
            return
        
        new_status = self.status_var.get()
        if not new_status:
            messagebox.showwarning("No Status", "Please select a new status.")
            return
        
        course_data = self.course_tree.item(selection[0])['values']
        course_id = course_data[0]
        current_status = course_data[3]
        reason = self.reason_var.get()
        
        if new_status == current_status:
            messagebox.showinfo("Same Status", "Course already has this status.")
            return
        
        if messagebox.askyesno("Confirm Change", f"Change status from '{current_status}' to '{new_status}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute("UPDATE courses SET status = ? WHERE id = ?",
                              (new_status, course_id))
                
                # Log in history
                changed_by = self.auth.current_user.get('username', 'System') if isinstance(self.auth.current_user, dict) else str(self.auth.current_user)
                cursor.execute('''
                INSERT INTO course_history (course_id, field_name, old_value, new_value, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (course_id, 'status', current_status, new_status, changed_by, timestamp))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo(_("common.success"), "Status updated successfully!")
                self.load_courses()
                self.result = True
                
            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to update status: {e}")


class CourseHistoryDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course History Viewer")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course selection
        selection_frame = ttk.LabelFrame(main_frame, text="Course Selection", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(selection_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)
        self.course_combo.bind('<<ComboboxSelected>>', self.load_history)
        
        ttk.Button(selection_frame, text="Show All Recent Changes", 
                  command=self.show_recent_changes).pack(side=tk.RIGHT, padx=5)
        
        # History display
        history_frame = ttk.LabelFrame(main_frame, text="Change History", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Date/Time", "Field", "Old Value", "New Value", "Changed By")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings")
        
        for col in columns:
            self.history_tree.heading(col, text=col)
            if col == "Date/Time":
                self.history_tree.column(col, width=150)
            elif col in ["Old Value", "New Value"]:
                self.history_tree.column(col, width=150)
            else:
                self.history_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load course options
        self.load_course_options()
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_course_options(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
    
    def load_history(self, event=None):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            return
        
        course_id = self.course_id_map[selected_text]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT field_name, old_value, new_value, changed_by, changed_at
            FROM course_history 
            WHERE course_id = ?
            ORDER BY changed_at DESC
            """, (course_id,))
            
            history = cursor.fetchall()
            
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            for entry in history:
                self.history_tree.insert("", tk.END, values=(entry[4], entry[0], entry[1], entry[2], entry[3]))
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load history: {e}")
    
    def show_recent_changes(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT c.course_code || ' - ' || c.course_name as course, 
                   ch.field_name, ch.old_value, ch.new_value, ch.changed_by, ch.changed_at
            FROM course_history ch
            JOIN courses c ON ch.course_id = c.id
            ORDER BY ch.changed_at DESC
            LIMIT 50
            """)
            
            changes = cursor.fetchall()
            
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)
            
            for change in changes:
                self.history_tree.insert("", tk.END, values=(change[5], f"{change[0]}: {change[1]}", 
                                                           change[2], change[3], change[4]))
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load recent changes: {e}")
