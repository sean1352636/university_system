import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def show_events_content(self):
    """Display events in main content area"""
    self.clear_content()
    events_frame = ttk.Frame(self.content_frame)
    events_frame.pack(fill=tk.BOTH, expand=True)
    # Create and display events content without notebook
    self._render_events_tab(events_frame)


def _render_events_tab(self, parent_frame):
    """Render events content in the provided parent frame"""
    # Events control panel
    control_frame = ttk.Frame(parent_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Label(control_frame, text=_t("student_union.events.events_and_activities"), font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
    ttk.Button(control_frame, text=_t("student_union.events.refresh"),
              command=self.refresh_events_list).pack(side=tk.RIGHT, padx=2)
    ttk.Button(control_frame, text=_t("student_union.events.create_event"),
              command=self.create_event_dialog).pack(side=tk.RIGHT, padx=2)
    ttk.Button(control_frame, text=_t("student_union.events.my_events"),
              command=self.show_my_events).pack(side=tk.RIGHT, padx=2)
    # Events treeview
    columns = ('ID', 'Name', 'Date', 'Time', 'Location', 'Organizer', 'Attendees', 'Status')
    column_translations = {
        'ID': _t("student_union.events.col_id"),
        'Name': _t("student_union.events.col_name"),
        'Date': _t("student_union.events.col_date"),
        'Time': _t("student_union.events.col_time"),
        'Location': _t("student_union.events.col_location"),
        'Organizer': _t("student_union.events.col_organizer"),
        'Attendees': _t("student_union.events.col_attendees"),
        'Status': _t("student_union.events.col_status")
    }
    self.events_tree = ttk.Treeview(parent_frame, columns=columns, show='headings', height=15)
    # Configure columns
    for col in columns:
        self.events_tree.heading(col, text=column_translations.get(col, col))
        if col == 'ID':
            self.events_tree.column(col, width=50)
        elif col == 'Name':
            self.events_tree.column(col, width=200)
        else:
            self.events_tree.column(col, width=100)
    # Add scrollbars
    events_scrollbar_v = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
    events_scrollbar_h = ttk.Scrollbar(parent_frame, orient=tk.HORIZONTAL, command=self.events_tree.xview)
    self.events_tree.configure(yscrollcommand=events_scrollbar_v.set, xscrollcommand=events_scrollbar_h.set)
    # Pack treeview and scrollbars
    self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0), pady=5)
    events_scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
    events_scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X, padx=10)
    # Event action buttons
    event_actions_frame = ttk.Frame(parent_frame)
    event_actions_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Button(event_actions_frame, text=_t("student_union.events.register_for_event"),
              command=self.register_for_selected_event).pack(side=tk.LEFT, padx=5)
    ttk.Button(event_actions_frame, text=_t("student_union.events.view_details"),
              command=self.view_event_details).pack(side=tk.LEFT, padx=5)
    # Load events initially
    self.refresh_events_list()


def show_events_tab(self):
    """Legacy method for backwards compatibility - creates tab in notebook if exists"""
    if hasattr(self, 'notebook') and self.notebook:
        events_frame = ttk.Frame(self.notebook)
        self.notebook.add(events_frame, text=_t("student_union.events.title"))
        self._render_events_tab(events_frame)
    else:
        # Fall back to content display
        self.show_events_content()


def refresh_events_list(self):
    """Refresh the events list"""
    # Clear existing items
    for item in self.events_tree.get_children():
        self.events_tree.delete(item)
    
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.event_id, e.event_name, e.event_date, e.start_time, 
                   e.location, c.club_name, e.current_attendees, e.max_attendees, e.status
            FROM union_events e
            LEFT JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.status IN ('upcoming', 'open')
            ORDER BY e.event_date, e.start_time
        ''')
        
        events = cursor.fetchall()
        
        for event in events:
            attendees = f"{event[6]}/{event[7]}" if event[7] else str(event[6])
            self.events_tree.insert('', tk.END, values=(
                event[0], event[1], event[2], event[3],
                event[4], event[5] or _t("student_union.events.unknown_organizer"), attendees, event[8]
            ))

        conn.close()
        self.update_status(_t("student_union.events.loaded_events").format(count=len(events)))

    except sqlite3.Error as e:
        messagebox.showerror(_t("student_union.events.database_error"), _t("student_union.events.failed_load_events").format(error=e))


def view_event_details(self):
    """View details of the selected event"""
    selection = self.events_tree.selection()
    if not selection:
        messagebox.showwarning(_t("student_union.events.no_selection"), _t("student_union.events.select_event_to_view"))
        return
    
    item = self.events_tree.item(selection[0])
    event_id = item['values'][0]
    
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.event_name, e.description, e.event_date, e.start_time, e.end_time,
                   e.location, e.category, e.max_attendees, e.current_attendees, 
                   c.club_name, e.status
            FROM union_events e
            LEFT JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_id = ?
        ''', (event_id,))
        
        event = cursor.fetchone()

        if event:
            details_window = tk.Toplevel(self.root)
            details_window.title(_t("student_union.events.event_details_title").format(name=event[0]))
            details_window.geometry("600x500")
            details_window.transient(self.root)

            details_frame = ttk.Frame(details_window)
            details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            details_text = scrolledtext.ScrolledText(details_frame, height=20, width=70)
            details_text.pack(fill=tk.BOTH, expand=True)

            time_str = event[3]
            if event[4]:
                time_str = f"{event[3]} - {event[4]}"
            max_capacity = event[7] if event[7] else _t("student_union.events.unlimited")

            content = _t("student_union.events.event_label").format(name=event[0]) + "\n"
            content += _t("student_union.events.organizer_label").format(organizer=event[9] or _t("student_union.events.unknown_organizer")) + "\n"
            content += _t("student_union.events.date_label").format(date=event[2]) + "\n"
            content += _t("student_union.events.time_label").format(time=time_str) + "\n"
            content += _t("student_union.events.location_label").format(location=event[5] or _t("student_union.events.tbd")) + "\n"
            content += _t("student_union.events.category_label").format(category=event[6] or _t("student_union.events.general")) + "\n"
            content += _t("student_union.events.capacity_label").format(current=event[8], max=max_capacity) + "\n"
            content += _t("student_union.events.status_label").format(status=event[10]) + "\n\n"
            content += _t("student_union.events.description_label") + "\n" + (event[1] or _t("student_union.events.no_description"))

            details_text.insert(1.0, content)
            details_text.config(state=tk.DISABLED)

        conn.close()

    except sqlite3.Error as e:
        messagebox.showerror(_t("student_union.events.database_error"), _t("student_union.events.failed_load_event_details").format(error=e))


def show_my_events(self):
    """Show events that the user has registered for"""
    my_events_window = tk.Toplevel(self.root)
    my_events_window.title(_t("student_union.events.my_events_title"))
    my_events_window.geometry("800x500")
    my_events_window.transient(self.root)

    # This would show user's registered events
    ttk.Label(my_events_window, text=_t("student_union.events.my_registered_events"),
             font=('Arial', 14, 'bold')).pack(pady=20)
    
    info_frame = ttk.Frame(my_events_window)
    info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    tree_columns = ('name', 'date', 'time', 'location', 'status')
    column_headings = [
        _t("student_union.events.col_event"),
        _t("student_union.events.col_date"),
        _t("student_union.events.col_time"),
        _t("student_union.events.col_location"),
        _t("student_union.events.col_status")
    ]
    my_tree = ttk.Treeview(info_frame, columns=tree_columns, show='headings')
    for col, heading in zip(tree_columns, column_headings):
        my_tree.heading(col, text=heading)
        my_tree.column(col, width=140)
    my_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=my_tree.yview)
    scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
    my_tree.configure(yscrollcommand=scrollbar.set)
    stats_label = ttk.Label(my_events_window, text="", font=('Arial', 10))
    stats_label.pack(pady=(5, 15))
    def load_my_events(conn):
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT e.event_name, e.event_date, e.start_time, e.end_time,
                   e.location, e.status
            FROM union_event_registrations r
            JOIN union_events e ON r.event_id = e.event_id
            WHERE r.user_id = ?
            ORDER BY e.event_date, e.start_time
            ''',
            (self.current_user['id'],)
        )
        return cursor.fetchall()
    events = self._safe_db_call(load_my_events)
    if events:
        for name, date, start, end, location, status in events:
            time_str = start or ''
            if start and end:
                time_str = f"{start} - {end}"
            my_tree.insert('', tk.END, values=(
                name,
                date or _t("student_union.events.tbd"),
                time_str or _t("student_union.events.tbd"),
                location or _t("student_union.events.tbd"),
                status or "upcoming"
            ))
        stats_label.config(text=_t("student_union.events.total_events_registered").format(count=len(events)))
    else:
        stats_label.config(text=_t("student_union.events.no_events_registered"))


def create_events_tab(self):
    """Create events management tab"""
    events_frame = ttk.Frame(self.notebook)
    self.notebook.add(events_frame, text=_t("student_union.events.title"))

    # Left panel
    left_panel = ttk.LabelFrame(events_frame, text=_t("student_union.events.event_actions"))
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)

    ttk.Button(left_panel, text=_t("student_union.events.view_events"),
              command=self.view_events).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.events.register_for_event"),
              command=self.register_for_event_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.events.my_events"),
              command=self.view_my_events).pack(fill='x', pady=2)

    ttk.Separator(left_panel, orient='horizontal').pack(fill='x', pady=10)

    ttk.Button(left_panel, text=_t("student_union.events.create_recurring_event"),
              command=self.create_recurring_event_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.events.manage_events"),
              command=self.manage_recurring_events).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.events.event_attendance"),
              command=self.manage_event_attendance).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.events.event_finances"),
              command=self.track_event_finances).pack(fill='x', pady=2)

    # Right panel
    right_panel = ttk.LabelFrame(events_frame, text=_t("student_union.events.event_information"))
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)

    self.events_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                height=30, width=80)
    self.events_text.pack(fill='both', expand=True, padx=5, pady=5)


def view_events(self):
    """GUI wrapper for viewing events"""
    self.update_status(_t("student_union.events.loading_events"))

    def callback(output, result):
        self.display_result(self.events_text, output)
        self.update_status(_t("student_union.events.events_loaded"))

    self.run_in_thread(student_union_cli.view_events, callback)


def view_my_events(self):
    """GUI wrapper for viewing my events"""
    self.update_status(_t("student_union.events.loading_your_events"))

    def callback(output, result):
        self.display_result(self.events_text, output)
        self.update_status(_t("student_union.events.your_events_loaded"))

    self.run_in_thread(student_union_cli.view_my_events, callback)

# Facility Management GUI Methods

