
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.systems.university.infrastructure.email.template_utils import render_template
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.UNIVERSITY_DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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
    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


def _ledger():
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.events import (
        finance_ledger,
    )
    return finance_ledger


def _ledger_conn():
    conn = get_connection(row_factory=False)
    _ledger().ensure_schema(conn)
    conn.commit()
    return conn


def _recorded_by(auth):
    user = getattr(auth, 'current_user', None) or {}
    return user.get('username') or None


def _export_event_report(parent, event_id, event_name):
    """Write the event's statement and every line to a CSV the user picks."""
    from tkinter import filedialog
    import csv

    safe_name = ''.join(ch if ch.isalnum() else '_' for ch in (event_name or 'event'))[:30]
    file_path = filedialog.asksaveasfilename(
        parent=parent,
        title=_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.export_financial_report', default="Export Financial Report"),
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile=f"financial_report_{safe_name}",
    )
    if not file_path:
        return
    try:
        conn = _ledger_conn()
        try:
            s = _ledger().summary(conn, event_id)
        finally:
            conn.close()
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Event Financial Report'])
            writer.writerow(['Event', s['title'] or event_name])
            writer.writerow(['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            writer.writerow(['Type', 'Category', 'Amount', 'Date', 'Vendor/Method', 'Description'])
            for e in s['entries']:
                writer.writerow([e['direction'].title(), e['category'], f"{e['amount']:.2f}",
                                 e['date'] or 'N/A', e['counterparty'] or '', e['description']])
            writer.writerow([])
            writer.writerow(['Summary'])
            writer.writerow(['Total Income', f"{s['total_income']:.2f}"])
            writer.writerow(['Total Expenses', f"{s['total_expense']:.2f}"])
            writer.writerow(['Net Balance', f"{s['net']:.2f}"])
            if s['budgets']:
                writer.writerow(['Budgeted Income', f"{s['budgeted_income']:.2f}"])
                writer.writerow(['Budgeted Expenses', f"{s['budgeted_expense']:.2f}"])
            writer.writerow([f"Attendees ({s['headcount_basis']})", s['headcount']])
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.report_generated', default="Report Generated"),
                            f"Report exported successfully to:\n{file_path}", parent=parent)
    except (OSError, sqlite3.Error) as e:
        messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"),
                             f"Failed to generate report: {e}", parent=parent)


class EventFinancesDialog:
    """Dialog for tracking event finances"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.event_data = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.events.event_finance.windows.event_financial_tracking', default="Event Financial Tracking"))
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
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.event_financial_tracking', default="Event Financial Tracking"), font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event selection
        event_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.select_event', default="Select Event"))
        event_frame.pack(fill='x', pady=(0, 10))

        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(event_frame, textvariable=self.event_var, width=60, state="readonly")
        self.event_combo.pack(side='left', padx=5, pady=5)
        self.event_combo.bind('<<ComboboxSelected>>', self.on_event_selected)

        ttk.Button(event_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.view_finances', default="View Finances"), command=self.view_finances).pack(side='left', padx=5)
        ttk.Button(event_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.add_expense', default="Add Expense"), command=self.add_expense).pack(side='left', padx=5)

        # Financial summary
        summary_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.financial_summary', default="Financial Summary"))
        summary_frame.pack(fill='x', pady=(0, 10))

        summary_grid = ttk.Frame(summary_frame)
        summary_grid.pack(fill='x', padx=10, pady=10)

        ttk.Label(summary_grid, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.budget', default="Budget:"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=5)
        self.budget_label = ttk.Label(summary_grid, text="—")
        self.budget_label.grid(row=0, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.expenses', default="Expenses:"), font=('Arial', 10, 'bold')).grid(row=0, column=2, sticky='w', padx=5)
        self.expenses_label = ttk.Label(summary_grid, text="£0.00")
        self.expenses_label.grid(row=0, column=3, sticky='w', padx=5)

        ttk.Label(summary_grid, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.revenue', default="Revenue:"), font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=5)
        self.revenue_label = ttk.Label(summary_grid, text="£0.00")
        self.revenue_label.grid(row=1, column=1, sticky='w', padx=5)

        ttk.Label(summary_grid, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.balance', default="Balance:"), font=('Arial', 10, 'bold')).grid(row=1, column=2, sticky='w', padx=5)
        self.balance_label = ttk.Label(summary_grid, text="£0.00")
        self.balance_label.grid(row=1, column=3, sticky='w', padx=5)

        # Transactions list
        trans_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.transactions', default="Transactions"))
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

        self.status_label = ttk.Label(main_frame, text="", foreground='gray')
        self.status_label.pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.generate_report', default="Generate Report"), command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='left')

    def load_events(self):
        """Load Student Union events (last 90 days onward)."""
        try:
            conn = _ledger_conn()
            try:
                events = _ledger().union_events(conn, since_days=90)
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to load events: {str(e)}", parent=self.dialog)
            return
        self.event_data = {_ledger().event_label(e): e for e in events}
        self.event_combo['values'] = list(self.event_data)
        if not events:
            self.status_label.config(text="No Student Union events in the last 90 days or upcoming.")

    def _selected_event(self, warn=True):
        event = self.event_data.get(self.event_var.get())
        if event is None and warn:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.events.event_finance.dialogs.please_select_an_event', default="Please select an event."), parent=self.dialog)
        return event

    def on_event_selected(self, event=None):
        """Load the selected event's money lines and totals."""
        selected = self._selected_event(warn=False)
        if selected:
            self.load_financial_data(selected['event_id'])

    def load_financial_data(self, event_id):
        try:
            conn = _ledger_conn()
            try:
                s = _ledger().summary(conn, event_id)
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to load financial data: {str(e)}", parent=self.dialog)
            return

        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        for e in s['entries']:
            sign = '-' if e['direction'] == 'expense' else '+'
            self.trans_tree.insert('', 'end', values=(
                e['date'] or "N/A",
                "Expense" if e['direction'] == 'expense' else "Revenue",
                e['category'],
                f"{sign}£{e['amount']:.2f}",
                e['description'] or e['counterparty'] or "",
            ))

        if s['budgeted_expense'] is None:
            self.budget_label.config(text="Not set")
        else:
            self.budget_label.config(text=f"£{s['budgeted_expense']:.2f} spend / £{s['budgeted_income']:.2f} income")
        self.expenses_label.config(text=f"£{s['total_expense']:.2f}")
        self.revenue_label.config(text=f"£{s['total_income']:.2f}")
        balance = s['net']
        if balance >= 0:
            self.balance_label.config(text=f"£{balance:.2f}", foreground="green")
        else:
            self.balance_label.config(text=f"-£{abs(balance):.2f}", foreground="red")
        self.status_label.config(text="" if s['entries'] else "No income or expenses recorded for this event yet.")

    def view_finances(self):
        """View finances for selected event"""
        selected = self._selected_event()
        if selected:
            self.load_financial_data(selected['event_id'])

    def add_expense(self):
        """Add expense to event"""
        selected = self._selected_event()
        if not selected:
            return
        dialog = AddExpenseDialog(self.dialog, self.auth, selected['title'], event_id=selected['event_id'])
        self.dialog.wait_window(dialog.dialog)
        self.load_financial_data(selected['event_id'])

    def generate_report(self):
        """Generate financial report for selected event"""
        selected = self._selected_event()
        if selected:
            _export_event_report(self.dialog, selected['event_id'], selected['title'])



class EventFinancialTrackingDialog:
    """Dialog for tracking event finances"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager
        self.event_data = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.events.event_finance.windows.event_financial_tracking', default="Event Financial Tracking"))
        self.dialog.geometry("1000x700")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_events()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.event_financial_tracking_variant_2', default="💰 Event Financial Tracking"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Event selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.select_event_variant_2', default="Select Event:")).pack(side='left', padx=(0, 10))
        self.event_var = tk.StringVar()
        self.event_combo = ttk.Combobox(select_frame, textvariable=self.event_var, width=40, state='readonly')
        self.event_combo.pack(side='left', fill='x', expand=True)
        self.event_combo.bind('<<ComboboxSelected>>', self.load_finances)

        # Notebook for income/expenses
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Income tab
        income_frame = ttk.Frame(notebook)
        notebook.add(income_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.tabs.income', default="Income"))
        self.create_income_tab(income_frame)

        # Expenses tab
        expenses_frame = ttk.Frame(notebook)
        notebook.add(expenses_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.tabs.expenses', default="Expenses"))
        self.create_expenses_tab(expenses_frame)

        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.tabs.financial_summary', default="Financial Summary"))
        self.create_summary_tab(summary_frame)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.add_income', default="Add Income"), command=self.add_income).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.add_expense', default="Add Expense"), command=self.add_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.set_budget', default="Set Budget"), command=self.set_budget).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.generate_report', default="Generate Report"), command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

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

    def load_events(self):
        try:
            conn = _ledger_conn()
            try:
                events = _ledger().union_events(conn)
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to load events: {e}", parent=self.dialog)
            return
        self.event_data = {_ledger().event_label(e): e for e in events}
        self.event_combo['values'] = list(self.event_data)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, "Select an event to see its finances." if events
                                 else "No Student Union events have been created yet.")

    def _selected_event(self, warn=True):
        event = self.event_data.get(self.event_var.get())
        if event is None and warn:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.events.event_finance.dialogs.please_select_an_event_first', default="Please select an event first."), parent=self.dialog)
        return event

    def load_finances(self, event=None):
        # Clear existing
        for item in self.income_tree.get_children():
            self.income_tree.delete(item)
        for item in self.expenses_tree.get_children():
            self.expenses_tree.delete(item)

        selected = self._selected_event(warn=False)
        if not selected:
            return
        try:
            conn = _ledger_conn()
            try:
                s = _ledger().summary(conn, selected['event_id'])
            finally:
                conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to load financial data: {e}", parent=self.dialog)
            return

        for e in s['entries']:
            row = (e['category'], f"£{e['amount']:,.2f}", e['date'] or '', e['counterparty'] or '', e['description'] or '')
            tree = self.income_tree if e['direction'] == 'income' else self.expenses_tree
            tree.insert('', 'end', values=row)

        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(1.0, _ledger().summary_text(s))

    def add_income(self):
        selected = self._selected_event()
        if not selected:
            return

        dialog = AddIncomeDialog(self.dialog, self.auth, selected['title'], event_id=selected['event_id'])
        self.dialog.wait_window(dialog.dialog)
        self.load_finances()  # Refresh data

    def add_expense(self):
        selected = self._selected_event()
        if not selected:
            return

        dialog = AddExpenseDialog(self.dialog, self.auth, selected['title'], event_id=selected['event_id'])
        self.dialog.wait_window(dialog.dialog)
        self.load_finances()  # Refresh data

    def set_budget(self):
        selected = self._selected_event()
        if not selected:
            return
        dialog = SetEventBudgetDialog(self.dialog, self.auth, selected['event_id'], selected['title'])
        self.dialog.wait_window(dialog.dialog)
        self.load_finances()

    def generate_report(self):
        selected = self._selected_event()
        if selected:
            _export_event_report(self.dialog, selected['event_id'], selected['title'])



class SetEventBudgetDialog:
    """Set budgeted income and spend per category for one event."""

    def __init__(self, parent, auth_manager, event_id, event_name):
        self.auth = auth_manager
        self.event_id = event_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Budget - {event_name}")
        self.dialog.geometry("520x620")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frame = ttk.Frame(self.dialog)
        frame.pack(fill='both', expand=True, padx=15, pady=15)
        ttk.Label(frame, text=f"Budget - {event_name}", font=('Arial', 12, 'bold')).pack(anchor='w', pady=(0, 10))
        ttk.Label(frame, text="Enter the planned amount per category (blank or 0 removes a line).",
                  foreground='gray').pack(anchor='w', pady=(0, 10))

        try:
            conn = _ledger_conn()
            try:
                current = {(b['direction'], b['category']): b['amount'] for b in _ledger().budgets(conn, event_id)}
            finally:
                conn.close()
        except sqlite3.Error:
            current = {}

        self.entries = {}
        grid = ttk.Frame(frame)
        grid.pack(fill='both', expand=True)
        row = 0
        for direction, cats in (('income', _ledger().INCOME_CATEGORIES), ('expense', _ledger().EXPENSE_CATEGORIES)):
            ttk.Label(grid, text="Income" if direction == 'income' else "Expenses",
                      font=('Arial', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=(8, 2))
            row += 1
            extra = [c for (d, c) in current if d == direction and c not in cats]
            for cat in (*cats, *extra):
                ttk.Label(grid, text=cat).grid(row=row, column=0, sticky='w', padx=(10, 0))
                var = tk.StringVar(value=f"{current[(direction, cat)]:.2f}" if (direction, cat) in current else "")
                ttk.Entry(grid, textvariable=var, width=14).grid(row=row, column=1, sticky='w', padx=10, pady=1)
                self.entries[(direction, cat)] = var
                row += 1

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        ttk.Button(buttons, text="Save Budget", command=self.save).pack(side='left')
        ttk.Button(buttons, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='right')

    def save(self):
        values = {}
        for key, var in self.entries.items():
            raw = var.get().strip().replace('£', '').replace(',', '')
            try:
                values[key] = float(raw) if raw else 0.0
            except ValueError:
                messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"),
                                       f"'{var.get()}' for {key[1]} is not a valid amount.", parent=self.dialog)
                return
        try:
            conn = _ledger_conn()
            try:
                for (direction, cat), amount in values.items():
                    _ledger().set_budget(conn, event_id=self.event_id, direction=direction, category=cat,
                                         amount=amount, updated_by=_recorded_by(self.auth))
            finally:
                conn.close()
        except (ValueError, sqlite3.Error) as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), str(e), parent=self.dialog)
            return
        messagebox.showinfo(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.success', default="Success"), "Budget saved.", parent=self.dialog)
        self.dialog.destroy()



def _resolve_event_id(conn, event_id, event_name):
    if event_id is not None:
        return event_id
    row = conn.execute("SELECT event_id FROM unified_events WHERE source_type = 'union' AND title = ? "
                       "ORDER BY event_id DESC LIMIT 1", (event_name,)).fetchone()
    return row[0] if row else None


class AddIncomeDialog:
    """Dialog for adding income to an event"""

    def __init__(self, parent, auth_manager, event_name, event_id=None):
        self.parent = parent
        self.auth = auth_manager
        self.event_name = event_name
        self.event_id = event_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.events.event_finance.windows.add_income', default="Add Income"))
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
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.income_source', default="Income Source:")).pack(anchor='w', pady=(0, 5))
        self.source_var = tk.StringVar()
        source_combo = ttk.Combobox(main_frame, textvariable=self.source_var, width=57)
        source_combo['values'] = _ledger().INCOME_CATEGORIES
        source_combo.pack(fill='x', pady=(0, 10))
        source_combo.current(0)

        # Amount
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.amount_variant_2', default="Amount (£):")).pack(anchor='w', pady=(0, 5))
        self.amount_entry = ttk.Entry(main_frame, width=60)
        self.amount_entry.pack(fill='x', pady=(0, 10))

        # Date
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.date_yyyy_mm_dd_variant_2', default="Date (YYYY-MM-DD):")).pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=60)
        self.date_entry.pack(fill='x', pady=(0, 10))
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Payment Method
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.payment_method', default="Payment Method:")).pack(anchor='w', pady=(0, 5))
        self.method_var = tk.StringVar()
        method_combo = ttk.Combobox(main_frame, textvariable=self.method_var, width=57)
        method_combo['values'] = ('Cash', 'Card', 'Bank Transfer', 'Cheque', 'Online Payment', 'Mixed')
        method_combo.pack(fill='x', pady=(0, 10))
        method_combo.current(1)

        # Notes
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.notes', default="Notes:")).pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.notes_text.pack(fill='both', expand=True, pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.add_income', default="Add Income"), command=self.add_income).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

    def add_income(self):
        source = self.source_var.get()
        amount = self.amount_entry.get().strip()
        date = self.date_entry.get().strip()
        method = self.method_var.get()
        notes = self.notes_text.get(1.0, tk.END).strip()

        if not all([source, amount, date]):
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.events.event_finance.dialogs.please_fill_in_source_amount_and_date_fields', default="Please fill in Source, Amount, and Date fields."), parent=self.dialog)
            return

        try:
            conn = _ledger_conn()
            try:
                event_id = _resolve_event_id(conn, self.event_id, self.event_name)
                if event_id is None:
                    raise ValueError("That event could not be found.")
                _ledger().add_entry(conn, event_id=event_id, direction='income', category=source,
                                    amount=amount.replace('£', '').replace(',', ''), entry_date=date,
                                    counterparty=method, description=notes,
                                    recorded_by=_recorded_by(self.auth))
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), str(e), parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to add income: {str(e)}", parent=self.dialog)
            return

        messagebox.showinfo(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.success', default="Success"), f"Income of £{float(amount.replace('£', '').replace(',', '')):.2f} from {source} has been recorded!", parent=self.dialog)
        self.dialog.destroy()



class AddExpenseDialog:
    """Dialog for adding expenses to an event"""

    def __init__(self, parent, auth_manager, event_name, event_id=None):
        self.parent = parent
        self.auth = auth_manager
        self.event_name = event_name
        self.event_id = event_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.events.event_finance.windows.add_expense', default="Add Expense"))
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
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.expense_category', default="Expense Category:")).pack(anchor='w', pady=(0, 5))
        self.category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, width=57)
        category_combo['values'] = _ledger().EXPENSE_CATEGORIES
        category_combo.pack(fill='x', pady=(0, 10))
        category_combo.current(0)

        # Amount
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.amount_variant_2', default="Amount (£):")).pack(anchor='w', pady=(0, 5))
        self.amount_entry = ttk.Entry(main_frame, width=60)
        self.amount_entry.pack(fill='x', pady=(0, 10))

        # Date
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.date_yyyy_mm_dd_variant_2', default="Date (YYYY-MM-DD):")).pack(anchor='w', pady=(0, 5))
        self.date_entry = ttk.Entry(main_frame, width=60)
        self.date_entry.pack(fill='x', pady=(0, 10))
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        # Vendor
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.vendor_supplier', default="Vendor/Supplier:")).pack(anchor='w', pady=(0, 5))
        self.vendor_entry = ttk.Entry(main_frame, width=60)
        self.vendor_entry.pack(fill='x', pady=(0, 10))

        # Receipt
        receipt_frame = ttk.Frame(main_frame)
        receipt_frame.pack(fill='x', pady=(0, 10))

        self.has_receipt_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(receipt_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.receipt_available', default="Receipt Available"),
                       variable=self.has_receipt_var).pack(side='left', padx=(0, 10))

        ttk.Label(receipt_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.receipt', default="Receipt #:")).pack(side='left', padx=(0, 5))
        self.receipt_entry = ttk.Entry(receipt_frame, width=20)
        self.receipt_entry.pack(side='left')

        # Notes
        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.labels.description_notes', default="Description/Notes:")).pack(anchor='w', pady=(0, 5))
        self.notes_text = scrolledtext.ScrolledText(main_frame, height=6, wrap=tk.WORD)
        self.notes_text.pack(fill='both', expand=True, pady=(0, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.add_expense', default="Add Expense"), command=self.add_expense).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.events.event_finance.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side='left')

    def add_expense(self):
        category = self.category_var.get()
        amount = self.amount_entry.get().strip()
        date = self.date_entry.get().strip()
        vendor = self.vendor_entry.get().strip()
        receipt_num = self.receipt_entry.get().strip()
        has_receipt = self.has_receipt_var.get()
        notes = self.notes_text.get(1.0, tk.END).strip()

        if not all([category, amount, date, vendor]):
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), _t('gui.pastoral.student_union_gui.events.event_finance.dialogs.please_fill_in_category_amount_date_and_vendor_fields', default="Please fill in Category, Amount, Date, and Vendor fields."), parent=self.dialog)
            return
        if has_receipt and receipt_num:
            notes = f"{notes} (receipt {receipt_num})".strip()
        elif not has_receipt:
            notes = f"{notes} (no receipt)".strip()

        try:
            conn = _ledger_conn()
            try:
                event_id = _resolve_event_id(conn, self.event_id, self.event_name)
                if event_id is None:
                    raise ValueError("That event could not be found.")
                _ledger().add_entry(conn, event_id=event_id, direction='expense', category=category,
                                    amount=amount.replace('£', '').replace(',', ''), entry_date=date,
                                    counterparty=vendor, description=notes,
                                    receipt=receipt_num if has_receipt else '',
                                    recorded_by=_recorded_by(self.auth))
            finally:
                conn.close()
        except ValueError as e:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.warning', default="Warning"), str(e), parent=self.dialog)
            return
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to add expense: {str(e)}", parent=self.dialog)
            return

        messagebox.showinfo(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.success', default="Success"), f"Expense of £{float(amount.replace('£', '').replace(',', '')):.2f} for {category} has been recorded!", parent=self.dialog)
        self.dialog.destroy()


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
        messagebox.showerror(_t('gui.pastoral.student_union_gui.events.event_finance.dialogs.error', default="Error"), f"Failed to open dialog: {str(e)}")


