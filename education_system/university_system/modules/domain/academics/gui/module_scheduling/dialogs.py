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

class AddScheduleDialog:
    def __init__(self, parent, scheduler, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Schedule")
        self.dialog.geometry("550x700")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Module selection
        ttk.Label(main_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)

        # Load modules
        try:
            modules = self.scheduler._get_known_modules()
            module_combo['values'] = list(modules.keys())
        except (AttributeError, Exception):
            pass

        module_combo.grid(row=0, column=1, pady=5, sticky=tk.W)

        # Day of week
        ttk.Label(main_frame, text="Day of Week:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar()
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=1, column=1, pady=5, sticky=tk.W)

        # Time
        ttk.Label(main_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar()
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=2, column=1, pady=5, sticky=tk.W)

        ttk.Label(main_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar()
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=3, column=1, pady=5, sticky=tk.W)

        # Building selection
        ttk.Label(main_frame, text="Building:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.building_var = tk.StringVar()
        self.building_combo = ttk.Combobox(main_frame, textvariable=self.building_var, width=30)

        # Load buildings from database
        buildings = self.get_buildings_from_db()
        self.building_combo['values'] = buildings
        self.building_combo.grid(row=4, column=1, pady=5, sticky=tk.W)

        # Bind building selection to update rooms
        self.building_combo.bind('<<ComboboxSelected>>', self.on_building_selected)

        # Room
        ttk.Label(main_frame, text="Room:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)
        self.room_combo.grid(row=5, column=1, pady=5, sticky=tk.W)

        # Store all rooms for filtering
        self.all_rooms = []
        self.load_all_rooms()
        
        # Instructor
        ttk.Label(main_frame, text="Instructor:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)

        # Load instructors
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()

            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values
        except Exception:
            pass

        instructor_combo.grid(row=6, column=1, pady=5, sticky=tk.W)

        # Session type
        ttk.Label(main_frame, text="Session Type:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar()
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=7, column=1, pady=5, sticky=tk.W)

        # Conflict notification area
        ttk.Label(main_frame, text="Conflicts/Warnings:").grid(row=8, column=0, sticky=tk.NW, pady=5)
        self.conflict_text = tk.Text(main_frame, width=30, height=4, state='disabled', bg='#f0f0f0')
        self.conflict_text.grid(row=8, column=1, pady=5, sticky=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Check Conflicts", command=self.check_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save", command=self.save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def get_buildings_from_db(self):
        """Fetch list of buildings from facilities management database"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if buildings table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='buildings'
                """)

                if cursor.fetchone():
                    # Get all building names
                    cursor.execute("""
                        SELECT DISTINCT building_name FROM buildings
                        ORDER BY building_name
                    """)
                    buildings = [row[0] for row in cursor.fetchall()]

                    if buildings:
                        return buildings

                # Fallback: Get buildings from rooms table
                cursor.execute("""
                    SELECT DISTINCT building FROM rooms
                    WHERE building IS NOT NULL AND building != ''
                    ORDER BY building
                """)
                buildings = [row[0] for row in cursor.fetchall()]

                if not buildings:
                    return ["Main Building", "Science Building", "Library"]

                return buildings

        except Exception as e:
            print(f"Error fetching buildings: {e}")
            return ["Main Building", "Science Building", "Library"]

    def load_all_rooms(self):
        """Load all rooms from database"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number, capacity, room_type FROM rooms WHERE is_active = 1 ORDER BY building, room_number')
                self.all_rooms = cursor.fetchall()

        except Exception as e:
            print(f"Error loading rooms: {e}")
            self.all_rooms = []

    def on_building_selected(self, event=None):
        """Filter rooms by selected building"""
        selected_building = self.building_var.get()

        if not selected_building:
            # No building selected, show all rooms
            filtered_rooms = self.all_rooms
        else:
            # Filter rooms by building
            filtered_rooms = [room for room in self.all_rooms if room[1] == selected_building]

        # Update room combobox
        room_values = [f"{room[0]} - {room[1]}-{room[2]} (Cap: {room[3]}, {room[4]})" for room in filtered_rooms]
        self.room_combo['values'] = room_values

        # Clear current selection if not in filtered list
        if self.room_var.get() and not any(str(room[0]) in self.room_var.get() for room in filtered_rooms):
            self.room_var.set('')

    def check_conflicts(self):
        """Check for scheduling conflicts and display in textbox"""
        try:
            day = self.day_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            room_str = self.room_var.get()
            instructor_str = self.instructor_var.get()

            if not all([day, start_time, end_time, room_str, instructor_str]):
                self.update_conflict_text("Please fill in all fields to check conflicts.")
                return

            # Extract IDs
            room_id = int(room_str.split(' - ')[0])
            instructor_id = int(instructor_str.split(' - ')[0])

            conflicts = []

            # Check room conflicts
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # Check if room is already booked for this time slot
                cursor.execute('''
                    SELECT module_code, start_time, end_time
                    FROM module_schedule
                    WHERE room_id = ? AND day_of_week = ?
                    AND ((start_time < ? AND end_time > ?) OR (start_time < ? AND end_time > ?))
                ''', (room_id, day, end_time, start_time, end_time, end_time))

                room_conflicts = cursor.fetchall()
                if room_conflicts:
                    conflicts.append("ROOM CONFLICTS:")
                    for conflict in room_conflicts:
                        conflicts.append(f"  • {conflict[0]} ({conflict[1]}-{conflict[2]})")

                # Check instructor conflicts
                cursor.execute('''
                    SELECT module_code, start_time, end_time
                    FROM module_schedule
                    WHERE instructor_id = ? AND day_of_week = ?
                    AND ((start_time < ? AND end_time > ?) OR (start_time < ? AND end_time > ?))
                ''', (instructor_id, day, end_time, start_time, end_time, end_time))

                instructor_conflicts = cursor.fetchall()
                if instructor_conflicts:
                    if conflicts:
                        conflicts.append("")
                    conflicts.append("INSTRUCTOR CONFLICTS:")
                    for conflict in instructor_conflicts:
                        conflicts.append(f"  • {conflict[0]} ({conflict[1]}-{conflict[2]})")

            if conflicts:
                self.update_conflict_text("\n".join(conflicts))
            else:
                self.update_conflict_text("✓ No conflicts found. Room and instructor are available.")

        except Exception as e:
            self.update_conflict_text(f"Error checking conflicts: {str(e)}")

    def update_conflict_text(self, message):
        """Update the conflict text widget"""
        self.conflict_text.config(state='normal')
        self.conflict_text.delete(1.0, tk.END)
        self.conflict_text.insert(1.0, message)
        self.conflict_text.config(state='disabled')

    def save_schedule(self):
        try:
            module_code = self.module_var.get()
            day = self.day_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            room_str = self.room_var.get()
            instructor_str = self.instructor_var.get()
            session_type = self.session_type_var.get()

            if not all([module_code, day, start_time, end_time, room_str, instructor_str, session_type]):
                messagebox.showerror("Error", "Please fill in all fields.", parent=self.dialog)
                return

            # Extract IDs
            room_id = int(room_str.split(' - ')[0])
            instructor_id = int(instructor_str.split(' - ')[0])

            # Check for conflicts before saving
            self.check_conflicts()

            # Check if there are actual conflicts
            conflict_message = self.conflict_text.get(1.0, tk.END).strip()
            if conflict_message and not conflict_message.startswith("✓"):
                # Show warning but allow user to proceed
                response = messagebox.askyesno(
                    "Conflicts Detected",
                    "There are scheduling conflicts:\n\n" + conflict_message + "\n\nDo you want to save anyway?",
                    icon='warning'
                , parent=self.dialog)
                if not response:
                    return

            # Save schedule
            success = self.scheduler.add_module_schedule(
                module_code, day, start_time, end_time, room_id, instructor_id, session_type
            )

            if success:
                # Send notifications to instructor and students
                try:
                    # Get module info for the notification
                    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                        cursor = conn.cursor()

                        # Get module name if available
                        cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
                        module_result = cursor.fetchone()
                        module_name = module_result[0] if module_result else module_code

                        # Get instructor email
                        cursor.execute('SELECT email, first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
                        instructor = cursor.fetchone()

                        # Get room info
                        cursor.execute('SELECT building, room_number FROM rooms WHERE id = ?', (room_id,))
                        room_info = cursor.fetchone()
                        room_str = f"{room_info[0]}-{room_info[1]}" if room_info else "TBA"

                        # Create notification message
                        message = f"A new class has been scheduled:\n\n{module_name} ({module_code})\n{day} {start_time}-{end_time}\nRoom: {room_str}"

                        # Email all students and instructor using the new function
                        try:
                            target = self.gui or self.parent
                            summary = target.email_all_students_on_module(
                                module_code,
                                f"New Class Schedule: {module_code}",
                                message,
                                include_instructor=True
                            )
                            print(f"Emails sent: {summary['students_emailed']} students, instructor: {summary['instructor_emailed']}")
                            if summary['errors']:
                                for error in summary['errors']:
                                    print(f"  - {error}")
                        except Exception as e:
                            print(f"Note: Notifications may not have been sent: {e}")

                        conn.commit()

                except Exception as notif_error:
                    # Don't fail the save if notifications fail
                    print(f"Note: Notifications may not have been sent: {notif_error}")

                self.result = True
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save schedule: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class AddRoomDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Room")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Room number
        ttk.Label(main_frame, text="Room Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.room_number_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.room_number_var, width=30).grid(row=0, column=1, pady=5)

        # Building - Fetch from facilities management database
        ttk.Label(main_frame, text="Building:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.building_var = tk.StringVar()

        # Get list of buildings from database
        buildings = self.get_buildings_from_db()

        building_combo = ttk.Combobox(main_frame, textvariable=self.building_var,
                                      values=buildings, width=27, state='normal')
        building_combo.grid(row=1, column=1, pady=5)
        
        # Capacity
        ttk.Label(main_frame, text="Capacity:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)
        
        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)
        
        # Equipment
        ttk.Label(main_frame, text="Equipment:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_var = tk.StringVar()
        equipment_entry = tk.Text(main_frame, width=30, height=3)
        equipment_entry.grid(row=4, column=1, pady=5)
        self.equipment_text = equipment_entry
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        notes_entry = tk.Text(main_frame, width=30, height=3)
        notes_entry.grid(row=5, column=1, pady=5)
        self.notes_text = notes_entry
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def get_buildings_from_db(self):
        """Fetch list of buildings from facilities management database"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if buildings table exists
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='buildings'
                """)

                if cursor.fetchone():
                    # Get all building names
                    cursor.execute("""
                        SELECT building_name FROM buildings
                        ORDER BY building_name
                    """)
                    buildings = [row[0] for row in cursor.fetchall()]

                    # If no buildings found, return default list
                    if not buildings:
                        return ["Main Building", "Science Building", "Library", "Sports Center"]

                    return buildings
                else:
                    # Table doesn't exist, return default list
                    return ["Main Building", "Science Building", "Library", "Sports Center"]

        except Exception as e:
            # On error, return default list
            print(f"Error fetching buildings: {e}")
            return ["Main Building", "Science Building", "Library", "Sports Center"]

    def save_room(self):
        try:
            room_number = self.room_number_var.get()
            building = self.building_var.get()
            capacity = int(self.capacity_var.get())
            room_type = self.room_type_var.get()
            equipment = self.equipment_text.get(1.0, tk.END).strip()
            notes = self.notes_text.get(1.0, tk.END).strip()

            if not all([room_number, building, str(capacity), room_type]):
                messagebox.showerror("Error", "Please fill in all required fields.", parent=self.dialog)
                return

            room_id = self.scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)

            if room_id:
                self.result = True
                self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Capacity must be a number.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save room: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class AddInstructorDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Instructor")
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Email:").grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Professional Information
        prof_frame = ttk.LabelFrame(main_frame, text="Professional Information", padding=10)
        prof_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prof_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Specialization:").grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Courses/Semester:").grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value="4")
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value="40")
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Scheduling Preferences
        sched_frame = ttk.LabelFrame(main_frame, text="Scheduling Preferences", padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text="Preferred Days:").grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., Monday,Tuesday)", font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text="Preferred Times:").grid(row=2, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., 09:00,10:00)", font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Instructor", command=self.save_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def save_instructor(self):
        try:
            # Validate inputs
            first_name = self.first_name_var.get().strip()
            last_name = self.last_name_var.get().strip()
            email = self.email_var.get().strip()

            if not first_name or not last_name or not email:
                messagebox.showerror("Validation Error", "First name, last name, and email are required.", parent=self.dialog)
                return

            # Validate email format
            import re
            email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
            if not re.match(email_pattern, email):
                messagebox.showerror("Validation Error", "Please enter a valid email address.", parent=self.dialog)
                return

            department = self.department_var.get().strip()
            specialization = self.specialization_var.get().strip()

            try:
                max_courses = int(self.max_courses_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max courses must be a number.", parent=self.dialog)
                return

            try:
                max_hours = int(self.max_hours_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max hours must be a number.", parent=self.dialog)
                return

            preferred_days = self.preferred_days_var.get().strip()
            preferred_times = self.preferred_times_var.get().strip()

            # Use database directly instead of scheduler method for consistency
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # Check for duplicate email
                cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
                if cursor.fetchone():
                    messagebox.showerror("Duplicate Error", f"Email '{email}' already exists.", parent=self.dialog)
                    return

                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO instructors (first_name, last_name, email, department, specialization,
                                       max_courses_per_semester, max_hours_per_week, preferred_days,
                                       preferred_times, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, department, specialization, max_courses,
                      max_hours, preferred_days, preferred_times, timestamp, timestamp))

                conn.commit()

            self.result = True
            messagebox.showinfo("Success", f"Instructor {first_name} {last_name} added successfully.", parent=self.dialog)
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save instructor: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class EditScheduleDialog:
    def __init__(self, parent, scheduler, schedule_id, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui
        self.schedule_id = schedule_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Schedule")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current schedule data"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type
                FROM module_schedule WHERE id = ?
                ''', (self.schedule_id,))

                schedule = cursor.fetchone()
            
            if schedule:
                self.current_data = {
                    'module_code': schedule[0],
                    'day_of_week': schedule[1],
                    'start_time': schedule[2],
                    'end_time': schedule[3],
                    'room_id': schedule[4],
                    'instructor_id': schedule[5],
                    'session_type': schedule[6]
                }
            else:
                raise CourseNotFoundError(f"Schedule {self.schedule_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror("Error", f"Failed to load schedule data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Module selection
        ttk.Label(main_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar(value=self.current_data['module_code'])
        module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)
        
        # Load modules
        try:
            modules = self.scheduler._get_known_modules()
            module_combo['values'] = list(modules.keys())
        except (AttributeError, Exception):
            pass
        
        module_combo.grid(row=0, column=1, pady=5, sticky=tk.W)
        
        # Day of week
        ttk.Label(main_frame, text="Day of Week:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar(value=self.current_data['day_of_week'])
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=1, column=1, pady=5, sticky=tk.W)
        
        # Time
        ttk.Label(main_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value=self.current_data['start_time'])
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=2, column=1, pady=5, sticky=tk.W)
        
        ttk.Label(main_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value=self.current_data['end_time'])
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=3, column=1, pady=5, sticky=tk.W)
        
        # Room
        ttk.Label(main_frame, text="Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)
        
        # Load rooms and set current
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number FROM rooms WHERE is_active = 1')
                rooms = cursor.fetchall()
            
            room_values = [f"{room[0]} - {room[1]}-{room[2]}" for room in rooms]
            room_combo['values'] = room_values
            
            # Set current room
            for room in rooms:
                if room[0] == self.current_data['room_id']:
                    self.room_var.set(f"{room[0]} - {room[1]}-{room[2]}")
                    break
        except Exception:
            pass
        
        room_combo.grid(row=4, column=1, pady=5, sticky=tk.W)
        
        # Instructor
        ttk.Label(main_frame, text="Instructor:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)
        
        # Load instructors and set current
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()
            
            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values
            
            # Set current instructor
            for inst in instructors:
                if inst[0] == self.current_data['instructor_id']:
                    self.instructor_var.set(f"{inst[0]} - {inst[1]} {inst[2]}")
                    break
        except Exception:
            pass
        
        instructor_combo.grid(row=5, column=1, pady=5, sticky=tk.W)
        
        # Session type
        ttk.Label(main_frame, text="Session Type:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar(value=self.current_data['session_type'])
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=6, column=1, pady=5, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_schedule(self):
        try:
            # Get new values
            updates = {}

            if self.day_var.get() != self.current_data['day_of_week']:
                updates['day_of_week'] = self.day_var.get()

            if self.start_time_var.get() != self.current_data['start_time']:
                updates['start_time'] = self.start_time_var.get()

            if self.end_time_var.get() != self.current_data['end_time']:
                updates['end_time'] = self.end_time_var.get()

            room_str = self.room_var.get()
            if room_str:
                room_id = int(room_str.split(' - ')[0])
                if room_id != self.current_data['room_id']:
                    updates['room_id'] = room_id

            instructor_str = self.instructor_var.get()
            if instructor_str:
                instructor_id = int(instructor_str.split(' - ')[0])
                if instructor_id != self.current_data['instructor_id']:
                    updates['instructor_id'] = instructor_id

            if self.session_type_var.get() != self.current_data['session_type']:
                updates['session_type'] = self.session_type_var.get()

            if not updates:
                messagebox.showinfo("Info", "No changes detected.", parent=self.dialog)
                return

            # Update schedule
            success = self.scheduler.update_module_schedule(self.schedule_id, **updates)

            if success:
                # Send notifications about schedule changes to instructor and students
                try:
                    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                        cursor = conn.cursor()

                        # Get schedule details
                        cursor.execute('''
                            SELECT ms.module_code, ms.instructor_id
                            FROM module_schedule ms
                            WHERE ms.id = ?
                        ''', (self.schedule_id,))
                        schedule = cursor.fetchone()

                        if schedule:
                            module_code, instructor_id = schedule

                            # Get module name
                            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
                            module_result = cursor.fetchone()
                            module_name = module_result[0] if module_result else module_code

                            # Create change description
                            changes = []
                            for key, value in updates.items():
                                if key == 'day_of_week':
                                    changes.append(f"Day: {value}")
                                elif key == 'start_time':
                                    changes.append(f"Start: {value}")
                                elif key == 'end_time':
                                    changes.append(f"End: {value}")
                                elif key == 'room_id':
                                    cursor.execute('SELECT building, room_number FROM rooms WHERE id = ?', (value,))
                                    room = cursor.fetchone()
                                    if room:
                                        changes.append(f"Room: {room[0]}-{room[1]}")

                            change_desc = ", ".join(changes) if changes else "schedule updated"
                            message = f"The schedule for {module_name} ({module_code}) has been updated:\n\nChanges: {change_desc}"

                            # Email all students and instructor using the new function
                            try:
                                target = self.gui or self.parent
                                summary = target.email_all_students_on_module(
                                    module_code,
                                    f"Schedule Changed: {module_code}",
                                    message,
                                    include_instructor=True
                                )
                                print(f"Schedule change emails sent: {summary['students_emailed']} students, instructor: {summary['instructor_emailed']}")
                                if summary['errors']:
                                    for error in summary['errors']:
                                        print(f"  - {error}")
                            except Exception as e:
                                print(f"Note: Notifications may not have been sent: {e}")

                        conn.commit()

                except Exception as notif_error:
                    # Don't fail the update if notifications fail
                    print(f"Note: Notifications may not have been sent: {notif_error}")

                self.result = True
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update schedule: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class EditRoomDialog:
    def __init__(self, parent, scheduler, room_id):
        self.parent = parent
        self.scheduler = scheduler
        self.room_id = room_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Room")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current room data"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM rooms WHERE id = ?', (self.room_id,))
                room = cursor.fetchone()
            
            if room:
                self.current_data = {
                    'room_number': room[1],
                    'building': room[2],
                    'capacity': room[3],
                    'room_type': room[4],
                    'equipment': room[5] or "",
                    'notes': room[6] or ""
                }
            else:
                raise CourseNotFoundError(f"Room {self.room_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror("Error", f"Failed to load room data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Room number (read-only)
        ttk.Label(main_frame, text="Room Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        room_label = ttk.Label(main_frame, text=self.current_data['room_number'], font=('Arial', 10, 'bold'))
        room_label.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Building (read-only)
        ttk.Label(main_frame, text="Building:").grid(row=1, column=0, sticky=tk.W, pady=5)
        building_label = ttk.Label(main_frame, text=self.current_data['building'], font=('Arial', 10, 'bold'))
        building_label.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Capacity
        ttk.Label(main_frame, text="Capacity:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar(value=str(self.current_data['capacity']))
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)
        
        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar(value=self.current_data['room_type'])
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)
        
        # Equipment
        ttk.Label(main_frame, text="Equipment:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_text = tk.Text(main_frame, width=30, height=3)
        self.equipment_text.grid(row=4, column=1, pady=5)
        self.equipment_text.insert(1.0, self.current_data['equipment'])
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(main_frame, width=30, height=3)
        self.notes_text.grid(row=5, column=1, pady=5)
        self.notes_text.insert(1.0, self.current_data['notes'])
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_room(self):
        try:
            new_capacity = int(self.capacity_var.get())
            new_equipment = self.equipment_text.get(1.0, tk.END).strip()
            new_notes = self.notes_text.get(1.0, tk.END).strip()

            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE rooms SET capacity = ?, equipment = ?, notes = ? WHERE id = ?
                ''', (new_capacity, new_equipment, new_notes, self.room_id))

                conn.commit()
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Room updated successfully.", parent=self.dialog)
            
        except ValueError:
            messagebox.showerror("Error", "Capacity must be a number.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update room: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class EditInstructorDialog:
    def __init__(self, parent, scheduler, instructor_id):
        self.parent = parent
        self.scheduler = scheduler
        self.instructor_id = instructor_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Instructor")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current instructor data"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, first_name, last_name, email, department,
                       COALESCE(max_hours_per_week, max_courses_per_semester * 8, 40) as max_hours_per_week,
                       preferred_days, preferred_times
                FROM instructors WHERE id = ?
                ''', (self.instructor_id,))
                instructor = cursor.fetchone()
            
            if instructor:
                self.current_data = {
                    'first_name': instructor[1],
                    'last_name': instructor[2],
                    'email': instructor[3],
                    'department': instructor[4],
                    'max_hours_per_week': instructor[5],
                    'preferred_days': instructor[6] or "",
                    'preferred_times': instructor[7] or ""
                }
            else:
                raise CourseNotFoundError(f"Instructor {self.instructor_id}")

        except (CourseNotFoundError, sqlite3.Error) as e:
            messagebox.showerror("Error", f"Failed to load instructor data: {str(e)}", parent=self.dialog)
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name (read-only)
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_label = ttk.Label(main_frame, text=f"{self.current_data['first_name']} {self.current_data['last_name']}", 
                              font=('Arial', 10, 'bold'))
        name_label.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Email
        ttk.Label(main_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar(value=self.current_data['email'])
        ttk.Entry(main_frame, textvariable=self.email_var, width=30).grid(row=1, column=1, pady=5)
        
        # Department
        ttk.Label(main_frame, text="Department:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.department_var = tk.StringVar(value=self.current_data['department'])
        ttk.Entry(main_frame, textvariable=self.department_var, width=30).grid(row=2, column=1, pady=5)
        
        # Max hours
        ttk.Label(main_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_hours_var = tk.StringVar(value=str(self.current_data['max_hours_per_week']))
        ttk.Entry(main_frame, textvariable=self.max_hours_var, width=30).grid(row=3, column=1, pady=5)
        
        # Preferred days
        ttk.Label(main_frame, text="Preferred Days:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.preferred_days_var = tk.StringVar(value=self.current_data['preferred_days'])
        ttk.Entry(main_frame, textvariable=self.preferred_days_var, width=30).grid(row=4, column=1, pady=5)
        
        # Preferred times
        ttk.Label(main_frame, text="Preferred Times:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.preferred_times_var = tk.StringVar(value=self.current_data['preferred_times'])
        ttk.Entry(main_frame, textvariable=self.preferred_times_var, width=30).grid(row=5, column=1, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_instructor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_instructor(self):
        try:
            new_email = self.email_var.get()
            new_department = self.department_var.get()
            new_max_hours = int(self.max_hours_var.get())
            new_preferred_days = self.preferred_days_var.get()
            new_preferred_times = self.preferred_times_var.get()

            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                # Check which column exists for max hours
                cursor.execute("PRAGMA table_info(instructors)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'max_hours_per_week' in columns:
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_hours_per_week = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_max_hours, new_preferred_days, new_preferred_times, self.instructor_id))
                elif 'max_courses_per_semester' in columns:
                    # Convert hours to courses (assuming 8 hours per course)
                    max_courses = max(1, round(float(new_max_hours) / 8))
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_courses_per_semester = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, max_courses, new_preferred_days, new_preferred_times, self.instructor_id))
                else:
                    # Fallback - update without max hours column
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_preferred_days, new_preferred_times, self.instructor_id))

                conn.commit()
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Instructor updated successfully.", parent=self.dialog)
            
        except ValueError:
            messagebox.showerror("Error", "Max hours must be a number.", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update instructor: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class AddHolidayDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Holiday")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Holiday name
        ttk.Label(main_frame, text="Holiday Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5)
        
        # Start date
        ttk.Label(main_frame, text="Start Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=1, column=1, pady=5)
        ttk.Label(main_frame, text="(YYYY-MM-DD format)", font=('Arial', 8)).grid(row=1, column=2, sticky=tk.W)
        
        # End date
        ttk.Label(main_frame, text="End Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=30).grid(row=2, column=1, pady=5)
        ttk.Label(main_frame, text="(leave blank if same as start)", font=('Arial', 8)).grid(row=2, column=2, sticky=tk.W)
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.description_text = tk.Text(main_frame, width=30, height=3)
        self.description_text.grid(row=3, column=1, pady=5)
        
        # Recurring
        self.recurring_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Recurring annually", variable=self.recurring_var).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_holiday).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_holiday(self):
        try:
            name = self.name_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get() or start_date
            description = self.description_text.get(1.0, tk.END).strip()
            recurring = self.recurring_var.get()
            
            if not all([name, start_date]):
                messagebox.showerror("Error", "Please fill in name and start date.", parent=self.dialog)
                return
            
            # Validate date format
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                if end_date != start_date:
                    datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.", parent=self.dialog)
                return
            
            self.scheduler.add_holiday(name, start_date, end_date, description, recurring)
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Holiday added successfully.", parent=self.dialog)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save holiday: {str(e)}", parent=self.dialog)
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

class GridViewWindow:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        
        self.window = tk.Toplevel(parent)
        self.window.title("Schedule Grid View")
        self.window.geometry("1200x800")
        self.window.transient(parent)
        
        self.create_grid_view()
        self.center_window()
    
    def create_grid_view(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Weekly Schedule Grid View", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Create grid frame with scrollbars
        grid_frame = ttk.Frame(main_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for scrolling
        canvas = tk.Canvas(grid_frame)
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Create the actual grid
        self.create_schedule_grid(scrollable_frame)
        
        # Pack scrollbars and canvas
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_schedule_grid(self, parent_frame):
        """Create the schedule grid with proper boxes"""
        try:
            # Get all schedules
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                       r.building, r.room_number, ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                ORDER BY ms.day_of_week, ms.start_time
                ''')

                schedules = cursor.fetchall()

            # Create grid data structure
            grid_data = {}
            for day in DAYS_OF_WEEK:
                grid_data[day] = {}
                for time_slot in TIME_SLOTS:
                    grid_data[day][time_slot] = []

            # Populate grid with schedule data
            for schedule in schedules:
                module_code, day, start_time, end_time, building, room_number, session_type = schedule

                # Find the closest time slot
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

                # Create session info
                room_str = f"{building}-{room_number}" if building and room_number else "TBA"
                session_info = {
                    'module': module_code,
                    'type': session_type,
                    'room': room_str,
                    'time': f"{start_time}-{end_time}"
                }

                if day in grid_data and closest_slot in grid_data[day]:
                    grid_data[day][closest_slot].append(session_info)

            # Create grid with proper boxes
            # Header row with time column
            time_header = tk.Label(parent_frame, text="Time", font=('Arial', 11, 'bold'),
                                   relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                   width=12, height=2)
            time_header.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")

            # Day headers
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                day_header = tk.Label(parent_frame, text=day, font=('Arial', 11, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                      width=20, height=2)
                day_header.grid(row=0, column=col, padx=2, pady=2, sticky="nsew")

            # Create time slots and schedule cells
            for row, time_slot in enumerate(TIME_SLOTS, 1):
                # Time label with box
                time_label = tk.Label(parent_frame, text=time_slot, font=('Arial', 10, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                      width=12, height=4)
                time_label.grid(row=row, column=0, padx=2, pady=2, sticky="nsew")

                # Schedule cells for each day
                for col, day in enumerate(DAYS_OF_WEEK, 1):
                    entries = grid_data[day][time_slot]

                    # Create cell frame with visible border
                    cell_frame = tk.Frame(parent_frame, relief=tk.SOLID, borderwidth=2,
                                         bg='#d4edda' if entries else 'white',
                                         width=180, height=100)
                    cell_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    cell_frame.grid_propagate(False)

                    if entries:
                        # Create inner container for better padding
                        inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                        inner_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                        # Display schedule entries
                        for i, entry in enumerate(entries):
                            if i < 2:  # Limit to 2 entries per cell
                                # Create a box for each session
                                session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                       bg='#c3e6cb', padx=3, pady=3)
                                session_box.pack(fill=tk.X, pady=2)

                                # Module code - bold and larger
                                module_label = tk.Label(session_box, text=entry['module'],
                                                        font=('Arial', 9, 'bold'),
                                                        bg='#c3e6cb', fg='#155724')
                                module_label.pack(anchor='w')

                                # Session type
                                type_label = tk.Label(session_box, text=entry['type'],
                                                      font=('Arial', 8),
                                                      bg='#c3e6cb', fg='#155724')
                                type_label.pack(anchor='w')

                                # Room
                                room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                      font=('Arial', 7),
                                                      bg='#c3e6cb', fg='#155724')
                                room_label.pack(anchor='w')

                                # Time
                                time_label = tk.Label(session_box, text=entry['time'],
                                                      font=('Arial', 7, 'italic'),
                                                      bg='#c3e6cb', fg='#155724')
                                time_label.pack(anchor='w')

                        if len(entries) > 2:
                            more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                                  font=('Arial', 7, 'italic'),
                                                  bg='#d4edda', fg='#155724')
                            more_label.pack(pady=2)
                    else:
                        # Empty cell indicator
                        empty_label = tk.Label(cell_frame, text="-", font=('Arial', 12),
                                               bg='white', fg='#cccccc')
                        empty_label.place(relx=0.5, rely=0.5, anchor='center')

            # Configure grid weights for proper resizing
            for i in range(len(TIME_SLOTS) + 1):
                parent_frame.grid_rowconfigure(i, weight=0, minsize=100)
            for i in range(len(DAYS_OF_WEEK) + 1):
                parent_frame.grid_columnconfigure(i, weight=0, minsize=180 if i > 0 else 100)

        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"Error creating grid: {str(e)}")
            error_label.pack(pady=20)
    
    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")

