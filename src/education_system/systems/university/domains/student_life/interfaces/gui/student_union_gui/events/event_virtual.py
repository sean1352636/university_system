
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
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
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    virtual_event_records as vev,
)
from education_system.systems.university.domains.student_life.interfaces.gui.student_union_gui.core import (
    su_records,
)

_V = 'gui.pastoral.student_union_gui.events.event_virtual'


def _event_label(r):
    return f"{r['title']} — {r.get('starts') or 'no date'} (#{r['event_id']})"


def _open_schedule_page(parent, platform):
    """Send the host to the platform to create a real meeting, then paste its link."""
    page = vev.SCHEDULE_PAGES.get(platform)
    if not page:
        messagebox.showinfo("Meeting link", "Create the meeting on your platform and paste its "
                            "join link into 'Meeting Link'.", parent=parent)
        return
    if messagebox.askyesno("Meeting link",
                           f"This app cannot create {platform} meetings itself.\n\n"
                           f"Open {page} to schedule the meeting, then paste its join link here?",
                           parent=parent):
        su_records.open_target(page)


class VirtualEventsDialog:
    """Main dialog for virtual events management"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self._events = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_V}.windows.virtual_events_platform', default="Virtual Events Platform"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t(f'{_V}.labels.virtual_events_platform', default="💻 Virtual Events Platform"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t(f'{_V}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        # Action buttons
        button_grid = ttk.Frame(main_frame)
        button_grid.pack(fill='x', pady=(0, 10))

        actions = [
            ("Create Virtual Event", self.create_virtual, "Set up online-only event"),
            ("Setup Hybrid Event", self.setup_hybrid, "Combine in-person + virtual"),
            ("Virtual Attendance", self.track_attendance, "Track online participation"),
            ("Tech Support", self.tech_support, "Technical assistance"),
        ]

        for i, (title, command, description) in enumerate(actions):
            card = ttk.LabelFrame(button_grid, text=title)
            card.grid(row=i//2, column=i%2, padx=10, pady=5, sticky='nsew')
            ttk.Label(card, text=description).pack(padx=10, pady=5)
            ttk.Button(card, text=_t(f'{_V}.buttons.open', default="Open"), command=command).pack(padx=10, pady=5)

        button_grid.columnconfigure(0, weight=1)
        button_grid.columnconfigure(1, weight=1)

        # Online events from the SU events store
        list_frame = ttk.LabelFrame(main_frame, text="Online & Hybrid Events")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        btns = ttk.Frame(list_frame)
        btns.pack(side='bottom', fill='x', padx=5, pady=5)
        ttk.Button(btns, text="Join / Open Link", command=self.join_selected).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Set Meeting Link…", command=self.set_link).pack(side='left', padx=(0, 10))
        ttk.Button(btns, text="Refresh", command=self.load_events).pack(side='left')

        cols = ('Event', 'Starts', 'Type', 'Platform / Venue', 'Registered', 'Meeting Link')
        self.tree = ttk.Treeview(list_frame, columns=cols, show='headings', height=8)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=220 if c in ('Event', 'Meeting Link') else 110)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_events(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        try:
            with su_records.db() as conn:
                rows = vev.list_events(conn)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load events:\n{e}", parent=self.dialog)
            return
        self._events = {str(r['event_id']): r for r in rows}
        for r in rows:
            where = r.get('location') or r['meta'].get('platform') or ''
            self.tree.insert('', 'end', iid=str(r['event_id']), values=(
                r['title'], r.get('starts') or '', (r.get('event_category') or 'virtual').title(),
                where, r.get('registered') or 0, r.get('virtual_link') or 'Not set'))
        if not rows:
            self.tree.insert('', 'end', iid='empty', values=("No online events yet", '', '', '', '', ''))

    def _selected(self):
        sel = self.tree.selection()
        r = self._events.get(sel[0]) if sel else None
        if not r:
            messagebox.showwarning("Warning", "Select an event first.", parent=self.dialog)
        return r

    def join_selected(self):
        r = self._selected()
        if not r:
            return
        if not r.get('virtual_link'):
            messagebox.showinfo("No link", "This event has no meeting link yet.", parent=self.dialog)
            return
        if not su_records.open_target(r['virtual_link']):
            messagebox.showwarning("Join", f"Could not open {r['virtual_link']}.", parent=self.dialog)

    def set_link(self):
        r = self._selected()
        if not r:
            return
        if not su_records.is_staff(self.auth):
            with su_records.db() as conn:
                me = su_records.owner_id(conn, self.auth)
            if not me or str(r.get('organizer_id') or '') != str(me):
                messagebox.showwarning("Not allowed", "Only the organiser or Student Union staff "
                                       "can change the meeting link.", parent=self.dialog)
                return
        link = simpledialog.askstring("Meeting link", "Join link (https://…):",
                                      initialvalue=r.get('virtual_link') or '', parent=self.dialog)
        if link is None:
            return
        try:
            with su_records.db() as conn:
                vev.set_meeting_link(conn, r['event_id'], link)
        except ValueError as e:
            messagebox.showwarning("Warning", str(e), parent=self.dialog)
            return
        self.load_events()

    def create_virtual(self):
        dialog = CreateVirtualEventDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_events()

    def setup_hybrid(self):
        dialog = SetupHybridEventDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)
        self.load_events()

    def track_attendance(self):
        dialog = VirtualAttendanceDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)

    def tech_support(self):
        dialog = VirtualTechSupportDialog(self.dialog, self.auth)
        self.dialog.wait_window(dialog.dialog)



class CreateVirtualEventDialog:
    """Dialog for creating virtual events (saved to unified_events)"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.created_id = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_V}.windows.create_virtual_event', default="Create Virtual Event"))
        self.dialog.geometry("800x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=_t(f'{_V}.labels.create_virtual_event', default="Create Virtual Event"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f'{_V}.buttons.create_event', default="Create Event"), command=self.create_event).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_V}.buttons.generate_meeting_link', default="Generate Meeting Link"), command=self.generate_link).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_V}.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

        # Form
        form = ttk.Frame(main_frame)
        form.pack(fill='both', expand=True)

        ttk.Label(form, text=_t(f'{_V}.labels.event_name', default="Event Name:")).grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(form, width=50)
        self.name_entry.grid(row=0, column=1, pady=5, sticky='ew')

        ttk.Label(form, text=_t(f'{_V}.labels.platform', default="Platform:")).grid(row=1, column=0, sticky='w', pady=5)
        self.platform_combo = ttk.Combobox(form, width=48, state='readonly')
        self.platform_combo['values'] = vev.PLATFORMS
        self.platform_combo.grid(row=1, column=1, pady=5, sticky='ew')
        self.platform_combo.current(0)

        ttk.Label(form, text=_t(f'{_V}.labels.meeting_link', default="Meeting Link:")).grid(row=2, column=0, sticky='w', pady=5)
        self.link_entry = ttk.Entry(form, width=50)
        self.link_entry.grid(row=2, column=1, pady=5, sticky='ew')

        ttk.Label(form, text=_t(f'{_V}.labels.virtual_capacity', default="Virtual Capacity:")).grid(row=3, column=0, sticky='w', pady=5)
        self.capacity_entry = ttk.Entry(form, width=50)
        self.capacity_entry.grid(row=3, column=1, pady=5, sticky='ew')
        self.capacity_entry.insert(0, "100")

        ttk.Label(form, text=_t(f'{_V}.labels.date_time', default="Date & Time:")).grid(row=4, column=0, sticky='w', pady=5)
        self.datetime_entry = ttk.Entry(form, width=50)
        self.datetime_entry.grid(row=4, column=1, pady=5, sticky='ew')
        self.datetime_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M'))

        ttk.Label(form, text="Ends (YYYY-MM-DD HH:MM):").grid(row=5, column=0, sticky='w', pady=5)
        self.end_entry = ttk.Entry(form, width=50)
        self.end_entry.grid(row=5, column=1, pady=5, sticky='ew')

        ttk.Label(form, text="Description:").grid(row=6, column=0, sticky='nw', pady=5)
        self.desc_text = scrolledtext.ScrolledText(form, width=50, height=4, wrap=tk.WORD)
        self.desc_text.grid(row=6, column=1, pady=5, sticky='ew')

        form.columnconfigure(1, weight=1)

        # Features
        features_frame = ttk.LabelFrame(main_frame, text=_t(f'{_V}.labels.features', default="Features"))
        features_frame.pack(fill='x', pady=15)

        self.recording_var = tk.BooleanVar(value=True)
        self.streaming_var = tk.BooleanVar(value=False)
        self.qa_var = tk.BooleanVar(value=True)
        self.breakout_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(features_frame, text=_t(f'{_V}.buttons.enable_recording', default="Enable Recording"), variable=self.recording_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text=_t(f'{_V}.buttons.live_streaming', default="Live Streaming"), variable=self.streaming_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text=_t(f'{_V}.buttons.q_a_session', default="Q&A Session"), variable=self.qa_var).pack(anchor='w', padx=10, pady=3)
        ttk.Checkbutton(features_frame, text=_t(f'{_V}.buttons.breakout_rooms', default="Breakout Rooms"), variable=self.breakout_var).pack(anchor='w', padx=10, pady=3)

    def _features(self):
        features = []
        if self.recording_var.get(): features.append("Recording")
        if self.streaming_var.get(): features.append("Streaming")
        if self.qa_var.get(): features.append("Q&A")
        if self.breakout_var.get(): features.append("Breakout Rooms")
        return features

    def create_event(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning(_t(f'{_V}.dialogs.warning', default="Warning"), _t(f'{_V}.dialogs.please_enter_an_event_name', default="Please enter an event name."), parent=self.dialog)
            return
        features = self._features()
        try:
            with su_records.db() as conn:
                self.created_id = vev.create_event(
                    conn, title=name, start=self.datetime_entry.get(), end=self.end_entry.get(),
                    description=self.desc_text.get(1.0, tk.END), platform=self.platform_combo.get(),
                    meeting_link=self.link_entry.get(), virtual_capacity=self.capacity_entry.get(),
                    mode='virtual', features=features, organizer_id=su_records.owner_id(conn, self.auth))
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not create the event:\n{e}", parent=self.dialog)
            return

        link = self.link_entry.get().strip()
        messagebox.showinfo(_t(f'{_V}.dialogs.success', default="Success"),
                            f"Virtual event '{name}' created (event #{self.created_id}) and added to the calendar.\n\n"
                            f"Platform: {self.platform_combo.get()}\nCapacity: {self.capacity_entry.get() or 'unlimited'}\n"
                            f"Features: {', '.join(features) or 'none'}\n"
                            f"Meeting link: {link or 'not set yet — add it from the Virtual Events list'}",
                            parent=self.dialog)
        self.dialog.destroy()

    def generate_link(self):
        _open_schedule_page(self.dialog, self.platform_combo.get())
        self.link_entry.focus_set()



class SetupHybridEventDialog:
    """Dialog for setting up hybrid events (saved to unified_events)"""

    INTEGRATION_FEATURES = (
        "Live stream venue to virtual attendees",
        "Virtual Q&A visible in venue",
        "Unified chat system",
        "Shared polls and surveys",
        "Networking rooms for both groups",
    )

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.created_id = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_V}.windows.setup_hybrid_event', default="Setup Hybrid Event"))
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_V}.labels.setup_hybrid_event_in_person_virtual', default="Setup Hybrid Event (In-Person + Virtual)"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side='bottom', fill='x')

        ttk.Button(button_frame, text=_t(f'{_V}.buttons.create_hybrid_event', default="Create Hybrid Event"), command=self.create_hybrid).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t(f'{_V}.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

        # Event basics
        basics = ttk.Frame(main_frame)
        basics.pack(fill='x', pady=(0, 10))
        ttk.Label(basics, text="Event Name:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.name_entry = ttk.Entry(basics, width=50)
        self.name_entry.grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(basics, text="Date & Time (YYYY-MM-DD HH:MM):").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.start_entry = ttk.Entry(basics, width=50)
        self.start_entry.grid(row=1, column=1, sticky='ew', padx=10, pady=5)
        self.start_entry.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M'))
        ttk.Label(basics, text="Ends (YYYY-MM-DD HH:MM):").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.end_entry = ttk.Entry(basics, width=50)
        self.end_entry.grid(row=2, column=1, sticky='ew', padx=10, pady=5)
        basics.columnconfigure(1, weight=1)

        # Notebook for in-person and virtual setup
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # In-person tab
        inperson_frame = ttk.Frame(notebook)
        notebook.add(inperson_frame, text=_t(f'{_V}.tabs.in_person', default="In-Person"))

        ttk.Label(inperson_frame, text=_t(f'{_V}.labels.venue', default="Venue:")).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.venue_entry = ttk.Entry(inperson_frame, width=40)
        self.venue_entry.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(inperson_frame, text=_t(f'{_V}.labels.capacity', default="Capacity:")).grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.capacity_entry = ttk.Entry(inperson_frame, width=40)
        self.capacity_entry.grid(row=1, column=1, padx=10, pady=5)
        self.capacity_entry.insert(0, "50")

        # Virtual tab
        virtual_frame = ttk.Frame(notebook)
        notebook.add(virtual_frame, text=_t(f'{_V}.tabs.virtual', default="Virtual"))

        ttk.Label(virtual_frame, text=_t(f'{_V}.labels.platform', default="Platform:")).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.platform_combo = ttk.Combobox(virtual_frame, width=38, state='readonly')
        self.platform_combo['values'] = ('Zoom', 'Microsoft Teams', 'Google Meet')
        self.platform_combo.grid(row=0, column=1, padx=10, pady=5)
        self.platform_combo.current(0)

        ttk.Label(virtual_frame, text=_t(f'{_V}.labels.virtual_capacity', default="Virtual Capacity:")).grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.vcapacity_entry = ttk.Entry(virtual_frame, width=40)
        self.vcapacity_entry.grid(row=1, column=1, padx=10, pady=5)
        self.vcapacity_entry.insert(0, "100")

        ttk.Label(virtual_frame, text="Meeting Link:").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.link_entry = ttk.Entry(virtual_frame, width=40)
        self.link_entry.grid(row=2, column=1, padx=10, pady=5)
        ttk.Button(virtual_frame, text="Get a meeting link…",
                   command=lambda: _open_schedule_page(self.dialog, self.platform_combo.get())).grid(row=3, column=1, sticky='w', padx=10, pady=5)

        # Integration tab
        integration_frame = ttk.Frame(notebook)
        notebook.add(integration_frame, text=_t(f'{_V}.tabs.integration', default="Integration"))

        self.feature_vars = {}
        for i, feature in enumerate(self.INTEGRATION_FEATURES):
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(integration_frame, text=feature, variable=var).grid(row=i, column=0, sticky='w', padx=10, pady=5)
            self.feature_vars[feature] = var

        # Setup summary
        summary_frame = ttk.LabelFrame(main_frame, text=_t(f'{_V}.labels.hybrid_event_benefits', default="Hybrid Event Benefits"))
        summary_frame.pack(fill='x', pady=(0, 15))

        summary = """✓ Wider reach (In-person + Virtual attendance)
✓ Flexible participation options
✓ Increased accessibility
✓ Recording available for both groups"""
        ttk.Label(summary_frame, text=summary, justify='left').pack(padx=15, pady=10)

    def create_hybrid(self):
        name = self.name_entry.get().strip()
        features = [f for f, v in self.feature_vars.items() if v.get()]
        try:
            with su_records.db() as conn:
                self.created_id = vev.create_event(
                    conn, title=name, start=self.start_entry.get(), end=self.end_entry.get(),
                    platform=self.platform_combo.get(), meeting_link=self.link_entry.get(),
                    virtual_capacity=self.vcapacity_entry.get(), mode='hybrid',
                    venue=self.venue_entry.get(), in_person_capacity=self.capacity_entry.get(),
                    features=features, organizer_id=su_records.owner_id(conn, self.auth))
        except ValueError as e:
            messagebox.showwarning("Check the form", str(e), parent=self.dialog)
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not create the event:\n{e}", parent=self.dialog)
            return
        messagebox.showinfo(_t(f'{_V}.dialogs.success', default="Success"),
                            f"Hybrid event '{name}' created (event #{self.created_id}) and added to the calendar.\n\n"
                            f"Venue: {self.venue_entry.get().strip()} (capacity {self.capacity_entry.get() or '—'})\n"
                            f"Online: {self.platform_combo.get()} (capacity {self.vcapacity_entry.get() or '—'})\n"
                            f"Meeting link: {self.link_entry.get().strip() or 'not set yet'}",
                            parent=self.dialog)
        self.dialog.destroy()



class VirtualAttendanceDialog:
    """Dialog for tracking virtual attendance from event registrations"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self._events = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_V}.windows.virtual_attendance_tracking', default="Virtual Attendance Tracking"))
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_V}.labels.virtual_attendance_tracking', default="Virtual Attendance Tracking"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        pick = ttk.Frame(main_frame)
        pick.pack(fill='x', pady=(0, 10))
        ttk.Label(pick, text="Event:").pack(side='left')
        self.event_combo = ttk.Combobox(pick, width=70, state='readonly')
        self.event_combo.pack(side='left', padx=5)
        self.event_combo.bind('<<ComboboxSelected>>', lambda e: self.load_attendance())

        ttk.Button(main_frame, text=_t(f'{_V}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        stats_frame = ttk.LabelFrame(main_frame, text=_t(f'{_V}.labels.session_statistics', default="Session Statistics"))
        stats_frame.pack(side='bottom', fill='x', pady=(0, 15))
        self.stats_label = ttk.Label(stats_frame, text="", justify='left', font=('Courier', 10))
        self.stats_label.pack(padx=15, pady=10, anchor='w')

        list_frame = ttk.LabelFrame(main_frame, text=_t(f'{_V}.labels.virtual_attendees', default="Virtual Attendees"))
        list_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Name', 'Registered', 'Join Time', 'Leave Time', 'Duration', 'Status')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill='both', expand=True, padx=5, pady=5)

    def load_events(self):
        try:
            with su_records.db() as conn:
                rows = vev.list_events(conn)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load events:\n{e}", parent=self.dialog)
            rows = []
        self._events = {_event_label(r): r['event_id'] for r in rows}
        self.event_combo['values'] = tuple(self._events)
        if rows:
            self.event_combo.current(0)
        self.load_attendance()

    def load_attendance(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        event_id = self._events.get(self.event_combo.get())
        if event_id is None:
            self.stats_label.config(text="No online or hybrid events yet.")
            return
        try:
            with su_records.db() as conn:
                rows = vev.attendance(conn, event_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load attendance:\n{e}", parent=self.dialog)
            return
        for r in rows:
            self.tree.insert('', 'end', values=(
                r['name'], (r.get('registration_date') or '')[:16],
                (str(r.get('checked_in_at') or '—'))[:16], (str(r.get('check_out_time') or '—'))[:16],
                r['duration'], (r.get('attendance_status') or 'registered').replace('_', ' ').title()))
        if not rows:
            self.tree.insert('', 'end', values=("No registrations yet", '', '', '', '', ''))
        joined = [r for r in rows if r.get('checked_in_at')]
        self.stats_label.config(text=(
            f"Registered: {len(rows)}\n"
            f"Joined (check-in recorded): {len(joined)}\n"
            f"Leave time recorded: {sum(1 for r in rows if r.get('check_out_time'))}\n"
            "Engagement and connection quality are not recorded by this app."))



class VirtualTechSupportDialog:
    """Dialog for virtual event tech support"""

    TUTORIALS = {
        "How to join a virtual event": (
            "1. Open Virtual Events and select the event.\n2. Press 'Join / Open Link'.\n"
            "3. Your browser opens the meeting; allow it to open the Zoom/Teams/Meet app if asked.\n"
            "4. Join a few minutes early to check audio."),
        "Using chat and Q&A features": (
            "Chat and Q&A run inside the meeting platform. Look for the Chat or Q&A button on the "
            "meeting toolbar; hosts can moderate questions there."),
        "Sharing your screen": (
            "Press 'Share' (Zoom/Teams) or 'Present now' (Meet) on the meeting toolbar, choose a "
            "window or screen, and grant screen-recording permission if your system asks."),
        "Using breakout rooms": (
            "Breakout rooms are created by the meeting host on the platform. When invited, accept "
            "the prompt to join; use 'Leave room' to return to the main session."),
        "Optimizing your connection": (
            "Use a wired connection or sit near the router, close other video/streaming apps, and "
            "turn your camera off if the call becomes choppy."),
    }

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t(f'{_V}.windows.virtual_event_tech_support', default="Virtual Event Tech Support"))
        self.dialog.geometry("900x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t(f'{_V}.labels.virtual_event_tech_support', default="🛠️ Virtual Event Tech Support"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        ttk.Button(main_frame, text=_t(f'{_V}.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='bottom')

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        troubleshoot_tab = ttk.Frame(notebook)
        notebook.add(troubleshoot_tab, text=_t(f'{_V}.tabs.troubleshooting', default="Troubleshooting"))

        issues = [
            ("Cannot connect to meeting", "Check internet connection\nVerify meeting link\nTry different browser"),
            ("No audio/video", "Check microphone/camera permissions\nRestart browser\nUpdate drivers"),
            ("Poor connection quality", "Close other applications\nMove closer to router\nLower video quality"),
            ("Cannot share screen", "Grant screen sharing permission\nRestart application\nCheck firewall settings")
        ]

        for issue, solution in issues:
            frame = ttk.LabelFrame(troubleshoot_tab, text=issue)
            frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(frame, text=solution, justify='left').pack(padx=10, pady=5, anchor='w')

        test_tab = ttk.Frame(notebook)
        notebook.add(test_tab, text=_t(f'{_V}.tabs.connection_test', default="Connection Test"))

        ttk.Label(test_tab, text=_t(f'{_V}.labels.run_system_check', default="Run System Check"), font=('Arial', 12, 'bold')).pack(pady=15)
        ttk.Button(test_tab, text=_t(f'{_V}.buttons.test_connection', default="Test Connection"), command=self.test_connection).pack(pady=5)
        ttk.Button(test_tab, text=_t(f'{_V}.buttons.test_camera_microphone', default="Test Camera/Microphone"), command=self.test_devices).pack(pady=5)
        ttk.Button(test_tab, text=_t(f'{_V}.buttons.test_screen_sharing', default="Test Screen Sharing"), command=self.test_screen).pack(pady=5)
        self.test_result = ttk.Label(test_tab, text="", justify='left')
        self.test_result.pack(pady=10)

        tutorials_tab = ttk.Frame(notebook)
        notebook.add(tutorials_tab, text=_t(f'{_V}.tabs.tutorials', default="Tutorials"))

        for tutorial in self.TUTORIALS:
            ttk.Button(tutorials_tab, text=tutorial, command=lambda t=tutorial: self.show_tutorial(t)).pack(fill='x', padx=10, pady=3)

    def test_connection(self):
        """Time a real TCP connection to the main meeting platforms (in a worker thread)."""
        self.test_result.config(text="Testing…")
        hosts = (("Zoom", "zoom.us"), ("Microsoft Teams", "teams.microsoft.com"), ("Google Meet", "meet.google.com"))

        def work():
            import socket
            import time
            lines = []
            for label, host in hosts:
                t0 = time.monotonic()
                try:
                    with socket.create_connection((host, 443), timeout=4):
                        lines.append(f"✓ {label}: reachable ({(time.monotonic() - t0) * 1000:.0f} ms)")
                except OSError as exc:
                    lines.append(f"✗ {label}: not reachable ({exc.__class__.__name__})")
            try:
                self.dialog.after(0, lambda: self._show_test("\n".join(lines)))
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _show_test(self, text):
        try:
            self.test_result.config(text=text)
        except tk.TclError:
            pass

    def test_devices(self):
        if messagebox.askyesno(_t(f'{_V}.dialogs.device_test', default="Device Test"),
                               "Camera and microphone can only be checked by the meeting app.\n\n"
                               "Open Zoom's test meeting (zoom.us/test) in your browser?", parent=self.dialog):
            su_records.open_target("https://zoom.us/test")

    def test_screen(self):
        messagebox.showinfo(_t(f'{_V}.dialogs.screen_share_test', default="Screen Share Test"),
                            "Screen sharing is granted by your operating system to the meeting app. "
                            "Join the test meeting (Test Camera/Microphone) and press Share to confirm it works.",
                            parent=self.dialog)

    def show_tutorial(self, tutorial_name):
        messagebox.showinfo(_t(f'{_V}.dialogs.tutorial', default="Tutorial"),
                            f"{tutorial_name}\n\n{self.TUTORIALS.get(tutorial_name, '')}", parent=self.dialog)


# ============================================================================
# KNOWLEDGE SHARING SESSIONS DIALOG
# ============================================================================


def open_virtual_events_dialog(self):
    """Open virtual events platform"""
    dialog = VirtualEventsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


