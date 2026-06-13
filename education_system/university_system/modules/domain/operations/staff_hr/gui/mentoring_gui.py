"""
Mentoring Programme GUI

Provides interface for:
- Viewing active mentoring relationships
- Session logging and tracking
- Goal setting and progress monitoring
- Finding and registering as mentors
- Programme administration
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.mentoring_manager import MentoringManager
from education_system.university_system.modules.domain.operations.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, validate_integer_entry, show_validation_error
)


class MentoringGUI:
    """GUI for mentoring programme management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Mentoring Management")
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
        notebook.add(self.tab_frame, text="Mentoring")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Mentoring Programme Management")
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

        self._create_my_mentoring_tab()
        self._create_sessions_tab()
        self._create_goals_tab()
        self._create_find_mentors_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_admin_tab()

    # ==================== TAB 1: MY MENTORING ====================

    def _create_my_mentoring_tab(self):
        """Create my mentoring relationships tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Mentoring")

        # Header with Refresh button
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Mentoring Relationships", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_mentoring).pack(side=tk.RIGHT, padx=5)

        # Mentoring treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Programme', 'Partner', 'Role', 'Status', 'Start Date')
        self.mentoring_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.mentoring_tree.yview)

        widths = {'ID': 50, 'Programme': 200, 'Partner': 150, 'Role': 100,
                  'Status': 100, 'Start Date': 120}
        for col in columns:
            self.mentoring_tree.heading(col, text=col)
            self.mentoring_tree.column(col, width=widths.get(col, 100))

        self.mentoring_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.mentoring_tree.tag_configure('active', background='#d4edda')
        self.mentoring_tree.tag_configure('proposed', background='#fff3cd')
        self.mentoring_tree.tag_configure('completed', background='#cce5ff')
        self.mentoring_tree.tag_configure('cancelled', background='#f8d7da')
        self.mentoring_tree.tag_configure('paused', background='#e2e3e5')

        # Double-click to view match detail
        self.mentoring_tree.bind('<Double-1>', self._view_match_detail)

        # Cache for programme names and match data
        self._programme_cache = {}
        self._match_cache = {}

        self._load_my_mentoring()

    def _load_programme_cache(self):
        """Load programme names into cache."""
        self._programme_cache = {}
        try:
            programmes = MentoringManager.get_programmes()
            for p in programmes:
                pid = p.get('programme_id') or p.get('id')
                self._programme_cache[pid] = p.get('name', '')
        except Exception:
            pass

    def _load_my_mentoring(self):
        """Load user's mentoring relationships."""
        for item in self.mentoring_tree.get_children():
            self.mentoring_tree.delete(item)

        self._load_programme_cache()
        self._match_cache = {}

        user_id = self._get_user_id()

        try:
            matches = MentoringManager.get_user_matches(user_id)
        except Exception:
            matches = []

        for m in matches:
            match_id = m.get('match_id') or m.get('id')
            programme_id = m.get('programme_id')
            programme_name = self._programme_cache.get(programme_id, str(programme_id))

            # Determine role and partner
            mentor_id_val = m.get('mentor_id')
            mentee_user_id = m.get('mentee_user_id') or m.get('mentee_id')

            # Check if user is the mentee
            if str(mentee_user_id) == str(user_id):
                role = 'Mentee'
                # Partner is the mentor - try to get the mentor's user_id
                try:
                    mentor_record = MentoringManager.get_mentor(mentor_id_val)
                    partner = mentor_record.get('user_id', str(mentor_id_val)) if mentor_record else str(mentor_id_val)
                except Exception:
                    partner = str(mentor_id_val)
            else:
                role = 'Mentor'
                partner = str(mentee_user_id)

            status = m.get('status', '').lower()
            display_status = status.replace('_', ' ').title()
            start_date = m.get('start_date', '') or ''

            self.mentoring_tree.insert('', tk.END, values=(
                match_id,
                programme_name,
                partner,
                role,
                display_status,
                start_date
            ), tags=(status,))

            self._match_cache[match_id] = m

    def _view_match_detail(self, event):
        """View match detail in a popup dialog."""
        selection = self.mentoring_tree.selection()
        if not selection:
            return

        item = self.mentoring_tree.item(selection[0])
        match_id = item['values'][0]

        try:
            match = MentoringManager.get_match(match_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load match details: {e}")
            return

        if not match:
            messagebox.showerror("Error", "Match not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Mentoring Match #{match_id}")
        dialog.geometry("550x450")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Match details
        details_frame = ttk.LabelFrame(frame, text="Match Details", padding=15)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        programme_id = match.get('programme_id')
        programme_name = self._programme_cache.get(programme_id, str(programme_id))

        # Resolve mentor user_id
        mentor_id_val = match.get('mentor_id')
        try:
            mentor_record = MentoringManager.get_mentor(mentor_id_val)
            mentor_display = mentor_record.get('user_id', str(mentor_id_val)) if mentor_record else str(mentor_id_val)
        except Exception:
            mentor_display = str(mentor_id_val)

        mentee_display = match.get('mentee_user_id') or match.get('mentee_id', '')

        fields = [
            ('Match ID', match.get('match_id') or match.get('id')),
            ('Programme', programme_name),
            ('Mentor', mentor_display),
            ('Mentee', mentee_display),
            ('Status', match.get('status', '').replace('_', ' ').title()),
            ('Start Date', match.get('start_date', '') or 'N/A'),
            ('Match Reason', match.get('match_reason', '') or 'N/A'),
            ('Matched By', match.get('matched_by', '') or match.get('created_by', '') or 'N/A'),
            ('Created', match.get('created_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=300).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Close button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    # ==================== TAB 2: SESSIONS ====================

    def _create_sessions_tab(self):
        """Create sessions tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sessions")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Mentoring Sessions", style='Header.TLabel').pack(side=tk.LEFT)

        # Match selector
        selector_frame = ttk.Frame(tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(selector_frame, text="Match:").pack(side=tk.LEFT, padx=5)
        self.sessions_match_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.sessions_match_combo.pack(side=tk.LEFT, padx=5)
        self.sessions_match_combo.bind('<<ComboboxSelected>>', lambda e: self._load_sessions())

        ttk.Button(selector_frame, text="Refresh",
                   command=self._refresh_sessions).pack(side=tk.LEFT, padx=5)

        # Store match mapping
        self.sessions_match_map = {}

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Log Session",
                   command=self._log_session_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Complete Session",
                   command=self._complete_session).pack(side=tk.LEFT, padx=5)

        # Sessions treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Date', 'Duration', 'Type', 'Status')
        self.sessions_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.sessions_tree.yview)

        widths = {'ID': 50, 'Date': 120, 'Duration': 100, 'Type': 150, 'Status': 100}
        for col in columns:
            self.sessions_tree.heading(col, text=col)
            self.sessions_tree.column(col, width=widths.get(col, 100))

        self.sessions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.sessions_tree.tag_configure('completed', background='#d4edda')
        self.sessions_tree.tag_configure('scheduled', background='#cce5ff')
        self.sessions_tree.tag_configure('cancelled', background='#f8d7da')
        self.sessions_tree.tag_configure('in_progress', background='#fff3cd')

        self._refresh_sessions()

    def _load_sessions_match_filter(self):
        """Load user's matches into the sessions match combobox."""
        self.sessions_match_map = {}

        user_id = self._get_user_id()
        try:
            matches = MentoringManager.get_user_matches(user_id)
        except Exception:
            matches = []

        self._load_programme_cache()

        display_values = []
        for m in matches:
            match_id = m.get('match_id') or m.get('id')
            programme_id = m.get('programme_id')
            programme_name = self._programme_cache.get(programme_id, str(programme_id))
            mentee = m.get('mentee_user_id') or m.get('mentee_id', '')
            status = m.get('status', '')
            label = f"#{match_id} - {programme_name} (Mentee: {mentee}) [{status}]"
            display_values.append(label)
            self.sessions_match_map[label] = match_id

        self.sessions_match_combo['values'] = display_values
        if display_values:
            self.sessions_match_combo.set(display_values[0])

    def _refresh_sessions(self):
        """Refresh match filter and reload sessions."""
        self._load_sessions_match_filter()
        self._load_sessions()

    def _get_selected_sessions_match_id(self):
        """Get the match ID from the sessions match combo selection."""
        selected = self.sessions_match_combo.get()
        return self.sessions_match_map.get(selected)

    def _load_sessions(self):
        """Load sessions for the selected match."""
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)

        match_id = self._get_selected_sessions_match_id()
        if not match_id:
            return

        try:
            sessions = MentoringManager.get_sessions(match_id)
        except Exception:
            sessions = []

        for s in sessions:
            session_id = s.get('session_id') or s.get('id')
            status = s.get('status', '').lower()
            display_type = s.get('session_type', '').replace('_', ' ').title()
            display_status = status.replace('_', ' ').title()
            duration = s.get('duration_minutes', '')
            duration_display = f"{duration} min" if duration else ''

            self.sessions_tree.insert('', tk.END, values=(
                session_id,
                s.get('session_date', ''),
                duration_display,
                display_type,
                display_status
            ), tags=(status,))

    def _log_session_dialog(self):
        """Open dialog to log a new mentoring session."""
        match_id = self._get_selected_sessions_match_id()
        if not match_id:
            messagebox.showinfo("Info", "Please select a match first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Log Mentoring Session")
        dialog.geometry("500x520")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Date
        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        # Duration
        ttk.Label(frame, text="Duration (min):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        duration_entry = ttk.Entry(frame, width=10)
        duration_entry.insert(0, "60")
        duration_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        type_combo = ttk.Combobox(
            frame, values=['one_on_one', 'group', 'virtual', 'workshop'],
            width=20, state='readonly'
        )
        type_combo.set('one_on_one')
        type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Location
        ttk.Label(frame, text="Location:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        location_entry = ttk.Entry(frame, width=35)
        location_entry.grid(row=3, column=1, padx=10, pady=8)

        # Virtual Link
        ttk.Label(frame, text="Virtual Link:").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        virtual_link_entry = ttk.Entry(frame, width=35)
        virtual_link_entry.grid(row=4, column=1, padx=10, pady=8)

        # Topics
        ttk.Label(frame, text="Topics:").grid(row=5, column=0, sticky='ne', padx=10, pady=8)
        topics_text = tk.Text(frame, width=35, height=3)
        topics_text.grid(row=5, column=1, padx=10, pady=8)

        # Action Items
        ttk.Label(frame, text="Action Items:").grid(row=6, column=0, sticky='ne', padx=10, pady=8)
        action_items_text = tk.Text(frame, width=35, height=3)
        action_items_text.grid(row=6, column=1, padx=10, pady=8)

        def save():
            try:
                session_date = validate_date_entry(date_entry, "Date")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                duration = validate_integer_entry(duration_entry, "Duration", min_value=1)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                session_type = validate_combobox(type_combo, "Type")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            location = location_entry.get().strip() or None
            virtual_link = virtual_link_entry.get().strip() or None
            topics = topics_text.get("1.0", "end-1c").strip() or None
            action_items = action_items_text.get("1.0", "end-1c").strip() or None

            try:
                session_id = MentoringManager.log_session(
                    match_id=match_id,
                    session_date=session_date,
                    duration_minutes=duration,
                    session_type=session_type,
                    location=location or '',
                    virtual_link=virtual_link or '',
                    topics_discussed=topics or '',
                    action_items=action_items or ''
                )
                messagebox.showinfo("Success",
                                    f"Session logged. ID: {session_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_sessions()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Log Session", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        date_entry.focus_set()

    def _complete_session(self):
        """Complete the selected session."""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a session to complete.")
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]
        session_status = item['values'][4]

        if session_status.lower() == 'completed':
            messagebox.showinfo("Info", "This session is already completed.")
            return

        if not messagebox.askyesno("Confirm", "Mark this session as completed?"):
            return

        try:
            MentoringManager.complete_session(session_id)
            messagebox.showinfo("Success", "Session marked as completed.")
            self._load_sessions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: GOALS ====================

    def _create_goals_tab(self):
        """Create goals tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Goals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Mentoring Goals", style='Header.TLabel').pack(side=tk.LEFT)

        # Match selector
        selector_frame = ttk.Frame(tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(selector_frame, text="Match:").pack(side=tk.LEFT, padx=5)
        self.goals_match_combo = ttk.Combobox(selector_frame, width=50, state='readonly')
        self.goals_match_combo.pack(side=tk.LEFT, padx=5)
        self.goals_match_combo.bind('<<ComboboxSelected>>', lambda e: self._load_goals())

        ttk.Button(selector_frame, text="Refresh",
                   command=self._refresh_goals).pack(side=tk.LEFT, padx=5)

        # Store match mapping
        self.goals_match_map = {}

        # Buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Add Goal",
                   command=self._add_goal_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Update Progress",
                   command=self._update_progress_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Complete Goal",
                   command=self._complete_goal).pack(side=tk.LEFT, padx=5)

        # Goals treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Title', 'Target Date', 'Progress', 'Status')
        self.goals_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.goals_tree.yview)

        widths = {'ID': 50, 'Title': 250, 'Target Date': 120, 'Progress': 100, 'Status': 100}
        for col in columns:
            self.goals_tree.heading(col, text=col)
            self.goals_tree.column(col, width=widths.get(col, 100))

        self.goals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.goals_tree.tag_configure('completed', background='#d4edda')
        self.goals_tree.tag_configure('in_progress', background='#cce5ff')
        self.goals_tree.tag_configure('deferred', background='#e2e3e5')
        self.goals_tree.tag_configure('not_started', background='#fff3cd')
        self.goals_tree.tag_configure('cancelled', background='#f8d7da')

        self._refresh_goals()

    def _load_goals_match_filter(self):
        """Load user's matches into the goals match combobox."""
        self.goals_match_map = {}

        user_id = self._get_user_id()
        try:
            matches = MentoringManager.get_user_matches(user_id)
        except Exception:
            matches = []

        self._load_programme_cache()

        display_values = []
        for m in matches:
            match_id = m.get('match_id') or m.get('id')
            programme_id = m.get('programme_id')
            programme_name = self._programme_cache.get(programme_id, str(programme_id))
            mentee = m.get('mentee_user_id') or m.get('mentee_id', '')
            status = m.get('status', '')
            label = f"#{match_id} - {programme_name} (Mentee: {mentee}) [{status}]"
            display_values.append(label)
            self.goals_match_map[label] = match_id

        self.goals_match_combo['values'] = display_values
        if display_values:
            self.goals_match_combo.set(display_values[0])

    def _refresh_goals(self):
        """Refresh match filter and reload goals."""
        self._load_goals_match_filter()
        self._load_goals()

    def _get_selected_goals_match_id(self):
        """Get the match ID from the goals match combo selection."""
        selected = self.goals_match_combo.get()
        return self.goals_match_map.get(selected)

    def _load_goals(self):
        """Load goals for the selected match."""
        for item in self.goals_tree.get_children():
            self.goals_tree.delete(item)

        match_id = self._get_selected_goals_match_id()
        if not match_id:
            return

        try:
            goals = MentoringManager.get_goals(match_id)
        except Exception:
            goals = []

        for g in goals:
            goal_id = g.get('goal_id') or g.get('id')
            status = g.get('status', '').lower()
            display_status = status.replace('_', ' ').title()
            progress = g.get('progress_pct', g.get('progress', 0)) or 0
            progress_display = f"{progress}%"

            self.goals_tree.insert('', tk.END, values=(
                goal_id,
                g.get('title', ''),
                g.get('target_date', '') or 'N/A',
                progress_display,
                display_status
            ), tags=(status,))

    def _add_goal_dialog(self):
        """Open dialog to add a new goal."""
        match_id = self._get_selected_goals_match_id()
        if not match_id:
            messagebox.showinfo("Info", "Please select a match first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Mentoring Goal")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        title_entry = ttk.Entry(frame, width=35)
        title_entry.grid(row=0, column=1, padx=10, pady=8)

        # Description
        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        desc_text = tk.Text(frame, width=35, height=4)
        desc_text.grid(row=1, column=1, padx=10, pady=8)

        # Target Date
        ttk.Label(frame, text="Target Date (YYYY-MM-DD):").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        target_date_entry = ttk.Entry(frame, width=15)
        target_date_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                title = validate_entry(title_entry, "Title")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            description = desc_text.get("1.0", "end-1c").strip() or ''

            try:
                target_date = validate_date_entry(target_date_entry, "Target Date")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                goal_id = MentoringManager.create_goal(
                    match_id=match_id,
                    title=title,
                    description=description,
                    target_date=target_date
                )
                messagebox.showinfo("Success",
                                    f"Goal created. ID: {goal_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_goals()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add Goal", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        title_entry.focus_set()

    def _update_progress_dialog(self):
        """Open dialog to update progress on the selected goal."""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a goal to update.")
            return

        item = self.goals_tree.item(selection[0])
        goal_id = item['values'][0]
        goal_title = item['values'][1]
        current_progress_str = str(item['values'][3]).replace('%', '')

        try:
            current_progress = int(current_progress_str)
        except ValueError:
            current_progress = 0

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Update Progress - {goal_title}")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Current progress display
        ttk.Label(frame, text=f"Current Progress: {current_progress}%",
                  font=('Arial', 10)).pack(anchor='w', pady=(0, 15))

        # Progress slider
        ttk.Label(frame, text="New Progress (%):").pack(anchor='w', pady=(0, 5))

        progress_var = tk.IntVar(value=current_progress)
        progress_scale = ttk.Scale(frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                   variable=progress_var, length=300)
        progress_scale.pack(fill=tk.X, pady=(0, 5))

        # Progress entry for precise input
        progress_entry_frame = ttk.Frame(frame)
        progress_entry_frame.pack(fill=tk.X, pady=(0, 10))
        progress_entry = ttk.Entry(progress_entry_frame, width=6)
        progress_entry.insert(0, str(current_progress))
        progress_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(progress_entry_frame, text="%").pack(side=tk.LEFT)

        # Sync slider and entry
        def on_scale_change(val):
            progress_entry.delete(0, tk.END)
            progress_entry.insert(0, str(int(float(val))))

        progress_scale.config(command=on_scale_change)

        def save():
            # Try entry first, fall back to slider
            entry_val = progress_entry.get().strip()
            try:
                progress = int(entry_val)
                if progress < 0 or progress > 100:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Validation Error",
                                     "Progress must be an integer between 0 and 100.",
                                     parent=dialog)
                return

            try:
                MentoringManager.update_goal(goal_id, progress_pct=progress)
                messagebox.showinfo("Success",
                                    f"Progress updated to {progress}%.",
                                    parent=dialog)
                dialog.destroy()
                self._load_goals()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Update", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _complete_goal(self):
        """Complete the selected goal."""
        selection = self.goals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a goal to complete.")
            return

        item = self.goals_tree.item(selection[0])
        goal_id = item['values'][0]
        goal_status = item['values'][4]

        if goal_status.lower() == 'completed':
            messagebox.showinfo("Info", "This goal is already completed.")
            return

        if not messagebox.askyesno("Confirm", "Mark this goal as completed?"):
            return

        try:
            MentoringManager.complete_goal(goal_id)
            messagebox.showinfo("Success", "Goal marked as completed.")
            self._load_goals()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: FIND MENTORS ====================

    def _create_find_mentors_tab(self):
        """Create find mentors tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Find Mentors")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Available Mentors", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter and action controls
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Programme:").pack(side=tk.LEFT, padx=5)
        self.mentors_programme_filter = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.mentors_programme_filter.pack(side=tk.LEFT, padx=5)
        self.mentors_programme_filter.bind('<<ComboboxSelected>>', lambda e: self._load_mentors())
        ttk.Button(filter_frame, text="Refresh",
                   command=self._refresh_mentors).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Register as Mentor",
                   command=self._register_mentor_dialog).pack(side=tk.LEFT, padx=5)

        # Store programme mapping for filter
        self.mentors_programme_map = {}

        # Mentors treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Name', 'Programme', 'Expertise', 'Slots', 'Availability')
        self.mentors_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.mentors_tree.yview)

        widths = {'ID': 50, 'Name': 150, 'Programme': 180, 'Expertise': 200,
                  'Slots': 100, 'Availability': 100}
        for col in columns:
            self.mentors_tree.heading(col, text=col)
            self.mentors_tree.column(col, width=widths.get(col, 100))

        self.mentors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Availability color tags
        self.mentors_tree.tag_configure('available', background='#d4edda')
        self.mentors_tree.tag_configure('limited', background='#fff3cd')
        self.mentors_tree.tag_configure('unavailable', background='#f8d7da')
        self.mentors_tree.tag_configure('on_leave', background='#e2e3e5')

        self._refresh_mentors()

    def _load_mentors_programme_filter(self):
        """Load programmes into the mentors filter combobox."""
        self.mentors_programme_map = {}

        try:
            programmes = MentoringManager.get_programmes()
        except Exception:
            programmes = []

        display_values = ['All']
        self.mentors_programme_map['All'] = None
        for p in programmes:
            pid = p.get('programme_id') or p.get('id')
            label = f"{p.get('name', '')} (#{pid})"
            display_values.append(label)
            self.mentors_programme_map[label] = pid

        self.mentors_programme_filter['values'] = display_values
        if not self.mentors_programme_filter.get():
            self.mentors_programme_filter.set('All')

    def _refresh_mentors(self):
        """Refresh programme filter and reload mentors."""
        self._load_mentors_programme_filter()
        self._load_mentors()

    def _load_mentors(self):
        """Load mentors based on programme filter."""
        for item in self.mentors_tree.get_children():
            self.mentors_tree.delete(item)

        selected = self.mentors_programme_filter.get()
        programme_id = self.mentors_programme_map.get(selected)

        try:
            if programme_id:
                mentors = MentoringManager.get_mentors(programme_id=programme_id)
            else:
                mentors = MentoringManager.get_mentors()
        except Exception:
            mentors = []

        self._load_programme_cache()

        for m in mentors:
            mentor_id = m.get('mentor_id') or m.get('id')
            prog_id = m.get('programme_id')
            programme_name = self._programme_cache.get(prog_id, str(prog_id))

            user_id = m.get('user_id', '')
            expertise = m.get('expertise_areas', m.get('expertise', '')) or ''
            current = m.get('current_mentees', 0) or 0
            max_m = m.get('max_mentees', 0) or 0
            slots_display = f"{current}/{max_m}"
            availability = m.get('availability', '').lower()
            display_availability = availability.replace('_', ' ').title()

            self.mentors_tree.insert('', tk.END, values=(
                mentor_id,
                user_id,
                programme_name,
                expertise[:50] if expertise else '',
                slots_display,
                display_availability
            ), tags=(availability,))

    def _register_mentor_dialog(self):
        """Open dialog to register as a mentor."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Register as Mentor")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Programme selector
        ttk.Label(frame, text="Programme:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        programme_combo = ttk.Combobox(frame, width=30, state='readonly')
        programme_combo.grid(row=0, column=1, padx=10, pady=8)

        programme_map = {}
        try:
            programmes = MentoringManager.get_programmes()
        except Exception:
            programmes = []

        combo_values = []
        for p in programmes:
            pid = p.get('programme_id') or p.get('id')
            label = f"{p.get('name', '')} (#{pid})"
            combo_values.append(label)
            programme_map[label] = pid
        programme_combo['values'] = combo_values
        if combo_values:
            programme_combo.current(0)

        # Expertise
        ttk.Label(frame, text="Expertise:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        expertise_text = tk.Text(frame, width=35, height=4)
        expertise_text.grid(row=1, column=1, padx=10, pady=8)

        # Max Mentees
        ttk.Label(frame, text="Max Mentees:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        max_mentees_entry = ttk.Entry(frame, width=10)
        max_mentees_entry.insert(0, "3")
        max_mentees_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Bio
        ttk.Label(frame, text="Bio:").grid(row=3, column=0, sticky='ne', padx=10, pady=8)
        bio_text = tk.Text(frame, width=35, height=4)
        bio_text.grid(row=3, column=1, padx=10, pady=8)

        def save():
            try:
                programme_label = validate_combobox(programme_combo, "Programme")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_programme_id = programme_map.get(programme_label)
            if not selected_programme_id:
                messagebox.showerror("Error", "Please select a valid programme.", parent=dialog)
                return

            try:
                expertise = validate_entry(expertise_text, "Expertise")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                max_mentees = validate_integer_entry(max_mentees_entry, "Max Mentees", min_value=1)
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            bio = bio_text.get("1.0", "end-1c").strip() or ''

            try:
                mentor_id = MentoringManager.register_mentor(
                    user_id=self._get_user_id(),
                    programme_id=selected_programme_id,
                    expertise_areas=expertise,
                    max_mentees=max_mentees,
                    bio=bio
                )
                messagebox.showinfo("Success",
                                    f"Registered as mentor. ID: {mentor_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_mentors()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Register", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        expertise_text.focus_set()

    # ==================== TAB 5: ADMIN ====================

    def _create_admin_tab(self):
        """Create admin tab for programme management (admin only)."""
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

        # ---- Programme CRUD Section ----
        crud_frame = ttk.LabelFrame(scroll_frame, text="Create Programme", padding=15)
        crud_frame.pack(fill=tk.X, padx=10, pady=10)

        # Name
        ttk.Label(crud_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_prog_name_entry = ttk.Entry(crud_frame, width=35)
        self.admin_prog_name_entry.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Description
        ttk.Label(crud_frame, text="Description:").grid(row=1, column=0, sticky='ne', padx=10, pady=8)
        self.admin_prog_desc_text = tk.Text(crud_frame, width=40, height=3)
        self.admin_prog_desc_text.grid(row=1, column=1, columnspan=2, padx=10, pady=8, sticky='w')

        # Type
        ttk.Label(crud_frame, text="Type:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_prog_type_combo = ttk.Combobox(
            crud_frame, values=['research', 'teaching', 'buddy', 'leadership', 'general'],
            width=20, state='readonly'
        )
        self.admin_prog_type_combo.set('general')
        self.admin_prog_type_combo.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Department
        ttk.Label(crud_frame, text="Department:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        self.admin_prog_dept_entry = ttk.Entry(crud_frame, width=25)
        self.admin_prog_dept_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Duration
        ttk.Label(crud_frame, text="Duration (months):").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        self.admin_prog_duration_entry = ttk.Entry(crud_frame, width=10)
        self.admin_prog_duration_entry.insert(0, "12")
        self.admin_prog_duration_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Create button
        ttk.Button(crud_frame, text="Create Programme",
                   command=self._create_programme).grid(row=5, column=1, padx=10, pady=15, sticky='w')

        # ---- Create/Activate Match Section ----
        match_frame = ttk.LabelFrame(scroll_frame, text="Create & Activate Match", padding=15)
        match_frame.pack(fill=tk.X, padx=10, pady=10)

        # Programme selector for match
        ttk.Label(match_frame, text="Programme:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.admin_match_prog_combo = ttk.Combobox(match_frame, width=30, state='readonly')
        self.admin_match_prog_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        self.admin_match_prog_combo.bind('<<ComboboxSelected>>', lambda e: self._load_admin_mentors())

        # Mentor selector
        ttk.Label(match_frame, text="Mentor:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.admin_match_mentor_combo = ttk.Combobox(match_frame, width=30, state='readonly')
        self.admin_match_mentor_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Mentee user ID
        ttk.Label(match_frame, text="Mentee User ID:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.admin_match_mentee_entry = ttk.Entry(match_frame, width=25)
        self.admin_match_mentee_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Match reason
        ttk.Label(match_frame, text="Match Reason:").grid(row=3, column=0, sticky='ne', padx=10, pady=8)
        self.admin_match_reason_text = tk.Text(match_frame, width=35, height=2)
        self.admin_match_reason_text.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Buttons
        match_btn_frame = ttk.Frame(match_frame)
        match_btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(match_btn_frame, text="Create Match",
                   command=self._admin_create_match).pack(side=tk.LEFT, padx=5)
        ttk.Button(match_btn_frame, text="Refresh Lists",
                   command=self._refresh_admin_match_lists).pack(side=tk.LEFT, padx=5)

        # Store mappings for admin match section
        self.admin_match_prog_map = {}
        self.admin_match_mentor_map = {}

        # ---- Statistics Section ----
        stats_frame = ttk.LabelFrame(scroll_frame, text="Programme Statistics", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        # Programme selector for stats
        stats_selector_row = ttk.Frame(stats_frame)
        stats_selector_row.pack(fill=tk.X, pady=5)
        ttk.Label(stats_selector_row, text="Programme:").pack(side=tk.LEFT, padx=5)
        self.admin_stats_prog_combo = ttk.Combobox(stats_selector_row, width=30, state='readonly')
        self.admin_stats_prog_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(stats_selector_row, text="Load Statistics",
                   command=self._load_statistics).pack(side=tk.LEFT, padx=5)

        # Statistics display
        self.stats_display_frame = ttk.Frame(stats_frame)
        self.stats_display_frame.pack(fill=tk.X, padx=10, pady=10)

        self.stats_label = ttk.Label(self.stats_display_frame,
                                     text="Select a programme and click 'Load Statistics'.",
                                     wraplength=600, justify=tk.LEFT)
        self.stats_label.pack(anchor='w')

        # Store stats programme mapping
        self.admin_stats_prog_map = {}

        # Load initial data for admin
        self._refresh_admin_match_lists()

    def _refresh_admin_match_lists(self):
        """Refresh the programme and mentor lists in admin match section."""
        self.admin_match_prog_map = {}
        self.admin_match_mentor_map = {}
        self.admin_stats_prog_map = {}

        try:
            programmes = MentoringManager.get_programmes()
        except Exception:
            programmes = []

        # Programme combos
        prog_display_values = []
        stats_display_values = []
        for p in programmes:
            pid = p.get('programme_id') or p.get('id')
            label = f"{p.get('name', '')} (#{pid})"
            prog_display_values.append(label)
            stats_display_values.append(label)
            self.admin_match_prog_map[label] = pid
            self.admin_stats_prog_map[label] = pid

        self.admin_match_prog_combo['values'] = prog_display_values
        self.admin_stats_prog_combo['values'] = stats_display_values
        if prog_display_values:
            self.admin_match_prog_combo.set(prog_display_values[0])
            self.admin_stats_prog_combo.set(stats_display_values[0])
            self._load_admin_mentors()
        else:
            self.admin_match_prog_combo.set('')
            self.admin_stats_prog_combo.set('')
            self.admin_match_mentor_combo['values'] = []
            self.admin_match_mentor_combo.set('')

    def _load_admin_mentors(self):
        """Load mentors for the selected programme in admin match section."""
        self.admin_match_mentor_map = {}

        selected = self.admin_match_prog_combo.get()
        programme_id = self.admin_match_prog_map.get(selected)

        if not programme_id:
            self.admin_match_mentor_combo['values'] = []
            self.admin_match_mentor_combo.set('')
            return

        try:
            mentors = MentoringManager.get_mentors(programme_id=programme_id)
        except Exception:
            mentors = []

        display_values = []
        for m in mentors:
            mentor_id = m.get('mentor_id') or m.get('id')
            user_id = m.get('user_id', '')
            current = m.get('current_mentees', 0) or 0
            max_m = m.get('max_mentees', 0) or 0
            label = f"{user_id} (#{mentor_id}) [{current}/{max_m} slots]"
            display_values.append(label)
            self.admin_match_mentor_map[label] = mentor_id

        self.admin_match_mentor_combo['values'] = display_values
        if display_values:
            self.admin_match_mentor_combo.set(display_values[0])
        else:
            self.admin_match_mentor_combo.set('')

    def _create_programme(self):
        """Create a new mentoring programme from the admin form."""
        try:
            name = validate_entry(self.admin_prog_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        description = self.admin_prog_desc_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showerror("Validation Error", "Description is required.")
            return

        try:
            programme_type = validate_combobox(self.admin_prog_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            department = validate_entry(self.admin_prog_dept_entry, "Department")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            duration = validate_integer_entry(self.admin_prog_duration_entry, "Duration", min_value=1)
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        user_id = self._get_user_id()

        try:
            programme_id = MentoringManager.create_programme(
                name=name,
                description=description,
                programme_type=programme_type,
                department=department,
                max_mentees_per_mentor=3,
                duration_months=duration,
                created_by=user_id
            )
            messagebox.showinfo("Success", f"Programme created. ID: {programme_id}")
            # Clear form
            self.admin_prog_name_entry.delete(0, tk.END)
            self.admin_prog_desc_text.delete("1.0", tk.END)
            self.admin_prog_type_combo.set('general')
            self.admin_prog_dept_entry.delete(0, tk.END)
            self.admin_prog_duration_entry.delete(0, tk.END)
            self.admin_prog_duration_entry.insert(0, "12")
            # Refresh lists
            self._refresh_admin_match_lists()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _admin_create_match(self):
        """Create a new mentor-mentee match from admin form."""
        # Validate programme selection
        try:
            prog_label = validate_combobox(self.admin_match_prog_combo, "Programme")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        selected_programme_id = self.admin_match_prog_map.get(prog_label)
        if not selected_programme_id:
            messagebox.showerror("Error", "Please select a valid programme.")
            return

        # Validate mentor selection
        try:
            mentor_label = validate_combobox(self.admin_match_mentor_combo, "Mentor")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        selected_mentor_id = self.admin_match_mentor_map.get(mentor_label)
        if not selected_mentor_id:
            messagebox.showerror("Error", "Please select a valid mentor.")
            return

        # Validate mentee user ID
        try:
            mentee_user_id = validate_entry(self.admin_match_mentee_entry, "Mentee User ID")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        match_reason = self.admin_match_reason_text.get("1.0", "end-1c").strip() or ''

        user_id = self._get_user_id()

        try:
            match_id = MentoringManager.create_match(
                programme_id=selected_programme_id,
                mentor_id=selected_mentor_id,
                mentee_user_id=mentee_user_id,
                match_reason=match_reason,
                matched_by=user_id
            )

            # Auto-activate the match
            try:
                MentoringManager.activate_match(
                    match_id=match_id,
                    start_date=datetime.now().strftime('%Y-%m-%d')
                )
            except Exception:
                pass  # Match was created but activation failed; still report success

            messagebox.showinfo("Success", f"Match created and activated. ID: {match_id}")
            self.admin_match_mentee_entry.delete(0, tk.END)
            self.admin_match_reason_text.delete("1.0", tk.END)
            self._load_admin_mentors()
            # Refresh my mentoring tab if visible
            try:
                self._load_my_mentoring()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_statistics(self):
        """Load and display statistics for the selected programme."""
        selected = self.admin_stats_prog_combo.get()
        programme_id = self.admin_stats_prog_map.get(selected)

        if not programme_id:
            messagebox.showinfo("Info", "Please select a programme first.")
            return

        try:
            stats = MentoringManager.get_programme_statistics(programme_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load statistics: {e}")
            return

        stats_text = (
            f"Programme ID: {stats.get('programme_id', 'N/A')}\n\n"
            f"Total Mentors: {stats.get('total_mentors', 0)}\n"
            f"Active Matches: {stats.get('active_matches', 0)}\n"
            f"Completed Matches: {stats.get('completed_matches', 0)}\n"
            f"Total Sessions: {stats.get('total_sessions', 0)}\n"
        )

        self.stats_label.config(text=stats_text)
