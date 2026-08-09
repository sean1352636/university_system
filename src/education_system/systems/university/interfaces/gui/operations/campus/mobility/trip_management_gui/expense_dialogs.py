
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.systems.university.interfaces.gui.operations.campus.mobility.trip_management_gui._imports import safe_db_operation


class AddExpenseDialog(Dialog):
    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = trip_id
        self.refresh_callback = refresh_callback
        super().__init__(parent, "Add Expense")

    def body(self, master):
        """Create the dialog body"""
        # Category selection
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.category', default="Category:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.category_var = tk.StringVar()
        categories = ['Transportation', 'Accommodation', 'Food', 'Activities', 'Equipment', 'Insurance', 'Miscellaneous']
        self.category_combo = ttk.Combobox(master, textvariable=self.category_var, values=categories, state="readonly")
        self.category_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W+tk.E)

        # Description
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.description', default="Description:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        # Amount
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.amount', default="Amount (\u00a3):")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        # Date
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=3, column=1, padx=5, pady=5)

        return self.category_combo  # Return widget, not StringVar

    def validate(self):
        """Validate expense data"""
        if not self.category_var.get():
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.please_select_a_category', default="Please select a category."))
            return False

        if not self.description_var.get().strip():
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.description_is_required', default="Description is required."))
            return False

        try:
            amount = float(self.amount_var.get())
            if amount < 0:
                messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.amount_cannot_be_negative', default="Amount cannot be negative."))
                return False
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount."))
            return False

        try:
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.please_enter_a_valid_date_yyyy_mm_dd', default="Please enter a valid date (YYYY-MM-DD)."))
            return False

        return True

    def apply(self):
        """Add the expense"""
        def add_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO trip_expenses (trip_id, category, description, amount, date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.trip_id,
                self.category_var.get(),
                self.description_var.get().strip(),
                float(self.amount_var.get()),
                self.date_var.get(),
                self.auth.current_user['id']
            ))
            return True


        if safe_db_operation(add_expense_operation):
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.success', default="Success"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.expense_added_successfully', default="Expense added successfully!"))
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.failed_to_add_expense', default="Failed to add expense."))


class EditExpenseDialog(Dialog):
    def __init__(self, parent, expense_id, refresh_callback):
        self.expense_id = expense_id
        self.refresh_callback = refresh_callback
        self.expense_data = None

        # Load expense data
        self.load_expense_data()

        super().__init__(parent, "Edit Expense")

    def load_expense_data(self):
        """Load existing expense data"""
        def get_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trip_expenses WHERE id = ?', (self.expense_id,))
            return cursor.fetchone()

        self.expense_data = safe_db_operation(get_expense_operation)

    def body(self, master):
        """Create the dialog body"""
        if not self.expense_data:
            ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.expense_not_found', default="Expense not found.")).pack(pady=20)
            return None

        expense = self.expense_data

        # Description
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.description', default="Description:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar(value=expense[3])
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        # Amount
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.amount', default="Amount (\u00a3):")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar(value=str(expense[4]))
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        # Date
        ttk.Label(master, text=_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=expense[5])
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        return self.description_var

    def validate(self):
        """Validate expense data"""
        if not self.description_var.get().strip():
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.description_is_required', default="Description is required."))
            return False

        try:
            amount = float(self.amount_var.get())
            if amount < 0:
                messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.amount_cannot_be_negative', default="Amount cannot be negative."))
                return False
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount."))
            return False

        try:
            datetime.strptime(self.date_var.get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.validation_error', default="Validation Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.please_enter_a_valid_date_yyyy_mm_dd', default="Please enter a valid date (YYYY-MM-DD)."))
            return False

        return True

    def apply(self):
        """Update the expense"""
        def update_expense_operation(conn):
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE trip_expenses SET description = ?, amount = ?, date = ?
            WHERE id = ?
            ''', (
                self.description_var.get().strip(),
                float(self.amount_var.get()),
                self.date_var.get(),
                self.expense_id
            ))
            return True


        if safe_db_operation(update_expense_operation):
            messagebox.showinfo(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.success', default="Success"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.expense_updated_successfully', default="Expense updated successfully!"))
            if self.refresh_callback:
                self.refresh_callback()
        else:
            messagebox.showerror(_t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.error', default="Error"), _t('gui.operations.campus.mobility.trip_management_gui.expense_dialogs.dialogs.failed_to_update_expense', default="Failed to update expense."))
