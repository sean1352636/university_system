"""
Payroll Management GUI

Provides interface for:
- Viewing payslips
- Overtime logging and approval
- Allowance management (admin)
- Running payroll (admin)
- Tax configuration (admin)
- Payroll reports (admin)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_hr.services.managers.payroll_manager import PayrollManager
from education_system.university_system.modules.domain.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class PayrollGUI:
    """GUI for payroll management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Payroll")
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
        notebook.add(self.tab_frame, text="Payroll")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Payroll Management")
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

        self._create_payslips_tab()
        self._create_overtime_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_allowances_tab()
            self._create_run_payroll_tab()
            self._create_tax_config_tab()
            self._create_reports_tab()

    # ==================== TAB 1: MY PAYSLIPS ====================

    def _create_payslips_tab(self):
        """Create payslips tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Payslips")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Payslips", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_payslips).pack(side=tk.RIGHT)

        # YTD Summary
        summary_frame = ttk.LabelFrame(tab, text="Year-to-Date Summary", padding=15)
        summary_frame.pack(fill=tk.X, padx=10, pady=10)

        self.ytd_labels = {}
        for key, label in [('gross', 'Gross YTD'), ('tax', 'Tax YTD'), ('net', 'Net YTD')]:
            frame = ttk.Frame(summary_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.ytd_labels[key] = ttk.Label(frame, text="£0.00", font=('Arial', 18, 'bold'))
            self.ytd_labels[key].pack()
            ttk.Label(frame, text=label).pack()

        # Payslips list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Period', 'Date', 'Basic', 'Overtime', 'Allowances', 'Gross', 'Tax', 'NI', 'Pension', 'Net')
        self.payslips_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.payslips_tree.yview)

        widths = {
            'Period': 140, 'Date': 100, 'Basic': 90, 'Overtime': 90,
            'Allowances': 90, 'Gross': 90, 'Tax': 80, 'NI': 80, 'Pension': 80, 'Net': 90
        }
        for col in columns:
            self.payslips_tree.heading(col, text=col)
            self.payslips_tree.column(col, width=widths.get(col, 100))

        self.payslips_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_payslips()

    def _load_payslips(self):
        """Load payslips data."""
        for item in self.payslips_tree.get_children():
            self.payslips_tree.delete(item)

        records = PayrollManager.get_user_payroll_history(self._get_user_id())

        ytd_gross = 0.0
        ytd_tax = 0.0
        ytd_net = 0.0
        current_year = datetime.now().year

        for r in records:
            # Accumulate YTD totals for current year records
            period_start = r.get('period_start', '')
            if period_start and period_start[:4] == str(current_year):
                ytd_gross += r.get('gross_pay', 0) or 0
                ytd_tax += r.get('tax', 0) or 0
                ytd_net += r.get('net_pay', 0) or 0

            self.payslips_tree.insert('', tk.END, values=(
                r.get('period_name', ''),
                r.get('payment_date', r.get('period_end', '')),
                f"£{r.get('basic_salary', 0):.2f}",
                f"£{r.get('overtime_pay', 0):.2f}",
                f"£{r.get('allowances', 0):.2f}",
                f"£{r.get('gross_pay', 0):.2f}",
                f"£{r.get('tax', 0):.2f}",
                f"£{r.get('national_insurance', 0):.2f}",
                f"£{r.get('pension', 0):.2f}",
                f"£{r.get('net_pay', 0):.2f}",
            ))

        self.ytd_labels['gross'].config(text=f"£{ytd_gross:.2f}")
        self.ytd_labels['tax'].config(text=f"£{ytd_tax:.2f}")
        self.ytd_labels['net'].config(text=f"£{ytd_net:.2f}")

    # ==================== TAB 2: OVERTIME ====================

    def _create_overtime_tab(self):
        """Create overtime management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Overtime")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Overtime Management", style='Header.TLabel').pack(side=tk.LEFT)

        # Log overtime form
        form_frame = ttk.LabelFrame(tab, text="Log Overtime", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="Date:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.ot_date_entry = ttk.Entry(form_frame, width=15)
        self.ot_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.ot_date_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Hours:").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.ot_hours_entry = ttk.Entry(form_frame, width=10)
        self.ot_hours_entry.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Rate Multiplier:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.ot_rate_combo = ttk.Combobox(form_frame, values=['1.0', '1.5', '2.0'], width=10, state='readonly')
        self.ot_rate_combo.set('1.5')
        self.ot_rate_combo.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Reason:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        self.ot_reason_entry = ttk.Entry(form_frame, width=40)
        self.ot_reason_entry.grid(row=1, column=3, padx=10, pady=8, sticky='w')

        # Submit button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Submit Overtime", command=self._log_overtime).pack()

        # My overtime list
        my_ot_frame = ttk.LabelFrame(tab, text="My Overtime Entries", padding=10)
        my_ot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(my_ot_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Date', 'Hours', 'Rate', 'Status')
        self.overtime_tree = ttk.Treeview(my_ot_frame, columns=columns, show='headings',
                                          height=6, yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.overtime_tree.yview)

        widths = {'ID': 50, 'Date': 100, 'Hours': 80, 'Rate': 80, 'Status': 100}
        for col in columns:
            self.overtime_tree.heading(col, text=col)
            self.overtime_tree.column(col, width=widths.get(col, 100))

        self.overtime_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.overtime_tree.tag_configure('pending', background='#fff3cd')
        self.overtime_tree.tag_configure('approved', background='#d4edda')
        self.overtime_tree.tag_configure('rejected', background='#f8d7da')

        # Admin section: Pending Approvals
        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            admin_frame = ttk.LabelFrame(tab, text="Pending Approvals", padding=10)
            admin_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            y_scroll2 = ttk.Scrollbar(admin_frame, orient=tk.VERTICAL)
            pending_columns = ('ID', 'User', 'Date', 'Hours', 'Rate', 'Reason')
            self.pending_ot_tree = ttk.Treeview(admin_frame, columns=pending_columns, show='headings',
                                                height=5, yscrollcommand=y_scroll2.set)
            y_scroll2.config(command=self.pending_ot_tree.yview)

            widths2 = {'ID': 50, 'User': 120, 'Date': 100, 'Hours': 80, 'Rate': 80, 'Reason': 200}
            for col in pending_columns:
                self.pending_ot_tree.heading(col, text=col)
                self.pending_ot_tree.column(col, width=widths2.get(col, 100))

            self.pending_ot_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            y_scroll2.pack(side=tk.RIGHT, fill=tk.Y)

            approval_btn_frame = ttk.Frame(tab)
            approval_btn_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Button(approval_btn_frame, text="Approve Selected",
                       command=self._approve_overtime).pack(side=tk.LEFT, padx=5)
            ttk.Button(approval_btn_frame, text="Reject Selected",
                       command=self._reject_overtime).pack(side=tk.LEFT, padx=5)

        self._load_overtime()

    def _log_overtime(self):
        """Log overtime entry with validation."""
        try:
            ot_date = validate_date_entry(self.ot_date_entry, "Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        hours_str = self.ot_hours_entry.get().strip()
        if not hours_str:
            messagebox.showerror("Validation Error", "Hours is required.")
            return
        try:
            hours = float(hours_str)
            if hours <= 0:
                messagebox.showerror("Validation Error", "Hours must be greater than 0.")
                return
        except ValueError:
            messagebox.showerror("Validation Error", "Hours must be a valid number.")
            return

        try:
            rate_str = validate_combobox(self.ot_rate_combo, "Rate Multiplier")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return
        rate_multiplier = float(rate_str)

        reason = self.ot_reason_entry.get().strip() or None

        try:
            overtime_id = PayrollManager.log_overtime(
                self._get_user_id(),
                date=ot_date,
                hours=hours,
                rate_multiplier=rate_multiplier,
                reason=reason
            )
            messagebox.showinfo("Success", f"Overtime logged successfully. ID: {overtime_id}")

            # Clear form
            self.ot_hours_entry.delete(0, tk.END)
            self.ot_reason_entry.delete(0, tk.END)
            self._load_overtime()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_overtime(self):
        """Load overtime entries."""
        for item in self.overtime_tree.get_children():
            self.overtime_tree.delete(item)

        entries = PayrollManager.get_user_overtime(self._get_user_id())

        for entry in entries:
            status = entry.get('status', '').lower()
            self.overtime_tree.insert('', tk.END, values=(
                entry.get('overtime_id'),
                entry.get('date', ''),
                f"{entry.get('hours', 0):.1f}",
                f"{entry.get('rate_multiplier', 1.0):.1f}x",
                entry.get('status', '').title()
            ), tags=(status,))

        # Load pending approvals if admin
        if hasattr(self, 'pending_ot_tree'):
            for item in self.pending_ot_tree.get_children():
                self.pending_ot_tree.delete(item)

            pending = PayrollManager.get_pending_overtime()
            for entry in pending:
                self.pending_ot_tree.insert('', tk.END, values=(
                    entry.get('overtime_id'),
                    entry.get('user_id', ''),
                    entry.get('date', ''),
                    f"{entry.get('hours', 0):.1f}",
                    f"{entry.get('rate_multiplier', 1.0):.1f}x",
                    entry.get('reason', '')[:40] if entry.get('reason') else ''
                ))

    def _approve_overtime(self):
        """Approve selected overtime entry."""
        selection = self.pending_ot_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an overtime entry to approve")
            return

        item = self.pending_ot_tree.item(selection[0])
        overtime_id = item['values'][0]

        try:
            PayrollManager.approve_overtime(overtime_id, self._get_user_id())
            messagebox.showinfo("Success", "Overtime approved")
            self._load_overtime()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_overtime(self):
        """Reject selected overtime entry."""
        selection = self.pending_ot_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an overtime entry to reject")
            return

        item = self.pending_ot_tree.item(selection[0])
        overtime_id = item['values'][0]

        try:
            PayrollManager.reject_overtime(overtime_id, self._get_user_id())
            messagebox.showinfo("Success", "Overtime rejected")
            self._load_overtime()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 3: ALLOWANCES (ADMIN) ====================

    def _create_allowances_tab(self):
        """Create allowance management tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Allowances")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Allowance Management", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_allowances).pack(side=tk.RIGHT)

        # Add allowance form
        form_frame = ttk.LabelFrame(tab, text="Add Allowance", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="User ID:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.allow_user_entry = ttk.Entry(form_frame, width=20)
        self.allow_user_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Type:").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.allow_type_combo = ttk.Combobox(form_frame,
            values=['Housing', 'Transport', 'Meal', 'Phone', 'Other'], width=15, state='readonly')
        self.allow_type_combo.set('Housing')
        self.allow_type_combo.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Amount ($):").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.allow_amount_entry = ttk.Entry(form_frame, width=15)
        self.allow_amount_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Frequency:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        self.allow_freq_combo = ttk.Combobox(form_frame,
            values=['monthly', 'bi-weekly', 'weekly', 'annual'], width=15, state='readonly')
        self.allow_freq_combo.set('monthly')
        self.allow_freq_combo.grid(row=1, column=3, padx=10, pady=8, sticky='w')

        # Add button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Add Allowance", command=self._add_allowance).pack()

        # Allowances list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'User', 'Type', 'Amount', 'Frequency', 'Active')
        self.allowances_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                            yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.allowances_tree.yview)

        widths = {'ID': 50, 'User': 120, 'Type': 100, 'Amount': 100, 'Frequency': 100, 'Active': 80}
        for col in columns:
            self.allowances_tree.heading(col, text=col)
            self.allowances_tree.column(col, width=widths.get(col, 100))

        self.allowances_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.allowances_tree.tag_configure('inactive', foreground='gray')

        # Deactivate button
        deact_frame = ttk.Frame(tab)
        deact_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(deact_frame, text="Deactivate Selected",
                   command=self._deactivate_allowance).pack(side=tk.LEFT, padx=5)

        self._load_allowances()

    def _add_allowance(self):
        """Add allowance with validation."""
        try:
            user_id = validate_entry(self.allow_user_entry, "User ID")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            allowance_type = validate_combobox(self.allow_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            amount = validate_currency_entry(self.allow_amount_entry, "Amount", min_value=0.01)
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            frequency = validate_combobox(self.allow_freq_combo, "Frequency")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            allowance_id = PayrollManager.add_allowance(
                user_id=user_id,
                allowance_type=allowance_type,
                amount=amount,
                frequency=frequency,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", f"Allowance added successfully. ID: {allowance_id}")

            # Clear form
            self.allow_user_entry.delete(0, tk.END)
            self.allow_amount_entry.delete(0, tk.END)
            self._load_allowances()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_allowances(self):
        """Load all allowances."""
        for item in self.allowances_tree.get_children():
            self.allowances_tree.delete(item)

        # Get allowances - use the database connection directly to get all users' allowances
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                rows = conn.execute('''
                    SELECT * FROM payroll_allowances
                    ORDER BY user_id, allowance_type
                ''').fetchall()
                allowances = [dict(row) for row in rows]
        except Exception:
            allowances = []

        for a in allowances:
            is_active = a.get('is_active', 1)
            tag = '' if is_active else 'inactive'
            self.allowances_tree.insert('', tk.END, values=(
                a.get('allowance_id'),
                a.get('user_id', ''),
                a.get('allowance_type', ''),
                f"£{a.get('amount', 0):.2f}",
                a.get('frequency', ''),
                'Active' if is_active else 'Inactive'
            ), tags=(tag,))

    def _deactivate_allowance(self):
        """Deactivate selected allowance."""
        selection = self.allowances_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an allowance to deactivate")
            return

        item = self.allowances_tree.item(selection[0])
        allowance_id = item['values'][0]

        if not messagebox.askyesno("Confirm", "Are you sure you want to deactivate this allowance?"):
            return

        try:
            PayrollManager.deactivate_allowance(allowance_id)
            messagebox.showinfo("Success", "Allowance deactivated")
            self._load_allowances()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 4: RUN PAYROLL (ADMIN) ====================

    def _create_run_payroll_tab(self):
        """Create run payroll tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Run Payroll")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Run Payroll", style='Header.TLabel').pack(side=tk.LEFT)

        # Create new period form
        form_frame = ttk.LabelFrame(tab, text="Create New Pay Period", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.period_name_entry = ttk.Entry(form_frame, width=25)
        self.period_name_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Type:").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.period_type_combo = ttk.Combobox(form_frame,
            values=['monthly', 'bi-weekly', 'weekly'], width=15, state='readonly')
        self.period_type_combo.set('monthly')
        self.period_type_combo.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Start Date:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.period_start_entry = ttk.Entry(form_frame, width=15)
        self.period_start_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="End Date:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        self.period_end_entry = ttk.Entry(form_frame, width=15)
        self.period_end_entry.grid(row=1, column=3, padx=10, pady=8, sticky='w')

        # Row 3
        ttk.Label(form_frame, text="Payment Date:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.period_payment_entry = ttk.Entry(form_frame, width=15)
        self.period_payment_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        # Create button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=2, columnspan=2, pady=8)
        ttk.Button(btn_frame, text="Create Period", command=self._create_period).pack()

        # Existing periods list
        periods_frame = ttk.LabelFrame(tab, text="Pay Periods", padding=10)
        periods_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        y_scroll = ttk.Scrollbar(periods_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Name', 'Type', 'Start', 'End', 'Status')
        self.periods_tree = ttk.Treeview(periods_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.periods_tree.yview)

        widths = {'ID': 50, 'Name': 160, 'Type': 100, 'Start': 100, 'End': 100, 'Status': 100}
        for col in columns:
            self.periods_tree.heading(col, text=col)
            self.periods_tree.column(col, width=widths.get(col, 100))

        self.periods_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.periods_tree.tag_configure('draft', background='#e2e3e5')
        self.periods_tree.tag_configure('completed', background='#d4edda')
        self.periods_tree.tag_configure('processing', background='#fff3cd')

        # Process payroll button and results
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(action_frame, text="Process Payroll for Selected Period",
                   command=self._run_payroll).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Refresh", command=self._load_periods).pack(side=tk.LEFT, padx=5)

        self.payroll_result_label = ttk.Label(action_frame, text="", font=('Arial', 10))
        self.payroll_result_label.pack(side=tk.LEFT, padx=20)

        self._load_periods()

    def _create_period(self):
        """Create a new pay period with validation."""
        try:
            name = validate_entry(self.period_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            period_type = validate_combobox(self.period_type_combo, "Type")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            start_date = validate_date_entry(self.period_start_entry, "Start Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            end_date = validate_date_entry(self.period_end_entry, "End Date")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        payment_date_str = self.period_payment_entry.get().strip() or None
        if payment_date_str:
            try:
                payment_date = validate_date_entry(self.period_payment_entry, "Payment Date")
            except ValidationError as e:
                show_validation_error(e, self.root)
                return
        else:
            payment_date = None

        try:
            period_id = PayrollManager.create_period(
                name=name,
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                payment_date=payment_date,
                created_by=self._get_user_id()
            )
            messagebox.showinfo("Success", f"Pay period created successfully. ID: {period_id}")

            # Clear form
            self.period_name_entry.delete(0, tk.END)
            self.period_start_entry.delete(0, tk.END)
            self.period_end_entry.delete(0, tk.END)
            self.period_payment_entry.delete(0, tk.END)
            self._load_periods()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_periods(self):
        """Load pay periods."""
        for item in self.periods_tree.get_children():
            self.periods_tree.delete(item)

        periods = PayrollManager.get_periods()

        for p in periods:
            status = p.get('status', '').lower()
            self.periods_tree.insert('', tk.END, values=(
                p.get('period_id'),
                p.get('name', ''),
                p.get('period_type', ''),
                p.get('start_date', ''),
                p.get('end_date', ''),
                p.get('status', '').title()
            ), tags=(status,))

    def _run_payroll(self):
        """Run payroll for selected period."""
        selection = self.periods_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a period to process")
            return

        item = self.periods_tree.item(selection[0])
        period_id = item['values'][0]
        period_name = item['values'][1]
        period_status = item['values'][5]

        if period_status.lower() == 'completed':
            messagebox.showwarning("Warning", "This period has already been processed")
            return

        if not messagebox.askyesno("Confirm",
                f"Run payroll for period '{period_name}'?\nThis will process all active contracts."):
            return

        try:
            result = PayrollManager.run_payroll(period_id, created_by=self._get_user_id())

            if result.get('error'):
                messagebox.showerror("Error", result['error'])
                return

            summary = (
                f"Payroll Complete: {result.get('total_records', 0)} records | "
                f"Gross: £{result.get('total_gross', 0):.2f} | "
                f"Net: £{result.get('total_net', 0):.2f}"
            )
            self.payroll_result_label.config(text=summary)
            messagebox.showinfo("Success", summary)
            self._load_periods()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 5: TAX CONFIG (ADMIN) ====================

    def _create_tax_config_tab(self):
        """Create tax configuration tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Tax Config")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Tax Configuration", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_tax_brackets).pack(side=tk.RIGHT)

        # Tax brackets list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Year', 'Bracket', 'Lower', 'Upper', 'Rate', 'Allowance')
        self.tax_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                     yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.tax_tree.yview)

        widths = {'ID': 50, 'Year': 80, 'Bracket': 140, 'Lower': 100, 'Upper': 100, 'Rate': 80, 'Allowance': 100}
        for col in columns:
            self.tax_tree.heading(col, text=col)
            self.tax_tree.column(col, width=widths.get(col, 100))

        self.tax_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Add bracket form
        form_frame = ttk.LabelFrame(tab, text="Add Tax Bracket", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="Year:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.tax_year_entry = ttk.Entry(form_frame, width=12)
        self.tax_year_entry.insert(0, '2025/26')
        self.tax_year_entry.grid(row=0, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Name:").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.tax_name_entry = ttk.Entry(form_frame, width=20)
        self.tax_name_entry.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Lower Limit:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.tax_lower_entry = ttk.Entry(form_frame, width=12)
        self.tax_lower_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Upper Limit:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        self.tax_upper_entry = ttk.Entry(form_frame, width=12)
        self.tax_upper_entry.grid(row=1, column=3, padx=10, pady=8, sticky='w')

        # Row 3
        ttk.Label(form_frame, text="Rate:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        self.tax_rate_entry = ttk.Entry(form_frame, width=12)
        self.tax_rate_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Allowance:").grid(row=2, column=2, sticky='e', padx=10, pady=8)
        self.tax_allowance_entry = ttk.Entry(form_frame, width=12)
        self.tax_allowance_entry.insert(0, '0')
        self.tax_allowance_entry.grid(row=2, column=3, padx=10, pady=8, sticky='w')

        # Add button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Add Tax Bracket", command=self._add_tax_bracket).pack()

        self._load_tax_brackets()

    def _load_tax_brackets(self):
        """Load tax brackets."""
        for item in self.tax_tree.get_children():
            self.tax_tree.delete(item)

        tax_year = self.tax_year_entry.get().strip() if hasattr(self, 'tax_year_entry') else '2025/26'
        brackets = PayrollManager.get_tax_brackets(tax_year)

        for b in brackets:
            upper = b.get('upper_limit')
            upper_display = f"£{upper:,.2f}" if upper else 'Unlimited'

            self.tax_tree.insert('', tk.END, values=(
                b.get('bracket_id', b.get('id', '')),
                b.get('tax_year', ''),
                b.get('bracket_name', ''),
                f"£{b.get('lower_limit', 0):,.2f}",
                upper_display,
                f"{(b.get('rate', 0) or 0) * 100:.1f}%",
                f"£{b.get('personal_allowance', 0):,.2f}"
            ))

    def _add_tax_bracket(self):
        """Add tax bracket with validation."""
        try:
            tax_year = validate_entry(self.tax_year_entry, "Year")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            bracket_name = validate_entry(self.tax_name_entry, "Name")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        lower_str = self.tax_lower_entry.get().strip()
        if not lower_str:
            messagebox.showerror("Validation Error", "Lower Limit is required.")
            return
        try:
            lower_limit = float(lower_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Lower Limit must be a valid number.")
            return

        upper_str = self.tax_upper_entry.get().strip()
        if not upper_str:
            messagebox.showerror("Validation Error", "Upper Limit is required.")
            return
        try:
            upper_limit = float(upper_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Upper Limit must be a valid number.")
            return

        rate_str = self.tax_rate_entry.get().strip()
        if not rate_str:
            messagebox.showerror("Validation Error", "Rate is required.")
            return
        try:
            rate = float(rate_str)
        except ValueError:
            messagebox.showerror("Validation Error", "Rate must be a valid number (e.g. 0.20 for 20%).")
            return

        allowance_str = self.tax_allowance_entry.get().strip()
        try:
            personal_allowance = float(allowance_str) if allowance_str else 0
        except ValueError:
            messagebox.showerror("Validation Error", "Allowance must be a valid number.")
            return

        try:
            bracket_id = PayrollManager.create_tax_bracket(
                tax_year=tax_year,
                bracket_name=bracket_name,
                lower_limit=lower_limit,
                upper_limit=upper_limit,
                rate=rate,
                personal_allowance=personal_allowance
            )
            messagebox.showinfo("Success", f"Tax bracket created successfully. ID: {bracket_id}")

            # Clear form (except year)
            self.tax_name_entry.delete(0, tk.END)
            self.tax_lower_entry.delete(0, tk.END)
            self.tax_upper_entry.delete(0, tk.END)
            self.tax_rate_entry.delete(0, tk.END)
            self.tax_allowance_entry.delete(0, tk.END)
            self.tax_allowance_entry.insert(0, '0')
            self._load_tax_brackets()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==================== TAB 6: REPORTS (ADMIN) ====================

    def _create_reports_tab(self):
        """Create payroll reports tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Payroll Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_payroll_report).pack(side=tk.RIGHT)

        # Period selector
        selector_frame = ttk.Frame(tab)
        selector_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(selector_frame, text="Select Period:").pack(side=tk.LEFT, padx=5)
        self.report_period_combo = ttk.Combobox(selector_frame, width=30, state='readonly')
        self.report_period_combo.pack(side=tk.LEFT, padx=5)
        self.report_period_combo.bind('<<ComboboxSelected>>', lambda e: self._load_payroll_report())

        # Load periods into combobox
        self._periods_data = {}
        self._load_report_periods()

        # Summary statistics
        stats_frame = ttk.LabelFrame(tab, text="Summary Statistics", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.report_stats = {}
        for key, label in [('records', 'Total Records'), ('gross', 'Total Gross'),
                           ('deductions', 'Total Deductions'), ('net', 'Total Net')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=25, pady=10)
            self.report_stats[key] = ttk.Label(frame, text="0" if key == 'records' else "£0.00",
                                               font=('Arial', 18, 'bold'))
            self.report_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # Department breakdown
        dept_frame = ttk.LabelFrame(tab, text="By Department", padding=10)
        dept_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Department', 'Records', 'Gross', 'Net')
        self.dept_tree = ttk.Treeview(dept_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.dept_tree.heading(col, text=col)
            self.dept_tree.column(col, width=150)

        self.dept_tree.pack(fill=tk.BOTH, expand=True)

        self._load_payroll_report()

    def _load_report_periods(self):
        """Load periods into report combobox."""
        periods = PayrollManager.get_periods(status='completed')
        self._periods_data = {}

        display_values = []
        for p in periods:
            display = f"{p.get('name', '')} ({p.get('start_date', '')} - {p.get('end_date', '')})"
            self._periods_data[display] = p.get('period_id')
            display_values.append(display)

        self.report_period_combo['values'] = display_values
        if display_values:
            self.report_period_combo.set(display_values[0])

    def _load_payroll_report(self):
        """Load payroll report for selected period."""
        selected = self.report_period_combo.get()
        period_id = self._periods_data.get(selected)

        if not period_id:
            self.report_stats['records'].config(text="0")
            self.report_stats['gross'].config(text="£0.00")
            self.report_stats['deductions'].config(text="£0.00")
            self.report_stats['net'].config(text="£0.00")
            for item in self.dept_tree.get_children():
                self.dept_tree.delete(item)
            return

        summary = PayrollManager.get_payroll_summary(period_id)

        self.report_stats['records'].config(text=str(summary.get('total_records', 0)))
        self.report_stats['gross'].config(text=f"£{summary.get('total_gross', 0):.2f}")
        self.report_stats['deductions'].config(text=f"£{summary.get('total_deductions', 0):.2f}")
        self.report_stats['net'].config(text=f"£{summary.get('total_net', 0):.2f}")

        # Department breakdown
        for item in self.dept_tree.get_children():
            self.dept_tree.delete(item)

        for dept, data in summary.get('by_department', {}).items():
            self.dept_tree.insert('', tk.END, values=(
                dept,
                data.get('record_count', 0),
                f"£{data.get('gross', 0):.2f}",
                f"£{data.get('net', 0):.2f}"
            ))
