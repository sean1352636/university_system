from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.post_18.university_system.core.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.post_18.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
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
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (
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
        from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI

def suggest_optimal_time_slot(self, module_code, session_type, duration_minutes=60):
    """Suggest optimal time slots for a new schedule"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get module information
        cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
        if not cursor.fetchone():
            messagebox.showerror("Error", f"Module {module_code} does not exist.", parent=self.root)
            return []

        suggestions = []

        for day in DAYS_OF_WEEK:
            for time_slot in TIME_SLOTS:
                # Calculate end time
                start_hour, start_min = map(int, time_slot.split(':'))
                end_time = datetime.strptime(time_slot, "%H:%M") + timedelta(minutes=duration_minutes)
                end_time_str = end_time.strftime("%H:%M")

                # Check availability
                score = self._calculate_slot_score(day, time_slot, end_time_str, session_type)

                if score > 0:  # Only suggest available slots
                    suggestions.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': end_time_str,
                        'score': score,
                        'reasons': self._get_score_reasons(day, time_slot, session_type)
                    })

        # Sort by score (highest first)
        suggestions.sort(key=lambda x: x['score'], reverse=True)

        return suggestions[:10]  # Return top 10 suggestions

ModuleSchedulingGUI.suggest_optimal_time_slot = suggest_optimal_time_slot

def _calculate_slot_score(self, day, start_time, end_time, session_type):
    """Calculate a score for a time slot based on various factors"""
    with get_connection() as conn:
        cursor = conn.cursor()

        score = 100  # Start with base score

        # Check for conflicts
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchone()[0]
        if conflicts > 0:
            score = 0  # No score for conflicting slots
            return score

        # Bonus for popular time slots (but not too crowded)
        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND start_time = ?
        ''', (day, start_time))

        same_time_count = cursor.fetchone()[0]
        if 1 <= same_time_count <= 3:  # Sweet spot
            score += 10
        elif same_time_count > 5:  # Too crowded
            score -= 20

        # Preference bonuses
        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            score += 15  # Morning lectures preferred
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            score += 10  # Afternoon labs preferred

        # Day preferences
        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            score += 5  # Mid-week preferred

        return score

ModuleSchedulingGUI._calculate_slot_score = _calculate_slot_score

def _get_score_reasons(self, day, start_time, session_type):
    """Get human-readable reasons for the score"""
    reasons = []

    if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
        reasons.append("Good time for lectures")
    elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
        reasons.append("Preferred afternoon lab time")

    if day in ['Tuesday', 'Wednesday', 'Thursday']:
        reasons.append("Mid-week scheduling preferred")

    if start_time in ['09:00', '10:00']:
        reasons.append("Popular morning slot")

    return reasons

ModuleSchedulingGUI._get_score_reasons = _get_score_reasons

def find_alternative_slots(self, day, start_time, end_time, room_type=None):
    """Find alternative time slots when conflicts occur"""
    alternatives = []

    # Try same day, different times
    for time_slot in TIME_SLOTS:
        if time_slot != start_time:
            duration = self._calculate_duration(start_time, end_time)
            alt_end = self._add_minutes_to_time(time_slot, duration)

            if self._is_slot_available(day, time_slot, alt_end):
                alternatives.append({
                    'day': day,
                    'start_time': time_slot,
                    'end_time': alt_end,
                    'type': 'same_day'
                })

    # Try same time, different days
    for alt_day in DAYS_OF_WEEK:
        if alt_day != day and self._is_slot_available(alt_day, start_time, end_time):
            alternatives.append({
                'day': alt_day,
                'start_time': start_time,
                'end_time': end_time,
                'type': 'same_time'
            })

    return alternatives

ModuleSchedulingGUI.find_alternative_slots = find_alternative_slots

def _calculate_duration(self, start_time, end_time):
    """Calculate duration in minutes between two times"""
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    return int((end - start).total_seconds() / 60)

ModuleSchedulingGUI._calculate_duration = _calculate_duration

def _add_minutes_to_time(self, time_str, minutes):
    """Add minutes to a time string"""
    time_obj = datetime.strptime(time_str, "%H:%M")
    new_time = time_obj + timedelta(minutes=minutes)
    return new_time.strftime("%H:%M")

ModuleSchedulingGUI._add_minutes_to_time = _add_minutes_to_time

def _is_slot_available(self, day, start_time, end_time):
    """Check if a time slot is available"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT COUNT(*) FROM module_schedule
        WHERE day_of_week = ? AND (
            (start_time < ? AND end_time > ?) OR
            (start_time < ? AND end_time > ?) OR
            (start_time >= ? AND end_time <= ?)
        )
        ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

        conflicts = cursor.fetchone()[0]

        return conflicts == 0

ModuleSchedulingGUI._is_slot_available = _is_slot_available

def schedule_module_interactively(self):
    """Interactive module scheduling wizard with optimal time slot suggestions"""
    # Create a dialog window for interactive scheduling
    dialog = tk.Toplevel(self.root)
    dialog.title("Interactive Module Scheduling Wizard")
    dialog.geometry("800x700")
    dialog.transient(self.root)
    dialog.grab_set()

    # Variables to store selections
    selected_module = tk.StringVar()
    selected_day = tk.StringVar()
    selected_session_type = tk.StringVar(value="Lecture")
    duration_var = tk.IntVar(value=60)

    # Main frame with scrollbar
    main_frame = ttk.Frame(dialog, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = ttk.Label(main_frame, text="Module Scheduling Wizard",
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=(0, 20))

    # Step 1: Select Module
    step1_frame = ttk.LabelFrame(main_frame, text="Step 1: Select Module", padding="10")
    step1_frame.pack(fill=tk.X, pady=10)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
        modules = cursor.fetchall()

    module_options = [f"{code} - {name}" for code, name in modules]
    module_combo = ttk.Combobox(step1_frame, textvariable=selected_module,
                               values=module_options, width=60, state='readonly')
    module_combo.pack(fill=tk.X, pady=5)
    if module_options:
        module_combo.current(0)

    # Step 2: Session Type and Duration
    step2_frame = ttk.LabelFrame(main_frame, text="Step 2: Session Type & Duration", padding="10")
    step2_frame.pack(fill=tk.X, pady=10)

    type_frame = ttk.Frame(step2_frame)
    type_frame.pack(fill=tk.X, pady=5)
    ttk.Label(type_frame, text="Session Type:").pack(side=tk.LEFT, padx=5)
    session_combo = ttk.Combobox(type_frame, textvariable=selected_session_type,
                                values=SESSION_TYPES, width=20, state='readonly')
    session_combo.pack(side=tk.LEFT, padx=5)
    session_combo.current(0)

    duration_frame = ttk.Frame(step2_frame)
    duration_frame.pack(fill=tk.X, pady=5)
    ttk.Label(duration_frame, text="Duration (minutes):").pack(side=tk.LEFT, padx=5)
    duration_spin = ttk.Spinbox(duration_frame, from_=30, to=180, increment=15,
                               textvariable=duration_var, width=10)
    duration_spin.pack(side=tk.LEFT, padx=5)

    # Step 3: Get Suggestions
    step3_frame = ttk.LabelFrame(main_frame, text="Step 3: Suggested Time Slots", padding="10")
    step3_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    # Suggestions tree
    columns = ('Day', 'Start Time', 'End Time', 'Score', 'Reasons')
    suggestions_tree = ttk.Treeview(step3_frame, columns=columns, show='headings', height=10)

    for col in columns:
        suggestions_tree.heading(col, text=col)
        suggestions_tree.column(col, width=120 if col != 'Reasons' else 250)

    suggestions_tree.pack(fill=tk.BOTH, expand=True, pady=5)

    # Scrollbar for suggestions
    suggestions_scroll = ttk.Scrollbar(step3_frame, orient=tk.VERTICAL,
                                      command=suggestions_tree.yview)
    suggestions_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    suggestions_tree.configure(yscrollcommand=suggestions_scroll.set)

    def get_suggestions():
        """Fetch and display suggestions"""
        suggestions_tree.delete(*suggestions_tree.get_children())

        module_text = selected_module.get()
        if not module_text:
            messagebox.showwarning("Warning", "Please select a module first.", parent=self.root)
            return

        module_code = module_text.split(' - ')[0]
        session_type = selected_session_type.get()
        duration = duration_var.get()

        suggestions = self.suggest_optimal_time_slot(module_code, session_type, duration)

        for suggestion in suggestions:
            reasons_text = ', '.join(suggestion['reasons']) if suggestion['reasons'] else 'Available slot'
            suggestions_tree.insert('', tk.END, values=(
                suggestion['day'],
                suggestion['start_time'],
                suggestion['end_time'],
                suggestion['score'],
                reasons_text
            ))

    # Get Suggestions button
    suggest_btn = ttk.Button(step3_frame, text="Get Optimal Time Slots",
                            command=get_suggestions, style='Action.TButton')
    suggest_btn.pack(pady=5)

    # Step 4: Finalize Scheduling
    step4_frame = ttk.LabelFrame(main_frame, text="Step 4: Finalize Schedule", padding="10")
    step4_frame.pack(fill=tk.X, pady=10)

    # Room and Instructor selection
    room_var = tk.StringVar()
    instructor_var = tk.StringVar()

    room_frame = ttk.Frame(step4_frame)
    room_frame.pack(fill=tk.X, pady=5)
    ttk.Label(room_frame, text="Room:").pack(side=tk.LEFT, padx=5)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, building, room_number, room_type FROM rooms WHERE is_active = 1")
        rooms = cursor.fetchall()

    room_options = [f"{building}-{room_num} ({room_type})" for _, building, room_num, room_type in rooms]
    room_combo = ttk.Combobox(room_frame, textvariable=room_var,
                             values=room_options, width=40, state='readonly')
    room_combo.pack(side=tk.LEFT, padx=5)
    if room_options:
        room_combo.current(0)

    instructor_frame = ttk.Frame(step4_frame)
    instructor_frame.pack(fill=tk.X, pady=5)
    ttk.Label(instructor_frame, text="Instructor:").pack(side=tk.LEFT, padx=5)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, department FROM instructors WHERE is_active = 1")
        instructors = cursor.fetchall()

    instructor_options = [f"{first} {last} ({dept})" for _, first, last, dept in instructors]
    instructor_combo = ttk.Combobox(instructor_frame, textvariable=instructor_var,
                                   values=instructor_options, width=40, state='readonly')
    instructor_combo.pack(side=tk.LEFT, padx=5)
    if instructor_options:
        instructor_combo.current(0)

    def schedule_selected():
        """Schedule the module with selected time slot"""
        selection = suggestions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a suggested time slot.", parent=self.root)
            return

        item = suggestions_tree.item(selection[0])
        values = item['values']

        module_text = selected_module.get()
        module_code = module_text.split(' - ')[0]

        day = values[0]
        start_time = values[1]
        end_time = values[2]
        session_type = selected_session_type.get()

        # Get room and instructor IDs
        room_idx = room_combo.current()
        instructor_idx = instructor_combo.current()

        if room_idx < 0 or instructor_idx < 0:
            messagebox.showwarning("Warning", "Please select both room and instructor.", parent=self.root)
            return

        room_id = rooms[room_idx][0]
        instructor_id = instructors[instructor_idx][0]

        # Add the schedule
        try:
            self.scheduler.add_module_schedule(
                module_code, day, start_time, end_time,
                room_id, instructor_id, session_type
            )
            messagebox.showinfo("Success", "Module scheduled successfully!", parent=self.root)
            self.refresh_all_data()
            dialog.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule module: {str(e)}", parent=self.root)

    # Bottom buttons
    button_frame = ttk.Frame(step4_frame)
    button_frame.pack(fill=tk.X, pady=10)

    schedule_btn = ttk.Button(button_frame, text="Schedule Selected Slot",
                             command=schedule_selected, style='Success.TButton')
    schedule_btn.pack(side=tk.LEFT, padx=5)

    cancel_btn = ttk.Button(button_frame, text="Cancel",
                           command=dialog.destroy)
    cancel_btn.pack(side=tk.LEFT, padx=5)

ModuleSchedulingGUI.schedule_module_interactively = schedule_module_interactively

def advanced_schedule_search(self, filters=None):
    """Advanced search with multiple criteria"""
    if filters is None:
        filters = {}

    with get_connection() as conn:
        cursor = conn.cursor()

        # Build dynamic query
        base_query = '''
        SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
               ms.start_time, ms.end_time, r.building, r.room_number,
               i.first_name, i.last_name, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE 1=1
        '''

        params = []

        # Add filters
        if 'module_code' in filters and filters['module_code']:
            base_query += " AND ms.module_code LIKE ?"
            params.append(f"%{escape_like(filters['module_code'])}%")

        if 'day' in filters and filters['day']:
            base_query += " AND ms.day_of_week = ?"
            params.append(filters['day'])

        if 'time_from' in filters and filters['time_from']:
            base_query += " AND ms.start_time >= ?"
            params.append(filters['time_from'])

        if 'time_to' in filters and filters['time_to']:
            base_query += " AND ms.end_time <= ?"
            params.append(filters['time_to'])

        if 'session_type' in filters and filters['session_type']:
            base_query += " AND ms.session_type = ?"
            params.append(filters['session_type'])

        if 'instructor' in filters and filters['instructor']:
            base_query += " AND (i.first_name LIKE ? OR i.last_name LIKE ?)"
            params.extend([f"%{escape_like(filters['instructor'])}%", f"%{escape_like(filters['instructor'])}%"])

        if 'building' in filters and filters['building']:
            base_query += " AND r.building LIKE ?"
            params.append(f"%{escape_like(filters['building'])}%")

        if 'room_type' in filters and filters['room_type']:
            base_query += " AND r.room_type = ?"
            params.append(filters['room_type'])

        base_query += " ORDER BY ms.day_of_week, ms.start_time"

        cursor.execute(base_query, params)
        results = cursor.fetchall()

        return results

ModuleSchedulingGUI.advanced_schedule_search = advanced_schedule_search

def find_schedule_gaps(self, entity_type, entity_id):
    """Find free periods in student or instructor schedules"""
    with get_connection() as conn:
        cursor = conn.cursor()

        if entity_type == 'student':
            # Get student's enrolled modules
            cursor.execute('SELECT module_code FROM student_modules WHERE student_id = ?', (entity_id,))
            modules = [row[0] for row in cursor.fetchall()]

            if not modules:
                return "Student not enrolled in any modules"

            # Get schedule for these modules
            placeholders = ','.join(['?'] * len(modules))
            query = f'''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE module_code IN ({placeholders})
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, modules)

        elif entity_type == 'instructor':
            query = '''
            SELECT day_of_week, start_time, end_time
            FROM module_schedule
            WHERE instructor_id = ?
            ORDER BY day_of_week, start_time
            '''
            cursor.execute(query, (entity_id,))

        schedules = cursor.fetchall()

        # Find gaps
        gaps = {}
        for day in DAYS_OF_WEEK:
            day_schedules = [s for s in schedules if s[0] == day]
            gaps[day] = self._find_daily_gaps(day_schedules)

        return gaps

ModuleSchedulingGUI.find_schedule_gaps = find_schedule_gaps

def _find_daily_gaps(self, day_schedules):
    """Find gaps in a single day's schedule"""
    if not day_schedules:
        return [{'start': '09:00', 'end': '17:00', 'duration': 480}]

    # Sort by start time
    day_schedules.sort(key=lambda x: x[1])

    gaps = []

    # Gap before first class
    first_start = day_schedules[0][1]
    if first_start > '09:00':
        duration = self._calculate_duration('09:00', first_start)
        gaps.append({'start': '09:00', 'end': first_start, 'duration': duration})

    # Gaps between classes
    for i in range(len(day_schedules) - 1):
        current_end = day_schedules[i][2]
        next_start = day_schedules[i + 1][1]

        if current_end < next_start:
            duration = self._calculate_duration(current_end, next_start)
            if duration >= 30:  # Only count gaps of 30+ minutes
                gaps.append({'start': current_end, 'end': next_start, 'duration': duration})

    # Gap after last class
    last_end = day_schedules[-1][2]
    if last_end < '17:00':
        duration = self._calculate_duration(last_end, '17:00')
        gaps.append({'start': last_end, 'end': '17:00', 'duration': duration})

    return gaps

ModuleSchedulingGUI._find_daily_gaps = _find_daily_gaps

def validate_data_consistency(self):
    """Validate data consistency and integrity"""
    with get_connection() as conn:
        cursor = conn.cursor()

        issues = []

        # Check for orphaned schedules (invalid room_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.room_id
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE r.id IS NULL
        ''')
        orphaned_rooms = cursor.fetchall()
        if orphaned_rooms:
            issues.append(f"Found {len(orphaned_rooms)} schedules with invalid room references")

        # Check for orphaned schedules (invalid instructor_id)
        cursor.execute('''
        SELECT ms.id, ms.module_code, ms.instructor_id
        FROM module_schedule ms
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE i.id IS NULL
        ''')
        orphaned_instructors = cursor.fetchall()
        if orphaned_instructors:
            issues.append(f"Found {len(orphaned_instructors)} schedules with invalid instructor references")

        # Check for duplicate schedules
        cursor.execute('''
        SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, COUNT(*)
        FROM module_schedule
        GROUP BY module_code, day_of_week, start_time, end_time, room_id, instructor_id
        HAVING COUNT(*) > 1
        ''')
        duplicates = cursor.fetchall()
        if duplicates:
            issues.append(f"Found {len(duplicates)} duplicate schedule entries")

        # Check for invalid time formats
        cursor.execute('''
        SELECT id, start_time, end_time
        FROM module_schedule
        WHERE start_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
           OR end_time NOT GLOB '[0-9][0-9]:[0-9][0-9]'
        ''')
        invalid_times = cursor.fetchall()
        if invalid_times:
            issues.append(f"Found {len(invalid_times)} schedules with invalid time formats")

    if issues:
        message = "Data Consistency Issues Found:\n\n" + "\n".join(f"{i}. {issue}" for i, issue in enumerate(issues, 1))
        messagebox.showwarning("Data Validation", message, parent=self.root)
    else:
        messagebox.showinfo("Data Validation", "No data consistency issues found.", parent=self.root)

    return issues

ModuleSchedulingGUI.validate_data_consistency = validate_data_consistency

def clean_orphaned_records(self):
    """Clean up orphaned records"""
    confirm = messagebox.askyesno(
        "Confirm Cleanup",
        "This will remove schedules with invalid room or instructor references.\n\n"
        "Are you sure you want to continue?"
    , parent=self.root)

    if not confirm:
        return

    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Remove schedules with invalid room references
            cursor.execute('''
            DELETE FROM module_schedule
            WHERE room_id NOT IN (SELECT id FROM rooms)
            ''')
            removed_room_refs = cursor.rowcount

            # Remove schedules with invalid instructor references
            cursor.execute('''
            DELETE FROM module_schedule
            WHERE instructor_id NOT IN (SELECT id FROM instructors)
            ''')
            removed_instructor_refs = cursor.rowcount

        message = f"Cleanup completed:\n\n" \
                 f"• Removed {removed_room_refs} schedules with invalid room references\n" \
                 f"• Removed {removed_instructor_refs} schedules with invalid instructor references"

        messagebox.showinfo("Cleanup Complete", message, parent=self.root)
        self.refresh_all_data()

    except Exception as e:
        messagebox.showerror("Error", f"Error during cleanup: {str(e)}", parent=self.root)

ModuleSchedulingGUI.clean_orphaned_records = clean_orphaned_records

