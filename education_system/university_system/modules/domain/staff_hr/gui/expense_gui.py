"""
Expense Claims GUI

Provides interface for:
- Submitting expense claims
- Viewing claim status
- Approving/rejecting claims (admin)
- Managing categories and policies (admin)
- Expense reports and analytics
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_hr.services.managers.expense_manager import ExpenseManager
from education_system.university_system.modules.domain.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_currency_entry, validate_combobox, show_validation_error
)


class ExpenseGUI:
    """GUI for managing expense claims and reimbursements."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Expense Claims")
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
        notebook.add(self.tab_frame, text="Expenses")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        """Create as standalone window."""
        self.window = tk.Toplevel(self.root)
        self.window.title("Expense Claims & Reimbursements")
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

        self._create_submit_tab()
        self._create_my_claims_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_approvals_tab()
            self._create_categories_tab()
            self._create_reports_tab()

    def _create_submit_tab(self):
        """Create submit expense claim tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Submit Claim")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Submit New Expense Claim", style='Header.TLabel').pack(side=tk.LEFT)

        # Form
        form_frame = ttk.LabelFrame(tab, text="Claim Details", padding=15)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1
        ttk.Label(form_frame, text="Category:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        self.category_combo = ttk.Combobox(form_frame, width=25, state='readonly')
        self.category_combo.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        self._load_categories_combo()

        ttk.Label(form_frame, text="Amount ($):").grid(row=0, column=2, sticky='e', padx=10, pady=8)
        self.amount_entry = ttk.Entry(form_frame, width=15)
        self.amount_entry.grid(row=0, column=3, padx=10, pady=8, sticky='w')

        # Row 2
        ttk.Label(form_frame, text="Expense Date:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        self.date_entry = ttk.Entry(form_frame, width=15)
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.date_entry.grid(row=1, column=1, padx=10, pady=8, sticky='w')

        ttk.Label(form_frame, text="Receipt:").grid(row=1, column=2, sticky='e', padx=10, pady=8)
        receipt_frame = ttk.Frame(form_frame)
        receipt_frame.grid(row=1, column=3, padx=10, pady=8, sticky='w')
        self.receipt_entry = ttk.Entry(receipt_frame, width=30)
        self.receipt_entry.pack(side=tk.LEFT)
        ttk.Button(receipt_frame, text="Browse", command=self._browse_receipt).pack(side=tk.LEFT, padx=5)

        # Row 3
        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='ne', padx=10, pady=8)
        self.description_text = tk.Text(form_frame, width=60, height=4)
        self.description_text.grid(row=2, column=1, columnspan=3, padx=10, pady=8, sticky='w')

        # Submit button
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=15)
        ttk.Button(btn_frame, text="Submit Claim", command=self._submit_claim).pack()

        # Recent submissions
        recent_frame = ttk.LabelFrame(tab, text="My Recent Submissions", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Date', 'Category', 'Amount', 'Status')
        self.recent_tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=5)

        for col in columns:
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=100)

        self.recent_tree.pack(fill=tk.BOTH, expand=True)
        self._load_recent_claims()

    def _load_categories_combo(self):
        """Load categories into combo box."""
        categories = ExpenseManager.get_all_categories()
        self.categories_data = {c['name']: c for c in categories}
        self.category_combo['values'] = [c['name'] for c in categories]
        if categories:
            self.category_combo.set(categories[0]['name'])

    def _browse_receipt(self):
        """Browse for receipt file."""
        filename = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.receipt_entry.delete(0, tk.END)
            self.receipt_entry.insert(0, filename)

    def _submit_claim(self):
        """Submit expense claim with validation."""
        # Validate category
        try:
            category_name = validate_combobox(self.category_combo, "Category")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        if category_name not in self.categories_data:
            messagebox.showerror("Error", "Please select a valid category")
            return

        category = self.categories_data[category_name]

        # Validate amount
        try:
            amount = validate_currency_entry(self.amount_entry, "Amount", min_value=0.01)
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        # Check category limit
        if category.get('max_amount') and amount > category['max_amount']:
            if not messagebox.askyesno("Warning",
                f"Amount exceeds category limit of £{category['max_amount']:.2f}. Continue?"):
                return

        # Check receipt requirement
        receipt_path = self.receipt_entry.get().strip() or None
        if category.get('requires_receipt') and not receipt_path:
            messagebox.showerror("Error", "This category requires a receipt")
            return

        # Validate date and description
        try:
            expense_date = validate_date_entry(self.date_entry, "Expense Date")
            description = validate_entry(self.description_text, "Description")
        except ValidationError as e:
            show_validation_error(e, self.root)
            return

        try:
            claim_id = ExpenseManager.create_claim(
                self._get_user_id(),
                category_id=category['category_id'],
                amount=amount,
                description=description,
                expense_date=expense_date,
                receipt_path=receipt_path
            )
            messagebox.showinfo("Success", f"Claim submitted successfully. ID: {claim_id}")

            # Clear form
            self.amount_entry.delete(0, tk.END)
            self.receipt_entry.delete(0, tk.END)
            self.description_text.delete("1.0", tk.END)
            self._load_recent_claims()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_recent_claims(self):
        """Load recent claims."""
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)

        claims = ExpenseManager.get_user_claims(self._get_user_id())
        for c in claims[:10]:
            self.recent_tree.insert('', tk.END, values=(
                c.get('claim_id'),
                c.get('expense_date', ''),
                c.get('category_name', ''),
                f"£{c.get('amount', 0):.2f}",
                c.get('status', '').title()
            ))

    def _create_my_claims_tab(self):
        """Create my claims tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Claims")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Expense Claims", style='Header.TLabel').pack(side=tk.LEFT)

        # Filter
        filter_frame = ttk.Frame(header_frame)
        filter_frame.pack(side=tk.RIGHT)
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_filter = ttk.Combobox(filter_frame,
            values=['All', 'Pending', 'Approved', 'Rejected', 'Reimbursed'], width=12, state='readonly')
        self.status_filter.set('All')
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_my_claims())
        ttk.Button(filter_frame, text="Refresh", command=self._load_my_claims).pack(side=tk.LEFT, padx=10)

        # Summary
        summary_frame = ttk.Frame(tab)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        self.summary_labels = {}
        for key, label in [('pending', 'Pending'), ('approved', 'Approved'), ('reimbursed', 'Reimbursed')]:
            frame = ttk.Frame(summary_frame)
            frame.pack(side=tk.LEFT, padx=20)
            self.summary_labels[key] = ttk.Label(frame, text="£0.00", font=('Arial', 14, 'bold'))
            self.summary_labels[key].pack()
            ttk.Label(frame, text=label).pack()

        # Claims list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'Date', 'Category', 'Amount', 'Description', 'Status', 'Submitted')
        self.claims_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.claims_tree.yview)

        widths = {'ID': 50, 'Date': 100, 'Category': 120, 'Amount': 80, 'Description': 200, 'Status': 100, 'Submitted': 100}
        for col in columns:
            self.claims_tree.heading(col, text=col)
            self.claims_tree.column(col, width=widths.get(col, 100))

        self.claims_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.claims_tree.tag_configure('pending', background='#fff3cd')
        self.claims_tree.tag_configure('approved', background='#d4edda')
        self.claims_tree.tag_configure('rejected', background='#f8d7da')
        self.claims_tree.tag_configure('reimbursed', background='#cce5ff')

        self._load_my_claims()

    def _load_my_claims(self):
        """Load my claims."""
        for item in self.claims_tree.get_children():
            self.claims_tree.delete(item)

        status = self.status_filter.get().lower()
        if status == 'all':
            status = None

        claims = ExpenseManager.get_user_claims(self._get_user_id(), status=status)

        totals = {'pending': 0, 'approved': 0, 'reimbursed': 0}

        for c in claims:
            claim_status = c.get('status', '').lower()
            if claim_status in totals:
                totals[claim_status] += c.get('amount', 0)

            self.claims_tree.insert('', tk.END, values=(
                c.get('claim_id'),
                c.get('expense_date', ''),
                c.get('category_name', ''),
                f"£{c.get('amount', 0):.2f}",
                c.get('description', '')[:40],
                c.get('status', '').title(),
                c.get('submitted_date', '')
            ), tags=(claim_status,))

        for key, total in totals.items():
            self.summary_labels[key].config(text=f"£{total:.2f}")

    def _create_approvals_tab(self):
        """Create approvals tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Approvals")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Pending Approvals", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_approvals).pack(side=tk.RIGHT)

        # Pending claims
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        columns = ('ID', 'User', 'Date', 'Category', 'Amount', 'Description', 'Receipt')
        self.approvals_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=y_scroll.set)
        y_scroll.config(command=self.approvals_tree.yview)

        for col in columns:
            self.approvals_tree.heading(col, text=col)
            self.approvals_tree.column(col, width=100)

        self.approvals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="Approve Selected", command=self._approve_claim).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reject Selected", command=self._reject_claim).pack(side=tk.LEFT, padx=5)

        self._load_approvals()

    def _load_approvals(self):
        """Load pending approvals."""
        for item in self.approvals_tree.get_children():
            self.approvals_tree.delete(item)

        claims = ExpenseManager.get_pending_approvals(self._get_user_id())

        for c in claims:
            self.approvals_tree.insert('', tk.END, values=(
                c.get('claim_id'),
                c.get('user_id'),
                c.get('expense_date', ''),
                c.get('category_name', ''),
                f"£{c.get('amount', 0):.2f}",
                c.get('description', '')[:40],
                'Yes' if c.get('receipt_path') else 'No'
            ))

    def _approve_claim(self):
        """Approve selected claim."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a claim to approve")
            return

        item = self.approvals_tree.item(selection[0])
        claim_id = item['values'][0]

        comments = tk.simpledialog.askstring("Comments", "Enter approval comments (optional):", parent=self.root)

        try:
            ExpenseManager.approve_claim(claim_id, self._get_user_id(), comments or '')
            messagebox.showinfo("Success", "Claim approved")
            self._load_approvals()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _reject_claim(self):
        """Reject selected claim."""
        selection = self.approvals_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a claim to reject")
            return

        item = self.approvals_tree.item(selection[0])
        claim_id = item['values'][0]

        comments = tk.simpledialog.askstring("Reason", "Enter rejection reason:", parent=self.root)
        if not comments:
            messagebox.showerror("Error", "Rejection reason is required")
            return

        try:
            ExpenseManager.reject_claim(claim_id, self._get_user_id(), comments)
            messagebox.showinfo("Success", "Claim rejected")
            self._load_approvals()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_categories_tab(self):
        """Create categories management tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Categories")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Expense Categories", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Add Category", command=self._add_category).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh", command=self._load_categories).pack(side=tk.RIGHT, padx=5)

        # Categories list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('ID', 'Name', 'Description', 'Max Amount', 'Receipt Required', 'Active')
        self.categories_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        for col in columns:
            self.categories_tree.heading(col, text=col)
            self.categories_tree.column(col, width=120)

        self.categories_tree.pack(fill=tk.BOTH, expand=True)

        self.categories_tree.tag_configure('inactive', foreground='gray')

        self._load_categories()

    def _load_categories(self):
        """Load categories."""
        for item in self.categories_tree.get_children():
            self.categories_tree.delete(item)

        categories = ExpenseManager.get_all_categories()

        for c in categories:
            tag = '' if c.get('is_active', True) else 'inactive'
            self.categories_tree.insert('', tk.END, values=(
                c.get('category_id'),
                c.get('name'),
                c.get('description', '')[:40],
                f"£{c['max_amount']:.2f}" if c.get('max_amount') else 'No limit',
                'Yes' if c.get('requires_receipt') else 'No',
                'Active' if c.get('is_active', True) else 'Inactive'
            ), tags=(tag,))

    def _add_category(self):
        """Add new category dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Category")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky='e', padx=10, pady=8)
        name_entry = ttk.Entry(frame, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Description:").grid(row=1, column=0, sticky='e', padx=10, pady=8)
        desc_entry = ttk.Entry(frame, width=30)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Max Amount:").grid(row=2, column=0, sticky='e', padx=10, pady=8)
        max_entry = ttk.Entry(frame, width=15)
        max_entry.grid(row=2, column=1, padx=10, pady=8, sticky='w')

        receipt_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Requires Receipt", variable=receipt_var).grid(
            row=3, column=0, columnspan=2, pady=10)

        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required")
                return

            try:
                max_amt = float(max_entry.get()) if max_entry.get().strip() else None
            except ValueError:
                max_amt = None

            try:
                ExpenseManager.create_category(
                    name=name,
                    description=desc_entry.get().strip(),
                    max_amount=max_amt,
                    requires_receipt=receipt_var.get()
                )
                messagebox.showinfo("Success", "Category created")
                dialog.destroy()
                self._load_categories()
                self._load_categories_combo()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(frame, text="Save", command=save).grid(row=4, column=0, columnspan=2, pady=20)

    def _create_reports_tab(self):
        """Create reports tab (admin)."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Expense Reports", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_expense_stats).pack(side=tk.RIGHT)

        # Statistics
        stats_frame = ttk.LabelFrame(tab, text="Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=10, pady=10)

        self.expense_stats = {}
        for key, label in [('total', 'Total Claims'), ('pending', 'Pending'), ('approved', 'Approved')]:
            frame = ttk.Frame(stats_frame)
            frame.pack(side=tk.LEFT, padx=30, pady=10)
            self.expense_stats[key] = ttk.Label(frame, text="£0", font=('Arial', 18, 'bold'))
            self.expense_stats[key].pack()
            ttk.Label(frame, text=label).pack()

        # By category
        cat_frame = ttk.LabelFrame(tab, text="By Category", padding=10)
        cat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Category', 'Claims', 'Total Amount', 'Average')
        self.cat_stats_tree = ttk.Treeview(cat_frame, columns=columns, show='headings', height=8)

        for col in columns:
            self.cat_stats_tree.heading(col, text=col)
            self.cat_stats_tree.column(col, width=150)

        self.cat_stats_tree.pack(fill=tk.BOTH, expand=True)

        self._load_expense_stats()

    def _load_expense_stats(self):
        """Load expense statistics."""
        stats = ExpenseManager.get_expense_statistics()

        self.expense_stats['total'].config(text=f"£{stats.get('total_amount', 0):.2f}")
        self.expense_stats['pending'].config(text=f"£{stats.get('pending_amount', 0):.2f}")
        self.expense_stats['approved'].config(text=f"£{stats.get('approved_amount', 0):.2f}")

        # By category
        for item in self.cat_stats_tree.get_children():
            self.cat_stats_tree.delete(item)

        for cat, data in stats.get('by_category', {}).items():
            count = data.get('count', 0)
            total = data.get('total', 0)
            avg = total / count if count > 0 else 0
            self.cat_stats_tree.insert('', tk.END, values=(
                cat,
                count,
                f"£{total:.2f}",
                f"£{avg:.2f}"
            ))


# Add simpledialog import for the approval dialogs
try:
    from tkinter import simpledialog
    tk.simpledialog = simpledialog
except ImportError:
    pass
