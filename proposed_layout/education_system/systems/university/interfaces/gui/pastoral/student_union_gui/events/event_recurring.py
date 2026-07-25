import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.interfaces.gui.pastoral.student_union_gui.events.event_dialogs import EventManagementDialog

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domain.pastoral.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class RecurringEventDialog:
    """Dialog for creating recurring events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Recurring Event")
        self.dialog.geometry("600x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Create Recurring Event", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details")
        details_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(details_frame, text="Event Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Description:").grid(row=1, column=0, sticky='nw', padx=5, pady=5)
        self.description_text = tk.Text(details_frame, height=4, width=40)
        self.description_text.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text="Location:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.location_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Recurrence pattern
        recurrence_frame = ttk.LabelFrame(main_frame, text="Recurrence Pattern")
        recurrence_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(recurrence_frame, text="Pattern:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.pattern_var = tk.StringVar(value="weekly")
        patterns = ttk.Combobox(recurrence_frame, textvariable=self.pattern_var,
                               values=["daily", "weekly", "monthly"], state="readonly", width=20)
        patterns.grid(row=0, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Start Date:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.start_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(recurrence_frame, textvariable=self.start_date_var, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="End Date:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.end_date_var = tk.StringVar(value=(datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'))
        ttk.Entry(recurrence_frame, textvariable=self.end_date_var, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Time:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.time_var = tk.StringVar(value="10:00")
        ttk.Entry(recurrence_frame, textvariable=self.time_var, width=20).grid(row=3, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(recurrence_frame, text="Duration (hours):").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.duration_var = tk.StringVar(value="2")
        ttk.Entry(recurrence_frame, textvariable=self.duration_var, width=20).grid(row=4, column=1, sticky='w', padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Create", command=self.create_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left')

    def create_event(self):
        """Create the recurring event"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter an event name.")
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            # Create recurring event record
            cursor.execute('''
            INSERT INTO recurring_events (event_name, description, location, recurrence_pattern,
                                         start_date, end_date, event_time, duration_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (name, self.description_text.get("1.0", tk.END).strip(), self.location_var.get(),
                  self.pattern_var.get(), self.start_date_var.get(), self.end_date_var.get(),
                  self.time_var.get(), float(self.duration_var.get())))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Recurring event '{name}' created successfully!")
            self.result = {'name': name}
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create event: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()



class RecurringEventsDialog:
    """Dialog for managing recurring events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Recurring Events")
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📅 Recurring Events Manager",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Series list
        list_frame = ttk.LabelFrame(main_frame, text="Event Series")
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Series', 'Pattern', 'Next Occurrence', 'Total', 'Status')
        tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            tree.heading(col, text=col)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample recurring events
        series = [
            ("Weekly Tech Talks", "Every Tuesday", "2025-04-08", "52/year", "Active"),
            ("Monthly Networking", "1st Friday", "2025-05-02", "12/year", "Active"),
            ("Bi-Weekly Study Group", "Every 2 Wednesdays", "2025-04-16", "26/year", "Active"),
            ("Quarterly Workshops", "Every 3 months", "2025-06-01", "4/year", "Active")
        ]

        for s in series:
            tree.insert('', 'end', values=s)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create Series", command=self.create_series).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Edit Series", command=self.edit_series).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel Occurrence", command=self.cancel_occurrence).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_series(self):
        dialog = CreateRecurringSeriesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def edit_series(self):
        dialog = EditRecurringSeriesDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def cancel_occurrence(self):
        messagebox.showinfo("Cancel", "Select specific occurrence to cancel.\n\nSeries will continue after canceled event.")



class CreateRecurringSeriesDialog:
    """Dialog for creating a recurring event series"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Recurring Event Series")
        self.dialog.geometry("650x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Create Recurring Event Series", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event name
        ttk.Label(main_frame, text="Event Name/Series Title:").pack(anchor='w', pady=(0, 5))
        self.name_entry = ttk.Entry(main_frame, width=60)
        self.name_entry.pack(fill='x', pady=(0, 10))
        self.name_entry.insert(0, "Weekly Study Group")

        # Recurrence pattern
        pattern_frame = ttk.LabelFrame(main_frame, text="Recurrence Pattern")
        pattern_frame.pack(fill='x', pady=(0, 10))

        pattern_inner = ttk.Frame(pattern_frame)
        pattern_inner.pack(padx=15, pady=15, fill='x')

        ttk.Label(pattern_inner, text="Pattern:").grid(row=0, column=0, sticky='w', pady=(0, 10))
        self.pattern_var = tk.StringVar(value="Weekly")
        pattern_combo = ttk.Combobox(pattern_inner, textvariable=self.pattern_var, width=20, state='readonly')
        pattern_combo['values'] = ('Daily', 'Weekly', 'Bi-Weekly', 'Monthly', 'Custom')
        pattern_combo.grid(row=0, column=1, sticky='w', pady=(0, 10), padx=(5, 0))

        ttk.Label(pattern_inner, text="Day of Week:").grid(row=1, column=0, sticky='w', pady=(0, 10))
        self.day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(pattern_inner, textvariable=self.day_var, width=20, state='readonly')
        day_combo['values'] = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
        day_combo.grid(row=1, column=1, sticky='w', pady=(0, 10), padx=(5, 0))

        # Date range
        dates_frame = ttk.Frame(main_frame)
        dates_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(dates_frame, text="Start Date:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.start_entry = ttk.Entry(dates_frame, width=15)
        self.start_entry.grid(row=0, column=1, sticky='w', padx=(5, 10))
        self.start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        ttk.Label(dates_frame, text="End Date:").grid(row=0, column=2, sticky='w', pady=(0, 5))
        self.end_entry = ttk.Entry(dates_frame, width=15)
        self.end_entry.grid(row=0, column=3, sticky='w', padx=(5, 0))
        self.end_entry.insert(0, (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'))

        # Time
        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(time_frame, text="Start Time:").grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.start_time_entry = ttk.Entry(time_frame, width=10)
        self.start_time_entry.grid(row=0, column=1, sticky='w', padx=(5, 10))
        self.start_time_entry.insert(0, "18:00")

        ttk.Label(time_frame, text="Duration (hours):").grid(row=0, column=2, sticky='w', pady=(0, 5))
        self.duration_entry = ttk.Entry(time_frame, width=10)
        self.duration_entry.grid(row=0, column=3, sticky='w', padx=(5, 0))
        self.duration_entry.insert(0, "2")

        # Location
        ttk.Label(main_frame, text="Location:").pack(anchor='w', pady=(0, 5))
        self.location_entry = ttk.Entry(main_frame, width=60)
        self.location_entry.pack(fill='x', pady=(0, 10))
        self.location_entry.insert(0, "Room 101, Student Union Building")

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(0, 5))
        self.description_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.description_text.pack(fill='both', expand=True, pady=(0, 15))
        self.description_text.insert(1.0, "Regular meeting for students to study together...")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Create Series", command=self.create_series).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def create_series(self):
        name = self.name_entry.get().strip()
        pattern = self.pattern_var.get()
        day = self.day_var.get()
        start_date = self.start_entry.get().strip()
        end_date = self.end_entry.get().strip()
        start_time = self.start_time_entry.get().strip()
        duration = self.duration_entry.get().strip()
        location = self.location_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()

        if not all([name, pattern, start_date, end_date, start_time, duration, location]):
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            duration_float = float(duration)
            if duration_float <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid duration.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_event_series (
                series_id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                day_of_week TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_hours REAL,
                location TEXT,
                description TEXT,
                created_by TEXT,
                created_date TEXT,
                status TEXT DEFAULT 'active'
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            created_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO recurring_event_series (
                series_name, pattern, day_of_week, start_date, end_date, start_time,
                duration_hours, location, description, created_by, created_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            ''', (name, pattern, day, start_date, end_date, start_time, duration_float,
                  location, description, created_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Recurring series '{name}' created!\n\nPattern: {pattern} on {day}s\nFrom: {start_date} to {end_date}")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to create series: {str(e)}")



class EditRecurringSeriesDialog:
    """Dialog for editing a recurring event series"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Recurring Event Series")
        self.dialog.geometry("650x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Edit Recurring Event Series", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Series selection
        ttk.Label(main_frame, text="Select Series to Edit:").pack(anchor='w', pady=(0, 5))
        self.series_var = tk.StringVar()
        series_combo = ttk.Combobox(main_frame, textvariable=self.series_var, width=57, state='readonly')
        series_combo['values'] = ('Weekly Tech Talks', 'Monthly Networking', 'Bi-Weekly Study Group')
        series_combo.pack(fill='x', pady=(0, 15))
        series_combo.current(0)

        # Edit options
        options_frame = ttk.LabelFrame(main_frame, text="What would you like to modify?")
        options_frame.pack(fill='both', expand=True, pady=(0, 15))

        options_inner = ttk.Frame(options_frame)
        options_inner.pack(padx=20, pady=20, fill='both', expand=True)

        self.edit_option = tk.StringVar(value="future")

        ttk.Radiobutton(options_inner, text="Edit future occurrences only",
                       variable=self.edit_option, value="future").pack(anchor='w', pady=(0, 10))

        ttk.Radiobutton(options_inner, text="Edit all occurrences (past and future)",
                       variable=self.edit_option, value="all").pack(anchor='w', pady=(0, 10))

        ttk.Radiobutton(options_inner, text="Change recurrence pattern",
                       variable=self.edit_option, value="pattern").pack(anchor='w', pady=(0, 10))

        ttk.Radiobutton(options_inner, text="End series early",
                       variable=self.edit_option, value="end").pack(anchor='w', pady=(0, 10))

        # New end date (for ending series early)
        end_frame = ttk.Frame(main_frame)
        end_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(end_frame, text="New End Date (if ending early):").pack(side='left', padx=(0, 10))
        self.new_end_entry = ttk.Entry(end_frame, width=20)
        self.new_end_entry.pack(side='left')
        self.new_end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Apply Changes", command=self.apply_changes).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def apply_changes(self):
        series = self.series_var.get()
        option = self.edit_option.get()
        new_end = self.new_end_entry.get().strip()

        if not series:
            messagebox.showwarning("Warning", "Please select a series to edit.")
            return

        option_messages = {
            "future": "Future occurrences of this series will be updated.",
            "all": "All occurrences (past and future) will be updated.",
            "pattern": "The recurrence pattern will be modified.\n\nA new pattern selection dialog would appear next.",
            "end": f"Series will end on {new_end}.\n\nNo new occurrences will be created after this date."
        }

        message = option_messages.get(option, "Changes applied!")
        messagebox.showinfo("Success", f"Series '{series}' has been updated!\n\n{message}")
        self.dialog.destroy()


# ============================================================================
# VIRTUAL EVENTS DIALOGS
# ============================================================================


def open_recurring_events_dialog(self):
    """Open recurring events manager"""
    dialog = RecurringEventsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def create_recurring_event_gui(self):
    """Create a recurring event with GUI dialog"""
    try:
        dialog = RecurringEventDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def manage_recurring_events(self):
    """Manage recurring events with GUI dialog"""
    try:
        dialog = EventManagementDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


