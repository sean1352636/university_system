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


class CourseValidationDialog:
    """Dialog for validating course data integrity and fixing issues"""
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Data Validation")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Course Data Validation", font=("Arial", 14, "bold")).pack(pady=10)
        
        # Validation options
        options_frame = ttk.LabelFrame(main_frame, text="Validation Checks", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.check_enrollment = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check enrollment vs capacity", 
                       variable=self.check_enrollment).pack(anchor=tk.W)
        
        self.check_codes = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate course code formats", 
                       variable=self.check_codes).pack(anchor=tk.W)
        
        self.check_orphans = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Find orphaned records", 
                       variable=self.check_orphans).pack(anchor=tk.W)
        
        self.check_duplicates = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Check for duplicate course codes", 
                       variable=self.check_duplicates).pack(anchor=tk.W)
        
        self.check_missing = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Find missing required data", 
                       variable=self.check_missing).pack(anchor=tk.W)
        
        # Buttons — pack before results so they stay visible on resize
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10, side=tk.BOTTOM)

        ttk.Button(button_frame, text="Run Validation", command=self.run_validation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Fix Issues", command=self.fix_issues).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Report", command=self.export_validation_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Validation Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_text = ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        self.issues_found = []
    
    def run_validation(self):
        self.results_text.delete(1.0, tk.END)
        self.issues_found = []
        
        self.results_text.insert(tk.END, "COURSE DATA VALIDATION REPORT\n")
        self.results_text.insert(tk.END, "=" * 50 + "\n")
        self.results_text.insert(tk.END, f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            total_issues = 0
            
            # Check enrollment vs capacity
            if self.check_enrollment.get():
                self.results_text.insert(tk.END, "1. Checking enrollment vs capacity...\n")
                cursor.execute("""
                SELECT id, course_code, course_name, current_enrollment, max_enrollment
                FROM courses
                WHERE course_code IS NOT NULL
                  AND course_name IS NOT NULL
                  AND COALESCE(current_enrollment, 0) > COALESCE(max_enrollment, 0)
                """)
                
                over_enrolled = cursor.fetchall()
                if over_enrolled:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(over_enrolled)} courses over capacity:\n")
                    for course in over_enrolled:
                        self.results_text.insert(tk.END, f"      {course[1]} - {course[2]}: {course[3]}/{course[4]}\n")
                        self.issues_found.append(('over_enrolled', course))
                    total_issues += len(over_enrolled)
                else:
                    self.results_text.insert(tk.END, "   ✅ All courses within capacity\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check course code formats
            if self.check_codes.get():
                self.results_text.insert(tk.END, "2. Validating course code formats...\n")
                cursor.execute("SELECT id, course_code, course_name FROM courses")
                all_courses = cursor.fetchall()
                
                invalid_codes = []
                for course in all_courses:
                    if not course[1]:
                        continue
                    # Fixed regex pattern - expects format like "CS101" or "MATH201"
                    if not re.match(r'^[A-Z]{2,4}\d{2,3}$', course[1]):
                        invalid_codes.append(course)
                
                if invalid_codes:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(invalid_codes)} courses with invalid codes:\n")
                    for course in invalid_codes:
                        self.results_text.insert(tk.END, f"      {course[1]} - {course[2]}\n")
                        self.issues_found.append(('invalid_code', course))
                    total_issues += len(invalid_codes)
                else:
                    self.results_text.insert(tk.END, "   ✅ All course codes valid\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for orphaned records
            if self.check_orphans.get():
                self.results_text.insert(tk.END, "3. Checking for orphaned records...\n")
                
                # Check prerequisites
                cursor.execute("""
                SELECT cp.id, cp.course_id, cp.prerequisite_course_id
                FROM course_prerequisites cp
                LEFT JOIN courses c1 ON cp.course_id = c1.id
                LEFT JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE c1.id IS NULL OR c2.id IS NULL
                """)
                orphaned_prereqs = cursor.fetchall()
                
                # Check schedules
                cursor.execute("""
                SELECT cs.id, cs.course_id
                FROM course_schedule cs
                LEFT JOIN courses c ON cs.course_id = c.id
                WHERE c.id IS NULL
                """)
                orphaned_schedules = cursor.fetchall()
                
                orphan_count = len(orphaned_prereqs) + len(orphaned_schedules)
                if orphan_count > 0:
                    self.results_text.insert(tk.END, f"   ❌ Found {orphan_count} orphaned records:\n")
                    self.results_text.insert(tk.END, f"      Prerequisites: {len(orphaned_prereqs)}\n")
                    self.results_text.insert(tk.END, f"      Schedules: {len(orphaned_schedules)}\n")
                    self.issues_found.append(('orphaned_prereqs', orphaned_prereqs))
                    self.issues_found.append(('orphaned_schedules', orphaned_schedules))
                    total_issues += orphan_count
                else:
                    self.results_text.insert(tk.END, "   ✅ No orphaned records found\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for duplicates
            if self.check_duplicates.get():
                self.results_text.insert(tk.END, "4. Checking for duplicate course codes...\n")
                cursor.execute("""
                SELECT course_code, COUNT(*) as count
                FROM courses
                WHERE course_code IS NOT NULL
                GROUP BY course_code
                HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    self.results_text.insert(tk.END, f"   ❌ Found {len(duplicates)} duplicate course codes:\n")
                    for code, count in duplicates:
                        self.results_text.insert(tk.END, f"      {code}: {count} instances\n")
                        self.issues_found.append(('duplicate_code', (code, count)))
                    total_issues += len(duplicates)
                else:
                    self.results_text.insert(tk.END, "   ✅ No duplicate course codes found\n")
                self.results_text.insert(tk.END, "\n")
            
            # Check for missing required data
            if self.check_missing.get():
                self.results_text.insert(tk.END, "5. Checking for missing required data...\n")
                
                # Missing course codes
                cursor.execute("SELECT id, course_code FROM courses WHERE course_code IS NULL OR course_code = ''")
                missing_codes = cursor.fetchall()

                # Missing course names
                cursor.execute("SELECT id, course_code FROM courses WHERE course_name IS NULL OR course_name = ''")
                missing_names = cursor.fetchall()
                
                # Missing departments
                cursor.execute("SELECT id, course_code FROM courses WHERE department IS NULL OR department = ''")
                missing_depts = cursor.fetchall()
                
                missing_count = len(missing_codes) + len(missing_names) + len(missing_depts)
                if missing_count > 0:
                    self.results_text.insert(tk.END, f"   ❌ Found {missing_count} records with missing data:\n")
                    if missing_codes:
                        self.results_text.insert(tk.END, f"      Missing codes: {len(missing_codes)}\n")
                        self.issues_found.append(('missing_codes', missing_codes))
                    if missing_names:
                        self.results_text.insert(tk.END, f"      Missing names: {len(missing_names)}\n")
                        self.issues_found.append(('missing_names', missing_names))
                    if missing_depts:
                        self.results_text.insert(tk.END, f"      Missing departments: {len(missing_depts)}\n")
                        self.issues_found.append(('missing_depts', missing_depts))
                    total_issues += missing_count
                else:
                    self.results_text.insert(tk.END, "   ✅ All required data present\n")
                self.results_text.insert(tk.END, "\n")
            
            # Summary
            self.results_text.insert(tk.END, f"VALIDATION SUMMARY:\n")
            self.results_text.insert(tk.END, f"Total issues found: {total_issues}\n")
            self.results_text.insert(tk.END, f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if total_issues > 0:
                self.results_text.insert(tk.END, "\nClick 'Fix Issues' to automatically resolve fixable problems.\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            self.results_text.insert(tk.END, f"❌ Database error during validation: {e}\n")

    def load_department_data(self):
        selected_dept = self.dept_var.get()
        if not selected_dept:
            return
            
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            self.dept_details.delete(1.0, tk.END)
            
            # Department statistics
            cursor.execute("""
            SELECT 
                COUNT(*) as total_courses,
                SUM(COALESCE(current_enrollment, 0)) as total_enrollment,
                AVG(COALESCE(current_enrollment, 0)) as avg_enrollment
            FROM courses 
            WHERE course_code IS NOT NULL
              AND course_name IS NOT NULL
              AND department = ?
              AND LOWER(COALESCE(status, 'active')) = 'active'
            """, (selected_dept,))
            
            stats = cursor.fetchone()
            if stats:
                self.dept_details.insert(tk.END, f"DEPARTMENT: {selected_dept}\n")
                self.dept_details.insert(tk.END, "=" * 30 + "\n")
                self.dept_details.insert(tk.END, f"Total Courses: {stats[0]}\n")
                self.dept_details.insert(tk.END, f"Total Enrollment: {stats[1]}\n")
                self.dept_details.insert(tk.END, f"Average Enrollment: {stats[2]:.1f}\n\n")
            
            # Top enrolled courses
            cursor.execute("""
            SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled
            FROM courses 
            WHERE COALESCE(department, 'Unknown') = ? AND status = 'Active'
            ORDER BY enrolled DESC
            LIMIT 5
            """, (selected_dept,))
            
            top_courses = cursor.fetchall()
            if top_courses:
                self.dept_details.insert(tk.END, "TOP ENROLLED COURSES:\n")
                for code, name, enrolled in top_courses:
                    self.dept_details.insert(tk.END, f"  {code} - {name}: {enrolled} students\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load department data: {e}")

    def fix_issues(self):
        if not self.issues_found:
            messagebox.showinfo("No Issues", "No issues found to fix. Run validation first.")
            return
        
        if not messagebox.askyesno("Confirm Fix", "This will attempt to automatically fix found issues. Continue?"):
            return
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            fixed_count = 0
            
            for issue_type, issue_data in self.issues_found:
                if issue_type == 'over_enrolled':
                    # Reset over-enrolled courses to capacity
                    for course in issue_data:
                        cursor.execute("UPDATE courses SET current_enrollment = max_enrollment WHERE id = ?", (course[0],))
                        fixed_count += 1
                
                elif issue_type == 'orphaned_prereqs':
                    # Remove orphaned prerequisites
                    for prereq in issue_data:
                        cursor.execute("DELETE FROM course_prerequisites WHERE id = ?", (prereq[0],))
                        fixed_count += 1
                
                elif issue_type == 'orphaned_schedules':
                    # Remove orphaned schedules
                    for schedule in issue_data:
                        cursor.execute("DELETE FROM course_schedule WHERE id = ?", (schedule[0],))
                        fixed_count += 1
                
                elif issue_type == 'missing_depts':
                    # Set missing departments to 'Unknown'
                    for course in issue_data:
                        cursor.execute("UPDATE courses SET department = 'Unknown' WHERE id = ?", (course[0],))
                        fixed_count += 1
            
            conn.commit()
            conn.close()
            
            self.results_text.insert(tk.END, f"\n✅ Fixed {fixed_count} issues automatically.\n")
            self.results_text.insert(tk.END, "Some issues may require manual intervention.\n")
            
            messagebox.showinfo("Fix Complete", f"Fixed {fixed_count} issues automatically.")
            
        except sqlite3.Error as e:
            messagebox.showerror("Fix Error", f"Failed to fix issues: {e}")
    
    def export_validation_report(self):
        filename = filedialog.asksaveasfilename(
            title="Export Validation Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.results_text.get(1.0, tk.END))
                messagebox.showinfo(_("common.export_complete"), f"Validation report exported to {filename}")
            except Exception as e:
                messagebox.showerror(_("common.export_error"), f"Failed to export report: {e}")


# Standalone validation functions (extracted from RecommendationsDialog)
def validate_course_code(code):
    """Validate the course code format (e.g., CS101, MATH200)."""
    import re
    pattern = r'^[A-Z]{2,4}\d{2,3}$'
    return bool(re.match(pattern, code))

def validate_email(email):
    """Validate email format using the centralized validator."""
    from education_system.university_system.modules.shared.utils.input_validation import is_valid_email
    return is_valid_email(email)

def validate_time_format(time_str):
    """Validate time format (HH:MM)."""
    import re
    pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))

def validate_days_of_week(days_str):
    """Validate a comma‑separated list of days of the week."""
    valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
    days = [day.strip() for day in days_str.split(',')]
    return all(day in valid_days for day in days)
