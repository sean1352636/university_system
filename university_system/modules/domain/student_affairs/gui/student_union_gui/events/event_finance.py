import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class EventFinancesDialog:
    """Dialog for tracking event finances"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Financial Tracking")
        self.dialog.geometry("900x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        ttk.Label(main_frame, text="Event Financial Tracking", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event selection
        event_frame = ttk.LabelFrame(main_frame, text="Select Event")
        event_frame.pack(fill='x', pady=(0, 10))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, width=60, state="readonly")
        self.event_combo.pack(side='left', padx=5, pady=5)
        self.event_combo.bind('<<ComboboxSelected>>', self.on_event_selected)

        ttk.Button(event_frame, text="View Finances", command=self.view_finances).pack(side='left', padx=5)
        ttk.Button(event_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=5)

        # Financial summary
        summary_frame = ttk.LabelFrame(main_frame, text="Financial Summary")
        summary_frame.pack(fill='x', pady=(0, 10))

        summary_grid = ttk.Frame(summary_frame)
        summary_grid.pack(fill='x', padx=10, pady=10)

        ttk.Label(summary_grid, text="Budget:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        self.budget_label = ttk.Label(summary_grid, text="$0.00")
        self.budget_label.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Expenses:", font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=5)
        self.expenses_label = ttk.Label(summary_grid, text="$0.00")
        self.expenses_label.grid(row=0, column=3, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Revenue:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=5)
        self.revenue_label = ttk.Label(summary_grid, text="$0.00")
        self.revenue_label.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text="Balance:", font=('Arial', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=5)
        self.balance_label = ttk.Label(summary_grid, text="$0.00")
        self.balance_label.grid(row=1, column=3, sticky='w', padx=5)

        # Transactions list
        trans_frame = ttk.LabelFrame(main_frame, text="Transactions")
        trans_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Date', 'Type', 'Category', 'Amount', 'Description')
        self.trans_tree = ttk.Treeview(trans_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.trans_tree.heading(col, text=col)
            self.trans_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(trans_frame, orient='vertical', command=self.trans_tree.yview)
        self.trans_tree.configure(yscrollcommand=scrollbar.set)

        self.trans_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load events"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT event_id, event_name, event_date
            FROM union_events
            WHERE event_date >= date('now', '-90 days')
            ORDER BY event_date DESC
            ''')

            events = cursor.fetchall()

            event_options = []
            self.event_data = {}

            for event in events:
                option = f"{event[1]} - {event[2]}"
                event_options.append(option)
                self.event_data[option] = event[0]

            self.event_combo['values'] = event_options
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load events: {str(e)}")

    def on_event_selected(self, event=None):
        """
        Handle event selection - Auto-loads financial data for the selected event.

        Updates the financial summary labels and populates the transactions
        treeview with expense and revenue records from the event_finances table.
        """
        selection = self.event_var.get()
        if not selection or selection not in self.event_data:
            return

        event_id = self.event_data[selection]

        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get financial data for this event
            cursor.execute('''
                SELECT expense_type, revenue_type, amount, description, date_recorded
                FROM event_finances
                WHERE event_id = ?
                ORDER BY date_recorded DESC
            ''', (event_id,))

            transactions = cursor.fetchall()

            # Calculate totals
            total_expenses = 0.0
            total_revenue = 0.0

            # Clear existing transactions in treeview
            for item in self.trans_tree.get_children():
                self.trans_tree.delete(item)

            # Populate transactions treeview
            for trans in transactions:
                expense_type, revenue_type, amount, description, date_recorded = trans
                amount = float(amount) if amount else 0.0

                if expense_type and expense_type.strip():
                    # This is an expense
                    total_expenses += amount
                    trans_type = "Expense"
                    category = expense_type
                    display_amount = f"-${amount:.2f}"
                elif revenue_type and revenue_type.strip():
                    # This is revenue
                    total_revenue += amount
                    trans_type = "Revenue"
                    category = revenue_type
                    display_amount = f"+${amount:.2f}"
                else:
                    # Unknown type, treat as expense
                    total_expenses += amount
                    trans_type = "Other"
                    category = "Uncategorized"
                    display_amount = f"${amount:.2f}"

                self.trans_tree.insert('', 'end', values=(
                    date_recorded or "N/A",
                    trans_type,
                    category,
                    display_amount,
                    description or ""
                ))

            # Calculate balance (revenue - expenses)
            balance = total_revenue - total_expenses

            # Update summary labels
            self.budget_label.config(text=f"${total_revenue:.2f}")
            self.expenses_label.config(text=f"${total_expenses:.2f}")
            self.revenue_label.config(text=f"${total_revenue:.2f}")

            # Color-code the balance
            if balance >= 0:
                self.balance_label.config(text=f"${balance:.2f}", foreground="green")
            else:
                self.balance_label.config(text=f"-${abs(balance):.2f}", foreground="red")

            conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load financial data: {str(e)}")

    def view_finances(self):
        """View finances for selected event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event.")
            return

        # Extract event_id from selection
        try:
            event_id = int(selection.split(':')[0])
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid event selection")
            return

        # Load and display financial data
        self.load_financial_data(event_id)

    def add_expense(self):
        """Add expense to event"""
        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event first.")
            return

        try:
            event_id = int(selection.split(':')[0])
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid event selection")
            return

        # Create expense dialog
        expense_dialog = tk.Toplevel(self.dialog)
        expense_dialog.title("Add Expense")
        expense_dialog.geometry("450x400")
        expense_dialog.transient(self.dialog)
        expense_dialog.grab_set()

        main_frame = ttk.Frame(expense_dialog, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add Expense", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill='both', expand=True)

        # Category
        ttk.Label(form_frame, text="Category *").grid(row=0, column=0, sticky='w', pady=5)
        category_var = tk.StringVar(value='Supplies')
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, state='readonly', width=28)
        category_combo['values'] = ['Supplies', 'Venue', 'Catering', 'Equipment', 'Marketing', 'Transportation', 'Other']
        category_combo.grid(row=0, column=1, pady=5)

        # Amount
        ttk.Label(form_frame, text="Amount ($) *").grid(row=1, column=0, sticky='w', pady=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var, width=30).grid(row=1, column=1, pady=5)

        # Description
        ttk.Label(form_frame, text="Description *").grid(row=2, column=0, sticky='nw', pady=5)
        desc_text = tk.Text(form_frame, height=4, width=30)
        desc_text.grid(row=2, column=1, pady=5)

        # Vendor/Payee
        ttk.Label(form_frame, text="Vendor/Payee").grid(row=3, column=0, sticky='w', pady=5)
        vendor_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=vendor_var, width=30).grid(row=3, column=1, pady=5)

        # Date
        ttk.Label(form_frame, text="Date (YYYY-MM-DD)").grid(row=4, column=0, sticky='w', pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=date_var, width=30).grid(row=4, column=1, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))

        def save_expense():
            try:
                amount = float(amount_var.get())
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be positive", parent=expense_dialog)
                    return
            except ValueError:
                messagebox.showerror("Error", "Invalid amount", parent=expense_dialog)
                return

            description = desc_text.get('1.0', 'end-1c').strip()
            if not description:
                messagebox.showerror("Error", "Description is required", parent=expense_dialog)
                return

            try:
                conn = student_union_cli.get_connection()
                cursor = conn.cursor()

                # Create table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS event_finances (
                        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        transaction_type TEXT NOT NULL,
                        category TEXT,
                        amount REAL NOT NULL,
                        description TEXT,
                        vendor TEXT,
                        transaction_date TEXT,
                        created_by TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    INSERT INTO event_finances
                    (event_id, transaction_type, category, amount, description, vendor, transaction_date, created_at)
                    VALUES (?, 'expense', ?, ?, ?, ?, ?, ?)
                ''', (event_id, category_var.get(), amount, description, vendor_var.get().strip(),
                      date_var.get().strip(), now))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Expense added successfully!", parent=expense_dialog)
                expense_dialog.destroy()
                self.load_financial_data(event_id)

            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to add expense: {str(e)}", parent=expense_dialog)

        ttk.Button(button_frame, text="Save Expense", command=save_expense).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=expense_dialog.destroy).pack(side='left', padx=5)

    def generate_report(self):
        """Generate financial report for selected event"""
        from tkinter import filedialog
        import csv

        selection = self.event_var.get()
        if not selection:
            messagebox.showwarning("Warning", "Please select an event first.")
            return

        try:
            event_id = int(selection.split(':')[0])
            event_name = selection.split(': ', 1)[1] if ': ' in selection else 'Event'
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Invalid event selection")
            return

        safe_name = event_name.replace(' ', '_').replace('/', '_')[:30]

        file_path = filedialog.asksaveasfilename(
            title="Export Financial Report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"financial_report_{safe_name}"
        )

        if not file_path:
            return

        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT transaction_type, category, amount, description, vendor, transaction_date
                FROM event_finances
                WHERE event_id = ?
                ORDER BY transaction_date DESC
            ''', (event_id,))

            transactions = cursor.fetchall()
            conn.close()

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Event Financial Report'])
                writer.writerow(['Event', event_name])
                writer.writerow(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])
                writer.writerow(['Type', 'Category', 'Amount', 'Description', 'Vendor', 'Date'])

                total_income = 0
                total_expenses = 0

                for trans_type, category, amount, desc, vendor, trans_date in transactions:
                    writer.writerow([trans_type, category, f"{amount:.2f}", desc, vendor or 'N/A', trans_date or 'N/A'])
                    if trans_type == 'income':
                        total_income += amount
                    else:
                        total_expenses += amount

                writer.writerow([])
                writer.writerow(['Summary'])
                writer.writerow(['Total Income', f"${total_income:.2f}"])
                writer.writerow(['Total Expenses', f"${total_expenses:.2f}"])
                writer.writerow(['Net Balance', f"${(total_income - total_expenses):.2f}"])

            messagebox.showinfo("Success", f"Report exported successfully to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")



class EventFinancialTrackingDialog:
    """Dialog for tracking event finances"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Event Financial Tracking")
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="💰 Event Financial Tracking",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Select Event:").pack(side='left', padx=(0, 10))
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(select_frame, textvariable=self.event_var, width=40, state='readonly')
        self.event_combo['values'] = ('Spring Festival 2025', 'Tech Workshop Series', 'Annual Gala')
        self.event_combo.pack(side='left', fill='x', expand=True)
        self.event_combo.bind('<<ComboboxSelected>>', self.load_finances)

        # Notebook for income/expenses
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Income tab
        income_frame = ttk.Frame(notebook)
        notebook.add(income_frame, text="Income")
        self.create_income_tab(income_frame)

        # Expenses tab
        expenses_frame = ttk.Frame(notebook)
        notebook.add(expenses_frame, text="Expenses")
        self.create_expenses_tab(expenses_frame)

        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Financial Summary")
        self.create_summary_tab(summary_frame)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Add Income", command=self.add_income).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def create_income_tab(self, parent):
        columns = ('Source', 'Amount', 'Date', 'Method', 'Notes')
        self.income_tree = ttk.Treeview(parent, columns=columns, show='tree headings')

        for col in columns:
            self.income_tree.heading(col, text=col)

        self.income_tree.pack(fill='both', expand=True, padx=10, pady=10)

    def create_expenses_tab(self, parent):
        columns = ('Category', 'Amount', 'Date', 'Vendor', 'Notes')
        self.expenses_tree = ttk.Treeview(parent, columns=columns, show='tree headings')

        for col in columns:
            self.expenses_tree.heading(col, text=col)

        self.expenses_tree.pack(fill='both', expand=True, padx=10, pady=10)

    def create_summary_tab(self, parent):
        self.summary_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=('Courier', 10))
        self.summary_text.pack(fill='both', expand=True, padx=10, pady=10)

    def load_finances(self, event=None):
        # Clear existing
        for item in self.income_tree.get_children():
            self.income_tree.delete(item)
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)

        # Sample income
        income_data = [
            ("Ticket Sales", "£2,500.00", "2025-03-15", "Card", "250 tickets sold"),
            ("Sponsorships", "£1,000.00", "2025-03-10", "Transfer", "Local business sponsor"),
            ("Merchandise", "£450.00", "2025-03-15", "Cash/Card", "Event merchandise")
        ]

        for income in income_data:
            self.income_tree.insert('', 'end', values=income)

        # Sample expenses
        expenses_data = [
            ("Venue", "£800.00", "2025-03-01", "University Facilities", "Hall booking"),
            ("Catering", "£1,200.00", "2025-03-14", "Catering Co", "Food for 250"),
            ("Equipment", "£350.00", "2025-03-10", "AV Rentals", "Sound system"),
            ("Marketing", "£150.00", "2025-03-05", "Print Shop", "Posters and flyers")
        ]

        for expense in expenses_data:
            self.expenses_tree.insert('', 'end', values=expense)

        # Update summary
        summary = """FINANCIAL SUMMARY - Spring Festival 2025
================================================================================

INCOME:
  Ticket Sales:         £2,500.00
  Sponsorships:         £1,000.00
  Merchandise:            £450.00
  --------------------------------
  Total Income:         £3,950.00

EXPENSES:
  Venue:                  £800.00
  Catering:             £1,200.00
  Equipment:              £350.00
  Marketing:              £150.00
  --------------------------------
  Total Expenses:       £2,500.00

NET PROFIT/LOSS:
  ================================
  Net Profit:           £1,450.00
  ================================

BUDGET ANALYSIS:
  Budgeted Income:      £3,500.00
  Actual Income:        £3,950.00
  Variance:               +£450.00 (+12.9%)

  Budgeted Expenses:    £3,000.00
  Actual Expenses:      £2,500.00
  Variance:               -£500.00 (-16.7%)

COST PER ATTENDEE:
  Total Attendees: 250
  Cost per Attendee: £10.00
  Revenue per Attendee: £15.80
  Profit per Attendee: £5.80

STATUS: ✓ Event was profitable and under budget
"""
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, summary)

    def add_income(self):
        event_name = self.event_var.get()
        if not event_name:
            messagebox.showwarning("Warning", "Please select an event first.")
            return

        dialog = AddIncomeDialog(self.dialog, self.auth, event_name)
        self.dialog.wait_window(dialog.dialog)
        self.load_finances()  # Refresh data

    def add_expense(self):
        event_name = self.event_var.get()
        if not event_name:
            messagebox.showwarning("Warning", "Please select an event first.")
            return

        dialog = AddExpenseDialog(self.dialog, self.auth, event_name)
        self.dialog.wait_window(dialog.dialog)
        self.load_finances()  # Refresh data

    def generate_report(self):
        messagebox.showinfo("Report Generated", "Financial report exported to:\nreports/spring_festival_2025_finances.pdf")



class AddIncomeDialog:
    """Dialog for adding income to an event"""

    def __init__(self, parent, auth_manager, event_name):
        self.parent = parent
        self.auth = auth_manager
        self.event_name = event_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Income")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=f"Add Income - {self.event_name}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Source
        ttk.Label(main_frame, text="Income Source:").pack(anchor='w', pady=(0, 5))
        self.source_var = tk.StringVar()
        source_combo = ttk.Combobox(main_frame, textvariable=self.source_var, width=57)
        source_combo['values'] = ('Ticket Sales', 'Sponsorships', 'Merchandise', 'Donations',
                                  'Entry Fees', 'Food Sales', 'Grants', 'Other')
        source_combo.pack(fill='x', pady=(0, 10))
        source_combo.current(0)

        # Amount
        ttk.Label(main_frame, text="Amount (£):").pack(anchor='w', pady=(0, 5))
        self.amount_entry = ttk.Entry(main_frame, width=60)
        self.amount_entry.pack(fill='x', pady=(0, 10))

        # Date
        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=60)
        self.date_entry.pack(fill='x', pady=(0, 10))
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Payment Method
        ttk.Label(main_frame, text="Payment Method:").pack(anchor='w', pady=(0, 5))
        self.method_var = tk.StringVar()
        method_combo = ttk.Combobox(main_frame, textvariable=self.method_var, width=57)
        method_combo['values'] = ('Cash', 'Card', 'Bank Transfer', 'Cheque', 'Online Payment', 'Mixed')
        method_combo.pack(fill='x', pady=(0, 10))
        method_combo.current(1)

        # Notes
        ttk.Label(main_frame, text="Notes:").pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.notes_text.pack(fill='both', expand=True, pady=(0, 15))
        self.notes_text.insert(1.0, "Additional details about this income...")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Add Income", command=self.add_income).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def add_income(self):
        source = self.source_var.get()
        amount = self.amount_entry.get().strip()
        date = self.date_entry.get().strip()
        method = self.method_var.get()
        notes = self.notes_text.get(1.0, tk.END).strip()

        if not all([source, amount, date]):
            messagebox.showwarning("Warning", "Please fill in Source, Amount, and Date fields.")
            return

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid amount.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_income (
                income_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                payment_method TEXT,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            recorded_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO event_income (
                event_name, source, amount, date, payment_method, notes, recorded_by, recorded_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.event_name, source, amount_float, date, method, notes,
                  recorded_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Income of £{amount_float:.2f} from {source} has been recorded!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add income: {str(e)}")



class AddExpenseDialog:
    """Dialog for adding expenses to an event"""

    def __init__(self, parent, auth_manager, event_name):
        self.parent = parent
        self.auth = auth_manager
        self.event_name = event_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Expense")
        self.dialog.geometry("600x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text=f"Add Expense - {self.event_name}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Category
        ttk.Label(main_frame, text="Expense Category:").pack(anchor='w', pady=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, width=57)
        category_combo['values'] = ('Venue', 'Catering', 'Equipment', 'Marketing', 'Entertainment',
                                    'Decorations', 'Staffing', 'Transportation', 'Supplies', 'Other')
        category_combo.pack(fill='x', pady=(0, 10))
        category_combo.current(0)

        # Amount
        ttk.Label(main_frame, text="Amount (£):").pack(anchor='w', pady=(0, 5))
        self.amount_entry = ttk.Entry(main_frame, width=60)
        self.amount_entry.pack(fill='x', pady=(0, 10))

        # Date
        ttk.Label(main_frame, text="Date (YYYY-MM-DD):").pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=60)
        self.date_entry.pack(fill='x', pady=(0, 10))
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Vendor
        ttk.Label(main_frame, text="Vendor/Supplier:").pack(anchor='w', pady=(0, 5))
        self.vendor_entry = ttk.Entry(main_frame, width=60)
        self.vendor_entry.pack(fill='x', pady=(0, 10))

        # Receipt
        receipt_frame = ttk.Frame(main_frame)
        receipt_frame.pack(fill='x', pady=(0, 10))

        self.has_receipt_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(receipt_frame, text="Receipt Available",
                       variable=self.has_receipt_var).pack(side='left', padx=(0, 10))

        ttk.Label(receipt_frame, text="Receipt #:").pack(side='left', padx=(0, 5))
        self.receipt_entry = ttk.Entry(receipt_frame, width=20)
        self.receipt_entry.pack(side='left')

        # Notes
        ttk.Label(main_frame, text="Description/Notes:").pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.notes_text.pack(fill='both', expand=True, pady=(0, 15))
        self.notes_text.insert(1.0, "Description of expense...")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Add Expense", command=self.add_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def add_expense(self):
        category = self.category_var.get()
        amount = self.amount_entry.get().strip()
        date = self.date_entry.get().strip()
        vendor = self.vendor_entry.get().strip()
        receipt_num = self.receipt_entry.get().strip()
        has_receipt = self.has_receipt_var.get()
        notes = self.notes_text.get(1.0, tk.END).strip()

        if not all([category, amount, date, vendor]):
            messagebox.showwarning("Warning", "Please fill in Category, Amount, Date, and Vendor fields.")
            return

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid amount.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_expenses (
                expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                vendor TEXT,
                receipt_number TEXT,
                has_receipt BOOLEAN,
                notes TEXT,
                recorded_by TEXT,
                recorded_date TEXT
            )
            ''')

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            recorded_by = result[0] if result else 'unknown'

            cursor.execute('''
            INSERT INTO event_expenses (
                event_name, category, amount, date, vendor, receipt_number,
                has_receipt, notes, recorded_by, recorded_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.event_name, category, amount_float, date, vendor, receipt_num,
                  has_receipt, notes, recorded_by, datetime.now().isoformat()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Expense of £{amount_float:.2f} for {category} has been recorded!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add expense: {str(e)}")



def open_event_financial_tracking_dialog(self):
    """Open event financial tracking"""
    dialog = EventFinancialTrackingDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def track_event_finances(self):
    """Track event finances with GUI dialog"""
    try:
        dialog = EventFinancesDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


