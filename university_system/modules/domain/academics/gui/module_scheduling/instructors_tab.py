from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from university_system.modules.shared.utils.gui_language_selector import (
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
    from university_system.modules.domain.academics.services.module_scheduling import (
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
        from university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from .main_gui import ModuleSchedulingGUI
from .dialogs import AddInstructorDialog, EditInstructorDialog

def create_instructors_tab(self):
    """Create the instructors management tab"""
    instructors_frame = ttk.Frame(self.notebook)
    self.notebook.add(instructors_frame, text=_t("scheduling.tabs.instructors"))
    
    # Controls frame
    controls_frame = ttk.Frame(instructors_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)
    
    ttk.Button(controls_frame, text=_t("scheduling.buttons.add_instructor"),
              command=self.show_add_instructor_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.edit_selected"),
              command=self.edit_selected_instructor).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.buttons.workload_report"),
              command=self.show_workload_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.refresh"),
              command=self.refresh_instructors).pack(side=tk.LEFT, padx=5)

    # Search
    search_frame = ttk.Frame(controls_frame)
    search_frame.pack(side=tk.RIGHT, padx=5)

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
    self.instructor_search_var = tk.StringVar()
    self.instructor_search_var.trace('w', self.filter_instructors)
    ttk.Entry(search_frame, textvariable=self.instructor_search_var, width=20).pack(side=tk.LEFT, padx=5)
    
    # Instructors treeview
    tree_frame = ttk.Frame(instructors_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    columns = ("ID", "Name", "Email", "Department", "Max Hours", "Current Hours", "Status")
    self.instructors_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
    
    for col in columns:
        self.instructors_tree.heading(col, text=col)
        if col == "ID":
            self.instructors_tree.column(col, width=50)
        elif col in ["Email", "Name"]:
            self.instructors_tree.column(col, width=150)
        else:
            self.instructors_tree.column(col, width=100)
    
    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.instructors_tree.yview)
    self.instructors_tree.configure(yscrollcommand=v_scrollbar.set)
    
    self.instructors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    self.instructors_tree.bind("<Double-1>", lambda e: self.edit_selected_instructor())

ModuleSchedulingGUI.create_instructors_tab = create_instructors_tab

def refresh_instructors(self):
    """Refresh the instructors treeview"""
    try:
        # Clear existing items
        for item in self.instructors_tree.get_children():
            self.instructors_tree.delete(item)
        
        from university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT i.id, i.first_name, i.last_name, i.email, i.department,
                   COALESCE(i.max_hours_per_week, i.max_courses_per_semester * 8, 40) as max_hours_per_week,
                   CASE WHEN i.status = 'Active' THEN 1 ELSE COALESCE(i.is_active, 1) END as is_active,
                   COALESCE(SUM(CASE
                       WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                       THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                            (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                       ELSE 0 END) / 60.0, 0) as current_hours
            FROM instructors i
            LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
            GROUP BY i.id
            ORDER BY i.last_name, i.first_name
            ''')

            instructors = cursor.fetchall()
        
        for instructor in instructors:
            instructor_id, first_name, last_name, email, department, max_hours, is_active, current_hours = instructor
            full_name = f"{first_name} {last_name}"
            status = "Active" if is_active else "Inactive"
            current_hours = round(current_hours or 0, 1)
            
            self.instructors_tree.insert("", tk.END, values=(
                instructor_id, full_name, email, department, max_hours, current_hours, status
            ))
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh instructors: {str(e)}")

ModuleSchedulingGUI.refresh_instructors = refresh_instructors

def filter_instructors(self, *args):
    """Filter instructors based on search term"""
    search_term = self.instructor_search_var.get().lower()
    
    # Clear current items
    for item in self.instructors_tree.get_children():
        self.instructors_tree.delete(item)
    
    if not search_term:
        self.refresh_instructors()
        return
    
    try:
        from university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT i.id, i.first_name, i.last_name, i.email, i.department,
                   COALESCE(i.max_hours_per_week, i.max_courses_per_semester * 8, 40) as max_hours_per_week,
                   CASE WHEN i.status = 'Active' THEN 1 ELSE COALESCE(i.is_active, 1) END as is_active,
                   COALESCE(SUM(CASE
                       WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                       THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                            (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                       ELSE 0 END) / 60.0, 0) as current_hours
            FROM instructors i
            LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
            WHERE LOWER(i.first_name) LIKE ?
               OR LOWER(i.last_name) LIKE ?
               OR LOWER(i.email) LIKE ?
               OR LOWER(i.department) LIKE ?
            GROUP BY i.id
            ORDER BY i.last_name, i.first_name
            ''', [f'%{search_term}%'] * 4)

            instructors = cursor.fetchall()
        
        for instructor in instructors:
            instructor_id, first_name, last_name, email, department, max_hours, is_active, current_hours = instructor
            full_name = f"{first_name} {last_name}"
            status = "Active" if is_active else "Inactive"
            current_hours = round(current_hours or 0, 1)
            
            self.instructors_tree.insert("", tk.END, values=(
                instructor_id, full_name, email, department, max_hours, current_hours, status
            ))
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to filter instructors: {str(e)}")

ModuleSchedulingGUI.filter_instructors = filter_instructors

def show_add_instructor_dialog(self):
    """Show dialog for adding a new instructor"""
    dialog = AddInstructorDialog(self.root, self.scheduler)
    if dialog.result:
        self.refresh_instructors()
        self.refresh_dashboard()
        self.update_activity_log("New instructor added")

ModuleSchedulingGUI.show_add_instructor_dialog = show_add_instructor_dialog

def edit_selected_instructor(self):
    """Edit the selected instructor"""
    selected = self.instructors_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select an instructor to edit.")
        return
    
    instructor_data = self.instructors_tree.item(selected[0])['values']
    instructor_id = instructor_data[0]
    
    dialog = EditInstructorDialog(self.root, self.scheduler, instructor_id)
    if dialog.result:
        self.refresh_instructors()
        self.update_activity_log(f"Instructor {instructor_id} updated")

ModuleSchedulingGUI.edit_selected_instructor = edit_selected_instructor

def quick_add_instructor(self):
    """Quick add instructor from dashboard"""
    self.notebook.select(3)  # Switch to instructors tab
    self.show_add_instructor_dialog()

ModuleSchedulingGUI.quick_add_instructor = quick_add_instructor

def view_instructor_schedule(self, instructor_id=None):
    """View schedule for a specific instructor"""
    if not instructor_id:
        # Show dialog to select instructor
        instructor_id = self._select_instructor_dialog()
        if not instructor_id:
            return

    schedules = self._get_instructor_schedule_data(instructor_id)

    if not schedules:
        messagebox.showinfo("No Schedule", f"No schedule found for instructor ID {instructor_id}")
        return

    # Get instructor name
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
        instructor_info = cursor.fetchone()

    instructor_name = f"{instructor_info[0]} {instructor_info[1]}" if instructor_info else f"Instructor {instructor_id}"

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Schedule for {instructor_name}")
    dialog.geometry("1000x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Day', 'Time', 'Module', 'Room', 'Type')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Day', width=120)
    tree.column('Time', width=140)
    tree.column('Module', width=150)
    tree.column('Room', width=150)
    tree.column('Type', width=120)

    for schedule in schedules:
        time_str = f"{schedule['start_time']} - {schedule['end_time']}"
        tree.insert('', tk.END, values=(
            schedule['day'],
            time_str,
            schedule['module_code'],
            schedule['room'],
            schedule['session_type']
        ))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.view_instructor_schedule = view_instructor_schedule

def _select_instructor_dialog(self):
    """Show dialog to select an instructor"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, department FROM instructors WHERE is_active = 1 ORDER BY last_name")
        instructors = cursor.fetchall()

    if not instructors:
        messagebox.showinfo("No Instructors", "No instructors found in the system.")
        return None

    dialog = tk.Toplevel(self.root)
    dialog.title("Select Instructor")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    selected = [None]

    listbox = tk.Listbox(dialog, font=('Arial', 10))
    for instructor_id, first, last, dept in instructors:
        listbox.insert(tk.END, f"{first} {last} ({dept})")
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_select():
        if listbox.curselection():
            idx = listbox.curselection()[0]
            selected[0] = instructors[idx][0]
            dialog.destroy()

    ttk.Button(dialog, text="Select", command=on_select).pack(pady=5)

    dialog.wait_window()
    return selected[0]

ModuleSchedulingGUI._select_instructor_dialog = _select_instructor_dialog

