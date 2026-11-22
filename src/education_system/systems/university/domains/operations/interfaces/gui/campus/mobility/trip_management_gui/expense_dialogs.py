
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.simpledialog import Dialog
from datetime import datetime

from education_system.systems.university.domains.operations.interfaces.gui.campus.mobility.trip_management_gui._api import (
    tm, call,
)

_K = 'gui.operations.campus.mobility.trip_management_gui.expense_dialogs'


def _validate_fields(dialog, *, need_category):
    """Shared form checks (the domain repeats them; these give instant feedback)."""
    if need_category and not dialog.category_var.get():
        messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.please_select_a_category", default="Please select a category."), parent=dialog)
        return False
    if not dialog.description_var.get().strip():
        messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.description_is_required", default="Description is required."), parent=dialog)
        return False
    try:
        if float(dialog.amount_var.get()) < 0:
            messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.amount_cannot_be_negative", default="Amount cannot be negative."), parent=dialog)
            return False
    except ValueError:
        messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.please_enter_a_valid_amount", default="Please enter a valid amount."), parent=dialog)
        return False
    try:
        datetime.strptime(dialog.date_var.get(), '%Y-%m-%d')
    except ValueError:
        messagebox.showerror(_t(f"{_K}.dialogs.validation_error", default="Validation Error"), _t(f"{_K}.dialogs.please_enter_a_valid_date_yyyy_mm_dd", default="Please enter a valid date (YYYY-MM-DD)."), parent=dialog)
        return False
    return True


class AddExpenseDialog(Dialog):
    """Record an expense through ``expenses.record_expense``."""

    def __init__(self, parent, auth, trip_id, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.add", default="Add Expense"))

    def body(self, master):
        ttk.Label(master, text=_t(f"{_K}.labels.category", default="Category:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(master, textvariable=self.category_var,
                                           values=list(tm('expenses').EXPENSE_CATEGORIES), state="readonly")
        self.category_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        ttk.Label(master, text=_t(f"{_K}.labels.description", default="Description:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.description_var, width=40).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.amount", default="Amount (£):")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.date_yyyy_mm_dd", default="Date (YYYY-MM-DD):")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=3, column=1, padx=5, pady=5)
        return self.category_combo

    def validate(self):
        return _validate_fields(self, need_category=True)

    def apply(self):
        ok, _ = call(self.parent, tm('expenses').record_expense, self.auth, self.trip_id,
                     self.category_var.get(), self.description_var.get().strip(),
                     float(self.amount_var.get()), self.date_var.get())
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.expense_added_successfully", default="Expense added successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()


class EditExpenseDialog(Dialog):
    """Change an expense through ``expenses.update_expense``.

    ``expense`` is the row from ``expenses.list_expenses`` (a dict).
    """

    def __init__(self, parent, auth, trip_id, expense, refresh_callback):
        self.auth = auth
        self.trip_id = int(trip_id)
        self.expense_data = expense
        self.refresh_callback = refresh_callback
        super().__init__(parent, _t(f"{_K}.windows.edit", default="Edit Expense"))

    def body(self, master):
        if not self.expense_data:
            ttk.Label(master, text=_t(f"{_K}.labels.expense_not_found", default="Expense not found.")).pack(pady=20)
            return None
        expense = self.expense_data

        ttk.Label(master, text=_t(f"{_K}.labels.category", default="Category:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.category_var = tk.StringVar(value=expense.get('category') or '')
        ttk.Combobox(master, textvariable=self.category_var, state="readonly",
                     values=list(tm('expenses').EXPENSE_CATEGORIES)).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        ttk.Label(master, text=_t(f"{_K}.labels.description", default="Description:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.description_var = tk.StringVar(value=expense.get('description') or '')
        self.description_entry = ttk.Entry(master, textvariable=self.description_var, width=40)
        self.description_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.amount", default="Amount (£):")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.amount_var = tk.StringVar(value=str(expense.get('amount') or 0))
        ttk.Entry(master, textvariable=self.amount_var, width=40).grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(master, text=_t(f"{_K}.labels.date_yyyy_mm_dd", default="Date (YYYY-MM-DD):")).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=expense.get('date') or '')
        ttk.Entry(master, textvariable=self.date_var, width=40).grid(row=3, column=1, padx=5, pady=5)
        return self.description_entry

    def validate(self):
        if not self.expense_data:
            return False
        return _validate_fields(self, need_category=False)

    def apply(self):
        fields = {'description': self.description_var.get().strip(),
                  'amount': float(self.amount_var.get()), 'date': self.date_var.get()}
        if self.category_var.get():
            fields['category'] = self.category_var.get()
        ok, _ = call(self.parent, tm('expenses').update_expense, self.auth, self.trip_id,
                     self.expense_data['id'], **fields)
        if ok:
            messagebox.showinfo(_t(f"{_K}.dialogs.success", default="Success"), _t(f"{_K}.dialogs.expense_updated_successfully", default="Expense updated successfully!"), parent=self.parent)
            if self.refresh_callback:
                self.refresh_callback()
