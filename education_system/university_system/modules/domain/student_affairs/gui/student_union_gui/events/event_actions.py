import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core import paths
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

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
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


def register_for_selected_event(self):
    """Register for the selected event"""
    if not self.current_user:
        messagebox.showerror(_t("common.authentication_required"), _t("student_union.events.login_to_register"))
        return

    selection = self.events_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.no_selection"), _t("student_union.events.select_event_to_register"))
        return

    item = self.events_tree.item(selection[0])
    event_id = item['values'][0]
    event_name = item['values'][1]

    values = item['values']
    max_capacity = values[7] if len(values) > 7 else None
    current_attendees = values[6] if len(values) > 6 else None

    # Check existing registration
    def has_existing_registration(conn):
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT 1 FROM unified_event_registrations
            WHERE event_id = ? AND user_id = ? AND user_type = 'student'
            ''',
            (event_id, self.current_user['id'])
        )
        return cursor.fetchone() is not None

    if self._safe_db_call(has_existing_registration):
        messagebox.showinfo(_t("student_union.events.already_registered"), _t("student_union.events.already_registered_msg"))
        return

    # Capacity check
    if isinstance(max_capacity, int) and isinstance(current_attendees, str):
        try:
            current_count = int(current_attendees.split('/')[0])
        except sqlite3.Error:
            current_count = None
    else:
        current_count = None

    if isinstance(max_capacity, int) and current_count is not None and current_count >= max_capacity:
        messagebox.showwarning(_t("student_union.events.event_full"), _t("student_union.events.event_full_msg"))
        return

    if messagebox.askyesno(_t("student_union.events.register_for_event"), _t("student_union.events.confirm_register", event_name=event_name)):
        if self._safe_db_call(self._register_event_operation, event_id):
            messagebox.showinfo(_t("common.success"), _t("student_union.events.registration_success", event_name=event_name))
            self.update_status(_t("student_union.events.registered_for", event_name=event_name))
            self.refresh_events_list()
        else:
            messagebox.showerror(_t("student_union.events.registration_failed"), _t("student_union.events.registration_failed_msg"))


def _register_event_operation(self, conn, event_id):
    """Database operation to register user for an event"""
    cursor = conn.cursor()

    # Get event details for email
    cursor.execute(
        '''
        SELECT title, start_datetime, NULL, location
        FROM unified_events
        WHERE event_id = ?
        ''',
        (event_id,)
    )
    event_details = cursor.fetchone()

    # Insert registration
    cursor.execute(
        '''
        INSERT INTO unified_event_registrations
        (event_id, user_id, user_type, registration_date, attendance_status)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (event_id, self.current_user['id'], 'student', datetime.now().isoformat(), 'registered')
    )
    conn.commit()

    # Send email confirmation if available
    if EMAIL_SERVICE_AVAILABLE and self.current_user.get('email') and event_details:
        try:
            event_name, event_date, event_time, location = event_details
            subject, email_body = render_template('student_union/event_registration_confirmation', {
                'username': self.current_user.get('username', 'Student'),
                'event_name': event_name,
                'event_date': event_date,
                'event_time': event_time or 'TBA',
                'location': location or 'TBA'
            })
            send_email(
                to_email=self.current_user['email'],
                subject=subject,
                body=email_body
            )
        except Exception as e:
            print(f"Failed to send event confirmation email: {e}")

    return True


def create_event_dialog(self):
    """Show dialog to create a new event"""
    create_window = tk.Toplevel(self.root)
    create_window.title(_t("student_union.events.create_new_event"))
    create_window.geometry("600x700")
    create_window.transient(self.root)
    create_window.grab_set()

    # Event creation form
    form_frame = ttk.Frame(create_window)
    form_frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

    ttk.Label(form_frame, text=_t("student_union.events.create_new_event"),
             font=('Arial', 14, 'bold')).pack(pady=10)

    # Form fields
    fields = {}

    # Event name
    ttk.Label(form_frame, text=_t("student_union.events.event_name")).pack(anchor=tk.W, pady=(10,0))
    fields['name'] = ttk.Entry(form_frame, width=60)
    fields['name'].pack(fill=tk.X, pady=(0,10))

    # Date and time
    time_frame = ttk.Frame(form_frame)
    time_frame.pack(fill=tk.X, pady=(0,10))

    ttk.Label(time_frame, text=_t("common.date")).grid(row=0, column=0, sticky=tk.W)
    fields['date'] = ttk.Entry(time_frame, width=15)
    fields['date'].grid(row=0, column=1, padx=5)

    ttk.Label(time_frame, text=_t("student_union.events.start_time")).grid(row=0, column=2, sticky=tk.W, padx=(20,0))
    fields['start_time'] = ttk.Entry(time_frame, width=10)
    fields['start_time'].grid(row=0, column=3, padx=5)

    ttk.Label(time_frame, text=_t("student_union.events.end_time")).grid(row=0, column=4, sticky=tk.W, padx=(10,0))
    fields['end_time'] = ttk.Entry(time_frame, width=10)
    fields['end_time'].grid(row=0, column=5, padx=5)

    # Location and category
    details_frame = ttk.Frame(form_frame)
    details_frame.pack(fill=tk.X, pady=(0,10))

    ttk.Label(details_frame, text=_t("common.location")).grid(row=0, column=0, sticky=tk.W)
    fields['location'] = ttk.Entry(details_frame, width=25)
    fields['location'].grid(row=0, column=1, padx=5, sticky=tk.W+tk.E)

    ttk.Label(details_frame, text=_t("common.category")).grid(row=0, column=2, sticky=tk.W, padx=(20,0))
    fields['category'] = ttk.Combobox(details_frame, values=[
        _t("student_union.events.cat_academic"), _t("student_union.events.cat_social"),
        _t("student_union.events.cat_sports"), _t("student_union.events.cat_arts"),
        _t("student_union.events.cat_technology"), _t("student_union.events.cat_workshop"),
        _t("common.other")
    ], width=15)
    fields['category'].grid(row=0, column=3, padx=5)

    details_frame.columnconfigure(1, weight=1)

    # Max attendees
    ttk.Label(form_frame, text=_t("student_union.events.max_attendees_hint")).pack(anchor=tk.W)
    fields['max_attendees'] = ttk.Entry(form_frame, width=20)
    fields['max_attendees'].pack(anchor=tk.W, pady=(0,10))

    # Description
    ttk.Label(form_frame, text=_t("common.description")).pack(anchor=tk.W)
    fields['description'] = scrolledtext.ScrolledText(form_frame, height=10, width=60)
    fields['description'].pack(fill=tk.BOTH, expand=True, pady=(0,10))

    # Set default values
    fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))

    # Buttons
    button_frame = ttk.Frame(form_frame)
    button_frame.pack(pady=20)

    def create_event():
        name = fields['name'].get().strip()
        date = fields['date'].get().strip()
        start_time = fields['start_time'].get().strip()
        end_time = fields['end_time'].get().strip()
        location = fields['location'].get().strip()
        category = fields['category'].get().strip()
        max_attendees = fields['max_attendees'].get().strip()
        description = fields['description'].get(1.0, tk.END).strip()

        if not name or not date:
            messagebox.showerror(_t("common.error"), _t("student_union.events.name_date_required"))
            return

        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_t("common.error"), _t("student_union.events.date_format_error"))
            return

        max_attendees_int = None
        if max_attendees:
            try:
                max_attendees_int = int(max_attendees)
            except ValueError:
                messagebox.showerror(_t("common.error"), _t("student_union.events.max_attendees_number"))
                return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert new event
            start_dt = f"{date} {start_time}" if start_time else date
            end_dt = f"{date} {end_time}" if end_time else None
            cursor.execute('''
                INSERT INTO unified_events (title, description, start_datetime, end_datetime,
                                        location, event_category, max_capacity, status, created_at, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, description, start_dt, end_dt,
                  location or None, category or None, max_attendees_int, 'upcoming',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'student_union'))

            conn.commit()
            conn.close()
            # Send event notification to all students
            self.send_event_notification_to_all_students(name, description, date, location or _t("common.tbd"))
            messagebox.showinfo(_t("common.success"), _t("student_union.events.event_created_success", name=name))
            create_window.destroy()
            self.refresh_events_list()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.database_error"), _t("student_union.events.event_create_failed", error=str(e)))

    ttk.Button(button_frame, text=_t("student_union.events.create_event"), command=create_event).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=create_window.destroy).pack(side=tk.LEFT, padx=5)

    fields['name'].focus()


def register_for_event_gui(self):
    """GUI for event registration"""
    dialog = EventRegistrationDialog(self.master, self.auth)
    self.master.wait_window(dialog.dialog)

    if dialog.result:
        self.update_status(_t("student_union.events.registered_successfully"))
        self.view_my_events()


