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

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI
from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import AddScheduleDialog, EditScheduleDialog

def create_schedules_tab(self):
    """Create the schedules management tab"""
    schedules_frame = ttk.Frame(self.notebook)
    self.notebook.add(schedules_frame, text=_t("scheduling.tabs.schedules"))
    
    # Controls frame
    controls_frame = ttk.Frame(schedules_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)
    
    # Add schedule button
    ttk.Button(controls_frame, text=_t("scheduling.buttons.add_schedule"),
              command=self.show_add_schedule_dialog).pack(side=tk.LEFT, padx=5)

    # Edit/Delete buttons
    ttk.Button(controls_frame, text=_t("common.edit_selected"),
              command=self.edit_selected_schedule).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.delete_selected"),
              command=self.delete_selected_schedule).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.refresh"),
              command=self.refresh_schedules).pack(side=tk.LEFT, padx=5)

    # Search frame
    search_frame = ttk.Frame(controls_frame)
    search_frame.pack(side=tk.RIGHT, padx=5)

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
    self.schedule_search_var = tk.StringVar()
    self.schedule_search_var.trace('w', self.filter_schedules)
    search_entry = ttk.Entry(search_frame, textvariable=self.schedule_search_var, width=20)
    search_entry.pack(side=tk.LEFT, padx=5)
    
    # Schedules treeview
    tree_frame = ttk.Frame(schedules_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    columns = ("ID", "Module", "Module Name", "Day", "Time", "Room", "Instructor", "Type")
    self.schedules_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
    
    # Configure columns
    for col in columns:
        self.schedules_tree.heading(col, text=col)
        if col == "ID":
            self.schedules_tree.column(col, width=50)
        elif col == "Module Name":
            self.schedules_tree.column(col, width=200)
        else:
            self.schedules_tree.column(col, width=100)
    
    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.schedules_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.schedules_tree.xview)
    self.schedules_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    # Pack treeview and scrollbars
    self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Double-click to edit
    self.schedules_tree.bind("<Double-1>", lambda e: self.edit_selected_schedule())

ModuleSchedulingGUI.create_schedules_tab = create_schedules_tab

def refresh_schedules(self):
    """Refresh the schedules treeview"""
    try:
        # Clear existing items
        for item in self.schedules_tree.get_children():
            self.schedules_tree.delete(item)
        
        # Get schedule data from backend
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, r.building, r.room_number,
                   i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()
        
        # Populate treeview
        for schedule in schedules:
            schedule_id, module_code, module_name, day, start_time, end_time, building, room_number, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"
            time_slot = f"{start_time}-{end_time}"
            room_str = f"{building}-{room_number}" if building and room_number else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
            
            self.schedules_tree.insert("", tk.END, values=(
                schedule_id, module_code, module_name, day, time_slot, room_str, instructor, session_type
            ))
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh schedules: {str(e)}", parent=self.root)

ModuleSchedulingGUI.refresh_schedules = refresh_schedules

def filter_schedules(self, *args):
    """Filter schedules based on search term"""
    search_term = self.schedule_search_var.get().lower()
    
    # Clear current items
    for item in self.schedules_tree.get_children():
        self.schedules_tree.delete(item)
    
    if not search_term:
        self.refresh_schedules()
        return
    
    # Refresh with filter
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, r.building, r.room_number,
                   i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            WHERE LOWER(ms.module_code) LIKE ?
               OR LOWER(m.module_name) LIKE ?
               OR LOWER(ms.day_of_week) LIKE ?
               OR LOWER(ms.session_type) LIKE ?
               OR LOWER(i.first_name) LIKE ?
               OR LOWER(i.last_name) LIKE ?
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''', [f'%{search_term}%'] * 6)

            schedules = cursor.fetchall()
        
        for schedule in schedules:
            schedule_id, module_code, module_name, day, start_time, end_time, building, room_number, first_name, last_name, session_type = schedule
            module_name = module_name or "Unknown"
            time_slot = f"{start_time}-{end_time}"
            room_str = f"{building}-{room_number}" if building and room_number else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
            
            self.schedules_tree.insert("", tk.END, values=(
                schedule_id, module_code, module_name, day, time_slot, room_str, instructor, session_type
            ))
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to filter schedules: {str(e)}", parent=self.root)

ModuleSchedulingGUI.filter_schedules = filter_schedules

def show_add_schedule_dialog(self):
    """Show dialog for adding a new schedule"""
    dialog = AddScheduleDialog(self.root, self.scheduler, gui=self)
    if dialog.result:
        self.refresh_schedules()
        self.refresh_dashboard()
        self.update_activity_log("New schedule added")

ModuleSchedulingGUI.show_add_schedule_dialog = show_add_schedule_dialog

def edit_selected_schedule(self):
    """Edit the selected schedule"""
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a schedule to edit.", parent=self.root)
        return
    
    schedule_data = self.schedules_tree.item(selected[0])['values']
    schedule_id = schedule_data[0]
    
    dialog = EditScheduleDialog(self.root, self.scheduler, schedule_id, gui=self)
    if dialog.result:
        self.refresh_schedules()
        self.update_activity_log(f"Schedule {schedule_id} updated")

ModuleSchedulingGUI.edit_selected_schedule = edit_selected_schedule

def delete_selected_schedule(self):
    """Delete the selected schedule"""
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a schedule to delete.", parent=self.root)
        return
    
    schedule_data = self.schedules_tree.item(selected[0])['values']
    schedule_id = schedule_data[0]
    module_code = schedule_data[1]
    
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the schedule for {module_code}?", parent=self.root):
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM module_schedule WHERE id = ?', (schedule_id,))
                conn.commit()
            
            self.refresh_schedules()
            self.refresh_dashboard()
            self.update_activity_log(f"Schedule {schedule_id} deleted")
            messagebox.showinfo("Success", "Schedule deleted successfully.", parent=self.root)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete schedule: {str(e)}", parent=self.root)

ModuleSchedulingGUI.delete_selected_schedule = delete_selected_schedule

def quick_add_schedule(self):
    """Quick add schedule from dashboard"""
    self.notebook.select(1)  # Switch to schedules tab
    self.show_add_schedule_dialog()

ModuleSchedulingGUI.quick_add_schedule = quick_add_schedule

def view_module_schedule(self, module_code=None):
    """View schedule for a specific module"""
    if not module_code:
        # Show dialog to select module
        module_code = self._select_module_dialog()
        if not module_code:
            return

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number,
               i.first_name, i.last_name,
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE ms.module_code = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (module_code,))

        schedules = cursor.fetchall()

    if not schedules:
        messagebox.showinfo("No Schedule", f"No schedule found for module {module_code}", parent=self.root)
        return

    # Create dialog to show schedule
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Schedule for Module {module_code}")
    dialog.geometry("900x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Day', 'Time', 'Room', 'Instructor', 'Type')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Day', width=120)
    tree.column('Time', width=140)
    tree.column('Room', width=150)
    tree.column('Instructor', width=200)
    tree.column('Type', width=120)

    for schedule in schedules:
        day, start, end, building, room, first, last, session_type = schedule
        time_str = f"{start} - {end}"
        room_str = f"{building}-{room}" if building and room else "TBA"
        instructor = f"{first} {last}" if first and last else "TBA"
        tree.insert('', tk.END, values=(day, time_str, room_str, instructor, session_type))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.view_module_schedule = view_module_schedule

