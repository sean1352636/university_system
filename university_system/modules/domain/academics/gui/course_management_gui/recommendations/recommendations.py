# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.constants import paths

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
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from university_system.modules.domain.academics.services.course_management import (
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
    from university_system.modules.domain.academics.services.lms.lms_core import launch_lms_gui
    from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_recommend_courses(self):
    """Show course recommendations dialog"""
    RecommendCoursesDialog(self.root, self.auth)


def find_alternative_courses(self):
    """Show find alternative courses dialog"""
    AlternativeCourseDialog(self.root, self.auth)


def recommend_courses_wrapper(self):
    """Recommend courses to student. Calls existing show_recommendations()."""
    self.show_recommendations()


def find_alternative_courses_wrapper(self):
    """Find alternative courses. Calls existing find_alternative_courses()."""
    self.find_alternative_courses()


class RecommendCoursesDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Recommendation type selection
        type_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        type_frame.pack(fill=tk.X, pady=5)
        
        self.rec_type = tk.StringVar(value="popular")
        
        ttk.Radiobutton(type_frame, text="Most Popular Courses", variable=self.rec_type, 
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Courses with Available Spots", variable=self.rec_type, 
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Under-enrolled Courses", variable=self.rec_type, 
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(type_frame, text="Prerequisites for Course", variable=self.rec_type, 
                       value="prerequisites").pack(anchor=tk.W, pady=2)
        
        # Course selection for prerequisites (conditional)
        self.prereq_frame = ttk.LabelFrame(main_frame, text="Select Course for Prerequisites", padding=10)
        self.prereq_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.prereq_frame, text="Course:").pack(side=tk.LEFT)
        self.prereq_course_combo = ttk.Combobox(self.prereq_frame, width=50)
        self.prereq_course_combo.pack(side=tk.LEFT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Recommendations", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.results_text = ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Bind radio button changes
        for widget in type_frame.winfo_children():
            if isinstance(widget, ttk.Radiobutton):
                widget.configure(command=self.on_type_change)
        
        self.load_courses()
        self.on_type_change()
    
    def load_courses(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.prereq_course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
    
    def on_type_change(self):
        if self.rec_type.get() == "prerequisites":
            self.prereq_frame.pack(fill=tk.X, pady=5, before=self.results_text.master.master)
        else:
            self.prereq_frame.pack_forget()
    
    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            rec_type = self.rec_type.get()
            
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "COURSE RECOMMENDATIONS\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")
            
            if rec_type == "popular":
                self.results_text.insert(tk.END, "MOST POPULAR COURSES:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       ROUND(CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1) * 100, 1) as popularity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC, popularity DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Popularity':<12}\n")
                self.results_text.insert(tk.END, "-" * 62 + "\n")
                
                for code, name, enrolled, capacity, popularity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {enrolled:<10} {popularity}%\n")
            
            elif rec_type == "available":
                self.results_text.insert(tk.END, "COURSES WITH AVAILABLE SPOTS:\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses 
                WHERE status = 'Active' AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")
                
                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n")
            
            elif rec_type == "under_enrolled":
                self.results_text.insert(tk.END, "UNDER-ENROLLED COURSES (< 50% capacity):\n\n")
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(COALESCE(current_enrollment, 0) AS FLOAT) / COALESCE(max_enrollment, 1))
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n")
                self.results_text.insert(tk.END, "-" * 60 + "\n")
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    self.results_text.insert(tk.END, f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n")
            
            elif rec_type == "prerequisites":
                selected_text = self.prereq_course_combo.get()
                if selected_text not in self.course_id_map:
                    messagebox.showwarning("No Course Selected", "Please select a course to view prerequisites.")
                    return
                
                course_id = self.course_id_map[selected_text]
                
                cursor.execute("""
                SELECT c1.course_code, c1.course_name, c2.course_code, c2.course_name, cp.is_required
                FROM course_prerequisites cp
                JOIN courses c1 ON cp.course_id = c1.id
                JOIN courses c2 ON cp.prerequisite_course_id = c2.id
                WHERE cp.course_id = ?
                ORDER BY cp.is_required DESC, c2.course_code
                """, (course_id,))
                
                prereqs = cursor.fetchall()
                
                if prereqs:
                    course_info = prereqs[0]
                    self.results_text.insert(tk.END, f"PREREQUISITES FOR {course_info[0]} - {course_info[1]}:\n\n")
                    self.results_text.insert(tk.END, f"{'Code':<10} {'Name':<30} {'Type':<12}\n")
                    self.results_text.insert(tk.END, "-" * 52 + "\n")
                    
                    for prereq in prereqs:
                        req_type = "Required" if prereq[4] else "Recommended"
                        name_short = prereq[3][:27] + "..." if len(prereq[3]) > 30 else prereq[3]
                        self.results_text.insert(tk.END, f"{prereq[2]:<10} {name_short:<30} {req_type:<12}\n")
                else:
                    self.results_text.insert(tk.END, "No prerequisites found for this course.\n")
            
            conn.close()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate recommendations: {e}")


class AlternativeCourseDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Find Alternative Courses")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Course selection
        selection_frame = ttk.LabelFrame(main_frame, text="Select Reference Course", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(selection_frame, text="Course:").pack(side=tk.LEFT)
        self.course_combo = ttk.Combobox(selection_frame, width=50)
        self.course_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(selection_frame, text="Find Alternatives", 
                  command=self.find_alternatives).pack(side=tk.RIGHT, padx=5)
        
        # Results display
        results_frame = ttk.LabelFrame(main_frame, text="Alternative Courses", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Code", "Name", "Department", "Level", "Match Type", "Available")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        
        for col in columns:
            self.results_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.load_course_options()
        
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)
    
    def load_course_options(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, course_code, course_name FROM courses WHERE LOWER(COALESCE(status, 'active')) = 'active' ORDER BY course_code")
            courses = cursor.fetchall()
            
            course_options = [f"{course[1]} - {course[2]}" for course in courses]
            self.course_combo['values'] = course_options
            
            self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses}
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
    
    def find_alternatives(self):
        selected_text = self.course_combo.get()
        if selected_text not in self.course_id_map:
            messagebox.showwarning(_("common.selection_required"), "Please select a course.")
            return
        
        course_id = self.course_id_map[selected_text]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get reference course details
            cursor.execute("SELECT course_code, course_name, department, level, credit_hours FROM courses WHERE id = ?", (course_id,))
            ref_course = cursor.fetchone()
            
            if not ref_course:
                return
            
            ref_code, ref_name, ref_dept, ref_level, ref_credits = ref_course
            
            # Find alternatives
            alternatives = []
            
            # Same department and level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Dept & Level' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE department = ? AND level = ? AND id != ? AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())

            # Same department, different level
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Department' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE department = ? AND level != ? AND id != ? AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_dept, ref_level, course_id))
            alternatives.extend(cursor.fetchall())

            # Same level, different department
            cursor.execute("""
            SELECT course_code, course_name, department, level, 'Same Level' as match_type,
                   (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
            FROM courses
            WHERE level = ? AND department != ? AND id != ? AND LOWER(COALESCE(status, 'active')) = 'active'
            ORDER BY course_name
            """, (ref_level, ref_dept, course_id))
            alternatives.extend(cursor.fetchall())
            
            # Clear previous results
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Remove duplicates and populate tree
            seen = set()
            for alt in alternatives:
                key = alt[0]  # course_code
                if key not in seen:
                    seen.add(key)
                    self.results_tree.insert("", tk.END, values=alt)
            
            conn.close()
            
            if not alternatives:
                messagebox.showinfo(_("common.no_results"), "No alternative courses found.")
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to find alternatives: {e}")


class RecommendationsDialog:
    def __init__(self, parent):
        self.parent = parent
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Course Recommendations")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Course Recommendations", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Recommendation types
        types_frame = ttk.LabelFrame(main_frame, text="Recommendation Type", padding=10)
        types_frame.pack(fill=tk.X, pady=5)
        
        self.rec_type = tk.StringVar(value="popular")
        
        ttk.Radiobutton(types_frame, text="Most Popular Courses", variable=self.rec_type, 
                       value="popular").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Courses with Available Spots", variable=self.rec_type, 
                       value="available").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="Under-enrolled Courses", variable=self.rec_type, 
                       value="under_enrolled").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(types_frame, text="New Courses", variable=self.rec_type, 
                       value="new").pack(anchor=tk.W, pady=2)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Generate Recommendations", command=self.generate_recommendations).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def generate_recommendations(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            rec_type = self.rec_type.get()
            
            recommendations = "COURSE RECOMMENDATIONS\n"
            recommendations += "=" * 50 + "\n\n"
            
            if rec_type == "popular":
                recommendations += "MOST POPULAR COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                ORDER BY enrolled DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Enrolled':<10} {'Capacity':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {enrolled:<10} {capacity:<10}\n"
                    
            elif rec_type == "available":
                recommendations += "COURSES WITH AVAILABLE SPOTS:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity,
                       (COALESCE(max_enrollment, 0) - COALESCE(current_enrollment, 0)) as available
                FROM courses 
                WHERE status = 'Active' AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)
                ORDER BY available DESC
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Available':<10} {'Total':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity, available in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    recommendations += f"{code:<10} {name_short:<30} {available:<10} {capacity:<10}\n"
                    
            elif rec_type == "under_enrolled":
                recommendations += "UNDER-ENROLLED COURSES (< 50% capacity):\n\n"
                cursor.execute("""
                SELECT course_code, course_name, COALESCE(current_enrollment, 0) as enrolled,
                       COALESCE(max_enrollment, 0) as capacity
                FROM courses 
                WHERE status = 'Active' AND COALESCE(max_enrollment, 0) > 0
                  AND COALESCE(current_enrollment, 0) < (COALESCE(max_enrollment, 0) * 0.5)
                ORDER BY (CAST(current_enrollment AS FLOAT) / max_enrollment)
                LIMIT 15
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Fill Rate':<10} {'Enrolled':<10}\n"
                recommendations += "-" * 60 + "\n"
                
                for code, name, enrolled, capacity in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    fill_rate = f"{(enrolled/capacity*100):.1f}%" if capacity > 0 else "0%"
                    enrollment_str = f"{enrolled}/{capacity}"
                    recommendations += f"{code:<10} {name_short:<30} {fill_rate:<10} {enrollment_str:<10}\n"
                    
            elif rec_type == "new":
                recommendations += "RECENTLY CREATED COURSES:\n\n"
                cursor.execute("""
                SELECT course_code, course_name, created_at, status
                FROM courses 
                WHERE created_at >= date('now', '-6 months')
                ORDER BY created_at DESC
                LIMIT 10
                """)
                
                courses = cursor.fetchall()
                recommendations += f"{'Code':<10} {'Name':<30} {'Created':<12} {'Status':<10}\n"
                recommendations += "-" * 62 + "\n"
                
                for code, name, created, status in courses:
                    name_short = name[:27] + "..." if len(name) > 30 else name
                    created_date = created.split()[0] if created else "Unknown"
                    recommendations += f"{code:<10} {name_short:<30} {created_date:<12} {status:<10}\n"
            
            conn.close()
            
            if not courses:
                recommendations += "No recommendations found for the selected criteria.\n"
            
            self.result = recommendations
            self.dialog.destroy()
            
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to generate recommendations: {e}")

    # =====================================================================
    # VALIDATION HELPER METHODS (Functions 2-5)
    # =====================================================================

    def validate_course_code(self, code):
        """Validate the course code format (e.g., CS101, MATH200)"""
        pattern = r'^[A-Z]{2,4}\d{2,3}$'
        return bool(re.match(pattern, code))

    def validate_email(self, email):
        """Validate email format - delegates to centralized validator"""
        from university_system.modules.shared.utils.input_validation import is_valid_email
        return is_valid_email(email)

    def validate_time_format(self, time_str):
        """Validate time format (HH:MM)"""
        pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        return bool(re.match(pattern, time_str))

    def validate_days_of_week(self, days_str):
        """Validate days of week format"""
        valid_days = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
        days = [day.strip() for day in days_str.split(',')]
        return all(day in valid_days for day in days)

    # =====================================================================
    # ENHANCED DATABASE INITIALIZATION (Function 1)
    # =====================================================================

    def initialize_enhanced_database_wrapper(self):
        """
        Wrapper for initialize_enhanced_database() from CLI module.
        This creates all advanced tables for course management.
        """
        try:
            if ORIGINAL_MODULE_AVAILABLE:
                success = initialize_enhanced_database()
                if success:
                    self.update_status("Enhanced database initialized successfully")
                    messagebox.showinfo(_("common.success"), "Enhanced database tables created successfully!")
                else:
                    self.update_status("Database initialization failed", error=True)
                    messagebox.showerror(_("common.error"), "Failed to initialize enhanced database")
            else:
                # Use fallback
                self.init_fallback_database()
                self.update_status("Database initialized with fallback")
        except Exception as e:
            self.update_status(f"Initialization error: {e}", error=True)
            messagebox.showerror(_("common.error"), f"Database initialization failed: {e}")

    # =====================================================================
    # CORE COURSE MANAGEMENT WRAPPERS (Functions 6-11)
    # =====================================================================

    def create_enhanced_course_wrapper(self):
        """
        Wrapper that opens the enhanced course creation dialog.
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def create_course_wrapper(self):
        """
        Basic course creation wrapper (same as enhanced for GUI).
        Calls the existing show_create_course() method.
        """
        self.show_create_course()

    def view_all_courses_wrapper(self):
        """
        Display all courses in the main list.
        Refreshes the course list and switches to the first tab.
        """
        self.refresh_course_list()
        self.notebook.select(0)  # Switch to course list tab
        self.update_status("Course list refreshed")

    def update_course_wrapper(self):
        """
        Update the selected course.
        Calls the existing edit_selected_course() method.
        """
        self.edit_selected_course()

    def delete_course_wrapper(self):
        """
        Delete the selected course.
        Calls the existing delete_selected_course() method.
        """
        self.delete_selected_course()

    def view_course_details_wrapper(self):
        """
        View detailed information about the selected course.
        Switches to the course details tab.
        """
        selected = self.course_tree.selection()
        if not selected:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course to view details.")
            return

        # Switch to details tab
        self.notebook.select(1)
        self.show_course_details()
        self.update_status("Viewing course details")

    # =====================================================================
    # PREREQUISITE MANAGEMENT (Functions 12-16)
    # =====================================================================

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
            cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
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
                cursor = conn.cursor()

                # Check for circular dependency
                if self.check_circular_prerequisite_db(cursor, course_id, prereq_id):
                    messagebox.showerror("Circular Dependency",
                                       "Adding this prerequisite would create a circular dependency!")
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
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
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
                cursor.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
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

    # =====================================================================
    # INSTRUCTOR MANAGEMENT WRAPPERS (Functions 17-19)
    # =====================================================================

    def create_instructor_wrapper(self):
        """
        Create a new instructor profile.
        Calls the existing show_add_instructor() method.
        """
        self.show_add_instructor()

    def view_instructors_wrapper(self):
        """
        View all instructors in the system.
        Refreshes the instructor list and switches to instructors tab.
        """
        self.refresh_instructor_list()
        # Find and select the instructors tab (usually tab 3)
        for i in range(self.notebook.index('end')):
            if 'Instructor' in self.notebook.tab(i, 'text'):
                self.notebook.select(i)
                break
        self.update_status("Instructor list refreshed")

    def assign_instructor_to_course_wrapper(self):
        """
        Assign an instructor to a course.
        Calls the existing show_assign_instructor() method.
        """
        self.show_assign_instructor()

    # =====================================================================
    # COURSE SCHEDULING (Functions 20-22)
    # =====================================================================

    def create_course_schedule_gui(self):
        """
        Create a schedule for a course - Integrated with Module Scheduling System.
        Opens a dialog to input schedule details using the module_schedule table.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Course Schedule")
        dialog.geometry("700x750")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Course Schedule",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Course selection
        course_frame = ttk.LabelFrame(main_frame, text="Select Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course/Module:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=50)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Schedule details
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule Details", padding="10")
        schedule_frame.pack(fill=tk.X, pady=5)

        # Day of week dropdown
        ttk.Label(schedule_frame, text="Day of Week:").grid(row=0, column=0, sticky=tk.W, pady=5)
        day_var = tk.StringVar()
        day_combo = ttk.Combobox(schedule_frame, textvariable=day_var,
                                values=DAYS_OF_WEEK, state='readonly', width=28)
        day_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Start time dropdown
        ttk.Label(schedule_frame, text="Start Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_time_var = tk.StringVar()
        start_time_combo = ttk.Combobox(schedule_frame, textvariable=start_time_var,
                                       values=TIME_SLOTS, state='readonly', width=28)
        start_time_combo.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        # End time dropdown
        ttk.Label(schedule_frame, text="End Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_time_var = tk.StringVar()
        end_time_combo = ttk.Combobox(schedule_frame, textvariable=end_time_var,
                                     values=TIME_SLOTS, state='readonly', width=28)
        end_time_combo.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)

        # Session type dropdown
        ttk.Label(schedule_frame, text="Session Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        session_type_var = tk.StringVar()
        session_type_combo = ttk.Combobox(schedule_frame, textvariable=session_type_var,
                                         values=SESSION_TYPES, state='readonly', width=28)
        session_type_combo.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        session_type_combo.current(0)  # Default to Lecture

        # Room selection - DROPDOWN with database
        ttk.Label(schedule_frame, text="Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        room_var = tk.StringVar()
        room_combo = ttk.Combobox(schedule_frame, textvariable=room_var, state='readonly', width=28)
        room_combo.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)

        # Instructor selection
        instructor_frame = ttk.LabelFrame(main_frame, text="Instructor", padding="10")
        instructor_frame.pack(fill=tk.X, pady=5)

        ttk.Label(instructor_frame, text="Instructor:").grid(row=0, column=0, sticky=tk.W, pady=5)
        instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(instructor_frame, textvariable=instructor_var,
                                       state='readonly', width=50)
        instructor_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        def load_data():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Load active courses/modules
                cursor.execute("""
                    SELECT id, course_code, course_name
                    FROM courses
                    WHERE status = 'Active'
                    ORDER BY course_code
                """)
                courses = cursor.fetchall()
                course_list = [f"{code} - {name}" for id, code, name in courses]
                course_combo['values'] = course_list

                # Load active rooms from rooms table
                cursor.execute("""
                    SELECT id, building, room_number, capacity, room_type
                    FROM rooms
                    WHERE is_active = 1
                    ORDER BY building, room_number
                """)
                rooms = cursor.fetchall()
                room_list = [f"{room[0]} - {room[1]}-{room[2]} (Cap: {room[3]}, Type: {room[4]})"
                            for room in rooms]
                room_combo['values'] = room_list

                # Load active instructors
                cursor.execute("""
                    SELECT id, first_name, last_name
                    FROM instructors
                    WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1
                    ORDER BY last_name, first_name
                """)
                instructors = cursor.fetchall()
                instructor_list = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
                instructor_combo['values'] = instructor_list

                conn.close()

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load data: {e}")
                dialog.destroy()

        def save_schedule():
            # Validation
            if not course_var.get():
                messagebox.showwarning("Incomplete", "Please select a course/module")
                return

            if not day_var.get():
                messagebox.showwarning("Incomplete", "Please select a day of week")
                return

            if not start_time_var.get() or not end_time_var.get():
                messagebox.showwarning("Incomplete", "Please select start and end times")
                return

            if not room_var.get():
                messagebox.showwarning("Incomplete", "Please select a room")
                return

            if not instructor_var.get():
                messagebox.showwarning("Incomplete", "Please select an instructor")
                return

            if not session_type_var.get():
                messagebox.showwarning("Incomplete", "Please select a session type")
                return

            try:
                # Extract course code
                module_code = course_var.get().split(" - ")[0]

                # Extract room ID
                room_id = int(room_var.get().split(" - ")[0])

                # Extract instructor ID
                instructor_id = int(instructor_var.get().split(" - ")[0])

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
                conn.execute('PRAGMA journal_mode=WAL')  # Enable WAL mode for better concurrency
                cursor = conn.cursor()

                # Ensure course_schedule table exists with proper schema
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                # Get current semester and year
                current_semester = "Fall"  # You can make this dynamic
                current_year = datetime.now().year

                # Check for schedule conflicts
                cursor.execute("""
                    SELECT id FROM course_schedule
                    WHERE course_code = ? AND day_of_week = ? AND semester = ? AND year = ?
                    AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))
                """, (module_code, day_var.get(), current_semester, current_year,
                     start_time_var.get(), start_time_var.get(),
                     end_time_var.get(), end_time_var.get()))

                if cursor.fetchone():
                    messagebox.showerror("Schedule Conflict",
                                       f"Schedule conflict detected for {module_code} on {day_var.get()}")
                    conn.close()
                    return

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert into course_schedule table
                cursor.execute('''
                    INSERT INTO course_schedule (course_code, day_of_week, start_time, end_time,
                                               room_id, instructor_id, session_type, semester, year, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, day_var.get(), start_time_var.get(), end_time_var.get(),
                      room_id, instructor_id, session_type_var.get(), current_semester, current_year, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"),
                                  f"Schedule created successfully!\n\n"
                                  f"Course: {module_code}\n"
                                  f"Day: {day_var.get()}\n"
                                  f"Time: {start_time_var.get()} - {end_time_var.get()}\n"
                                  f"Session: {session_type_var.get()}\n"
                                  f"Semester: {current_semester} {current_year}")
                self.update_status("Course schedule created in course_schedule table")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to create schedule: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Create Schedule", command=save_schedule).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_data()

    def view_course_schedules_gui(self):
        """
        View course schedules using course_schedule table.
        Displays timetable in grid format matching Module Scheduling GUI.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Schedules - Timetable View")
        dialog.geometry("1400x900")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Schedules - Timetable View",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Create notebook for list and grid views
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # ==========================
        # TAB 1: LIST VIEW
        # ==========================
        list_tab = ttk.Frame(notebook)
        notebook.add(list_tab, text="📋 List View")

        # Filter frame
        filter_frame = ttk.Frame(list_tab)
        filter_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_filter_var = tk.StringVar()
        course_filter_combo = ttk.Combobox(filter_frame, textvariable=course_filter_var,
                                          state='readonly', width=40)
        course_filter_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text="🔄 Refresh",
                  command=lambda: load_list_view()).pack(side=tk.LEFT, padx=5)

        # Treeview for schedules
        tree_frame = ttk.Frame(list_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        columns = ('ID', 'Course', 'Day', 'Time', 'Room', 'Instructor', 'Type', 'Semester')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        tree.heading('ID', text='ID')
        tree.heading('Course', text='Course Code')
        tree.heading('Day', text='Day')
        tree.heading('Time', text='Time')
        tree.heading('Room', text='Room')
        tree.heading('Instructor', text='Instructor')
        tree.heading('Type', text='Session Type')
        tree.heading('Semester', text='Semester')

        tree.column('ID', width=50)
        tree.column('Course', width=120)
        tree.column('Day', width=100)
        tree.column('Time', width=120)
        tree.column('Room', width=150)
        tree.column('Instructor', width=150)
        tree.column('Type', width=100)
        tree.column('Semester', width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Buttons for list view
        list_button_frame = ttk.Frame(list_tab)
        list_button_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Button(list_button_frame, text="❌ Delete Selected",
                  command=lambda: delete_selected_schedule()).pack(side=tk.LEFT, padx=5)
        ttk.Button(list_button_frame, text="✏️ Edit Selected",
                  command=lambda: edit_selected_schedule()).pack(side=tk.LEFT, padx=5)

        # ==========================
        # TAB 2: TIMETABLE GRID VIEW
        # ==========================
        grid_tab = ttk.Frame(notebook)
        notebook.add(grid_tab, text="📅 Timetable Grid")

        # Filter for grid view
        grid_filter_frame = ttk.Frame(grid_tab)
        grid_filter_frame.pack(fill=tk.X, pady=5, padx=10)

        ttk.Label(grid_filter_frame, text="Show schedule for:").pack(side=tk.LEFT, padx=5)
        grid_filter_var = tk.StringVar(value="All Courses")
        grid_filter_combo = ttk.Combobox(grid_filter_frame, textvariable=grid_filter_var,
                                        state='readonly', width=40)
        grid_filter_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(grid_filter_frame, text="🔄 Refresh Grid",
                  command=lambda: load_timetable_grid()).pack(side=tk.LEFT, padx=5)

        # Scrollable grid container
        grid_canvas_frame = ttk.Frame(grid_tab)
        grid_canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        grid_canvas = tk.Canvas(grid_canvas_frame, bg='white')
        grid_scrollbar_v = ttk.Scrollbar(grid_canvas_frame, orient="vertical", command=grid_canvas.yview)
        grid_scrollbar_h = ttk.Scrollbar(grid_canvas_frame, orient="horizontal", command=grid_canvas.xview)

        grid_frame = tk.Frame(grid_canvas, bg='white')
        grid_frame.bind("<Configure>", lambda e: grid_canvas.configure(scrollregion=grid_canvas.bbox("all")))

        grid_canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_canvas.configure(yscrollcommand=grid_scrollbar_v.set, xscrollcommand=grid_scrollbar_h.set)

        grid_canvas.pack(side="left", fill="both", expand=True)
        grid_scrollbar_v.pack(side="right", fill="y")
        grid_scrollbar_h.pack(side="bottom", fill="x")

        # ==========================
        # FUNCTIONS
        # ==========================

        def load_courses():
            """Load course filter options"""
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT course_code FROM courses WHERE status = 'Active' ORDER BY course_code")
                courses = [row[0] for row in cursor.fetchall()]
                conn.close()

                course_list = ["-- All Courses --"] + courses
                course_filter_combo['values'] = course_list
                course_filter_combo.current(0)

                grid_filter_combo['values'] = course_list
                grid_filter_combo.current(0)

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

        def load_list_view(*args):
            """Load schedules in list view"""
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                filter_course = course_filter_var.get()

                if filter_course == "-- All Courses --" or not filter_course:
                    query = """
                        SELECT cs.id, cs.course_code, cs.day_of_week,
                               cs.start_time, cs.end_time,
                               r.building, r.room_number,
                               i.first_name, i.last_name,
                               cs.session_type, cs.semester, cs.year
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        LEFT JOIN instructors i ON cs.instructor_id = i.id
                        ORDER BY cs.course_code, cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT cs.id, cs.course_code, cs.day_of_week,
                               cs.start_time, cs.end_time,
                               r.building, r.room_number,
                               i.first_name, i.last_name,
                               cs.session_type, cs.semester, cs.year
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        LEFT JOIN instructors i ON cs.instructor_id = i.id
                        WHERE cs.course_code = ?
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query, (filter_course,))

                schedules = cursor.fetchall()
                conn.close()

                for sched in schedules:
                    sched_id, course_code, day, start, end, building, room_num, first, last, session_type, semester, year = sched
                    time_str = f"{start}-{end}"
                    room_str = f"{building}-{room_num}" if building and room_num else "TBA"
                    instructor = f"{first} {last}" if first and last else "TBA"
                    semester_str = f"{semester} {year}" if semester and year else "N/A"

                    tree.insert('', tk.END, values=(
                        sched_id, course_code, day, time_str, room_str,
                        instructor, session_type or '', semester_str
                    ))

                if not schedules:
                    messagebox.showinfo(_("common.no_results"), "No course schedules found")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load schedules: {e}")
                print(_("course_management.errors.schedule_load", error=str(e)))

        def delete_selected_schedule():
            """Delete selected schedule from list"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a schedule to delete")
                return

            item = tree.item(selection[0])
            schedule_id = item['values'][0]
            course_code = item['values'][1]

            if not messagebox.askyesno("Confirm Delete",
                                      f"Delete schedule for {course_code}?\n\nThis action cannot be undone."):
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("DELETE FROM course_schedule WHERE id = ?", (schedule_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), f"Schedule deleted successfully!")
                self.update_status(f"Deleted schedule {schedule_id}")
                load_list_view()
                load_timetable_grid()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to delete schedule: {e}")

        def edit_selected_schedule():
            """Edit selected schedule"""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a schedule to edit")
                return

            item = tree.item(selection[0])
            schedule_id = item['values'][0]

            # Call update schedule function with this ID
            self.show_update_schedule_by_id(schedule_id)
            dialog.destroy()

        def load_timetable_grid():
            """Load timetable in grid format matching Module Scheduling GUI"""
            # Clear existing grid
            for widget in grid_frame.winfo_children():
                widget.destroy()

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_code TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    room_id INTEGER,
                    instructor_id INTEGER,
                    session_type TEXT,
                    semester TEXT,
                    year INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES rooms(id),
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                )
                ''')

                filter_course = grid_filter_var.get()

                if filter_course == "-- All Courses --" or not filter_course:
                    query = """
                        SELECT cs.course_code, cs.day_of_week, cs.start_time, cs.end_time,
                               r.building, r.room_number, cs.session_type
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT cs.course_code, cs.day_of_week, cs.start_time, cs.end_time,
                               r.building, r.room_number, cs.session_type
                        FROM course_schedule cs
                        LEFT JOIN rooms r ON cs.room_id = r.id
                        WHERE cs.course_code = ?
                        ORDER BY cs.day_of_week, cs.start_time
                    """
                    cursor.execute(query, (filter_course,))

                schedule_data = cursor.fetchall()
                conn.close()

                # Create grid data structure
                grid_data = {}
                for day in DAYS_OF_WEEK:
                    grid_data[day] = {}
                    for time_slot in TIME_SLOTS:
                        grid_data[day][time_slot] = []

                # Populate grid with schedule data
                for entry in schedule_data:
                    course_code, day, start_time, end_time, building, room_num, session_type = entry

                    if not day or not start_time:
                        continue

                    # Find the closest time slot
                    try:
                        closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
                    except Exception:
                        continue

                    session_info = {
                        'course': course_code,
                        'type': session_type or 'Session',
                        'room': f"{building}-{room_num}" if building and room_num else "TBA",
                        'time': f"{start_time}-{end_time}"
                    }

                    if day in grid_data and closest_slot in grid_data[day]:
                        grid_data[day][closest_slot].append(session_info)

                # Create grid header - Time column
                time_header = tk.Label(grid_frame, text="Time", font=('Arial', 10, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                      width=10, height=2)
                time_header.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")

                # Day headers
                for col, day in enumerate(DAYS_OF_WEEK, 1):
                    day_header = tk.Label(grid_frame, text=day, font=('Arial', 10, 'bold'),
                                         relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                         width=18, height=2)
                    day_header.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

                # Create time slots and schedule cells
                for row, time_slot in enumerate(TIME_SLOTS, 1):
                    # Time label
                    time_label = tk.Label(grid_frame, text=time_slot, font=('Arial', 9, 'bold'),
                                         relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                         width=10, height=4)
                    time_label.grid(row=row, column=0, padx=1, pady=1, sticky="nsew")

                    # Schedule cells for each day
                    for col, day in enumerate(DAYS_OF_WEEK, 1):
                        entries = grid_data[day][time_slot]

                        # Create cell frame
                        cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                             bg='#d4edda' if entries else 'white',
                                             width=160, height=80)
                        cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                        cell_frame.grid_propagate(False)

                        if entries:
                            # Inner container
                            inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                            inner_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

                            # Display entries
                            for i, entry in enumerate(entries):
                                if i < 2:  # Limit to 2 entries per cell
                                    session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                          bg='#c3e6cb', padx=2, pady=2)
                                    session_box.pack(fill=tk.X, pady=1)

                                    # Course code
                                    course_label = tk.Label(session_box, text=entry['course'],
                                                           font=('Arial', 8, 'bold'),
                                                           bg='#c3e6cb', fg='#155724')
                                    course_label.pack(anchor='w')

                                    # Session type
                                    type_label = tk.Label(session_box, text=entry['type'],
                                                         font=('Arial', 7),
                                                         bg='#c3e6cb', fg='#155724')
                                    type_label.pack(anchor='w')

                                    # Room
                                    room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                         font=('Arial', 6),
                                                         bg='#c3e6cb', fg='#155724')
                                    room_label.pack(anchor='w')

                            if len(entries) > 2:
                                more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                                     font=('Arial', 7, 'italic'),
                                                     bg='#d4edda', fg='#155724')
                                more_label.pack(anchor='w', pady=2)

                if not schedule_data:
                    no_data_label = tk.Label(grid_frame, text="No course schedules found",
                                            font=('Arial', 12), fg='gray')
                    no_data_label.grid(row=1, column=1, columnspan=5, pady=50)

            except Exception as e:
                error_label = tk.Label(grid_frame, text=f"Error loading timetable: {e}",
                                      font=('Arial', 12), fg='red')
                error_label.grid(row=1, column=1, columnspan=5, pady=50)
                print(_("course_management.errors.timetable_grid", error=str(e)))

        # Bind filter changes
        course_filter_combo.bind('<<ComboboxSelected>>', load_list_view)
        grid_filter_combo.bind('<<ComboboxSelected>>', lambda e: load_timetable_grid())

        # Main buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_list_view()
        load_timetable_grid()

    def show_update_schedule_by_id(self, schedule_id):
        """Helper method to show update dialog for a specific schedule ID"""
        # For now, open the general update dialog
        # Can be enhanced later to pre-populate with schedule data
        self.show_update_schedule()
        messagebox.showinfo("Edit Schedule", f"Please select schedule ID: {schedule_id} from the list")

    def update_schedule_gui(self):
        """
        Update an existing course schedule.
        Opens a dialog to modify schedule details.
        """
        # First, show schedule selection dialog
        select_dialog = tk.Toplevel(self.root)
        select_dialog.title("Select Schedule to Update")
        select_dialog.geometry("600x400")
        select_dialog.transient(self.root)

        main_frame = ttk.Frame(select_dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Select Schedule to Update",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Listbox for schedules
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        schedule_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        schedule_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=schedule_listbox.yview)

        schedule_data = {}

        def load_schedules():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.id, c.course_code, c.course_name, s.semester, s.year
                    FROM course_schedule s
                    JOIN courses c ON s.course_id = c.id
                    ORDER BY s.year DESC, s.semester, c.course_code
                """)
                schedules = cursor.fetchall()
                conn.close()

                for sched_id, code, name, semester, year in schedules:
                    display_text = f"{code} - {name[:30]} ({semester} {year})"
                    schedule_listbox.insert(tk.END, display_text)
                    schedule_data[display_text] = sched_id

                if not schedules:
                    schedule_listbox.insert(tk.END, "No schedules found")

            except sqlite3.Error as e:
                messagebox.showerror(_("common.error"), f"Failed to load schedules: {e}")

        def open_edit_dialog():
            selection = schedule_listbox.curselection()
            if not selection:
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a schedule to update")
                return

            selected_text = schedule_listbox.get(selection[0])
            if selected_text == "No schedules found":
                return

            schedule_id = schedule_data.get(selected_text)
            if not schedule_id:
                return

            select_dialog.destroy()
            self._show_schedule_edit_dialog(schedule_id)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Edit Selected", command=open_edit_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=select_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_schedules()

    def _show_schedule_edit_dialog(self, schedule_id):
        """Helper method to show the schedule edit dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Course Schedule")
        dialog.geometry("600x500")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Update Course Schedule",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Load current schedule data
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT course_id, semester, year, start_time, end_time,
                       days_of_week, classroom, instructor_id
                FROM course_schedule WHERE id = ?
            """, (schedule_id,))
            current = cursor.fetchone()
            conn.close()

            if not current:
                messagebox.showerror(_("common.error"), "Schedule not found")
                dialog.destroy()
                return

        except sqlite3.Error as e:
            messagebox.showerror(_("common.error"), f"Failed to load schedule: {e}")
            dialog.destroy()
            return

        # Create form fields with current values
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        row = 0

        # Semester
        ttk.Label(form_frame, text="Semester:").grid(row=row, column=0, sticky=tk.W, pady=5)
        semester_var = tk.StringVar(value=current[1])
        semester_combo = ttk.Combobox(form_frame, textvariable=semester_var,
                                     values=["Fall", "Spring", "Summer", "Winter"],
                                     state='readonly', width=25)
        semester_combo.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Year
        ttk.Label(form_frame, text="Year:").grid(row=row, column=0, sticky=tk.W, pady=5)
        year_var = tk.StringVar(value=str(current[2]))
        year_entry = ttk.Entry(form_frame, textvariable=year_var, width=27)
        year_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Start time
        ttk.Label(form_frame, text="Start Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=5)
        start_time_var = tk.StringVar(value=current[3] or '')
        start_time_entry = ttk.Entry(form_frame, textvariable=start_time_var, width=27)
        start_time_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # End time
        ttk.Label(form_frame, text="End Time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=5)
        end_time_var = tk.StringVar(value=current[4] or '')
        end_time_entry = ttk.Entry(form_frame, textvariable=end_time_var, width=27)
        end_time_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Days
        ttk.Label(form_frame, text="Days of Week:").grid(row=row, column=0, sticky=tk.W, pady=5)
        days_var = tk.StringVar(value=current[5] or '')
        days_entry = ttk.Entry(form_frame, textvariable=days_var, width=27)
        days_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        # Classroom
        ttk.Label(form_frame, text="Classroom:").grid(row=row, column=0, sticky=tk.W, pady=5)
        classroom_var = tk.StringVar(value=current[6] or '')
        classroom_entry = ttk.Entry(form_frame, textvariable=classroom_var, width=27)
        classroom_entry.grid(row=row, column=1, sticky=tk.W, pady=5, padx=5)
        row += 1

        def save_changes():
            # Validate inputs
            if start_time_var.get() and not self.validate_time_format(start_time_var.get()):
                messagebox.showerror("Invalid Format", "Start time must be in HH:MM format")
                return

            if end_time_var.get() and not self.validate_time_format(end_time_var.get()):
                messagebox.showerror("Invalid Format", "End time must be in HH:MM format")
                return

            if days_var.get() and not self.validate_days_of_week(days_var.get()):
                messagebox.showerror("Invalid Format", "Days must be full day names separated by commas")
                return

            try:
                year = int(year_var.get())
            except ValueError:
                messagebox.showerror("Invalid Year", "Please enter a valid year")
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE course_schedule
                    SET semester = ?, year = ?, start_time = ?, end_time = ?,
                        days_of_week = ?, classroom = ?
                    WHERE id = ?
                """, (semester_var.get(), year,
                      start_time_var.get() or None, end_time_var.get() or None,
                      days_var.get() or None, classroom_var.get() or None,
                      schedule_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Schedule updated successfully!")
                self.update_status("Course schedule updated")
                dialog.destroy()

            except sqlite3.Error as e:
                messagebox.showerror(_("common.error"), f"Failed to update schedule: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # =====================================================================
    # WAITLIST MANAGEMENT (Functions 29-31)
    # =====================================================================

    def add_to_waitlist_gui(self):
        """
        Add a student to a course waitlist.
        Opens a dialog to select full course and enter student ID.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student to Waitlist")
        dialog.geometry("550x350")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Student to Course Waitlist",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Course selection (full courses only)
        course_frame = ttk.LabelFrame(main_frame, text="Select Full Course", padding="10")
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(course_frame, textvariable=course_var, state='readonly', width=45)
        course_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)

        # Student ID
        student_frame = ttk.LabelFrame(main_frame, text="Student Information", padding="10")
        student_frame.pack(fill=tk.X, pady=5)

        ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(student_frame, textvariable=student_id_var, width=30)
        student_id_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        # Info label
        info_label = ttk.Label(main_frame, text="", foreground="blue", wraplength=500)
        info_label.pack(pady=10)

        def load_full_courses():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, course_code, course_name, current_enrollment, max_enrollment
                    FROM courses
                    WHERE current_enrollment >= max_enrollment AND status = 'Active'
                    ORDER BY course_code
                """)
                courses = cursor.fetchall()
                conn.close()

                if courses:
                    course_list = [f"{code} - {name} ({enr}/{max}) (ID: {id})"
                                 for id, code, name, enr, max in courses]
                    course_combo['values'] = course_list
                    info_label.config(text=f"Found {len(courses)} full course(s)")
                else:
                    course_combo['values'] = ["No full courses available"]
                    info_label.config(text="No full courses found")

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")
                dialog.destroy()

        def add_student():
            if not course_var.get() or course_var.get() == "No full courses available":
                messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course")
                return

            if not student_id_var.get().strip():
                messagebox.showerror("Missing Data", "Please enter student ID")
                return

            try:
                course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
                student_id = student_id_var.get().strip()

                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                # Validate student exists in database
                cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_id = ?", (student_id,))
                student_record = cursor.fetchone()

                if not student_record:
                    messagebox.showerror("Invalid Student",
                                       f"Student ID '{student_id}' does not exist in the database.\n\n"
                                       f"Please enter a valid student ID.")
                    conn.close()
                    return

                student_name = f"{student_record[1]} {student_record[2]}"

                # Check if already on waitlist
                cursor.execute("""
                    SELECT id FROM course_waitlist
                    WHERE course_id = ? AND student_id = ?
                """, (course_id, student_id))

                if cursor.fetchone():
                    messagebox.showerror("Duplicate", f"Student {student_name} ({student_id}) is already on the waitlist for this course")
                    conn.close()
                    return

                # Get next position
                cursor.execute("""
                    SELECT COALESCE(MAX(position), 0) + 1
                    FROM course_waitlist WHERE course_id = ?
                """, (course_id,))
                position = cursor.fetchone()[0]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO course_waitlist (course_id, student_id, position, added_at, status)
                    VALUES (?, ?, ?, ?, 'Waiting')
                ''', (course_id, student_id, position, timestamp))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"),
                                  f"Student {student_name} ({student_id}) added to waitlist at position {position}")
                self.update_status(f"Added student {student_name} ({student_id}) to waitlist")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to add to waitlist: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add to Waitlist", command=add_student).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        load_full_courses()

    def view_waitlists_gui(self):
        """
        View waitlists for all courses or a specific course.
        Opens a dialog with waitlist information.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("View Course Waitlists")
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Course Waitlists",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="Filter by Course:").pack(side=tk.LEFT, padx=5)
        course_var = tk.StringVar()
        course_combo = ttk.Combobox(filter_frame, textvariable=course_var, state='readonly', width=40)
        course_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Treeview for waitlist
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        columns = ('Course', 'Position', 'Student ID', 'Added Date', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Course':
                tree.column(col, width=200)
            elif col == 'Student ID':
                tree.column(col, width=120)
            else:
                tree.column(col, width=100)

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

        def load_waitlist(*args):
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()

                selected = course_var.get()

                if selected == "-- All Courses --" or not selected:
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        ORDER BY c.course_code, w.position
                    """)
                else:
                    course_id = int(selected.split("ID: ")[1].rstrip(")"))
                    cursor.execute("""
                        SELECT c.course_code, c.course_name, w.position,
                               w.student_id, w.added_at, w.status
                        FROM course_waitlist w
                        JOIN courses c ON w.course_id = c.id
                        WHERE w.course_id = ?
                        ORDER BY w.position
                    """, (course_id,))

                waitlist = cursor.fetchall()
                conn.close()

                for entry in waitlist:
                    code, name, position, student, added, status = entry
                    course = f"{code} - {name[:25]}"
                    added_date = added.split()[0] if added else "Unknown"

                    tree.insert('', tk.END, values=(
                        course, position, student, added_date, status
                    ))

                if not waitlist:
                    messagebox.showinfo(_("common.no_results"), "No waitlist entries found")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load waitlist: {e}")

        course_combo.bind('<<ComboboxSelected>>', load_waitlist)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Refresh", command=load_waitlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Initial load
        load_courses()
        load_waitlist()

    def process_waitlist_gui(self):
        """
        Process waitlist and enroll students when spots become available.
        Opens a dialog to select course and process waitlist.
        """
        messagebox.showinfo("Process Waitlist",
                          "This feature would automatically enroll students from the waitlist\n"
                          "when spots become available in the course.\n\n"
                          "Implementation requires integration with enrollment system.")

    # =====================================================================
    # COURSE STATUS & HISTORY (Functions 34, 36)
    # =====================================================================

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
                    FROM courses ORDER BY course_code
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

    # =====================================================================
    # WRAPPER FUNCTIONS FOR EXISTING FEATURES (Functions 23-28, 32-33, 35, 37)
    # =====================================================================

    def search_courses_wrapper(self):
        """Search courses with filters. Calls existing show_search_dialog()."""
        self.show_search_dialog()

    def import_courses_from_csv_wrapper(self):
        """Import courses from CSV file. Calls existing import_csv()."""
        self.import_csv()

    def export_courses_to_csv_wrapper(self):
        """Export courses to CSV file. Calls existing export_csv()."""
        self.export_csv()

    def generate_course_analytics_wrapper(self):
        """Generate course analytics. Calls existing generate_analytics()."""
        self.generate_analytics()

    def generate_enrollment_report_wrapper(self):
        """Generate enrollment report. Calls existing show_enrollment_report()."""
        self.show_enrollment_report()

    def department_statistics_wrapper(self):
        """Generate department statistics. Calls existing show_department_stats()."""
        self.show_department_stats()

    def recommend_courses_wrapper(self):
        """Recommend courses to student. Calls existing show_recommendations()."""
        self.show_recommendations()

    def find_alternative_courses_wrapper(self):
        """Find alternative courses. Calls existing find_alternative_courses()."""
        self.find_alternative_courses()

    def bulk_update_courses_wrapper(self):
        """Bulk update multiple courses. Calls existing show_bulk_update()."""
        self.show_bulk_update()

    def system_maintenance_wrapper(self):
        """System maintenance operations. Calls existing show_maintenance()."""
        self.show_maintenance()
