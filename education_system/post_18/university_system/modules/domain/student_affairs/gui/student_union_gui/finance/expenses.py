import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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
    from education_system.post_18.university_system.infrastructure.database.db import get_connection
    from education_system.post_18.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class ExpenseSubmitDialog:
    """Dialog for submitting expense requests"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.expenses.dialogs.submit_expense_request"))
        self.dialog.geometry("600x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t("student_union.expenses.dialogs.submit_expense_request"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        details_frame = ttk.LabelFrame(main_frame, text=_t("student_union.expenses.labels.expense_details"))
        details_frame.pack(fill='both', expand=True, pady=(0, 10))

        ttk.Label(details_frame, text=_t("student_union.expenses.labels.category")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.category_var = tk.StringVar(value=_t("student_union.expenses.categories.supplies"))
        ttk.Combobox(details_frame, textvariable=self.category_var,
                    values=[_t("student_union.expenses.categories.supplies"), _t("student_union.expenses.categories.equipment"), _t("student_union.expenses.categories.food"), _t("student_union.expenses.categories.transportation"), _t("student_union.expenses.categories.venue"), _t("student_union.expenses.categories.other")],
                    state="readonly", width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text=_t("student_union.expenses.labels.amount")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.amount_var, width=32).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text=_t("student_union.expenses.labels.description")).grid(row=2, column=0, sticky='nw', padx=5, pady=5)
        self.description_text = tk.Text(details_frame, height=4, width=32)
        self.description_text.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text=_t("student_union.expenses.labels.related_event")).grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(details_frame, textvariable=self.event_var, width=30)
        self.event_combo.grid(row=3, column=1, padx=5, pady=5)

        ttk.Label(details_frame, text=_t("student_union.expenses.labels.receipt_invoice")).grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.receipt_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.receipt_var, width=32).grid(row=4, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text=_t("student_union.expenses.buttons.submit"), command=self.submit_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.expenses.buttons.cancel"), command=self.dialog.destroy).pack(side='left')

    def submit_expense(self):
        """Submit the expense request"""
        amount_str = self.amount_var.get().strip()
        if not amount_str:
            messagebox.showwarning(_t("student_union.expenses.messages.warning"), _t("student_union.expenses.messages.please_enter_amount"))
            return

        try:
            amount = float(amount_str)
            messagebox.showinfo(_t("student_union.expenses.messages.success"), _t("student_union.expenses.messages.expense_submitted_success").format(amount=f"{amount:.2f}"))
            self.dialog.destroy()
        except ValueError:
            messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.invalid_amount"))



class ExpenseApprovalDialog:
    """Dialog for approving expense requests"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("student_union.expenses.dialogs.approve_expense_requests"))
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_pending_expenses()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(main_frame, text=_t("student_union.expenses.dialogs.pending_expense_requests"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text=_t("student_union.expenses.labels.pending_requests"))
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Category', 'Amount', 'Description', 'Submitted By', 'Date', 'Status')
        column_texts = (
            _t("student_union.expenses.columns.id"),
            _t("student_union.expenses.columns.category"),
            _t("student_union.expenses.columns.amount"),
            _t("student_union.expenses.columns.description"),
            _t("student_union.expenses.columns.submitted_by"),
            _t("student_union.expenses.columns.date"),
            _t("student_union.expenses.columns.status")
        )
        self.expenses_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col, text in zip(columns, column_texts):
            self.expenses_tree.heading(col, text=text)
            self.expenses_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.expenses_tree.yview)
        self.expenses_tree.configure(yscrollcommand=scrollbar.set)

        self.expenses_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(button_frame, text=_t("student_union.expenses.buttons.approve"), command=self.approve_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.expenses.buttons.reject"), command=self.reject_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t("student_union.expenses.buttons.close"), command=self.dialog.destroy).pack(side='left')

    def load_pending_expenses(self):
        """Load pending expense requests"""
        try:
            # Clear existing items
            for item in self.expenses_tree.get_children():
                self.expenses_tree.delete(item)

            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expense_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    amount REAL NOT NULL,
                    description TEXT,
                    submitted_by TEXT,
                    submitted_date TEXT,
                    status TEXT DEFAULT 'pending',
                    approved_by TEXT,
                    approved_date TEXT,
                    club_id INTEGER,
                    event_id INTEGER
                )
            ''')
            conn.commit()

            cursor.execute('''
                SELECT request_id, category, amount, description, submitted_by, submitted_date, status
                FROM expense_requests
                WHERE status = 'pending'
                ORDER BY submitted_date DESC
            ''')

            expenses = cursor.fetchall()
            conn.close()

            na_text = _t("student_union.expenses.messages.na")
            for expense in expenses:
                req_id, category, amount, desc, submitted_by, sub_date, status = expense
                self.expenses_tree.insert('', 'end', values=(
                    req_id,
                    category or na_text,
                    f"£{amount:.2f}",
                    (desc or na_text)[:30],
                    submitted_by or na_text,
                    sub_date or na_text,
                    status
                ))

            if not expenses:
                self.expenses_tree.insert('', 'end', values=('', _t("student_union.expenses.messages.no_pending_expenses"), '', '', '', '', ''))

        except sqlite3.Error as e:
            messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.failed_to_load_expenses").format(error=str(e)))

    def approve_expense(self):
        """Approve selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning(_t("student_union.expenses.messages.warning"), _t("student_union.expenses.messages.please_select_expense_approve"))
            return

        item = self.expenses_tree.item(selection[0])
        request_id = item['values'][0]

        if not request_id or request_id == '':
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            approver = self.auth.get('username', 'Admin') if isinstance(self.auth, dict) else 'Admin'

            cursor.execute('''
                UPDATE expense_requests
                SET status = 'approved', approved_by = ?, approved_date = ?
                WHERE request_id = ?
            ''', (approver, now, request_id))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("student_union.expenses.messages.success"), _t("student_union.expenses.messages.expense_approved").format(request_id=request_id))
            self.load_pending_expenses()

        except sqlite3.Error as e:
            messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.failed_to_approve_expense").format(error=str(e)))

    def reject_expense(self):
        """Reject selected expense"""
        selection = self.expenses_tree.selection()
        if not selection:
            messagebox.showwarning(_t("student_union.expenses.messages.warning"), _t("student_union.expenses.messages.please_select_expense_reject"))
            return

        item = self.expenses_tree.item(selection[0])
        request_id = item['values'][0]

        if not request_id or request_id == '':
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            approver = self.auth.get('username', 'Admin') if isinstance(self.auth, dict) else 'Admin'

            cursor.execute('''
                UPDATE expense_requests
                SET status = 'rejected', approved_by = ?, approved_date = ?
                WHERE request_id = ?
            ''', (approver, now, request_id))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t("student_union.expenses.messages.info"), _t("student_union.expenses.messages.expense_rejected").format(request_id=request_id))
            self.load_pending_expenses()

        except sqlite3.Error as e:
            messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.failed_to_reject_expense").format(error=str(e)))



def create_finances_tab(self):
    """Create financial management tab"""
    finances_frame = ttk.Frame(self.notebook)
    self.notebook.add(finances_frame, text=_t("student_union.expenses.tabs.finances"))

    # Left panel
    left_panel = ttk.LabelFrame(finances_frame, text=_t("student_union.expenses.tabs.financial_actions"))
    left_panel.pack(side='left', fill='y', padx=5, pady=5, ipadx=5, ipady=5)

    ttk.Button(left_panel, text=_t("student_union.expenses.action_buttons.submit_expense_request"),
              command=self.submit_expense_request_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.expenses.action_buttons.approve_expenses"),
              command=self.approve_expense_requests_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.expenses.action_buttons.financial_reports"),
              command=self.view_club_financial_reports_gui).pack(fill='x', pady=2)
    ttk.Button(left_panel, text=_t("student_union.expenses.action_buttons.manage_budgets"),
              command=self.manage_club_budgets_gui).pack(fill='x', pady=2)

    # Right panel
    right_panel = ttk.LabelFrame(finances_frame, text=_t("student_union.expenses.tabs.financial_information"))
    right_panel.pack(side='right', fill='both', expand=True, padx=5, pady=5)

    self.finances_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD,
                                                  height=30, width=80)
    self.finances_text.pack(fill='both', expand=True, padx=5, pady=5)


def submit_expense_request_gui(self):
    """Submit expense request with GUI dialog"""
    try:
        dialog = ExpenseSubmitDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.failed_to_open_dialog").format(error=str(e)))


def approve_expense_requests_gui(self):
    """Approve expense requests with GUI dialog"""
    try:
        dialog = ExpenseApprovalDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror(_t("student_union.expenses.messages.error"), _t("student_union.expenses.messages.failed_to_open_dialog").format(error=str(e)))


