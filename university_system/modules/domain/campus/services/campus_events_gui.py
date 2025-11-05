"""
Campus Events Hub GUI

Full-featured Tkinter interface for managing campus events, registrations,
event series, announcements, and sponsorships.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.domain.campus.services.campus_events_core import (
    CampusEventManager,
    EventRegistrationManager,
    EventSeriesManager,
    EventAnnouncementManager,
    EventSponsorManager
)


class CampusEventsGUI:
    """Campus Events Hub GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Campus Events GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access Campus Events Hub.")
            return

        self.window = tk.Toplevel(root)
        self.window.title("Campus Events Hub")
        self.window.geometry("1200x800")
        self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed Campus Events Hub', user=self.auth.current_user.get('username'))
        print("✅ Campus Events Hub GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from university_system.infrastructure.database.schemas import init_campus_events_system_db
            init_campus_events_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning("Warning", f"Database initialization issue: {e}")

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Campus Events Hub",
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=f"User: {self.auth.current_user.get('username', 'Unknown')}",
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_events_tab()
        self._create_registrations_tab()
        self._create_series_tab()
        self._create_announcements_tab()
        self._create_sponsors_tab()

        # Close button
        ttk.Button(
            main_frame,
            text="Close",
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _create_events_tab(self):
        """Create Events tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Events")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create Event", command=self._create_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="View Upcoming", command=self._view_upcoming_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel Event", command=self._cancel_event).pack(side=tk.LEFT, padx=5)

        # Events list
        list_frame = ttk.LabelFrame(tab, text="Campus Events", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event Name', 'Type', 'Category', 'Date', 'Time', 'Location', 'Capacity', 'Status')
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.events_tree.heading('#0', text='')
        self.events_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.events_tree.heading(col, text=col)
            if col == 'ID':
                self.events_tree.column(col, width=40)
            elif col in ['Time', 'Capacity', 'Status']:
                self.events_tree.column(col, width=80)
            elif col == 'Event Name':
                self.events_tree.column(col, width=200)
            else:
                self.events_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.events_tree.yview)
        self.events_tree.configure(yscrollcommand=scrollbar.set)

        self.events_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_events()

    def _create_registrations_tab(self):
        """Create Registrations tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Registrations")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Register for Event", command=self._register_for_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Check In", command=self._check_in_attendee).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_registrations).pack(side=tk.LEFT, padx=5)

        # Registrations list
        list_frame = ttk.LabelFrame(tab, text="Event Registrations", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'User ID', 'User Type', 'Registration Date', 'Status', 'Checked In')
        self.registrations_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.registrations_tree.heading('#0', text='')
        self.registrations_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.registrations_tree.heading(col, text=col)
            if col in ['ID', 'Event ID']:
                self.registrations_tree.column(col, width=60)
            elif col in ['User Type', 'Status']:
                self.registrations_tree.column(col, width=100)
            else:
                self.registrations_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.registrations_tree.yview)
        self.registrations_tree.configure(yscrollcommand=scrollbar.set)

        self.registrations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_registrations()

    def _create_series_tab(self):
        """Create Event Series tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Event Series")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Create Series", command=self._create_series).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_series).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deactivate Series", command=self._deactivate_series).pack(side=tk.LEFT, padx=5)

        # Series list
        list_frame = ttk.LabelFrame(tab, text="Recurring Event Series", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Series Name', 'Organizer', 'Pattern', 'Start Date', 'End Date', 'Active')
        self.series_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.series_tree.heading('#0', text='')
        self.series_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.series_tree.heading(col, text=col)
            if col == 'ID':
                self.series_tree.column(col, width=50)
            elif col in ['Active']:
                self.series_tree.column(col, width=60)
            elif col == 'Series Name':
                self.series_tree.column(col, width=220)
            else:
                self.series_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.series_tree.yview)
        self.series_tree.configure(yscrollcommand=scrollbar.set)

        self.series_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_series()

    def _create_announcements_tab(self):
        """Create Announcements tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Announcements")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Send Announcement", command=self._send_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_announcements).pack(side=tk.LEFT, padx=5)

        # Announcements list
        list_frame = ttk.LabelFrame(tab, text="Event Announcements", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'Announcement', 'Sent To', 'Sent By', 'Sent At')
        self.announcements_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.announcements_tree.heading('#0', text='')
        self.announcements_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.announcements_tree.heading(col, text=col)
            if col in ['ID', 'Event ID']:
                self.announcements_tree.column(col, width=60)
            elif col == 'Announcement':
                self.announcements_tree.column(col, width=300)
            else:
                self.announcements_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.announcements_tree.yview)
        self.announcements_tree.configure(yscrollcommand=scrollbar.set)

        self.announcements_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_announcements()

    def _create_sponsors_tab(self):
        """Create Sponsors tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Sponsors")

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Add Sponsor", command=self._add_sponsor).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_sponsors).pack(side=tk.LEFT, padx=5)

        # Sponsors list
        list_frame = ttk.LabelFrame(tab, text="Event Sponsors", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'Sponsor Name', 'Type', 'Contribution', 'Website')
        self.sponsors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.sponsors_tree.heading('#0', text='')
        self.sponsors_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.sponsors_tree.heading(col, text=col)
            if col in ['ID', 'Event ID']:
                self.sponsors_tree.column(col, width=60)
            elif col in ['Type', 'Contribution']:
                self.sponsors_tree.column(col, width=120)
            elif col == 'Sponsor Name':
                self.sponsors_tree.column(col, width=220)
            else:
                self.sponsors_tree.column(col, width=200)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.sponsors_tree.yview)
        self.sponsors_tree.configure(yscrollcommand=scrollbar.set)

        self.sponsors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_sponsors()

    # Load methods
    def _load_events(self):
        """Load all events"""
        try:
            self.events_tree.delete(*self.events_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT event_id, event_name, event_type, event_category,
                           event_date, start_time, location, capacity, status
                    FROM campus_events
                    ORDER BY event_date DESC, start_time DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['event_id'],
                        row['event_name'],
                        row['event_type'],
                        row['event_category'],
                        row['event_date'],
                        row['start_time'],
                        row['location'] or 'TBA',
                        row['capacity'] or 'Unlimited',
                        row['status']
                    )
                    self.events_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load events: {e}")

    def _load_registrations(self):
        """Load event registrations"""
        try:
            self.registrations_tree.delete(*self.registrations_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT registration_id, event_id, alumni_id,
                           registration_date, payment_status, check_in_time,
                           attendance_confirmed
                    FROM event_registrations
                    ORDER BY registration_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['registration_id'],
                        row['event_id'],
                        row['alumni_id'],
                        'Alumni',  # User type - hardcoded since table is for alumni
                        row['registration_date'][:10] if row['registration_date'] else '',
                        row['payment_status'] or 'pending',
                        row['check_in_time'][:16] if row['check_in_time'] else 'No'
                    )
                    self.registrations_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load registrations: {e}")

    def _load_series(self):
        """Load event series"""
        try:
            self.series_tree.delete(*self.series_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT series_id, series_name, organizer_id, recurrence_pattern,
                           start_date, end_date, is_active
                    FROM event_series
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['series_id'],
                        row['series_name'],
                        row['organizer_id'],
                        row['recurrence_pattern'],
                        row['start_date'],
                        row['end_date'] or 'Ongoing',
                        '✓' if row['is_active'] else '✗'
                    )
                    self.series_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load event series: {e}")

    def _load_announcements(self):
        """Load announcements"""
        try:
            self.announcements_tree.delete(*self.announcements_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT announcement_id, event_id, announcement_text,
                           sent_to, sent_by, sent_at
                    FROM event_announcements
                    ORDER BY sent_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    announcement_preview = row['announcement_text'][:50] + '...' if len(row['announcement_text']) > 50 else row['announcement_text']
                    values = (
                        row['announcement_id'],
                        row['event_id'],
                        announcement_preview,
                        row['sent_to'],
                        row['sent_by'] or 'System',
                        row['sent_at'][:16] if row['sent_at'] else ''
                    )
                    self.announcements_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load announcements: {e}")

    def _load_sponsors(self):
        """Load sponsors"""
        try:
            self.sponsors_tree.delete(*self.sponsors_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT sponsor_id, event_id, sponsor_name, sponsor_type,
                           contribution_amount, website_url
                    FROM event_sponsors
                    ORDER BY contribution_amount DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['sponsor_id'],
                        row['event_id'],
                        row['sponsor_name'],
                        row['sponsor_type'] or 'N/A',
                        f"${row['contribution_amount']:,.2f}" if row['contribution_amount'] else 'N/A',
                        row['website_url'] or 'N/A'
                    )
                    self.sponsors_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sponsors: {e}")

    # Action methods
    def _create_event(self):
        """Create a new event"""
        CreateEventDialog(self.window, self.auth, self._load_events)

    def _view_upcoming_events(self):
        """View upcoming events"""
        ViewUpcomingEventsDialog(self.window, self.auth)

    def _cancel_event(self):
        """Cancel the selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event to cancel")
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]

        if not messagebox.askyesno("Confirm Cancel", f"Cancel event '{event_name}'?"):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE campus_events SET status = ? WHERE event_id = ?', ('cancelled', event_id))

            log_activity(f'Cancelled campus event: {event_id}',
                        user=self.auth.current_user.get('username'))
            messagebox.showinfo("Success", "Event cancelled successfully")
            self._load_events()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel event: {e}")

    def _register_for_event(self):
        """Register for an event"""
        RegisterForEventDialog(self.window, self.auth, self._load_registrations)

    def _check_in_attendee(self):
        """Check in an attendee"""
        selection = self.registrations_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a registration to check in")
            return

        item = self.registrations_tree.item(selection[0])
        registration_id = item['values'][0]

        try:
            EventRegistrationManager.check_in_attendee(registration_id)

            log_activity(f'Checked in attendee: {registration_id}',
                        user=self.auth.current_user.get('username'))
            messagebox.showinfo("Success", "Attendee checked in successfully")
            self._load_registrations()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check in attendee: {e}")

    def _create_series(self):
        """Create a new event series"""
        CreateSeriesDialog(self.window, self.auth, self._load_series)

    def _deactivate_series(self):
        """Deactivate the selected series"""
        selection = self.series_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a series to deactivate")
            return

        item = self.series_tree.item(selection[0])
        series_id = item['values'][0]

        try:
            with transaction() as conn:
                conn.execute('UPDATE event_series SET is_active = 0 WHERE series_id = ?', (series_id,))

            messagebox.showinfo("Success", "Series deactivated successfully")
            self._load_series()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to deactivate series: {e}")

    def _send_announcement(self):
        """Send an event announcement"""
        SendAnnouncementDialog(self.window, self.auth, self._load_announcements)

    def _add_sponsor(self):
        """Add an event sponsor"""
        AddSponsorDialog(self.window, self.auth, self._load_sponsors)


# Dialog Classes

class CreateEventDialog:
    """Dialog for creating a new event"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Event")
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create New Event", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Event Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=35)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Event Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=[
            'Academic', 'Social', 'Athletic', 'Cultural', 'Career', 'Workshop', 'Other'
        ])
        self.type_combo.set('Social')
        self.type_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Category:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=32, values=[
            'Student Life', 'Academics', 'Athletics', 'Arts', 'Community Service', 'Other'
        ])
        self.category_combo.set('Student Life')
        self.category_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Event Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(form_frame, width=35)
        self.date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        self.date_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Start Time (HH:MM):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_entry = ttk.Entry(form_frame, width=35)
        self.start_entry.insert(0, "18:00")
        self.start_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="End Time (HH:MM):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_entry = ttk.Entry(form_frame, width=35)
        self.end_entry.insert(0, "20:00")
        self.end_entry.grid(row=5, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Location:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.location_entry = ttk.Entry(form_frame, width=35)
        self.location_entry.grid(row=6, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Capacity (0 for unlimited):").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.capacity_entry = ttk.Entry(form_frame, width=35)
        self.capacity_entry.insert(0, "0")
        self.capacity_entry.grid(row=7, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Registration Required:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.reg_var = tk.BooleanVar()
        ttk.Checkbutton(form_frame, variable=self.reg_var).grid(row=8, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Public Event:").grid(row=9, column=0, sticky=tk.W, pady=5)
        self.public_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, variable=self.public_var).grid(row=9, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Description:").grid(row=10, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=33, height=4)
        self.desc_text.grid(row=10, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            event_type = self.type_combo.get()
            category = self.category_combo.get()
            event_date = self.date_entry.get().strip()
            start_time = self.start_entry.get().strip()
            end_time = self.end_entry.get().strip()
            location = self.location_entry.get().strip()
            capacity = int(self.capacity_entry.get())
            registration_required = self.reg_var.get()
            is_public = self.public_var.get()
            description = self.desc_text.get('1.0', tk.END).strip()

            if not name or not event_date or not start_time or not end_time:
                messagebox.showerror("Error", "Name, date, and times are required")
                return

            event_id = CampusEventManager.create_event(
                event_name=name,
                event_type=event_type,
                event_category=category,
                organizer_id=self.auth.current_user.get('username', ''),
                organizer_type='staff',
                event_date=event_date,
                start_time=start_time,
                end_time=end_time,
                location=location,
                capacity=capacity,
                registration_required=registration_required,
                is_public=is_public,
                description=description
            )

            log_activity(f'Created campus event: {event_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo("Success", f"Event created successfully (ID: {event_id})")
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Invalid capacity number")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create event: {e}")


class ViewUpcomingEventsDialog:
    """Dialog for viewing upcoming events"""

    def __init__(self, parent, auth):
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Upcoming Events")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)

        self._create_widgets()
        self._load_upcoming()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Upcoming Events (Next 30 Days)",
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # List
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Event Name', 'Date', 'Time', 'Location', 'Category', 'Capacity')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=20)

        self.tree.heading('#0', text='')
        self.tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Event Name':
                self.tree.column(col, width=250)
            else:
                self.tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(10, 0))

    def _load_upcoming(self):
        try:
            events = CampusEventManager.get_upcoming_events(days_ahead=30)

            for event in events:
                values = (
                    event.get('event_name', 'N/A'),
                    event.get('event_date', 'N/A'),
                    f"{event.get('start_time', '')} - {event.get('end_time', '')}",
                    event.get('location', 'TBA'),
                    event.get('event_category', 'N/A'),
                    event.get('capacity', 'Unlimited') if event.get('capacity') else 'Unlimited'
                )
                self.tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load upcoming events: {e}")


class RegisterForEventDialog:
    """Dialog for registering for an event"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Register for Event")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Register for Event", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Event ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_entry = ttk.Entry(form_frame, width=30)
        self.event_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="User ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_entry = ttk.Entry(form_frame, width=30)
        self.user_entry.insert(0, self.auth.current_user.get('username', ''))
        self.user_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="User Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.user_type_combo = ttk.Combobox(form_frame, width=27, values=['student', 'staff', 'faculty', 'guest'])
        self.user_type_combo.set('student')
        self.user_type_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Register", command=self._register).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _register(self):
        try:
            event_id = int(self.event_entry.get())
            user_id = self.user_entry.get().strip()
            user_type = self.user_type_combo.get()

            if not user_id:
                messagebox.showerror("Error", "User ID is required")
                return

            registration_id = EventRegistrationManager.register_for_event(
                event_id=event_id,
                user_id=user_id,
                user_type=user_type
            )

            log_activity(f'Created event registration: {registration_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo("Success", f"Registered successfully (ID: {registration_id})")
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Invalid event ID")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register: {e}")


class CreateSeriesDialog:
    """Dialog for creating an event series"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Create Event Series")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Create Event Series", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Series Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Recurrence Pattern:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.pattern_combo = ttk.Combobox(form_frame, width=27, values=['daily', 'weekly', 'bi-weekly', 'monthly'])
        self.pattern_combo.set('weekly')
        self.pattern_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Start Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_entry = ttk.Entry(form_frame, width=30)
        self.start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.start_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="End Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_entry = ttk.Entry(form_frame, width=30)
        self.end_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=28, height=6)
        self.desc_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Create", command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            pattern = self.pattern_combo.get()
            start_date = self.start_entry.get().strip()
            end_date = self.end_entry.get().strip()
            description = self.desc_text.get('1.0', tk.END).strip()

            if not name or not start_date:
                messagebox.showerror("Error", "Series name and start date are required")
                return

            series_id = EventSeriesManager.create_series(
                series_name=name,
                organizer_id=self.auth.current_user.get('username', ''),
                recurrence_pattern=pattern,
                start_date=start_date,
                end_date=end_date,
                description=description
            )

            log_activity(f'Created event series: {series_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo("Success", f"Event series created (ID: {series_id})")
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create series: {e}")


class SendAnnouncementDialog:
    """Dialog for sending an event announcement"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Event Announcement")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Send Event Announcement", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Event ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_entry = ttk.Entry(form_frame, width=30)
        self.event_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Send To:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.sent_to_combo = ttk.Combobox(form_frame, width=27, values=['all_registrants', 'staff', 'students', 'faculty'])
        self.sent_to_combo.set('all_registrants')
        self.sent_to_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Announcement:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.announcement_text = scrolledtext.ScrolledText(form_frame, width=28, height=10)
        self.announcement_text.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Send", command=self._send).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _send(self):
        try:
            event_id = int(self.event_entry.get())
            sent_to = self.sent_to_combo.get()
            announcement = self.announcement_text.get('1.0', tk.END).strip()

            if not announcement:
                messagebox.showerror("Error", "Announcement text is required")
                return

            announcement_id = EventAnnouncementManager.send_announcement(
                event_id=event_id,
                announcement_text=announcement,
                sent_to=sent_to,
                sent_by=self.auth.current_user.get('username', '')
            )

            log_activity(f'Created event announcement: {announcement_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo("Success", f"Announcement sent (ID: {announcement_id})")
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Invalid event ID")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send announcement: {e}")


class AddSponsorDialog:
    """Dialog for adding an event sponsor"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Event Sponsor")
        self.dialog.geometry("400x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Add Event Sponsor", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Event ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_entry = ttk.Entry(form_frame, width=30)
        self.event_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Sponsor Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Sponsor Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=27, values=['corporate', 'individual', 'foundation', 'government'])
        self.type_combo.set('corporate')
        self.type_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Contribution Amount:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.amount_entry = ttk.Entry(form_frame, width=30)
        self.amount_entry.insert(0, "0")
        self.amount_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text="Website URL:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(form_frame, width=30)
        self.url_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="Add", command=self._add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add(self):
        try:
            event_id = int(self.event_entry.get())
            name = self.name_entry.get().strip()
            sponsor_type = self.type_combo.get()
            amount = float(self.amount_entry.get())
            website_url = self.url_entry.get().strip()

            if not name:
                messagebox.showerror("Error", "Sponsor name is required")
                return

            sponsor_id = EventSponsorManager.add_sponsor(
                event_id=event_id,
                sponsor_name=name,
                sponsor_type=sponsor_type,
                contribution_amount=amount,
                website_url=website_url
            )

            log_activity(f'Created event sponsor: {sponsor_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo("Success", f"Sponsor added (ID: {sponsor_id})")
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Error", "Invalid event ID or contribution amount")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add sponsor: {e}")


# Launcher function
def launch_campus_events_gui(root, auth):
    """Launch the Campus Events Hub GUI"""
    try:
        CampusEventsGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Campus Events GUI: {e}")
        print(f"❌ Campus Events GUI error: {e}")


__all__ = ['CampusEventsGUI', 'launch_campus_events_gui']
