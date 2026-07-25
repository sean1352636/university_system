"""
Leave Management GUI

Provides interface for:
- Viewing and submitting leave requests
- Managing leave balances
- Approving/rejecting leave requests (admin/staff)
- Leave calendar view
- Exporting leave reports
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional
import csv
import os

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.activity_logger import log_activity


class LeaveManagementGUI:
    """GUI for managing staff leave requests and balances."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Leave Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def create_as_tab(self, notebook: ttk.Notebook):
        """Create as a tab in parent notebook."""
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Leave Management")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Leave Management System")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)

        # Bottom frame with close button
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Status bar
        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
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
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()
        self._create_calendar_tab()

    def _create_requests_tab(self):
        """Create the leave requests tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Requests")

        # Header frame
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Leave Requests", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="New Request", command=self._show_request_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_requests).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export", command=self._export_requests).pack(side=tk.LEFT, padx=5)

        # Filter frame
        filter_frame = ttk.LabelFrame(tab, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_filter = ttk.Combobox(filter_frame, values=['All', 'Pending', 'Approved', 'Rejected', 'Cancelled'], width=12)
        self.status_filter.set('All')
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_requests())

        ttk.Label(filter_frame, text="Year:").pack(side=tk.LEFT, padx=15)
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
        self.request_menu.add_command(label="View Details", command=self._view_request_details)
        self.request_menu.add_command(label="Cancel Request", command=self._cancel_request)
        self.requests_tree.bind('<Button-3>', self._show_request_menu)

        # Load data
        self._load_requests()

    def _create_balances_tab(self):
        """Create the leave balances tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Balances")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Leave Balances", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_balances).pack(side=tk.RIGHT, padx=5)

        # Year selector
        year_frame = ttk.Frame(tab)
        year_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(year_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        current_year = datetime.now().year
        self.balance_year = ttk.Combobox(year_frame, values=[str(y) for y in range(current_year - 2, current_year + 2)], width=8)
        self.balance_year.set(str(current_year))
        self.balance_year.pack(side=tk.LEFT, padx=5)
        self.balance_year.bind('<<ComboboxSelected>>', lambda e: self._load_balances())

        # Balances treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Leave Type', 'Allocated', 'Used', 'Carried Over', 'Remaining')
        self.balances_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.balances_tree.heading(col, text=col)
            self.balances_tree.column(col, width=120, anchor=tk.CENTER)

        self.balances_tree.pack(fill=tk.BOTH, expand=True)

        # Summary frame
        summary_frame = ttk.LabelFrame(tab, text="Summary", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.total_allocated_label = ttk.Label(summary_frame, text="Total Allocated: 0 days")
        self.total_allocated_label.pack(side=tk.LEFT, padx=20)
        self.total_used_label = ttk.Label(summary_frame, text="Total Used: 0 days")
        self.total_used_label.pack(side=tk.LEFT, padx=20)
        self.total_remaining_label = ttk.Label(summary_frame, text="Total Remaining: 0 days")
        self.total_remaining_label.pack(side=tk.LEFT, padx=20)

        self._load_balances()

    def _create_approvals_tab(self):
        """Create the approvals tab (admin/staff only)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Pending Approvals")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Pending Leave Requests", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Approve Selected", command=self._approve_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reject Selected", command=self._reject_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_pending_approvals).pack(side=tk.LEFT, padx=5)

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
        self.notebook.add(tab, text="Leave Calendar")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Team Leave Calendar", style='Header.TLabel').pack(side=tk.LEFT)

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

            with get_connection() as conn:
                cursor = conn.cursor()

                query = '''
                    SELECT r.request_id, t.name, r.start_date, r.end_date,
                           r.total_days, r.status, r.created_at, r.approved_by
                    FROM leave_requests r
                    JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                    WHERE r.user_id = ?
                    AND strftime('%Y', r.start_date) = ?
                '''
                params = [self.current_user.get('id') or self.current_user.get('username'), year_filter]

                if status_filter != 'All':
                    query += ' AND r.status = ?'
                    params.append(status_filter.lower())

                query += ' ORDER BY r.created_at DESC'

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    status = row[5]
                    values = (row[0], row[1], row[2], row[3],
                              f"{row[4]:.1f}", status.capitalize(),
                              row[6][:10] if row[6] else '', row[7] or '')
                    self.requests_tree.insert('', 'end', values=values, tags=(status,))

            self._update_status(f"Loaded {len(self.requests_tree.get_children())} requests")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load requests: {e}")

    def _load_balances(self):
        """Load leave balances for current user."""
        try:
            self.balances_tree.delete(*self.balances_tree.get_children())

            year = int(self.balance_year.get())
            user_id = self.current_user.get('id') or self.current_user.get('username')

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get all leave types and balances
                cursor.execute('''
                    SELECT t.name,
                           COALESCE(b.allocated_days, t.max_days_per_year) as allocated,
                           COALESCE(b.used_days, 0) as used,
                           COALESCE(b.carried_over, 0) as carried
                    FROM leave_types t
                    LEFT JOIN leave_balances b ON t.leave_type_id = b.leave_type_id
                        AND b.user_id = ? AND b.year = ?
                    WHERE t.is_active = 1
                    ORDER BY t.name
                ''', (user_id, year))

                total_allocated = 0
                total_used = 0
                total_remaining = 0

                for row in cursor.fetchall():
                    allocated = row[1] or 0
                    used = row[2] or 0
                    carried = row[3] or 0
                    remaining = allocated + carried - used

                    self.balances_tree.insert('', 'end', values=(
                        row[0], f"{allocated:.1f}", f"{used:.1f}",
                        f"{carried:.1f}", f"{remaining:.1f}"
                    ))

                    total_allocated += allocated
                    total_used += used
                    total_remaining += remaining

            self.total_allocated_label.config(text=f"Total Allocated: {total_allocated:.1f} days")
            self.total_used_label.config(text=f"Total Used: {total_used:.1f} days")
            self.total_remaining_label.config(text=f"Total Remaining: {total_remaining:.1f} days")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load balances: {e}")

    def _load_pending_approvals(self):
        """Load pending leave requests for approval."""
        try:
            self.approvals_tree.delete(*self.approvals_tree.get_children())

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT r.request_id, r.user_id, t.name, r.start_date,
                           r.end_date, r.total_days, r.reason, r.created_at
                    FROM leave_requests r
                    JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                    WHERE r.status = 'pending'
                    ORDER BY r.created_at ASC
                ''')

                for row in cursor.fetchall():
                    values = (row[0], row[1], row[2], row[3], row[4],
                              f"{row[5]:.1f}", row[6][:50] if row[6] else '',
                              row[7][:10] if row[7] else '')
                    self.approvals_tree.insert('', 'end', values=values)

            self._update_status(f"Found {len(self.approvals_tree.get_children())} pending requests")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load pending approvals: {e}")

    def _show_request_dialog(self):
        """Show dialog to submit a new leave request."""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Leave Request")
        dialog.geometry("450x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Submit Leave Request", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Leave type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Leave Type:", width=15, anchor=tk.W).pack(side=tk.LEFT)

        leave_types = self._get_leave_types()
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(type_frame, textvariable=type_var, values=list(leave_types.keys()), width=25, state='readonly')
        type_combo.pack(side=tk.LEFT, padx=5)

        # Start date
        start_frame = ttk.Frame(main_frame)
        start_frame.pack(fill=tk.X, pady=5)
        ttk.Label(start_frame, text="Start Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        start_entry = ttk.Entry(start_frame, textvariable=start_var, width=27)
        start_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(start_frame, text="(YYYY-MM-DD)", font=('Arial', 8)).pack(side=tk.LEFT)

        # End date
        end_frame = ttk.Frame(main_frame)
        end_frame.pack(fill=tk.X, pady=5)
        ttk.Label(end_frame, text="End Date:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        end_entry = ttk.Entry(end_frame, textvariable=end_var, width=27)
        end_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(end_frame, text="(YYYY-MM-DD)", font=('Arial', 8)).pack(side=tk.LEFT)

        # Days calculation
        days_frame = ttk.Frame(main_frame)
        days_frame.pack(fill=tk.X, pady=5)
        ttk.Label(days_frame, text="Total Days:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        days_label = ttk.Label(days_frame, text="0", font=('Arial', 10, 'bold'))
        days_label.pack(side=tk.LEFT, padx=5)

        def update_days(*args):
            try:
                start = datetime.strptime(start_var.get(), "%Y-%m-%d")
                end = datetime.strptime(end_var.get(), "%Y-%m-%d")
                days = (end - start).days + 1
                days_label.config(text=str(max(0, days)))
            except ValueError:
                days_label.config(text="Invalid dates")

        start_var.trace_add('write', update_days)
        end_var.trace_add('write', update_days)

        # Reason
        ttk.Label(main_frame, text="Reason:", anchor=tk.W).pack(fill=tk.X, pady=(15, 5))
        reason_text = scrolledtext.ScrolledText(main_frame, height=6, width=40)
        reason_text.pack(fill=tk.X, pady=5)

        # Error label
        error_label = ttk.Label(main_frame, text="", foreground='red')
        error_label.pack(fill=tk.X, pady=5)

        def submit_request():
            if not type_var.get():
                error_label.config(text="Please select a leave type")
                return

            try:
                start_date = datetime.strptime(start_var.get(), "%Y-%m-%d")
                end_date = datetime.strptime(end_var.get(), "%Y-%m-%d")
            except ValueError:
                error_label.config(text="Invalid date format. Use YYYY-MM-DD")
                return

            if end_date < start_date:
                error_label.config(text="End date must be after start date")
                return

            total_days = (end_date - start_date).days + 1
            reason = reason_text.get('1.0', tk.END).strip()
            leave_type_id = leave_types[type_var.get()]
            user_id = self.current_user.get('id') or self.current_user.get('username')

            try:
                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO leave_requests
                        (user_id, leave_type_id, start_date, end_date, total_days, reason, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                    ''', (user_id, leave_type_id, start_var.get(), end_var.get(),
                          total_days, reason, datetime.now().isoformat()))

                log_activity('create', 'leave_request', user_id=user_id,
                             details={'leave_type': type_var.get(), 'days': total_days})

                messagebox.showinfo("Success", "Leave request submitted successfully!")
                dialog.destroy()
                self._load_requests()

            except Exception as e:
                error_label.config(text=f"Error: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Submit Request", command=submit_request).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        update_days()

    def _get_leave_types(self) -> dict:
        """Get active leave types as {name: id} dict."""
        leave_types = {}
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT leave_type_id, name FROM leave_types WHERE is_active = 1')
                for row in cursor.fetchall():
                    leave_types[row[1]] = row[0]
        except Exception:
            pass
        return leave_types

    def _view_request_details(self, event=None):
        """View details of selected request."""
        selection = self.requests_tree.selection()
        if not selection:
            return

        item = self.requests_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT r.*, t.name as leave_type
                    FROM leave_requests r
                    JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                    WHERE r.request_id = ?
                ''', (request_id,))
                row = cursor.fetchone()

            if row:
                details = f"""
Request ID: {row[0]}
Leave Type: {row[-1]}
Start Date: {row[4]}
End Date: {row[5]}
Total Days: {row[6]}
Status: {row[8].capitalize()}
Reason: {row[7] or 'Not specified'}
Submitted: {row[12]}
Approved By: {row[9] or 'N/A'}
Approved Date: {row[10] or 'N/A'}
Rejection Reason: {row[11] or 'N/A'}
                """
                messagebox.showinfo("Leave Request Details", details.strip())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load details: {e}")

    def _cancel_request(self):
        """Cancel selected leave request."""
        selection = self.requests_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a request to cancel")
            return

        item = self.requests_tree.item(selection[0])
        request_id = item['values'][0]
        status = item['values'][5].lower()

        if status != 'pending':
            messagebox.showwarning("Warning", "Only pending requests can be cancelled")
            return

        if not messagebox.askyesno("Confirm", "Are you sure you want to cancel this request?"):
            return

        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE leave_requests SET status = 'cancelled', updated_at = ?
                    WHERE request_id = ?
                ''', (datetime.now().isoformat(), request_id))

            log_activity('update', 'leave_request', details={'action': 'cancelled', 'request_id': request_id})
            messagebox.showinfo("Success", "Request cancelled successfully")
            self._load_requests()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel request: {e}")

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
            messagebox.showwarning("Warning", "Please select requests to approve")
            return

        if not messagebox.askyesno("Confirm", f"Approve {len(selection)} selected request(s)?"):
            return

        approved_by = self.current_user.get('username') or self.current_user.get('id')
        approved_date = datetime.now().isoformat()

        availability_changes: list[dict] = []
        try:
            with transaction() as conn:
                for item_id in selection:
                    item = self.approvals_tree.item(item_id)
                    request_id = item['values'][0]

                    conn.execute('''
                        UPDATE leave_requests
                        SET status = 'approved', approved_by = ?, approved_date = ?, updated_at = ?
                        WHERE request_id = ?
                    ''', (approved_by, approved_date, approved_date, request_id))

                    # Update leave balance
                    user_id = item['values'][1]
                    days = float(item['values'][5])
                    self._update_leave_balance(conn, user_id, request_id, days)

                    # Capture for the post-commit availability broadcast
                    # (#8). Subscribers (Module Scheduling, Exam,
                    # Timetable, Grade) repaint affected slots.
                    try:
                        full = conn.execute(
                            "SELECT user_id, start_date, end_date, leave_type_id "
                            "FROM leave_requests WHERE request_id = ?",
                            (request_id,),
                        ).fetchone()
                        if full:
                            availability_changes.append(dict(full))
                    except Exception:
                        pass

                    log_activity('update', 'leave_request',
                                 details={'action': 'approved', 'approved_by': approved_by, 'request_id': request_id})

            messagebox.showinfo("Success", f"Approved {len(selection)} request(s)")
            self._load_pending_approvals()

            # Bus broadcast (#8). Best-effort; never raises.
            try:
                from education_system.systems.university.services.bus.staff_hr_bus import (
                    publish_availability_change,
                )
                for r in availability_changes:
                    publish_availability_change(
                        r["user_id"], action="leave_approved",
                        start_date=r["start_date"], end_date=r["end_date"],
                        leave_type=str(r.get("leave_type_id") or ""),
                        source="leave_management",
                    )
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to approve requests: {e}")

    def _reject_selected(self):
        """Reject selected leave requests."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select requests to reject")
            return

        # Ask for rejection reason
        dialog = tk.Toplevel(self.root)
        dialog.title("Rejection Reason")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Please provide a reason for rejection:", padding=10).pack()
        reason_text = scrolledtext.ScrolledText(dialog, height=5, width=40)
        reason_text.pack(padx=10, pady=5)

        def reject():
            reason = reason_text.get('1.0', tk.END).strip()
            if not reason:
                messagebox.showwarning("Warning", "Please provide a rejection reason")
                return

            rejected_by = self.current_user.get('username') or self.current_user.get('id')

            try:
                with transaction() as conn:
                    for item_id in selection:
                        item = self.approvals_tree.item(item_id)
                        request_id = item['values'][0]

                        conn.execute('''
                            UPDATE leave_requests
                            SET status = 'rejected', rejection_reason = ?, updated_at = ?
                            WHERE request_id = ?
                        ''', (reason, datetime.now().isoformat(), request_id))

                        log_activity('update', 'leave_request',
                                     details={'action': 'rejected', 'rejected_by': rejected_by, 'request_id': request_id})

                messagebox.showinfo("Success", f"Rejected {len(selection)} request(s)")
                dialog.destroy()
                self._load_pending_approvals()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to reject requests: {e}")

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Reject", command=reject).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _update_leave_balance(self, conn, user_id, request_id, days):
        """Update leave balance when request is approved."""
        cursor = conn.cursor()

        # Get leave type from request
        cursor.execute('SELECT leave_type_id, start_date FROM leave_requests WHERE request_id = ?', (request_id,))
        result = cursor.fetchone()
        if not result:
            return

        leave_type_id = result[0]
        year = int(result[1][:4])

        # Check if balance exists
        cursor.execute('''
            SELECT balance_id, used_days FROM leave_balances
            WHERE user_id = ? AND leave_type_id = ? AND year = ?
        ''', (user_id, leave_type_id, year))

        balance = cursor.fetchone()

        if balance:
            # Update existing balance
            cursor.execute('''
                UPDATE leave_balances SET used_days = used_days + ?, updated_at = ?
                WHERE balance_id = ?
            ''', (days, datetime.now().isoformat(), balance[0]))
        else:
            # Get max days from leave type
            cursor.execute('SELECT max_days_per_year FROM leave_types WHERE leave_type_id = ?', (leave_type_id,))
            max_days = cursor.fetchone()[0] or 0

            # Create new balance record
            cursor.execute('''
                INSERT INTO leave_balances (user_id, leave_type_id, year, allocated_days, used_days)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, leave_type_id, year, max_days, days))

    def _show_approval_dialog(self, event=None):
        """Show detailed approval dialog."""
        selection = self.approvals_tree.selection()
        if not selection:
            return

        item = self.approvals_tree.item(selection[0])
        request_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT r.*, t.name as leave_type
                    FROM leave_requests r
                    JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                    WHERE r.request_id = ?
                ''', (request_id,))
                row = cursor.fetchone()

            if not row:
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Review Leave Request")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text="Leave Request Details", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

            details_frame = ttk.Frame(main_frame)
            details_frame.pack(fill=tk.X)

            details = [
                ("Employee:", row[1]),
                ("Leave Type:", row[-1]),
                ("Start Date:", row[4]),
                ("End Date:", row[5]),
                ("Total Days:", f"{float(row[6]):.1f}" if row[6] else "N/A"),
                ("Reason:", row[7] or "Not specified"),
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

            ttk.Button(btn_frame, text="Approve", command=approve, width=15).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Reject", command=reject, width=15).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Close", command=dialog.destroy, width=15).pack(side=tk.LEFT, padx=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load request details: {e}")

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

            messagebox.showinfo("Success", f"Exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

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

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT r.user_id, r.start_date, r.end_date, t.name
                    FROM leave_requests r
                    JOIN leave_types t ON r.leave_type_id = t.leave_type_id
                    WHERE r.status = 'approved'
                    AND ((strftime('%Y', r.start_date) = ? AND strftime('%m', r.start_date) = ?)
                         OR (strftime('%Y', r.end_date) = ? AND strftime('%m', r.end_date) = ?))
                ''', (str(year), f"{month:02d}", str(year), f"{month:02d}"))

                for row in cursor.fetchall():
                    start = datetime.strptime(row[1], "%Y-%m-%d")
                    end = datetime.strptime(row[2], "%Y-%m-%d")
                    current = start

                    while current <= end:
                        date_str = current.strftime("%Y-%m-%d")
                        if date_str not in leave_data:
                            leave_data[date_str] = []
                        leave_data[date_str].append(f"{row[0][:10]}")
                        current += timedelta(days=1)

        except Exception:
            pass

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
        messagebox.showerror("Error", f"Failed to launch Leave Management: {e}")
        return None
