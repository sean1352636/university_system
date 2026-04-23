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
from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import AddRoomDialog, EditRoomDialog

def create_rooms_tab(self):
    """Create the rooms management tab"""
    rooms_frame = ttk.Frame(self.notebook)
    self.notebook.add(rooms_frame, text=_t("scheduling.tabs.rooms"))

    # Controls frame
    controls_frame = ttk.Frame(rooms_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(controls_frame, text=_t("scheduling.buttons.add_room"),
              command=self.show_add_room_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.edit_selected"),
              command=self.edit_selected_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.buttons.deactivate_selected"),
              command=self.deactivate_selected_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("scheduling.buttons.reactivate_selected"),
              command=self.reactivate_selected_room).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.refresh"),
              command=self.refresh_rooms).pack(side=tk.LEFT, padx=5)

    # Search
    search_frame = ttk.Frame(controls_frame)
    search_frame.pack(side=tk.RIGHT, padx=5)

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
    self.room_search_var = tk.StringVar()
    self.room_search_var.trace('w', self.filter_rooms)
    ttk.Entry(search_frame, textvariable=self.room_search_var, width=20).pack(side=tk.LEFT, padx=5)

    # Rooms treeview
    tree_frame = ttk.Frame(rooms_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ("ID", "Building", "Room", "Capacity", "Type", "Equipment", "Status")
    self.rooms_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                   style='Data.Treeview', selectmode="extended")

    for col in columns:
        self.rooms_tree.heading(col, text=col)
        if col == "ID":
            self.rooms_tree.column(col, width=50)
        elif col == "Equipment":
            self.rooms_tree.column(col, width=200)
        else:
            self.rooms_tree.column(col, width=100)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.rooms_tree.yview)
    self.rooms_tree.configure(yscrollcommand=v_scrollbar.set)

    self.rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    self.rooms_tree.bind("<Double-1>", lambda e: self.edit_selected_room())

ModuleSchedulingGUI.create_rooms_tab = create_rooms_tab

def refresh_rooms(self):
    """Refresh the rooms treeview"""
    try:
        # Clear existing items
        for item in self.rooms_tree.get_children():
            self.rooms_tree.delete(item)

        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type, equipment, is_active
            FROM rooms
            ORDER BY building, room_number
            ''')

            rooms = cursor.fetchall()

        for room in rooms:
            room_id, room_number, building, capacity, room_type, equipment, is_active = room
            status = "Active" if is_active else "Inactive"
            equipment = equipment or "N/A"

            self.rooms_tree.insert("", tk.END, values=(
                room_id, building, room_number, capacity, room_type, equipment, status
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh rooms: {str(e)}", parent=self.root)

ModuleSchedulingGUI.refresh_rooms = refresh_rooms

def filter_rooms(self, *args):
    """Filter rooms based on search term"""
    search_term = self.room_search_var.get().lower()

    # Clear current items
    for item in self.rooms_tree.get_children():
        self.rooms_tree.delete(item)

    if not search_term:
        self.refresh_rooms()
        return

    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type, equipment, is_active
            FROM rooms
            WHERE LOWER(room_number) LIKE ?
               OR LOWER(building) LIKE ?
               OR LOWER(room_type) LIKE ?
               OR LOWER(equipment) LIKE ?
            ORDER BY building, room_number
            ''', [f'%{search_term}%'] * 4)

            rooms = cursor.fetchall()

        for room in rooms:
            room_id, room_number, building, capacity, room_type, equipment, is_active = room
            status = "Active" if is_active else "Inactive"
            equipment = equipment or "N/A"

            self.rooms_tree.insert("", tk.END, values=(
                room_id, building, room_number, capacity, room_type, equipment, status
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to filter rooms: {str(e)}", parent=self.root)

ModuleSchedulingGUI.filter_rooms = filter_rooms

def show_add_room_dialog(self):
    """Show dialog for adding a new room"""
    dialog = AddRoomDialog(self.root, self.scheduler)
    if dialog.result:
        self.refresh_rooms()
        self.refresh_dashboard()
        self.update_activity_log("New room added")

ModuleSchedulingGUI.show_add_room_dialog = show_add_room_dialog

def edit_selected_room(self):
    """Edit the selected room"""
    selected = self.rooms_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a room to edit.", parent=self.root)
        return

    room_data = self.rooms_tree.item(selected[0])['values']
    room_id = room_data[0]

    dialog = EditRoomDialog(self.root, self.scheduler, room_id)
    if dialog.result:
        self.refresh_rooms()
        self.update_activity_log(f"Room {room_id} updated")

ModuleSchedulingGUI.edit_selected_room = edit_selected_room

def deactivate_selected_room(self):
    """Deactivate the selected room with session checking and reassignment"""
    selected = self.rooms_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a room to deactivate.", parent=self.root)
        return

    room_data = self.rooms_tree.item(selected[0])['values']
    room_id = room_data[0]
    room_name = f"{room_data[1]}-{room_data[2]}"

    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            # Check if room has scheduled sessions
            cursor.execute('''
                SELECT ms.id, ms.module_code, ms.day_of_week, ms.start_time, ms.end_time, ms.session_type
                FROM module_schedule ms
                WHERE ms.room_id = ?
                ORDER BY ms.day_of_week, ms.start_time
            ''', (room_id,))

            affected_sessions = cursor.fetchall()

            if affected_sessions:
                # Show message listing affected sessions
                session_list = "\n".join([
                    f"- {s[1]} ({s[5]}) on {s[2]} at {s[3]}-{s[4]}"
                    for s in affected_sessions
                ])

                message = f"Room {room_name} has {len(affected_sessions)} scheduled session(s):\n\n{session_list}\n\n"
                message += "Do you want to proceed? The system will attempt to reassign sessions to other available rooms."

                if not messagebox.askyesno("Confirm Deactivate", message, parent=self.root):
                    return

                # Try to reassign sessions to available rooms
                reassigned = []
                failed_reassignments = []

                for session in affected_sessions:
                    session_id, module_code, day, start_time, end_time, session_type = session

                    # Find an available room for this time slot
                    cursor.execute('''
                        SELECT r.id, r.building, r.room_number, r.capacity
                        FROM rooms r
                        WHERE r.is_active = 1
                        AND r.id != ?
                        AND r.id NOT IN (
                            SELECT room_id FROM module_schedule
                            WHERE day_of_week = ?
                            AND start_time = ?
                            AND room_id IS NOT NULL
                        )
                        ORDER BY r.capacity
                        LIMIT 1
                    ''', (room_id, day, start_time))

                    available_room = cursor.fetchone()

                    if available_room:
                        new_room_id, new_building, new_room_num, capacity = available_room
                        new_room_name = f"{new_building}-{new_room_num}"

                        # Update the session with new room
                        cursor.execute('''
                            UPDATE module_schedule
                            SET room_id = ?
                            WHERE id = ?
                        ''', (new_room_id, session_id))

                        reassigned.append({
                            'module': module_code,
                            'session_type': session_type,
                            'day': day,
                            'time': f"{start_time}-{end_time}",
                            'old_room': room_name,
                            'new_room': new_room_name
                        })

                        # Send email notifications
                        self._send_room_change_notifications(
                            module_code, day, start_time, end_time,
                            room_name, new_room_name
                        )
                    else:
                        failed_reassignments.append({
                            'module': module_code,
                            'day': day,
                            'time': f"{start_time}-{end_time}"
                        })

                # Deactivate the room
                cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))
                conn.commit()

                # Show result message
                result_msg = f"Room {room_name} has been deactivated.\n\n"

                if reassigned:
                    result_msg += f"Successfully reassigned {len(reassigned)} session(s):\n"
                    for r in reassigned[:5]:  # Show first 5
                        result_msg += f"- {r['module']} ({r['session_type']}) {r['day']} {r['time']}: {r['old_room']} → {r['new_room']}\n"
                    if len(reassigned) > 5:
                        result_msg += f"... and {len(reassigned) - 5} more\n"
                    result_msg += "\nEmail notifications sent to affected students and lecturers.\n"

                if failed_reassignments:
                    result_msg += f"\n⚠️ Warning: {len(failed_reassignments)} session(s) could not be reassigned (no available rooms):\n"
                    for f in failed_reassignments:
                        result_msg += f"- {f['module']} {f['day']} {f['time']}\n"
                    result_msg += "\nThese sessions will need manual room assignment."

                messagebox.showinfo("Room Deactivated", result_msg, parent=self.root)
            else:
                # No sessions, just deactivate
                if messagebox.askyesno("Confirm Deactivate", f"Are you sure you want to deactivate room {room_name}?", parent=self.root):
                    cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))
                    conn.commit()
                    messagebox.showinfo("Success", f"Room {room_name} deactivated successfully.", parent=self.root)

        self.refresh_rooms()
        self.refresh_dashboard()
        self.update_activity_log(f"Room {room_name} deactivated")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to deactivate room: {str(e)}", parent=self.root)

ModuleSchedulingGUI.deactivate_selected_room = deactivate_selected_room

def reactivate_selected_room(self):
    """Reactivate the selected room"""
    selected = self.rooms_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a room to reactivate.", parent=self.root)
        return

    room_data = self.rooms_tree.item(selected[0])['values']
    room_id = room_data[0]
    room_name = f"{room_data[1]}-{room_data[2]}"
    room_status = room_data[6]

    # Check if room is already active
    if room_status == "Active":
        messagebox.showinfo("Info", f"Room {room_name} is already active.", parent=self.root)
        return

    if messagebox.askyesno("Confirm Reactivate", f"Are you sure you want to reactivate room {room_name}?", parent=self.root):
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE rooms SET is_active = 1 WHERE id = ?', (room_id,))
                conn.commit()

            self.refresh_rooms()
            self.refresh_dashboard()
            self.update_activity_log(f"Room {room_name} reactivated")
            messagebox.showinfo("Success", f"Room {room_name} reactivated successfully.", parent=self.root)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to reactivate room: {str(e)}", parent=self.root)

ModuleSchedulingGUI.reactivate_selected_room = reactivate_selected_room

def quick_add_room(self):
    """Quick add room from dashboard"""
    self.notebook.select(2)  # Switch to rooms tab
    self.show_add_room_dialog()

ModuleSchedulingGUI.quick_add_room = quick_add_room

def view_room_schedule(self, room_id=None):
    """View schedule for a specific room"""
    if not room_id:
        # Show dialog to select room
        room_id = self._select_room_dialog()
        if not room_id:
            return

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms.day_of_week, ms.start_time, ms.end_time,
               ms.module_code, m.module_name,
               i.first_name, i.last_name,
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN modules m ON ms.module_code = m.module_code
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE ms.room_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (room_id,))

        schedules = cursor.fetchall()

        # Get room info
        cursor.execute('SELECT building, room_number FROM rooms WHERE id = ?', (room_id,))
        room_info = cursor.fetchone()

    if not schedules:
        messagebox.showinfo("No Schedule", f"No schedule found for room ID {room_id}", parent=self.root)
        return

    room_name = f"{room_info[0]}-{room_info[1]}" if room_info else f"Room {room_id}"

    # Create dialog
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Schedule for {room_name}")
    dialog.geometry("1000x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Day', 'Time', 'Module', 'Module Name', 'Instructor', 'Type')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Day', width=100)
    tree.column('Time', width=120)
    tree.column('Module', width=100)
    tree.column('Module Name', width=250)
    tree.column('Instructor', width=180)
    tree.column('Type', width=100)

    for schedule in schedules:
        day, start, end, module_code, module_name, first, last, session_type = schedule
        time_str = f"{start} - {end}"
        instructor = f"{first} {last}" if first and last else "TBA"
        tree.insert('', tk.END, values=(day, time_str, module_code, module_name or '', instructor, session_type))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.view_room_schedule = view_room_schedule

def _select_room_dialog(self):
    """Show dialog to select a room"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, building, room_number FROM rooms WHERE is_active = 1 ORDER BY building, room_number")
        rooms = cursor.fetchall()

    if not rooms:
        messagebox.showinfo("No Rooms", "No rooms found in the system.", parent=self.root)
        return None

    dialog = tk.Toplevel(self.root)
    dialog.title("Select Room")
    dialog.geometry("400x400")
    dialog.transient(self.root)
    dialog.grab_set()

    selected = [None]

    listbox = tk.Listbox(dialog, font=('Arial', 10))
    for room_id, building, room_num in rooms:
        listbox.insert(tk.END, f"{building}-{room_num}")
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_select():
        if listbox.curselection():
            idx = listbox.curselection()[0]
            selected[0] = rooms[idx][0]
            dialog.destroy()

    ttk.Button(dialog, text="Select", command=on_select).pack(pady=5)

    dialog.wait_window()
    return selected[0]

ModuleSchedulingGUI._select_room_dialog = _select_room_dialog

def find_free_rooms(self, day, start_time, end_time, min_capacity=0, room_type=None):
    """Find available rooms for a specific time slot"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Base query for rooms
        query = '''
        SELECT r.id, r.room_number, r.building, r.capacity, r.room_type, r.equipment
        FROM rooms r
        WHERE r.is_active = 1 AND r.capacity >= ?
        '''
        params = [min_capacity]

        if room_type:
            query += " AND r.room_type = ?"
            params.append(room_type)

        # Exclude rooms that are scheduled during this time
        query += '''
        AND r.id NOT IN (
            SELECT ms.room_id FROM module_schedule ms
            WHERE ms.day_of_week = ? AND (
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time < ? AND ms.end_time > ?) OR
                (ms.start_time >= ? AND ms.end_time <= ?)
            )
        )
        '''
        params.extend([day, end_time, start_time, end_time, start_time, start_time, end_time])

        query += " ORDER BY r.building, r.room_number"

        cursor.execute(query, params)
        free_rooms = cursor.fetchall()

        return free_rooms

ModuleSchedulingGUI.find_free_rooms = find_free_rooms

