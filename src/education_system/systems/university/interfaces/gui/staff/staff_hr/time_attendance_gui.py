"""
Time & Attendance GUI

Provides interface for:
- Clock in/out functionality
- Viewing time entries
- Managing timesheets
- Overtime tracking
- Attendance reports
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Optional
import csv

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.i18n import get_text as get_translation

# Translation helper
_t = get_translation


class TimeAttendanceGUI:
    """GUI for managing time tracking and attendance."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.login_required", default="Login required to access Time & Attendance"))
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t("staff_hr.time_attendance.tab_title", default="Time & Attendance"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t("staff_hr.time_attendance.window_title", default="Time & Attendance System"))
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t("staff_hr.time_attendance.close", default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_bar = ttk.Label(self.window, text=_t("staff_hr.time_attendance.ready", default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Clock.TButton', font=('Arial', 12, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_clock_tab()
        self._create_entries_tab()
        self._create_timesheets_tab()
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()

    def _create_clock_tab(self):
        """Create the clock in/out tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.time_attendance.tabs.clock_in_out", default="Clock In/Out"))

        # Main clock display
        clock_frame = ttk.LabelFrame(tab, text=_t("staff_hr.time_attendance.clock.time_clock", default="Time Clock"), padding=30)
        clock_frame.pack(pady=30)

        # Current time display
        self.time_label = ttk.Label(clock_frame, text="", font=('Arial', 36, 'bold'))
        self.time_label.pack(pady=10)

        self.date_label = ttk.Label(clock_frame, text="", font=('Arial', 14))
        self.date_label.pack(pady=5)

        # Status display
        self.clock_status = ttk.Label(clock_frame, text=_t("staff_hr.time_attendance.clock.status_checking", default="Checking status..."), font=('Arial', 12))
        self.clock_status.pack(pady=20)

        # Clock buttons
        btn_frame = ttk.Frame(clock_frame)
        btn_frame.pack(pady=20)

        self.clock_in_btn = ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.clock.btn_clock_in", default="Clock In"), style='Clock.TButton',
                                       command=self._clock_in, width=15)
        self.clock_in_btn.pack(side=tk.LEFT, padx=20)

        self.clock_out_btn = ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.clock.btn_clock_out", default="Clock Out"), style='Clock.TButton',
                                        command=self._clock_out, width=15)
        self.clock_out_btn.pack(side=tk.LEFT, padx=20)

        # Work type selection
        type_frame = ttk.Frame(clock_frame)
        type_frame.pack(pady=10)

        ttk.Label(type_frame, text=_t("staff_hr.time_attendance.clock.work_type_label", default="Work Type:")).pack(side=tk.LEFT, padx=5)
        self.work_type = ttk.Combobox(type_frame, values=[
            _t("staff_hr.time_attendance.clock.work_types.regular", default="Regular"),
            _t("staff_hr.time_attendance.clock.work_types.remote", default="Remote"),
            _t("staff_hr.time_attendance.clock.work_types.overtime", default="Overtime")
        ], width=15, state='readonly')
        self.work_type.set(_t("staff_hr.time_attendance.clock.work_types.regular", default="Regular"))
        self.work_type.pack(side=tk.LEFT, padx=5)

        ttk.Label(type_frame, text=_t("staff_hr.time_attendance.clock.location_label", default="Location:")).pack(side=tk.LEFT, padx=15)
        self.location = ttk.Combobox(type_frame, values=[
            _t("staff_hr.time_attendance.clock.locations.office", default="Office"),
            _t("staff_hr.time_attendance.clock.locations.home", default="Home"),
            _t("staff_hr.time_attendance.clock.locations.field", default="Field"),
            _t("staff_hr.time_attendance.clock.locations.other", default="Other")
        ], width=15, state='readonly')
        self.location.set(_t("staff_hr.time_attendance.clock.locations.office", default="Office"))
        self.location.pack(side=tk.LEFT, padx=5)

        # Today's summary
        summary_frame = ttk.LabelFrame(tab, text=_t("staff_hr.time_attendance.summary.todays_summary", default="Today's Summary"), padding=15)
        summary_frame.pack(fill=tk.X, padx=30, pady=20)

        self.today_hours = ttk.Label(summary_frame, text=_t("staff_hr.time_attendance.summary.hours_worked", default="Hours Worked: {hours}", hours="0.00"), font=('Arial', 12))
        self.today_hours.pack(side=tk.LEFT, padx=30)

        self.today_entries = ttk.Label(summary_frame, text=_t("staff_hr.time_attendance.summary.entries", default="Entries: {count}", count="0"), font=('Arial', 12))
        self.today_entries.pack(side=tk.LEFT, padx=30)

        self.week_hours = ttk.Label(summary_frame, text=_t("staff_hr.time_attendance.summary.week_total", default="Week Total: {hours} hours", hours="0.00"), font=('Arial', 12))
        self.week_hours.pack(side=tk.LEFT, padx=30)

        # Start clock update
        self._update_clock()
        self._update_clock_status()

    def _create_entries_tab(self):
        """Create the time entries tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.time_attendance.tabs.time_entries", default="Time Entries"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.time_attendance.entries.header", default="Time Entries"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.entries.btn_add_manual", default="Add Manual Entry"), command=self._add_manual_entry).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.entries.btn_refresh", default="Refresh"), command=self._load_entries).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.entries.btn_export", default="Export"), command=self._export_entries).pack(side=tk.LEFT, padx=5)

        # Date range filter
        filter_frame = ttk.LabelFrame(tab, text=_t("staff_hr.time_attendance.entries.date_range", default="Date Range"), padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t("staff_hr.time_attendance.entries.label_from", default="From:")).pack(side=tk.LEFT, padx=5)
        self.entries_from = ttk.Entry(filter_frame, width=12)
        self.entries_from.insert(0, (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))
        self.entries_from.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text=_t("staff_hr.time_attendance.entries.label_to", default="To:")).pack(side=tk.LEFT, padx=15)
        self.entries_to = ttk.Entry(filter_frame, width=12)
        self.entries_to.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.entries_to.pack(side=tk.LEFT, padx=5)

        ttk.Button(filter_frame, text=_t("staff_hr.time_attendance.entries.btn_filter", default="Filter"), command=self._load_entries).pack(side=tk.LEFT, padx=15)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.time_attendance.entries.columns.id", default="ID"),
            _t("staff_hr.time_attendance.entries.columns.date", default="Date"),
            _t("staff_hr.time_attendance.entries.columns.clock_in", default="Clock In"),
            _t("staff_hr.time_attendance.entries.columns.clock_out", default="Clock Out"),
            _t("staff_hr.time_attendance.entries.columns.break", default="Break"),
            _t("staff_hr.time_attendance.entries.columns.hours", default="Hours"),
            _t("staff_hr.time_attendance.entries.columns.type", default="Type"),
            _t("staff_hr.time_attendance.entries.columns.location", default="Location")
        )
        self.entries_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.entries_tree.yview)

        col_widths = [50, 100, 80, 80, 60, 60, 80, 80]
        for i, col in enumerate(columns):
            self.entries_tree.heading(col, text=col)
            self.entries_tree.column(col, width=col_widths[i], anchor=tk.CENTER)

        self.entries_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click for editing
        self.entries_tree.bind('<Double-1>', self._edit_entry)

        # Summary
        summary_frame = ttk.Frame(tab)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        self.entries_total = ttk.Label(summary_frame, text=_t("staff_hr.time_attendance.entries.summary.total_hours", default="Total Hours: {hours}", hours="0.00"), font=('Arial', 11, 'bold'))
        self.entries_total.pack(side=tk.LEFT, padx=20)

        self.entries_overtime = ttk.Label(summary_frame, text=_t("staff_hr.time_attendance.entries.summary.overtime", default="Overtime: {hours}", hours="0.00"), font=('Arial', 11))
        self.entries_overtime.pack(side=tk.LEFT, padx=20)

        self._load_entries()

    def _create_timesheets_tab(self):
        """Create the timesheets tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.time_attendance.tabs.timesheets", default="Timesheets"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.time_attendance.timesheets.header", default="Timesheets"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.timesheets.btn_create", default="Create Timesheet"), command=self._create_timesheet).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.timesheets.btn_submit", default="Submit Selected"), command=self._submit_timesheet).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.timesheets.btn_refresh", default="Refresh"), command=self._load_timesheets).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.time_attendance.timesheets.columns.id", default="ID"),
            _t("staff_hr.time_attendance.timesheets.columns.week_start", default="Week Start"),
            _t("staff_hr.time_attendance.timesheets.columns.week_end", default="Week End"),
            _t("staff_hr.time_attendance.timesheets.columns.regular", default="Regular"),
            _t("staff_hr.time_attendance.timesheets.columns.overtime", default="Overtime"),
            _t("staff_hr.time_attendance.timesheets.columns.total", default="Total"),
            _t("staff_hr.time_attendance.timesheets.columns.status", default="Status"),
            _t("staff_hr.time_attendance.timesheets.columns.submitted", default="Submitted")
        )
        self.timesheets_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                            yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.timesheets_tree.yview)

        for col in columns:
            self.timesheets_tree.heading(col, text=col)
            self.timesheets_tree.column(col, width=100, anchor=tk.CENTER)

        self.timesheets_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status tags
        self.timesheets_tree.tag_configure('draft', background='#e2e3e5')
        self.timesheets_tree.tag_configure('submitted', background='#fff3cd')
        self.timesheets_tree.tag_configure('approved', background='#d4edda')
        self.timesheets_tree.tag_configure('rejected', background='#f8d7da')

        self._load_timesheets()

    def _create_approvals_tab(self):
        """Create the timesheet approvals tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("staff_hr.time_attendance.tabs.approve_timesheets", default="Approve Timesheets"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("staff_hr.time_attendance.approvals.header", default="Pending Timesheet Approvals"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.approvals.btn_approve", default="Approve Selected"), command=self._approve_timesheets).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.approvals.btn_reject", default="Reject Selected"), command=self._reject_timesheets).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.approvals.btn_refresh", default="Refresh"), command=self._load_pending_timesheets).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = (
            _t("staff_hr.time_attendance.timesheets.columns.id", default="ID"),
            _t("staff_hr.time_attendance.timesheets.columns.employee", default="Employee"),
            _t("staff_hr.time_attendance.timesheets.columns.week_start", default="Week Start"),
            _t("staff_hr.time_attendance.timesheets.columns.week_end", default="Week End"),
            _t("staff_hr.time_attendance.timesheets.columns.regular", default="Regular"),
            _t("staff_hr.time_attendance.timesheets.columns.overtime", default="Overtime"),
            _t("staff_hr.time_attendance.timesheets.columns.total", default="Total"),
            _t("staff_hr.time_attendance.timesheets.columns.submitted", default="Submitted")
        )
        self.pending_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.pending_tree.yview)

        for col in columns:
            self.pending_tree.heading(col, text=col)
            self.pending_tree.column(col, width=100, anchor=tk.CENTER)

        self.pending_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_pending_timesheets()

    def _update_clock(self):
        """Update the clock display."""
        # Check if widgets still exist before updating
        if not hasattr(self, 'time_label') or not self.time_label.winfo_exists():
            return

        try:
            now = datetime.now()
            self.time_label.config(text=now.strftime("%H:%M:%S"))
            self.date_label.config(text=now.strftime("%A, %B %d, %Y"))

            # Schedule next update
            self.root.after(1000, self._update_clock)
        except tk.TclError:
            # Widget was destroyed, stop updating
            pass

    def _update_clock_status(self):
        """Update clock in/out status."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        today = datetime.now().strftime("%Y-%m-%d")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check for open entry (clocked in but not out)
                cursor.execute('''
                    SELECT entry_id, clock_in FROM time_entries
                    WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
                    ORDER BY clock_in DESC LIMIT 1
                ''', (user_id, today))

                open_entry = cursor.fetchone()

                if open_entry:
                    clock_in_time = open_entry[1]
                    self.clock_status.config(text=_t("staff_hr.time_attendance.clock.status_clocked_in", default="Clocked in since {time}", time=clock_in_time), foreground='green')
                    self.clock_in_btn.config(state=tk.DISABLED)
                    self.clock_out_btn.config(state=tk.NORMAL)
                else:
                    self.clock_status.config(text=_t("staff_hr.time_attendance.clock.status_not_clocked_in", default="Not clocked in"), foreground='gray')
                    self.clock_in_btn.config(state=tk.NORMAL)
                    self.clock_out_btn.config(state=tk.DISABLED)

                # Get today's summary
                cursor.execute('''
                    SELECT COUNT(*), SUM(
                        CASE WHEN clock_out IS NOT NULL THEN
                            (julianday(clock_out) - julianday(clock_in)) * 24 - COALESCE(break_minutes, 0) / 60.0
                        ELSE 0 END
                    )
                    FROM time_entries WHERE user_id = ? AND entry_date = ?
                ''', (user_id, today))

                result = cursor.fetchone()
                entries = result[0] or 0
                hours = result[1] or 0

                self.today_hours.config(text=_t("staff_hr.time_attendance.summary.hours_worked", default="Hours Worked: {hours}", hours=f"{hours:.2f}"))
                self.today_entries.config(text=_t("staff_hr.time_attendance.summary.entries", default="Entries: {count}", count=entries))

                # Get week total
                week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
                cursor.execute('''
                    SELECT SUM(
                        CASE WHEN clock_out IS NOT NULL THEN
                            (julianday(clock_out) - julianday(clock_in)) * 24 - COALESCE(break_minutes, 0) / 60.0
                        ELSE 0 END
                    )
                    FROM time_entries WHERE user_id = ? AND entry_date >= ?
                ''', (user_id, week_start))

                week_total = cursor.fetchone()[0] or 0
                self.week_hours.config(text=_t("staff_hr.time_attendance.summary.week_total", default="Week Total: {hours} hours", hours=f"{week_total:.2f}"))

        except Exception as e:
            self.clock_status.config(text=_t("staff_hr.time_attendance.errors.status_error", default="Error: {error}", error=str(e)), foreground='red')

    def _clock_in(self):
        """Clock in for the current user."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        now = datetime.now()

        try:
            with transaction() as conn:
                conn.execute('''
                    INSERT INTO time_entries (user_id, entry_date, clock_in, work_type, location)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"),
                      self.work_type.get().lower(), self.location.get().lower()))

            log_activity('create', 'time_entry', user_id=user_id, details={'action': 'clock_in'})
            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.clock_in.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.clock_in.success_message", default="Clocked in at {time}", time=now.strftime('%H:%M:%S')))
            self._update_clock_status()
            self._load_entries()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.clock_in_failed", default="Failed to clock in: {error}", error=str(e)))

    def _clock_out(self):
        """Clock out for the current user."""
        user_id = self.current_user.get('id') or self.current_user.get('username')
        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M:%S")

        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE time_entries SET clock_out = ?, updated_at = ?
                    WHERE user_id = ? AND entry_date = ? AND clock_out IS NULL
                ''', (now, datetime.now().isoformat(), user_id, today))

            log_activity('update', 'time_entry', user_id=user_id, details={'action': 'clock_out'})
            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.clock_out.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.clock_out.success_message", default="Clocked out at {time}", time=now))
            self._update_clock_status()
            self._load_entries()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.clock_out_failed", default="Failed to clock out: {error}", error=str(e)))

    def _load_entries(self):
        """Load time entries."""
        try:
            self.entries_tree.delete(*self.entries_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')
            from_date = self.entries_from.get()
            to_date = self.entries_to.get()

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT entry_id, entry_date, clock_in, clock_out, break_minutes,
                           work_type, location
                    FROM time_entries
                    WHERE user_id = ? AND entry_date BETWEEN ? AND ?
                    ORDER BY entry_date DESC, clock_in DESC
                ''', (user_id, from_date, to_date))

                total_hours = 0
                total_overtime = 0

                for row in cursor.fetchall():
                    hours = 0
                    if row[3]:  # clock_out exists
                        clock_in = datetime.strptime(f"{row[1]} {row[2]}", "%Y-%m-%d %H:%M:%S")
                        clock_out = datetime.strptime(f"{row[1]} {row[3]}", "%Y-%m-%d %H:%M:%S")
                        hours = (clock_out - clock_in).total_seconds() / 3600 - (row[4] or 0) / 60

                    values = (row[0], row[1], row[2], row[3] or '-', row[4] or 0,
                              f"{hours:.2f}", row[5].capitalize(), row[6].capitalize())
                    self.entries_tree.insert('', 'end', values=values)

                    total_hours += hours
                    if row[5] == 'overtime':
                        total_overtime += hours

            self.entries_total.config(text=_t("staff_hr.time_attendance.entries.summary.total_hours", default="Total Hours: {hours}", hours=f"{total_hours:.2f}"))
            self.entries_overtime.config(text=_t("staff_hr.time_attendance.entries.summary.overtime", default="Overtime: {hours}", hours=f"{total_overtime:.2f}"))

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.load_entries_failed", default="Failed to load entries: {error}", error=str(e)))

    def _add_manual_entry(self):
        """Add a manual time entry."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("staff_hr.time_attendance.dialogs.add_manual_entry.title", default="Add Manual Entry"))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.header", default="Manual Time Entry"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Date
        date_frame = ttk.Frame(main_frame)
        date_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_date", default="Date:"), width=12, anchor=tk.W).pack(side=tk.LEFT)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=date_var, width=15).pack(side=tk.LEFT)

        # Clock in
        in_frame = ttk.Frame(main_frame)
        in_frame.pack(fill=tk.X, pady=5)
        ttk.Label(in_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_clock_in", default="Clock In:"), width=12, anchor=tk.W).pack(side=tk.LEFT)
        in_var = tk.StringVar(value=_t("staff_hr.time_attendance.values.default_clock_in", default="09:00:00"))
        ttk.Entry(in_frame, textvariable=in_var, width=15).pack(side=tk.LEFT)
        ttk.Label(in_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.hint_time_format", default="(HH:MM:SS)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Clock out
        out_frame = ttk.Frame(main_frame)
        out_frame.pack(fill=tk.X, pady=5)
        ttk.Label(out_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_clock_out", default="Clock Out:"), width=12, anchor=tk.W).pack(side=tk.LEFT)
        out_var = tk.StringVar(value=_t("staff_hr.time_attendance.values.default_clock_out", default="17:00:00"))
        ttk.Entry(out_frame, textvariable=out_var, width=15).pack(side=tk.LEFT)
        ttk.Label(out_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.hint_time_format", default="(HH:MM:SS)"), font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # Break
        break_frame = ttk.Frame(main_frame)
        break_frame.pack(fill=tk.X, pady=5)
        ttk.Label(break_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_break", default="Break (min):"), width=12, anchor=tk.W).pack(side=tk.LEFT)
        break_var = tk.StringVar(value=_t("staff_hr.time_attendance.values.default_break", default="30"))
        ttk.Entry(break_frame, textvariable=break_var, width=15).pack(side=tk.LEFT)

        # Work type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_work_type", default="Work Type:"), width=12, anchor=tk.W).pack(side=tk.LEFT)
        type_var = tk.StringVar(value=_t("staff_hr.time_attendance.clock.work_types.regular", default="Regular"))
        ttk.Combobox(type_frame, textvariable=type_var, values=[
            _t("staff_hr.time_attendance.clock.work_types.regular", default="Regular"),
            _t("staff_hr.time_attendance.clock.work_types.remote", default="Remote"),
            _t("staff_hr.time_attendance.clock.work_types.overtime", default="Overtime")
        ], width=13, state='readonly').pack(side=tk.LEFT)

        # Notes
        ttk.Label(main_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.label_notes", default="Notes:"), anchor=tk.W).pack(fill=tk.X, pady=(10, 5))
        notes_entry = ttk.Entry(main_frame, width=40)
        notes_entry.pack(fill=tk.X)

        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def save_entry():
            user_id = self.current_user.get('id') or self.current_user.get('username')

            try:
                break_mins = int(break_var.get())
            except ValueError:
                error_label.config(text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.error_invalid_break", default="Invalid break duration"))
                return

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO time_entries
                        (user_id, entry_date, clock_in, clock_out, break_minutes, work_type, location, is_manual, notes)
                        VALUES (?, ?, ?, ?, ?, ?, 'office', 1, ?)
                    ''', (user_id, date_var.get(), in_var.get(), out_var.get(),
                          break_mins, type_var.get().lower(), notes_entry.get()))

                log_activity('create', 'time_entry', user_id=user_id, details={'action': 'manual_entry'})
                messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.add_manual_entry.success_title", default="Success"),
                                  _t("staff_hr.time_attendance.dialogs.add_manual_entry.success_message", default="Manual entry added"))
                dialog.destroy()
                self._load_entries()

            except Exception as e:
                error_label.config(text=_t("staff_hr.time_attendance.errors.error_with_message", default="Error: {error}", error=str(e)))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.btn_save", default="Save"), command=save_entry).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("staff_hr.time_attendance.dialogs.add_manual_entry.btn_cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _edit_entry(self, event=None):
        """Edit selected time entry."""
        selection = self.entries_tree.selection()
        if not selection:
            return

        item = self.entries_tree.item(selection[0])
        entry_id = item['values'][0]

        # Similar dialog to add_manual_entry but pre-filled
        messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.edit_entry.title", default="Edit Entry"),
                          _t("staff_hr.time_attendance.dialogs.edit_entry.message", default="Editing entry {id}\n(Full edit dialog would open here)", id=entry_id))

    def _load_timesheets(self):
        """Load user's timesheets."""
        try:
            self.timesheets_tree.delete(*self.timesheets_tree.get_children())

            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timesheet_id, week_start, week_end, regular_hours,
                           overtime_hours, total_hours, status, submitted_date
                    FROM timesheets
                    WHERE user_id = ?
                    ORDER BY week_start DESC
                ''', (user_id,))

                for row in cursor.fetchall():
                    values = (row[0], row[1], row[2], f"{row[3]:.2f}", f"{row[4]:.2f}",
                              f"{row[5]:.2f}", row[6].capitalize(), row[7] or '-')
                    self.timesheets_tree.insert('', 'end', values=values, tags=(row[6],))

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.load_timesheets_failed", default="Failed to load timesheets: {error}", error=str(e)))

    def _create_timesheet(self):
        """Create a new timesheet for current week."""
        user_id = self.current_user.get('id') or self.current_user.get('username')

        # Calculate current week
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if timesheet already exists
                cursor.execute('''
                    SELECT timesheet_id FROM timesheets
                    WHERE user_id = ? AND week_start = ?
                ''', (user_id, week_start.strftime("%Y-%m-%d")))

                if cursor.fetchone():
                    messagebox.showwarning(_t("staff_hr.time_attendance.errors.error_generic", default="Warning"),
                                         _t("staff_hr.time_attendance.dialogs.create_timesheet.warning_exists", default="Timesheet for this week already exists"))
                    return

                # Calculate hours from time entries
                cursor.execute('''
                    SELECT work_type,
                           SUM((julianday(clock_out) - julianday(clock_in)) * 24 - COALESCE(break_minutes, 0) / 60.0)
                    FROM time_entries
                    WHERE user_id = ? AND entry_date BETWEEN ? AND ? AND clock_out IS NOT NULL
                    GROUP BY work_type
                ''', (user_id, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))

                regular_hours = 0
                overtime_hours = 0

                for row in cursor.fetchall():
                    if row[0] == 'overtime':
                        overtime_hours = row[1] or 0
                    else:
                        regular_hours += row[1] or 0

            with transaction() as conn:
                conn.execute('''
                    INSERT INTO timesheets
                    (user_id, week_start, week_end, regular_hours, overtime_hours, total_hours, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'draft')
                ''', (user_id, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"),
                      regular_hours, overtime_hours, regular_hours + overtime_hours))

            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.create_timesheet.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.create_timesheet.success_message", default="Timesheet created"))
            self._load_timesheets()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.create_timesheet_failed", default="Failed to create timesheet: {error}", error=str(e)))

    def _submit_timesheet(self):
        """Submit selected timesheet for approval."""
        selection = self.timesheets_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_hr.time_attendance.errors.error_generic", default="Warning"),
                                 _t("staff_hr.time_attendance.dialogs.submit_timesheet.warning_select", default="Please select a timesheet to submit"))
            return

        item = self.timesheets_tree.item(selection[0])
        timesheet_id = item['values'][0]
        status = item['values'][6].lower()

        if status != 'draft':
            messagebox.showwarning(_t("staff_hr.time_attendance.errors.error_generic", default="Warning"),
                                 _t("staff_hr.time_attendance.dialogs.submit_timesheet.warning_draft_only", default="Only draft timesheets can be submitted"))
            return

        if not messagebox.askyesno(_t("staff_hr.time_attendance.dialogs.submit_timesheet.confirm_title", default="Confirm"),
                                  _t("staff_hr.time_attendance.dialogs.submit_timesheet.confirm_message", default="Submit this timesheet for approval?")):
            return

        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE timesheets SET status = 'submitted', submitted_date = ?, updated_at = ?
                    WHERE timesheet_id = ?
                ''', (datetime.now().strftime("%Y-%m-%d"), datetime.now().isoformat(), timesheet_id))

            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.submit_timesheet.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.submit_timesheet.success_message", default="Timesheet submitted for approval"))
            self._load_timesheets()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.submit_timesheet_failed", default="Failed to submit timesheet: {error}", error=str(e)))

    def _load_pending_timesheets(self):
        """Load pending timesheets for approval."""
        try:
            self.pending_tree.delete(*self.pending_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timesheet_id, user_id, week_start, week_end,
                           regular_hours, overtime_hours, total_hours, submitted_date
                    FROM timesheets
                    WHERE status = 'submitted'
                    ORDER BY submitted_date ASC
                ''')

                for row in cursor.fetchall():
                    values = (row[0], row[1], row[2], row[3], f"{row[4]:.2f}",
                              f"{row[5]:.2f}", f"{row[6]:.2f}", row[7] or '-')
                    self.pending_tree.insert('', 'end', values=values)

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.load_pending_failed", default="Failed to load pending timesheets: {error}", error=str(e)))

    def _approve_timesheets(self):
        """Approve selected timesheets."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_hr.time_attendance.errors.error_generic", default="Warning"),
                                 _t("staff_hr.time_attendance.dialogs.approve_timesheets.warning_select", default="Please select timesheets to approve"))
            return

        if not messagebox.askyesno(_t("staff_hr.time_attendance.dialogs.approve_timesheets.confirm_title", default="Confirm"),
                                  _t("staff_hr.time_attendance.dialogs.approve_timesheets.confirm_message", default="Approve {count} timesheet(s)?", count=len(selection))):
            return

        approved_by = self.current_user.get('username') or self.current_user.get('id')

        try:
            with transaction() as conn:
                for item_id in selection:
                    item = self.pending_tree.item(item_id)
                    timesheet_id = item['values'][0]

                    conn.execute('''
                        UPDATE timesheets
                        SET status = 'approved', approved_by = ?, approved_date = ?, updated_at = ?
                        WHERE timesheet_id = ?
                    ''', (approved_by, datetime.now().strftime("%Y-%m-%d"),
                          datetime.now().isoformat(), timesheet_id))

            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.approve_timesheets.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.approve_timesheets.success_message", default="Approved {count} timesheet(s)", count=len(selection)))
            self._load_pending_timesheets()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.approve_failed", default="Failed to approve timesheets: {error}", error=str(e)))

    def _reject_timesheets(self):
        """Reject selected timesheets."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning(_t("staff_hr.time_attendance.errors.error_generic", default="Warning"),
                                 _t("staff_hr.time_attendance.dialogs.reject_timesheets.warning_select", default="Please select timesheets to reject"))
            return

        reason = tk.simpledialog.askstring(_t("staff_hr.time_attendance.dialogs.reject_timesheets.prompt_reason", default="Rejection Reason"),
                                          _t("staff_hr.time_attendance.dialogs.reject_timesheets.prompt_reason", default="Enter rejection reason:"))
        if not reason:
            return

        try:
            with transaction() as conn:
                for item_id in selection:
                    item = self.pending_tree.item(item_id)
                    timesheet_id = item['values'][0]

                    conn.execute('''
                        UPDATE timesheets
                        SET status = 'rejected', rejection_reason = ?, updated_at = ?
                        WHERE timesheet_id = ?
                    ''', (reason, datetime.now().isoformat(), timesheet_id))

            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.reject_timesheets.success_title", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.reject_timesheets.success_message", default="Rejected {count} timesheet(s)", count=len(selection)))
            self._load_pending_timesheets()

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.reject_failed", default="Failed to reject timesheets: {error}", error=str(e)))

    def _export_entries(self):
        """Export time entries to CSV."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"{_t('staff_hr.time_attendance.dialogs.export_entries.filename_prefix', default='time_entries')}_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.id", default="ID"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.date", default="Date"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.clock_in", default="Clock In"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.clock_out", default="Clock Out"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.break", default="Break"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.hours", default="Hours"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.type", default="Type"),
                    _t("staff_hr.time_attendance.dialogs.export_entries.csv_headers.location", default="Location")
                ])

                for item_id in self.entries_tree.get_children():
                    item = self.entries_tree.item(item_id)
                    writer.writerow(item['values'])

            messagebox.showinfo(_t("staff_hr.time_attendance.dialogs.export_entries.success", default="Success"),
                              _t("staff_hr.time_attendance.dialogs.export_entries.success", default="Exported to {filename}", filename=filename))

        except Exception as e:
            messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                               _t("staff_hr.time_attendance.errors.export_failed", default="Failed to export: {error}", error=str(e)))


def launch_time_attendance_gui(root, auth):
    """Launch Time & Attendance GUI."""
    try:
        return TimeAttendanceGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t("staff_hr.time_attendance.errors.error_generic", default="Error"),
                           _t("staff_hr.time_attendance.errors.error_with_message", default="Failed to launch Time & Attendance: {error}", error=str(e)))
        return None
