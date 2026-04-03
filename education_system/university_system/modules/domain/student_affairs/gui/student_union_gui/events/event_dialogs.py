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


class EventRegistrationDialog:
    """Dialog for event registration"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Register for Event")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Register for Event", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Events list
        list_frame = ttk.LabelFrame(main_frame, text="Upcoming Events")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Treeview for events
        columns = ('ID', 'Name', 'Date', 'Time', 'Location', 'Organizer', 'Capacity')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.events_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Event details
        details_frame = ttk.LabelFrame(main_frame, text="Event Details")
        details_frame.pack(fill='x', pady=(0, 10))

        self.details_text = tk.Text(details_frame, height=5, wrap=tk.WORD)
        self.details_text.pack(fill='x', padx=5, pady=5)

        # Bind selection event
        self.events_tree.bind('<<TreeviewSelect>>', self.on_event_selected)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Register for Selected Event",
                  command=self.register_for_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel",
                  command=self.cancel).pack(side='left')

    def load_events(self):
        """Load upcoming events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location,
                   c.club_name, e.max_attendees, e.current_attendees, e.description
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_date >= ? AND e.status = 'upcoming'
            ORDER BY e.event_date, e.start_time
            ''', (current_date,))

            events = cursor.fetchall()

            for event in events:
                capacity = f"{event[7]}/{event[6]}" if event[6] > 0 else f"{event[7]}/∞"
                self.events_tree.insert('', 'end', values=(
                    event[0], event[1], event[2], event[3], event[4], event[5], capacity
                ), tags=(event[8],))  # Store description in tags

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def on_event_selected(self, event=None):
        """Handle event selection"""
        selection = self.events_tree.selection()
        if not selection:
            return

        item = self.events_tree.item(selection[0])
        values = item['values']
        description = item['tags'][0] if item['tags'] else "No description available"

        details = f"Event: {values[1]}\n"
        details += f"Date: {values[2]} at {values[3]}\n"
        details += f"Location: {values[4]}\n"
        details += f"Organizer: {values[5]}\n"
        details += f"Capacity: {values[6]}\n\n"
        details += f"Description: {description}"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def register_for_event(self):
        """Register for the selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to register for.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Do you want to register for {event_name}?"):
            try:
                self.result = {'event_id': event_id, 'event_name': event_name}
                messagebox.showinfo("Success", f"Successfully registered for {event_name}!")
                self.dialog.destroy()
            except (tk.TclError, AttributeError) as e:
                messagebox.showerror("Error", f"Failed to register for event: {str(e)}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()



class EventManagementDialog:
    """Dialog for managing recurring events"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Manage Recurring Events")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Recurring Events Management", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Events list
        list_frame = ttk.LabelFrame(main_frame, text="Events")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Name', 'Pattern', 'Start', 'End', 'Status')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.events_tree.heading(col, text=col)
            self.events_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.events_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text="Edit Selected", command=self.edit_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Pause/Resume", command=self.toggle_status).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Delete", command=self.delete_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load recurring events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, recurrence_pattern, start_date, end_date, status
            FROM recurring_events
            ORDER BY start_date DESC
            ''')

            events = cursor.fetchall()

            for event in events:
                self.events_tree.insert('', 'end', values=event)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def edit_event(self):
        """Edit selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to edit.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_name, description, location, recurrence_pattern,
                       start_date, end_date, event_time, duration_hours
                FROM recurring_events WHERE event_id = ?
            ''', (event_id,))
            event = cursor.fetchone()
            conn.close()

            if not event:
                messagebox.showerror("Error", "Event not found")
                return

            name, desc, location, pattern, start_date, end_date, event_time, duration = event

            # Create edit dialog
            edit_dialog = tk.Toplevel(self.dialog)
            edit_dialog.title(f"Edit Event - {name}")
            edit_dialog.geometry("500x550")
            edit_dialog.transient(self.dialog)
            edit_dialog.grab_set()

            main_frame = ttk.Frame(edit_dialog, padding="10")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text="Edit Recurring Event",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 10))

            form_frame = ttk.Frame(main_frame)
            form_frame.pack(fill='both', expand=True)

            # Event Name
            ttk.Label(form_frame, text="Event Name *").grid(row=0, column=0, sticky='w', pady=5)
            name_var = tk.StringVar(value=name or '')
            ttk.Entry(form_frame, textvariable=name_var, width=35).grid(row=0, column=1, pady=5)

            # Description
            ttk.Label(form_frame, text="Description").grid(row=1, column=0, sticky='nw', pady=5)
            desc_text = tk.Text(form_frame, height=4, width=35)
            desc_text.insert('1.0', desc or '')
            desc_text.grid(row=1, column=1, pady=5)

            # Location
            ttk.Label(form_frame, text="Location").grid(row=2, column=0, sticky='w', pady=5)
            location_var = tk.StringVar(value=location or '')
            ttk.Entry(form_frame, textvariable=location_var, width=35).grid(row=2, column=1, pady=5)

            # Recurrence Pattern
            ttk.Label(form_frame, text="Recurrence Pattern").grid(row=3, column=0, sticky='w', pady=5)
            pattern_var = tk.StringVar(value=pattern or 'weekly')
            pattern_combo = ttk.Combobox(form_frame, textvariable=pattern_var, state='readonly', width=33)
            pattern_combo['values'] = ['daily', 'weekly', 'biweekly', 'monthly']
            pattern_combo.grid(row=3, column=1, pady=5)

            # Start Date
            ttk.Label(form_frame, text="Start Date (YYYY-MM-DD)").grid(row=4, column=0, sticky='w', pady=5)
            start_var = tk.StringVar(value=start_date or '')
            ttk.Entry(form_frame, textvariable=start_var, width=35).grid(row=4, column=1, pady=5)

            # End Date
            ttk.Label(form_frame, text="End Date (YYYY-MM-DD)").grid(row=5, column=0, sticky='w', pady=5)
            end_var = tk.StringVar(value=end_date or '')
            ttk.Entry(form_frame, textvariable=end_var, width=35).grid(row=5, column=1, pady=5)

            # Event Time
            ttk.Label(form_frame, text="Event Time (HH:MM)").grid(row=6, column=0, sticky='w', pady=5)
            time_var = tk.StringVar(value=event_time or '')
            ttk.Entry(form_frame, textvariable=time_var, width=35).grid(row=6, column=1, pady=5)

            # Duration
            ttk.Label(form_frame, text="Duration (hours)").grid(row=7, column=0, sticky='w', pady=5)
            duration_var = tk.StringVar(value=str(duration or 1))
            ttk.Entry(form_frame, textvariable=duration_var, width=35).grid(row=7, column=1, pady=5)

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', pady=(10, 0))

            def save_changes():
                new_name = name_var.get().strip()
                if not new_name:
                    messagebox.showerror("Error", "Event name is required", parent=edit_dialog)
                    return

                try:
                    conn = student_union_cli.get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                        UPDATE recurring_events
                        SET event_name = ?, description = ?, location = ?,
                            recurrence_pattern = ?, start_date = ?, end_date = ?,
                            event_time = ?, duration_hours = ?
                        WHERE event_id = ?
                    ''', (
                        new_name,
                        desc_text.get('1.0', 'end-1c').strip(),
                        location_var.get().strip(),
                        pattern_var.get(),
                        start_var.get().strip(),
                        end_var.get().strip(),
                        time_var.get().strip(),
                        float(duration_var.get()) if duration_var.get() else 1,
                        event_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Event updated successfully!", parent=edit_dialog)
                    edit_dialog.destroy()

                    # Refresh the events list
                    self.events_tree.delete(*self.events_tree.get_children())
                    self.load_events()

                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to update event: {str(e)}", parent=edit_dialog)

            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load event: {str(e)}")

    def toggle_status(self):
        """Toggle event status"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        current_status = item['values'][5]
        new_status = 'paused' if current_status == 'active' else 'active'

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE recurring_events SET status = ? WHERE event_id = ?', (new_status, event_id))
            conn.commit()
            conn.close()

            # Refresh list
            self.events_tree.delete(*self.events_tree.get_children())
            self.load_events()
            messagebox.showinfo("Success", f"Event status changed to {new_status}")
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")

    def delete_event(self):
        """Delete selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to delete.")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]

        if messagebox.askyesno("Confirm", f"Delete recurring event '{event_name}'?"):
            try:
                conn = student_union_cli.get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM recurring_events WHERE event_id = ?', (event_id,))
                conn.commit()
                conn.close()

                self.events_tree.delete(selection[0])
                messagebox.showinfo("Success", "Event deleted successfully!")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to delete event: {str(e)}")



class EventAttendanceDialog:
    """Dialog for managing event attendance"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Attendance Management")
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Event Attendance Tracking", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event selection
        event_frame = ttk.LabelFrame(main_frame, text="Select Event")
        event_frame.pack(fill='x', pady=(0, 10))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, width=60, state="readonly")
        self.event_combo.pack(side='left', padx=5, pady=5)
        self.event_combo.bind('<<ComboboxSelected>>', self.on_event_selected)

        ttk.Button(event_frame, text="View Attendance", command=self.view_attendance).pack(side='left', padx=5)

        # Attendance details
        details_frame = ttk.LabelFrame(main_frame, text="Attendance Details")
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Student ID', 'Name', 'Check-in Time', 'Check-out Time', 'Status')
        self.attendance_tree = ttk.Treeview(details_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.attendance_tree.heading(col, text=col)
            self.attendance_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(details_frame, orient='vertical', command=self.attendance_tree.yview)
        self.attendance_tree.configure(yscrollcommand=scrollbar.set)

        self.attendance_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Stats
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics")
        stats_frame.pack(fill='x', pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="Select an event to view statistics")
        self.stats_label.pack(padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Export", command=self.export_attendance).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load events for attendance tracking"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, event_date, event_time
            FROM union_events
            WHERE event_date >= date('now', '-30 days')
            ORDER BY event_date DESC
            ''')

            events = cursor.fetchall()

            event_options = []
            self.event_data = {}

            for event in events:
                option = f"{event[1]} - {event[2]} {event[3]}"
                event_options.append(option)
                self.event_data[option] = event[0]

            self.event_combo['values'] = event_options
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def on_event_selected(self, event=None):
        """
        Handle event selection - Automatically loads attendance data for selected event
        """
        if self.event_var.get():
            self.view_attendance()

    def view_attendance(self):
        """View attendance for selected event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        event_id = self.event_data[selection]

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT COALESCE(er.student_id, 'N/A'), u.username, er.registration_date, er.status
            FROM union_event_registrations er
            JOIN users u ON er.user_id = u.id
            WHERE er.event_id = ?
            ORDER BY u.username
            ''', (event_id,))

            attendance = cursor.fetchall()

            # Clear previous data
            self.attendance_tree.delete(*self.attendance_tree.get_children())

            # Insert attendance data
            for record in attendance:
                self.attendance_tree.insert('', 'end', values=(record[0], record[1], record[2], '-', record[3]))

            # Update stats
            total = len(attendance)
            attended = sum(1 for r in attendance if r[3] == 'Attended')
            self.stats_label.config(text=f"Total Registered: {total} | Attended: {attended} | Attendance Rate: {(attended/total*100 if total > 0 else 0):.1f}%")

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load attendance: {str(e)}")

    def export_attendance(self):
        """Export attendance data to CSV"""
        from tkinter import filedialog
        import csv

        if not hasattr(self, 'current_event_id') or not self.current_event_id:
            messagebox.showwarning("Warning", "Please select an event first")
            return

        # Get event name for filename
        event_selection = self.event_var.get()
        event_name = event_selection.split(': ', 1)[1] if ': ' in event_selection else 'event'
        safe_name = event_name.replace(' ', '_').replace('/', '_')[:30]

        file_path = filedialog.asksaveasfilename(
            title="Export Attendance to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"attendance_{safe_name}"
        )

        if not file_path:
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT u.user_id, u.username, u.email, er.status, er.registration_date
                FROM unified_event_registrations er
                JOIN users u ON er.user_id = u.user_id
                WHERE er.event_id = ?
                ORDER BY u.username
            ''', (self.current_event_id,))

            attendees = cursor.fetchall()
            conn.close()

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Event', event_name])
                writer.writerow(['Export Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                writer.writerow(['User ID', 'Username', 'Email', 'Status', 'Registration Date'])

                for user_id, username, email, status, reg_date in attendees:
                    writer.writerow([user_id, username, email or 'N/A', status or 'Registered', reg_date or 'N/A'])

                # Summary
                writer.writerow([])
                writer.writerow(['Summary'])
                total = len(attendees)
                attended = sum(1 for a in attendees if a[3] == 'Attended')
                writer.writerow(['Total Registered', total])
                writer.writerow(['Attended', attended])
                writer.writerow(['Attendance Rate', f"{(attended/total*100 if total > 0 else 0):.1f}%"])

            messagebox.showinfo("Success", f"Attendance exported successfully to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export attendance: {str(e)}")



# ============================================================================
# PEER SUPPORT & WELLNESS SYSTEM - 7 Features
# ============================================================================


