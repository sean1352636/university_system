# gui_course_management.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, Toplevel
from tkinter.scrolledtext import ScrolledText
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _, init_i18n
init_i18n()
import os
from pathlib import Path
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core import paths

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
    from education_system.post_18.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email = None

# Import module scheduling constants for timetable integration
try:
    from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (
        DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES
    )
except ImportError:
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']

# Import the original course management functions
try:
    from education_system.post_18.university_system.modules.domain.academics.services.course_management import (
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
    from education_system.post_18.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import launch_degree_audit_gui
    from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import launch_course_evaluation_gui
    ACADEMIC_SYSTEMS_AVAILABLE = True
except ImportError as e:
    ACADEMIC_SYSTEMS_AVAILABLE = False
    print(_("course_management.warnings.academic_systems_unavailable", error=str(e)))

# =====================================================================
# GUI APPLICATION CLASS
# =====================================================================


def show_create_schedule(self):
    """Open dialog to create a new course schedule entry"""
    CreateScheduleDialog(self.root, self.auth)


def show_view_schedules(self):
    """Open dialog to view all schedules"""
    ViewSchedulesDialog(self.root, self.auth)


def show_update_schedule(self):
    """Show update schedule dialog"""
    UpdateScheduleDialog(self.root, self.auth)


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
            try:
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

                messagebox.showinfo(_("common.success"),
                                  f"Schedule created successfully!\n\n"
                                  f"Course: {module_code}\n"
                                  f"Day: {day_var.get()}\n"
                                  f"Time: {start_time_var.get()} - {end_time_var.get()}\n"
                                  f"Session: {session_type_var.get()}\n"
                                  f"Semester: {current_semester} {current_year}")
                self.update_status("Course schedule created in course_schedule table")
                dialog.destroy()
            finally:
                conn.close()

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

            messagebox.showinfo(_("common.success"), "Schedule deleted successfully!")
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


def show_update_schedule_by_id(self, schedule_id):
    """Helper method to show update dialog for a specific schedule ID"""
    # For now, open the general update dialog
    # Can be enhanced later to pre-populate with schedule data
    self.show_update_schedule()
    messagebox.showinfo("Edit Schedule", f"Please select schedule ID: {schedule_id} from the list")


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


class CreateScheduleDialog:
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 18)]

    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Course Schedule")
        self.dialog.geometry("560x580")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self._ui()

    def _get_selected_days(self):
        return ','.join(self.DAY_NAMES[i] for i, v in enumerate(self._day_vars) if v.get())

    def _refresh_availability(self, *_args):
        """Reload rooms and instructors filtered by selected time/days/term."""
        semester = self.semester_var.get()
        year = self.year_var.get()
        start = self.start_var.get()
        end = self.end_var.get()
        days = self._get_selected_days()
        if not (semester and year and start and end):
            return
        self._load_rooms(semester, int(year), start, end, days)
        self._load_instructors(semester, int(year), start, end, days)

    def _ui(self):
        from datetime import datetime
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Course
        course_frame = ttk.LabelFrame(frm, text="Course", padding=10); course_frame.pack(fill=tk.X, pady=5)
        ttk.Label(course_frame, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(course_frame, width=50, state='readonly')
        self.course_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        self._load_courses()

        # Term
        term_frame = ttk.LabelFrame(frm, text="Term", padding=10); term_frame.pack(fill=tk.X, pady=5)
        ttk.Label(term_frame, text="Semester:").grid(row=0, column=0, sticky=tk.W)
        self.semester_var = tk.StringVar(value="Fall")
        sem_combo = ttk.Combobox(term_frame, textvariable=self.semester_var,
                     values=["Fall", "Spring", "Summer", "Winter"],
                     state='readonly', width=12)
        sem_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        sem_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        ttk.Label(term_frame, text="Year:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        current_year = datetime.now().year
        self.year_var = tk.StringVar(value=str(current_year))
        year_combo = ttk.Combobox(term_frame, textvariable=self.year_var,
                     values=[str(y) for y in range(current_year, current_year + 5)],
                     state='readonly', width=10)
        year_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        year_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        # Meeting details
        mtg = ttk.LabelFrame(frm, text="Meeting Details", padding=10); mtg.pack(fill=tk.X, pady=5)

        ttk.Label(mtg, text="Start Time:").grid(row=0, column=0, sticky=tk.W)
        self.start_var = tk.StringVar(value="09:00")
        start_combo = ttk.Combobox(mtg, textvariable=self.start_var, values=self.TIME_SLOTS,
                     state='readonly', width=10)
        start_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        start_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        ttk.Label(mtg, text="End Time:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.end_var = tk.StringVar(value="10:00")
        end_combo = ttk.Combobox(mtg, textvariable=self.end_var, values=self.TIME_SLOTS,
                     state='readonly', width=10)
        end_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        end_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        # Days — checkbuttons
        ttk.Label(mtg, text="Days:").grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
        days_frame = ttk.Frame(mtg)
        days_frame.grid(row=2, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        self._day_vars = []
        for day in self.DAY_SHORT:
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(days_frame, text=day, variable=var, command=self._refresh_availability)
            cb.pack(side=tk.LEFT, padx=2)
            self._day_vars.append(var)

        # Classroom — availability-filtered
        ttk.Label(mtg, text="Classroom:").grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(mtg, textvariable=self.room_var, width=45, state='readonly')
        self.room_combo.grid(row=3, column=1, sticky=tk.W, padx=6, pady=(6, 0))

        # Instructor — availability-filtered
        ttk.Label(mtg, text="Instructor:").grid(row=4, column=0, sticky=tk.W, pady=(6, 0))
        self.instructor_combo = ttk.Combobox(mtg, width=45, state='readonly')
        self.instructor_combo.grid(row=4, column=1, sticky=tk.W, padx=6, pady=(6, 0))

        # Initial load
        self._load_rooms(self.semester_var.get(), current_year, "09:00", "10:00", "")
        self._load_instructors(self.semester_var.get(), current_year, "09:00", "10:00", "")

        # Buttons
        btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=12)
        ttk.Button(btns, text="Create", command=self._create).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_courses(self):
        self._course_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute(
                "SELECT id, COALESCE(course_code, code), COALESCE(course_name, name) "
                "FROM courses "
                "WHERE LOWER(COALESCE(status, 'active')) = 'active' "
                "ORDER BY COALESCE(course_code, code)"
            )
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} - {r[2]}" for r in rows]
            self._course_id = {f"{r[1]} - {r[2]}": r[0] for r in rows}
            self.course_combo['values'] = vals
            if vals:
                self.course_combo.current(0)
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def _load_instructors(self, semester, year, start, end, days):
        self._instr_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
            if not cur.fetchone():
                self.instructor_combo['values'] = []; conn.close(); return

            # Find booked instructors at this slot
            booked_q = ("SELECT DISTINCT cs.instructor_id FROM course_schedule cs "
                        "WHERE cs.semester = ? AND cs.year = ? AND cs.start_time = ? AND cs.end_time = ? "
                        "AND cs.instructor_id IS NOT NULL")
            params = [semester, year, start, end]
            if days:
                day_list = [d.strip() for d in days.split(',')]
                day_conds = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
                booked_q += f" AND ({day_conds})"
                params.extend([f"%{d}%" for d in day_list])
            cur.execute(booked_q, params)
            booked = {r[0] for r in cur.fetchall()}

            cur.execute("SELECT id, first_name, last_name, department FROM instructors "
                        "WHERE LOWER(status) = 'active' ORDER BY last_name, first_name")
            rows = cur.fetchall(); conn.close()
            vals = []
            for r in rows:
                if r[0] not in booked:
                    label = f"{r[1]} {r[2]} — {r[3] or 'N/A'}"
                    vals.append(label)
                    self._instr_id[label] = r[0]
            self.instructor_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load instructors: {e}")

    def _load_rooms(self, semester, year, start, end, days):
        self._room_map = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()

            # Find booked rooms at this slot
            booked_q = ("SELECT DISTINCT cs.classroom FROM course_schedule cs "
                        "WHERE cs.semester = ? AND cs.year = ? AND cs.start_time = ? AND cs.end_time = ? "
                        "AND cs.classroom IS NOT NULL")
            params = [semester, year, start, end]
            if days:
                day_list = [d.strip() for d in days.split(',')]
                day_conds = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
                booked_q += f" AND ({day_conds})"
                params.extend([f"%{d}%" for d in day_list])
            cur.execute(booked_q, params)
            booked = {r[0] for r in cur.fetchall()}

            cur.execute("SELECT id, room_number, building, capacity, room_type "
                        "FROM rooms WHERE is_active = 1 AND LOWER(COALESCE(status,'available')) = 'available' "
                        "ORDER BY building, room_number")
            rows = cur.fetchall(); conn.close()
            vals = []
            for r in rows:
                if r[1] not in booked:
                    label = f"{r[1]} — {r[2] or 'N/A'} ({r[4] or 'N/A'}, cap: {r[3] or '?'})"
                    vals.append(label)
                    self._room_map[label] = r[1]
            self.room_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load rooms: {e}")

    def _create(self):
        course_key = self.course_combo.get().strip()
        if course_key not in self._course_id:
            messagebox.showwarning(_("common.validation"), "Please select a course."); return

        semester = self.semester_var.get().strip()
        year = int(self.year_var.get())
        course_id = self._course_id[course_key]

        instr_key = self.instructor_combo.get().strip()
        instructor_id = self._instr_id.get(instr_key) if instr_key else None

        days_str = self._get_selected_days() or None
        room_key = self.room_var.get().strip()
        classroom = self._room_map.get(room_key) if room_key else None
        start_time = self.start_var.get() or None
        end_time = self.end_var.get() or None

        if start_time and end_time and end_time <= start_time:
            messagebox.showwarning(_("common.validation"), "End time must be after start time."); return

        conn = None
        try:
            from datetime import datetime as dt
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cur = conn.cursor()

            # Check duplicate
            cur.execute("SELECT id FROM course_schedule WHERE course_id = ? AND semester = ? AND year = ?",
                        (course_id, semester, year))
            if cur.fetchone():
                messagebox.showerror("Duplicate", f"A schedule already exists for this course in {semester} {year}.")
                return

            cur.execute("""
            INSERT INTO course_schedule
            (course_id, instructor_id, semester, year, start_time, end_time, days_of_week, classroom, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (course_id, instructor_id, semester, year, start_time, end_time,
                  days_str, classroom, dt.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

            # Send email notification
            try:
                from education_system.post_18.university_system.modules.domain.academics.services.course_management.scheduling import _send_schedule_email
                _send_schedule_email(cur, course_id, semester, year, start_time, end_time,
                                    days_str, classroom, instructor_id, "Created")
            except Exception:
                pass  # Email is best-effort

            messagebox.showinfo(_("common.success"), "Schedule created successfully.")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to create schedule: {e}")
        finally:
            if conn:
                conn.close()


class ViewSchedulesDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("View Course Schedules")
        self.dialog.geometry("900x520")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui(); self._load()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("ID","Code","Name","Semester","Year","Time","Days","Room","Instructor")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("ID", width=50); self.tree.column("Code", width=90)
        self.tree.column("Name", width=240); self.tree.column("Semester", width=90)
        self.tree.column("Year", width=60); self.tree.column("Time", width=120)
        self.tree.column("Days", width=120); self.tree.column("Room", width=90)
        self.tree.column("Instructor", width=160)
        y = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); y.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.dialog); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Refresh", command=self._load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        from education_system.post_18.university_system.infrastructure.database.db import sqlite3
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()

            # Load from course_schedule table
            cur.execute("""
            SELECT cs.id,
                   c.course_code, c.course_name,
                   cs.semester, cs.year,
                   COALESCE(cs.start_time,'') || CASE WHEN cs.end_time IS NOT NULL THEN '-'||cs.end_time ELSE '' END as time_slot,
                   COALESCE(cs.days_of_week,''), COALESCE(cs.classroom,''),
                   COALESCE(i.first_name||' '||i.last_name,'')
            FROM course_schedule cs
            JOIN courses c ON cs.course_id = c.id
            LEFT JOIN instructors i ON cs.instructor_id = i.id
            ORDER BY cs.year DESC, cs.semester, c.course_code
            """)
            rows = list(cur.fetchall())

            # Also load from module_schedule table
            cur.execute("""
            SELECT ms.id,
                   ms.module_code,
                   c.course_name,
                   '', '',
                   COALESCE(ms.start_time,'') || CASE WHEN ms.end_time IS NOT NULL THEN '-'||ms.end_time ELSE '' END as time_slot,
                   COALESCE(ms.day_of_week,''),
                   '',
                   COALESCE(i.first_name||' '||i.last_name,'')
            FROM module_schedule ms
            LEFT JOIN courses c ON ms.module_code = c.course_code
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            ORDER BY ms.module_code
            """)
            module_rows = cur.fetchall()
            rows.extend(module_rows)

            conn.close()
            for i in self.tree.get_children(): self.tree.delete(i)
            for r in rows: self.tree.insert("", tk.END, values=r)
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load schedules: {e}")


class UpdateScheduleDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Course Schedule")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.focus_set()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Show existing schedules
        self.schedule_tree = ttk.Treeview(main_frame, columns=("ID", "Code", "Name", "Semester", "Year", "Time"), show="headings")
        for col in ["ID", "Code", "Name", "Semester", "Year", "Time"]:
            self.schedule_tree.heading(col, text=col)
        self.schedule_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Update Selected", command=self.update_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_schedules).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

        self.load_schedules()

    def load_schedules(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
            SELECT cs.id, c.course_code, c.course_name, cs.semester, cs.year,
                   COALESCE(cs.start_time || '-' || cs.end_time, 'TBA') as time_slot
            FROM course_schedule cs
            JOIN courses c ON cs.course_id = c.id
            ORDER BY cs.year DESC, cs.semester, c.course_code
            """)

            schedules = cursor.fetchall()

            for item in self.schedule_tree.get_children():
                self.schedule_tree.delete(item)

            for schedule in schedules:
                self.schedule_tree.insert("", tk.END, values=schedule)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load schedules: {e}")

    def update_schedule(self):
        selection = self.schedule_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a schedule to update.")
            return

        schedule_data = self.schedule_tree.item(selection[0])['values']
        schedule_id = schedule_data[0]

        # Open update form dialog
        UpdateScheduleFormDialog(self.dialog, schedule_id, self.auth)
        self.load_schedules()


class UpdateScheduleFormDialog:
    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 18)]

    def __init__(self, parent, schedule_id, auth):
        self.parent = parent
        self.schedule_id = schedule_id
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Update Schedule Details")
        self.dialog.geometry("560x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.load_current_data()
        if hasattr(self, 'current_data') and self.current_data:
            self.create_widgets()
        self.dialog.focus_set()

    def load_current_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM course_schedule WHERE id = ?", (self.schedule_id,))
            self.current_data = cursor.fetchone()
            # (id, course_id, semester, year, start_time, end_time, days_of_week, classroom, instructor_id, created_at)

            # Get course info
            if self.current_data:
                cursor.execute("SELECT course_code, course_name FROM courses WHERE id = ?", (self.current_data[1],))
                cr = cursor.fetchone()
                self.course_label = f"{cr[0]} - {cr[1]}" if cr else "Unknown"
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load schedule: {e}")
            self.dialog.destroy()

    def _get_selected_days(self):
        return ','.join(self.DAY_NAMES[i] for i, v in enumerate(self._day_vars) if v.get())

    def _refresh_availability(self, *_args):
        start = self.start_var.get()
        end = self.end_var.get()
        days = self._get_selected_days()
        semester = self.current_data[2]
        year = self.current_data[3]
        if not (start and end):
            return
        self._load_rooms(semester, year, start, end, days)
        self._load_instructors(semester, year, start, end, days)

    def create_widgets(self):
        frm = ttk.Frame(self.dialog)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Course info (read-only)
        info_frame = ttk.LabelFrame(frm, text="Course", padding=10)
        info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(info_frame, text=f"{self.course_label}  —  {self.current_data[2]} {self.current_data[3]}",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        # Meeting details
        mtg = ttk.LabelFrame(frm, text="Meeting Details", padding=10)
        mtg.pack(fill=tk.X, pady=5)

        cur_start = self.current_data[4] or ""
        cur_end = self.current_data[5] or ""
        cur_days = self.current_data[6] or ""
        cur_room = self.current_data[7] or ""
        self._orig_instructor_id = self.current_data[8]

        # Start time
        ttk.Label(mtg, text="Start Time:").grid(row=0, column=0, sticky=tk.W)
        self.start_var = tk.StringVar(value=cur_start if cur_start in self.TIME_SLOTS else "09:00")
        start_combo = ttk.Combobox(mtg, textvariable=self.start_var, values=self.TIME_SLOTS,
                                   state='readonly', width=10)
        start_combo.grid(row=0, column=1, sticky=tk.W, padx=6)
        start_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        # End time
        ttk.Label(mtg, text="End Time:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.end_var = tk.StringVar(value=cur_end if cur_end in self.TIME_SLOTS else "10:00")
        end_combo = ttk.Combobox(mtg, textvariable=self.end_var, values=self.TIME_SLOTS,
                                 state='readonly', width=10)
        end_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        end_combo.bind('<<ComboboxSelected>>', self._refresh_availability)

        # Days — checkbuttons pre-set from current
        ttk.Label(mtg, text="Days:").grid(row=2, column=0, sticky=tk.W, pady=(6, 0))
        days_frame = ttk.Frame(mtg)
        days_frame.grid(row=2, column=1, sticky=tk.W, padx=6, pady=(6, 0))
        self._day_vars = []
        for i, day in enumerate(self.DAY_SHORT):
            var = tk.BooleanVar(value=self.DAY_NAMES[i] in cur_days)
            cb = ttk.Checkbutton(days_frame, text=day, variable=var, command=self._refresh_availability)
            cb.pack(side=tk.LEFT, padx=2)
            self._day_vars.append(var)

        # Classroom — availability-filtered
        ttk.Label(mtg, text="Classroom:").grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(mtg, textvariable=self.room_var, width=45, state='readonly')
        self.room_combo.grid(row=3, column=1, sticky=tk.W, padx=6, pady=(6, 0))

        # Instructor — availability-filtered
        ttk.Label(mtg, text="Instructor:").grid(row=4, column=0, sticky=tk.W, pady=(6, 0))
        self.instructor_combo = ttk.Combobox(mtg, width=45, state='readonly')
        self.instructor_combo.grid(row=4, column=1, sticky=tk.W, padx=6, pady=(6, 0))

        # Initial load with availability filtering
        semester = self.current_data[2]
        year = self.current_data[3]
        self._load_rooms(semester, year, self.start_var.get(), self.end_var.get(), cur_days)
        self._load_instructors(semester, year, self.start_var.get(), self.end_var.get(), cur_days)

        # Pre-select current room if it's in the list
        if cur_room:
            for val in self.room_combo['values']:
                if val.startswith(cur_room + " ") or val.startswith(cur_room + "\u2009"):
                    self.room_var.set(val)
                    break

        # Buttons
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, pady=12)
        ttk.Button(btns, text="Update", command=self.update_schedule).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_rooms(self, semester, year, start, end, days):
        self._room_map = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            booked_q = ("SELECT DISTINCT cs.classroom FROM course_schedule cs "
                        "WHERE cs.semester = ? AND cs.year = ? AND cs.start_time = ? AND cs.end_time = ? "
                        "AND cs.classroom IS NOT NULL AND cs.id != ?")
            params = [semester, year, start, end, self.schedule_id]
            if days:
                day_list = [d.strip() for d in days.split(',')]
                day_conds = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
                booked_q += f" AND ({day_conds})"
                params.extend([f"%{d}%" for d in day_list])
            cur.execute(booked_q, params)
            booked = {r[0] for r in cur.fetchall()}

            cur.execute("SELECT id, room_number, building, capacity, room_type "
                        "FROM rooms WHERE is_active = 1 AND LOWER(COALESCE(status,'available')) = 'available' "
                        "ORDER BY building, room_number")
            rows = cur.fetchall(); conn.close()
            vals = []
            for r in rows:
                if r[1] not in booked:
                    label = f"{r[1]} — {r[2] or 'N/A'} ({r[4] or 'N/A'}, cap: {r[3] or '?'})"
                    vals.append(label)
                    self._room_map[label] = r[1]
            self.room_combo['values'] = vals
        except sqlite3.Error:
            pass

    def _load_instructors(self, semester, year, start, end, days):
        self._instr_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            booked_q = ("SELECT DISTINCT cs.instructor_id FROM course_schedule cs "
                        "WHERE cs.semester = ? AND cs.year = ? AND cs.start_time = ? AND cs.end_time = ? "
                        "AND cs.instructor_id IS NOT NULL AND cs.id != ?")
            params = [semester, year, start, end, self.schedule_id]
            if days:
                day_list = [d.strip() for d in days.split(',')]
                day_conds = " OR ".join(["cs.days_of_week LIKE ?" for _ in day_list])
                booked_q += f" AND ({day_conds})"
                params.extend([f"%{d}%" for d in day_list])
            cur.execute(booked_q, params)
            booked = {r[0] for r in cur.fetchall()}

            cur.execute("SELECT id, first_name, last_name, department FROM instructors "
                        "WHERE LOWER(status) = 'active' ORDER BY last_name, first_name")
            rows = cur.fetchall(); conn.close()
            vals = ["(None — remove instructor)"]
            self._instr_id[vals[0]] = None
            for r in rows:
                if r[0] not in booked:
                    label = f"{r[1]} {r[2]} — {r[3] or 'N/A'}"
                    vals.append(label)
                    self._instr_id[label] = r[0]
            self.instructor_combo['values'] = vals

            # Pre-select current instructor
            if self._orig_instructor_id:
                for v in vals:
                    if self._instr_id.get(v) == self._orig_instructor_id:
                        self.instructor_combo.set(v)
                        break
        except sqlite3.Error:
            pass

    def update_schedule(self):
        new_start = self.start_var.get() or None
        new_end = self.end_var.get() or None
        new_days = self._get_selected_days() or None
        room_key = self.room_var.get().strip()
        new_classroom = self._room_map.get(room_key) if room_key else None
        instr_key = self.instructor_combo.get().strip()
        new_instructor_id = self._instr_id.get(instr_key, self._orig_instructor_id)

        if new_start and new_end and new_end <= new_start:
            messagebox.showwarning(_("common.validation"), "End time must be after start time.")
            return

        # Get original values for comparison
        orig_start = self.current_data[4]
        orig_end = self.current_data[5]
        orig_days = self.current_data[6]
        orig_room = self.current_data[7]
        orig_instr = self._orig_instructor_id

        if (new_start == orig_start and new_end == orig_end and new_days == orig_days
                and new_classroom == orig_room and new_instructor_id == orig_instr):
            messagebox.showinfo("No Changes", "No changes were made to the schedule.")
            return

        # Build change summary
        changes = []
        if new_start != orig_start:
            changes.append(f"Start time: {orig_start or 'TBA'} → {new_start or 'TBA'}")
        if new_end != orig_end:
            changes.append(f"End time: {orig_end or 'TBA'} → {new_end or 'TBA'}")
        if new_days != orig_days:
            changes.append(f"Days: {orig_days or 'TBA'} → {new_days or 'TBA'}")
        if new_classroom != orig_room:
            changes.append(f"Classroom: {orig_room or 'TBA'} → {new_classroom or 'TBA'}")
        if new_instructor_id != orig_instr:
            changes.append("Instructor changed")

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cur = conn.cursor()

            cur.execute("""
            UPDATE course_schedule
            SET start_time = ?, end_time = ?, days_of_week = ?, classroom = ?, instructor_id = ?
            WHERE id = ?
            """, (new_start, new_end, new_days, new_classroom, new_instructor_id, self.schedule_id))

            conn.commit()

            # Send email notifications
            change_details = "\nChanges:\n" + "\n".join(f"  - {c}" for c in changes)
            course_id = self.current_data[1]
            semester = self.current_data[2]
            year = self.current_data[3]
            try:
                from education_system.post_18.university_system.modules.domain.academics.services.course_management.scheduling import _send_schedule_email
                # Notify old instructor if unassigned
                if orig_instr and orig_instr != new_instructor_id:
                    _send_schedule_email(cur, course_id, semester, year, new_start, new_end,
                                        new_days, new_classroom, orig_instr, "Updated (Unassigned)", change_details)
                # Notify current/new instructor
                if new_instructor_id:
                    _send_schedule_email(cur, course_id, semester, year, new_start, new_end,
                                        new_days, new_classroom, new_instructor_id, "Updated", change_details)
            except Exception:
                pass  # Email is best-effort

            messagebox.showinfo(_("common.success"),
                                "Schedule updated successfully!\n\nChanges:\n" + "\n".join(f"• {c}" for c in changes))
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to update schedule: {e}")
        finally:
            if conn:
                conn.close()
