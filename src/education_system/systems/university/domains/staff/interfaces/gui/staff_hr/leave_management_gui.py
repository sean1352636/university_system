"""
Leave Management GUI

Provides interface for:
- Viewing and submitting leave requests
- Managing leave balances
- Approving/rejecting leave requests (line managers and HR)
- Leave calendar view
- Exporting leave reports
- Sickness absence, family leave, flexible working, entitlements (HR)

Everything goes through ``LeaveManager`` and the ``domain/staff_hr``
leave modules (no SQL here); people are keyed by username.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional
import csv
import os

from education_system.systems.university.domains.staff.domain.staff_hr.services import LeaveManager
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr import _access as hr_access
from education_system.systems.university.domains.staff.interfaces.gui.staff_hr.leave_extra_tabs import (
    LeaveExtraTabsMixin,
)
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity


class LeaveManagementGUI(LeaveExtraTabsMixin):
    """GUI for managing staff leave requests and balances."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None
        self.actor = hr_access.actor(self)
        self.me = hr_access.user_key(self) if self.current_user else ''

        if not self.current_user:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), _t('gui.staff.staff_hr.leave_management.dialogs.login_required_to_access_leave_management', default="Login required to access Leave Management"))
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text=_t('gui.staff.staff_hr.leave_management.tabs.leave_management', default="Leave Management"))
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title(_t('gui.staff.staff_hr.leave_management.windows.leave_management_system', default="Leave Management System"))
        self.window.geometry("1400x900")
        self.window.minsize(1200, 800)

        # Bottom frame with close button
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.close', default="Close"), command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = ttk.Label(self.window, text=_t('gui.staff.staff_hr.leave_management.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._build_interface(self.window)

    def _build_interface(self, parent):
        """Build the main interface."""
        # Configure styles
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        # Main notebook with tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self._create_requests_tab()
        self._create_balances_tab()
        if hr_access.can(self, 'manager'):
            self._create_approvals_tab()
        self._create_calendar_tab()
        self._create_absence_tab()
        self._create_family_tab()
        self._create_flexible_tab()
        if hr_access.can(self, 'hr'):
            self._create_entitlements_tab()

    def _create_requests_tab(self):
        """Create the leave requests tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.leave_management.tabs.my_requests', default="My Requests"))

        # Header frame
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.leave_management.labels.leave_requests', default="Leave Requests"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.new_request', default="New Request"), command=self._show_request_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.refresh', default="Refresh"), command=self._load_requests).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.export', default="Export"), command=self._export_requests).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.leave_management.labels.filters', default="Filters"), padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.leave_management.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
        self.status_filter = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Approved', 'Rejected', 'Cancelled'], width=12)
        self.status_filter.set('All')
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_requests())

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.leave_management.labels.year', default="Year:")).pack(side=tk.LEFT, padx=15)
        current_year = datetime.now().year
        self.year_filter = ttk.Combobox(filter_frame, values=[str(y) for y in range(current_year - 2, current_year + 2)], width=8)
        self.year_filter.set(str(current_year))
        self.year_filter.pack(side=tk.LEFT, padx=5)
        self.year_filter.bind('<<ComboboxSelected>>', lambda e: self._load_requests())

        # Treeview frame
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        # Treeview
        columns = ('ID', 'Type', 'Start Date', 'End Date', 'Days', 'Status', 'Submitted', 'Approved By')
        self.requests_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                          yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        y_scroll.config(command=self.requests_tree.yview)
        x_scroll.config(command=self.requests_tree.xview)

        # Configure columns
        col_widths = {'ID': 50, 'Type': 120, 'Start Date': 100, 'End Date': 100,
                      'Days': 60, 'Status': 80, 'Submitted': 100, 'Approved By': 100}
        for col in columns:
            self.requests_tree.heading(col, text=col)
            self.requests_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        # Pack treeview and scrollbars
        self.requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure status tags
        self.requests_tree.tag_configure('pending', background='#fff3cd')
        self.requests_tree.tag_configure('approved', background='#d4edda')
        self.requests_tree.tag_configure('rejected', background='#f8d7da')
        self.requests_tree.tag_configure('cancelled', background='#e2e3e5')

        # Bind double-click
        self.requests_tree.bind('<Double-1>', self._view_request_details)

        # Context menu
        self.request_menu = tk.Menu(self.requests_tree, tearoff=0)
        self.request_menu.add_command(label=_t('gui.staff.staff_hr.leave_management.menus.view_details', default="View Details"), command=self._view_request_details)
        self.request_menu.add_command(label=_t('gui.staff.staff_hr.leave_management.menus.cancel_request', default="Cancel Request"), command=self._cancel_request)
        self.requests_tree.bind('<Button-3>', self._show_request_menu)

        # Load data
        self._load_requests()

    def _create_balances_tab(self):
        """Create the leave balances tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.leave_management.tabs.my_balances', default="My Balances"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.leave_management.labels.leave_balances', default="Leave Balances"), style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.refresh', default="Refresh"), command=self._load_balances).pack(side=tk.RIGHT, padx=5)

        # Year selector
        year_frame = ttk.Frame(tab)
        year_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(year_frame, text=_t('gui.staff.staff_hr.leave_management.labels.year', default="Year:")).pack(side=tk.LEFT, padx=5)
        current_year = datetime.now().year
        self.balance_year = ttk.Combobox(year_frame, values=[str(y) for y in range(current_year - 2, current_year + 2)], width=8)
        self.balance_year.set(str(current_year))
        self.balance_year.pack(side=tk.LEFT, padx=5)
        self.balance_year.bind('<<ComboboxSelected>>', lambda e: self._load_balances())

        # Balances treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Leave Type', 'Allocated', 'Used', 'Carried Over', 'Remaining',
                   'Bank Holidays', 'Pending', 'Carry Expires')
        self.balances_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.balances_tree.heading(col, text=col)
            self.balances_tree.column(col, width=120, anchor=tk.CENTER)

        self.balances_tree.pack(fill=tk.BOTH, expand=True)

        # Summary frame
        summary_frame = ttk.LabelFrame(tab, text=_t('gui.staff.staff_hr.leave_management.labels.summary', default="Summary"), padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_allocated_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.leave_management.labels.total_allocated_0_days', default="Total Allocated: 0 days"))
        self.total_allocated_label.pack(side=tk.LEFT, padx=20)
        self.total_used_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.leave_management.labels.total_used_0_days', default="Total Used: 0 days"))
        self.total_used_label.pack(side=tk.LEFT, padx=20)
        self.total_remaining_label = ttk.Label(summary_frame, text=_t('gui.staff.staff_hr.leave_management.labels.total_remaining_0_days', default="Total Remaining: 0 days"))
        self.total_remaining_label.pack(side=tk.LEFT, padx=20)

        self._load_balances()

    def _create_approvals_tab(self):
        """Create the approvals tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.leave_management.tabs.pending_approvals', default="Pending Approvals"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.leave_management.labels.pending_leave_requests', default="Pending Leave Requests"), style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.approve_selected', default="Approve Selected"), command=self._approve_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.reject_selected', default="Reject Selected"), command=self._reject_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.refresh', default="Refresh"), command=self._load_pending_approvals).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        columns = ('ID', 'Employee', 'Type', 'Start', 'End', 'Days', 'Reason', 'Submitted')
        self.approvals_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                           yscrollcommand=y_scroll.set)

        y_scroll.config(command=self.approvals_tree.yview)

        col_widths = {'ID': 50, 'Employee': 120, 'Type': 100, 'Start': 100,
                      'End': 100, 'Days': 50, 'Reason': 200, 'Submitted': 100}
        for col in columns:
            self.approvals_tree.heading(col, text=col)
            self.approvals_tree.column(col, width=col_widths.get(col, 100))

        self.approvals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click
        self.approvals_tree.bind('<Double-1>', self._show_approval_dialog)

        self._load_pending_approvals()

    def _create_calendar_tab(self):
        """Create the leave calendar tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t('gui.staff.staff_hr.leave_management.tabs.leave_calendar', default="Leave Calendar"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text=_t('gui.staff.staff_hr.leave_management.labels.team_leave_calendar', default="Team Leave Calendar"), style='Header.TLabel').pack(side=tk.LEFT)

        # Month/Year selector
        nav_frame = ttk.Frame(header_frame)
        nav_frame.pack(side=tk.RIGHT)

        ttk.Button(nav_frame, text="<", width=3, command=self._prev_month).pack(side=tk.LEFT, padx=2)

        self.calendar_month = tk.StringVar(value=datetime.now().strftime("%B %Y"))
        ttk.Label(nav_frame, textvariable=self.calendar_month, width=15, anchor=tk.CENTER).pack(side=tk.LEFT, padx=10)

        ttk.Button(nav_frame, text=">", width=3, command=self._next_month).pack(side=tk.LEFT, padx=2)

        # Calendar display
        self.calendar_frame = ttk.Frame(tab)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.current_calendar_date = datetime.now().replace(day=1)
        self._render_calendar()

    def _load_requests(self):
        """Load leave requests for current user."""
        try:
            self.requests_tree.delete(*self.requests_tree.get_children())

            status_filter = self.status_filter.get()
            year_filter = self.year_filter.get()
            rows = LeaveManager.get_requests(
                self.me, status=None if status_filter == 'All' else status_filter.lower(),
                year=int(year_filter) if year_filter else None, limit=500)
            for row in rows:
                status = row.get('status') or ''
                values = (row['request_id'], row['leave_type_name'], row['start_date'],
                          row['end_date'], f"{float(row['total_days'] or 0):.1f}",
                          status.capitalize(), (row.get('created_at') or '')[:10],
                          row.get('approved_by') or '')
                self.requests_tree.insert('', 'end', values=values, tags=(status,))

            self._update_status(f"Loaded {len(self.requests_tree.get_children())} requests")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to load requests: {e}")

    def _load_balances(self):
        """Load leave balances for current user."""
        try:
            self.balances_tree.delete(*self.balances_tree.get_children())

            year = int(self.balance_year.get())
            total_allocated = 0
            total_used = 0
            total_remaining = 0

            for row in LeaveManager.get_balance(self.me, year):
                allocated = float(row.get('allocated_days') or 0)
                used = float(row.get('used_days') or 0)
                carried = float(row.get('carried_over') or 0) - \
                    float(row.get('carry_over_expired') or 0)
                bank = float(row.get('bank_holiday_days') or 0)
                remaining = float(row.get('remaining_days') or 0)

                self.balances_tree.insert('', 'end', values=(
                    row['leave_type_name'], f"{allocated:.1f}", f"{used:.1f}",
                    f"{carried:.1f}", f"{remaining:.1f}", f"{bank:.1f}",
                    f"{float(row.get('pending_days') or 0):.1f}",
                    row.get('carry_over_expires') or ''
                ))

                total_allocated += allocated
                total_used += used
                total_remaining += remaining

            self.total_allocated_label.config(text=f"Total Allocated: {total_allocated:.1f} days")
            self.total_used_label.config(text=f"Total Used: {total_used:.1f} days")
            self.total_remaining_label.config(text=f"Total Remaining: {total_remaining:.1f} days")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to load balances: {e}")

    def _load_pending_approvals(self):
        """Load the pending requests the signed-in person may approve."""
        try:
            self.approvals_tree.delete(*self.approvals_tree.get_children())

            for row in LeaveManager.get_pending_approvals(self.me, actor=self.actor):
                name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
                values = (row['request_id'], name or row['user_id'], row['leave_type_name'],
                          row['start_date'], row['end_date'],
                          f"{float(row['total_days'] or 0):.1f}",
                          (row.get('reason') or '')[:50], (row.get('created_at') or '')[:10])
                self.approvals_tree.insert('', 'end', iid=str(row['request_id']), values=values)

            self._update_status(f"Found {len(self.approvals_tree.get_children())} pending requests")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to load pending approvals: {e}")

    def _show_request_dialog(self):
        """Show dialog to submit a new leave request."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.leave_management.windows.new_leave_request', default="New Leave Request"))
        dialog.geometry("450x560")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.leave_management.labels.submit_leave_request', default="Submit Leave Request"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Leave type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text=_t('gui.staff.staff_hr.leave_management.labels.leave_type', default="Leave Type:"), width=15, anchor=tk.W).pack(side=tk.LEFT)

        leave_types = self._get_leave_types()
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=type_var, values=list(leave_types.keys()), width=25, state='readonly')
        type_combo.pack(side=tk.LEFT, padx=5)

        # Start date
        start_frame = ttk.Frame(main_frame)
        start_frame.pack(fill=tk.X, pady=5)
        ttk.Label(start_frame, text=_t('gui.staff.staff_hr.leave_management.labels.start_date', default="Start Date:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        start_entry = ttk.Entry(start_frame, textvariable=start_var, width=27)
        start_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(start_frame, text=_t('gui.staff.staff_hr.leave_management.labels.yyyy_mm_dd', default="(YYYY-MM-DD)"), font=('Arial', 8)).pack(side=tk.LEFT)

        # End date
        end_frame = ttk.Frame(main_frame)
        end_frame.pack(fill=tk.X, pady=5)
        ttk.Label(end_frame, text=_t('gui.staff.staff_hr.leave_management.labels.end_date', default="End Date:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        end_entry = ttk.Entry(end_frame, textvariable=end_var, width=27)
        end_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(end_frame, text=_t('gui.staff.staff_hr.leave_management.labels.yyyy_mm_dd', default="(YYYY-MM-DD)"), font=('Arial', 8)).pack(side=tk.LEFT)

        # Days calculation
        days_frame = ttk.Frame(main_frame)
        days_frame.pack(fill=tk.X, pady=5)
        ttk.Label(days_frame, text=_t('gui.staff.staff_hr.leave_management.labels.total_days', default="Total Days:"), width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_label = ttk.Label(days_frame, text="0", font=('Arial', 10, 'bold'))
        days_label.pack(side=tk.LEFT, padx=5)

        half_frame = ttk.Frame(main_frame)
        half_frame.pack(fill=tk.X, pady=5)
        start_half_var = tk.BooleanVar(value=False)
        end_half_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(half_frame, text="Half day at start", variable=start_half_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(half_frame, text="Half day at end", variable=end_half_var).pack(side=tk.LEFT, padx=5)

        def update_days(*args):
            try:
                datetime.strptime(start_var.get(), "%Y-%m-%d")
                datetime.strptime(end_var.get(), "%Y-%m-%d")
                days = LeaveManager.count_days(self.me, start_var.get(), end_var.get(),
                                               start_half_var.get(), end_half_var.get())
                days_label.config(text=f"{days:g} working days")
            except ValueError:
                days_label.config(text=_t('gui.staff.staff_hr.leave_management.text.invalid_dates', default="Invalid dates"))

        start_var.trace_add('write', update_days)
        end_var.trace_add('write', update_days)
        start_half_var.trace_add('write', update_days)
        end_half_var.trace_add('write', update_days)

        # Reason
        ttk.Label(main_frame, text=_t('gui.staff.staff_hr.leave_management.labels.reason', default="Reason:"), anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        reason_text = scrolledtext.ScrolledText(main_frame, height=6, width=40)
        reason_text.pack(fill=tk.X, pady=5)

        # Error label
        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def submit_request():
            if not type_var.get():
                error_label.config(text=_t('gui.staff.staff_hr.leave_management.text.please_select_a_leave_type', default="Please select a leave type"))
                return

            try:
                start_date = datetime.strptime(start_var.get(), "%Y-%m-%d")
                end_date = datetime.strptime(end_var.get(), "%Y-%m-%d")
            except ValueError:
                error_label.config(text=_t('gui.staff.staff_hr.leave_management.text.invalid_date_format_use_yyyy_mm_dd', default="Invalid date format. Use YYYY-MM-DD"))
                return

            if end_date < start_date:
                error_label.config(text=_t('gui.staff.staff_hr.leave_management.text.end_date_must_be_after_start_date', default="End date must be after start date"))
                return

            reason = reason_text.get('1.0', tk.END).strip()
            leave_type_id = leave_types[type_var.get()]

            try:
                request_id = LeaveManager.submit_request(
                    self.me, leave_type_id, start_var.get(), end_var.get(), reason=reason,
                    start_half=start_half_var.get(), end_half=end_half_var.get(),
                    actor=self.actor)
                log_activity('create', 'leave_request', user_id=self.me,
                             details={'leave_type': type_var.get(), 'request_id': request_id})

                messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.success', default="Success"), _t('gui.staff.staff_hr.leave_management.dialogs.leave_request_submitted_successfully', default="Leave request submitted successfully!"))
                dialog.destroy()
                self._load_requests()
                self._load_balances()

            except Exception as e:
                error_label.config(text=f"Error: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.submit_request', default="Submit Request"), command=submit_request).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        update_days()

    def _get_leave_types(self) -> dict:
        """Get active leave types as {name: id} dict."""
        leave_types = {}
        try:
            for row in LeaveManager.get_leave_types():
                leave_types[row['name']] = row['leave_type_id']
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return leave_types

    def _view_request_details(self, event=None):
        """View details of selected request."""
        selection = self.requests_tree.selection()
        if not selection:
            return

        item = self.requests_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            row = LeaveManager.get_request(int(request_id), actor=self.actor)
            if row:
                details = f"""
Request ID: {row['request_id']}
Leave Type: {row['leave_type_name']}
Start Date: {row['start_date']}{' (half day)' if row.get('start_half') else ''}
End Date: {row['end_date']}{' (half day)' if row.get('end_half') else ''}
Working Days: {row['total_days']}
Status: {(row['status'] or '').capitalize()}
Reason: {row.get('reason') or 'Not specified'}
Submitted: {row.get('created_at')}
Approved By: {row.get('approved_by') or 'N/A'}
Approved Date: {row.get('approved_date') or 'N/A'}
Rejection Reason: {row.get('rejection_reason') or 'N/A'}
                """
                messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.leave_request_details', default="Leave Request Details"), details.strip())

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to load details: {e}")

    def _cancel_request(self):
        """Cancel selected leave request (pending, or approved and not yet started)."""
        selection = self.requests_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.leave_management.dialogs.please_select_a_request_to_cancel', default="Please select a request to cancel"))
            return

        item = self.requests_tree.item(selection[0])
        request_id = item['values'][0]
        status = item['values'][5].lower()

        if status not in ('pending', 'approved'):
            messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.leave_management.dialogs.only_pending_requests_can_be_cancelled', default="Only pending requests can be cancelled"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.leave_management.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.leave_management.dialogs.are_you_sure_you_want_to_cancel_this_request', default="Are you sure you want to cancel this request?")):
            return

        try:
            if not LeaveManager.cancel_request(int(request_id), self.me, actor=self.actor):
                messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"),
                                       "This request can no longer be cancelled (leave that has started cannot be).")
                return
            log_activity('update', 'leave_request', details={'action': 'cancelled', 'request_id': request_id})
            messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.success', default="Success"), _t('gui.staff.staff_hr.leave_management.dialogs.request_cancelled_successfully', default="Request cancelled successfully"))
            self._load_requests()
            self._load_balances()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to cancel request: {e}")

    def _show_request_menu(self, event):
        """Show context menu for requests."""
        item = self.requests_tree.identify_row(event.y)
        if item:
            self.requests_tree.selection_set(item)
            self.request_menu.post(event.x_root, event.y_root)

    def _approve_selected(self):
        """Approve selected leave requests."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.leave_management.dialogs.please_select_requests_to_approve', default="Please select requests to approve"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.leave_management.dialogs.confirm', default="Confirm"), f"Approve {len(selection)} selected request(s)?"):
            return

        approved, problems = 0, []
        for item_id in selection:
            request_id = int(self.approvals_tree.item(item_id)['values'][0])
            try:
                if LeaveManager.approve_request(request_id, self.me, actor=self.actor):
                    approved += 1
                    log_activity('update', 'leave_request',
                                 details={'action': 'approved', 'approved_by': self.me, 'request_id': request_id})
                else:
                    problems.append(f"#{request_id}: no longer pending")
            except (PermissionError, ValueError) as e:
                problems.append(f"#{request_id}: {e}")
            except Exception as e:
                logger.exception("leave approval failed")
                problems.append(f"#{request_id}: {e}")

        text = f"Approved {approved} request(s)"
        if problems:
            text += "\n\nNot approved:\n" + "\n".join(problems)
        messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.success', default="Success"), text)
        self._load_pending_approvals()

    def _reject_selected(self):
        """Reject selected leave requests."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.leave_management.dialogs.please_select_requests_to_reject', default="Please select requests to reject"))
            return

        # Ask for rejection reason
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.leave_management.windows.rejection_reason', default="Rejection Reason"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.leave_management.labels.please_provide_a_reason_for_rejection', default="Please provide a reason for rejection:"), padding=10).pack()
        reason_text = scrolledtext.ScrolledText(dialog, height=5, width=40)
        reason_text.pack(padx=10, pady=5)

        def reject():
            reason = reason_text.get('1.0', tk.END).strip()
            if not reason:
                messagebox.showwarning(_t('gui.staff.staff_hr.leave_management.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.leave_management.dialogs.please_provide_a_rejection_reason', default="Please provide a rejection reason"))
                return

            rejected, problems = 0, []
            for item_id in selection:
                request_id = int(self.approvals_tree.item(item_id)['values'][0])
                try:
                    if LeaveManager.reject_request(request_id, self.me, reason, actor=self.actor):
                        rejected += 1
                        log_activity('update', 'leave_request',
                                     details={'action': 'rejected', 'rejected_by': self.me, 'request_id': request_id})
                except (PermissionError, ValueError) as e:
                    problems.append(f"#{request_id}: {e}")
                except Exception as e:
                    logger.exception("leave rejection failed")
                    problems.append(f"#{request_id}: {e}")

            text = f"Rejected {rejected} request(s)"
            if problems:
                text += "\n\nNot rejected:\n" + "\n".join(problems)
            messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.success', default="Success"), text)
            dialog.destroy()
            self._load_pending_approvals()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.reject', default="Reject"), command=reject).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _show_approval_dialog(self, event=None):
        """Show detailed approval dialog."""
        selection = self.approvals_tree.selection()
        if not selection:
            return

        item = self.approvals_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            row = LeaveManager.get_request(int(request_id), actor=self.actor)
            if not row:
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.staff.staff_hr.leave_management.windows.review_leave_request', default="Review Leave Request"))
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t('gui.staff.staff_hr.leave_management.labels.leave_request_details', default="Leave Request Details"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

            details_frame = ttk.Frame(main_frame)
            details_frame.pack(fill=tk.X)

            balance = LeaveManager.get_balance_for_type(row['user_id'], row['leave_type_id'])
            details = [
                ("Employee:", item['values'][1]),
                ("Leave Type:", row['leave_type_name']),
                ("Start Date:", row['start_date']),
                ("End Date:", row['end_date']),
                ("Working Days:", f"{float(row['total_days']):.1f}" if row['total_days'] else "N/A"),
                ("Remaining:", f"{balance['remaining_days']:.1f} days" if balance else "N/A"),
                ("Reason:", row.get('reason') or "Not specified"),
            ]

            for label, value in details:
                row_frame = ttk.Frame(details_frame)
                row_frame.pack(fill=tk.X, pady=2)
                ttk.Label(row_frame, text=label, width=15, anchor=tk.W, font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
                ttk.Label(row_frame, text=str(value), anchor=tk.W, wraplength=350).pack(side=tk.LEFT, fill=tk.X)

            # Action buttons
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(pady=30)

            def approve():
                self.approvals_tree.selection_set(selection[0])
                dialog.destroy()
                self._approve_selected()

            def reject():
                self.approvals_tree.selection_set(selection[0])
                dialog.destroy()
                self._reject_selected()

            ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.approve', default="Approve"), command=approve, width=15).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.reject', default="Reject"), command=reject, width=15).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.leave_management.buttons.close', default="Close"), command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=10)

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to load request details: {e}")

    def _export_requests(self):
        """Export leave requests to CSV."""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"leave_requests_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Type', 'Start Date', 'End Date', 'Days', 'Status', 'Submitted', 'Approved By'])

                for item_id in self.requests_tree.get_children():
                    item = self.requests_tree.item(item_id)
                    writer.writerow(item['values'])

            messagebox.showinfo(_t('gui.staff.staff_hr.leave_management.dialogs.success', default="Success"), f"Exported to {filename}")

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to export: {e}")

    def _render_calendar(self):
        """Render the leave calendar."""
        # Clear existing content
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Update month label
        self.calendar_month.set(self.current_calendar_date.strftime("%B %Y"))

        # Day headers
        header_frame = ttk.Frame(self.calendar_frame)
        header_frame.pack(fill=tk.X, pady=5)

        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for day in days:
            ttk.Label(header_frame, text=day, width=15, anchor=tk.CENTER,
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=1)

        # Get leave data for the month
        leave_data = self._get_month_leaves()

        # Calendar grid
        cal_frame = ttk.Frame(self.calendar_frame)
        cal_frame.pack(fill=tk.BOTH, expand=True)

        import calendar
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(self.current_calendar_date.year, self.current_calendar_date.month)

        for week in month_days:
            week_frame = ttk.Frame(cal_frame)
            week_frame.pack(fill=tk.X, pady=1)

            for day in week:
                day_frame = ttk.Frame(week_frame, relief=tk.RIDGE, borderwidth=1)
                day_frame.pack(side=tk.LEFT, padx=1, fill=tk.BOTH, expand=True)

                if day == 0:
                    tk.Label(day_frame, text="", width=15, height=4).pack()
                else:
                    ttk.Label(day_frame, text=str(day), anchor=tk.NW, font=('Arial', 9, 'bold')).pack(anchor=tk.NW)

                    # Show leaves for this day
                    date_str = f"{self.current_calendar_date.year}-{self.current_calendar_date.month:02d}-{day:02d}"
                    if date_str in leave_data:
                        for leave in leave_data[date_str][:3]:  # Show max 3
                            ttk.Label(day_frame, text=leave, font=('Arial', 7),
                                      background='#d4edda', wraplength=100).pack(fill=tk.X, padx=1)

    def _get_month_leaves(self) -> dict:
        """Get approved leaves for current calendar month."""
        leave_data = {}
        try:
            year = self.current_calendar_date.year
            month = self.current_calendar_date.month

            for row in LeaveManager.get_calendar(month=month, year=year, actor=self.actor):
                start = datetime.strptime(row['start_date'], "%Y-%m-%d")
                end = datetime.strptime(row['end_date'], "%Y-%m-%d")
                name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip() \
                    or row['user_id']
                current = start

                while current <= end:
                    date_str = current.strftime("%Y-%m-%d")
                    if date_str not in leave_data:
                        leave_data[date_str] = []
                    leave_data[date_str].append(f"{name[:14]} ({row['leave_type_name'][:10]})")
                    current += timedelta(days=1)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        return leave_data

    def _prev_month(self):
        """Go to previous month in calendar."""
        if self.current_calendar_date.month == 1:
            self.current_calendar_date = self.current_calendar_date.replace(year=self.current_calendar_date.year - 1, month=12)
        else:
            self.current_calendar_date = self.current_calendar_date.replace(month=self.current_calendar_date.month - 1)
        self._render_calendar()

    def _next_month(self):
        """Go to next month in calendar."""
        if self.current_calendar_date.month == 12:
            self.current_calendar_date = self.current_calendar_date.replace(year=self.current_calendar_date.year + 1, month=1)
        else:
            self.current_calendar_date = self.current_calendar_date.replace(month=self.current_calendar_date.month + 1)
        self._render_calendar()

    def _update_status(self, message: str):
        """Update status bar message."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.config(text=message)


def launch_leave_management_gui(root, auth):
    """Launch Leave Management GUI."""
    try:
        return LeaveManagementGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t('gui.staff.staff_hr.leave_management.dialogs.error', default="Error"), f"Failed to launch Leave Management: {e}")
        return None
