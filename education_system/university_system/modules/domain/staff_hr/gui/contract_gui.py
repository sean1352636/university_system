"""
Contract Management GUI

Provides interface for:
- Viewing contract details
- Contract history
- Probation tracking
- Contract amendments (admin)
- Renewal management (admin)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.contract_manager import ContractManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, show_validation_error
)


class ContractGUI:
    """GUI for managing staff contracts."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Contract Management")
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
        notebook.add(self.tab_frame, text="Contracts")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Contract Management")
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
        style.configure('SubHeader.TLabel', font=('Arial', 11, 'bold'))

        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_contract_tab()
        self._create_history_tab()
        self._create_probation_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_search_tab()
            self._create_manage_tab()
            self._create_reports_tab()

    def _create_my_contract_tab(self):
        """Create my contract tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Contract")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Current Contract Details", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_contract).pack(side=tk.RIGHT, padx=5)

        # Contract details frame
        self.contract_frame = ttk.LabelFrame(tab, text="Contract Information", padding=15)
        self.contract_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create labels for contract details
        self.contract_labels = {}
        fields = [
            ('contract_id', 'Contract ID:'),
            ('contract_type', 'Contract Type:'),
            ('status', 'Status:'),
            ('start_date', 'Start Date:'),
            ('end_date', 'End Date:'),
            ('department', 'Department:'),
            ('job_title', 'Job Title:'),
            ('working_hours', 'Working Hours:'),
            ('notice_period', 'Notice Period:'),
            ('probation_end', 'Probation End:'),
        ]

        for i, (key, label) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            ttk.Label(self.contract_frame, text=label, font=('Arial', 10, 'bold')).grid(
                row=row, column=col, sticky='e', padx=(10, 5), pady=5)
            self.contract_labels[key] = ttk.Label(self.contract_frame, text="-")
            self.contract_labels[key].grid(row=row, column=col+1, sticky='w', padx=(5, 30), pady=5)

        self._load_my_contract()

    def _load_my_contract(self):
        """Load current user's contract."""
        user_id = self._get_user_id()
        contract = ContractManager.get_active_contract(user_id)

        if contract:
            self.contract_labels['contract_id'].config(text=str(contract.get('contract_id', '-')))
            self.contract_labels['contract_type'].config(text=contract.get('contract_type', '-').title())
            self.contract_labels['status'].config(text=contract.get('status', '-').title())
            self.contract_labels['start_date'].config(text=contract.get('start_date', '-'))
            self.contract_labels['end_date'].config(text=contract.get('end_date', 'Ongoing'))
            self.contract_labels['department'].config(text=contract.get('department', '-'))
            self.contract_labels['job_title'].config(text=contract.get('job_title', '-'))
            self.contract_labels['working_hours'].config(
                text=f"{contract.get('working_hours_per_week', '-')} hrs/week")
            self.contract_labels['notice_period'].config(
                text=f"{contract.get('notice_period_days', '-')} days")
            self.contract_labels['probation_end'].config(
                text=contract.get('probation_end_date', 'N/A'))
        else:
            for key in self.contract_labels:
                self.contract_labels[key].config(text="No active contract")

    def _create_history_tab(self):
        """Create contract history tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="History")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Contract History", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_history).pack(side=tk.RIGHT)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Type', 'Status', 'Start', 'End', 'Job Title', 'Department')
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show='headings',
                                         yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.history_tree.yview)

        col_widths = {'ID': 60, 'Type': 100, 'Status': 80, 'Start': 100,
                      'End': 100, 'Job Title': 150, 'Department': 150}
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=col_widths.get(col, 100))

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_tree.tag_configure('active', background='#d4edda')
        self.history_tree.tag_configure('terminated', background='#f8d7da')

        self._load_history()

    def _load_history(self):
        """Load contract history."""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        user_id = self._get_user_id()
        contracts = ContractManager.get_user_contracts(user_id, include_inactive=True)

        for c in contracts:
            tag = 'active' if c.get('status') == 'active' else 'terminated' if c.get('status') == 'terminated' else ''
            self.history_tree.insert('', tk.END, values=(
                c.get('contract_id'),
                c.get('contract_type', '').title(),
                c.get('status', '').title(),
                c.get('start_date', ''),
                c.get('end_date', 'Ongoing'),
                c.get('job_title', ''),
                c.get('department', '')
            ), tags=(tag,))

    def _create_probation_tab(self):
        """Create probation tracking tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Probation")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Probation Status", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_probation).pack(side=tk.RIGHT)

        # Status frame
        self.probation_status_frame = ttk.LabelFrame(tab, text="Current Status", padding=15)
        self.probation_status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.probation_labels = {}
        fields = [('status', 'Status:'), ('end_date', 'End Date:'), ('days_remaining', 'Days Remaining:')]

        for i, (key, label) in enumerate(fields):
            ttk.Label(self.probation_status_frame, text=label, font=('Arial', 10, 'bold')).grid(
                row=0, column=i*2, sticky='e', padx=10, pady=5)
            self.probation_labels[key] = ttk.Label(self.probation_status_frame, text="-")
            self.probation_labels[key].grid(row=0, column=i*2+1, sticky='w', padx=10, pady=5)

        # Reviews treeview
        reviews_frame = ttk.LabelFrame(tab, text="Probation Reviews", padding=10)
        reviews_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Date', 'Type', 'Reviewer', 'Rating', 'Outcome', 'Comments')
        self.reviews_tree = ttk.Treeview(reviews_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.reviews_tree.heading(col, text=col)
            self.reviews_tree.column(col, width=100)

        self.reviews_tree.pack(fill=tk.BOTH, expand=True)

        self._load_probation()

    def _load_probation(self):
        """Load probation status."""
        user_id = self._get_user_id()
        contract = ContractManager.get_active_contract(user_id)

        if contract and contract.get('probation_end_date'):
            self.probation_labels['status'].config(text="On Probation", foreground='orange')
            self.probation_labels['end_date'].config(text=contract['probation_end_date'])

            try:
                end_date = datetime.fromisoformat(contract['probation_end_date'])
                days = (end_date - datetime.now()).days
                self.probation_labels['days_remaining'].config(text=str(max(0, days)))
            except (ValueError, TypeError):
                self.probation_labels['days_remaining'].config(text='-')
        else:
            self.probation_labels['status'].config(text="Not on Probation", foreground='green')
            self.probation_labels['end_date'].config(text='-')
            self.probation_labels['days_remaining'].config(text='-')

        # Load reviews
        for item in self.reviews_tree.get_children():
            self.reviews_tree.delete(item)

        reviews = ContractManager.get_probation_reviews(user_id)
        for r in reviews:
            self.reviews_tree.insert('', tk.END, values=(
                r.get('review_date', ''),
                r.get('review_type', ''),
                r.get('reviewer_id', ''),
                f"{r.get('performance_rating', '-')}/5" if r.get('performance_rating') else '-',
                r.get('outcome', ''),
                r.get('comments', '')[:50] if r.get('comments') else ''
            ))

    def _create_search_tab(self):
        """Create contract search tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Search")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Search Contracts", style='Header.TLabel').pack(side=tk.LEFT)

        # Search filters
        filter_frame = ttk.LabelFrame(tab, text="Search Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(filter_frame, text="User/Name:").grid(row=0, column=0, padx=5, pady=5)
        self.search_term = ttk.Entry(filter_frame, width=20)
        self.search_term.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(filter_frame, text="Department:").grid(row=0, column=2, padx=5, pady=5)
        self.search_dept = ttk.Entry(filter_frame, width=15)
        self.search_dept.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(filter_frame, text="Type:").grid(row=0, column=4, padx=5, pady=5)
        self.search_type = ttk.Combobox(filter_frame, values=['', 'permanent', 'fixed-term', 'temporary', 'casual', 'contractor'], width=12)
        self.search_type.grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(filter_frame, text="Search", command=self._search_contracts).grid(row=0, column=6, padx=15, pady=5)

        # Results
        results_frame = ttk.Frame(tab)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL)
        columns = ('ID', 'User', 'Type', 'Status', 'Start', 'End', 'Job Title', 'Department')
        self.search_tree = ttk.Treeview(results_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.search_tree.yview)

        for col in columns:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, width=100)

        self.search_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.search_tree.bind('<Double-1>', self._view_contract_details)

    def _search_contracts(self):
        """Search contracts."""
        for item in self.search_tree.get_children():
            self.search_tree.delete(item)

        term = self.search_term.get().strip() or None
        dept = self.search_dept.get().strip() or None
        ctype = self.search_type.get().strip() or None

        contracts = ContractManager.search_contracts(search_term=term, department=dept, contract_type=ctype)

        for c in contracts:
            self.search_tree.insert('', tk.END, values=(
                c.get('contract_id'),
                c.get('user_id'),
                c.get('contract_type', '').title(),
                c.get('status', '').title(),
                c.get('start_date', ''),
                c.get('end_date', 'Ongoing'),
                c.get('job_title', ''),
                c.get('department', '')
            ))

    def _view_contract_details(self, event):
        """View contract details dialog."""
        selection = self.search_tree.selection()
        if not selection:
            return

        item = self.search_tree.item(selection[0])
        contract_id = item['values'][0]
        contract = ContractManager.get_contract(contract_id)

        if not contract:
            return

        # Create details dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Contract #{contract_id}")
        dialog.geometry("500x400")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ('Contract ID', contract.get('contract_id')),
            ('User ID', contract.get('user_id')),
            ('Contract Type', contract.get('contract_type', '').title()),
            ('Status', contract.get('status', '').title()),
            ('Start Date', contract.get('start_date')),
            ('End Date', contract.get('end_date', 'Ongoing')),
            ('Department', contract.get('department')),
            ('Job Title', contract.get('job_title')),
            ('Working Hours', f"{contract.get('working_hours_per_week', '-')} hrs/week"),
            ('Notice Period', f"{contract.get('notice_period_days', '-')} days"),
            ('Probation End', contract.get('probation_end_date', 'N/A')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='e', padx=10, pady=3)
            ttk.Label(frame, text=str(value)).grid(row=i, column=1, sticky='w', padx=10, pady=3)

        ttk.Button(frame, text="Close", command=dialog.destroy).grid(
            row=len(fields), column=0, columnspan=2, pady=20)

    def _create_manage_tab(self):
        """Create contract management tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Manage")

        # Create new contract section
        create_frame = ttk.LabelFrame(tab, text="Create New Contract", padding=10)
        create_frame.pack(fill=tk.X, padx=10, pady=10)

        fields_frame = ttk.Frame(create_frame)
        fields_frame.pack(fill=tk.X)

        # Row 1
        ttk.Label(fields_frame, text="User ID:").grid(row=0, column=0, padx=5, pady=5)
        self.new_user_id = ttk.Entry(fields_frame, width=15)
        self.new_user_id.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Type:").grid(row=0, column=2, padx=5, pady=5)
        self.new_type = ttk.Combobox(fields_frame, values=['permanent', 'fixed-term', 'temporary', 'casual', 'contractor'], width=12)
        self.new_type.set('permanent')
        self.new_type.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(fields_frame, text="Start Date:").grid(row=0, column=4, padx=5, pady=5)
        self.new_start = ttk.Entry(fields_frame, width=12)
        self.new_start.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.new_start.grid(row=0, column=5, padx=5, pady=5)

        # Row 2
        ttk.Label(fields_frame, text="Department:").grid(row=1, column=0, padx=5, pady=5)
        self.new_dept = ttk.Entry(fields_frame, width=15)
        self.new_dept.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Job Title:").grid(row=1, column=2, padx=5, pady=5)
        self.new_title = ttk.Entry(fields_frame, width=20)
        self.new_title.grid(row=1, column=3, columnspan=2, padx=5, pady=5, sticky='w')

        ttk.Button(fields_frame, text="Create Contract", command=self._create_contract).grid(
            row=1, column=5, padx=10, pady=5)

        # Expiring contracts section
        expiring_frame = ttk.LabelFrame(tab, text="Expiring Contracts", padding=10)
        expiring_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header = ttk.Frame(expiring_frame)
        header.pack(fill=tk.X)

        ttk.Label(header, text="Days ahead:").pack(side=tk.LEFT, padx=5)
        self.expiry_days = ttk.Spinbox(header, from_=30, to=180, width=5)
        self.expiry_days.set(90)
        self.expiry_days.pack(side=tk.LEFT, padx=5)
        ttk.Button(header, text="Refresh", command=self._load_expiring).pack(side=tk.LEFT, padx=10)

        columns = ('ID', 'User', 'Type', 'End Date', 'Days Left', 'Job Title', 'Department')
        self.expiring_tree = ttk.Treeview(expiring_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.expiring_tree.heading(col, text=col)
            self.expiring_tree.column(col, width=100)

        self.expiring_tree.pack(fill=tk.BOTH, expand=True, pady=10)

        self.expiring_tree.tag_configure('urgent', background='#f8d7da')
        self.expiring_tree.tag_configure('warning', background='#fff3cd')

        self._load_expiring()

    def _create_contract(self):
        """Create a new contract with validation."""
        validator = FormValidator(self.root)
        validator.add_required(self.new_user_id, "User ID", "user_id")
        validator.add_combobox(self.new_type, "Contract Type", "contract_type")
        validator.add_date(self.new_start, "Start Date", "start_date")
        validator.add_required(self.new_dept, "Department", "department")
        validator.add_required(self.new_title, "Job Title", "job_title")

        if not validator.validate():
            return

        values = validator.get_values()

        try:
            contract_id = ContractManager.create_contract(
                values['user_id'],
                contract_type=values['contract_type'],
                start_date=values['start_date'],
                department=values['department'],
                job_title=values['job_title']
            )
            messagebox.showinfo("Success", f"Contract created. ID: {contract_id}")
            self.new_user_id.delete(0, tk.END)
            self.new_dept.delete(0, tk.END)
            self.new_title.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_expiring(self):
        """Load expiring contracts."""
        for item in self.expiring_tree.get_children():
            self.expiring_tree.delete(item)

        try:
            days = int(self.expiry_days.get())
        except (ValueError, TypeError):
            days = 90

        contracts = ContractManager.get_expiring_contracts(days)
        today = datetime.now().date()

        for c in contracts:
            try:
                end_date = datetime.fromisoformat(c.get('end_date', '')).date()
                days_left = (end_date - today).days
            except (ValueError, TypeError):
                days_left = '-'

            tag = ''
            if isinstance(days_left, int):
                if days_left <= 14:
                    tag = 'urgent'
                elif days_left <= 30:
                    tag = 'warning'

            self.expiring_tree.insert('', tk.END, values=(
                c.get('contract_id'),
                c.get('user_id'),
                c.get('contract_type', '').title(),
                c.get('end_date', ''),
                days_left,
                c.get('job_title', ''),
                c.get('department', '')
            ), tags=(tag,))

    def _create_reports_tab(self):
        """Create reports tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Contract Statistics", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_statistics).pack(side=tk.RIGHT)

        # Statistics frame
        stats_frame = ttk.LabelFrame(tab, text="Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.stats_labels = {}
        stats_fields = [
            ('total_active', 'Total Active Contracts'),
            ('expiring_30_days', 'Expiring in 30 Days'),
            ('in_probation', 'Currently in Probation'),
        ]

        for i, (key, label) in enumerate(stats_fields):
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.stats_labels[key] = ttk.Label(frame, text="0", font=('Arial', 24, 'bold'))
            self.stats_labels[key].pack()
            ttk.Label(frame, text=label).pack()

        # By type frame
        type_frame = ttk.LabelFrame(tab, text="By Contract Type", padding=15)
        type_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Type', 'Count', 'Percentage')
        self.type_tree = ttk.Treeview(type_frame, columns=columns, show='headings', height=6)

        for col in columns:
            self.type_tree.heading(col, text=col)
            self.type_tree.column(col, width=150)

        self.type_tree.pack(fill=tk.BOTH, expand=True)

        self._load_statistics()

    def _load_statistics(self):
        """Load contract statistics."""
        stats = ContractManager.get_contract_statistics()

        self.stats_labels['total_active'].config(text=str(stats.get('total_active', 0)))
        self.stats_labels['expiring_30_days'].config(text=str(stats.get('expiring_30_days', 0)))
        self.stats_labels['in_probation'].config(text=str(stats.get('in_probation', 0)))

        # Load by type
        for item in self.type_tree.get_children():
            self.type_tree.delete(item)

        total = stats.get('total_active', 0) or 1
        for ctype, count in stats.get('by_type', {}).items():
            pct = (count / total) * 100
            self.type_tree.insert('', tk.END, values=(
                ctype.title(),
                count,
                f"{pct:.1f}%"
            ))
