"""
Grant Budget Management GUI

Provides interface for:
- Budget overview with per-category allocation tracking
- Expense submission and tracking
- Funding threshold alerts
- Budget transfer requests
- Admin expense/transfer approval and category management
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grant_budget_manager import GrantBudgetManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, validate_currency_entry, show_validation_error
)


class GrantBudgetGUI:
    """GUI for grant budget management."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        # Grant application mapping: display label -> grant_application_id
        self.grant_map = {}

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Grant Budget Management")
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
        notebook.add(self.tab_frame, text="Grant Budgets")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Grant Budget Management")
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

        self._load_grant_map()

        self._create_budget_overview_tab()
        self._create_expenses_tab()
        self._create_alerts_tab()
        self._create_transfers_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_admin_tab()

    # ==================== GRANT MAP ====================

    def _load_grant_map(self):
        """Load approved grant applications into the grant_map."""
        self.grant_map = {}
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT grant_application_id, title FROM grant_applications WHERE status='approved'"
                ).fetchall()
                for row in rows:
                    r = dict(row)
                    label = f"{r.get('title', '')} (#{r.get('grant_application_id')})"
                    self.grant_map[label] = r.get('grant_application_id')
        except Exception:
            pass

    def _get_grant_combo_values(self):
        """Return the list of display labels for the grant combo."""
        return list(self.grant_map.keys())

    def _populate_grant_combo(self, combo, include_all=False):
        """Populate a combobox with grant labels and optionally an 'All' entry."""
        self._load_grant_map()
        values = self._get_grant_combo_values()
        if include_all:
            values = ['All'] + values
        combo['values'] = values
        if values:
            combo.current(0)

    def _get_selected_grant_id(self, combo):
        """Get the grant_application_id from a grant combobox selection."""
        selected = combo.get()
        if selected == 'All':
            return None
        return self.grant_map.get(selected)

    # ==================== TAB 1: BUDGET OVERVIEW ====================

    def _create_budget_overview_tab(self):
        """Create budget overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Budget Overview")

        # Header with grant selector
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Budget Overview", style='Header.TLabel').pack(side=tk.LEFT)

        selector_frame = ttk.Frame(header_frame)
        selector_frame.pack(side=tk.RIGHT)
        ttk.Label(selector_frame, text="Grant:").pack(side=tk.LEFT, padx=5)
        self.overview_grant_combo = ttk.Combobox(selector_frame, width=35, state='readonly')
        self.overview_grant_combo.pack(side=tk.LEFT, padx=5)
        self.overview_grant_combo.bind('<<ComboboxSelected>>', lambda e: self._load_budget_overview())
        ttk.Button(selector_frame, text="Refresh", command=self._refresh_budget_overview).pack(side=tk.LEFT, padx=5)
        ttk.Button(selector_frame, text="Add Allocation",
                   command=self._add_allocation_dialog).pack(side=tk.LEFT, padx=5)

        self._populate_grant_combo(self.overview_grant_combo)

        # Summary cards frame
        self.summary_frame = ttk.LabelFrame(tab, text="Summary", padding=10)
        self.summary_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        cards_frame = ttk.Frame(self.summary_frame)
        cards_frame.pack(fill=tk.X)

        self.summary_allocated_label = ttk.Label(cards_frame, text="Allocated: £0.00",
                                                  font=('Arial', 11, 'bold'))
        self.summary_allocated_label.pack(side=tk.LEFT, padx=20)

        self.summary_spent_label = ttk.Label(cards_frame, text="Spent: £0.00",
                                              font=('Arial', 11, 'bold'))
        self.summary_spent_label.pack(side=tk.LEFT, padx=20)

        self.summary_committed_label = ttk.Label(cards_frame, text="Committed: £0.00",
                                                   font=('Arial', 11, 'bold'))
        self.summary_committed_label.pack(side=tk.LEFT, padx=20)

        self.summary_remaining_label = ttk.Label(cards_frame, text="Remaining: £0.00",
                                                   font=('Arial', 11, 'bold'))
        self.summary_remaining_label.pack(side=tk.LEFT, padx=20)

        # Per-category treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('Category', 'Allocated', 'Spent', 'Committed', 'Remaining', 'Usage %')
        self.overview_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.overview_tree.yview)

        widths = {'Category': 200, 'Allocated': 120, 'Spent': 120,
                  'Committed': 120, 'Remaining': 120, 'Usage %': 100}
        for col in columns:
            self.overview_tree.heading(col, text=col)
            self.overview_tree.column(col, width=widths.get(col, 100))

        self.overview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Color tags for usage percentage
        self.overview_tree.tag_configure('green', background='#d4edda')
        self.overview_tree.tag_configure('yellow', background='#fff3cd')
        self.overview_tree.tag_configure('red', background='#f8d7da')

        self._load_budget_overview()

    def _refresh_budget_overview(self):
        """Refresh grant combo and reload overview."""
        self._populate_grant_combo(self.overview_grant_combo)
        self._load_budget_overview()

    def _load_budget_overview(self):
        """Load budget overview for the selected grant."""
        for item in self.overview_tree.get_children():
            self.overview_tree.delete(item)

        # Reset summary labels
        self.summary_allocated_label.config(text="Allocated: £0.00")
        self.summary_spent_label.config(text="Spent: £0.00")
        self.summary_committed_label.config(text="Committed: £0.00")
        self.summary_remaining_label.config(text="Remaining: £0.00")

        grant_id = self._get_selected_grant_id(self.overview_grant_combo)
        if not grant_id:
            return

        try:
            summary = GrantBudgetManager.get_grant_budget_summary(grant_id)
        except Exception:
            return

        # Update summary cards
        self.summary_allocated_label.config(
            text=f"Allocated: £{summary.get('total_allocated', 0):,.2f}")
        self.summary_spent_label.config(
            text=f"Spent: £{summary.get('total_spent', 0):,.2f}")
        self.summary_committed_label.config(
            text=f"Committed: £{summary.get('total_committed', 0):,.2f}")
        self.summary_remaining_label.config(
            text=f"Remaining: £{summary.get('total_remaining', 0):,.2f}")

        # Populate per-category treeview
        categories = summary.get('categories', [])
        for cat in categories:
            allocated = cat.get('allocated_amount', 0)
            spent = cat.get('spent_amount', 0)
            committed = cat.get('committed_amount', 0)
            remaining = cat.get('remaining_amount', 0)

            if allocated > 0:
                usage_pct = ((spent + committed) / allocated) * 100
            else:
                usage_pct = 0.0

            # Determine color tag
            if usage_pct >= 80:
                tag = 'red'
            elif usage_pct >= 60:
                tag = 'yellow'
            else:
                tag = 'green'

            self.overview_tree.insert('', tk.END, values=(
                cat.get('category_name', ''),
                f"£{allocated:,.2f}",
                f"£{spent:,.2f}",
                f"£{committed:,.2f}",
                f"£{remaining:,.2f}",
                f"{usage_pct:.1f}%"
            ), tags=(tag,))

    def _add_allocation_dialog(self):
        """Open dialog to add a new budget allocation."""
        grant_id = self._get_selected_grant_id(self.overview_grant_combo)
        if not grant_id:
            messagebox.showinfo("Info", "Please select a grant first.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Allocation")
        dialog.geometry("450x300")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Category selector
        ttk.Label(frame, text="Category:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        category_combo = ttk.Combobox(frame, width=30, state='readonly')
        category_combo.grid(row=0, column=1, padx=10, pady=8)

        category_map = {}
        try:
            categories = GrantBudgetManager.get_categories()
        except Exception:
            categories = []

        combo_values = []
        for c in categories:
            label = f"{c.get('name', '')} (#{c.get('category_id')})"
            combo_values.append(label)
            category_map[label] = c.get('category_id')
        category_combo['values'] = combo_values
        if combo_values:
            category_combo.current(0)

        # Allocated amount
        ttk.Label(frame, text="Allocated Amount:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        amount_entry = ttk.Entry(frame, width=20)
        amount_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        # Notes
        ttk.Label(frame, text="Notes:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        notes_entry = ttk.Entry(frame, width=35)
        notes_entry.grid(row=2, column=1, padx=10, pady=8)

        def save():
            try:
                category_label = validate_combobox(category_combo, "Category")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_category_id = category_map.get(category_label)
            if not selected_category_id:
                messagebox.showerror("Error", "Please select a valid category.", parent=dialog)
                return

            try:
                amount = validate_currency_entry(amount_entry, "Allocated Amount")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            notes = notes_entry.get().strip() or None

            try:
                allocation_id = GrantBudgetManager.create_allocation(
                    grant_application_id=grant_id,
                    category_id=selected_category_id,
                    allocated_amount=amount,
                    notes=notes
                )
                messagebox.showinfo("Success",
                                    f"Allocation created. ID: {allocation_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_budget_overview()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        amount_entry.focus_set()

    # ==================== TAB 2: EXPENSES ====================

    def _create_expenses_tab(self):
        """Create expenses tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Expenses")

        # Header with filters
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Expenses", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="Grant:").pack(side=tk.LEFT, padx=5)
        self.expenses_grant_combo = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.expenses_grant_combo.pack(side=tk.LEFT, padx=5)
        self.expenses_grant_combo.bind('<<ComboboxSelected>>', lambda e: self._load_expenses())

        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.expenses_status_combo = ttk.Combobox(
            filter_frame, values=['All', 'submitted', 'approved', 'rejected'],
            width=12, state='readonly')
        self.expenses_status_combo.set('All')
        self.expenses_status_combo.pack(side=tk.LEFT, padx=5)
        self.expenses_status_combo.bind('<<ComboboxSelected>>', lambda e: self._load_expenses())

        ttk.Button(filter_frame, text="Refresh", command=self._refresh_expenses).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Submit Expense",
                   command=self._submit_expense_dialog).pack(side=tk.LEFT, padx=5)

        self._populate_grant_combo(self.expenses_grant_combo, include_all=True)

        # Expenses treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Date', 'Category', 'Description', 'Amount', 'Vendor', 'Status')
        self.expenses_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.expenses_tree.yview)

        widths = {'ID': 50, 'Date': 100, 'Category': 120, 'Description': 200,
                  'Amount': 100, 'Vendor': 150, 'Status': 100}
        for col in columns:
            self.expenses_tree.heading(col, text=col)
            self.expenses_tree.column(col, width=widths.get(col, 100))

        self.expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.expenses_tree.tag_configure('submitted', background='#fff3cd')
        self.expenses_tree.tag_configure('approved', background='#d4edda')
        self.expenses_tree.tag_configure('rejected', background='#f8d7da')

        # Double-click to view expense detail
        self.expenses_tree.bind('<Double-1>', self._view_expense_detail)

        # Cache for category names
        self._expense_category_cache = {}

        self._load_expenses()

    def _refresh_expenses(self):
        """Refresh grant combo and reload expenses."""
        self._populate_grant_combo(self.expenses_grant_combo, include_all=True)
        self._load_expenses()

    def _load_expense_category_cache(self):
        """Build a mapping of category_id -> name."""
        self._expense_category_cache = {}
        try:
            categories = GrantBudgetManager.get_categories(active_only=False)
            for c in categories:
                self._expense_category_cache[c.get('category_id')] = c.get('name', '')
        except Exception:
            pass

    def _load_expenses(self):
        """Load expenses based on current filters."""
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)

        self._load_expense_category_cache()

        grant_id = self._get_selected_grant_id(self.expenses_grant_combo)
        status_filter = self.expenses_status_combo.get()
        status = None if status_filter == 'All' else status_filter

        try:
            expenses = GrantBudgetManager.get_expenses(
                grant_application_id=grant_id,
                status=status
            )
        except Exception:
            expenses = []

        for exp in expenses:
            exp_status = exp.get('status', '').lower()
            category_name = self._expense_category_cache.get(
                exp.get('category_id'), str(exp.get('category_id', '')))

            self.expenses_tree.insert('', tk.END, values=(
                exp.get('expense_id'),
                exp.get('expense_date', ''),
                category_name,
                (exp.get('description', '') or '')[:40],
                f"£{exp.get('amount', 0):,.2f}",
                (exp.get('vendor', '') or '')[:25],
                exp_status.replace('_', ' ').title()
            ), tags=(exp_status,))

    def _view_expense_detail(self, event):
        """View expense details in a popup dialog."""
        selection = self.expenses_tree.selection()
        if not selection:
            return

        item = self.expenses_tree.item(selection[0])
        expense_id = item['values'][0]

        try:
            expense = GrantBudgetManager.get_expense(expense_id)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load expense details: {e}")
            return

        if not expense:
            messagebox.showerror("Error", "Expense not found")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Expense #{expense_id}")
        dialog.geometry("550x500")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        details_frame = ttk.LabelFrame(frame, text="Expense Details", padding=15)
        details_frame.pack(fill=tk.X, pady=(0, 10))

        category_name = self._expense_category_cache.get(
            expense.get('category_id'), str(expense.get('category_id', '')))

        fields = [
            ('Expense ID', expense.get('expense_id')),
            ('Grant Application', expense.get('grant_application_id')),
            ('Category', category_name),
            ('Description', expense.get('description', '')),
            ('Amount', f"£{expense.get('amount', 0):,.2f}"),
            ('Date', expense.get('expense_date', '')),
            ('Vendor', expense.get('vendor', '') or 'N/A'),
            ('Invoice #', expense.get('invoice_number', '') or 'N/A'),
            ('Receipt', expense.get('receipt_path', '') or 'N/A'),
            ('Status', expense.get('status', '').replace('_', ' ').title()),
            ('Submitted By', expense.get('submitted_by', '')),
            ('Approved By', expense.get('approved_by', '') or 'N/A'),
            ('Notes', expense.get('notes', '') or 'N/A'),
            ('Created', expense.get('created_at', '')),
        ]

        for i, (label, value) in enumerate(fields):
            ttk.Label(details_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i, column=0, sticky='ne', padx=(10, 5), pady=4)
            ttk.Label(details_frame, text=str(value), wraplength=350).grid(
                row=i, column=1, sticky='nw', padx=(5, 10), pady=4)

        # Close button
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _submit_expense_dialog(self):
        """Open dialog to submit a new expense."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Submit Expense")
        dialog.geometry("550x550")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Grant selector
        ttk.Label(frame, text="Grant:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        grant_combo = ttk.Combobox(frame, width=35, state='readonly')
        grant_combo.grid(row=0, column=1, padx=10, pady=8)

        grant_values = self._get_grant_combo_values()
        grant_combo['values'] = grant_values
        if grant_values:
            grant_combo.current(0)

        # Category selector
        ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        category_combo = ttk.Combobox(frame, width=30, state='readonly')
        category_combo.grid(row=1, column=1, padx=10, pady=8)

        category_map = {}
        allocation_map = {}
        try:
            categories = GrantBudgetManager.get_categories()
        except Exception:
            categories = []

        combo_values = []
        for c in categories:
            label = f"{c.get('name', '')} (#{c.get('category_id')})"
            combo_values.append(label)
            category_map[label] = c.get('category_id')
        category_combo['values'] = combo_values
        if combo_values:
            category_combo.current(0)

        # Description
        ttk.Label(frame, text="Description:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        desc_entry = ttk.Entry(frame, width=35)
        desc_entry.grid(row=2, column=1, padx=10, pady=8)

        # Amount
        ttk.Label(frame, text="Amount:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        amount_entry = ttk.Entry(frame, width=20)
        amount_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Date
        ttk.Label(frame, text="Date (YYYY-MM-DD):").grid(row=4, column=0, sticky='e', padx=10, pady=8)
        date_entry = ttk.Entry(frame, width=15)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=4, column=1, padx=10, pady=8, sticky='w')

        # Vendor
        ttk.Label(frame, text="Vendor:").grid(row=5, column=0, sticky='e', padx=10, pady=8)
        vendor_entry = ttk.Entry(frame, width=35)
        vendor_entry.grid(row=5, column=1, padx=10, pady=8)

        # Receipt path
        ttk.Label(frame, text="Receipt Path:").grid(row=6, column=0, sticky='e', padx=10, pady=8)
        receipt_entry = ttk.Entry(frame, width=35)
        receipt_entry.grid(row=6, column=1, padx=10, pady=8)

        # Invoice number
        ttk.Label(frame, text="Invoice #:").grid(row=7, column=0, sticky='e', padx=10, pady=8)
        invoice_entry = ttk.Entry(frame, width=25)
        invoice_entry.grid(row=7, column=1, padx=10, pady=8, sticky='w')

        # Notes
        ttk.Label(frame, text="Notes:").grid(row=8, column=0, sticky='e', padx=10, pady=8)
        notes_entry = ttk.Entry(frame, width=35)
        notes_entry.grid(row=8, column=1, padx=10, pady=8)

        def save():
            # Validate grant selection
            try:
                grant_label = validate_combobox(grant_combo, "Grant")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_grant_id = self.grant_map.get(grant_label)
            if not selected_grant_id:
                messagebox.showerror("Error", "Please select a valid grant.", parent=dialog)
                return

            # Validate category
            try:
                category_label = validate_combobox(category_combo, "Category")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_category_id = category_map.get(category_label)
            if not selected_category_id:
                messagebox.showerror("Error", "Please select a valid category.", parent=dialog)
                return

            # Find matching allocation for this grant + category
            allocation_id = None
            try:
                allocations = GrantBudgetManager.get_allocations(selected_grant_id)
                for a in allocations:
                    if a.get('category_id') == selected_category_id:
                        allocation_id = a.get('allocation_id')
                        break
            except Exception:
                pass

            if not allocation_id:
                messagebox.showerror("Error",
                                     "No allocation found for this grant and category. "
                                     "Please create an allocation first.",
                                     parent=dialog)
                return

            # Validate required fields
            try:
                description = validate_entry(desc_entry, "Description")
                amount = validate_currency_entry(amount_entry, "Amount")
                expense_date = validate_date_entry(date_entry, "Date")
                vendor = validate_entry(vendor_entry, "Vendor")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            receipt_path = receipt_entry.get().strip() or ''
            invoice_number = invoice_entry.get().strip() or ''
            notes = notes_entry.get().strip() or None

            try:
                expense_id = GrantBudgetManager.submit_expense(
                    grant_application_id=selected_grant_id,
                    allocation_id=allocation_id,
                    category_id=selected_category_id,
                    description=description,
                    amount=amount,
                    expense_date=expense_date,
                    vendor=vendor,
                    receipt_path=receipt_path,
                    invoice_number=invoice_number,
                    submitted_by=self._get_user_id(),
                    notes=notes
                )
                messagebox.showinfo("Success",
                                    f"Expense submitted. ID: {expense_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_expenses()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Submit", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        desc_entry.focus_set()

    # ==================== TAB 3: ALERTS ====================

    def _create_alerts_tab(self):
        """Create alerts tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Alerts")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Funding Alerts", style='Header.TLabel').pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Refresh", command=self._load_alerts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Mark Read",
                   command=self._mark_alert_read).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Resolve",
                   command=self._resolve_alert).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Check Thresholds",
                   command=self._check_thresholds).pack(side=tk.LEFT, padx=5)

        # Alerts treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Type', 'Severity', 'Message', 'Read', 'Date')
        self.alerts_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.alerts_tree.yview)

        widths = {'ID': 50, 'Type': 140, 'Severity': 80, 'Message': 350, 'Read': 60, 'Date': 150}
        for col in columns:
            self.alerts_tree.heading(col, text=col)
            self.alerts_tree.column(col, width=widths.get(col, 100))

        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Severity color tags
        self.alerts_tree.tag_configure('info', background='#cce5ff')
        self.alerts_tree.tag_configure('warning', background='#fff3cd')
        self.alerts_tree.tag_configure('critical', background='#f8d7da')

        self._load_alerts()

    def _load_alerts(self):
        """Load all funding alerts."""
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)

        try:
            alerts = GrantBudgetManager.get_alerts()
        except Exception:
            alerts = []

        for alert in alerts:
            severity = alert.get('severity', '').lower()
            is_read = 'Yes' if alert.get('is_read') else 'No'

            self.alerts_tree.insert('', tk.END, values=(
                alert.get('alert_id'),
                alert.get('alert_type', '').replace('_', ' ').title(),
                severity.title(),
                (alert.get('message', '') or '')[:60],
                is_read,
                alert.get('created_at', '')
            ), tags=(severity,))

    def _mark_alert_read(self):
        """Mark the selected alert as read."""
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an alert first.")
            return

        item = self.alerts_tree.item(selection[0])
        alert_id = item['values'][0]

        try:
            GrantBudgetManager.mark_alert_read(alert_id)
            messagebox.showinfo("Success", "Alert marked as read.")
            self._load_alerts()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _resolve_alert(self):
        """Resolve the selected alert."""
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an alert first.")
            return

        item = self.alerts_tree.item(selection[0])
        alert_id = item['values'][0]

        if not messagebox.askyesno("Confirm", "Resolve this alert?"):
            return

        try:
            GrantBudgetManager.resolve_alert(
                alert_id=alert_id,
                resolved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Alert resolved.")
            self._load_alerts()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _check_thresholds(self):
        """Check threshold alerts for all loaded grants."""
        grant_ids = list(self.grant_map.values())
        if not grant_ids:
            messagebox.showinfo("Info", "No grants available to check.")
            return

        total_alerts = 0
        for grant_id in grant_ids:
            try:
                new_alerts = GrantBudgetManager.check_threshold_alerts(grant_id)
                total_alerts += len(new_alerts)
            except Exception:
                pass

        messagebox.showinfo("Threshold Check",
                            f"Check complete. {total_alerts} new alert(s) created.")
        self._load_alerts()

    # ==================== TAB 4: TRANSFERS ====================

    def _create_transfers_tab(self):
        """Create transfers tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Transfers")

        # Header with grant filter
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Budget Transfers", style='Header.TLabel').pack(side=tk.LEFT)

        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Grant:").pack(side=tk.LEFT, padx=5)
        self.transfers_grant_combo = ttk.Combobox(filter_frame, width=25, state='readonly')
        self.transfers_grant_combo.pack(side=tk.LEFT, padx=5)
        self.transfers_grant_combo.bind('<<ComboboxSelected>>', lambda e: self._load_transfers())
        ttk.Button(filter_frame, text="Refresh", command=self._refresh_transfers).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Request Transfer",
                   command=self._request_transfer_dialog).pack(side=tk.LEFT, padx=5)

        self._populate_grant_combo(self.transfers_grant_combo, include_all=True)

        # Transfers treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'From Category', 'To Category', 'Amount', 'Reason', 'Status')
        self.transfers_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.transfers_tree.yview)

        widths = {'ID': 50, 'From Category': 150, 'To Category': 150,
                  'Amount': 100, 'Reason': 250, 'Status': 100}
        for col in columns:
            self.transfers_tree.heading(col, text=col)
            self.transfers_tree.column(col, width=widths.get(col, 100))

        self.transfers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status color tags
        self.transfers_tree.tag_configure('pending', background='#fff3cd')
        self.transfers_tree.tag_configure('approved', background='#d4edda')
        self.transfers_tree.tag_configure('rejected', background='#f8d7da')

        # Cache for allocation -> category name mapping
        self._transfer_allocation_cache = {}

        self._load_transfers()

    def _refresh_transfers(self):
        """Refresh grant combo and reload transfers."""
        self._populate_grant_combo(self.transfers_grant_combo, include_all=True)
        self._load_transfers()

    def _build_allocation_cache(self):
        """Build a mapping of allocation_id -> category_name for all grants."""
        self._transfer_allocation_cache = {}
        for grant_id in self.grant_map.values():
            try:
                allocations = GrantBudgetManager.get_allocations(grant_id)
                for a in allocations:
                    self._transfer_allocation_cache[a.get('allocation_id')] = a.get('category_name', '')
            except Exception:
                pass

    def _load_transfers(self):
        """Load transfers based on current filter."""
        for item in self.transfers_tree.get_children():
            self.transfers_tree.delete(item)

        self._build_allocation_cache()

        grant_id = self._get_selected_grant_id(self.transfers_grant_combo)

        try:
            transfers = GrantBudgetManager.get_transfers(grant_application_id=grant_id)
        except Exception:
            transfers = []

        for t in transfers:
            status = t.get('status', '').lower()
            from_name = self._transfer_allocation_cache.get(
                t.get('from_allocation_id'), str(t.get('from_allocation_id', '')))
            to_name = self._transfer_allocation_cache.get(
                t.get('to_allocation_id'), str(t.get('to_allocation_id', '')))

            self.transfers_tree.insert('', tk.END, values=(
                t.get('transfer_id'),
                from_name,
                to_name,
                f"£{t.get('amount', 0):,.2f}",
                (t.get('reason', '') or '')[:40],
                status.replace('_', ' ').title()
            ), tags=(status,))

    def _request_transfer_dialog(self):
        """Open dialog to request a budget transfer."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Request Transfer")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Grant selector
        ttk.Label(frame, text="Grant:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        grant_combo = ttk.Combobox(frame, width=35, state='readonly')
        grant_combo.grid(row=0, column=1, padx=10, pady=8)

        grant_values = self._get_grant_combo_values()
        grant_combo['values'] = grant_values
        if grant_values:
            grant_combo.current(0)

        # From Allocation
        ttk.Label(frame, text="From Allocation:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        from_combo = ttk.Combobox(frame, width=35, state='readonly')
        from_combo.grid(row=1, column=1, padx=10, pady=8)

        # To Allocation
        ttk.Label(frame, text="To Allocation:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        to_combo = ttk.Combobox(frame, width=35, state='readonly')
        to_combo.grid(row=2, column=1, padx=10, pady=8)

        # Allocation mapping for this dialog
        dialog_allocation_map = {}

        def load_allocations(event=None):
            """Populate allocation combos when grant changes."""
            dialog_allocation_map.clear()
            selected_grant_id = self.grant_map.get(grant_combo.get())
            if not selected_grant_id:
                from_combo['values'] = []
                to_combo['values'] = []
                return

            try:
                allocations = GrantBudgetManager.get_allocations(selected_grant_id)
            except Exception:
                allocations = []

            alloc_values = []
            for a in allocations:
                label = (f"{a.get('category_name', '')} "
                         f"(#{a.get('allocation_id')}) - "
                         f"Remaining: £{a.get('remaining_amount', 0):,.2f}")
                alloc_values.append(label)
                dialog_allocation_map[label] = a.get('allocation_id')

            from_combo['values'] = alloc_values
            to_combo['values'] = alloc_values
            if alloc_values:
                from_combo.current(0)
                if len(alloc_values) > 1:
                    to_combo.current(1)
                else:
                    to_combo.current(0)

        grant_combo.bind('<<ComboboxSelected>>', load_allocations)
        load_allocations()

        # Amount
        ttk.Label(frame, text="Amount:").grid(row=3, column=0, sticky='e', padx=10, pady=8)
        amount_entry = ttk.Entry(frame, width=20)
        amount_entry.grid(row=3, column=1, padx=10, pady=8, sticky='w')

        # Reason
        ttk.Label(frame, text="Reason:").grid(row=4, column=0, sticky='ne', padx=10, pady=8)
        reason_entry = ttk.Entry(frame, width=35)
        reason_entry.grid(row=4, column=1, padx=10, pady=8)

        def save():
            # Validate grant
            try:
                grant_label = validate_combobox(grant_combo, "Grant")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            selected_grant_id = self.grant_map.get(grant_label)
            if not selected_grant_id:
                messagebox.showerror("Error", "Please select a valid grant.", parent=dialog)
                return

            # Validate from allocation
            try:
                from_label = validate_combobox(from_combo, "From Allocation")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            from_allocation_id = dialog_allocation_map.get(from_label)
            if not from_allocation_id:
                messagebox.showerror("Error", "Please select a valid source allocation.", parent=dialog)
                return

            # Validate to allocation
            try:
                to_label = validate_combobox(to_combo, "To Allocation")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            to_allocation_id = dialog_allocation_map.get(to_label)
            if not to_allocation_id:
                messagebox.showerror("Error", "Please select a valid destination allocation.", parent=dialog)
                return

            if from_allocation_id == to_allocation_id:
                messagebox.showerror("Error",
                                     "Source and destination allocations must be different.",
                                     parent=dialog)
                return

            # Validate amount and reason
            try:
                amount = validate_currency_entry(amount_entry, "Amount")
                reason = validate_entry(reason_entry, "Reason")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            try:
                transfer_id = GrantBudgetManager.request_transfer(
                    grant_application_id=selected_grant_id,
                    from_allocation_id=from_allocation_id,
                    to_allocation_id=to_allocation_id,
                    amount=amount,
                    reason=reason,
                    requested_by=self._get_user_id()
                )
                messagebox.showinfo("Success",
                                    f"Transfer requested. ID: {transfer_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_transfers()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Request", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        amount_entry.focus_set()

    # ==================== TAB 5: ADMIN ====================

    def _create_admin_tab(self):
        """Create admin tab for budget administration (admin only)."""
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

        # ---- Expense Approval Section ----
        expense_frame = ttk.LabelFrame(scroll_frame, text="Expense Approval Queue", padding=15)
        expense_frame.pack(fill=tk.X, padx=10, pady=10)

        expense_btn_frame = ttk.Frame(expense_frame)
        expense_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(expense_btn_frame, text="Refresh",
                   command=self._load_admin_expenses).pack(side=tk.LEFT, padx=5)
        ttk.Button(expense_btn_frame, text="Approve",
                   command=self._approve_expense).pack(side=tk.LEFT, padx=5)
        ttk.Button(expense_btn_frame, text="Reject",
                   command=self._reject_expense).pack(side=tk.LEFT, padx=5)

        # Expenses treeview
        expense_tree_frame = ttk.Frame(expense_frame)
        expense_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll = ttk.Scrollbar(expense_tree_frame, orient=tk.VERTICAL)
        admin_exp_columns = ('ID', 'Grant', 'Description', 'Amount', 'Vendor', 'Submitted By', 'Date')
        self.admin_expenses_tree = ttk.Treeview(
            expense_tree_frame, columns=admin_exp_columns, show='headings',
            yscrollcommand=y_scroll.set, height=8)
        y_scroll.config(command=self.admin_expenses_tree.yview)

        admin_exp_widths = {'ID': 50, 'Grant': 80, 'Description': 200, 'Amount': 100,
                            'Vendor': 120, 'Submitted By': 120, 'Date': 100}
        for col in admin_exp_columns:
            self.admin_expenses_tree.heading(col, text=col)
            self.admin_expenses_tree.column(col, width=admin_exp_widths.get(col, 100))

        self.admin_expenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Category Management Section ----
        category_frame = ttk.LabelFrame(scroll_frame, text="Category Management", padding=15)
        category_frame.pack(fill=tk.X, padx=10, pady=10)

        cat_btn_frame = ttk.Frame(category_frame)
        cat_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(cat_btn_frame, text="Refresh",
                   command=self._load_admin_categories).pack(side=tk.LEFT, padx=5)
        ttk.Button(cat_btn_frame, text="Add Category",
                   command=self._add_category_dialog).pack(side=tk.LEFT, padx=5)

        # Categories treeview
        cat_tree_frame = ttk.Frame(category_frame)
        cat_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll_cat = ttk.Scrollbar(cat_tree_frame, orient=tk.VERTICAL)
        cat_columns = ('ID', 'Name', 'Description', 'Sort Order', 'Active')
        self.admin_categories_tree = ttk.Treeview(
            cat_tree_frame, columns=cat_columns, show='headings',
            yscrollcommand=y_scroll_cat.set, height=6)
        y_scroll_cat.config(command=self.admin_categories_tree.yview)

        cat_widths = {'ID': 50, 'Name': 180, 'Description': 250, 'Sort Order': 80, 'Active': 60}
        for col in cat_columns:
            self.admin_categories_tree.heading(col, text=col)
            self.admin_categories_tree.column(col, width=cat_widths.get(col, 100))

        self.admin_categories_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll_cat.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Transfer Approval Section ----
        transfer_frame = ttk.LabelFrame(scroll_frame, text="Transfer Approval", padding=15)
        transfer_frame.pack(fill=tk.X, padx=10, pady=10)

        transfer_btn_frame = ttk.Frame(transfer_frame)
        transfer_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(transfer_btn_frame, text="Refresh",
                   command=self._load_admin_transfers).pack(side=tk.LEFT, padx=5)
        ttk.Button(transfer_btn_frame, text="Approve",
                   command=self._approve_transfer).pack(side=tk.LEFT, padx=5)
        ttk.Button(transfer_btn_frame, text="Reject",
                   command=self._reject_transfer).pack(side=tk.LEFT, padx=5)

        # Pending transfers treeview
        transfer_tree_frame = ttk.Frame(transfer_frame)
        transfer_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        y_scroll_tr = ttk.Scrollbar(transfer_tree_frame, orient=tk.VERTICAL)
        admin_tr_columns = ('ID', 'Grant', 'From', 'To', 'Amount', 'Reason', 'Requested By')
        self.admin_transfers_tree = ttk.Treeview(
            transfer_tree_frame, columns=admin_tr_columns, show='headings',
            yscrollcommand=y_scroll_tr.set, height=6)
        y_scroll_tr.config(command=self.admin_transfers_tree.yview)

        admin_tr_widths = {'ID': 50, 'Grant': 80, 'From': 130, 'To': 130,
                           'Amount': 100, 'Reason': 200, 'Requested By': 120}
        for col in admin_tr_columns:
            self.admin_transfers_tree.heading(col, text=col)
            self.admin_transfers_tree.column(col, width=admin_tr_widths.get(col, 100))

        self.admin_transfers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll_tr.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self._load_admin_expenses()
        self._load_admin_categories()
        self._load_admin_transfers()

    def _load_admin_expenses(self):
        """Load submitted expenses for approval."""
        for item in self.admin_expenses_tree.get_children():
            self.admin_expenses_tree.delete(item)

        try:
            expenses = GrantBudgetManager.get_expenses(status='submitted')
        except Exception:
            expenses = []

        for exp in expenses:
            self.admin_expenses_tree.insert('', tk.END, values=(
                exp.get('expense_id'),
                exp.get('grant_application_id', ''),
                (exp.get('description', '') or '')[:35],
                f"£{exp.get('amount', 0):,.2f}",
                (exp.get('vendor', '') or '')[:20],
                exp.get('submitted_by', ''),
                exp.get('expense_date', '')
            ))

    def _approve_expense(self):
        """Approve the selected expense."""
        selection = self.admin_expenses_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an expense to approve.")
            return

        item = self.admin_expenses_tree.item(selection[0])
        expense_id = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Approve expense #{expense_id}?"):
            return

        try:
            GrantBudgetManager.approve_expense(
                expense_id=expense_id,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Expense approved.")
            self._load_admin_expenses()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_expense(self):
        """Reject the selected expense."""
        selection = self.admin_expenses_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an expense to reject.")
            return

        item = self.admin_expenses_tree.item(selection[0])
        expense_id = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Reject expense #{expense_id}?"):
            return

        try:
            GrantBudgetManager.reject_expense(
                expense_id=expense_id,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Expense rejected.")
            self._load_admin_expenses()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_admin_categories(self):
        """Load all categories into the admin categories treeview."""
        for item in self.admin_categories_tree.get_children():
            self.admin_categories_tree.delete(item)

        try:
            categories = GrantBudgetManager.get_categories(active_only=False)
        except Exception:
            categories = []

        for c in categories:
            self.admin_categories_tree.insert('', tk.END, values=(
                c.get('category_id'),
                c.get('name', ''),
                (c.get('description', '') or '')[:40],
                c.get('sort_order', ''),
                'Yes' if c.get('is_active') else 'No'
            ))

    def _add_category_dialog(self):
        """Open dialog to add a new budget category."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Category")
        dialog.geometry("450x280")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Name
        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        # Description
        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        desc_entry = ttk.Entry(frame, width=35)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        # Sort order
        ttk.Label(frame, text="Sort Order:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        sort_entry = ttk.Entry(frame, width=10)
        sort_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        def save():
            try:
                name = validate_entry(name_entry, "Name")
                description = validate_entry(desc_entry, "Description")
            except ValidationError as e:
                show_validation_error(e, dialog)
                return

            sort_order = None
            sort_str = sort_entry.get().strip()
            if sort_str:
                try:
                    sort_order = int(sort_str)
                except ValueError:
                    messagebox.showerror("Validation Error",
                                         "Sort Order must be an integer.", parent=dialog)
                    return

            try:
                category_id = GrantBudgetManager.create_category(
                    name=name,
                    description=description,
                    sort_order=sort_order
                )
                messagebox.showinfo("Success",
                                    f"Category created. ID: {category_id}",
                                    parent=dialog)
                dialog.destroy()
                self._load_admin_categories()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        name_entry.focus_set()

    def _load_admin_transfers(self):
        """Load pending transfers for approval."""
        for item in self.admin_transfers_tree.get_children():
            self.admin_transfers_tree.delete(item)

        self._build_allocation_cache()

        try:
            transfers = GrantBudgetManager.get_transfers(status='pending')
        except Exception:
            transfers = []

        for t in transfers:
            from_name = self._transfer_allocation_cache.get(
                t.get('from_allocation_id'), str(t.get('from_allocation_id', '')))
            to_name = self._transfer_allocation_cache.get(
                t.get('to_allocation_id'), str(t.get('to_allocation_id', '')))

            self.admin_transfers_tree.insert('', tk.END, values=(
                t.get('transfer_id'),
                t.get('grant_application_id', ''),
                from_name,
                to_name,
                f"£{t.get('amount', 0):,.2f}",
                (t.get('reason', '') or '')[:30],
                t.get('requested_by', '')
            ))

    def _approve_transfer(self):
        """Approve the selected transfer."""
        selection = self.admin_transfers_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a transfer to approve.")
            return

        item = self.admin_transfers_tree.item(selection[0])
        transfer_id = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Approve transfer #{transfer_id}?"):
            return

        try:
            GrantBudgetManager.approve_transfer(
                transfer_id=transfer_id,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Transfer approved.")
            self._load_admin_transfers()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_transfer(self):
        """Reject the selected transfer."""
        selection = self.admin_transfers_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a transfer to reject.")
            return

        item = self.admin_transfers_tree.item(selection[0])
        transfer_id = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Reject transfer #{transfer_id}?"):
            return

        try:
            GrantBudgetManager.reject_transfer(
                transfer_id=transfer_id,
                approved_by=self._get_user_id()
            )
            messagebox.showinfo("Success", "Transfer rejected.")
            self._load_admin_transfers()
        except Exception as e:
            messagebox.showerror("Error", str(e))
