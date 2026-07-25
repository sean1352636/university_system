# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.interfaces.gui.learners.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _safe_set_combobox, _safe_entry_insert

def view_student_timetable(self, student_id, first_name, last_name):
    """Display student's weekly timetable in grid format matching module scheduling GUI"""
    try:
        timetable_window = tk.Toplevel(self.root)
        _install_clean_close(timetable_window)
        timetable_window.title(f"Timetable - {first_name} {last_name} ({student_id})")
        timetable_window.geometry("1400x800")
        timetable_window.transient(self.root)

        main_frame = ttk.Frame(timetable_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(main_frame, text=f"Weekly Timetable for {first_name} {last_name} ({student_id})",
                              font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Fetch timetable from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            timetable_window.destroy()
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ms.day_of_week,
                ms.start_time,
                ms.end_time,
                ms.module_code,
                m.module_name,
                ms.session_type,
                ms.room_id
            FROM student_modules sm
            JOIN module_schedule ms ON sm.module_code = ms.module_code
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY
                CASE ms.day_of_week
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    WHEN 'Sunday' THEN 7
                END,
                ms.start_time
        """, (student_id,))

        timetable_data = list(cursor.fetchall())
        conn.close()

        # Merge in section-based meetings from Course Management (the other
        # scheduling model). Section meetings are keyed by course; the bridge
        # maps the student's enrolled modules to their courses. Best-effort —
        # never let this break the module timetable.
        try:
            from education_system.systems.university.domain.academics.services.timetable_bridge import (
                get_student_section_meetings,
            )
            for m in get_student_section_meetings(student_id):
                timetable_data.append((
                    m["day_of_week"], m["start_time"], m["end_time"],
                    m["code"], m["name"], m["session_type"], m["location"],
                ))
        except Exception:
            pass

        if not timetable_data:
            tk.Label(main_frame, text=_t("student.no_timetable_entries"),
                    font=('Arial', 12)).pack(pady=20)
            ttk.Button(main_frame, text=_t("common.close"),
                      command=timetable_window.destroy).pack()
            return

        # Create canvas with scrollbars for grid view
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)

        grid_container = ttk.Frame(canvas)
        grid_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=grid_container, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Define time slots and days
        DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']

        # Create grid data structure
        grid_data = {}
        for day in DAYS_OF_WEEK:
            grid_data[day] = {}
            for time_slot in TIME_SLOTS:
                grid_data[day][time_slot] = []

        # Populate grid with timetable data
        for entry in timetable_data:
            day, start_time, end_time, module_code, module_name, session_type, room_id = entry

            if not day or not start_time:
                continue

            # Find the closest time slot
            try:
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            except (ValueError, TypeError, IndexError):
                continue

            # room_id is an int for module classes, but the section bridge
            # passes a free-text location string — render either sensibly.
            if isinstance(room_id, str):
                room_disp = room_id or 'TBA'
            else:
                room_disp = f"Room {room_id}" if room_id else 'TBA'
            session_info = {
                'module': module_code or 'N/A',
                'name': module_name or 'Unknown Module',
                'type': session_type or 'Session',
                'room': room_disp,
                'time': f"{start_time}-{end_time}"
            }

            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        # Create grid frame
        grid_frame = tk.Frame(grid_container)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header row - Time column
        time_header = tk.Label(grid_frame, text=_t("student.timetable_time"), font=('Arial', 10, 'bold'),
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
                            room_label = tk.Label(session_box, text=entry['room'],
                                                 font=('Arial', 6),
                                                 bg='#c3e6cb', fg='#155724')
                            room_label.pack(anchor='w')

                    if len(entries) > 2:
                        more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                             font=('Arial', 7, 'italic'),
                                             bg='#d4edda', fg='#155724')
                        more_label.pack(anchor='w', pady=2)

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        # Calculate statistics
        total_sessions = len(timetable_data)
        unique_modules = len(set(entry[3] for entry in timetable_data))
        days_with_classes = len(set(entry[0] for entry in timetable_data))

        ttk.Label(summary_frame, text=f"Total Sessions: {total_sessions}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Unique Modules: {unique_modules}").grid(row=0, column=1, padx=10)
        ttk.Label(summary_frame, text=f"Days with Classes: {days_with_classes}").grid(row=0, column=2, padx=10)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"),
                  command=timetable_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_timetable", error=str(e)))
        if 'timetable_window' in locals():
            timetable_window.destroy()

