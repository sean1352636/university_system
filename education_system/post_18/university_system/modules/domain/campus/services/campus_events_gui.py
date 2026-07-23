"""
Campus Events Hub GUI

Full-featured Tkinter interface for managing campus events, registrations,
event series, announcements, and sponsorships.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.modules.domain.campus.services.campus_events_core import (
    CampusEventManager,
    EventRegistrationManager,
    EventSeriesManager,
    EventAnnouncementManager,
    EventSponsorManager
)

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector


class CampusEventsGUI:
    """Campus Events Hub GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Campus Events GUI"""
        self.root = root
        self.auth = auth

        # Initialize i18n for multi-language support
        init_i18n()

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_t("common.error"), _t("campus_events.login_required"))
            return

        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it. Frames have no
        # ``wm_title``; Tk/Toplevel do.
        if root is not None and not hasattr(root, "wm_title"):
            self.window = root
        else:
            self.window = tk.Toplevel(root)
            self.window.title(_t("campus_events.window_title"))
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
            from education_system.post_18.university_system.infrastructure.database.schemas.campus_events_schemas import init_campus_events_system_db
            init_campus_events_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_t("common.warning"), _t("campus_events.db_init_issue", error=str(e)))

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = ttk.Label(
            header_frame,
            text=_t("campus_events.header_title"),
            font=('Arial', 18, 'bold')
        )
        self.title_label.pack(side=tk.LEFT)

        user_label = ttk.Label(
            header_frame,
            text=_t("campus_events.user_info", username=self.auth.current_user.get('username', 'Unknown')),
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT)

        # Language button
        self.lang_btn = ttk.Button(
            header_frame,
            text=f"{_t('menu.language')}: {get_current_language_name()}",
            command=self.change_language
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=10)

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
            text=_t("common.close"),
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def change_language(self):
        """Open language selector and refresh UI on change"""
        old_lang = get_current_language()
        show_gui_language_selector(self.window)
        new_lang = get_current_language()
        if old_lang != new_lang:
            self.refresh_ui_text()

    def refresh_ui_text(self):
        """Refresh all UI text after language change"""
        self.window.title(_t("campus_events.window_title"))
        # Recreate the widgets
        for widget in self.window.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _create_events_tab(self):
        """Create Events tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("campus_events.tab_events"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("campus_events.create_event"), command=self._create_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.view_upcoming"), command=self._view_upcoming_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_events).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.cancel_event"), command=self._cancel_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.uncancel_event"), command=self._uncancel_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.buttons.export_to_ics"), command=self._export_selected_to_ics).pack(side=tk.LEFT, padx=5)

        # Events list
        list_frame = ttk.LabelFrame(tab, text=_t("campus_events.events_list"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event Name', 'Type', 'Category', 'Date', 'Time', 'Location', 'Capacity', 'Status')
        col_headers = {
            'ID': _t("campus_events.columns.id"),
            'Event Name': _t("campus_events.columns.event_name"),
            'Type': _t("campus_events.columns.type"),
            'Category': _t("campus_events.columns.category"),
            'Date': _t("campus_events.columns.date"),
            'Time': _t("campus_events.columns.time"),
            'Location': _t("campus_events.columns.location"),
            'Capacity': _t("campus_events.columns.capacity"),
            'Status': _t("campus_events.columns.status")
        }
        self.events_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.events_tree.heading('#0', text='')
        self.events_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.events_tree.heading(col, text=col_headers.get(col, col))
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
        self.notebook.add(tab, text=_t("campus_events.tab_registrations"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("campus_events.register_event"), command=self._register_for_event).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.check_in"), command=self._check_in_attendee).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_registrations).pack(side=tk.LEFT, padx=5)

        # Registrations list
        list_frame = ttk.LabelFrame(tab, text=_t("campus_events.registrations_list"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'User ID', 'User Type', 'Registration Date', 'Status', 'Checked In')
        col_headers = {
            'ID': _t("campus_events.columns.id"),
            'Event ID': _t("campus_events.columns.event_id"),
            'User ID': _t("campus_events.columns.user_id"),
            'User Type': _t("campus_events.columns.user_type"),
            'Registration Date': _t("campus_events.columns.registration_date"),
            'Status': _t("campus_events.columns.status"),
            'Checked In': _t("campus_events.columns.checked_in")
        }
        self.registrations_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.registrations_tree.heading('#0', text='')
        self.registrations_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.registrations_tree.heading(col, text=col_headers.get(col, col))
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
        self.notebook.add(tab, text=_t("campus_events.tab_series"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("campus_events.create_series"), command=self._create_series).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_series).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("campus_events.deactivate_series"), command=self._deactivate_series).pack(side=tk.LEFT, padx=5)

        # Series list
        list_frame = ttk.LabelFrame(tab, text=_t("campus_events.series_list"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Series Name', 'Organizer', 'Pattern', 'Start Date', 'End Date', 'Active')
        col_headers = {
            'ID': _t("campus_events.columns.id"),
            'Series Name': _t("campus_events.columns.series_name"),
            'Organizer': _t("campus_events.columns.organizer"),
            'Pattern': _t("campus_events.columns.pattern"),
            'Start Date': _t("campus_events.columns.start_date"),
            'End Date': _t("campus_events.columns.end_date"),
            'Active': _t("campus_events.columns.active")
        }
        self.series_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.series_tree.heading('#0', text='')
        self.series_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.series_tree.heading(col, text=col_headers.get(col, col))
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
        self.notebook.add(tab, text=_t("campus_events.tab_announcements"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("campus_events.send_announcement"), command=self._send_announcement).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_announcements).pack(side=tk.LEFT, padx=5)

        # Announcements list
        list_frame = ttk.LabelFrame(tab, text=_t("campus_events.announcements_list"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'Announcement', 'Sent To', 'Sent By', 'Sent At')
        col_headers = {
            'ID': _t("campus_events.columns.id"),
            'Event ID': _t("campus_events.columns.event_id"),
            'Announcement': _t("campus_events.columns.announcement"),
            'Sent To': _t("campus_events.columns.sent_to"),
            'Sent By': _t("campus_events.columns.sent_by"),
            'Sent At': _t("campus_events.columns.sent_at")
        }
        self.announcements_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.announcements_tree.heading('#0', text='')
        self.announcements_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.announcements_tree.heading(col, text=col_headers.get(col, col))
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
        self.notebook.add(tab, text=_t("campus_events.tab_sponsors"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("campus_events.add_sponsor"), command=self._add_sponsor).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.refresh"), command=self._load_sponsors).pack(side=tk.LEFT, padx=5)

        # Sponsors list
        list_frame = ttk.LabelFrame(tab, text=_t("campus_events.sponsors_list"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('ID', 'Event ID', 'Sponsor Name', 'Type', 'Contribution', 'Website')
        col_headers = {
            'ID': _t("campus_events.columns.id"),
            'Event ID': _t("campus_events.columns.event_id"),
            'Sponsor Name': _t("campus_events.columns.sponsor_name"),
            'Type': _t("campus_events.columns.type"),
            'Contribution': _t("campus_events.columns.contribution"),
            'Website': _t("campus_events.columns.website")
        }
        self.sponsors_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.sponsors_tree.heading('#0', text='')
        self.sponsors_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.sponsors_tree.heading(col, text=col_headers.get(col, col))
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
                    SELECT event_id, title AS event_name, event_type, event_category,
                           DATE(start_datetime) AS event_date,
                           TIME(start_datetime) AS start_time,
                           location, max_capacity AS capacity, status
                    FROM unified_events
                    WHERE source_type = 'campus'
                    ORDER BY start_datetime DESC
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
                        row['location'] or _t("campus_events.defaults.tba"),
                        row['capacity'] or _t("campus_events.defaults.unlimited"),
                        row['status']
                    )
                    self.events_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_events", error=str(e)))

    def _load_registrations(self):
        """Load event registrations"""
        try:
            self.registrations_tree.delete(*self.registrations_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT registration_id, r.event_id, user_id, user_type,
                           registration_date, attendance_status, checked_in_at
                    FROM unified_event_registrations r
                    JOIN unified_events e ON r.event_id = e.event_id
                    WHERE e.source_type = 'campus'
                    ORDER BY registration_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['registration_id'],
                        row['event_id'],
                        row['user_id'],
                        row['user_type'].capitalize() if row['user_type'] else _t("campus_events.defaults.na"),
                        row['registration_date'][:10] if row['registration_date'] else '',
                        row['attendance_status'] or _t("campus_events.defaults.registered"),
                        row['checked_in_at'][:16] if row['checked_in_at'] else _t("common.no")
                    )
                    self.registrations_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_registrations", error=str(e)))

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
                        row['end_date'] or _t("campus_events.defaults.ongoing"),
                        '✓' if row['is_active'] else '✗'
                    )
                    self.series_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_series", error=str(e)))

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
                        row['sent_by'] or _t("campus_events.defaults.system"),
                        row['sent_at'][:16] if row['sent_at'] else ''
                    )
                    self.announcements_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_announcements", error=str(e)))

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
                        row['sponsor_type'] or _t("campus_events.defaults.na"),
                        f"£{row['contribution_amount']:,.2f}" if row['contribution_amount'] else _t("campus_events.defaults.na"),
                        row['website_url'] or _t("campus_events.defaults.na")
                    )
                    self.sponsors_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_sponsors", error=str(e)))

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
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.select_event_cancel"))
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]

        if not messagebox.askyesno(_t("campus_events.dialogs.confirm_cancel"), _t("campus_events.messages.confirm_cancel_event", name=event_name)):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE unified_events SET status = ? WHERE event_id = ? AND source_type = ?', ('cancelled', event_id, 'campus'))

            log_activity(f'Cancelled campus event: {event_id}',
                        user=self.auth.current_user.get('username'))
            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.event_cancelled"))
            self._load_events()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.cancel_event", error=str(e)))

    def _uncancel_event(self):
        """Un-cancel (reactivate) the selected event"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.select_event_uncancel"))
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]
        event_name = item['values'][1]
        current_status = item['values'][8]

        if current_status != 'cancelled':
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.event_not_cancelled", name=event_name, status=current_status))
            return

        if not messagebox.askyesno(_t("campus_events.dialogs.confirm_uncancel"), _t("campus_events.messages.confirm_uncancel_event", name=event_name)):
            return

        try:
            with transaction() as conn:
                conn.execute('UPDATE unified_events SET status = ? WHERE event_id = ? AND source_type = ?', ('scheduled', event_id, 'campus'))

            log_activity(f'Un-cancelled campus event: {event_id}',
                        user=self.auth.current_user.get('username'))
            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.event_reactivated"))
            self._load_events()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.uncancel_event", error=str(e)))

    def _export_selected_to_ics(self):
        """Export selected event to .ics file"""
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.select_event_calendar"))
            return

        item = self.events_tree.item(selection[0])
        event_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT title AS event_name,
                           DATE(start_datetime) AS event_date,
                           TIME(start_datetime) AS start_time,
                           TIME(end_datetime) AS end_time,
                           location, description
                    FROM unified_events
                    WHERE event_id = ? AND source_type = 'campus'
                ''', (event_id,))
                event = cursor.fetchone()

                if not event:
                    messagebox.showerror(_t("common.error"), _t("campus_events.errors.event_not_found"))
                    return

            self._export_to_ics(
                event_id, event['event_name'], event['event_date'],
                event['start_time'], event['end_time'],
                event['location'] or 'TBA',
                event['description'] or ''
            )

        except Exception as e:
            messagebox.showerror(_t("common.error"),
                f"Failed to add to Academic Calendar: {str(e)}")

    def _export_to_ics(self, event_id, event_name, event_date, start_time, end_time, location, description):
        """Export event to .ics file"""
        try:
            from datetime import datetime
            from tkinter import filedialog

            # Format datetime for iCal (YYYYMMDDTHHMMSS)
            start_dt = datetime.strptime(f"{event_date} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{event_date} {end_time}", "%Y-%m-%d %H:%M")

            start_ical = start_dt.strftime("%Y%m%dT%H%M%S")
            end_ical = end_dt.strftime("%Y%m%dT%H%M%S")
            created_ical = datetime.now().strftime("%Y%m%dT%H%M%S")

            # Create .ics content
            ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Campus Events//University System//EN
BEGIN:VEVENT
UID:{event_id}@campusevents.university.edu
DTSTAMP:{created_ical}
DTSTART:{start_ical}
DTEND:{end_ical}
SUMMARY:{event_name}
LOCATION:{location}
DESCRIPTION:{description}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

            # Save to file
            filename = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
                initialfile=f"{event_name.replace(' ', '_')}.ics"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(ics_content)

                log_activity(f'Exported event {event_id} to calendar file',
                            user=self.auth.current_user.get('username'))
                messagebox.showinfo(_t("common.success"),
                    _t("campus_events.messages.exported_to_ics", filename=filename))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.export_ics", error=str(e)))

    def _register_for_event(self):
        """Register for an event"""
        RegisterForEventDialog(self.window, self.auth, self._load_registrations)

    def _check_in_attendee(self):
        """Check in an attendee"""
        selection = self.registrations_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.select_registration"))
            return

        item = self.registrations_tree.item(selection[0])
        registration_id = item['values'][0]

        try:
            EventRegistrationManager.check_in_attendee(registration_id)

            log_activity(f'Checked in attendee: {registration_id}',
                        user=self.auth.current_user.get('username'))
            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.attendee_checked_in"))
            self._load_registrations()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.check_in", error=str(e)))

    def _create_series(self):
        """Create a new event series"""
        CreateSeriesDialog(self.window, self.auth, self._load_series)

    def _deactivate_series(self):
        """Deactivate the selected series"""
        selection = self.series_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("campus_events.warnings.select_series"))
            return

        item = self.series_tree.item(selection[0])
        series_id = item['values'][0]

        try:
            with transaction() as conn:
                conn.execute('UPDATE event_series SET is_active = 0 WHERE series_id = ?', (series_id,))

            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.series_deactivated"))
            self._load_series()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.deactivate_series", error=str(e)))

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
        self.dialog.title(_t("campus_events.dialogs.create_event"))
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.create_new_event"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("campus_events.labels.event_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=35)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.event_type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=[
            _t("campus_events.types.academic"), _t("campus_events.types.social"),
            _t("campus_events.types.athletic"), _t("campus_events.types.cultural"),
            _t("campus_events.types.career"), _t("campus_events.types.workshop"),
            _t("campus_events.types.other")
        ])
        self.type_combo.set(_t("campus_events.types.social"))
        self.type_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.category")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.category_combo = ttk.Combobox(form_frame, width=32, values=[
            _t("campus_events.categories.student_life"), _t("campus_events.categories.academics"),
            _t("campus_events.categories.athletics"), _t("campus_events.categories.arts"),
            _t("campus_events.categories.community_service"), _t("campus_events.types.other")
        ])
        self.category_combo.set(_t("campus_events.categories.student_life"))
        self.category_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.event_date")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(form_frame, width=35)
        self.date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        self.date_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.start_time")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_entry = ttk.Entry(form_frame, width=35)
        self.start_entry.insert(0, "18:00")
        self.start_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.end_time")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_entry = ttk.Entry(form_frame, width=35)
        self.end_entry.insert(0, "20:00")
        self.end_entry.grid(row=5, column=1, pady=5, padx=(10, 0))

        # Building/Location dropdown - integrated with Facilities
        ttk.Label(form_frame, text=_t("campus_events.labels.building")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.buildings_dict = self._load_buildings()
        building_names = list(self.buildings_dict.keys())
        self.building_combo = ttk.Combobox(form_frame, width=32, values=building_names, state='readonly')
        if building_names:
            self.building_combo.set(building_names[0])
        self.building_combo.grid(row=6, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.location")).grid(row=7, column=0, sticky=tk.W, pady=5)
        self.location_entry = ttk.Entry(form_frame, width=35)
        self.location_entry.grid(row=7, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.capacity")).grid(row=8, column=0, sticky=tk.W, pady=5)
        self.capacity_entry = ttk.Entry(form_frame, width=35)
        self.capacity_entry.insert(0, "0")
        self.capacity_entry.grid(row=8, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.registration_required")).grid(row=9, column=0, sticky=tk.W, pady=5)
        self.reg_var = tk.BooleanVar()
        ttk.Checkbutton(form_frame, variable=self.reg_var).grid(row=9, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.public_event")).grid(row=10, column=0, sticky=tk.W, pady=5)
        self.public_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, variable=self.public_var).grid(row=10, column=1, sticky=tk.W, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.description")).grid(row=11, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=33, height=4)
        self.desc_text.grid(row=11, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("common.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_buildings(self):
        """Load buildings from Facilities system"""
        buildings_dict = {}
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT building_id, building_name, building_code
                    FROM buildings
                    WHERE is_active = 1
                    ORDER BY building_name
                ''')
                for row in cursor.fetchall():
                    display_name = f"{row['building_name']} ({row['building_code']})"
                    buildings_dict[display_name] = {
                        'id': row['building_id'],
                        'name': row['building_name'],
                        'code': row['building_code']
                    }
        except Exception as e:
            print(f"Warning: Could not load buildings: {e}")
            # Provide fallback option
            buildings_dict['Custom Location'] = {'id': None, 'name': 'Custom Location', 'code': ''}

        if not buildings_dict:
            buildings_dict['Custom Location'] = {'id': None, 'name': 'Custom Location', 'code': ''}

        return buildings_dict

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            event_type = self.type_combo.get()
            category = self.category_combo.get()
            event_date = self.date_entry.get().strip()
            start_time = self.start_entry.get().strip()
            end_time = self.end_entry.get().strip()

            # Get location from building selection or custom location
            selected_building = self.building_combo.get()
            custom_location = self.location_entry.get().strip()

            if custom_location:
                location = custom_location
            elif selected_building and selected_building in self.buildings_dict:
                building_info = self.buildings_dict[selected_building]
                location = building_info['name']
            else:
                location = ""

            capacity = int(self.capacity_entry.get())
            registration_required = self.reg_var.get()
            is_public = self.public_var.get()
            description = self.desc_text.get('1.0', tk.END).strip()

            if not name or not event_date or not start_time or not end_time:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.required_fields"))
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

            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.event_created", event_id=event_id))
            self.callback()

            # Offer ICS export
            if messagebox.askyesno(_t("common.export"),
                                   "Would you like to export this event as an .ics calendar file?"):
                self._offer_ics_export(event_id, name, event_date, start_time, end_time, location, description)

            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.invalid_capacity"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.create_event", error=str(e)))

    def _offer_ics_export(self, event_id, event_name, event_date, start_time, end_time, location, description):
        """Export event to .ics file"""
        try:
            from tkinter import filedialog

            start_dt = datetime.strptime(f"{event_date} {start_time}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{event_date} {end_time}", "%Y-%m-%d %H:%M")

            ics_content = (
                "BEGIN:VCALENDAR\nVERSION:2.0\n"
                "PRODID:-//Campus Events//University System//EN\n"
                "BEGIN:VEVENT\n"
                f"UID:{event_id}@campusevents.university.edu\n"
                f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%S')}\n"
                f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}\n"
                f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}\n"
                f"SUMMARY:{event_name}\n"
                f"LOCATION:{location or 'TBA'}\n"
                f"DESCRIPTION:{description or ''}\n"
                "STATUS:CONFIRMED\n"
                "END:VEVENT\nEND:VCALENDAR"
            )

            filename = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
                initialfile=f"{event_name.replace(' ', '_')}.ics"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(ics_content)
                messagebox.showinfo(_t("common.success"),
                    _t("campus_events.messages.exported_to_ics", filename=filename))

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to export: {e}")


class ViewUpcomingEventsDialog:
    """Dialog for viewing upcoming events"""

    def __init__(self, parent, auth):
        self.auth = auth

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("campus_events.dialogs.upcoming_events"))
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)

        self._create_widgets()
        self._load_upcoming()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.upcoming_events_30_days"),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # List
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('Event Name', 'Date', 'Time', 'Location', 'Category', 'Capacity')
        col_headers = {
            'Event Name': _t("campus_events.columns.event_name"),
            'Date': _t("campus_events.columns.date"),
            'Time': _t("campus_events.columns.time"),
            'Location': _t("campus_events.columns.location"),
            'Category': _t("campus_events.columns.category"),
            'Capacity': _t("campus_events.columns.capacity")
        }
        self.tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=20)

        self.tree.heading('#0', text='')
        self.tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.tree.heading(col, text=col_headers.get(col, col))
            if col == 'Event Name':
                self.tree.column(col, width=250)
            else:
                self.tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"), command=self.dialog.destroy).pack(pady=(10, 0))

    def _load_upcoming(self):
        try:
            events = CampusEventManager.get_upcoming_events(days_ahead=30)

            for event in events:
                values = (
                    event.get('event_name', _t("campus_events.defaults.na")),
                    event.get('event_date', _t("campus_events.defaults.na")),
                    f"{event.get('start_time', '')} - {event.get('end_time', '')}",
                    event.get('location', _t("campus_events.defaults.tba")),
                    event.get('event_category', _t("campus_events.defaults.na")),
                    event.get('capacity', _t("campus_events.defaults.unlimited")) if event.get('capacity') else _t("campus_events.defaults.unlimited")
                )
                self.tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.load_upcoming", error=str(e)))


class RegisterForEventDialog:
    """Dialog for registering for an event"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("campus_events.dialogs.register_for_event"))
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.register_for_event"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Event dropdown - load upcoming events
        ttk.Label(form_frame, text=_t("campus_events.labels.select_event")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.events_dict = self._load_upcoming_events()
        event_names = list(self.events_dict.keys())
        self.event_combo = ttk.Combobox(form_frame, width=40, values=event_names, state='readonly')
        if event_names:
            self.event_combo.set(event_names[0])
        self.event_combo.grid(row=0, column=1, pady=5, padx=(10, 0), columnspan=2)

        ttk.Label(form_frame, text=_t("campus_events.labels.user_id")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_entry = ttk.Entry(form_frame, width=43)
        self.user_entry.insert(0, self.auth.current_user.get('username', ''))
        self.user_entry.grid(row=1, column=1, pady=5, padx=(10, 0), columnspan=2)

        ttk.Label(form_frame, text=_t("campus_events.labels.user_type")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.user_type_combo = ttk.Combobox(form_frame, width=40, values=[
            _t("campus_events.user_types.student"), _t("campus_events.user_types.staff"),
            _t("campus_events.user_types.faculty"), _t("campus_events.user_types.guest")
        ])
        self.user_type_combo.set(_t("campus_events.user_types.student"))
        self.user_type_combo.grid(row=2, column=1, pady=5, padx=(10, 0), columnspan=2)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("campus_events.buttons.register"), command=self._register).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _load_upcoming_events(self):
        """Load upcoming events for dropdown"""
        events_dict = {}
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT event_id, title AS event_name,
                           DATE(start_datetime) AS event_date,
                           TIME(start_datetime) AS start_time,
                           location
                    FROM unified_events
                    WHERE source_type = 'campus'
                      AND DATE(start_datetime) >= DATE('now')
                      AND status = 'scheduled'
                    ORDER BY start_datetime
                    LIMIT 50
                ''')
                for row in cursor.fetchall():
                    display_name = f"{row['event_name']} - {row['event_date']} {row['start_time']} ({row['location'] or 'TBA'})"
                    events_dict[display_name] = row['event_id']
        except Exception as e:
            print(f"Warning: Could not load events: {e}")

        if not events_dict:
            events_dict['No upcoming events available'] = None

        return events_dict

    def _register(self):
        try:
            # Get event_id from selected event
            selected_event = self.event_combo.get()
            if not selected_event or selected_event not in self.events_dict:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.select_event"))
                return

            event_id = self.events_dict[selected_event]
            if event_id is None:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.no_events_available"))
                return

            user_id = self.user_entry.get().strip()
            user_type = self.user_type_combo.get()

            if not user_id:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.user_id_required"))
                return

            registration_id = EventRegistrationManager.register_for_event(
                event_id=event_id,
                user_id=user_id,
                user_type=user_type
            )

            log_activity(f'Created event registration: {registration_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.registered_success", registration_id=registration_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.invalid_event_id"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.register_event", error=str(e)))


class CreateSeriesDialog:
    """Dialog for creating an event series"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("campus_events.dialogs.create_series"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.create_series"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("campus_events.labels.series_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.recurrence_pattern")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.pattern_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("campus_events.patterns.daily"), _t("campus_events.patterns.weekly"),
            _t("campus_events.patterns.bi_weekly"), _t("campus_events.patterns.monthly")
        ])
        self.pattern_combo.set(_t("campus_events.patterns.weekly"))
        self.pattern_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.start_date")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_entry = ttk.Entry(form_frame, width=30)
        self.start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.start_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.end_date")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_entry = ttk.Entry(form_frame, width=30)
        self.end_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.description")).grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.desc_text = scrolledtext.ScrolledText(form_frame, width=28, height=6)
        self.desc_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("common.create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            pattern = self.pattern_combo.get()
            start_date = self.start_entry.get().strip()
            end_date = self.end_entry.get().strip()
            description = self.desc_text.get('1.0', tk.END).strip()

            if not name or not start_date:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.series_required_fields"))
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

            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.series_created", series_id=series_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.create_series", error=str(e)))


class SendAnnouncementDialog:
    """Dialog for sending an event announcement"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("campus_events.dialogs.send_announcement"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.send_announcement"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Event dropdown - load all events with registrations
        ttk.Label(form_frame, text=_t("campus_events.labels.select_event")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.events_dict = self._load_events_with_registrations()
        event_names = list(self.events_dict.keys())
        self.event_combo = ttk.Combobox(form_frame, width=40, values=event_names, state='readonly')
        if event_names:
            self.event_combo.set(event_names[0])
        self.event_combo.bind('<<ComboboxSelected>>', self._on_event_selected)
        self.event_combo.grid(row=0, column=1, pady=5, padx=(10, 0), columnspan=2)

        # Registration count info
        self.registrant_info_label = ttk.Label(form_frame, text="", foreground="blue")
        self.registrant_info_label.grid(row=1, column=1, sticky=tk.W, pady=2, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.send_to")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.sent_to_combo = ttk.Combobox(form_frame, width=37, values=[
            _t("campus_events.recipients.all_registrants"), _t("campus_events.user_types.staff"),
            _t("campus_events.user_types.students"), _t("campus_events.user_types.faculty")
        ])
        self.sent_to_combo.set(_t("campus_events.recipients.all_registrants"))
        self.sent_to_combo.grid(row=2, column=1, pady=5, padx=(10, 0), columnspan=2)

        ttk.Label(form_frame, text=_t("campus_events.labels.announcement")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.announcement_text = scrolledtext.ScrolledText(form_frame, width=38, height=10)
        self.announcement_text.grid(row=3, column=1, pady=5, padx=(10, 0), columnspan=2)

        # Email preview info
        info_label = ttk.Label(form_frame, text="✉️ Emails will be sent to all registered users",
                              foreground="green", font=('Arial', 9, 'italic'))
        info_label.grid(row=4, column=1, sticky=tk.W, pady=5, padx=(10, 0), columnspan=2)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("common.send"), command=self._send).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Update registrant count for initial selection
        if event_names:
            self._update_registrant_count()

    def _load_events_with_registrations(self):
        """Load events that have registrations"""
        events_dict = {}
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT DISTINCT e.event_id, e.title AS event_name,
                           DATE(e.start_datetime) AS event_date,
                           TIME(e.start_datetime) AS start_time,
                           COUNT(r.registration_id) as reg_count
                    FROM unified_events e
                    LEFT JOIN unified_event_registrations r ON e.event_id = r.event_id
                    WHERE e.source_type = 'campus' AND e.status = 'scheduled'
                    GROUP BY e.event_id
                    ORDER BY e.start_datetime DESC
                    LIMIT 50
                ''')
                for row in cursor.fetchall():
                    reg_count = row['reg_count'] or 0
                    display_name = f"{row['event_name']} - {row['event_date']} ({reg_count} registered)"
                    events_dict[display_name] = {
                        'id': row['event_id'],
                        'name': row['event_name'],
                        'reg_count': reg_count
                    }
        except Exception as e:
            print(f"Warning: Could not load events: {e}")

        if not events_dict:
            events_dict['No events available'] = {'id': None, 'name': '', 'reg_count': 0}

        return events_dict

    def _on_event_selected(self, event):
        """Update registrant count when event is selected"""
        self._update_registrant_count()

    def _update_registrant_count(self):
        """Update the registrant count label"""
        selected_event = self.event_combo.get()
        if selected_event and selected_event in self.events_dict:
            reg_count = self.events_dict[selected_event]['reg_count']
            self.registrant_info_label.config(
                text=f"📊 {reg_count} user(s) registered for this event"
            )

    def _send(self):
        try:
            # Get event_id from selected event
            selected_event = self.event_combo.get()
            if not selected_event or selected_event not in self.events_dict:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.select_event"))
                return

            event_info = self.events_dict[selected_event]
            event_id = event_info['id']

            if event_id is None:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.no_events_available"))
                return

            sent_to = self.sent_to_combo.get()
            announcement = self.announcement_text.get('1.0', tk.END).strip()

            if not announcement:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.announcement_required"))
                return

            # Confirm before sending emails
            reg_count = event_info['reg_count']
            if reg_count == 0:
                messagebox.showwarning(
                    _t("common.warning"),
                    "No users are registered for this event. The announcement will be saved but no emails will be sent."
                )

            confirm_msg = f"Send announcement to {reg_count} registered user(s)?\n\nEmails will be sent via the email queue system."
            if not messagebox.askyesno(_t("campus_events.dialogs.confirm_send"), confirm_msg):
                return

            # Send announcement (this will also trigger email sending)
            announcement_id = EventAnnouncementManager.send_announcement(
                event_id=event_id,
                announcement_text=announcement,
                sent_to=sent_to,
                sent_by=self.auth.current_user.get('username', '')
            )

            log_activity(f'Created event announcement: {announcement_id}',
                        user=self.auth.current_user.get('username'))

            success_msg = f"✅ Announcement #{announcement_id} sent successfully!\n\n📧 Emails delivered to {reg_count} registered user(s)\n\n📬 Check recipient inboxes in Email Manager\n\nEvent: {event_info['name']}\n\n💡 Tip: Recipients can view this in their inbox via\nMain Menu → Email Manager → Messages"
            messagebox.showinfo(_t("common.success"), success_msg)
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.invalid_event_id"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.send_announcement", error=str(e)))


class AddSponsorDialog:
    """Dialog for adding an event sponsor"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("campus_events.dialogs.add_sponsor"))
        self.dialog.geometry("400x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("campus_events.dialogs.add_sponsor"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("campus_events.labels.event_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.event_entry = ttk.Entry(form_frame, width=30)
        self.event_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.sponsor_name")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=30)
        self.name_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.sponsor_type")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=27, values=[
            _t("campus_events.sponsor_types.corporate"), _t("campus_events.sponsor_types.individual"),
            _t("campus_events.sponsor_types.foundation"), _t("campus_events.sponsor_types.government")
        ])
        self.type_combo.set(_t("campus_events.sponsor_types.corporate"))
        self.type_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.contribution_amount")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.amount_entry = ttk.Entry(form_frame, width=30)
        self.amount_entry.insert(0, "0")
        self.amount_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("campus_events.labels.website_url")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(form_frame, width=30)
        self.url_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("common.add"), command=self._add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add(self):
        try:
            event_id = int(self.event_entry.get())
            name = self.name_entry.get().strip()
            sponsor_type = self.type_combo.get()
            amount = float(self.amount_entry.get())
            website_url = self.url_entry.get().strip()

            if not name:
                messagebox.showerror(_t("common.error"), _t("campus_events.errors.sponsor_name_required"))
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

            messagebox.showinfo(_t("common.success"), _t("campus_events.messages.sponsor_added", sponsor_id=sponsor_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.invalid_id_or_amount"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("campus_events.errors.add_sponsor", error=str(e)))


# Launcher function
def launch_campus_events_gui(root, auth):
    """Launch the Campus Events Hub GUI"""
    try:
        CampusEventsGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("campus_events.errors.launch_gui", error=str(e)))
        print(f"❌ Campus Events GUI error: {e}")


__all__ = ['CampusEventsGUI', 'launch_campus_events_gui']
