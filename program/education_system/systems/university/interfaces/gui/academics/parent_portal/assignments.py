from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.interfaces.gui.academics.parent_portal.base import ParentPortalGUI

def view_child_assignments(self, child):
    """View assignments for a specific child"""
    self.clear_content()
    self.update_status(f"Viewing assignments for {child[1]} {child[3]}")

    title = ttk.Label(self.content_frame, text=f"Assignments for {child[1]} {child[3]}",
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)

    student_id = child[0]

    # Create notebook for different assignment categories
    notebook = ttk.Notebook(self.content_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Upcoming assignments tab
    upcoming_frame = ttk.Frame(notebook)
    notebook.add(upcoming_frame, text="Upcoming")
    upcoming_tree = self.create_assignments_tree(upcoming_frame)

    # Overdue assignments tab
    overdue_frame = ttk.Frame(notebook)
    notebook.add(overdue_frame, text="Overdue")
    overdue_tree = self.create_assignments_tree(overdue_frame)

    # Completed assignments tab
    completed_frame = ttk.Frame(notebook)
    notebook.add(completed_frame, text="Completed")
    completed_tree = self.create_assignments_tree(completed_frame)

    # Load assignments from database
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # Get student's enrolled modules
        cursor.execute("""
            SELECT DISTINCT module_code FROM student_modules WHERE student_id = ?
        """, (student_id,))
        enrolled_modules = [m[0] for m in cursor.fetchall()]

        if enrolled_modules:
            placeholders = ','.join(['?' for _ in enrolled_modules])

            # Upcoming assignments (not submitted yet, due date in future)
            cursor.execute("""
                SELECT a.module_code, a.title, a.due_date, 'Pending', a.max_marks
                FROM assignments a
                LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id AND sub.student_id = ?
                WHERE a.module_code IN (""" + placeholders + """)
                  AND a.is_active = 1
                  AND a.due_date >= ?
                  AND sub.id IS NULL
                ORDER BY a.due_date ASC
            """, (student_id, *enrolled_modules, today))

            for assignment in cursor.fetchall():
                upcoming_tree.insert('', tk.END, values=assignment)

            # Overdue assignments (not submitted, due date passed)
            cursor.execute("""
                SELECT a.module_code, a.title, a.due_date, 'Overdue', a.max_marks
                FROM assignments a
                LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id AND sub.student_id = ?
                WHERE a.module_code IN (""" + placeholders + """)
                  AND a.is_active = 1
                  AND a.due_date < ?
                  AND sub.id IS NULL
                ORDER BY a.due_date DESC
            """, (student_id, *enrolled_modules, today))

            for assignment in cursor.fetchall():
                overdue_tree.insert('', tk.END, values=assignment)

            # Completed assignments (submitted)
            cursor.execute("""
                SELECT a.module_code, a.title, a.due_date, sub.status, COALESCE(sub.grade, 'Pending')
                FROM assignments a
                INNER JOIN assignment_submissions sub ON a.id = sub.assignment_id AND sub.student_id = ?
                WHERE a.module_code IN (""" + placeholders + """)
                ORDER BY sub.submission_date DESC
            """, (student_id, *enrolled_modules))

            for assignment in cursor.fetchall():
                completed_tree.insert('', tk.END, values=assignment)
        else:
            upcoming_tree.insert('', tk.END, values=('N/A', 'No enrolled modules found', '', '', ''))

        conn.close()

    except Exception as e:
        upcoming_tree.insert('', tk.END, values=('Error', str(e), '', '', ''))

    # Back button
    back_btn = ttk.Button(self.content_frame, text="← Back", command=self.show_children)
    back_btn.pack(pady=10)
ParentPortalGUI.view_child_assignments = view_child_assignments

def create_assignments_tree(self, parent):
    """Create a tree widget for assignments"""
    columns = ('Module', 'Assignment', 'Due Date', 'Status', 'Grade/Priority')
    tree = ttk.Treeview(parent, columns=columns, show='headings', height=10)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)

    scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    return tree
ParentPortalGUI.create_assignments_tree = create_assignments_tree

def show_timetable_interface(self):
    """Show timetable interface"""
    self.clear_content()
    self.update_status("Timetable")

    title = ttk.Label(self.content_frame, text="Student Timetables", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Timetable display frame
    timetable_frame = ttk.LabelFrame(self.content_frame, text="Weekly Timetable", padding=15)
    timetable_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_timetable():
        # Clear existing widgets
        for widget in timetable_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(timetable_frame, text="Please select a child").pack(pady=20)
            return

        # Extract student ID
        student_id = selected_child.split("ID: ")[1].rstrip(")")

        # Create timetable grid
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        time_slots = ["08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
                     "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00"]

        # Create header
        ttk.Label(timetable_frame, text="Time", font=('Arial', 10, 'bold'),
                 relief=tk.RIDGE, width=15).grid(row=0, column=0, sticky='nsew', padx=1, pady=1)

        for col, day in enumerate(days, start=1):
            ttk.Label(timetable_frame, text=day, font=('Arial', 10, 'bold'),
                     relief=tk.RIDGE).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # Try to load actual timetable from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            schedule = []

            # Try multiple sources for timetable data

            # 1. First try student_timetables table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_timetables'")
            if cursor.fetchone():
                cursor.execute("""
                    SELECT st.day_of_week, st.time_slot,
                           COALESCE(m.module_name, st.module_code) as subject,
                           COALESCE(st.room, 'TBA') as room,
                           COALESCE(i.first_name || ' ' || i.last_name, 'TBA') as instructor
                    FROM student_timetables st
                    LEFT JOIN modules m ON st.module_code = m.module_code
                    LEFT JOIN instructors i ON st.instructor_id = i.id
                    WHERE st.student_id = ?
                    ORDER BY st.day_of_week, st.time_slot
                """, (student_id,))
                schedule = cursor.fetchall()

            # 2. If no data, try module_schedule via enrollments
            if not schedule:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'")
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT ms.day_of_week, ms.start_time || '-' || ms.end_time as time_slot,
                               COALESCE(m.module_name, ms.module_code) as subject,
                               COALESCE(r.room_name, r.room_number, 'TBA') as room,
                               COALESCE(i.first_name || ' ' || i.last_name, 'TBA') as instructor
                        FROM module_schedule ms
                        LEFT JOIN modules m ON ms.module_code = m.module_code
                        LEFT JOIN rooms r ON ms.room_id = r.id
                        LEFT JOIN instructors i ON ms.instructor_id = i.id
                        INNER JOIN student_modules sm ON sm.module_code = ms.module_code
                        WHERE sm.student_id = ?
                        ORDER BY ms.day_of_week, ms.start_time
                    """, (student_id,))
                    schedule = cursor.fetchall()

            # 3. If still no data via enrollments, show all module schedules for admin
            if not schedule and self.is_admin():
                cursor.execute("""
                    SELECT ms.day_of_week, ms.start_time || '-' || ms.end_time as time_slot,
                           COALESCE(m.module_name, ms.module_code) as subject,
                           COALESCE(r.room_name, r.room_number, 'TBA') as room,
                           COALESCE(i.first_name || ' ' || i.last_name, 'TBA') as instructor
                    FROM module_schedule ms
                    LEFT JOIN modules m ON ms.module_code = m.module_code
                    LEFT JOIN rooms r ON ms.room_id = r.id
                    LEFT JOIN instructors i ON ms.instructor_id = i.id
                    ORDER BY ms.day_of_week, ms.start_time
                    LIMIT 50
                """)
                schedule = cursor.fetchall()

            schedule_dict = {}
            for entry in schedule:
                day = entry[0]
                time_slot = entry[1]
                # Normalize time slot format
                if time_slot and ':' in time_slot:
                    key = (day, time_slot)
                    schedule_dict[key] = f"{entry[2]}\n{entry[3]}\n{entry[4]}"

            # Populate timetable
            for row, time_slot in enumerate(time_slots, start=1):
                ttk.Label(timetable_frame, text=time_slot, font=('Arial', 9),
                         relief=tk.RIDGE, width=15).grid(row=row, column=0, sticky='nsew', padx=1, pady=1)

                for col, day in enumerate(days, start=1):
                    # Try to match time slots flexibly
                    cell_text = "-"
                    for sched_key, sched_val in schedule_dict.items():
                        if sched_key[0] == day and time_slot.split('-')[0] in str(sched_key[1]):
                            cell_text = sched_val
                            break
                    cell = ttk.Label(timetable_frame, text=cell_text, font=('Arial', 8),
                                   relief=tk.SUNKEN, anchor='center')
                    cell.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)

            if not schedule:
                ttk.Label(timetable_frame, text="No timetable entries found for this student.\nCheck enrollments or contact administration.",
                         font=('Arial', 11)).grid(row=1, column=0, columnspan=6, pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(timetable_frame, text=f"Error loading timetable: {str(e)}").grid(
                row=1, column=0, columnspan=6, pady=20)

        # Configure grid weights
        for i in range(9):
            timetable_frame.rowconfigure(i, weight=1)
        for i in range(6):
            timetable_frame.columnconfigure(i, weight=1)

    ttk.Button(child_frame, text="Load Timetable", command=load_timetable).pack(side=tk.LEFT, padx=5)

    # Load initial timetable
    load_timetable()
ParentPortalGUI.show_timetable_interface = show_timetable_interface

def show_homework_interface(self):
    """Show homework and assignments interface"""
    self.clear_content()
    self.update_status("Homework & Assignments")

    title = ttk.Label(self.content_frame, text="Homework & Assignments", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Homework display frame
    homework_frame = ttk.LabelFrame(self.content_frame, text="Assignments", padding=15)
    homework_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_homework():
        for widget in homework_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(homework_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='assignments'
            """)

            if cursor.fetchone():
                # Use correct column names: title (not assignment_name), module_code (not subject), id (not assignment_id)
                cursor.execute("""
                    SELECT a.title, COALESCE(m.module_name, a.module_code) as subject, a.due_date, a.description,
                           COALESCE(s.status, 'Not Started') as status
                    FROM assignments a
                    LEFT JOIN modules m ON a.module_code = m.module_code
                    LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                                                       AND s.student_id = ?
                    WHERE a.due_date >= date('now') AND a.is_active = 1
                    ORDER BY a.due_date
                    LIMIT 20
                """, (student_id,))

                assignments = cursor.fetchall()

                if assignments:
                    columns = ("Assignment", "Subject", "Due Date", "Status")
                    tree = ttk.Treeview(homework_frame, columns=columns, show="headings", height=12)

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=150)

                    for assignment in assignments:
                        tree.insert('', tk.END, values=assignment[:4], tags=(assignment[4],))

                    tree.tag_configure('Completed', foreground='green')
                    tree.tag_configure('Not Started', foreground='red')
                    tree.tag_configure('In Progress', foreground='orange')

                    scrollbar = ttk.Scrollbar(homework_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    def view_details():
                        selected = tree.selection()
                        if selected:
                            item = tree.item(selected[0])
                            messagebox.showinfo("Assignment Details",
                                               f"Assignment: {item['values'][0]}\n"
                                               f"Subject: {item['values'][1]}\n"
                                               f"Due: {item['values'][2]}\n"
                                               f"Status: {item['values'][3]}")

                    ttk.Button(homework_frame, text="View Details", command=view_details).pack(pady=10)
                else:
                    ttk.Label(homework_frame, text="No upcoming assignments",
                             font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(homework_frame, text="Assignments system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(homework_frame, text=f"Error loading assignments: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Assignments", command=load_homework).pack(side=tk.LEFT, padx=5)
    load_homework()
ParentPortalGUI.show_homework_interface = show_homework_interface
