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


def show_add_waitlist(self):
    """Open dialog to add a student to a course waitlist"""
    AddToWaitlistDialog(self.root, self.auth)


def show_view_waitlists(self):
    """Open dialog to view course waitlists"""
    ViewWaitlistsDialog(self.root, self.auth)


def show_process_waitlist(self):
    """Show process waitlist dialog"""
    ProcessWaitlistDialog(self.root, self.auth)


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

    # Configure grid columns
    student_frame.columnconfigure(1, weight=1)

    ttk.Label(student_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
    student_id_var = tk.StringVar()
    student_id_entry = ttk.Entry(student_frame, textvariable=student_id_var, width=20)
    student_id_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

    # Add lookup button
    def lookup_student():
        """Open student lookup dialog"""
        lookup_dialog = tk.Toplevel(dialog)
        lookup_dialog.title("Lookup Student")
        lookup_dialog.geometry("600x400")
        lookup_dialog.transient(dialog)
        lookup_dialog.grab_set()

        lookup_frame = ttk.Frame(lookup_dialog, padding=10)
        lookup_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(lookup_frame, text="Search for Student", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Search field
        search_frame = ttk.Frame(lookup_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search (ID, Name):").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Student list
        columns = ('ID', 'Name', 'Email')
        tree = ttk.Treeview(lookup_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=180)
        tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(lookup_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        def search_students():
            """Search and display students"""
            for item in tree.get_children():
                tree.delete(item)

            search_text = search_var.get().strip()
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                if search_text:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email_address LIKE ?
                        ORDER BY student_id
                        LIMIT 100
                    """, (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"))
                else:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        ORDER BY student_id
                        LIMIT 100
                    """)

                students = cursor.fetchall()
                for student in students:
                    tree.insert('', tk.END, values=student)

                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to search students: {str(e)}")

        def select_student():
            """Select the highlighted student"""
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                student_id = item['values'][0]
                student_id_var.set(student_id)
                lookup_dialog.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select a student")

        ttk.Button(search_frame, text="Search", command=search_students).pack(side=tk.LEFT, padx=5)

        # Button frame
        btn_frame = ttk.Frame(lookup_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Select", command=select_student).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Initial load
        search_students()

        # Bind double-click
        tree.bind('<Double-1>', lambda e: select_student())

    ttk.Button(student_frame, text="Lookup", command=lookup_student).grid(row=0, column=2, sticky=tk.W, pady=5, padx=5)

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
                WHERE COALESCE(current_enrollment, 0) >= COALESCE(max_enrollment, 0)
                  AND LOWER(COALESCE(status, 'active')) = 'active'
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

        conn = None
        try:
            course_id = int(course_var.get().split("ID: ")[1].rstrip(")"))
            student_id = student_id_var.get().strip()

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Validate student exists in database
            cursor.execute("SELECT student_id, first_name, last_name FROM students WHERE student_id = ?", (student_id,))
            student_record = cursor.fetchone()

            if not student_record:
                messagebox.showerror("Invalid Student",
                                   f"Student ID '{student_id}' does not exist in the database.\n\n"
                                   f"Please enter a valid student ID.")
                return

            student_name = f"{student_record[1]} {student_record[2]}"

            # Check if already on waitlist
            cursor.execute("""
                SELECT id FROM course_waitlist
                WHERE course_id = ? AND student_id = ?
            """, (course_id, student_id))

            if cursor.fetchone():
                messagebox.showerror("Duplicate", f"Student {student_name} ({student_id}) is already on the waitlist for this course")
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

            messagebox.showinfo(_("common.success"),
                              f"Student {student_name} ({student_id}) added to waitlist at position {position}")
            self.update_status(f"Added student {student_name} ({student_id}) to waitlist")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to add to waitlist: {e}")
        finally:
            if conn:
                conn.close()

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


class AddToWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add to Course Waitlist")
        self.dialog.geometry("420x240")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(frm, text="Course:").grid(row=0, column=0, sticky=tk.W)
        self.course_combo = ttk.Combobox(frm, width=45); self.course_combo.grid(row=0, column=1, sticky=tk.W, padx=6, columnspan=2)
        ttk.Label(frm, text="Student ID:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
        self.student_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.student_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=6, pady=(8,0))
        ttk.Button(frm, text="Lookup", command=self._lookup_student).grid(row=1, column=2, sticky=tk.W, padx=6, pady=(8,0))

        self._load_courses()
        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=12)
        ttk.Button(btns, text="Add", command=self._add).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_courses(self):
        from university_system.infrastructure.database.db import sqlite3
        self._course_id = {}
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            cur.execute("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
            rows = cur.fetchall(); conn.close()
            vals = [f"{r[1]} - {r[2]}" for r in rows]
            self._course_id = {f"{r[1]} - {r[2]}": r[0] for r in rows}
            self.course_combo['values'] = vals
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load courses: {e}")

    def _lookup_student(self):
        """Open student lookup dialog"""
        lookup_dialog = tk.Toplevel(self.dialog)
        lookup_dialog.title("Lookup Student")
        lookup_dialog.geometry("600x400")
        lookup_dialog.transient(self.dialog)
        lookup_dialog.grab_set()

        lookup_frame = ttk.Frame(lookup_dialog, padding=10)
        lookup_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(lookup_frame, text="Search for Student", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Search field
        search_frame = ttk.Frame(lookup_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search (ID, Name):").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Student list
        columns = ('ID', 'Name', 'Email')
        tree = ttk.Treeview(lookup_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=180)
        tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(lookup_frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        def search_students():
            """Search and display students"""
            for item in tree.get_children():
                tree.delete(item)

            search_text = search_var.get().strip()
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                if search_text:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email_address LIKE ?
                        ORDER BY student_id
                        LIMIT 100
                    """, (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%", f"%{search_text}%"))
                else:
                    cursor.execute("""
                        SELECT student_id, first_name || ' ' || last_name, email_address
                        FROM students
                        ORDER BY student_id
                        LIMIT 100
                    """)

                students = cursor.fetchall()
                for student in students:
                    tree.insert('', tk.END, values=student)

                conn.close()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to search students: {str(e)}")

        def select_student():
            """Select the highlighted student"""
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                student_id = item['values'][0]
                self.student_var.set(student_id)
                lookup_dialog.destroy()
            else:
                messagebox.showwarning("No Selection", "Please select a student")

        ttk.Button(search_frame, text="Search", command=search_students).pack(side=tk.LEFT, padx=5)

        # Button frame
        btn_frame = ttk.Frame(lookup_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Select", command=select_student).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=lookup_dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Initial load
        search_students()

        # Bind double-click
        tree.bind('<Double-1>', lambda e: select_student())

    def _add(self):
        from university_system.infrastructure.database.db import sqlite3
        course_key = self.course_combo.get().strip()
        student_id = self.student_var.get().strip()
        if course_key not in self._course_id:
            messagebox.showwarning(_("common.validation"), "Select a course."); return
        if not student_id:
            messagebox.showwarning(_("common.validation"), "Enter a student ID."); return
        course_id = self._course_id[course_key]

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=10.0)
            conn.execute("PRAGMA busy_timeout = 10000")
            cur = conn.cursor()
            # ensure waitlist table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS course_waitlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                status TEXT DEFAULT 'Waiting',
                FOREIGN KEY(course_id) REFERENCES courses(id),
                UNIQUE(course_id, student_id)
            )
            """)
            cur.execute("SELECT COALESCE(MAX(position),0) + 1 FROM course_waitlist WHERE course_id = ?", (course_id,))
            pos = cur.fetchone()[0] or 1
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("INSERT INTO course_waitlist (course_id, student_id, position, added_at) VALUES (?, ?, ?, ?)",
                        (course_id, student_id, pos, timestamp))
            conn.commit()
            messagebox.showinfo(_("common.success"), f"Added student {student_id} to waitlist (position {pos}).")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to add to waitlist: {e}")
        finally:
            if conn:
                conn.close()


class ViewWaitlistsDialog:
    def __init__(self, parent, auth):
        self.parent = parent; self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("View Course Waitlists")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent); self.dialog.grab_set()
        self._ui(); self._load()

    def _ui(self):
        frm = ttk.Frame(self.dialog); frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        cols = ("ID","Code","Name","Student ID","Position","Status","Added")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings")
        for c in cols: self.tree.heading(c, text=c)
        self.tree.column("ID", width=60); self.tree.column("Code", width=90)
        self.tree.column("Name", width=240); self.tree.column("Student ID", width=120)
        self.tree.column("Position", width=80); self.tree.column("Status", width=90)
        self.tree.column("Added", width=140)
        y = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); y.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.dialog); btns.pack(fill=tk.X, padx=10, pady=8)
        ttk.Button(btns, text="Refresh", command=self._load).pack(side=tk.LEFT)
        ttk.Button(btns, text="Remove Selected", command=self._remove).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load(self):
        from university_system.infrastructure.database.db import sqlite3
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cur = conn.cursor()
                cur.execute("""
                SELECT w.id, c.course_code, c.course_name, w.student_id, w.position, w.status, w.added_at
                FROM course_waitlist w
                JOIN courses c ON w.course_id = c.id
                ORDER BY c.course_code, w.position
                """)
                rows = cur.fetchall()
            for i in self.tree.get_children(): self.tree.delete(i)
            for r in rows: self.tree.insert("", tk.END, values=r)
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load waitlists: {e}")

    def _remove(self):
        from university_system.infrastructure.database.db import sqlite3
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Pick a waitlist entry to remove."); return
        row = self.tree.item(sel[0])['values']; waitlist_id = row[0]
        if not messagebox.askyesno(_("common.confirm"), "Remove selected waitlist entry?"): return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH)); cur = conn.cursor()
            # capture course to fix positions
            cur.execute("SELECT course_id, position FROM course_waitlist WHERE id = ?", (waitlist_id,))
            r = cur.fetchone()
            if not r:
                conn.close(); self._load(); return
            course_id, pos = r
            cur.execute("DELETE FROM course_waitlist WHERE id = ?", (waitlist_id,))
            # close the gap in positions for remaining 'Waiting'
            cur.execute("""
                UPDATE course_waitlist
                SET position = position - 1
                WHERE course_id = ? AND status = 'Waiting' AND position > ?
            """, (course_id, pos))
            conn.commit(); conn.close()
            self._load()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to remove entry: {e}")


class ProcessWaitlistDialog:
    def __init__(self, parent, auth):
        self.parent = parent
        self.auth = auth
        self.result = None
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Course Waitlists")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
        self.load_waitlist_data()
        self.dialog.focus_set()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Label(main_frame, text="Courses with Available Spots and Waitlists", 
                 font=("Arial", 12, "bold")).pack(pady=10)
        
        # Course waitlist display
        columns = ("Course ID", "Code", "Name", "Available", "Waitlist Count")
        self.waitlist_tree = ttk.Treeview(main_frame, columns=columns, show="headings")
        
        for col in columns:
            self.waitlist_tree.heading(col, text=col)
            if col == "Course ID":
                self.waitlist_tree.column(col, width=80)
            elif col == "Code":
                self.waitlist_tree.column(col, width=80)
            elif col == "Name":
                self.waitlist_tree.column(col, width=250)
            else:
                self.waitlist_tree.column(col, width=100)
        
        self.waitlist_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Process Selected", command=self.process_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process All", command=self.process_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_waitlist_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def load_waitlist_data(self):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            cursor.execute("""
            SELECT c.id, c.course_code, c.course_name,
                   (COALESCE(c.max_enrollment, 0) - COALESCE(c.current_enrollment, 0)) as available_spots,
                   COUNT(w.id) as waitlist_count
            FROM courses c
            LEFT JOIN course_waitlist w ON c.id = w.course_id AND LOWER(w.status) = 'waiting'
            WHERE LOWER(COALESCE(c.status, 'active')) = 'active'
              AND COALESCE(c.current_enrollment, 0) < COALESCE(c.max_enrollment, 0)
            GROUP BY c.id, c.course_code, c.course_name, c.current_enrollment, c.max_enrollment
            HAVING waitlist_count > 0
            ORDER BY available_spots DESC, waitlist_count DESC
            """)
            
            courses = cursor.fetchall()
            
            for item in self.waitlist_tree.get_children():
                self.waitlist_tree.delete(item)
            
            for course in courses:
                self.waitlist_tree.insert("", tk.END, values=course)
            
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), f"Failed to load waitlist data: {e}")
    
    def process_selected(self):
        selection = self.waitlist_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), "Please select a course to process.")
            return
        
        course_data = self.waitlist_tree.item(selection[0])['values']
        course_id = course_data[0]
        
        if self.process_course_waitlist(course_id):
            self.load_waitlist_data()
    
    def process_all(self):
        if messagebox.askyesno(_("common.confirm"), "Process all waitlists? This will enroll students from waitlists where spots are available."):
            processed = 0
            for item in self.waitlist_tree.get_children():
                course_data = self.waitlist_tree.item(item)['values']
                course_id = course_data[0]
                if self.process_course_waitlist(course_id, show_messages=False):
                    processed += 1
            
            messagebox.showinfo("Complete", f"Processed waitlists for {processed} courses.")
            self.load_waitlist_data()
    
    def process_course_waitlist(self, course_id, show_messages=True):
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            # Get course info and available spots
            cursor.execute("""
            SELECT course_code, course_name, current_enrollment, max_enrollment
            FROM courses WHERE id = ?
            """, (course_id,))
            
            course_info = cursor.fetchone()
            if not course_info:
                return False
            
            code, name, current_enrolled, max_enrolled = course_info
            available_spots = max_enrolled - current_enrolled
            
            if available_spots <= 0:
                if show_messages:
                    messagebox.showwarning("No Spots", f"No available spots in {code}")
                return False
            
            # Get waitlist students
            cursor.execute("""
            SELECT id, student_id FROM course_waitlist 
            WHERE course_id = ? AND status = 'Waiting'
            ORDER BY position
            LIMIT ?
            """, (course_id, available_spots))
            
            waitlist_students = cursor.fetchall()
            
            if not waitlist_students:
                return False
            
            # Process each student
            enrolled_count = 0
            for waitlist_id, student_id in waitlist_students:
                # Update waitlist status
                cursor.execute("UPDATE course_waitlist SET status = 'Enrolled' WHERE id = ?", (waitlist_id,))
                enrolled_count += 1
            
            # Update course enrollment
            cursor.execute("""
            UPDATE courses SET current_enrollment = current_enrollment + ?
            WHERE id = ?
            """, (enrolled_count, course_id))
            
            # Update remaining waitlist positions
            cursor.execute("""
            UPDATE course_waitlist 
            SET position = position - ?
            WHERE course_id = ? AND status = 'Waiting'
            """, (enrolled_count, course_id))
            
            conn.commit()
            conn.close()
            
            if show_messages:
                messagebox.showinfo(_("common.success"), f"Enrolled {enrolled_count} students from waitlist for {code}")
            
            return True
            
        except sqlite3.Error as e:
            if show_messages:
                messagebox.showerror(_("common.database_error"), f"Failed to process waitlist: {e}")
            return False
