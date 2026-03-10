from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']
    
    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from .main_gui import ModuleSchedulingGUI
from .dialogs import GridViewWindow

def create_timetables_tab(self):
    """Create the timetables generation tab"""
    timetables_frame = ttk.Frame(self.notebook)
    self.notebook.add(timetables_frame, text=_t("scheduling.tabs.timetables"))
    
    # Left panel for controls with scrollbar
    left_outer = ttk.Frame(timetables_frame, width=250)
    left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
    left_outer.pack_propagate(False)

    left_canvas = tk.Canvas(left_outer, highlightthickness=0)
    left_scrollbar = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=left_canvas.yview)
    left_panel = ttk.Frame(left_canvas)

    left_panel.bind(
        "<Configure>",
        lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
    )
    left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
    left_canvas.configure(yscrollcommand=left_scrollbar.set)

    left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Mousewheel scrolling for sidebar
    def _on_sidebar_mousewheel(event):
        try:
            if not left_scrollbar.winfo_viewable():
                return
        except tk.TclError:
            return
        if getattr(event, "delta", 0):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            left_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            left_canvas.yview_scroll(1, "units")

    left_canvas.bind("<Enter>", lambda e: (
        left_canvas.bind_all("<MouseWheel>", _on_sidebar_mousewheel),
        left_canvas.bind_all("<Button-4>", _on_sidebar_mousewheel),
        left_canvas.bind_all("<Button-5>", _on_sidebar_mousewheel),
    ))
    left_canvas.bind("<Leave>", lambda e: (
        left_canvas.unbind_all("<MouseWheel>"),
        left_canvas.unbind_all("<Button-4>"),
        left_canvas.unbind_all("<Button-5>"),
    ))

    # Student timetable section
    student_frame = ttk.LabelFrame(left_panel, text=_t("scheduling.student_timetables"), padding=10)
    student_frame.pack(fill=tk.X, pady=5)

    ttk.Label(student_frame, text=_t("scheduling.student_id") + ":").pack(anchor=tk.W)
    self.student_id_var = tk.StringVar()
    ttk.Entry(student_frame, textvariable=self.student_id_var, width=20).pack(fill=tk.X, pady=2)

    ttk.Button(student_frame, text=_t("scheduling.generate_student_timetable"),
              command=self.generate_student_timetable).pack(fill=tk.X, pady=2)
    ttk.Button(student_frame, text=_t("scheduling.email_timetable_to_student"),
              command=self.email_student_timetable).pack(fill=tk.X, pady=2)
    ttk.Button(student_frame, text=_t("scheduling.check_student_conflicts"),
              command=self.check_student_conflicts).pack(fill=tk.X, pady=2)

    # Instructor timetable section
    instructor_frame = ttk.LabelFrame(left_panel, text=_t("scheduling.instructor_timetables"), padding=10)
    instructor_frame.pack(fill=tk.X, pady=5)

    ttk.Label(instructor_frame, text=_t("scheduling.instructor_id") + ":").pack(anchor=tk.W)
    self.instructor_id_var = tk.StringVar()
    ttk.Entry(instructor_frame, textvariable=self.instructor_id_var, width=20).pack(fill=tk.X, pady=2)

    ttk.Button(instructor_frame, text=_t("scheduling.generate_instructor_timetable"),
              command=self.generate_instructor_timetable).pack(fill=tk.X, pady=2)
    ttk.Button(instructor_frame, text=_t("scheduling.email_timetable_to_instructor"),
              command=self.email_instructor_timetable).pack(fill=tk.X, pady=2)

    # Export options
    export_frame = ttk.LabelFrame(left_panel, text=_t("scheduling.export_options"), padding=10)
    export_frame.pack(fill=tk.X, pady=5)

    self.export_format_var = tk.StringVar(value="PDF")
    formats = ["PDF", "CSV", "Excel", "iCal"]

    for fmt in formats:
        ttk.Radiobutton(export_frame, text=fmt, variable=self.export_format_var,
                       value=fmt).pack(anchor=tk.W)

    ttk.Button(export_frame, text=_t("scheduling.export_last_generated"),
              command=self.export_last_timetable).pack(fill=tk.X, pady=5)

    # Right panel for timetable display
    right_panel = ttk.Frame(timetables_frame)
    right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Timetable display area
    display_frame = ttk.LabelFrame(right_panel, text=_t("scheduling.timetable_display"), padding=10)
    display_frame.pack(fill=tk.BOTH, expand=True)

    # Create canvas with scrollbars for grid view
    canvas = tk.Canvas(display_frame)
    v_scrollbar = ttk.Scrollbar(display_frame, orient=tk.VERTICAL, command=canvas.yview)
    h_scrollbar = ttk.Scrollbar(display_frame, orient=tk.HORIZONTAL, command=canvas.xview)

    self.timetable_frame = ttk.Frame(canvas)
    self.timetable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=self.timetable_frame, anchor="nw")
    canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

ModuleSchedulingGUI.create_timetables_tab = create_timetables_tab

def generate_student_timetable(self):
    """Generate timetable for a student"""
    student_id = self.student_id_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID.")
        return

    try:
        # Check if student exists
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

        if not student:
            messagebox.showerror("Error", f"Student ID {student_id} does not exist.")
            return

        student_name = f"{student[0]} {student[1]}"

        # Get schedule data
        schedule_data = self.scheduler._get_student_schedule_data(student_id)

        if not schedule_data:
            # Clear and show message
            for widget in self.timetable_frame.winfo_children():
                widget.destroy()
            tk.Label(self.timetable_frame, text=f"No schedule found for student {student_id}",
                    font=('Arial', 12)).pack(pady=20)
            return

        # Display timetable in grid view
        self._display_timetable_grid(schedule_data, f"Timetable for {student_name} ({student_id})")

        # Check for conflicts
        conflicts = self.scheduler.check_student_conflicts(student_id)
        if conflicts:
            conflict_label = tk.Label(self.timetable_frame, text=f"⚠️ {len(conflicts)} scheduling conflict(s) detected",
                                     font=('Arial', 10, 'bold'), fg='red')
            conflict_label.pack(pady=10)

        self.update_activity_log(f"Generated timetable for student {student_id}")
        self.last_timetable_data = schedule_data  # Store for export
        self.last_timetable_type = 'student'
        self.last_timetable_id = student_id

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate student timetable: {str(e)}")

ModuleSchedulingGUI.generate_student_timetable = generate_student_timetable

def generate_instructor_timetable(self):
    """Generate timetable for an instructor"""
    instructor_id_str = self.instructor_id_var.get().strip()
    if not instructor_id_str:
        messagebox.showwarning("Warning", "Please enter an instructor ID.")
        return

    try:
        instructor_id = int(instructor_id_str)

        # Check if instructor exists
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
            instructor = cursor.fetchone()

        if not instructor:
            messagebox.showerror("Error", f"Instructor ID {instructor_id} does not exist.")
            return

        first_name, last_name = instructor
        instructor_name = f"{first_name} {last_name}"

        # Get schedule data
        schedule_data = self.scheduler._get_instructor_schedule_data(instructor_id)

        if not schedule_data:
            # Clear and show message
            for widget in self.timetable_frame.winfo_children():
                widget.destroy()
            tk.Label(self.timetable_frame, text=f"No schedule found for instructor {instructor_name}",
                    font=('Arial', 12)).pack(pady=20)
            return

        # Display timetable in grid view
        self._display_timetable_grid(schedule_data, f"Timetable for {instructor_name} (ID: {instructor_id})")

        self.update_activity_log(f"Generated timetable for instructor {instructor_name}")
        self.last_timetable_data = schedule_data  # Store for export
        self.last_timetable_type = 'instructor'
        self.last_timetable_id = instructor_id

    except ValueError:
        messagebox.showerror("Error", "Invalid instructor ID. Please enter a number.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate instructor timetable: {str(e)}")

ModuleSchedulingGUI.generate_instructor_timetable = generate_instructor_timetable

def email_student_timetable(self):
    """Email timetable to a student"""
    student_id = self.student_id_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID.")
        return

    try:
        # Get student info
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (student_id,))
            student = cursor.fetchone()

        if not student:
            messagebox.showerror("Error", f"Student ID {student_id} not found.")
            return

        first_name, last_name, email = student
        student_name = f"{first_name} {last_name}"

        if not email:
            messagebox.showerror("Error", f"No email address found for student {student_name}.")
            return

        # Get schedule data
        schedule_data = self.scheduler._get_student_schedule_data(student_id)

        if not schedule_data:
            messagebox.showinfo("Info", f"No schedule found for student {student_id}.")
            return

        # Format timetable as email body
        body = self._format_timetable_email(schedule_data, student_name, 'student')

        # Send email
        from education_system.university_system.infrastructure.email.email_service import send_email
        subject = f"Your Timetable - {student_name}"

        success = send_email(email, subject, body)

        if success:
            messagebox.showinfo("Success", f"Timetable emailed to {email}")
            self.update_activity_log(f"Emailed timetable to student {student_id} ({email})")
        else:
            messagebox.showerror("Error", "Failed to send timetable email.")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to email timetable: {str(e)}")

ModuleSchedulingGUI.email_student_timetable = email_student_timetable

def email_instructor_timetable(self):
    """Email timetable to an instructor"""
    instructor_id_str = self.instructor_id_var.get().strip()
    if not instructor_id_str:
        messagebox.showwarning("Warning", "Please enter an instructor ID.")
        return

    try:
        instructor_id = int(instructor_id_str)

        # Get instructor info
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, last_name, email FROM instructors WHERE id = ?', (instructor_id,))
            instructor = cursor.fetchone()

        if not instructor:
            messagebox.showerror("Error", f"Instructor ID {instructor_id} not found.")
            return

        first_name, last_name, email = instructor
        instructor_name = f"{first_name} {last_name}"

        if not email:
            messagebox.showerror("Error", f"No email address found for instructor {instructor_name}.")
            return

        # Get schedule data
        schedule_data = self.scheduler._get_instructor_schedule_data(instructor_id)

        if not schedule_data:
            messagebox.showinfo("Info", f"No schedule found for instructor {instructor_id}.")
            return

        # Format timetable as email body
        body = self._format_timetable_email(schedule_data, instructor_name, 'instructor')

        # Send email
        from education_system.university_system.infrastructure.email.email_service import send_email
        subject = f"Your Teaching Schedule - {instructor_name}"

        success = send_email(email, subject, body)

        if success:
            messagebox.showinfo("Success", f"Timetable emailed to {email}")
            self.update_activity_log(f"Emailed timetable to instructor {instructor_id} ({email})")
        else:
            messagebox.showerror("Error", "Failed to send timetable email.")

    except ValueError:
        messagebox.showerror("Error", "Invalid instructor ID. Please enter a number.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to email timetable: {str(e)}")

ModuleSchedulingGUI.email_instructor_timetable = email_instructor_timetable

def _format_timetable_email(self, schedule_data, name, recipient_type):
    """Format schedule data as an email-friendly timetable"""
    lines = []
    lines.append(f"Dear {name},\n")

    if recipient_type == 'student':
        lines.append("Here is your class timetable:\n")
    else:
        lines.append("Here is your teaching schedule:\n")

    lines.append("=" * 60)
    lines.append("")

    # Group by day
    days_data = {}
    for entry in schedule_data:
        day = entry.get('day', entry.get('day_of_week', 'Unknown'))
        if day not in days_data:
            days_data[day] = []
        days_data[day].append(entry)

    # Sort days
    day_order = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 'Friday': 5, 'Saturday': 6, 'Sunday': 7}

    for day in sorted(days_data.keys(), key=lambda d: day_order.get(d, 8)):
        lines.append(f"\n{day.upper()}")
        lines.append("-" * 40)

        # Sort by start time
        day_entries = sorted(days_data[day], key=lambda x: x.get('start_time', ''))

        for entry in day_entries:
            module_code = entry.get('module_code', 'N/A')
            module_name = entry.get('module_name', '')
            start_time = entry.get('start_time', 'TBA')
            end_time = entry.get('end_time', 'TBA')
            room = entry.get('room', 'TBA')
            session_type = entry.get('session_type', 'Session')

            lines.append(f"  {start_time} - {end_time}")
            lines.append(f"    {module_code}: {module_name}" if module_name else f"    {module_code}")
            lines.append(f"    Type: {session_type}")
            lines.append(f"    Room: {room}")
            lines.append("")

    lines.append("=" * 60)
    lines.append("\nIf you have any questions about your schedule, please contact the Academic Office.")
    lines.append("\nBest regards,")
    lines.append("Academic Scheduling System")
    lines.append("University Management System")

    return "\n".join(lines)

ModuleSchedulingGUI._format_timetable_email = _format_timetable_email

def _display_timetable_grid(self, schedule_data, title):
    """Display timetable in grid format matching the grid view"""
    # Clear existing content
    for widget in self.timetable_frame.winfo_children():
        widget.destroy()

    # Title
    title_label = tk.Label(self.timetable_frame, text=title, font=('Arial', 14, 'bold'))
    title_label.pack(pady=10)

    # Create grid data structure
    grid_data = {}
    for day in DAYS_OF_WEEK:
        grid_data[day] = {}
        for time_slot in TIME_SLOTS:
            grid_data[day][time_slot] = []

    # Populate grid with schedule data
    for entry in schedule_data:
        day = entry.get('day', entry.get('day_of_week', ''))
        start_time = entry.get('start_time', '')

        if not day or not start_time:
            continue

        # Find the closest time slot
        try:
            closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
        except (ValueError, TypeError, IndexError):
            continue

        session_info = {
            'module': entry.get('module_code', 'N/A'),
            'type': entry.get('session_type', 'Session'),
            'room': entry.get('room', 'TBA'),
            'time': f"{entry.get('start_time', '')}-{entry.get('end_time', '')}"
        }

        if day in grid_data and closest_slot in grid_data[day]:
            grid_data[day][closest_slot].append(session_info)

    # Create grid frame
    grid_frame = tk.Frame(self.timetable_frame)
    grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Header row - Time column
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

                        # Module code
                        module_label = tk.Label(session_box, text=entry['module'],
                                               font=('Arial', 8, 'bold'),
                                               bg='#c3e6cb', fg='#155724')
                        module_label.pack(anchor='w')

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

ModuleSchedulingGUI._display_timetable_grid = _display_timetable_grid

def check_student_conflicts(self):
    """Check for conflicts in student's schedule"""
    student_id = self.student_id_var.get().strip()
    if not student_id:
        messagebox.showwarning("Warning", "Please enter a student ID.")
        return

    try:
        conflicts = self.scheduler.check_student_conflicts(student_id)

        # Clear the timetable frame
        for widget in self.timetable_frame.winfo_children():
            widget.destroy()

        if not conflicts:
            tk.Label(self.timetable_frame,
                    text=f"No scheduling conflicts found for student {student_id}",
                    font=('Arial', 12)).pack(pady=20)
        else:
            # Header
            tk.Label(self.timetable_frame,
                    text=f"Scheduling Conflicts for Student {student_id}",
                    font=('Arial', 14, 'bold')).pack(pady=10)

            for i, conflict in enumerate(conflicts, 1):
                module1 = conflict['module1']
                module2 = conflict['module2']

                # Create frame for each conflict
                conflict_frame = ttk.LabelFrame(self.timetable_frame,
                                                text=f"Conflict {i}", padding=10)
                conflict_frame.pack(fill=tk.X, padx=10, pady=5)

                tk.Label(conflict_frame,
                        text=f"Module 1: {module1['code']} - {module1['name']}",
                        font=('Arial', 10, 'bold'), fg='red').pack(anchor='w')
                tk.Label(conflict_frame,
                        text=f"    {module1['day']} {module1['time']} in {module1['room']}",
                        font=('Arial', 10)).pack(anchor='w')

                tk.Label(conflict_frame,
                        text=f"Module 2: {module2['code']} - {module2['name']}",
                        font=('Arial', 10, 'bold'), fg='red').pack(anchor='w', pady=(5, 0))
                tk.Label(conflict_frame,
                        text=f"    {module2['day']} {module2['time']} in {module2['room']}",
                        font=('Arial', 10)).pack(anchor='w')

        self.update_activity_log(f"Checked conflicts for student {student_id}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to check student conflicts: {str(e)}")

ModuleSchedulingGUI.check_student_conflicts = check_student_conflicts

def export_last_timetable(self):
    """Export the last generated timetable"""
    # Check if we have timetable data stored
    if not hasattr(self, 'last_timetable_data') or not self.last_timetable_data:
        messagebox.showwarning("Warning", "No timetable to export. Please generate a timetable first.")
        return

    format_type = self.export_format_var.get()

    try:
        if format_type == "iCal":
            self._export_timetable_to_ical(self.last_timetable_data)
        elif format_type == "PDF":
            self._export_timetable_to_pdf(self.last_timetable_data)
        elif format_type == "CSV":
            self._export_timetable_to_csv(self.last_timetable_data)
        elif format_type == "Excel":
            self._export_timetable_to_excel(self.last_timetable_data)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export timetable: {str(e)}")

ModuleSchedulingGUI.export_last_timetable = export_last_timetable

def _get_student_schedule_data(self, student_id):
    """Get schedule data for a student"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (student_id,))
        modules = [row[0] for row in cursor.fetchall()]

        if not modules:
            return []

        placeholders = ','.join(['?'] * len(modules))
        query = f'''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.module_code IN ({placeholders})
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, modules)
        schedules = cursor.fetchall()

        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })

        return schedule_data

ModuleSchedulingGUI._get_student_schedule_data = _get_student_schedule_data

def _get_instructor_schedule_data(self, instructor_id):
    """Get schedule data for an instructor"""
    with get_connection() as conn:
        cursor = conn.cursor()

        query = '''
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        '''

        cursor.execute(query, (instructor_id,))
        schedules = cursor.fetchall()

        schedule_data = []
        for schedule in schedules:
            module_code, module_name, day, start, end, building, room, first_name, last_name, session_type = schedule
            schedule_data.append({
                'module_code': module_code,
                'module_name': module_name or "Unknown",
                'day': day,
                'start_time': start,
                'end_time': end,
                'room': f"{building}-{room}" if building and room else "TBA",
                'instructor': f"{first_name} {last_name}" if first_name and last_name else "TBA",
                'session_type': session_type
            })

        return schedule_data

ModuleSchedulingGUI._get_instructor_schedule_data = _get_instructor_schedule_data

def _select_module_dialog(self):
    """Show dialog to select a module"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
        modules = cursor.fetchall()

    if not modules:
        messagebox.showinfo("No Modules", "No modules found in the system.")
        return None

    dialog = tk.Toplevel(self.root)
    dialog.title("Select Module")
    dialog.geometry("600x400")
    dialog.transient(self.root)
    dialog.grab_set()

    selected = [None]

    listbox = tk.Listbox(dialog, font=('Arial', 10))
    for code, name in modules:
        listbox.insert(tk.END, f"{code} - {name}")
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_select():
        if listbox.curselection():
            idx = listbox.curselection()[0]
            selected[0] = modules[idx][0]
            dialog.destroy()

    ttk.Button(dialog, text="Select", command=on_select).pack(pady=5)

    dialog.wait_window()
    return selected[0]

ModuleSchedulingGUI._select_module_dialog = _select_module_dialog

def view_calendar(self):
    """View academic calendar - opens the full academic calendar GUI"""
    try:
        # Try to launch the academic calendar GUI
        from education_system.university_system.modules.domain.academics.gui.academic_calendar.main_gui import CalendarGUI

        # Create calendar GUI in a new top-level window
        calendar_window = tk.Toplevel(self.root)
        calendar_window.title("Academic Calendar")
        calendar_window.geometry("1200x800")

        # Initialize calendar GUI
        try:
            calendar_gui = CalendarGUI(parent_window=calendar_window)
            self.update_activity_log("Opened Academic Calendar")
            return
        except Exception as e:
            print(f"Could not load full calendar GUI: {e}")
            # Fall back to basic view
            calendar_window.destroy()
            calendar_window = tk.Toplevel(self.root)
            calendar_window.title("Academic Calendar - Basic View")
            calendar_window.geometry("600x400")
        
        # Calendar display
        calendar_text = scrolledtext.ScrolledText(calendar_window, font=('Courier', 10))
        calendar_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Get current month's holidays
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute('''
            SELECT holiday_name, start_date, end_date, description
            FROM holidays
            WHERE start_date LIKE ?
            ORDER BY start_date
            ''', (f"{current_month}%",))

            holidays = cursor.fetchall()
        
        calendar_text.insert(tk.END, f"Academic Calendar - {datetime.now().strftime('%B %Y')}\n")
        calendar_text.insert(tk.END, "=" * 60 + "\n")
        
        if holidays:
            for holiday in holidays:
                name, start, end, desc = holiday
                if start == end:
                    calendar_text.insert(tk.END, f"{start}: {name}\n")
                else:
                    calendar_text.insert(tk.END, f"{start} to {end}: {name}\n")
                if desc:
                    calendar_text.insert(tk.END, f"  {desc}\n")
                calendar_text.insert(tk.END, "\n")
        else:
            calendar_text.insert(tk.END, "No holidays scheduled for this month.\n")
        
        calendar_text.insert(tk.END, "=" * 60 + "\n")
        calendar_text.config(state=tk.DISABLED)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to view calendar: {str(e)}")

ModuleSchedulingGUI.view_calendar = view_calendar

def show_grid_view(self):
    """Show schedule in grid view"""
    GridViewWindow(self.root, self.scheduler)

ModuleSchedulingGUI.show_grid_view = show_grid_view

