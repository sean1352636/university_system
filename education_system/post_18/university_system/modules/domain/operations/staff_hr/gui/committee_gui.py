"""
Committee Management GUI

Provides interface for:
- Committee membership viewing
- Meeting scheduling and agenda management
- Minutes recording
- Voting and ballots
- Committee administration
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.committee_manager import CommitteeManager
from education_system.post_18.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, show_validation_error
)


class CommitteeGUI:
    """GUI for committee management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Committee Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        """Get user ID from current user dict."""
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Committees")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Committee Management")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_committees_tab()
        self._create_meetings_tab()
        self._create_minutes_tab()
        self._create_voting_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_admin_tab()

    # ==================== TAB 1: MY COMMITTEES ====================

    def _create_my_committees_tab(self):
        """Create my committees tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Committees")

        # Header with Refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Committees", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_committees).pack(side=tk.RIGHT, padx=5)

        # Committees treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Name', 'Type', 'Role', 'Status')
        self.committees_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.committees_tree.yview)

        widths = {'ID': 50, 'Name': 250, 'Type': 120, 'Role': 120, 'Status': 100}
        for col in columns:
            self.committees_tree.heading(col, text=col)
            self.committees_tree.column(col, width=widths.get(col, 100))

        self.committees_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.committees_tree.tag_configure('active', background='#d4edda')
        self.committees_tree.tag_configure('inactive', background='#f8d7da')
        self.committees_tree.tag_configure('dissolved', background='#e2e3e5')

        # Double-click to view members
        self.committees_tree.bind('<Double-1>', self._view_committee_members)

        self._load_my_committees()

    def _load_my_committees(self):
        """Load user's committee memberships."""
        for item in self.committees_tree.get_children():
            self.committees_tree.delete(item)

        try:
            committees = CommitteeManager.get_committees()
        except Exception:
            committees = []

        user_id = self._get_user_id()

        for c in committees:
            committee_id = c.get('id')
            try:
                members = CommitteeManager.get_committee_members(committee_id)
            except Exception:
                members = []

            # Find current user's membership
            user_role = None
            for m in members:
                if str(m.get('user_id')) == str(user_id):
                    user_role = m.get('role', 'member')
                    break

            if user_role is None:
                continue

            status = c.get('status', 'active').lower()
            display_type = c.get('committee_type', '').replace('_', ' ').title()
            display_role = user_role.replace('_', ' ').title()
            display_status = status.replace('_', ' ').title()

            self.committees_tree.insert('', tk.END, values=(
                committee_id,
                c.get('name', ''),
                display_type,
                display_role,
                display_status
            ), tags=(status,))

    def _view_committee_members(self, event):
        """View committee members in a popup dialog."""
        selection = self.committees_tree.selection()
        if not selection:
            return

        item = self.committees_tree.item(selection[0])
        committee_id = item['values'][0]
        committee_name = item['values'][1]

        try:
            members = CommitteeManager.get_committee_members(committee_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load committee members: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Members - {committee_name}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        # Header
        header_frame = ttk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=f"Members of {committee_name}",
                  font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        # Members treeview
        tree_frame = ttk.Frame(dialog)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        mem_columns = ('User ID', 'Role', 'Joined')
        members_tree = ttk.Treeview(
            tree_frame, columns=mem_columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=members_tree.yview)

        mem_widths = {'User ID': 150, 'Role': 120, 'Joined': 150}
        for col in mem_columns:
            members_tree.heading(col, text=col)
            members_tree.column(col, width=mem_widths.get(col, 100))

        members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for m in members:
            members_tree.insert('', tk.END, values=(
                m.get('user_id', ''),
                m.get('role', '').replace('_', ' ').title(),
                m.get('joined_at', '')
            ))

        # Close button
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 2: MEETINGS ====================

    def _create_meetings_tab(self):
        """Create meetings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Meetings")

        # Header with committee filter
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Meetings", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Committee:").pack(side=tk.LEFT, padx=5)
        self.meetings_committee_filter = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.meetings_committee_filter.pack(side=tk.LEFT, padx=5)
        self.meetings_committee_filter.bind('<<ComboboxSelected>>', lambda e: self._load_meetings())
        ttk.Button(filter_frame, text="Refresh", command=self._refresh_meetings).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Schedule Meeting",
                   command=self._schedule_meeting_dialog).pack(side=tk.LEFT, padx=5)

        # Store committee mapping for filter
        self.meetings_committee_map = {}

        # Meetings treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Committee', 'Title', 'Date', 'Time', 'Location', 'Status')
        self.meetings_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.meetings_tree.yview)

        widths = {'ID': 50, 'Committee': 150, 'Title': 200, 'Date': 100,
                  'Time': 100, 'Location': 150, 'Status': 100}
        for col in columns:
            self.meetings_tree.heading(col, text=col)
            self.meetings_tree.column(col, width=widths.get(col, 100))

        self.meetings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.meetings_tree.tag_configure('scheduled', background='#cce5ff')
        self.meetings_tree.tag_configure('in_progress', background='#fff3cd')
        self.meetings_tree.tag_configure('completed', background='#d4edda')
        self.meetings_tree.tag_configure('cancelled', background='#f8d7da')

        # Double-click to view meeting detail
        self.meetings_tree.bind('<Double-1>', self._view_meeting_details)

        self._refresh_meetings()

    def _load_meeting_committee_filter(self):
        """Load committees into the meetings filter combobox."""
        self.meetings_committee_map = {}

        try:
            committees = CommitteeManager.get_committees()
        except Exception:
            committees = []

        display_values = ['All']
        self.meetings_committee_map['All'] = None
        for c in committees:
            label = f"{c.get('name', '')} (#{c.get('id')})"
            display_values.append(label)
            self.meetings_committee_map[label] = c.get('id')

        self.meetings_committee_filter['values'] = display_values
        if not self.meetings_committee_filter.get():
            self.meetings_committee_filter.set('All')

    def _refresh_meetings(self):
        """Refresh committee filter list and reload meetings."""
        self._load_meeting_committee_filter()
        self._load_meetings()

    def _load_meetings(self):
        """Load meetings based on filter."""
        for item in self.meetings_tree.get_children():
            self.meetings_tree.delete(item)

        selected = self.meetings_committee_filter.get()
        committee_id = self.meetings_committee_map.get(selected)

        try:
            meetings = CommitteeManager.get_meetings(committee_id=committee_id)
        except Exception:
            meetings = []

        # Build committee name cache
        committee_names = {}
        try:
            all_committees = CommitteeManager.get_committees()
            for c in all_committees:
                committee_names[c.get('id')] = c.get('name', '')
        except Exception:
            pass

        for m in meetings:
            status = m.get('status', '').lower()
            display_status = status.replace('_', ' ').title()
            start_time = m.get('start_time', '')
            end_time = m.get('end_time', '')
            time_display = start_time
            if end_time:
                time_display = f"{start_time} - {end_time}"

            c_id = m.get('committee_id')
            committee_name = committee_names.get(c_id, str(c_id))

            self.meetings_tree.insert('', tk.END, values=(
                m.get('id'),
                committee_name,
                m.get('title', '')[:40],
                m.get('meeting_date', ''),
                time_display,
                m.get('location', '') or m.get('virtual_link', '') or '',
                display_status
            ), tags=(status,))

    def _schedule_meeting_dialog(self):
        """Open dialog to schedule a new meeting."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Schedule Meeting")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Committee selector
        ttk.Label(frame, text="Committee:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        committee_combo = ttk.Combobox(frame, width=30, state='readonly')
        committee_combo.grid(row=0, column=1, padx=10, pady=8)

        committee_map = {}
        try:
            committees = CommitteeManager.get_committees()
        except Exception:
            committees = []

        combo_values = []
        for c in committees:
            label = f"{c.get('name', '')} (#{c.get('id')})"
            combo_values.append(label)
            committee_map[label] = c.get('id')
        committee_combo['values'] = combo_values
        if combo_values:
            committee_combo.current(0)

        # Title
        ttk.Label(frame, text="Title:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=35)
        title_entry.grid(row=1, column=1, padx=10, pady=8)

        # Date
        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Start time
        ttk.Label(frame, text="Start Time:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        start_time_entry = ttk.Entry(frame, width=15)
        start_time_entry.insert(0, "09:00")
        start_time_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # End time
        ttk.Label(frame, text="End Time:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        end_time_entry = ttk.Entry(frame, width=15)
        end_time_entry.insert(0, "10:00")
        end_time_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Location
        ttk.Label(frame, text="Location:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        location_entry = ttk.Entry(frame, width=35)
        location_entry.grid(row=5, column=1, padx=10, pady=8)

        # Virtual link
        ttk.Label(frame, text="Virtual Link:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        virtual_link_entry = ttk.Entry(frame, width=35)
        virtual_link_entry.grid(row=6, column=1, padx=10, pady=8)

        def save():
            # Validate committee selection
            try:
                committee_label = validate_combobox(committee_combo, "Committee")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_committee_id = committee_map.get(committee_label)
            if not selected_committee_id:
                messagebox.showerror("Error", "Please select a valid committee.", parent=dialog)
                return

            # Validate required fields
            try:
                title = validate_entry(title_entry, "Title")
                meeting_date = validate_date_entry(date_entry, "Date")
                start_time = validate_entry(start_time_entry, "Start Time")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            end_time = end_time_entry.get().strip() or None
            location = location_entry.get().strip() or None
            virtual_link = virtual_link_entry.get().strip() or None

            try:
                meeting_id = CommitteeManager.schedule_meeting(
                    committee_id=selected_committee_id,
                    title=title,
                    meeting_date=meeting_date,
                    start_time=start_time,
                    end_time=end_time,
                    location=location,
                    virtual_link=virtual_link,
                    created_by=self._get_user_id()
                )
                messagebox.showinfo("Success",
                                    f"Meeting scheduled. ID: {meeting_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_meetings()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Schedule", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _view_meeting_details(self, event):
        """View meeting details and agenda in a popup dialog."""
        selection = self.meetings_tree.selection()
        if not selection:
            return

        item = self.meetings_tree.item(selection[0])
        meeting_id = item['values'][0]

        try:
            meeting = CommitteeManager.get_meeting(meeting_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load meeting details: {e}")
            return

        if not meeting:
            messagebox.showerror("Error", "Meeting not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Meeting #{meeting_id} - {meeting.get('title', '')}")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        # Scrollable content
        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Meeting details
        details_frame = ttk.LabelFrame(scroll_frame, text="Meeting Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Meeting ID', meeting.get('id')),
            ('Title', meeting.get('title', '')),
            ('Date', meeting.get('meeting_date', '')),
            ('Start Time', meeting.get('start_time', '')),
            ('End Time', meeting.get('end_time', '') or 'N/A'),
            ('Location', meeting.get('location', '') or 'N/A'),
            ('Virtual Link', meeting.get('virtual_link', '') or 'N/A'),
            ('Status', meeting.get('status', '').replace('_', ' ').title()),
            ('Created', meeting.get('created_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Agenda items
        agenda_frame = ttk.LabelFrame(scroll_frame, text="Agenda", padding=10)
        agenda_frame.pack(fill=tk.X, padx=10, pady=10)

        try:
            agenda_items = CommitteeManager.get_agenda(meeting_id)
        except Exception:
            agenda_items = []

        if agenda_items:
            agenda_cols = ('Order', 'Title', 'Type', 'Presenter', 'Duration')
            agenda_tree = ttk.Treeview(agenda_frame, columns=agenda_cols, show='headings', height=6)

            agenda_widths = {'Order': 50, 'Title': 200, 'Type': 100, 'Presenter': 120, 'Duration': 80}
            for col in agenda_cols:
                agenda_tree.heading(col, text=col)
                agenda_tree.column(col, width=agenda_widths.get(col, 100))

            for a in agenda_items:
                agenda_tree.insert('', tk.END, values=(
                    a.get('item_order', ''),
                    a.get('title', ''),
                    a.get('item_type', '').replace('_', ' ').title(),
                    a.get('presenter_id', '') or 'N/A',
                    f"{a.get('duration_minutes', 15)} min"
                ))
            agenda_tree.pack(fill=tk.X)
        else:
            ttk.Label(agenda_frame, text="No agenda items yet.").pack(anchor='w')

        # Add Agenda Item button
        agenda_btn_frame = ttk.Frame(agenda_frame)
        agenda_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(agenda_btn_frame, text="Add Agenda Item",
                   command=lambda: self._add_agenda_item_dialog(meeting_id, dialog)).pack(side=tk.LEFT, padx=5)

        # Close button
        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _add_agenda_item_dialog(self, meeting_id, parent_dialog=None):
        """Open dialog to add an agenda item to a meeting."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Agenda Item")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=30)
        title_entry.grid(row=0, column=1, padx=10, pady=8)

        # Type
        ttk.Label(frame, text="Type:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['discussion', 'decision', 'information', 'action'],
            width=20, state='readonly'
        )
        type_combo.set('discussion')
        type_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Presenter
        ttk.Label(frame, text="Presenter:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        presenter_entry = ttk.Entry(frame, width=25)
        presenter_entry.grid(row=2, column=1, padx=10, pady=8)

        # Duration
        ttk.Label(frame, text="Duration (min):").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        duration_entry = ttk.Entry(frame, width=10)
        duration_entry.insert(0, "15")
        duration_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                title = validate_entry(title_entry, "Title")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                item_type = validate_combobox(type_combo, "Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            presenter = presenter_entry.get().strip() or None

            # Parse duration
            duration_str = duration_entry.get().strip()
            try:
                duration = int(duration_str)
                if duration < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "Duration must be a positive integer.", parent=dialog)
                return

            # Determine next item order
            try:
                existing_items = CommitteeManager.get_agenda(meeting_id)
                item_order = len(existing_items) + 1
            except Exception:
                item_order = 1

            try:
                item_id = CommitteeManager.add_agenda_item(
                    meeting_id=meeting_id,
                    title=title,
                    item_order=item_order,
                    item_type=item_type,
                    presenter_id=presenter,
                    duration_minutes=duration
                )
                messagebox.showinfo("Success",
                                    f"Agenda item added. ID: {item_id}",
                                    parent=dialog)
                dialog.destroy()
                # Refresh parent meeting detail dialog if open
                if parent_dialog and parent_dialog.winfo_exists():
                    parent_dialog.destroy()
                    # Re-open the meeting details by simulating the view
                    self._open_meeting_detail_by_id(meeting_id)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _open_meeting_detail_by_id(self, meeting_id):
        """Open meeting detail dialog directly by meeting ID."""
        try:
            meeting = CommitteeManager.get_meeting(meeting_id)
        except Exception:
            return

        if not meeting:
            return

        # Create a fake event-like flow by directly opening the dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Meeting #{meeting_id} - {meeting.get('title', '')}")
        dialog.geometry("700x600")
        dialog.transient(self.root)

        canvas = tk.Canvas(dialog)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        details_frame = ttk.LabelFrame(scroll_frame, text="Meeting Details", padding=15)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        fields = [
            ('Meeting ID', meeting.get('id')),
            ('Title', meeting.get('title', '')),
            ('Date', meeting.get('meeting_date', '')),
            ('Start Time', meeting.get('start_time', '')),
            ('End Time', meeting.get('end_time', '') or 'N/A'),
            ('Location', meeting.get('location', '') or 'N/A'),
            ('Virtual Link', meeting.get('virtual_link', '') or 'N/A'),
            ('Status', meeting.get('status', '').replace('_', ' ').title()),
            ('Created', meeting.get('created_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=400).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        agenda_frame = ttk.LabelFrame(scroll_frame, text="Agenda", padding=10)
        agenda_frame.pack(fill=tk.X, padx=10, pady=10)

        try:
            agenda_items = CommitteeManager.get_agenda(meeting_id)
        except Exception:
            agenda_items = []

        if agenda_items:
            agenda_cols = ('Order', 'Title', 'Type', 'Presenter', 'Duration')
            agenda_tree = ttk.Treeview(agenda_frame, columns=agenda_cols, show='headings', height=6)

            agenda_widths = {'Order': 50, 'Title': 200, 'Type': 100, 'Presenter': 120, 'Duration': 80}
            for col in agenda_cols:
                agenda_tree.heading(col, text=col)
                agenda_tree.column(col, width=agenda_widths.get(col, 100))

            for a in agenda_items:
                agenda_tree.insert('', tk.END, values=(
                    a.get('item_order', ''),
                    a.get('title', ''),
                    a.get('item_type', '').replace('_', ' ').title(),
                    a.get('presenter_id', '') or 'N/A',
                    f"{a.get('duration_minutes', 15)} min"
                ))
            agenda_tree.pack(fill=tk.X)
        else:
            ttk.Label(agenda_frame, text="No agenda items yet.").pack(anchor='w')

        agenda_btn_frame = ttk.Frame(agenda_frame)
        agenda_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(agenda_btn_frame, text="Add Agenda Item",
                   command=lambda: self._add_agenda_item_dialog(meeting_id, dialog)).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(scroll_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 3: MINUTES ====================

    def _create_minutes_tab(self):
        """Create minutes tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Minutes")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Meeting Minutes", style='Header.TLabel').pack(side=tk.LEFT)

        # Meeting selector
        selector_frame = ttk.LabelFrame(tab, text="Select Meeting", padding=10)
        selector_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selector_frame, text="Meeting:").pack(side=tk.LEFT, padx=5)
        self.minutes_meeting_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.minutes_meeting_combo.pack(side=tk.LEFT, padx=5)
        self.minutes_meeting_combo.bind('<<ComboboxSelected>>', lambda e: self._load_minutes())
        ttk.Button(selector_frame, text="Refresh List",
                   command=self._load_minutes_meetings).pack(side=tk.LEFT, padx=10)

        # Store meeting mapping
        self.minutes_meeting_map = {}

        # Minutes status label
        self.minutes_status_label = ttk.Label(tab, text="", font=('Arial', 10))
        self.minutes_status_label.pack(fill=tk.X, padx=10, pady=(0, 5))

        # Minutes content area
        content_frame = ttk.LabelFrame(tab, text="Minutes Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.minutes_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, width=80, height=20)
        self.minutes_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Record Minutes",
                   command=self._record_minutes).pack(side=tk.LEFT, padx=5)

        # Approve button (admin only)
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            ttk.Button(btn_frame, text="Approve",
                       command=self._approve_minutes).pack(side=tk.LEFT, padx=5)

        # Store current minute ID for approval
        self.current_minute_id = None

        # Load initial meeting list
        self._load_minutes_meetings()

    def _load_minutes_meetings(self):
        """Load meetings into the minutes meeting selector."""
        self.minutes_meeting_map = {}

        try:
            meetings = CommitteeManager.get_meetings()
        except Exception:
            meetings = []

        # Build committee name cache
        committee_names = {}
        try:
            all_committees = CommitteeManager.get_committees()
            for c in all_committees:
                committee_names[c.get('id')] = c.get('name', '')
        except Exception:
            pass

        display_values = []
        for m in meetings:
            c_id = m.get('committee_id')
            committee_name = committee_names.get(c_id, str(c_id))
            label = f"#{m.get('id')} - {committee_name}: {m.get('title', '')[:30]} ({m.get('meeting_date', '')})"
            display_values.append(label)
            self.minutes_meeting_map[label] = m.get('id')

        self.minutes_meeting_combo['values'] = display_values
        if display_values:
            self.minutes_meeting_combo.set(display_values[0])
            self._load_minutes()
        else:
            self.minutes_meeting_combo.set('')
            self.minutes_text.delete("1.0", tk.END)
            self.minutes_status_label.config(text="")
            self.current_minute_id = None

    def _get_selected_minutes_meeting_id(self):
        """Get the meeting ID from the minutes meeting combo selection."""
        selected = self.minutes_meeting_combo.get()
        return self.minutes_meeting_map.get(selected)

    def _load_minutes(self):
        """Load minutes for the selected meeting."""
        self.minutes_text.delete("1.0", tk.END)
        self.current_minute_id = None
        self.minutes_status_label.config(text="")

        meeting_id = self._get_selected_minutes_meeting_id()
        if not meeting_id:
            return

        try:
            minutes_list = CommitteeManager.get_minutes(meeting_id)
        except Exception:
            minutes_list = []

        if minutes_list:
            # Show the most recent minutes entry
            latest = minutes_list[-1]
            content = latest.get('content', '')
            status = latest.get('status', 'draft').replace('_', ' ').title()
            recorded_by = latest.get('recorded_by', 'Unknown')
            created_at = latest.get('created_at', '')
            self.current_minute_id = latest.get('id')

            self.minutes_text.insert("1.0", content)
            self.minutes_status_label.config(
                text=f"Status: {status} | Recorded by: {recorded_by} | Created: {created_at}"
            )
        else:
            self.minutes_status_label.config(text="No minutes recorded for this meeting yet.")

    def _record_minutes(self):
        """Record or update minutes for the selected meeting."""
        meeting_id = self._get_selected_minutes_meeting_id()
        if not meeting_id:
            messagebox.showinfo("Info", "Please select a meeting first.")
            return

        content = self.minutes_text.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showerror("Validation Error", "Minutes content cannot be empty.")
            return

        try:
            minute_id = CommitteeManager.record_minutes(
                meeting_id=meeting_id,
                content=content,
                recorded_by=self._get_user_id()
            )
            messagebox.showinfo("Success", f"Minutes recorded. ID: {minute_id}")
            self._load_minutes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _approve_minutes(self):
        """Approve the currently displayed minutes."""
        if not self.current_minute_id:
            messagebox.showinfo("Info", "No minutes to approve. Please select a meeting with recorded minutes.")
            return

        if not messagebox.askyesno("Confirm", "Approve these minutes?"):
            return

        try:
            CommitteeManager.approve_minutes(
                minute_id=self.current_minute_id,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Minutes approved.")
            self._load_minutes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: VOTING ====================

    def _create_voting_tab(self):
        """Create voting tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Voting")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Open Votes", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_votes).pack(side=tk.RIGHT, padx=5)

        # Votes treeview (top pane)
        top_frame = ttk.Frame(tab)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        y_scroll = ttk.Scrollbar(top_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Type', 'Secret Ballot', 'Status')
        self.votes_tree = ttk.Treeview(
            top_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set, height=8)
        y_scroll.config(command=self.votes_tree.yview)

        widths = {'ID': 50, 'Title': 250, 'Type': 130, 'Secret Ballot': 100, 'Status': 100}
        for col in columns:
            self.votes_tree.heading(col, text=col)
            self.votes_tree.column(col, width=widths.get(col, 100))

        self.votes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.votes_tree.tag_configure('open', background='#fff3cd')
        self.votes_tree.tag_configure('closed', background='#e2e3e5')

        # Select event to show detail panel
        self.votes_tree.bind('<<TreeviewSelect>>', self._on_vote_selected)

        # Detail panel (bottom pane)
        self.vote_detail_frame = ttk.LabelFrame(tab, text="Vote Details", padding=10)
        self.vote_detail_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        # Description
        self.vote_desc_label = ttk.Label(self.vote_detail_frame, text="Select a vote to see details.",
                                         wraplength=700)
        self.vote_desc_label.pack(anchor='w', padx=5, pady=5)

        # Voting controls
        vote_controls_frame = ttk.Frame(self.vote_detail_frame)
        vote_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        self.vote_choice_var = tk.StringVar(value='for')
        ttk.Radiobutton(vote_controls_frame, text="For", variable=self.vote_choice_var,
                        value='for').pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(vote_controls_frame, text="Against", variable=self.vote_choice_var,
                        value='against').pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(vote_controls_frame, text="Abstain", variable=self.vote_choice_var,
                        value='abstain').pack(side=tk.LEFT, padx=10)

        # Action buttons
        vote_btn_frame = ttk.Frame(self.vote_detail_frame)
        vote_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(vote_btn_frame, text="Cast Vote",
                   command=self._cast_vote).pack(side=tk.LEFT, padx=5)
        ttk.Button(vote_btn_frame, text="View Results",
                   command=self._view_vote_results).pack(side=tk.LEFT, padx=5)

        # Store vote data cache
        self._votes_cache = {}

        self._load_votes()

    def _load_votes(self):
        """Load all votes across all meetings."""
        for item in self.votes_tree.get_children():
            self.votes_tree.delete(item)

        self._votes_cache = {}

        # Retrieve all meetings and their votes
        try:
            meetings = CommitteeManager.get_meetings()
        except Exception:
            meetings = []

        all_votes = []
        for m in meetings:
            try:
                votes = CommitteeManager.get_meeting_votes(m.get('id'))
                all_votes.extend(votes)
            except Exception:
                pass

        for v in all_votes:
            vote_id = v.get('id')
            status = v.get('status', '').lower()
            display_type = v.get('vote_type', '').replace('_', ' ').title()
            is_secret = 'Yes' if v.get('is_secret_ballot') else 'No'
            display_status = status.replace('_', ' ').title()

            self.votes_tree.insert('', tk.END, values=(
                vote_id,
                v.get('title', '')[:50],
                display_type,
                is_secret,
                display_status
            ), tags=(status,))

            self._votes_cache[vote_id] = v

        # Reset detail panel
        self.vote_desc_label.config(text="Select a vote to see details.")

    def _on_vote_selected(self, event):
        """Update detail panel when a vote is selected."""
        selection = self.votes_tree.selection()
        if not selection:
            return

        item = self.votes_tree.item(selection[0])
        vote_id = item['values'][0]

        vote = self._votes_cache.get(vote_id, {})
        description = vote.get('description', '') or 'No description provided.'
        title = vote.get('title', '')
        vote_type = vote.get('vote_type', '').replace('_', ' ').title()
        status = vote.get('status', '').replace('_', ' ').title()

        detail_text = (
            f"Title: {title}\n"
            f"Type: {vote_type}\n"
            f"Status: {status}\n\n"
            f"Description: {description}"
        )
        self.vote_desc_label.config(text=detail_text)

    def _cast_vote(self):
        """Cast a vote on the selected vote item."""
        selection = self.votes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a vote first.")
            return

        item = self.votes_tree.item(selection[0])
        vote_id = item['values'][0]
        vote_status = item['values'][4]

        if vote_status.lower() != 'open':
            messagebox.showinfo("Info", "This vote is no longer open.")
            return

        choice = self.vote_choice_var.get()

        if not messagebox.askyesno("Confirm",
                                    f"Cast your vote as '{choice.title()}'?"):
            return

        try:
            CommitteeManager.cast_ballot(
                vote_id=vote_id,
                voter_id=self._get_user_id(),
                choice=choice
            )
            messagebox.showinfo("Success", "Your vote has been cast.")
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _view_vote_results(self):
        """View results for the selected vote."""
        selection = self.votes_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a vote first.")
            return

        item = self.votes_tree.item(selection[0])
        vote_id = item['values'][0]

        try:
            results = CommitteeManager.get_vote_results(vote_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load vote results: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Vote Results - {results.get('title', '')}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Vote info
        info_frame = ttk.LabelFrame(frame, text="Vote Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        vote_type = results.get('vote_type', '').replace('_', ' ').title()
        status = results.get('status', '').replace('_', ' ').title()
        result = results.get('result', '').replace('_', ' ').title() if results.get('result') else 'Pending'
        is_secret = 'Yes' if results.get('is_secret_ballot') else 'No'

        info_fields = [
            ('Title', results.get('title', '')),
            ('Vote Type', vote_type),
            ('Secret Ballot', is_secret),
            ('Status', status),
            ('Result', result),
        ]

        for i, (label, value) in enumerate(info_fields):
            ttk.Label(info_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='e', padx=(10, 5), pady=3)
            ttk.Label(info_frame, text=str(value)).grid(
                row=i, column=1, sticky='w', padx=(5, 10), pady=3)

        # Tallies
        tally_frame = ttk.LabelFrame(frame, text="Tallies", padding=10)
        tally_frame.pack(fill=tk.X, pady=(0, 10))

        votes_for = results.get('votes_for', 0) or 0
        votes_against = results.get('votes_against', 0) or 0
        votes_abstain = results.get('votes_abstain', 0) or 0

        for key, label, color in [('for', 'For', '#28a745'), ('against', 'Against', '#dc3545'),
                                   ('abstain', 'Abstain', '#6c757d')]:
            count = {'for': votes_for, 'against': votes_against, 'abstain': votes_abstain}[key]
            row_frame = ttk.Frame(tally_frame)
            row_frame.pack(fill=tk.X, pady=3)
            ttk.Label(row_frame, text=f"{label}:", width=10).pack(side=tk.LEFT, padx=5)
            ttk.Label(row_frame, text=str(count), font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)

        # Individual ballots (only for non-secret ballots)
        ballots = results.get('ballots')
        if ballots is not None:
            ballots_frame = ttk.LabelFrame(frame, text="Individual Ballots", padding=10)
            ballots_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            ballot_cols = ('Voter', 'Choice', 'Cast At')
            ballot_tree = ttk.Treeview(ballots_frame, columns=ballot_cols, show='headings', height=6)

            for col in ballot_cols:
                ballot_tree.heading(col, text=col)
                ballot_tree.column(col, width=150)

            for b in ballots:
                ballot_tree.insert('', tk.END, values=(
                    b.get('voter_id', ''),
                    b.get('choice', '').title(),
                    b.get('cast_at', '')
                ))
            ballot_tree.pack(fill=tk.BOTH, expand=True)
        else:
            ttk.Label(frame, text="Secret ballot - individual votes are not displayed.",
                      font=('Arial', 9, 'italic')).pack(anchor='w', pady=5)

        # Close button
        ttk.Button(frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5, pady=10)

    # ==================== TAB 5: ADMIN ====================

    def _create_admin_tab(self):
        """Create admin tab for committee management (admin only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Admin")

        # Scrollable content
        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Committee CRUD Section ----
        crud_frame = ttk.LabelFrame(scroll_frame, text="Create Committee", padding=15)
        crud_frame.pack(fill=tk.X, padx=10, pady=10)

        # Name
        ttk.Label(crud_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_name_entry = ttk.Entry(crud_frame, width=35)
        self.admin_name_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(crud_frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        self.admin_desc_text = tk.Text(crud_frame, width=40, height=3)
        self.admin_desc_text.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(crud_frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_type_combo = ttk.Combobox(
            crud_frame, values=['standing', 'ad_hoc', 'advisory', 'task_force'],
            width=20, state='readonly'
        )
        self.admin_type_combo.set('standing')
        self.admin_type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(crud_frame, text="Department:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.admin_dept_entry = ttk.Entry(crud_frame, width=25)
        self.admin_dept_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Create button
        ttk.Button(crud_frame, text="Create Committee",
                   command=self._create_committee).grid(row=4, column=1, padx=10, pady=15, sticky='w')

        # ---- Members Management Section ----
        members_frame = ttk.LabelFrame(scroll_frame, text="Manage Members", padding=15)
        members_frame.pack(fill=tk.X, padx=10, pady=10)

        # Committee selector
        selector_row = ttk.Frame(members_frame)
        selector_row.pack(fill=tk.X, pady=5)
        ttk.Label(selector_row, text="Committee:").pack(side=tk.LEFT, padx=5)
        self.admin_committee_combo = ttk.Combobox(selector_row, width=35, state='readonly')
        self.admin_committee_combo.pack(side=tk.LEFT, padx=5)
        self.admin_committee_combo.bind('<<ComboboxSelected>>', lambda e: self._load_admin_members())
        ttk.Button(selector_row, text="Refresh",
                   command=self._refresh_admin_committees).pack(side=tk.LEFT, padx=5)

        # Store committee mapping for admin
        self.admin_committee_map = {}

        # Add member controls
        add_row = ttk.Frame(members_frame)
        add_row.pack(fill=tk.X, pady=10)
        ttk.Label(add_row, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.admin_user_id_entry = ttk.Entry(add_row, width=20)
        self.admin_user_id_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(add_row, text="Role:").pack(side=tk.LEFT, padx=5)
        self.admin_member_role_combo = ttk.Combobox(
            add_row, values=['chair', 'secretary', 'member'],
            width=12, state='readonly'
        )
        self.admin_member_role_combo.set('member')
        self.admin_member_role_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(add_row, text="Add Member",
                   command=self._add_member).pack(side=tk.LEFT, padx=5)
        ttk.Button(add_row, text="Remove Selected",
                   command=self._remove_member).pack(side=tk.LEFT, padx=5)

        # Members treeview
        tree_frame = ttk.Frame(members_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        mem_columns = ('User ID', 'Role', 'Joined')
        self.admin_members_tree = ttk.Treeview(
            tree_frame, columns=mem_columns, show='headings',
            yscrollcommand=y_scroll.set, height=8)
        y_scroll.config(command=self.admin_members_tree.yview)

        mem_widths = {'User ID': 200, 'Role': 120, 'Joined': 200}
        for col in mem_columns:
            self.admin_members_tree.heading(col, text=col)
            self.admin_members_tree.column(col, width=mem_widths.get(col, 100))

        self.admin_members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial committees for admin
        self._refresh_admin_committees()

    def _refresh_admin_committees(self):
        """Refresh the committee list in admin panel."""
        self.admin_committee_map = {}

        try:
            committees = CommitteeManager.get_committees()
        except Exception:
            committees = []

        display_values = []
        for c in committees:
            label = f"{c.get('name', '')} (#{c.get('id')})"
            display_values.append(label)
            self.admin_committee_map[label] = c.get('id')

        self.admin_committee_combo['values'] = display_values
        if display_values:
            self.admin_committee_combo.set(display_values[0])
            self._load_admin_members()
        else:
            self.admin_committee_combo.set('')
            for item in self.admin_members_tree.get_children():
                self.admin_members_tree.delete(item)

    def _get_admin_selected_committee_id(self):
        """Get the committee ID from the admin committee combo selection."""
        selected = self.admin_committee_combo.get()
        return self.admin_committee_map.get(selected)

    def _load_admin_members(self):
        """Load members for the selected committee in admin panel."""
        for item in self.admin_members_tree.get_children():
            self.admin_members_tree.delete(item)

        committee_id = self._get_admin_selected_committee_id()
        if not committee_id:
            return

        try:
            members = CommitteeManager.get_committee_members(committee_id)
        except Exception:
            members = []

        for m in members:
            self.admin_members_tree.insert('', tk.END, values=(
                m.get('user_id', ''),
                m.get('role', '').replace('_', ' ').title(),
                m.get('joined_at', '')
            ))

    def _create_committee(self):
        """Create a new committee from the admin form."""
        try:
            name = validate_entry(self.admin_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        description = self.admin_desc_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required.")
            return

        try:
            committee_type = validate_combobox(self.admin_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            department = validate_entry(self.admin_dept_entry, "Department")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        user_id = self._get_user_id()

        try:
            committee_id = CommitteeManager.create_committee(
                name=name,
                description=description,
                committee_type=committee_type,
                chair_id=user_id,
                department=department,
                created_by=user_id
            )
            messagebox.showinfo("Success", f"Committee created. ID: {committee_id}")
            # Clear form
            self.admin_name_entry.delete(0, tk.END)
            self.admin_desc_text.delete("1.0", tk.END)
            self.admin_type_combo.set('standing')
            self.admin_dept_entry.delete(0, tk.END)
            # Refresh admin committees and my committees
            self._refresh_admin_committees()
            self._load_my_committees()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_member(self):
        """Add a member to the selected committee."""
        committee_id = self._get_admin_selected_committee_id()
        if not committee_id:
            messagebox.showinfo("Info", "Please select a committee first.")
            return

        try:
            user_id = validate_entry(self.admin_user_id_entry, "User ID")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            role = validate_combobox(self.admin_member_role_combo, "Role")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            member_id = CommitteeManager.add_member(
                committee_id=committee_id,
                user_id=user_id,
                role=role
            )
            messagebox.showinfo("Success", f"Member added. ID: {member_id}")
            self.admin_user_id_entry.delete(0, tk.END)
            self._load_admin_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _remove_member(self):
        """Remove the selected member from the committee."""
        selection = self.admin_members_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a member to remove.")
            return

        committee_id = self._get_admin_selected_committee_id()
        if not committee_id:
            messagebox.showinfo("Info", "Please select a committee first.")
            return

        item = self.admin_members_tree.item(selection[0])
        user_id = item['values'][0]

        if not messagebox.askyesno("Confirm",
                                    f"Remove member '{user_id}' from this committee?"):
            return

        try:
            CommitteeManager.remove_member(
                committee_id=committee_id,
                user_id=str(user_id)
            )
            messagebox.showinfo("Success", "Member removed.")
            self._load_admin_members()
        except Exception as e:
            messagebox.showerror("Error", str(e))
