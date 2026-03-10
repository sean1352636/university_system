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


def show_search_dialog(self):
    """Show advanced search dialog"""
    dialog = AdvancedSearchDialog(self.root)
    if dialog.result:
        # Apply search results to main course list
        self.apply_search_results(dialog.result)


def show_advanced_search(self):
    """Show advanced search dialog"""
    AdvancedCourseSearchDialog(self.root, self.auth)


def apply_search_results(self, search_criteria):
    """Apply search results to course list"""
    try:
        # Clear existing items
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)
        
        # Build query from search criteria
        query = """
        SELECT id, course_code, course_name, department, level, credit_hours,
               COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
               status
        FROM courses WHERE course_code IS NOT NULL
        """
        params = []
        
        for field, value in search_criteria.items():
            if field == "available_only" and value:
                query += " AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)"
            elif value and (isinstance(value, str) and value.strip()):
                if field == "keyword":
                    query += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
                    search_param = f"%{value}%"
                    params.extend([search_param, search_param, search_param])
                elif field == "min_credits":
                    query += " AND credit_hours >= ?"
                    params.append(float(value))
                elif field == "max_credits":
                    query += " AND credit_hours <= ?"
                    params.append(float(value))
                elif field not in ["available_only"]:
                    query += f" AND {field} LIKE ?"
                    params.append(f"%{value}%")
        
        query += " ORDER BY course_code"
        
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute(query, params)
        courses = cursor.fetchall()
        conn.close()
        
        # Populate results
        for course in courses:
            self.course_tree.insert("", tk.END, values=course)
        
        self.update_status(f"Search completed: {len(courses)} courses found")
        
    except sqlite3.Error as e:
        messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))


def search_courses_wrapper(self):
    """Search courses with filters. Calls existing show_search_dialog()."""
    self.show_search_dialog()


class AdvancedCourseSearchDialog:
    """Enhanced version of the existing AdvancedSearchDialog with more features"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Course Search")
        self.dialog.geometry("800x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Advanced Course Search", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Create notebook for different search types
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Basic Search Tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Search")
        self.create_basic_search(basic_frame)
        
        # Advanced Filters Tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced Filters")
        self.create_advanced_filters(advanced_frame)
        
        # Results Tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="Search Results")
        self.create_results_display(results_frame)
        
        # Search buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Results", command=self.export_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def create_basic_search(self, parent):
        # Keyword search
        keyword_frame = ttk.LabelFrame(parent, text="Keyword Search", padding=10)
        keyword_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(keyword_frame, text="Search in:").grid(row=0, column=0, sticky=tk.W)
        self.search_in_var = tk.StringVar(value="all")
        
        search_options = [
            ("All fields", "all"),
            ("Course name only", "name"),
            ("Description only", "description"),
            ("Course code only", "code")
        ]
        
        for i, (text, value) in enumerate(search_options):
            ttk.Radiobutton(keyword_frame, text=text, variable=self.search_in_var, 
                           value=value).grid(row=i+1, column=0, sticky=tk.W)
        
        ttk.Label(keyword_frame, text="Keywords:").grid(row=0, column=1, sticky=tk.W, padx=(20,0))
        self.keyword_var = tk.StringVar()
        ttk.Entry(keyword_frame, textvariable=self.keyword_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=(20,0))
        
        # Quick filters
        quick_frame = ttk.LabelFrame(parent, text="Quick Filters", padding=10)
        quick_frame.pack(fill=tk.X, pady=5)
        
        self.only_available = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Only courses with available spots", 
                       variable=self.only_available).pack(anchor=tk.W)
        
        self.only_active = tk.BooleanVar(value=True)
        ttk.Checkbutton(quick_frame, text="Only active courses", 
                       variable=self.only_active).pack(anchor=tk.W)
        
        self.online_only = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Only online available courses", 
                       variable=self.online_only).pack(anchor=tk.W)
        
        self.no_lab = tk.BooleanVar()
        ttk.Checkbutton(quick_frame, text="Exclude lab courses", 
                       variable=self.no_lab).pack(anchor=tk.W)
    
    def create_advanced_filters(self, parent):
        # Academic filters
        academic_frame = ttk.LabelFrame(parent, text="Academic Criteria", padding=10)
        academic_frame.pack(fill=tk.X, pady=5)
        
        # Department multi-select
        ttk.Label(academic_frame, text="Departments:").grid(row=0, column=0, sticky=tk.NW)
        dept_frame = ttk.Frame(academic_frame)
        dept_frame.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        self.dept_vars = {}
        self.load_departments(dept_frame)
        
        # Level selection
        ttk.Label(academic_frame, text="Levels:").grid(row=1, column=0, sticky=tk.NW, pady=(10,0))
        level_frame = ttk.Frame(academic_frame)
        level_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(10,0))
        
        self.level_vars = {}
        levels = ["Undergraduate", "Postgraduate", "PhD", "Certificate", "Diploma"]
        for i, level in enumerate(levels):
            var = tk.BooleanVar()
            self.level_vars[level] = var
            ttk.Checkbutton(level_frame, text=level, variable=var).grid(row=i//2, column=i%2, sticky=tk.W)
        
        # Credit hours range
        credits_frame = ttk.LabelFrame(parent, text="Credit Hours", padding=10)
        credits_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(credits_frame, text="Min:").grid(row=0, column=0, sticky=tk.W)
        self.min_credits_var = tk.StringVar()
        ttk.Entry(credits_frame, textvariable=self.min_credits_var, width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(credits_frame, text="Max:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.max_credits_var = tk.StringVar()
        ttk.Entry(credits_frame, textvariable=self.max_credits_var, width=10).grid(row=0, column=3, padx=5)
        
        # Enrollment filters
        enrollment_frame = ttk.LabelFrame(parent, text="Enrollment Criteria", padding=10)
        enrollment_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(enrollment_frame, text="Fill rate:").grid(row=0, column=0, sticky=tk.W)
        self.fill_rate_var = tk.StringVar(value="any")
        
        fill_options = [
            ("Any", "any"),
            ("Under 25%", "low"),
            ("25-75%", "medium"),
            ("Over 75%", "high"),
            ("Full", "full")
        ]
        
        for i, (text, value) in enumerate(fill_options):
            ttk.Radiobutton(enrollment_frame, text=text, variable=self.fill_rate_var, 
                           value=value).grid(row=i//3, column=(i%3)+1, sticky=tk.W)
    
    def create_results_display(self, parent):
        # Results treeview
        columns = ("Code", "Name", "Department", "Level", "Credits", "Enrollment", "Fill Rate", "Status")
        self.results_tree = ttk.Treeview(parent, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
            if col == "Code":
                self.results_tree.column(col, width=80)
            elif col == "Name":
                self.results_tree.column(col, width=200)
            elif col in ["Department", "Level"]:
                self.results_tree.column(col, width=120)
            elif col == "Credits":
                self.results_tree.column(col, width=70)
            elif col == "Enrollment":
                self.results_tree.column(col, width=100)
            elif col == "Fill Rate":
                self.results_tree.column(col, width=80)
            elif col == "Status":
                self.results_tree.column(col, width=80)
        
        scrollbar_v = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar_h = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_v.grid(row=0, column=1, sticky="ns")
        scrollbar_h.grid(row=1, column=0, sticky="ew")
        
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Results summary
        self.results_summary = ttk.Label(parent, text="No search performed yet")
        self.results_summary.grid(row=2, column=0, columnspan=2, pady=5)
        
        # Double-click for details
        self.results_tree.bind("<Double-1>", self.show_course_details)
    
    def load_departments(self, parent):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT department FROM courses WHERE course_code IS NOT NULL AND department IS NOT NULL ORDER BY department")
            departments = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            for i, dept in enumerate(departments):
                var = tk.BooleanVar()
                self.dept_vars[dept] = var
                ttk.Checkbutton(parent, text=dept, variable=var).grid(row=i//3, column=i%3, sticky=tk.W)
        except sqlite3.Error:
            pass
    
    def perform_search(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Build search query
            conditions = []
            params = []
            
            # Keyword search
            keyword = self.keyword_var.get().strip()
            if keyword:
                search_in = self.search_in_var.get()
                if search_in == "all":
                    conditions.append("(course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)")
                    params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
                elif search_in == "name":
                    conditions.append("course_name LIKE ?")
                    params.append(f"%{keyword}%")
                elif search_in == "description":
                    conditions.append("description LIKE ?")
                    params.append(f"%{keyword}%")
                elif search_in == "code":
                    conditions.append("course_code LIKE ?")
                    params.append(f"%{keyword}%")
            
            # Quick filters
            if self.only_active.get():
                conditions.append("LOWER(COALESCE(status, 'active')) = 'active'")
            
            if self.only_available.get():
                conditions.append("COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)")
            
            if self.online_only.get():
                conditions.append("online_available = 1")
            
            if self.no_lab.get():
                conditions.append("lab_required = 0")
            
            # Department filter
            selected_depts = [dept for dept, var in self.dept_vars.items() if var.get()]
            if selected_depts:
                placeholders = ','.join(['?' for _ in selected_depts])
                conditions.append(f"department IN ({placeholders})")
                params.extend(selected_depts)
            
            # Level filter
            selected_levels = [level for level, var in self.level_vars.items() if var.get()]
            if selected_levels:
                placeholders = ','.join(['?' for _ in selected_levels])
                conditions.append(f"level IN ({placeholders})")
                params.extend(selected_levels)
            
            # Credit hours filter
            if self.min_credits_var.get():
                try:
                    min_credits = float(self.min_credits_var.get())
                    conditions.append("credit_hours >= ?")
                    params.append(min_credits)
                except ValueError:
                    pass
            
            if self.max_credits_var.get():
                try:
                    max_credits = float(self.max_credits_var.get())
                    conditions.append("credit_hours <= ?")
                    params.append(max_credits)
                except ValueError:
                    pass
            
            # Fill rate filter
            fill_rate = self.fill_rate_var.get()
            if fill_rate != "any":
                if fill_rate == "low":
                    conditions.append("COALESCE(max_enrollment, 0) > 0 AND CAST(COALESCE(current_enrollment, 0) AS FLOAT) / max_enrollment < 0.25")
                elif fill_rate == "medium":
                    conditions.append("COALESCE(max_enrollment, 0) > 0 AND CAST(COALESCE(current_enrollment, 0) AS FLOAT) / max_enrollment BETWEEN 0.25 AND 0.75")
                elif fill_rate == "high":
                    conditions.append("COALESCE(max_enrollment, 0) > 0 AND CAST(COALESCE(current_enrollment, 0) AS FLOAT) / max_enrollment > 0.75")
                elif fill_rate == "full":
                    conditions.append("COALESCE(current_enrollment, 0) >= COALESCE(max_enrollment, 0)")
            
            # Build final query - exclude module records (course_code IS NULL)
            base_query = """
            SELECT course_code, course_name, department, level, credit_hours,
                   current_enrollment, max_enrollment, status
            FROM courses
            """

            conditions.insert(0, "course_name IS NOT NULL")
            conditions.insert(0, "course_code IS NOT NULL")
            query = base_query + " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY course_code"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Populate results
            for course in results:
                code, name, dept, level, credits, current, max_enroll, status = course
                enrollment_str = f"{current or 0}/{max_enroll or 0}"
                fill_rate = f"{(current or 0)/(max_enroll or 1)*100:.1f}%" if max_enroll else "N/A"
                
                self.results_tree.insert("", tk.END, values=(
                    code, name, dept or "N/A", level or "N/A", credits or "N/A",
                    enrollment_str, fill_rate, status
                ))
            
            # Update summary
            self.results_summary.config(text=f"Found {len(results)} courses matching search criteria")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))
    
    def clear_search(self):
        # Clear all search fields
        self.keyword_var.set("")
        self.search_in_var.set("all")
        self.only_available.set(False)
        self.only_active.set(True)
        self.online_only.set(False)
        self.no_lab.set(False)
        self.min_credits_var.set("")
        self.max_credits_var.set("")
        self.fill_rate_var.set("any")
        
        # Clear department and level selections
        for var in self.dept_vars.values():
            var.set(False)
        for var in self.level_vars.values():
            var.set(False)
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        self.results_summary.config(text="Search cleared")
    
    def export_results(self):
        if not self.results_tree.get_children():
            messagebox.showwarning("No Results", "No search results to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Export Search Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write headers
                    headers = ["Code", "Name", "Department", "Level", "Credits", "Enrollment", "Fill Rate", "Status"]
                    writer.writerow(headers)
                    
                    # Write data
                    for item in self.results_tree.get_children():
                        values = self.results_tree.item(item)['values']
                        writer.writerow(values)
                
                messagebox.showinfo(_("common.export_complete"), f"Results exported to {filename}")
                
            except Exception as e:
                messagebox.showerror(_("common.export_error"), f"Failed to export results: {e}")
    
    def show_course_details(self, event):
        selection = self.results_tree.selection()
        if selection:
            values = self.results_tree.item(selection[0])['values']
            course_code = values[0]
            
            # Find course ID and show details
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM courses WHERE course_code = ?", (course_code,))
                result = cursor.fetchone()
                if result:
                    # Use existing course details method from main GUI
                    self.parent.view_course_details(cursor, result[0])
                conn.close()
            except sqlite3.Error:
                pass


class AdvancedSearchDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Advanced Search")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Advanced Course Search", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Search criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        criteria_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(criteria_frame, text="Keyword:").grid(row=0, column=0, sticky=tk.W)
        self.keyword_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.keyword_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Department:").grid(row=1, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.department_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Level:").grid(row=2, column=0, sticky=tk.W)
        self.level_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.level_var, width=30).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Course Type:").grid(row=3, column=0, sticky=tk.W)
        self.type_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.type_var, width=30).grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Min Credits:").grid(row=4, column=0, sticky=tk.W)
        self.min_credits_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.min_credits_var, width=15).grid(row=4, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(criteria_frame, text="Max Credits:").grid(row=5, column=0, sticky=tk.W)
        self.max_credits_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.max_credits_var, width=15).grid(row=5, column=1, sticky=tk.W, padx=5)
        
        # Status filter
        self.show_available_only = tk.BooleanVar()
        ttk.Checkbutton(criteria_frame, text="Show only courses with available spots", 
                       variable=self.show_available_only).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_fields).pack(side=tk.LEFT, padx=5)
    
    def clear_fields(self):
        for var in [self.keyword_var, self.department_var, self.level_var, self.type_var, 
                   self.min_credits_var, self.max_credits_var]:
            var.set("")
        self.show_available_only.set(False)
    
    def perform_search(self):
        self.result = {
            "keyword": self.keyword_var.get(),
            "department": self.department_var.get(),
            "level": self.level_var.get(),
            "course_type": self.type_var.get(),
            "min_credits": self.min_credits_var.get(),
            "max_credits": self.max_credits_var.get(),
            "available_only": self.show_available_only.get()
        }
        self.dialog.destroy()
